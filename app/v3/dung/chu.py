# -*- coding: utf-8 -*-
"""Text engine bằng skia-python (skia.textlayout = SkParagraph + HarfBuzz): kerning thật, variable font (wght),
nhiều viền, nhiều bóng, gradient, nền pill, tách từ/ký tự với trạng thái riêng. Trả numpy RGBA thẳng (un-premultiplied).

Cách làm: xếp dòng tự làm (ngắt ở khoảng trắng, tránh mồ côi), MỖI TỪ (hoặc ký tự) là một Paragraph riêng → hộp
chính xác từng phần, kerning trong từ giữ nguyên. Mỗi phần vẽ 1 lần thành sprite premultiplied (bóng → viền dày→mỏng → fill)
rồi ghép với trạng thái riêng (opacity/scale/x/y). Supersampling 2× khi cỡ < 40 px.

kieu_dang (kd) các trường: font (đường dẫn .ttf/.otf hoặc vai tieu_de|phu_de|nhan|than|script), co (px), dam (100..900),
mau (#hex), hoa (bool), gian (em, vd -0.02), dong (hệ số dòng, vd 1.1), can (trai|giua|phai), rong_max (0..1 của W hoặc px>1),
vien [{"w","mau"}], bong [{"x","y","mo","mau"}], nen {"mau","dem":[x,y],"bo","vien":{"w","mau"}}, gradient {"mau":[...],"goc":deg,"diem":[0..1]},
mau_noi (màu từ đang nói — karaoke), nghieng (độ, skew).
"""
import math, os, re, threading, unicodedata, weakref
from collections import OrderedDict
import numpy as np
import skia

try:
    import chung
except ImportError:  # chạy từ thư mục khác
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import chung

tl = skia.textlayout


# ---------------------------------------------------------------- lỗi thiếu trường quyết định (1.2.21) ----
class ThieuTruong(RuntimeError):
    """thiếu trường quyết định (AI/kênh phải ghi) — máy KHÔNG tự điền. .loi() → dict {"duong","ma":"thieu_truong",...} cho kiem.json["loi"].
    Định nghĩa ở đây (mô-đun thấp nhất của engine chữ); dung/lop.py, dung/anim.py dùng chung lớp này."""

    def __init__(self, duong, goi_y="", lop=None):
        self.duong, self.ma, self.goi_y, self.lop = str(duong), "thieu_truong", goi_y, lop
        super().__init__("thieu_truong: %s%s" % (self.duong, (" — " + goi_y) if goi_y else ""))

    def __reduce__(self):                      # R4b 1.2.21: qua process pool (pickle) giữ nguyên duong/goi_y/lop — không thành "thieu_truong: thieu_truong: …"
        return (ThieuTruong, (self.duong, self.goi_y, self.lop))

    def loi(self):
        return {"id": "thieu_truong", "ma": "thieu_truong", "duong": self.duong, "lop": self.lop, "t": None,
                "mo_ta": "thiếu trường `%s`%s — ghi vào công thức hoặc quyet-dinh.json của kênh" % (self.duong, (" (" + self.goi_y + ")") if self.goi_y else "")}


# ---------------------------------------------------------------- cache ảnh có trần RAM (1.2.21) ----
_THIEU_ = object()


class CacheAnh:
    """cache dict-like có trần TỔNG (mọi CacheAnh cộng lại) theo cau_hinh().get("cache_anh_mb", 300) — LRU đơn giản (OrderedDict).
    Giá trị: skia.Image / numpy / tuple-list lồng → ước MB theo điểm ảnh; không ước được → 0.05 MB. An toàn luồng (RLock)."""
    _TAT_CA = weakref.WeakSet()     # R4b 1.2.21: tham chiếu YẾU — cache của lớp đã dựng xong (LopChu._cache…) được giải phóng cùng lớp, không ghim RAM tới trần
    _KHOA = threading.RLock()
    _TONG = [0.0]
    _TRAN = [None]

    def __init__(self, ten="cache"):
        self.ten = ten; self.d = OrderedDict(); self.mb = {}
        with CacheAnh._KHOA:
            CacheAnh._TAT_CA.add(self)

    def __del__(self):
        try:
            with CacheAnh._KHOA:
                CacheAnh._TONG[0] -= sum(self.mb.values())
                if CacheAnh._TONG[0] < 0:
                    CacheAnh._TONG[0] = 0.0
        except Exception:
            pass

    @staticmethod
    def tran_mb():
        if CacheAnh._TRAN[0] is None:
            try:
                CacheAnh._TRAN[0] = float(chung.cau_hinh().get("cache_anh_mb", 300) or 300)
            except Exception:
                CacheAnh._TRAN[0] = 300.0
        return CacheAnh._TRAN[0]

    @staticmethod
    def _uoc_mb(v):
        try:
            if isinstance(v, np.ndarray):
                return v.nbytes / 1048576.0
            if hasattr(v, "width") and hasattr(v, "height") and callable(v.width):
                return v.width() * v.height() * 4 / 1048576.0
            if isinstance(v, (tuple, list)):
                return sum(CacheAnh._uoc_mb(x) for x in v)
            if isinstance(v, dict):
                return sum(CacheAnh._uoc_mb(x) for x in v.values())
            if hasattr(v, "anh_khoi"):             # BoChu: ảnh nằm trong _SPRITE, bản thân nhẹ
                return 0.02
        except Exception:
            pass
        return 0.05

    def __contains__(self, k):
        with CacheAnh._KHOA:
            return k in self.d

    def __len__(self):
        return len(self.d)

    def __iter__(self):
        return iter(list(self.d))

    def get(self, k, mac_dinh=None):
        with CacheAnh._KHOA:
            if k in self.d:
                self.d.move_to_end(k)
                return self.d[k]
            return mac_dinh

    def __getitem__(self, k):
        v = self.get(k, _THIEU_)
        if v is _THIEU_:
            raise KeyError(k)
        return v

    def __setitem__(self, k, v):
        mb = self._uoc_mb(v)
        with CacheAnh._KHOA:
            if k in self.d:
                CacheAnh._TONG[0] -= self.mb.get(k, 0.0); self.d.pop(k, None)
            self.d[k] = v; self.mb[k] = mb; CacheAnh._TONG[0] += mb
            self._bot()

    def pop(self, k, *a):
        with CacheAnh._KHOA:
            if k in self.d:
                CacheAnh._TONG[0] -= self.mb.pop(k, 0.0)
                return self.d.pop(k)
            if a:
                return a[0]
            raise KeyError(k)

    def clear(self):
        with CacheAnh._KHOA:
            CacheAnh._TONG[0] -= sum(self.mb.values()); self.d.clear(); self.mb.clear()

    def _bot(self):
        """vượt trần → bỏ LRU của chính cache này trước, rồi cache khác nặng nhất (cũ nhất trước)"""
        tran = self.tran_mb()
        while CacheAnh._TONG[0] > tran and len(self.d) > 1:
            self.pop(next(iter(self.d)))
        vong = 0
        while CacheAnh._TONG[0] > tran and vong < 10000:
            vong += 1
            con = [c for c in list(CacheAnh._TAT_CA) if c is not self and len(c.d) > 1]
            if not con:
                break
            c = max(con, key=lambda x: sum(x.mb.values()))
            c.pop(next(iter(c.d)))

    @staticmethod
    def tinh_trang():
        return {"tong_mb": round(CacheAnh._TONG[0], 1), "tran_mb": CacheAnh.tran_mb(),
                "cache": {c.ten: {"so": len(c.d), "mb": round(sum(c.mb.values()), 1)} for c in list(CacheAnh._TAT_CA)}}

