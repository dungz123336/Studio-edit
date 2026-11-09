import ast
import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import types
import unittest
import uuid
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / 'app/studio/server.py'
TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))
PICKER = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'chon_tep')
DIALOG_SCRIPT = ast.literal_eval(next(n.value for n in TREE.body if isinstance(n, ast.Assign)
                                    and any(isinstance(t, ast.Name) and t.id == 'CHON_TEP' for t in n.targets)))


class PickerTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).parent / ('picker-test-' + uuid.uuid4().hex)
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root)
        self.video = self.root / 'clip chính.mp4'
        self.video.write_bytes(b'test')
        self.audio = self.root / 'sample.mp3'
        self.audio.write_bytes(b'test')
        self.lock = threading.Lock()
        self.run = Mock(return_value=subprocess.CompletedProcess([], 0, json.dumps([str(self.video)]).encode(), b''))
        self.namespace = dict(subprocess=types.SimpleNamespace(run=self.run, TimeoutExpired=subprocess.TimeoutExpired),
                              sys=sys, os=os, json=json, CHON_TEP=DIALOG_SCRIPT, KHOA_CHON_TEP=self.lock,
                              DUOI_AUDIO=('.mp3',), DUOI_VIDEO=('.mp4',), DUOI_NHAN=('.mp4', '.mp3'))
        exec(compile(ast.Module(body=[PICKER], type_ignores=[]), str(SOURCE), 'exec'), self.namespace)
        self.choose = self.namespace['chon_tep']

    def test_valid_unicode_file_returns_path(self):
        self.assertEqual(self.choose(), [str(self.video)])
        self.assertFalse(self.lock.locked())
        self.assertEqual(self.run.call_args.kwargs['env']['PYTHONUTF8'], '1')

    def test_cancel_is_empty_result(self):
        self.run.return_value.stdout = b'[]'
        self.assertEqual(self.choose(), [])

    def test_second_request_is_rejected_without_new_process(self):
        self.lock.acquire()
        with self.assertRaisesRegex(RuntimeError, 'đang mở'):
            self.choose()
        self.run.assert_not_called()
        self.lock.release()

    def test_native_failure_is_visible_and_lock_released(self):
        self.run.return_value = subprocess.CompletedProcess([], 1, b'', b'Traceback\nTclError: cannot open display')
        with self.assertRaisesRegex(RuntimeError, 'TclError: cannot open display'):
            self.choose()
        self.assertFalse(self.lock.locked())

    def test_empty_malformed_and_wrong_typed_output_are_errors(self):
        for output in (b'', b'not-json', b'{}', b'[123]'):
            with self.subTest(output=output):
                self.run.return_value.stdout = output
                with self.assertRaisesRegex(RuntimeError, 'kết quả hợp lệ'):
                    self.choose()
                self.assertFalse(self.lock.locked())

    def test_timeout_releases_lock_and_next_attempt_can_succeed(self):
        self.run.side_effect = subprocess.TimeoutExpired('picker', 900)
        with self.assertRaisesRegex(RuntimeError, 'hết thời gian'):
            self.choose()
        self.assertFalse(self.lock.locked())
        self.run.side_effect = None
        self.assertEqual(self.choose(), [str(self.video)])

    def test_spawn_failure_is_visible(self):
        self.run.side_effect = OSError('Python missing')
        with self.assertRaisesRegex(RuntimeError, 'Python missing'):
            self.choose()
        self.assertFalse(self.lock.locked())

    def test_file_types_and_directory_are_filtered(self):
        self.run.return_value.stdout = json.dumps([str(self.video), str(self.audio), str(self.root), 'missing.mp4']).encode()
        self.assertEqual(self.choose('video'), [str(self.video)])
        self.assertEqual(self.choose('audio'), [str(self.audio)])
        self.assertEqual(self.choose('tat-ca'), [str(self.video), str(self.audio)])
        self.assertEqual(self.choose('thu-muc'), [str(self.root)])


class NativeDialogOwnershipTests(unittest.TestCase):
    def run_dialog(self, kind, fail=False):
        root = Mock()
        dialog = types.ModuleType('tkinter.filedialog')
        method = Mock(side_effect=RuntimeError('dialog failed') if fail else None,
                      return_value=['clip.mp4'] if kind == 'video' else 'sample.mp3')
        dialog.askopenfilenames = method
        dialog.askopenfilename = method
        dialog.askdirectory = method
        tkinter = types.ModuleType('tkinter')
        tkinter.Tk = Mock(return_value=root)
        tkinter.filedialog = dialog
        modules = {'tkinter': tkinter, 'tkinter.filedialog': dialog}
        with patch.dict(sys.modules, modules), patch.object(sys, 'argv', ['picker', kind]), contextlib.redirect_stdout(io.StringIO()):
            try:
                exec(DIALOG_SCRIPT, {})
            except (RuntimeError, SystemExit):
                pass
        self.assertIs(method.call_args.kwargs['parent'], root)
        root.update.assert_called_once()
        root.destroy.assert_called_once()

    def test_video_dialog_has_parent_and_destroys_root(self):
        self.run_dialog('video')

    def test_single_audio_dialog_has_parent_and_destroys_root(self):
        self.run_dialog('audio')

    def test_folder_dialog_has_parent_and_destroys_root(self):
        self.run_dialog('thu-muc')

    def test_dialog_failure_still_destroys_root(self):
        self.run_dialog('video', fail=True)


if __name__ == '__main__':
    unittest.main()
