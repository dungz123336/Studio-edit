# -*- coding: utf-8 -*-
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
"""BẢN SẮC KÊNH (nháp) từ video ĐẦU TIÊN đã giao: ke-hoach.json (công thức đã chuẩn hoá) → Style Spec đúng schema.
Kênh chưa có style-spec.json → sau khi giao, máy ghi bản nháp này; video sau AI giữ nhất quán; người dùng sửa bằng `gop-y`
hoặc thay bằng bài học từ video mẫu (tab Học). Không có gu của app: mọi giá trị lấy từ chính công thức AI đã làm cho kênh.

    tao(ke_hoach, ghi_chu="") -> spec (dict)        python v3/hoc/spec_tu_cong_thuc.py <du_an> [--ghi <ho_so>]
"""
import os, sys, json, time
from collections import Counter

V3 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if V3 not in sys.path:
    sys.path.insert(0, V3)
import chung


def _pho_bien(ds, mac_dinh=None):
    ds = [x for x in ds if x is not None]
    return Counter(ds).most_common(1)[0][0] if ds else mac_dinh


def _co_chu(lops):
    kd = [l.get("kieu_dang") or {} for l in lops]
    if not kd:
        return None
    ra = {}
    co = _pho_bien([k.get("co") for k in kd])
    if co is not None:
        ra["co"] = round(float(co))
    dam = _pho_bien([k.get("dam") for k in kd])
    if dam is not None:
        ra["dam"] = int(dam)
    hoa = _pho_bien([k.get("hoa") for k in kd if k.get("hoa") is not None])
    if hoa is not None:
        ra["hoa"] = bool(hoa)
    d = _pho_bien([k.get("dong") for k in kd])
    if d:
        ra["dong"] = round(float(d), 2)
    return ra or None


def _anchor(lops, vai):
    vt = [l.get("vi_tri") for l in lops if l.get("vi_tri")]
    if not vt:
        return None
    a = _pho_bien([v.get("anchor") for v in vt], "tc")
    x = round(float(_pho_bien([round(float(v.get("x", 0.5)), 2) for v in vt], 0.5)), 2)
    y = round(float(_pho_bien([round(float(v.get("y", 0.5)), 2) for v in vt], 0.5)), 2)
    ra = {"vai": vai, "anchor": a if a in ("tl", "tc", "tr", "ml", "mc", "mr", "bl", "bc", "br") else "tc", "x": min(1, max(0, x)), "y": min(1, max(0, y))}
    sv = _pho_bien([v.get("so_voi") for v in vt])
    if sv in ("khung", "mat", "duoi_cam", "tren_dau"):
        ra["so_voi"] = sv
    return ra


def _dong_tac(lops, khoa):
    ds = []
    for l in lops:
        a = (l.get("anim") or {}).get(khoa)
        if isinstance(a, dict) and a.get("kieu"):
            ds.append((a["kieu"], round(float(a.get("dai", 0.25)), 2), a.get("ease")))
    if not ds:
        return []
    ra = []
    for (k, d, e), n in Counter(ds).most_common(3):
        if k not in ("fade", "slide", "pop", "blur", "wipe", "typewriter", "none"):
            continue
        x = {"kieu": k, "dai": min(2.0, max(0.0, d)), "tan_suat": round(n / len(ds), 2)}
        if e in ("linear", "in", "out", "in_out", "back", "spring", "expo"):
            x["ease"] = e
        ra.append(x)
    return ra


