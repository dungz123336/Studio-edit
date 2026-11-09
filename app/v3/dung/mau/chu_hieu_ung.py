# -*- coding: utf-8 -*-
"""MẪU CHỮ HIỆU ỨNG (mũi Mẫu 2) — chữ có hoạt ảnh BÊN TRONG mẫu: từng ký tự/từ có trạng thái riêng (gõ máy, giải mã,
viết tay lộ theo nét, nảy lò xo, trượt mask, karaoke nền chạy, rung nhấn, phát sáng, 3D đùn khối, glitch…).

Mọi chữ đi qua `c.ve_chu` (kerning, dấu Việt, viền/bóng của engine chung). Bố cục dòng lấy từ `dung.chu.bo_cuc` nên vị trí
từng từ/ký tự trùng khít với khối chữ engine vẽ; mỗi phần được vẽ thành sprite riêng (cache) rồi ghép với biến đổi riêng.
Không hằng số thẩm mỹ hàn chết: cỡ chữ mặc định = lớn nhất vừa hộp; màu theo vai phong cách (c.mau); mọi nhịp/biên độ là tham số.

Phần đầu tệp là TIỆN ÍCH VẼ dùng chung cho các tệp mẫu của mũi Mẫu 2 (do_hoa, chuyen_canh, khung import từ đây).
"""
import json, math, os, random

import cv2
import numpy as np
import skia

from dung.mau import dang_ky
from dung import chu as _chu

# ============================================================================ TIỆN ÍCH CHUNG ====
# Skia raster ở máy này: cubic ~100 ms, Blur/DropShadow 50–150 ms, phối cảnh ~60 ms → dùng linear + nhoè/phối cảnh bằng cv2
SAMP = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kNone)
SAMP_LIN = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kNone)
SAMP_NONE = skia.SamplingOptions()


def kep(u, a=0.0, b=1.0):
    return a if u < a else b if u > b else float(u)


def pha(t, t0, dai):
    """tiến độ 0..1 của đoạn [t0, t0+dai]"""
    if dai <= 1e-6:
        return 1.0 if t >= t0 else 0.0
    return kep((t - t0) / dai)


def e_out(u, k=3.0):
    u = kep(u)
    return 1 - (1 - u) ** k


def e_in_out(u):
    u = kep(u)
    return 4 * u * u * u if u < 0.5 else 1 - ((-2 * u + 2) ** 3) / 2


def e_expo(u, k=10.0):
    u = kep(u)
    return 1.0 if u >= 1 else 1 - 2 ** (-k * u)


def e_back(u, s=1.70158):
    u = kep(u)
    c3 = s + 1
    return 1 + c3 * (u - 1) ** 3 + s * (u - 1) ** 2


def lo_xo(u, tat=6.0, tan=1.5):
    """lò xo tắt dần: 0→1 có vượt đích (tat: độ tắt, tan: số dao động trong đoạn)"""
    if u <= 0:
        return 0.0
    if u >= 1:
        return 1.0
    return 1 - math.exp(-tat * u) * math.cos(2 * math.pi * tan * u)


def tron(a, b, u):
    return a + (b - a) * u


def s_px(c, v):
    """px@1080 (khung rộng 1080) → px khung thật"""
    return float(v) * min(c.W, c.H) / 1080.0


def rgba(c, v, md="sang"):
    """vai|#hex → (r,g,b,a) 0..255"""
    return _chu.mau(c.mau(v if v not in (None, "") else md))


def mau_sk(c, v, md="sang", a=1.0):
    """vai|#hex → màu skia (nhân alpha a)"""
    return _chu.mau_skia(c.mau(v if v not in (None, "") else md), kep(a))


def hex_tu(rgb):
    return "#%02x%02x%02x" % tuple(int(kep(x, 0, 255)) for x in rgb[:3])


def toi_di(c, v, k):
    """màu vai/#hex nhân sáng k (k<1 tối đi) → #hex"""
    r, g, b, a = rgba(c, v)
    return hex_tu((r * k, g * k, b * k))


def do_sang(rgb):
    r, g, b = [x / 255.0 for x in rgb[:3]]
    f = lambda x: x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def mau_tuong_phan(c, nen, toi="toi", sang="sang"):
    """chọn vai chữ đọc rõ trên màu nền"""
    l = do_sang(rgba(c, nen))
    lt, ls = do_sang(rgba(c, toi)), do_sang(rgba(c, sang))
    tp = lambda a, b: (max(a, b) + 0.05) / (min(a, b) + 0.05)
    return toi if tp(l, lt) >= tp(l, ls) else sang


def be_mat(W, H):
    s = skia.Surface(max(1, int(W)), max(1, int(H)))
    cv = s.getCanvas()
    cv.clear(skia.Color4f(0, 0, 0, 0))
    return s, cv


def ra_np(surf, bong=None):
    """surface skia (premul) → numpy RGBA thẳng (h,w,4). bong=(dy, sigma, độ đậm) → thêm bóng mềm cả lớp"""
    p = np_premul(surf.makeImageSnapshot())
    if bong:
        p = bong_np(p, *bong)
    return unpremul_rgba(p)


