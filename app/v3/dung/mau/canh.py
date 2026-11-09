# -*- coding: utf-8 -*-
"""MẪU CẢNH TRÁM (nhóm "canh") + BỘ CÔNG CỤ VẼ CHUNG của mũi Mẫu 1 (the.py · giao_dien.py · chen.py import từ đây).

Cảnh trám = một tấm giao diện vẽ ĐÚNG thứ đang nói (sơ đồ, checklist, biểu đồ, so sánh, các bước, dòng thời gian…).
Ba kiểu nền (tham số `kieu_nen`):
  "toan"  cả hộp là nền lưới + quầng màu nhấn trôi chậm (hoặc ảnh nền kho `anh_nen`) — cảnh trám cả khung
  "noi"   phủ tối hình bên dưới (`do_toi`) rồi đặt tấm nổi lên — người nói vẫn hiện mờ phía sau
  "trong" chỉ vẽ nội dung, nền trong suốt — đặt tấm vào một hộp nhỏ cạnh người nói
Mọi kích thước = hàm của hộp W×H (đơn vị u = cạnh ngắn vùng nội dung / 1000 × ti_le_chu). Màu theo vai của phong cách video.
Hoạt ảnh vào/ra tổng thể do engine lo; mẫu chỉ diễn NỘI DUNG theo t (mọc nhánh, cột lớn dần, tích từng dòng…).
"""
import math, os, hashlib
import numpy as np
import cv2
import skia
from dung import chu as _chu
from dung.mau import dang_ky

# ============================================================================ thời gian / easing ====
def kep(u, a=0.0, b=1.0):
    return a if u < a else b if u > b else u


def e_out(u):
    u = kep(u); return 1 - (1 - u) ** 3


def e_io(u):
    u = kep(u); return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2


def e_back(u, k=1.70158):
    u = kep(u); return 1 + (k + 1) * (u - 1) ** 3 + k * (u - 1) ** 2


def tien(t, t0, dai):
    """tiến độ 0..1 của một nhịp bắt đầu t0 dài `dai` giây"""
    if dai <= 0:
        return 1.0 if t >= t0 else 0.0
    return kep((t - t0) / dai)


def lich(n, dur, nhip, bat_dau=0.3, rieng=None, cuoi=0.72):
    """giây hiện của n mục: rieng[i] (giây tính từ đầu lớp) nếu có; còn lại dàn đều bat_dau + i·nhip,
    tự nén nhịp để mục cuối hiện trước cuoi·dur (lớp ngắn vẫn hiện đủ mục)"""
    nh = float(nhip)
    if n > 1:
        nh = min(nh, max(0.05, dur * cuoi - bat_dau) / (n - 1))
    ra = []
    for i in range(n):
        r = rieng[i] if rieng and i < len(rieng) else None
        try:
            ra.append(float(r) if r is not None else bat_dau + i * nh)
        except (TypeError, ValueError):
            ra.append(bat_dau + i * nh)
    return ra


def muc(x, cac_khoa=("chu", "t")):
    """mục danh sách: "chữ" | [chữ, giây, …] | {"chu":…, "t":…} → dict theo cac_khoa"""
    if isinstance(x, dict):
        return dict(x)
    if isinstance(x, (list, tuple)):
        return {k: (x[i] if i < len(x) else None) for i, k in enumerate(cac_khoa)}
    return {cac_khoa[0]: x}


def so(x, mac_dinh=0.0):
    """số từ 12 | "12,5" | "1.200" | "35%" → float"""
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x or "").strip().replace("%", "").replace(" ", "")
    if s.count(".") > 1 or (s.count(".") == 1 and len(s.split(".")[1]) == 3 and "," not in s):
        s = s.replace(".", "")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return mac_dinh


def so_vn(v, le=None):
    """định dạng số kiểu Việt: 1.234 · 12,5"""
    if le is None:
        le = 0 if abs(v) >= 100 or float(v).is_integer() else 1
    s = f"{v:,.{int(le)}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def le_cua(x):
    """số chữ số thập phân của số đích (để đếm 4,9 không thành 5)"""
    if isinstance(x, str):
        s = x.strip().replace("%", "")
        if "," in s:
            return len(s.split(",")[-1])
        if s.count(".") == 1 and len(s.split(".")[1]) != 3:
            return len(s.split(".")[1])
        return 0
    v = float(x)
    if v.is_integer():
        return 0
    return min(2, len(repr(v).split(".")[-1]))


# ============================================================================ màu ====
def rgba(m):
    return _chu.mau(m)


def hexm(r, g, b, a=255):
    return "#%02x%02x%02x%02x" % (int(r), int(g), int(b), int(a))


def tron(a, b, k):
    """trộn màu a→b theo k (0..1) → hex"""
    x, y = rgba(a), rgba(b)
    return hexm(*[round(x[i] * (1 - k) + y[i] * k) for i in range(4)])


def voi_alpha(m, al):
    r, g, b, a = rgba(m)
    return hexm(r, g, b, a * al)


def sk(m, al=1.0):
    return _chu.mau_skia(m, al)


def do_sang(m):
    r, g, b, _ = rgba(m)
    f = lambda v: (v / 255) / 12.92 if v <= 10 else ((v / 255 + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def chu_tren(nen, toi="#111114", sang="#ffffff"):
    """màu chữ đọc rõ trên nền `nen` (tương phản cao hơn thắng)"""
    L = do_sang(nen)
    c_toi = (L + 0.05) / (do_sang(toi) + 0.05)
    c_sang = (do_sang(sang) + 0.05) / (L + 0.05)
    return toi if c_toi > c_sang else sang


def bang_mau(c, p):
    """bảng màu giao diện theo vai màu của video + tham số tong_mau (toi|sang|kinh), mau/mau2 (vai|#hex)"""
    toi, sang = c.mau("toi"), c.mau("sang")
    nhan, nhan2 = c.mau(p.get("mau") or "nhan"), c.mau(p.get("mau2") or "nhan2")
    tong = str(p.get("tong_mau") or "toi")
    if tong == "sang":
        B = dict(nen=tron(sang, "#ffffff", 0.35), the="#ffffff", the2=tron("#ffffff", toi, 0.05), chu=toi,
                 phu=tron(toi, "#ffffff", 0.40), mo=tron(toi, "#ffffff", 0.62), vien=tron(toi, "#ffffff", 0.88),
                 bong_al=0.16, luoi="#000000")
        if do_sang(nhan) > 0.55:                      # nhấn quá sáng trên giấy trắng → đậm lại cho đọc được
            nhan = tron(nhan, "#000000", 0.35)
        if do_sang(nhan2) > 0.55:
            nhan2 = tron(nhan2, "#000000", 0.45)
    elif tong == "kinh":
        B = dict(nen=toi, the=voi_alpha("#ffffff", 0.13), the2=voi_alpha("#ffffff", 0.2), chu=sang, phu=tron(sang, toi, 0.3),
                 mo=tron(sang, toi, 0.55), vien=voi_alpha("#ffffff", 0.28), bong_al=0.22, luoi="#ffffff")
    else:
        B = dict(nen=toi, the=tron(toi, "#ffffff", 0.075), the2=tron(toi, "#ffffff", 0.13), chu=sang, phu=tron(sang, toi, 0.36),
                 mo=tron(sang, toi, 0.6), vien=tron(toi, "#ffffff", 0.16), bong_al=0.45, luoi="#ffffff")
    B.update(nhan=nhan, nhan2=nhan2, toi=toi, sang=sang, tong=tong,
             tren_nhan=chu_tren(nhan, toi, "#ffffff"), tren_nhan2=chu_tren(nhan2, toi, "#ffffff"))
    return B


def day_mau(B, n):
    """n màu phân biệt cho chuỗi dữ liệu (biểu đồ tròn…), bắt đầu từ màu nhấn"""
    goc = [B["nhan"], B["nhan2"], tron(B["nhan"], B["chu"], 0.45), tron(B["nhan2"], B["nen"], 0.35),
           tron(B["nhan"], B["nhan2"], 0.5), B["mo"], tron(B["nhan"], B["nen"], 0.45), tron(B["nhan2"], B["chu"], 0.5)]
    return [goc[i % len(goc)] for i in range(n)]


# ============================================================================ chữ ====
_CACHE_CHU = _chu.CacheAnh("mau.canh._CACHE_CHU")      # 1.2.21: trần RAM chung (cau_hinh cache_anh_mb)
SAMP = skia.SamplingOptions()
SAMP_LIN = skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kNone)   # mipmap làm mỗi lần vẽ chậm 10–50×
SAMP_CUBIC = skia.SamplingOptions(skia.CubicResampler.Mitchell())


def _kd(c, co, mau, vai, dam, can, hoa, gian, dong, bong, vien):
    """1.2.21: dam/dong/mau không còn 700 / 1.15 / #ffffff hàn ở đây — None → quyet_dinh chu.dam / chu.dong / bang_mau.sang (qua c)"""
    f = vai if (isinstance(vai, str) and os.path.isfile(vai)) else c.font(vai or "nhan")
    if dam is None:
        dam = c.quyet("chu.dam")
    if dong is None:
        dong = c.quyet("chu.dong")
    if mau is None:
        mau = c.mau("sang")
    kd = {"font": f, "co": round(float(co), 1), "dam": int(dam), "mau": mau, "can": can, "hoa": bool(hoa),
          "gian": float(gian), "dong": float(dong)}
    if bong:
        kd["bong"] = bong
    if vien:
        kd["vien"] = vien
    return kd


def anh_chu(c, text, co, mau=None, vai="nhan", dam=None, rong=None, can="trai", hoa=False, gian=0.0, dong=None,
            bong=None, vien=None):
    """khối chữ qua text engine chung (kerning, dấu Việt, ngắt dòng) → (skia.Image premul, meta); có cache"""
    text = str(text if text is not None else "")
    kd = _kd(c, co, mau, vai, dam, can, hoa, gian, dong, bong, vien)
    k = (text, repr(sorted(kd.items())), int(rong) if rong else None)
    r = _CACHE_CHU.get(k)
    if r is None:
        r = c.ve_chu(text, kd, rong_max_px=(float(rong) if rong else None), tra_skia=True)
        _CACHE_CHU[k] = r
    return r


def do_chu(c, text, co, vai="nhan", dam=None, rong=None, hoa=False, gian=0.0, dong=None):
    """→ (w, h, số dòng) khối chữ nhìn thấy"""
    kd = _kd(c, co, "#fff", vai, dam, "trai", hoa, gian, dong, None, None)
    bc = _chu.bo_cuc(str(text or ""), kd, float(rong) if rong else None, c.W)
    return bc["w"], bc["h"], len(bc["dong"])


def vua_co(c, text, co, rong, so_dong=2, cao=None, co_min=None, **kw):
    """cỡ chữ lớn nhất ≤ co để khối vừa rộng `rong`, ≤ so_dong dòng (và ≤ cao nếu có)"""
    co_min = co_min or co * 0.5
    co = float(co)
    while True:
        w, h, n = do_chu(c, text, co, rong=rong, **kw)
        if (n <= so_dong and w <= rong + 0.5 and (cao is None or h <= cao)) or co <= co_min:
            return co
        co = max(co_min, co * 0.92)


def vua(c, text, co, rong, dong_dep=1, dong_max=2, co_min=None, **kw):
    """cỡ chữ đẹp: ưu tiên gọn trong `dong_dep` dòng (thu tối đa 28%), không được thì cho tới `dong_max` dòng (thu tới co_min)"""
    c1 = vua_co(c, text, co, rong, dong_dep, co_min=co * 0.72, **kw)
    w, h, n = do_chu(c, text, c1, rong=rong, **kw)
    if n <= dong_dep and w <= rong + 0.5:
        return c1
    return vua_co(c, text, co, rong, dong_max, co_min=co_min, **kw)


def kich(im):
    x0, y0, x1, y1 = im[1]["khoi"]
    return x1 - x0, y1 - y0


def dat(cv, im, x, y, neo="tl", alpha=1.0, ti_le=1.0):
    """đặt khối chữ: điểm neo (t|m|b + l|c|r) của HỘP NHÌN THẤY tại (x,y) → (x0,y0,x1,y1) hộp đã đặt"""
    img, meta = im
    kx0, ky0, kx1, ky1 = meta["khoi"]
    w, h = kx1 - kx0, ky1 - ky0
    ay = {"t": 0.0, "m": 0.5, "b": 1.0}[neo[0]]
    ax = {"l": 0.0, "c": 0.5, "r": 1.0}[neo[1]]
    bx, by = x - ax * w, y - ay * h
    if alpha <= 0.002:
        return (bx, by, bx + w, by + h)
    paint = None
    if alpha < 0.998:
        paint = skia.Paint(); paint.setAlphaf(float(alpha))
    if abs(ti_le - 1) > 1e-3:
        cv.save(); cv.translate(x, y); cv.scale(ti_le, ti_le); cv.translate(-x, -y)
        cv.drawImage(img, bx - kx0, by - ky0, SAMP_CUBIC, paint)
        cv.restore()
    else:
        cv.drawImage(img, round(bx - kx0), round(by - ky0), SAMP, paint)
    return (bx, by, bx + w, by + h)


# ============================================================================ hình ====
def p_to(m, al=1.0):
    p = skia.Paint(AntiAlias=True); p.setColor(sk(m, al)); return p


def p_net(m, w, al=1.0, tron_dau=True):
    p = skia.Paint(AntiAlias=True); p.setColor(sk(m, al)); p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(float(w))
    if tron_dau:
        p.setStrokeCap(skia.Paint.kRound_Cap); p.setStrokeJoin(skia.Paint.kRound_Join)
    return p


def rr(x0, y0, x1, y1, r):
    r = max(0.0, min(float(r), (x1 - x0) / 2, (y1 - y0) / 2))
    return skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(x0, y0, x1, y1), r, r)


