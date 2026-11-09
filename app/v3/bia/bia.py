# -*- coding: utf-8 -*-
"""Ảnh bìa từ thiết kế khai báo (§6), cùng text engine dung/chu.py (Skia).
ve(du_an, bia_spec, ctx) → [bia-1.png, …] — MỖI phương án AI đưa (bia.phuong_an[i].thiet_ke) một bìa; không có phuong_an → thiet_ke = 1 bìa;
không có gì → lỗi thieu_truong(bia.phuong_an). 1.2.21: KHÔNG còn _bien_the (máy tự xoay sắc / bỏ người) và không bù đủ 3.
+ kiểm (ghi dung/bia-kiem.json): mặt thấy ≥ 1 (YuNet) nếu có người, chữ trong khung, tương phản chữ/nền, số dòng, hộp thật từng khối,
CHỒNG CHỮ giữa các khối (chong_chu: cặp id + % giao), chữ đè mặt — mọi ngưỡng đọc từ ctx.quyet_dinh["bia"] (tuong_phan_toi_thieu, de_mat_toi_da).
Tách người: doc.alpha.tach_anh(rgb, muc="cao") nếu import được; không thì GrabCut quanh mặt YuNet (ghi "fallback": "grabcut").
1.2.21 (B3): tách người chạy trong luồng có hạn bia_tach_toi_da_giay (90 s) — quá hạn/lỗi (GPU hỏng sau lỗi CUDA, CPU treo) → bìa VẪN vẽ
không tách người, ghi may_sua {"id": "bia_khong_tach_nguoi", "ly_do"} vào bia-kiem.json, không dừng việc (1.2.20 treo tới watchdog 45 phút)."""
import os, math, subprocess, json, threading
import numpy as np
import cv2
import skia

try:
    import chung
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import chung
from dung import chu as _chu
from dung import lop as _lop

try:
    from doc import alpha as _alpha
    if not hasattr(_alpha, "tach_anh"):
        _alpha = None
except Exception:
    _alpha = None

_SAMP_CUBIC = skia.SamplingOptions(skia.CubicResampler.Mitchell())
_SAMP_LIN = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear)
MAC_DINH = {"yunet_diem": 0.6}      # CHỈ còn ngưỡng tin cậy bộ dò mặt (vật lý). Nền/bóng/viền người/tương phản/đè mặt → ctx.quyet_dinh["bia"] (§1c)


def _q(ctx, duong, mac_dinh=_lop._THIEU):
    """ctx.quyet_dinh["bia"...] — thiếu → ThieuTruong(duong) (lop="bia")"""
    return _lop.quyet(ctx, duong, mac_dinh, lop="bia")


# ---------------------------------------------------------------- mặt (YuNet) ----
_YUNET = {}


def _yunet(w, h):
    p = os.path.join(chung.duong("mo_hinh"), "yunet.onnx")
    if not os.path.isfile(p):
        return None
    k = (w, h)
    if k not in _YUNET:
        try:
            _YUNET[k] = cv2.FaceDetectorYN.create(chung.duong_ascii(p), "", (w, h), MAC_DINH["yunet_diem"], 0.3, 5000)
        except Exception:
            _YUNET[k] = None
    return _YUNET[k]


def tim_mat(bgr, canh=640):
    """→ [{"x","y","w","h","diem"}] toạ độ 0..1 (mặt lớn nhất trước)"""
    H, W = bgr.shape[:2]
    s = canh / max(W, H)
    nho = cv2.resize(bgr, (max(1, int(W * s)), max(1, int(H * s))), interpolation=cv2.INTER_AREA) if s < 1 else bgr
    det = _yunet(nho.shape[1], nho.shape[0])
    if det is None:
        return []
    det.setInputSize((nho.shape[1], nho.shape[0]))
    _, faces = det.detect(nho)
    ra = []
    for f in (faces if faces is not None else []):
        x, y, w, h, diem = float(f[0]), float(f[1]), float(f[2]), float(f[3]), float(f[14])
        ra.append({"x": x / nho.shape[1], "y": y / nho.shape[0], "w": w / nho.shape[1], "h": h / nho.shape[0], "diem": diem})
    ra.sort(key=lambda m: -m["w"] * m["h"])
    return ra


