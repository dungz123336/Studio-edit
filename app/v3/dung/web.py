# -*- coding: utf-8 -*-
"""Lớp MỞ HTML/CSS/SVG (kieu "web") — AI tự sáng tác motion graphics bằng trang web, máy chụp từng khung bằng trình duyệt headless.

Công thức:
  {"kieu":"web","t0":2,"t1":6,"noi_dung":{"html":"lop-rieng/bang-so.html" | "ma":"<html>…</html>", "props":{...}},
   "vi_tri":{"anchor":"mc","x":0.5,"y":0.4,"w":0.9,"h":0.3}, "anim":{...}}
  · w,h ≤ 1 = tỉ lệ khung, > 1 = px. Trang render đúng hộp w×h, nền trong suốt.
  · props: chuỗi "kho:<id>" được đổi thành URL file của tài nguyên kho.

Trang nhận (chèn đầu <head>, trước mã của trang):
  CSS: --mau-nhan --mau-nhan2 --mau-sang --mau-toi · --font-tieu-de --font-nhan --font-phu-de --font-than --font-script
       (font của phong cách video, nạp bằng @font-face từ file) · --W --H (px hộp) · --khung-W --khung-H (px khung video)
  JS : window.PROPS · window.KHUNG {w,h,W,H,dur,fps} · window.TOKENS · ganTimeline(anim, batDau=0)
  Trang định nghĩa window.veTai(t, dur) (giây từ t0) đặt trạng thái tất định. CSS animation / Element.animate được máy tự tua
  theo t (đồng hồ ảo, xem web_khung.js). Không có veTai + không hoạt ảnh → lớp tĩnh, chụp 1 lần.

Kết xuất: MỘT tiến trình Edge/Chrome headless (--headless=new) cho cả lần dựng (dùng chung giữa các luồng VÀ các tiến trình con
của ProcessPoolExecutor qua tệp đăng ký theo PID gốc); mỗi lớp một tab + một kết nối DevTools riêng → an toàn song song.
Mỗi khung: Runtime.evaluate __studio.dat(t,dur) → khoá trạng thái; khoá đổi → Page.captureScreenshot PNG → numpy BGRA thẳng.
Không cần gói ngoài (client WebSocket tối giản bằng thư viện chuẩn).

Thử:  python v3/dung/web.py --thu <file.html> --ra <thư mục> [--w 1080 --h 600 --dur 3 --props '{...}' --do 60]
"""
import os, sys, io, re, json, time, base64, socket, struct, threading, hashlib, atexit, shutil, subprocess, tempfile, weakref
import urllib.request, urllib.parse
from pathlib import Path

import numpy as np
import cv2
import skia

try:
    import chung
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import chung
from dung import lop as _lop
from dung.lop import Lop

THU_MUC = os.path.dirname(os.path.abspath(__file__))
VAI_MAU = ("nhan", "nhan2", "sang", "toi")      # 1.2.21: KHÔNG còn MAU_MAC_DINH — màu thiếu trong phong cách video → quyet_dinh bang_mau.<vai> → thieu_truong
VAI_FONT = ("tieu_de", "nhan", "phu_de", "than", "script")
HAN_TAI = 20.0            # giây chờ trang tải + font + sanSang (vật lý: chặn treo)
HAN_KHUNG = 8.0           # giây cho mỗi lệnh JS của khung (veTai treo / vòng lặp vô hạn → lỗi, không treo dựng)
HAN_CHUP = 20.0           # giây cho mỗi lần chụp (máy bận vẫn kịp)
LOI_TOI_DA = 6
# 1.2.21: video cho trang web (VP9 webm) — chất lượng/cỡ là cấu hình máy: cau-hinh.json v3.web_video {crf, cao_toi_da, cpu_used, deadline}
WEB_VIDEO_MAC_DINH = {"crf": 34, "cao_toi_da": 720, "cpu_used": 8, "deadline": "realtime"}


def cau_hinh_web_video():
    c = dict(WEB_VIDEO_MAC_DINH)
    try:
        c.update(chung.cau_hinh().get("web_video") or {})
    except Exception:
        pass
    return c


class LoiWeb(Exception):
    pass