def _chi_ai(kh, tho):
    """1.2.19 (D3): giữ lại trong kế hoạch CHỈ những trường AI đã ghi trong cong-thuc.json gốc (tho) — số máy điền (cỡ, viền, vị trí,
    anim, phụ đề mặc định…) KHÔNG được rút thành bản sắc kênh. Không có bản gốc → dùng kế hoạch như cũ."""
    if not isinstance(tho, dict):
        return kh
    import copy as _cp
    kh2 = _cp.deepcopy(kh)
    lop_tho = {str(l.get("id")): l for l in (tho.get("lop") or []) if isinstance(l, dict)}
    tho_ds = [l for l in (tho.get("lop") or []) if isinstance(l, dict)]
    lop_moi = []
    for i_l, l in enumerate(kh2.get("lop") or []):
        t = lop_tho.get(str(l.get("id")))
        if t is None and i_l < len(tho_ds) and len(tho_ds) == len(kh2.get("lop") or []):
            t = tho_ds[i_l]                      # chuan_hoa đổi id (thiếu/trùng) → khớp theo vị trí
        if t is None:
            if str(l.get("id", "")).startswith("pd"):
                lop_moi.append(l)
            continue
        kd_t = t.get("kieu_dang") if isinstance(t.get("kieu_dang"), dict) else {}
        l["kieu_dang"] = {k: v for k, v in (l.get("kieu_dang") or {}).items() if k in kd_t}
        if not isinstance(t.get("vi_tri"), dict):
            l.pop("vi_tri", None)
        if not isinstance(t.get("anim"), dict):
            l.pop("anim", None)
        else:
            l["anim"] = {k: v for k, v in (l.get("anim") or {}).items() if k in t["anim"]}
        lop_moi.append(l)
    kh2["lop"] = lop_moi
    pd_t = tho.get("phu_de") if isinstance(tho.get("phu_de"), dict) else {}
    pd = kh2.get("phu_de") or {}
    kd_t = pd_t.get("kieu_dang") if isinstance(pd_t.get("kieu_dang"), dict) else {}
    pd["kieu_dang"] = {k: v for k, v in (pd.get("kieu_dang") or {}).items() if k in kd_t} or None
    if not isinstance(pd_t.get("vi_tri"), dict):
        pd.pop("vi_tri", None)
    for k in ("che_do", "toi_da_chu"):
        if k not in pd_t:
            pd.pop(k, None)
    kh2["phu_de"] = pd
    pc_t = tho.get("phong_cach") if isinstance(tho.get("phong_cach"), dict) else {}
    pc = kh2.get("phong_cach") or {}
    for k in ("mau_nhan", "mau_nhan2", "mau_sang", "mau_toi"):
        if not pc_t.get(k):
            pc.pop(k, None)
    if not isinstance(pc_t.get("font"), dict):
        pc["font"] = {}
    kh2["phong_cach"] = pc
    if not isinstance(tho.get("cat_tu_dong"), dict):
        kh2.pop("cat_tu_dong", None)
    am_t = tho.get("am") if isinstance(tho.get("am"), dict) else {}
    if not am_t.get("nhac"):
        (kh2.get("am") or {}).pop("nhac", None)
    return kh2