def hop(cv, x0, y0, x1, y1, r, mau, al=1.0, vien=None, vien_w=0.0, vien_al=1.0):
    cv.drawRRect(rr(x0, y0, x1, y1, r), p_to(mau, al))
    if vien and vien_w > 0:
        h = vien_w / 2
        cv.drawRRect(rr(x0 + h, y0 + h, x1 - h, y1 - h, max(0, r - h)), p_net(vien, vien_w, al * vien_al, False))


_BONG = {}


def _anh_bong(r, mo, mau=None):
    """ảnh 9 mảnh của bóng mờ một hình bo góc r (vẽ blur 1 lần, khung nào cũng chỉ dán) — blur trực tiếp trên CPU 20–50 ms;
    màu bóng nướng sẵn vào ảnh (ColorFilter lúc vẽ chậm 40×)"""
    r = int(round(max(0.0, r))); s = max(1, int(round(mo)))
    k = (r, s, mau)
    if k in _BONG:
        return _BONG[k]
    e = int(math.ceil(s * 1.6)) + 2
    core = 2 * r + 4
    S = core + 2 * e
    surf = skia.Surface(S, S); c = surf.getCanvas(); c.clear(skia.Color4f(0, 0, 0, 0))
    p = skia.Paint(AntiAlias=True); p.setColor(sk(mau) if mau else skia.ColorBLACK)
    p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, s / 2.0))
    c.drawRRect(rr(e, e, e + core, e + core, r), p)
    if len(_BONG) > 300:
        _BONG.clear()
    _BONG[k] = (surf.makeImageSnapshot(), e, r, S)
    return _BONG[k]


def bong(cv, x0, y0, x1, y1, r, mo, al=0.35, dx=0.0, dy=0.0, mau=None):
    """bóng mềm dưới hình bo góc (x0..y1, r), độ mờ `mo` px"""
    if al <= 0.003 or x1 - x0 < 2 or y1 - y0 < 2:
        return
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    img, e, ri, S = _anh_bong(r, mo, mau)
    k = e + ri
    X0, Y0, X1, Y1 = x0 - e + dx, y0 - e + dy, x1 + e + dx, y1 + e + dy
    p = skia.Paint(); p.setAlphaf(float(kep(al)))
    sx = [0, k, S - k, S]; dxs = [X0, X0 + k, X1 - k, X1]
    dys = [Y0, Y0 + k, Y1 - k, Y1]
    for i in range(3):
        for j in range(3):
            if dxs[i + 1] - dxs[i] <= 0 or dys[j + 1] - dys[j] <= 0:
                continue
            cv.drawImageRect(img, skia.Rect.MakeLTRB(sx[i], sx[j], sx[i + 1], sx[j + 1]),
                             skia.Rect.MakeLTRB(dxs[i], dys[j], dxs[i + 1], dys[j + 1]), SAMP_LIN, p)


def the_noi(cv, B, x0, y0, x1, y1, r, u, mau=None, al=1.0, vien=True, do_bong=1.0):
    """tấm thẻ: bóng mềm + nền + viền mảnh theo bảng màu"""
    bong(cv, x0, y0, x1, y1, r, 34 * u, B["bong_al"] * al * do_bong, dy=10 * u)
    hop(cv, x0, y0, x1, y1, r, mau or B["the"], al, B["vien"] if vien else None, max(1.0, 2 * u))


def duong_cat(cv, path, k, paint):
    """vẽ k (0..1) đầu tiên của đường (một nét liền)"""
    if k <= 0:
        return
    if k >= 0.999:
        cv.drawPath(path, paint); return
    pm = skia.PathMeasure(path, False)
    L = pm.getLength()
    d = skia.Path()
    pm.getSegment(0, L * k, d, True)
    cv.drawPath(d, paint)


def duong_gap(pts):
    p = skia.Path(); p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    return p


def dau_tich(cv, cx, cy, s, mau, k=1.0, w=None):
    """dấu ✓ vẽ bằng nét (không phụ thuộc glyph) — k: tiến độ nét"""
    pa = duong_gap([(cx - 0.42 * s, cy + 0.02 * s), (cx - 0.12 * s, cy + 0.32 * s), (cx + 0.45 * s, cy - 0.3 * s)])
    duong_cat(cv, pa, k, p_net(mau, w or s * 0.16))


def dau_x(cv, cx, cy, s, mau, k=1.0, w=None):
    p = p_net(mau, w or s * 0.15)
    a = 0.32 * s
    duong_cat(cv, duong_gap([(cx - a, cy - a), (cx + a, cy + a)]), kep(k * 2), p)
    duong_cat(cv, duong_gap([(cx + a, cy - a), (cx - a, cy + a)]), kep(k * 2 - 1), p)


def path_sao(cx, cy, r, trong=0.46):
    p = skia.Path()
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr_ = r if i % 2 == 0 else r * trong
        x, y = cx + rr_ * math.cos(a), cy + rr_ * math.sin(a)
        p.moveTo(x, y) if i == 0 else p.lineTo(x, y)
    p.close()
    return p


def sao(cv, cx, cy, r, mau, mau_nen, phan=1.0, al=1.0):
    """một ngôi sao, tô `phan` (0..1) từ trái sang (sao lẻ 4,5)"""
    pa = path_sao(cx, cy, r)
    cv.drawPath(pa, p_to(mau_nen, al))
    if phan > 0:
        cv.save(); cv.clipRect(skia.Rect.MakeLTRB(cx - r, cy - r, cx - r + 2 * r * kep(phan), cy + r), True)
        cv.drawPath(pa, p_to(mau, al)); cv.restore()


# ============================================================================ ảnh từ kho ====
def _thu_muc_cache():
    try:
        import chung
        d = os.path.join(chung.duong("du_lieu"), "cache-anh-mau")
    except Exception:
        d = os.path.join(os.path.expanduser("~"), ".cache-anh-mau")
    os.makedirs(d, exist_ok=True)
    return d


