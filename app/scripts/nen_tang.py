#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Lớp NỀN TẢNG — mọi chỗ khác nhau giữa Mac và Windows gom về đây. Script khác không tự hỏi hệ điều hành.

    python3 nen_tang.py        # in: hệ điều hành, bộ mã hoá, bộ nhận dạng giọng, bộ tách người đang dùng

| Việc            | Mac (Apple Silicon)            | Windows / Linux                                  |
|-----------------|--------------------------------|--------------------------------------------------|
| Nhận dạng giọng | mlx-whisper                    | faster-whisper (GPU NVIDIA nếu có, không thì CPU) |
| Giải mã nhanh   | -hwaccel videotoolbox          | thử cuda/dxva2/d3d11va/qsv, chọn cách nhanh nhất |
| Mã hoá nhanh    | h264_videotoolbox              | h264_nvenc → h264_qsv → h264_amf → libx264       |
| Tách người      | Apple Vision (tach_nguoi.swift)| MediaPipe Selfie Segmentation                    |
| Kho mặc định    | ~/Movies/VideoKit-Free         | ~/Videos/VideoKit-Free                           |
"""
import functools, os, platform, shutil, subprocess, sys, tempfile

HE = {"Darwin": "mac", "Windows": "win"}.get(platform.system(), "linux")
APPLE_SILICON = HE == "mac" and platform.machine() == "arm64"
DIR = os.path.dirname(os.path.abspath(__file__))


def kho_mac_dinh():
    return os.path.expanduser("~/Movies/VideoKit-Free" if HE == "mac" else "~/Videos/VideoKit-Free")


def tam(ten=""):
    """thư mục tạm hợp lệ trên mọi máy (Windows không có /tmp)"""
    d = os.path.join(tempfile.gettempdir(), "tro-ly-edit-video")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, ten) if ten else d


def python_venv():
    """đường dẫn python trong .venv của skill (Windows: Scripts\\python.exe)"""
    goc = os.path.join(os.path.dirname(DIR), ".venv")
    return os.path.join(goc, "Scripts", "python.exe") if HE == "win" else os.path.join(goc, "bin", "python")


# ───────────────────────────── ffmpeg: giải mã / mã hoá
def lien_ket(nguon, dich):
    """Đặt `dich` trỏ tới file `nguon`: liên kết mềm → liên kết cứng → chép.
    Windows thường cấm liên kết mềm khi chưa bật Developer Mode; chép là đường cuối nhưng luôn chạy được."""
    if os.path.lexists(dich):
        return dich
    for lam in (os.symlink, os.link):
        try:
            lam(nguon, dich)
            return dich
        except (OSError, NotImplementedError):
            pass
    shutil.copy2(nguon, dich)
    return dich


def loc(p):
    """đường dẫn đặt trong filter ffmpeg (subtitles='…', fontfile='…', fontsdir='…').
    Windows: đổi \\ thành / và thoát dấu : của ổ đĩa (C\\:/…), không thì ffmpeg hiểu nhầm là dấu tách tham số."""
    p = str(p)
    if "'" in p and os.path.exists(p):               # 1.2.13: dấu ' trong đường dẫn không thoát được ổn định trong filter ffmpeg
        import hashlib, shutil                       # → chép sang thư mục tạm với tên an toàn (file hoặc thư mục font)
        dich = os.path.join(tam(), "loc_" + hashlib.sha1(p.encode("utf-8")).hexdigest()[:12] + os.path.splitext(p)[1])
        if not os.path.exists(dich):
            (shutil.copytree if os.path.isdir(p) else shutil.copy2)(p, dich)
        p = dich
    if HE != "win":
        return p
    return p.replace("\\", "/").replace(":", "\\:")



# ───────────────────────────── PHẦN CỨNG (1.2.12): dò THẬT từng máy, nhớ kết quả, lỗi thì lùi CPU
# Bài học thực tế: máy có card NVIDIA đời mới hay "lỗi CUDA" vì faster-whisper/ctranslate2 thấy GPU nhưng thiếu cuBLAS/cuDNN
# (lỗi nổ ra GIỮA lúc nhận giọng, có khi làm sập tiến trình); NVENC đòi driver đủ mới; d3d11va có máy còn chậm hơn CPU.
# → mọi thứ được THỬ trong tiến trình riêng, chọn cách nhanh nhất chạy được, ghi ~/.studio-edit-video/phan-cung.json
#   (khoá theo phiên bản ffmpeg / driver / thư viện — đổi là tự dò lại).
import json as _json, re as _re, time as _time

PHAN_CUNG = os.path.join(os.path.expanduser(os.environ.get("STUDIO_DATA") or "~/.studio-edit-video"), "phan-cung.json")
_AN = 0x08000000 if HE == "win" else 0          # không bật cửa sổ console


def _pc_doc():
    try:
        return _json.load(open(PHAN_CUNG, encoding="utf-8"))
    except Exception:
        return {}


def _pc_ghi(k, v):
    """1.2.13: ghi NGUYÊN TỬ (tmp riêng tiến trình + replace) — nhiều tiến trình thử phần cứng cùng lúc không còn xoá mất kết quả nhau"""
    try:
        os.makedirs(os.path.dirname(PHAN_CUNG), exist_ok=True)
        d = _pc_doc(); d[k] = v
        tmp = f"{PHAN_CUNG}.{os.getpid()}.tmp"
        _json.dump(d, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        for _ in range(20):
            try:
                os.replace(tmp, PHAN_CUNG)
                break
            except PermissionError:                   # Windows: file đang được tiến trình khác đọc
                _time.sleep(0.1)
    except OSError:
        pass


@functools.lru_cache(maxsize=1)
def _ffver():
    try:
        return subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, creationflags=_AN).stdout.split("\n")[0][:60]
    except Exception:
        return "?"


@functools.lru_cache(maxsize=1)
def nvidia():
    """→ {"ten", "driver"} nếu máy có card NVIDIA (nvidia-smi), không thì {}"""
    if HE == "mac" or not shutil.which("nvidia-smi"):
        return {}
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=15, creationflags=_AN)
        ten, drv = [x.strip() for x in r.stdout.strip().splitlines()[0].split(",")[:2]]
        return {"ten": ten, "driver": drv}
    except Exception:
        return {}


def _ffthu(lenh, toi_da=60):
    try:
        t = _time.time()
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", *lenh], capture_output=True, text=True, errors="replace",
                           timeout=toi_da, creationflags=_AN)
        dong = [l for l in r.stderr.strip().splitlines() if l.strip()]
        loi = next((l for l in dong if _re.search(r"(?i)driver|not support|cannot|failed|no device|error", l)), dong[-1] if dong else "")
        return r.returncode == 0, _time.time() - t, loi[:160]
    except Exception as e:
        return False, 0, str(e)[:160]


# ── mã hoá
CHAT_MA_HOA = {
    "h264_nvenc": ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "vbr", "-cq", "19", "-b:v", "0", "-bf", "0"],   # card đời cũ không có khung B
    "h264_qsv": ["-c:v", "h264_qsv", "-global_quality", "20", "-preset", "veryfast"],
    "h264_amf": ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "cqp", "-qp_i", "18", "-qp_p", "20"],
    "h264_videotoolbox": ["-c:v", "h264_videotoolbox", "-q:v", "65"],
    "libx264": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"],
}


@functools.lru_cache(maxsize=1)
def _bo_ma_hoa():
    if HE == "mac":
        return "h264_videotoolbox"
    if os.environ.get("STUDIO_CPU_ONLY"):
        return "libx264"
    khoa = f"{_ffver()}|{nvidia().get('driver', '')}"
    c = _pc_doc().get("ma_hoa") or {}
    if c.get("khoa") == khoa and c.get("enc") in CHAT_MA_HOA and _time.time() < c.get("het_han", 9e12):
        return c["enc"]
    ket, thu = "libx264", {}
    tam_ra = os.path.join(tam(), f"_thu_ma_hoa_{os.getpid()}.mp4")
    for enc in ("h264_nvenc", "h264_qsv", "h264_amf"):
        # mã hoá THẬT 1080x1920 (khổ dọc, đúng chất lượng sẽ dùng) — có tên trong danh sách chưa chắc chạy (driver, phần cứng)
        ok, s, loi = _ffthu(["-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=1", "-pix_fmt", "yuv420p",
                             *CHAT_MA_HOA[enc], tam_ra], 40)
        ok = ok and os.path.isfile(tam_ra) and os.path.getsize(tam_ra) > 1000
        thu[enc] = "ok" if ok else (loi or "lỗi")
        if ok:
            ket = enc
            break
    ghi = {"khoa": khoa, "enc": ket, "thu": thu, "luc": _time.strftime("%Y-%m-%d %H:%M")}
    if ket == "libx264" and any(_qua_gio(v) for v in thu.values()):
        ghi["het_han"] = _time.time() + 6 * 3600          # 1.2.13: GPU bận lúc thử ≠ không có GPU
    _pc_ghi("ma_hoa", ghi)
    try:
        os.remove(tam_ra)
    except OSError:
        pass
    return ket


def ma_hoa(bitrate=None):
    """tham số mã hoá H.264 nhanh nhất máy có (đã thử thật); không truyền bitrate = chế độ chất lượng cố định"""
    enc = _bo_ma_hoa()
    if enc == "h264_videotoolbox" and not APPLE_SILICON:  # 1.2.13: Mac Intel — videotoolbox không có -q:v
        return ["-c:v", enc, "-b:v", bitrate or "14M"]
    if bitrate and enc != "libx264":
        return ["-c:v", enc, "-b:v", bitrate]
    return list(CHAT_MA_HOA[enc])


# ── giải mã
def _qua_gio(loi):
    """lỗi do hết giờ / tiến trình bị dừng (máy bận) — không phải phần cứng không hỗ trợ"""
    return bool(_re.search(r"timeout|timed out|quá lâu|quá giờ|bị dừng|TimeoutExpired", str(loi or ""), _re.I))


@functools.lru_cache(maxsize=256)
def hdr_sdr(nguon):
    """1.2.13: video HDR (iPhone 12+ quay HLG/Dolby Vision, máy ảnh PQ) → đổi về SDR BT.709 trước khi dựng.
    Không đổi thì ra xám nhạt, mất màu — tức là SAI màu gốc người xem thấy trên điện thoại. → chuỗi filter (kết thúc bằng ',') hoặc ''."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_transfer",
                            "-of", "csv=p=0", nguon], capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=30, creationflags=_AN)
        trc = (r.stdout or "").strip().lower()
    except Exception:
        return ""
    if trc not in ("arib-std-b67", "smpte2084"):
        return ""
    if not _co_filter("zscale"):
        return ""
    return "zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,"


