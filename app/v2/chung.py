# -*- coding: utf-8 -*-
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Tiện ích chung Studio 2.0: đường dẫn, lệnh ngoài, json, băm, hồ sơ & token, khổ hình.
Không ghi cứng đường dẫn máy — mọi thứ đi qua đây."""
import os, sys, json, hashlib, subprocess, unicodedata, time, copy, glob

V2 = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(V2)
sys.path.insert(0, os.path.join(SKILL, "studio"))
from moi_truong import python_da_chon
SCRIPTS = os.path.join(SKILL, "scripts")
NAO = os.path.join(SKILL, "nao")
CA_NHAN = os.path.join(NAO, "ca-nhan")
if V2 in sys.path:
    sys.path.remove(V2)
sys.path.insert(0, V2)                 # gói 2.0 (nao/, kho/, dung/…) đứng trước
if SCRIPTS not in sys.path:
    sys.path.append(SCRIPTS)           # công cụ 1.x (kit, config, nen_tang, soi_tu_dai…) đứng sau — scripts/nao.py không được đè v2/nao

if os.name == "nt":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace"); sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def nfc(s):
    return unicodedata.normalize("NFC", s) if isinstance(s, str) else s


def python_skill():
    selected = python_da_chon()
    if selected:
        return selected
    p = os.path.join(SKILL, ".venv", "Scripts", "python.exe") if os.name == "nt" else os.path.join(SKILL, ".venv", "bin", "python")
    return p if os.path.exists(p) else sys.executable


def sh(cmd, kiem=True, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if kiem and r.returncode:
        raise RuntimeError(f"Lệnh lỗi: {' '.join(map(str, cmd[:6]))} …\n{r.stderr[-1500:]}")
    return r


def doc(p, mac_dinh=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return mac_dinh


def ghi(p, obj):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    tmp = f"{p}.{os.getpid()}.tmp"                     # 1.2.13: tmp riêng từng tiến trình
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    for i in range(40):                                 # Windows: file đang mở ở tiến trình khác → WinError 5, thử lại
        try:
            os.replace(tmp, p)
            break
        except PermissionError:
            if i == 39:
                raise
            time.sleep(0.05 * (i + 1))
    return p


def bam(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16]


def bay_gio():
    return time.strftime("%Y-%m-%d %H:%M:%S")


# ───────── kho
def kho():
    """thư mục kho sạch (VideoKit-Free) — dùng kit.kho() của 1.x để tôn trọng cấu hình máy"""
    try:
        import kit
        return kit.kho()
    except Exception:
        d = os.path.expanduser("~/Videos/VideoKit-Free")
        return d


def bo_mua():
    try:
        import kit
        return kit.bo_mua()
    except Exception:
        return ""


def thu_muc_ban_do():
    d = os.path.join(kho(), "ban-do-kho")
    os.makedirs(d, exist_ok=True)
    return d


def tim_file(ten, goc=None):
    """tìm file theo tên (so NFC) trong kho sạch + bộ mua"""
    ten = nfc(ten)
    for g in ([goc] if goc else [kho(), bo_mua()]):
        if not g or not os.path.isdir(g):
            continue
        for r, _, fs in os.walk(g):
            for f in fs:
                if nfc(f) == ten:
                    return os.path.join(r, f)
    return None


_DUONG_THAT = {}


def duong_that(p):
    """đường dẫn có thật trên đĩa dù tên thư mục là NFC hay NFD (bộ quà tặng giải nén từ Mac lưu NFD; danh mục ghi NFC)"""
    if not p:
        return None
    if os.path.exists(p):
        return p
    if p in _DUONG_THAT:
        return _DUONG_THAT[p]
    q = os.path.normpath(p)
    phan = q.split(os.sep)
    cur = phan[0] + os.sep if phan[0].endswith(":") else (os.sep if q.startswith(os.sep) else phan[0])
    for x in phan[1:]:
        nx = nfc(x)
        try:
            khop = next((y for y in os.listdir(cur) if nfc(y) == nx), None)
        except OSError:
            khop = None
        if khop is None:
            _DUONG_THAT[p] = None
            return None
        cur = os.path.join(cur, khop)
    _DUONG_THAT[p] = cur
    return cur


def thu_muc_font():
    return [p for p in (os.path.join(kho(), "fonts"), os.path.join(kho(), "fonts", "tinh"), os.path.join(V2, "font-them")) if os.path.isdir(p)]


DAM_LUI = {}      # 1.3: đường font biến thiên dùng THAY một bản đậm cụ thể đang thiếu → độ đậm cần đặt


def do_dam_tu_ten(ten):
    """'Lexend-SemiBold.ttf' → 600 · 'X-Black' → 900 · không rõ → None"""
    t = os.path.splitext(os.path.basename(str(ten)))[0].lower().replace(" ", "").replace("_", "")
    for k, v in (("extralight", 200), ("ultralight", 200), ("semibold", 600), ("demibold", 600), ("extrabold", 800),
                 ("ultrabold", 800), ("thin", 100), ("light", 300), ("medium", 500), ("black", 900), ("heavy", 900),
                 ("bold", 700), ("regular", 400)):
        if k in t:
            return v
    return None


def font_path(ten):
    if not ten:
        ten = "BeVietnamPro-Bold.ttf"
    if os.path.isabs(ten):
        that = duong_that(ten)
        if that:
            return that
    for d in thu_muc_font():
        p = os.path.join(d, ten)
        if os.path.exists(p):
            return p
    p = tim_file(ten)
    if p:
        return p
    ho = os.path.splitext(os.path.basename(ten))[0].split("-")[0].lower()      # 1.3: thiếu đúng file → cùng HỌ (vd Lexend-Var)
    for d in thu_muc_font():
        for f in sorted(os.listdir(d)):
            if f.lower().startswith(ho) and f.lower().endswith((".ttf", ".otf")):
                p = os.path.join(d, f)
                dam = do_dam_tu_ten(ten)
                if dam and "var" in f.lower():          # bản biến thiên: nhớ độ đậm được yêu cầu (vd SemiBold → 600) cho nen.F
                    DAM_LUI[p] = dam
                return p
    for ten2 in ("BeVietnamPro-Bold.ttf", "Inter-Var.ttf"):    # lùi về font đi kèm skill (v2/font-them) — không bao giờ dừng vì thiếu kho
        for d in thu_muc_font():
            p = os.path.join(d, ten2)
            if os.path.exists(p):
                return p
    raise FileNotFoundError(ten)


# ───────── hồ sơ & token
def ho_so_hien_tai():
    if os.environ.get("HO_SO", "").strip():
        return os.environ["HO_SO"].strip()
    try:
        return open(os.path.join(CA_NHAN, "HIEN-TAI"), encoding="utf-8").read().strip() or None
    except OSError:
        return None


BANG_NHAN = ["#FF6B5A", "#18C3B4", "#8B6CFF", "#B6E62E", "#3BA7FF", "#FF4FA3", "#FF8A1F", "#3DDC97", "#E5384F", "#5B8CFF"]
TOKEN_MAC_DINH = {
    "mau": {"sang": "#FAF8F2", "toi": "#111114", "nhan": "#F2C230", "nhan_tu_canh": True},
    "chu": {"phu_de": {"font": "BeVietnamPro-Bold.ttf", "co": 60, "vi_tri": "tu_chon", "che_do": "tu_chon"},
            "nhan": {"font": "BeVietnamPro-Black.ttf", "font_phu": "PlayfairDisplay-Italic.ttf"},
            "tieu_de": {"font": "Anton-Regular.ttf"}},
    "am": {"giong": -16.0, "nhac_duoi_giong": 18.0, "dich": -15.5, "dinh": -2.0, "nen_lra": None},
    "khung": "9:16", "toc_do": 1.0,
    "cam": [], "luat_cung": ["khong_den_trang"], "tu_duyet": True,
    "bia": {"kieu_uu_tien": [], "xu_ly_chu": "bong_mem"},
    "phong_cach_nhanh": None,
}


def _tron(a, b):
    out = copy.deepcopy(a)
    for k, v in (b or {}).items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _tron(out[k], v)
        else:
            out[k] = v
    return out


def token(ho_so=None, goi=None):
    """token gộp: mặc định trung tính → (gói phong cách nhanh) → token.json của hồ sơ (hoặc dựng từ cau-hinh.json cũ).
    Hồ sơ đè gói: gu chủ kênh thắng gói chọn nhanh, trừ khi gói được chọn tường minh cho video này (goi=)."""
    hs = ho_so or ho_so_hien_tai()
    t = copy.deepcopy(TOKEN_MAC_DINH)
    if hs:                         # 1.2.13: hồ sơ chưa đặt màu nhấn → mỗi kênh một màu riêng (trước: mọi kênh cùng vàng mặc định)
        t["mau"]["nhan"] = BANG_NHAN[int(hashlib.sha1(hs.encode("utf-8")).hexdigest(), 16) % len(BANG_NHAN)]
    tk_hs = {}
    if hs:
        p = os.path.join(CA_NHAN, hs, "token.json")
        if os.path.exists(p):
            tk_hs = doc(p, {})
        else:
            cfg = doc(os.path.join(CA_NHAN, hs, "cau-hinh.json"), {})
            m, c, a = cfg.get("mau", {}), cfg.get("chu", {}), cfg.get("am_thanh", {})
            tk_hs = {"mau": {k2: v for k2, v in (("nhan", m.get("nhan")), ("sang", m.get("chu_chinh")), ("toi", m.get("nen_card"))) if v},
                     "chu": {"phu_de": {"font": c.get("phu_de")} if c.get("phu_de") else {},
                             "tieu_de": {"font": c.get("title_to")} if c.get("title_to") else {}},
                     "am": {k2: v for k2, v in (("giong", a.get("giong")), ("dich", a.get("dich_cuoi")), ("dinh", a.get("dinh_that"))) if v is not None}}
    goi_id = goi or tk_hs.get("phong_cach_nhanh")
    if goi_id:
        g = doc(os.path.join(V2, "phong_cach", "goi", f"{goi_id}.json"), {})
        if g.get("token"):                          # 1.2.15: gói nhanh giữ NHỊP/cấu trúc; màu + font không ghim — AI chọn theo video
            g["token"] = {k: v for k, v in g["token"].items() if k not in ("mau", "chu")}
        if goi:            # chọn tường minh cho video này → gói đè gu thường ngày, nhưng giữ luật cứng/cấm của hồ sơ
            t = _tron(_tron(t, tk_hs), g.get("token", {}))
            t["cam"] = sorted(set(tk_hs.get("cam", [])) | set(g.get("token", {}).get("cam", [])))
            t["luat_cung"] = sorted(set(t.get("luat_cung", [])) | set(tk_hs.get("luat_cung", [])))
            t["phong_cach_nhanh"] = goi_id
            return t
        t = _tron(t, g.get("token", {}))
    t = _tron(t, tk_hs)
    if hs and not t.get("mau", {}).get("nhan2"):          # 1.2.11: màu nhấn phụ + mức sáng tạo đặt trong Studio (cau-hinh.json)
        cfg = doc(os.path.join(CA_NHAN, hs, "cau-hinh.json"), {}) or {}
        if (cfg.get("mau") or {}).get("nhan2"):
            t.setdefault("mau", {})["nhan2"] = cfg["mau"]["nhan2"]
    if hs and not (t.get("bia") or {}).get("phong"):       # 1.2.12: gu bìa của khách (tu_dong | dung | khung_that) đặt trong hồ sơ
        cfg = doc(os.path.join(CA_NHAN, hs, "cau-hinh.json"), {}) or {}
        b = cfg.get("bia") if isinstance(cfg.get("bia"), dict) else {}
        if b.get("phong"):
            t.setdefault("bia", {})["phong"] = b["phong"]
        if b.get("kieu_uu_tien") and not (t.get("bia") or {}).get("kieu_uu_tien"):
            t.setdefault("bia", {})["kieu_uu_tien"] = b["kieu_uu_tien"]
    if hs:                                                 # 1.2.15: mục người dùng KHOÁ trong tab Thương hiệu (cau-hinh.json "khoa")
        cfg = doc(os.path.join(CA_NHAN, hs, "cau-hinh.json"), {}) or {}
        khoa = [k for k in (cfg.get("khoa") or []) if isinstance(k, str)]
        if khoa:
            t["khoa"] = sorted(set(t.get("khoa") or []) | set(khoa))
            c_ = cfg.get("chu") or {}
            if "mau_nhan" in khoa and (cfg.get("mau") or {}).get("nhan"):
                t.setdefault("mau", {})["nhan"] = cfg["mau"]["nhan"]
            if "font_phu_de" in khoa and c_.get("phu_de"):
                t.setdefault("chu", {}).setdefault("phu_de", {})["font"] = c_["phu_de"]
            if "font_tieu_de" in khoa and c_.get("title_to"):
                t.setdefault("chu", {}).setdefault("tieu_de", {})["font"] = c_["title_to"]
    if "khong_den_trang" not in t.get("luat_cung", []):
        t.setdefault("luat_cung", []).append("khong_den_trang")     # luật hệ: luôn bật
    return t


def khoa_phong_cach(tk):
    """1.2.15: những mục phong cách NGƯỜI DÙNG tự khoá trong hồ sơ (token "khoa": ["mau_nhan", "font_phu_de", …]) — chỉ các mục này
    AI không được đổi; còn lại mỗi video AI tự chọn (Studio là công cụ, không ôm gu đặt sẵn của ai)."""
    return set((tk or {}).get("khoa") or [])


def token_video(du_an, tk=None, kh=None):
    """token của MỘT video = token hồ sơ (chụp lúc bat-dau) + phong cách AI chọn cho video này (ke-hoach.phong_cach_ai), trừ mục
    người dùng đã khoá. Dùng chung cho dựng, bìa, chấm, CapCut để cả bộ cùng một màu/một font."""
    if tk is None:
        tk = (doc(os.path.join(du_an, "01-ho-so.json"), {}) or {}).get("token") or token()
    kh = kh if kh is not None else (doc(os.path.join(du_an, "ke-hoach.json"), {}) or {})
    ai = kh.get("phong_cach_ai") or {}
    if not ai:
        return tk
    t = copy.deepcopy(tk)
    khoa = khoa_phong_cach(t)
    m = t.setdefault("mau", {})
    for k_ai, k in (("mau_nhan", "nhan"), ("mau_nhan2", "nhan2"), ("mau_sang", "sang"), ("mau_toi", "toi")):
        if ai.get(k_ai) and k_ai not in khoa:
            m[k] = ai[k_ai]
    c = t.setdefault("chu", {})
    f = dict(ai.get("font") or {})
    if f.get("tieu_de"):                      # 1.2.16: vai AI không ghi → theo font AI chọn (không rơi về font cài sẵn trong token)
        f.setdefault("nhan", f["tieu_de"]); f.setdefault("phu", f["nhan"]); f.setdefault("script", f["phu"])
    for vai, duong in (("phu_de", ("phu_de", "font")), ("tieu_de", ("tieu_de", "font")), ("nhan", ("nhan", "font")),
                       ("phu", ("nhan", "font_phu")), ("script", ("script", "font"))):
        if f.get(vai) and f"font_{vai}" not in khoa:
            c.setdefault(duong[0], {})[duong[1]] = f[vai]
    return t


def kich_thuoc(tk_or_khung):
    k = tk_or_khung.get("khung") if isinstance(tk_or_khung, dict) else tk_or_khung
    return (1920, 1080) if k in ("16:9", "ngang") else (1080, 1920)


def hex_rgb(h, a=None):
    h = h.lstrip("#")
    c = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return c + (a,) if a is not None else c


# ───────── dự án
def goc_du_an():
    return os.path.expanduser(os.environ.get("STUDIO_DU_AN") or "~/Videos/studio-du-an")


def ffprobe(p):
    r = sh(["ffprobe", "-v", "error", "-show_entries",
            "format=duration:stream=codec_type,width,height,r_frame_rate,avg_frame_rate:stream_side_data=rotation:stream_tags=rotate",
            "-of", "json", p])
    j = json.loads(r.stdout)
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})

    def _fps(x):
        try:
            a, b = (x or "0/0").split("/")
            return float(a) / float(b) if float(b) else 0.0
        except (ValueError, ZeroDivisionError):
            return 0.0
    fps = _fps(v.get("avg_frame_rate")) or _fps(v.get("r_frame_rate")) or 30.0     # 1.2.13: VFR điện thoại → khung TRUNG BÌNH
    w, h = v.get("width"), v.get("height")
    xoay = [abs(int(float(d.get("rotation", 0) or 0))) for d in (v.get("side_data_list") or [])]
    xoay.append(abs(int(float((v.get("tags") or {}).get("rotate", 0) or 0))))
    if any(x % 180 == 90 for x in xoay):                                             # 1.2.13: video xoay → khổ HIỂN THỊ
        w, h = h, w
    return {"duong": p, "dai": float(j.get("format", {}).get("duration", 0)), "w": w, "h": h,
            "fps": round(min(fps, 120.0), 3), "co_am": any(s.get("codec_type") == "audio" for s in j.get("streams", []))}


# ───────── 1.2.13: độ dài khách yêu cầu
def dai_muc_tieu(yeu_cau):
    """lời yêu cầu → {giay, lo, hi, kieu} hoặc None. '30s', '30 giây', 'tầm 45s', '1 phút', '1p30', 'dưới 30s', 'tối đa 1 phút'.
    'dưới / tối đa / không quá' → trần cứng; còn lại cho lệch 20% ngắn hơn, 12% (≥ 2 s) dài hơn."""
    import re as _r
    yc = (yeu_cau or "").lower()
    m = _r.search(r"(\d{1,2})\s*(?:p|ph[uú]t)\s*(\d{1,2})\s*(?:s|gi[aâ]y)?\b", yc)
    giay = int(m.group(1)) * 60 + int(m.group(2)) if m else None
    if giay is None:
        m = _r.search(r"(\d{1,3}(?:[.,]5)?)\s*(?:s|gi[aâ]y|giay|sec|seconds?)\b", yc)
        if m:
            giay = float(m.group(1).replace(",", "."))
    if giay is None:
        m = _r.search(r"(\d(?:[.,]5)?)\s*(?:ph[uú]t|phut|min)\b", yc)
        if m:
            giay = float(m.group(1).replace(",", ".")) * 60
    if not giay or not (8 <= giay <= 600):
        return None
    tran = bool(_r.search(r"(dưới|duoi|tối đa|toi da|không quá|khong qua|max|ngắn hơn)\s*\d", yc))
    lo = giay * (0.6 if tran else 0.8)
    hi = giay if tran else giay + max(2.0, giay * 0.12)
    return {"giay": giay, "lo": round(lo, 1), "hi": round(hi, 1), "kieu": "tran" if tran else "khoang"}