# ---------------------------------------------------------------- khung & tách người ----
def lay_khung(video, t, W, H, du_an=None):
    """khung tại t (giây gốc) → BGR W×H (cắt cover). 1.2.21: tệp tạm TRONG dự án, tên theo pid (2 việc song song không lấy nhầm khung);
    nguồn 10-bit/HDR → chung.loc_mau_vao trước scale (§1f)."""
    thu = os.path.join(du_an, "dung") if du_an else chung.duong("nhat_ky")
    os.makedirs(thu, exist_ok=True)
    tmp = os.path.join(thu, "_bia_khung-%d-%s.png" % (os.getpid(), os.urandom(3).hex()))
    loc = _lop.loc_mau_vao(video)
    vf = (loc + "," if loc else "") + f"crop=w='min(iw,ih*{W}/{H})':h='min(ih,iw*{H}/{W})',scale={W}:{H}:flags=lanczos"
    try:
        chung.sh([chung.duong("ffmpeg"), "-v", "error", "-y", "-ss", "%.3f" % t, "-i", video, "-frames:v", "1", "-vf", vf, tmp], timeout=120)
        a = chung.cv_doc(tmp)                               # 1.2.19 (E2): đường dẫn có dấu
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    if a is None:
        raise RuntimeError("không lấy được khung bìa tại %.2fs" % t)
    return a


