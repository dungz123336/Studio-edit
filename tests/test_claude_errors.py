import ast
import contextlib
import io
import json
from pathlib import Path
import re
import threading
import time
import types
import unittest
from unittest.mock import Mock


SOURCE = Path(__file__).resolve().parents[1] / 'app/studio/dong_co.py'
TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))
ENGINE = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'DongCo')
NAMES = {'_che_khoa_loi', '_loi_claude', '_mat_phien_claude'}
HELPERS = [n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name in NAMES]
METHODS = [n for n in ENGINE.body if isinstance(n, ast.FunctionDef) and n.name in {'_lam', '_chay_viec'}]


class Input(io.BytesIO):
    def close(self):
        self.sent = self.getvalue()
        super().close()


class Process:
    def __init__(self, messages, stderr='', code=0):
        self.stdin = Input()
        self.stdout = [json.dumps(m).encode() + b'\n' for m in messages]
        self.stderr = io.BytesIO(stderr.encode())
        self.code = code

    def wait(self):
        return self.code


def result(is_error=False, **fields):
    return {'type': 'result', 'is_error': is_error, **fields}


class ClaudeErrors(unittest.TestCase):
    def setUp(self):
        self.job = {'phien': 'old-session', 'ho_so': 'kenh', 'loi_goc': 'USER REQUEST', 'tin': [], 'luot': []}
        self.messages = []
        self.popen = Mock()
        self.data = types.SimpleNamespace(
            SKILL='app', DATA='no-write', CN='profiles', WIN=True, KHONG_CUA_SO=0,
            doc_viec=lambda vid: self.job,
            sua_viec=lambda vid, action: action(self.job),
            doc_json=lambda *args: {},
            cai_dat=lambda: {},
            py_skill=lambda: 'python.exe',
            env_con=lambda **kwargs: {},
            p_phieu=lambda vid: 'phieu',
            p_phieu2=lambda vid: 'phieu2',
            them_tin=lambda vid, role, text: self.messages.append((role, text)),
            ghi_luot=lambda vid, message: self.job['luot'].append({}),
        )
        self.namespace = dict(
            re=re, json=json, os=__import__('os'), time=time, threading=threading,
            D=self.data, bac_si=types.SimpleNamespace(them_path=lambda: None),
            subprocess=types.SimpleNamespace(Popen=self.popen, PIPE=-1),
            _co_gon=lambda exe: [], _co_tran=lambda exe, cd: [],
            CONG_CU='Read', HUONG_DAN_V3='GUIDE {ho_so}', BUOC_NHIN_NHANH='', BUOC_NHIN_KY='',
            CHU_VIET=re.compile('.*'), gio_mo_lai=lambda text: None,
            LOI_MANG=re.compile(r'ECONNREFUSED|network|\b(?:502|503|504|522|529)\b', re.I),
            co_mang=lambda: True,
            open=lambda *args, **kwargs: contextlib.nullcontext(io.StringIO()),
        )
        exec(compile(ast.Module(body=HELPERS + METHODS, type_ignores=[]), str(SOURCE), 'exec'), self.namespace)
        self.engine = types.SimpleNamespace(exe='claude.exe')
        self.engine._lam = types.MethodType(self.namespace['_lam'], self.engine)
        self.state = {'bi_dung': False}

    def run_processes(self, *processes, **options):
        self.popen.side_effect = processes
        return self.engine._lam('job', 'USER REQUEST', self.state, **options)

    def test_missing_session_in_stderr_retries_fresh_once(self):
        first = Process([result(True)], 'No conversation found with session ID: old-session', 1)
        second = Process([{'type': 'system', 'subtype': 'init', 'session_id': 'new-session'}, result()])
        self.run_processes(first, second)
        self.assertEqual(self.popen.call_count, 2)
        self.assertIn('--resume', self.popen.call_args_list[0].args[0])
        self.assertNotIn('--resume', self.popen.call_args_list[1].args[0])
        self.assertEqual(second.stdin.sent.count(b'USER REQUEST'), 1)
        self.assertEqual(self.job['phien'], 'new-session')
        self.assertEqual([t for role, t in self.messages if role == 'loi'], [])
        self.assertEqual(sum(role == 'he_thong' for role, text in self.messages), 1)
        self.assertEqual([turn['ma'] for turn in self.job['luot']], [1, 0])

    def test_missing_session_in_errors_list_is_not_hidden(self):
        self.run_processes(Process([result(True, errors=['No conversation found with session ID: old-session'])], code=1),
                           Process([result()]))
        self.assertEqual(self.popen.call_count, 2)

    def test_repeated_missing_session_cannot_loop(self):
        self.run_processes(Process([result(True, errors=['No conversation found with session ID: old-session'])], code=1),
                           Process([result(True, errors=['No conversation found with session ID: wrong-session'])], code=1))
        self.assertEqual(self.popen.call_count, 2)
        self.assertIn('wrong-session', [text for role, text in self.messages if role == 'loi'][-1])

    def test_successful_resume_is_not_replaced(self):
        self.run_processes(Process([result()]))
        self.assertEqual(self.popen.call_count, 1)
        self.assertEqual(self.job['phien'], 'old-session')

    def test_authentication_error_is_visible_without_erasing_session(self):
        self.run_processes(Process([result(True, errors=[{'message': '401 invalid API key'}])], code=1))
        self.assertEqual(self.job['phien'], 'old-session')
        self.assertIn('401 invalid API key', self.messages[-1][1])
        self.assertFalse(self.state['loi_mang'])

    def test_oauth_refresh_keeps_existing_bounded_retry_protocol(self):
        transient = self.run_processes(Process([result(True, error={'message': 'OAuth refresh failed'})], code=1),
                                       im_loi_tam=True)
        self.assertTrue(transient)
        self.assertFalse(self.messages)

    def test_rate_limit_is_not_reclassified_as_network(self):
        self.run_processes(Process([result(True, errors=['rate limit reached'])], code=1))
        self.assertTrue(self.state['het_luot'])
        self.assertFalse(self.state['loi_mang'])

    def test_synthetic_api_error_is_used_when_result_has_no_details(self):
        synthetic = {'type': 'assistant', 'message': {'model': '<synthetic>',
                     'content': [{'type': 'text', 'text': 'API Error: ECONNREFUSED'}]}}
        self.run_processes(Process([synthetic, result(True)], code=1))
        self.assertTrue(self.state['loi_mang'])
        self.assertIn('ECONNREFUSED', self.messages[-1][1])

    def test_error_event_without_result_is_used(self):
        self.run_processes(Process([{'type': 'error', 'error': {'message': 'Provider rejected this model'}}], code=1))
        self.assertIn('Provider rejected this model', self.messages[-1][1])

    def test_522_is_short_and_waits_two_minutes(self):
        self.run_processes(Process([result(True, errors=['API Error: 522 ' + '<html>noise</html>' * 1000])], code=1))
        self.assertTrue(self.state['loi_mang'])
        self.assertEqual(self.state['loi_mang_cho'], 120)
        self.assertIn('HTTP 522', self.messages[-1][1])
        self.assertNotIn('<html>', self.messages[-1][1])
        self.assertLess(len(self.messages[-1][1]), 250)

    def test_structured_522_status_is_understood(self):
        message = self.namespace['_loi_claude']({'error': {'status_code': 522, 'message': 'timed out'}})
        self.assertIn('HTTP 522', message)

    def test_error_secrets_are_redacted(self):
        key = 'sk-ant-' + 'A' * 40
        message = self.namespace['_loi_claude']({'errors': [f'Authorization: Bearer {key}', 'api_key=abc-secret-value']})
        self.assertNotIn(key, message)
        self.assertNotIn('abc-secret-value', message)

    def run_network_loop(self, stop_during_wait=False):
        state = {'bi_dung': False, 'loi_mang': False}
        calls, sleeps = [], []
        clock = {'now': 0}

        def sleep(seconds):
            sleeps.append(seconds)
            clock['now'] += seconds
            if stop_during_wait:
                state['bi_dung'] = True

        def fake_lam(vid, text, st, **kwargs):
            calls.append(text)
            st['loi_mang'] = len(calls) == 1
            if st['loi_mang']:
                st['loi_mang_cho'] = 120
            return False

        self.namespace['time'] = types.SimpleNamespace(monotonic=lambda: clock['now'], sleep=sleep)
        engine = types.SimpleNamespace(chay={'job': state}, cho_viec={}, khoa=threading.Lock(),
                                       _lam=fake_lam, _con_do=lambda vid, st: False)
        self.namespace['_chay_viec'](engine, {'viec': 'job', 'chu': 'USER REQUEST'})
        return calls, sleeps

    def test_522_backoff_waits_120_seconds_before_retry(self):
        calls, sleeps = self.run_network_loop()
        self.assertEqual(len(calls), 2)
        self.assertEqual(sum(sleeps), 120)
        self.assertTrue(any('Máy chủ API' in text and '2 phút' in text for role, text in self.messages))
        self.assertIn('HTTP 522', calls[1])

    def test_stop_interrupts_522_wait_within_one_second(self):
        calls, sleeps = self.run_network_loop(stop_during_wait=True)
        self.assertEqual(len(calls), 1)
        self.assertEqual(sum(sleeps), 1)


if __name__ == '__main__':
    unittest.main()
