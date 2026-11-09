# -*- coding: utf-8 -*-
"""THƯ VIỆN MẪU — đồ hoạ dựng sẵn (cảnh trám, thẻ, chữ hiệu ứng, đồ hoạ chỉ dẫn, giao diện giả, chuyển cảnh, lớp phủ…)
cho engine 1.3. Mẫu KHÔNG phải khuôn cố định: AI gọi bằng id, đổi mọi tham số, màu/font lấy từ phong cách của video,
hoạt ảnh vào/ra/keyframe do engine chung lo (anim của lớp). Mẫu chỉ vẽ NỘI DUNG theo thời gian t của nó.

AI dùng trong cong-thuc.json:
  {"id":"s1","kieu":"mau","t0":4,"t1":9,"noi_dung":{"mau":"mau.so-do-tu-duy","tham_so":{"tam":"AI edit","nhanh":["Chữ","Hiệu ứng"]}},
   "vi_tri":{"anchor":"mc","x":0.5,"y":0.45,"w":0.9,"h":0.5}, "anim":{"vao":{"kieu":"pop"}}}

HỢP ĐỒNG MỘT MẪU (mỗi file trong thư mục này, mỗi hàm một mẫu):
    from dung.mau import dang_ky
    @dang_ky(id="mau.so-do-tu-duy", nhom="canh", ten="Sơ đồ tư duy mọc nhánh",
             mo_ta="ý trung tâm + các nhánh hiện dần theo lời", hop_nghia=["liệt kê", "phân loại", "nhiều ý"],
             tham_so={"tam": "chữ trung tâm", "nhanh": "list chữ nhánh", "nhip": "giây giữa 2 nhánh (0.35)"},
             mac_dinh={"nhip": 0.35}, hop={"anchor": "mc", "x": 0.5, "y": 0.45, "w": 0.9, "h": 0.5},
             dong=True, toan_khung=False, sfx_goi_y=["pop nhẹ"], vi_du={...tham_so mẫu để vẽ thử...})
    def ve(t, dur, W, H, c, p):
        '''t: giây từ t0 · dur: t1−t0 · W,H: px HỘP của lớp · c: CongCu (màu/font/chữ/ảnh/kho/mặt) · p: tham số đã điền mặc định
        → numpy uint8 RGBA (H, W, 4) KHÔNG nhân trước alpha'''
- dong=False: nội dung không đổi theo t (engine vẽ 1 lần, chỉ chạy anim vào/ra) — nhanh hơn nhiều.
- toan_khung=True: mẫu chiếm cả khung (cảnh trám toàn màn, chuyển cảnh) — hộp mặc định = cả khung.
- lam_nen=True: mẫu cần ảnh nền thật dưới nó (vd làm mờ/tối ngoài vùng, chữ sau người) — engine truyền c.nen(t) (RGB khung đã dựng) nếu có.
Không hằng số "gu": mọi kích thước tính theo W/H và tham số; màu mặc định = vai màu của phong cách video (c.mau("nhan"…)).
"""
import importlib, os, pkgutil, traceback

REGISTRY = {}          # id → {"ham": fn, "the": {...}}
_DA_NAP = False


def dang_ky(**the):
    def boc(fn):
        the.setdefault("mac_dinh", {})
        the.setdefault("tham_so", {})
        the.setdefault("dong", True)
        the.setdefault("toan_khung", False)
        the.setdefault("lam_nen", False)
        # 1.2.21: mẫu không khai hộp → KHÔNG còn hộp 0.8×0.4 hàn trong máy: lớp lấy quyet_dinh vi_tri.hop_mac_dinh.mau (lop.hop_mac_dinh)
        the.setdefault("hop", {"anchor": "mc", "x": 0.5, "y": 0.5} if not the["toan_khung"] else {"anchor": "tl", "x": 0, "y": 0, "w": 1, "h": 1})
        the["module"] = fn.__module__
        cu = REGISTRY.get(the["id"])
        if cu and cu["the"].get("module") != the["module"]:
            print(f"(CẢNH BÁO mẫu trùng id `{the['id']}`: {cu['the'].get('module')} bị {the['module']} đè)")
        REGISTRY[the["id"]] = {"ham": fn, "the": the}
        return fn
    return boc


