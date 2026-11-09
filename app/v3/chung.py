# -*- coding: utf-8 -*-
"""Studio AI — lõi dùng chung: đường dẫn, cấu hình, JSON, chạy lệnh, ffprobe, băm, đo thời gian, phần cứng.
Mọi mô-đun import `chung` và KHÔNG ghi cứng đường dẫn."""
import hashlib, json, os, subprocess, sys, time, unicodedata, shutil, platform, re, threading, random

APP = os.path.dirname(os.path.abspath(__file__))          # .../app/v3  — lõi mới (1.3) của Studio
SKILL = os.path.dirname(APP)                               # .../app      — gói Studio (giao diện, bản quyền, cập nhật)
NFC = lambda s: unicodedata.normalize("NFC", s) if isinstance(s, str) else s
_CFG = None

MAC_DINH = {
    "khung_mac_dinh": [1080, 1920], "fps_mac_dinh": 30, "proxy_cao": 0, "alpha_canh_ngan": 0, "alpha_ref": 0,   # 0 = theo năng lực máy đo được
    "whisper": {"model": "", "beam": 1, "vad": True, "compute": "int8"},                                           # "" = theo năng lực máy
    "ai": {"model": "", "model_nhanh": "", "toi_da_luot": 2, "claude": ""},
    # 1.2.21: 16:9 có bảng riêng (trước dùng số của 9:16 → video ngang chừa đáy 22 %)
    "vung_an_toan": {"9:16": {"tren": 0.08, "duoi": 0.22, "trai": 0.04, "phai": 0.10}, "16:9": {"tren": 0.06, "duoi": 0.10, "trai": 0.05, "phai": 0.05}},
    "am": {"giong_lufs": -16, "nhac_db": -20, "dinh_dbtp": -2.0},
    "ffmpeg_im_toi_da_giay": 300,      # ffmpeg không tiến trong N giây = treo (giết, trả 124) — cai-dat.json của Studio đè qua cau-hinh v3
    "giu_cache_ngay": 3,               # cache/khuc cũ hơn N ngày xoá sau khi dựng xong
    "tang_toc": "auto",                # "cpu" = không hwaccel / không encoder phần cứng / ORT CPU (hoặc env STUDIO_CPU_ONLY=1)
}


class ThieuTruong(Exception):
    """máy KHÔNG tự điền số thẩm mỹ: thiếu trường trong công thức / quyet-dinh.json → trả AI danh sách
    [{"duong": "quyet_dinh.am.giong_lufs", "ma": "thieu_truong", "goi_y": "..."}] (khớp hợp đồng v3/ai/hop_dong.py)"""

    def __init__(self, loi):
        self.loi = [l if isinstance(l, dict) else {"duong": str(l), "ma": "thieu_truong"} for l in (loi or [])]
        super().__init__("thieu_truong: " + ", ".join(l.get("duong", "?") for l in self.loi))


def _tron(a, b):
    for k, v in (b or {}).items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            _tron(a[k], v)
        else:
            a[k] = v
    return a


def cau_hinh():
    """mặc định của lõi + mục "v3" trong cau-hinh.json của Studio (người dùng/bộ cài ghi; cập nhật không đè)"""
    global _CFG
    if _CFG is None:
        g = doc_json(os.path.join(SKILL, "cau-hinh.json"), {}) or {}
        c = json.loads(json.dumps(MAC_DINH))
        _tron(c, g.get("v3") or {})
        kho = g.get("kho") or {}
        c.setdefault("kho_goc", c.get("kho_goc") or kho.get("bo_mua") or kho.get("duong_dan") or "")
        _CFG = c
    return _CFG


def _data_studio():
    return os.path.expanduser(os.environ.get("STUDIO_DATA") or "~/.studio-edit-video")


def duong(khoa):
    """đường dẫn chuẩn: app · skill · du_lieu · ho_so · du_an · kho_chi_muc · mo_hinh · font_mac_dinh · kho_goc · tai_len · nhat_ky · python · ffmpeg · ffprobe"""
    c = cau_hinh()
    dl = os.path.expanduser(c.get("du_lieu") or os.path.join(_data_studio(), "v3"))
    m = {
        "app": APP, "skill": SKILL, "du_lieu": dl,
        "ho_so": os.path.join(SKILL, "nao", "ca-nhan"),                 # dùng chung hồ sơ kênh của Studio
        "du_an": os.path.expanduser(c.get("du_an") or "~/Videos/studio-du-an"),
        "kho_chi_muc": os.path.join(dl, "kho-chi-muc"),
        "mo_hinh": os.path.join(APP, "mo-hinh"), "font_mac_dinh": os.path.join(APP, "font-mac-dinh"),
        "tai_len": os.path.join(dl, "tai-len"), "nhat_ky": os.path.join(dl, "nhat-ky"),
        "kho_goc": c.get("kho_goc", ""),
        "python": sys.executable,
        "ffmpeg": shutil.which("ffmpeg") or "ffmpeg", "ffprobe": shutil.which("ffprobe") or "ffprobe",
    }
    p = m[khoa]
    if khoa in ("du_lieu", "kho_chi_muc", "tai_len", "nhat_ky", "du_an"):
        os.makedirs(p, exist_ok=True)
    return p


def doc_json(p, mac_dinh=None):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return mac_dinh


# ----------------------------------------------------------------------------- 1.2.19 (E2/E3): OpenCV + đường dẫn có dấu, ổ đĩa, đường ASCII
def cv_doc(p, flags=None):
    """cv2.imread an toàn với đường dẫn có dấu tiếng Việt (thư mục người dùng có dấu): đọc bytes → imdecode"""
    import cv2, numpy as np
    try:
        buf = np.fromfile(p, dtype=np.uint8)
    except OSError:
        return None
    if buf.size == 0:
        return None
    return cv2.imdecode(buf, cv2.IMREAD_COLOR if flags is None else flags)


def cv_ghi(p, img, params=None):
    """cv2.imwrite an toàn với đường dẫn có dấu: imencode → tofile. Trả True/False."""
    import cv2
    ext = os.path.splitext(p)[1].lower() or ".png"
    ok, buf = cv2.imencode(ext, img, params or [])
    if not ok:
        return False
    os.makedirs(os.path.dirname(os.path.abspath(p)) or ".", exist_ok=True)
    buf.tofile(p)
    return True


def duong_ascii(p):
    """đường dẫn chỉ ASCII cho thư viện C không đọc được Unicode (OpenCV nạp model, một số DLL): có dấu → chép sang %TEMP%/studio-ascii/"""
    try:
        p.encode("ascii")
        return p
    except UnicodeEncodeError:
        pass
    import hashlib, tempfile, shutil as _sh
    d = os.path.join(tempfile.gettempdir(), "studio-ascii")
    try:
        d.encode("ascii")
    except UnicodeEncodeError:
        d = os.path.join(os.environ.get("SystemDrive", "C:") + os.sep, "studio-ascii") if os.name == "nt" else "/tmp/studio-ascii"
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        return p
    dich = os.path.join(d, hashlib.md5(p.encode("utf-8")).hexdigest()[:10] + "-" + re.sub(r"[^A-Za-z0-9._-]+", "_", os.path.basename(p)))
    try:
        if not os.path.isfile(dich) or os.path.getmtime(dich) < os.path.getmtime(p):
            _sh.copyfile(p, dich)
        return dich
    except OSError:
        return p


def o_dia_trong_gb(p):
    """GB còn trống của ổ chứa p (None nếu không đo được)"""
    try:
        d = p if os.path.isdir(p) else os.path.dirname(os.path.abspath(p))
        while d and not os.path.exists(d):
            d = os.path.dirname(d)
        return shutil.disk_usage(d).free / 1e9
    except Exception:
        return None


def ten_tam(p):
    """tên tệp tạm NGẪU NHIÊN cạnh p (pid + luồng + số ngẫu nhiên): 2 việc song song ghi cùng tệp không giẫm nhau (1.2.21)"""
    return f"{p}.{os.getpid()}-{threading.get_ident() % 100000}-{random.randrange(1 << 20):05x}.tmp"


def ghi_json(p, obj):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    tmp = ten_tam(p)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        for i in range(10):                                  # Windows: tệp đang bị tiến trình khác đọc → replace lỗi thoáng qua
            try:
                os.replace(tmp, p)
                return
            except PermissionError:
                if i == 9:
                    raise
                time.sleep(0.05 * (i + 1))
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass


def don_tep_tam(thu_muc, tuoi_giay=120, duoi=(".tmp", ".tmp.mp4", ".tmp.m4a", ".tmp.mkv", ".tmp.wav"), bo_qua=None):
    """xoá tệp tạm dở (ghi dở rồi bị giết) trong thu_muc (không đệ quy) — chỉ tệp KHÔNG được chạm quá tuoi_giay (tệp đang ghi
    có mtime mới). bo_qua(tên) → True: giữ (tệp của tiến trình khác còn sống, ví dụ alpha sớm). Trả số tệp đã xoá. Dùng khi mở lại việc (1j)."""
    n = 0
    try:
        ds = os.listdir(thu_muc)
    except OSError:
        return 0
    bay = time.time()
    for ten in ds:
        if not (ten.endswith(duoi) or re.search(r"\.\d+-\d+-[0-9a-f]{5}\.tmp$", ten) or re.search(r"\.luot\d+\.mkv$", ten)):
            continue
        if bo_qua is not None and bo_qua(ten):
            continue
        p = os.path.join(thu_muc, ten)
        try:
            if os.path.isfile(p) and bay - os.path.getmtime(p) > tuoi_giay:
                os.remove(p); n += 1
        except OSError:
            pass
    return n


def doc_jsonl(p):
    ra = []
    try:
        with open(p, "r", encoding="utf-8") as f:
            for d in f:
                d = d.strip()
                if d:
                    ra.append(json.loads(d))
    except FileNotFoundError:
        pass
    return ra


_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def python_nen():
    """Python cho tiến trình NỀN tách rời trên Windows: pythonw.exe (không console) — python.exe của .venv là trình phóng,
    chạy DETACHED thì tiến trình con của nó được Windows cấp một cửa sổ console mới (cửa sổ đen). Không có pythonw → sys.executable."""
    if os.name == "nt":
        w = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if os.path.isfile(w):
            return w
    return sys.executable



def sh(cmd, timeout=None, log=None, cwd=None, env=None, nhap=None):
    """chạy lệnh (list) → (mã, stdout, stderr) UTF-8, không mở cửa sổ. log(msg) nếu muốn in lệnh."""
    if log:
        log("$ " + " ".join(str(c) for c in cmd[:12]) + (" …" if len(cmd) > 12 else ""))
    e = dict(os.environ)
    e.setdefault("PYTHONUTF8", "1"); e.setdefault("PYTHONIOENCODING", "utf-8")
    if env:
        e.update(env)
    try:
        r = subprocess.run([str(c) for c in cmd], capture_output=True, timeout=timeout, cwd=cwd, env=e,
                           creationflags=_NO_WINDOW, input=nhap)
        return r.returncode, r.stdout.decode("utf-8", "replace"), r.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as ex:
        return 124, (ex.stdout or b"").decode("utf-8", "replace"), "TIMEOUT " + str(timeout)
    except (OSError, FileNotFoundError) as ex:              # 1.2.21: lệnh không có (nvidia-smi trên máy không NVIDIA, ffmpeg chưa cài) → mã 127, không nổ
        return 127, "", f"{type(ex).__name__}: {ex}"


