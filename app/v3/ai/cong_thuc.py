# -*- coding: utf-8 -*-
"""Chuẩn hoá công thức AI (cong-thuc.json) → ke-hoach.json (đủ trường, giải font/kho, kiểm giây).

chuan_hoa(du_an, cong_thuc) -> (ke_hoach, loi_chan[])
Máy KHÔNG thêm lớp, KHÔNG đổi kiểu hoạt ảnh, KHÔNG đổi màu, KHÔNG có số thẩm mỹ riêng (1.2.21):
mọi trường AI bỏ trống điền theo thứ tự  lớp → bài học/Style Spec đang bật (hoc/ap_spec) → QUYẾT ĐỊNH KÊNH (quyet-dinh.json,
ai/hop_dong.py) → lỗi `thieu_truong` (có `duong` = đường dẫn trường, vd lop[3].kieu_dang.co).
Mọi số máy buộc phải sửa (tràn thời lượng, font thiếu glyph, id kho không có) đều ghi vào ke_hoach["may_sua"].
Kho: nghĩa → top-5 kèm số đo (diem, chu_ky, da_dung, dur) ghi ke_hoach["tra_kho"][i]["ung_vien"], top-1 dùng để dựng bản xem;
kho không có LOẠI đó → một cảnh báo gộp `kho_khong_co_<loai>` (ke_hoach["canh_bao_chuan_hoa"]) thay vì lỗi chặn từng lớp.
"""
import glob, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung
from ai import hop_dong

try:
    from kho import tim as kho_tim          # kho.tim.tim(loai, nghia, n) / kho.tim.lay(id)
    KHO_SAN_SANG = True
except Exception:
    kho_tim = None
    KHO_SAN_SANG = False