@functools.lru_cache(maxsize=8)
def _co_filter(ten):
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30, creationflags=_AN)
        return f" {ten} " in r.stdout
    except Exception:
        return False


def giai_ma(nguon=None):
    """tham số tăng tốc giải mã đặt TRƯỚC -i. Có `nguon` → dùng cách đã THỬ nhanh nhất cho loại file đó (codec/độ sâu màu/khổ);
    không có → '-hwaccel auto' như cũ (ffmpeg tự lùi CPU)."""
    if HE == "mac":
        return ["-hwaccel", "videotoolbox"]
    if not nguon or os.environ.get("STUDIO_CPU_ONLY"):
        return [] if nguon else ["-hwaccel", "auto"]
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,pix_fmt,width,height",
                            "-of", "json", nguon], capture_output=True, text=True, timeout=30, creationflags=_AN)
        st = (_json.loads(r.stdout).get("streams") or [{}])[0]
        codec, pix, w, h = st.get("codec_name", ""), st.get("pix_fmt", ""), st.get("width", 0), st.get("height", 0)
    except Exception:
        return []
    loai = f"{codec}|{pix}|{'4k' if max(int(w or 0), int(h or 0)) > 2200 else 'hd'}"
    khoa = f"{_ffver()}|{nvidia().get('driver', '')}"
    c = (_pc_doc().get("giai_ma") or {}).get(loai) or {}
    if c.get("khoa") == khoa and _time.time() < c.get("het_han", 9e12):
        return list(c.get("tham_so") or [])
    ket, tot, thu = [], None, {}
    for hw in (None, "cuda", "dxva2", "d3d11va", "qsv"):
        a = ["-hwaccel", hw] if hw else []
        ok, s, loi = _ffthu([*a, "-t", "6", "-i", nguon, "-an", "-f", "null", "-"], 60)
        thu[hw or "cpu"] = round(s, 2) if ok else (loi or "lỗi")
        if ok and (tot is None or s < tot * (1.0 if hw is None else 0.87)):     # GPU phải nhanh hơn CPU ≥ 13% mới dùng
            tot, ket = s, a
    m = dict((_pc_doc().get("giai_ma") or {}))
    m[loai] = {"khoa": khoa, "tham_so": ket, "thu": thu, "luc": _time.strftime("%Y-%m-%d %H:%M")}
    # 1.2.13: GPU thua vì QUÁ GIỜ (máy đang bận việc khác) ≠ GPU không giải mã được → chỉ nhớ 6 giờ rồi thử lại
    if any(isinstance(v, str) and _qua_gio(v) for v in thu.values()):
        m[loai]["het_han"] = _time.time() + 6 * 3600
    _pc_ghi("giai_ma", m)
    return list(ket)