def anh_tu_np_rgb(rgb):
    """numpy RGB/RGBA (h,w,3|4) → skia.Image"""
    a = np.ascontiguousarray(rgb)
    if a.shape[2] == 3:
        a = cv2.cvtColor(a, cv2.COLOR_RGB2BGRA)
    else:
        a = cv2.cvtColor(a, cv2.COLOR_RGBA2BGRA)
    a = np.ascontiguousarray(a)
    al = a[..., 3:4]
    if al.min() < 255:                       # nhân trước alpha một lần (ảnh unpremul vẽ chậm ~40× trên CPU)
        a = np.ascontiguousarray(np.concatenate([(a[..., :3].astype(np.uint16) * al + 127) // 255, al], axis=2).astype(np.uint8))
    return skia.Image.fromarray(a, skia.kBGRA_8888_ColorType, skia.kPremul_AlphaType)


def np_premul(img):
    """skia.Image → numpy BGRA premul (copy nhanh)"""
    return img.toarray(colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType)


def sk_premul(a):
    return skia.Image.fromarray(np.ascontiguousarray(a), skia.kBGRA_8888_ColorType, skia.kPremul_AlphaType)


def nhoe_np(a, sx, sy=None):
    """Gauss bằng cv2: thu nhỏ theo sigma → nhoè → phóng lại (≈ nhanh 10–15× Skia raster). a: uint8/float (h,w[,c])"""
    sy = sx if sy is None else sy
    if sx < 0.3 and sy < 0.3:
        return a
    h, w = a.shape[:2]
    fx, fy = max(1.0, sx / 2.0), max(1.0, sy / 2.0)
    if fx > 1.4 or fy > 1.4:
        nw, nh = max(1, int(round(w / fx))), max(1, int(round(h / fy)))
        b = cv2.resize(a, (nw, nh), interpolation=cv2.INTER_AREA)
        b = cv2.GaussianBlur(b, (0 if sx >= 0.3 else 1, 0 if sy >= 0.3 else 1), max(0.1, sx * nw / w), max(0.1, sy * nh / h))
        return cv2.resize(b, (w, h), interpolation=cv2.INTER_LINEAR)
    return cv2.GaussianBlur(a, (0 if sx >= 0.3 else 1, 0 if sy >= 0.3 else 1), max(0.1, sx), max(0.1, sy))


_MO = {}


def anh_mo(img, sx, sy=None, buoc=0.5):
    """skia.Image → (ảnh nhoè premul, lề) — cache theo mức nhoè (lượng tử `buoc` px)"""
    sy = sx if sy is None else sy
    qx, qy = round(sx / buoc) * buoc, round(sy / buoc) * buoc
    if qx < 0.3 and qy < 0.3:
        return img, 0
    k = (id(img), qx, qy)
    r = _MO.get(k)
    if r is not None and r[0] is img:
        return r[1], r[2]
    pad = int(math.ceil(3 * max(qx, qy))) + 2
    a = cv2.copyMakeBorder(np_premul(img), pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0)
    out = sk_premul(nhoe_np(a, qx, qy))
    if len(_MO) > 600:
        _MO.clear()
    _MO[k] = (img, out, pad)
    return out, pad


_NP = {}


def np_cache(img):
    """numpy premul của một skia.Image bất biến (cache theo đối tượng)"""
    r = _NP.get(id(img))
    if r is None or r[0] is not img:
        if len(_NP) > 3000:
            _NP.clear()
        r = (img, np_premul(img).copy())
        _NP[id(img)] = r
    return r[1]


_TO = {}


def to_mau(img, mau_rgb, sig=0.0):
    """ảnh → bóng/hào quang một màu (alpha giữ, tuỳ nhoè sig) — thay ColorFilter (chậm ~20 ms) → (ảnh, lề)"""
    k = (id(img), tuple(mau_rgb[:3]), round(sig, 1))
    r = _TO.get(k)
    if r is not None and r[0] is img:
        return r[1], r[2]
    a = np_cache(img)[..., 3]
    pad = 0
    if sig > 0.3:
        pad = int(math.ceil(3 * sig)) + 2
        a = nhoe_np(cv2.copyMakeBorder(a, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0), sig)
    af = a.astype(np.float32) * (1.0 / 255)
    out = np.dstack([af * mau_rgb[2], af * mau_rgb[1], af * mau_rgb[0], a.astype(np.float32)]).astype(np.uint8)
    im = sk_premul(out)
    if len(_TO) > 500:
        _TO.clear()
    _TO[k] = (img, im, pad)
    return im, pad


def ve_bien_doi(cv, img, x, y, cx, cy, sx=1.0, sy=1.0, rot=0.0, paint=None):
    """vẽ img (vị trí gốc x,y) phóng/xoay quanh (cx,cy). Có xoay → cv2.warpAffine (Skia raster xoay ~0.2 µs/px, quá chậm)"""
    if not rot:
        cv.save()
        cv.translate(cx, cy); cv.scale(sx, sy); cv.translate(-cx, -cy)
        cv.drawImage(img, x, y, SAMP, paint)
        cv.restore()
        return
    a = np_cache(img)
    h, w = a.shape[:2]
    th = math.radians(rot)
    co_, si = math.cos(th), math.sin(th)
    A = np.array([[co_ * sx, -si * sy], [si * sx, co_ * sy]], np.float64)
    t0 = A @ np.array([x - cx, y - cy]) + np.array([cx, cy])
    goc = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float64) @ A.T + t0
    bx0, by0 = math.floor(goc[:, 0].min()) - 1, math.floor(goc[:, 1].min()) - 1
    bw, bh = int(math.ceil(goc[:, 0].max())) + 2 - bx0, int(math.ceil(goc[:, 1].max())) + 2 - by0
    if bw <= 0 or bh <= 0:
        return
    M = np.hstack([A, (t0 - np.array([bx0, by0]))[:, None]]).astype(np.float32)
    patch = cv2.warpAffine(a, M, (bw, bh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    cv.drawImage(sk_premul(patch), bx0, by0, SAMP_NONE, paint)


def ve_xoay(cv, img, cx, cy, goc, sc=1.0, paint=None):
    """vẽ img xoay `goc` độ, tâm ảnh đặt tại (cx,cy)"""
    ve_bien_doi(cv, img, cx - img.width() / 2, cy - img.height() / 2, cx, cy, sc, sc, goc, paint)


def bong_np(pre, dy, sig, do=0.5, dx=0.0, mau=(0, 0, 0)):
    """thêm bóng đổ mềm dưới cả lớp (numpy BGRA premul) — thay DropShadow của Skia (chậm). Chỉ tính trong hộp có nội dung."""
    if do <= 0:
        return pre
    a = pre[..., 3]
    x, y, w, h = cv2.boundingRect(a)
    if w == 0 or h == 0:
        return pre
    m = int(math.ceil(3 * sig + max(abs(dx), abs(dy)))) + 2
    H_, W_ = a.shape
    x0, y0, x1, y1 = max(0, x - m), max(0, y - m), min(W_, x + w + m), min(H_, y + h + m)
    sub = pre[y0:y1, x0:x1]
    sa = np.ascontiguousarray(sub[..., 3])
    sh = nhoe_np(sa, sig)
    if dx or dy:
        sh = cv2.warpAffine(sh, np.float32([[1, 0, dx], [0, 1, dy]]), (sh.shape[1], sh.shape[0]))
    sh = cv2.multiply(sh, 255 - sa, scale=kep(do) / 255.0)
    out = pre.copy()
    o = out[y0:y1, x0:x1]
    if any(mau):
        for i, v in enumerate((mau[2], mau[1], mau[0])):
            if v:
                o[..., i] = cv2.add(np.ascontiguousarray(o[..., i]), cv2.convertScaleAbs(sh, alpha=v / 255.0))
    o[..., 3] = cv2.add(sa, sh)
    return out


def unpremul_rgba(p):
    b, g, r, a = cv2.split(p)
    return cv2.merge([cv2.divide(r, a, scale=255.0), cv2.divide(g, a, scale=255.0), cv2.divide(b, a, scale=255.0), a])


def rong(W, H):
    return np.zeros((max(1, int(H)), max(1, int(W)), 4), np.uint8)


def nen_hop(c, t, W, H):
    """ảnh nền thật dưới HỘP của lớp (RGB hoặc RGBA nếu engine gửi kèm alpha người) cỡ (H,W) — None nếu engine không cấp"""
    try:
        n = c.nen(t)
    except Exception:
        n = None
    if n is None:
        return None
    n = np.asarray(n)
    if n.ndim != 3 or n.shape[2] not in (3, 4):
        return None
    if n.shape[:2] == (H, W):
        return n
    try:
        if n.shape[:2] == (c.H, c.W) and c.lop is not None:
            x0, y0, w, h = c.lop.khoi()
            x0, y0 = int(round(x0)), int(round(y0))
            out = np.zeros((H, W, n.shape[2]), n.dtype)
            xa, ya, xb, yb = max(0, x0), max(0, y0), min(c.W, x0 + W), min(c.H, y0 + H)
            if xb > xa and yb > ya:
                out[ya - y0:yb - y0, xa - x0:xb - x0] = n[ya:yb, xa:xb]
            return out
    except Exception:
        pass
    return cv2.resize(n, (W, H), interpolation=cv2.INTER_LINEAR)


def alpha_nguoi(c, t, W, H):
    """mặt nạ người 0..1 (H,W) nếu engine cấp: kênh alpha của c.nen(t) (RGBA) hoặc ctx.nguoi(lop,t) — None nếu không có"""
    f = getattr(c.ctx, "nguoi", None) or getattr(c.ctx, "lay_nguoi", None)
    if callable(f):
        try:
            m = f(c.lop, t)
            if m is not None:
                m = np.asarray(m, np.float32)
                if m.max() > 1.5:
                    m = m / 255.0
                if m.shape[:2] != (H, W):
                    m = cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)
                return m
        except Exception:
            pass
    n = nen_hop(c, t, W, H)
    if n is not None and n.shape[2] == 4:
        return n[..., 3].astype(np.float32) / 255.0
    return None


def duong_muot(pts, dong=False):
    """polyline → path mượt (quad qua trung điểm)"""
    p = skia.Path()
    if len(pts) < 2:
        return p
    p.moveTo(*pts[0])
    if len(pts) == 2:
        p.lineTo(*pts[1])
        return p
    for i in range(1, len(pts) - 1):
        mx, my = (pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2
        p.quadTo(pts[i][0], pts[i][1], mx, my)
    p.lineTo(*pts[-1])
    if dong:
        p.close()
    return p


def cat_duong(path, u0, u1=None):
    """đoạn [u0,u1] (tỉ lệ độ dài) của path (một nét liền) → (path con, độ dài, (điểm, tiếp tuyến) cuối)"""
    if u1 is None:
        u0, u1 = 0.0, u0
    pm = skia.PathMeasure(path, False)
    L = pm.getLength()
    d = skia.Path()
    if L <= 0 or u1 <= u0:
        return d, L, None
    pm.getSegment(L * kep(u0), L * kep(u1), d, True)
    pt = pm.getPosTan(L * kep(u1))
    return d, L, pt


def but_net(mau, day, cap=True):
    p = skia.Paint(AntiAlias=True)
    p.setStyle(skia.Paint.kStroke_Style)
    p.setStrokeWidth(float(day))
    p.setStrokeCap(skia.Paint.kRound_Cap if cap else skia.Paint.kButt_Cap)
    p.setStrokeJoin(skia.Paint.kRound_Join)
    p.setColor(mau)
    return p


def loc_mau(mau_sk_):
    """color filter tô toàn bộ ảnh thành một màu (giữ alpha)"""
    return skia.ColorFilters.Blend(mau_sk_, skia.BlendMode.kSrcIn)


def ve_lo(cv, img, x, y, e, mem, goc=0.0, cy=None, paint=None, sampling=None):
    """vẽ img tại (x,y) nhưng chỉ LỘ phần trước mép quét e (toạ độ canvas, đi trái→phải), mép mềm `mem` px,
    nghiêng `goc` độ (mép như nét bút chéo)."""
    if cy is None:
        cy = y + img.height() / 2
    cv.saveLayer(None, paint)
    cv.drawImage(img, x, y, sampling or SAMP_NONE, None)
    a = math.radians(goc)
    nx, ny = math.cos(a), math.sin(a)
    m = skia.Paint()
    m.setBlendMode(skia.BlendMode.kDstIn)
    m.setShader(skia.GradientShader.MakeLinear([skia.Point(e - mem * nx, cy - mem * ny), skia.Point(e, cy)],
                                               [skia.ColorBLACK, skia.ColorTRANSPARENT]))
    cv.drawRect(skia.Rect.MakeXYWH(x - 4, y - 4, img.width() + 8, img.height() + 8), m)
    cv.restore()


def chuoi(v):
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return " ".join(str(x) for x in v)
    return str(v)


# ---------------------------------------------------------------------------- kiểu dáng ----
_KHOA_KD = ("font", "co", "dam", "hoa", "gian", "dong", "nghieng", "can")


def kieu_dang(c, p, font="tieu_de", mau="sang", tien_to="", **them):
    """dựng kieu_dang cho engine chữ từ tham số mẫu. tien_to: tiền tố khoá (vd "phu_" → phu_co, phu_font…).
    - "co" bỏ trống = tự lớn nhất vừa hộp; "vien" = độ dày viền theo em (0.05) + "mau_vien"; "bong" = 0..1 độ đậm bóng mềm
    - "kieu_dang" (dict) ghi đè toàn bộ như lớp chu"""
    kd = {"font": font, "mau": mau}
    kd.update(them)
    for k in _KHOA_KD:
        v = p.get(tien_to + k)
        if v is not None:
            kd[k] = v
    v = p.get(tien_to + "mau_chu") if tien_to else p.get("mau_chu")
    if v not in (None, ""):
        kd["mau"] = v
    kd.update(p.get(tien_to + "kieu_dang") or {})
    kd.pop("nen", None)
    kd.pop("rong_max", None)
    f = str(kd.get("font") or font)
    kd["font"] = f if os.path.isfile(f) else c.ctx.font_file(f)
    kd["mau"] = c.mau(kd["mau"]) if isinstance(kd["mau"], str) else kd["mau"]
    # 1.2.21: đậm / hệ số dòng / căn thiếu → quyet_dinh chu.* (không còn 700 / 1.15 / giua trong chu.py)
    for k in ("dam", "dong", "can"):
        if kd.get(k) is None:
            kd[k] = c.quyet("chu." + k)
    if "vien" in kd and isinstance(kd["vien"], list):
        kd["vien"] = [dict(v, mau=c.mau(v.get("mau", "toi"))) for v in kd["vien"]]
    else:
        v = float(p.get(tien_to + "vien", them.get("_vien", 0)) or 0)
        kd.pop("vien", None)
        if v > 0:
            kd["_vien_em"] = [v, c.mau(p.get(tien_to + "mau_vien") or "toi")]
    if "bong" in kd and isinstance(kd["bong"], list):
        kd["bong"] = [dict(b, mau=c.mau(b.get("mau", "#000000aa"))) for b in kd["bong"]]
    else:
        # 1.2.21: bóng mặc định của mẫu KHÔNG còn 0.5 hàn trong máy: tham số mẫu `bong` → `_bong` của mẫu → quyet_dinh chu.bong
        # (list bóng engine → dùng nguyên; số 0..1 → độ đậm bóng mềm theo em; null/[] → không bóng)
        b = p.get(tien_to + "bong", them.get("_bong"))
        kd.pop("bong", None)
        if b is None:
            b = c.quyet("chu.bong", None, bat_buoc=False)
            if b is None and not c.quyet("chu", None, bat_buoc=False):
                raise c.thieu("chu.bong", "bóng chữ của mẫu")
        if isinstance(b, list):
            if b:
                kd["bong"] = [dict(x, mau=c.mau(x.get("mau", "#000000aa"))) for x in b if isinstance(x, dict)]
        elif b:
            kd["_bong_em"] = float(b)
    kd.pop("_vien", None)
    kd.pop("_bong", None)
    return kd


def _ap_em(kd, co):
    k = {x: v for x, v in kd.items() if not x.startswith("_")}
    k["co"] = float(co)
    if kd.get("_vien_em"):
        w, m = kd["_vien_em"]
        k["vien"] = [{"w": max(1.0, w * co), "mau": m}]
    if kd.get("_bong_em"):
        s = kep(kd["_bong_em"], 0, 2)
        k["bong"] = [{"x": 0, "y": round(co * 0.035, 1), "mo": round(co * 0.16, 1), "mau": "#000000%02x" % int(kep(0.55 * s) * 255)},
                     {"x": 0, "y": round(co * 0.012, 1), "mo": round(co * 0.035, 1), "mau": "#000000%02x" % int(kep(0.35 * s) * 255)}]
    return k


def _js(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------- khối chữ ----
_BO = _chu.CacheAnh("mau.chu._BO")            # 1.2.21: trần RAM chung (cache_anh_mb)
_SPRITE = _chu.CacheAnh("mau.chu._SPRITE")


def _le_mau(c, w, h):
    """1.2.21: lề hộp chữ của mẫu là THAM SỐ (le_ngang/le_doc, phần hộp 0..0.45, mặc định 0) — không còn W*0.8/H*0.62 hàn trong mẫu"""
    p = getattr(c, "p", None) or {}
    try:
        ln = kep(float(p.get("le_ngang", 0) or 0), 0, 0.45); ld = kep(float(p.get("le_doc", 0) or 0), 0, 0.45)
    except Exception:
        ln = ld = 0.0
    return w * (1 - 2 * ln), h * (1 - 2 * ld)


class BoChu:
    """khối chữ đã xếp dòng + vừa hộp. Toạ độ phần (từ/ký tự) tính từ gốc khối (0,0) = góc trên-trái hộp dòng đầu.
    .phan [{txt,x,y,w,h,i,tu,dong}] · .w .h (hộp dòng) · .tren .duoi (mực thật so với hộp: tren ≤ 0, duoi ≥ h) · .co · .base
    1.2.21: AI ghi `co` > 0 → TÔN TRỌNG khi vừa HỘP lớp (canvas vật lý của mẫu); tràn hộp → thu tới vừa và ghi may_sua
    {sua: "thu_chu_mau", co_truoc, co_sau, hop} (R4b: trước so với khung video nên chữ bị cắt ở mép hộp mà không báo).
    `co` bỏ trống → tự tìm cỡ lớn nhất vừa hộp (tìm kiếm vật lý, bắt đầu từ h·co_hop)."""

    def __init__(self, c, text, kd, w, h, tach="tu", co_hop=1.0, rong_max=None, co_toi_da=None):
        self.c = c
        text = _chu.NFC(chuoi(text)) if hasattr(_chu, "NFC") else chuoi(text)
        co = float(kd.get("co") or 0)
        tu_vua = co <= 0
        co_ai = None if tu_vua else co
        if tu_vua:
            co = max(8.0, h * co_hop)
        if co_toi_da and tu_vua:
            co = min(co, float(co_toi_da))
        bc = None
        # R4b 1.2.21: giới hạn VẬT LÝ là HỘP của lớp (mẫu vẽ lên canvas W×H = hộp, LopMau.noi_dung cắt đúng hộp) — không phải khung video:
        # trước đây so với c.W×c.H nên chữ co AI ghi lớn hơn hộp bị CẮT ở mép hộp mà không có may_sua (thử co=300 ở hộp 993×499: mất mực trên/dưới)
        W_k, H_k = float(w), float(h)
        for _ in range(40):
            kdc = _ap_em(kd, co)
            kdp = _chu._kd(kdc, c.W)
            le = _chu.le_kd(kdp)
            aw = max(8.0, w - le["trai"] - le["phai"])
            ah = max(8.0, h - le["tren"] - le["duoi"])
            rm = min(aw, rong_max) if rong_max else aw
            bc = _chu.bo_cuc(text, kdp, rm, c.W)
            noi = " ".join(t["txt"] for t in bc["tu"]) or "H"
            tren, duoi = _chu._muc_doc(noi, bc["kd"])
            n = max(1, len(bc["dong"]))
            muc_tren = min(0.0, bc["base"] + tren)
            muc_duoi = max(bc["h"], (n - 1) * bc["cao_dong"] + bc["base"] + duoi)
            cao = muc_duoi - muc_tren
            if bc["w"] <= rm + 0.5 and cao <= ah + 0.5:   # cỡ AI ghi: giữ nguyên khi vừa hộp; tràn hộp → thu + may_sua (AI nới vi_tri.w/h nếu muốn to hơn)
                break
            r = min(rm / max(bc["w"], 1.0), ah / max(cao, 1.0))
            co *= max(0.5, min(0.96, r if r < 0.96 else 0.96))
        if co_ai is not None and abs(co - co_ai) > 0.05:
            try:
                c.ghi_may_sua({"sua": "thu_chu_mau", "co_truoc": round(co_ai, 1), "co_sau": round(co, 1), "hop": [int(W_k), int(H_k)],
                               "mo_ta": "chữ mẫu «%s» cỡ %g tràn hộp lớp %d×%d px (vi_tri.w/h) → thu còn %g; muốn to hơn thì nới hộp" % (text[:30], co_ai, int(W_k), int(H_k), round(co, 1))})
            except Exception:
                pass
        self.co_ai = co_ai
        self.text = text
        self.kd = dict(kdc)
        self.kd["dong"] = float(bc["kd"]["dong"])
        self.kdp = bc["kd"]
        self.co = co
        self.le = le
        self.rm = rm
        self.w, self.h = float(bc["w"]), float(bc["h"])
        self.cao_dong, self.base = float(bc["cao_dong"]), float(bc["base"])
        self.tren, self.duoi = muc_tren, muc_duoi
        self.dong = bc["dong"]
        self.tu = bc["tu"]
        self.ky = _chu._ky_tu(bc) if tach == "ky_tu" else None
        self.phan = self.ky if tach == "ky_tu" else self.tu
        self.muc_tren, self.muc_duoi = tren, duoi       # so với baseline
        self._kd_js = _js(self.kd)

    # gốc khối để khối (kể cả mực dấu) nằm giữa hộp (ax, ay: 0 trái/trên … 1 phải/dưới)
    def goc(self, W, H, ax=0.5, ay=0.5, dx=0.0, dy=0.0):
        cao = self.duoi - self.tren
        ox = (W - self.w) * ax + dx
        oy = (H - cao) * ay - self.tren + dy
        return round(ox), round(oy)

    def sprite(self, txt, mau=None, them=None):
        """→ (skia.Image, gx, gy, rộng mực) : vẽ ở (gốc + phan.x − gx, gốc + phan.y − gy)"""
        k = (txt, mau, _js(them) if them else "", self._kd_js)
        r = _SPRITE.get(k)
        if r is None:
            kd2 = dict(self.kd)
            if mau is not None:
                kd2["mau"] = mau
            if them:
                kd2.update(them)
            img, meta = self.c.ve_chu(txt, kd2, tra_skia=True)
            x0, y0, x1, y1 = meta["khoi"]
            r = (img, float(meta["goc"][0]), float(meta["goc"][1]), float(x1 - x0))
            _SPRITE[k] = r
        return r

    def anh_khoi(self, mau=None, them=None):
        """cả khối thành một ảnh → (img, gx, gy): vẽ ở (gốc − gx, gốc − gy)"""
        k = ("\x00khoi", self.text, mau, _js(them) if them else "", self._kd_js, round(self.rm, 1))
        r = _SPRITE.get(k)
        if r is None:
            kd2 = dict(self.kd)
            if mau is not None:
                kd2["mau"] = mau
            if them:
                kd2.update(them)
            img, meta = self.c.ve_chu(self.text, kd2, rong_max_px=self.rm, tra_skia=True)
            r = (img, float(meta["goc"][0]), float(meta["goc"][1]))
            _SPRITE[k] = r
        return r

    def tam_phan(self, i, ox, oy, chan=False):
        p = self.phan[i]
        cx = ox + p["x"] + p["w"] / 2
        cy = oy + p["y"] + (self.base if chan else self.base - self.co * 0.36)
        return cx, cy

    def ve_phan(self, cv, i, ox, oy, op=1.0, sc=1.0, dx=0.0, dy=0.0, rot=0.0, mau=None, mo=0.0, mo_y=None, sx=None, sy=None,
                chan=False, txt=None, paint=None):
        """vẽ phần i với biến đổi riêng (scale/rot quanh tâm phần, chan=True: quanh chân baseline)"""
        if op <= 0.002 or sc <= 0.002:
            return
        p = self.phan[i]
        img, gx, gy, wv = self.sprite(txt if txt is not None else p["txt"], mau)
        x = ox + p["x"] - gx + dx
        y = oy + p["y"] - gy + dy
        if txt is not None:          # ký tự thay (giải mã): canh giữa ô ký tự gốc
            x += (p["w"] - wv) / 2
        pt = paint or skia.Paint(AntiAlias=True)
        if op < 0.999:
            pt.setAlphaf(kep(op))
        my = mo if mo_y is None else mo_y
        if mo > 0.25 or my > 0.25:
            img, pad = anh_mo(img, mo, my, buoc=max(0.5, max(mo, my) / 6))
            x -= pad; y -= pad
        bien = sc != 1.0 or rot != 0.0 or sx is not None or sy is not None
        if not bien:
            if abs(dx - round(dx)) < 1e-3 and abs(dy - round(dy)) < 1e-3:
                cv.drawImage(img, round(x), round(y), SAMP_NONE, pt)
            else:
                cv.drawImage(img, x, y, SAMP_LIN, pt)
            return
        cx, cy = self.tam_phan(i, ox + dx, oy + dy, chan)
        ve_bien_doi(cv, img, x, y, cx, cy, sx if sx is not None else sc, sy if sy is not None else sc, rot, pt)

    def ve_khoi(self, cv, ox, oy, op=1.0, sc=1.0, mau=None, mo=0.0, paint=None, tam=None, them=None):
        img, gx, gy = self.anh_khoi(mau, them)
        pt = paint or skia.Paint(AntiAlias=True)
        if op < 0.999:
            pt.setAlphaf(kep(op))
        if mo > 0.25:
            img, pad = anh_mo(img, mo, buoc=max(0.5, mo / 6))
            gx += pad; gy += pad
        if sc == 1.0:
            cv.drawImage(img, round(ox - gx), round(oy - gy), SAMP_NONE, pt)
            return
        cx, cy = tam if tam else (ox + self.w / 2, oy + (self.tren + self.duoi) / 2)
        cv.save()
        cv.translate(cx, cy)
        cv.scale(sc, sc)
        cv.translate(-cx, -cy)
        cv.drawImage(img, ox - gx, oy - gy, SAMP, pt)
        cv.restore()

    def hop_phan(self, i, ox, oy, dem=0.0):
        """hộp mực của phần i (toạ độ canvas) → (x0,y0,x1,y1)"""
        p = self.phan[i]
        return (ox + p["x"] - dem, oy + p["y"] + self.base + self.muc_tren - dem,
                ox + p["x"] + p["w"] + dem, oy + p["y"] + self.base + self.muc_duoi + dem)


def bo_chu(c, text, kd, w, h, tach="tu", co_hop=1.0, rong_max=None, co_toi_da=None):
    """khối chữ vừa hộp (w, h) — 1.2.21: hộp đã trừ lề tham số mẫu le_ngang/le_doc (c.p); cache theo khoá (trần RAM chung)"""
    w, h = _le_mau(c, w, h)
    k = (chuoi(text), _js(kd), int(w), int(h), tach, round(co_hop, 3), rong_max, co_toi_da, int(getattr(c, "W", 0)), int(getattr(c, "H", 0)))
    b = _BO.get(k)
    if b is None:
        b = BoChu(c, text, kd, w, h, tach, co_hop, rong_max, co_toi_da)
        _BO[k] = b
    elif b.co_ai is not None and abs(b.co - b.co_ai) > 0.05:          # cache trúng nhưng lớp khác → vẫn ghi may_sua cho lớp này
        try:
            c.ghi_may_sua({"sua": "thu_chu_mau", "co_truoc": round(b.co_ai, 1), "co_sau": round(b.co, 1),
                           "mo_ta": "chữ mẫu «%s» cỡ %g tràn hộp lớp → thu còn %g; muốn to hơn thì nới vi_tri.w/h" % (b.text[:30], b.co_ai, round(b.co, 1))})
        except Exception:
            pass
    return b


def moc_tu(p, n, nhip_md=0.3, tre_md=0.0):
    """mốc giây xuất hiện từng từ: p["moc"] (list giây từ t0, vd lấy từ lời Whisper) hoặc đều theo p["nhip"]"""
    m = p.get("moc")
    if isinstance(m, (list, tuple)) and len(m) >= n:
        return [float(x) for x in m[:n]]
    tre = float(p.get("tre", tre_md))
    nh = float(p.get("nhip", nhip_md))
    return [tre + i * nh for i in range(n)]


def lam_sach(s):
    return "".join(ch for ch in s.lower() if ch.isalnum())


# chung cho mô tả tham số
TS_CHU = {"co": "cỡ chữ px — ghi thì máy TÔN TRỌNG (chỉ thu khi tràn khung video, có ghi may_sua); bỏ trống = lớn nhất vừa hộp",
          "font": "vai (tieu_de|phu_de|nhan|than|script) hoặc id font kho",
          "dam": "độ đậm 100..900 (bỏ trống = quyet_dinh chu.dam)", "mau_chu": "màu chữ: vai (sang|toi|nhan|nhan2) hoặc #hex", "hoa": "true = IN HOA",
          "gian": "giãn chữ (em, vd -0.02)", "vien": "viền chữ dày (em, 0 = không)", "mau_vien": "màu viền (toi)",
          "bong": "bóng dưới chữ: số 0..1 độ đậm bóng mềm | list bóng như lớp chu | 0 = không (bỏ trống = quyet_dinh chu.bong)",
          "le_ngang": "lề trái/phải chừa trong hộp mẫu, phần hộp 0..0.45 (0 = dùng hết hộp)", "le_doc": "lề trên/dưới chừa trong hộp mẫu, phần hộp 0..0.45 (0)",
          "kieu_dang": "dict kieu_dang đầy đủ như lớp chu (ghi đè)"}


def _ts(**kw):
    d = dict(TS_CHU)
    d.update(kw)
    return d


HOP_CHU = {"anchor": "mc", "x": 0.5, "y": 0.5, "w": 0.9, "h": 0.24}


# ============================================================================ MẪU CHỮ ====

# ---------------------------------------------------------------- chữ cộng dồn theo lời ----
@dang_ky(id="mau.go-theo-loi", nhom="chu", ten="Chữ cộng dồn theo lời",
         mo_ta="câu then chốt hiện TỪNG TỪ đúng lúc nói (mờ + nhích lên), giữ lại cả câu theo trang ≤ so_dong dòng; từ khoá tô màu nhấn",
         hop_nghia=["câu chốt", "nhấn mạnh", "lời hứa", "trích dẫn", "đọc cùng nhịp"],
         tham_so=_ts(chu="câu (≤ 14 từ)", moc="list giây xuất hiện từng từ tính từ t0 (lấy từ lời) — bỏ trống = đều theo nhip",
                     nhip="giây giữa 2 từ khi không có moc (0.28)", dai_hien="giây mỗi từ hiện (0.14)", nang="độ nhích lên (em, 0.22)",
                     so_dong="số dòng tối đa mỗi trang (2)", nhan_tu="list từ tô màu nhấn", mau_nhan="màu từ nhấn (nhan)"),
         mac_dinh={"nhip": 0.28, "dai_hien": 0.14, "nang": 0.22, "so_dong": 2, "nhan_tu": [], "mau_nhan": "nhan", "bong": 0.6},
         hop={"anchor": "mc", "x": 0.5, "y": 0.66, "w": 0.9, "h": 0.2}, dong=True,
         sfx_goi_y=["gõ nhẹ từng từ", "tick nhỏ"],
         vi_du={"chu": "Đừng bao giờ bỏ cuộc khi bạn đã đi được nửa đường", "nhan_tu": ["bỏ cuộc", "nửa đường"], "nhip": 0.22})
def go_theo_loi(t, dur, W, H, c, p):
    kd = kieu_dang(c, p, "phu_de", "sang")
    so_dong = max(1, int(p.get("so_dong", 2)))
    co_max = float(kd.get("co") or H / (so_dong * 1.32))
    co = co_max
    if not kd.get("co"):                       # lớn nhất mà cả câu ≤ so_dong dòng; không được thì chia trang ở cỡ vừa
        co = co_max * 0.72
        k = co_max
        while k >= co_max * 0.5:
            if len(bo_chu(c, p.get("chu", ""), dict(kd, co=round(k, 1)), W, H * 30).dong) <= so_dong:
                co = k
                break
            k *= 0.93
    bc = bo_chu(c, p.get("chu", ""), dict(kd, co=round(co, 1)), W, H * 30)
    n = len(bc.tu)
    if n == 0:
        return rong(W, H)
    moc = moc_tu(p, n, 0.28)
    dai = float(p.get("dai_hien", 0.14))
    nhan = set()
    for cum in p.get("nhan_tu") or []:
        for x in str(cum).split():
            nhan.add(lam_sach(x))
    mau_nhan = c.mau(p.get("mau_nhan", "nhan"))
    hien = [i for i in range(n) if t >= moc[i]]
    if not hien:
        return rong(W, H)
    dong_cuoi = bc.tu[hien[-1]]["dong"]
    trang = dong_cuoi // so_dong
    d0, d1 = trang * so_dong, min(len(bc.dong), trang * so_dong + so_dong)
    k = d1 - d0
    s, cv = be_mat(W, H)
    cao = (k - 1) * bc.cao_dong + bc.base + bc.muc_duoi - min(0, bc.base + bc.muc_tren)
    ox = round((W - bc.w) / 2)
    oy = round((H - cao) / 2 - min(0, bc.base + bc.muc_tren) - d0 * bc.cao_dong)
    nang = float(p.get("nang", 0.22)) * bc.co
    for i in hien:
        tu = bc.tu[i]
        if not (d0 <= tu["dong"] < d1):
            continue
        u = e_out(pha(t, moc[i], dai))
        m = mau_nhan if lam_sach(tu["txt"]) in nhan else None
        bc.ve_phan(cv, i, ox, oy, op=u, dy=(1 - u) * nang, mau=m)
    return ra_np(s)


# ---------------------------------------------------------------- từ khoá bật ----
@dang_ky(id="mau.tu-khoa-nay", nhom="chu", ten="Từ khoá bật",
         mo_ta="một ý chính chữ to bật từ to → vừa (vượt đích nhẹ), kèm dòng nhỏ dẫn phía trên mờ vào",
         hop_nghia=["từ khoá", "ý chính", "kết quả", "nhấn mạnh", "con số"],
         tham_so=_ts(chu="từ/cụm chính", phu="dòng nhỏ phía trên (tuỳ)", nay="tỉ lệ lúc bật (1.25)", dai="giây bật (0.3)",
                     mau_phu="màu dòng nhỏ (sang)", ti_le_phu="phần chiều cao hộp cho dòng nhỏ (0.26)", phu_co="cỡ dòng nhỏ px (tự)"),
         mac_dinh={"nay": 1.25, "dai": 0.3, "mau_chu": "nhan", "mau_phu": "sang", "ti_le_phu": 0.26, "bong": 0.6},
         hop=HOP_CHU, dong=True, sfx_goi_y=["bật pop", "whoosh ngắn"],
         vi_du={"chu": "TĂNG GẤP ĐÔI", "phu": "chỉ sau 7 ngày"})
def tu_khoa_nay(t, dur, W, H, c, p):
    phu = chuoi(p.get("phu"))
    tp = float(p.get("ti_le_phu", 0.26)) if phu else 0.0
    nay = max(1.0, float(p.get("nay", 1.25)))
    kd = kieu_dang(c, p, "tieu_de", "nhan", gian=-0.02)
    bc = bo_chu(c, p.get("chu", ""), kd, W * 0.96 / min(nay, 1.12), H * (1 - tp) * 0.92)
    s, cv = be_mat(W, H)
    hp = 0.0
    if phu:
        kp = kieu_dang(c, {"mau_chu": p.get("mau_phu", "sang"), "co": p.get("phu_co"), "bong": p.get("bong", 0.6),
                           "font": p.get("phu_font")}, "phu_de", "sang")
        bp = bo_chu(c, phu, kp, W * 0.9, H * tp)
        hp = bp.duoi - bp.tren
    cao_main = bc.duoi - bc.tren
    gap = bc.co * 0.08 if phu else 0
    tong = hp + gap + cao_main
    y0 = (H - tong) / 2
    ox, oy = bc.goc(W, H)
    oy = round(y0 + hp + gap - bc.tren)
    dai = float(p.get("dai", 0.3))
    u = pha(t, 0, dai)
    nay_eff = min(nay, W * 0.99 / max(bc.w, 1), H * 0.99 / max(cao_main, 1) if not phu else nay)
    sc = nay_eff + (1 - nay_eff) * e_back(u, 2.0) if u < 1 else 1.0
    bc.ve_khoi(cv, ox, oy, op=e_out(pha(t, 0, dai * 0.4)), sc=sc)
    if phu:
        ua = e_out(pha(t, 0.08, 0.22))
        bx, by = bp.goc(W, H)
        by = round(y0 - bp.tren + (1 - ua) * bp.co * 0.3)
        bp.ve_khoi(cv, bx, by, op=ua)
    return ra_np(s)


# ---------------------------------------------------------------- chữ hai tầng ----
@dang_ky(id="mau.hai-tang", nhom="chu", ten="Chữ hai tầng (hook)",
         mo_ta="lời hứa 3 giây đầu: dòng nhỏ dẫn mờ vào + dòng lớn chốt bật lên sau một nhịp",
         hop_nghia=["mở đầu", "hook", "lời hứa", "tiêu đề", "số liệu"],
         tham_so=_ts(dong1="dòng nhỏ dẫn", dong2="dòng lớn chốt", mau1="màu dòng nhỏ (sang)", mau2="màu dòng lớn (nhan)",
                     ti_le="phần chiều cao cho dòng nhỏ (0.3)", tre="giây dòng lớn vào sau dòng nhỏ (0.15)", dai="giây mỗi dòng vào (0.3)",
                     font1="font dòng nhỏ (phu_de)", font2="font dòng lớn (tieu_de)"),
         mac_dinh={"mau1": "sang", "mau2": "nhan", "ti_le": 0.3, "tre": 0.15, "dai": 0.3, "font1": "phu_de", "font2": "tieu_de", "bong": 0.6},
         hop={"anchor": "mc", "x": 0.5, "y": 0.24, "w": 0.92, "h": 0.26}, dong=True,
         sfx_goi_y=["whoosh lên", "bùm trầm"],
         vi_du={"dong1": "Bí quyết mà ít ai nói", "dong2": "LƯƠNG 50 TRIỆU"})
def hai_tang(t, dur, W, H, c, p):
    tl = kep(float(p.get("ti_le", 0.3)), 0.1, 0.6)
    k1 = kieu_dang(c, dict(p, mau_chu=p.get("mau1")), p.get("font1", "phu_de"), "sang")
    k2 = kieu_dang(c, dict(p, mau_chu=p.get("mau2")), p.get("font2", "tieu_de"), "nhan", gian=-0.03)
    k1.pop("co", None); k2.pop("co", None)
    b1 = bo_chu(c, p.get("dong1", ""), k1, W * 0.9, H * tl * 0.95)
    b2 = bo_chu(c, p.get("dong2", ""), k2, W * 0.96 / 1.04, H * (1 - tl) * 0.92)
    h1, h2 = b1.duoi - b1.tren, b2.duoi - b2.tren
    gap = b2.co * 0.06
    y0 = (H - h1 - gap - h2) / 2
    s, cv = be_mat(W, H)
    dai = float(p.get("dai", 0.3))
    u1 = e_out(pha(t, 0, dai * 0.75))
    x1, _ = b1.goc(W, H)
    b1.ve_khoi(cv, x1, round(y0 - b1.tren + (1 - u1) * b1.co * 0.35), op=u1)
    tre = float(p.get("tre", 0.15))
    if t >= tre:
        u2 = pha(t, tre, dai)
        x2, _ = b2.goc(W, H)
        y2 = round(y0 + h1 + gap - b2.tren)
        b2.ve_khoi(cv, x2, y2, op=e_out(pha(t, tre, dai * 0.4)), sc=0.85 + 0.15 * e_back(u2, 1.6) if u2 < 1 else 1.0)
    return ra_np(s)


# ---------------------------------------------------------------- âm tiết trượt lên ----
@dang_ky(id="mau.truot-len", nhom="chu", ten="Âm tiết trượt lên + nhoè dọc",
         mo_ta="từng âm tiết trượt từ dưới lên so le, nhoè chuyển động dọc theo tốc độ rồi nét lại — cảm giác nhanh, mượt",
         hop_nghia=["tốc độ", "đi lên", "tăng trưởng", "mượt", "hiện đại"],
         tham_so=_ts(chu="cụm ngắn", so_le="giây giữa 2 âm tiết (0.08)", dai="giây mỗi âm tiết (0.4)", quang="quãng trượt (em, 0.8)",
                     nhoe="độ nhoè dọc tối đa (em, 0.25)", huong="len|xuong (len)"),
         mac_dinh={"so_le": 0.08, "dai": 0.4, "quang": 0.8, "nhoe": 0.25, "huong": "len", "mau_chu": "sang", "bong": 0.5},
         hop=HOP_CHU, dong=True, sfx_goi_y=["whoosh nhanh", "vút lên"],
         vi_du={"chu": "Nhanh gấp ba lần"})
def truot_len(t, dur, W, H, c, p):
    kd = kieu_dang(c, p, "tieu_de", "sang")
    bc = bo_chu(c, p.get("chu", ""), kd, W, H)
    s, cv = be_mat(W, H)
    ox, oy = bc.goc(W, H)
    so_le, dai = float(p.get("so_le", 0.08)), float(p.get("dai", 0.4))
    dau = 1 if p.get("huong", "len") == "len" else -1
    q = float(p.get("quang", 0.8)) * bc.co * dau
    nh = float(p.get("nhoe", 0.25)) * bc.co
    for i in range(len(bc.phan)):
        u = pha(t, i * so_le, dai)
        if u <= 0:
            continue
        e = e_expo(u, 8)
        v = (1 - e) ** 1.5
        bc.ve_phan(cv, i, ox, oy, op=e_out(u * 1.6), dy=q * (1 - e), mo=0.01, mo_y=nh * v)
    return ra_np(s)


# ---------------------------------------------------------------- chữ mờ ảo ----
@dang_ky(id="mau.mo-ao", nhom="chu", ten="Chữ mờ ảo",
         mo_ta="chữ hiện từ nhoè sang nét (phóng nhẹ về đúng cỡ), tuỳ chọn nhoè dần khi ra — mơ hồ, ký ức, suy tư",
         hop_nghia=["mơ hồ", "ký ức", "suy nghĩ", "tâm sự", "giấc mơ"],
         tham_so=_ts(chu="cụm chữ", mo="độ nhoè ban đầu (em, 0.18)", dai_vao="giây rõ dần (0.6)", ra="true = nhoè dần lúc cuối",
                     dai_ra="giây nhoè ra (0.45)", tach="true = từng từ rõ dần so le", so_le="giây giữa 2 từ (0.12)", phong="tỉ lệ phóng lúc đầu (1.06)"),
         mac_dinh={"mo": 0.18, "dai_vao": 0.6, "ra": True, "dai_ra": 0.45, "tach": False, "so_le": 0.12, "phong": 1.06,
                   "font": "phu_de", "mau_chu": "sang", "bong": 0.4},
         hop=HOP_CHU, dong=True, sfx_goi_y=["ngân mơ hồ", "gió nhẹ"],
         vi_du={"chu": "Ký ức ngày xưa ấy", "tach": True})
def mo_ao(t, dur, W, H, c, p):
    kd = kieu_dang(c, p, "phu_de", "sang")
    ph = max(1.0, float(p.get("phong", 1.06)))
    bc = bo_chu(c, p.get("chu", ""), kd, W / ph, H / ph)
    s, cv = be_mat(W, H)
    ox, oy = bc.goc(W, H)
    mo = float(p.get("mo", 0.18)) * bc.co
    dv, dr = float(p.get("dai_vao", 0.6)), float(p.get("dai_ra", 0.45))
    ura = e_in_out(pha(t, dur - dr, dr)) if p.get("ra", True) else 0.0
    if p.get("tach"):
        sl = float(p.get("so_le", 0.12))
        for i in range(len(bc.phan)):
            u = e_out(pha(t, i * sl, dv))
            bc.ve_phan(cv, i, ox, oy, op=(0.15 + 0.85 * u) * (u > 0) * (1 - 0.7 * ura), sc=ph + (1 - ph) * u,
                       mo=mo * (1 - u) + mo * 0.8 * ura)
    else:
        u = e_out(pha(t, 0, dv))
        bc.ve_khoi(cv, ox, oy, op=(0.2 + 0.8 * u) * (1 - 0.7 * ura), sc=ph + (1 - ph) * u + 0.04 * ura,
                   mo=mo * (1 - u) + mo * 0.8 * ura)
    return ra_np(s)


# ---------------------------------------------------------------- chữ phát sáng ----
@dang_ky(id="mau.phat-sang", nhom="chu", ten="Chữ phát sáng (neon nhịp)",
         mo_ta="chữ hiện rồi bừng quầng sáng cùng tông, quầng thở theo nhịp — sáng, nổi bật, ý tưởng",
         hop_nghia=["sáng", "ý tưởng", "nổi bật", "neon", "hứng khởi"],
         tham_so=_ts(chu="cụm chữ", mau_sang="màu quầng (nhan)", cuong_do="độ mạnh quầng 0..2 (1)", ban_kinh="bán kính quầng (em, 0.22)",
                     nhip="nhịp thở quầng Hz (0.8; 0 = đứng yên)", bien_do="biên độ thở 0..1 (0.35)", tre="giây quầng bắt đầu bừng (0.1)",
                     loi="0..1 lõi chữ ngả trắng lúc bừng (0.3)"),
         mac_dinh={"mau_sang": "nhan", "cuong_do": 1.0, "ban_kinh": 0.22, "nhip": 0.8, "bien_do": 0.35, "tre": 0.1, "loi": 0.3,
                   "mau_chu": "sang", "font": "phu_de", "bong": 0},
         hop=HOP_CHU, dong=True, sfx_goi_y=["ánh sáng bừng", "ngân sáng"],
         vi_du={"chu": "Ý tưởng loé sáng"})
def phat_sang(t, dur, W, H, c, p):
    kd = kieu_dang(c, p, "phu_de", "sang")
    bk = float(p.get("ban_kinh", 0.22))
    bc = bo_chu(c, p.get("chu", ""), kd, W * (1 - bk * 0.5), H * (1 - bk))
    s, cv = be_mat(W, H)
    ox, oy = bc.goc(W, H)
    ua = e_out(pha(t, 0, 0.15))
    g = e_out(pha(t, float(p.get("tre", 0.1)), 0.4))
    f = float(p.get("nhip", 0.8))
    if f > 0:
        g *= 1 - float(p.get("bien_do", 0.35)) * (0.5 - 0.5 * math.cos(2 * math.pi * f * max(0, t - 0.5)))
    g *= float(p.get("cuong_do", 1.0))
    img, gx, gy = bc.anh_khoi()
    r = bk * bc.co
    for sig, a in ((r, 0.9), (r * 0.35, 0.8)):
        if g * a <= 0.01:
            continue
        im2, pad = to_mau(img, rgba(c, p.get("mau_sang"), "nhan"), round(sig))
        pt = skia.Paint(AntiAlias=True)
        pt.setAlphaf(kep(g * a * ua))
        cv.drawImage(im2, ox - gx - pad, oy - gy - pad, SAMP_NONE, pt)
    bc.ve_khoi(cv, ox, oy, op=ua)
    lo = float(p.get("loi", 0.3)) * kep(g)
    if lo > 0.01:
        im3, _ = to_mau(img, (255, 255, 255))
        pt = skia.Paint(AntiAlias=True)
        pt.setAlphaf(kep(lo * ua))
        cv.drawImage(im3, ox - gx, oy - gy, SAMP_NONE, pt)
    return ra_np(s)


# ---------------------------------------------------------------- giải mã ----
_KT_MA = "ABCDEFGHKLMNOPQRSTUVXY0123456789#$%&@*"


@dang_ky(id="mau.giai-ma", nhom="chu", ten="Chữ giải mã",
         mo_ta="từng ký tự nhảy ngẫu nhiên rồi chốt đúng chữ theo thứ tự (trái→phải, giữa ra, ngẫu nhiên), loé sáng khi chốt",
         hop_nghia=["bí mật", "tiết lộ", "công nghệ", "mã", "hack", "dữ liệu"],
         tham_so=_ts(chu="cụm chữ", dai="giây tới khi chốt hết (0.9)", tre="giây trước khi bắt đầu chốt (0.1)",
                     toc_doi="số lần đổi ký tự/giây (22)", huong="trai|phai|giua|ngau_nhien (trai)", bo_ky_tu="chuỗi ký tự ngẫu nhiên",
                     mau_ma="màu ký tự đang nhảy (nhan2)", chop="0..1 loé sáng khi chốt (0.7)", hat="số hạt ngẫu nhiên (1)"),
         mac_dinh={"dai": 0.9, "tre": 0.1, "toc_doi": 22, "huong": "trai", "bo_ky_tu": _KT_MA, "mau_ma": "nhan2", "chop": 0.7, "hat": 1,
                   "mau_chu": "nhan", "bong": 0.5},
         hop=HOP_CHU, dong=True, sfx_goi_y=["máy tính giải mã", "bíp dữ liệu", "gõ phím nhanh"],
         vi_du={"chu": "BÍ MẬT ĐƯỢC TIẾT LỘ"})
def giai_ma(t, dur, W, H, c, p):
    kd = kieu_dang(c, p, "tieu_de", "nhan")
    bc = bo_chu(c, p.get("chu", ""), kd, W, H, tach="ky_tu")
    n = len(bc.phan)
    if n == 0:
        return rong(W, H)
    s, cv = be_mat(W, H)
    ox, oy = bc.goc(W, H)
    rnd = random.Random(int(p.get("hat", 1)) * 7919 + n)
    huong = p.get("huong", "trai")
    if huong == "phai":
        hang = [(n - 1 - i) / max(1, n - 1) for i in range(n)]
    elif huong == "giua":
        hang = [abs(i - (n - 1) / 2) / max(1, (n - 1) / 2) for i in range(n)]
    elif huong in ("ngau_nhien", "ngau-nhien"):
        o = list(range(n)); rnd.shuffle(o)
        hang = [0.0] * n
        for k, i in enumerate(o):
            hang[i] = k / max(1, n - 1)
    else:
        hang = [i / max(1, n - 1) for i in range(n)]
    tre, dai = float(p.get("tre", 0.1)), float(p.get("dai", 0.9))
    td = float(p.get("toc_doi", 22))
    bo = str(p.get("bo_ky_tu") or _KT_MA)
    if not kd.get("hoa") and bc.text == bc.text.lower():
        bo = bo.lower()
    mm = c.mau(p.get("mau_ma", "nhan2"))
    chop = float(p.get("chop", 0.7))
    buoc = int(t * td)
    for i in range(n):
        tc = tre + dai * hang[i] + 0.04 * rnd.random()
        if t >= tc:
            bc.ve_phan(cv, i, ox, oy)
            if chop > 0:
                k = 1 - pha(t, tc, 0.14)
                if k > 0:
                    bc.ve_phan(cv, i, ox, oy, op=chop * k, sc=1 + 0.12 * k, mau="#FFFFFF")
        else:
            r2 = random.Random(i * 1009 + buoc * 31 + int(p.get("hat", 1)))
            ch = bo[r2.randrange(len(bo))]
            bc.ve_phan(cv, i, ox, oy, op=0.55 + 0.4 * r2.random(), mau=mm, txt=ch)
    return ra_np(s)


# ---------------------------------------------------------------- gõ máy ----
@dang_ky(id="mau.go-may", nhom="chu", ten="Gõ chữ + con trỏ",
         mo_ta="chữ gõ từng ký tự nhịp tay người (ngắt ở dấu cách/dấu câu), con trỏ nhấp nháy, tuỳ chọn ô nhập liệu bo tròn",
         hop_nghia=["gõ", "nhắn tin", "câu hỏi", "prompt", "tìm kiếm", "lệnh"],
         tham_so=_ts(chu="câu ngắn", toc="ký tự/giây (16)", ngau_nhien="0..1 độ lệch nhịp gõ (0.35)", tre="giây trước khi gõ (0.1)",
                     o_nen="true = ô nhập liệu", mau_o="màu ô (sang)", bo="bo góc ô (0..1 của chiều cao ô, 0.5)",
                     con_tro="thanh|gach|khoi|khong (thanh)", mau_con_tro="nhan", nhap_nhay="Hz (2)", nay_go="0..0.4 ký tự mới nảy (0.12)",
                     dem="đệm trong ô (em, [0.6, 0.35])"),
         mac_dinh={"toc": 16, "ngau_nhien": 0.35, "tre": 0.1, "o_nen": True, "mau_o": "sang", "bo": 0.5, "con_tro": "thanh",
                   "mau_con_tro": "nhan", "nhap_nhay": 2.0, "nay_go": 0.12, "dem": [0.6, 0.35], "font": "phu_de", "bong": 0},
         hop={"anchor": "mc", "x": 0.5, "y": 0.6, "w": 0.9, "h": 0.1}, dong=True,
         sfx_goi_y=["gõ phím", "bàn phím cơ"],
         vi_du={"chu": "Cách kiếm tiền online cho người mới?"})
def go_may(t, dur, W, H, c, p):
    o = bool(p.get("o_nen", True))
    dem = p.get("dem", [0.6, 0.35])
    if isinstance(dem, (int, float)):
        dem = [dem, dem]
    mau_chu = p.get("mau_chu") or (mau_tuong_phan(c, p.get("mau_o", "sang")) if o else "sang")
    kd = kieu_dang(c, dict(p, mau_chu=mau_chu), "phu_de", "sang")
    # ô chiếm cả hộp: chữ vừa phần trong (đệm theo cỡ → ước theo chiều cao)
    fx = 1.0 / (1 + 2 * float(dem[1])) if o else 1.0
    bc = bo_chu(c, p.get("chu", ""), kd, W - (2 * float(dem[0]) * H * fx * 0.9 if o else 0), H * fx, tach="ky_tu", co_hop=0.78)
    n = len(bc.phan)
    s, cv = be_mat(W, H)
    rnd = random.Random(n * 131 + 7)
    toc = max(1.0, float(p.get("toc", 16)))
    nn = float(p.get("ngau_nhien", 0.35))
    moc = []
    tt = float(p.get("tre", 0.1))
    for i in range(n):
        if i > 0 and bc.phan[i]["tu"] != bc.phan[i - 1]["tu"]:
            tt += 0.9 / toc
            if bc.phan[i - 1]["txt"] in ",.!?;:…":
                tt += 1.6 / toc
        moc.append(tt)
        tt += (1.0 / toc) * (1 + nn * (rnd.random() * 2 - 1))
    het = tt
    cao = bc.duoi - bc.tren
    ox, oy = bc.goc(W, H)
    if o:
        px, py = float(dem[0]) * bc.co, float(dem[1]) * bc.co
        bw = min(W - 2, bc.w + 2 * px + bc.co * 0.3)
        bh = min(H - 2, cao + 2 * py)
        x0, y0 = (W - bw) / 2, (H - bh) / 2
        bo = kep(float(p.get("bo", 0.5)), 0, 0.5) * bh
        ve = skia.Paint(AntiAlias=True)
        ve.setColor(mau_sk(c, p.get("mau_o"), "sang", 0.96))
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x0, y0, bw, bh), bo, bo), ve)
        ox = round(x0 + px)
    ng = float(p.get("nay_go", 0.12))
    cuoi = -1
    for i in range(n):
        if t >= moc[i]:
            k = 1 - pha(t, moc[i], 0.08)
            bc.ve_phan(cv, i, ox, oy, sc=1 + ng * k, chan=True)
            cuoi = i
    kieu = p.get("con_tro", "thanh")
    if kieu != "khong":
        dang_go = t < het + 0.15
        if dang_go or (int(t * float(p.get("nhap_nhay", 2.0)) * 2) % 2 == 0):
            if cuoi >= 0:
                q = bc.phan[cuoi]
                cx = ox + q["x"] + q["w"] + bc.co * 0.06
                ly = q["y"]
            else:
                q = bc.phan[0] if n else {"x": 0, "y": 0}
                cx = ox + q["x"]
                ly = q["y"]
            yb = oy + ly + bc.base
            pt = skia.Paint(AntiAlias=True)
            pt.setColor(mau_sk(c, p.get("mau_con_tro"), "nhan"))
            if kieu == "gach":
                r = skia.Rect.MakeXYWH(cx, yb + bc.co * 0.06, bc.co * 0.5, bc.co * 0.08)
            elif kieu == "khoi":
                r = skia.Rect.MakeXYWH(cx, yb - bc.co * 0.74, bc.co * 0.5, bc.co * 0.9)
                pt.setAlphaf(0.75)
            else:
                r = skia.Rect.MakeXYWH(cx, yb - bc.co * 0.78, max(2.0, bc.co * 0.07), bc.co * 0.98)
            cv.drawRect(r, pt)
    return ra_np(s, bong=(H * 0.03, H * 0.06, 0.35) if o else None)


# ---------------------------------------------------------------- viết tay ----
def _ve_viet(cv, bc, ox, oy, t, t0, toc_px, mem, goc, mau=None):
    """viết lộ dần từng ký tự theo nét (mép bút mềm nghiêng); trả (đã xong?, x mép bút, y)"""
    tong = 0.0
    xong = True
    vt = None
    for i, q in enumerate(bc.phan):
        dai_k = (q["w"] + mem) / toc_px
        if i > 0 and q["tu"] != bc.phan[i - 1]["tu"]:
            tong += 0.35 * bc.co / toc_px
        bat = t0 + tong
        tong += dai_k * 0.92
        u = pha(t, bat, dai_k)
        if u <= 0:
            xong = False
            continue
        img, gx, gy, _ = bc.sprite(q["txt"], mau)
        x = ox + q["x"] - gx
        y = oy + q["y"] - gy
        if u >= 1:
            cv.drawImage(img, round(x), round(y), SAMP_NONE, None)
            continue
        xong = False
        e = ox + q["x"] - mem * 0.3 + (q["w"] + mem * 1.3) * e_in_out(u) * 0.98 + mem * 0.02
        ve_lo(cv, img, round(x), round(y), e, mem, goc=goc, cy=oy + q["y"] + bc.base - bc.co * 0.35)
        vt = (e, oy + q["y"] + bc.base - bc.co * 0.3)
    return xong, vt, t0 + tong


def _elip_tay(x0, y0, x1, y1, hat=1, vong=1.12, run=0.035, bat=-2.2):
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    rnd = random.Random(hat)
    n = 64
    ph = rnd.uniform(0, 6.28)
    pts = []
    for k in range(n + 1):
        a = bat + 2 * math.pi * vong * k / n
        j = 1 + run * math.sin(k * 0.21 + ph) + run * 0.4 * math.sin(k * 0.53 + ph * 2) + (k / n) * run * 1.2
        pts.append((cx + rx * j * math.cos(a), cy + ry * j * math.sin(a)))
    return pts


@dang_ky(id="mau.viet-tay", nhom="chu", ten="Viết tay hiện dần",
         mo_ta="chữ viết tay lộ dần theo nét bút (mép mực mềm, nghiêng) từng ký tự trái→phải, tuỳ chọn gạch chân/khoanh sau khi viết",
         hop_nghia=["ghi chú", "viết tay", "cá nhân", "ý tưởng", "chữ ký", "nhật ký"],
         tham_so=_ts(chu="cụm ngắn", toc="tốc độ bút (em/giây, 5.5)", tre="giây trước khi viết (0.05)", mem="độ mềm mép mực (em, 0.35)",
                     goc_but="độ nghiêng mép bút (độ, 18)", them="gach|khoanh|khong (khong)", mau_net="màu nét thêm (nhan)",
                     day_net="dày nét thêm (em, 0.07)"),
         mac_dinh={"toc": 5.5, "tre": 0.05, "mem": 0.35, "goc_but": 18, "them": "khong", "mau_net": "nhan", "day_net": 0.07,
                   "font": "script", "mau_chu": "sang", "bong": 0.45, "dam": 700},
         hop=HOP_CHU, dong=True, sfx_goi_y=["bút viết trên giấy", "bút dạ"],
         vi_du={"chu": "Ghi nhớ điều này nhé", "them": "gach"})
def viet_tay(t, dur, W, H, c, p):
    them = p.get("them", "khong")
    kd = kieu_dang(c, p, "script", "sang", dam=700)
    fh = 0.8 if them == "khoanh" else 0.88
    bc = bo_chu(c, p.get("chu", ""), kd, W * (0.86 if them == "khoanh" else 1.0), H * fh, tach="ky_tu")
    s, cv = be_mat(W, H)
    ox, oy = bc.goc(W, H, ay=0.45 if them == "gach" else 0.5)
    toc_px = float(p.get("toc", 5.5)) * bc.co
    mem = float(p.get("mem", 0.35)) * bc.co
    xong, vt, t_het = _ve_viet(cv, bc, ox, oy, t, float(p.get("tre", 0.05)), toc_px, mem, float(p.get("goc_but", 18)))
    if them in ("gach", "khoanh"):
        u = e_in_out(pha(t, t_het, 0.4))
        if u > 0:
            day = max(2.0, float(p.get("day_net", 0.07)) * bc.co)
            if them == "gach":
                yb = oy + (len(bc.dong) - 1) * bc.cao_dong + bc.base + bc.muc_duoi * 0.55 + day
                x0, x1 = ox - bc.co * 0.1, ox + bc.w + bc.co * 0.1
                pts = [(x0 + (x1 - x0) * k / 24, yb + day * 0.6 * math.sin(k * 0.55) - (k / 24) * day * 0.8) for k in range(25)]
            else:
                pts = _elip_tay(ox - bc.co * 0.3, oy + bc.tren - bc.co * 0.15, ox + bc.w + bc.co * 0.3, oy + bc.duoi + bc.co * 0.1, hat=3)
            d, _, _ = cat_duong(duong_muot(pts), u)
            pt = but_net(mau_sk(c, p.get("mau_net"), "nhan"), day)
            cv.drawPath(d, pt)
    return ra_np(s)


# ---------------------------------------------------------------- xếp lớp ----
@dang_ky(id="mau.xep-lop", nhom="chu", ten="Chữ xếp lớp (sans + viết tay)",
         mo_ta="từ khoá sans đậm to bật vào + một từ viết tay nghiêng màu nhấn được 'viết' đè chéo lên — kiểu tiêu đề kênh có gu",
         hop_nghia=["tiêu đề", "ý chính", "lời hứa", "kết quả", "phong cách"],
         tham_so=_ts(chu="từ khoá chính (1–3 từ)", viet="từ viết tay (1–2 từ)", mau_viet="màu từ viết tay (nhan)", goc="độ nghiêng từ viết tay (−8)",
                     lech="lệch ngang từ viết tay −1..1 (0.3)", tren="true = từ viết tay đè phía trên", co_viet="tỉ lệ cỡ từ viết tay (1.0)",
                     font_viet="font từ viết tay (script)", tre="giây bắt đầu viết (0.18)", dai_viet="giây viết (0.5)"),
         mac_dinh={"mau_chu": "sang", "mau_viet": "nhan", "goc": -8, "lech": 0.3, "tren": False, "co_viet": 1.0, "font_viet": "script",
                   "tre": 0.18, "dai_viet": 0.5, "hoa": True, "bong": 0.55},
         hop={"anchor": "mc", "x": 0.5, "y": 0.5, "w": 0.92, "h": 0.28}, dong=True,
         sfx_goi_y=["bật pop", "bút viết nhanh"],
         vi_du={"chu": "kiếm tiền", "viet": "dễ thôi"})
def xep_lop(t, dur, W, H, c, p):
    kd = kieu_dang(c, p, "tieu_de", "sang", gian=-0.02)
    tren = bool(p.get("tren"))
    b1 = bo_chu(c, p.get("chu", ""), kd, W * 0.94, H * 0.56)
    s, cv = be_mat(W, H)
    cao1 = b1.duoi - b1.tren
    ox, _ = b1.goc(W, H)
    oy = round((H - cao1) / 2 - b1.tren + (cao1 * 0.18 if tren else -cao1 * 0.14))
    u1 = pha(t, 0, 0.3)
    b1.ve_khoi(cv, ox, oy, op=e_out(pha(t, 0, 0.12)), sc=0.8 + 0.2 * e_back(u1, 1.8) if u1 < 1 else 1.0)
    viet = chuoi(p.get("viet"))
    if viet:
        kv = kieu_dang(c, {"mau_chu": p.get("mau_viet", "nhan"), "font": p.get("font_viet", "script"), "bong": p.get("bong", 0.55),
                           "kieu_dang": p.get("kieu_dang_viet")}, "script", "nhan", dam=700)
        cao_dong1 = b1.cao_dong
        b2 = bo_chu(c, viet, kv, W * 0.86, H * 0.5, tach="ky_tu",
                    co_toi_da=b1.co * 1.6 * float(p.get("co_viet", 1.0)))
        cy1 = oy + (b1.tren + b1.duoi) / 2
        cy = cy1 + (-1 if tren else 1) * cao1 * 0.42
        cx = W / 2 + float(p.get("lech", 0.3)) * b1.w * 0.5
        cao2 = b2.duoi - b2.tren
        cx = kep(cx, b2.w / 2 + 2, W - b2.w / 2 - 2)
        cy = kep(cy, cao2 / 2 + 2, H - cao2 / 2 - 2)
        pad = int(b2.co * 0.5)
        s2, cv2_ = be_mat(b2.w + 2 * pad, cao2 + 2 * pad)
        dv = float(p.get("dai_viet", 0.5))
        tong_w = sum(q["w"] for q in b2.phan) + 1
        _ve_viet(cv2_, b2, pad, round(pad - b2.tren), t, float(p.get("tre", 0.18)), tong_w / max(0.05, dv), 0.3 * b2.co, 18)
        ve_xoay(cv, s2.makeImageSnapshot(), cx, cy, float(p.get("goc", -8)))
    return ra_np(s)


# ---------------------------------------------------------------- chữ 3D ----
_KHOI3D = _chu.CacheAnh("mau.chu._KHOI3D")


def _dun_khoi(c, bc, mat, ben, toi, sau_px, goc_dun):
    """khối đùn 3D (numpy, dựng 1 lần/cache): thành bên = các lớp alpha lệch dần theo hướng đùn, màu từ `toi` (xa) → `ben` (gần)"""
    k = (bc._kd_js, bc.text, mat, ben, toi, round(sau_px, 1), round(goc_dun, 1), round(bc.rm, 1))
    r = _KHOI3D.get(k)
    if r is not None:
        return r
    img, gx, gy = bc.anh_khoi()
    a = math.radians(goc_dun)
    dx, dy = math.cos(a), math.sin(a)
    pad = int(math.ceil(sau_px)) + 4
    mat_ = cv2.copyMakeBorder(np_premul(img), pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=0).astype(np.float32) / 255.0
    A = mat_[..., 3]
    h, w = A.shape
    out = np.zeros((h, w, 4), np.float32)
    n = max(2, int(math.ceil(sau_px)))
    cb, ct = _chu.mau(ben), _chu.mau(toi)
    for k_ in range(n, 0, -1):
        f = k_ / n
        col = [tron(cb[j], ct[j], f ** 0.8) / 255.0 for j in range(3)]
        sh = cv2.warpAffine(A, np.float32([[1, 0, dx * k_ * sau_px / n], [0, 1, dy * k_ * sau_px / n]]), (w, h))
        inv = 1 - sh
        out[..., 3] = sh + out[..., 3] * inv
        for ch, v in zip((0, 1, 2), (col[2], col[1], col[0])):
            out[..., ch] = sh * v + out[..., ch] * inv
    inv = 1 - mat_[..., 3:4]
    out = mat_ + out * inv
    arr = np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8)
    r = (sk_premul(arr), pad + gx, pad + gy, arr)
    _KHOI3D[k] = r
    return r


@dang_ky(id="mau.chu-3d", nhom="chu", ten="Chữ khối 3D xoay phối cảnh",
         mo_ta="chữ thành khối đùn 3D (mặt + thành bên tối dần) xoay phối cảnh vung vào rồi đứng nghiêng — từ có lực, tên chiêu, con số",
         hop_nghia=["mạnh", "kết quả", "con số", "tên chiêu", "ấn tượng"],
         tham_so=_ts(chu="1–2 từ", mau_mat="màu mặt chữ (nhan)", mau_ben="màu thành gần mặt (tự = mặt tối 55%)", mau_sau="màu thành xa (tự = mặt tối 25%)",
                     do_sau="độ sâu khối (em, 0.16)", goc_dun="hướng đùn (độ, 50 = xuống-phải)", goc="góc xoay Y cuối (độ, 16)",
                     goc_vao="góc xoay Y lúc vào (độ, 55)", nghieng="xoay mặt phẳng (độ, −4)", dai="giây vung vào (0.5)", tieu_cu="tiêu cự (× rộng chữ, 1.6)",
                     phong_vao="tỉ lệ cỡ lúc bắt đầu vung vào so với cỡ đứng (1 = không phóng; 0.75 = nhỏ hơn rồi lớn dần)",
                     tho="biên độ thở khi đứng (độ, 0 = đứng yên)"),
         mac_dinh={"mau_mat": "nhan", "do_sau": 0.16, "goc_dun": 50, "goc": 16, "goc_vao": 55, "nghieng": -4, "dai": 0.5, "tieu_cu": 1.6,
                   "hoa": True, "bong": 0, "vien": 0, "phong_vao": 1.0, "tho": 0, "le_ngang": 0, "le_doc": 0},
         hop={"anchor": "mc", "x": 0.5, "y": 0.5, "w": 0.92, "h": 0.26}, dong=True,
         sfx_goi_y=["whoosh nặng", "đập trầm"],
         vi_du={"chu": "SIÊU TỐC"})
def chu_3d(t, dur, W, H, c, p):
    mat = c.mau(p.get("mau_mat") or p.get("mau_chu") or "nhan")
    kd = kieu_dang(c, dict(p, mau_chu=mat), "tieu_de", mat)
    ds = float(p.get("do_sau", 0.16))
    # 1.2.21: hộp chữ = CẢ hộp mẫu trừ phần đùn khối (ds·co chiếm thêm chiều cao — vật lý); lề thêm là tham số le_ngang/le_doc (bo_chu đọc c.p)
    bc = bo_chu(c, p.get("chu", ""), kd, W, H / (1 + ds))
    ben = c.mau(p["mau_ben"]) if p.get("mau_ben") else toi_di(c, mat, 0.55)
    toi = c.mau(p["mau_sau"]) if p.get("mau_sau") else toi_di(c, mat, 0.22)
    img, gx, gy, arr = _dun_khoi(c, bc, mat, ben, toi, ds * bc.co, float(p.get("goc_dun", 50)))
    dai = float(p.get("dai", 0.5))
    u = pha(t, 0, dai)
    g_cuoi, g_vao = float(p.get("goc", 16)), float(p.get("goc_vao", 55))
    goc = g_cuoi + (g_vao - g_cuoi) * (1 - e_back(u, 1.4)) if u < 1 else g_cuoi
    goc += float(p.get("tho", 0) or 0) * math.sin(max(0, t - dai) * 1.3)      # thở khi đứng: biên độ là tham số (0 = không)
    pv = float(p.get("phong_vao", 1.0) or 1.0)
    sc = pv + (1.0 - pv) * e_out(u)
    iw, ih = img.width(), img.height()
    # khối chữ (gốc gx,gy) → tâm mặt chữ
    fx, fy = gx + bc.w / 2, gy + (bc.tren + bc.duoi) / 2
    th = math.radians(goc)
    f = float(p.get("tieu_cu", 1.6)) * bc.w
    def chieu(x, y):
        X, Y = x - fx, y - fy
        xr, z = X * math.cos(th), X * math.sin(th)
        k = f / (f + z)
        return skia.Point(W / 2 + xr * k * sc, H / 2 + Y * k * sc)
    ng = math.radians(float(p.get("nghieng", -4)) * e_out(u))
    def xoay(q):
        dx, dy = q.fX - W / 2, q.fY - H / 2
        return [W / 2 + dx * math.cos(ng) - dy * math.sin(ng), H / 2 + dx * math.sin(ng) + dy * math.cos(ng)]
    src = np.float32([[0, 0], [iw, 0], [iw, ih], [0, ih]])
    dst = np.float32([xoay(chieu(0, 0)), xoay(chieu(iw, 0)), xoay(chieu(iw, ih)), xoay(chieu(0, ih))])
    out = cv2.warpPerspective(arr, cv2.getPerspectiveTransform(src, dst), (W, H), flags=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    op = e_out(pha(t, 0, 0.12))
    if op < 0.999:
        out = (out.astype(np.float32) * op).astype(np.uint8)
    out = bong_np(out, bc.co * 0.08, bc.co * 0.12, 0.45)
    return unpremul_rgba(out)


# ---------------------------------------------------------------- phụ đề chạy ----
def _cum_tu(tus, toi_da):
    cum, hien = [], []
    for i, w in enumerate(tus):
        hien.append(i)
        if len(hien) >= toi_da or w[-1:] in ".,!?…;:":
            cum.append(hien); hien = []
    if hien:
        cum.append(hien)
    return cum


@dang_ky(id="mau.phu-de-chay", nhom="chu", ten="Phụ đề chạy karaoke",
         mo_ta="phụ đề bám lời theo cụm ≤ N từ, từ đang nói đổi màu + nảy nhẹ; cùng một cỡ cho mọi cụm",
         hop_nghia=["phụ đề", "lời thoại", "karaoke", "câu nói"],
         tham_so=_ts(chu="cả câu/đoạn lời", moc="list giây bắt đầu từng từ (từ lời Whisper) — bỏ trống = đều theo nhip",
                     nhip="giây/từ khi không có moc (0.32)", toi_da_tu="số từ tối đa mỗi cụm (4)", mau_noi="màu từ đang nói (nhan)",
                     nay="tỉ lệ nảy từ đang nói (1.1)", hien_dan="true = từ chỉ hiện khi tới lượt", nen="màu pill nền sau cụm (null = không)"),
         mac_dinh={"nhip": 0.32, "toi_da_tu": 4, "mau_noi": "nhan", "nay": 1.1, "hien_dan": False, "nen": None, "font": "phu_de",
                   "mau_chu": "sang", "vien": 0.06, "bong": 0.5, "hoa": False},
         hop={"anchor": "mc", "x": 0.5, "y": 0.74, "w": 0.88, "h": 0.12}, dong=True,
         sfx_goi_y=[],
         vi_du={"chu": "Hôm nay mình sẽ chỉ bạn cách dựng video thật nhanh và đẹp", "nhip": 0.25})
def phu_de_chay(t, dur, W, H, c, p):
    kd = kieu_dang(c, p, "phu_de", "sang")
    tus = chuoi(p.get("chu")).split()
    if not tus:
        return rong(W, H)
    moc = moc_tu(p, len(tus), 0.32)
    cums = _cum_tu(tus, max(1, int(p.get("toi_da_tu", 4))))
    # một cỡ chung = cỡ nhỏ nhất trong các cụm
    nay = max(1.0, float(p.get("nay", 1.1)))
    if not kd.get("co"):
        co = min(bo_chu(c, " ".join(tus[i] for i in cm), kd, W / nay, H * 0.9).co for cm in cums)
        kd = dict(kd, co=round(co, 1))
    k = 0
    for j, cm in enumerate(cums):
        if t >= moc[cm[0]]:
            k = j
    cm = cums[k]
    bc = bo_chu(c, " ".join(tus[i] for i in cm), kd, W / nay, H * 0.9)
    s, cv = be_mat(W, H)
    ox, oy = bc.goc(W, H)
    if p.get("nen"):
        r = skia.Rect.MakeLTRB(ox - bc.co * 0.35, oy + bc.tren - bc.co * 0.12, ox + bc.w + bc.co * 0.35, oy + bc.duoi + bc.co * 0.12)
        pt = skia.Paint(AntiAlias=True); pt.setColor(mau_sk(c, p.get("nen"), "toi", 0.85))
        cv.drawRRect(skia.RRect.MakeRectXY(r, bc.co * 0.3, bc.co * 0.3), pt)
    mn = c.mau(p.get("mau_noi", "nhan"))
    hien_dan = bool(p.get("hien_dan"))
    for a, i in enumerate(cm):
        if a >= len(bc.phan):
            break
        bd = moc[i]
        kt = moc[i + 1] if i + 1 < len(moc) else bd + float(p.get("nhip", 0.32))
        if hien_dan and t < bd:
            continue
        dang = bd <= t < kt or (i == cm[-1] and t >= bd)
        u = pha(t, bd, 0.18)
        sc = 1 + (nay - 1) * math.sin(math.pi * u) if dang and u < 1 else 1.0
        bc.ve_phan(cv, a, ox, oy, mau=mn if dang else None, sc=sc, chan=True, op=e_out(pha(t, bd, 0.08)) if hien_dan else 1.0)
    return ra_np(s)


# ---------------------------------------------------------------- chữ sau người ----
@dang_ky(id="mau.sau-nguoi", nhom="chu", ten="Chữ to sau người",
         mo_ta="chữ rất to nằm SAU người nói (người đè lên chữ) — chiều sâu kiểu bìa tạp chí; cần engine cấp mặt nạ người, thiếu thì vẽ như chữ thường",
         hop_nghia=["chủ đề", "tên", "tiêu đề lớn", "cao cấp", "tạp chí"],
         tham_so=_ts(chu="1–2 từ ngắn (đọc được dù bị che một phần)", do_dac="0..1 độ đục chữ (0.92)", dai="giây trồi lên (0.45)",
                     quang="quãng trồi (em, 0.25)"),
         mac_dinh={"do_dac": 0.92, "dai": 0.45, "quang": 0.25, "mau_chu": "sang", "hoa": True, "bong": 0, "gian": -0.03},
         hop={"anchor": "mc", "x": 0.5, "y": 0.3, "w": 0.96, "h": 0.3}, dong=True, lam_nen=True,
         sfx_goi_y=["trầm cinematic", "whoosh chậm"],
         vi_du={"chu": "ĐAM MÊ"})
def sau_nguoi(t, dur, W, H, c, p):
    kd = kieu_dang(c, p, "tieu_de", "sang")
    bc = bo_chu(c, p.get("chu", ""), kd, W, H)
    s, cv = be_mat(W, H)
    u = e_out(pha(t, 0, float(p.get("dai", 0.45))))
    ox, oy = bc.goc(W, H, dy=(1 - u) * float(p.get("quang", 0.25)) * bc.co)
    bc.ve_khoi(cv, ox, oy, op=u * float(p.get("do_dac", 0.92)))
    a = ra_np(s)
    m = alpha_nguoi(c, t, W, H)
    if m is not None:
        a[..., 3] = (a[..., 3].astype(np.float32) * (1 - np.clip(m, 0, 1))).astype(np.uint8)
    return a


# ============================================================================ MẪU CHỮ MỚI ====

@dang_ky(id="mau.nay-tung-chu", nhom="chu", ten="Nảy từng chữ cái (lò xo)",
         mo_ta="từng chữ cái rơi/bật vào bằng lò xo (phóng từ 0, vượt đích rồi tắt dần), so le trái→phải, nghiêng nhẹ ngẫu nhiên",
         hop_nghia=["vui", "năng động", "bất ngờ", "trẻ trung", "tiêu đề"],
         tham_so=_ts(chu="cụm ngắn", so_le="giây giữa 2 chữ cái (0.035)", dai="giây mỗi chữ (0.6)", tat="độ tắt lò xo (5.5)",
                     tan="số dao động (1.6)", nang="độ rơi (em, 0.6; âm = bật từ dưới)", xoay="nghiêng ngẫu nhiên ban đầu (độ, 18)",
                     tach="ky_tu|tu (ky_tu)"),
         mac_dinh={"so_le": 0.035, "dai": 0.6, "tat": 5.5, "tan": 1.6, "nang": 0.6, "xoay": 18, "tach": "ky_tu", "mau_chu": "nhan", "bong": 0.55},
         hop=HOP_CHU, dong=True, sfx_goi_y=["pop liên tiếp", "boing lò xo"],
         vi_du={"chu": "Quá đỉnh luôn!"})
def nay_tung_chu(t, dur, W, H, c, p):
    kd = kieu_dang(c, p, "tieu_de", "nhan")
    tach = "tu" if p.get("tach") == "tu" else "ky_tu"
    bc = bo_chu(c, p.get("chu", ""), kd, W / 1.08, H / 1.25, tach=tach)
    s, cv = be_mat(W, H)
    ox, oy = bc.goc(W, H)
    sl, dai = float(p.get("so_le", 0.035)), float(p.get("dai", 0.6))
    tat, tan = float(p.get("tat", 5.5)), float(p.get("tan", 1.6))
    nang = float(p.get("nang", 0.6)) * bc.co
    xo = float(p.get("xoay", 18))
    rnd = random.Random(len(bc.phan) * 17 + 3)
    for i in range(len(bc.phan)):
        r0 = rnd.uniform(-1, 1) * xo
        u = pha(t, i * sl, dai)
        if u <= 0:
            continue
        e = lo_xo(u, tat, tan)
        bc.ve_phan(cv, i, ox, oy, op=e_out(u * 4), sc=max(0.0, e), dy=-nang * (1 - e_out(u, 4)), rot=r0 * (1 - e), chan=True)
    return ra_np(s)


@dang_ky(id="mau.truot-mask-dong", nhom="chu", ten="Trượt lên từ mask từng dòng",
         mo_ta="mỗi dòng trồi lên từ sau một khe che vô hình (mask) so le dòng — kiểu tiêu đề quảng cáo/Apple; tuỳ chọn so le cả từng từ",
         hop_nghia=["tiêu đề", "giới thiệu", "sang trọng", "thông báo", "trích dẫn"],
         tham_so=_ts(chu="1–3 dòng (\\n để xuống dòng)", so_le_dong="giây giữa 2 dòng (0.12)", so_le_tu="giây giữa 2 từ trong dòng (0.04)",
                     dai="giây mỗi dòng (0.6)", huong="len|xuong (len)", ra="true = trượt ra tiếp lúc cuối", dai_ra="giây ra (0.4)"),
         mac_dinh={"so_le_dong": 0.12, "so_le_tu": 0.04, "dai": 0.6, "huong": "len", "ra": False, "dai_ra": 0.4, "mau_chu": "sang", "bong": 0.3},
         hop={"anchor": "mc", "x": 0.5, "y": 0.5, "w": 0.9, "h": 0.3}, dong=True,
         sfx_goi_y=["whoosh mềm", "trượt nhẹ"],
         vi_du={"chu": "Ra mắt sản phẩm\nphiên bản mới nhất"})
def truot_mask_dong(t, dur, W, H, c, p):
    kd = kieu_dang(c, p, "tieu_de", "sang")
    bc = bo_chu(c, chuoi(p.get("chu")), kd, W, H)
    s, cv = be_mat(W, H)
    ox, oy = bc.goc(W, H)
    sld, slt, dai = float(p.get("so_le_dong", 0.12)), float(p.get("so_le_tu", 0.04)), float(p.get("dai", 0.6))
    dau = 1 if p.get("huong", "len") == "len" else -1
    dr = float(p.get("dai_ra", 0.4))
    ra = p.get("ra")
    tren = bc.base + bc.muc_tren - bc.co * 0.08
    duoi = bc.base + bc.muc_duoi + bc.co * 0.06
    cao_khe = duoi - tren
    for li, d in enumerate(bc.dong):
        y = oy + d["y"]
        cv.save()
        cv.clipRect(skia.Rect.MakeLTRB(0, y + tren, W, y + duoi), skia.ClipOp.kIntersect, True)
        for k, tu in enumerate(d["tu"]):
            u = e_expo(pha(t, li * sld + k * slt, dai), 9)
            v = e_in_out(pha(t, dur - dr + li * sld * 0.5, dr)) if ra else 0.0
            dy = dau * (cao_khe * (1 - u) - cao_khe * v)
            if u <= 0:
                continue
            bc.ve_phan(cv, tu["i"], ox, oy, dy=dy)
        cv.restore()
    return ra_np(s)


@dang_ky(id="mau.karaoke-nen", nhom="chu", ten="Karaoke nền chạy",
         mo_ta="cả câu hiện sẵn, một khối màu bo tròn TRƯỢT từ từ này sang từ kia đúng nhịp nói, từ đang nói đổi màu tương phản",
         hop_nghia=["karaoke", "phụ đề nổi bật", "nhấn từng từ", "đọc theo", "lời bài hát"],
         tham_so=_ts(chu="câu (≤ 10 từ)", moc="list giây từng từ (từ lời) — bỏ trống = đều theo nhip", nhip="giây/từ (0.32)",
                     mau_nen="màu khối chạy (nhan)", mau_noi="màu chữ trên khối (tự tương phản)", chuyen="giây khối trượt (0.12)",
                     bo="bo góc khối (em, 0.18)", dem="đệm khối (em, [0.14, 0.06])", mo_chua="độ đục từ chưa nói (0.85)", xoay="nghiêng khối (độ, 0)"),
         mac_dinh={"nhip": 0.32, "mau_nen": "nhan", "chuyen": 0.12, "bo": 0.18, "dem": [0.14, 0.06], "mo_chua": 0.85, "xoay": 0,
                   "mau_chu": "sang", "font": "phu_de", "bong": 0.5},
         hop={"anchor": "mc", "x": 0.5, "y": 0.7, "w": 0.9, "h": 0.16}, dong=True,
         sfx_goi_y=["tick nhịp", "pop nhỏ"],
         vi_du={"chu": "Học một lần dùng cả đời", "nhip": 0.4})
def karaoke_nen(t, dur, W, H, c, p):
    kd = kieu_dang(c, p, "phu_de", "sang")
    dem = p.get("dem", [0.14, 0.06])
    if isinstance(dem, (int, float)):
        dem = [dem, dem]
    bc = bo_chu(c, p.get("chu", ""), kd, W / (1 + 2 * float(dem[0]) * 0.3), H / (1 + 2 * float(dem[1]) + 0.1))
    n = len(bc.tu)
    if not n:
        return rong(W, H)
    s, cv = be_mat(W, H)
    ox, oy = bc.goc(W, H)
    moc = moc_tu(p, n, 0.32)
    k = -1
    for i in range(n):
        if t >= moc[i]:
            k = i
    dx, dy = float(dem[0]) * bc.co, float(dem[1]) * bc.co
    def hop(i):
        x0, y0, x1, y1 = bc.hop_phan(i, ox, oy)
        y0 = oy + bc.tu[i]["y"] + bc.base - bc.co * 0.78
        y1 = oy + bc.tu[i]["y"] + bc.base + bc.co * 0.24
        return (x0 - dx, y0 - dy, x1 + dx, y1 + dy)
    if k >= 0:
        u = e_out(pha(t, moc[k], float(p.get("chuyen", 0.12))), 4)
        h1 = hop(k)
        h0 = hop(k - 1) if k > 0 else (h1[0] + (h1[2] - h1[0]) / 2, h1[1], h1[0] + (h1[2] - h1[0]) / 2, h1[3])
        r = [tron(a, b, u) for a, b in zip(h0, h1)]
        sc = 1 + 0.08 * math.sin(math.pi * u)
        cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        cv.save()
        cv.translate(cx, cy); cv.rotate(float(p.get("xoay", 0))); cv.scale(sc, sc); cv.translate(-cx, -cy)
        pt = skia.Paint(AntiAlias=True)
        pt.setColor(mau_sk(c, p.get("mau_nen"), "nhan"))
        bo = float(p.get("bo", 0.18)) * bc.co
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(*r), bo, bo), pt)
        cv.restore()
    mn = c.mau(p.get("mau_noi") or mau_tuong_phan(c, p.get("mau_nen", "nhan")))
    mc = float(p.get("mo_chua", 0.85))
    for i in range(n):
        bc.ve_phan(cv, i, ox, oy, mau=mn if i == k else None, op=1.0 if i <= k else mc)
    return ra_np(s)