# ---------------------------------------------------------------- font ----
FONT_MAC_DINH_DIR = chung.duong("font_mac_dinh")
VAI_MAC_DINH = {           # vai → tên file trong FONT_MAC_DINH_DIR (thứ tự ưu tiên)
    "tieu_de": ["BeVietnamPro-Black.ttf", "BeVietnamPro-Bold.ttf"],
    "phu_de": ["BeVietnamPro-Bold.ttf", "BeVietnamPro-Black.ttf"],
    "nhan": ["BeVietnamPro-Bold.ttf"],
    "than": ["BeVietnamPro-Regular.ttf"],
    "script": ["DancingScript[wght].ttf", "BeVietnamPro-Bold.ttf"],
    "bien": ["Inter[opsz,wght].ttf", "BeVietnamPro-Bold.ttf"],
}
GIAI_FONT = None           # hook: dung.py đặt = ctx.font (vai|id → đường dẫn); None → mặc định


def font_mac_dinh(vai="phu_de"):
    for f in VAI_MAC_DINH.get(vai, VAI_MAC_DINH["phu_de"]):
        p = os.path.join(FONT_MAC_DINH_DIR, f)
        if os.path.isfile(p):
            return p
    # cuối cùng: bất kỳ ttf trong thư mục mặc định, rồi Arial của Windows
    try:
        for f in sorted(os.listdir(FONT_MAC_DINH_DIR)):
            if f.lower().endswith((".ttf", ".otf")):
                return os.path.join(FONT_MAC_DINH_DIR, f)
    except Exception:
        pass
    return os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts", "arialbd.ttf")


def giai_font(ten):
    """vai|id|đường dẫn → đường dẫn file font"""
    if ten and isinstance(ten, str) and os.path.isfile(ten):
        return ten
    if GIAI_FONT:
        try:
            p = GIAI_FONT(ten)
            if p and os.path.isfile(p):
                return p
        except Exception:
            pass
    return font_mac_dinh(ten if ten in VAI_MAC_DINH else "phu_de")


_PROV = tl.TypefaceFontProvider()
_FC = tl.FontCollection(); _FC.setDefaultFontManager(_PROV)