def nap_tat_ca():
    """import mọi file mẫu trong thư mục (lỗi một file không làm hỏng cả thư viện)"""
    global _DA_NAP
    if _DA_NAP:
        return REGISTRY
    _DA_NAP = True
    g = os.path.dirname(os.path.abspath(__file__))
    for m in pkgutil.iter_modules([g]):
        if m.name.startswith("_"):
            continue
        try:
            importlib.import_module(f"{__name__}.{m.name}")
        except Exception:
            print(f"(mẫu {m.name} lỗi khi nạp: {traceback.format_exc(limit=1).strip()[-200:]})")
    # mẫu RIÊNG: hồ sơ (nao/ca-nhan/<hs>/mau-rieng — học từ video mẫu) và dự án (<du_an>/mau-rieng) — V3_MAU_RIENG = các thư mục
    for thu in [x for x in os.environ.get("V3_MAU_RIENG", "").split(os.pathsep) if x and os.path.isdir(x)]:
        nap_thu_muc(thu)
    return REGISTRY


def nap_thu_muc(thu):
    """nạp mọi tệp .py trong một thư mục mẫu riêng (mỗi tệp dùng @dang_ky như thư viện chung) → số mẫu mới"""
    import importlib.util, hashlib
    truoc = len(REGISTRY)
    for f in sorted(os.listdir(thu)):
        if not f.endswith(".py") or f.startswith("_"):
            continue
        p = os.path.join(thu, f)
        try:
            ten = "mau_rieng_" + hashlib.md5(p.encode("utf-8")).hexdigest()[:10]
            sp = importlib.util.spec_from_file_location(ten, p)
            m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
        except Exception:
            print(f"(mẫu riêng {f} lỗi khi nạp: {traceback.format_exc(limit=1).strip()[-200:]})")
    return len(REGISTRY) - truoc


def lay(mid):
    nap_tat_ca()
    return REGISTRY.get(mid)


def danh_sach():
    """[{id, nhom, ten, mo_ta, hop_nghia, tham_so, toan_khung, sfx_goi_y}] — cho từ điển công cụ / kho hiệu ứng"""
    nap_tat_ca()
    ra = []
    for mid, r in sorted(REGISTRY.items()):
        t = r["the"]
        ra.append({k: t.get(k) for k in ("id", "nhom", "ten", "mo_ta", "hop_nghia", "tham_so", "mac_dinh", "toan_khung", "dong", "sfx_goi_y", "vi_du", "hop")})
    return ra