@dang_ky(id="mau.rung-nhan", nhom="chu", ten="Chữ rung lắc nhấn",
         mo_ta="chữ đập vào (phóng to → vừa) rồi từng ký tự rung lắc ngẫu nhiên tắt dần — sốc, tức giận, cảnh báo, hài",
         hop_nghia=["sốc", "bất ngờ", "cảnh báo", "tức giận", "hài hước", "mạnh"],
         tham_so=_ts(chu="cụm ngắn", dap="tỉ lệ lúc đập vào (1.35)", dai_vao="giây đập (0.18)", bien_do="biên độ rung (em, 0.05)",
                     xoay="biên độ nghiêng (độ, 5)", tan_so="Hz rung (14)", tat="độ tắt dần (3; 0 = rung mãi)", lien_tuc="true = rung suốt"),
         mac_dinh={"dap": 1.35, "dai_vao": 0.18, "bien_do": 0.05, "xoay": 5, "tan_so": 14, "tat": 3.0, "lien_tuc": False,
                   "mau_chu": "nhan", "hoa": True, "bong": 0.6, "vien": 0},
         hop=HOP_CHU, dong=True, sfx_goi_y=["đập mạnh", "rung bần bật"],
         vi_du={"chu": "SAI LẦM CHẾT NGƯỜI"})
