# -*- coding: utf-8 -*-
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Thư viện KIỂU CHỮ gọi theo tên — dựng lại các preset chữ của bộ 'Edit Không Khó'
(bóc từ draft CapCut: màu chữ, viền, quầng sáng, cách đặt lệch, hiệu ứng vào).

Dùng trong script dựng:

    import kieu_chu as K
    ev  = K.su_kien("lech-tren", "Tương lai|Tiền tệ", 3.0, 5.2, W, H, y=980)
    ev += K.su_kien("quang-xanh", "THỜI GIAN", 6.0, 8.0, W, H)
    ass = K.tao_ass(ev, W, H)          # -> file .ass, đưa thẳng vào filter subtitles
    # hoặc lấy PNG trong suốt để overlay như các lớp khác:
    p = K.ve_png("chu-rong", "OUTLINE|TEXT", W, H)

Xem danh sách:  python3 kieu_chu.py
Dựng video thử: python3 kieu_chu.py demo [dọc|ngang] [đường/dẫn/ra.mp4]
"""
import os, sys, glob, subprocess, tempfile
import nen_tang as NT

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ───────── màu (ASS dùng &HBBGGRR) ─────────
def mau_ass(hx):
    hx = hx.lstrip("#")
    r, g, b = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
    return f"&H00{b:02X}{g:02X}{r:02X}&"

VANG   = mau_ass("#FFD200")   # vàng nhấn của bộ gốc
CHANH  = mau_ass("#FCFF00")   # vàng chanh (chữ rỗng, viền)
TRANG  = mau_ass("#FFFFFF")
LAM    = mau_ass("#5DA7FF")   # xanh THỜI GIAN
LAM_D  = mau_ass("#0089FF")
DO     = mau_ass("#FF3B30")
LUC    = mau_ass("#00FF8A")
TIM    = mau_ass("#B47CFF")

# ───────── font: gom font cần dùng vào 1 thư mục cho libass ─────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import kit
    KHO_MAC_DINH, MUA = kit.kho(), kit.bo_mua()     # đọc từ cau-hinh.json
except Exception:
    KHO_MAC_DINH, MUA = NT.kho_mac_dinh(), ""
def _con_nfc(goc, *phan):
    """ghép đường dẫn con, mỗi tầng so tên theo NFC (ổ đĩa có thể lưu tên dạng NFD) — không thấy thì ghép thẳng"""
    import unicodedata
    d = goc
    for x in phan:
        try:
            d = os.path.join(d, next((c for c in os.listdir(d) if unicodedata.normalize("NFC", c) == unicodedata.normalize("NFC", x)), x))
        except OSError:
            d = os.path.join(d, x)
    return d
FONT_MUA = _con_nfc(MUA, "3. 405 FONT Việt Hóa Edit Không Khó", "405 FONT") if MUA else ""
# họ font → tên file ưu tiên (tìm trong kho rồi tới bộ mua)
HO_FONT = {
    "DTPhudu":         ["DTPhudu-Black.otf", "DTPhudu-Bold.otf"],
    "Poppins":         ["Poppins-Black.ttf", "Poppins-Bold.ttf"],
    "Anton":           ["Anton-Regular.ttf"],
    "Barlow Condensed":["BarlowCondensed-Black.ttf", "BarlowCondensed-ExtraBold.ttf"],
    "Be Vietnam Pro":  ["BeVietnamPro-Black.ttf", "BeVietnamPro-Bold.ttf"],
}
MAC_DINH_FONT = "DTPhudu"        # font chính của bộ gốc; thiếu thì lùi về Be Vietnam Pro

def kho():
    try:
        import kit
        return kit.kho()
    except Exception:
        return os.environ.get("VIDEOKIT", KHO_MAC_DINH)

_FDIR = [None]
def thu_muc_font():
    """Gom mọi font cần dùng vào một thư mục tạm (libass chỉ nhận 1 fontsdir)."""
    if _FDIR[0]:
        return _FDIR[0]
    d = os.path.join(tempfile.gettempdir(), "kieuchu_fonts")
    os.makedirs(d, exist_ok=True)
    nguon = [f"{kho()}/fonts", FONT_MUA]
    for thu in nguon:
        for f in glob.glob(f"{thu}/*.[ot]tf"):
            dich = os.path.join(d, os.path.basename(f))
            if not os.path.exists(dich):
                try: NT.lien_ket(f, dich)
                except OSError as e: print(f"  [font] không đưa được {os.path.basename(f)} vào thư mục font: {e}")
    _FDIR[0] = d
    return d

def co_font(ho):
    """Họ font này có file thật không (để lùi về font khác cho khỏi ra ô vuông)."""
    d = thu_muc_font()
    return any(os.path.exists(os.path.join(d, t)) for t in HO_FONT.get(ho, []))

def font_chinh():
    return MAC_DINH_FONT if co_font(MAC_DINH_FONT) else "Be Vietnam Pro"

# ───────── mảnh dựng chung ─────────
def _tc(t):
    return f"{int(t//3600)}:{int(t%3600//60):02d}:{t%60:05.2f}"

def _ev(L, a, b, st, txt, tags="", layer=0):
    L.append(f"Dialogue: {layer},{_tc(a)},{_tc(b)},{st},,0,0,0,,{{{tags}}}{txt}")

VIEN_TOI = "&H00120C08&"     # viền tối mảnh: tách chữ khỏi quầng, giữ nét

def _quang(L, a, b, txt, x, y, co, mau, buoc=None, lop=0, them="", font=None, sang=1.0):
    """Chữ nét là chính; quầng sáng chỉ là lớp nền mờ phía sau.

    sang=0  -> tắt quầng, chữ nét hoàn toàn (mặc định của kiểu thường)
    sang=1  -> quầng vừa phải như bộ gốc
    """
    fn = f"\\fn{font}" if font else ""
    if sang > 0:
        b0 = buoc or ((int(16*sang) + 6, 150), (int(8*sang) + 4, 110))
        for k, (nhoe, mo) in enumerate(b0):
            mo = min(255, int(mo + (1 - min(sang, 1)) * 60))
            _ev(L, a, b, "G", txt, f"\\an5\\pos({x},{y})\\fs{co}{fn}\\1a&HFF&\\3c{mau}"
                                   f"\\bord{max(4, int(co*0.05))}\\blur{nhoe}\\alpha&H{mo:02X}&{them}", layer=lop+k)
        n = len(b0)
    else:
        n = 0
    vt = max(2, int(co * 0.035))
    _ev(L, a, b, "G", txt, f"\\an5\\pos({x},{y})\\fs{co}{fn}\\1c{mau}\\3c{VIEN_TOI}\\bord{vt}{them}", layer=lop+n)

def _tach(chu, n):
    d = [x.strip() for x in str(chu).split("|")]
    while len(d) < n: d.append("")
    return d[:n]

VAO = {   # hiệu ứng vào, dùng chung cho các kiểu tĩnh
    "nay":    "\\fscx60\\fscy60\\t(0,140,\\fscx106\\fscy106)\\t(140,240,\\fscx100\\fscy100)",
    "bong":   "\\fscx20\\fscy20\\t(0,110,\\fscx120\\fscy120)\\t(110,210,\\fscx100\\fscy100)",
    "lui":    "\\fscx155\\fscy155\\t(0,300,\\fscx100\\fscy100)",
    "mo":     "\\fad(120,100)",
    "len":    "\\fscy10\\alpha&HFF&\\t(0,130,\\fscy116\\alpha&H00&)\\t(130,220,\\fscy100)",
    "khong":  "",
}

# ───────── từng kiểu ─────────
def _k_lech_tren(L, d, a, b, W, H, x, y, co, mau, font):
    m1, m2 = (mau + [TRANG, VANG])[:2]
    _quang(L, a,      b, d[0], int(x - W*0.10), y - int(96*co), int(84*co),  m1, lop=0,  font=font)
    _quang(L, a+0.08, b, d[1], int(x + W*0.06), y + int(6*co),  int(136*co), m2, lop=5,  font=font)

def _k_kep_hai_ben(L, d, a, b, W, H, x, y, co, mau, font):
    m1, m2, m3 = (mau + [TRANG, VANG, TRANG])[:3]
    _quang(L, a,      b, d[0], int(x - W*0.19), y - int(122*co), int(72*co),  m1, lop=0,  font=font)
    _quang(L, a+0.10, b, d[1], int(x),           y + int(4*co),   int(140*co), m2, lop=5,  font=font)
    _quang(L, a+0.18, b, d[2], int(x + W*0.20),  y + int(126*co), int(72*co),  m3, lop=10, font=font)

def _k_lech_duoi(L, d, a, b, W, H, x, y, co, mau, font):
    m1, m2 = (mau + [VANG, TRANG])[:2]
    _quang(L, a,      b, d[0], int(x - W*0.04), y - int(40*co), int(132*co), m1, lop=0, font=font)
    _quang(L, a+0.10, b, d[1], int(x + W*0.10), y + int(62*co), int(104*co), m2, lop=5, font=font)

def _k_han_muc(L, d, a, b, W, H, x, y, co, mau, font):
    m1, m2 = (mau + [VANG, TRANG])[:2]
    _quang(L, a,      b, d[0], int(x - W*0.06), y - int(44*co), int(132*co), m1, lop=0, font=font)
    _quang(L, a+0.08, b, d[1], int(x + W*0.10), y + int(56*co), int(100*co), m2, lop=5, font=font)

def _k_quang_xanh(L, d, a, b, W, H, x, y, co, mau, font):
    m = (mau + [LAM])[0]
    _quang(L, a, b, d[0], x, y, int(132*co), m, font=font, sang=1.15)

def _k_chu_rong(L, d, a, b, W, H, x, y, co, mau, font):
    m = (mau + [CHANH])[0]
    fn = f"\\fn{font}" if font else ""
    dong = [t for t in d if t]
    for i, t in enumerate(dong):
        yy = y + int((i - (len(dong)-1)/2) * 160 * co)
        for k, (nhoe, mo) in enumerate(((16,150),)):
            _ev(L, a, b, "G", t, f"\\an5\\pos({x},{yy})\\fs{int(150*co)}{fn}\\1a&HFF&\\3c{m}"
                                 f"\\bord{int(10*co)}\\blur{nhoe}\\alpha&H{mo:02X}&", layer=k)
        _ev(L, a, b, "G", t, f"\\an5\\pos({x},{yy})\\fs{int(150*co)}{fn}\\1a&HFF&\\3c{m}\\bord{int(5*co)}", layer=3)

def _k_vien_chong(L, d, a, b, W, H, x, y, co, mau, font):
    m = (mau + [VANG])[0]
    fn = f"\\fn{font}" if font else ""
    for k, (day, c) in enumerate(((17, mau_ass("#F9C92B")), (13, mau_ass("#FF0000")), (7, TRANG))):
        _ev(L, a, b, "G", d[0], f"\\an5\\pos({x},{y})\\fs{int(140*co)}{fn}\\1c{m}"
                                f"\\bord{int(day*co)}\\3c{c}{VAO['nay']}", layer=k)

def _k_loe_nhap_nhay(L, d, a, b, W, H, x, y, co, mau, font):
    m = (mau + [VANG])[0]
    _quang(L, a, b, d[0], x, y, int(140*co), m, font=font)
    fn = f"\\fn{font}" if font else ""
    for k in range(4):
        s = a + 0.06 + k*0.11
        if s + 0.05 < b:
            _ev(L, s, s+0.05, "G", d[0], f"\\an5\\pos({x},{y})\\fs{int(140*co)}{fn}\\1c{TRANG}\\blur14", layer=8)

def _k_bong_bong(L, d, a, b, W, H, x, y, co, mau, font):
    _quang(L, a, b, d[0], x, y, int(132*co), (mau + [VANG])[0], them=VAO["bong"], font=font)

def _k_lui_nhoe(L, d, a, b, W, H, x, y, co, mau, font):
    _quang(L, a, b, d[0], x, y, int(132*co), (mau + [TRANG])[0], them=VAO["lui"], font=font)

def _k_den_hong(L, d, a, b, W, H, x, y, co, mau, font):
    m = (mau + [VANG])[0]; con = b - a
    doan = [(1,.08),(0,.05),(1,.04),(0,.06),(1,.05),(0,.04),(1, max(0.2, con-0.32))]
    for k, (sang, dai) in enumerate(doan):
        s = a + sum(x2[1] for x2 in doan[:k])
        if sang and s < b:
            _quang(L, s, min(s+dai, b), d[0], x, y, int(132*co), m, font=font)

def _k_quet_sang(L, d, a, b, W, H, x, y, co, mau, font):
    m = (mau + [TRANG])[0]
    fn = f"\\fn{font}" if font else ""
    r = int(430*co); h = int(95*co)
    _ev(L, a, b, "G", d[0], f"\\an5\\pos({x},{y})\\fs{int(132*co)}{fn}\\1c&H00606060&\\bord0")
    _quang(L, a, b, d[0], x, y, int(132*co), m, buoc=((14,120),), lop=3, font=font,
           them=f"\\clip({x-r},{y-h},{x-r+100},{y+h})\\t(0,1000,\\clip({x+r-100},{y-h},{x+r},{y+h}))")

def _k_bang_lat(L, d, a, b, W, H, x, y, co, mau, font):
    m1, m2 = (mau + [TRANG, VANG])[:2]
    for k, (t, c) in enumerate(((d[0], m1), (d[1], m2))):
        if not t: continue
        _quang(L, a + k*0.13, b, t, x, y + int((k-0.5)*176*co), int(116*co), c, lop=k*5,
               them=VAO["len"], font=font)

KIEU = {
    "lech-tren":     dict(ham=_k_lech_tren,     dong=2, ten="Lệch Trên",       goc="Tương lai / Tiền tệ",  vd="Tương lai|Tiền tệ"),
    "kep-hai-ben":   dict(ham=_k_kep_hai_ben,   dong=3, ten="Kẹp Hai Bên",     goc="Texto1 / Poppins",     vd="Trước|CHỈNH SỬA|Sau"),
    "lech-duoi":     dict(ham=_k_lech_duoi,     dong=2, ten="Lệch Dưới",       goc="BẤT NGỜ / chưa",       vd="BẤT NGỜ|chưa"),
    "han-muc":       dict(ham=_k_han_muc,       dong=2, ten="Vàng Trên Trắng", goc="Hạn mức / Vay",        vd="Hạn mức|Vay"),
    "quang-xanh":    dict(ham=_k_quang_xanh,    dong=1, ten="Quầng Xanh",      goc="THỜI GIAN",            vd="THỜI GIAN"),
    "chu-rong":      dict(ham=_k_chu_rong,      dong=2, ten="Chữ Rỗng Sáng",   goc="OUTLINE TEXT",         vd="OUTLINE|TEXT"),
    "vien-chong":    dict(ham=_k_vien_chong,    dong=1, ten="Viền Chồng",      goc="CARTOON",              vd="CARTOON"),
    "loe-nhap-nhay": dict(ham=_k_loe_nhap_nhay, dong=1, ten="Loé Nhấp Nháy",   goc="Flicker Style",        vd="LOÉ SÁNG"),
    "bong-bong":     dict(ham=_k_bong_bong,     dong=1, ten="Bong Bóng",       goc="Aparición burbujeante",vd="BONG BÓNG"),
    "lui-nhoe":      dict(ham=_k_lui_nhoe,      dong=1, ten="Lùi Nhoè",        goc="Alejar con desenfoque",vd="LÙI NHOÈ"),
    "den-hong":      dict(ham=_k_den_hong,      dong=1, ten="Đèn Hỏng",        goc="Fallo de linterna",    vd="ĐÈN HỎNG"),
    "quet-sang":     dict(ham=_k_quet_sang,     dong=1, ten="Quét Sáng",       goc="Light Sweep",          vd="QUÉT SÁNG"),
    "bang-lat":      dict(ham=_k_bang_lat,      dong=2, ten="Bảng Lật",        goc="Cartel hacia arriba",  vd="BẢNG|LẬT LÊN"),
}

def ten_kieu():
    return list(KIEU) + [k for k in du_lieu() if k not in KIEU]

def bang():
    d = ["── kiểu chỉnh tay (6 kiểu anh gửi ảnh + 7 kiểu hay dùng) ──"]
    d += [f"{k:16} {v['ten']:16} {v['dong']} dòng   ví dụ: {v['vd']}" for k, v in KIEU.items()]
    dl = du_lieu()
    if dl:
        d.append(f"── kiểu lấy thẳng từ bộ 'Edit Không Khó' ({len(dl)} kiểu) ──")
        for k, v in dl.items():
            d.append(f"{k:22} {v['dong']} dòng · {v['ten']:34} chữ mẫu: {v['goc'][:38]}")
    return "\n".join(d)

# ───────── kiểu lấy thẳng từ bộ 'Edit Không Khó' (71 kiểu, sinh từ dự án gốc) ─────────
import json as _json

def _xep_lai(r):
    """Giữ bố cục gốc nhưng: kéo chữ về trong khung và tách dòng đủ thoáng để khỏi chồng nhau."""
    dong = []
    for l in r["lop"]:
        v = next((v for v in dong if v["chu"] == l["chu"]
                  and abs(v["dx"]-l["dx"]) < 0.02 and abs(v["dy"]-l["dy"]) < 0.02), None)
        if v is None: dong.append(dict(chu=l["chu"], dx=l["dx"], dy=l["dy"], co=l["co"], lop=[l]))
        else:
            v["lop"].append(l); v["co"] = max(v["co"], l["co"])
    dong.sort(key=lambda v: v["dy"])
    for v in dong: v["dx"] = max(-0.17, min(0.17, v["dx"]))      # khỏi tràn mép
    for i in range(1, len(dong)):
        cach = 0.62*max(dong[i]["co"], dong[i-1]["co"]) + 0.18*min(dong[i]["co"], dong[i-1]["co"])
        xa = 1.45*max(dong[i]["co"], dong[i-1]["co"])
        if dong[i]["dy"] - dong[i-1]["dy"] < cach: dong[i]["dy"] = dong[i-1]["dy"] + cach
        elif dong[i]["dy"] - dong[i-1]["dy"] > xa:  dong[i]["dy"] = dong[i-1]["dy"] + xa
    giua = (dong[0]["dy"] + dong[-1]["dy"]) / 2 if dong else 0
    for v in dong:
        for l in v["lop"]:
            l["dx"], l["dy"] = v["dx"], v["dy"] - giua


NEON = {"neon-button", "glass-button", "thoi-gian", "thoi-gian-2", "thoi-gian-3", "sticker",
        "blue-style", "blue-style-2", "blue-style-3", "shine", "shine-2", "shine-3", "shiney",
        "shiney-2", "flicker", "flicker-2", "flicker-3", "old-vibes", "aesthetic-text", "do-la",
        "loc-phat", "level", "rising", "focus", "focus-2"}

_DU = [None]
CO_CHUAN = 0.082        # dòng chính chiếm bao nhiêu phần chiều cao khung sau khi chuẩn hoá

def du_lieu(tat_ca=False):
    """Nạp presets/kieu-chu-day-du.json (bóc từ dự án CapCut của bộ mua) và chuẩn hoá cỡ chữ.

    Bộ gốc đặt mỗi kiểu ở một góc khung mẫu với cỡ khác nhau; ở đây quy mọi kiểu về
    cùng một cỡ chuẩn, giữ nguyên tỉ lệ giữa các dòng, và bỏ các cụm nằm rải rác
    (thực chất là nhiều kiểu đứng cạnh nhau trong bộ mẫu).
    """
    if _DU[0] is None:
        d = {}
        for p in (os.path.join(kho(), "presets", "kieu-chu-day-du.json"),
                  os.path.join(os.path.dirname(os.path.abspath(__file__)), "kieu-chu-day-du.json")):
            if os.path.exists(p):
                for r in _json.load(open(p, encoding="utf-8")):
                    lop = r["lop"]
                    smax = max((l["co"] for l in lop), default=0.05) or 0.05
                    f = CO_CHUAN / smax
                    dong = {(round(l["dx"], 2), round(l["dy"], 2)) for l in lop if l["chu"]}
                    rong = (max(x for x, _ in dong) - min(x for x, _ in dong)) * f if dong else 0
                    if rong > 0.42: continue          # cụm rải rác: bỏ, đã có kiểu con riêng
                    r = dict(r, lop=[dict(l, co=l["co"]*f, dx=l["dx"]*f, dy=l["dy"]*f) for l in lop])
                    _xep_lai(r)
                    d[r["ma"]] = r
                break
        _DU[0] = d
    if tat_ca: return _DU[0]
    return {k: v for k, v in _DU[0].items() if v.get("loai") != "canh"}

def _hieu_ung(hu, x, y, co):
    """hiệu ứng vào -> (thẻ ASS thêm, chuỗi move thay cho pos nếu có)"""
    d = int(140 * co)
    B = {
        "bong-bong":   ("\\fscx20\\fscy20\\t(0,110,\\fscx120\\fscy120)\\t(110,210,\\fscx100\\fscy100)", None),
        "zoom-nhe":    ("\\fscx88\\fscy88\\t(0,220,\\fscx100\\fscy100)", None),
        "phong-toi":   ("\\fscx170\\fscy170\\alpha&HFF&\\t(0,70,\\alpha&H00&)\\t(0,260,\\fscx100\\fscy100)", None),
        "nay-dan-hoi": ("\\fscx70\\fscy70\\t(0,130,\\fscx112\\fscy112)\\t(130,210,\\fscx96\\fscy96)\\t(210,280,\\fscx100\\fscy100)", None),
        "bang-lat":    (VAO["len"], None),
        "nay-song":    ("\\fscy60\\t(0,120,\\fscy115)\\t(120,200,\\fscy100)", None),
        "mo-sach":     ("\\fscx10\\t(0,200,\\fscx100)", None),
        "hien-dan":    ("\\fad(160,80)", None),
        "lui-nhoe":    ("\\fscx155\\fscy155\\blur10\\t(0,300,\\fscx100\\fscy100\\blur0)", None),
        "vao-nhoe":    ("\\blur16\\alpha&H50&\\t(0,260,\\blur0\\alpha&H00&)", None),
        "chu-rung":    ("\\fscx104\\t(0,60,\\fscx98)\\t(60,120,\\fscx102)\\t(120,190,\\fscx100)", None),
        "loe-sang":    ("", None),
        "den-hong":    ("", None),
    }
    MOVE = {
        "roi-nhanh":   (0, -d), "truot-len": (0, d), "truot-xuong": (0, -d),
        "nhay-len":    (0, int(d*0.55)), "roi-truot": (0, int(-d*0.7)), "nhoe-trai": (int(d*1.2), 0),
    }
    them = ""; move = None
    for h in hu:
        if h in B: them += B[h][0]
        elif h in MOVE:
            ddx, ddy = MOVE[h]
            move = f"\\move({x+ddx},{y+ddy},{x},{y},0,220)"
            them += "\\fad(70,0)" + ("\\blur10\\t(0,220,\\blur0)" if h == "nhoe-trai" else "")
    return them, move

def su_kien_du_lieu(ma, chu=None, t0=0.0, t1=2.0, W=1080, H=1920, x=None, y=None, co=1.0, mau=None, font=None, sang=None):
    """Dựng một kiểu lấy từ bộ gốc. chu=None thì giữ nguyên chữ mẫu."""
    r = du_lieu().get(ma) or du_lieu(True).get(ma)     # kể cả nhóm khối giao diện
    if r is None:
        raise KeyError(f"Chưa có kiểu '{ma}'")
    x = W // 2 if x is None else int(x)
    y = int(H * 0.51) if y is None else int(y)
    # gom lớp theo dòng (cùng chữ + cùng chỗ = các lớp chồng của một dòng)
    dong = []
    for l in r["lop"]:
        v = next((v for v in dong if v["chu"] == l["chu"]
                  and abs(v["dx"]-l["dx"]) < 0.02 and abs(v["dy"]-l["dy"]) < 0.02), None)
        if v is None: dong.append(dict(chu=l["chu"], dx=l["dx"], dy=l["dy"], lop=[l]))
        else: v["lop"].append(l)
    dong.sort(key=lambda v: (v["dy"], v["dx"]))
    if sang is None:
        sang = 1.0 if (r["ma"] in NEON or any(l.get("bong") for l in r["lop"])) else 0.0
    thay = [t.strip() for t in str(chu).split("|")] if chu else []
    L = []
    for i, v in enumerate(dong):
        t = thay[i] if i < len(thay) and thay[i] else (v["chu"] if not thay else thay[-1] if len(thay) < len(dong) and i >= len(thay) else v["chu"])
        if not t: continue
        hep = max(0.25, min(1.0, 1.0 - len(t)/26.0))          # chữ càng dài càng kéo về giữa
        px = int(x + v["dx"] * hep * H * co); py = int(y + v["dy"] * H * co)
        lop_sx = sorted(v["lop"], key=lambda l: -(l["day"] or 0))
        goc_l = lop_sx[-1]
        fs = max(12, int(goc_l["co"] * H * co))
        fsp = f"\\fsp{goc_l['gian']*fs:.1f}" if goc_l.get("gian") else ""
        fn = f"\\fn{font}" if font else ""
        m_fill = mau_ass((mau or [None]*9)[i] or goc_l["mau"]) if (mau and i < len(mau) and mau[i]) else mau_ass(goc_l["mau"])
        them, move = _hieu_ung(goc_l.get("hieu_ung") or [], px, py, co)
        dat = move or f"\\pos({px},{py})"
        cn = f"\\an5{dat}\\fs{fs}{fn}{fsp}{them}"
        lp = i * 12
        day_vien = [l for l in lop_sx if l["vien"] and (l["day"] or 0) > 0.03]
        if day_vien:                                   # viền chồng: viền dày vẽ trước
            for j, l in enumerate(day_vien):
                _ev(L, t0, t1, "G", t, cn + f"\\1c{mau_ass(l['mau'])}\\3c{mau_ass(l['vien'])}"
                                         f"\\bord{max(2, int((l['day'] or 0) * fs)):d}", layer=lp+j)
            _ev(L, t0, t1, "G", t, cn + f"\\1c{m_fill}\\bord0", layer=lp+len(day_vien))
        else:                                          # chữ nét; quầng chỉ thêm cho kiểu neon
            if sang > 0:
                for j, (nhoe, mo) in enumerate(((int(15*sang)+6, 150), (int(7*sang)+4, 115))):
                    _ev(L, t0, t1, "G", t, cn + f"\\1a&HFF&\\3c{m_fill}\\bord{max(4, int(fs*0.05))}"
                                                f"\\blur{nhoe}\\alpha&H{mo:02X}&", layer=lp+j)
            _ev(L, t0, t1, "G", t, cn + f"\\1c{m_fill}\\3c{VIEN_TOI}\\bord{max(2, int(fs*0.035))}",
                layer=lp+(2 if sang > 0 else 0))
        hu = goc_l.get("hieu_ung") or []
        if "loe-sang" in hu:                            # loé trắng nhấp nháy
            for k in range(4):
                s0 = t0 + 0.06 + k*0.11
                if s0 + 0.05 < t1: _ev(L, s0, s0+0.05, "G", t, cn + f"\\1c{TRANG}\\blur14", layer=lp+8)
        if "den-hong" in hu:                            # đèn hỏng: chớp tắt
            for a0, b0 in ((t0+0.08, t0+0.13), (t0+0.19, t0+0.23)):
                if b0 < t1: _ev(L, a0, b0, "G", t, cn + "\\1c&H00101010&\\bord0", layer=lp+9)
    return L

# ───────── API chính ─────────
def _co_vua_khung(chu, W, H, co):
    """thu cỡ chữ lại cho dòng dài nhất nằm gọn trong khung (chữ Việt dài hay tràn mép)"""
    if not chu: return co
    dai = max((len(t.strip()) for t in str(chu).split("|")), default=0)
    if dai < 1: return co
    rong_uoc = 0.50 * (0.082 * H * co) * dai          # ước lượng bề ngang
    gioi_han = 0.92 * W
    return co * gioi_han / rong_uoc if rong_uoc > gioi_han else co

def su_kien(kieu, chu, t0, t1, W=1080, H=1920, x=None, y=None, co=1.0, mau=None, font=None, sang=None):
    """Trả về danh sách dòng Dialogue của ASS cho một khối chữ.

    kieu : tên trong KIEU          chu : "Dòng 1|Dòng 2"
    x, y : tâm khối (mặc định giữa ngang, 51% chiều cao)
    co   : hệ số cỡ chữ (1.0 = như bộ gốc ở khung 1080x1920)
    mau  : danh sách mã màu ghi đè, ví dụ ["#FFD200", "#FFFFFF"]
    """
    co = _co_vua_khung(chu, W, H, co)
    if kieu not in KIEU:
        if kieu in du_lieu():
            return su_kien_du_lieu(kieu, chu, t0, t1, W, H, x, y, co, mau, font, sang)
        raise KeyError(f"Chưa có kiểu '{kieu}'. Có: {', '.join(list(KIEU) + list(du_lieu()))}")
    d = _tach(chu, KIEU[kieu]["dong"])
    x = W // 2 if x is None else int(x)
    y = int(H * 0.51) if y is None else int(y)
    m = [mau_ass(c) if str(c).startswith("#") else c for c in (mau or [])]
    L = []
    KIEU[kieu]["ham"](L, d, float(t0), float(t1), W, H, x, y, float(co), m, font)
    return L

def tao_ass(su_kien_list, W=1080, H=1920, font=None, ra=None):
    """Gói danh sách Dialogue thành file .ass dùng cho filter subtitles."""
    f = font or font_chinh()
    ra = ra or os.path.join(tempfile.gettempdir(), f"kieuchu_{os.getpid()}_{len(su_kien_list)}.ass")
    hd = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: {W}\nPlayResY: {H}\nWrapStyle: 2\n"
          "ScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
          "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,"
          "Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
          f"Style: G,{f},120,&H00FFFFFF,&H00FFFFFF,&H00101208,&H00101208,0,0,0,0,100,100,1,0,1,0,0,5,40,40,40,1\n"
          f"Style: Lab,{f},54,&H0000D2FF,&H0000D2FF,&H00101208,&H00101208,0,0,0,0,100,100,3,0,1,4,0,2,70,70,250,1\n"
          f"Style: Ghi,{f},40,&H00909090,&H00909090,&H00101208,&H00101208,0,0,0,0,100,100,2,0,1,3,0,2,70,70,190,1\n\n"
          "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    open(ra, "w", encoding="utf-8").write(hd + "\n".join(su_kien_list) + "\n")
    return ra

def loc_ass(ass_path):
    """Chuỗi filter subtitles đã kèm fontsdir — nối thẳng vào filter_complex."""
    return f"subtitles='{NT.loc(ass_path)}':fontsdir='{NT.loc(thu_muc_font())}'"

def ve_png(kieu, chu, W=1080, H=1920, x=None, y=None, co=1.0, mau=None, font=None, ra=None, giay=1.2):
    """Vẽ khối chữ ra PNG trong suốt để overlay.

    libass vẽ đè lên khung nền; nếu nền trong suốt thì kết quả vẫn trong suốt (ảnh rỗng).
    Nên phải vẽ hai lần — một lần trên nền đen, một lần trên nền trắng — rồi tính ngược
    ra độ đục: A = 1 - (trắng - đen)/255, màu = đen / A.
    """
    import numpy as _np
    ev = su_kien(kieu, chu, 0, 3, W, H, x, y, co, mau, font)
    p = tao_ass(ev, W, H, font)
    ra = ra or os.path.join(tempfile.gettempdir(), f"kieuchu_{kieu}.png")
    def _ve(nen):
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                            "-i", f"color=c={nen}:s={W}x{H}:d=3:r=30", "-ss", f"{giay}",
                            "-vf", f"{loc_ass(p)},format=rgb24", "-frames:v", "1",
                            "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True)
        return _np.frombuffer(r.stdout[:W*H*3], _np.uint8).reshape(H, W, 3).astype(_np.float32)
    den, trang = _ve("black"), _ve("white")
    a = _np.clip(1.0 - (trang - den).mean(axis=2) / 255.0, 0, 1)
    mauRGB = _np.where(a[..., None] > 0.01, den / _np.maximum(a[..., None], 0.01), 0)
    out = _np.zeros((H, W, 4), _np.uint8)
    out[..., :3] = _np.clip(mauRGB, 0, 255).astype(_np.uint8)
    out[..., 3] = (a * 255).astype(_np.uint8)
    try:
        import sys as _s; _s.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from chung import png_np
    except Exception:
        from PIL import Image                      # dự phòng
        Image.fromarray(out, "RGBA").save(ra); return ra
    png_np(ra, out)
    return ra

# ───────── video thử + bảng tra ─────────
def danh_sach_kieu(bo="tatca"):
    if bo == "tay": return [(k, v["ten"], v["goc"], v["vd"]) for k, v in KIEU.items()]
    dl = [(k, v["ten"], v["goc"], None) for k, v in du_lieu(bo == "canh").items()
          if bo != "canh" or v.get("loai") == "canh"]
    if bo == "bo": return dl
    return [(k, v["ten"], v["goc"], v["vd"]) for k, v in KIEU.items()] + dl

def demo(dang="doc", ra=None, bo="tatca", D=1.9):
    """Dựng video thử: mỗi kiểu một nhịp, kèm tên để gọi lại."""
    W, H = (1080, 1920) if str(dang).startswith("d") else (1920, 1080)
    ds = danh_sach_kieu(bo)
    ten_ra = f"kieu-chu-{'doc' if W < H else 'ngang'}{'' if bo == 'tatca' else '-' + bo}.mp4"
    ra = ra or os.path.expanduser(f"~/Downloads/video-kieu-chu-test/{ten_ra}")
    os.makedirs(os.path.dirname(ra), exist_ok=True)
    CY = int(H * 0.50); co = 1.0 if W < H else 0.85
    ev = []; moc = []
    for i, (k, ten, goc, vd) in enumerate(ds):
        a = i * D; b = a + D
        moc.append((a, k))
        ev += su_kien(k, vd, a + 0.05, b - 0.05, W, H, y=CY, co=co)
        _ev(ev, a, b, "Lab", f"{i+1:02d} · {k}", "\\fad(80,80)")
        _ev(ev, a, b, "Ghi", f"{ten}  ·  bộ gốc\\: {goc[:46]}", "\\fad(80,80)")
    T = len(ds) * D
    p = tao_ass(ev, W, H)
    tam = tempfile.mkdtemp(prefix="kieuchu_")
    hinh = f"{tam}/hinh.mp4"
    subprocess.run(["ffmpeg", "-v", "warning", "-stats", "-y", "-f", "lavfi",
                    "-i", f"color=c=0x08090A:s={W}x{H}:d={T:.2f}:r=30",
                    "-vf", f"{loc_ass(p)},format=yuv420p", *NT.ma_hoa("14M"),
                    "-t", f"{T:.2f}", hinh], check=True)
    K = kho()
    nhac = sorted(glob.glob(f"{K}/music/*.wav"))
    sfx = sorted(glob.glob(f"{K}/sfx/bup-*.wav")) or sorted(glob.glob(f"{K}/sfx/click-*.wav"))
    if nhac and sfx:
        vao = ["-stream_loop", "-1", "-i", nhac[0]]
        fc = [f"[0:a]atrim=0:{T:.2f},volume=-19dB[nen]"]
        tron = "[nen]"
        for j, (t, _) in enumerate(moc):
            vao += ["-i", sfx[j % len(sfx)]]
            fc.append(f"[{j+1}:a]adelay={int(t*1000)}|{int(t*1000)},volume=-11dB[s{j}]")
            tron += f"[s{j}]"
        fc.append(f"{tron}amix=inputs={len(moc)+1}:normalize=0:dropout_transition=0[a]")
        tron_wav = f"{tam}/tron.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y"] + vao +
                       ["-filter_complex", ";".join(fc), "-map", "[a]", "-t", f"{T:.2f}", tron_wav], check=True)
        import re as _re
        do = subprocess.run(["ffmpeg", "-hide_banner", "-i", tron_wav, "-af", "ebur128", "-f", "null", "-"],
                            capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
        I = float(_re.findall(r"I:\s+(-?[\d.]+) LUFS", do)[-1]); g = -16.0 - I
        subprocess.run(["ffmpeg", "-v", "warning", "-stats", "-y", "-i", hinh, "-i", tron_wav,
                        "-af", f"volume={g:.2f}dB,alimiter=limit=0.78:attack=3:release=60:level=disabled",
                        "-map", "0:v", "-map", "1:a",
                        "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "192k", "-t", f"{T:.2f}", ra], check=True)
    else:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", hinh, "-c", "copy", ra], check=True)
    print("XONG:", ra, f"{T:.1f}s ·", len(ds), "kiểu")
    return ra, moc, D, ds

def bang_anh(dang="doc", bo="tatca", moi_bang=12, D=1.9):
    """Dựng video rồi cắt mỗi kiểu một khung, ghép thành bảng tra ảnh để chọn kiểu."""
    ra, moc, D, ds = demo(dang, None, bo, D)
    thu = os.path.dirname(ra)
    W, H = (1080, 1920) if str(dang).startswith("d") else (1920, 1080)
    tam = tempfile.mkdtemp(prefix="bangchu_")
    for i, (t, k) in enumerate(moc):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t + D*0.75:.2f}", "-i", ra,
                        "-frames:v", "1", f"{tam}/{i:03d}.png"], check=True)
    anh = sorted(glob.glob(f"{tam}/*.png")); ras = []
    cot = 4
    for s0 in range(0, len(anh), moi_bang):
        nhom = anh[s0:s0+moi_bang]
        hang = (len(nhom) + cot - 1) // cot
        vao = []
        for a in nhom: vao += ["-i", a]
        fc = "".join(f"[{i}:v]scale=420:-2[a{i}];" for i in range(len(nhom)))
        fc += "".join(f"[a{i}]" for i in range(len(nhom))) + f"xstack=inputs={len(nhom)}:layout="
        fc += "|".join(f"{(i%cot)}_{(i//cot)}".replace("0_", "0_").replace("_", "_") for i in range(len(nhom)))
        out = f"{thu}/bang-{s0//moi_bang + 1}.png"
        lay = "|".join("+".join(["0" if (i % cot) == 0 else "w0"*1] ) for i in range(len(nhom)))
        # dùng tile cho gọn thay vì xstack
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", ra, "-vf",
                        f"select='" + "+".join(f"eq(n\\,{int((t + D*0.75)*30)})" for t, _ in moc[s0:s0+moi_bang]) +
                        f"',scale=420:-2,tile={cot}x{hang}:padding=8:color=0x1A1A1A", "-frames:v", "1",
                        "-fps_mode", "passthrough", out], check=True)
        ras.append(out)
    print("bảng tra:", ", ".join(os.path.basename(x) for x in ras))
    return ras

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "demo":
        demo(*(sys.argv[2:] or ["doc"]))
    else:
        print("Font đang dùng:", font_chinh(), "· thư mục font:", thu_muc_font())
        print(bang())
