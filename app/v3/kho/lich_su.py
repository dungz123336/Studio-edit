# -*- coding: utf-8 -*-
"""Lịch sử dùng tài nguyên kho theo hồ sơ → bảng `lich_su` trong kho-chi-muc/kho.sqlite (kho/csdl.py; 1.2.21 — trước là lich-su-dung.jsonl)

ghi_tu_du_an(du_an, ho_so=None)   đọc cong-thuc.json (+ ke-hoach.json) của dự án → mọi id kho / đường dẫn file kho đã dùng → ghi
                                  (thay bản cũ của CHÍNH dự án đó, gọi lại vô hại). Điều phối nên gọi sau bước giao. Chữ ký giữ nguyên.
gan_day(ho_so, n_video=None, bo=None) → {id: số video đã dùng} của n video gần nhất của hồ sơ (bỏ dự án `bo`) — SQL có LIMIT.
                                  n_video mặc định = cau_hinh v3.kho.n_lich_su (30).
dem_toan_may(thang=12) → {id: số dự án} trên cả máy trong `thang` tháng gần đây — tie-break "ít dùng" ở kho/tim.py; nhớ theo phiên csdl.
n_lich_su() → số video lịch sử theo cấu hình.
"""
import os, sys, re, time, threading
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung
from kho import csdl

_khoa = threading.Lock()
MAU_ID = re.compile(r"^(nhac|sfx|font|nen|icon|video|lut|anh|preset_capcut|mau)\.[a-z0-9][a-z0-9_-]*$")   # 1.2.19: ghi cả mẫu đồ hoạ (mau.<id>)
THANG_DEM = 12


def cau_hinh_kho():
    """mục `kho` trong cấu hình lõi (cau-hinh.json → v3.kho): n_lich_su, bac_it_dung, so_ung_vien, lam_nong, thang_dem"""
    c = chung.cau_hinh().get("kho")
    return c if isinstance(c, dict) else {}


def n_lich_su():
    try:
        return max(1, int(cau_hinh_kho().get("n_lich_su", 30)))
    except (TypeError, ValueError):
        return 30


def _ten_du_an(du_an):
    return os.path.basename(os.path.normpath(du_an))


def _ho_so_cua(du_an):
    viec = chung.doc_json(os.path.join(du_an, "viec.json"), {}) or {}
    return viec.get("ho_so") or ""


def id_trong(obj, theo_duong=None):
    """mọi id kho (và đường dẫn file kho, nếu có bảng theo_duong) xuất hiện trong obj JSON"""
    ra = []

    def di(x):
        if isinstance(x, dict):
            for v in x.values():
                di(v)
        elif isinstance(x, list):
            for v in x:
                di(v)
        elif isinstance(x, str):
            s = x.strip()
            if MAU_ID.match(s):
                ra.append(s)
            elif theo_duong and len(s) > 4 and (":" in s or "/" in s or "\\" in s):
                k = os.path.normcase(os.path.normpath(s))
                if k in theo_duong:
                    ra.append(theo_duong[k])
    di(obj)
    return ra


def ghi_tu_du_an(du_an, ho_so=None):
    """→ danh sách id đã ghi"""
    from kho import tim
    ho_so = ho_so or _ho_so_cua(du_an)
    theo_duong = {os.path.normcase(os.path.normpath(m["duong"])): m["id"] for m in tim.tat_ca() if m.get("duong")}
    ids = []
    for f in ("cong-thuc.json", "ke-hoach.json"):
        j = chung.doc_json(os.path.join(du_an, f))
        if j:
            ids.extend(id_trong(j, theo_duong))
    da = []
    for i in ids:
        if i not in da and (i.startswith("mau.") or tim.lay(i)):
            da.append(i)
    if not da:
        return []
    with _khoa:
        csdl.ghi_lich_su(_ten_du_an(du_an), ho_so, da, time.strftime("%Y-%m-%d %H:%M:%S"))
    return da


_DEM = {"phien": None, "thang": None, "ra": {}, "luc": 0.0}
DEM_NHO_GIAY = 0.5     # R3 1.2.21: api._gon / tim gọi dem_toan_may() từng mục — csdl.phien() mở SQLite ~2 ms → chỉ hỏi lại phiên sau 0,5 s


def dem_toan_may(thang=None):
    """{id: số dự án đã dùng} trên CẢ máy (mọi hồ sơ), chỉ `thang` tháng gần đây (mặc định cấu hình v3.kho.thang_dem = 12).
    Nhớ theo phiên csdl: chỉ truy vấn lại khi bảng đổi."""
    if thang is None:
        try:
            thang = int(cau_hinh_kho().get("thang_dem", THANG_DEM))
        except (TypeError, ValueError):
            thang = THANG_DEM
    if _DEM["phien"] is not None and thang == _DEM["thang"] and time.time() - _DEM["luc"] < DEM_NHO_GIAY:
        return _DEM["ra"]
    try:
        ph = csdl.phien()
    except Exception:
        return {}
    _DEM["luc"] = time.time()
    if ph != _DEM["phien"] or thang != _DEM["thang"]:
        _DEM["ra"] = csdl.dem_toan_may(thang)
        _DEM["phien"], _DEM["thang"] = ph, thang
    return _DEM["ra"]


def gan_day(ho_so, n_video=None, bo=None):
    """{id: số video} trong n video gần nhất của hồ sơ (SQL LIMIT)"""
    if not ho_so:
        return {}
    return csdl.lich_su_gan_day(ho_so, n_video or n_lich_su(), bo)


def du_an_da_ghi(ho_so):
    """tên các dự án đã có lịch sử của hồ sơ (goi_video đồng bộ dự án còn thiếu)"""
    return csdl.du_an_da_ghi(ho_so) if ho_so else set()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(ghi_tu_du_an(sys.argv[1]))