# ======================================================================== WebSocket tối giản (RFC 6455, chỉ client) ====
class _WS:
    def __init__(self, url, timeout=10.0):
        u = urllib.parse.urlparse(url)
        self.s = socket.create_connection((u.hostname, u.port or 80), timeout=timeout)
        self.s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        key = base64.b64encode(os.urandom(16)).decode()
        duong = (u.path or "/") + (("?" + u.query) if u.query else "")
        self.s.sendall((f"GET {duong} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            c = self.s.recv(4096)
            if not c:
                raise LoiWeb("WebSocket: máy chủ đóng khi bắt tay")
            buf += c
        dau, self._du = buf.split(b"\r\n\r\n", 1)
        if b" 101" not in dau.split(b"\r\n", 1)[0]:
            raise LoiWeb("WebSocket: bắt tay hỏng: " + dau.split(b"\r\n", 1)[0].decode("latin1"))
        self._du = bytearray(self._du)

    def dat_han(self, giay):
        self.s.settimeout(giay)

    def _doc(self, n):
        if len(self._du) >= n:
            r = bytes(self._du[:n]); del self._du[:n]
            return r
        out = bytearray(n); mv = memoryview(out)
        co = len(self._du); mv[:co] = self._du; self._du = bytearray()
        while co < n:
            k = self.s.recv_into(mv[co:], n - co)
            if not k:
                raise LoiWeb("WebSocket: kết nối đóng")
            co += k
        return bytes(out)

    def _gui_khung(self, op, data):
        n = len(data)
        dau = bytearray([0x80 | op])
        if n < 126:
            dau.append(0x80 | n)
        elif n < 65536:
            dau.append(0x80 | 126); dau += struct.pack(">H", n)
        else:
            dau.append(0x80 | 127); dau += struct.pack(">Q", n)
        dau += b"\x00\x00\x00\x00"          # khoá mặt nạ 0 (hợp lệ theo RFC) → khỏi XOR dữ liệu
        self.s.sendall(bytes(dau) + data)

    def gui(self, text):
        self._gui_khung(0x1, text.encode("utf-8"))

    def nhan(self):
        manh = []
        while True:
            b0, b1 = self._doc(2)
            op = b0 & 0x0F; n = b1 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._doc(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._doc(8))[0]
            mask = self._doc(4) if b1 & 0x80 else None
            data = self._doc(n) if n else b""
            if mask:
                data = (np.frombuffer(data, np.uint8) ^ np.resize(np.frombuffer(mask, np.uint8), n)).tobytes()
            if op == 0x9:
                self._gui_khung(0xA, data); continue
            if op == 0xA:
                continue
            if op == 0x8:
                raise LoiWeb("WebSocket: trình duyệt đóng kết nối")
            manh.append(data)
            if b0 & 0x80:
                return b"".join(manh).decode("utf-8", "replace")

    def dong(self):
        try:
            self._gui_khung(0x8, b"\x03\xe8")
        except Exception:
            pass
        try:
            self.s.close()
        except Exception:
            pass


# ======================================================================== tab DevTools ====
class _Tab:
    """một tab + một kết nối DevTools riêng (không chia sẻ giữa luồng)"""

    def __init__(self, trinh_duyet):
        self.td = trinh_duyet
        # mỗi lớp một CỬA SỔ riêng (newWindow): tab nền trong cùng cửa sổ không sinh khung → captureScreenshot treo khi song song
        self.target = trinh_duyet.tao_cua_so()
        self.ws = _WS(f"ws://127.0.0.1:{trinh_duyet.cong}/devtools/page/{self.target}")
        self._id = 0
        self.su_kien = []           # sự kiện chưa xử lý (đã lọc)
        self.loi = []               # lỗi trang (exception / console.error / tài nguyên)
        self.da_tai = False

    def goi(self, method, params=None, han=HAN_KHUNG):
        self._id += 1; mid = self._id
        self.ws.gui(json.dumps({"id": mid, "method": method, "params": params or {}}))
        het = time.time() + han
        while True:
            con = het - time.time()
            if con <= 0:
                raise LoiWeb(f"quá {han:.0f}s chờ {method} (trang treo? vòng lặp vô hạn?)")
            self.ws.dat_han(con)
            try:
                m = json.loads(self.ws.nhan())
            except socket.timeout:
                raise LoiWeb(f"quá {han:.0f}s chờ {method} (trang treo? vòng lặp vô hạn?)")
            if m.get("id") == mid:
                if "error" in m:
                    raise LoiWeb(f"{method}: {m['error'].get('message')} {m['error'].get('data', '')}".strip())
                return m.get("result") or {}
            self._xu_ly(m)

    def _xu_ly(self, m):
        me = m.get("method"); p = m.get("params") or {}
        if me == "Runtime.exceptionThrown":
            d = p.get("exceptionDetails") or {}
            ex = d.get("exception") or {}
            self._ghi("lỗi JS: " + (ex.get("description") or d.get("text") or "?").split("\n    at ")[0]
                      + (f" (dòng {d.get('lineNumber', 0) + 1})" if "lineNumber" in d else ""))
        elif me == "Runtime.consoleAPICalled" and p.get("type") == "error":
            self._ghi("console.error: " + " ".join(str(a.get("value", a.get("description", ""))) for a in p.get("args") or []))
        elif me == "Log.entryAdded":
            e = p.get("entry") or {}
            if e.get("level") == "error":
                self._ghi(("tài nguyên: " if e.get("source") == "network" else "") + str(e.get("text", "")) + (" " + e["url"] if e.get("url") else ""))
        elif me == "Page.loadEventFired":
            self.da_tai = True
        elif me == "Inspector.targetCrashed":
            self._ghi("tab trình duyệt bị sập (hết bộ nhớ?)")

    def _ghi(self, s):
        s = str(s)[:400]
        if len(self.loi) < 40 and s not in self.loi:
            self.loi.append(s)

    def cho_tai(self, han):
        het = time.time() + han
        while not self.da_tai:
            con = het - time.time()
            if con <= 0:
                raise LoiWeb(f"trang không tải xong sau {han:.0f}s")
            self.ws.dat_han(con)
            try:
                self._xu_ly(json.loads(self.ws.nhan()))
            except socket.timeout:
                raise LoiWeb(f"trang không tải xong sau {han:.0f}s")

    def danh_gia(self, bieu_thuc, han=HAN_KHUNG, cho_promise=False):
        r = self.goi("Runtime.evaluate", {"expression": bieu_thuc, "returnByValue": True, "awaitPromise": cho_promise}, han=han)
        if r.get("exceptionDetails"):
            d = r["exceptionDetails"]; ex = d.get("exception") or {}
            raise LoiWeb("lỗi JS: " + (ex.get("description") or d.get("text") or "?").split("\n    at ")[0])
        return (r.get("result") or {}).get("value")

    def dong(self):
        try:
            self.ws.dong()
        finally:
            try:
                self.td.http("GET", "/json/close/" + self.target, han=3)
            except Exception:
                pass


# ======================================================================== trình duyệt ====
def tim_trinh_duyet():
    """đường dẫn Edge/Chrome/Chromium có sẵn trên máy (biến môi trường STUDIO_TRINH_DUYET ưu tiên) → str | None"""
    ung = []
    e = os.environ.get("STUDIO_TRINH_DUYET")
    if e:
        ung.append(e)
    if os.name == "nt":
        for goc in (os.environ.get("PROGRAMFILES(X86)"), os.environ.get("PROGRAMFILES"), os.environ.get("LOCALAPPDATA"),
                    r"C:\Program Files (x86)", r"C:\Program Files"):
            if goc:
                ung += [os.path.join(goc, "Microsoft", "Edge", "Application", "msedge.exe"),
                        os.path.join(goc, "Google", "Chrome", "Application", "chrome.exe"),
                        os.path.join(goc, "Chromium", "Application", "chrome.exe")]
    elif sys.platform == "darwin":
        for app in ("Google Chrome.app/Contents/MacOS/Google Chrome", "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                    "Chromium.app/Contents/MacOS/Chromium", "Brave Browser.app/Contents/MacOS/Brave Browser"):
            ung += ["/Applications/" + app, os.path.expanduser("~/Applications/" + app)]
    for ten in ("msedge", "microsoft-edge", "microsoft-edge-stable", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        p = shutil.which(ten)
        if p:
            ung.append(p)
    for p in ung:
        if p and os.path.isfile(p):
            return p
    return None


def _gan_job_tu_huy(proc):
    """Windows: gắn tiến trình trình duyệt vào Job KILL_ON_JOB_CLOSE → tiến trình Python chết (kể cả bị kill) thì trình duyệt chết theo"""
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)

        class _Basic(ctypes.Structure):
            _fields_ = [("a", ctypes.c_int64), ("b", ctypes.c_int64), ("LimitFlags", wintypes.DWORD), ("c", ctypes.c_size_t),
                        ("d", ctypes.c_size_t), ("e", wintypes.DWORD), ("f", ctypes.c_size_t), ("g", wintypes.DWORD), ("h", wintypes.DWORD)]

        class _Ext(ctypes.Structure):
            _fields_ = [("Basic", _Basic), ("Io", ctypes.c_uint64 * 6), ("i", ctypes.c_size_t), ("j", ctypes.c_size_t),
                        ("k", ctypes.c_size_t), ("l", ctypes.c_size_t)]
        k32.CreateJobObjectW.restype = wintypes.HANDLE
        job = k32.CreateJobObjectW(None, None)
        info = _Ext(); info.Basic.LimitFlags = 0x2000 | 0x800      # KILL_ON_JOB_CLOSE | BREAKAWAY_OK
        k32.SetInformationJobObject(wintypes.HANDLE(job), 9, ctypes.byref(info), ctypes.sizeof(info))
        k32.AssignProcessToJobObject(wintypes.HANDLE(job), wintypes.HANDLE(int(proc._handle)))
        return job
    except Exception:
        return None


def _pid_goc():
    try:
        import multiprocessing
        pp = multiprocessing.parent_process()
        if pp is not None and pp.pid:
            return pp.pid
    except Exception:
        pass
    return os.getpid()


def _thu_muc_phien():
    try:
        g = os.path.join(chung.duong("du_lieu"), "web-trinh-duyet")
    except Exception:
        g = os.path.join(tempfile.gettempdir(), "studio-web-trinh-duyet")
    os.makedirs(g, exist_ok=True)
    return g


class _KhoaTep:
    """khoá liên tiến trình bằng tệp (msvcrt / fcntl)"""

    def __init__(self, duong):
        self.duong = duong; self.f = None

    def __enter__(self):
        self.f = open(self.duong, "a+b")
        het = time.time() + 60
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    self.f.seek(0); msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self.f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except OSError:
                if time.time() > het:
                    raise LoiWeb("không lấy được khoá trình duyệt dùng chung")
                time.sleep(0.05)

    def __exit__(self, *a):
        try:
            if os.name == "nt":
                import msvcrt
                self.f.seek(0); msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.f.fileno(), fcntl.LOCK_UN)
        finally:
            self.f.close()


class _TrinhDuyet:
    def __init__(self, cong, proc=None, ho_so=None, job=None, exe=None):
        self.cong = cong; self.proc = proc; self.ho_so = ho_so; self.job = job; self.exe = exe

    def http(self, method, duong, han=10):
        req = urllib.request.Request(f"http://127.0.0.1:{self.cong}{duong}", method=method)
        with urllib.request.urlopen(req, timeout=han) as r:
            b = r.read()
        try:
            return json.loads(b.decode("utf-8"))
        except Exception:
            return b.decode("utf-8", "replace")

    def _goi_browser(self, method, params, han=10):
        ws_url = self.http("GET", "/json/version", han=3).get("webSocketDebuggerUrl")
        w = _WS(ws_url, timeout=han)
        try:
            w.dat_han(han)
            w.gui(json.dumps({"id": 1, "method": method, "params": params}))
            while True:
                m = json.loads(w.nhan())
                if m.get("id") == 1:
                    if "error" in m:
                        raise LoiWeb(f"{method}: {m['error'].get('message')}")
                    return m.get("result") or {}
        finally:
            w.dong()

    def tao_cua_so(self):
        return self._goi_browser("Target.createTarget", {"url": "about:blank", "newWindow": True, "background": False})["targetId"]

    def con_song(self):
        if self.proc is not None and self.proc.poll() is not None:
            return False
        try:
            self.http("GET", "/json/version", han=2)
            return True
        except Exception:
            return False

    @staticmethod
    def don_rac():
        """xoá hồ sơ/tệp đăng ký của lần chạy cũ bị giết ngang (cổng không còn trả lời, cũ hơn 2 phút)"""
        g = _thu_muc_phien(); bay_gio = time.time()
        for ten in os.listdir(g):
            p = os.path.join(g, ten)
            try:
                if bay_gio - os.path.getmtime(p) < 120:
                    continue
                cong = None
                if ten.startswith("ho-so-"):
                    try:
                        with open(os.path.join(p, "DevToolsActivePort"), encoding="utf-8") as f:
                            cong = int(f.read().split()[0])
                    except Exception:
                        pass
                elif ten.startswith("phien-") and ten.endswith(".json"):
                    cong = int((chung.doc_json(p) or {}).get("cong") or 0) or None
                elif ten.startswith("phien-") and ten.endswith(".lock"):
                    os.remove(p); continue
                else:
                    continue
                if cong and _TrinhDuyet(cong).con_song():
                    continue
                shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
            except Exception:
                pass

    @staticmethod
    def khoi_dong(exe):
        _TrinhDuyet.don_rac()
        ho_so = os.path.join(_thu_muc_phien(), f"ho-so-{os.getpid()}-{os.urandom(3).hex()}")
        os.makedirs(ho_so, exist_ok=True)
        cmd = [exe, "--headless=new", "--remote-debugging-port=0", "--remote-allow-origins=*", f"--user-data-dir={ho_so}",
               "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-component-extensions-with-background-pages",
               "--disable-background-networking", "--disable-sync", "--disable-default-apps", "--disable-component-update",
               "--hide-scrollbars", "--mute-audio", "--allow-file-access-from-files",
               "--disable-background-timer-throttling", "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows",
               "--disable-ipc-flooding-protection", "--force-color-profile=srgb", "--font-render-hinting=none",
               "--disable-features=Translate,MediaRouter,OptimizationHints,msEdgeSidebarV2,msUndersideButton,EdgeCollections,AutofillServerCommunication",
               "--no-pings", "--password-store=basic", "--use-mock-keychain", "about:blank"]
        cmd.insert(1, "--disable-partial-raster")      # vẽ lại cả ô khi đổi → điểm ảnh không phụ thuộc thứ tự khung (thiếu cờ: lệch viền AA)
        if not os.environ.get("STUDIO_WEB_GPU"):
            # vẽ phần mềm + bỏ vsync/giới hạn fps: chụp 1080×600 ≈ 13 ms thay vì 72 ms (GPU + vsync, đo GTX 1050);
            # cũng tất định hơn giữa các máy/driver. STUDIO_WEB_GPU=1 để dùng GPU.
            cmd[1:1] = ["--disable-gpu", "--disable-gpu-vsync", "--disable-frame-rate-limit"]
        for c in (os.environ.get("STUDIO_WEB_CO") or "").split():
            cmd.insert(1, c)
        flags = 0x08000000 if os.name == "nt" else 0           # CREATE_NO_WINDOW
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        job = _gan_job_tu_huy(proc)
        tep = os.path.join(ho_so, "DevToolsActivePort")
        het = time.time() + 30
        cong = None
        while time.time() < het:
            if proc.poll() is not None:
                raise LoiWeb(f"trình duyệt thoát ngay khi khởi động (mã {proc.returncode}): {exe}")
            try:
                with open(tep, encoding="utf-8") as f:
                    d = f.read().split()
                if d:
                    cong = int(d[0]); break
            except Exception:
                pass
            time.sleep(0.05)
        if not cong:
            _giet(proc)
            raise LoiWeb("trình duyệt không mở cổng DevTools sau 30s")
        td = _TrinhDuyet(cong, proc, ho_so, job, exe)
        for _ in range(100):
            if td.con_song():
                return td
            time.sleep(0.05)
        _giet(proc)
        raise LoiWeb("cổng DevTools không trả lời")

    def dong(self):
        if self.proc is None:
            return
        try:
            ws_url = self.http("GET", "/json/version", han=2).get("webSocketDebuggerUrl")
            if ws_url:
                w = _WS(ws_url, timeout=3); w.gui(json.dumps({"id": 1, "method": "Browser.close"})); w.dong()
                self.proc.wait(timeout=5)
        except Exception:
            pass
        _giet(self.proc)
        self.proc = None
        if self.job is not None:
            try:
                import ctypes
                ctypes.WinDLL("kernel32").CloseHandle(self.job)
            except Exception:
                pass
            self.job = None
        for _ in range(20):
            try:
                shutil.rmtree(self.ho_so)
                break
            except FileNotFoundError:
                break
            except Exception:
                time.sleep(0.1)


def _giet(proc):
    try:
        if proc and proc.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, creationflags=0x08000000, timeout=10)
            else:
                proc.kill()
            proc.wait(timeout=5)
    except Exception:
        pass


_TD = None                 # trình duyệt của phiên (tiến trình này dùng)
_TD_CUA_MINH = None        # trình duyệt do CHÍNH tiến trình này khởi động (phải đóng khi thoát)
_KHOA = threading.Lock()


def lay_trinh_duyet():
    """trình duyệt dùng chung cho lần dựng: cùng tiến trình → 1 đối tượng; tiến trình con của pool → dùng chung qua tệp đăng ký
    theo PID gốc. Không có Edge/Chrome → LoiWeb("máy không có Edge/Chrome")."""
    global _TD, _TD_CUA_MINH
    with _KHOA:
        if _TD is not None and _TD.con_song():
            return _TD
        exe = tim_trinh_duyet()
        if not exe:
            raise LoiWeb("máy không có Edge/Chrome (cần Microsoft Edge hoặc Google Chrome/Chromium để dựng lớp web)")
        g = _thu_muc_phien(); goc = _pid_goc()
        dk = os.path.join(g, f"phien-{goc}.json")
        with _KhoaTep(os.path.join(g, f"phien-{goc}.lock")):
            d = chung.doc_json(dk)
            if d and d.get("cong"):
                td = _TrinhDuyet(int(d["cong"]), exe=d.get("exe"))
                if td.con_song():
                    _TD = td
                    return td
            td = _TrinhDuyet.khoi_dong(exe)
            chung.ghi_json(dk, {"cong": td.cong, "pid": td.proc.pid, "exe": exe, "chu": os.getpid(), "luc": time.time()})
            _TD = td; _TD_CUA_MINH = td
            _canh_ranh(td, dk)
            return td


def _canh_ranh(td, dk):
    """trình duyệt do tiến trình này mở: không còn tab lớp nào (mọi tiến trình) suốt 45 s → đóng (Studio chạy lâu không giữ Edge ngầm)"""
    def _chay():
        ranh = 0.0
        while td.proc is not None and td.proc.poll() is None:
            time.sleep(3)
            try:
                tabs = [t for t in td.http("GET", "/json/list", han=3) if t.get("type") == "page" and t.get("url") != "about:blank"]
            except Exception:
                return
            ranh = ranh + 3 if not tabs else 0
            if ranh >= 45:
                with _KHOA:
                    dong_trinh_duyet(td)
                return
    threading.Thread(target=_chay, daemon=True, name="web-canh-ranh").start()


def dong_trinh_duyet(td=None):
    """đóng trình duyệt do tiến trình này khởi động (gọi khi xong lần dựng; atexit tự gọi)"""
    global _TD, _TD_CUA_MINH
    td = td or _TD_CUA_MINH
    if td is None:
        return
    td.dong()
    if _TD is td:
        _TD = None
    if _TD_CUA_MINH is td:
        _TD_CUA_MINH = None
    try:
        g = _thu_muc_phien(); dk = os.path.join(g, f"phien-{_pid_goc()}.json")
        d = chung.doc_json(dk)
        if d and int(d.get("cong", 0)) == td.cong:
            os.remove(dk)
        lk = os.path.join(g, f"phien-{_pid_goc()}.lock")
        if os.path.isfile(lk) and _pid_goc() == os.getpid():
            os.remove(lk)
    except Exception:
        pass


atexit.register(lambda: dong_trinh_duyet())


# ======================================================================== trang ====
def _uri(p):
    return Path(os.path.abspath(p)).as_uri()


def _css_chuoi(s):
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _mau_hop_le(s, mac_dinh):
    s = str(s or "").strip()
    return s if re.fullmatch(r"#[0-9A-Fa-f]{3,8}|rgba?\([\d\s.,%]+\)|hsla?\([\d\s.,%deg]+\)|[a-zA-Z]+", s) else mac_dinh


def dau_trang(ctx, w, h, dur, props, pc=None):
    """khối chèn đầu <head>: token CSS + @font-face + bộ điều khiển đồng hồ ảo + PROPS"""
    pc = pc if pc is not None else (getattr(ctx, "pc", None) or {})
    mau = {}
    for k in VAI_MAU:                       # màu vai: phong cách video → quyet_dinh bang_mau (kênh) → thieu_truong
        v = _mau_hop_le(pc.get("mau_" + k), None)
        if not v:
            v = _mau_hop_le(_lop.quyet(ctx, "bang_mau." + k, lop="web"), None)
            if not v:
                raise _lop.ThieuTruong("bang_mau." + k, "màu không hợp lệ", "web")
        mau[k] = v
    font_face = []; bien = []; ho = []
    for vai in VAI_FONT:
        try:
            f = ctx.font_file(vai)
        except Exception:
            f = None
        ten = "st-" + vai.replace("_", "-")
        if f and os.path.isfile(f):
            font_face.append("@font-face{font-family:%s;src:url(%s);font-weight:1 1000;font-style:normal;font-display:block}"
                             % (_css_chuoi(ten), _css_chuoi(_uri(f))))
            ho.append(ten)
        bien.append("--font-%s:%s,%s" % (vai.replace("_", "-"), _css_chuoi(ten), "cursive" if vai == "script" else "sans-serif"))
    tokens = {"mau_" + k: v for k, v in mau.items()}
    tokens.update({"font_" + v: "st-" + v.replace("_", "-") for v in VAI_FONT})
    khung = {"w": w, "h": h, "W": ctx.W, "H": ctx.H, "dur": dur, "fps": ctx.fps}
    css = ("%s :root{--mau-nhan:%s;--mau-nhan2:%s;--mau-sang:%s;--mau-toi:%s;%s;--W:%dpx;--H:%dpx;--khung-W:%dpx;--khung-H:%dpx} "
           "html,body{margin:0;padding:0;background:transparent;overflow:hidden;width:%dpx;height:%dpx}"
           % (" ".join(font_face), mau["nhan"], mau["nhan2"], mau["sang"], mau["toi"], ";".join(bien), w, h, ctx.W, ctx.H, w, h))
    js = ("window.PROPS=%s;window.KHUNG=%s;window.TOKENS=%s;window.__STUDIO_FONT=%s;"
          % (json.dumps(props, ensure_ascii=False), json.dumps(khung), json.dumps(tokens, ensure_ascii=False), json.dumps(ho)))
    js = js.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    # MỘT dòng (không xuống dòng) → số dòng lỗi JS khớp tệp gốc; bộ điều khiển nạp đồng bộ từ web_khung.js, chạy trước mã trang
    return ('<meta charset="utf-8"><style id="studio-token">%s</style><script id="studio-du-lieu">%s</script>'
            '<script id="studio-khung" src="%s"></script>' % (css.replace("\n", " "), js, _uri(os.path.join(THU_MUC, "web_khung.js"))))


def ghep_trang(html, dau, base_dir):
    """chèn khối đầu + <base href> vào ngay sau <head> (hoặc <html>, hoặc đầu tệp); giữ <!doctype> ở trên cùng"""
    them = '<base href="%s/">' % _uri(base_dir).rstrip("/")
    if re.search(r"\bTHREE\b|\bS3D\b", html):        # trang dùng three.js / S3D → tiêm bản ngoại tuyến (web-lib/three.min.js, MIT) trước mã trang
        p3 = os.path.join(THU_MUC, "web-lib", "three.min.js")
        if os.path.isfile(p3):
            them += '<script id="studio-three" src="%s"></script>' % _uri(p3)
        p4 = os.path.join(THU_MUC, "web-lib", "studio3d.js")
        if "S3D" in html and os.path.isfile(p4):           # tay cầm three.js của Studio (cảnh, thẻ, video, chữ) — tuỳ chọn
            them += '<script id="studio-s3d" src="%s"></script>' % _uri(p4)
    them += dau
    m = re.search(r"<head\b[^>]*>", html, re.I)
    if m:
        return html[:m.end()] + them + html[m.end():]
    m = re.search(r"<html\b[^>]*>", html, re.I)
    if m:
        return html[:m.end()] + "<head>" + them + "</head>" + html[m.end():]
    m = re.match(r"\s*<!doctype[^>]*>", html, re.I)
    if m:
        return html[:m.end()] + "<head>" + them + "</head>" + html[m.end():]
    return "<!doctype html><head>" + them + "</head>" + html


# ======================================================================== lớp web ====
class LopWeb(Lop):
    """trang HTML/CSS/SVG do AI viết, render đúng hộp lớp, nền trong suốt; hoạt ảnh tất định theo t (veTai / CSS / WAAPI)"""
    kieu = "web"

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        nd = spec.get("noi_dung") or {}
        if isinstance(nd, str):
            nd = {"html": nd} if not nd.lstrip().startswith("<") else {"ma": nd}
        self.props = self._giai_props(nd.get("props") or {})
        self.html = None; self.base_dir = ctx.du_an or os.getcwd(); self.nguon = None
        if nd.get("ma"):
            self.html = str(nd["ma"]); self.nguon = "ma"
        elif nd.get("html"):
            f = str(nd["html"])
            p = f if os.path.isabs(f) else os.path.join(ctx.du_an or "", f)
            if not os.path.isfile(p):
                p2 = ctx.tai_nguyen(f)
                p = p2 if p2 else p
            if os.path.isfile(p):
                try:
                    with open(p, encoding="utf-8-sig") as fh:
                        self.html = fh.read()
                    self.base_dir = os.path.dirname(os.path.abspath(p)); self.nguon = p
                except Exception as ex:
                    self._loi("tai_nguyen_khong_co", f"không đọc được trang {f}: {ex}")
            else:
                self._loi("tai_nguyen_khong_co", f"không có tệp trang `{f}` (đường dẫn tính từ thư mục dự án)")
        else:
            self._loi("tai_nguyen_khong_co", "lớp web thiếu noi_dung.html hoặc noi_dung.ma")
        self._tab = None; self._hong = self.html is None
        self._tinh = False; self._info = {}
        self._lt_dat = None; self._khoa_dat = None
        self._khoa_anh = object(); self._anh = None
        self.do = {"dat": 0.0, "chup": 0.0, "giai_ma": 0.0, "so_chup": 0, "so_dat": 0, "tai": 0.0}
        self._o = [None]                                   # ô giữ tab cho finalize (không tham chiếu self)
        weakref.finalize(self, LopWeb._dong_tab, self._o)

    # ---- tiện ích
    def _loi(self, id_, mo_ta):
        if sum(1 for l in self.loi if l.get("lop") == self.id) >= LOI_TOI_DA:
            return
        if any(l.get("mo_ta") == mo_ta for l in self.loi):
            return
        self.loi.append({"id": id_, "lop": self.id, "t": self.t0, "mo_ta": "lớp web: " + mo_ta})

    _DUOI_VIDEO = (".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".ts", ".mts")

    def _video_web(self, p):
        """video cho trang web (texture three.js / <video>): trình duyệt ẩn không giải mã H.264 → chuyển VP9 webm ≤720p, cache theo tệp"""
        if not p or not os.path.isfile(p):
            return p
        if p.lower().endswith(".webm"):
            return p
        try:
            st = os.stat(p)
            cache = os.path.join(self.ctx.du_an or os.getcwd(), "cache")
            os.makedirs(cache, exist_ok=True)
            ra = os.path.join(cache, "web-%s.webm" % hashlib.md5(("%s|%d|%d" % (os.path.abspath(p), st.st_size, int(st.st_mtime))).encode("utf-8")).hexdigest()[:12])
            if os.path.isfile(ra) and os.path.getsize(ra) > 1000:
                return ra
            cw = cau_hinh_web_video()
            loc = _lop.loc_mau_vao(p)                      # 1.2.21 (§1f): nguồn 10-bit/HDR → bt709 trước scale
            vf = (loc + "," if loc else "") + "scale='min(%d,iw)':-2" % int(cw["cao_toi_da"])
            cmd = [chung.duong("ffmpeg"), "-v", "error", "-y", "-i", p, "-an", "-vf", vf, "-c:v", "libvpx-vp9", "-crf", str(int(cw["crf"])), "-b:v", "0",
                   "-deadline", str(cw["deadline"]), "-cpu-used", str(int(cw["cpu_used"])), "-row-mt", "1", "-pix_fmt", "yuv420p", ra + ".tmp.webm"]
            ma, out, err = chung.sh(cmd, timeout=900)
            if ma != 0 or not os.path.isfile(ra + ".tmp.webm"):
                self._loi("web_loi", f"không chuyển được video cho trang web: {err[-200:] if err else ma}")
                return p
            os.replace(ra + ".tmp.webm", ra)
            return ra
        except Exception as ex:
            self._loi("web_loi", f"video cho trang web lỗi: {ex}")
            return p

    def _giai_props(self, props):
        def di(v):
            if isinstance(v, str) and v.startswith("nguon:"):          # video nguồn thứ i của dự án
                try:
                    i = int(v[6:] or 0)
                    p = (self.ctx.nguon or [])[i]
                except Exception:
                    p = None
                if not p or not os.path.isfile(p):
                    self._loi("tai_nguyen_khong_co", f"props: không có video nguồn `{v}`")
                    return ""
                return _uri(self._video_web(p))
            if isinstance(v, str) and v.startswith("kho:"):
                p = self.ctx.tai_nguyen(v[4:])
                if not p:
                    self._loi("tai_nguyen_khong_co", f"props: không có tài nguyên kho `{v[4:]}`")
                    return ""
                if str(p).lower().endswith(self._DUOI_VIDEO):
                    p = self._video_web(p)
                return _uri(p)
            if isinstance(v, str) and v.lower().endswith(self._DUOI_VIDEO) and os.path.isfile(v):
                return _uri(self._video_web(v))
            if isinstance(v, str) and v.lower().startswith("file:///") and v.lower().endswith(self._DUOI_VIDEO):
                try:
                    from urllib.request import url2pathname
                    from urllib.parse import urlparse, unquote
                    pth = url2pathname(unquote(urlparse(v).path))
                    if os.path.isfile(pth):
                        return _uri(self._video_web(pth))
                except Exception:
                    pass
                return v
            if isinstance(v, dict):
                return {k: di(x) for k, x in v.items()}
            if isinstance(v, list):
                return [di(x) for x in v]
            return v
        return di(props)

    @staticmethod
    def _dong_tab(o):
        tab = o[0]
        if tab is not None:
            o[0] = None
            try:
                tab.dong()
            except Exception:
                pass

    def dong(self):
        """đóng tab (tự gọi khi lớp bị thu gom)"""
        LopWeb._dong_tab(self._o)
        self._tab = None

    # ---- hợp đồng Lop
    def _kich_thuoc_goc(self):
        return _lop.hop_mac_dinh(self, "web")      # 1.2.21: thiếu w/h → quyet_dinh vi_tri.hop_mac_dinh.web

    def kich_thuoc(self):
        w, h = self._kich_thuoc_goc()
        return (w * self.ti_le, h * self.ti_le)

    def le_noi_dung(self):
        return {"trai": 0, "phai": 0, "tren": 0, "duoi": 0}

    def khoa_noi_dung(self, lt):
        if self._hong:
            return None
        try:
            self._mo()
            if self._tinh:
                return None
            return self._dat(lt)
        except LoiWeb as ex:
            self._hu(str(ex))
            return None

    def noi_dung(self, lt):
        self.khoi()
        w, h = self.kich_thuoc(); w, h = max(2, int(round(w))), max(2, int(round(h)))
        if self._hong:
            return self._trong(w, h), (0, 0)
        try:
            self._mo()
            k = None if self._tinh else (self._khoa_dat if self._lt_dat == lt else self._dat(lt))
            if self._anh is not None and k == self._khoa_anh:
                return self._anh, (0, 0)
            a = self._chup(w, h)
            self._anh = _lop.anh_skia_tu_numpy(a, bgra=True); self._khoa_anh = k
            return self._anh, (0, 0)
        except LoiWeb as ex:
            self._hu(str(ex))
            return self._trong(w, h), (0, 0)

    @staticmethod
    def _trong(w, h):
        return skia.Surface(w, h).makeImageSnapshot()

    def _hu(self, msg):
        id_ = "tai_nguyen_khong_co" if "Edge/Chrome" in msg else "web_loi"
        self._loi(id_, msg)
        self._hong = True
        if self._tab is not None:
            tab, self._tab = self._tab, None
            self._o[0] = None
            threading.Thread(target=tab.dong, daemon=True).start()

    # ---- trình duyệt
    def _mo(self):
        if self._tab is not None:
            return
        self.khoi()                                   # chốt ti_le trước khi đặt viewport
        t_bd = time.time()
        td = lay_trinh_duyet()
        tab = _Tab(td)
        self._o[0] = tab
        self._tab = tab
        wg, hg = self._kich_thuoc_goc(); wg, hg = int(round(wg)), int(round(hg))
        tab.goi("Page.enable"); tab.goi("Runtime.enable"); tab.goi("Log.enable"); tab.goi("Animation.enable")
        tab.goi("Animation.setPlaybackRate", {"playbackRate": 0})       # đóng băng đồng hồ hoạt ảnh của tài liệu: hoạt ảnh ngắn không "chạy mất" lúc tải
        # 1.2.21: deviceScaleFactor theo ti_le CHỈ khi bị thu (< 1); lớp toàn khung / không thu → render đúng 1.0
        dsf = float(self.ti_le) if (self.ti_le < 1.0 - 1e-6 and not self.toan_khung) else 1.0
        tab.goi("Emulation.setDeviceMetricsOverride", {"width": wg, "height": hg, "deviceScaleFactor": dsf, "mobile": False})
        tab.goi("Emulation.setDefaultBackgroundColorOverride", {"color": {"r": 0, "g": 0, "b": 0, "a": 0}})
        dau = dau_trang(self.ctx, wg, hg, float(self.dur), self.props)
        trang = ghep_trang(self.html, dau, self.base_dir)
        tep = self._tep_tam(trang)
        tab.da_tai = False
        self._url_tam = _uri(tep)
        r = tab.goi("Page.navigate", {"url": self._url_tam}, han=HAN_TAI)
        if r.get("errorText"):
            raise LoiWeb("không mở được trang: " + r["errorText"])
        tab.cho_tai(HAN_TAI)
        tab.danh_gia("window.__studio ? window.__studio.sanSang() : true", han=HAN_TAI, cho_promise=True)
        if not tab.danh_gia("!!window.__studio"):
            raise LoiWeb("trang không chạy được bộ điều khiển (HTML hỏng?)")
        self._dat(0.0)
        self._info = tab.danh_gia("__studio.thongTin()") or {}
        self._tinh = not (self._info.get("veTai") or self._info.get("anim") or self._info.get("raf") or self._info.get("hen") or self._info.get("canvas"))
        self.do["tai"] = round(time.time() - t_bd, 3)
        # chữ tràn hộp: đo ở giữa lớp (lúc hoạt ảnh vào thường đã xong) — trang là hàm thuần theo t nên tua tới rồi về 0 vô hại
        if not self._tinh:
            self._dat(self.dur * 0.5)
        tran = tab.danh_gia("__studio.kiemTran()") or []
        if tran:
            ct = "; ".join("«%s» lệch %s" % (x["chu"], ",".join("%s %dpx" % (k, x[k]) for k in ("trai", "phai", "tren", "duoi") if x[k] > 2)) for x in tran[:3])
            self._loi("chu_tran_khung", f"chữ vượt hộp {wg}×{hg} lúc t={self.dur * 0.5:.2f}s (bị cắt): {ct} — thu cỡ chữ hoặc nới vi_tri.w/h")
        if not self._tinh:
            self._dat(0.0)
        self._xa_loi_tab()

    def _tep_tam(self, trang):
        g = os.path.join(self.ctx.du_an, "cache", "web") if self.ctx.du_an else os.path.join(_thu_muc_phien(), "trang")
        os.makedirs(g, exist_ok=True)
        p = os.path.join(g, "trang-" + hashlib.sha1(trang.encode("utf-8")).hexdigest()[:16] + ".html")
        if not os.path.isfile(p):
            tmp = p + ".%d.tmp" % threading.get_ident()
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(trang)
            try:
                os.replace(tmp, p)
            except Exception:
                pass
        return p

    def _xa_loi_tab(self, ds=None):
        tab = self._tab
        ten = os.path.basename(self.nguon) if self.nguon and self.nguon != "ma" else "trang"
        for s in (ds or []) + (tab.loi if tab else []):
            if getattr(self, "_url_tam", None):
                s = s.replace(self._url_tam, ten)
            self._loi("tai_nguyen_khong_co" if s.startswith(("tài nguyên", "không tải được")) else "web_loi", s)
        if tab:
            tab.loi.clear()

    def _dat(self, lt):
        t = time.time()
        r = self._tab.danh_gia("__studio.dat(%r,%r)" % (float(lt), float(self.dur)), cho_promise=True) or {}
        self.do["dat"] += time.time() - t; self.do["so_dat"] += 1
        self._lt_dat = lt; self._khoa_dat = r.get("khoa")
        if r.get("loi") or self._tab.loi:
            self._xa_loi_tab(r.get("loi") or [])
        return self._khoa_dat

    def _chup(self, w, h):
        t = time.time()
        r = self._tab.goi("Page.captureScreenshot", {"format": "png", "fromSurface": True, "captureBeyondViewport": False,
                                                     "optimizeForSpeed": True}, han=HAN_CHUP)
        t2 = time.time()
        a = cv2.imdecode(np.frombuffer(base64.b64decode(r["data"]), np.uint8), cv2.IMREAD_UNCHANGED)
        if a is None:
            raise LoiWeb("ảnh chụp hỏng")
        if a.ndim == 2:
            a = cv2.cvtColor(a, cv2.COLOR_GRAY2BGRA)
        elif a.shape[2] == 3:
            a = cv2.cvtColor(a, cv2.COLOR_BGR2BGRA)
        if a.shape[0] != h or a.shape[1] != w:             # deviceScaleFactor lẻ → lệch 1 px: cắt/đệm cho đúng hộp
            b = np.zeros((h, w, 4), np.uint8)
            hh, ww = min(h, a.shape[0]), min(w, a.shape[1])
            b[:hh, :ww] = a[:hh, :ww]; a = b
        self.do["chup"] += t2 - t; self.do["giai_ma"] += time.time() - t2; self.do["so_chup"] += 1
        return np.ascontiguousarray(a)


try:                                      # import web.py trước lop.py → móc trong lop.py chưa kịp cắm: tự cắm
    _lop.KIEU.setdefault("web", LopWeb)
except Exception:
    pass


# ======================================================================== từ điển cho AI ====
def tu_dien_web():
    """hợp đồng ngắn (≤ 900 ký tự) cho AI"""
    return (
        "LỚP web: HTML/CSS/SVG tự viết, nền trong suốt.\n"
        '{"kieu":"web","t0":2,"t1":6,"noi_dung":{"html":"lop-rieng/x.html"|"ma":"<html>…","props":{}},"vi_tri":{"anchor":"mc","x":.5,"y":.4,"w":.9,"h":.3}}\n'
        "Trang = hộp w×h; có: --mau-nhan --mau-nhan2 --mau-sang --mau-toi, --font-tieu-de --font-nhan --font-phu-de --font-than, "
        "--W --H; window.PROPS (\"kho:<id>\"→URL tệp). CSS animation/el.animate tự tua. "
        "window.veTai(t,dur) (giây từ t0) đặt trạng thái: hàm thuần, không mạng. Chữ tràn hộp → lỗi. "
        "3D: CSS transform perspective()/rotateX/rotateY/translateZ, transform-style:preserve-3d — chồng thẻ phối cảnh, lật, xoay, parallax nhiều lớp đều chụp đúng từng khung. "
        "3D THẬT: viết `THREE` là máy tiêm sẵn three.js (r152, window.THREE, WebGL phần mềm): vật thể, thẻ/ảnh/B-roll trong không gian (PlaneGeometry + TextureLoader(PROPS.anh) / VideoTexture), "
        "camera bay, ánh sáng, đổ bóng; renderer {alpha:true, preserveDrawingBuffer:true}, vẽ trong veTai(t). B-roll/video nguồn làm texture: props {clip:\"kho:<id video>\"|\"nguon:0\"|đường dẫn} "
        "→ máy tự chuyển webm, trang dùng <video src=PROPS.clip muted preload=auto> + THREE.VideoTexture; veTai async: await loadeddata; v.currentTime=t; await seeked; tex.needsUpdate=true; render; return t. "
        "Ảnh: PROPS \"kho:<id anh>\" → URL, TextureLoader. "
        "Tay cầm S3D (viết S3D là có): const c=S3D.canh({z:7}); const v=S3D.video(PROPS.clip); const man=S3D.the({w:2.4,h:4.26,tex:v.tex,day:0.1}); c.scene.add(man); "
        "const t1=S3D.chu('AI edit',{co:120,mau:'nhan'}); veTai=async(t)=>{await v.tua(t); S3D.quay(man,{y:Math.sin(t)*20}); c.cam.position.x=Math.sin(t*.5); c.ve(); return t}. "
        "S3D.the({anh:URL}|{mau:'sang'}), S3D.chu(text,{font:'tieu-de'|'nhan',co,mau,dam,vien}), S3D.ease(ten,u).\n"
        "<svg width=300 height=200><path id=p d='M0 190L100 120L300 20' pathLength=1 fill=none stroke='var(--mau-nhan)' stroke-width=8 stroke-dasharray=1 /></svg>\n"
        "<b id=n style='font:900 120px var(--font-tieu-de);color:var(--mau-sang)'></b>\n"
        "<script>const e=u=>1-(1-u)**3;\n"
        "veTai=(t,d)=>{const u=e(Math.min(t/1.5,1));\n"
        " p.style.strokeDashoffset=1-u;\n"
        " n.textContent=Math.round(PROPS.so*u).toLocaleString('vi')}</script>"
    )


# ======================================================================== thử từ dòng lệnh ====
def _ban_co(h, w, o=16):
    y, x = np.mgrid[0:h, 0:w]
    v = np.where(((x // o) + (y // o)) % 2 == 0, 200, 140).astype(np.uint8)
    return np.dstack([v, v, v])


def _chay_thu(a):
    os.makedirs(a.ra, exist_ok=True)
    w, h = int(a.w), int(a.h)
    from dung.mau import bang as _bang
    ctx = _lop.Ctx(max(1080, w), max(1920, h), a.fps, du_an=os.path.abspath(a.ra), quyet_dinh=_bang.QUYET_DINH_XEM_TRUOC)   # tệp tạm vào thư mục ra
    if a.mau:
        ctx.pc = json.loads(a.mau)
    spec = {"id": "thu", "kieu": "web", "t0": 0, "t1": a.dur, "ne_mat": False,
            "noi_dung": {"html": os.path.abspath(a.thu), "props": json.loads(a.props) if a.props else {}},
            "vi_tri": {"anchor": "tl", "x": 0, "y": 0, "w": w, "h": h}, "anim": {"vao": {"kieu": "none"}, "ra": {"kieu": "none"}}}
    t = time.time()
    l = _lop.tao_lop(spec, ctx)
    print("lớp:", type(l).__module__, type(l).__name__)
    l.ctx.vung = {"tren": 0, "duoi": 0, "trai": 0, "phai": 0}
    l._khoi = (0, 0, w, h)
    k0 = l.khoa_noi_dung(0.0)
    print(f"mở trình duyệt + tải trang: {time.time() - t:.2f}s  (tải trang {l.do['tai']}s)  tĩnh={l._tinh}  thông tin={l._info}")
    # dải 6 khung
    moc = [a.dur * i / 5 for i in range(6)]
    moc[-1] = a.dur - 1.0 / a.fps
    o = []
    for i, tt in enumerate(moc):
        img, _ = l.noi_dung(tt)
        bgra = _lop.numpy_bgra_tu_skia(img)
        chung.cv_ghi(os.path.join(a.ra, "khung-%d-%.2fs.png" % (i, tt)), bgra)
        al = bgra[..., 3:4].astype(np.float32) / 255
        nen = _ban_co(h, w).astype(np.float32)
        o.append((bgra[..., :3].astype(np.float32) * al + nen * (1 - al)).astype(np.uint8))
        nhan = "%.2fs" % tt
        cv2.putText(o[-1], nhan, (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.putText(o[-1], nhan, (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 255), 2, cv2.LINE_AA)
    cot = 2 if w > h else 3
    hang = [np.hstack(o[r * cot:(r + 1) * cot]) for r in range(len(o) // cot)]
    dai = np.vstack(hang)
    s = min(1.0, 1800 / dai.shape[1])
    dai = cv2.resize(dai, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    p = os.path.join(a.ra, "dai-6-khung.jpg"); chung.cv_ghi(p, dai, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print("dải:", p)
    # đo hiệu năng: mọi khung fps trong [0, dur] (khoá + chụp khi đổi) — đúng đường ket_xuat_sprite dùng
    if a.do:
        n = min(int(a.do), int(a.dur * a.fps))
        for k in l.do:
            l.do[k] = 0 if not isinstance(l.do[k], float) else 0.0
        t = time.time(); so_ve = 0; kt = object()
        for i in range(n):
            lt = i / a.fps
            k = l.khoa_noi_dung(lt)
            if i == 0 or k != kt:
                l.noi_dung(lt); so_ve += 1
            kt = k
        tg = time.time() - t
        d = l.do
        print(f"ĐO {n} khung {w}×{h}: tổng {tg * 1000 / n:.1f} ms/khung · chụp {so_ve} khung "
              f"→ {tg * 1000 / max(1, so_ve):.1f} ms/khung chụp (dat {d['dat'] * 1000 / max(1, d['so_dat']):.1f} · "
              f"captureScreenshot {d['chup'] * 1000 / max(1, d['so_chup']):.1f} · giải mã PNG {d['giai_ma'] * 1000 / max(1, d['so_chup']):.1f} ms)")
    if l.loi:
        print("LỖI:", json.dumps(l.loi, ensure_ascii=False, indent=1))
    if l.may_sua:
        print("máy sửa:", json.dumps(l.may_sua, ensure_ascii=False))
    l.dong()
    dong_trinh_duyet()


if __name__ == "__main__":
    import argparse
    sys.path.insert(0, os.path.dirname(THU_MUC))
    ap = argparse.ArgumentParser(description="thử lớp web: dải 6 khung + đo ms/khung")
    ap.add_argument("--thu", required=True, help="tệp .html")
    ap.add_argument("--ra", required=True, help="thư mục ảnh ra")
    ap.add_argument("--w", type=int, default=1080); ap.add_argument("--h", type=int, default=600)
    ap.add_argument("--dur", type=float, default=3.0); ap.add_argument("--fps", type=float, default=30)
    ap.add_argument("--props", default=None); ap.add_argument("--mau", default=None, help='{"mau_nhan":"#..."}')
    ap.add_argument("--do", type=int, default=0, help="đo N khung liên tiếp")
    a = ap.parse_args()
    from dung import web as _web            # dùng bản mô-đun (cùng bản lop.py đã cắm) thay vì __main__
    _web._chay_thu(a)