# ── nhận giọng (faster-whisper): GPU chỉ khi đã thử chạy THẬT được
def _dll_nvidia():
    """thư viện CUDA cài bằng pip (nvidia-cublas-cu12, nvidia-cudnn-cu12) nằm trong site-packages/nvidia/*/bin — báo Windows tìm ở đó"""
    if HE != "win":
        return []
    import glob as _g, site as _s
    ds = []
    for sp in set(_s.getsitepackages() + [os.path.join(sys.prefix, "Lib", "site-packages")]):
        ds += [d for d in _g.glob(os.path.join(sp, "nvidia", "*", "bin")) if os.path.isdir(d)]
    for d in ds:
        try:
            os.add_dll_directory(d)
        except (OSError, AttributeError):
            pass
        if d not in os.environ.get("PATH", ""):
            os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    return ds


_THU_WHISPER = r'''
import sys, os, numpy as np
sys.path.insert(0, sys.argv[2]); import nen_tang as NT; NT._dll_nvidia()
from faster_whisper import WhisperModel
m = WhisperModel(sys.argv[1], device="cuda", compute_type="float16")
segs, _ = m.transcribe(np.zeros(16000 * 2, dtype=np.float32), language="vi")
list(segs); print("GPU_OK")
'''


def whisper_thiet_bi(model="large-v3-turbo"):
    """→ ("cuda", "float16") nếu đã THỬ nhận giọng trên GPU chạy được; không thì ("cpu", "int8"). Kết quả nhớ theo driver + thư viện."""
    if APPLE_SILICON or os.environ.get("STUDIO_CPU_ONLY"):
        return "cpu", "int8"
    _dll_nvidia()
    try:
        import ctranslate2
        so_gpu = ctranslate2.get_cuda_device_count()
        ct2 = ctranslate2.__version__
    except Exception:
        return "cpu", "int8"
    if so_gpu < 1:
        return "cpu", "int8"
    khoa = f"{ct2}|{nvidia().get('driver', '')}|{len(_dll_nvidia())}"
    c = _pc_doc().get("whisper") or {}
    if c.get("khoa") == khoa and _time.time() < c.get("het_han", 9e12):
        return (c["thiet_bi"], c["kieu"])
    try:
        r = subprocess.run([sys.executable, "-c", _THU_WHISPER, _ten_fw(model), DIR], capture_output=True, text=True,
                           errors="replace", timeout=240, creationflags=_AN)
        ok = "GPU_OK" in r.stdout
        ly_do = "" if ok else ((r.stderr or r.stdout).strip().splitlines() or ["tiến trình thử bị dừng"])[-1][:200]
    except Exception as e:
        ok, ly_do = False, f"thử GPU quá lâu/lỗi: {e}"[:200]
    kq = ("cuda", "float16") if ok else ("cpu", "int8")
    ghi = {"khoa": khoa, "thiet_bi": kq[0], "kieu": kq[1], "ly_do": ly_do, "luc": _time.strftime("%Y-%m-%d %H:%M")}
    if not ok and _qua_gio(ly_do):                     # 1.2.13: thử lúc máy quá tải → chỉ nhớ 6 giờ, máy rảnh tự thử lại
        ghi["het_han"] = _time.time() + 6 * 3600
    _pc_ghi("whisper", ghi)
    return kq


