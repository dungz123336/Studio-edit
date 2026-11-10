import contextlib
import ast
import importlib.util
import io
import os
from pathlib import Path
import shutil
import sys
import types
import unittest
import uuid
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "app" / "studio"


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SelectedRuntime(unittest.TestCase):
    def setUp(self):
        cache = ROOT / ".cache"
        cache.mkdir(exist_ok=True)
        self.root = cache / ("test-selected-runtime-" + uuid.uuid4().hex)
        self.assertEqual(self.root.resolve().parent, cache.resolve())
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root)
        self.app = self.root / "app"
        self.selected = self.root / ".runtime" / "system-venv"
        self.python = self.selected / "Scripts" / "python.exe"
        self.base = self.root / "installed-python"
        self.legacy = self.app / ".venv" / "pyvenv.cfg"
        for path, content in (
            (self.python, "selected interpreter"),
            (self.selected / "pyvenv.cfg", f"home = {self.base}\ninclude-system-site-packages = false\n"),
            (self.base / "python.exe", "installed interpreter"),
            (self.legacy, "legacy environment must stay untouched\n"),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, STUDIO_PYTHON=str(self.python), STUDIO_DATA=str(self.root / "data")))
        self.stack.enter_context(patch.object(sys, "executable", str(self.python)))
        self.stack.enter_context(patch.object(sys, "prefix", str(self.selected)))
        # App scripts have their own directory on sys.path, rather than the repo root.
        self.stack.enter_context(patch.object(sys, "path", [str(STUDIO), *sys.path]))
        self.helper = load("selected_runtime_helper", "app/studio/moi_truong.py")
        self.stack.enter_context(patch.dict(sys.modules, moi_truong=self.helper))

    def test_selection_must_match_running_venv_and_cannot_fallback(self):
        self.assertEqual(self.helper.python_da_chon(), str(self.python))
        with patch.object(sys, "executable", str(self.base / "python.exe")):
            with self.assertRaisesRegex(RuntimeError, "không khớp"):
                self.helper.python_da_chon()
        with patch.dict(os.environ, STUDIO_PYTHON="relative/python.exe"):
            with self.assertRaisesRegex(RuntimeError, "tuyệt đối"):
                self.helper.python_da_chon()

    def test_current_pythonw_may_use_console_sibling_in_same_venv(self):
        if os.name != "nt":
            self.skipTest("Windows python/pythonw pair")
        with patch.object(sys, "executable", str(self.python.with_name("pythonw.exe"))):
            self.assertEqual(self.helper.python_da_chon(), str(self.python))
        with patch.object(sys, "prefix", str(self.base)):
            with self.assertRaises(RuntimeError):
                self.helper.python_da_chon()

    def test_subprocess_selection_ignores_existing_legacy_interpreter(self):
        legacy_python = self.legacy.parent / "Scripts" / "python.exe"
        legacy_python.parent.mkdir(parents=True)
        legacy_python.write_text("blocked launcher", encoding="utf-8")
        data = load("selected_runtime_data", "app/studio/du_lieu.py")
        self.assertEqual(data.py_skill(), str(self.python))
        self.assertTrue(data.da_cai())
        self.assertEqual(data.env_con()["STUDIO_PYTHON"], str(self.python))

    def test_doctor_and_healer_keep_selected_cfg_and_do_not_search_uv(self):
        healer = load("selected_runtime_healer", "app/studio/sua_venv.py")
        self.stack.enter_context(patch.dict(sys.modules, sua_venv=healer))
        doctor = load("selected_runtime_doctor", "app/studio/bac_si.py")
        selected_before = (self.selected / "pyvenv.cfg").read_bytes()
        legacy_before = self.legacy.read_bytes()
        with patch.object(healer, "ung_vien", side_effect=AssertionError("must not search another Python")), \
                patch.object(healer.subprocess, "run", side_effect=AssertionError("must not install another Python")):
            self.assertEqual(doctor.VENV_PY, str(self.python))
            self.assertTrue(doctor.k_venv()[0])
            self.assertEqual(doctor.s_venv()[0], 0)
            (self.base / "python.exe").unlink()
            self.assertFalse(healer.chua(cai_neu_thieu=True)[0])
            self.assertEqual(doctor.s_venv()[0], 1)
        self.assertEqual((self.selected / "pyvenv.cfg").read_bytes(), selected_before)
        self.assertEqual(self.legacy.read_bytes(), legacy_before)

    def test_setup_and_platform_report_use_selected_python(self):
        installer = load("selected_runtime_installer", "app/scripts/cai_dat.py")
        platform_report = load("selected_runtime_platform", "app/scripts/nen_tang.py")
        healer = load("selected_runtime_healer", "app/studio/sua_venv.py")
        self.assertEqual(installer.PY, str(self.python))
        self.assertEqual(platform_report.python_venv(), str(self.python))
        commands = []

        def stop_at_pip(command, **kwargs):
            commands.append(command)
            return types.SimpleNamespace(returncode=1)

        class Output(io.StringIO):
            def reconfigure(self, **kwargs):
                pass

        with patch.dict(sys.modules, sua_venv=healer), \
                patch.object(installer.shutil, "which", side_effect=lambda name: "tools/" + name), \
                patch.object(installer, "chay", side_effect=stop_at_pip), \
                contextlib.redirect_stdout(Output()):
            self.assertEqual(installer.main(), 1)
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0][1:5], ["pip", "install", "--python", str(self.python)])

    def test_launcher_preserves_both_cfg_files_and_propagates_selected_python(self):
        launcher = load("selected_runtime_launcher", "launcher.py")
        launcher.ROOT, launcher.APP = self.root, self.app
        launcher.PYTHON, launcher.RUNTIME = self.python, self.base
        selected_before = (self.selected / "pyvenv.cfg").read_bytes()
        legacy_before = self.legacy.read_bytes()
        launcher.rebase_python()
        self.assertEqual((self.selected / "pyvenv.cfg").read_bytes(), selected_before)
        self.assertEqual(self.legacy.read_bytes(), legacy_before)
        self.assertEqual(launcher.env_for_app()["STUDIO_PYTHON"], str(self.python))

    def test_old_shortcut_migration_is_disabled_for_selected_environment(self):
        opener = load("selected_runtime_opener", "app/studio/mo.py")
        with patch.object(opener.subprocess, "run", side_effect=AssertionError("must not alter shortcuts")):
            self.assertEqual(opener.doi_loi_tat_cu(), 0)

    def test_v2_cli_does_not_reexecute_existing_legacy_python(self):
        legacy_python = self.legacy.parent / "Scripts" / "python.exe"
        legacy_python.parent.mkdir(parents=True)
        legacy_python.write_text("blocked launcher", encoding="utf-8")
        tree = ast.parse((ROOT / "app/v2/st.py").read_text(encoding="utf-8"))
        prelude = []
        for node in tree.body:
            if isinstance(node, ast.Import) and any(item.name == "chung" for item in node.names):
                break
            prelude.append(node)
        code = compile(ast.Module(body=prelude, type_ignores=[]), "app/v2/st.py", "exec")
        namespace = {"__name__": "__main__", "__file__": str(self.app / "v2/st.py")}
        with patch("subprocess.call", side_effect=AssertionError("must not execute blocked legacy Python")):
            exec(code, namespace)
        self.assertEqual(namespace["_VENV"], str(self.python))

        common = load("selected_runtime_v2_common", "app/v2/chung.py")
        common.SKILL = str(self.app)
        self.assertEqual(common.python_skill(), str(self.python))

    def test_unselected_v2_cli_keeps_original_interpreter_switch(self):
        legacy_python = self.legacy.parent / "Scripts" / "python.exe"
        legacy_python.parent.mkdir(parents=True)
        legacy_python.write_text("legacy launcher", encoding="utf-8")
        tree = ast.parse((ROOT / "app/v2/st.py").read_text(encoding="utf-8"))
        prelude = []
        for node in tree.body:
            if isinstance(node, ast.Import) and any(item.name == "chung" for item in node.names):
                break
            prelude.append(node)
        code = compile(ast.Module(body=prelude, type_ignores=[]), "app/v2/st.py", "exec")
        called = Mock(return_value=19)
        with patch.dict(os.environ, STUDIO_PYTHON=""), patch("subprocess.call", called):
            with self.assertRaises(SystemExit) as raised:
                exec(code, {"__name__": "__main__", "__file__": str(self.app / "v2/st.py")})
        self.assertEqual(raised.exception.code, 19)
        self.assertEqual(called.call_args.args[0][0], str(legacy_python))

    def test_no_explicit_selection_preserves_legacy_behavior(self):
        with patch.dict(os.environ, STUDIO_PYTHON=""):
            self.assertIsNone(self.helper.python_da_chon())
            healer = load("unselected_runtime_healer", "app/studio/sua_venv.py")
            self.assertEqual(healer.VENV, str(STUDIO.parent / ".venv"))


if __name__ == "__main__":
    unittest.main()