def chi_cpu():
    """1.2.21: khách chọn "chỉ CPU" (cai-dat.json tang_toc=cpu → Studio đặt STUDIO_CPU_ONLY=1 cho mọi tiến trình con; hoặc cau-hinh v3 tang_toc)"""
    if os.environ.get("STUDIO_CPU_ONLY", "").strip() not in ("", "0"):
        return True
    return str(cau_hinh().get("tang_toc") or "auto").lower() == "cpu"


# ----------------------------------------------------------------------------- 1.2.21 (1e): ffmpeg có tiến độ, treo = không tiến
def chay_ffmpeg(cmd, du_an, buoc, dur=None, im_toi_da=None, cwd=None, env=None):
    """chạy ffmpeg (list, đã có đường ffmpeg ở đầu) với `-progress pipe:1 -nostats`; đọc out_time_us.
    Không tiến trong im_toi_da giây (cau-hinh ffmpeg_im_toi_da_giay, mặc định 300) → giết, trả (124, "TREO <giây> không tiến").
    nhat-ky.txt chỉ ghi khi tiến độ ĐỔI (≥ 10 % hoặc ≥ 60 s) — watchdog 45 phút của Studio nhìn vào đó. Không trần giờ cứng.
    → (mã, stderr). Lệnh ghi ra stdout ("-") không dùng được pipe:1 → chạy sh() thường."""
    cmd = [str(c) for c in cmd]
    if (cmd and cmd[-1] in ("-", "pipe:1", "pipe:")) or "-progress" in cmd:
        ma, _, err = sh(cmd, cwd=cwd, env=env)
        return ma, err
    try:   # tham số: gọi hàm → env STUDIO_FFMPEG_IM_TOI_DA (Studio đặt từ cai-dat.json cho tiến trình con) → cau-hinh v3 → 300
        im_toi_da = float(im_toi_da or os.environ.get("STUDIO_FFMPEG_IM_TOI_DA") or cau_hinh().get("ffmpeg_im_toi_da_giay") or 300)
    except (TypeError, ValueError):
        im_toi_da = 300.0
    im_toi_da = max(30.0, im_toi_da)
    cmd = cmd[:1] + ["-progress", "pipe:1", "-nostats"] + cmd[1:]
    e = dict(os.environ); e.setdefault("PYTHONUTF8", "1")
    if env:
        e.update(env)
    log(du_an, f"$ ffmpeg … ({buoc})")
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, cwd=cwd, env=e,
                             creationflags=_NO_WINDOW)
    except OSError as ex:
        return 127, f"{type(ex).__name__}: {ex}"
    err_buf, tien = [], {"us": -1, "frame": -1, "luc": time.time(), "doi": False}
    khoa = threading.Lock()

    def _doc_err():
        try:
            for d in p.stderr:
                err_buf.append(d)
                if len(err_buf) > 400:
                    del err_buf[:200]
        except Exception:
            pass

    def _doc_out():
        try:
            for d in p.stdout:
                d = d.decode("utf-8", "replace").strip()
                k, _, v = d.partition("=")
                if k in ("out_time_us", "out_time_ms"):      # ffmpeg ≥ 6: out_time_ms thực ra cũng là micro giây
                    try:
                        us = int(v)
                    except ValueError:
                        continue
                    with khoa:
                        if us > tien["us"]:
                            tien["us"], tien["luc"], tien["doi"] = us, time.time(), True
                elif k == "frame":
                    try:
                        f = int(v)
                    except ValueError:
                        continue
                    with khoa:
                        if f > tien["frame"]:
                            tien["frame"], tien["luc"], tien["doi"] = f, time.time(), True
        except Exception:
            pass
    t_err = threading.Thread(target=_doc_err, daemon=True); t_err.start()
    t_out = threading.Thread(target=_doc_out, daemon=True); t_out.start()
    t0, pct_log, luc_log, treo = time.time(), -1.0, time.time(), None
    while True:
        try:
            p.wait(timeout=0.5)
            break
        except subprocess.TimeoutExpired:
            pass
        with khoa:
            im = time.time() - tien["luc"]; doi = tien["doi"]; tien["doi"] = False; us = tien["us"]; fr = tien["frame"]
        if doi:
            pct = (us / 1e6 / dur * 100.0) if (dur and us >= 0) else None
            if pct is None:
                if time.time() - luc_log >= 60:
                    log(du_an, f"ffmpeg {buoc}: " + (f"{us / 1e6:.0f}s" if us >= 0 else f"{fr} khung") + f" · {time.time() - t0:.0f}s")
                    luc_log = time.time()
            elif pct - pct_log >= 10 or time.time() - luc_log >= 60:
                log(du_an, f"ffmpeg {buoc}: {min(100.0, pct):.0f}% ({us / 1e6:.1f}/{dur:.1f}s) · {time.time() - t0:.0f}s")
                pct_log, luc_log = pct, time.time()
        if im > im_toi_da:
            treo = int(im)
            try:
                p.kill()
            except Exception:
                pass
            p.wait()
            break
    t_out.join(timeout=5); t_err.join(timeout=5)
    for f in (p.stdout, p.stderr):                       # R4a: đóng ống ngay (không chờ GC) — dựng dài gọi hàng trăm lần
        try:
            f.close()
        except Exception:
            pass
    err = b"".join(err_buf).decode("utf-8", "replace")
    if treo is not None:
        log(du_an, f"ffmpeg {buoc}: TREO {treo} s không tiến → đã tắt")
        return 124, f"TREO {treo} không tiến\n" + err[-1500:]
    if p.returncode != 0:
        log(du_an, f"ffmpeg lỗi ({buoc}, mã {p.returncode}): {err[-1500:]}")
    return p.returncode, err


def popen(cmd, stdin=None, stdout=None, cwd=None, uu_tien_thap=False):
    e = dict(os.environ); e.setdefault("PYTHONUTF8", "1")
    flags = _NO_WINDOW | (0x00004000 if (uu_tien_thap and os.name == "nt") else 0)   # BELOW_NORMAL_PRIORITY_CLASS
    return subprocess.Popen([str(c) for c in cmd], stdin=stdin, stdout=stdout, stderr=subprocess.DEVNULL, cwd=cwd, env=e,
                            creationflags=flags)


def _bit_depth(pix_fmt):
    m = re.search(r"(10|12|14|16)(?:le|be)?$", pix_fmt or "")
    return int(m.group(1)) if m else 8


def ffprobe(p):
    """→ {"w","h","fps","dur","co_am","codec","xoay","nb_frames", "pix_fmt","bit_depth","color_transfer","color_primaries","color_space","hdr"}; lỗi → None.
    fps: avg_frame_rate trước (đúng với tệp VFR điện thoại), r_frame_rate dự phòng (1.2.21)."""
    ma, out, _ = sh([duong("ffprobe"), "-v", "error", "-print_format", "json", "-show_streams", "-show_format", p])
    if ma != 0:
        return None
    try:
        j = json.loads(out)
    except Exception:
        return None
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), None)
    ra = {"dur": float(j.get("format", {}).get("duration") or 0), "co_am": a is not None, "w": 0, "h": 0, "fps": 30.0, "codec": "", "xoay": 0,
          "pix_fmt": "", "bit_depth": 8, "color_transfer": "", "color_primaries": "", "color_space": "", "hdr": False}
    if v:
        ra["fps"] = 0.0
        for k in ("avg_frame_rate", "r_frame_rate"):
            num, _, den = (v.get(k) or "0/1").partition("/")
            try:
                f = float(num) / float(den or 1)
            except Exception:
                f = 0.0
            if 1.0 <= f <= 240.0:
                ra["fps"] = f
                break
        ra["fps"] = ra["fps"] or 30.0
        ra["w"], ra["h"], ra["codec"] = int(v.get("width") or 0), int(v.get("height") or 0), v.get("codec_name", "")
        ra["pix_fmt"] = v.get("pix_fmt") or ""
        ra["bit_depth"] = int(v.get("bits_per_raw_sample") or 0) or _bit_depth(ra["pix_fmt"])
        ra["color_transfer"] = (v.get("color_transfer") or "").lower()
        ra["color_primaries"] = (v.get("color_primaries") or "").lower()
        ra["color_space"] = (v.get("color_space") or "").lower()
        ra["hdr"] = ra["color_transfer"] in ("arib-std-b67", "smpte2084") or ra["color_primaries"] == "bt2020" \
            or ra["color_space"] in ("bt2020nc", "bt2020c")
        rot = 0
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(float(sd["rotation"]))
        rot = rot or int(float((v.get("tags") or {}).get("rotate", 0) or 0))
        ra["xoay"] = rot % 360
        if ra["xoay"] in (90, 270):
            ra["w"], ra["h"] = ra["h"], ra["w"]
        if not ra["dur"]:
            ra["dur"] = float(v.get("duration") or 0)
        ra["nb_frames"] = int(v.get("nb_frames") or 0)
    return ra


_CO_FILTER = {}


def co_filter(ten):
    """ffmpeg có bộ lọc `ten` không (đọc `ffmpeg -filters` một lần / tiến trình)"""
    if "ds" not in _CO_FILTER:
        ma, out, _ = sh([duong("ffmpeg"), "-hide_banner", "-filters"], timeout=30)
        _CO_FILTER["ds"] = set(re.findall(r"^\s*[A-Z.]{2,3}\s+(\S+)\s+\S+->\S+", out or "", re.M)) if ma == 0 else set()
    return ten in _CO_FILTER["ds"]


def loc_mau_vao(info):
    """1.2.21 (1f): chuỗi filter đặt TRƯỚC scale khi đọc nguồn, theo ffprobe(info):
    HDR (HLG/PQ/bt2020) → tonemap về BT.709 (zscale+hable; thiếu zscale → colorspace); 10-bit SDR → format=yuv420p; 8-bit → "".
    Dùng ở proxy, ghép nguồn, base, lớp video, broll, học mẫu — một chỗ, mọi nơi cùng màu."""
    info = info or {}
    if info.get("hdr"):
        if co_filter("zscale") and co_filter("tonemap"):
            return ("zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
                    "zscale=t=bt709:m=bt709:r=tv,format=yuv420p")
        iall = "bt2020" if (info.get("color_primaries") == "bt2020" or str(info.get("color_space", "")).startswith("bt2020")) else "bt709"
        return f"colorspace=all=bt709:iall={iall}:format=yuv420p"
    if int(info.get("bit_depth") or 8) > 8 or str(info.get("pix_fmt") or "").endswith(("10le", "12le", "10be", "16le")):
        return "format=yuv420p"
    return ""