def rung_nhan(t, dur, W, H, c, p):
    kd = kieu_dang(c, p, "tieu_de", "nhan")
    bd = float(p.get("bien_do", 0.05))
    bc = bo_chu(c, p.get("chu", ""), kd, W / (1 + 4 * bd), H / (1 + 4 * bd), tach="ky_tu")
    s, cv = be_mat(W, H)
    ox, oy = bc.goc(W, H)
    dv = float(p.get("dai_vao", 0.18))
    u = pha(t, 0, dv)
    dap = max(1.0, float(p.get("dap", 1.35)))
    nay_eff = min(dap, W / max(bc.w, 1))
    sc_k = nay_eff + (1 - nay_eff) * e_out(u, 4)
    A = bd * bc.co
    if not p.get("lien_tuc") and float(p.get("tat", 3)) > 0:
        A *= math.exp(-float(p.get("tat", 3)) * max(0.0, t - dv)) if t > dv else 1.0
    f = float(p.get("tan_so", 14))
    xo = float(p.get("xoay", 5))
    rnd = random.Random(len(bc.phan) * 7 + 1)
    cxk, cyk = ox + bc.w / 2, oy + (bc.tren + bc.duoi) / 2
    cv.save()
    if sc_k != 1:
        cv.translate(cxk, cyk); cv.scale(sc_k, sc_k); cv.translate(-cxk, -cyk)
    for i in range(len(bc.phan)):
        ph = [rnd.uniform(0, 6.283) for _ in range(4)]
        w = 2 * math.pi * f * t
        nx = 0.6 * math.sin(w + ph[0]) + 0.4 * math.sin(1.7 * w + ph[1])
        ny = 0.6 * math.sin(1.3 * w + ph[2]) + 0.4 * math.sin(2.1 * w + ph[3])
        bc.ve_phan(cv, i, ox, oy, dx=A * nx, dy=A * ny, rot=xo * (A / max(bd * bc.co, 1e-6)) * nx * 0.8 if A > 0.05 else 0.0,
                   op=e_out(pha(t, 0, dv * 0.5)))
    cv.restore()
    return ra_np(s)