def tach_nguoi(bgr):
    """→ (alpha float32 HxW 0..1, nguon: "modnet"|"grabcut"|None)"""
    if _alpha is not None:
        try:
            a = _alpha.tach_anh(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB), muc="cao")
            if a is not None:
                return np.clip(np.asarray(a, np.float32), 0, 1), "modnet"
        except Exception:
            pass
    # --- fallback: GrabCut quanh mặt YuNet (mặt nạ mềm tạm) ---
    H, W = bgr.shape[:2]
    ms = tim_mat(bgr)
    if not ms:
        return None, None
    m = ms[0]
    s = 540 / max(W, H)
    nho = cv2.resize(bgr, (int(W * s), int(H * s)), interpolation=cv2.INTER_AREA)
    h, w = nho.shape[:2]
    fx, fy, fw, fh = m["x"] * w, m["y"] * h, m["w"] * w, m["h"] * h
    x0 = int(max(0, fx - fw * 1.6)); x1 = int(min(w - 1, fx + fw * 2.6)); y0 = int(max(0, fy - fh * 0.9)); y1 = h - 1
    mask = np.zeros((h, w), np.uint8)
    mask[:] = cv2.GC_BGD
    mask[y0:y1, x0:x1] = cv2.GC_PR_BGD
    # chắc chắn là người: vùng mặt + thân dưới mặt (hẹp)
    mask[int(fy + fh * 0.1):int(fy + fh * 0.95), int(fx + fw * 0.15):int(fx + fw * 0.85)] = cv2.GC_FGD
    mask[int(fy + fh * 1.2):min(h - 1, int(fy + fh * 4.5)), int(max(0, fx - fw * 0.2)):int(min(w - 1, fx + fw * 1.2))] = cv2.GC_PR_FGD
    bgd = np.zeros((1, 65), np.float64); fgd = np.zeros((1, 65), np.float64)
    try:
        cv2.grabCut(nho, mask, None, bgd, fgd, 4, cv2.GC_INIT_WITH_MASK)
    except Exception:
        return None, None
    a = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 1.0, 0.0).astype(np.float32)
    # dọn mảnh nhỏ: giữ thành phần lớn nhất
    n, lab, st, _ = cv2.connectedComponentsWithStats((a > 0.5).astype(np.uint8), 8)
    if n > 2:
        k = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
        a = (lab == k).astype(np.float32)
    a = cv2.morphologyEx(a, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    a = cv2.GaussianBlur(a, (0, 0), 1.2)
    a = cv2.resize(a, (W, H), interpolation=cv2.INTER_LINEAR)
    # mép mềm theo ảnh: guided-lite bằng bilateral trên alpha
    a = np.clip(a, 0, 1)
    return a, "grabcut"


def tach_nguoi_co_han(bgr, du_an=None, han=None):
    """1.2.21 (B3): tach_nguoi(bgr) chạy trong luồng daemon, chờ tối đa `han` giây (cau_hinh bia_tach_toi_da_giay, mặc định 90).
    → (alpha, nguon, ly_do): quá hạn / ném lỗi / không thấy người → (None, None, lý do) — bìa vẫn vẽ không tách người; luồng kẹt bị
    bỏ lại (không giết được lệnh trên card) nhưng việc KHÔNG đứng im."""
    if han is None:
        han = float((chung.cau_hinh() or {}).get("bia_tach_toi_da_giay", 90) or 90)
    kq = {}

    def _w():
        try:
            kq["r"] = tach_nguoi(bgr)
        except BaseException as ex:      # noqa
            kq["e"] = ex
    t = threading.Thread(target=_w, daemon=True, name="bia-tach-nguoi")
    t.start()
    t.join(han)
    if t.is_alive():
        ly_do = f"tách người không trả về sau {han:.0f} s (card/CPU treo) → bìa vẽ không tách người"
        chung.log(du_an, "bìa: " + ly_do)
        return None, None, ly_do
    if "e" in kq:
        ly_do = f"tách người lỗi ({str(kq['e'])[-160:]}) → bìa vẽ không tách người"
        chung.log(du_an, "bìa: " + ly_do)
        return None, None, ly_do
    a, ng = kq.get("r") or (None, None)
    if a is None:
        return None, None, "không tìm thấy người/mặt trong khung → bìa vẽ không tách người"
    return a, ng, None


# ---------------------------------------------------------------- màu ----
def _do_sang(c):
    r, g, b, _ = _chu.mau(c)
    def lin(v):
        v = v / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def tuong_phan(c1, L2):
    L1 = _do_sang(c1)
    a, b = max(L1, L2), min(L1, L2)
    return (a + 0.05) / (b + 0.05)


# ---------------------------------------------------------------- vẽ ----
def _bgr_skia(bgr):
    a = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
    return skia.Image.fromarray(np.ascontiguousarray(a), skia.kBGRA_8888_ColorType, skia.kUnpremul_AlphaType)


_NEN_CACHE = {}


def _anh_nen(p):
    """ảnh nền bìa từ kho: ảnh → BGRA; VIDEO (nền động) → khung giữa video. None nếu không đọc được."""
    if p in _NEN_CACHE:
        return _NEN_CACHE[p]
    a = None
    try:
        if p.lower().endswith((".mp4", ".mov", ".webm", ".mkv", ".avi", ".gif")):
            dur = float((chung.ffprobe(p) or {}).get("dur") or 0)
            r = subprocess.run([chung.duong("ffmpeg"), "-v", "error", "-ss", f"{dur / 2:.2f}", "-i", p, "-frames:v", "1",
                                "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, timeout=60, creationflags=(0x08000000 if os.name == "nt" else 0))
            b = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR) if r.stdout else None
            a = cv2.cvtColor(b, cv2.COLOR_BGR2BGRA) if b is not None else None
        else:
            a = _lop.doc_anh(p)
        if a is None or getattr(a, "ndim", 0) != 3 or a.shape[2] != 4:
            a = None
    except Exception:
        a = None
    _NEN_CACHE[p] = a
    return a


def _ve_nen(c, nen, khung_bgr, W, H, ctx):
    kieu = nen.get("kieu")
    if not kieu:
        raise _lop.ThieuTruong("bia.nen.kieu", "mau|gradient|anh|kho|khung_mo", "bia")
    gt = nen.get("gia_tri")
    if kieu == "mau":
        c.drawColor(_chu.mau_skia(gt or _mau_video(ctx, "toi")))
    elif kieu == "gradient":
        ms = gt if isinstance(gt, list) else [gt or _mau_video(ctx, "toi"), _mau_video(ctx, "toi")]
        p = skia.Paint(); p.setShader(_chu._shader_gradient({"mau": ms, "goc": float(nen.get("goc", 90))}, (0, 0, W, H)))
        c.drawRect(skia.Rect.MakeWH(W, H), p)
    elif kieu in ("anh", "kho") and ctx is not None and ctx.tai_nguyen(gt) and _anh_nen(ctx.tai_nguyen(gt)) is not None:
        img = _lop.anh_skia_tu_numpy(_anh_nen(ctx.tai_nguyen(gt)), bgra=True)
        s = max(W / img.width(), H / img.height())
        c.drawImageRect(img, skia.Rect.MakeXYWH((W - img.width() * s) / 2, (H - img.height() * s) / 2, img.width() * s, img.height() * s), _SAMP_LIN)
    else:  # khung_mo
        if nen.get("mo") is None:
            raise _lop.ThieuTruong("bia.nen.mo", "độ mờ khung 0..1 (0 = khung thật)", "bia")
        mo = float(nen["mo"])
        if mo <= 0.01:                                     # mo = 0: khung THẬT, không mờ (AI đặt "không làm mờ" thì tôn trọng)
            c.drawImage(_bgr_skia(khung_bgr), 0, 0)
        else:
            k = 8 if mo >= 0.3 else 4 if mo >= 0.15 else 2
            nho = cv2.resize(khung_bgr, (W // k, H // k), interpolation=cv2.INTER_AREA)
            sig = max(0.6, mo * 12 / (8 / k))
            nho = cv2.GaussianBlur(nho, (0, 0), sig)
            big = cv2.resize(nho, (W, H), interpolation=cv2.INTER_CUBIC)
            c.drawImage(_bgr_skia(big), 0, 0)
    toi = float(nen.get("toi") or 0)
    if toi > 0:
        c.drawColor(skia.ColorSetARGB(int(255 * min(toi, 1)), 0, 0, 0))


def _mau_video(ctx, vai):
    """màu vai của VIDEO (phong_cach) → của KÊNH (quyet_dinh bang_mau) → thieu_truong. Không còn #FFFFFF / #0E0E12 hàn trong bìa."""
    pc = getattr(ctx, "pc", None) or {}
    v = pc.get("mau_" + vai)
    if v:
        return v
    return _q(ctx, "bang_mau." + vai)


def _goc_sang_tam(o, w, h, W, H):
    """x,y của khối/hình trên bìa = GÓC TRÊN-TRÁI (0..1) như cách người thiết kế đặt → tâm px để xoay"""
    if o.get("tam"):
        return float(o.get("x", 0.5)) * W, float(o.get("y", 0.5)) * H
    return float(o.get("x", 0)) * W + w / 2, float(o.get("y", 0)) * H + h / 2


def _ve_khoi(c, k, W, H):
    if k.get("w") is None or k.get("h") is None:
        raise _lop.ThieuTruong("bia.thiet_ke.khoi[].w/h", "khối bìa cần w, h (0..1)", "bia")
    w, h = float(k["w"]) * W, float(k["h"]) * H
    x, y = _goc_sang_tam(k, w, h, W, H)
    c.save(); c.translate(x, y); c.rotate(float(k.get("xoay", 0)))
    _chu.ve_khoi(c, (-w / 2, -h / 2, w / 2, h / 2), {"mau": k.get("mau"), "bo": k.get("bo", 0), "hinh": k.get("hinh", "rect"),
                                                   "vien": k.get("vien"), "bong": k.get("bong"), "gradient": k.get("gradient")})
    c.restore()


def _ve_nguoi(c, khung_bgr, alpha, ng, W, H, ctx=None):
    """người tách (co, x,y = tâm hộp người, vien_sang, bong, lat). 1.2.21: bóng/viền sáng thiếu chi tiết → quyet_dinh bia.nguoi.bong / bia.nguoi.vien_sang"""
    a8 = (np.clip(alpha, 0, 1) * 255).astype(np.uint8)
    ys, xs = np.nonzero(a8 > 8)
    if len(ys) == 0:
        return
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    bgra = cv2.cvtColor(khung_bgr, cv2.COLOR_BGR2BGRA); bgra[..., 3] = a8
    cat = np.ascontiguousarray(bgra[y0:y1, x0:x1])
    if ng.get("lat"):
        cat = np.ascontiguousarray(cat[:, ::-1])
    img = skia.Image.fromarray(cat, skia.kBGRA_8888_ColorType, skia.kUnpremul_AlphaType)
    co = float(ng.get("co", 1.0))
    cw, ch = (x1 - x0) * co, (y1 - y0) * co
    cx = float(ng.get("x", (x0 + x1) / 2 / W)) * W; cy = float(ng.get("y", (y0 + y1) / 2 / H)) * H
    dst = skia.Rect.MakeXYWH(cx - cw / 2, cy - ch / 2, cw, ch)
    # bóng: dict {x, y, mo, mau} — `true` → quyet_dinh bia.nguoi.bong (dict) → thieu_truong
    if ng.get("bong"):
        b = ng["bong"] if isinstance(ng["bong"], dict) else _q(ctx, "bia.nguoi.bong")
        if not isinstance(b, dict):
            raise _lop.ThieuTruong("bia.nguoi.bong", "bóng người cần dict {x, y, mo, mau}", "bia")
        for k_ in ("x", "y", "mo", "mau"):
            if b.get(k_) is None:
                raise _lop.ThieuTruong("bia.nguoi.bong." + k_, lop="bia")
        lp = skia.Paint(); lp.setImageFilter(skia.ImageFilters.Blur(float(b["mo"]) / 2, float(b["mo"]) / 2))
        c.saveLayer(None, lp); c.translate(float(b["x"]), float(b["y"]))
        p = skia.Paint(); p.setColorFilter(skia.ColorFilters.Blend(_chu.mau_skia(b["mau"]), skia.BlendMode.kSrcIn))
        c.drawImageRect(img, dst, _SAMP_LIN, p); c.restore()
    # viền sáng: dilate alpha — {w, mau}; `true` → quyet_dinh bia.nguoi.vien_sang
    vs = ng.get("vien_sang")
    if vs and not isinstance(vs, dict):
        vs = _q(ctx, "bia.nguoi.vien_sang")
    if isinstance(vs, dict) and vs:
        if vs.get("w") is None:
            raise _lop.ThieuTruong("bia.nguoi.vien_sang.w", lop="bia")
        w = float(vs["w"])
    else:
        w = 0.0
    if w > 0:
        k = int(max(1, round(w / co)))
        dil = cv2.dilate(a8, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))
        dil = cv2.GaussianBlur(dil, (0, 0), 0.8)
        vien = np.zeros_like(bgra); r, g, b_, a = _chu.mau(vs.get("mau") or _mau_video(ctx, "nhan"))
        vien[..., 0] = b_; vien[..., 1] = g; vien[..., 2] = r; vien[..., 3] = dil
        vimg = np.ascontiguousarray(vien[max(0, y0 - k - 2):min(H, y1 + k + 2), max(0, x0 - k - 2):min(W, x1 + k + 2)])
        if ng.get("lat"):
            vimg = np.ascontiguousarray(vimg[:, ::-1])
        vi = skia.Image.fromarray(vimg, skia.kBGRA_8888_ColorType, skia.kUnpremul_AlphaType)
        ox = (max(0, x0 - k - 2) - x0) * co; oy = (max(0, y0 - k - 2) - y0) * co
        if ng.get("lat"):
            ox = (x0 + (x1 - x0) - min(W, x1 + k + 2)) * co
        c.drawImageRect(vi, skia.Rect.MakeXYWH(dst.left() + ox, dst.top() + oy, vimg.shape[1] * co, vimg.shape[0] * co), _SAMP_LIN)
    c.drawImageRect(img, dst, _SAMP_CUBIC if co > 1 else _SAMP_LIN)


def _ve_hinh(c, hs, W, H, ctx):
    p = ctx.tai_nguyen(hs.get("duong") or hs.get("id")) if ctx is not None else (hs.get("duong") if os.path.isfile(hs.get("duong", "")) else None)
    if not p:
        return
    a = _lop.doc_anh(p)
    if a is None:
        return
    img = _lop.anh_skia_tu_numpy(a, bgra=True)
    w = float(hs.get("w", 0.3)) * W; h = float(hs["h"]) * H if hs.get("h") else w * img.height() / img.width()
    x, y = _goc_sang_tam(hs, w, h, W, H)
    c.save(); c.translate(x, y); c.rotate(float(hs.get("xoay", 0)))
    bo = float(hs.get("bo", 0))
    if bo:
        c.clipRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-w / 2, -h / 2, w, h), bo, bo), True)
    c.drawImageRect(img, skia.Rect.MakeXYWH(-w / 2, -h / 2, w, h), _SAMP_CUBIC)
    c.restore()