MAU_RA_BT709 = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709"]   # gắn thẻ màu cho base/đoạn (đoạn đọc base ra RGB đúng ma trận)


def bam(x):
    """sha256[:16] của obj JSON / chuỗi / file (đường dẫn + size + mtime để nhanh)"""
    h = hashlib.sha256()
    if isinstance(x, (dict, list, tuple)):
        h.update(json.dumps(x, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    elif isinstance(x, str) and os.path.isfile(x):
        st = os.stat(x)
        h.update(f"{os.path.abspath(x)}|{st.st_size}|{int(st.st_mtime)}".encode("utf-8"))
    else:
        h.update(str(x).encode("utf-8"))
    return h.hexdigest()[:16]


def khong_dau(s):
    s = NFC(s or "").replace("đ", "d").replace("Đ", "D")          # đ/Đ không tách dấu khi NFD → đổi TRƯỚC khi bỏ dấu
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii").lower()


def slug(s, dai=48):
    s = khong_dau(NFC(s)).replace("đ", "d")
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:dai] or "x"


def log(du_an, msg):
    """in + ghi du_an/nhat-ky.txt (Studio đọc file này để hiện tiến độ)"""
    dong = time.strftime("%H:%M:%S ") + str(msg)
    try:
        print(dong, flush=True)
    except Exception:
        pass
    if du_an:
        try:
            with open(os.path.join(du_an, "nhat-ky.txt"), "a", encoding="utf-8") as f:
                f.write(dong + "\n")
        except Exception:
            pass


class DoThoiGian:
    """with DoThoiGian(du_an, "proxy"): …  → ghi {"buoc","giay","luc"} vào nhat-ky-thoi-gian.json"""

    def __init__(self, du_an, buoc):
        self.du_an, self.buoc = du_an, buoc

    def __enter__(self):
        self.t0 = time.time()
        log(self.du_an, f"▶ {self.buoc}")
        return self

    _KHOA = threading.Lock()      # R4a (1.2.21): b_doc chạy lời/mặt/khung/b-roll 4 luồng, mỗi luồng một DoThoiGian — đọc-sửa-ghi cùng tệp phải khoá

    def __exit__(self, *a):
        g = time.time() - self.t0
        log(self.du_an, f"■ {self.buoc} {g:.1f}s" + (" (lỗi)" if a[0] else ""))
        if self.du_an:
            p = os.path.join(self.du_an, "nhat-ky-thoi-gian.json")
            with DoThoiGian._KHOA:
                d = doc_json(p, []) or []
                d.append({"buoc": self.buoc, "giay": round(g, 2), "luc": time.strftime("%Y-%m-%d %H:%M:%S"), "loi": bool(a[0])})
                try:
                    ghi_json(p, d)
                except OSError as ex:                       # tiến trình khác (alpha sớm) đang giữ tệp → không làm hỏng bước vì một dòng đo giờ
                    log(None, f"nhat-ky-thoi-gian.json: không ghi được ({ex})")
        return False


def _ung_vien_hw():
    """(hwaccel ứng viên, encoder ứng viên) theo hệ — Mac: videotoolbox (1.2.21)"""
    if sys.platform == "darwin":
        return [("videotoolbox", ["-hwaccel", "videotoolbox"])], ["h264_videotoolbox"]
    if os.name == "nt":
        return [("cuda", ["-hwaccel", "cuda"]), ("qsv", ["-hwaccel", "qsv"]), ("d3d11va", ["-hwaccel", "d3d11va"])], ["h264_nvenc", "h264_qsv", "h264_amf"]
    return [("cuda", ["-hwaccel", "cuda"]), ("vaapi", ["-hwaccel", "vaapi"]), ("qsv", ["-hwaccel", "qsv"])], ["h264_nvenc", "h264_vaapi", "h264_qsv"]


def _thu_hwaccel():
    """thử giải mã bằng phần cứng và mã hoá NVENC/QSV/AMF/VideoToolbox trên một clip tổng hợp 1 giây"""
    ff = duong("ffmpeg")
    tam = os.path.join(duong("nhat_ky"), f"_thu-{os.getpid()}.mp4")
    sh([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30:duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", tam])
    hw = "none"
    hw_ds, enc_ds = _ung_vien_hw()
    for ten, args in hw_ds:
        ma, _, err = sh([ff, "-v", "error"] + args + ["-i", tam, "-f", "null", "-"], timeout=60)
        if ma == 0 and "Error" not in err:
            hw = ten
            break
    enc = "libx264"
    for ten in enc_ds:
        ma, _, err = sh([ff, "-v", "error", "-y", "-i", tam, "-c:v", ten, "-f", "null", "-"], timeout=60)
        if ma == 0:
            enc = ten
            break
    try:
        os.remove(tam)
    except Exception:
        pass
    return hw, enc


# ---------------------------------------------------------------- phan-cung.json: đọc-sửa-ghi có khoá (1.2.21, 1b)
KHOA_GIU = ("ma_hoa", "giai_ma", "whisper", "proxy", "hwaccel_loi", "encoder_loi", "nang_luc", "chuan")   # khoá của nen_tang/đo — không bị đo lại ghi đè


def _duong_phan_cung():
    return os.path.join(duong("du_lieu"), "phan-cung.json")


def _khoa_tep(f, mo=True, cho_toi_da=120.0):
    """khoá / mở khoá tệp .lock → True khi được. R4a (1.2.21): Windows dùng LK_NBLCK + vòng chờ ngắn (5–25 ms) tới cho_toi_da giây —
    LK_LOCK cũ chỉ thử 10 lần cách 1 s rồi ném OSError (bị nuốt): 2 tiến trình ghi dồn dập → bên chờ trượt 10 lần liền → ghi KHÔNG khoá
    → mất cập nhật (đo 2 × 50 lần: tổng 99). Hết cho_toi_da vẫn không khoá được → False (người gọi ghi nhật ký, vẫn ghi để không treo việc)."""
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            if not mo:
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                return True
            het = time.time() + cho_toi_da
            while True:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                    return True
                except OSError:
                    if time.time() > het:
                        return False
                    time.sleep(0.005 + random.random() * 0.02)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX if mo else fcntl.LOCK_UN)
            return True
    except OSError:
        return False


_PC_CACHE = None


def cap_nhat_phan_cung(fn):
    """ĐỌC-SỬA-GHI phan-cung.json dưới khoá tệp (phan-cung.json.lock): fn(d) sửa dict tại chỗ (trả dict mới cũng được).
    Nhiều tiến trình (dựng, bác sĩ, nen_tang) ghi cùng lúc không mất khoá của nhau. → dict sau khi ghi."""
    global _PC_CACHE
    p = _duong_phan_cung()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".lock", "a+") as lk:
        if not _khoa_tep(lk, True):
            log(None, "phan-cung.json: không khoá được tệp sau 120 s → ghi không khoá (có thể đè cập nhật của tiến trình khác)")
        try:
            d = doc_json(p) or {}
            r = fn(d)
            if isinstance(r, dict):
                d = r
            ghi_json(p, d)
        finally:
            _khoa_tep(lk, False)
    _PC_CACHE = None
    return d


def _ap_che_do(d):
    """áp lựa chọn phiên lên bản đo (KHÔNG ghi tệp): chỉ CPU → không hwaccel/encoder phần cứng/ORT CPU; encoder từng lỗi → libx264"""
    d = dict(d)
    d["encoder_do"] = d.get("encoder_do") or d.get("encoder")
    if chi_cpu():
        d.update(hwaccel="none", encoder="libx264", ort="CPUExecutionProvider", chi_cpu=True)
        return d
    enc = d.get("encoder") or ""
    if enc and enc != "libx264" and loi_con_hieu_luc(d, "encoder_loi", enc):      # R4a: có THỜI HẠN (1 h × 2^(lan−1), ≤ 24 h) — hết hạn thử lại
        d["encoder_bo"] = enc
        d["encoder"] = "libx264"
    # R4a/B3 (1.2.21): provider ORT (DML/CoreML/CUDA) từng hỏng (doc/alpha ghi ort_loi + ort_loi_luc), lỗi còn hiệu lực (cùng thời hạn)
    # và chưa "Đo lại" từ đó (giờ đo d["luc"] không mới hơn giờ lỗi) → ort = CPU để hang_may / bác sĩ / tóm tắt cùng thấy "AI trên CPU"
    pv = d.get("ort") or ""
    if pv and pv != "CPUExecutionProvider" and loi_con_hieu_luc(d, "ort_loi", pv):
        luc_loi = str(((d.get("ort_loi_luc") or {}).get(pv) or {}).get("luc") or "")
        luc_do = str(d.get("luc") or "")
        if not (luc_loi and luc_do and luc_do > luc_loi):
            d["ort_bo"] = pv
            d["ort"] = "CPUExecutionProvider"
    return d


def phan_cung(lam_moi=False):
    """→ {"luong","ram_gb","gpu","hwaccel","encoder","ort", "hwaccel_loi","encoder_loi","nang_luc",…} (đo một lần, lưu du_lieu/phan-cung.json).
    1.2.21: đo lại KHÔNG ghi đè các khoá nen_tang/đo (KHOA_GIU); ghi qua cap_nhat_phan_cung; STUDIO_CPU_ONLY / tang_toc=cpu → CPU thuần;
    encoder có trong encoder_loi (≥ 1 lần) → libx264 tới khi khách bấm "Đo lại" (lam_moi xoá encoder_loi/hwaccel_loi)."""
    global _PC_CACHE
    p = _duong_phan_cung()
    if _PC_CACHE is not None and not lam_moi:
        return _ap_che_do(_PC_CACHE)
    cu = doc_json(p) or {}
    if cu and not lam_moi and cu.get("khoa") == khoa_chuan():   # đổi card / driver / ffmpeg → đo lại (hwaccel, encoder, ort, VRAM)
        _PC_CACHE = cu
        return _ap_che_do(cu)
    d = {"luong": os.cpu_count() or 4, "ram_gb": 8, "gpu": "", "he": platform.system(), "khoa": khoa_chuan()}
    try:
        if os.name == "nt":
            import ctypes
            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            ms = MS(); ms.dwLength = ctypes.sizeof(MS); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
            d["ram_gb"] = round(ms.ullTotalPhys / 2**30, 1)
        else:
            d["ram_gb"] = round(ram_tong_gb(), 1)
    except Exception:
        pass
    nv = shutil.which("nvidia-smi")                          # 1.2.21: máy không NVIDIA → không gọi (trước: FileNotFoundError chết ngay bước đọc)
    ma, out = (sh([nv, "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader,nounits"], timeout=20)[:2] if nv else (127, ""))
    if ma == 0 and out.strip():
        phan = [x.strip() for x in out.strip().splitlines()[0].split(",")]
        d["gpu"] = ", ".join(phan[:2])
        try:
            d["vram_gb"] = round(float(phan[2]) / 1024, 1)        # alpha.py: VRAM ≥ 4 GB → batch MODNet lớn hơn
        except (IndexError, ValueError):
            pass
    try:
        import onnxruntime as ort
        pr = ort.get_available_providers()
        d["ort"] = "DmlExecutionProvider" if "DmlExecutionProvider" in pr else "CPUExecutionProvider"
    except Exception:
        d["ort"] = "CPUExecutionProvider"
    d["hwaccel"], d["encoder"] = _thu_hwaccel()
    d["luc"] = time.strftime("%Y-%m-%d %H:%M")

    def _gop(cu_tep):
        for k, v in cu_tep.items():                          # giữ MỌI khoá không phải số vừa đo (nen_tang: ma_hoa/giai_ma/whisper; hwaccel_loi, encoder_loi, nang_luc, chuan…)
            if k not in d and not (lam_moi and k in ("hwaccel_loi", "encoder_loi", "ort_loi", "ort_loi_luc")):   # lam_moi ("Đo lại") → quên lỗi (kể cả ORT/alpha) để thử lại phần cứng
                d[k] = v
        cu_tep.clear(); cu_tep.update(d)
    _PC_CACHE = cap_nhat_phan_cung(_gop)
    return _ap_che_do(_PC_CACHE)


def nho_loi_phan_cung(loai, khoa, loi=""):
    """nhớ vào phan-cung.json CÓ THỜI HẠN (R4a, 1.2.21): loai="hwaccel_loi" (khoá codec|cỡ) | "encoder_loi" (h264_nvenc) | "ort_loi" (provider)
    → {"lan": n, "luc": epoch, "luc_chu": "YYYY-mm-dd HH:MM", "loi": "..."} (lan cộng dồn; giá trị `True` cũ = lan 1, luc 0).
    Hiệu lực xét bằng loi_con_hieu_luc(): 1 lần → 1 giờ, 2 → 2 giờ, 3 → 4 giờ … tối đa 24 giờ; hết hạn → thử lại GPU, lỗi tiếp → lan+1.
    Gọi được từ mọi tiến trình (khoá tệp). "Đo lại" (lam_moi) xoá."""
    if not khoa:
        return
    def _f(d):
        m = d.setdefault(loai, {})
        c = m.get(khoa) if isinstance(m.get(khoa), dict) else ({"lan": 1} if m.get(khoa) else {})
        m[khoa] = {"lan": int(c.get("lan") or 0) + 1, "luc": time.time(), "luc_chu": time.strftime("%Y-%m-%d %H:%M"), "loi": str(loi)[-200:]}
    try:
        cap_nhat_phan_cung(_f)
    except Exception:
        pass


HAN_LOI_GIO_TOI_DA = 24.0


def _epoch_cua(luc):
    """luc: epoch (số) | chuỗi "YYYY-mm-dd HH:MM[:SS]" (bản ghi trước R4a) | thiếu → 0"""
    if isinstance(luc, (int, float)):
        return float(luc)
    s = str(luc or "").strip()
    for dinh_dang in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return time.mktime(time.strptime(s, dinh_dang))
        except ValueError:
            pass
    return 0.0


def loi_con_hieu_luc(pc, loai, khoa, bay=None):
    """lỗi phần cứng đã nhớ (hwaccel_loi / encoder_loi / ort_loi) còn hiệu lực không → bool.
    Hiệu lực khi now − luc < min(24 h, 1 h × 2^(lan−1)); cau-hinh v3 {"loi_gpu_vinh_vien": true} → luôn hiệu lực (như 1.2.20 trở về trước).
    Khách KHÔNG mất GPU vĩnh viễn vì một lần card bận (L2 biên bản R4a); hết hạn thử lại, lỗi tiếp thì lan+1 (thời hạn gấp đôi)."""
    v = ((pc or {}).get(loai) or {}).get(khoa)
    if not v:
        return False
    if cau_hinh().get("loi_gpu_vinh_vien"):
        return True
    if not isinstance(v, dict):                                  # `True` cũ: lan 1, luc 0 → coi như hết hạn (thử lại GPU)
        lan, luc = 1, 0.0
    else:
        lan, luc = max(1, int(v.get("lan") or 1)), _epoch_cua(v.get("luc"))
    han = min(HAN_LOI_GIO_TOI_DA * 3600.0, 3600.0 * (2 ** (lan - 1)))
    return ((bay if bay is not None else time.time()) - luc) < han


# ---------------------------------------------------------------- HẠNG MÁY → công suất
BANG_HANG = {
    # whisper · luồng whisper (trừ) · proxy cao · sprite song song (trừ) · x264 preset · MODNet ref · alpha cạnh ngắn · khúc song song
    "A": {"whisper": "large-v3-turbo", "whisper_tru": 1, "proxy_cao": 960, "sprite_tru": 0, "sprite_toi_da": 10, "x264_preset": "veryfast", "alpha_ref": 512, "alpha_canh_ngan": 720, "khuc_song_song": 3},
    "B": {"whisper": "large-v3-turbo", "whisper_tru": 2, "proxy_cao": 960, "sprite_tru": 1, "sprite_toi_da": 6, "x264_preset": "veryfast", "alpha_ref": 512, "alpha_canh_ngan": 720, "khuc_song_song": 2},
    "C": {"whisper": "large-v3-turbo", "whisper_tru": 1, "proxy_cao": 720, "sprite_tru": 1, "sprite_toi_da": 3, "x264_preset": "superfast", "alpha_ref": 384, "alpha_canh_ngan": 540, "khuc_song_song": 1},
    "D": {"whisper": "small", "whisper_tru": 0, "proxy_cao": 540, "sprite_tru": 0, "sprite_toi_da": 2, "x264_preset": "ultrafast", "alpha_ref": 320, "alpha_canh_ngan": 480, "khuc_song_song": 1},
}


NGUONG_TOC_DO = (("A", 120), ("B", 240), ("C", 480))   # giây máy cho 1 phút video thành phẩm → hạng (vượt 480 s → D)
_THU_TU = "ABCD"
GIA_TRI_TRUNG_TINH = {"nhan_giong": 40.0, "tach_nguoi": 60.0, "ma_hoa": 60.0, "o_dia": 5.0}   # thiếu số đo → giữa hạng B


def _so(x, n=1):
    return f"{x:.{n}f}".replace(".", ",")


def _hang_thong_so(pc):
    """hạng theo THÔNG SỐ (cách cũ). Điểm: luồng (≥12:3, ≥8:2, ≥6:1) + RAM (≥16:2, ≥12:1) + GPU cho AI (1)
    + mã hoá phần cứng (1) + Apple Silicon (2) → ≥6 A · ≥4 B · ≥2 C · còn lại D."""
    luong, ram = int(pc.get("luong") or 4), float(pc.get("ram_gb") or 8)
    diem = (3 if luong >= 12 else 2 if luong >= 8 else 1 if luong >= 6 else 0) + (2 if ram >= 16 else 1 if ram >= 12 else 0)
    diem += 1 if pc.get("ort") in ("DmlExecutionProvider", "CoreMLExecutionProvider", "CUDAExecutionProvider") else 0
    diem += 1 if (pc.get("encoder") or "libx264") != "libx264" else 0
    if pc.get("he") == "Darwin" and platform.machine() == "arm64":
        diem += 2
    return ("A" if diem >= 6 else "B" if diem >= 4 else "C" if diem >= 2 else "D"), diem


def uoc_1_phut(ch):
    """số đo chuẩn → giây máy cần cho 1 phút video thành phẩm 1080×1920 30 fps (1800 khung), theo từng phần + "tong".
    Cách suy ra (kỹ thuật — chỉ dùng số đo, không cảm tính):
      nhan_giong = 2,2 × whisper_giay      whisper_giay đo trên 8 s lời thật, nhưng Whisper luôn chạy bộ mã hoá trên cửa sổ đủ 30 s
                                           → 1 phút lời ≈ 2 cửa sổ; ×1,1 cho phần giải mã khi lời dày hơn mẫu 8 s.
                                           Quá giờ đo → 2,2 × thời hạn đã cho (cận dưới).
      tach_nguoi = 0,5 × 1800 × modnet_ms/1000   MODNet mạng 512 (512×928 với 9:16) mỗi khung; Studio không tách cả video —
                                           giả định ≈ ½ thời lượng cần rãnh alpha (chữ sau người, đổi nền).
      ma_hoa     = 2 × 1800 / x264_fps     x264 veryfast 1080×1920 trên nguồn có hạt nhiễu (gần cảnh quay thật): 1 lượt bản xuất
                                           + ≈ 1 lượt quy đổi cho proxy 960p, khúc cache, vẽ lớp phủ (cùng CPU).
      o_dia      = 800 MB / o_ghi_mb_s     nguồn ≈ 150 MB/phút đọc 2 lần + ≈ 500 MB ghi trung gian (proxy, alpha, khúc, bản xuất).
    Thiếu một số đo → GIA_TRI_TRUNG_TINH (giữa hạng B) cho phần đó, ghi vào "thieu"."""
    t, thieu = {}, []
    if ch.get("whisper_giay"):
        t["nhan_giong"] = 2.2 * float(ch["whisper_giay"])
    elif ch.get("whisper_qua_han"):
        t["nhan_giong"] = 2.2 * float(ch["whisper_qua_han"])
    if ch.get("modnet_ms"):
        t["tach_nguoi"] = 0.5 * 1800 * float(ch["modnet_ms"]) / 1000
    if ch.get("x264_fps"):
        t["ma_hoa"] = 2 * 1800 / float(ch["x264_fps"])
    if ch.get("o_ghi_mb_s"):
        t["o_dia"] = 800 / float(ch["o_ghi_mb_s"])
    for k, v in GIA_TRI_TRUNG_TINH.items():
        if k not in t:
            t[k] = v
            thieu.append(k)
    t = {k: round(v, 1) for k, v in t.items()}
    t["tong"] = round(sum(t.values()), 1)
    t["thieu"] = thieu
    t["nut_that"] = max(GIA_TRI_TRUNG_TINH, key=lambda k: t[k])
    return t


_TEN_PHAN = {"nhan_giong": "nhận giọng", "tach_nguoi": "tách người", "ma_hoa": "mã hoá", "o_dia": "ổ đĩa"}


def _uoc_tu_nang_luc(nl, pc):
    """BẢN KÊ NĂNG LỰC (đo bằng việc thật, 1.2.21) → giây máy cho 1 phút video 1080×1920 30 fps, cùng công thức uoc_1_phut:
      ma_hoa     = 2 × 1800 / fps của ENCODER ĐANG DÙNG (pc["encoder"]; không có số → libx264)
      tach_nguoi = 0,5 × 1800 × ms_khung / 1000
      nhan_giong = giay_moi_phut (đã gồm hệ số cửa sổ 30 s của Whisper)
      o_dia      = 800 / mb_s"""
    ch = {}
    mh = nl.get("ma_hoa") or {}
    enc = pc.get("encoder") or "libx264"
    f = (mh.get(enc) or {}).get("fps_1080x1920") or (mh.get("libx264") or {}).get("fps_1080x1920")
    if f:
        ch["x264_fps"] = float(f)
    tn = nl.get("tach_nguoi") or {}
    if tn.get("ms_khung_540"):
        ch["modnet_ms"] = float(tn["ms_khung_540"])
    ng = nl.get("nhan_giong") or {}
    if ng.get("giay_moi_phut"):
        ch["whisper_giay"] = float(ng["giay_moi_phut"]) / 2.2
    od = nl.get("o_dia") or {}
    if od.get("mb_s"):
        ch["o_ghi_mb_s"] = float(od["mb_s"])
    return uoc_1_phut(ch)


def nang_luc_gop(pc):
    """bản kê năng lực DÙNG ĐỂ XẾP HẠNG: bản hiện tại gộp với bản đo trước (nang_luc_truoc — giữ khi bản mới đo lúc máy bận),
    lấy giá trị TỐT HƠN của từng số (fps max, ms/khung min, MB/s max, s/phút min) — đo lúc đang mở app khác không hạ hạng oan."""
    nl = pc.get("nang_luc") or {}
    tr = pc.get("nang_luc_truoc") or {}
    if not nl or not tr or tr.get("khoa") != nl.get("khoa"):
        return nl
    g = json.loads(json.dumps(nl))
    mh = g.setdefault("ma_hoa", {})
    for e, v in (tr.get("ma_hoa") or {}).items():
        if v.get("fps_1080x1920") and float(v["fps_1080x1920"]) > float((mh.get(e) or {}).get("fps_1080x1920") or 0):
            mh[e] = dict(v)
    gm = g.setdefault("giai_ma", {})
    for k, v in (tr.get("giai_ma") or {}).items():
        if v.get("fps") and float(v["fps"]) > float((gm.get(k) or {}).get("fps") or 0):
            gm[k] = dict(v)
    tn, tn0 = g.get("tach_nguoi") or {}, tr.get("tach_nguoi") or {}
    if tn0.get("ms_khung_540") and (not tn.get("ms_khung_540") or float(tn0["ms_khung_540"]) < float(tn["ms_khung_540"])):
        g["tach_nguoi"] = dict(tn0)
    ng, ng0 = g.get("nhan_giong") or {}, tr.get("nhan_giong") or {}
    if ng0.get("giay_moi_phut") and (not ng.get("giay_moi_phut") or float(ng0["giay_moi_phut"]) < float(ng["giay_moi_phut"])):
        g["nhan_giong"] = dict(ng0)
    od, od0 = g.get("o_dia") or {}, tr.get("o_dia") or {}
    if od0.get("mb_s") and float(od0["mb_s"]) > float(od.get("mb_s") or 0):
        g["o_dia"] = dict(od0)
    g["gop_voi_truoc"] = True
    return g


def nang_luc_con_dung(nl=None):
    nl = (phan_cung().get("nang_luc") if nl is None else nl) or {}
    return bool(nl) and nl.get("khoa") == khoa_chuan() and nl.get("phien") == NANG_LUC_PHIEN


def hang_may(pc=None, ha_luong=True):
    """hạng máy A/B/C/D + bảng tham số công suất (mỗi bước đọc ở đây thay vì số cứng).
    · 1.2.21: có BẢN KÊ NĂNG LỰC (phan-cung.json["nang_luc"], đo bằng việc thật — do_chuan) → xếp hạng từ đó (ưu tiên hơn "chuan" cũ);
      mọi tham số máy chọn ghi câu "Máy: … vì …" vào b["mo_ta_may"] (may_chon() ghi nhật ký + nguon.json["may"]).
      cau-hinh.json v3 {"hang_may_tham_so": {"proxy_cao": 720, …}} đè từng giá trị.
    · Có số đo tốc độ thật (do_chuan, mục "chuan" trong phan-cung.json, khoá còn đúng) → xếp theo TỐC ĐỘ:
      ước giây máy cho 1 phút video thành phẩm (uoc_1_phut — cách suy ra ở đó) so với NGUONG_TOC_DO:
        ≤ 120 s (1 phút video ≤ 2 phút máy: dư sức chạy song song 3 khúc, Whisper turbo, proxy 960p)  → A
        ≤ 240 s (≤ 4 phút)                                                                             → B
        ≤ 480 s (≤ 8 phút: video 3 phút chờ ≈ ½ giờ — còn chịu được nếu dùng tham số nhẹ hơn)         → C
        còn lại                                                                                        → D
      KẾT HỢP thông số: tốc độ không đẩy quá 1 bậc trên hạng thông số (RAM/luồng giới hạn chạy song song mà
      phép đo một tác vụ không thấy); số đo lúc máy bận (do_luc_may_ban) không kéo quá 1 bậc dưới hạng thông số.
    · Không có / số đo cũ (đổi ffmpeg, driver, số luồng) → theo thông số như trước (_hang_thong_so).
    · cau-hinh.json {"v3": {"hang_may": "B"}} ép hạng (người dùng/bác sĩ máy).
    · ha_luong: hệ đang bận > 60% CPU (luong_ranh) → sprite_luong / whisper_luong không vượt số luồng còn rảnh (tối thiểu 2).
    "ly_do" = câu giải thích cho Bác sĩ máy hiện."""
    pc = pc or phan_cung()
    ep = str(cau_hinh().get("hang_may") or "").upper()
    luong, ram = int(pc.get("luong") or 4), float(pc.get("ram_gb") or 8)
    hang_ts, diem = _hang_thong_so(pc)
    ch = pc.get("chuan") or None
    ly_do, hang_td, uoc = [], None, None
    ts_mo_ta = f"{luong} luồng, {_so(ram)} GB RAM, {'GPU cho AI' if pc.get('ort') not in (None, 'CPUExecutionProvider') else 'AI trên CPU'}, mã hoá {pc.get('encoder') or 'libx264'}"
    nl = nang_luc_gop(pc) or None
    if ep in BANG_HANG:
        hang = ep
        ly_do.append(f"ép hạng {ep} trong cau-hinh.json")
    elif nl and nang_luc_con_dung(nl):
        uoc = _uoc_tu_nang_luc(nl, pc)
        hang_td = next((h for h, g in NGUONG_TOC_DO if uoc["tong"] <= g), "D")
        i, its = _THU_TU.index(hang_td), _THU_TU.index(hang_ts)
        phan = " · ".join(f"{_TEN_PHAN[k]} {uoc[k]:.0f} s" + (" (ước)" if k in uoc["thieu"] else "") for k in GIA_TRI_TRUNG_TINH)
        ly_do.append(f"năng lực đo {nl.get('luc', '?')}: 1 phút video ≈ {_so(uoc['tong'] / 60)} phút máy ({phan}; nút thắt: {_TEN_PHAN[uoc['nut_that']]}) → {hang_td}")
        if i < its - 1:
            i = its - 1
            ly_do.append(f"thông số chỉ cho tối đa {_THU_TU[i]}")
        if nl.get("do_luc_may_ban") and i > its + 1:
            i = its + 1
            ly_do.append("đo lúc máy bận → không hạ quá 1 bậc dưới thông số")
        if nl.get("gop_voi_truoc"):
            ly_do.append("gộp với bản đo trước (lấy số tốt hơn từng mục)")
        hang = _THU_TU[i]
        ly_do.append(f"thông số {hang_ts} ({diem} điểm: {ts_mo_ta})")
    elif ch and chuan_con_dung(ch):
        uoc = uoc_1_phut(ch)
        hang_td = next((h for h, g in NGUONG_TOC_DO if uoc["tong"] <= g), "D")
        i, its = _THU_TU.index(hang_td), _THU_TU.index(hang_ts)
        phan = " · ".join(f"{_TEN_PHAN[k]} {uoc[k]:.0f} s" + (" (ước)" if k in uoc["thieu"] else "") for k in GIA_TRI_TRUNG_TINH)
        ly_do.append(f"tốc độ đo {ch.get('luc', '?')}: 1 phút video ≈ {_so(uoc['tong'] / 60)} phút máy ({phan}; nút thắt: {_TEN_PHAN[uoc['nut_that']]}) → {hang_td}")
        if i < its - 1:
            i = its - 1
            ly_do.append(f"thông số chỉ cho tối đa {_THU_TU[i]}")
        if ch.get("do_luc_may_ban") and i > its + 1:
            i = its + 1
            ly_do.append(f"đo lúc máy bận → không hạ quá 1 bậc dưới thông số")
        hang = _THU_TU[i]
        ly_do.append(f"thông số {hang_ts} ({diem} điểm: {ts_mo_ta})")
    else:
        hang = hang_ts
        ly_do.append(("số đo tốc độ đã cũ (đổi ffmpeg/driver/CPU) — đo lại; " if ch else "chưa đo tốc độ — ")
                     + f"theo thông số: {ts_mo_ta} → {diem} điểm")
    b = dict(BANG_HANG[hang])
    b.update({"hang": hang, "diem": diem, "luong": luong, "ram_gb": ram, "hang_thong_so": hang_ts, "hang_toc_do": hang_td,
              "giay_1_phut": uoc["tong"] if uoc else None,
              "whisper_luong": max(2, luong - b["whisper_tru"]),
              # 1.2.21: không trần cứng 10 — theo luồng và RAM trống (mỗi luồng vẽ ~0,6 GB)
              "sprite_luong": max(1, min(luong - b["sprite_tru"], max(2, int(ram_trong_gb() / 0.6))))})
    de = cau_hinh().get("hang_may_tham_so") or {}
    if isinstance(de, dict) and de:
        for k, v in de.items():
            if k in b and v not in (None, "", 0):
                b[k] = v
        ly_do.append("cau-hinh đè: " + ", ".join(f"{k}={v}" for k, v in de.items()))
    if ha_luong:
        r = luong_ranh()
        b["may_ban"] = r["ban"]
        if r["ban"] > 0.6:
            tran = max(2, r["luong_ranh"])
            b["whisper_luong"] = min(b["whisper_luong"], tran)
            b["sprite_luong"] = min(b["sprite_luong"], tran)
            ly_do.append(f"máy đang bận {r['ban']:.0%} CPU → tạm dùng ≤ {tran} luồng")
    b["ly_do"] = "; ".join(ly_do)
    # câu "Máy: … vì …" (1b) — mỗi lựa chọn kèm số đo làm căn cứ
    vi = []
    if nl and nang_luc_con_dung(nl):
        mh = (nl.get("ma_hoa") or {}).get(pc.get("encoder") or "libx264") or {}
        if mh.get("fps_1080x1920"):
            vi.append(f"mã hoá 1080p {pc.get('encoder') or 'libx264'} đo {mh['fps_1080x1920']:.0f} fps")
        tn = nl.get("tach_nguoi") or {}
        if tn.get("ms_khung_540"):
            vi.append(f"tách người {tn['ms_khung_540']:.0f} ms/khung ({tn.get('provider', '?')})")
        ng = nl.get("nhan_giong") or {}
        if ng.get("giay_moi_phut"):
            vi.append(f"nghe {ng['giay_moi_phut']:.0f} s/phút lời ({ng.get('model', '?')})")
        od = nl.get("o_dia") or {}
        if od.get("mb_s"):
            vi.append(f"ổ {od['mb_s']:.0f} MB/s")
    elif ch and chuan_con_dung(ch):
        vi.append("số đo chuẩn cũ (chưa có bản kê năng lực)")
    else:
        vi.append(f"chưa đo năng lực — theo thông số {ts_mo_ta}")
    b["do_luc_may_ban"] = bool(nl and nl.get("do_luc_may_ban"))
    b["mo_ta_may"] = (f"Máy: proxy {b['proxy_cao']}p · nghe {b['whisper']} ({b['whisper_luong']} luồng) · tách người cạnh {b['alpha_canh_ngan']} "
                      f"(mạng {b['alpha_ref']}) · vẽ {b['sprite_luong']} luồng · {b['khuc_song_song']} khúc song song · x264 {b['x264_preset']} "
                      f"· hạng {hang} vì " + "; ".join(vi)
                      + (" (đo lúc máy bận — bấm Đo lại máy khi rảnh)" if b["do_luc_may_ban"] else ""))
    return b


_MAY_DA_GHI = set()


def may_chon(du_an=None, ghi=True):
    """lựa chọn máy đưa ra từ số đo (proxy_cao, model nghe, cạnh ngắn tách người, luồng) → dict cho doc/nguon.json["may"];
    ghi=True → một dòng "Máy: … vì …" vào nhat-ky.txt (mỗi dự án/tiến trình ghi một lần)"""
    b = hang_may(ha_luong=False)
    m = {"mo_ta": b["mo_ta_may"], "hang": b["hang"], "proxy_cao": b["proxy_cao"], "whisper": b["whisper"], "whisper_luong": b["whisper_luong"],
         "alpha_canh_ngan": b["alpha_canh_ngan"], "alpha_ref": b["alpha_ref"], "sprite_luong": b["sprite_luong"],
         "khuc_song_song": b["khuc_song_song"], "x264_preset": b["x264_preset"], "encoder": phan_cung().get("encoder"),
         "hwaccel": phan_cung().get("hwaccel"), "chi_cpu": bool(phan_cung().get("chi_cpu")), "ly_do": b["ly_do"]}
    if ghi and du_an and du_an not in _MAY_DA_GHI:
        _MAY_DA_GHI.add(du_an)
        log(du_an, b["mo_ta_may"])
    return m


# ---------------------------------------------------------------- MÁY BẬN → hạ luồng
_RANH = {"luc": 0.0, "kq": None}


def _cpu_he_thong():
    """Windows: (rảnh, tổng) tích luỹ đơn vị 100 ns của cả máy — GetSystemTimes (kernel đã gồm idle)"""
    import ctypes
    from ctypes import wintypes
    i, k, u = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(i), ctypes.byref(k), ctypes.byref(u)):
        raise OSError("GetSystemTimes lỗi")
    f = lambda x: (x.dwHighDateTime << 32) | x.dwLowDateTime
    return f(i), f(k) + f(u)