@dang_ky(id="mau.zoom-mo", nhom="chu", ten="Chữ phóng to dần + nhoè phóng",
         mo_ta="chữ lao tới từ rất to (nhoè phóng xuyên tâm, vệt mờ) rồi chốt nét, sau đó đẩy nhẹ to dần; tuỳ chọn lao qua camera khi ra",
         hop_nghia=["ấn tượng", "điện ảnh", "tiêu đề", "mạnh", "bùng nổ"],
         tham_so=_ts(chu="cụm ngắn", tu="tỉ lệ lúc bắt đầu (1.8; <1 = từ nhỏ phóng ra)", dai="giây chốt (0.45)", mo="độ nhoè ban đầu (em, 0.12)",
                     vet="số vệt nhoè phóng (5)", troi="phóng thêm khi giữ (0.05)", ra="true = lao qua camera lúc cuối", dai_ra="giây ra (0.35)"),
         mac_dinh={"tu": 1.8, "dai": 0.45, "mo": 0.12, "vet": 5, "troi": 0.05, "ra": False, "dai_ra": 0.35, "mau_chu": "sang", "hoa": True, "bong": 0.5},
         hop=HOP_CHU, dong=True, sfx_goi_y=["whoosh lao tới", "bùm"],
         vi_du={"chu": "CHƯƠNG MỚI", "ra": True})
