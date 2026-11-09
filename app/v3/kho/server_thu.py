# -*- coding: utf-8 -*-
"""Máy chủ KHO (Studio tự bật, cổng 4789; chạy tay mặc định 4801): /api/kho/* → kho/api.py, còn lại tĩnh từ v3/web-kho/.
    python kho/server_thu.py [cổng] [-q]
Mở: http://127.0.0.1:4801/kho.html
1.2.21: ghi PID + cổng vào <kho_chi_muc>/server_thu.pid (dòng 1 = pid, dòng 2 = cổng) để Studio tắt được khi tắt/cập nhật; xoá khi thoát."""
import os, sys, json, threading, types
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit, unquote
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung
from kho import api

CONG = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 4801
TINH = os.path.join(chung.APP, "web-kho")          # giao diện kho (nhúng vào khung Kho của Studio)


def duong_pid():
    return os.path.join(chung.duong("kho_chi_muc"), f"server_thu-{CONG}.pid")   # 1.2.21 (R1): tệp pid THEO CỔNG — hai Studio/kho khác cổng không giết nhau


def ghi_pid():
    p = duong_pid()
    try:
        tmp = p + f".{os.getpid()}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(f"{os.getpid()}\n{CONG}\n")
        os.replace(tmp, p)
    except OSError:
        pass


def xoa_pid():
    p = duong_pid()
    try:
        with open(p, "r", encoding="utf-8") as f:
            cua_toi = f.readline().strip() == str(os.getpid())
        if cua_toi:                                # R3 1.2.21: xoá SAU khi đóng tệp (Windows: xoá tệp đang mở → WinError 32, tệp pid không bao giờ được xoá)
            os.remove(p)
    except OSError:
        pass


def _lenh_cua_pid(pid):
    """dòng lệnh của tiến trình pid ("" nếu không đọc được) — R3 1.2.21"""
    import subprocess
    try:
        if os.name == "nt":
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"],
                               capture_output=True, text=True, timeout=20, creationflags=getattr(chung, "_NO_WINDOW", 0))
        else:
            r = subprocess.run(["ps", "-o", "command=", "-p", str(int(pid))], capture_output=True, text=True, timeout=10)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def _la_server_thu(pid):
    return "server_thu" in _lenh_cua_pid(pid)


def _pid_song(pid):
    """còn sống? (Windows: os.kill(pid, 0) là TerminateProcess — không dùng)"""
    if os.name == "nt":
        import subprocess
        try:
            r = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/NH", "/FO", "CSV"], capture_output=True, text=True, timeout=10,
                               creationflags=getattr(chung, "_NO_WINDOW", 0))
            return f'"{int(pid)}"' in (r.stdout or "")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def tat_ban_cu():
    """bản server_thu cũ còn chạy (pid trong tệp, bị bỏ rơi khi Studio cập nhật/tắt cứng) → tắt trước khi mở cổng.
    Windows cho 2 tiến trình cùng bind 1 cổng (SO_REUSEADDR) → request đi vào bản CŨ chạy mã cũ, nên phải tắt thật."""
    p = duong_pid()
    try:
        with open(p, "r", encoding="utf-8") as f:
            pid = int(f.readline().strip() or 0)
    except (OSError, ValueError):
        return
    if not pid or pid == os.getpid():
        return
    if not _la_server_thu(pid):                 # R3 1.2.21: tệp pid cũ (kill cứng) → pid có thể đã thuộc tiến trình KHÁC → không giết bừa
        try:
            os.remove(p)
        except OSError:
            pass
        return
    try:
        import signal as _sg
        os.kill(pid, getattr(_sg, "SIGTERM", 15))
        import time as _t
        for _ in range(30):
            if not _pid_song(pid):
                break
            _t.sleep(0.1)
        sys.stderr.write(f"(server_thu: đã tắt bản cũ pid {pid})\n")
    except OSError:
        pass
    try:
        os.remove(p)
    except OSError:
        pass


class _Sv(ThreadingHTTPServer):
    allow_reuse_address = os.name != "nt"      # Windows: không cho bind chồng cổng đang có chủ khác → lỗi rõ thay vì chạy mà không nhận request


class Xl(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def handle(self):
        try:
            super().handle()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, TimeoutError):
            pass

    def log_message(self, fmt, *a):
        if "-q" not in sys.argv:
            sys.stderr.write("%s %s\n" % (self.command, self.path[:120]))

    def _gui(self, status, mime, body, hdr=None):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        hdr = dict(hdr or {})
        if isinstance(body, (bytes, bytearray)):
            hdr.setdefault("Content-Length", str(len(body)))
        elif "Content-Length" not in hdr:
            hdr["Connection"] = "close"
        for k, v in hdr.items():
            self.send_header(k, v)
        self.end_headers()
        if self.command == "HEAD":
            return
        try:
            if isinstance(body, (bytes, bytearray)):
                self.wfile.write(body)
            else:
                for khuc in body:
                    self.wfile.write(khuc)
                    self.wfile.flush()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            pass
        if "Connection" in hdr:
            self.close_connection = True

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        self.do_GET()

    def do_GET(self):
        u = urlsplit(self.path)
        if u.path.startswith("/api/kho/"):
            st, mime, body, hdr = api.xu_ly_day_du(u.path, u.query, {"Range": self.headers.get("Range")})
            return self._gui(st, mime, body, hdr)
        p = unquote(u.path).lstrip("/") or "kho.html"
        p = os.path.normpath(os.path.join(TINH, p))
        if not p.startswith(os.path.normpath(TINH)) or not os.path.isfile(p):
            return self._gui(404, "text/plain; charset=utf-8", "không có".encode("utf-8"))
        with open(p, "rb") as f:
            body = f.read()
        return self._gui(200, api._mime(p) if not p.endswith((".html", ".js", ".css")) else
                         {"html": "text/html; charset=utf-8", "js": "text/javascript; charset=utf-8", "css": "text/css; charset=utf-8"}[p.rsplit(".", 1)[1]],
                         body, {"Cache-Control": "no-cache"})


if __name__ == "__main__":
    import atexit, signal
    tat_ban_cu()
    try:
        sv = _Sv(("127.0.0.1", CONG), Xl)
    except OSError as ex:
        print(f"Kho thử: không mở được cổng {CONG} ({ex}) — cổng đang bị tiến trình khác giữ", flush=True)
        sys.exit(1)
    sv.daemon_threads = True
    ghi_pid()
    atexit.register(xoa_pid)
    for _sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGBREAK", None)):
        if _sig is not None:
            try:
                signal.signal(_sig, lambda *_: sys.exit(0))
            except (ValueError, OSError):
                pass
    print(f"Kho thử: http://127.0.0.1:{CONG}/kho.html  (tĩnh: {TINH}; pid {os.getpid()} → {duong_pid()})", flush=True)
    try:
        sv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        xoa_pid()