def _ve_chu(c, cs, W, H, ctx, nen_mau_lay=None):
    """vẽ 1 khối chữ → (hộp (x0,y0,x1,y1) px, kd, meta). 1.2.21: kiểu dáng thiếu → quyet_dinh bia.chu (co/dam/vien/bong/mau) → chu.*;
    font thiếu dấu → meta["thieu_glyph"] (ghi vào bia-kiem.json)."""
    kd = dict(cs.get("kieu_dang") or {})
    for k in ("co", "dam", "mau"):
        if kd.get(k) is None:
            kd[k] = _q(ctx, "bia.chu." + k)
    for k in ("vien", "bong", "nen", "gradient"):
        if k not in kd:
            kd[k] = _q(ctx, "bia.chu." + k, None)
    kd = _lop.kd_tu_quyet(kd, ctx, "chu", lop="bia")               # dong/can còn thiếu → chu.dong / chu.can
    kd["font"] = ctx.font_file(kd.get("font") or _q(ctx, "bia.chu.font", "tieu_de")) if ctx is not None else _chu.giai_font(kd.get("font"))
    rm = kd.get("rong_max", (cs.get("vi_tri") or {}).get("w"))
    rong = float(rm) * W if rm and float(rm) <= 1 else (float(rm) if rm else None)
    kd.pop("rong_max", None)
    img, meta = _chu.ve_chu(cs.get("text", ""), kd, W, H, rong, tra_skia=True)
    kx0, ky0, kx1, ky1 = meta["khoi"]; bw, bh = kx1 - kx0, ky1 - ky0
    vt = cs.get("vi_tri") or {}
    ax, ay = _lop.ANCHOR.get(vt.get("anchor", "mc"), (0.5, 0.5))
    px, py = float(vt.get("x", 0.5)) * W, float(vt.get("y", 0.5)) * H
    x0, y0 = px - ax * bw, py - ay * bh
    xoay = float(cs.get("xoay", 0))
    if nen_mau_lay is not None:
        nen_mau_lay(x0, y0, bw, bh)
    c.save()
    if xoay:
        c.translate(px, py); c.rotate(xoay); c.translate(-px, -py)
    c.drawImage(img, round(x0 - kx0), round(y0 - ky0))
    c.restore()
    hop = (x0, y0, x0 + bw, y0 + bh)
    if xoay:                                                      # hộp bao của hình chữ nhật đã xoay (hộp THẬT để đo chồng)
        g = abs(math.radians(xoay))
        bw2, bh2 = bw * math.cos(g) + bh * math.sin(g), bw * math.sin(g) + bh * math.cos(g)
        cx, cy = x0 + bw / 2, y0 + bh / 2
        hop = (cx - bw2 / 2, cy - bh2 / 2, cx + bw2 / 2, cy + bh2 / 2)
    return hop, kd, meta