def luong_ranh(cache_giay=10.0):
    """đo nhanh phần CPU cả máy đang bị chiếm → {"ban": 0..1, "luong", "luong_ranh", "cach"}.
    Windows: GetSystemTimes 2 mẫu cách 0,3 s, trừ phần của chính tiến trình này; Mac/Linux: os.getloadavg()[0] / số luồng.
    Giữ kết quả cache_giay giây (hang_may được gọi nhiều lần). Tiến trình con (ffmpeg…) vẫn tính là bận — CPU đó không rảnh thật."""
    now = time.time()
    if _RANH["kq"] and now - _RANH["luc"] < cache_giay:
        return _RANH["kq"]
    luong = os.cpu_count() or 4
    ban, cach = 0.0, "khong_do_duoc"
    try:
        if os.name == "nt":
            r1, t1 = _cpu_he_thong(); p1 = sum(os.times()[:2]); w1 = time.perf_counter()
            time.sleep(0.3)
            r2, t2 = _cpu_he_thong(); p2 = sum(os.times()[:2]); w2 = time.perf_counter()
            ban = 1.0 - (r2 - r1) / max(1, t2 - t1)
            ban -= (p2 - p1) / max(1e-6, (w2 - w1) * luong)
            cach = "GetSystemTimes"
        elif hasattr(os, "getloadavg"):
            ban = os.getloadavg()[0] / luong
            cach = "loadavg"
    except Exception:
        pass
    ban = min(1.0, max(0.0, ban))
    kq = {"ban": round(ban, 3), "luong": luong, "luong_ranh": max(1, int(round(luong * (1 - ban)))), "cach": cach}
    _RANH.update(luc=now, kq=kq)
    return kq