def tao(kh, ghi_chu="", tho=None):
    kh = _chi_ai(kh, tho)
    pc = kh.get("phong_cach") or {}
    lop = [l for l in (kh.get("lop") or []) if isinstance(l, dict)]
    chu = [l for l in lop if l.get("kieu") == "chu" and not str(l.get("id", "")).startswith("pd")]
    tieu_de = [l for l in chu if (l.get("kieu_dang") or {}).get("font") in ("tieu_de", (pc.get("font") or {}).get("tieu_de"))] or chu[:1]
    nhan = [l for l in chu if l not in tieu_de] or chu
    the = [l for l in lop if l.get("kieu") == "the"]
    mau_lop = [l for l in lop if l.get("kieu") == "mau"]
    pd = kh.get("phu_de") or {}
    dur = float(kh.get("dur") or 0) or max([float(l.get("t1", 0)) for l in lop] + [1])
    spec = {"phien_ban": 1, "nguon": "video_dau_tien",
            "palette": {k: v for k, v in (("nhan", pc.get("mau_nhan")), ("sang", pc.get("mau_sang")), ("toi", pc.get("mau_toi"))) if v},
            "type_scale": {}, "layout": {"anchors": []}, "motion_vocab": {}, "graphics_vocab": {}, "sfx_vocab": {}, "rhythm_rules": {},
            "dau_an_khong_chep": [], "ghi_chu": ""}
    if pc.get("mau_nhan2"):
        spec["palette"]["nhan2"] = pc["mau_nhan2"]
    for vai, ds in (("tieu_de", tieu_de), ("nhan", nhan)):
        c = _co_chu(ds)
        if c:
            spec["type_scale"][vai] = c
    if pd.get("kieu_dang"):
        spec["type_scale"]["phu_de"] = _co_chu([{"kieu_dang": pd["kieu_dang"]}])
    fonts = {os.path.basename(str(v)) for v in (pc.get("font") or {}).values() if v}
    spec["type_scale"]["so_font_khac_nhau"] = max(1, min(5, len(fonts) or 1))
    for vai, ds in (("tieu_de", tieu_de), ("nhan", nhan), ("the", the)):
        a = _anchor(ds, vai)
        if a:
            spec["layout"]["anchors"].append(a)
    if pd.get("vi_tri"):
        a = _anchor([{"vi_tri": pd["vi_tri"]}], "phu_de")
        if a:
            spec["layout"]["anchors"].append(a)
    rm = _pho_bien([(l.get("kieu_dang") or {}).get("rong_max") for l in chu])
    if rm:
        spec["layout"]["rong_max_chu"] = min(1, max(0.2, float(rm)))
    vao, ra = _dong_tac(chu + the, "vao"), _dong_tac(chu + the, "ra")
    if vao:
        spec["motion_vocab"]["vao"] = vao
    if ra:
        spec["motion_vocab"]["ra"] = ra
    tach = _pho_bien([(l.get("anim") or {}).get("tach") for l in chu])
    if tach in ("none", "tu", "ky_tu"):
        spec["motion_vocab"]["tach"] = tach
    dai_tb = sum(x["dai"] for x in vao) / len(vao) if vao else 0.3
    spec["motion_vocab"]["nhip_dong"] = "rat_nhanh" if dai_tb < 0.15 else "nhanh" if dai_tb < 0.3 else "vua" if dai_tb < 0.6 else "cham"
    # CHỈ ghi những gì video đầu ĐÃ DÙNG (bản sắc = màu/font/nhịp/cách chữ hiện). KHÔNG ghi điều vắng mặt ("không hình", "không nền mới",
    # "không icon"): một video không dùng ≠ kênh cấm — ghi vào là khoá chết công cụ của mọi video sau.
    if the:
        kd = the[0].get("kieu_dang") or {}
        gv_the = {"hinh": kd.get("hinh") if kd.get("hinh") in ("pill", "rect", "circle") else "pill"}
        if any((l.get("noi_dung") or {}).get("icon") for l in the):
            gv_the["co_icon"] = True
        spec["graphics_vocab"]["the"] = gv_the
    if chu:
        kd = [l.get("kieu_dang") or {} for l in chu]
        gv_chu = {k: True for k, co in (("vien", any(x.get("vien") for x in kd)), ("bong", any(x.get("bong") for x in kd)),
                                        ("nen_khoi", any(x.get("nen") for x in kd)), ("gradient", any(x.get("gradient") for x in kd))) if co}
        if _pho_bien([bool(k.get("hoa")) for k in kd], False):
            gv_chu["hoa"] = True
        if gv_chu:
            spec["graphics_vocab"]["chu"] = gv_chu
    n_hinh = sum(1 for l in lop if l.get("kieu") in ("hinh", "video"))
    if n_hinh:
        spec["graphics_vocab"]["hinh_minh_hoa"] = "it" if n_hinh / max(1, dur / 60) <= 3 else "nhieu"
    nm = kh.get("nen_moi") or []
    if nm and (nm[0].get("nen") or {}).get("kieu") in ("mau", "gradient", "anh", "video", "mo"):
        spec["graphics_vocab"]["nen_moi"] = (nm[0].get("nen") or {}).get("kieu")
    if not spec["graphics_vocab"]:
        spec.pop("graphics_vocab")
    am = kh.get("am") or {}
    sfx = am.get("sfx") or []
    spec["sfx_vocab"] = {"dung": bool(sfx)}                 # không khoá tệp nhạc cụ thể: mỗi video chọn nhạc theo nội dung
    cam = kh.get("camera") or []
    if cam:
        spec["camera_vocab"] = {"dung": True, "tan_suat_giay": round(dur / len(cam), 1)}
    rr = {}
    if pd.get("che_do") in ("cum", "tu", "tat"):
        rr["phu_de"] = pd["che_do"]
    if pd.get("toi_da_chu"):
        rr["phu_de_toi_da_chu"] = max(4, int(pd["toi_da_chu"]))
    if chu:
        rr["hook_giay"] = round(min(float(l.get("t0", 0)) for l in chu), 1)
    spec["rhythm_rules"] = rr
    bia = kh.get("bia") or {}
    tk = bia.get("thiet_ke") or {}
    if tk:
        spec["bia"] = {"so_chu": sum(len(str(c.get("text", "")).split()) for c in (tk.get("chu") or []) if isinstance(c, dict)),
                       "nguoi": tk.get("nguoi") is not None,
                       "nen": (tk.get("nen") or {}).get("kieu") if (tk.get("nen") or {}).get("kieu") in ("mau", "gradient", "khung_mo", "anh") else "khung_mo"}
    nh = am.get("nhac") or {}
    spec["am_nhac"] = {"co": bool(nh) and str(nh.get("muc") or "") != "khong", "muc": str(nh.get("muc") or ("vua" if nh else "khong"))}
    ctd = kh.get("cat_tu_dong") or {}
    if ctd.get("nhip") in ("nhanh", "vua", "cham"):
        spec["cat"] = {"nhip": ctd["nhip"]}
    spec["ghi_chu"] = (ghi_chu or "Bản sắc NHÁP máy rút từ video đầu tiên của kênh: màu, font, nhịp, cách chữ hiện, phụ đề — giữ nhất quán. "
                       "KHÔNG giới hạn loại công cụ: mỗi video tự chọn mẫu đồ hoạ, hình, nền mới, camera, chuyển cảnh theo nội dung. "
                       "Người dùng chưa duyệt; sửa bằng góp ý (gop-y) hoặc bài học từ video mẫu.")
    spec["_nguon"] = {"loai": "video_dau_tien", "luc": time.strftime("%Y-%m-%d %H:%M")}
    try:
        from hoc import kiem_spec
        loi = kiem_spec.kiem(spec)
        if loi:
            spec["_loi_schema"] = loi[:10]
    except Exception:
        pass
    return spec