def zoom_mo(t, dur, W, H, c, p):
    kd = kieu_dang(c, p, "tieu_de", "sang")
    troi = float(p.get("troi", 0.05))
    bc = bo_chu(c, p.get("chu", ""), kd, W / (1 + troi), H / (1 + troi))
    s, cv = be_mat(W, H)
    ox, oy = bc.goc(W, H)
    s0, dai = float(p.get("tu", 1.8)), float(p.get("dai", 0.45))
    u = pha(t, 0, dai)
    e = e_expo(u, 7)
    sc = s0 + (1 - s0) * e
    sc *= 1 + troi * pha(t, dai, max(0.01, dur - dai))
    dr = float(p.get("dai_ra", 0.35))
    v = e_in_out(pha(t, dur - dr, dr)) if p.get("ra") else 0.0
    sc *= 1 + 1.6 * v ** 2
    mo = float(p.get("mo", 0.12)) * bc.co * ((1 - e) + 2.5 * v)
    op = e_out(pha(t, 0, dai * 0.35)) * (1 - v)
    n = int(p.get("vet", 5))
    ds = abs(s0 - 1) * (1 - e) * 0.5 + v * 0.8
    if n > 0 and ds > 0.01:
        for k in range(n, 0, -1):
            f = k / n
            bc.ve_khoi(cv, ox, oy, op=op * 0.35 * (1 - f) ** 1.2, sc=sc * (1 + ds * f * (1 if s0 >= 1 else -1)), mo=mo * 0.6)
    bc.ve_khoi(cv, ox, oy, op=op, sc=sc, mo=mo)
    return ra_np(s)