# ---------------------------------------------------------------- ĐO TỐC ĐỘ THẬT (một lần lúc cài / bác sĩ)
CHUAN_PHIEN = 2          # đổi cách đo → số cũ hết dùng (1.2.21: đo cùng lúc với bản kê năng lực)
CHUAN_MUC_TIEU = 30.0    # giây — tổng thời gian đo nhắm tới
CHUAN_TRAN = 60.0        # giây — trần cứng (1b: không kéo dài đo quá 60 s tổng)
NANG_LUC_PHIEN = 2
NGUONG_BAN_KHI_DO = 0.3  # ≥ 30% CPU đã bị chiếm lúc đo → số đo thấp hơn thật đáng kể → gắn cờ do_luc_may_ban


def _driver_gpu():
    """chuỗi driver card màn hình, đọc nhanh không chạy lệnh: Windows → registry lớp Display; Mac → phiên bản macOS"""
    try:
        if os.name == "nt":
            import winreg
            goc = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            ra = []
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, goc) as k:
                for i in range(32):
                    try:
                        ten = winreg.EnumKey(k, i)
                    except OSError:
                        break
                    if not ten.isdigit():
                        continue
                    try:
                        with winreg.OpenKey(k, ten) as kk:
                            ra.append(f"{winreg.QueryValueEx(kk, 'DriverDesc')[0]} {winreg.QueryValueEx(kk, 'DriverVersion')[0]}")
                    except OSError:
                        pass
            return " | ".join(sorted(ra))
        if sys.platform == "darwin":
            return "macOS " + platform.mac_ver()[0]
    except Exception:
        pass
    return ""