class CongCu:
    """bộ công cụ cho hàm vẽ mẫu — không để mẫu tự đọc file cấu hình"""

    def __init__(self, ctx, lop=None):
        self.ctx = ctx
        self.lop = lop
        self.pc = getattr(ctx, "pc", None) or {}
        self.W, self.H, self.fps = ctx.W, ctx.H, ctx.fps
        self.p = {}                       # tham số của lớp mẫu (LopMau gán) — bo_chu đọc le_ngang/le_doc

    # ---- quyết định của kênh (1.2.21)
    def quyet(self, duong, mac_dinh=None, bat_buoc=True):
        """ctx.quyet_dinh theo đường "a.b" — thiếu → ThieuTruong (bat_buoc) hoặc mac_dinh (chỉ cho giá trị vật lý)"""
        from dung import lop as _lop
        if bat_buoc:
            return _lop.quyet(self.ctx, duong, lop=getattr(self.lop, "id", None))
        return _lop.quyet(self.ctx, duong, mac_dinh, lop=getattr(self.lop, "id", None))

    def thieu(self, duong, goi_y=""):
        from dung import lop as _lop
        return _lop.ThieuTruong(duong, goi_y, getattr(self.lop, "id", None))

    def ghi_may_sua(self, muc):
        if self.lop is not None and hasattr(self.lop, "may_sua"):
            if muc not in self.lop.may_sua:
                self.lop.may_sua.append(dict(muc, lop=getattr(self.lop, "id", None)))

    # màu theo vai của phong cách video: nhan · nhan2 · sang · toi ; hoặc "#hex".
    # 1.2.21: vai không có trong phong cách video → quyet_dinh bang_mau.<vai> của kênh → thieu_truong (KHÔNG còn #FFFFFF/#BBBBBB/#111111 hàn trong máy)
    def mau(self, vai_hoac_hex, mac_dinh=None):
        v = vai_hoac_hex
        if isinstance(v, str) and (v.startswith("#") or v.startswith("rgb")):
            return v
        if isinstance(v, (list, tuple)):
            return v
        bang = {"nhan": self.pc.get("mau_nhan"), "nhan2": self.pc.get("mau_nhan2"), "sang": self.pc.get("mau_sang"), "toi": self.pc.get("mau_toi")}
        if v in bang and bang[v]:
            return bang[v]
        if v in bang:
            return self.quyet("bang_mau." + str(v))
        if mac_dinh is not None:
            return self.mau(mac_dinh)
        raise self.thieu("bang_mau." + str(v), "vai màu `%s` không có trong phong cách video lẫn quyet_dinh" % v)

    def font(self, vai="nhan"):
        return self.ctx.font_file(vai)

    def ve_chu(self, text, kieu_dang=None, rong_max_px=None, **kw):
        """→ (rgba numpy, meta) — text engine chung (kerning, viền, bóng, dấu Việt).
        1.2.21: thiếu co/dam/dong/can → quyet_dinh chu.* (không còn 60/700/1.15/giua trong chu.py); font thiếu dấu → may_sua font_thieu_dau"""
        from dung import chu as _chu, lop as _lop
        kd = dict(kieu_dang or {})
        kd.setdefault("font", "nhan")
        kd["font"] = self.ctx.font_file(kd["font"]) if not os.path.isfile(str(kd["font"])) else kd["font"]
        for k in ("co", "dam", "dong", "can"):
            if kd.get(k) is None:
                kd[k] = self.quyet("chu." + k)
        if kd.get("mau") is None:
            kd["mau"] = self.mau("sang")
        r = _chu.ve_chu(text, kd, self.W, self.H, rong_max_px=rong_max_px, **kw)
        try:
            td = (r[1] or {}).get("thieu_glyph")
            if td:
                self.ghi_may_sua(dict({"sua": "font_thieu_dau"}, **td))
        except Exception:
            pass
        return r

    def tai_nguyen(self, id_hoac_duong):
        try:
            return self.ctx.tai_nguyen(id_hoac_duong)
        except Exception:
            return None

    def mat(self, t0=None, t1=None):
        try:
            l = self.lop
            return self.ctx.mat_tai(l.t0 if t0 is None else t0, l.t1 if t1 is None else t1) if l else None
        except Exception:
            return None

    def nguoi(self, t):
        """mặt nạ người (float/uint8, CẮT đúng hộp lớp) tại t giây TÍNH TỪ t0 của lớp — None nếu engine không cấp"""
        f = getattr(self.ctx, "nguoi", None)
        try:
            return f(self.lop, t) if f else None
        except Exception:
            return None

    alpha = nguoi

    def nen(self, t):
        """RGB khung đã dựng dưới lớp tại t giây TÍNH TỪ t0 của lớp (chỉ khi mẫu khai lam_nen=True và engine cung cấp) — None nếu không có"""
        f = getattr(self.ctx, "lay_nen", None)
        return f(self.lop, t) if f else None

    @staticmethod
    def ease(ten, u):
        from dung import anim
        return anim.ease(ten, max(0.0, min(1.0, u)))