# 1.3: họ font DỰ PHÒNG cho ký tự font chính không có (→ ✓ ★ • …) — font ký hiệu sẵn của hệ điều hành
_DU_PHONG = []
_DU_PHONG_DUONG = []       # 1.2.21: đường font dự phòng (để báo may_sua font_thieu_dau họ nào đã dùng)
for _i, _p in enumerate([os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", f) for f in ("seguisym.ttf", "segoeui.ttf", "seguiemj.ttf")]
                        + ["/System/Library/Fonts/Apple Symbols.ttf", "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                           "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]):
    try:
        if os.path.isfile(_p):
            _tf = skia.Typeface.MakeFromFile(_p)
            if _tf is not None:
                _PROV.registerTypeface(_tf, f"du_phong_{_i}")
                _DU_PHONG.append(f"du_phong_{_i}"); _DU_PHONG_DUONG.append(_p)
    except Exception:
        pass
_UNI = skia.Unicode.ICU_Make()
_TF = {}                  # (path, wght) → (alias, typeface)
_KHOA = threading.RLock()  # SkParagraph không đảm bảo an toàn luồng → khoá quanh build/paint
_WGHT = int.from_bytes(b"wght", "big")


def _typeface(path, dam):
    dam = int(dam or 0)
    k = (path, dam)
    with _KHOA:
        if k in _TF:
            return _TF[k]
        tf = skia.Typeface.MakeFromFile(path)
        if tf is None:
            raise FileNotFoundError("không nạp được font: " + path)
        try:
            truc = tf.getVariationDesignParameters() or []
        except Exception:
            truc = []
        ax = next((a for a in truc if a.tag == _WGHT), None)
        if ax is not None and dam:
            w = min(max(float(dam), ax.min), ax.max)
            fa = skia.FontArguments()
            fa.setVariationDesignPosition(skia.FontArguments.VariationPosition(skia.FontArguments.VariationPosition.Coordinates([skia.FontArguments.VariationPosition.Coordinate(_WGHT, w)])))
            c = tf.makeClone(fa)
            if c is not None:
                tf = c
        alias = "f%s_%d" % (chung.bam(os.path.abspath(path) + "|" + str(os.path.getsize(path))), dam)
        _PROV.registerTypeface(tf, alias)
        _TF[k] = (alias, tf)
        return _TF[k]


# ---------------------------------------------------------------- màu ----
_TEN_MAU = {"trang": "#ffffff", "den": "#000000", "white": "#ffffff", "black": "#000000", "do": "#ff3b30", "vang": "#ffd200", "xanh": "#22d3ee"}


def mau(s, mac_dinh=(255, 255, 255, 255)):
    """'#rgb' '#rgba' '#rrggbb' '#rrggbbaa' | [r,g,b(,a)] → (r,g,b,a) 0..255"""
    if s is None:
        return mac_dinh
    if isinstance(s, (list, tuple)):
        v = [int(x) for x in s]
        return (v[0], v[1], v[2], v[3] if len(v) > 3 else 255)
    s = _TEN_MAU.get(str(s).strip().lower(), str(s).strip())
    m = re.match(r"rgba?\(([^)]*)\)", s)
    if m:
        v = [float(x) for x in m.group(1).split(",")]
        a = v[3] if len(v) > 3 else 1.0
        return (int(v[0]), int(v[1]), int(v[2]), int(round(a * 255 if a <= 1 else a)))
    s = s.lstrip("#")
    if len(s) in (3, 4):
        s = "".join(c * 2 for c in s)
    if len(s) == 6:
        s += "ff"
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16))
    except Exception:
        return mac_dinh


def mau_skia(s, alpha_nhan=1.0):
    r, g, b, a = mau(s)
    return skia.ColorSetARGB(int(round(a * alpha_nhan)), r, g, b)


# ---------------------------------------------------------------- kiểu dáng ----
def _kd(kd, W=1080):
    """chuẩn hoá đơn vị px. 1.2.21: KHÔNG còn mặc định co 60 / dam 700 / dong 1.15 / can giua — thiếu → ThieuTruong(kieu_dang.<khoá>)
    (lớp/mẫu/bìa phải điền từ quyet_dinh["chu"] trước khi gọi: lop.kd_tu_quyet / mau.CongCu.ve_chu / bia._ve_chu)"""
    kd = dict(kd or {})
    for k in ("co", "dam", "dong", "can"):
        if kd.get(k) is None:
            raise ThieuTruong("kieu_dang." + k, "chữ thiếu %s (quyet_dinh chu.%s)" % (k, k))
    kd["co"] = float(kd["co"])
    kd["dam"] = int(kd["dam"])
    kd["dong"] = float(kd["dong"])
    kd["gian_px"] = float(kd.get("gian", 0) or 0) * kd["co"]
    kd["can"] = kd["can"]
    kd["_font"] = giai_font(kd.get("font"))
    kd["vien"] = [v for v in (kd.get("vien") or []) if v and float(v.get("w", 0)) > 0]
    kd["bong"] = [b for b in (kd.get("bong") or []) if b]
    rm = kd.get("rong_max")
    if rm is not None:
        kd["rong_max_px"] = float(rm) * W if float(rm) <= 1.0 else float(rm)
    return kd


def _skey(kd, fill=None):
    """khoá cache theo kiểu (không gồm text)"""
    return (kd["_font"], kd["dam"], kd["co"], kd["dong"], kd["gian_px"], kd.get("nghieng", 0),
            str(fill if fill is not None else kd.get("mau")), str(kd.get("gradient")), str(kd["vien"]), str(kd["bong"]))


def _text_style(kd, paint=None, color=None):
    alias, _ = _typeface(kd["_font"], kd["dam"])
    ts = tl.TextStyle()
    ts.setFontFamilies([alias] + _DU_PHONG)
    ts.setFontSize(kd["co"])
    ts.setHeight(kd["dong"]); ts.setHeightOverride(True)
    if kd["gian_px"]:
        ts.setLetterSpacing(kd["gian_px"])
    if paint is not None:
        ts.setForegroundPaint(paint)
    else:
        ts.setColor(color if color is not None else skia.ColorWHITE)
    return ts


def _paragraph(txt, kd, paint=None, color=None, rong=1e7):
    ps = tl.ParagraphStyle()
    ps.setTextStyle(_text_style(kd, paint, color))
    ps.setTextAlign(tl.TextAlign.kLeft)
    pb = tl.ParagraphBuilder.make(ps, _FC, _UNI)
    pb.addText(txt)
    p = pb.Build()
    p.layout(rong)
    return p


_DO = {}


def _do(txt, kd):
    """đo 1 từ → (w, h_dong, baseline)"""
    k = (txt, kd["_font"], kd["dam"], kd["co"], kd["dong"], kd["gian_px"])
    r = _DO.get(k)
    if r is None:
        with _KHOA:
            p = _paragraph(txt, kd)
            r = (float(p.LongestLine), float(p.Height), float(p.AlphabeticBaseline))
        if len(_DO) > 20000:
            _DO.clear()
        _DO[k] = r
    return r


def _rong_cach(kd):
    _, tf = _typeface(kd["_font"], kd["dam"])
    f = skia.Font(tf, kd["co"])
    return float(f.measureText(" ")) + kd["gian_px"]