def _dien_mau_video(tk, ctx):
    """thiết kế bìa thiếu màu → bảng màu của VIDEO (phong_cach) → của KÊNH (quyet_dinh bang_mau) → thieu_truong. Không có màu "nhà" cố định."""
    if not isinstance(tk, dict):
        return tk
    tk = json.loads(json.dumps(tk))
    for k in tk.get("khoi") or []:
        if isinstance(k, dict) and not k.get("mau") and not k.get("gradient"):
            k["mau"] = _mau_video(ctx, "nhan")
    ng = tk.get("nguoi")
    if isinstance(ng, dict) and isinstance(ng.get("vien_sang"), dict) and not ng["vien_sang"].get("mau"):
        ng["vien_sang"]["mau"] = _mau_video(ctx, "nhan")
    nen = tk.get("nen")
    if isinstance(nen, dict):
        if nen.get("kieu") == "mau" and not nen.get("gia_tri"):
            nen["gia_tri"] = _mau_video(ctx, "toi")
        if nen.get("kieu") == "gradient" and not nen.get("gia_tri"):
            nen["gia_tri"] = [_mau_video(ctx, "toi"), _mau_video(ctx, "toi")]
    return tk


def _giao_hop(a, b):
    """a, b = (x0,y0,x1,y1) → diện tích giao (px²)"""
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def _chong_chu(kiem_chu):
    """mọi cặp khối chữ có hộp giao nhau → [{"a": id, "b": id, "giao": % so với khối nhỏ hơn, "px": diện tích}] (máy chỉ ĐO, AI quyết)"""
    ra = []
    for i in range(len(kiem_chu)):
        for j in range(i + 1, len(kiem_chu)):
            ha, hb = kiem_chu[i]["hop"], kiem_chu[j]["hop"]
            g = _giao_hop(ha, hb)
            if g <= 0:
                continue
            nho = max(1.0, min((ha[2] - ha[0]) * (ha[3] - ha[1]), (hb[2] - hb[0]) * (hb[3] - hb[1])))
            ra.append({"a": kiem_chu[i]["id"], "b": kiem_chu[j]["id"], "giao": round(100.0 * g / nho, 1), "px": int(g)})
    return ra


