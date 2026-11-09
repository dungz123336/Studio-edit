"""External Studio launcher with explicit provenance for recorded local changes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
import uuid


ROOT = Path(__file__).resolve().parent
APP = ROOT / "app"
DATA = ROOT / "data"
RUNTIME = Path(os.environ.get("STUDIO_RUNTIME_HOME") or ROOT / "runtime").resolve()
PYTHON = Path(os.environ.get("STUDIO_PYTHON") or APP / ".venv" / "Scripts" / "python.exe").resolve()
PORT = 4788
URL = f"http://127.0.0.1:{PORT}"
STATE = DATA / "portable-instance.json"
WEB_MARKER = APP / "studio" / "web" / "portable-instance.json"
MARKER_URL = URL + "/portable-instance.json"
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def read_json(path: Path, default=None):
    if not path.exists():
        return {} if default is None else default
    with path.open(encoding="utf-8-sig") as stream:
        result = json.load(stream)
    if not isinstance(result, dict):
        raise RuntimeError(f"Tệp cấu hình không phải đối tượng JSON: {path}")
    return result


def write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def env_for_app():
    result = dict(os.environ)
    result.update(
        STUDIO_PORT=str(PORT),
        STUDIO_DATA=str(DATA),
        PYTHONUTF8="1",
        PYTHONIOENCODING="utf-8",
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    result.pop("PYTHONHOME", None)
    result.pop("PYTHONPATH", None)
    result.pop("CAU_HINH", None)
    result.pop("HO_SO", None)
    git_bash = ROOT / "git" / "bin" / "bash.exe"
    if git_bash.is_file():
        result["CLAUDE_CODE_GIT_BASH_PATH"] = str(git_bash)
    result["PATH"] = os.pathsep.join(
        [str(ROOT / "tools"), str(ROOT / "git" / "cmd"), str(ROOT / "git" / "bin"),
         str(PYTHON.parent), str(RUNTIME), result.get("PATH", "")]
    )
    return result


def require_files():
    required = [RUNTIME / "python.exe", PYTHON, APP / "studio" / "mo.py"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise RuntimeError("Môi trường chưa đủ; chạy start.bat để thiết lập: " + ", ".join(missing))
    tools = ("ffmpeg", "ffprobe", "uv", "claude", "git")
    absent = [name for name in tools if not shutil.which(name, path=env_for_app()["PATH"])]
    if absent:
        raise RuntimeError("Thiếu công cụ; chạy start.bat để thiết lập: " + ", ".join(absent))


def rebase_python():
    cfg = APP / ".venv" / "pyvenv.cfg"
    cfg.write_text(
        f"home = {RUNTIME}\n"
        "implementation = CPython\n"
        f"version_info = {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}\n"
        "include-system-site-packages = false\n",
        encoding="utf-8",
    )


def prepare_config():
    DATA.mkdir(parents=True, exist_ok=True)
    projects = ROOT / "projects"
    projects.mkdir(parents=True, exist_ok=True)
    config_path = APP / "cau-hinh.json"
    config = read_json(config_path)
    config["du_an"] = str(projects)
    for section in ("v3", "kho"):
        if not isinstance(config.get(section), dict):
            if section in config:
                raise RuntimeError(f"Mục {section} trong {config_path.name} phải là đối tượng JSON.")
            config[section] = {}
    config["v3"].update(du_an=str(projects), du_lieu=str(DATA / "v3"))
    config["kho"]["duong_dan"] = str(APP / "tai-nguyen")
    write_json(config_path, config)

    settings_path = DATA / "cai-dat.json"
    if not settings_path.exists():
        write_json(settings_path, {"cong_kho": 4790, "don_rac": {"tu_dong": False}})


def state_for_current_path():
    state = read_json(STATE)
    root_hash = hashlib.sha256(str(ROOT).casefold().encode("utf-8")).hexdigest()
    if state.get("root_hash") != root_hash or not state.get("instance"):
        state = {"schema": 1, "root_hash": root_hash, "instance": uuid.uuid4().hex}
    return state


def save_state(state: dict):
    write_json(STATE, state)
    # This extra static data file identifies this installation; no signed file is edited.
    write_json(WEB_MARKER, {"instance": state["instance"], "root_hash": state["root_hash"]})


def port_in_use():
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", PORT)) == 0


def is_our_server(state: dict):
    try:
        with HTTP.open(MARKER_URL, timeout=2) as response:
            remote = json.load(response)
        return (
            isinstance(remote, dict)
            and remote.get("instance") == state.get("instance")
            and remote.get("root_hash") == state.get("root_hash")
        )
    except Exception:
        return False


def run_app_python(arguments, *, capture=False, timeout=None):
    return subprocess.run(
        [str(PYTHON), *map(str, arguments)],
        cwd=APP,
        env=env_for_app(),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
        timeout=timeout,
        creationflags=0x08000000 if os.name == "nt" else 0,
    )


CHECK_CODE = r'''
import hashlib, importlib, json, pathlib
root = pathlib.Path.cwd()
report = {"imports": {}, "version": (root / "VERSION").read_text(encoding="utf-8").strip(), "source_changes": [], "source_missing": []}
modules = ["faster_whisper", "av", "mediapipe", "numpy", "PIL", "scipy", "fontTools", "requests", "cryptography", "skia", "onnxruntime"]
for name in modules:
    try:
        module = importlib.import_module(name)
        if name == "av" and int(module.__version__.split(".")[0]) >= 15:
            raise RuntimeError("cần av 14.2.0 theo cấu hình dự án")
        report["imports"][name] = "ok"
    except Exception as error:
        report["imports"][name] = type(error).__name__ + ": " + str(error)
try:
    manifest = json.loads((root / "TEP-GOI.json").read_text(encoding="utf-8"))
    for relative, original in manifest.get("tep", {}).items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            report["source_missing"].append(relative)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != original:
            report["source_changes"].append(relative)
except Exception as error:
    report["source_note"] = type(error).__name__ + ": " + str(error)
print("GIT_CHECK " + json.dumps(report, ensure_ascii=False))
'''


def check_runtime():
    print("Đang kiểm tra Python và thư viện...", flush=True)
    completed = run_app_python(["-c", CHECK_CODE], capture=True, timeout=180)
    report = None
    for line in (completed.stdout or "").splitlines():
        if line.startswith("GIT_CHECK "):
            report = json.loads(line[len("GIT_CHECK "):])
    if report is None:
        print((completed.stdout or "Không nhận được kết quả kiểm tra.")[-6000:])
        raise RuntimeError("Môi trường Python không chạy được.")
    print("Phiên bản: " + report.get("version", "?"))
    print("Nguồn: bản mã nguồn tùy chỉnh của chủ repository; Git quản lý các lần sửa mã.")
    if report.get("source_changes") or report.get("source_missing"):
        print(f"Đối chiếu bản gốc: {len(report['source_changes'])} tệp đã sửa, {len(report['source_missing'])} tệp thiếu; thông tin này không khóa việc sửa mã trong Git.")
    failed = {name: detail for name, detail in report["imports"].items() if detail != "ok"}
    for name, detail in failed.items():
        print(f"Thiếu/lỗi thư viện {name}: {detail}")
    if completed.returncode or failed:
        raise RuntimeError("Kiểm tra thư viện chưa đạt; chạy lại start.bat để thiết lập.")
    print(f"Thư viện Python: đủ {len(report['imports'])} mô-đun.")
    return report


def index_has_items():
    database = DATA / "v3" / "kho-chi-muc" / "kho.sqlite"
    if not database.is_file():
        return False
    try:
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
            return connection.execute("SELECT COUNT(*) FROM muc").fetchone()[0] > 0
    except sqlite3.Error:
        return False


def ensure_index(state: dict):
    manifest_hash = hashlib.sha256((APP / "TEP-GOI.json").read_bytes()).hexdigest()
    if state.get("index_manifest") == manifest_hash and index_has_items():
        return
    print("Đang chuẩn bị chỉ mục tài nguyên đi kèm, lần đầu có thể mất vài phút...", flush=True)
    completed = run_app_python([APP / "v3" / "kho" / "lap.py"], timeout=1200)
    if completed.returncode or not index_has_items():
        raise RuntimeError("Chưa lập được chỉ mục tài nguyên. Xem thông báo ở trên.")
    state["index_manifest"] = manifest_hash
    save_state(state)


def stop_server(state: dict):
    if not port_in_use():
        print("Studio portable đã dừng.")
        return
    if not is_our_server(state):
        raise RuntimeError(f"Cổng {PORT} đang do ứng dụng khác sử dụng; không gửi lệnh tắt.")
    result = run_app_python([APP / "studio" / "mo.py", "--tat"], timeout=45)
    if result.returncode or port_in_use():
        raise RuntimeError("Studio chưa dừng xong. Đóng cửa sổ Studio và thử lại.")
    print("Đã dừng Studio portable.")


def main():
    parser = argparse.ArgumentParser(description="Mở Studio portable và kiểm tra nguồn gói cùng các thay đổi cục bộ đã ghi nhận.")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check", action="store_true", help="Kiểm tra ngoại tuyến, không bật máy chủ")
    action.add_argument("--stop", action="store_true", help="Dừng đúng máy chủ portable này")
    parser.add_argument("--no-browser", action="store_true", help="Chỉ bật máy chủ, không mở trình duyệt")
    options = parser.parse_args()
    require_files()
    rebase_python()
    state = state_for_current_path()
    if options.stop:
        stop_server(state)
        return 0
    prepare_config()
    if options.check:
        check_runtime()
        return 0
    running = port_in_use()
    if running and not is_our_server(state):
        raise RuntimeError(f"Cổng {PORT} đang được ứng dụng khác sử dụng. Đóng ứng dụng đó rồi mở lại start.bat.")
    if not running:
        check_runtime()
        save_state(state)
        ensure_index(state)
    args = [APP / "studio" / "mo.py"]
    if options.no_browser:
        args.append("--chi-bat")
    completed = run_app_python(args, timeout=45)
    if completed.returncode:
        raise RuntimeError(f"Không mở được Studio. Nhật ký: {DATA / 'server.log'}")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not is_our_server(state):
        time.sleep(0.2)
    if not is_our_server(state):
        raise RuntimeError(f"Chưa xác nhận được đúng máy chủ. Nhật ký: {DATA / 'server.log'}")
    print(f"Studio đã mở: {URL}")
    if (APP / "LOCAL-CHANGES.json").exists():
        print("Đây là bản tùy chỉnh cục bộ của người dùng. Đăng nhập Claude để dùng AI; dừng bằng stop.bat.")
    else:
        print("Dừng bằng stop.bat. Cần kích hoạt chính thức và đăng nhập Claude để dựng video.")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"LỖI: {error}", file=sys.stderr)
        raise SystemExit(1)