def dich(a, dx, dy):
    """dịch mảng (nguyên px), chỗ trống = 0"""
    dx, dy = int(round(dx)), int(round(dy))
    if not dx and not dy:
        return a
    out = np.zeros_like(a)
    h, w = a.shape[:2]
    xs, xd = (0, dx) if dx >= 0 else (-dx, 0)
    ys, yd = (0, dy) if dy >= 0 else (-dy, 0)
    cw, ch = w - abs(dx), h - abs(dy)
    if cw > 0 and ch > 0:
        out[yd:yd + ch, xd:xd + cw] = a[ys:ys + ch, xs:xs + cw]
    return out


def tach_kenh_np(pre, lr, lb, lg=(0, 0)):
    """numpy BGRA premul → tách kênh: R lệch lr, B lệch lb, G lệch lg; alpha = max (mép không tối)"""
    r = dich(pre[..., [2, 3]], *lr)
    g = dich(pre[..., [1, 3]], *lg)
    b = dich(pre[..., [0, 3]], *lb)
    return np.dstack([b[..., 0], g[..., 0], r[..., 0], np.maximum(np.maximum(r[..., 1], g[..., 1]), b[..., 1])])


def dat_vao(nen, a, x, y):
    """dán mảng a vào nen (cùng số kênh) tại (x,y) nguyên, cắt mép"""
    x, y = int(round(x)), int(round(y))
    H, W = nen.shape[:2]
    h, w = a.shape[:2]
    xa, ya, xb, yb = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
    if xb > xa and yb > ya:
        nen[ya:yb, xa:xb] = a[ya - y:yb - y, xa - x:xb - x]
    return nen


