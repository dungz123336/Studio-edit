#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Đọc cau-hinh.json. Thiếu khoá nào thì lấy mặc định, không nổ."""
import json, os, functools
import nen_tang as NT

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)


def ho_so_hien_tai():
    """tên hồ sơ cá nhân đang dùng — biến HO_SO (Studio ghim theo việc) → nao/ca-nhan/HIEN-TAI (tầng 3 của bộ não)"""
    if os.environ.get("HO_SO", "").strip():
        return os.environ["HO_SO"].strip()
    try:
        return open(os.path.join(SKILL, "nao", "ca-nhan", "HIEN-TAI"), encoding="utf-8").read().strip() or None
    except OSError:
        return None


_hs = ho_so_hien_tai()
_file_hs = os.path.join(SKILL, "nao", "ca-nhan", _hs, "cau-hinh.json") if _hs else ""
FILE = os.environ.get("CAU_HINH") or (_file_hs if _file_hs and os.path.exists(_file_hs)
                                      else os.path.join(SKILL, "cau-hinh.json"))
FILE = os.path.expanduser(FILE)   # biến môi trường CAU_HINH cho phép mỗi kênh một hồ sơ riêng

MAC_DINH = {
    "kenh": {"ten": "", "seri": "", "ngon_ngu": "vi"},
    "kho": {"duong_dan": NT.kho_mac_dinh()},
    "chu": {"phu_de": "BeVietnamPro-Black.ttf", "title_to": "Anton-Regular.ttf",      # font OFL — có trong kho sạch
            "bia": "BarlowCondensed-Black.ttf"},
    "mau": {"nhan": "#FFD200", "chu_chinh": "#FFFFFF",
            "nen_card": "#0E0E12", "vien": "#000000"},
    "logo": {"duong_dan": ""},
    "quay": {"may": "", "profile_mau": "thuong"},
    "dung": {"toc_do": 1.1, "giu_nghi": 0.20, "giu_nghi_dai": 0.28,
             "nguong_lang": 0.33, "khung_hinh": 30, "kich_thuoc": [1080, 1920]},
    "am_thanh": {"giong": -16, "nhac": -34, "nhan": -27, "chuyen_canh": -30,
                 "giao_dien": -29, "dich_cuoi": -15.5, "dinh_that": -2.0},
    "bia": {"kieu": "hai-dong", "cat_tiktok": [240, 1680], "le_duoi": 100,
            "mo_tu_y": 880},
    "ban_giao": {"thu_muc": "~/Downloads", "moi_video_mot_thu_muc": True},
}


MAY = os.path.join(SKILL, "cau-hinh.json")   # lớp MÁY: kho ở đâu, sức máy — chung mọi hồ sơ trên máy này


def _tron(cfg, file):
    if not os.path.exists(file):
        return
    try:
        nguoi_dung = json.load(open(file, encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"{file} hỏng ở dòng {e.lineno}: {e.msg}")
    for k, v in nguoi_dung.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update({a: b for a, b in v.items() if not a.startswith("_")})
        else:
            cfg[k] = v


@functools.lru_cache(maxsize=1)
def tai():
    """3 lớp, lớp sau đè lớp trước: mặc định → cau-hinh.json của máy → cau-hinh.json của hồ sơ đang dùng"""
    cfg = {k: dict(v) if isinstance(v, dict) else v for k, v in MAC_DINH.items()}
    _tron(cfg, MAY)
    if os.path.abspath(FILE) != os.path.abspath(MAY):
        _tron(cfg, FILE)
    return cfg


def lay(*duong, mac_dinh=None):
    """lay('am_thanh','giong') -> -16"""
    o = tai()
    for d in duong:
        if not isinstance(o, dict) or d not in o:
            return mac_dinh
        o = o[d]
    return o


def dung_lut():
    return lay("quay", "profile_mau") == "dlog"


if __name__ == "__main__":
    c = tai()
    print(f"Hồ sơ  : {ho_so_hien_tai() or '(không)'}  ->  {FILE}")
    print(f"Kênh   : {c['kenh']['ten'] or '(chưa đặt)'}")
    print(f"Kho    : {c['kho']['duong_dan']}")
    print(f"Phụ đề : {c['chu']['phu_de']}")
    print(f"Màu    : {c['mau']['nhan']}")
    print(f"LUT    : {'có' if dung_lut() else 'không (quay profile thường)'}")