# ───────────────────────────── nhận dạng giọng nói
MODEL_FW = {"whisper-small": "small", "whisper-large-v3-turbo": "large-v3-turbo", "whisper-large-v3": "large-v3"}


def _ten_fw(model):
    ten = model.split("/")[-1].replace("-mlx", "")
    return MODEL_FW.get(ten, ten)


def bo_nhan_dang():
    return "mlx-whisper" if APPLE_SILICON else "faster-whisper"


_MH_GIONG = {}


def _mo_hinh_giong(WM, ten, tb, kieu):
    """1.2.13: nạp mô hình giọng MỘT lần mỗi tiến trình (trước: mỗi clip nạp lại — 20–30 clip là 20–30 lần nạp)"""
    k = (ten, tb, kieu)
    if k not in _MH_GIONG:
        _MH_GIONG.clear()
        _MH_GIONG[k] = WM(ten, device=tb, compute_type=kieu)
    return _MH_GIONG[k]


def nhan_dang(wav, model, **kw):
    """→ {"segments": [{"start","end","text","words":[{"start","end","word","probability"}]}]} — cùng dạng mlx-whisper"""
    kw.setdefault("language", "vi")
    if APPLE_SILICON:
        import mlx_whisper
        return mlx_whisper.transcribe(wav, path_or_hf_repo=model, word_timestamps=True, **kw)
    from faster_whisper import WhisperModel
    tb, kieu = whisper_thiet_bi(model)                 # 1.2.12: GPU chỉ khi đã thử chạy thật được (không còn "lỗi CUDA")

    def chay(tb, kieu):
        m = _mo_hinh_giong(WhisperModel, _ten_fw(model), tb, kieu)
        segs, _ = m.transcribe(wav, language=kw["language"], word_timestamps=True,
                               condition_on_previous_text=kw.get("condition_on_previous_text", False))
        out = []
        for s in segs:                                  # lỗi CUDA nổ ra ở đây (lúc chạy), không phải lúc tạo mô hình
            out.append({"start": s.start, "end": s.end, "text": s.text,
                        "words": [{"start": w.start, "end": w.end, "word": w.word, "probability": w.probability}
                                  for w in (s.words or [])]})
        return {"segments": out}
    if tb == "cuda":
        try:
            return chay("cuda", kieu)
        except Exception as e:                          # GPU hỏng giữa chừng → nhớ lại là CPU cho máy này, chạy lại bằng CPU
            c = _pc_doc().get("whisper") or {}
            c.update(thiet_bi="cpu", kieu="int8", ly_do=f"lỗi khi chạy: {e}"[:200])
            _pc_ghi("whisper", c)
    return chay("cpu", "int8")


