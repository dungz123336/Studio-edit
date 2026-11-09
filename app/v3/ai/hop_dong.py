# -*- coding: utf-8 -*-
"""HỢP ĐỒNG DỮ LIỆU (1.2.21, mục 1c/1d): khuôn cho `cong-thuc.json` (AI viết mỗi video) và `quyet-dinh.json`
(QUYẾT ĐỊNH CỦA KÊNH — AI viết một lần, thay mọi mặc định thẩm mỹ từng hàn trong máy).

    kiem(cong_thuc, quyet_dinh, khung) -> {"loi": [{"duong", "ma", "goi_y"}], "canh_bao": [...]}
        ma ∈ thieu_truong | sai_kieu | ngoai_mien | khong_biet
        duong: đường dẫn trường đúng cú pháp JSON, vd `lop[2].vi_tri.w`, `quyet_dinh.chu.co`
    kiem_quyet_dinh(qd) -> [loi]            kiem_cong_thuc(ct, khung) -> ({"loi", "canh_bao"})
    doc_quyet_dinh(du_an, ho_so) -> (qd|None, nguon|None, loi[])      # <dự án>/quyet-dinh-kenh.json → hồ sơ → None
    luu_quyet_dinh(ho_so, qd, nguon="") -> đường tệp                 # ghi nao/ca-nhan/<hs>/quyet-dinh.json, lịch sử 20 bản
    mau_quyet_dinh() -> dict                                           # v3/ai/quyet-dinh.mau.json (mẫu chuẩn, bộ hồi quy dùng)
    khuon_toi_thieu_md() -> str                                        # khuôn gọn in vào tóm tắt khi kênh chưa có quyết định
Viết tay, không gói ngoài. Thứ tự điền trường trống của công thức (cong_thuc.py): lớp → bài học/Style Spec → quyet_dinh → lỗi thieu_truong.
"""
import json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung

AI_DIR = os.path.dirname(os.path.abspath(__file__))
KIEU_LOP = ("chu", "khoi", "the", "hinh", "video", "duong", "py", "mau", "web")
ANCHOR = ("tl", "tc", "tr", "ml", "mc", "mr", "bl", "bc", "br")
SO_VOI = ("khung", "mat", "duoi_cam", "tren_dau")
ANIM_KIEU = ("fade", "slide", "pop", "blur", "wipe", "typewriter", "flip", "tilt", "none")
EASE = ("linear", "in", "out", "in_out", "back", "spring", "expo", "step")
TACH = ("none", "tu", "ky_tu", "dong")
CAN = ("trai", "giua", "phai")
HOA_TRON = ("normal", "screen", "add", "multiply", "overlay", "soft_light", "lighten", "darken")
MAU_RE = re.compile(r"^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
SO_LICH_SU = 20


# ---------------------------------------------------------------- bộ tả khuôn (mini-schema)
def so(lo=None, hi=None):
    return ("so", lo, hi)


def nguyen(lo=None, hi=None):
    return ("int", lo, hi)


def chuoi(toi_da=None):
    return ("str", toi_da)


def bool_():
    return ("bool",)


def mau():
    return ("mau",)


def enum(*gia_tri):
    return ("enum", tuple(gia_tri))


def ds(item, it=None, nhieu=None):
    return ("list", item, it, nhieu)


def obj(truong, mo=False):
    """truong: {ten: (spec, bat_buoc)}; mo=True → khoá lạ không báo"""
    return ("obj", truong, mo)


def hoac(*spec):
    return ("hoac", spec)


def bat_ky():
    return ("any",)


NULL = ("null",)
R = True
O = False

# ---- mảnh dùng chung (hình dạng = đúng thứ engine đọc: dung/mau/bang.py QUYET_DINH_XEM_TRUOC — A3)
VIEN_ITEM = obj({"w": (so(0, 60), R), "mau": (mau(), R)})
BONG_ITEM = obj({"x": (so(-400, 400), O), "y": (so(-400, 400), O), "mo": (so(0, 120), O), "mau": (mau(), R)})
NEN_CHU = hoac(NULL, obj({"mau": (mau(), R), "dem": (ds(so(0, 200), 2, 2), R), "bo": (so(0, 200), R)}))
GRADIENT = hoac(NULL, obj({"mau": (ds(mau(), 2, 4), R), "goc": (so(-360, 360), R)}))
VIEN_HOAC_NULL = hoac(NULL, VIEN_ITEM)
DS_VIEN = hoac(NULL, ds(VIEN_ITEM))
DS_BONG = hoac(NULL, ds(BONG_ITEM))
DONG_TAC = obj({"kieu": (enum(*ANIM_KIEU), R), "dai": (so(0, 3), R), "ease": (enum(*EASE), R),
                "tu": (obj({}, mo=True), O), "toi": (obj({}, mo=True), O)})
DONG_TAC_QD = hoac(obj({"kieu": (enum("none"), R), "dai": (so(0, 3), O), "ease": (enum(*EASE), O)}), DONG_TAC)   # kieu none không cần dai/ease
VI_TRI_QD = obj({"anchor": (enum(*ANCHOR), R), "x": (so(-1, 2), R), "y": (so(-1, 2), R), "so_voi": (enum(*SO_VOI), R), "theo_mat": (bool_(), O)})
CAP = ds(so(0, 1), 2, 2)
TRANG_THAI = obj({}, mo=True)
KD_CHU_QD = {"co": (so(10, 600), R), "dam": (nguyen(100, 900), R), "dong": (so(0.7, 2.5), R), "can": (enum(*CAN), R), "mau": (mau(), R),
             "font": (chuoi(200), R), "rong_max": (so(0.2, 1), R), "hoa": (bool_(), O), "gian": (so(-0.2, 0.5), O),
             "vien": (DS_VIEN, O), "bong": (DS_BONG, O), "nen": (NEN_CHU, O), "gradient": (GRADIENT, O)}

# ---- QUYẾT ĐỊNH KÊNH (mục 1c; R = engine/cong_thuc đọc bắt buộc, O = tuỳ chọn — thiếu thì AI phải ghi trong công thức khi dùng tới)
KHUON_QUYET_DINH = obj({
    "phien": (nguyen(1, 99999), R),
    "ly_do": (chuoi(600), O),
    "font": (obj({"tieu_de": (chuoi(200), R), "phu_de": (chuoi(200), R), "nhan": (chuoi(200), R)}), R),
    "bang_mau": (hoac(NULL, obj({"nhan": (mau(), R), "nhan2": (mau(), R), "sang": (mau(), R), "toi": (mau(), R)})), R),
    "chu": (obj(KD_CHU_QD), R),
    "khoi": (obj({"cach_dong": (so(0.3, 2), R), "can": (enum(*CAN), O), "rong_max": (so(0.2, 1), O)}), R),
    "the": (obj({"hinh": (enum("pill", "rect", "circle"), R), "mau": (mau(), R), "bo": (so(0, 300), R), "dem": (ds(so(0, 200), 2, 2), R),
                 "vien": (VIEN_HOAC_NULL, O), "bong": (DS_BONG, O),
                 "chu": (obj({"co": (so(10, 300), R), "dam": (nguyen(100, 900), R), "mau": (mau(), R), "font": (chuoi(200), R),
                              "vien": (DS_VIEN, O), "bong": (DS_BONG, O), "gradient": (GRADIENT, O)}), R)}), R),
    "hinh": (obj({"fit": (enum("cover", "contain"), R), "bo": (so(0, 300), R), "vien": (VIEN_HOAC_NULL, O), "bong": (DS_BONG, O)}), O),
    "duong": (obj({"w": (so(1, 80), R), "ve": (so(0, 5), R), "ease": (enum(*EASE), R), "mau": (mau(), O)}), R),
    "phu_de": (obj({"che_do": (enum("cum", "tu", "tat"), R), "toi_da_chu": (nguyen(8, 60), R), "karaoke": (bool_(), R),
                    "keo_dai": (so(0, 2), R), "lang_ngat": (so(0, 5), R), "tween": (so(0, 2), R), "nhuong_cho": (so(0, 1), R), "mau_noi": (mau(), R),
                    "hien": (enum("noi", "dan"), O), "khi_chong": (enum("doi", "an"), O), "an_khi_lop_chu": (bool_(), O),
                    "kieu_dang": (obj({"font": (chuoi(200), R), "co": (so(10, 400), R), "dam": (nguyen(100, 900), R), "mau": (mau(), R),
                                       "dong": (so(0.7, 2.5), R), "can": (enum(*CAN), R), "mau_noi": (mau(), O), "hoa": (bool_(), O), "gian": (so(-0.2, 0.5), O),
                                       "rong_max": (so(0.2, 1), O), "vien": (DS_VIEN, O), "bong": (DS_BONG, O), "nen": (NEN_CHU, O), "gradient": (GRADIENT, O)}), R),
                    "vi_tri": (VI_TRI_QD, R),
                    "anim": (obj({"vao": (DONG_TAC_QD, R), "ra": (DONG_TAC_QD, R)}), R)}), R),
    "anim": (obj({"vao": (DONG_TAC, R), "ra": (DONG_TAC, R), "so_le": (so(0, 1), R), "keyframe_dai": (so(0, 5), R),
                  "keyframe_ease": (enum(*EASE), R), "ken_burns": (ds(so(1, 2), 2, 2), R), "nhoe_dong": (so(0, 4), O),
                  "kieu": (obj({"slide": (TRANG_THAI, R), "pop": (TRANG_THAI, R), "blur": (TRANG_THAI, R), "flip": (TRANG_THAI, R), "tilt": (TRANG_THAI, R)}), R)}), R),
    "camera": (obj({"ease": (enum(*EASE), R), "dai": (so(0, 10), O)}), R),
    "vi_tri": (obj({"hop_mac_dinh": (obj({"hinh": (CAP, R), "py": (CAP, R), "mau": (CAP, R), "web": (CAP, R), "video": (CAP, O)}), R),
                    "cach_nhom": (so(0, 1), R), "anchor": (enum(*ANCHOR), O), "so_voi": (enum(*SO_VOI), O), "xep": (enum("doc", "ngang"), O)}), R),
    "ne_mat": (obj({"thu_toi": (so(0.3, 1), R), "noi": (so(0, 1), O)}), R),
    "am": (obj({"nhac": (obj({"db": (so(-40, -4), R), "vao": (so(0, 10), R), "ra": (so(0, 10), R), "ne_giong": (bool_(), R)}), R),
                "sfx": (obj({"db": (so(-40, -3), R)}), R),
                "giong_lufs": (so(-30, -8), R), "dinh_dbtp": (so(-6, 0), R), "giong_db": (so(-6, 6), O),
                "sidechain": (obj({"threshold": (so(0, 1), R), "ratio": (so(1, 20), R), "attack": (so(0, 2000), R), "release": (so(0, 5000), R)}), O)}), R),
    "nen_moi": (obj({"mau": (mau(), R), "mo_sigma": (so(0, 200), R), "toi": (so(0, 1), R), "kieu": (enum("mau", "gradient", "mo"), O),
                     "mo": (so(0, 1), O), "vien_sang": (VIEN_HOAC_NULL, O)}), R),
    "chuyen_canh": (obj({"flash_dai": (so(0, 2), R), "zoom_dai": (so(0, 2), O)}), R),
    "cat": (obj({"nhip": (enum("nhanh", "vua", "cham"), R)}), O),
    "bia": (obj({"so_phuong_an": (nguyen(1, 8), R),
                 "nen": (obj({"kieu": (enum("mau", "gradient", "khung_mo", "anh", "kho"), R), "gia_tri": (bat_ky(), O), "mo": (so(0, 1), R), "toi": (so(0, 1), R)}), R),
                 "nguoi": (obj({"co": (so(0.3, 3), R), "x": (so(0, 1), R), "y": (so(0, 1), R), "vien_sang": (VIEN_HOAC_NULL, R),
                                "bong": (hoac(NULL, BONG_ITEM), R), "lat": (bool_(), O)}), R),
                 "chu": (obj({"co": (so(10, 600), R), "dam": (nguyen(100, 900), R), "mau": (mau(), R), "font": (chuoi(200), R),
                              "hoa": (bool_(), O), "can": (enum(*CAN), O), "gian": (so(-0.2, 0.5), O), "dong": (so(0.7, 2.5), O), "rong_max": (so(0.2, 1), O),
                              "vien": (DS_VIEN, O), "bong": (DS_BONG, O), "nen": (NEN_CHU, O), "gradient": (GRADIENT, O)}), R),
                 "tuong_phan_toi_thieu": (so(1, 21), R), "de_mat_toi_da": (so(0, 1), R)}), R),
})

# ---- CÔNG THỨC (cong-thuc.json) — AI viết gọn; trường bỏ trống điền theo thứ tự lớp → spec → quyết định → thieu_truong
KD_CHU = obj({"font": (chuoi(200), O), "co": (so(10, 600), O), "dam": (nguyen(100, 900), O), "mau": (mau(), O), "hoa": (bool_(), O),
              "gian": (so(-0.2, 0.5), O), "dong": (so(0.7, 2.5), O), "can": (enum(*CAN), O), "nghieng": (so(-30, 30), O),
              "noi_3d": (obj({"sau": (so(0, 120), R), "goc": (so(-360, 360), R), "mau": (mau(), R), "mau2": (mau(), O)}), O),
              "vien": (ds(VIEN_ITEM), O), "bong": (ds(BONG_ITEM), O),
              "nen": (hoac(NULL, obj({"mau": (mau(), R), "dem": (ds(so(0, 200), 2, 2), O), "bo": (so(0, 200), O)})), O),
              "gradient": (hoac(NULL, obj({"mau": (ds(mau(), 2, 4), R), "goc": (so(-360, 360), R)})), O),
              "rong_max": (so(0.2, 1), O)}, mo=True)
KD_THE = obj({"hinh": (enum("pill", "rect", "circle"), O), "mau": (mau(), O), "bo": (so(0, 300), O), "dem": (ds(so(0, 200), 2, 2), O),
              "vien": (hoac(NULL, VIEN_ITEM, ds(VIEN_ITEM)), O), "bong": (ds(BONG_ITEM), O),
              "chu": (obj({"co": (so(10, 300), O), "dam": (nguyen(100, 900), O), "mau": (mau(), O), "font": (chuoi(200), O)}), O)}, mo=True)
KD_PHU = {"hoa_tron": (enum(*HOA_TRON), O), "do_trong": (so(0, 1), O), "fit": (enum("cover", "contain"), O), "bo": (so(0, 300), O),
          "vien": (hoac(NULL, VIEN_ITEM, ds(VIEN_ITEM)), O), "bong": (ds(BONG_ITEM), O), "am_db": (so(-40, 6), O), "lap": (bool_(), O),
          "toc_do": (so(0.25, 4), O), "am": (bool_(), O)}
VI_TRI_CT = obj({"anchor": (enum(*ANCHOR), O), "x": (so(-1, 2), O), "y": (so(-1, 2), O), "so_voi": (enum(*SO_VOI), O),
                 "w": (so(0.02, 4000), O), "h": (so(0.02, 4000), O), "theo_mat": (bool_(), O), "nhom": (chuoi(40), O),
                 "xep": (enum("doc", "ngang"), O), "cach": (so(0, 400), O)}, mo=True)
DONG_TAC_CT = obj({"kieu": (enum(*ANIM_KIEU), O), "dai": (so(0, 3), O), "ease": (enum(*EASE), O), "tu": (obj({}, mo=True), O), "toi": (obj({}, mo=True), O)})
ANIM_CT = obj({"vao": (DONG_TAC_CT, O), "ra": (DONG_TAC_CT, O), "tach": (enum(*TACH), O), "so_le": (so(0, 1), O), "nhoe_dong": (so(0, 4), O),
               "keyframes": (ds(obj({"t": (so(0, 10000), R), "dai": (so(0, 5), O), "ease": (enum(*EASE), O)}, mo=True)), O),
               "ken_burns": (obj({"z": (ds(so(1, 2), 2, 2), R)}), O)}, mo=True)
AM_LOP = hoac(chuoi(200), obj({"vao": (hoac(chuoi(200), obj({"id": (chuoi(200), R), "db": (so(-40, 6), O), "lech": (so(-1, 1), O)})), O),
                               "ra": (hoac(chuoi(200), obj({"id": (chuoi(200), R), "db": (so(-40, 6), O), "lech": (so(-1, 1), O)})), O),
                               "db": (so(-40, 6), O), "lech": (so(-1, 1), O)}))
DONG_KHOI = hoac(chuoi(400), obj({"text": (chuoi(400), R), "lech": (so(-1, 1), O), "xoay": (so(-60, 60), O), "dx": (so(-1080, 1080), O), "dy": (so(-1080, 1080), O),
                                  "tre": (so(0, 10), O), "anim": (ANIM_CT, O), "kieu_dang": (KD_CHU, O)}, mo=True))
NOI_DUNG = {
    "chu": obj({"text": (chuoi(600), R), "theo_loi": (bool_(), O)}),
    "khoi": obj({"dong": (ds(DONG_KHOI, 1, 40), R)}),
    "the": obj({"text": (chuoi(300), R), "icon": (hoac(NULL, chuoi(200)), O)}),
    "hinh": obj({"duong": (chuoi(600), R)}),
    "video": obj({"src": (nguyen(0, 99), O), "a": (so(0, 100000), O), "duong": (chuoi(600), O), "id": (chuoi(200), O)}),
    "duong": obj({"loai": (enum("gach_chan", "mui_ten", "khung", "khoanh"), R), "tu": (CAP, R), "den": (CAP, R)}),
    "py": obj({"file": (chuoi(300), R)}),
    "mau": obj({"mau": (chuoi(120), R), "tham_so": (obj({}, mo=True), O)}),
    "web": obj({}, mo=True),
}
THIET_KE_BIA = obj({"nen": (obj({"kieu": (enum("mau", "gradient", "khung_mo", "anh", "kho"), O), "gia_tri": (bat_ky(), O), "mo": (so(0, 1), O), "toi": (so(0, 1), O)}, mo=True), O),
                    "nguoi": (hoac(NULL, obj({"co": (so(0.3, 3), O), "x": (so(0, 1), O), "y": (so(0, 1), O), "vien_sang": (hoac(NULL, bool_(), VIEN_ITEM), O),
                                              "bong": (hoac(NULL, bool_(), BONG_ITEM), O), "lat": (bool_(), O)})), O),   # R2: bong/vien_sang nhận dict|true|null như cong_thuc/bia.py
                    "khoi": (ds(obj({"hinh": (enum("rect", "pill", "circle"), O), "x": (so(0, 1), R), "y": (so(0, 1), R), "w": (so(0, 1), R), "h": (so(0, 1), R),
                                     "mau": (mau(), R), "bo": (so(0, 400), O), "xoay": (so(-180, 180), O)})), O),
                    "chu": (ds(obj({"text": (chuoi(300), R), "kieu_dang": (KD_CHU, O), "vi_tri": (VI_TRI_CT, O), "xoay": (so(-180, 180), O)})), O),
                    "hinh": (ds(obj({"duong": (chuoi(600), R), "x": (so(0, 1), R), "y": (so(0, 1), R), "w": (so(0, 1), R), "h": (so(0, 1), R),
                                     "bo": (so(0, 400), O), "xoay": (so(-180, 180), O)})), O)})
PHUONG_AN_BIA = obj({"ten": (chuoi(80), O), "y_tuong": (chuoi(300), O), "khung_t": (so(0, 100000), R), "thiet_ke": (THIET_KE_BIA, R)})
KHUON_CONG_THUC = obj({
    "y_do": (hoac(chuoi(2000), obj({}, mo=True)), O),
    "khung": (ds(nguyen(16, 8192), 2, 2), O),
    "cat": (hoac(NULL, ds(obj({"src": (nguyen(0, 99), O), "a": (so(0, 100000), R), "b": (so(0, 100000), R)}))), O),
    "cat_tu_dong": (obj({"nhip": (enum("nhanh", "vua", "cham"), O)}, mo=True), O),
    "nhip": (enum("nhanh", "vua", "cham"), O),
    "phong_cach": (obj({"mau_nhan": (mau(), O), "mau_nhan2": (mau(), O), "mau_sang": (mau(), O), "mau_toi": (mau(), O),
                        "font": (obj({"tieu_de": (chuoi(200), O), "phu_de": (chuoi(200), O), "nhan": (chuoi(200), O)}), O), "cam_giac": (chuoi(300), O)}), O),
    "camera": (ds(obj({"t": (so(0, 100000), R), "z": (so(1, 2), O), "x": (so(0, 1), O), "y": (so(0, 1), O), "ease": (enum(*EASE), O), "dai": (so(0, 10), O)})), O),
    "lop": (ds(bat_ky()), R),
    "phu_de": (obj({"che_do": (enum("cum", "tu", "tat"), O), "toi_da_chu": (nguyen(8, 60), O), "karaoke": (bool_(), O), "hien": (enum("noi", "dan"), O),
                    "khi_chong": (enum("doi", "an"), O), "an_khi_lop_chu": (bool_(), O), "sua": (obj({}, mo=True), O),
                    "kieu_dang": (obj({"font": (chuoi(200), O), "co": (so(10, 400), O), "dam": (nguyen(100, 900), O), "mau": (mau(), O), "mau_noi": (mau(), O),
                                       "hoa": (bool_(), O), "vien": (ds(VIEN_ITEM), O), "bong": (ds(BONG_ITEM), O),
                                       "nen": (hoac(NULL, obj({"mau": (mau(), R), "dem": (ds(so(0, 200), 2, 2), O), "bo": (so(0, 200), O)})), O)}), O),
                    "vi_tri": (VI_TRI_CT, O), "anim": (ANIM_CT, O)}), O),
    "nen_moi": (ds(obj({"t0": (so(0, 100000), O), "t1": (so(0, 100000), O),
                        "nen": (obj({"kieu": (enum("mau", "gradient", "anh", "video", "kho", "mo"), O), "gia_tri": (bat_ky(), O), "mo": (so(0, 1), O)}), O),   # R2: kieu bỏ → quyết định nen_moi.kieu → thieu_truong
                        "vien_sang": (hoac(NULL, obj({"w": (so(0, 40), O), "mau": (mau(), O)})), O)})), O),
    "chuyen_canh": (ds(obj({"t": (so(0, 100000), R), "kieu": (enum("flash", "zoom", "cut"), R), "dai": (so(0, 2), O)})), O),
    "am": (obj({"nhac": (hoac(NULL, chuoi(200), obj({"id": (chuoi(200), O), "muc": (enum("nhe", "vua", "noi", "khong"), O), "db": (so(-40, -4), O),
                                                     "ne_giong": (bool_(), O), "vao": (so(0, 10), O), "ra": (so(0, 10), O), "bat_dau": (so(0, 100000), O)})), O),
                "sfx": (ds(obj({"t": (so(0, 100000), R), "id": (chuoi(200), R), "db": (so(-40, 6), O)})), O),
                "giong_db": (so(-6, 6), O)}), O),
    "mau_video": (hoac(NULL, chuoi(200), obj({"lut": (chuoi(200), O), "cuong_do": (so(0, 1), O), "sang": (so(-1, 1), O), "tuong_phan": (so(-1, 1), O),
                                              "bao_hoa": (so(-1, 1), O), "am_lanh": (so(-1, 1), O)})), O),
    "xuat": (obj({"cao": (nguyen(720, 4320), O), "fps": (nguyen(24, 60), O)}), O),
    "bia": (hoac(ds(PHUONG_AN_BIA, 1, 8),
                 obj({"phuong_an": (ds(PHUONG_AN_BIA, 1, 8), O), "khung_t": (so(0, 100000), O), "thiet_ke": (THIET_KE_BIA, O)})), O),
    "ghi_chu": (chuoi(2000), O),
})
LOP_CHUNG = {"id": (chuoi(60), O), "kieu": (enum(*KIEU_LOP), R), "t0": (so(0, 100000), R), "t1": (so(0, 100000), R),
             "vi_tri": (VI_TRI_CT, O), "anim": (ANIM_CT, O), "z": (nguyen(-10, 10), O), "ne_mat": (bool_(), O), "sau_nguoi": (bool_(), O),
             "toan_khung": (bool_(), O),           # R2: mọi kiểu lớp (kể cả chu/khoi/the) được ghi toan_khung:true → cong_thuc chép sang kế hoạch
             "co_y": (bool_(), O), "am": (AM_LOP, O), "sfx": (AM_LOP, O)}


# ---------------------------------------------------------------- bộ kiểm
def _ten_kieu(spec):
    k = spec[0]
    if k == "so":
        return "số" + (f" {spec[1]}..{spec[2]}" if spec[1] is not None or spec[2] is not None else "")
    if k == "int":
        return "số nguyên" + (f" {spec[1]}..{spec[2]}" if spec[1] is not None else "")
    if k == "enum":
        return "|".join(str(x) for x in spec[1])
    return {"str": "chuỗi", "bool": "true|false", "mau": "màu #RRGGBB[AA]", "list": "mảng", "obj": "object", "null": "null", "any": "bất kỳ"}.get(k, k)


def _hop_kieu(v, spec):
    """giá trị v có cùng kiểu cơ bản với nhánh spec của `hoac` không (để chọn nhánh báo lỗi đúng chỗ)"""
    k = spec[0]
    if k == "null":
        return v is None
    if k == "obj":
        return isinstance(v, dict)
    if k == "list":
        return isinstance(v, list)
    if k in ("str", "mau", "enum"):
        return isinstance(v, str)
    if k == "bool":
        return isinstance(v, bool)
    if k in ("so", "int"):
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    return True


def _kiem(v, spec, duong, loi, canh_bao):
    k = spec[0]
    if k == "any":
        return
    if k == "null":
        if v is not None:
            loi.append({"duong": duong, "ma": "sai_kieu", "goi_y": "phải là null"})
        return
    if k == "hoac":
        tot = None
        ung = [s for s in spec[1] if _hop_kieu(v, s)] or list(spec[1])   # R2: ưu tiên nhánh cùng kiểu với giá trị (null/dict/list/str/bool) → lỗi đúng chỗ
        for s in ung:
            l2, c2 = [], []
            _kiem(v, s, duong, l2, c2)
            if not l2:
                canh_bao.extend(c2)
                return
            if tot is None or len(l2) < len(tot[0]):
                tot = (l2, c2)
        if tot:
            loi.extend(tot[0]); canh_bao.extend(tot[1])
        return
    if k == "bool":
        if not isinstance(v, bool):
            loi.append({"duong": duong, "ma": "sai_kieu", "goi_y": "phải là true|false"})
        return
    if k in ("so", "int"):
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            loi.append({"duong": duong, "ma": "sai_kieu", "goi_y": f"phải là {_ten_kieu(spec)}"})
            return
        if k == "int" and int(v) != v:
            loi.append({"duong": duong, "ma": "sai_kieu", "goi_y": "phải là số nguyên"})
            return
        lo, hi = spec[1], spec[2]
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            loi.append({"duong": duong, "ma": "ngoai_mien", "goi_y": f"{v} ngoài {lo}..{hi}"})
        return
    if k == "str":
        if not isinstance(v, str):
            loi.append({"duong": duong, "ma": "sai_kieu", "goi_y": "phải là chuỗi"})
        elif spec[1] and len(v) > spec[1]:
            loi.append({"duong": duong, "ma": "ngoai_mien", "goi_y": f"dài {len(v)} > {spec[1]} ký tự"})
        return
    if k == "mau":
        if not isinstance(v, str) or not MAU_RE.match(v.strip()):
            loi.append({"duong": duong, "ma": "sai_kieu", "goi_y": "màu dạng #RRGGBB hoặc #RRGGBBAA"})
        return
    if k == "enum":
        if v not in spec[1]:
            loi.append({"duong": duong, "ma": "khong_biet", "goi_y": f"`{v}` không có; nhận: {_ten_kieu(spec)}"})
        return
    if k == "list":
        if not isinstance(v, list):
            loi.append({"duong": duong, "ma": "sai_kieu", "goi_y": "phải là mảng"})
            return
        it, nhieu = spec[2], spec[3]
        if it is not None and len(v) < it:
            loi.append({"duong": duong, "ma": "ngoai_mien", "goi_y": f"cần ≥ {it} phần tử"})
        if nhieu is not None and len(v) > nhieu:
            loi.append({"duong": duong, "ma": "ngoai_mien", "goi_y": f"tối đa {nhieu} phần tử"})
        for i, x in enumerate(v):
            _kiem(x, spec[1], f"{duong}[{i}]", loi, canh_bao)
        return
    if k == "obj":
        if not isinstance(v, dict):
            loi.append({"duong": duong, "ma": "sai_kieu", "goi_y": "phải là object"})
            return
        truong, mo = spec[1], spec[2]
        for ten, (s, bat_buoc) in truong.items():
            if ten not in v:
                if bat_buoc:
                    loi.append({"duong": f"{duong}.{ten}" if duong else ten, "ma": "thieu_truong", "goi_y": f"thiếu `{ten}` ({_ten_kieu(s)})"})
                continue
            _kiem(v[ten], s, f"{duong}.{ten}" if duong else ten, loi, canh_bao)
        if not mo:
            for ten in v:
                if ten not in truong and not str(ten).startswith("_"):
                    canh_bao.append({"duong": f"{duong}.{ten}" if duong else ten, "ma": "khong_biet", "goi_y": f"trường `{ten}` không có trong khuôn — bỏ qua"})
        return
    loi.append({"duong": duong, "ma": "sai_kieu", "goi_y": f"khuôn không hiểu kiểu {k}"})


def kiem_quyet_dinh(qd):
    """→ danh sách lỗi (đường dẫn tiền tố `quyet_dinh.`)"""
    loi, cb = [], []
    if not isinstance(qd, dict):
        return [{"duong": "quyet_dinh", "ma": "sai_kieu", "goi_y": "quyet-dinh.json phải là object JSON"}]
    _kiem(qd, KHUON_QUYET_DINH, "quyet_dinh", loi, cb)
    return loi


def _kiem_lop(l, i, loi, canh_bao, khung):
    d = f"lop[{i}]"
    if not isinstance(l, dict):
        loi.append({"duong": d, "ma": "sai_kieu", "goi_y": "mỗi lớp là object"})
        return
    kieu = l.get("kieu")
    _kiem(l, obj(LOP_CHUNG, mo=True), d, loi, canh_bao)
    if isinstance(l.get("t0"), (int, float)) and isinstance(l.get("t1"), (int, float)) and l["t1"] <= l["t0"]:
        loi.append({"duong": f"{d}.t1", "ma": "ngoai_mien", "goi_y": f"t1 ({l['t1']}) phải > t0 ({l['t0']})"})
    if kieu not in KIEU_LOP:
        return
    nd = l.get("noi_dung")
    if nd is None:
        if kieu != "web":
            loi.append({"duong": f"{d}.noi_dung", "ma": "thieu_truong", "goi_y": f"lớp {kieu} cần noi_dung"})
    else:
        _kiem(nd, NOI_DUNG[kieu], f"{d}.noi_dung", loi, canh_bao)
        if kieu == "video" and isinstance(nd, dict) and nd.get("src") is None and not nd.get("duong") and not nd.get("id"):
            loi.append({"duong": f"{d}.noi_dung.src", "ma": "thieu_truong", "goi_y": "lớp video cần src (nguồn phụ) hoặc duong/id (kho, đường dẫn)"})
    kd = l.get("kieu_dang")
    if kd is not None:
        if kieu in ("chu", "khoi"):
            _kiem(kd, KD_CHU, f"{d}.kieu_dang", loi, canh_bao)
        elif kieu == "the":
            _kiem(kd, KD_THE, f"{d}.kieu_dang", loi, canh_bao)
        elif kieu in ("hinh", "video"):
            _kiem(kd, obj(KD_PHU, mo=True), f"{d}.kieu_dang", loi, canh_bao)
        elif kieu == "duong":
            _kiem(kd, obj({"w": (so(1, 80), O), "mau": (mau(), O), "ve": (so(0, 5), O)}), f"{d}.kieu_dang", loi, canh_bao)
        elif not isinstance(kd, dict):
            loi.append({"duong": f"{d}.kieu_dang", "ma": "sai_kieu", "goi_y": "phải là object"})
    vt = l.get("vi_tri")
    if isinstance(vt, dict) and khung and kieu != "web":
        for k_ in ("w", "h"):
            if isinstance(vt.get(k_), (int, float)) and vt[k_] > 1:
                loi.append({"duong": f"{d}.vi_tri.{k_}", "ma": "ngoai_mien", "goi_y": "w/h là tỉ lệ 0..1 của khung (chỉ lớp web nhận px)"})


def kiem_cong_thuc(ct, khung=None):
    loi, cb = [], []
    if not isinstance(ct, dict):
        return {"loi": [{"duong": "", "ma": "sai_kieu", "goi_y": "cong-thuc.json phải là object JSON có `lop`"}], "canh_bao": []}
    _kiem(ct, KHUON_CONG_THUC, "", loi, cb)
    for i, l in enumerate(ct.get("lop") or []):
        _kiem_lop(l, i, loi, cb, khung)
    if isinstance(ct.get("khung"), list) and khung and len(ct["khung"]) == 2:
        try:
            if [int(ct["khung"][0]), int(ct["khung"][1])] != [int(khung[0]), int(khung[1])]:
                cb.append({"duong": "khung", "ma": "ngoai_mien", "goi_y": f"công thức ghi khung {ct['khung']} nhưng việc là {list(khung)} — máy dùng khung của việc"})
        except Exception:
            pass
    return {"loi": loi, "canh_bao": cb}


def kiem(cong_thuc, quyet_dinh=None, khung=None):
    """kiểm công thức + quyết định kênh (nếu có). quyet_dinh=None → cảnh báo `quyet_dinh_chua_co` (lỗi thieu_truong cụ thể do cong_thuc.py báo
    khi điền trường trống). → {"loi": [{"duong","ma","goi_y"}], "canh_bao": [...]}"""
    kq = kiem_cong_thuc(cong_thuc, khung) if cong_thuc is not None else {"loi": [], "canh_bao": []}
    if quyet_dinh is None:
        kq["canh_bao"].append({"duong": "quyet_dinh", "ma": "thieu_truong",
                               "goi_y": "kênh chưa có quyet-dinh.json — mọi trường công thức bỏ trống sẽ báo thieu_truong; Write <dự án>/quyet-dinh-kenh.json theo khuôn"})
    else:
        kq["loi"] += kiem_quyet_dinh(quyet_dinh)
    return kq


# ---------------------------------------------------------------- đọc / lưu quyết định kênh
def _p_ho_so(ho_so):
    return os.path.join(chung.duong("ho_so"), str(ho_so or ""))


def duong_quyet_dinh(ho_so):
    return os.path.join(_p_ho_so(ho_so), "quyet-dinh.json")


def mau_quyet_dinh():
    return chung.doc_json(os.path.join(AI_DIR, "quyet-dinh.mau.json")) or {}


def luu_quyet_dinh(ho_so, qd, nguon="", ly_do_luu=""):
    """ghi nao/ca-nhan/<hs>/quyet-dinh.json (tmp + replace qua chung.ghi_json) + lịch sử quyet-dinh-lich-su/<ts>.json (giữ SO_LICH_SU bản).
    Trùng nội dung bản hiện có → không ghi lịch sử. Trả đường tệp."""
    if not ho_so:
        raise ValueError("thiếu tên hồ sơ")
    p = duong_quyet_dinh(ho_so)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    cu = chung.doc_json(p)
    if cu is not None and chung.bam({k: v for k, v in cu.items() if not k.startswith("_")}) == chung.bam({k: v for k, v in qd.items() if not k.startswith("_")}):
        return p
    ls = os.path.join(_p_ho_so(ho_so), "quyet-dinh-lich-su")
    os.makedirs(ls, exist_ok=True)
    if cu is not None:
        ten = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}.json"
        chung.ghi_json(os.path.join(ls, ten), {"luc": time.strftime("%Y-%m-%d %H:%M:%S"), "nguon": cu.get("_nguon"), "ly_do_luu": cu.get("_ly_do_luu"), "quyet_dinh": cu})
        cac = sorted(f for f in os.listdir(ls) if f.endswith(".json"))
        for f in cac[:-SO_LICH_SU] if len(cac) > SO_LICH_SU else []:
            try:
                os.remove(os.path.join(ls, f))
            except OSError:
                pass
    moi = dict(qd)
    moi["_nguon"] = nguon or moi.get("_nguon") or "ai"
    moi["_luc"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if ly_do_luu:
        moi["_ly_do_luu"] = ly_do_luu
    chung.ghi_json(p, moi)
    return p


def doc_quyet_dinh(du_an=None, ho_so=None, luu=True):
    """→ (qd | None, nguon | None, loi[]).
    1) <dự án>/quyet-dinh-kenh.json (AI vừa viết) → kiểm khuôn → đạt: lưu vào hồ sơ (lịch sử 20 bản) → dùng; lỗi → (None, "du_an", loi)
    2) nao/ca-nhan/<hs>/quyet-dinh.json
    3) None"""
    if du_an:
        p = os.path.join(du_an, "quyet-dinh-kenh.json")
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8-sig") as f:
                    qd = json.load(f)
            except Exception as ex:
                return None, "du_an", [{"duong": "quyet_dinh", "ma": "sai_kieu", "goi_y": f"quyet-dinh-kenh.json không phải JSON hợp lệ: {str(ex)[:120]}"}]
            loi = kiem_quyet_dinh(qd)
            if loi:
                return None, "du_an", loi
            if luu and ho_so:
                try:
                    luu_quyet_dinh(ho_so, qd, nguon="ai", ly_do_luu=f"AI viết trong dự án {os.path.basename(os.path.abspath(du_an))}")
                except Exception:
                    pass
            return qd, "du_an", []
    if ho_so:
        qd = chung.doc_json(duong_quyet_dinh(ho_so))
        if isinstance(qd, dict):
            loi = kiem_quyet_dinh(qd)
            return (qd, "ho_so", []) if not loi else (None, "ho_so", loi)
    return None, None, []


def _mo_ta_khuon(spec, sau=0):
    """khuôn → chuỗi JSON-ish gọn (kiểu/miền thay giá trị) để in cho AI"""
    k = spec[0]
    if k == "obj":
        phan = []
        for ten, (s, bat_buoc) in spec[1].items():
            phan.append(f'"{ten}{"" if bat_buoc else "?"}": {_mo_ta_khuon(s, sau + 1)}')
        return "{" + ", ".join(phan) + "}"
    if k == "list":
        return "[" + _mo_ta_khuon(spec[1], sau + 1) + ("" if spec[2] is None else f" ×{spec[2]}" + (f"..{spec[3]}" if spec[3] and spec[3] != spec[2] else "")) + "]"
    if k == "hoac":
        return " | ".join(_mo_ta_khuon(s, sau + 1) for s in spec[1])
    return "<" + _ten_kieu(spec) + ">"


def khuon_toi_thieu_md():
    """khuôn quyet-dinh.json dạng gọn (mọi trường, kiểu + miền) — in vào tóm tắt khi kênh chưa có quyết định"""
    D = ["Khuôn quyet-dinh.json (khoá có dấu ? = tuỳ chọn, còn lại BẮT BUỘC; số là px ở khổ 1080 / giây / tỉ lệ 0..1; màu #RRGGBB[AA]; "
         "font = id kho | tên họ | đường dẫn; <a> | <b> = một trong hai dạng):"]
    for ten, (s, bat_buoc) in KHUON_QUYET_DINH[1].items():
        D.append(f'  "{ten}{"" if bat_buoc else "?"}": {_mo_ta_khuon(s)}')
    D.append(f"Mẫu đầy đủ chép được: {os.path.join(AI_DIR, 'quyet-dinh.mau.json')}")
    return "\n".join(D)


def _gon(spec, v):
    """khuôn → giá trị ví dụ CHỈ khoá bắt buộc (lấy từ mẫu chuẩn); không có mẫu → <kiểu>"""
    k = spec[0]
    if k == "hoac":
        for s in spec[1]:
            if _hop_kieu(v, s):
                return _gon(s, v)
        return _gon(spec[1][-1], v)
    if k == "obj":
        return {ten: _gon(s, v.get(ten) if isinstance(v, dict) else None) for ten, (s, r) in spec[1].items() if r}
    if k == "list":
        return [_gon(spec[1], x) for x in v[:2]] if isinstance(v, list) else []
    return v if v is not None else "<" + _ten_kieu(spec) + ">"


def khuon_gon_md():
    """khuôn GỌN (R2, ≤ ~3k ký tự) in vào tóm tắt khi kênh chưa có quyết định: CHỈ khoá BẮT BUỘC, giá trị = ví dụ từ mẫu chuẩn
    (AI tự chọn số của kênh); khoá tuỳ chọn + kiểu/miền đầy đủ → `python v3/ai/hop_dong.py khuon` / từ điển."""
    mau = mau_quyet_dinh()
    D = ["Khuôn GỌN quyet-dinh.json — chỉ khoá BẮT BUỘC, giá trị dưới đây là VÍ DỤ từ mẫu chuẩn (số/màu/font là lựa chọn của bạn cho kênh; "
         "px ở khổ 1080 / giây / tỉ lệ 0..1; màu #RRGGBB[AA]; font = id kho | tên họ | đường dẫn):"]
    for ten, (s, bat_buoc) in KHUON_QUYET_DINH[1].items():
        if not bat_buoc:
            continue
        D.append(f'  "{ten}": {json.dumps(_gon(s, mau.get(ten)), ensure_ascii=False, separators=(",", ":"))}')
    tuy = [ten for ten, (s, r) in KHUON_QUYET_DINH[1].items() if not r]
    D.append(f"Khoá tuỳ chọn ({', '.join(tuy)}; trong mục: hoa/gian/nen/gradient/vien/bong, phu_de.hien/khi_chong/an_khi_lop_chu, anim.nhoe_dong, "
             "camera.dai, vi_tri.anchor/so_voi/xep/hop_mac_dinh.video, ne_mat.noi, am.giong_db/sidechain, nen_moi.kieu/mo/vien_sang, chuyen_canh.zoom_dai, "
             "bia.nguoi.lat, bia.chu.*) + kiểu/miền đầy đủ: xem từ điển mục QUYẾT ĐỊNH KÊNH hoặc `python v3/ai/hop_dong.py khuon`. "
             f"Mẫu đầy đủ chép được: {os.path.join(AI_DIR, 'quyet-dinh.mau.json')}")
    return "\n".join(D)


def quyet_dinh_gon(qd, toi_da=2600, dong_toi_da=420):
    """bản rút gọn ĐỦ MỌI TRƯỜNG (JSON compact từng mục) để in trong tóm tắt. R2: KHÔNG cắt JSON giữa chừng — mục dài hơn
    dong_toi_da thì tách thành từng khoá con (`- phu_de.kieu_dang: {...}`), AI đọc được trọn vẹn."""
    if not isinstance(qd, dict):
        return []
    D = []

    def them(ten, v):
        s = json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        if len(s) + len(ten) + 4 <= dong_toi_da or not isinstance(v, dict) or not v:
            D.append(f"- {ten}: {s}")
            return
        for k2, v2 in v.items():
            them(f"{ten}.{k2}", v2)
    for k, v in qd.items():
        if k.startswith("_"):
            continue
        them(k, v)
    return D


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "khuon":
        print(khuon_toi_thieu_md())
    elif a and a[0] == "khuon-gon":
        print(khuon_gon_md())
    elif a and a[0] == "mau":
        print(json.dumps(kiem_quyet_dinh(mau_quyet_dinh()), ensure_ascii=False, indent=1))
    elif len(a) >= 1:
        ct = chung.doc_json(a[0])
        qd = chung.doc_json(a[1]) if len(a) > 1 else None
        print(json.dumps(kiem(ct, qd), ensure_ascii=False, indent=1))
    else:
        print(__doc__)