def skia_tu_bgra(a):
    """numpy BGRA alpha thẳng → skia.Image NHÂN TRƯỚC alpha (vẽ ảnh unpremul mỗi lần chậm ~40×: skia đổi cả ảnh mỗi lượt vẽ)"""
    a = np.ascontiguousarray(a)
    al = a[..., 3:4]
    if al.min() < 255:
        a = np.ascontiguousarray(np.concatenate([(a[..., :3].astype(np.uint16) * al + 127) // 255, al], axis=2).astype(np.uint8))
    return skia.Image.fromarray(a, skia.kBGRA_8888_ColorType, skia.kPremul_AlphaType)


_DUONG = {}


def duong_tai_nguyen(c, ref, loai=None):
    """id kho | đường dẫn | (loai≠None) NGHĨA → đường dẫn file hoặc None (nhớ kết quả: tra kho mỗi khung tốn vài ms)"""
    if not ref:
        return None
    k = (id(c.ctx), str(ref), loai)
    if k in _DUONG:
        return _DUONG[k]
    p = _tra_duong(c, ref, loai)
    if len(_DUONG) > 2000:
        _DUONG.clear()
    _DUONG[k] = p
    return p


def _tra_duong(c, ref, loai):
    p = c.tai_nguyen(ref)
    if p:
        return p
    try:
        from kho import tim as _K
        m = _K.lay(str(ref))
        if m and m.get("duong") and os.path.isfile(m["duong"]):
            return m["duong"]
        if loai:
            r = _K.tim(loai=loai, nghia=str(ref), n=1)
            if r and os.path.isfile(r[0].get("duong", "")):
                return r[0]["duong"]
    except Exception:
        pass
    return None


_ANH = _chu.CacheAnh("mau.canh._ANH")      # 1.2.21: trần RAM chung


def anh(c, ref, canh_max=1200, loai=None, cat_trong=False):
    """ảnh (id kho | đường dẫn | nghĩa nếu loai) → skia.Image (thu nhỏ ≤ canh_max, cache đĩa — icon kho có cái 11 000 px)"""
    p = duong_tai_nguyen(c, ref, loai)
    if not p:
        return None
    k = (p, int(canh_max), cat_trong)
    if k in _ANH:
        return _ANH[k]
    a = None
    try:
        st = os.stat(p)
        ten = hashlib.md5(f"{os.path.abspath(p)}|{st.st_size}|{int(st.st_mtime)}|{canh_max}|{cat_trong}".encode()).hexdigest()[:16] + ".png"
        pc = os.path.join(_thu_muc_cache(), ten)
        if os.path.isfile(pc):
            a = cv2.imdecode(np.fromfile(pc, np.uint8), cv2.IMREAD_UNCHANGED)
        if a is None:
            a = cv2.imdecode(np.fromfile(p, np.uint8), cv2.IMREAD_UNCHANGED)
            if a is None:
                raise ValueError("không đọc được ảnh")
            if a.ndim == 2:
                a = cv2.cvtColor(a, cv2.COLOR_GRAY2BGRA)
            elif a.shape[2] == 3:
                a = cv2.cvtColor(a, cv2.COLOR_BGR2BGRA)
            if a.dtype != np.uint8:
                a = (a.astype(np.float32) / max(float(a.max()), 1) * 255).astype(np.uint8)
            if cat_trong:                                     # cắt viền trong suốt → cỡ đặt = cỡ hình thật
                ys, xs = np.where(a[..., 3] > 8)
                if len(xs):
                    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            s = canh_max / max(a.shape[:2])
            if s < 1:
                a = cv2.resize(a, (max(1, int(a.shape[1] * s)), max(1, int(a.shape[0] * s))), interpolation=cv2.INTER_AREA)
            try:
                cv2.imencode(".png", a)[1].tofile(pc)
            except Exception:
                pass
        img = skia_tu_bgra(a)
    except Exception:
        img = None
    _ANH[k] = img
    return img


def ve_anh_phu(cv, img, x0, y0, x1, y1, z=1.0, cx=0.5, cy=0.5, al=1.0, r=0.0):
    """dán ảnh phủ kín (cover) hộp, zoom z quanh (cx,cy), bo góc r"""
    w, h = x1 - x0, y1 - y0
    s = max(w / img.width(), h / img.height()) * z
    dw, dh = img.width() * s, img.height() * s
    dx = x0 + (w - dw) * cx; dy = y0 + (h - dh) * cy
    p = None
    if al < 0.998:
        p = skia.Paint(); p.setAlphaf(al)
    cv.save()
    if r > 0:
        cv.clipRRect(rr(x0, y0, x1, y1, r), True)
    else:
        cv.clipRect(skia.Rect.MakeLTRB(x0, y0, x1, y1))
    cv.drawImageRect(img, skia.Rect.MakeLTRB(dx, dy, dx + dw, dy + dh), SAMP_LIN, p)
    cv.restore()


# ============================================================================ khung / nền / vùng ====
def be_mat(W, H):
    s = skia.Surface(int(W), int(H))
    cv = s.getCanvas(); cv.clear(skia.Color4f(0, 0, 0, 0))
    return s, cv


def _bo_nhan_truoc(a):
    b, g, r_, al = cv2.split(a)
    return cv2.merge([cv2.divide(r_, al, scale=255.0), cv2.divide(g, al, scale=255.0), cv2.divide(b, al, scale=255.0), al])


def ra(surf, duc=False, vung=None):
    """skia surface → numpy RGBA thẳng (không nhân trước alpha). duc=True: biết chắc ảnh đục → bỏ bước chia alpha.
    vung=(x0,y0,x1,y1): chỉ vùng này có hình (phần còn lại trong suốt) → chỉ xử lý vùng đó (mẫu thưa trên hộp lớn)"""
    if vung is not None:
        W, H = surf.width(), surf.height()
        x0, y0 = max(0, int(vung[0]) - 2), max(0, int(vung[1]) - 2)
        x1, y1 = min(W, int(math.ceil(vung[2])) + 2), min(H, int(math.ceil(vung[3])) + 2)
        out = np.zeros((H, W, 4), np.uint8)
        if x1 > x0 and y1 > y0:
            img = surf.makeImageSnapshot(skia.IRect.MakeLTRB(x0, y0, x1, y1))
            a = img.toarray(colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
            out[y0:y1, x0:x1] = _bo_nhan_truoc(a)
        return out
    a = surf.makeImageSnapshot().toarray(colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
    if duc:
        return cv2.cvtColor(a, cv2.COLOR_BGRA2RGBA)
    return _bo_nhan_truoc(a)


_NEN = _chu.CacheAnh("mau.canh._NEN")      # 1.2.21: trần RAM chung


def _anh_nen_luoi(W, H, toi, nhan, luoi, sang, o):
    """nền lưới mảnh + quầng màu nhấn góc trên + tối dần mép — sinh bằng mã, cache theo cỡ/màu"""
    k = (W, H, toi, nhan, luoi, sang, int(o))
    if k in _NEN:
        return _NEN[k]
    # vẽ ở nửa cỡ rồi phóng (nền mềm, rẻ); lưới vẽ bằng skia ở cỡ thật cho nét
    w2, h2 = max(2, W // 2), max(2, H // 2)
    yy, xx = np.mgrid[0:h2, 0:w2].astype(np.float32)
    goc = np.array(rgba(toi)[:3], np.float32)
    im = np.ones((h2, w2, 3), np.float32) * goc
    r = np.sqrt(((xx - w2 * 0.8) / max(w2, h2)) ** 2 + ((yy - h2 * 0.12) / max(w2, h2)) ** 2)
    q = np.clip(1 - r / 0.85, 0, 1)[..., None] ** 2 * (0.2 if sang else 0.36)
    im = im * (1 - q) + np.array(rgba(nhan)[:3], np.float32) * q
    r2 = np.sqrt(((xx - w2 * 0.1) / max(w2, h2)) ** 2 + ((yy - h2 * 0.95) / max(w2, h2)) ** 2)
    q2 = np.clip(1 - r2 / 0.7, 0, 1)[..., None] ** 2 * (0.08 if sang else 0.16)
    im = im * (1 - q2) + np.array(rgba(nhan)[:3], np.float32) * q2
    v = np.sqrt(((xx - w2 / 2) / w2) ** 2 + ((yy - h2 / 2) / h2) ** 2)
    im *= (1 - (0.12 if sang else 0.38) * np.clip(v - 0.25, 0, 1))[..., None]
    im = cv2.resize(np.clip(im, 0, 255).astype(np.uint8), (W, H), interpolation=cv2.INTER_LINEAR)
    nen = skia_tu_bgra(cv2.cvtColor(im, cv2.COLOR_RGB2BGRA))
    s = skia.Surface(W, H); c = s.getCanvas(); c.drawImage(nen, 0, 0)
    p = p_net(luoi, 1.2, 0.07 if not sang else 0.06, False)
    x = (W % o) / 2
    while x < W:
        c.drawLine(x, 0, x, H, p); x += o
    y = (H % o) / 2
    while y < H:
        c.drawLine(0, y, W, y, p); y += o
    _NEN[k] = s.makeImageSnapshot()
    return _NEN[k]


def ve_nen(cv, c, p, B, t, dur, W, H):
    """nền cảnh theo kieu_nen → True nếu nền đục (bỏ được bước chia alpha khi xuất)"""
    kieu = str(p.get("kieu_nen") or "toan")
    if kieu == "toan":
        img = anh(c, p.get("anh_nen"), max(W, H)) if p.get("anh_nen") else None
        z = 1.0 + float(p.get("troi_nen", 0.04)) * kep(t / max(dur, 1e-3))
        if img is not None:
            cv.drawRect(skia.Rect.MakeWH(W, H), p_to(B["nen"]))
            ve_anh_phu(cv, img, 0, 0, W, H, z)
            cv.drawRect(skia.Rect.MakeWH(W, H), p_to(B["nen"], float(p.get("do_toi", 0.55))))
        else:
            o = max(16, int(min(W, H) / float(p.get("o_luoi", 18))))
            g = _anh_nen_luoi(W, H, B["nen"], B["nhan"], B["luoi"], B["tong"] == "sang", o)
            dw, dh = W * z, H * z
            cv.drawImageRect(g, skia.Rect.MakeLTRB((W - dw) / 2, (H - dh) / 2, (W + dw) / 2, (H + dh) / 2), SAMP_LIN)
        return True
    if kieu == "noi":
        dt = float(p.get("do_toi", 0.62))
        cv.drawRect(skia.Rect.MakeWH(W, H), p_to(B["toi"] if B["tong"] != "sang" else B["nen"], dt))
    return False


def vung(c, W, H, p):
    """vùng đặt nội dung (x0,y0,x1,y1) + đơn vị u: hộp = cả khung → đúng vùng an toàn của nền tảng (chung.vung_an_toan — một nguồn,
    1.2.21: bỏ bản sao luật +H·0.02 / lề 0.05 trong mẫu); hộp nhỏ → lề đều theo tham số `le` (mặc định 0)"""
    le = float(p.get("le", 0) or 0)
    if W >= c.W * 0.97 and H >= c.H * 0.97:
        v = getattr(c.ctx, "vung", None) or __import__("chung").vung_an_toan(c.W, c.H)
        x0 = W * max(float(v.get("trai", 0)), le); x1 = W * (1 - max(float(v.get("phai", 0)), le))
        y0 = H * max(float(v.get("tren", 0)), le); y1 = H * (1 - max(float(v.get("duoi", 0)), le))
    else:
        d = le * min(W, H)
        x0, y0, x1, y1 = d, d, W - d, H - d
    u = min(x1 - x0, y1 - y0) / 1000.0 * float(p.get("ti_le_chu", 1.0))
    return x0, y0, x1, y1, max(u, 0.15)


def ve_tieu_de(cv, c, p, B, x0, x1, y, u, t, can="trai", co=66):
    """nhãn nhỏ (nhan_tren) + tiêu đề → y dưới khối"""
    td, nt = p.get("tieu_de"), p.get("nhan_tren")
    if not td and not nt:
        return y
    a = e_out(tien(t, 0, 0.35))
    dy = (1 - a) * 16 * u
    neo = {"trai": "tl", "giua": "tc", "phai": "tr"}[can]
    xa = {"trai": x0, "giua": (x0 + x1) / 2, "phai": x1}[can]
    if nt:
        im = anh_chu(c, nt, 30 * u, B["nhan"], vai=p.get("font") or "nhan", hoa=True, gian=0.12)
        b = dat(cv, im, xa, y + dy, neo, a)
        y = b[3] + 10 * u
    if td:
        cw = vua_co(c, td, co * u, x1 - x0, 2, vai=p.get("font_tieu_de") or "tieu_de")
        im = anh_chu(c, td, cw, B["chu"], vai=p.get("font_tieu_de") or "tieu_de", rong=x1 - x0, can=can, dong=1.1)
        b = dat(cv, im, xa, y + dy, neo, a)
        y = b[3]
    return y + 44 * u


THAM_SO_NEN = {
    "kieu_nen": "toan (nền lưới/ảnh cả hộp) | noi (phủ tối hình dưới + tấm nổi) | trong (nền trong suốt)",
    "tong_mau": "toi | sang | kinh (kính mờ) — tông tấm giao diện",
    "mau": "màu nhấn chính (vai nhan|nhan2|sang|toi hoặc #hex)", "mau2": "màu nhấn phụ",
    "anh_nen": "id kho nen.* / đường ảnh làm nền khi kieu_nen=toan (tuỳ)", "do_toi": "độ phủ tối 0..1 (noi 0.62, ảnh nền 0.55)",
    "ti_le_chu": "nhân cỡ chữ/khối (1.0)", "phong": "phóng khối tối đa khi hộp thừa chỗ (1.3; khối luôn tự thu cho khỏi tràn)", "le": "lề trong hộp, phần cạnh ngắn (0 = không; hộp cả khung dùng vùng an toàn nền tảng)",
    "tieu_de": "dòng tiêu đề (tuỳ, lấy từ lời)", "nhan_tren": "nhãn nhỏ trên tiêu đề (tuỳ)",
    "font": "vai/id font chữ thân (nhan)", "font_tieu_de": "vai/id font tiêu đề (tieu_de)",
}
MAC_DINH_NEN = {"kieu_nen": "toan", "tong_mau": "toi", "ti_le_chu": 1.0}


def _the_canh(**kw):
    ts = dict(THAM_SO_NEN); ts.update(kw.pop("tham_so", {}))
    md = dict(MAC_DINH_NEN); md.update(kw.pop("mac_dinh", {}))
    kw.setdefault("toan_khung", True); kw.setdefault("dong", True)
    return dict(nhom="canh", tham_so=ts, mac_dinh=md, **kw)


def _bat_dau(c, p, W, H, t, dur):
    """mở bề mặt + nền + bảng màu + vùng → (surf, cv, B, (x0,y0,x1,y1,u), duc)"""
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    duc = ve_nen(cv, c, p, B, t, dur, W, H)
    return surf, cv, B, vung(c, W, H, p), duc


_PHONG = {}


def phong(khoa, u0, do_can, co, p=None, toi_thieu=0.45):
    """đơn vị u để khối vừa chiều cao `co`: do_can(u) → chiều cao cần. Thừa chỗ → phóng (≤ tham số `phong`, mặc định 1.3);
    thiếu chỗ → thu (không tràn hộp). Kết quả cache theo khoa (tham số + cỡ hộp) → chỉ đo ở khung đầu."""
    toi_da = float((p or {}).get("phong", 1.3))
    k = (khoa, round(u0, 4), round(co, 1), toi_da)
    f = _PHONG.get(k)
    if f is None:
        h = do_can(u0)
        f = kep(co / max(h, 1.0), toi_thieu, max(1.0, toi_da))
        if abs(f - 1) > 0.02:
            for _ in range(3):                       # chữ ngắt dòng khác ở cỡ mới → đo lại, thu thêm nếu vẫn tràn
                h2 = do_can(u0 * f)
                if h2 <= co * 1.001:
                    break
                f *= co / h2 * 0.98
        if len(_PHONG) > 2000:
            _PHONG.clear()
        _PHONG[k] = f
    return u0 * f


def khop(khoa, u0, do_wh, W, H, p=None, toi_da=3.0):
    """đơn vị u để khối do_wh(u) → (w, h) VỪA KHÍT hộp W×H (phóng tới khi chạm một chiều, thu khi tràn).
    w = 0 → chỉ khớp theo chiều cao (bố cục đã trải hết bề ngang hộp). Cache theo khoá."""
    toi_da = float((p or {}).get("phong", toi_da))
    k = ("khop", khoa, round(u0, 4), int(W), int(H), toi_da)
    f = _PHONG.get(k)
    if f is None:
        def ti(x):
            w, h = do_wh(u0 * x)
            return min(W / w if w > 0 else 1e9, H / h if h > 0 else 1e9)
        f = kep(ti(1.0), 0.15, toi_da)
        for _ in range(4):                       # ngắt dòng đổi theo cỡ → đo lại tới khi vừa
            g = ti(f)
            if g >= 0.999:
                break
            f *= g * 0.985
        if len(_PHONG) > 2000:
            _PHONG.clear()
        _PHONG[k] = f
    return u0 * f


def bong_chu(u, dam=1.0):
    """bóng mềm cho chữ đặt thẳng trên video"""
    return [{"x": 0, "y": 3 * u, "mo": 16 * u, "mau": voi_alpha("#000000", 0.62 * dam)}]


def don_vi_goc(c):
    """1 đơn vị thiết kế = 1 px ở khung dọc 1080 (theo cạnh ngắn khung)"""
    return min(c.W, c.H) / 1080.0


def khoa_p(mid, W, H, p, B=None):
    """khoá cache bố cục: mẫu + cỡ hộp + tham số + bảng màu"""
    return (mid, int(W), int(H), repr(sorted((k, repr(v)) for k, v in p.items())), repr(sorted(B.items())) if B else "")


_BO = _chu.CacheAnh("mau.canh._BO")      # 1.2.21: trần RAM chung


def nho(khoa, u, fn):
    """bố cục fn(u) nhớ theo khoá — chữ đã đo/vẽ không phải đo lại mỗi khung"""
    k = (khoa, round(u, 4))
    r = _BO.get(k)
    if r is None:
        r = _BO[k] = fn(u)
    return r


def cao_tieu_de(c, p, x0, x1, u, co=66):
    """chiều cao ve_tieu_de sẽ chiếm (gồm khoảng cách dưới)"""
    td, nt = p.get("tieu_de"), p.get("nhan_tren")
    if not td and not nt:
        return 0.0
    h = 0.0
    if nt:
        h += kich(anh_chu(c, nt, 30 * u, "#fff", vai=p.get("font") or "nhan", hoa=True, gian=0.12))[1] + 10 * u
    if td:
        cw = vua_co(c, td, co * u, x1 - x0, 2, vai=p.get("font_tieu_de") or "tieu_de")
        h += do_chu(c, td, cw, vai=p.get("font_tieu_de") or "tieu_de", rong=x1 - x0, dong=1.1)[1]
    return h + 44 * u


# ============================================================================ MẪU ====

# ---------------------------------------------------------------- sơ đồ tư duy
@dang_ky(**_the_canh(
    id="mau.so-do-tu-duy", ten="Sơ đồ tư duy mọc nhánh",
    mo_ta="Ý trung tâm + các nhánh ý con mọc ra lần lượt đúng lúc nói tới (dọc: thân giữa 2 cột; ngang: toả 2 bên).",
    hop_nghia=["liệt kê", "phân loại", "nhiều ý", "một ý lớn tách ra", "sơ đồ", "các yếu tố"],
    tham_so={"tam": "chữ trung tâm (1–4 từ)", "nhanh": "list ý con: \"chữ\" | [chữ, giây từ đầu lớp] (≤ 8)",
             "nhip": "giây giữa 2 nhánh khi không ghi giây (0.45)", "bat_dau": "giây nhánh đầu (0.5)"},
    mac_dinh={"nhip": 0.45, "bat_dau": 0.5}, sfx_goi_y=["pop nhẹ", "whoosh nhẹ", "click"],
    vi_du={"tam": "Bán hàng online", "nhanh": ["Chọn sản phẩm đúng nhu cầu", "Quay video ngắn mỗi ngày", "Trả lời bình luận nhanh",
                                              "Livestream tối thứ Bảy", "Chăm khách cũ"], "nhip": 0.4, "tieu_de": "5 việc mỗi tuần"}))
def so_do_tu_duy(t, dur, W, H, c, p):
    surf, cv, B, (X0, Y0, X1, Y1, u0), duc = _bat_dau(c, p, W, H, t, dur)
    ds = [muc(x) for x in (p.get("nhanh") or [])][:8]
    n = len(ds)
    ts = lich(n, dur, p.get("nhip", 0.45), p.get("bat_dau", 0.5), [d.get("t") for d in ds])
    font = p.get("font") or "nhan"
    ngang = (X1 - X0) / max(1.0, Y1 - Y0) > 1.25
    tam = str(p.get("tam") or "")
    so_hang = (n + 1) // 2 if n > 1 else 1

    def bo(u):
        L = {"u": u}
        rong_t = (X1 - X0) * (0.26 if ngang else 0.78)
        co_t = vua(c, tam, 62 * u, rong_t, 1, 2, vai=font)
        im_t = anh_chu(c, tam, co_t, B["tren_nhan"], vai=font, rong=rong_t, can="giua")
        tw, th = kich(im_t)
        nw, nh = tw + 96 * u, th + 60 * u
        gap = 80 * u
        cot_w = min((X1 - X0) * 0.3, (X1 - X0 - nw) / 2 - 130 * u) if ngang else ((X1 - X0 - gap) / 2 if n > 1 else (X1 - X0) * 0.7)
        pad_x = 30 * u
        rong_chu = cot_w - pad_x * 2 - 26 * u
        co_n = min(vua(c, d.get("chu", ""), 50 * u, rong_chu, 2, 3, co_min=28 * u, vai=font) for d in ds) if ds else 40 * u
        o = []
        for d in ds:
            im = anh_chu(c, d.get("chu", ""), co_n, B["chu"], vai=font, rong=rong_chu)
            o.append((im, kich(im)))
        hang_h = max([k[1] for _, k in o] + [co_n]) + 64 * u
        khe_hang = 52 * u
        td_h = cao_tieu_de(c, p, X0, X1, u)
        if ngang:
            cot_h = ((n + 1) // 2) * (hang_h + 26 * u)
            can = td_h + max(nh, cot_h)
        else:
            can = td_h + nh + 110 * u + so_hang * hang_h + (so_hang - 1) * khe_hang
        L.update(cot_w=cot_w, pad_x=pad_x, o=o, hang_h=hang_h, im_t=im_t, nw=nw, nh=nh, khe_hang=khe_hang, can=can, td_h=td_h)
        return L
    kh = khoa_p("so-do", W, H, p, B)
    u = phong(kh, u0, lambda x: nho(kh, x, bo)["can"], Y1 - Y0, p)
    L = nho(kh, u, bo)
    cot_w, pad_x, o, hang_h, im_t, nw, nh, khe_hang = (L[k] for k in ("cot_w", "pad_x", "o", "hang_h", "im_t", "nw", "nh", "khe_hang"))
    y = Y0 + max(0.0, (Y1 - Y0 - L["can"]) * 0.45)
    y = ve_tieu_de(cv, c, p, B, X0, X1, y, u, t, "giua")
    cx = (X0 + X1) / 2
    cot = []
    if ngang:
        cy = (y + Y1) / 2 if L["can"] < Y1 - Y0 else y + (L["can"] - L["td_h"]) / 2
        for ben, ids in ((0, list(range(0, n, 2))), (1, list(range(1, n, 2)))):
            tong = len(ids) * hang_h + (len(ids) - 1) * 26 * u
            y0 = cy - tong / 2
            for j, i in enumerate(ids):
                ex = X0 + cot_w / 2 if ben == 0 else X1 - cot_w / 2
                cot.append((i, ex, y0 + j * (hang_h + 26 * u) + hang_h / 2, ben))
        cot.sort()
    else:
        cy = y + nh / 2
        vy0 = cy + nh / 2 + 110 * u
        buoc = hang_h + khe_hang
        for i in range(n):
            if n == 1 or (n % 2 == 1 and i == n - 1):
                cot.append((i, cx, vy0 + (i // 2) * buoc + hang_h / 2, 2))
            else:
                ben = i % 2
                cot.append((i, X0 + cot_w / 2 if ben == 0 else X1 - cot_w / 2, vy0 + (i // 2) * buoc + hang_h / 2, ben))
    lw = max(2.0, 5 * u)
    if not ngang and n:                                   # thân dọc mọc tới nhánh mới nhất
        y_den = cy + nh / 2
        for (i, ex, ey, ben) in cot:
            k = e_out(tien(t, ts[i], 0.3))
            dich = ey if ben != 2 else ey - hang_h / 2
            if k > 0:
                y_den = max(y_den, (cy + nh / 2) + (dich - (cy + nh / 2)) * k)
        cv.drawLine(cx, cy + nh / 2, cx, y_den, p_net(B["vien"] if B["tong"] != "toi" else B["mo"], lw, 0.9))
    for (i, ex, ey, ben) in cot:
        ti = ts[i]
        kn = e_out(tien(t, ti, 0.3))
        if kn <= 0:
            continue
        mn = B["nhan"] if i % 2 == 0 else B["nhan2"]
        (im, (iw, ih)) = o[i]
        bx0, bx1 = ex - cot_w / 2, ex + cot_w / 2
        by0, by1 = ey - hang_h / 2, ey + hang_h / 2
        if ngang:
            sx = cx - nw / 2 if ben == 0 else cx + nw / 2
            dx_ = bx1 if ben == 0 else bx0
            pa = skia.Path(); pa.moveTo(sx, cy)
            mx = (sx + dx_) / 2
            pa.cubicTo(mx, cy, mx, ey, dx_, ey)
            duong_cat(cv, pa, kn, p_net(mn, lw))
        elif ben != 2:
            dx_ = bx1 if ben == 0 else bx0
            duong_cat(cv, duong_gap([(cx, ey), (dx_, ey)]), kn, p_net(mn, lw))
            cv.drawCircle(cx, ey, 9 * u * kn, p_to(mn))
        kt = tien(t, ti + 0.18, 0.38)
        if kt <= 0:
            continue
        s = 0.86 + 0.14 * e_back(kt)
        a = e_out(kt * 1.6)
        cv.save(); cv.translate(ex, ey); cv.scale(s, s); cv.translate(-ex, -ey)
        the_noi(cv, B, bx0, by0, bx1, by1, 26 * u, u, al=a)
        cv.drawRRect(rr(bx0 + 18 * u, ey - ih / 2, bx0 + 26 * u, ey + ih / 2, 4 * u), p_to(mn, a))
        dat(cv, im, bx0 + pad_x + 22 * u, ey, "ml", a)
        cv.restore()
    k0 = tien(t, 0, 0.45)                                 # nút tâm vẽ sau cùng (đè gốc nhánh)
    s0 = 0.6 + 0.4 * e_back(k0)
    cv.save(); cv.translate(cx, cy); cv.scale(s0, s0); cv.translate(-cx, -cy)
    bong(cv, cx - nw / 2, cy - nh / 2, cx + nw / 2, cy + nh / 2, nh / 2, 40 * u, 0.45 * e_out(k0), dy=12 * u, mau=B["nhan"] if B["tong"] == "toi" else None)
    hop(cv, cx - nw / 2, cy - nh / 2, cx + nw / 2, cy + nh / 2, nh / 2, B["nhan"], e_out(k0 * 2))
    dat(cv, im_t, cx, cy, "mc", e_out(k0 * 2))
    cv.restore()
    return ra(surf, duc)


# ---------------------------------------------------------------- checklist
@dang_ky(**_the_canh(
    id="mau.checklist", ten="Checklist tích từng ý",
    mo_ta="Danh sách việc/tiêu chí: mỗi dòng hiện ra rồi được tích (✓ / số / ✗) đúng lúc nói, dòng cũ dịu đi để mắt theo dòng mới.",
    hop_nghia=["liệt kê", "tiêu chí", "việc cần làm", "điều kiện", "đã xong", "kiểm tra"],
    tham_so={"muc": "list: \"chữ\" | [chữ, giây] (≤ 7)", "dau": "tich | so | x (tich)", "nhip": "giây giữa 2 dòng (0.7)",
             "bat_dau": "giây dòng đầu (0.4)", "tre_tich": "giây từ lúc dòng hiện tới lúc tích (0.3)", "diu_cu": "làm dịu dòng cũ true/false (true)"},
    mac_dinh={"dau": "tich", "nhip": 0.7, "bat_dau": 0.4, "tre_tich": 0.3, "diu_cu": True}, sfx_goi_y=["tích", "pop nhẹ", "click"],
    vi_du={"tieu_de": "Trước khi đăng video", "muc": ["Hook 3 giây đầu", "Phụ đề rõ, đúng dấu", "Nhạc nền nhỏ hơn giọng", "Kêu gọi hành động cuối"],
           "nhip": 0.45}))
def checklist(t, dur, W, H, c, p):
    surf, cv, B, (X0, Y0, X1, Y1, u0), duc = _bat_dau(c, p, W, H, t, dur)
    ds = [muc(x) for x in (p.get("muc") or [])][:7]
    ts = lich(len(ds), dur, p.get("nhip", 0.7), p.get("bat_dau", 0.4), [d.get("t") for d in ds])
    font = p.get("font") or "nhan"

    def bo(u):
        o_w = 72 * u
        rong = X1 - X0 - o_w - 3 * 36 * u
        co = min([vua(c, d.get("chu", ""), 56 * u, rong, 1, 2, co_min=32 * u, vai=font) for d in ds] or [56 * u])
        ims = [anh_chu(c, d.get("chu", ""), co, B["chu"], vai=font, rong=rong) for d in ds]
        hh = [max(kich(im)[1] + 70 * u, o_w + 64 * u) for im in ims]
        khe = 26 * u
        can = sum(hh) + khe * max(0, len(hh) - 1) + cao_tieu_de(c, p, X0, X1, u)
        return dict(o_w=o_w, rong=rong, co=co, ims=ims, hh=hh, khe=khe, can=can)
    kh = khoa_p("checklist", W, H, p, B)
    u = phong(kh, u0, lambda x: nho(kh, x, bo)["can"], Y1 - Y0, p)
    L = nho(kh, u, bo)
    o_w, rong, co, ims, hh, khe = (L[k] for k in ("o_w", "rong", "co", "ims", "hh", "khe"))
    ims_m = [anh_chu(c, d.get("chu", ""), co, B["phu"], vai=font, rong=rong) for d in ds]
    y = Y0 + max(0, (Y1 - Y0 - L["can"]) * 0.42)
    y = ve_tieu_de(cv, c, p, B, X0, X1, y, u, t)
    moi = max([i for i, ti in enumerate(ts) if t >= ti] or [-1])
    dau = str(p.get("dau") or "tich")
    tre = float(p.get("tre_tich", 0.3))
    for i, d in enumerate(ds):
        k = tien(t, ts[i], 0.35)
        h = hh[i]
        if k > 0:
            a = e_out(k)
            yy = y + (1 - a) * 28 * u
            the_noi(cv, B, X0, yy, X1, yy + h, 28 * u, u, al=a, mau=B["the2"] if i == moi else B["the"])
            if i == moi:
                cv.drawRRect(rr(X0, yy + 22 * u, X0 + 7 * u, yy + h - 22 * u, 3 * u), p_to(B["nhan"], a))
            bx, by = X0 + 36 * u, yy + h / 2
            kt = tien(t, ts[i] + tre, 0.3)
            o = (bx, by - o_w / 2, bx + o_w, by + o_w / 2)
            mau_o = B["nhan"] if dau != "x" else B["mo"]
            if kt > 0:
                hop(cv, *o, 18 * u, mau_o, a * e_out(kt * 1.5))
            hop(cv, *o, 18 * u, "#00000000", a, mau_o, 4 * u)
            if kt > 0:
                if dau == "so":
                    imn = anh_chu(c, str(i + 1), o_w * 0.5, B["tren_nhan"], vai=p.get("font_tieu_de") or "tieu_de")
                    dat(cv, imn, bx + o_w / 2, by, "mc", a * e_out(kt * 2))
                elif dau == "x":
                    dau_x(cv, bx + o_w / 2, by, o_w * 0.8, chu_tren(mau_o), e_io(kt))
                else:
                    dau_tich(cv, bx + o_w / 2, by, o_w * 0.8, B["tren_nhan"], e_io(kt))
            diu = bool(p.get("diu_cu", True)) and i != moi
            dat(cv, ims_m[i] if diu else ims[i], bx + o_w + 36 * u, by, "ml", a)
        y += h + khe
    return ra(surf, duc)


# ---------------------------------------------------------------- biểu đồ cột
@dang_ky(**_the_canh(
    id="mau.bieu-do-cot", ten="Biểu đồ cột mọc dần",
    mo_ta="So sánh các con số THẬT trong lời: cột mọc lên lần lượt, số chạy tới giá trị; cột cao nhất tô màu nhấn.",
    hop_nghia=["số liệu", "so sánh số", "tăng trưởng", "doanh thu", "kết quả", "thống kê"],
    tham_so={"cot": "list [nhãn, giá trị, giây?] (≤ 7) — số phải có trong lời", "don_vi": "hậu tố số (%, tr, k…)",
             "noi_bat": "chỉ số cột tô nhấn (mặc định cột cao nhất)", "nhip": "giây giữa 2 cột (0.45)", "bat_dau": "giây cột đầu (0.4)",
             "moc": "giây cột mọc (0.8)", "luoi": "vạch lưới ngang true/false (true)"},
    mac_dinh={"don_vi": "", "nhip": 0.45, "bat_dau": 0.4, "moc": 0.8, "luoi": True}, sfx_goi_y=["whoosh lên", "tick đếm số", "pop nhẹ"],
    vi_du={"tieu_de": "Doanh thu 4 tháng", "nhan_tren": "Triệu đồng", "cot": [["Tháng 1", 12], ["Tháng 2", 18], ["Tháng 3", 27], ["Tháng 4", 45]],
           "nhip": 0.3, "moc": 0.6}))
def bieu_do_cot(t, dur, W, H, c, p):
    surf, cv, B, (X0, Y0, X1, Y1, u), duc = _bat_dau(c, p, W, H, t, dur)
    ds = [muc(x, ("nhan", "gia_tri", "t")) for x in (p.get("cot") or [])][:7]
    y = ve_tieu_de(cv, c, p, B, X0, X1, Y0, u, t)
    if not ds:
        return ra(surf, duc)
    n = len(ds)
    vals = [so(d.get("gia_tri")) for d in ds]
    vmax = max(vals + [1e-9])
    ts = lich(n, dur, p.get("nhip", 0.45), p.get("bat_dau", 0.4), [d.get("t") for d in ds], cuoi=0.55)
    nb = p.get("noi_bat")
    nb = int(nb) if nb is not None else vals.index(vmax)
    font = p.get("font") or "nhan"
    slot = (X1 - X0) / n
    bw = min(slot * 0.62, 190 * u)
    co_nhan = min([vua_co(c, str(d.get("nhan", "")), 40 * u, slot * 0.92, 2, co_min=24 * u, vai=font) for d in ds])
    ims_n = [anh_chu(c, str(d.get("nhan", "")), co_nhan, B["phu"], vai=font, rong=slot * 0.92, can="giua") for d in ds]
    nhan_h = max(kich(im)[1] for im in ims_n)
    co_so = min(58 * u, slot * 0.36)
    yb = Y1 - nhan_h - 34 * u
    yt = y + co_so * 1.9
    if yb - yt < 120 * u:
        yt = yb - 120 * u
    # lưới
    if p.get("luoi", True):
        for k in range(1, 4):
            yy = yb - (yb - yt) * k / 3
            cv.drawLine(X0, yy, X1, yy, p_net(B["vien"], max(1, 2 * u), 0.9, False))
    cv.drawLine(X0, yb, X1, yb, p_net(B["mo"], max(1.5, 3 * u), 0.8))
    moc = float(p.get("moc", 0.8))
    don_vi = str(p.get("don_vi") or "")
    for i, d in enumerate(ds):
        k = e_io(tien(t, ts[i], moc))
        cx = X0 + (i + 0.5) * slot
        dat(cv, ims_n[i], cx, yb + 20 * u, "tc", e_out(tien(t, ts[i] - 0.2, 0.3)))
        if k <= 0:
            continue
        h = (yb - yt) * max(vals[i], 0) / vmax * k
        mau = B["nhan"] if i == nb else (B["nhan2"] if B["tong"] != "sang" and vals[i] == sorted(vals)[-2] and n > 2 else B["mo"])
        if h > 1:
            r = min(18 * u, bw / 2)
            cv.save(); cv.clipRect(skia.Rect.MakeLTRB(cx - bw, yt - 10 * u - r, cx + bw, yb))
            if i == nb:
                bong(cv, cx - bw / 2, yb - h, cx + bw / 2, yb + r, r, 40 * u, 0.35, mau=B["nhan"] if B["tong"] == "toi" else None)
            pnt = p_to(mau)
            pnt.setShader(skia.GradientShader.MakeLinear([skia.Point(0, yb - h), skia.Point(0, yb)], [sk(mau), sk(tron(mau, B["nen"], 0.25))]))
            cv.drawRRect(rr(cx - bw / 2, yb - h, cx + bw / 2, yb + r, r), pnt)
            cv.restore()
        v = vals[i] * k
        txt = so_vn(v, le_cua(d.get("gia_tri"))) + don_vi
        ims = anh_chu(c, txt, co_so, B["chu"] if i != nb else B["nhan"], vai=p.get("font_tieu_de") or "tieu_de")
        dat(cv, ims, cx, yb - h - 14 * u, "bc", e_out(k * 3))
    return ra(surf, duc)


# ---------------------------------------------------------------- bảng so sánh A/B
@dang_ky(**_the_canh(
    id="mau.bang-so-sanh", ten="Bảng so sánh A / B (sai–đúng, cũ–mới)",
    mo_ta="Hai cột cạnh nhau: bên yếu có dấu ✗ dịu màu, bên thắng ✓ sáng màu nhấn — từng hàng hiện theo lời.",
    hop_nghia=["so sánh", "trước sau", "sai đúng", "cũ mới", "đối thủ", "lựa chọn"],
    tham_so={"a": "tên cột trái", "b": "tên cột phải", "dong": "list [chữ trái, chữ phải, giây?] (≤ 6)", "thang": "a | b — cột thắng (b)",
             "nhip": "giây giữa 2 hàng (0.6)", "bat_dau": "giây hàng đầu (0.5)"},
    mac_dinh={"a": "Trước", "b": "Sau", "thang": "b", "nhip": 0.6, "bat_dau": 0.5}, sfx_goi_y=["pop nhẹ", "tích", "swoosh"],
    vi_du={"tieu_de": "Tự làm hay dùng Studio?", "a": "Tự dựng tay", "b": "Có Studio", "dong": [["3 tiếng một video", "10 phút một video"],
           ["Phụ đề gõ từng chữ", "Phụ đề tự khớp giọng"], ["Dễ sai dấu tiếng Việt", "Dấu chuẩn, đọc rõ"]], "nhip": 0.45}))
def bang_so_sanh(t, dur, W, H, c, p):
    surf, cv, B, (X0, Y0, X1, Y1, u0), duc = _bat_dau(c, p, W, H, t, dur)
    ds = [muc(x, ("trai", "phai", "t")) for x in (p.get("dong") or [])][:6]
    ts = lich(len(ds), dur, p.get("nhip", 0.6), p.get("bat_dau", 0.5), [d.get("t") for d in ds])
    font = p.get("font") or "nhan"
    thang_b = str(p.get("thang", "b")) != "a"

    def bo(u):
        khe = 24 * u
        cw = (X1 - X0 - khe) / 2
        pad = 30 * u
        dau_w = 48 * u
        rong = cw - pad * 2 - dau_w - 18 * u
        co = min([vua(c, str(d.get(k) or ""), 44 * u, rong, 2, 3, co_min=26 * u, vai="than") for d in ds for k in ("trai", "phai")] or [44 * u])
        hang = []
        for d in ds:
            ia = anh_chu(c, str(d.get("trai") or ""), co, B["phu"] if thang_b else B["chu"], vai="than", rong=rong)
            ib = anh_chu(c, str(d.get("phai") or ""), co, B["chu"] if thang_b else B["phu"], vai="than", rong=rong)
            hang.append((ia, ib, max(kich(ia)[1], kich(ib)[1], dau_w) + 50 * u))
        co_h = min(vua(c, str(p.get(k) or ""), 52 * u, cw - 2 * pad, 1, 2, vai=font) for k in ("a", "b"))
        iha = anh_chu(c, str(p.get("a") or ""), co_h, B["phu"] if thang_b else B["nhan"], vai=font, rong=cw - 2 * pad, can="giua")
        ihb = anh_chu(c, str(p.get("b") or ""), co_h, B["nhan"] if thang_b else B["phu"], vai=font, rong=cw - 2 * pad, can="giua")
        head_h = max(kich(iha)[1], kich(ihb)[1]) + 64 * u
        cao = head_h + sum(h for _, _, h in hang) + 34 * u
        return dict(khe=khe, cw=cw, pad=pad, dau_w=dau_w, hang=hang, iha=iha, ihb=ihb, head_h=head_h, cao=cao,
                    can=cao + cao_tieu_de(c, p, X0, X1, u))
    kh = khoa_p("so-sanh", W, H, p, B)
    u = phong(kh, u0, lambda x: nho(kh, x, bo)["can"], Y1 - Y0, p)
    L = nho(kh, u, bo)
    khe, cw, pad, dau_w, hang, iha, ihb, head_h, cao = (L[k] for k in ("khe", "cw", "pad", "dau_w", "hang", "iha", "ihb", "head_h", "cao"))
    y = Y0 + max(0, (Y1 - Y0 - L["can"]) * 0.42)
    y = ve_tieu_de(cv, c, p, B, X0, X1, y, u, t)
    for j in (0, 1):
        x0 = X0 + j * (cw + khe)
        la_thang = (j == 1) == thang_b
        mau = tron(B["the"], B["nhan"], 0.14) if la_thang else B["the"]
        the_noi(cv, B, x0, y, x0 + cw, y + cao, 32 * u, u, mau=mau)
        if la_thang:
            hop(cv, x0, y, x0 + cw, y + cao, 32 * u, "#00000000", 1, B["nhan"], 3 * u, 0.85)
        dat(cv, iha if j == 0 else ihb, x0 + cw / 2, y + head_h / 2, "mc")
        cv.drawLine(x0 + pad, y + head_h, x0 + cw - pad, y + head_h, p_net(B["vien"], max(1, 2 * u), 1, False))
    yy = y + head_h + 17 * u
    for i, (ia, ib, h) in enumerate(hang):
        k = tien(t, ts[i], 0.35)
        if k > 0:
            a = e_out(k)
            for j, im in ((0, ia), (1, ib)):
                x0 = X0 + j * (cw + khe)
                la_thang = (j == 1) == thang_b
                mx, my = x0 + pad + dau_w / 2, yy + h / 2
                if la_thang:
                    cv.drawCircle(mx, my, dau_w / 2, p_to(B["nhan"], a))
                    dau_tich(cv, mx, my, dau_w * 0.62, B["tren_nhan"], e_io(tien(t, ts[i] + 0.1, 0.3)))
                else:
                    cv.drawCircle(mx, my, dau_w / 2, p_to(B["mo"], a * 0.35))
                    dau_x(cv, mx, my, dau_w * 0.6, B["mo"], e_io(tien(t, ts[i], 0.3)))
                dat(cv, im, x0 + pad + dau_w + 18 * u, my + (1 - a) * 14 * u, "ml", a)
        yy += h
    return ra(surf, duc)


# ---------------------------------------------------------------- các bước
@dang_ky(**_the_canh(
    id="mau.cac-buoc", ten="Các bước nối nhau",
    mo_ta="Quy trình nhiều bước dọc: từng bước sáng lên, đường nối chạy tới bước kế — người xem biết đang ở bước nào.",
    hop_nghia=["quy trình", "hướng dẫn", "bước", "cách làm", "thứ tự", "lộ trình"],
    tham_so={"buoc": "list: \"chữ\" | [chữ, giây] | {chu, mo_ta, t} (≤ 6)", "nhip": "giây giữa 2 bước (0.8)", "bat_dau": "giây bước đầu (0.4)"},
    mac_dinh={"nhip": 0.8, "bat_dau": 0.4}, sfx_goi_y=["pop nhẹ", "click", "whoosh nhẹ"],
    vi_du={"tieu_de": "Dựng video trong 3 bước", "buoc": [{"chu": "Thả video quay thô", "mo_ta": "Máy tự cắt khoảng lặng"},
           {"chu": "Gõ yêu cầu", "mo_ta": "Ví dụ: phụ đề vàng, nhạc vui"}, {"chu": "Xem lại và xuất", "mo_ta": "Sửa nhanh nếu cần"}], "nhip": 0.6}))
def cac_buoc(t, dur, W, H, c, p):
    surf, cv, B, (X0, Y0, X1, Y1, u0), duc = _bat_dau(c, p, W, H, t, dur)
    ds = [muc(x) for x in (p.get("buoc") or [])][:6]
    ts = lich(len(ds), dur, p.get("nhip", 0.8), p.get("bat_dau", 0.4), [d.get("t") for d in ds])
    font = p.get("font") or "nhan"

    def bo(u):
        r = 42 * u
        xg = X0 + r + 4 * u
        cx0 = xg + r + 30 * u
        pad = 30 * u
        rong = X1 - cx0 - 2 * pad
        co = min([vua(c, str(d.get("chu", "")), 54 * u, rong, 1, 2, co_min=32 * u, vai=font) for d in ds] or [54 * u])
        co_m = co * 0.7
        khoi = []
        for d in ds:
            ic = anh_chu(c, str(d.get("chu", "")), co, B["chu"], vai=font, rong=rong)
            im_m = anh_chu(c, str(d.get("mo_ta")), co_m, B["phu"], vai="than", rong=rong) if d.get("mo_ta") else None
            h = kich(ic)[1] + ((kich(im_m)[1] + 8 * u) if im_m else 0) + 2 * pad
            khoi.append((ic, im_m, max(h, 2 * r + 24 * u)))
        khe = 36 * u
        can = sum(h for *_, h in khoi) + khe * max(0, len(khoi) - 1) + cao_tieu_de(c, p, X0, X1, u)
        return dict(r=r, xg=xg, cx0=cx0, pad=pad, khoi=khoi, khe=khe, can=can)
    kh = khoa_p("cac-buoc", W, H, p, B)
    u = phong(kh, u0, lambda x: nho(kh, x, bo)["can"], Y1 - Y0, p)
    L = nho(kh, u, bo)
    r, xg, cx0, pad, khoi, khe = (L[k] for k in ("r", "xg", "cx0", "pad", "khoi", "khe"))
    y = Y0 + max(0, (Y1 - Y0 - L["can"]) * 0.42)
    y = ve_tieu_de(cv, c, p, B, X0, X1, y, u, t)
    tam = []
    yy = y
    for (_, _, h) in khoi:
        tam.append(yy + h / 2); yy += h + khe
    lw = max(2, 6 * u)
    for i in range(len(khoi) - 1):
        cv.drawLine(xg, tam[i] + r, xg, tam[i + 1] - r, p_net(B["vien"], lw))
        k = e_io(tien(t, ts[i + 1] - 0.35, 0.35))
        if k > 0:
            cv.drawLine(xg, tam[i] + r, xg, tam[i] + r + (tam[i + 1] - tam[i] - 2 * r) * k, p_net(B["nhan"], lw))
    hien = max([i for i, ti in enumerate(ts) if t >= ti] or [-1])
    for i, (ic, im_m, h) in enumerate(khoi):
        on = t >= ts[i]
        k = tien(t, ts[i], 0.35)
        cy = tam[i]
        a_the = 0.45 + 0.55 * e_out(k)
        y0 = cy - h / 2
        dx = (1 - e_out(k)) * 24 * u if on else 0
        the_noi(cv, B, cx0 + dx, y0, X1 + dx, y0 + h, 26 * u, u, al=a_the, mau=B["the2"] if i == hien else B["the"])
        if i == hien:
            cv.drawRRect(rr(cx0 + dx, y0 + 20 * u, cx0 + dx + 7 * u, y0 + h - 20 * u, 3 * u), p_to(B["nhan"]))
            v = (t - ts[i]) % 1.4 / 1.4
            cv.drawCircle(xg, cy, r * (1 + 0.5 * e_out(v)), p_net(B["nhan"], 3 * u, 0.6 * (1 - v)))
        rr_ = r * (1 + 0.12 * math.sin(math.pi * k)) if on else r
        cv.drawCircle(xg, cy, rr_, p_to(B["nhan"] if on else B["the"]))
        cv.drawCircle(xg, cy, rr_ - 1.5 * u, p_net(B["nhan"] if on else B["vien"], 3 * u))
        isn = anh_chu(c, str(i + 1), 40 * u, B["tren_nhan"] if on else B["phu"], vai=p.get("font_tieu_de") or "tieu_de")
        dat(cv, isn, xg, cy, "mc")
        al = 0.4 + 0.6 * e_out(k)
        h_chu = kich(ic)[1] + ((kich(im_m)[1] + 8 * u) if im_m else 0)
        b = dat(cv, ic, cx0 + pad + dx, cy - h_chu / 2, "tl", al)
        if im_m:
            dat(cv, im_m, b[0], b[3] + 8 * u, "tl", al)
    return ra(surf, duc)


# ---------------------------------------------------------------- biểu đồ tròn
@dang_ky(**_the_canh(
    id="mau.bieu-do-tron", ten="Biểu đồ tròn (vành khuyên) quét dần",
    mo_ta="Tỉ lệ các phần của một tổng: vành khuyên quét từng phần, giữa hiện % phần nổi bật đếm lên, chú thích kèm %.",
    hop_nghia=["tỉ lệ", "phần trăm", "cơ cấu", "chiếm bao nhiêu", "phân bổ", "thị phần"],
    tham_so={"phan": "list [nhãn, giá trị, màu?] (≤ 6) — số có trong lời", "noi_bat": "chỉ số phần hiện ở giữa (0)",
             "nhan_giua": "chữ nhỏ dưới số giữa (mặc định nhãn phần nổi bật)", "do_day": "độ dày vành / bán kính (0.3)",
             "quet": "giây quét hết vành (1.2)", "bat_dau": "giây bắt đầu quét (0.3)", "le": "số lẻ của % (0)"},
    mac_dinh={"noi_bat": 0, "do_day": 0.3, "quet": 1.2, "bat_dau": 0.3, "le": 0}, sfx_goi_y=["whoosh tròn", "tick đếm số"],
    vi_du={"tieu_de": "Khách đến từ đâu?", "phan": [["TikTok", 62], ["Facebook", 23], ["Khách cũ giới thiệu", 15]], "nhan_giua": "từ TikTok"}))
def bieu_do_tron(t, dur, W, H, c, p):
    surf, cv, B, (X0, Y0, X1, Y1, u), duc = _bat_dau(c, p, W, H, t, dur)
    ds = [muc(x, ("nhan", "gia_tri", "mau")) for x in (p.get("phan") or [])][:6]
    y = ve_tieu_de(cv, c, p, B, X0, X1, Y0, u, t)
    if not ds:
        return ra(surf, duc)
    vals = [max(0.0, so(d.get("gia_tri"))) for d in ds]
    tong = sum(vals) or 1.0
    mau = day_mau(B, len(ds))
    mau = [c.mau(d["mau"]) if d.get("mau") else mau[i] for i, d in enumerate(ds)]
    font = p.get("font") or "nhan"
    ngang = (X1 - X0) / max(1, Y1 - y) > 1.15
    # chú thích
    le_ = int(p.get("le", 0))
    hang = []
    rong_cc = (X1 - X0) * (0.48 if ngang else 1.0) - 60 * u
    co_cc = min(vua(c, str(d.get("nhan", "")), (56 if ngang else 46) * u, rong_cc - 150 * u, 1, 2, co_min=26 * u, vai=font) for d in ds)
    for i, d in enumerate(ds):
        hang.append((anh_chu(c, str(d.get("nhan", "")), co_cc, B["chu"], vai=font, rong=rong_cc - 150 * u),
                     anh_chu(c, so_vn(vals[i] / tong * 100, le_) + "%", co_cc, B["phu"], vai=font)))
    cc_h = sum(max(kich(a)[1], co_cc) + 34 * u for a, _ in hang)
    if ngang:
        R = min((X1 - X0) * 0.24, (Y1 - y) * 0.46)
        cx, cy = X0 + (X1 - X0) * 0.26, (y + Y1) / 2
        lx0, ly = X0 + (X1 - X0) * 0.52, cy - cc_h / 2
    else:
        R = min((X1 - X0) * 0.39, (Y1 - y - cc_h - 70 * u) * 0.5)
        tong_h = 2 * R + 70 * u + cc_h
        top = y + max(0, (Y1 - y - tong_h) * 0.4)
        cx, cy = (X0 + X1) / 2, top + R
        lx0, ly = X0 + 30 * u, top + 2 * R + 70 * u
    day = R * float(p.get("do_day", 0.3))
    rm = R - day / 2
    oval = skia.Rect.MakeLTRB(cx - rm, cy - rm, cx + rm, cy + rm)
    cv.drawOval(oval, p_net(B["vien"], day, 0.7, False))
    k = e_io(tien(t, float(p.get("bat_dau", 0.3)), float(p.get("quet", 1.2))))
    goc = -90.0
    het = 360.0 * k
    khe = min(2.5, 360 * 0.004) if len(ds) > 1 else 0
    for i, v in enumerate(vals):
        sw = 360.0 * v / tong
        a0 = goc + khe / 2
        lam = min(sw - khe, het - (goc + 90))
        if lam > 0:
            pn = p_net(mau[i], day * (1.0 if i != int(p.get("noi_bat", 0)) else 1.12), 1, False)
            cv.drawArc(oval, a0, lam, False, pn)
        goc += sw
    nb = int(p.get("noi_bat", 0)) % len(ds)
    pct = vals[nb] / tong * 100 * kep(k / max(1e-3, sum(vals[:nb + 1]) / tong))
    im_so = anh_chu(c, so_vn(pct, le_) + "%", R * 0.42, mau[nb] if B["tong"] != "sang" else B["chu"], vai=p.get("font_tieu_de") or "tieu_de")
    sw_, sh_ = kich(im_so)
    ng = str(p.get("nhan_giua") or ds[nb].get("nhan") or "")
    im_ng = anh_chu(c, ng, vua_co(c, ng, R * 0.15, (rm - day / 2) * 1.6, 2, vai=font), B["phu"], vai=font, rong=(rm - day / 2) * 1.6, can="giua")
    gh = sh_ + kich(im_ng)[1]
    dat(cv, im_so, cx, cy - gh / 2, "tc")
    dat(cv, im_ng, cx, cy - gh / 2 + sh_, "tc")
    tich = 0.0
    for i, (ia, ib) in enumerate(hang):
        tich += vals[i] / tong
        kk = e_out(tien(k, (tich - vals[i] / tong) * 0.9, 0.15)) if k < 1 else 1.0
        h = max(kich(ia)[1], co_cc) + 34 * u
        my = ly + h / 2
        cv.drawRRect(rr(lx0, my - 13 * u, lx0 + 26 * u, my + 13 * u, 8 * u), p_to(mau[i], kk))
        dat(cv, ia, lx0 + 48 * u, my, "ml", kk)
        dat(cv, ib, lx0 + rong_cc + 30 * u, my, "mr", kk)
        ly += h
    return ra(surf, duc)


# ---------------------------------------------------------------- biểu đồ đường
def _muot(pts):
    """đường cong mượt ĐƠN ĐIỆU qua các điểm (Fritsch–Carlson): không vồng quá số liệu thật giữa hai mốc"""
    n = len(pts)
    xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
    d = [(ys[i + 1] - ys[i]) / max(1e-9, xs[i + 1] - xs[i]) for i in range(n - 1)]
    m = [d[0]] + [((d[i - 1] + d[i]) / 2 if d[i - 1] * d[i] > 0 else 0.0) for i in range(1, n - 1)] + [d[-1]]
    for i in range(n - 1):
        if abs(d[i]) < 1e-12:
            m[i] = m[i + 1] = 0.0
            continue
        a_, b_ = m[i] / d[i], m[i + 1] / d[i]
        s_ = a_ * a_ + b_ * b_
        if s_ > 9:
            tau = 3 / math.sqrt(s_)
            m[i] = tau * a_ * d[i]; m[i + 1] = tau * b_ * d[i]
    pa = skia.Path(); pa.moveTo(xs[0], ys[0])
    for i in range(n - 1):
        h = xs[i + 1] - xs[i]
        pa.cubicTo(xs[i] + h / 3, ys[i] + m[i] * h / 3, xs[i + 1] - h / 3, ys[i + 1] - m[i + 1] * h / 3, xs[i + 1], ys[i + 1])
    return pa


def _vach_dep(vmin, vmax, n=4):
    span = max(vmax - vmin, 1e-9)
    buoc = 10 ** math.floor(math.log10(span / n))
    for m in (1, 2, 2.5, 5, 10):
        if span / (buoc * m) <= n:
            buoc *= m; break
    a = math.floor(vmin / buoc) * buoc
    ra_ = []
    v = a
    while True:
        ra_.append(v)
        if v >= vmax - 1e-9:
            break
        v += buoc
    return ra_


@dang_ky(**_the_canh(
    id="mau.bieu-do-duong", ten="Biểu đồ đường vẽ dần",
    mo_ta="Xu hướng theo thời gian: đường vẽ dần qua các mốc, vùng dưới đường tô mờ, nhãn số chạy theo đầu đường.",
    hop_nghia=["tăng trưởng", "xu hướng", "theo thời gian", "lượt xem", "doanh số tăng", "biến động"],
    tham_so={"diem": "list [nhãn trục, giá trị] (≥ 2, ≤ 12) — số có trong lời", "don_vi": "hậu tố số", "ve_trong": "giây vẽ hết đường (1.6)",
             "bat_dau": "giây bắt đầu (0.3)", "muot": "đường cong mượt true/false (true)", "tu_0": "trục dọc bắt đầu từ 0 (true)"},
    mac_dinh={"don_vi": "", "ve_trong": 1.6, "bat_dau": 0.3, "muot": True, "tu_0": True}, sfx_goi_y=["whoosh dài", "tick đếm số"],
    vi_du={"tieu_de": "Lượt xem sau khi đổi cách dựng", "don_vi": "k", "diem": [["T1", 8], ["T2", 11], ["T3", 9], ["T4", 24], ["T5", 41], ["T6", 68]],
           "ve_trong": 1.4}))
def bieu_do_duong(t, dur, W, H, c, p):
    surf, cv, B, (X0, Y0, X1, Y1, u), duc = _bat_dau(c, p, W, H, t, dur)
    ds = [muc(x, ("nhan", "gia_tri")) for x in (p.get("diem") or [])][:12]
    y = ve_tieu_de(cv, c, p, B, X0, X1, Y0, u, t)
    if len(ds) < 2:
        return ra(surf, duc)
    vals = [so(d.get("gia_tri")) for d in ds]
    font = p.get("font") or "nhan"
    don_vi = str(p.get("don_vi") or "")
    vmin = 0.0 if p.get("tu_0", True) else min(vals)
    vach = _vach_dep(vmin, max(vals))
    co_tr = 32 * u
    ims_v = [anh_chu(c, so_vn(v) + (don_vi if v else ""), co_tr, B["mo"], vai="than") for v in vach]
    trai = max(kich(im)[0] for im in ims_v) + 20 * u
    gx0, gx1 = X0 + trai, X1 - 30 * u
    nhan_h = co_tr * 1.6
    ngang = (X1 - X0) / max(1, Y1 - y) > 1.15
    gy1 = Y1 - nhan_h - 16 * u
    gy0 = y + 90 * u
    if not ngang:
        cao_max = (gx1 - gx0) * 1.15
        if gy1 - gy0 > cao_max:
            d_ = (gy1 - gy0 - cao_max) * 0.45
            gy0 += d_; gy1 = gy0 + cao_max
    lo, hi = vach[0], vach[-1]
    Y = lambda v: gy1 - (v - lo) / max(hi - lo, 1e-9) * (gy1 - gy0)
    for v, im in zip(vach, ims_v):
        yy = Y(v)
        cv.drawLine(gx0, yy, gx1, yy, p_net(B["vien"], max(1, 1.5 * u), 0.7, False))
        dat(cv, im, gx0 - 14 * u, yy, "mr")
    n = len(ds)
    xs = [gx0 + (gx1 - gx0) * i / (n - 1) for i in range(n)]
    pts = [(xs[i], Y(vals[i])) for i in range(n)]
    co_x = min(co_tr, (gx1 - gx0) / n * 0.3)
    for i, d in enumerate(ds):
        dat(cv, anh_chu(c, str(d.get("nhan", "")), co_x, B["phu"], vai=font), xs[i], gy1 + 16 * u, "tc")
    k = e_io(tien(t, float(p.get("bat_dau", 0.3)), float(p.get("ve_trong", 1.6))))
    pa = _muot(pts) if p.get("muot", True) else duong_gap(pts)
    xk = gx0 + (gx1 - gx0) * k
    if k > 0:
        vung_ = skia.Path(pa)
        vung_.lineTo(gx1, gy1); vung_.lineTo(gx0, gy1); vung_.close()
        pv = p_to(B["nhan"])
        pv.setShader(skia.GradientShader.MakeLinear([skia.Point(0, gy0), skia.Point(0, gy1)], [sk(B["nhan"], 0.42), sk(B["nhan"], 0.0)]))
        cv.save(); cv.clipRect(skia.Rect.MakeLTRB(gx0 - 2, gy0 - 50 * u, xk, gy1 + 1))
        cv.drawPath(vung_, pv)
        cv.drawPath(pa, p_net(B["nhan"], 7 * u))
        cv.restore()
    # đầu đường: điểm tại x = xk
    seg = min(n - 2, int((xk - gx0) / max(1e-6, (gx1 - gx0) / (n - 1))))
    f = (xk - xs[seg]) / max(1e-6, xs[seg + 1] - xs[seg])
    v_dau = vals[seg] + (vals[seg + 1] - vals[seg]) * kep(f)
    for i in range(n):
        if xs[i] <= xk + 0.5 and k > 0:
            cv.drawCircle(pts[i][0], pts[i][1], 9 * u, p_to(B["nen"] if B["tong"] != "kinh" else B["toi"]))
            cv.drawCircle(pts[i][0], pts[i][1], 9 * u, p_net(B["nhan"], 4 * u))
    if k > 0:
        # tìm y trên đường cong tại xk bằng đo đường
        yk = Y(v_dau)
        if p.get("muot", True):
            pm = skia.PathMeasure(pa, False); L = pm.getLength(); lo_, hi_ = 0.0, L
            for _ in range(18):
                m_ = (lo_ + hi_) / 2; pt = pm.getPosTan(m_)[0]
                if pt.x() < xk:
                    lo_ = m_
                else:
                    hi_ = m_
            yk = pm.getPosTan(lo_)[0].y()
        cv.drawCircle(xk, yk, 15 * u, p_to(B["nhan"]))
        cv.drawCircle(xk, yk, 26 * u, p_to(B["nhan"], 0.25))
        im = anh_chu(c, so_vn(v_dau, le_cua(ds[-1].get("gia_tri"))) + don_vi, 40 * u, B["tren_nhan"], vai=p.get("font_tieu_de") or "tieu_de")
        bw, bh = kich(im)
        bx = kep(xk, gx0 + bw / 2 + 20 * u, gx1 - bw / 2 - 20 * u)
        by1 = yk - 40 * u
        if by1 - bh - 24 * u < gy0 - 80 * u:
            by1 = yk + 40 * u + bh + 24 * u
        hop(cv, bx - bw / 2 - 20 * u, by1 - bh - 24 * u, bx + bw / 2 + 20 * u, by1, 16 * u, B["nhan"])
        dat(cv, im, bx, by1 - 12 * u, "bc")
    return ra(surf, duc)


# ---------------------------------------------------------------- dòng thời gian
@dang_ky(**_the_canh(
    id="mau.dong-thoi-gian", ten="Dòng thời gian (mốc so le)",
    mo_ta="Hành trình theo mốc thời gian: trục giữa chạy dần, mỗi mốc là một thẻ so le hai bên (dọc) hoặc trên/dưới (ngang).",
    hop_nghia=["hành trình", "lịch sử", "mốc thời gian", "câu chuyện", "từ ngày đầu", "năm"],
    tham_so={"moc": "list [mốc (năm/ngày), chữ, giây?] (≤ 6)", "nhip": "giây giữa 2 mốc (0.8)", "bat_dau": "giây mốc đầu (0.4)"},
    mac_dinh={"nhip": 0.8, "bat_dau": 0.4}, sfx_goi_y=["pop nhẹ", "whoosh nhẹ", "tick"],
    vi_du={"tieu_de": "Hành trình của shop", "moc": [["2021", "Bán online từ phòng trọ"], ["2023", "Mở cửa hàng đầu tiên"],
           ["2025", "10.000 khách quay lại"], ["2026", "Ra mắt thương hiệu riêng"]], "nhip": 0.5}))
def dong_thoi_gian(t, dur, W, H, c, p):
    surf, cv, B, (X0, Y0, X1, Y1, u0), duc = _bat_dau(c, p, W, H, t, dur)
    ds = [muc(x, ("moc", "chu", "t")) for x in (p.get("moc") or [])][:6]
    ts = lich(len(ds), dur, p.get("nhip", 0.8), p.get("bat_dau", 0.4), [d.get("t") for d in ds])
    if not ds:
        ve_tieu_de(cv, c, p, B, X0, X1, Y0, u0, t, "giua")
        return ra(surf, duc)
    font_td = p.get("font_tieu_de") or "tieu_de"
    n = len(ds)
    ngang = (X1 - X0) / max(1, Y1 - Y0) > 1.25
    hien = [tien(t, ti, 0.4) for ti in ts]
    if not ngang:
        cx = (X0 + X1) / 2

        def bo(u):
            cw = (X1 - X0) / 2 - 46 * u
            pad = 28 * u
            rong = cw - 2 * pad
            co = min(vua(c, str(d.get("chu", "")), 42 * u, rong, 2, 3, co_min=26 * u, vai="than") for d in ds)
            khoi = []
            for d in ds:
                im_m = anh_chu(c, str(d.get("moc", "")), co * 1.3, B["nhan"], vai=font_td)
                im_c = anh_chu(c, str(d.get("chu", "")), co, B["chu"], vai="than", rong=rong)
                khoi.append((im_m, im_c, kich(im_m)[1] + kich(im_c)[1] + 2 * pad + 6 * u))
            chong = 0.55                                      # thẻ so le chồng dọc lên nhau một phần
            khe = 30 * u
            can = sum(h * chong for *_, h in khoi[:-1]) + khoi[-1][2] + khe * (n - 1) + cao_tieu_de(c, p, X0, X1, u)
            return dict(cw=cw, pad=pad, khoi=khoi, chong=chong, khe=khe, can=can)
        kh = khoa_p("dtg", W, H, p, B)
        u = phong(kh, u0, lambda x: nho(kh, x, bo)["can"], Y1 - Y0, p)
        L = nho(kh, u, bo)
        cw, pad, khoi, chong, khe = (L[k] for k in ("cw", "pad", "khoi", "chong", "khe"))
        y = Y0 + max(0, (Y1 - Y0 - L["can"]) * 0.42)
        y = ve_tieu_de(cv, c, p, B, X0, X1, y, u, t, "giua")
        lw = max(2, 6 * u)
        tam = []
        yy = y
        for (_, _, h) in khoi:
            tam.append(yy + h / 2); yy += h * chong + khe
        cv.drawLine(cx, tam[0], cx, tam[-1], p_net(B["vien"], lw))
        moi = max([i for i in range(n) if hien[i] > 0] or [-1])
        if moi >= 0:
            yk = tam[0]
            if moi > 0:
                yk = tam[moi - 1] + (tam[moi] - tam[moi - 1]) * e_io(tien(t, ts[moi] - 0.3, 0.3))
            cv.drawLine(cx, tam[0], cx, yk, p_net(B["nhan"], lw))
        for i, (im_m, im_c, h) in enumerate(khoi):
            k = hien[i]
            on = k > 0
            cv.drawCircle(cx, tam[i], 15 * u, p_to(B["nhan"] if on else B["the"]))
            cv.drawCircle(cx, tam[i], 15 * u, p_net(B["nhan"] if on else B["vien"], 4 * u))
            if not on:
                continue
            a = e_out(k)
            trai = i % 2 == 0
            x0 = cx - 46 * u - cw if trai else cx + 46 * u
            dx = (1 - a) * 30 * u * (-1 if trai else 1)
            y0 = tam[i] - h / 2
            cv.drawLine(cx + (-15 if trai else 15) * u, tam[i], (x0 + cw if trai else x0) + dx, tam[i], p_net(B["nhan"], 3 * u, a))
            the_noi(cv, B, x0 + dx, y0, x0 + cw + dx, y0 + h, 24 * u, u, al=a)
            b = dat(cv, im_m, x0 + pad + dx, y0 + pad, "tl", a)
            dat(cv, im_c, x0 + pad + dx, b[3] + 6 * u, "tl", a)
    else:
        def bo(u):
            cw = min((X1 - X0) / max(1, (n + 1) // 2) * 0.9, (X1 - X0) / n * 1.75) if n > 1 else (X1 - X0) * 0.5
            pad = 24 * u
            rong = cw - 2 * pad
            co = min(vua(c, str(d.get("chu", "")), 38 * u, rong, 2, 3, co_min=22 * u, vai="than") for d in ds)
            khoi = []
            for d in ds:
                im_m = anh_chu(c, str(d.get("moc", "")), co * 1.3, B["nhan"], vai=font_td)
                im_c = anh_chu(c, str(d.get("chu", "")), co, B["chu"], vai="than", rong=rong, can="giua")
                khoi.append((im_m, im_c, kich(im_m)[1] + kich(im_c)[1] + 2 * pad + 6 * u))
            hmax = max(h for *_, h in khoi)
            can = 2 * (hmax + 50 * u) + cao_tieu_de(c, p, X0, X1, u)
            return dict(cw=cw, pad=pad, khoi=khoi, hmax=hmax, can=can)
        kh = khoa_p("dtg-n", W, H, p, B)
        u = phong(kh, u0, lambda x: nho(kh, x, bo)["can"], Y1 - Y0, p)
        L = nho(kh, u, bo)
        cw, pad, khoi = L["cw"], L["pad"], L["khoi"]
        y = Y0 + max(0, (Y1 - Y0 - L["can"]) * 0.42)
        y = ve_tieu_de(cv, c, p, B, X0, X1, y, u, t, "giua")
        lw = max(2, 6 * u)
        cy = y + L["hmax"] + 50 * u
        xs = [X0 + (X1 - X0) * (i + 0.5) / n for i in range(n)]
        cv.drawLine(X0, cy, X1, cy, p_net(B["vien"], lw))
        moi = max([i for i in range(n) if hien[i] > 0] or [-1])
        if moi >= 0:
            xk = xs[0]
            if moi > 0:
                xk = xs[moi - 1] + (xs[moi] - xs[moi - 1]) * e_io(tien(t, ts[moi] - 0.3, 0.3))
            cv.drawLine(X0, cy, xk, cy, p_net(B["nhan"], lw))
        for i, (im_m, im_c, h) in enumerate(khoi):
            on = hien[i] > 0
            cv.drawCircle(xs[i], cy, 14 * u, p_to(B["nhan"] if on else B["the"]))
            cv.drawCircle(xs[i], cy, 14 * u, p_net(B["nhan"] if on else B["vien"], 4 * u))
            if not on:
                continue
            a = e_out(hien[i])
            tren = i % 2 == 0
            y0 = cy - 50 * u - h if tren else cy + 50 * u
            dy = (1 - a) * 24 * u * (-1 if tren else 1)
            x0 = kep(xs[i] - cw / 2, X0, X1 - cw)
            cv.drawLine(xs[i], cy + (-14 if tren else 14) * u, xs[i], (y0 + h if tren else y0) + dy, p_net(B["nhan"], 3 * u, a))
            the_noi(cv, B, x0, y0 + dy, x0 + cw, y0 + h + dy, 22 * u, u, al=a)
            b = dat(cv, im_m, x0 + cw / 2, y0 + pad + dy, "tc", a)
            dat(cv, im_c, x0 + cw / 2, b[3] + 6 * u, "tc", a)
    return ra(surf, duc)