KIEU_LOP = ("chu", "khoi", "the", "hinh", "video", "duong", "py", "mau", "web")
HOA_TRON = ("normal", "screen", "add", "multiply", "overlay", "soft_light", "lighten", "darken")
ANCHOR = ("tl", "tc", "tr", "ml", "mc", "mr", "bl", "bc", "br")
SO_VOI = ("khung", "mat", "duoi_cam", "tren_dau")
ANIM_KIEU = ("fade", "slide", "pop", "blur", "wipe", "typewriter", "flip", "tilt", "none")
EASE = ("linear", "in", "out", "in_out", "back", "spring", "expo", "step")
TACH = ("none", "tu", "ky_tu", "dong")
VAI_FONT = ("tieu_de", "phu_de", "nhan")
KHO_ID = re.compile(r"^(nhac|sfx|font|nen|icon|lut|video|anh)\.[a-z0-9][a-z0-9_\-]*$")
MAU_RE = re.compile(r"^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
KY_TU_VIET = "ệẤởữđƯơẳ"
FONT_MAC_DINH_DIR = chung.duong("font_mac_dinh")
SO_UNG_VIEN_KHO = 5
_FONT_DAU = {}
_FONT_CMAP = {}
_THIEU = object()


# ---------------------------------------------------------------- tiện ích chung
def so(x, mac_dinh=None, lo=None, hi=None):
    """float(x); không đổi được → mac_dinh (None = không có số: trường thiếu, máy không bịa). Kẹp [lo, hi] = giới hạn vật lý."""
    try:
        v = float(x)
    except Exception:
        if mac_dinh is None:
            return None
        try:
            v = float(mac_dinh)
        except Exception:
            return None
    if lo is not None:
        v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def nguyen(x, mac_dinh=None, lo=None, hi=None):
    v = so(x, mac_dinh, lo, hi)
    return None if v is None else int(round(v))


def mau_chuan(m, mac_dinh=None):
    """'#fff' → '#FFFFFF', '#fffc' → '#FFFFFFCC' (chỉ đổi cách ghi, không đổi màu). Không hợp lệ → mac_dinh."""
    if not isinstance(m, str) or not MAU_RE.match(m.strip()):
        return mac_dinh
    s = m.strip()[1:]
    if len(s) in (3, 4):
        s = "".join(c * 2 for c in s)
    return "#" + s.upper()


def font_du_dau(duong):
    """font có glyph tiếng Việt? (fontTools cmap, cache)"""
    if not duong or not os.path.isfile(duong):
        return False
    if duong in _FONT_DAU:
        return _FONT_DAU[duong]
    ok = False
    try:
        from fontTools.ttLib import TTFont
        f = TTFont(duong, lazy=True, fontNumber=0)
        cmap = f.getBestCmap() or {}
        ok = all(ord(c) in cmap for c in KY_TU_VIET)
        f.close()
    except Exception:
        ok = False
    _FONT_DAU[duong] = ok
    return ok


def font_du_chu(duong, text):
    """font có đủ glyph cho CHỮ NÀY? (chữ tiếng Anh/không dấu không bị ép đổi font; cache cmap theo tệp)"""
    if not duong or not os.path.isfile(duong):
        return False
    can = {c for c in str(text or "") if not c.isspace()}
    if not can:
        return True
    cmap = _FONT_CMAP.get(duong)
    if cmap is None:
        try:
            from fontTools.ttLib import TTFont
            f = TTFont(duong, lazy=True, fontNumber=0)
            cmap = set((f.getBestCmap() or {}).keys())
            f.close()
        except Exception:
            cmap = set()
        _FONT_CMAP[duong] = cmap
    return all(ord(c) in cmap for c in can)


# ---------------------------------------------------------------- thời gian theo cat
def dur_cat(cat):
    return sum(max(0.0, c["b"] - c["a"]) for c in cat)


def goc_sang_tp(cat, t_goc, src=0):
    """giây gốc (của nguồn src) → giây thành phẩm; None nếu bị cắt bỏ."""
    d = 0.0
    for c in cat:
        if c.get("src", 0) == src and c["a"] - 1e-6 <= t_goc <= c["b"] + 1e-6:
            return d + (t_goc - c["a"])
        d += c["b"] - c["a"]
    return None


def tp_sang_goc(cat, t):
    """giây thành phẩm → (src, giây gốc)."""
    d = 0.0
    for c in cat:
        l = c["b"] - c["a"]
        if t <= d + l + 1e-6:
            return c.get("src", 0), c["a"] + max(0.0, t - d)
        d += l
    if cat:
        return cat[-1].get("src", 0), cat[-1]["b"]
    return 0, t


# ---------------------------------------------------------------- QUYẾT ĐỊNH KÊNH — nguồn mặc định duy nhất
def _lay_duong(d, khoa):
    cur = d
    for k in str(khoa).split("."):
        if not isinstance(cur, dict) or k not in cur:
            return _THIEU
        cur = cur[k]
    return cur


class QuyetDinh:
    """đọc quyet_dinh[khoa]; thiếu → ghi nhận thieu_truong (gộp theo khoá quyết định, kèm đường dẫn trường trong công thức)."""

    def __init__(self, qd, du_an="", im=False, may_sua=None):
        self.qd = qd if isinstance(qd, dict) else None
        self.du_an = du_an
        self.ms = may_sua
        self.im = im                   # True = quyết định đang lỗi khuôn → không báo thieu_truong lẻ (đã có lỗi quyet_dinh_sai)
        self.thieu = {}                # khoa → [duong…]
        self._da = set()
        self.rieng = []                # thieu_truong không gắn khoá quyết định (AI bắt buộc ghi)

    def co(self):
        return self.qd is not None

    def lay(self, khoa, duong):
        v = _lay_duong(self.qd or {}, khoa)
        if v is _THIEU:
            if (khoa, duong) not in self._da:
                self._da.add((khoa, duong))
                self.thieu.setdefault(khoa, []).append(duong)
            return None
        return json.loads(json.dumps(v)) if isinstance(v, (dict, list)) else v

    def dien(self, d, k, khoa, duong, khoa_phu=None):
        """d[k] nếu AI ghi (khác None) — không thì quyết định kênh[khoa] (→ [khoa_phu] nếu có, vd bia.chu.co → chu.co)"""
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
        return self.lay2(khoa, khoa_phu, f"{duong}.{k}") if khoa_phu else self.lay(khoa, f"{duong}.{k}")

    def tuy(self, khoa):
        """giá trị tuỳ chọn của quyết định (không báo thiếu)"""
        v = _lay_duong(self.qd or {}, khoa)
        return None if v is _THIEU else (json.loads(json.dumps(v)) if isinstance(v, (dict, list)) else v)

    def lay2(self, khoa, khoa_phu, duong):
        """khoa (vd bia.chu.gian) → khoa_phu (vd chu.gian) → thieu_truong ghi theo khoa_phu"""
        v = _lay_duong(self.qd or {}, khoa)
        if v is not _THIEU:
            return json.loads(json.dumps(v)) if isinstance(v, (dict, list)) else v
        return self.lay(khoa_phu, duong)

    def bat_buoc(self, duong, ly_do):
        """trường AI BẮT BUỘC ghi (không có mặc định ở kênh)"""
        if duong not in self._da:
            self._da.add(duong)
            self.rieng.append((duong, ly_do))

    def ket(self, loi):
        if self.im:
            return
        for duong, ly_do in self.rieng:
            loi.append({"id": "thieu_truong", "lop": duong.split(".")[0], "duong": duong, "mo_ta": f"thiếu `{duong}` — {ly_do}"})
        if not self.thieu:
            return
        if self.qd is None:
            loi.insert(0, {"id": "thieu_truong", "lop": "quyet_dinh", "duong": "quyet_dinh", "khong_sua_duoc": False,
                           "mo_ta": f"KÊNH CHƯA CÓ QUYẾT ĐỊNH — Write `{os.path.join(self.du_an, 'quyet-dinh-kenh.json')}` theo khuôn "
                                    f"(python v3/ai/hop_dong.py khuon; mẫu v3/ai/quyet-dinh.mau.json) rồi Write lại công thức; "
                                    f"{sum(len(v) for v in self.thieu.values())} trường bỏ trống đang không có mặc định"})
        for khoa, ds in self.thieu.items():
            loi.append({"id": "thieu_truong", "lop": ds[0].split(".")[0], "duong": ds[0], "quyet_dinh": khoa, "so": len(ds), "cung": ds[1:8],
                        "mo_ta": f"thiếu `{ds[0]}`" + (f" (+{len(ds) - 1} chỗ khác)" if len(ds) > 1 else "")
                                 + f" — AI không ghi và quyết định kênh không có `{khoa}`: ghi vào công thức hoặc thêm `{khoa}` vào quyet-dinh-kenh.json"})


# ---------------------------------------------------------------- lớp giải font / kho
class GiaiTaiNguyen:
    def __init__(self, du_an, phong_cach, ho_so, may_sua, loi, tra_kho, Q=None, canh_bao=None):
        self.du_an, self.pc, self.ho_so = du_an, phong_cach or {}, ho_so or {}
        self.may_sua, self.loi, self.tra_kho = may_sua, loi, tra_kho
        self.Q = Q or QuyetDinh(None, du_an, im=True)
        self.canh_bao = canh_bao if canh_bao is not None else []
        self._font_cache = {}
        self._quet = None
        self._co_loai_cache = {}

    # ---- kho
    def _lay(self, id_):
        if not KHO_SAN_SANG:
            return None
        try:
            return kho_tim.lay(id_)
        except Exception:
            return None

    def _tim(self, loai, nghia, n=SO_UNG_VIEN_KHO, tranh=None, dur=None):
        if not KHO_SAN_SANG:
            return []
        try:
            return kho_tim.tim(loai=loai, nghia=nghia, n=n, tranh=list(tranh or []), dur=dur) or []
        except TypeError:
            try:
                return kho_tim.tim(loai=loai, nghia=nghia, n=n) or []
            except Exception:
                return []
        except Exception:
            return []

    def _co_loai(self, loai):
        """kho có mục nào thuộc loại này không (cache) — không có → cảnh báo gộp một lần, không chặn"""
        if loai in self._co_loai_cache:
            return self._co_loai_cache[loai]
        co = False
        if KHO_SAN_SANG:
            for l in str(loai).split(","):
                if self._tim(l.strip(), "", 1):
                    co = True
                    break
        self._co_loai_cache[loai] = co
        if not co:
            ten = str(loai).replace(",", "_")
            self.canh_bao.append({"id": f"kho_khong_co_{ten}", "lop": "kho", "thong_tin": True,
                                  "mo_ta": f"kho trên máy không có mục loại `{loai}` — mọi chỗ tra loại này bị bỏ qua (không dựng được tài nguyên đó); lập chỉ mục kho hoặc đổi cách làm không cần {loai}"})
        return co

    @staticmethod
    def _ung_vien(kq):
        ra = []
        for m in kq[:SO_UNG_VIEN_KHO]:
            sd = m.get("so_do") or {}
            ra.append({"id": m.get("id"), "diem": m.get("diem"), "diem_td": m.get("diem_td"), "khop": m.get("khop"), "chu_ky": m.get("chu_ky"),
                       "da_dung": m.get("da_dung"), "dur": m.get("dur", sd.get("dur")), "ten": m.get("ten")})
        return ra

    def kho(self, gia_tri, loai, lop_id, bat_buoc=True, tranh=None, dur=None):
        """id kho | đường dẫn | nghĩa → đường dẫn file (None nếu không có). Nghĩa → tra top-5 kèm số đo (tra_kho[].ung_vien), dựng bằng top-1.
        Kho không có loại → cảnh báo gộp, không lỗi. Có loại nhưng không khớp nghĩa → lỗi tai_nguyen_khong_co nếu bat_buoc."""
        if gia_tri is None or gia_tri == "":
            return None
        g = str(gia_tri).strip()
        if os.path.isabs(g) and os.path.isfile(g):
            return g
        trong_du_an = os.path.join(self.du_an, g)
        if os.path.isfile(trong_du_an):
            return trong_du_an
        if KHO_ID.match(g):
            m = self._lay(g)
            if m and m.get("duong") and os.path.isfile(m["duong"]):
                return m["duong"]
            if not KHO_SAN_SANG:
                self.loi.append({"id": "tai_nguyen_khong_co", "lop": lop_id, "mo_ta": f"mô-đun kho chưa sẵn sàng, không tra được id `{g}`", "khong_sua_duoc": True})
                return None
            if not self._co_loai(loai):
                return None
            # id không có → tra theo nghĩa lấy từ tên id (bỏ số), ghi may_sua
            nghia = re.sub(r"[-_]+", " ", g.split(".", 1)[1])
            nghia = re.sub(r"\d+", " ", nghia).strip()
            kq = self._tim(loai, nghia, SO_UNG_VIEN_KHO) if nghia else []
            kq = [m for m in kq if m.get("duong") and os.path.isfile(m["duong"])]
            if kq:
                self.may_sua.append({"lop": lop_id, "sua": "kho", "tu": g, "den": kq[0].get("id"), "mo_ta": f"id `{g}` không có → tra nghĩa “{nghia}” → {kq[0].get('id')}"})
                self.tra_kho.append({"lop": lop_id, "loai": loai, "nghia": nghia, "id": kq[0].get("id"), "duong": kq[0]["duong"], "tu_id": g, "ung_vien": self._ung_vien(kq)})
                return kq[0]["duong"]
            if bat_buoc:
                self.loi.append({"id": "tai_nguyen_khong_co", "lop": lop_id, "mo_ta": f"không có id kho `{g}` ({loai}) và không có gì hợp nghĩa `{nghia}` — ghi id khác hoặc nghĩa khác"})
            return None
        # nghĩa
        if not KHO_SAN_SANG:
            self.tra_kho.append({"lop": lop_id, "loai": loai, "nghia": g, "id": None, "mo_ta": "mô-đun kho chưa sẵn sàng — bỏ qua", "ung_vien": []})
            return None
        if not self._co_loai(loai):
            return None
        kq = self._tim(loai, g, SO_UNG_VIEN_KHO, tranh, dur) or (self._tim(loai, g, SO_UNG_VIEN_KHO, None, dur) if (tranh or dur) else [])
        kq = [m for m in kq if m.get("duong") and os.path.isfile(m["duong"])]
        if kq:
            self.tra_kho.append({"lop": lop_id, "loai": loai, "nghia": g, "id": kq[0].get("id"), "duong": kq[0]["duong"], "ung_vien": self._ung_vien(kq)})
            return kq[0]["duong"]
        if bat_buoc:
            self.loi.append({"id": "tai_nguyen_khong_co", "lop": lop_id, "mo_ta": f"kho không có {loai} nào hợp nghĩa `{g}` — ghi nghĩa khác hoặc id kho (tra: python v3/kho/tim.py {loai.split(',')[0]} \"…\")"})
        return None

    # ---- font
    def _quet_font_kho(self):
        """quét ttf/otf trong kho_goc (dự phòng khi kho chưa lập chỉ mục); cache 1 file."""
        if self._quet is not None:
            return self._quet
        p = os.path.join(chung.duong("kho_chi_muc"), "font-quet.json")
        d = chung.doc_json(p)
        goc = chung.duong("kho_goc")
        if d and d.get("goc") == goc and d.get("ds"):
            self._quet = d["ds"]
            return self._quet
        ds = []
        if goc and os.path.isdir(goc):
            for ext in ("ttf", "otf", "TTF", "OTF"):
                ds += glob.glob(os.path.join(goc, "**", "*." + ext), recursive=True)
        ds = sorted(set(ds))[:2000]
        self._quet = [{"duong": f, "ten": os.path.splitext(os.path.basename(f))[0], "du_dau": font_du_dau(f)} for f in ds]
        chung.ghi_json(p, {"goc": goc, "ds": self._quet})
        return self._quet

    @staticmethod
    def _kieu_trong_ten(t):
        """'Montserrat ExtraBold Italic' → (họ 'montserrat', dam 800, nghieng True); không có từ kiểu → (họ, None, None)"""
        t_ = chung.khong_dau(str(t)).lower()
        bang = (("thin", 100), ("hairline", 100), ("extralight", 200), ("ultralight", 200), ("light", 300), ("regular", 400), ("book", 400), ("normal", 400),
                ("medium", 500), ("semibold", 600), ("demibold", 600), ("extrabold", 800), ("ultrabold", 800), ("black", 900), ("heavy", 900), ("bold", 700))
        dam = None
        for tu, d_ in bang:
            if re.search(r"\b" + tu + r"\b", t_.replace("-", " ").replace("_", " ")):
                dam = d_; break
        m_ = re.search(r"\b([1-9]00)\b", t_)
        if m_:
            dam = int(m_.group(1))
        ngh = True if re.search(r"\bitalic\b|\boblique\b", t_) else None
        ho = re.sub(r"\b(thin|hairline|extra ?light|ultra ?light|light|regular|book|normal|medium|semi ?bold|demi ?bold|extra ?bold|ultra ?bold|black|heavy|bold|italic|oblique|[1-9]00)\b", " ", t_)
        return chung.slug(ho), dam, ngh

    @staticmethod
    def _chon_font(kq, t, dam, nghieng, du):
        """trong kết quả tra kho: ưu tiên đúng HỌ, rồi đúng nghiêng, rồi gần độ đậm AI ghi (font biến thiên = mọi độ đậm), rồi đủ ký tự
        — đối sánh theo TÊN AI ghi, không có gu đậm/mảnh của máy"""
        ho_q, dam_t, ngh_t = GiaiTaiNguyen._kieu_trong_ten(t)
        ho_q = GiaiTaiNguyen._khoa_ten(ho_q)                      # R2: so họ không phân biệt khoảng trắng/gạch ("Be Vietnam Pro" ↔ "BeVietnamPro-Bold")
        dam = dam if dam is not None else dam_t
        nghieng = nghieng if nghieng is not None else ngh_t
        tot = None
        for i, m in enumerate(kq):
            p = m.get("duong")
            if not p or not os.path.isfile(p) or not du(p):
                continue
            sd = m.get("so_do") or {}
            ho_m = GiaiTaiNguyen._khoa_ten(str(sd.get("ho") or m.get("ten") or ""))
            diem = 0.0
            if ho_q and (ho_m.startswith(ho_q) or ho_q in ho_m):
                diem += 10
            elif ho_q:
                continue                                           # R2: KHÔNG đúng họ AI ghi → không chọn (trước lấy tệp đầu bảng BM25 khác họ)
            ng_m = bool(sd.get("nghieng")) or bool(re.search(r"italic|oblique", str(m.get("ten") or ""), re.I))
            if nghieng is not None:
                diem += 4 if ng_m == bool(nghieng) else -4
            elif ng_m:
                diem -= 2
            if dam is not None:
                if sd.get("var") and "wght" in (sd.get("truc") or []):
                    diem += 3
                else:
                    diem += 3 - min(3.0, abs(int(sd.get("dam") or 400) - int(dam)) / 100.0)
            diem -= i * 0.05
            if tot is None or diem > tot[0]:
                tot = (diem, p)
        return tot[1] if tot else None

    def _tim_font_ho(self, t):
        """tra font theo TÊN HỌ: không khử trùng họ (cần đủ mọi độ đậm/nghiêng của cùng họ để chọn đúng tệp)"""
        if not KHO_SAN_SANG:
            return []
        try:
            return kho_tim.tim(loai="font", nghia=t, n=40, da_dang=False) or []
        except Exception:
            return self._tim("font", t, 40)

    @staticmethod
    def _khoa_ten(t):
        """'Be Vietnam Pro' / 'BeVietnamPro-Bold' → 'bevietnampro' / 'bevietnamprobold' (so khớp họ không phân biệt khoảng trắng/gạch)"""
        return chung.slug(str(t or "")).replace("-", "")

    def _font_trong_thu_muc_mac_dinh(self, t, du, dam=None):
        """font-mac-dinh/ của app: khớp theo TÊN HỌ AI ghi (không phân biệt khoảng trắng/gạch), chọn độ đậm gần `dam` AI ghi; không có gu đậm/mảnh"""
        kt = self._khoa_ten(t)
        if not kt or not os.path.isdir(FONT_MAC_DINH_DIR):
            return None
        ung = sorted(glob.glob(os.path.join(FONT_MAC_DINH_DIR, "*.[to]tf")) + glob.glob(os.path.join(FONT_MAC_DINH_DIR, "*.[TO]TF")))
        hop = []
        for u in ung:
            ten_u = os.path.splitext(os.path.basename(u))[0]
            if kt in self._khoa_ten(ten_u) and du(u):
                _, d_u, _ = self._kieu_trong_ten(ten_u)
                hop.append((abs((d_u if d_u is not None else 400) - (dam if dam is not None else 400)), ten_u, u))
        if not hop:
            return None
        hop.sort()
        return hop[0][2]

    def _giai_font(self, t, dam, nghieng, du, lop_id):
        """một tên/id/đường dẫn → (đường dẫn|None, lý do|None) — không tự bù font khác"""
        t = str(t or "").strip()
        if not t:
            return None, "không có tên font"
        if os.path.isfile(t):
            return (t, None) if du(t) else (None, f"font `{os.path.basename(t)}` thiếu glyph")
        if KHO_ID.match(t):
            m = self._lay(t)
            d = m.get("duong") if m else None
            if not d:
                return None, (f"không có id font `{t}`" if KHO_SAN_SANG else f"mô-đun kho chưa sẵn sàng, không tra được `{t}`")
            return (d, None) if du(d) else (None, f"font `{t}` thiếu glyph tiếng Việt")
        kq = self._tim_font_ho(t)
        d = self._chon_font(kq, t, dam, nghieng, du)
        if not d:
            d = self._font_trong_thu_muc_mac_dinh(t, du, dam)
        if not d:
            kt = self._khoa_ten(t)
            for m in self._quet_font_kho():
                if kt and kt in self._khoa_ten(m["ten"]) and du(m["duong"]):
                    d = m["duong"]; break
        if not d and re.fullmatch(r"[A-Za-z][A-Za-z0-9 +\-]{1,40}", t):     # tên họ kiểu Google Fonts → máy tự tải
            try:
                from kho import font_mang as _FM
                tep = _FM.tai(t, log=lambda *_: None)
                if tep:
                    d = self._chon_font(self._tim_font_ho(t), t, dam, nghieng, du)
                    if not d:
                        for p_ in tep:
                            if du(p_):
                                d = p_; break
                    if d:
                        self.may_sua.append({"lop": lop_id, "sua": "font_tai", "tu": t, "den": d, "mo_ta": f"font `{t}` chưa có trong kho → đã tải Google Fonts ({len(tep)} tệp)"})
            except Exception:
                pass
        if not d:
            co_ten = any(self._khoa_ten(t) in self._khoa_ten(m.get("ten")) for m in kq)
            return None, (f"font `{t}` có trong kho nhưng thiếu glyph cần" if co_ten else f"không tìm thấy font `{t}` (kho, font-mac-dinh, Google Fonts)")
        return d, None

    def font(self, ten, lop_id, vai_mac_dinh="nhan", text=None, dam=None, nghieng=None, duong=None):
        """vai | font.<id> | tên họ | đường dẫn → đường dẫn font. text=None: phải đủ dấu Việt (phụ đề, font kênh);
        text="…": chỉ cần đủ ký tự của chữ đó. Không giải được → thử font của KÊNH cùng vai (quyết định) + may_sua; vẫn không → lỗi font_thieu_dau."""
        goc = ten
        vai = vai_mac_dinh
        if isinstance(ten, str) and ten in VAI_FONT:
            vai = ten
            ten = (self.pc.get("font") or {}).get(vai) or ""
            if ten in VAI_FONT:
                ten = ""
        du = (lambda d: font_du_chu(d, text)) if text is not None else font_du_dau
        khoa = (goc, vai, None if text is None else "".join(sorted({c for c in str(text) if not c.isspace()})), dam, nghieng)
        if khoa in self._font_cache:
            return self._font_cache[khoa]
        d, ly_do = (None, f"không có font cho vai `{vai}`") if not ten else self._giai_font(ten, dam, nghieng, du, lop_id)
        if not d and ten and text is not None:
            # chữ có ký tự lẻ font không có (vd "→", emoji): font vẫn đủ dấu Việt thì nhận; engine vẽ ký tự thiếu bằng font dự phòng và ghi may_sua (dung/chu.py)
            d2, _ = self._giai_font(ten, dam, nghieng, font_du_dau, lop_id)
            if d2:
                thieu = "".join(sorted({c for c in str(text) if not c.isspace() and not font_du_chu(d2, c)}))[:12]
                self.may_sua.append({"lop": lop_id, "sua": "font_glyph", "tu": str(ten), "den": d2, "mo_ta": f"font `{ten}` thiếu ký tự «{thieu}» trong chữ — giữ font (đủ dấu Việt), ký tự đó vẽ bằng font dự phòng lúc dựng"})
                d = d2
        if not d:
            kenh = ((self.Q.qd or {}).get("font") or {}).get(vai) if self.Q.co() else None
            if kenh and str(kenh) != str(ten):
                d2, _ = self._giai_font(kenh, dam, nghieng, du, lop_id)
                if d2:
                    self.may_sua.append({"lop": lop_id, "sua": "font", "tu": str(ten), "den": d2, "mo_ta": f"{ly_do} → dùng font kênh `{kenh}` (quyet-dinh.font.{vai})"})
                    d = d2
        if not d:
            self.loi.append({"id": "font_thieu_dau", "lop": lop_id, "mo_ta": f"{ly_do} — ghi font khác (id kho / tên họ Google Fonts / đường dẫn) ở "
                                                                            f"{duong or ('phong_cach.font.' + vai)} hoặc quyet-dinh.font.{vai}"})
        self._font_cache[khoa] = d
        return d


# ---------------------------------------------------------------- chuẩn hoá từng phần (mặc định = quyết định kênh)
def _vien_ds(x):
    if isinstance(x, dict):
        return [x]
    if isinstance(x, list):
        return [i for i in x if isinstance(i, dict)]
    return []


def _vien_chuan(kd, Q, khoa, duong, khoa_phu=None):
    """vien: AI ghi mảng/object → từng mục cần w + mau (thiếu → thieu_truong); AI không ghi → quyết định kênh[khoa] (tuỳ chọn → [khoa_phu] → [])"""
    if "vien" in kd:
        if kd.get("vien") is None:
            return []
        ra = []
        for i, v in enumerate(_vien_ds(kd.get("vien"))):
            w = so(v.get("w"), None, 0, 60); m = mau_chuan(v.get("mau"))
            if w is None:
                Q.bat_buoc(f"{duong}.vien[{i}].w", "viền AI ghi phải có w (px)")
            if m is None:
                Q.bat_buoc(f"{duong}.vien[{i}].mau", "viền AI ghi phải có mau")
            if w is not None and m is not None:
                ra.append({"w": w, "mau": m})
        return ra
    v = Q.tuy(khoa)
    if v is None and khoa_phu:
        v = Q.tuy(khoa_phu)
    return [{"w": so(x.get("w"), 0, 0, 60), "mau": mau_chuan(x.get("mau"), "#000000")} for x in _vien_ds(v)] if v else []


def _bong_chuan(kd, Q, khoa, duong, khoa_phu=None):
    """bong: x/y/mo bỏ = 0 (không lệch, không nhoè — không phải gu); mau bắt buộc khi AI ghi mục; AI không ghi → quyết định (tuỳ chọn) → []"""
    if "bong" in kd:
        if kd.get("bong") is None:
            return []
        ra = []
        for i, b in enumerate(_vien_ds(kd.get("bong"))):
            m = mau_chuan(b.get("mau"))
            if m is None:
                Q.bat_buoc(f"{duong}.bong[{i}].mau", "bóng AI ghi phải có mau")
                continue
            ra.append({"x": so(b.get("x"), 0), "y": so(b.get("y"), 0), "mo": so(b.get("mo"), 0, 0, 120), "mau": m})
        return ra
    v = Q.tuy(khoa)
    if v is None and khoa_phu:
        v = Q.tuy(khoa_phu)
    return [{"x": so(b.get("x"), 0), "y": so(b.get("y"), 0), "mo": so(b.get("mo"), 0, 0, 120), "mau": mau_chuan(b.get("mau"), "#000000")} for b in _vien_ds(v)] if v else []


def _nen_chu_chuan(kd, Q, khoa, duong, khoa_phu=None):
    """nen chữ: AI null/[] = cố ý không nền; AI {mau[, dem, bo]} → thiếu dem/bo lấy ở quyết định[khoa] (dict) → thieu_truong;
    AI không ghi → quyết định[khoa] (null | {mau,dem,bo}; tuỳ chọn → [khoa_phu])"""
    q = Q.tuy(khoa)
    if q is None and khoa_phu:
        q = Q.tuy(khoa_phu)
    if "nen" in kd:
        n = kd.get("nen")
        if not isinstance(n, dict) or not n:
            return None
        m = mau_chuan(n.get("mau"))
        if m is None:
            Q.bat_buoc(f"{duong}.nen.mau", "nền chữ AI ghi phải có mau")
            return None
        dem = n.get("dem") if isinstance(n.get("dem"), list) and len(n.get("dem")) >= 2 else (q.get("dem") if isinstance(q, dict) else None)
        bo = so(n.get("bo"), None, 0, 200)
        if bo is None and isinstance(q, dict):
            bo = so(q.get("bo"), None, 0, 200)
        if not dem or bo is None:                     # quyết định chu.nen = null → đệm/bo THẺ của kênh (the.dem/the.bo, bắt buộc trong khuôn)
            the_q = Q.tuy("the") or {}
            if not dem and isinstance(the_q.get("dem"), list) and len(the_q["dem"]) >= 2:
                dem = the_q["dem"]
            if bo is None:
                bo = so(the_q.get("bo"), None, 0, 200)
            if dem and bo is not None and Q.ms is not None:
                Q.ms.append({"lop": duong.split(".")[0], "sua": "nen", "mo_ta": f"{duong}.nen thiếu dem/bo và quyết định chu.nen = null → dùng the.dem/the.bo của kênh ({dem}, {bo})"})
        if not dem:
            Q.bat_buoc(f"{duong}.nen.dem", "nền chữ cần dem [x,y] (quyết định kênh chu.nen = null, the.dem không có)")
        if bo is None:
            Q.bat_buoc(f"{duong}.nen.bo", "nền chữ cần bo (px)")
        if not dem or bo is None:
            return None
        return {"mau": m, "dem": [so(dem[0], 0, 0, 200), so(dem[-1], 0, 0, 200)], "bo": bo}
    if isinstance(q, dict) and q.get("mau"):
        dem = q.get("dem") or [0, 0]
        return {"mau": mau_chuan(q.get("mau"), "#000000"), "dem": [so(dem[0], 0, 0, 200), so(dem[-1], 0, 0, 200)], "bo": so(q.get("bo"), 0, 0, 200)}
    return None


def _kieu_dang_chu(kd, Q, duong, goc="chu", font_vai="tieu_de"):
    """kiểu dáng chữ (lớp chu, dòng khoi, chữ bìa, phụ đề): trường trống → quyết định kênh[goc].* → (goc ≠ chu) chu.*.
    hoa/gian bỏ ở cả hai = không đổi chữ (False / 0 — phép đồng nhất, không phải gu)."""
    kd = dict(kd) if isinstance(kd, dict) else {}
    phu = "chu" if goc != "chu" else None

    def g(k, bat_buoc=True):
        if kd.get(k) is not None:
            return kd[k]
        if not bat_buoc:
            v = Q.tuy(f"{goc}.{k}")
            return v if v is not None else (Q.tuy(f"chu.{k}") if phu else None)
        return Q.dien(kd, k, f"{goc}.{k}", duong, khoa_phu=(f"chu.{k}" if phu else None))
    hoa = g("hoa", False)
    can = g("can")
    gr_q = kd.get("gradient") if "gradient" in kd else (Q.tuy(f"{goc}.gradient") if Q.tuy(f"{goc}.gradient") is not None else (Q.tuy("chu.gradient") if phu else None))
    ra = {
        "font": kd.get("font") or Q.tuy(f"{goc}.font") or font_vai,      # R2: lớp chu cũng đọc quyết định chu.font (trước bỏ qua)
        "co": so(g("co"), None, 10, 600),
        "dam": nguyen(g("dam"), None, 100, 900),
        "mau": mau_chuan(g("mau")),
        "hoa": bool(hoa) if hoa is not None else False,
        "gian": so(g("gian", False), 0, -0.2, 0.5),
        "nghieng": so(kd.get("nghieng"), 0, -30, 30),
        "dong": so(g("dong"), None, 0.7, 2.5),
        "can": can if can in ("trai", "giua", "phai") else None,
        "vien": _vien_chuan(kd, Q, f"{goc}.vien", duong, khoa_phu=(f"chu.vien" if phu else None)),
        "bong": _bong_chuan(kd, Q, f"{goc}.bong", duong, khoa_phu=(f"chu.bong" if phu else None)),
        "nen": _nen_chu_chuan(kd, Q, f"{goc}.nen", duong, khoa_phu=(f"chu.nen" if phu else None)),
        "gradient": None, "noi_3d": None,
        "rong_max": so(g("rong_max"), None, 0.2, 1),
    }
    if "gradient" not in kd and isinstance(gr_q, dict):
        kd["gradient"] = gr_q
    n3 = kd.get("noi_3d")
    if isinstance(n3, dict):
        sau, goc3, m3 = so(n3.get("sau"), None, 0, 120), so(n3.get("goc"), None, -360, 360), mau_chuan(n3.get("mau"))
        for k_, v_ in (("sau", sau), ("goc", goc3), ("mau", m3)):
            if v_ is None:
                Q.bat_buoc(f"{duong}.noi_3d.{k_}", "chữ nổi khối AI chọn phải ghi đủ sau (px), goc (độ), mau")
        if sau is not None and goc3 is not None and m3 is not None:
            ra["noi_3d"] = {"sau": sau, "goc": goc3, "mau": m3}
            if mau_chuan(n3.get("mau2")):
                ra["noi_3d"]["mau2"] = mau_chuan(n3.get("mau2"))
    gr = kd.get("gradient")
    if isinstance(gr, dict):
        ms = [mau_chuan(m) for m in (gr.get("mau") if isinstance(gr.get("mau"), list) else [])][:4]
        ms = [m for m in ms if m]
        goc_g = so(gr.get("goc"), None, -360, 360)
        if len(ms) < 2:
            Q.bat_buoc(f"{duong}.gradient.mau", "gradient AI chọn cần ≥ 2 màu hợp lệ")
        if goc_g is None:
            Q.bat_buoc(f"{duong}.gradient.goc", "gradient AI chọn phải ghi goc (độ)")
        if len(ms) >= 2 and goc_g is not None:
            ra["gradient"] = {"mau": ms, "goc": goc_g}
    return ra


def _kieu_dang_the(kd, Q, duong):
    kd = dict(kd) if isinstance(kd, dict) else {}
    chu = kd.get("chu") if isinstance(kd.get("chu"), dict) else {}

    def g(k):
        return Q.dien(kd, k, f"the.{k}", duong)

    def gc(k):
        return Q.dien(chu, k, f"the.chu.{k}", f"{duong}.chu")
    hinh = g("hinh")
    dem = g("dem")
    vien = None
    if "vien" in kd:
        v = kd.get("vien")
        v = v[0] if isinstance(v, list) and v else (v if isinstance(v, dict) else None)
        if v:
            w, m = so(v.get("w"), None, 0, 40), mau_chuan(v.get("mau"))
            if w is None:
                Q.bat_buoc(f"{duong}.vien.w", "viền thẻ AI ghi phải có w")
            if m is None:
                Q.bat_buoc(f"{duong}.vien.mau", "viền thẻ AI ghi phải có mau")
            if w is not None and m is not None:
                vien = {"w": w, "mau": m}
    else:
        q = Q.tuy("the.vien")
        if isinstance(q, dict) and q.get("mau"):
            vien = {"w": so(q.get("w"), 0, 0, 40), "mau": mau_chuan(q.get("mau"), "#FFFFFF")}
    return {
        "hinh": hinh if hinh in ("pill", "rect", "circle") else None,
        "mau": mau_chuan(g("mau")),
        "vien": vien,
        "bo": so(g("bo"), None, 0, 300),
        "bong": _bong_chuan(kd, Q, "the.bong", duong),
        "dem": [so(dem[0], 0, 0, 200), so(dem[-1], 0, 0, 200)] if isinstance(dem, list) and len(dem) >= 2 else None,
        "chu": {"co": so(gc("co"), None, 10, 300), "mau": mau_chuan(gc("mau")), "font": gc("font") or "nhan", "dam": nguyen(gc("dam"), None, 100, 900)},
    }


def _anim_buoc(d, Q, khoa, duong, may_sua, lop_id):
    """một bước vào/ra: AI ghi gì giữ nấy, trống → quyết định kênh[khoa].*; kiểu không có → máy đổi sang kiểu kênh và ghi may_sua"""
    d = dict(d) if isinstance(d, dict) else {}
    k = Q.dien(d, "kieu", f"{khoa}.kieu", duong)
    if k is not None and k not in ANIM_KIEU:
        k2 = Q.lay(f"{khoa}.kieu", f"{duong}.kieu")
        may_sua.append({"lop": lop_id, "sua": "anim", "tu": k, "den": k2, "mo_ta": f"kiểu anim `{k}` không có → {k2} (quyết định kênh)"})
        k = k2
    if k == "none":                          # không hoạt ảnh: dai 0 / ease linear là phép đồng nhất, không cần quyết định
        return {"kieu": "none", "dai": 0.0, "ease": "linear"}
    e = Q.dien(d, "ease", f"{khoa}.ease", duong)
    ra = {"kieu": k, "dai": so(Q.dien(d, "dai", f"{khoa}.dai", duong), None, 0, 3), "ease": e if e in EASE else (None if e is None else "linear")}
    if e is not None and e not in EASE:
        may_sua.append({"lop": lop_id, "sua": "anim", "tu": e, "den": "linear", "mo_ta": f"ease `{e}` không có → linear"})
    for kh in ("tu", "toi"):
        if isinstance(d.get(kh), dict):
            ra[kh] = d[kh]
    if "kieu" not in d:                      # AI không ghi gì cho bước này → lấy cả tu/toi của kênh (nếu có)
        q = Q.lay(khoa, duong) if Q.co() else None
        if isinstance(q, dict):
            for kh in ("tu", "toi"):
                if isinstance(q.get(kh), dict) and kh not in ra:
                    ra[kh] = q[kh]
    return ra


def _anim_chuan(a, Q, duong, may_sua, lop_id, goc="anim"):
    a = dict(a) if isinstance(a, dict) else {}
    ra = {"vao": _anim_buoc(a.get("vao"), Q, f"{goc}.vao", f"{duong}.vao", may_sua, lop_id),
          "ra": _anim_buoc(a.get("ra"), Q, f"{goc}.ra", f"{duong}.ra", may_sua, lop_id)}
    ra["nhoe_dong"] = so(a.get("nhoe_dong"), None, 0, 4)
    if ra["nhoe_dong"] is None:
        ra["nhoe_dong"] = so(Q.tuy("anim.nhoe_dong"), 0, 0, 4) if goc == "anim" else 0.0      # tuỳ chọn; thiếu = 0 (tắt)
    for kh_, tt_ in (("vao", "tu"), ("ra", "toi")):                                           # trạng thái đầu/cuối có SỐ → quyết định anim.kieu.<kieu>
        b_ = ra[kh_]
        if isinstance(b_, dict) and b_.get("kieu") in ("slide", "pop", "blur", "flip", "tilt") and not isinstance(b_.get(tt_), dict):
            st_ = Q.lay(f"anim.kieu.{b_['kieu']}", f"{duong}.{kh_}.{tt_}")
            if isinstance(st_, dict):
                b_[tt_] = st_
    t = a.get("tach", "none")
    ra["tach"] = t if t in TACH else "none"
    if ra["tach"] != "none":
        ra["so_le"] = so(a.get("so_le"), None, 0, 1)
        if ra["so_le"] is None:
            ra["so_le"] = so(Q.lay("anim.so_le", f"{duong}.so_le"), 0, 0, 1)
    else:
        ra["so_le"] = 0.0
    kf = []
    for i, k in enumerate(a.get("keyframes") or []):
        if isinstance(k, dict) and "t" in k:
            k = dict(k)
            k["t"] = so(k["t"], 0, 0)
            dai = so(k.get("dai"), None, 0, 5)
            k["dai"] = dai if dai is not None else so(Q.lay("anim.keyframe_dai", f"{duong}.keyframes[{i}].dai"), 0, 0, 5)
            e = k.get("ease")
            k["ease"] = e if e in EASE else (Q.lay("anim.keyframe_ease", f"{duong}.keyframes[{i}].ease") or "linear")
            kf.append(k)
    ra["keyframes"] = sorted(kf, key=lambda k: k["t"])
    if "ken_burns" in a and isinstance(a["ken_burns"], dict):
        z = a["ken_burns"].get("z")
        if not (isinstance(z, list) and len(z) >= 2):
            z = Q.lay("anim.ken_burns", f"{duong}.ken_burns.z") or [1.0, 1.0]
        ra["ken_burns"] = {"z": [so(z[0], 1, 1, 2), so(z[-1], 1, 1, 2)]}
    return ra


def _vi_tri_chuan(v, kieu, Q, duong, may_sua, lop_id):
    """anchor/so_voi trống → quyết định vi_tri.*; x,y: so_voi=khung bắt buộc AI ghi, so_voi theo mặt bỏ = 0 (không lệch); w,h → hop_mac_dinh[kieu]"""
    v = dict(v) if isinstance(v, dict) else {}
    an = Q.dien(v, "anchor", "vi_tri.anchor", duong)
    if an is not None and an not in ANCHOR:
        an2 = Q.lay("vi_tri.anchor", f"{duong}.anchor")
        may_sua.append({"lop": lop_id, "sua": "anchor", "tu": an, "den": an2, "mo_ta": f"anchor `{an}` không có → {an2} (quyết định kênh)"})
        an = an2
    sv = Q.dien(v, "so_voi", "vi_tri.so_voi", duong)
    if sv is not None and sv not in SO_VOI:
        may_sua.append({"lop": lop_id, "sua": "so_voi", "tu": sv, "den": "khung", "mo_ta": f"so_voi `{sv}` không có → khung"})
        sv = "khung"
    ra = {"anchor": an, "so_voi": sv}
    for k in ("x", "y"):
        val = so(v.get(k), None, -1, 2)
        if val is None:
            if sv == "khung" or sv is None:
                Q.bat_buoc(f"{duong}.{k}", "vị trí trong khung là quyết định của AI (0..1)")
            else:
                val = 0.0
        ra[k] = val
    can_wh = kieu in ("hinh", "video", "py", "mau", "web")
    hop = None
    for k in ("w", "h"):
        if k in v or can_wh:
            val = so(v.get(k), None, 0.02, 4000 if kieu == "web" else 1)
            if val is None and can_wh:
                if hop is None:
                    hop = Q.lay(f"vi_tri.hop_mac_dinh.{kieu}", f"{duong}.{k}") or [None, None]      # R2: video cũng đọc quyết định hop_mac_dinh.video (không còn [1,1] máy)
                val = so(hop[0 if k == "w" else 1], None, 0.02, 4000 if kieu == "web" else 1)
            if val is not None:
                ra[k] = val
    if v.get("theo_mat") and sv in ("tren_dau", "duoi_cam", "mat"):      # y (và x với "mat") tính theo chiều cao/rộng mặt
        ra["theo_mat"] = True
    if v.get("nhom"):                      # xếp chồng: lớp cùng nhóm đang hiện cùng lúc → engine xếp cột/hàng không chồng
        ra["nhom"] = str(v["nhom"])[:40]
        xep = Q.dien(v, "xep", "vi_tri.xep", duong)
        ra["xep"] = xep if xep in ("doc", "ngang") else "doc"
        c = so(v.get("cach"), None, 0, 400)
        ra["cach"] = c if c is not None else so(Q.lay("vi_tri.cach_nhom", f"{duong}.cach"), 0, 0, 400)
    return ra


def _kd_phu(kd, may_sua, lid, video=True):
    """trường lớp phủ video/ảnh: hoa_tron, do_trong 0..1, lap, toc_do (bỏ = không hoà trộn/không trong/không lặp/tốc độ 1 — không phải gu)"""
    ra = {}
    ht = kd.get("hoa_tron")
    if ht is not None:
        if ht not in HOA_TRON:
            may_sua.append({"lop": lid, "sua": "hoa_tron", "tu": ht, "den": "normal", "mo_ta": f"hoa_tron `{ht}` không có → normal"})
            ht = "normal"
        ra["hoa_tron"] = ht
    if kd.get("do_trong") is not None:
        ra["do_trong"] = so(kd.get("do_trong"), 1, 0, 1)
    if video:
        if kd.get("lap") is not None:
            ra["lap"] = bool(kd.get("lap"))
        if kd.get("toc_do") is not None:
            ra["toc_do"] = so(kd.get("toc_do"), 1, 0.25, 4)
    return ra


def _kd_hinh(kd, Q, duong, may_sua, lid, video):
    fit = Q.dien(kd, "fit", "hinh.fit", duong)
    vien = None
    if "vien" in kd:
        vs = _vien_ds(kd.get("vien"))
        if vs:
            w, m = so(vs[0].get("w"), None, 0, 40), mau_chuan(vs[0].get("mau"))
            if w is None:
                Q.bat_buoc(f"{duong}.vien.w", "viền AI ghi phải có w")
            if m is None:
                Q.bat_buoc(f"{duong}.vien.mau", "viền AI ghi phải có mau")
            if w is not None and m is not None:
                vien = {"w": w, "mau": m}
    else:
        q = Q.tuy("hinh.vien")
        if isinstance(q, dict) and q.get("mau"):
            vien = {"w": so(q.get("w"), 0, 0, 40), "mau": mau_chuan(q.get("mau"), "#FFFFFF")}
    ra = {"fit": fit if fit in ("cover", "contain") else None, "bo": so(Q.dien(kd, "bo", "hinh.bo", duong), None, 0, 300),
          "vien": vien, "bong": _bong_chuan(kd, Q, "hinh.bong", duong)}
    ra.update(_kd_phu(kd, may_sua, lid, video=video))
    return ra


def _doi_moc_cong_thuc(ct, giu_cu, giu_moi):
    """mốc giây THÀNH PHẨM theo cat cũ → giây gốc → giây thành phẩm theo cat mới (lớp, sfx, camera, chuyển cảnh, nền mới)"""
    def tp_sang_goc_(t, giu):
        tp = 0.0
        for g in giu:
            d = float(g["b"]) - float(g["a"])
            if t <= tp + d + 1e-6:
                return float(g["a"]) + max(0.0, t - tp)
            tp += d
        return float(giu[-1]["b"]) if giu else t

    def goc_sang_tp_(t, giu):
        tp = 0.0
        for g in giu:
            a, b = float(g["a"]), float(g["b"])
            if t < a:
                return tp
            if t <= b + 1e-6:
                return tp + (t - a)
            tp += b - a
        return tp

    def doi(t):
        try:
            return round(goc_sang_tp_(tp_sang_goc_(float(t), giu_cu), giu_moi), 3)
        except Exception:
            return t
    for l in ct.get("lop") or []:
        if isinstance(l, dict):
            for k in ("t0", "t1"):
                if l.get(k) is not None:
                    l[k] = doi(l[k])
            if isinstance(l.get("t1"), (int, float)) and isinstance(l.get("t0"), (int, float)) and l["t1"] <= l["t0"]:
                l["t1"] = round(l["t0"] + 0.5, 3)
    for s_ in ((ct.get("am") or {}).get("sfx") or []):
        if isinstance(s_, dict) and s_.get("t") is not None:
            s_["t"] = doi(s_["t"])
    for c in ct.get("camera") or []:
        if isinstance(c, dict) and c.get("t") is not None:
            c["t"] = doi(c["t"])
    for c in ct.get("chuyen_canh") or []:
        if isinstance(c, dict) and c.get("t") is not None:
            c["t"] = doi(c["t"])
    for n in ct.get("nen_moi") or []:
        if isinstance(n, dict):
            for k in ("t0", "t1"):
                if n.get(k) is not None:
                    n[k] = doi(n[k])


def _the_mau(mid):
    try:
        from dung import mau as _M
        r = _M.lay(mid)
        return (r or {}).get("the") or {}
    except Exception:
        return {}


def _moc_tu_loi(du_an, cat, t0, t1, chu):
    """giây (tính từ t0) từng từ của `chu` theo loi.json trong [t0, t1] thành phẩm — khớp từ (bỏ dấu, bỏ câu cú), từ không khớp
    thì nội suy. Không có chữ → mốc của các từ lời trong khoảng. Không có lời → None."""
    loi = chung.doc_json(os.path.join(du_an, "doc", "loi.json")) or {}
    tus = []
    for w in loi.get("tu") or []:
        a = goc_sang_tp(cat, float(w["a"]), int(w.get("src", 0)))
        if a is not None and t0 - 0.15 <= a < t1:
            tus.append((max(0.0, a - t0), re.sub(r"[^0-9a-z]", "", chung.khong_dau(w.get("w", "")))))
    if not tus:
        return None
    ws = [re.sub(r"[^0-9a-z]", "", chung.khong_dau(x)) for x in chu.split()] if chu.strip() else []
    if not ws:
        return [round(a, 3) for a, _ in tus]
    moc, j = [None] * len(ws), 0
    for i, w in enumerate(ws):
        for k in range(j, min(len(tus), j + 4)):
            if w and tus[k][1] == w:
                moc[i] = tus[k][0]; j = k + 1
                break
    if all(m is None for m in moc):
        if abs(len(tus) - len(ws)) <= max(1, len(ws) // 4):      # cùng số từ ~ → ghép theo thứ tự
            moc = [tus[min(i, len(tus) - 1)][0] for i in range(len(ws))]
        else:
            return None
    biet = [(i, m) for i, m in enumerate(moc) if m is not None]
    for i in range(len(moc)):
        if moc[i] is None:
            truoc = max((b for b in biet if b[0] < i), default=None, key=lambda b: b[0])
            sau = min((b for b in biet if b[0] > i), default=None, key=lambda b: b[0])
            if truoc and sau:
                moc[i] = truoc[1] + (sau[1] - truoc[1]) * (i - truoc[0]) / (sau[0] - truoc[0])
            elif truoc:
                moc[i] = truoc[1] + 0.25 * (i - truoc[0])
            else:
                moc[i] = max(0.0, sau[1] - 0.25 * (sau[0] - i))
    return [round(min(m, max(0.0, t1 - t0 - 0.05)), 3) for m in moc]


class _NhomSfx:
    """nhóm SFX của GÓI KHO video (doc/kho-video.json, kho/goi_video.py): tên nhóm → XOAY VÒNG các id trong nhóm, bỏ id vừa dùng liền trước"""

    def __init__(self, du_an):
        d = chung.doc_json(os.path.join(du_an, "doc", "kho-video.json")) or {}
        sx = d.get("sfx") if isinstance(d.get("sfx"), dict) else {}
        self.nhom = {k: [m["id"] for m in v if isinstance(m, dict) and m.get("id")] for k, v in sx.items() if isinstance(v, list)}
        self.i = {}

    def lay(self, ten, tranh=()):
        ten = str(ten or "").strip()
        k = ten if ten in self.nhom else chung.slug(ten).replace("-", "_")
        ds = self.nhom.get(k)
        if not ds:
            return None
        for _ in range(len(ds)):
            j = self.i.get(k, 0); self.i[k] = j + 1
            if ds[j % len(ds)] not in tranh:
                return ds[j % len(ds)]
        return ds[0]


def _sfx_lop(lop, am_sfx, gt, dur, may_sua, ns=None, Q=None, canh_bao=None):
    """SFX GẮN VÀO LỚP: lop.am {vao, ra: id kho|nghĩa|"tu_dong", db, lech} → thêm vào am.sfx đúng lúc lớp hiện (t0+lech) / bắt đầu
    ra (t1 − dài anim ra đã giải). db bỏ → quyết định am.sfx.db. Không tìm thấy → GOM thành một cảnh báo (không chặn từng lớp)."""
    can = []
    db_kenh = None
    for l in lop:
        a = l.get("am") or {}
        for khi in ("vao", "ra"):
            g = a.get(khi)
            if not g:
                continue
            if isinstance(g, dict):
                db = g.get("db", a.get("db")); lech = g.get("lech", a.get("lech")); g = g.get("id")
            else:
                db, lech = a.get("db"), a.get("lech")
            if not g:
                continue
            if khi == "vao":
                t = l["t0"] + so(lech, 0, -1, 1)
            else:
                dr = so(((l.get("anim") or {}).get("ra") or {}).get("dai"), 0, 0, 3)
                t = max(l["t0"], l["t1"] - dr) + so(lech, 0, -1, 1)
            dai_anim = None
            if g == "tu_dong":
                goi_y = _the_mau((l.get("noi_dung") or {}).get("mau", "")).get("sfx_goi_y") or []
                if not goi_y:
                    may_sua.append({"lop": l["id"], "sua": "am", "mo_ta": "am tu_dong nhưng lớp không phải mẫu có sfx_goi_y → bỏ"})
                    continue
                k_td = _sfx_lop.dem_td.get(khi, 0); _sfx_lop.dem_td[khi] = k_td + 1
                g = goi_y[(k_td if khi == "vao" else k_td + 1) % len(goi_y)]
                dai_anim = so((((l.get("anim") or {}).get(khi) or {}).get("dai")), 0.3, 0.05, 3)
            if db is None:
                if db_kenh is None and Q is not None:
                    db_kenh = so(Q.lay("am.sfx.db", f"lop[{l['id']}].am.db"), None, -40, 6)
                db = db_kenh
            if db is None:
                continue
            can.append({"t": round(max(0.0, min(t, dur - 0.05) if dur else t), 3), "id": g, "db": so(db, -40, -40, 6),
                        "lop": l["id"], "khi": khi, "dai_anim": dai_anim})
    if not can:
        return am_sfx
    tat_ca = sorted([dict(s, _cu=True) for s in am_sfx] + can, key=lambda s: s["t"])
    ra, truoc, khong_thay = [], None, []
    for s in tat_ca:
        if s.pop("_cu", False):
            ra.append(s); truoc = s.get("id_kho") or s.get("id"); continue
        tranh = [truoc] if truoc and KHO_ID.match(str(truoc)) else []
        n_tra = len(gt.tra_kho)
        g_nhom = ns.lay(s["id"], tranh) if ns is not None else None          # tên nhóm của gói kho video → xoay vòng id
        # tiếng ghép theo VẬT LÝ hoạt ảnh — tiếng gợi ý của mẫu không dài hơn hoạt ảnh + 0,8 s (đo được, không phải gu)
        dur_rb = (0.05, max(0.6, (s.get("dai_anim") or 0) + 0.8)) if s.get("dai_anim") else None
        p = gt.kho(g_nhom or s["id"], "sfx", f"{s['lop']}.am.{s['khi']}", bat_buoc=False, tranh=tranh, dur=dur_rb)
        if g_nhom and p:
            gt.tra_kho.append({"lop": s["lop"], "loai": "sfx", "nghia": f"nhóm {s['id']}", "id": g_nhom, "duong": p, "ung_vien": []})
        if not p:
            khong_thay.append(f"{s['lop']}.am.{s['khi']}=«{str(s['id'])[:40]}»")
            continue
        id_kho = gt.tra_kho[-1].get("id") if len(gt.tra_kho) > n_tra else s["id"]
        if tranh and id_kho == tranh[0]:
            may_sua.append({"lop": s["lop"], "sua": "am", "mo_ta": f"sfx {id_kho} trùng sfx liền trước (AI ghi id) — giữ"})
        ra.append({"t": s["t"], "id": s["id"], "id_kho": id_kho, "duong": p, "db": s["db"], "lop": s["lop"], "khi": s["khi"]})
        truoc = id_kho
    if khong_thay and canh_bao is not None and gt._co_loai("sfx"):
        canh_bao.append({"id": "sfx_khong_tim_thay", "lop": "am.sfx", "so": len(khong_thay),
                         "mo_ta": f"{len(khong_thay)} tiếng gắn lớp không tìm thấy trong kho (bỏ qua, không chặn): " + "; ".join(khong_thay[:12])
                                  + (" …" if len(khong_thay) > 12 else "") + " — ghi id kho hoặc tính chất tiếng khác (python v3/kho/tim.py sfx \"…\")"})
    return ra


_sfx_lop.dem_td = {}          # bộ đếm gợi ý "tu_dong" trong 1 lần chuẩn hoá (đặt lại ở chuan_hoa)


# ---------------------------------------------------------------- quyết định kênh: nạp
def nap_quyet_dinh(du_an, viec, loi):
    """→ (qd|None, nguon). Thứ tự: <dự án>/quyet-dinh-kenh.json (kiểm khuôn → lưu hồ sơ, lịch sử 20) → hồ sơ → gói phong cách (viec.goi) → None.
    Lỗi khuôn → loi `quyet_dinh_sai` (chặn) và qd=None."""
    qd, nguon, loi_qd = hop_dong.doc_quyet_dinh(du_an, viec.get("ho_so"))
    if loi_qd:
        for l in loi_qd[:40]:
            loi.append({"id": "quyet_dinh_sai", "lop": "quyet_dinh", "duong": l.get("duong"), "ma": l.get("ma"),
                        "mo_ta": f"{l.get('duong')}: {l.get('goi_y')} — sửa {'quyet-dinh-kenh.json trong dự án' if nguon == 'du_an' else 'quyet-dinh.json của hồ sơ'}"})
        return None, nguon, True
    if qd is None and viec.get("goi"):
        try:
            from phong_cach import ap as _apg
            qd = _apg.quyet_dinh_cho(viec["goi"])
            nguon = "goi:" + str(viec["goi"]) if qd else None
        except Exception:
            qd = None
    return qd, nguon, False


# ---------------------------------------------------------------- chính
def chuan_hoa(du_an, cong_thuc):
    """→ (ke_hoach, loi_chan[]). Ghi du_an/ke-hoach.json (có "quyet_dinh" = bản quyết định kênh đã dùng)."""
    du_an = os.path.abspath(du_an)
    if isinstance(cong_thuc, str):
        cong_thuc = chung.doc_json(cong_thuc) or {}
    ct = cong_thuc if isinstance(cong_thuc, dict) else {}
    viec = chung.doc_json(os.path.join(du_an, "viec.json")) or {}
    cfg = chung.cau_hinh()
    ho_so = chung.doc_json(os.path.join(chung.duong("ho_so"), viec.get("ho_so") or "", "ho-so.json")) or {}
    may_sua, loi, tra_kho, canh_bao = [], [], [], []
    _sfx_lop.dem_td = {}

    # --- khung, fps
    khung = ct.get("khung") or viec.get("khung") or cfg.get("khung_mac_dinh") or [1080, 1920]
    try:
        W, H = int(khung[0]), int(khung[1])
    except Exception:
        W, H = 1080, 1920
    if viec.get("khung") and [W, H] != [int(viec["khung"][0]), int(viec["khung"][1])]:
        may_sua.append({"lop": "khung", "sua": "khung", "tu": [W, H], "den": viec["khung"], "mo_ta": "khung của việc thắng khung ghi trong công thức"})
        W, H = int(viec["khung"][0]), int(viec["khung"][1])
    fps = int(so(viec.get("fps") or cfg.get("fps_mac_dinh") or 30, 30, 10, 60))

    # --- QUYẾT ĐỊNH KÊNH + hợp đồng công thức (hop_dong) — trước khi điền
    qd, nguon_qd, qd_loi = nap_quyet_dinh(du_an, viec, loi)
    Q = QuyetDinh(qd, du_an, im=qd_loi, may_sua=may_sua)
    hd = hop_dong.kiem_cong_thuc(ct, (W, H))
    for l in hd["loi"]:
        loi.append({"id": "hop_dong", "lop": (l.get("duong") or "").split(".")[0] or "cong_thuc", "duong": l.get("duong"), "ma": l.get("ma"),
                    "mo_ta": f"{l.get('duong')}: {l.get('goi_y')}"})
    for c in hd["canh_bao"]:
        canh_bao.append({"id": "hop_dong_" + str(c.get("ma")), "lop": c.get("duong"), "thong_tin": True, "mo_ta": f"{c.get('duong')}: {c.get('goi_y')}"})

    # --- BẢN SẮC KÊNH áp bằng MÁY: trường AI bỏ trống lấy từ bài học/Style Spec đang bật (ánh xạ, không chấm điểm) — trước quyết định
    try:
        spec_ap = None
        if viec.get("goi"):
            from phong_cach import ap as _apg
            spec_ap = _apg.spec_cho(viec["goi"])
        if not spec_ap:                                    # bài học đang BẬT mới nhất (tab Học) thắng bản nháp/góp ý
            tm_hs = os.path.join(chung.duong("ho_so"), viec.get("ho_so") or "")
            bai = sorted(glob.glob(os.path.join(tm_hs, "hoc", "*.json")), key=os.path.getmtime, reverse=True)
            for f_ in bai:
                b_ = chung.doc_json(f_, {}) or {}
                if b_.get("bat", True) and isinstance(b_.get("style_spec"), dict):
                    spec_ap = b_["style_spec"]; break
        if not spec_ap:
            spec_ap = chung.doc_json(os.path.join(chung.duong("ho_so"), viec.get("ho_so") or "", "style-spec.json"))
        if spec_ap:
            from hoc import ap_spec as _aps
            ct = json.loads(json.dumps(ct))
            _aps.ap_vao_cong_thuc(ct, spec_ap, ghi=may_sua, qd=qd)
    except Exception as ex:
        may_sua.append({"lop": "phong_cach", "sua": "ban_sac", "mo_ta": f"không áp được bản sắc kênh: {ex}"})

    # --- nguồn
    nguon = []
    nguon_cache = chung.doc_json(os.path.join(du_an, "doc", "nguon-ffprobe.json")) or {}
    doi = False
    for i, n in enumerate(viec.get("nguon") or []):
        p = n.get("duong") if isinstance(n, dict) else str(n)
        k = f"{p}|{chung.bam(p) if os.path.isfile(p) else ''}"
        info = nguon_cache.get(k)
        if not info:
            info = chung.ffprobe(p) if os.path.isfile(p) else None
            info = info or {"dur": 0, "w": 0, "h": 0, "fps": 30, "co_am": False}
            nguon_cache[k] = info
            doi = True
        nguon.append({"i": i, "duong": p, "vai": (n.get("vai") if isinstance(n, dict) else "chinh") or "chinh", "dur": float(info.get("dur") or 0),
                      "w": info.get("w", 0), "h": info.get("h", 0), "fps": info.get("fps", 30), "co_am": info.get("co_am", False)})
    if doi:
        chung.ghi_json(os.path.join(du_an, "doc", "nguon-ffprobe.json"), nguon_cache)

    def dur_nguon(src):
        return nguon[src]["dur"] if 0 <= src < len(nguon) else 0.0

    # --- xuất: khổ ra (cạnh ngắn 1080|1440|2160) + fps (30|60) — theo viec.json xuat_4k / giu_fps hoặc công thức `xuat`
    xu_ai = ct.get("xuat") if isinstance(ct.get("xuat"), dict) else {}
    cao = xu_ai.get("cao") or (2160 if viec.get("xuat_4k") else None)
    xuat = {}
    if cao:
        c_ = int(so(cao, 1080))
        c_ = min((1080, 1440, 2160), key=lambda v: abs(v - c_))
        if c_ != int(so(cao, 1080)):
            may_sua.append({"lop": "xuat", "sua": "cao", "tu": cao, "den": c_, "mo_ta": "xuat.cao chỉ nhận 1080|1440|2160"})
        if c_ != min(W, H):
            xuat["cao"] = c_
    f_ai = xu_ai.get("fps")
    if f_ai is None and viec.get("giu_fps") and nguon:
        f_ai = 60 if float(nguon[0].get("fps") or 30) > 45 else 30
    if f_ai is not None:
        f_ = 60 if so(f_ai, 30) > 45 else 30
        xuat["fps"] = f_
        fps = f_

    # --- cat (nhịp cắt lặng: công thức cat_tu_dong.nhip → quyết định cat.nhip → thieu_truong)
    cat_goc = ct.get("cat")
    nguon_cat = "ai"
    nhip_dung = None
    if not isinstance(cat_goc, list) or not cat_goc:
        dx = chung.doc_json(os.path.join(du_an, "doc", "cat-de-xuat.json")) or {}
        ctd = ct.get("cat_tu_dong") if isinstance(ct.get("cat_tu_dong"), dict) else {}
        nhip_moi = str(ctd.get("nhip") or ct.get("nhip") or "").lower()          # cong-thuc.nhip (A1) hoặc cat_tu_dong.nhip
        if nhip_moi not in ("nhanh", "vua", "cham"):
            nhip_moi = str(Q.tuy("cat.nhip") or "").lower()
        nhip_dung = nhip_moi if nhip_moi in ("nhanh", "vua", "cham") else None
        if nhip_dung is None and dx.get("giu"):
            canh_bao.append({"id": "cat_nhip_mac_dinh", "lop": "cat", "thong_tin": True,
                             "mo_ta": f"công thức không ghi cat_tu_dong.nhip và quyết định kênh không có cat.nhip → dùng đề xuất cắt sẵn (nhịp `{dx.get('nhip')}`)"})
        if nhip_dung and nhip_dung != dx.get("nhip") and dx.get("giu"):
            # nhịp khác đề xuất đã có → tính lại đề xuất và DỜI mọi mốc giây thành phẩm của công thức sang dòng thời gian mới
            try:
                from doc import cat as _catm
                ng_ = chung.doc_json(os.path.join(du_an, "doc", "nguon.json")) or {}
                am16 = (ng_.get("chinh") or {}).get("am16") or ng_.get("am16")
                giu_cu = dx.get("giu") or []
                _catm.de_xuat(os.path.join(du_an, "doc", "loi.json"), am16, du_an, nhip=nhip_dung)
                dx = chung.doc_json(os.path.join(du_an, "doc", "cat-de-xuat.json")) or {}
                _doi_moc_cong_thuc(ct, giu_cu, dx.get("giu") or [])
                may_sua.append({"lop": "cat", "sua": "nhip", "den": nhip_dung, "mo_ta": f"nhịp cắt `{nhip_dung}`: {dx.get('dur_goc')}s → {dx.get('dur_sau')}s, mốc giây các lớp đã dời theo"})
            except Exception as ex:
                may_sua.append({"lop": "cat", "sua": "nhip", "mo_ta": f"không đổi được nhịp cắt ({ex}) — giữ đề xuất cũ"})
        cat_goc = dx.get("giu") or []
        nguon_cat = "de_xuat"
    if not cat_goc:
        cat_goc = [{"src": 0, "a": 0.0, "b": dur_nguon(0)}]
        nguon_cat = "toan_bo"
    cat = []
    for c in cat_goc:
        if not isinstance(c, dict):
            continue
        src = int(so(c.get("src", 0), 0, 0))
        a, b = so(c.get("a", 0), 0, 0), so(c.get("b", 0), 0, 0)
        dn = dur_nguon(src)
        if src >= len(nguon):
            loi.append({"id": "thoi_gian", "lop": "cat", "t": a, "mo_ta": f"cat dùng src {src} nhưng chỉ có {len(nguon)} nguồn"})
            continue
        if dn > 0 and b > dn + 0.05:
            may_sua.append({"lop": "cat", "sua": "giay", "tu": b, "den": round(dn, 3), "mo_ta": f"cat b={b} vượt thời lượng nguồn {dn:.2f}s → cắt bớt"})
            b = dn
        if b - a < 0.04:
            loi.append({"id": "thoi_gian", "lop": "cat", "t": a, "mo_ta": f"đoạn cat [{a}, {b}] rỗng hoặc b ≤ a"})
            continue
        cat.append({"src": src, "a": round(a, 3), "b": round(b, 3)})
    if not cat:
        loi.append({"id": "thoi_gian", "lop": "cat", "t": 0, "mo_ta": "không còn đoạn cat nào hợp lệ"})
        dur = dur_nguon(0)
    else:
        dur = round(dur_cat(cat), 3)

    # --- phong cách: màu (AI → hồ sơ khoá → quyết định bang_mau → thieu_truong), font (AI → hồ sơ khoá → quyết định font → thieu_truong)
    pc_ai = ct.get("phong_cach") if isinstance(ct.get("phong_cach"), dict) else {}
    bm = Q.lay("bang_mau", "phong_cach") if Q.co() else None
    pc = {"font": {}, "cam_giac": str(pc_ai.get("cam_giac") or "")}
    for k_ct, k_qd in (("mau_nhan", "nhan"), ("mau_nhan2", "nhan2"), ("mau_sang", "sang"), ("mau_toi", "toi")):
        m = mau_chuan(pc_ai.get(k_ct))
        if m is None and isinstance(bm, dict):
            m = mau_chuan(bm.get(k_qd))
        if m is None:
            Q.bat_buoc(f"phong_cach.{k_ct}", "quyết định kênh bang_mau = null (hoặc chưa có) → mỗi video AI phải ghi phong_cach.mau_nhan/mau_nhan2/mau_sang/mau_toi")
        pc[k_ct] = m
    mau_hs = ho_so.get("mau") if isinstance(ho_so.get("mau"), dict) else {}
    if mau_hs.get("khoa") and mau_chuan(mau_hs.get("nhan")):
        mk = mau_chuan(mau_hs["nhan"])
        if mk != pc["mau_nhan"]:
            may_sua.append({"lop": "phong_cach", "sua": "mau_khoa", "tu": pc["mau_nhan"], "den": mk, "mo_ta": "hồ sơ khoá màu nhấn → dùng màu khoá"})
            pc["mau_nhan"] = mk
    f_ai = pc_ai.get("font") if isinstance(pc_ai.get("font"), dict) else {}
    f_hs = ho_so.get("font") if isinstance(ho_so.get("font"), dict) else {}
    for vai in VAI_FONT:
        f_ = f_ai.get(vai)
        f_ = "" if f_ in VAI_FONT else f_                     # R2: AI ghi tên vai (vd "tieu_de") = dùng mặc định → rơi xuống hồ sơ/quyết định, không may_sua
        f_ = f_ or f_hs.get(vai) or Q.lay(f"font.{vai}", f"phong_cach.font.{vai}") or ""
        pc["font"][vai] = f_ if f_ not in VAI_FONT else ""
    if f_hs.get("khoa"):
        for vai in ("tieu_de", "phu_de"):
            if f_hs.get(vai) and f_ai.get(vai) and f_ai.get(vai) != f_hs.get(vai):
                may_sua.append({"lop": "phong_cach", "sua": "font_khoa", "tu": f_ai[vai], "den": f_hs[vai], "mo_ta": f"hồ sơ khoá font {vai}"})
                pc["font"][vai] = f_hs[vai]
    gt = GiaiTaiNguyen(du_an, pc, ho_so, may_sua, loi, tra_kho, Q=Q, canh_bao=canh_bao)
    font_vai = {vai: gt.font(vai, "phong_cach", vai, duong=f"phong_cach.font.{vai}") for vai in VAI_FONT}

    # --- camera
    cam = []
    for i, k in enumerate(ct.get("camera") or []):
        if not isinstance(k, dict):
            continue
        e = Q.dien(k, "ease", "camera.ease", f"camera[{i}]")
        cam.append({"t": so(k.get("t", 0), 0, 0), "z": so(k.get("z"), 1, 1, 2), "x": so(k.get("x"), 0.5, 0, 1), "y": so(k.get("y"), 0.5, 0, 1),
                    "ease": e if e in EASE else "linear", "dai": so(k.get("dai") if k.get("dai") is not None else Q.tuy("camera.dai"), 0, 0, 10)})
    cam.sort(key=lambda k: k["t"])
    if not cam or cam[0]["t"] > 0:
        cam.insert(0, {"t": 0, "z": 1.0, "x": 0.5, "y": 0.5, "ease": "linear", "dai": 0})      # khung đầu = nguyên bản (không zoom)
    cam = [k for k in cam if k["t"] <= dur + 1e-6]

    # --- lớp
    lop = []
    ids = set()
    for i, l in enumerate(ct.get("lop") or []):
        if not isinstance(l, dict):
            continue
        lid = str(l.get("id") or f"lop{i + 1}")
        if lid in ids:
            lid = f"{lid}_{i + 1}"
        ids.add(lid)
        D = f"lop[{i}]"
        kieu = l.get("kieu")
        if kieu not in KIEU_LOP:
            loi.append({"id": "cong_thuc_sai", "lop": lid, "duong": f"{D}.kieu", "mo_ta": f"kiểu lớp `{kieu}` không có ({'|'.join(KIEU_LOP)})"})
            continue
        try:
            t0, t1 = so(l.get("t0"), 0, 0), so(l.get("t1"), 0, 0)
            if t0 < 0:
                may_sua.append({"lop": lid, "sua": "giay", "tu": t0, "den": 0, "mo_ta": "t0 < 0 → 0"})
                t0 = 0.0
            if dur > 0 and t1 > dur + 0.02:
                may_sua.append({"lop": lid, "sua": "giay", "tu": t1, "den": dur, "mo_ta": f"t1 vượt thời lượng {dur:.2f}s → cắt"})
                t1 = dur
            if t1 - t0 < 0.05:
                loi.append({"id": "thoi_gian", "lop": lid, "t": t0, "duong": f"{D}.t1", "mo_ta": f"t1 ({t1}) ≤ t0 ({t0}) hoặc ngoài [0, {dur:.2f}]"})
                continue
            nd = l.get("noi_dung") if isinstance(l.get("noi_dung"), dict) else {}
            kd_goc = l.get("kieu_dang") if isinstance(l.get("kieu_dang"), dict) else {}
            m = {"id": lid, "kieu": kieu, "t0": round(t0, 3), "t1": round(t1, 3), "noi_dung": {}, "kieu_dang": {},
                 "vi_tri": None, "anim": _anim_chuan(l.get("anim"), Q, f"{D}.anim", may_sua, lid)}
            if kieu != "mau":
                m["vi_tri"] = _vi_tri_chuan(l.get("vi_tri"), kieu, Q, f"{D}.vi_tri", may_sua, lid)
            if kieu == "chu":
                text = str(nd.get("text") or "").replace("\\n", "\n")
                if not text.strip():
                    loi.append({"id": "cong_thuc_sai", "lop": lid, "duong": f"{D}.noi_dung.text", "mo_ta": "lớp chu thiếu noi_dung.text"})
                    continue
                m["noi_dung"] = {"text": text, "theo_loi": bool(nd.get("theo_loi", False))}
                kd = _kieu_dang_chu(kd_goc, Q, f"{D}.kieu_dang", "chu", "tieu_de")
                kd["font_duong"] = gt.font(kd["font"], lid, "tieu_de", text=text, dam=kd.get("dam"), nghieng=(True if kd.get("nghieng") else None), duong=f"{D}.kieu_dang.font")
                m["kieu_dang"] = kd
            elif kieu == "khoi":
                # khối chữ nhiều dòng — mỗi dòng kiểu dáng riêng; kieu_dang của lớp = mặc định cho dòng + can/cach_dong/rong_max (quyết định khoi.*)
                ds = nd.get("dong") if isinstance(nd.get("dong"), list) else []
                dong = []
                RIENG = ("text", "lech", "kieu_dang", "xoay", "dx", "dy", "tre", "anim")
                for j, d in enumerate(ds):
                    if isinstance(d, str):
                        d = {"text": d}
                    if not isinstance(d, dict):
                        continue
                    text = str(d.get("text") or "").replace("\\n", "\n")
                    if not text.strip():
                        continue
                    hop = {k: v for k, v in kd_goc.items() if k not in ("can", "cach_dong", "rong_max", "dong")}
                    hop.update({k: v for k, v in d.items() if k not in RIENG})
                    if isinstance(d.get("kieu_dang"), dict):
                        hop.update(d["kieu_dang"])
                    hop.setdefault("dong", 1.0)              # dòng của khối xếp sát theo cach_dong (không phải khoảng dòng của chữ)
                    Dd = f"{D}.noi_dung.dong[{j}]"
                    kd = _kieu_dang_chu(hop, Q, Dd, "chu", kd_goc.get("font") or "tieu_de")
                    kd["font_duong"] = gt.font(kd["font"], lid, "tieu_de", text=text, dam=kd.get("dam"), nghieng=(True if kd.get("nghieng") else None), duong=f"{Dd}.font")
                    d_ra = {"text": text, "kieu_dang": kd, "lech": so(d.get("lech"), 0, -1, 1)}
                    if d.get("xoay") is not None:
                        d_ra["xoay"] = so(d.get("xoay"), 0, -60, 60)
                    for k_ in ("dx", "dy"):
                        if d.get(k_) is not None:
                            d_ra[k_] = so(d.get(k_), 0, -1080, 1080)
                    if d.get("tre") is not None:
                        d_ra["tre"] = so(d.get("tre"), 0, 0, 10)
                    if isinstance(d.get("anim"), dict):
                        an_ = _anim_chuan(d["anim"], Q, f"{Dd}.anim", may_sua, f"{lid}.dong")
                        d_ra["anim"] = {k_: an_[k_] for k_ in ("vao", "ra", "nhoe_dong") if k_ in d["anim"]}
                    dong.append(d_ra)
                if not dong:
                    loi.append({"id": "cong_thuc_sai", "lop": lid, "duong": f"{D}.noi_dung.dong", "mo_ta": "lớp khoi thiếu noi_dung.dong [{text, co, mau, font, dam, nghieng…}]"})
                    continue
                m["noi_dung"] = {"dong": dong}
                can = Q.dien(kd_goc, "can", "khoi.can", f"{D}.kieu_dang", khoa_phu="chu.can")
                m["kieu_dang"] = {"can": can if can in ("trai", "giua", "phai") else None,
                                  "cach_dong": so(Q.dien(kd_goc, "cach_dong", "khoi.cach_dong", f"{D}.kieu_dang"), None, 0.3, 2.0),
                                  "rong_max": so(Q.dien(kd_goc, "rong_max", "khoi.rong_max", f"{D}.kieu_dang", khoa_phu="chu.rong_max"), None, 0.2, 1)}
            elif kieu == "the":
                text = str(nd.get("text") or "")
                icon = nd.get("icon")
                m["noi_dung"] = {"text": text, "icon": icon, "icon_duong": gt.kho(icon, "icon", lid, bat_buoc=False) if icon else None}
                if icon and not m["noi_dung"]["icon_duong"]:
                    may_sua.append({"lop": lid, "sua": "icon", "tu": icon, "den": None, "mo_ta": f"không có icon `{icon}` → thẻ không icon"})
                kd = _kieu_dang_the(kd_goc, Q, f"{D}.kieu_dang")
                kd["chu"]["font_duong"] = gt.font(kd["chu"]["font"], lid, "nhan", text=text, dam=kd["chu"].get("dam"), duong=f"{D}.kieu_dang.chu.font")
                m["kieu_dang"] = kd
            elif kieu == "hinh":
                d = nd.get("duong")
                p = gt.kho(d, "anh,nen", lid) if d else None
                if not d:
                    loi.append({"id": "cong_thuc_sai", "lop": lid, "duong": f"{D}.noi_dung.duong", "mo_ta": "lớp hinh thiếu noi_dung.duong"})
                m["noi_dung"] = {"duong": d, "duong_giai": p}
                m["kieu_dang"] = _kd_hinh(kd_goc, Q, f"{D}.kieu_dang", may_sua, lid, video=False)
            elif kieu == "video" and (nd.get("duong") or nd.get("id")):
                # video KHO (nền động, ánh sáng/light leak, bokeh, khói…) hoặc đường dẫn — có hoà trộn / lặp / tốc độ
                d = nd.get("duong") or nd.get("id")
                p = gt.kho(d, "video,nen", lid)
                a = so(nd.get("a"), 0, 0)
                kdp = _kd_hinh(kd_goc, Q, f"{D}.kieu_dang", may_sua, lid, video=True)
                if p:
                    dv = float((chung.ffprobe(p) or {}).get("dur") or 0)
                    if dv > 0 and not kdp.get("lap") and a + (t1 - t0) * kdp.get("toc_do", 1.0) > dv + 0.05:
                        t1m = round(t0 + (dv - a) / kdp.get("toc_do", 1.0), 3)
                        if t1m - t0 >= 0.3:
                            may_sua.append({"lop": lid, "sua": "giay", "tu": t1, "den": t1m, "mo_ta": f"video kho dài {dv:.1f}s hết trước t1 → rút t1 (hoặc ghi kieu_dang.lap=true)"})
                            m["t1"] = t1m
                        else:
                            kdp["lap"] = True
                            may_sua.append({"lop": lid, "sua": "lap", "mo_ta": f"video kho dài {dv:.1f}s ngắn hơn lớp → lặp"})
                m["noi_dung"] = {"duong": d, "duong_giai": p, "a": a}
                if kd_goc.get("am_db") is not None:
                    m["am_db"] = so(kd_goc.get("am_db"), -40, -40, 6)
                m["kieu_dang"] = kdp
            elif kieu == "video":
                src = int(so(nd.get("src"), 1, 0))
                a = so(nd.get("a"), 0, 0)
                if src >= len(nguon):
                    loi.append({"id": "tai_nguyen_khong_co", "lop": lid, "duong": f"{D}.noi_dung.src", "mo_ta": f"lớp video dùng src {src} nhưng chỉ có {len(nguon)} nguồn"})
                elif dur_nguon(src) > 0 and a >= dur_nguon(src):
                    loi.append({"id": "thoi_gian", "lop": lid, "t": t0, "duong": f"{D}.noi_dung.a", "mo_ta": f"a={a} vượt thời lượng nguồn {src} ({dur_nguon(src):.2f}s)"})
                elif dur_nguon(src) > 0 and a + (t1 - t0) > dur_nguon(src) + 0.05:
                    t1m = round(t0 + (dur_nguon(src) - a), 3)
                    may_sua.append({"lop": lid, "sua": "giay", "tu": t1, "den": t1m, "mo_ta": "nguồn phụ hết trước t1 → rút t1"})
                    m["t1"] = t1m
                m["noi_dung"] = {"src": src, "a": a, "duong": nguon[src]["duong"] if src < len(nguon) else None}
                if kd_goc.get("am_db") is not None:                 # tiếng của B-roll (dB so với giọng) — trộn như sfx đúng đoạn
                    m["am_db"] = so(kd_goc.get("am_db"), -40, -40, 6)
                m["kieu_dang"] = _kd_hinh(kd_goc, Q, f"{D}.kieu_dang", may_sua, lid, video=True)
                m["kieu_dang"]["am"] = bool(kd_goc.get("am", False))
            elif kieu == "duong":
                loai = nd.get("loai")
                if loai not in ("gach_chan", "mui_ten", "khung", "khoanh"):
                    loi.append({"id": "cong_thuc_sai", "lop": lid, "duong": f"{D}.noi_dung.loai", "mo_ta": f"lớp duong loai `{loai}` không có"})
                    continue
                tu, den = nd.get("tu"), nd.get("den")
                if not (isinstance(tu, list) and len(tu) >= 2 and isinstance(den, list) and len(den) >= 2):
                    Q.bat_buoc(f"{D}.noi_dung.tu", "lớp duong phải ghi tu [x,y] và den [x,y]")
                    continue
                m["noi_dung"] = {"loai": loai, "tu": [so(tu[0], 0, 0, 1), so(tu[-1], 0, 0, 1)], "den": [so(den[0], 0, 0, 1), so(den[-1], 0, 0, 1)]}
                m["kieu_dang"] = {"w": so(Q.dien(kd_goc, "w", "duong.w", f"{D}.kieu_dang"), None, 1, 80),
                                  "mau": mau_chuan(kd_goc.get("mau") if kd_goc.get("mau") is not None else (Q.tuy("duong.mau") or Q.lay("bang_mau.nhan", f"{D}.kieu_dang.mau"))),
                                  "ease": kd_goc.get("ease") if kd_goc.get("ease") in EASE else Q.lay("duong.ease", f"{D}.kieu_dang.ease"),
                                  "ve": so(Q.dien(kd_goc, "ve", "duong.ve", f"{D}.kieu_dang"), None, 0, 5)}
                x0, x1 = sorted([m["noi_dung"]["tu"][0], m["noi_dung"]["den"][0]])
                y0, y1 = sorted([m["noi_dung"]["tu"][1], m["noi_dung"]["den"][1]])
                m["vi_tri"] = {"anchor": "tl", "so_voi": "khung", "x": x0, "y": y0, "w": max(x1 - x0, 0.01), "h": max(y1 - y0, 0.01)}
            elif kieu == "py":
                f = str(nd.get("file") or "")
                p = os.path.normpath(os.path.join(du_an, f)) if f else ""
                trong = p.startswith(os.path.normpath(os.path.join(du_an, "lop-rieng")) + os.sep)
                if not f or not os.path.isfile(p) or not trong or not p.endswith(".py"):
                    loi.append({"id": "tai_nguyen_khong_co", "lop": lid, "duong": f"{D}.noi_dung.file", "mo_ta": f"file lớp py `{f}` không có (phải nằm trong lop-rieng/ của dự án)"})
                m["noi_dung"] = {"file": f, "duong": p if trong else None}
                m["kieu_dang"] = {}
            elif kieu == "mau":
                mid = str(nd.get("mau") or "")
                if mid and not mid.startswith("mau."):
                    mid = "mau." + mid
                the = _the_mau(mid)
                if not the:
                    loi.append({"id": "tai_nguyen_khong_co", "lop": lid, "duong": f"{D}.noi_dung.mau", "mo_ta": f"không có mẫu `{mid}` trong thư viện — xem DANH MỤC MẪU"})
                    continue
                ts = nd.get("tham_so") if isinstance(nd.get("tham_so"), dict) else {}
                m["noi_dung"] = {"mau": mid, "tham_so": ts}
                vt_ai = l.get("vi_tri") if isinstance(l.get("vi_tri"), dict) else {}
                vt = dict(the.get("hop") or {}); vt.update(vt_ai)          # hộp của mẫu (thuộc mẫu), AI ghi đè
                m["vi_tri"] = _vi_tri_chuan(vt, "mau", Q, f"{D}.vi_tri", may_sua, lid)
                m["kieu_dang"] = {k: v for k, v in kd_goc.items() if k in ("do_trong",)}
                if the.get("toan_khung"):
                    m["toan_khung"] = True; m["ne_mat"] = False
                try:
                    from dung.lop import lam_nen_cua as _lnc
                    ln = _lnc(the, dict(the.get("mac_dinh") or {}, **ts))
                except Exception:
                    ln = bool(the.get("lam_nen")) and not isinstance(the.get("lam_nen"), str)
                if ln:
                    m["lam_nen"] = True
                if the.get("ne_mat") is False or (the.get("ne_mat") is None and (the.get("toan_khung") or ln)):
                    m["ne_mat"] = False                # mẫu tự xử lý người (chữ sau người…) — không dời khỏi mặt
                if the.get("nhom") == "chuyen_canh":           # mẫu chuyển cảnh tự lo đường cong cường độ → vào/ra none nếu AI không ghi
                    an_ai = l.get("anim") if isinstance(l.get("anim"), dict) else {}
                    for k_ in ("vao", "ra"):
                        if k_ not in an_ai:
                            m["anim"][k_] = {"kieu": "none", "dai": 0.0, "ease": "linear"}
                mo_ta_moc = str((the.get("tham_so") or {}).get("moc") or "")
                if "moc" not in ts and "từ" in mo_ta_moc and ("lời" in mo_ta_moc or "giây" in mo_ta_moc):
                    moc = _moc_tu_loi(du_an, cat, t0, t1, str(ts.get("chu") or ""))
                    if moc:
                        m["noi_dung"]["tham_so"] = dict(ts, moc=moc)
                        may_sua.append({"lop": lid, "sua": "moc", "mo_ta": f"mẫu {mid}: tự điền moc ({len(moc)} từ) theo lời trong [{t0}, {t1}]"})
                sai = [k for k in ts if the.get("tham_so") and k not in the["tham_so"]]
                if sai:
                    may_sua.append({"lop": lid, "sua": "tham_so", "mo_ta": f"mẫu {mid} không có tham số {sai} (bỏ qua) — có: {list(the.get('tham_so') or {})}"})
            elif kieu == "web":
                m["noi_dung"] = dict(nd)
                m["kieu_dang"] = dict(kd_goc)
            # --- trường chung
            if l.get("z") is not None:
                m["z"] = int(so(l.get("z"), 0, -10, 10))
            if l.get("ne_mat") is False:
                m["ne_mat"] = False
            if l.get("toan_khung"):                   # R2: toan_khung:true trên MỌI kiểu lớp (chu/khoi/the — dựng lại bản chép hoc/dung_lai cần) → chép sang kế hoạch
                m["toan_khung"] = True; m["ne_mat"] = False
            if l.get("sau_nguoi"):
                m["sau_nguoi"] = True; m["ne_mat"] = False       # lớp nằm SAU người: máy tách người che phần chồng → cố ý chồng mặt/vai
            if kieu in ("video", "hinh", "web", "py", "mau") and m.get("vi_tri"):
                vt = m["vi_tri"]
                if (m["kieu_dang"].get("hoa_tron") not in (None, "normal")) or (so(vt.get("w"), 0) >= 0.9 and so(vt.get("h"), 0) >= 0.9):
                    m["ne_mat"] = False              # lớp phủ ánh sáng / lớp toàn khung: không phải vật che mặt
                    if so(vt.get("w"), 0) >= 0.9 and so(vt.get("h"), 0) >= 0.9:
                        m["toan_khung"] = True
            if l.get("co_y"):
                m["co_y"] = True                      # AI CỐ Ý (chữ nhanh/chồng có chủ đích) → luật đọc-kịp/chồng-lớp chỉ cảnh báo
            am_l = l.get("am") if l.get("am") is not None else l.get("sfx")
            if isinstance(am_l, (str, dict)):
                if isinstance(am_l, str):
                    am_l = {"vao": am_l}
                m["am"] = {k: am_l.get(k) for k in ("vao", "ra", "db", "lech") if am_l.get(k) is not None}
            lop.append(m)
        except Exception as ex:
            loi.append({"id": "cong_thuc_sai", "lop": lid, "duong": D, "mo_ta": f"lớp {lid} không chuẩn hoá được: {type(ex).__name__}: {str(ex)[:160]}"})
    lop.sort(key=lambda l: (l["t0"], l["t1"]))

    # --- phụ đề (mọi trường trống → quyết định phu_de.*)
    pd_ai = ct.get("phu_de") if isinstance(ct.get("phu_de"), dict) else {}
    che_do = Q.dien(pd_ai, "che_do", "phu_de.che_do", "phu_de")
    if che_do not in ("cum", "tu", "tat"):
        che_do = che_do if che_do is None else "cum"
    kd_pd = _kieu_dang_chu(pd_ai.get("kieu_dang"), Q, "phu_de.kieu_dang", "phu_de.kieu_dang", "phu_de")
    kd_ai_pd = pd_ai.get("kieu_dang") if isinstance(pd_ai.get("kieu_dang"), dict) else {}
    kd_pd["mau_noi"] = mau_chuan(kd_ai_pd.get("mau_noi") if kd_ai_pd.get("mau_noi") is not None else (Q.tuy("phu_de.kieu_dang.mau_noi") or Q.lay("phu_de.mau_noi", "phu_de.kieu_dang.mau_noi")))
    kd_pd["font_duong"] = gt.font(kd_pd["font"], "phu_de", "phu_de", dam=kd_pd.get("dam"), duong="phu_de.kieu_dang.font")
    vt_pd = pd_ai.get("vi_tri") if isinstance(pd_ai.get("vi_tri"), dict) else Q.lay("phu_de.vi_tri", "phu_de.vi_tri")
    vt_pd = _vi_tri_chuan(vt_pd or {}, "chu", Q, "phu_de.vi_tri", may_sua, "phu_de")
    an_pd = pd_ai.get("anim") if isinstance(pd_ai.get("anim"), dict) else Q.lay("phu_de.anim", "phu_de.anim")
    hien = pd_ai.get("hien") if pd_ai.get("hien") is not None else Q.tuy("phu_de.hien")
    khi_chong = pd_ai.get("khi_chong") if pd_ai.get("khi_chong") is not None else Q.tuy("phu_de.khi_chong")
    karaoke = Q.dien(pd_ai, "karaoke", "phu_de.karaoke", "phu_de")
    an_khi = pd_ai.get("an_khi_lop_chu") if pd_ai.get("an_khi_lop_chu") is not None else Q.tuy("phu_de.an_khi_lop_chu")
    phu_de = {"che_do": che_do, "toi_da_chu": nguyen(Q.dien(pd_ai, "toi_da_chu", "phu_de.toi_da_chu", "phu_de"), None, 8, 60),
              "karaoke": bool(karaoke) if karaoke is not None else None,
              "hien": hien if hien in ("noi", "dan") else None,
              "khi_chong": khi_chong if khi_chong in ("doi", "an") else None,
              "an_khi_lop_chu": bool(an_khi) if an_khi is not None else None,
              "kieu_dang": kd_pd, "vi_tri": vt_pd, "anim": _anim_chuan(an_pd or {}, Q, "phu_de.anim", may_sua, "phu_de", goc="phu_de.anim"),
              "mau_noi": kd_pd["mau_noi"]}
    for k_ in ("keo_dai", "lang_ngat", "tween", "nhuong_cho"):                 # nhịp phụ đề (engine đọc): công thức → quyết định phu_de.*
        v_ = so(pd_ai.get(k_), None, 0, 5)
        phu_de[k_] = v_ if v_ is not None else so(Q.lay(f"phu_de.{k_}", f"phu_de.{k_}"), None, 0, 5)
    if isinstance(pd_ai.get("sua"), dict):                 # sửa lỗi nhận dạng giọng: {"cụm sai": "cụm đúng"}
        phu_de["sua"] = {str(k_)[:60]: str(v_)[:80] for k_, v_ in list(pd_ai["sua"].items())[:60] if str(k_).strip()}

    # --- nền mới
    nen_moi = []
    for i, n in enumerate(ct.get("nen_moi") or []):
        if not isinstance(n, dict):
            continue
        Dn = f"nen_moi[{i}]"
        nn = n.get("nen") if isinstance(n.get("nen"), dict) else {}
        kieu_n = nn.get("kieu") if nn.get("kieu") in ("mau", "gradient", "anh", "video", "kho", "mo") else Q.lay("nen_moi.kieu", f"{Dn}.nen.kieu")
        if kieu_n not in ("mau", "gradient", "anh", "video", "kho", "mo"):        # R2: thiếu cả hai → thieu_truong nen_moi[i].nen.kieu (không tự "mau")
            continue
        gia_tri = nn.get("gia_tri")
        giai = None
        if kieu_n in ("anh", "video", "kho"):
            giai = gt.kho(gia_tri, "video" if kieu_n == "video" else "nen", "nen_moi")
        elif kieu_n == "mau":
            gia_tri = mau_chuan(gia_tri) or mau_chuan(Q.lay("nen_moi.mau", f"{Dn}.nen.gia_tri"))
        elif kieu_n == "gradient":
            gia_tri = [mau_chuan(x) for x in (gia_tri if isinstance(gia_tri, list) else [])][:4]
            gia_tri = [x for x in gia_tri if x]
            if len(gia_tri) < 2:
                Q.bat_buoc(f"{Dn}.nen.gia_tri", "nền gradient cần ≥ 2 màu")
        mo = so(nn.get("mo"), None, 0, 1)
        if mo is None:
            mo = so(Q.tuy("nen_moi.mo"), 0, 0, 1)                     # độ mờ chỉ dùng khi kieu = "mo"; tuỳ chọn
        vs = None
        if "vien_sang" in n:
            v = n.get("vien_sang")
            if isinstance(v, dict):
                q_ = Q.tuy("nen_moi.vien_sang") or {}
                w_ = so(v.get("w"), None, 0, 40); m_ = mau_chuan(v.get("mau"))
                if w_ is None:
                    w_ = so(q_.get("w"), None, 0, 40)
                if m_ is None:
                    m_ = mau_chuan(q_.get("mau"))
                if w_ is None:
                    Q.bat_buoc(f"{Dn}.vien_sang.w", "viền sáng cần w (px)")
                if m_ is None:
                    Q.bat_buoc(f"{Dn}.vien_sang.mau", "viền sáng cần mau")
                if w_ is not None and m_ is not None:
                    vs = {"w": w_, "mau": m_}
        else:
            q = Q.tuy("nen_moi.vien_sang")
            if isinstance(q, dict) and q.get("mau"):
                vs = {"w": so(q.get("w"), 0, 0, 40), "mau": mau_chuan(q.get("mau"), "#FFFFFF")}
        nen_moi.append({"t0": so(n.get("t0"), 0, 0, dur or 1e9), "t1": so(n.get("t1"), dur, 0, dur or 1e9),
                        "nen": {"kieu": kieu_n, "gia_tri": gia_tri, "duong": giai, "mo": mo,
                                "mo_sigma": so(nn.get("mo_sigma"), None, 0, 200) if nn.get("mo_sigma") is not None else so(Q.lay("nen_moi.mo_sigma", f"{Dn}.nen.mo_sigma"), None, 0, 200),
                                "toi": so(nn.get("toi"), None, 0, 1) if nn.get("toi") is not None else so(Q.lay("nen_moi.toi", f"{Dn}.nen.toi"), None, 0, 1)},
                        "vien_sang": vs})
    nen_moi = [n for n in nen_moi if n["t1"] > n["t0"]]

    # --- chuyển cảnh
    chuyen = []
    for i, c in enumerate(ct.get("chuyen_canh") or []):
        if isinstance(c, dict) and c.get("kieu") in ("flash", "zoom", "cut"):
            dai = so(c.get("dai"), None, 0, 2)
            if dai is None:
                dai = 0.0 if c["kieu"] == "cut" else so(Q.tuy(f"chuyen_canh.{c['kieu']}_dai") if Q.tuy(f"chuyen_canh.{c['kieu']}_dai") is not None else Q.lay(f"chuyen_canh.{c['kieu']}_dai", f"chuyen_canh[{i}].dai"), None, 0, 2)
            chuyen.append({"t": so(c.get("t", 0), 0, 0, dur or 1e9), "kieu": c["kieu"], "dai": dai})
    chuyen.sort(key=lambda c: c["t"])

    # --- âm
    am_ai = ct.get("am") if isinstance(ct.get("am"), dict) else {}
    nhac = None
    na = am_ai.get("nhac")
    if isinstance(na, str):
        na = {"id": na}
    muc_nhac = str((na or {}).get("muc") or "").lower() if isinstance(na, dict) else ""
    if isinstance(na, dict) and na.get("id") and muc_nhac != "khong":
        p = gt.kho(na["id"], "nhac", "am.nhac")
        if p:
            # mức nhạc = LU DƯỚI GIỌNG: `muc` nhe|vua|noi hoặc `db`; không ghi → quyết định am.nhac.db (máy đo giọng + tệp nhạc rồi đặt đúng)
            if muc_nhac not in ("nhe", "vua", "noi"):
                muc_nhac = ""
            db_ = so(na.get("db"), None, -40, -4)
            if db_ is None and not muc_nhac:
                db_ = so(Q.lay("am.nhac.db", "am.nhac.db"), None, -40, -4)
            ne = Q.dien(na, "ne_giong", "am.nhac.ne_giong", "am.nhac")
            nhac = {"id": na["id"], "duong": p, "muc": muc_nhac or None, "db": db_, "ne_giong": bool(ne) if ne is not None else True,
                    "vao": so(Q.dien(na, "vao", "am.nhac.vao", "am.nhac"), 0, 0, 10), "ra": so(Q.dien(na, "ra", "am.nhac.ra", "am.nhac"), 0, 0, 10),
                    "bat_dau": so(na.get("bat_dau"), 0, 0)}
    elif isinstance(na, dict) and na.get("id") and muc_nhac == "khong":
        may_sua.append({"lop": "am.nhac", "sua": "bo", "mo_ta": "am.nhac.muc = khong → không nhạc nền"})
    sfx = []
    ns_sfx = _NhomSfx(du_an)
    db_sfx_kenh = _THIEU
    for i_s, s in enumerate(am_ai.get("sfx") or []):
        if not isinstance(s, dict) or not s.get("id"):
            continue
        t = so(s.get("t", 0), 0, 0)
        if dur and t > dur:
            may_sua.append({"lop": "am.sfx", "sua": "giay", "tu": t, "den": None, "mo_ta": f"sfx t={t} ngoài thời lượng → bỏ"})
            continue
        db = so(s.get("db"), None, -40, 6)
        if db is None:
            if db_sfx_kenh is _THIEU:
                db_sfx_kenh = so(Q.lay("am.sfx.db", f"am.sfx[{i_s}].db"), None, -40, 6)      # R2: đường đúng cú pháp JSON (trước `am.sfx[@t]`)
            db = db_sfx_kenh
        if db is None:
            continue
        n_tra = len(gt.tra_kho)
        g_nhom = ns_sfx.lay(s["id"])
        p = gt.kho(g_nhom or s["id"], "sfx", f"am.sfx@{t}", bat_buoc=False)
        if g_nhom and p:
            gt.tra_kho.append({"lop": f"am.sfx@{t}", "loai": "sfx", "nghia": f"nhóm {s['id']}", "id": g_nhom, "duong": p, "ung_vien": []})
        if p:
            sfx.append({"t": round(t, 3), "id": s["id"], "id_kho": gt.tra_kho[-1].get("id") if len(gt.tra_kho) > n_tra else s["id"], "duong": p, "db": db})
        elif gt._co_loai("sfx"):
            canh_bao.append({"id": "sfx_khong_tim_thay", "lop": f"am.sfx@{t}", "mo_ta": f"am.sfx t={t} «{str(s['id'])[:40]}» không tìm thấy trong kho — bỏ qua"})
    for l_ in lop:                                                     # tiếng của lớp video (B-roll) có am_db
        if l_.get("kieu") == "video" and l_.get("am_db") is not None:
            p_ = (l_.get("noi_dung") or {}).get("duong_giai") or (l_.get("noi_dung") or {}).get("duong")
            if not p_ or not os.path.isfile(p_):
                continue
            if not (chung.ffprobe(p_) or {}).get("co_am"):
                may_sua.append({"lop": l_["id"], "sua": "am", "mo_ta": "am_db nhưng video không có tiếng → bỏ"})
                continue
            sfx.append({"t": round(float(l_["t0"]), 3), "id": f"lop:{l_['id']}", "id_kho": None, "duong": p_, "db": float(l_["am_db"]),
                        "tu": round(float((l_.get("noi_dung") or {}).get("a") or 0), 3), "dai": round(float(l_["t1"]) - float(l_["t0"]), 3), "mo": 0.12,
                        "lop": l_["id"], "khi": "video"})
    sfx = _sfx_lop(lop, sfx, gt, dur, may_sua, ns_sfx, Q=Q, canh_bao=canh_bao)
    sfx.sort(key=lambda s: s["t"])
    am = {"nhac": nhac, "sfx": sfx, "sidechain": (am_ai.get("sidechain") if isinstance(am_ai.get("sidechain"), dict) else Q.tuy("am.sidechain")),
          "giong_lufs": so(Q.lay("am.giong_lufs", "am.giong_lufs"), None, -30, -8),
          "giong_db": so(am_ai.get("giong_db") if am_ai.get("giong_db") is not None else Q.tuy("am.giong_db"), 0, -6, 6),
          "dinh_dbtp": so(Q.lay("am.dinh_dbtp", "am.dinh_dbtp"), None, -6, 0)}

    # --- chỉnh màu / LUT (chỉ khi người dùng cho phép: viec.json cho_chinh_mau)
    mau_video = None
    mv_ai = ct.get("mau_video")
    if isinstance(mv_ai, str):
        mv_ai = {"lut": mv_ai}
    if isinstance(mv_ai, dict) and mv_ai:
        if not viec.get("cho_chinh_mau"):
            loi.append({"id": "chinh_mau_khong_cho_phep", "lop": "mau_video", "khong_sua_duoc": False,
                        "mo_ta": "người dùng KHÔNG cho chỉnh màu/LUT (viec.json cho_chinh_mau=false) — bỏ `mau_video` khỏi công thức"})
        else:
            mau_video = {"cuong_do": so(mv_ai.get("cuong_do"), 1.0, 0, 1)}
            for k in ("sang", "tuong_phan", "bao_hoa", "am_lanh"):
                if mv_ai.get(k) is not None:
                    mau_video[k] = so(mv_ai.get(k), 0, -1, 1)
            if mv_ai.get("lut"):
                pl = gt.kho(mv_ai["lut"], "lut", "mau_video")
                if pl and not pl.lower().endswith((".cube", ".3dl")):
                    loi.append({"id": "tai_nguyen_khong_co", "lop": "mau_video", "mo_ta": f"`{mv_ai['lut']}` không phải LUT .cube/.3dl"})
                    pl = None
                mau_video["lut"] = mv_ai["lut"]; mau_video["duong"] = pl
            if not mau_video.get("duong") and len(mau_video) == 1:
                mau_video = None

    # --- bìa: phuong_an[1..N] do AI (khung_t + thiet_ke); không có khung ứng viên máy chọn, không bù biến thể
    bia_ai = ct.get("bia") if isinstance(ct.get("bia"), dict) else {}
    dn0 = dur_nguon(0) if dur_nguon(0) else 1e9

    def _chuan_tk(thiet_ke, Db):
        tk = json.loads(json.dumps(thiet_ke))
        for j, c in enumerate(tk.get("chu") or []):
            if isinstance(c, dict):
                Dc = f"{Db}.chu[{j}]"
                kd = _kieu_dang_chu(c.get("kieu_dang"), Q, f"{Dc}.kieu_dang", "bia.chu", "tieu_de")
                kd["font_duong"] = gt.font(kd["font"], "bia", "tieu_de", text=str(c.get("text") or ""), dam=kd.get("dam"), nghieng=(True if kd.get("nghieng") else None), duong=f"{Dc}.kieu_dang.font")
                c["kieu_dang"] = kd
                c["vi_tri"] = _vi_tri_chuan(c.get("vi_tri"), "chu", Q, f"{Dc}.vi_tri", may_sua, "bia")
        for h in tk.get("hinh") or []:
            if isinstance(h, dict) and h.get("duong"):
                h["duong_giai"] = gt.kho(h["duong"], "anh", "bia.hinh", bat_buoc=False)
        nen_b = tk.get("nen") if isinstance(tk.get("nen"), dict) else None
        if nen_b is None:
            nen_b = Q.lay("bia.nen", f"{Db}.nen") or {}
        else:
            nen_b = dict(nen_b)
            for k_ in ("kieu", "mo", "toi"):
                if nen_b.get(k_) is None:
                    v_ = Q.lay(f"bia.nen.{k_}", f"{Db}.nen.{k_}")
                    if v_ is not None:
                        nen_b[k_] = v_
        if nen_b.get("kieu") in ("anh", "kho") and nen_b.get("gia_tri"):
            nen_b["duong"] = gt.kho(nen_b["gia_tri"], "nen", "bia.nen", bat_buoc=False)
        tk["nen"] = nen_b
        ng = tk.get("nguoi")
        if isinstance(ng, dict):
            for k_ in ("co", "x", "y", "bong"):
                if ng.get(k_) is None:
                    v_ = Q.lay(f"bia.nguoi.{k_}", f"{Db}.nguoi.{k_}")
                    if v_ is not None:
                        ng[k_] = v_
            if ng.get("lat") is None and Q.tuy("bia.nguoi.lat") is not None:   # R2: lat tuỳ chọn trong khuôn → không báo thieu_truong
                ng["lat"] = Q.tuy("bia.nguoi.lat")
            if "vien_sang" not in ng:
                q = Q.lay("bia.nguoi.vien_sang", f"{Db}.nguoi.vien_sang")
                ng["vien_sang"] = {"w": q.get("w"), "mau": q.get("mau")} if isinstance(q, dict) and q.get("mau") else None
            elif ng.get("vien_sang") is True:
                q = Q.lay("bia.nguoi.vien_sang", f"{Db}.nguoi.vien_sang")
                ng["vien_sang"] = dict(q) if isinstance(q, dict) else None
            if ng.get("bong") is True or "bong" not in ng:
                q = Q.lay("bia.nguoi.bong", f"{Db}.nguoi.bong")
                ng["bong"] = dict(q) if isinstance(q, dict) else None
            elif isinstance(ng.get("bong"), dict) and mau_chuan(ng["bong"].get("mau")) is None:
                Q.bat_buoc(f"{Db}.nguoi.bong.mau", "bóng người AI ghi cần mau")
        return tk

    phuong_an = []
    pa_ai = bia_ai.get("phuong_an") if isinstance(bia_ai.get("phuong_an"), list) else (ct.get("bia") if isinstance(ct.get("bia"), list) else [])
    if not pa_ai and isinstance(bia_ai.get("thiet_ke"), dict):
        pa_ai = [{"ten": "thiết kế", "khung_t": bia_ai.get("khung_t"), "thiet_ke": bia_ai["thiet_ke"]}]
        may_sua.append({"lop": "bia", "sua": "phuong_an", "mo_ta": "bia.thiet_ke đơn → coi là bia.phuong_an[0] (1 bìa); nhiều bìa thì ghi phuong_an[]"})
    for i, pa in enumerate(pa_ai[:8]):
        if not isinstance(pa, dict):
            continue
        Db = f"bia.phuong_an[{i}]"
        tk_ = pa.get("thiet_ke") if isinstance(pa.get("thiet_ke"), dict) else (pa if any(k in pa for k in ("nen", "chu", "khoi", "nguoi", "hinh")) else None)
        if not tk_:
            loi.append({"id": "bia", "lop": Db, "duong": f"{Db}.thiet_ke", "khong_sua_duoc": False, "mo_ta": "phương án bìa thiếu thiet_ke{nen,nguoi,khoi,chu,hinh}"})
            continue
        kt_ = so(pa.get("khung_t"), None, 0, dn0)
        if kt_ is None:
            Q.bat_buoc(f"{Db}.khung_t", "giây gốc lấy khung bìa là lựa chọn của AI (xem bia-ung-vien.jpg / bang-khung.jpg)")
            continue
        phuong_an.append({"ten": str(pa.get("ten") or pa.get("y_tuong") or f"phương án {i + 1}")[:60], "khung_t": round(kt_, 3), "thiet_ke": _chuan_tk(tk_, Db)})
    if not phuong_an and not any((l.get("duong") or "").startswith("bia") for l in loi) and not any(d.startswith("bia") for d, _ in Q.rieng):
        Q.bat_buoc("bia.phuong_an", "bìa là thiết kế của AI: phuong_an[{ten, khung_t, thiet_ke}] ≥ 1; máy không có bìa mặc định")
    so_pa = nguyen(Q.lay("bia.so_phuong_an", "bia.so_phuong_an"), None, 1, 8) if phuong_an else None
    if so_pa and len(phuong_an) != so_pa:
        canh_bao.append({"id": "bia_so_phuong_an", "lop": "bia", "thong_tin": True, "mo_ta": f"AI ghi {len(phuong_an)} phương án bìa, quyết định kênh ghi {so_pa} — máy vẽ đúng {len(phuong_an)} bìa AI ghi"})
    bia = {"khung_t": phuong_an[0]["khung_t"] if phuong_an else None, "thiet_ke": phuong_an[0]["thiet_ke"] if phuong_an else None, "phuong_an": phuong_an}
    can_alpha = bool(nen_moi) or any((p_.get("thiet_ke") or {}).get("nguoi") for p_ in phuong_an) or any(l.get("lam_nen") for l in lop)

    # --- lỗi thieu_truong gộp + gộp may_sua trùng
    Q.ket(loi)
    da, ms2 = set(), []
    for m in may_sua:
        k = json.dumps(m, sort_keys=True, ensure_ascii=False, default=str)
        if k not in da:
            da.add(k); ms2.append(m)
    may_sua[:] = ms2
    ke_hoach = {
        "phien_ban": 2, "du_an": du_an, "ten": viec.get("ten") or os.path.basename(du_an), "ho_so": viec.get("ho_so"),
        "khung": [W, H], "fps": fps, "dur": dur, "vung_an_toan": chung.vung_an_toan(W, H),
        "nguon": nguon, "cat": cat, "nguon_cat": nguon_cat, "y_do": ct.get("y_do") if isinstance(ct.get("y_do"), (dict, str)) else None,
        "cat_tu_dong": {"nhip": nhip_dung or (chung.doc_json(os.path.join(du_an, "doc", "cat-de-xuat.json")) or {}).get("nhip")} if nguon_cat == "de_xuat" else (ct.get("cat_tu_dong") or None),
        "phong_cach": pc, "font": font_vai,
        "quyet_dinh": (dict(qd, _nguon=nguon_qd) if isinstance(qd, dict) else None), "quyet_dinh_nguon": nguon_qd,
        "camera": cam, "lop": lop, "phu_de": phu_de, "nen_moi": nen_moi, "chuyen_canh": chuyen, "am": am, "bia": bia,
        "mau_video": mau_video, "xuat": xuat or None,
        "can_alpha": can_alpha, "tra_kho": tra_kho, "may_sua": may_sua, "loi_chuan_hoa": loi, "canh_bao_chuan_hoa": canh_bao,
        "ghi_chu": str(ct.get("ghi_chu") or ""), "kho_san_sang": KHO_SAN_SANG,
    }
    chung.ghi_json(os.path.join(du_an, "ke-hoach.json"), ke_hoach)
    return ke_hoach, loi


if __name__ == "__main__":
    import pprint
    if len(sys.argv) > 1:
        da = sys.argv[1]
        kh, l = chuan_hoa(da, os.path.join(da, "cong-thuc.json"))
        print("lớp:", len(kh["lop"]), "dur:", kh["dur"], "font:", kh["font"], "quyết định:", kh.get("quyet_dinh_nguon"))
        pprint.pprint(l)
        pprint.pprint(kh["may_sua"])
        pprint.pprint(kh["canh_bao_chuan_hoa"])
