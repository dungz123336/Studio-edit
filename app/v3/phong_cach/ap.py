# -*- coding: utf-8 -*-
"""PHONG CÁCH NHANH — 20 Style Spec mẫu (người dùng gõ /review, /sanpham… → Studio nạp spec của gói cho video đó).
Đây là lựa chọn CỦA NGƯỜI DÙNG nên gói được mang gu; luật cứng/khoá màu-font của hồ sơ vẫn thắng (điều phối gộp).

    from phong_cach import ap
    ap.ds()                       # [{id, ten, lenh, mo_ta, hop_voi, minh_hoa (đường dẫn tuyệt đối)}]
    ap.spec_cho("review")         # dict Style Spec (đúng nao/style_spec.schema.json) — nhận id hoặc lệnh "/danhgia"
    ap.quyet_dinh_cho("review")   # dict quyet_dinh của gói (khuôn ai/hop_dong) — mặc định kênh khi hồ sơ chưa có quyet-dinh.json
    ap.tim("/Đánh-giá")           # → "review" | None
    ap.goi_y("review tai nghe")   # → [(id, điểm)] top 3 theo từ khoá
    python v3/phong_cach/ap.py ds | xem /review | goi-y "câu yêu cầu" | kiem
"""
import os, sys, json, glob, re, unicodedata

DAY = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.dirname(DAY)
if V3 not in sys.path:
    sys.path.insert(0, V3)
_GOI = None


def _chuan(s):
    s = (s or "").strip().replace(chr(92), "/")
    if "/" in s.strip("/"):                       # Git Bash đổi "/review" → "C:/Program Files/Git/review" → lấy phần cuối
        s = s.rstrip("/").rsplit("/", 1)[-1]
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")
    return re.sub(r"[\s\-_]+", "", s).lstrip("/")


def _nap():
    global _GOI
    if _GOI is None:
        _GOI = {}
        for p in sorted(glob.glob(os.path.join(DAY, "*.json"))):
            try:
                with open(p, encoding="utf-8") as f:
                    g = json.load(f)
                if g.get("id") and g.get("spec"):
                    _GOI[g["id"]] = g
            except Exception:
                pass
    return _GOI


def tim(lenh_hoac_id):
    """'/Đánh-giá' | 'danhgia' | 'review' → id gói (None nếu không có)"""
    k = _chuan(lenh_hoac_id)
    for gid, g in _nap().items():
        if k == _chuan(gid) or any(k == _chuan(l) for l in g.get("lenh") or []):
            return gid
    return None


def goi(goi_id):
    """toàn bộ gói (meta + spec) hoặc None"""
    gid = tim(goi_id)
    return json.loads(json.dumps(_nap()[gid])) if gid else None


def spec_cho(goi_id, ho_so=None):
    """id hoặc /lệnh → Style Spec (bản sao, sửa thoải mái). KeyError nếu không có gói.
    1.2.21: không còn biến thể bố cục theo băm tên hồ sơ (ho_so giữ để tương thích, không dùng) — gu của gói là của gói, khách chọn."""
    g = goi(goi_id)
    if not g:
        raise KeyError(f"không có phong cách '{goi_id}' — xem ds()")
    s = g["spec"]
    s["_goi"] = {"id": g["id"], "ten": g.get("ten"), "grade": g.get("grade"), "cam": g.get("cam") or [], "cho_phep_den_trang": g.get("cho_phep_den_trang")}
    return s


def quyet_dinh_cho(goi_id):
    """id hoặc /lệnh → quyet_dinh (khuôn ai/hop_dong.KHUON_QUYET_DINH) của gói — bản sao; None nếu gói không có"""
    g = goi(goi_id)
    if not g or not isinstance(g.get("quyet_dinh"), dict):
        return None
    q = g["quyet_dinh"]
    q["_nguon"] = "goi:" + g["id"]
    return q


def ds():
    ra = []
    for gid, g in _nap().items():
        ra.append({"id": gid, "ten": g.get("ten"), "lenh": g.get("lenh") or [], "mo_ta": g.get("mo_ta"), "hop_voi": g.get("hop_voi") or [],
                   "minh_hoa": os.path.join(DAY, g["minh_hoa"]) if g.get("minh_hoa") and os.path.isfile(os.path.join(DAY, g["minh_hoa"])) else None})
    return ra


def goi_y(cau, n=3):
    """câu yêu cầu tự do → [(id, điểm)] theo từ khoá/hợp với (không dấu)"""
    c = " " + re.sub(r"\s+", " ", unicodedata.normalize("NFD", (cau or "").lower())) + " "
    c = "".join(x for x in c if unicodedata.category(x) != "Mn").replace("đ", "d")
    diem = []
    for gid, g in _nap().items():
        d = 0.0
        for t in (g.get("tu_khoa") or []) + (g.get("hop_voi") or []):
            t2 = "".join(x for x in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(x) != "Mn").replace("đ", "d")
            if t2 and t2 in c:
                d += 1.0 + 0.2 * len(t2.split())
        if any(_chuan(l) in _chuan(cau) for l in g.get("lenh") or []):
            d += 5
        if d > 0:
            diem.append((gid, round(d, 2)))
    diem.sort(key=lambda r: -r[1])
    return diem[:n]


def kiem():
    """→ {id: [lỗi spec] + [lỗi quyết định]} (quyết định kiểm bằng ai/hop_dong)"""
    from hoc import kiem_spec as K
    from ai import hop_dong as H
    ra = {}
    for gid, g in _nap().items():
        l = list(K.kiem(g["spec"]))
        if not isinstance(g.get("quyet_dinh"), dict):
            l.append("thiếu quyet_dinh")
        else:
            l += [f"{x['duong']}: {x['goi_y']}" for x in H.kiem_quyet_dinh(g["quyet_dinh"])]
        ra[gid] = l
    return ra


if __name__ == "__main__":
    a = sys.argv[1:] or ["ds"]
    if a[0] == "ds":
        for g in ds():
            print(f"{g['id']:<11} {' '.join(g['lenh']):<44} {g['ten']}")
    elif a[0] == "xem":
        print(json.dumps(goi(a[1]), ensure_ascii=False, indent=1))
    elif a[0] == "goi-y":
        print(goi_y(" ".join(a[1:])))
    elif a[0] == "kiem":
        k = kiem()
        for gid, l in k.items():
            print(("✓ " if not l else "✗ ") + gid + ("" if not l else " " + "; ".join(l)))
        print(f"{sum(1 for l in k.values() if not l)}/{len(k)} hợp lệ")