def _dau_ffmpeg():
    p = shutil.which("ffmpeg")
    if not p:
        return "khong-co-ffmpeg"
    try:
        p = os.path.realpath(p)
        st = os.stat(p)
        return f"{p}|{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        return p


_KHOA = {}


def khoa_chuan():
    """khoá hiệu lực của số đo: bản ffmpeg (đường + cỡ + giờ sửa tệp) + driver card + số luồng + CHUAN_PHIEN"""
    if "k" not in _KHOA:
        _KHOA["k"] = bam({"ff": _dau_ffmpeg(), "drv": _driver_gpu(), "luong": os.cpu_count(), "v": CHUAN_PHIEN})
    return _KHOA["k"]


def chuan_con_dung(ch=None):
    ch = phan_cung().get("chuan") if ch is None else ch
    return bool(ch) and ch.get("khoa") == khoa_chuan() and ch.get("phien") == CHUAN_PHIEN


def _json_cuoi(out, tien_to="CHUAN"):
    for d in reversed((out or "").splitlines()):
        if d.startswith(tien_to):
            try:
                return json.loads(d[len(tien_to):])
            except Exception:
                return None
    return None


def _do_o(han, mb=200):
    """ghi rồi đọc mb MB tạm trong du_lieu → MB/s. Ghi có fsync (ra đĩa thật); đọc bỏ bộ đệm hệ điều hành khi được
    (Windows FILE_FLAG_NO_BUFFERING, Mac F_NOCACHE, Linux fadvise DONTNEED) — không thì ghi rõ "co_the_dem"."""
    p = os.path.join(duong("du_lieu"), "_chuan-o.tmp")
    khoi = os.urandom(8 << 20)
    viet, t0 = 0, time.perf_counter()
    ra = {}
    try:
        with open(p, "wb", buffering=0) as f:
            while viet < (mb << 20) and time.perf_counter() - t0 < han * 0.6:
                f.write(khoi)
                viet += len(khoi)
            os.fsync(f.fileno())
        g = time.perf_counter() - t0
        ra["o_ghi_mb_s"] = round(viet / 2**20 / max(1e-3, g))
        ra["o_mb"] = viet >> 20
        t0 = time.perf_counter()
        doc, cach = _doc_khong_dem(p, t0 + han * 0.4)
        ra["o_doc_mb_s"] = round(doc / 2**20 / max(1e-3, time.perf_counter() - t0))
        ra["o_doc_cach"] = cach
    finally:
        try:
            os.remove(p)
        except OSError:
            pass
    return ra


def _doc_khong_dem(p, han_luc):
    n = 8 << 20
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.CreateFileW.restype = wintypes.HANDLE
            k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
            k32.VirtualAlloc.restype = ctypes.c_void_p
            k32.VirtualAlloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
            k32.VirtualFree.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
            k32.ReadFile.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
            k32.CloseHandle.argtypes = [wintypes.HANDLE]
            h = k32.CreateFileW(p, 0x80000000, 1, None, 3, 0x20000000 | 0x08000000, None)   # GENERIC_READ, NO_BUFFERING|SEQUENTIAL
            if h and h != wintypes.HANDLE(-1).value:
                buf = k32.VirtualAlloc(None, n, 0x3000, 0x04)                                 # trang bộ nhớ → thẳng hàng sector
                tong, got = 0, wintypes.DWORD(0)
                try:
                    while time.perf_counter() < han_luc:
                        if not k32.ReadFile(h, buf, n, ctypes.byref(got), None) or got.value == 0:
                            break
                        tong += got.value
                finally:
                    k32.VirtualFree(buf, 0, 0x8000)
                    k32.CloseHandle(h)
                if tong:
                    return tong, "khong_dem"
        except Exception:
            pass
    cach = "co_the_dem"
    tong = 0
    with open(p, "rb", buffering=0) as f:
        try:
            if sys.platform == "darwin":
                import fcntl
                fcntl.fcntl(f.fileno(), 48, 1)               # F_NOCACHE
                cach = "khong_dem"
            elif hasattr(os, "posix_fadvise"):
                os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
                cach = "khong_dem"
        except Exception:
            pass
        while time.perf_counter() < han_luc:
            b = f.read(n)
            if not b:
                break
            tong += len(b)
    return tong, cach


