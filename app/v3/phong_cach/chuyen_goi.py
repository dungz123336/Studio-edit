# -*- coding: utf-8 -*-
"""QUYẾT ĐỊNH KÊNH cho 20 gói phong cách nhanh (phong_cach/<id>.json["quyet_dinh"]) — sinh từ chính Style Spec của gói.
Phong cách nhanh là lựa chọn CỦA NGƯỜI DÙNG (gõ /lệnh) nên gói được mang gu: mọi số nằm TRONG TỪNG GÓI (spec + quyet_dinh của gói),
mã này chỉ ánh xạ spec → khuôn quyết định (ai/hop_dong.KHUON_QUYET_DINH, đúng trường engine đọc), không giữ số riêng.
(Bước chuyển từ gói v2 đã làm xong ở 1.2.19 — các tệp JSON là nguồn sự thật; mã chuyển v2 đã gỡ.)

    python v3/phong_cach/chuyen_goi.py            # sinh quyet_dinh cho gói chưa có (--ep: ghi đè mọi gói), kiểm khuôn
    python v3/phong_cach/chuyen_goi.py --kiem     # chỉ kiểm
"""
import os, sys, json, glob, copy

DAY = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.dirname(DAY)
if V3 not in sys.path:
    sys.path.insert(0, V3)


def _dong_tac(mv, khoa, chuan):
    ds = [x for x in (mv.get(khoa) or []) if isinstance(x, dict) and x.get("kieu")]
    if not ds:
        return copy.deepcopy(chuan)
    x = max(ds, key=lambda d: float(d.get("tan_suat", 0) or 0))
    k = {"word_by_word": "pop", "mask_reveal": "wipe", "doi_ky_tu": "typewriter"}.get(x["kieu"], x["kieu"])
    if k not in ("fade", "slide", "pop", "blur", "wipe", "typewriter", "flip", "tilt", "none"):
        k = chuan["kieu"]
    e = x.get("ease") if x.get("ease") in ("linear", "in", "out", "in_out", "back", "spring", "expo") else chuan["ease"]
    return {"kieu": k, "dai": float(x.get("dai", chuan["dai"]) or 0), "ease": e}


def _anchor(spec, vai, chuan):
    ds = [a for a in ((spec.get("layout") or {}).get("anchors") or []) if a.get("vai") == vai]
    if not ds:
        return dict(chuan)
    a = max(ds, key=lambda d: float(d.get("tan_suat", 0) or 0))
    return {"anchor": a.get("anchor") or chuan["anchor"], "x": float(a.get("x", chuan["x"])), "y": float(a.get("y", chuan["y"])),
            "so_voi": a.get("so_voi") if a.get("so_voi") in ("khung", "mat", "duoi_cam", "tren_dau") else "khung"}


def _vien(co, w, toi):
    return [{"w": w, "mau": toi}] if co else None