DONG_KHE = 0.06          # khe tối thiểu giữa mực dòng trên và mực dòng dưới (× cỡ chữ) — luật chất lượng, AI không hạ được


def _muc_doc(text, kd):
    """mực thật của các ký tự trong câu so với baseline → (tren<0, duoi>0) px (dấu chồng Ể Ẫ Ữ, chân g y)"""
    _, tf = _typeface(kd["_font"], kd["dam"])
    f = skia.Font(tf, kd["co"])
    ky = "".join(sorted(set(c for c in text if not c.isspace()))) or "H"
    try:
        gl = f.textToGlyphs(ky)
        bs = f.getBounds(gl)
        tren = min(b.top() for b in bs); duoi = max(b.bottom() for b in bs)
    except Exception:
        m = f.getMetrics(); tren, duoi = m.fAscent, m.fDescent
    return float(tren), float(duoi)


_DAU_NOI = {"·", "•", "-", "–", "—", "|", "/", "+", "&", "→"}


def _bo_dau_dau_cuoi(dong):
    """dấu ngăn cách ("·", "|", "-"…) rơi vào đầu/cuối dòng sau khi ngắt → bỏ (dòng chỉ còn dấu thì giữ)"""
    ra = []
    for d in dong:
        while len(d) > 1 and d[0][0] in _DAU_NOI:
            d = d[1:]
        while len(d) > 1 and d[-1][0] in _DAU_NOI:
            d = d[:-1]
        ra.append(d)
    return ra


def _noi_dong(cac_dong, kd, cao_dong):
    """khoảng dòng < (chân mực dòng trên − đỉnh mực dòng dưới) + khe → nới hệ số dòng; ghi kd["_noi_dong"] để máy kiểm báo"""
    can = 0.0
    muc = [_muc_doc(t, kd) for t in cac_dong]
    vien = max([float(v.get("w", 0)) for v in kd.get("vien") or []] + [0.0])          # viền phủ cả dòng trên lẫn dòng dưới
    bong = max([max(0.0, float(b.get("y", 0))) + float(b.get("mo", 0)) * 0.25 for b in kd.get("bong") or []] + [0.0])
    khe = DONG_KHE * kd["co"] + 2 * vien + bong
    for (t1, d1), (t2, d2) in zip(muc, muc[1:]):
        can = max(can, d1 - t2 + khe)
    if cao_dong >= can - 0.5:
        return kd, cao_dong, _do("Hg", kd)[2]
    kd = dict(kd)
    kd["_noi_dong"] = (round(kd["dong"], 3), round(kd["dong"] * can / cao_dong, 3))
    kd["dong"] = kd["dong"] * can / cao_dong
    _, cao_dong, base = _do("Hg", kd)
    return kd, cao_dong, base


# ---------------------------------------------------------------- bố cục ----
def bo_cuc(text, kieu_dang, rong_max_px=None, W=1080):
    """xếp dòng → {"w","h","cao_dong","base","dong":[{"y","w","x","tu":[...]}],"tu":[{"txt","x","y","w","h","i","dong"}],"kd"}"""
    kd = kieu_dang if "_font" in (kieu_dang or {}) else _kd(kieu_dang, W)
    if rong_max_px is None:
        rong_max_px = kd.get("rong_max_px")
    text = chung.NFC(text or "")
    if kd.get("hoa"):
        text = text.upper()
    _, cao_dong, base = _do("Hg", kd)
    if "\n" in text or (rong_max_px and _do(text, kd)[0] > rong_max_px):
        kd, cao_dong, base = _noi_dong(text, kd, cao_dong)     # nhiều dòng → không cho dấu dòng dưới chạm chân dòng trên
    cach = _rong_cach(kd)
    dong = []
    for doan in text.split("\n"):
        tus = [t for t in doan.split() if t]
        if not tus:
            dong.append([])
            continue
        ws = [_do(t, kd)[0] for t in tus]
        if not rong_max_px or rong_max_px <= 0:
            dong.append(list(zip(tus, ws)))
            continue
        # ngắt tham lam theo khoảng trắng
        cac = []; hien = []; rong_hien = 0.0
        for t, w in zip(tus, ws):
            them = w if not hien else cach + w
            if hien and rong_hien + them > rong_max_px:
                cac.append(hien); hien = [(t, w)]; rong_hien = w
            else:
                hien.append((t, w)); rong_hien += them
        if hien:
            cac.append(hien)
        # chống mồ côi: dòng cuối 1 từ mà dòng trước ≥ 3 từ → kéo từ cuối dòng trước xuống (nếu vẫn vừa)
        if len(cac) >= 2 and len(cac[-1]) == 1 and len(cac[-2]) >= 3:
            tcu = cac[-2][-1]
            if tcu[1] + cach + cac[-1][0][1] <= rong_max_px:
                cac[-2] = cac[-2][:-1]; cac[-1] = [tcu] + cac[-1]
        dong.extend(cac)
    dong = _bo_dau_dau_cuoi(dong)
    if len(dong) >= 2:                                         # nhiều dòng → dấu dòng dưới không được chạm chân dòng trên
        kd, cao_dong, base = _noi_dong([" ".join(t for t, _ in d) for d in dong], kd, cao_dong)
    # toạ độ
    rong_dong = [sum(w for _, w in d) + cach * max(0, len(d) - 1) for d in dong]
    bw = max(rong_dong) if rong_dong else 0.0
    bh = cao_dong * len(dong)
    can = kd["can"]
    ra_dong = []; tat_ca = []; i = 0
    for li, d in enumerate(dong):
        lw = rong_dong[li]
        x0 = 0.0 if can == "trai" else (bw - lw) if can == "phai" else (bw - lw) / 2
        y = li * cao_dong
        x = x0; ds = []
        for t, w in d:
            tu = {"txt": t, "x": x, "y": y, "w": w, "h": cao_dong, "i": i, "dong": li}
            ds.append(tu); tat_ca.append(tu); i += 1
            x += w + cach
        ra_dong.append({"y": y, "w": lw, "x": x0, "tu": ds})
    return {"w": bw, "h": bh, "cao_dong": cao_dong, "base": base, "dong": ra_dong, "tu": tat_ca, "kd": kd, "cach": cach}