def _args_enc_do(enc):
    return {"h264_nvenc": ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "19", "-b:v", "0"],
            "h264_qsv": ["-c:v", "h264_qsv", "-global_quality", "20"],
            "h264_amf": ["-c:v", "h264_amf", "-quality", "balanced"],
            "h264_videotoolbox": ["-c:v", "h264_videotoolbox", "-b:v", "8M"],
            "h264_vaapi": ["-c:v", "h264_vaapi"]}.get(enc, ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"])


def _do_ma_hoa(enc, han, giay=10.0):
    """1b: mã hoá `giay` s testsrc2 1080×1920 30 fps (+ hạt nhiễu ~ cảnh quay thật) bằng encoder `enc`, đọc -progress → fps.
    Quá giờ han → giết nhưng vẫn tính fps từ số khung đã mã hoá (máy chậm không mất số đo)."""
    ff = duong("ffmpeg")
    cmd = [ff, "-v", "error", "-nostdin", "-progress", "pipe:1", "-nostats", "-f", "lavfi", "-i", f"testsrc2=size=1080x1920:rate=30:duration={giay:g}",
           "-vf", "noise=alls=12:allf=t", "-pix_fmt", "yuv420p"] + _args_enc_do(enc) + ["-f", "null", "-"]
    t0 = time.perf_counter()
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, creationflags=_NO_WINDOW)
    except OSError as ex:
        return {"loi": str(ex)[:120]}
    khung = {"n": 0}

    def _doc():
        try:
            for d in p.stdout:
                d = d.decode("utf-8", "replace").strip()
                if d.startswith("frame="):
                    try:
                        khung["n"] = int(d[6:])
                    except ValueError:
                        pass
        except Exception:
            pass
    t = threading.Thread(target=_doc, daemon=True); t.start()
    qua_gio = False
    try:
        p.wait(timeout=max(3.0, han))
    except subprocess.TimeoutExpired:
        qua_gio = True
        try:
            p.kill()
        except Exception:
            pass
        p.wait()
    g = time.perf_counter() - t0
    t.join(timeout=2)
    err = (p.stderr.read() or b"").decode("utf-8", "replace") if p.stderr else ""
    n = khung["n"] if qua_gio else int(round(giay * 30))
    if (p.returncode != 0 and not qua_gio) or n < 10:
        return {"loi": (err.strip()[-160:] or f"mã {p.returncode}")}
    return {"fps_1080x1920": round(n / max(1e-3, g), 1), "qua_gio": qua_gio} if qua_gio else {"fps_1080x1920": round(n / max(1e-3, g), 1)}