@dang_ky(id="mau.chu-glitch", nhom="chu", ten="Chữ glitch tách màu",
         mo_ta="chữ nhiễu kỹ thuật số: tách kênh RGB, cắt lát lệch ngang theo từng cơn ngẫu nhiên, vào bằng một cơn nhiễu mạnh",
         hop_nghia=["lỗi", "công nghệ", "hack", "căng thẳng", "game", "kỹ thuật số"],
         tham_so=_ts(chu="cụm ngắn", tach="độ tách kênh khi nhiễu (em, 0.07)", tach_nen="độ tách kênh thường trực (em, 0.012)",
                     tan_so="số cơn nhiễu/giây (2.5)", dai_con="giây mỗi cơn (0.12)", lat="số lát cắt mỗi cơn (5)", hat="hạt ngẫu nhiên (1)",
                     vao="giây cơn nhiễu mở đầu (0.3)", vach="0..1 vạch nhiễu màu (1)"),
         mac_dinh={"tach": 0.07, "tach_nen": 0.012, "tan_so": 2.5, "dai_con": 0.12, "lat": 5, "hat": 1, "vao": 0.3, "vach": 1.0,
                   "mau_chu": "sang", "hoa": True, "bong": 0, "font": "tieu_de"},
         hop=HOP_CHU, dong=True, sfx_goi_y=["glitch điện tử", "nhiễu sóng"],
         vi_du={"chu": "LỖI HỆ THỐNG"})
def chu_glitch(t, dur, W, H, c, p):
    kd = kieu_dang(c, p, "tieu_de", "sang")
    tach = float(p.get("tach", 0.07))
    bc = bo_chu(c, p.get("chu", ""), kd, W / (1 + 3 * tach), H * 0.9)
    ox, oy = bc.goc(W, H)
    img, gx, gy = bc.anh_khoi()
    hat = int(p.get("hat", 1))
    dc = max(0.02, float(p.get("dai_con", 0.12)))
    o = int(t / dc)
    r_o = random.Random(hat * 104729 + o)
    vao = float(p.get("vao", 0.3))
    if t < vao:
        cuong = 1 - pha(t, 0, vao) * 0.6
    else:
        cuong = 1.0 if r_o.random() < float(p.get("tan_so", 2.5)) * dc else 0.0
    tn = float(p.get("tach_nen", 0.012)) * bc.co
    d = tn + cuong * tach * bc.co * (0.5 + 0.5 * r_o.random())
    pre = dat_vao(np.zeros((H, W, 4), np.uint8), np_cache(img), ox - gx, oy - gy)
    out = tach_kenh_np(pre, (-d, 0), (d, d * 0.15 * cuong))
    if cuong > 0:
        nlat = max(1, int(p.get("lat", 5)))
        y0, y1 = int(max(0, oy + bc.tren)), int(min(H, oy + bc.duoi))
        if y1 > y0 + 2:
            cat = sorted(set([y0] + [int(r_o.uniform(y0, y1)) for _ in range(nlat - 1)] + [y1]))
            for a, b in zip(cat, cat[1:]):
                if r_o.random() < 0.6:
                    lx = r_o.uniform(-1, 1) * tach * bc.co * 1.5 * cuong
                    out[a:b] = dich(out[a:b], lx, 0)
        vach = float(p.get("vach", 1.0))
        for _ in range(int(3 * cuong * vach + 0.5)):
            yy = int(r_o.uniform(oy + bc.tren, oy + bc.duoi))
            hh = max(1, int(bc.co * r_o.uniform(0.015, 0.04)))
            xx = int(ox + r_o.uniform(-0.1, 0.6) * bc.w)
            ww = int(r_o.uniform(0.1, 0.5) * bc.w)
            r_, g_, b_, _ = rgba(c, r_o.choice(["nhan", "nhan2", "sang"]))
            al = 0.75
            ya, yb, xa, xb = max(0, yy), min(H, yy + hh), max(0, xx), min(W, xx + ww)
            if yb > ya and xb > xa:
                out[ya:yb, xa:xb] = (np.array([b_, g_, r_, 255], np.float32) * al).astype(np.uint8)
    op = e_out(pha(t, 0, 0.08))
    if op < 0.999:
        out = (out.astype(np.float32) * op).astype(np.uint8)
    return unpremul_rgba(out)