def _ky_tu(bc):
    """chia từng từ thành ký tự: hộp qua đo tiền tố (giữ kerning)"""
    kd = bc["kd"]; ra = []; i = 0
    for tu in bc["tu"]:
        t = tu["txt"]; truoc = 0.0
        for j, ch in enumerate(t):
            wp = _do(t[: j + 1], kd)[0]
            ra.append({"txt": ch, "x": tu["x"] + truoc, "y": tu["y"], "w": max(wp - truoc, 1.0), "h": tu["h"], "i": i, "tu": tu["i"], "dong": tu["dong"]})
            truoc = wp; i += 1
    return ra


# ---------------------------------------------------------------- lề (viền + bóng) ----
def le_kd(kd):
    """lề cần thêm quanh hộp chữ cho viền/bóng → {"trai","phai","tren","duoi"} px"""
    kd = kd if "_font" in (kd or {}) else _kd(kd)
    v = max([float(x.get("w", 0)) for x in kd["vien"]] + [0.0])
    bx = by = 0.0
    for b in kd["bong"]:
        mo = float(b.get("mo", 0)) * 1.5
        bx = max(bx, abs(float(b.get("x", 0))) + mo); by = max(by, abs(float(b.get("y", 0))) + mo)
    return {"trai": v + bx + 2, "phai": v + bx + 2, "tren": v + by + 2, "duoi": v + by + 2}


def _pad_phan(kd):
    le = le_kd(kd)
    co = kd["co"]
    nghieng = abs(math.tan(math.radians(float(kd.get("nghieng", 0))))) * co
    return (le["trai"] + co * 0.12 + nghieng, le["phai"] + co * 0.12 + nghieng, le["tren"] + co * 0.35, le["duoi"] + co * 0.3)


# ---------------------------------------------------------------- font thiếu dấu (1.2.21) ----
_GLYPH = {}     # (font path, ký tự) → bool có glyph
_HO_FONT = {}   # font path → họ (tên gia đình)


def _ho_font(path):
    if path not in _HO_FONT:
        try:
            _HO_FONT[path] = skia.Typeface.MakeFromFile(path).getFamilyName()
        except Exception:
            _HO_FONT[path] = os.path.basename(path)
    return _HO_FONT[path]


def ky_tu_thieu(text, kd):
    """ký tự tiếng Việt (chữ có dấu, ngoài ASCII) trong text mà font chính KHÔNG có glyph → chuỗi ký tự thiếu ("" = đủ).
    Dò bằng Typeface.unicharsToGlyphs (cmap); lỗi dò → coi là đủ (không chặn)."""
    path = kd.get("_font") or giai_font(kd.get("font"))
    ky = sorted(set(ch for ch in chung.NFC(text or "") if ord(ch) > 127 and unicodedata.category(ch).startswith("L")))
    if not ky or not path:
        return ""
    can = [ch for ch in ky if (path, ch) not in _GLYPH]
    if can:
        try:
            _, tf = _typeface(path, kd.get("dam") or 400)
            try:
                gl = tf.unicharsToGlyphs([ord(ch) for ch in can])
            except Exception:
                gl = [tf.unicharToGlyph(ord(ch)) for ch in can]
            for ch, g in zip(can, gl):
                _GLYPH[(path, ch)] = int(g) != 0
        except Exception:
            for ch in can:
                _GLYPH[(path, ch)] = True
    return "".join(ch for ch in ky if not _GLYPH.get((path, ch), True))


def _meta_thieu_glyph(text, kd):
    th = ky_tu_thieu(text, kd)
    if not th:
        return None
    du = [_ho_font(p) for p in _DU_PHONG_DUONG] or ["(không có font dự phòng)"]
    return {"font": kd.get("_font"), "ho": _ho_font(kd.get("_font")) if kd.get("_font") else None, "ky_tu": th, "du_phong": du,
            "mo_ta": "font `%s` thiếu glyph %s → chữ đó vẽ bằng font dự phòng %s (đổi font trong quyet_dinh.font hoặc kieu_dang.font)"
                     % (_ho_font(kd.get("_font")) if kd.get("_font") else "?", th, "/".join(du))}


# ---------------------------------------------------------------- vẽ phần ----
_PHAN = CacheAnh("chu._PHAN")      # (txt, skey, vị trí gradient) → (skia.Image premul, px, py) — trần RAM theo cache_anh_mb


def _shader_gradient(gr, rect):
    """gradient trên hộp rect (x0,y0,x1,y1): goc 0 = trái→phải, 90 = trên→dưới"""
    ms = [mau_skia(m) for m in (gr.get("mau") or ["#ffffff", "#bbbbbb"])]     # thiếu màu → trung tính (AI phải ghi màu)
    if len(ms) < 2:
        ms = ms * 2
    goc = math.radians(float(gr.get("goc", 90)))
    x0, y0, x1, y1 = rect
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h = (x1 - x0), (y1 - y0)
    dx, dy = math.cos(goc), math.sin(goc)
    L = abs(w * dx) + abs(h * dy)           # chiều dài hình chiếu
    p0 = skia.Point(cx - dx * L / 2, cy - dy * L / 2); p1 = skia.Point(cx + dx * L / 2, cy + dy * L / 2)
    diem = gr.get("diem")
    pos = [float(p) for p in diem] if diem and len(diem) == len(ms) else None
    return skia.GradientShader.MakeLinear([p0, p1], ms, pos)