def _do_giai_ma(han):
    """1b: giải mã h264 8-bit và hevc 10-bit (clip testsrc 3 s 1080×1920 sinh tại chỗ) bằng hwaccel đang có rồi CPU → {"h264|8": {"fps","hwaccel"}, "hevc|10": …}"""
    ff = duong("ffmpeg")
    pc = _PC_CACHE or doc_json(_duong_phan_cung()) or {}
    hw = pc.get("hwaccel") or "none"
    if chi_cpu():
        hw = "none"
    tam = os.path.join(duong("nhat_ky"), f"_giai-{os.getpid()}")
    ra = {}
    t_het = time.perf_counter() + max(4.0, han)
    for ten, enc_args in (("h264|8", ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p"]),
                          ("hevc|10", ["-c:v", "libx265", "-preset", "ultrafast", "-pix_fmt", "yuv420p10le", "-x265-params", "log-level=none"])):
        clip = f"{tam}-{ten.replace('|', '')}.mp4"
        ma, _, err = sh([ff, "-v", "error", "-y", "-nostdin", "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=3"] + enc_args + [clip],
                        timeout=max(3.0, t_het - time.perf_counter()))
        if ma != 0 or not os.path.isfile(clip):
            ra[ten] = {"loi": (err or "").strip()[-120:] or f"không sinh được clip (mã {ma})"}
            continue
        for h in ([hw] if hw != "none" else []) + ["none"]:
            t0 = time.perf_counter()
            ma, _, err = sh([ff, "-v", "error", "-nostdin"] + (["-hwaccel", h] if h != "none" else []) + ["-i", clip, "-f", "null", "-"],
                            timeout=max(3.0, t_het - time.perf_counter()))
            g = time.perf_counter() - t0
            if ma == 0 and "Error" not in (err or ""):
                ra[ten] = {"fps": round(90 / max(1e-3, g), 1), "hwaccel": h}
                break
            ra[ten] = {"loi": (err or "").strip()[-120:] or f"mã {ma}", "hwaccel": h}
        try:
            os.remove(clip)
        except OSError:
            pass
    return ra


def _do_x264(han):
    """(giữ tên cho mã cũ) x264 veryfast 1080×1920 → x264_fps"""
    r = _do_ma_hoa("libx264", han)
    return {"x264_fps": r["fps_1080x1920"]} if r.get("fps_1080x1920") else {"loi_x264": r.get("loi", "?")}


_MA_MODNET = r'''
import sys, os, time, json
sys.path.insert(0, sys.argv[1])
import numpy as np
from doc import alpha as A
t0 = time.perf_counter(); s, pv = A._session(); mo = time.perf_counter() - t0
rw, rh, pw, ph = A._kich_thuoc_mang(1080, 1920, 512)
x = A._tien_xu_ly([np.random.default_rng(1).integers(0, 255, (1920, 1080, 3), dtype=np.uint8)], rw, rh, pw, ph)
ghi_chu = ""
try:
    t0 = time.perf_counter(); A._suy_luan(s, x); dau = time.perf_counter() - t0
except Exception as ex:
    ghi_chu = pv + " lỗi: " + str(ex)[:80]
    s, pv = A._session("CPUExecutionProvider")
    t0 = time.perf_counter(); A._suy_luan(s, x); dau = time.perf_counter() - t0
han_s = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0
ds, han = [], time.perf_counter() + han_s
while len(ds) < 20 and (not ds or time.perf_counter() < han):          # 1b: 20 khung (hoặc hết giờ) — trung vị
    t0 = time.perf_counter(); A._suy_luan(s, x); ds.append(time.perf_counter() - t0)
ds.sort()
print("CHUAN" + json.dumps({"modnet_ms": round(1000 * ds[len(ds) // 2], 1), "modnet_ms_dau": round(1000 * dau, 1), "modnet_khung": len(ds),
      "modnet_provider": pv, "modnet_mang": [pw, ph], "modnet_mo_s": round(mo, 2), "modnet_ghi_chu": ghi_chu}))
'''

_MA_WHISPER = r'''
import sys, os, time, json
import numpy as np
skill, luong, ten_cfg = sys.argv[1], int(sys.argv[2]), sys.argv[3]
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio
ung_vien = ["mobiuslabsgmbh/faster-whisper-large-v3-turbo", "large-v3-turbo"] if ten_cfg in ("", "large-v3-turbo") else [ten_cfg]
m, ten, t0 = None, None, time.perf_counter()
for uv in ung_vien:
    try:
        m = WhisperModel(uv, device="cpu", compute_type="int8", cpu_threads=luong, local_files_only=True); ten = uv; break
    except Exception:
        pass
nap = time.perf_counter() - t0
if m is None:
    print("CHUAN" + json.dumps({"whisper_loi": "chưa có model " + (ten_cfg or "large-v3-turbo") + " trên máy (không tải mới)"})); sys.exit(0)
GIAY = 10                                         # 1b: 10 s lời
x, am = [], "giong-thu"
for i in range(6):
    p = os.path.join(skill, "v2", "giong-thu", f"giong-{i}.mp3")
    if os.path.isfile(p):
        try:
            x.append(decode_audio(p))
        except Exception:
            pass
    if sum(len(a) for a in x) >= 16000 * GIAY:
        break
if sum(len(a) for a in x) >= 16000 * GIAY:
    x = np.concatenate(x)[:16000 * GIAY].astype(np.float32)
elif x:                                           # lời mẫu ngắn hơn 10 s → lặp cho đủ
    x = np.concatenate(x).astype(np.float32)
    x = np.tile(x, int(np.ceil(16000 * GIAY / max(1, len(x)))))[:16000 * GIAY]
else:                                             # không có lời mẫu → âm tổng hợp (VAD sẽ bỏ hết nên tắt VAD)
    am = "sine"
    t = np.arange(16000 * GIAY) / 16000.0
    x = (0.3 * np.sin(2 * np.pi * 220 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t))).astype(np.float32)
t0 = time.perf_counter()
seg, info = m.transcribe(x, language="vi", beam_size=1, vad_filter=(am != "sine"), word_timestamps=True,
                         condition_on_previous_text=False, temperature=0.0)
chu = " ".join(s.text.strip() for s in seg)
nhan = time.perf_counter() - t0
print("CHUAN" + json.dumps({"whisper_giay": round(nhan, 2), "whisper_nap_giay": round(nap, 2), "whisper_model": ten, "whisper_am_giay": GIAY,
      "whisper_luong": luong, "whisper_am": am, "whisper_chu": chu[:60]}, ensure_ascii=False))
'''


def do_chuan(lam_moi=False, log=None, ep=False):
    """ĐO TỐC ĐỘ THẬT một lần (lúc cài / Bác sĩ máy / nút "Đo lại"), nhắm ≤ CHUAN_MUC_TIEU s, trần cứng CHUAN_TRAN = 60 s (1b):
      (d) ổ: ghi (fsync) + đọc (bỏ bộ đệm) 200 MB tạm trong du_lieu → o_ghi_mb_s, o_doc_mb_s
      (a) mã hoá 10 s testsrc2 1080×1920 30 fps cho TỪNG encoder khả dụng (libx264 + encoder phần cứng đã thử được) → nang_luc.ma_hoa
      (a') giải mã h264 8-bit và hevc 10-bit (hwaccel rồi CPU) → nang_luc.giai_ma
      (b) MODNet mạng 512, 20 khung, provider mặc định (tiến trình riêng: GPU treo không kéo theo) → nang_luc.tach_nguoi
      (c) Whisper model có sẵn (KHÔNG tải mới) nạp + nhận 10 s lời mẫu (v2/giong-thu) → nang_luc.nhan_giong
    Đo CPU đang bị chiếm trước + sau (luong_ranh) → do_luc_may_ban nếu ≥ NGUONG_BAN_KHI_DO.
    Ghi phan-cung.json mục "chuan" (khoá cũ, bác sĩ hiện) + "nang_luc" (BẢN KÊ NĂNG LỰC — hang_may() tính từ đây) qua cap_nhat_phan_cung;
    lam_moi=True (khách bấm "Đo lại") còn xoá encoder_loi/hwaccel_loi/ort_loi để thử lại phần cứng. Trả "chuan".
    R4a: máy đang bận (> 50 % CPU) → KHÔNG đo (số đo lúc bận hạ hạng oan, hạn con không ép được khi GPU bị chiếm): trả
    {"ban": True, "loi": "máy đang bận — đo sau", "ban_cpu": x} và không xoá lỗi đã nhớ; ep=True (khách ép) → đo bất kể."""
    log = log or (lambda m: None)
    if not lam_moi:
        pc = phan_cung()
        cu = pc.get("chuan")
        if cu and chuan_con_dung(cu) and nang_luc_con_dung(pc.get("nang_luc")):
            return cu
    if not ep:
        ban = float(luong_ranh(cache_giay=0).get("ban") or 0)
        if ban > 0.5:
            log(f"máy đang bận {ban:.0%} CPU → không đo (đo sau khi rảnh)")
            return {"ban": True, "loi": "máy đang bận — đo sau", "ban_cpu": round(ban, 2)}
    pc = phan_cung(lam_moi=lam_moi)
    cu = pc.get("chuan")
    if cu and not lam_moi and chuan_con_dung(cu) and nang_luc_con_dung(pc.get("nang_luc")):
        return cu
    t_bd = time.perf_counter()
    con = lambda: CHUAN_TRAN - (time.perf_counter() - t_bd)
    ban_truoc = luong_ranh(cache_giay=0)["ban"]
    ch = {"phien": CHUAN_PHIEN, "khoa": khoa_chuan(), "luong": os.cpu_count() or 4, "driver": _driver_gpu(), "ban_truoc": ban_truoc}
    nl = {"phien": NANG_LUC_PHIEN, "khoa": khoa_chuan(), "ma_hoa": {}, "giai_ma": {}, "tach_nguoi": {}, "nhan_giong": {}, "o_dia": {}}
    ma, out, _ = sh([duong("ffmpeg"), "-version"], timeout=15)
    ch["ffmpeg"] = (out.splitlines() or ["?"])[0][:80]
    try:
        log("đo ổ đĩa…")
        ch.update(_do_o(min(5.0, con())))
        nl["o_dia"] = {"mb_s": ch.get("o_ghi_mb_s"), "doc_mb_s": ch.get("o_doc_mb_s"), "cach": ch.get("o_doc_cach")}
    except Exception as ex:
        ch["loi_o"] = str(ex)[-160:]
    # đo MỌI encoder khả dụng của hệ (libx264 + ứng viên phần cứng theo _ung_vien_hw), KHÔNG phụ thuộc khoá cũ / encoder_loi:
    # encoder không có thì ffmpeg báo lỗi ngay (< 1 s) → ghi {"loi"}; encoder chạy được → fps. Sau đó chọn encoder nhanh nhất.
    encs = ["libx264"] + [e for e in _ung_vien_hw()[1] if e != "libx264"]
    for enc in encs:
        log(f"đo mã hoá {enc}…")
        nl["ma_hoa"][enc] = _do_ma_hoa(enc, max(4.0, min(12.0, con() - 26)))
    tot = sorted((v["fps_1080x1920"], e) for e, v in nl["ma_hoa"].items() if e != "libx264" and v.get("fps_1080x1920") and not v.get("qua_gio"))
    enc_chon = tot[-1][1] if tot else "libx264"
    nl["encoder_chon"] = enc_chon
    if nl["ma_hoa"]["libx264"].get("fps_1080x1920"):
        ch["x264_fps"] = nl["ma_hoa"]["libx264"]["fps_1080x1920"]
    else:
        ch["loi_x264"] = nl["ma_hoa"]["libx264"].get("loi", "?")
    log("đo giải mã h264/hevc…")
    nl["giai_ma"] = _do_giai_ma(max(4.0, min(10.0, con() - 20)))
    log("đo tách người (MODNet, 20 khung)…")
    han_mn = max(8.0, min(16.0, con() - 14))
    ma, out, err = sh([duong("python"), "-c", _MA_MODNET, APP, str(max(2.0, han_mn - 8))], timeout=han_mn, cwd=APP)   # vòng đo dừng sớm 8 s trước hạn (nạp ORT + in kết quả)
    j = _json_cuoi(out)
    ch.update(j if j else {"loi_modnet": ("quá giờ" if ma == 124 else (err or out).strip()[-160:]) or f"mã {ma}"})
    nl["tach_nguoi"] = ({"ms_khung_540": j["modnet_ms"], "provider": j.get("modnet_provider"), "khung": j.get("modnet_khung"), "mang": j.get("modnet_mang")}
                        if j else {"loi": ch.get("loi_modnet")})
    log("đo nhận giọng (Whisper, 10 s)…")
    luong = int(ch["luong"])
    wl = max(2, luong - BANG_HANG[_hang_thong_so(pc)[0]]["whisper_tru"])
    han_wh = max(10.0, con())
    ma, out, err = sh([duong("python"), "-c", _MA_WHISPER, SKILL, str(wl), str(cau_hinh().get("whisper", {}).get("model") or "")],
                      timeout=han_wh, cwd=APP)
    j = _json_cuoi(out)
    if j:
        ch.update(j)
        if j.get("whisper_giay"):
            nl["nhan_giong"] = {"giay_moi_phut": round(2.2 * float(j["whisper_giay"]), 1), "model": j.get("whisper_model"), "giay_10s": j["whisper_giay"],
                                "nap_giay": j.get("whisper_nap_giay"), "luong": wl}
        else:
            nl["nhan_giong"] = {"loi": j.get("whisper_loi")}
    elif ma == 124:
        ch["whisper_qua_han"] = round(han_wh, 1)
        nl["nhan_giong"] = {"giay_moi_phut": round(2.2 * han_wh, 1), "qua_han": True}
    else:
        ch["whisper_loi"] = (err or out).strip()[-160:] or f"mã {ma}"
        nl["nhan_giong"] = {"loi": ch["whisper_loi"]}
    ch["ban_sau"] = luong_ranh(cache_giay=0)["ban"]
    ch["do_luc_may_ban"] = max(ch["ban_truoc"], ch["ban_sau"]) >= NGUONG_BAN_KHI_DO
    ch["tong_giay"] = round(time.perf_counter() - t_bd, 1)
    ch["luc"] = time.strftime("%Y-%m-%d %H:%M")
    nl.update(do_luc=int(time.time()), luc=ch["luc"], tong_giay=ch["tong_giay"], do_luc_may_ban=ch["do_luc_may_ban"])

    def _f(d):
        cu_nl = d.get("nang_luc") or {}
        if nl.get("do_luc_may_ban") and cu_nl.get("khoa") == nl.get("khoa"):   # đo lúc bận → giữ bản tốt nhất đã có (cũ gộp cũ-trước) ở nang_luc_truoc
            d["nang_luc_truoc"] = nang_luc_gop(d) or cu_nl
            d["nang_luc_truoc"].pop("gop_voi_truoc", None)
        elif not nl.get("do_luc_may_ban"):
            d.pop("nang_luc_truoc", None)                    # đo lúc rảnh = bản chuẩn, không cần bản cũ
        d["chuan"] = ch; d["nang_luc"] = nl
        d["encoder"] = enc_chon                              # encoder chọn lại theo fps đo được (chi_cpu / encoder_loi áp lúc đọc: _ap_che_do)
        if lam_moi:
            d.pop("encoder_loi", None); d.pop("hwaccel_loi", None); d.pop("ort_loi", None); d.pop("ort_loi_luc", None)
    cap_nhat_phan_cung(_f)
    return ch


def ti_le(W, H):
    return "9:16" if H > W else "16:9"


def vung_an_toan(W, H):
    """vùng an toàn theo tỉ lệ khung: bảng riêng 9:16 và 16:9 (1.2.21), cau-hinh.json v3.vung_an_toan đè từng bảng"""
    tl = ti_le(W, H)
    md = MAC_DINH["vung_an_toan"].get(tl) or MAC_DINH["vung_an_toan"]["9:16"]
    v = (cau_hinh().get("vung_an_toan") or {}).get(tl) or md
    return {k: float(v.get(k, md[k])) for k in ("tren", "duoi", "trai", "phai")}


def _ram_win():
    import ctypes
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    ms = MS(); ms.dwLength = ctypes.sizeof(MS); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
    return ms.ullTotalPhys / 2**30, ms.ullAvailPhys / 2**30


def ram_tong_gb():
    try:
        if os.name == "nt":
            return _ram_win()[0]
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2**30
    except Exception:
        return 8.0


def ram_trong_gb():
    """GB RAM còn trống — Windows GlobalMemoryStatusEx · Mac vm_stat (free + inactive + speculative) · Linux /proc/meminfo MemAvailable (1.2.21: Mac đọc thật, không trả 4.0)"""
    try:
        if os.name == "nt":
            return _ram_win()[1]
        if sys.platform == "darwin":
            ma, out, _ = sh(["vm_stat"], timeout=10)
            if ma == 0:
                m = re.search(r"page size of (\d+)", out)
                trang = int(m.group(1)) if m else 4096
                tong = 0
                for ten in ("Pages free", "Pages inactive", "Pages speculative"):
                    mm = re.search(ten + r":\s+(\d+)", out)
                    if mm:
                        tong += int(mm.group(1))
                if tong:
                    return tong * trang / 2**30
            ma, out, _ = sh(["sysctl", "-n", "hw.memsize"], timeout=10)
            if ma == 0 and out.strip().isdigit():
                return int(out.strip()) / 2**30 * 0.5
        else:
            with open("/proc/meminfo", encoding="utf-8") as f:
                for d in f:
                    if d.startswith("MemAvailable:"):
                        return int(d.split()[1]) / 2**20
    except Exception:
        pass
    return 4.0


def dat_hf_home():
    """1.2.21 (1h): model Whisper (HuggingFace) đặt vào du_lieu/mo-hinh-hf để gỡ cài biết; ĐÃ có cache ở ~/.cache/huggingface (hoặc HF_HOME
    đã đặt) thì giữ nguyên — không làm khách tải lại 1,6 GB. Gọi một lần lúc import chung."""
    if os.environ.get("HF_HOME") or os.environ.get("HUGGINGFACE_HUB_CACHE"):
        return os.environ.get("HF_HOME")
    cu = os.path.expanduser("~/.cache/huggingface")
    try:
        if os.path.isdir(os.path.join(cu, "hub")) and any(x.startswith("models--") for x in os.listdir(os.path.join(cu, "hub"))):
            return None
    except OSError:
        pass
    try:
        p = os.path.join(duong("du_lieu"), "mo-hinh-hf")
        os.makedirs(p, exist_ok=True)
        os.environ["HF_HOME"] = p
        return p
    except Exception:
        return None


try:
    dat_hf_home()
except Exception:
    pass


def du_an_duong(ten):
    return os.path.join(duong("du_an"), ten)