def quyet_dinh_tu_spec(spec, mau):
    """Style Spec của gói + mẫu chuẩn (quyet-dinh.mau.json làm khung giá trị cho trường spec không mô tả) → quyet_dinh đủ khuôn.
    Mọi số gu lấy từ spec của gói; mẫu chỉ bù trường spec không có (cách nhóm, hộp mặc định, LUFS, nhịp phụ đề…)."""
    q = copy.deepcopy(mau)
    pal = spec.get("palette") or {}
    ts = spec.get("type_scale") or {}
    mv = spec.get("motion_vocab") or {}
    gv = spec.get("graphics_vocab") or {}
    rr = spec.get("rhythm_rules") or {}
    am = spec.get("am_nhac") or {}
    sfx = spec.get("sfx_vocab") or {}
    bia = spec.get("bia") or {}
    q["phien"] = 1
    q["ly_do"] = (spec.get("ghi_chu") or "Gói phong cách nhanh")[:400]
    q["font"] = {"tieu_de": (ts.get("tieu_de") or {}).get("font") or (ts.get("nhan") or {}).get("font") or mau["font"]["tieu_de"],
                 "phu_de": (ts.get("phu_de") or {}).get("font") or mau["font"]["phu_de"],
                 "nhan": (ts.get("nhan") or {}).get("font") or (ts.get("tieu_de") or {}).get("font") or mau["font"]["nhan"]}
    if pal.get("nhan"):
        q["bang_mau"] = {"nhan": pal["nhan"], "nhan2": pal.get("nhan2") or pal.get("sang") or mau["bang_mau"]["nhan2"],
                         "sang": pal.get("sang") or mau["bang_mau"]["sang"], "toi": pal.get("toi") or mau["bang_mau"]["toi"]}
    toi, sang, nhan = q["bang_mau"]["toi"], q["bang_mau"]["sang"], q["bang_mau"]["nhan"]
    chu_gv = gv.get("chu") or {}
    vai_chu = ts.get("nhan") or ts.get("tieu_de") or {}
    q["chu"].update({k: v for k, v in (("co", vai_chu.get("co")), ("dam", vai_chu.get("dam")), ("hoa", vai_chu.get("hoa")),
                                        ("gian", vai_chu.get("gian")), ("dong", vai_chu.get("dong"))) if v is not None})
    q["chu"]["mau"] = vai_chu.get("mau") or sang
    q["chu"]["font"] = "nhan" if ts.get("nhan") else "tieu_de"
    q["chu"]["rong_max"] = float((spec.get("layout") or {}).get("rong_max_chu") or mau["chu"]["rong_max"])
    co_vien = vai_chu.get("vien") if vai_chu.get("vien") is not None else bool(chu_gv.get("vien"))
    co_bong = vai_chu.get("bong") if vai_chu.get("bong") is not None else bool(chu_gv.get("bong"))
    q["chu"]["vien"] = _vien(co_vien, mau["chu"]["vien"][0]["w"] if mau["chu"]["vien"] else 4, toi)
    q["chu"]["bong"] = copy.deepcopy(mau["chu"]["bong"]) if co_bong else None
    q["chu"]["nen"] = ({"mau": vai_chu.get("nen_mau") or (toi + "CC" if len(toi) == 7 else toi), "dem": [28, 16], "bo": 18}
                       if (chu_gv.get("nen_khoi") or vai_chu.get("nen_mau")) else None)
    q["chu"]["gradient"] = ({"mau": [nhan, q["bang_mau"]["nhan2"]], "goc": 90} if chu_gv.get("gradient") else None)
    q["khoi"]["rong_max"] = q["chu"]["rong_max"]
    the = gv.get("the") or {}
    q["the"]["hinh"] = the.get("hinh") if the.get("hinh") in ("pill", "rect", "circle") else mau["the"]["hinh"]
    q["the"]["mau"] = (toi + ("AA" if the.get("nen_mo") else "DD")) if len(toi) == 7 else toi
    if the.get("bo") is not None:
        q["the"]["bo"] = min(300.0, float(the["bo"]))                 # spec cũ ghi 999 = "bo tròn hết" → kẹp theo miền khuôn (0..300 px)
    cv = the.get("co_vien")
    q["the"]["vien"] = ({"w": float(cv) if isinstance(cv, (int, float)) and not isinstance(cv, bool) and cv > 0 else 2.0, "mau": nhan} if cv else None)
    q["the"]["chu"] = {"co": float((ts.get("nhan") or {}).get("co") or mau["the"]["chu"]["co"]) * 0.5 if (ts.get("nhan") or {}).get("co") else mau["the"]["chu"]["co"],
                       "dam": int((ts.get("nhan") or {}).get("dam") or mau["the"]["chu"]["dam"]), "mau": sang, "font": "nhan", "vien": None, "bong": None, "gradient": None}
    q["duong"]["mau"] = nhan
    pd = ts.get("phu_de") or {}
    q["phu_de"]["che_do"] = rr.get("phu_de") if rr.get("phu_de") in ("cum", "tu", "tat") else "cum"
    if rr.get("phu_de_toi_da_chu"):
        n = int(rr["phu_de_toi_da_chu"])
        q["phu_de"]["toi_da_chu"] = max(8, n if n > 8 else n * 4)      # spec cũ ghi theo TỪ (≤ 8) → ký tự
    if rr.get("karaoke") is not None:
        q["phu_de"]["karaoke"] = bool(rr["karaoke"])
    if rr.get("phu_de_hien") in ("noi", "dan"):
        q["phu_de"]["hien"] = rr["phu_de_hien"]
    q["phu_de"]["mau_noi"] = nhan
    kd = q["phu_de"]["kieu_dang"]
    kd.update({k: v for k, v in (("co", pd.get("co")), ("dam", pd.get("dam")), ("hoa", pd.get("hoa"))) if v is not None})
    kd["mau"] = pd.get("mau") or sang
    kd["font"] = "phu_de"
    kd["vien"] = None if pd.get("vien") is False else [{"w": v["w"], "mau": toi} for v in (mau["phu_de"]["kieu_dang"]["vien"] or [])]
    kd["nen"] = {"mau": pd["nen_mau"], "dem": [22, 12], "bo": 14} if pd.get("nen_mau") else None
    q["phu_de"]["vi_tri"] = _anchor(spec, "phu_de", mau["phu_de"]["vi_tri"])
    q["anim"]["vao"] = _dong_tac(mv, "vao", mau["anim"]["vao"])
    q["anim"]["ra"] = _dong_tac(mv, "ra", mau["anim"]["ra"])
    if mv.get("so_le") is not None:
        q["anim"]["so_le"] = float(mv["so_le"])
    vt_nhan = _anchor(spec, "nhan", {"anchor": mau["vi_tri"].get("anchor", "mc"), "x": 0.5, "y": 0.5, "so_voi": mau["vi_tri"].get("so_voi", "khung")})
    q["vi_tri"]["anchor"] = vt_nhan["anchor"]
    q["vi_tri"]["so_voi"] = vt_nhan["so_voi"]
    if am.get("co") is False or am.get("muc") == "khong":
        q["am"]["nhac"]["db"] = -40.0
    elif sfx.get("nhac_db") is not None:
        q["am"]["nhac"]["db"] = max(-40.0, min(-4.0, float(sfx["nhac_db"])))
    elif am.get("muc") in ("nhe", "vua", "noi"):
        q["am"]["nhac"]["db"] = {"nhe": -24.0, "vua": -18.0, "noi": -12.0}[am["muc"]]
    q["nen_moi"]["mau"] = toi
    c_ = spec.get("cat") or {}
    if c_.get("nhip") in ("nhanh", "vua", "cham"):
        q["cat"] = {"nhip": c_["nhip"]}
    if bia:
        q["bia"]["nen"]["kieu"] = bia.get("nen") if bia.get("nen") in ("mau", "gradient", "khung_mo", "anh", "kho") else q["bia"]["nen"]["kieu"]
        td = ts.get("tieu_de") or {}
        if td.get("co"):
            q["bia"]["chu"]["co"] = float(td["co"])
        if td.get("dam"):
            q["bia"]["chu"]["dam"] = int(td["dam"])
        if td.get("hoa") is not None:
            q["bia"]["chu"]["hoa"] = bool(td["hoa"])
    q["bia"]["chu"]["mau"] = sang
    q["bia"]["chu"]["font"] = "tieu_de"
    q["bia"]["chu"]["vien"] = [{"w": v["w"], "mau": toi} for v in (mau["bia"]["chu"]["vien"] or [])]
    for k in list(q.keys()):
        if k.startswith("_"):
            q.pop(k)
    return q


def main(ep=False, chi_kiem=False):
    from ai import hop_dong as H
    mau = H.mau_quyet_dinh()
    so, loi = 0, 0
    for p in sorted(glob.glob(os.path.join(DAY, "*.json"))):
        with open(p, encoding="utf-8") as f:
            g = json.load(f)
        if not g.get("id") or not g.get("spec"):
            continue
        if not chi_kiem and (ep or not isinstance(g.get("quyet_dinh"), dict)):
            g["quyet_dinh"] = quyet_dinh_tu_spec(g["spec"], mau)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(g, f, ensure_ascii=False, indent=1)
        l = H.kiem_quyet_dinh(g.get("quyet_dinh") or {})
        if l:
            loi += 1
            print("✗", g["id"], [f"{x['duong']}: {x['goi_y']}" for x in l][:6])
        so += 1
    print(f"{so} gói · quyet_dinh ({loi} lỗi khuôn)")
    return loi


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("--ep", action="store_true"); ap.add_argument("--kiem", action="store_true")
    a = ap.parse_args()
    sys.exit(1 if main(ep=a.ep, chi_kiem=a.kiem) else 0)