def _nhoe_np(a, sig):
    """Gauss bằng cv2: sigma lớn thì thu nhỏ → nhoè → phóng (nhanh hơn Skia raster rất nhiều). a: uint8 (h,w)"""
    import cv2
    if sig < 0.3:
        return a
    h, w = a.shape[:2]
    f = max(1.0, sig / 2.0)
    if f > 1.4:
        nw, nh = max(1, int(round(w / f))), max(1, int(round(h / f)))
        b = cv2.resize(a, (nw, nh), interpolation=cv2.INTER_AREA)
        b = cv2.GaussianBlur(b, (0, 0), max(0.1, sig * nw / w), max(0.1, sig * nh / h))
        return cv2.resize(b, (w, h), interpolation=cv2.INTER_LINEAR)
    return cv2.GaussianBlur(a, (0, 0), sig, sig)


def _bong_mo(txt, kd, viens, b, W_, H_, S, pl, pt, base, ng):
    """bóng mờ của một phần chữ → skia.Image premul cỡ (W_, H_) pixel (đã lệch x,y, đã nhoè sigma = mo/2)"""
    surf = skia.Surface(max(W_, 1), max(H_, 1))
    c = surf.getCanvas(); c.clear(skia.Color4f(0, 0, 0, 0))
    c.scale(S, S)
    if ng:
        c.translate(pl, pt + base); c.skew(-math.tan(math.radians(ng)), 0); c.translate(-pl, -(pt + base))
    c.translate(float(b.get("x", 0)), float(b.get("y", 0)))
    trang = skia.ColorSetARGB(255, 255, 255, 255)
    if viens:
        sp = skia.Paint(AntiAlias=True); sp.setStyle(skia.Paint.kStroke_Style); sp.setStrokeWidth(2 * float(viens[0]["w"]))
        sp.setStrokeJoin(skia.Paint.kRound_Join); sp.setStrokeCap(skia.Paint.kRound_Cap); sp.setColor(trang)
        _paragraph(txt, kd, paint=sp).paint(c, pl, pt)
    fp = skia.Paint(AntiAlias=True); fp.setColor(trang)
    _paragraph(txt, kd, paint=fp).paint(c, pl, pt)
    a = surf.makeImageSnapshot().toarray(colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType)[..., 3]
    a = _nhoe_np(np.ascontiguousarray(a), float(b.get("mo", 0)) / 2 * S)
    r, g, bl, al = mau(b.get("mau", "#000000cc"))
    a = (a.astype(np.float32) * (al / 255.0))
    out = np.empty(a.shape + (4,), np.uint8)
    out[..., 0] = (a * (bl / 255.0) + 0.5).astype(np.uint8); out[..., 1] = (a * (g / 255.0) + 0.5).astype(np.uint8)
    out[..., 2] = (a * (r / 255.0) + 0.5).astype(np.uint8); out[..., 3] = (a + 0.5).astype(np.uint8)
    return skia.Image.fromarray(np.ascontiguousarray(out), skia.kBGRA_8888_ColorType, skia.kPremul_AlphaType)


def _ve_phan(txt, kd, fill=None, grad_rect=None, vi_tri=(0.0, 0.0)):
    """vẽ 1 phần (từ/ký tự) → (Image premul, pad_trai, pad_tren). fill: màu ghi đè (karaoke). grad_rect: hộp gradient (toạ độ khối),
    vi_tri: (x,y) phần trong khối — để gradient liền mạch qua các phần."""
    gr = kd.get("gradient") if fill is None else None
    k = (txt, _skey(kd, fill), (round(vi_tri[0], 1), round(vi_tri[1], 1), tuple(round(v, 1) for v in grad_rect)) if gr else None)
    r = _PHAN.get(k)
    if r is not None:
        return r
    w, h, base = _do(txt, kd)
    pl, pr, pt, pb = _pad_phan(kd)
    S = 2 if kd["co"] < 40 else 1
    W_ = int(math.ceil((w + pl + pr) * S)); H_ = int(math.ceil((h + pt + pb) * S))
    with _KHOA:
        surf = skia.Surface(max(W_, 1), max(H_, 1))
        c = surf.getCanvas(); c.clear(skia.Color4f(0, 0, 0, 0))
        c.scale(S, S)
        ng = float(kd.get("nghieng", 0))
        if ng:
            c.translate(pl, pt + base); c.skew(-math.tan(math.radians(ng)), 0); c.translate(-pl, -(pt + base))
        viens = sorted(kd["vien"], key=lambda v: -float(v["w"]))
        # --- bóng: hình bóng (viền dày nhất + fill) cùng màu, làm mờ, lệch ---
        for b in kd["bong"]:
            mo = float(b.get("mo", 0)); mb = mau_skia(b.get("mau", "#000000cc"))
            if mo > 0:            # nhoè bằng cv2 (thu nhỏ → Gauss → phóng): Skia ImageFilters.Blur raster chậm ~10×
                c.save(); c.resetMatrix()
                c.drawImage(_bong_mo(txt, kd, viens, b, W_, H_, S, pl, pt, base, ng), 0, 0)
                c.restore()
                continue
            lp = skia.Paint()
            c.saveLayer(None, lp)
            c.translate(float(b.get("x", 0)), float(b.get("y", 0)))
            if viens:
                sp = skia.Paint(AntiAlias=True); sp.setStyle(skia.Paint.kStroke_Style); sp.setStrokeWidth(2 * float(viens[0]["w"]))
                sp.setStrokeJoin(skia.Paint.kRound_Join); sp.setStrokeCap(skia.Paint.kRound_Cap); sp.setColor(mb)
                _paragraph(txt, kd, paint=sp).paint(c, pl, pt)
            fp = skia.Paint(AntiAlias=True); fp.setColor(mb)
            _paragraph(txt, kd, paint=fp).paint(c, pl, pt)
            c.restore()
        # --- viền: dày → mỏng ---
        for v in viens:
            sp = skia.Paint(AntiAlias=True); sp.setStyle(skia.Paint.kStroke_Style); sp.setStrokeWidth(2 * float(v["w"]))
            sp.setStrokeJoin(skia.Paint.kRound_Join); sp.setStrokeCap(skia.Paint.kRound_Cap); sp.setColor(mau_skia(v.get("mau", "#000")))
            _paragraph(txt, kd, paint=sp).paint(c, pl, pt)
        # --- fill ---
        fp = skia.Paint(AntiAlias=True)
        if gr and grad_rect is not None:
            sh = _shader_gradient(gr, grad_rect)
            sh = sh.makeWithLocalMatrix(skia.Matrix.Translate(pl - vi_tri[0], pt - vi_tri[1]))
            fp.setShader(sh)
        else:
            fp.setColor(mau_skia(fill if fill is not None else kd.get("mau", "#ffffff")))
        _paragraph(txt, kd, paint=fp).paint(c, pl, pt)
        img = surf.makeImageSnapshot()
        if S != 1:
            img = img.resize(int(math.ceil(w + pl + pr)), int(math.ceil(h + pt + pb)), skia.SamplingOptions(skia.FilterMode.kLinear, skia.MipmapMode.kLinear))
    r = (img, pl, pt)
    _PHAN[k] = r
    return r