# ───────────────────────────── tách người
def bo_tach_nguoi():
    return "apple-vision" if HE == "mac" else "mediapipe"


def tach_nguoi(vao, ra, muc="balanced"):
    """thư mục khung PNG `vao` → thư mục mặt nạ xám cùng tên `ra` (trắng = người)"""
    os.makedirs(ra, exist_ok=True)
    if HE == "mac":
        bin_ = os.path.join(DIR, "tach_nguoi")
        if not os.path.exists(bin_):
            # 1.2.21: KHÔNG biên dịch Swift lúc chạy (cần Xcode, tach_nguoi.swift không còn trong gói) — lõi 1.3 tách người bằng
            # MODNet (onnxruntime, v3/doc/alpha.py); đường 1.x trên Mac chỉ dùng được khi có bản dựng sẵn `scripts/tach_nguoi`
            raise RuntimeError("tách người đường 1.x trên Mac cần bản dựng sẵn scripts/tach_nguoi (không có) — dùng lõi 1.3 (MODNet/onnxruntime)")
        subprocess.run([bin_, vao, ra, muc], check=True, capture_output=True)
        return ra
    import numpy as np
    from PIL import Image
    import mediapipe as mp
    with mp.solutions.selfie_segmentation.SelfieSegmentation(model_selection=1 if muc != "fast" else 0) as seg:
        for f in sorted(os.listdir(vao)):
            if not f.lower().endswith((".png", ".jpg")):
                continue
            a = np.asarray(Image.open(os.path.join(vao, f)).convert("RGB"))
            m = seg.process(a).segmentation_mask
            Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8), "L").save(
                os.path.join(ra, os.path.splitext(f)[0] + ".png"))
    return ra


def thieu():
    """liệt kê thứ còn thiếu trên máy này (dùng cho kit.py / tu_kiem.py)"""
    l = []
    for b in ("ffmpeg", "ffprobe"):
        if not shutil.which(b):
            l.append(f"{b} (Mac: brew install ffmpeg · Windows: winget install Gyan.FFmpeg)")
    goi = ["mlx_whisper"] if APPLE_SILICON else ["faster_whisper"]
    if HE != "mac":
        goi.append("mediapipe")
    for g in goi:
        try:
            __import__(g)
        except Exception:
            l.append(f"gói Python {g.replace('_', '-')} (cài vào .venv của skill)")
    # 1.2.21: không còn đòi swiftc trên Mac — tách người của lõi 1.3 dùng onnxruntime (bác sĩ máy kiểm)
    return l


if __name__ == "__main__":
    print(f"Hệ điều hành : {HE}{' (Apple Silicon)' if APPLE_SILICON else ''}")
    print(f"GPU NVIDIA   : {nvidia() or 'không có'}")
    print(f"Mã hoá       : {_bo_ma_hoa()}")
    print(f"Nhận giọng   : {'/'.join(whisper_thiet_bi())}  ({(_pc_doc().get('whisper') or {}).get('ly_do') or 'ok'})")
    print(f"Nhận dạng    : {bo_nhan_dang()}")
    print(f"Tách người   : {bo_tach_nguoi()}")
    print(f"Kho mặc định : {kho_mac_dinh()}")
    print(f"Thư mục tạm  : {tam()}")
    t = thieu()
    print("Thiếu        : " + ("không" if not t else "\n  - " + "\n  - ".join(t)))