def tom_tat(spec):
    """một dòng cho AI/người dùng: màu, font, nhịp, nhạc, cắt"""
    p = spec.get("palette") or {}
    mv = spec.get("motion_vocab") or {}
    vao = (mv.get("vao") or [{}])[0].get("kieu", "?")
    return (f"màu nhấn {p.get('nhan')}" + (f"/{p.get('nhan2')}" if p.get("nhan2") else "") + f" · chữ vào `{vao}` nhịp {mv.get('nhip_dong', '?')}"
            f" · nhạc {((spec.get('am_nhac') or {}).get('muc') or 'không')} · cắt {((spec.get('cat') or {}).get('nhip') or 'vua')}"
            f" · phụ đề {((spec.get('rhythm_rules') or {}).get('phu_de') or 'cum')}")


if __name__ == "__main__":
    du_an = sys.argv[1]
    kh = chung.doc_json(os.path.join(du_an, "ke-hoach.json")) or {}
    sp = tao(kh)
    if "--ghi" in sys.argv:
        hs = sys.argv[sys.argv.index("--ghi") + 1]
        p = os.path.join(chung.duong("ho_so"), hs, "style-spec.json")
        chung.ghi_json(p, sp); print("ghi", p)
    print(json.dumps(sp, ensure_ascii=False, indent=1)[:3000])
    print(tom_tat(sp))