# ---------------------------------------------------------------- nền / khối ----
def ve_khoi(canvas, rect, nen, alpha=1.0):
    """vẽ nền/khối (pill|rect|circle) với màu, viền, bóng. rect = (x0,y0,x1,y1). nen: {"mau","bo","hinh","vien":{"w","mau"},"bong":[...]}"""
    if not nen:
        return
    x0, y0, x1, y1 = rect
    hinh = nen.get("hinh", "rect")
    bo = float(nen.get("bo", 0))
    if hinh == "pill":
        bo = (y1 - y0) / 2
    rr = skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(x0, y0, x1, y1), bo, bo)
    if hinh == "circle":
        r_ = min(x1 - x0, y1 - y0) / 2
        rr = skia.RRect.MakeOval(skia.Rect.MakeXYWH((x0 + x1) / 2 - r_, (y0 + y1) / 2 - r_, 2 * r_, 2 * r_))
    for b in nen.get("bong") or []:
        mo = float(b.get("mo", 0)); lp = skia.Paint()
        if mo > 0:
            lp.setImageFilter(skia.ImageFilters.Blur(mo / 2, mo / 2))
        canvas.saveLayer(None, lp)
        canvas.translate(float(b.get("x", 0)), float(b.get("y", 0)))
        p = skia.Paint(AntiAlias=True); p.setColor(mau_skia(b.get("mau", "#0008"), alpha))
        canvas.drawRRect(rr, p)
        canvas.restore()
    if nen.get("mau"):
        p = skia.Paint(AntiAlias=True)
        gr = nen.get("gradient")
        if gr:
            p.setShader(_shader_gradient(gr, rect)); p.setAlphaf(alpha)
        else:
            p.setColor(mau_skia(nen["mau"], alpha))
        canvas.drawRRect(rr, p)
    v = nen.get("vien")
    if v and float(v.get("w", 0)) > 0:
        p = skia.Paint(AntiAlias=True); p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(float(v["w"]))
        p.setColor(mau_skia(v.get("mau", "#fff"), alpha))
        canvas.drawRRect(rr, p)


def _dem(kd):
    d = (kd.get("nen") or {}).get("dem", [0, 0])
    if isinstance(d, (int, float)):
        d = [d, d]
    return float(d[0]), float(d[1])


# ---------------------------------------------------------------- API ----
def do_kich_thuoc(text, kieu_dang, rong_max_px=None, W=1080):
    """→ (w, h) hộp nhìn thấy của khối chữ (gồm đệm nền pill nếu có), chưa gồm lề viền/bóng"""
    kd = _kd(kieu_dang, W)
    bc = bo_cuc(text, kd, rong_max_px, W)
    dx, dy = _dem(kd) if kd.get("nen") else (0.0, 0.0)
    return (bc["w"] + 2 * dx, bc["h"] + 2 * dy)


_SAMPLING_CUBIC = skia.SamplingOptions(skia.CubicResampler.Mitchell())
_SAMPLING_NONE = skia.SamplingOptions()