def ve(du_an, bia_spec, ctx, nguon=None):
    """→ [bia-1.png, …] (một bìa mỗi phương án AI đưa); ghi dung/bia-kiem.json (so_dong, chong_chu, hộp thật, tương phản, đè mặt)"""
    W, H = (ctx.W, ctx.H) if ctx is not None else (1080, 1920)
    out = os.path.join(du_an, "dung"); os.makedirs(out, exist_ok=True)
    nguon = nguon or (ctx.nguon if ctx is not None else None) or []
    nguon = [n.get("duong") if isinstance(n, dict) else n for n in nguon]          # kế hoạch lưu {duong, vai}
    nguon = [n for n in nguon if n]
    t = float(bia_spec.get("khung_t", 0))
    tk0 = bia_spec.get("thiet_ke") or {}
    # 1.2.21: số bìa = số phương án AI đưa (không bù đủ 3, không biến thể máy tự chế); không có phương án → thiet_ke = 1 bìa; không có gì → thieu_truong
    pa = [p_ for p_ in (bia_spec.get("phuong_an") or []) if isinstance(p_, dict) and p_.get("thiet_ke")]
    ds_tk = [(float(p_.get("khung_t", t)), p_["thiet_ke"], p_.get("ten") or f"phương án {i + 1}") for i, p_ in enumerate(pa)]
    if not ds_tk and tk0:
        ds_tk = [(t, tk0, "như thiết kế")]
    if not ds_tk:
        raise _lop.ThieuTruong("bia.phuong_an", "AI chưa đưa thiết kế bìa nào (bia.phuong_an[].thiet_ke hoặc bia.thiet_ke)", "bia")
    ds_tk = [(a_, _dien_mau_video(b_, ctx), c_) for a_, b_, c_ in ds_tk]
    # ngưỡng đo (kênh quyết): tương phản tối thiểu WCAG, phần diện tích mặt bị chữ đè coi là đè
    tp_min = float(_q(ctx, "bia.tuong_phan_toi_thieu"))
    de_mat_max = float(_q(ctx, "bia.de_mat_toi_da"))
    # cache: cùng thiết kế + cùng nguồn + cùng khổ + cùng mã bìa + cùng quyết định → dùng lại bìa cũ (sửa một chữ trong video không vẽ lại bìa)
    try:
        ma = "".join(open(__file__, encoding="utf-8").read().split())
        pc = getattr(ctx, "pc", None) or {}
        bam = chung.bam({"spec": bia_spec, "nguon": [(n, os.path.getmtime(n) if os.path.isfile(n) else 0) for n in nguon],
                         "W": W, "H": H, "pc": pc, "ma": chung.bam(ma), "qd": (getattr(ctx, "quyet_dinh", None) or {}).get("bia")})
    except Exception:
        bam = None
    p_bam = os.path.join(out, ".bia-bam.txt")
    if bam and os.path.isfile(os.path.join(out, "bia-kiem.json")):
        try:
            if open(p_bam, encoding="utf-8").read().strip() == bam:
                cu = [x["file"] for x in (chung.doc_json(os.path.join(out, "bia-kiem.json"), {}) or {}).get("bien_the", []) if os.path.isfile(x.get("file", ""))]
                if len(cu) == len(ds_tk):
                    return cu
        except OSError:
            pass
    _khung_cache, _alpha_cache = {}, {}

    def _lay(tk_t):
        if tk_t not in _khung_cache:
            _khung_cache[tk_t] = lay_khung(nguon[0], tk_t, W, H, du_an) if nguon else np.zeros((H, W, 3), np.uint8)
        return _khung_cache[tk_t]

    def _alpha(tk_t):
        if tk_t not in _alpha_cache:
            _alpha_cache[tk_t] = tach_nguoi_co_han(_lay(tk_t), du_an)      # 1.2.21 (B3): có hạn 90 s — treo/lỗi → (None, None, lý do)
        return _alpha_cache[tk_t]
    ket = {"khung_t": t, "tach_nguoi": None, "so_bia": len(ds_tk), "nguong": {"tuong_phan_toi_thieu": tp_min, "de_mat_toi_da": de_mat_max},
           "bien_the": [], "may_sua": []}
    paths = []
    for so, (t_so, tk, ten_pa) in enumerate(ds_tk, 1):
        khung = _lay(t_so)
        alpha, nguon_alpha = (None, None)
        if tk.get("nguoi") is not None:
            alpha, nguon_alpha, ly_do_khong = _alpha(t_so)
            ket["tach_nguoi"] = ket["tach_nguoi"] or nguon_alpha
            if alpha is None:                           # bìa vẫn ra (nền + khối + chữ), báo máy đã bỏ người để AI/khách biết
                ket["may_sua"].append({"id": "bia_khong_tach_nguoi", "bia": so, "khung_t": t_so, "ly_do": ly_do_khong or "tách người không có kết quả"})
        surf = skia.Surface(W, H); c = surf.getCanvas(); c.clear(skia.ColorBLACK)
        nen = dict(tk.get("nen") or {})
        if not nen.get("kieu"):                      # thiết kế không ghi nền → nền của KÊNH (quyet_dinh bia.nen) — không còn khung_mo 0.4/0.3 trong máy
            qn = _q(ctx, "bia.nen")
            nen = dict(qn if isinstance(qn, dict) else {}, **nen)
        _ve_nen(c, nen, khung, W, H, ctx)
        for k in tk.get("khoi") or []:
            if not k.get("tren"):
                _ve_khoi(c, k, W, H)
        if tk.get("nguoi") is not None and alpha is not None:
            ng = dict(tk["nguoi"]) if isinstance(tk["nguoi"], dict) else {}
            for k_ in ("co", "x", "y"):                # người thiếu cỡ/vị trí → quyet_dinh bia.nguoi
                if ng.get(k_) is None:
                    ng[k_] = _q(ctx, "bia.nguoi." + k_)
            _ve_nguoi(c, khung, alpha, ng, W, H, ctx)
        for k in tk.get("khoi") or []:
            if k.get("tren"):
                _ve_khoi(c, k, W, H)
        for hs in tk.get("hinh") or []:
            _ve_hinh(c, hs, W, H, ctx)
        # nền dưới chữ (để đo tương phản) lấy trước khi vẽ chữ
        truoc = surf.makeImageSnapshot().toarray(colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
        kiem_chu = []
        for i_c, cs in enumerate(tk.get("chu") or []):
            hop, kd, meta = _ve_chu(c, cs, W, H, ctx)
            x0, y0, x1, y1 = [int(round(v)) for v in hop]
            trong = x0 >= -2 and y0 >= -2 and x1 <= W + 2 and y1 <= H + 2
            vung = truoc[max(0, y0):max(1, min(H, y1)), max(0, x0):max(1, min(W, x1)), :3]
            if vung.size:
                bgr = vung.reshape(-1, 3).mean(0)
                L2 = _do_sang((int(bgr[2]), int(bgr[1]), int(bgr[0])))
            else:
                L2 = 0.0
            mau_fill = kd.get("mau")
            if kd.get("gradient"):
                ms = kd["gradient"].get("mau") or [mau_fill]
                r = g = b = 0
                for m in ms:
                    rr, gg, bb, _ = _chu.mau(m); r += rr; g += gg; b += bb
                mau_fill = (r // len(ms), g // len(ms), b // len(ms))
            tp = tuong_phan(mau_fill, L2)
            for v in kd.get("vien") or []:
                tp = max(tp, tuong_phan(v.get("mau") or mau_fill, L2))
            muc = {"id": cs.get("id") or f"chu{i_c + 1}", "text": cs.get("text", "")[:40], "hop": [x0, y0, x1, y1], "trong_khung": trong,
                   "so_dong": int(meta.get("so_dong") or 1), "co": kd.get("co"), "tuong_phan": round(tp, 2), "dat": trong and tp >= tp_min}
            if meta.get("thieu_glyph"):
                muc["font_thieu_dau"] = meta["thieu_glyph"]
            kiem_chu.append(muc)
        chong = _chong_chu(kiem_chu)                 # 1.2.21: chồng chữ giữa các khối — ĐO và báo, không tự dời (AI quyết)
        img = surf.makeImageSnapshot()
        p = os.path.join(out, f"bia-{so}.png")
        img.save(p)
        bgr = cv2.cvtColor(img.toarray(colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType), cv2.COLOR_BGRA2BGR)
        mats = tim_mat(bgr) if (tk.get("nguoi") is not None and alpha is not None) else []
        can_mat = tk.get("nguoi") is not None and alpha is not None
        # chữ/khối đè lên MẶT (mắt–cằm) quá de_mat_toi_da diện tích mặt → bìa không đạt, báo rõ chữ nào (AI sửa vị trí thay vì đoán)
        for m_ in mats:
            fx0, fy0, fx1, fy1 = m_["x"] * W, m_["y"] * H, (m_["x"] + m_["w"]) * W, (m_["y"] + m_["h"]) * H
            for kc in kiem_chu:
                x0, y0, x1, y1 = kc["hop"]
                gx = max(0, min(x1, fx1) - max(x0, fx0)); gy = max(0, min(y1, fy1) - max(y0, fy0))
                phan = gx * gy / max(1.0, (fx1 - fx0) * (fy1 - fy0))
                kc["de_mat_phan"] = round(max(kc.get("de_mat_phan", 0.0), phan), 3)
                if phan > de_mat_max:
                    kc["dat"] = False; kc["de_mat"] = True
        ket["bien_the"].append({"file": p, "ten": ten_pa, "khung_t": t_so, "co_nguoi": can_mat, "mat_thay": len(mats), "mat_dat": (len(mats) >= 1) if can_mat else None,
                                "chu": kiem_chu, "chong_chu": chong, "so_dong": {k["id"]: k["so_dong"] for k in kiem_chu},
                                "dat": all(k["dat"] for k in kiem_chu) and ((len(mats) >= 1) if can_mat else True)})
        paths.append(p)
    for so in range(len(ds_tk) + 1, 7):
        try:
            os.remove(os.path.join(out, f"bia-{so}.png"))
        except OSError:
            pass
    chung.ghi_json(os.path.join(out, "bia-kiem.json"), ket)
    if bam:
        try:
            open(p_bam, "w", encoding="utf-8").write(bam)
        except OSError:
            pass
    return paths