def ve_chu(text, kieu_dang, W=1080, H=1920, rong_max_px=None, tach=None, u_phan=None, phan_tt=None, noi=None, tra_skia=False, an_sau=None):
    """Vẽ khối chữ → (np.uint8 RGBA thẳng (h,w,4), meta). meta: {"w","h" (ảnh), "khoi":(x0,y0,x1,y1) hộp nhìn thấy trong ảnh,
    "goc":(ox,oy) gốc toạ độ khối chữ trong ảnh, "le":{...}, "tu":[hộp từng từ (toạ độ ảnh)], "phan":[hộp từng phần], "n_phan"}.
    tach: None|"tu"|"ky_tu"; phan_tt: [trạng thái từng phần {"opacity","scale","x","y"}]; u_phan: [u] → opacity;
    noi: chỉ số (hoặc tập chỉ số) từ đang nói → màu kd["mau_noi"]."""
    kd = _kd(kieu_dang, W)
    bc = bo_cuc(text, kd, rong_max_px, W)
    phan = _ky_tu(bc) if tach == "ky_tu" else bc["tu"]
    le = le_kd(kd)
    pl, pr, pt, pb = _pad_phan(kd)
    dx, dy = _dem(kd) if kd.get("nen") else (0.0, 0.0)
    # biên độ dịch chuyển của các phần → nới ảnh
    mx = my = 0.0; ms = 1.0
    for s in (phan_tt or []):
        mx = max(mx, abs(float(s.get("x", 0)))); my = max(my, abs(float(s.get("y", 0)))); ms = max(ms, float(s.get("scale", 1)))
    nx = pl + dx + mx + (ms - 1) * bc["w"] / 2; ny = pt + dy + my + (ms - 1) * bc["h"] / 2
    IW = int(math.ceil(bc["w"] + nx + pr + dx + mx + (ms - 1) * bc["w"] / 2)); IH = int(math.ceil(bc["h"] + ny + pb + dy + my + (ms - 1) * bc["h"] / 2))
    IW, IH = max(IW, 1), max(IH, 1)
    ox, oy = nx, ny                                        # gốc khối chữ trong ảnh
    if isinstance(noi, int):
        noi = {noi}
    elif noi is not None:
        noi = set(noi)
    else:
        noi = set()
    grad_rect = (0.0, 0.0, bc["w"], bc["h"])
    with _KHOA:
        surf = skia.Surface(IW, IH)
        c = surf.getCanvas(); c.clear(skia.Color4f(0, 0, 0, 0))
        if kd.get("nen") and bc["tu"]:
            ve_khoi(c, (ox - dx, oy - dy, ox + bc["w"] + dx, oy + bc["h"] + dy), dict(kd["nen"], hinh=kd["nen"].get("hinh", "rect")))
        hop_phan = []
        for p in phan:
            i = p["i"]
            tu_i = p.get("tu", i)
            if an_sau is not None and tu_i > an_sau:        # hiện dần: từ sau từ đang nói → chưa vẽ (giữ chỗ để khối không nhảy)
                hop_phan.append((p["x"] + ox, p["y"] + oy, p["w"], p["h"]))
                continue
            fill = kd.get("mau_noi") if (tu_i in noi and kd.get("mau_noi")) else None
            img, ppl, ppt = _ve_phan(p["txt"], kd, fill=fill, grad_rect=grad_rect, vi_tri=(p["x"], p["y"]))
            tt = (phan_tt[i] if phan_tt and i < len(phan_tt) else None) or {}
            op = float(tt.get("opacity", 1.0))
            if u_phan is not None and i < len(u_phan):
                op *= float(u_phan[i])
            if op <= 0.001:
                hop_phan.append((p["x"] + ox, p["y"] + oy, p["w"], p["h"]))
                continue
            sc = float(tt.get("scale", 1.0)); tx = float(tt.get("x", 0)); ty = float(tt.get("y", 0))
            px = ox + p["x"] - ppl + tx; py = oy + p["y"] - ppt + ty
            paint = skia.Paint(); paint.setAlphaf(min(op, 1.0))
            c.save()
            if sc != 1.0:
                cx = ox + p["x"] + p["w"] / 2 + tx; cy = oy + p["y"] + bc["base"] + ty   # scale quanh tâm ngang, baseline
                c.translate(cx, cy); c.scale(sc, sc); c.translate(-cx, -cy)
                c.drawImage(img, px, py, _SAMPLING_CUBIC, paint)
            elif abs(px - round(px)) < 1e-3 and abs(py - round(py)) < 1e-3:
                c.drawImage(img, round(px), round(py), _SAMPLING_NONE, paint)
            else:
                c.drawImage(img, round(px), round(py), _SAMPLING_NONE, paint)   # làm tròn: chữ nét, lệch ≤ 0.5 px
            c.restore()
            hop_phan.append((p["x"] + ox + tx, p["y"] + oy + ty, p["w"] * sc, p["h"] * sc))
        img_out = surf.makeImageSnapshot()
    meta = {"w": IW, "h": IH, "goc": (ox, oy), "le": le, "khoi": (ox - dx, oy - dy, ox + bc["w"] + dx, oy + bc["h"] + dy),
            "tu": [(t["x"] + ox, t["y"] + oy, t["w"], t["h"]) for t in bc["tu"]], "phan": hop_phan, "n_phan": len(phan),
            "cao_dong": bc["cao_dong"], "so_dong": len(bc["dong"]), "kd": kd,
            "thieu_glyph": _meta_thieu_glyph(text, kd)}        # 1.2.21: font thiếu dấu → lớp/bìa ghi may_sua font_thieu_dau (không lặng lẽ)
    if tra_skia:
        return img_out, meta
    import cv2
    p = img_out.toarray(colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
    b, g, r, a = cv2.split(p)
    arr = cv2.merge([cv2.divide(r, a, scale=255.0), cv2.divide(g, a, scale=255.0), cv2.divide(b, a, scale=255.0), a])
    return arr, meta


def so_phan(text, kieu_dang, rong_max_px=None, tach=None, W=1080):
    """số phần (từ/ký tự) để tính so le"""
    kd = _kd(kieu_dang, W)
    bc = bo_cuc(text, kd, rong_max_px, W)
    return len(_ky_tu(bc)) if tach == "ky_tu" else len(bc["tu"])


def xoa_cache():
    _PHAN.clear(); _DO.clear(); _GLYPH.clear()
