# -*- coding: utf-8 -*-
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
"""ÁP STYLE SPEC (bản sắc đã học) vào công thức — cơ chế để "edit theo phong cách đã học" là VIỆC CỦA MÁY, không trông vào AI nhớ.
1) ap_vao_cong_thuc(ct, spec): điền những trường AI BỎ TRỐNG trong cong-thuc.json từ spec theo vai (tieu_de/nhan/the/phu_de):
   kiểu dáng chữ (cỡ, đậm, HOA, viền/bóng/nền khối), vị trí (anchor/x/y/so_voi), anim vào/ra/tách, phụ đề (chế độ, cỡ, vị trí), nhạc, cắt.
   AI ghi gì thì giữ nguyên — spec chỉ là mặc định của KÊNH. 1.2.21: CHỈ ÁNH XẠ trường spec → trường công thức (số đo của mẫu);
   không có hệ số/số cứng của máy (viền 6, bóng, nền, chấm gu font): chỗ spec chỉ nói "có" (vien/bong true) thì lấy từ quyết định
   kênh (qd) nếu được truyền, không thì để trống → cong_thuc điền theo quyết định kênh / báo thieu_truong.
2) cong_thuc_tu_spec(spec, du_an, ...): sinh một công thức THỬ hoàn toàn từ spec + lời của clip thử (không AI) — để vòng đo
   "học → dựng lại → so với mẫu" chạy tự động (kiem_thu/hoc_vong.py).
"""
import os, sys, json, re, copy

V3 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if V3 not in sys.path:
    sys.path.insert(0, V3)
import chung

VAI_CHU = ("tieu_de", "nhan", "phu_de", "the", "hinh", "khac")


def _vai_lop(l, pc_font):
    """vai của một lớp chữ/thẻ: the → "the"; chu có font tieu_de hoặc id gợi hook/tieu-de → "tieu_de"; còn lại "nhan" """
    k = l.get("kieu")
    if k == "the":
        return "the"
    if k == "khoi":
        return "tieu_de"
    if k != "chu":
        return None
    f = str((l.get("kieu_dang") or {}).get("font") or "")
    if f == "tieu_de" or (pc_font and f and f == pc_font.get("tieu_de")):
        return "tieu_de"
    if re.search(r"hook|tieu[-_]?de|title|chot|cta|ket", str(l.get("id") or ""), re.I):
        return "tieu_de"
    return "nhan"


def _dong_tac(mv, khoa):
    ds = [x for x in (mv.get(khoa) or []) if isinstance(x, dict) and x.get("kieu")]
    if not ds:
        return None
    x = max(ds, key=lambda d: float(d.get("tan_suat", 0) or 0))
    ra = {"kieu": x["kieu"]}
    if x.get("kieu") in ("word_by_word",):
        ra["kieu"] = "pop"
    elif x.get("kieu") == "mask_reveal":
        ra["kieu"] = "wipe"
    elif x.get("kieu") == "doi_ky_tu":
        ra["kieu"] = "typewriter"
    if x.get("dai") is not None:
        ra["dai"] = float(x["dai"])
    if x.get("ease"):
        ra["ease"] = x["ease"]
    return ra


def _anim_spec(mv):
    a = {}
    v, r = _dong_tac(mv, "vao"), _dong_tac(mv, "ra")
    if v:
        a["vao"] = v
    if r:
        a["ra"] = r
    if mv.get("tach") in ("tu", "ky_tu"):
        a["tach"] = mv["tach"]
        if mv.get("so_le") is not None:
            a["so_le"] = float(mv["so_le"])
    top = max((x for x in (mv.get("vao") or []) if isinstance(x, dict)), key=lambda d: float(d.get("tan_suat", 0) or 0), default=None)
    if top and top.get("kieu") == "word_by_word":
        a["tach"] = "tu"
    return a


def _anchor(spec, vai):
    """neo theo vai, lấy anchor có tan_suat cao nhất. so_voi tren_dau/duoi_cam/mat + khoang_theo_cao_mat → y tính theo CHIỀU CAO MẶT
    (vi_tri.theo_mat=True, engine nhân với h mặt) — video mới mặt to/nhỏ khác mẫu vẫn giữ đúng khoảng cách tương đối."""
    ds = [a for a in ((spec.get("layout") or {}).get("anchors") or []) if a.get("vai") == vai]
    if not ds:
        return None
    a = max(ds, key=lambda d: float(d.get("tan_suat", 0) or 0))
    sv = a.get("so_voi") or "khung"
    vt = {"anchor": a.get("anchor", "tc"), "x": float(a.get("x", 0.5)), "y": float(a.get("y", 0.1))}
    if sv in ("tren_dau", "duoi_cam") and a.get("khoang_theo_cao_mat") is not None:
        cot = (vt["anchor"] or "tc")[-1]
        vt.update({"so_voi": sv, "y": max(0.0, float(a["khoang_theo_cao_mat"])), "theo_mat": True,
                   "anchor": ("b" if sv == "tren_dau" else "t") + (cot if cot in "lcr" else "c")})   # 1.2.20: neo đúng mép máy đo (trước lệch nửa chữ)
    elif sv == "mat" and a.get("khoang_theo_cao_mat") is not None:
        vt.update({"so_voi": "mat", "x": float(a.get("lech_x_theo_rong_mat", 0) or 0), "y": float(a["khoang_theo_cao_mat"]), "theo_mat": True})
    else:
        vt["so_voi"] = "khung"
    return vt


def _kieu_dang_chu(spec, vai, qd=None):
    """type_scale[vai] + graphics_vocab.chu (số ĐO của mẫu) → kieu_dang. vien/bong chỉ là cờ có/không: có → lấy mảng của quyết định kênh
    (qd.chu.vien/bong) nếu có, không → để cong_thuc điền; không → [] (cố ý không viền/bóng)."""
    ts = (spec.get("type_scale") or {}).get(vai) or {}
    gv = (spec.get("graphics_vocab") or {}).get("chu") or {}
    pal = spec.get("palette") or {}
    qchu = (qd or {}).get("chu") if isinstance(qd, dict) else None
    kd = {}
    if ts.get("co"):
        kd["co"] = float(ts["co"])
    if ts.get("dam"):
        kd["dam"] = int(ts["dam"])
    if ts.get("hoa") is not None:
        kd["hoa"] = bool(ts["hoa"])
    if ts.get("dong"):
        kd["dong"] = float(ts["dong"])
    if ts.get("gian") is not None:
        kd["gian"] = float(ts["gian"])
    co_vien = ts.get("vien") if ts.get("vien") is not None else (True if gv.get("vien") else None)
    co_bong = ts.get("bong") if ts.get("bong") is not None else (True if gv.get("bong") else None)
    if co_vien is False:
        kd["vien"] = []
    elif co_vien and isinstance(qchu, dict) and isinstance(qchu.get("vien"), list) and qchu["vien"]:
        kd["vien"] = copy.deepcopy(qchu["vien"])
    if co_bong is False:
        kd["bong"] = []
    elif co_bong and isinstance(qchu, dict) and isinstance(qchu.get("bong"), list) and qchu["bong"]:
        kd["bong"] = copy.deepcopy(qchu["bong"])
    qnen = qchu.get("nen") if isinstance(qchu, dict) else None
    if ts.get("nen_mau"):
        kd["nen"] = {"mau": ts["nen_mau"]}                      # dem/bo: cong_thuc lấy ở quyết định chu.nen (null → the.dem/the.bo)
    elif gv.get("nen_khoi") and isinstance(qnen, dict) and qnen.get("mau"):
        kd["nen"] = copy.deepcopy(qnen)                         # spec chỉ nói "có nền" → nền của quyết định kênh; kênh chu.nen = null → để trống
    rm = (spec.get("layout") or {}).get("rong_max_chu")
    if rm:
        kd["rong_max"] = float(rm)
    if ts.get("mau"):
        kd["mau"] = ts["mau"]
    kd["font"] = "tieu_de" if vai == "tieu_de" else "nhan"
    return kd


def _kieu_dang_the(spec, qd=None):
    """graphics_vocab.the (số đo của mẫu) → kieu_dang thẻ; màu nền thẻ = pal.toi đo được (độ trong nen_mo không có số → để quyết định kênh)"""
    gt = (spec.get("graphics_vocab") or {}).get("the") or {}
    pal = spec.get("palette") or {}
    kd = {}
    if gt.get("hinh") in ("pill", "rect", "circle"):
        kd["hinh"] = gt["hinh"]
    if gt.get("bo") is not None:
        kd["bo"] = float(gt["bo"])
    cv = gt.get("co_vien")
    q_vien = ((qd or {}).get("the") or {}).get("vien") if isinstance(qd, dict) else None
    mau_vien = (q_vien.get("mau") if isinstance(q_vien, dict) else None) or pal.get("nhan")     # R2: màu viền thẻ = quyết định the.vien.mau → màu nhấn đo được
    if isinstance(cv, (int, float)) and not isinstance(cv, bool) and cv > 0 and mau_vien:
        kd["vien"] = {"w": float(cv), "mau": mau_vien}
    elif cv is False or (isinstance(cv, (int, float)) and not isinstance(cv, bool) and cv == 0):
        kd["vien"] = None
    if pal.get("toi") and not gt.get("nen_mo"):
        kd["mau"] = pal["toi"]
    return kd


NHOM_FONT_NGHIA = {"sans_dam": "sans đậm hiện đại", "sans_thuong": "sans thường dễ đọc", "serif": "serif có chân thanh lịch",
                   "display": "display tiêu đề ấn tượng", "viet_tay": "viết tay script", "mono": "monospace mã"}
_FONT_CACHE = {}


def _tim_font(nghia):
    """mô tả font nhìn thấy (font_goi_y của spec) → id font đủ dấu đầu bảng của kho/tim (máy không chấm gu script/nghiêng/đậm); None nếu không có"""
    if not nghia:
        return None
    if nghia in _FONT_CACHE:
        return _FONT_CACHE[nghia]
    ra = None
    try:
        sys.path.insert(0, os.path.join(V3, "kho"))
        import tim as _tim
        ds = _tim.tim("font", nghia, 20) or []
        for m in ds:
            if m.get("du_dau") is not False and m.get("id"):
                ra = m["id"]; break
        if ra is None and ds:
            ra = ds[0].get("id")
    except Exception:
        ra = None
    _FONT_CACHE[nghia] = ra
    return ra


def _font_theo_spec(spec, vai):
    """font cho vai từ spec: co_chu.font_goi_y (AI nhìn) → tra kho; không có → nhom_font[0] → tra kho; không có → None"""
    ts = (spec.get("type_scale") or {})
    goi_y = (ts.get(vai) or {}).get("font_goi_y")
    if goi_y:
        f = _tim_font(str(goi_y))
        if f:
            return f
    nhom = ts.get("nhom_font") or []
    if nhom:
        f = _tim_font(NHOM_FONT_NGHIA.get(nhom[0], str(nhom[0])))
        if f:
            return f
    return None


def _tron_thieu(dich, nguon):
    """điền vào `dich` những khoá `nguon` có mà dich chưa có (không ghi đè)"""
    for k, v in (nguon or {}).items():
        if k not in dich:                   # AI ghi null/[]/{} = CỐ Ý bỏ (vd phụ đề không nền) → tôn trọng, không điền theo spec
            dich[k] = copy.deepcopy(v)
    return dich


def ap_vao_cong_thuc(ct, spec, ghi=None, qd=None):
    """điền MẶC ĐỊNH KÊNH từ spec vào công thức thô (AI ghi gì giữ nấy) → số trường đã điền. qd = quyết định kênh (chỉ để lấy mảng viền/bóng khi spec nói "có")"""
    if not isinstance(ct, dict) or not isinstance(spec, dict):
        return 0
    n = 0
    pc = ct.setdefault("phong_cach", {}) if isinstance(ct.get("phong_cach"), dict) else ct.setdefault("phong_cach", {})
    pal = spec.get("palette") or {}
    for k_ct, k_sp in (("mau_nhan", "nhan"), ("mau_nhan2", "nhan2"), ("mau_sang", "sang"), ("mau_toi", "toi")):
        if not pc.get(k_ct) and pal.get(k_sp):
            pc[k_ct] = pal[k_sp]; n += 1
    pf = pc.setdefault("font", {}) if isinstance(pc.get("font"), dict) else pc.setdefault("font", {})
    for vai_f in ("tieu_de", "nhan", "phu_de"):
        if not pf.get(vai_f):
            f_ = _font_theo_spec(spec, vai_f)
            if f_:
                pf[vai_f] = f_; n += 1
    mv = spec.get("motion_vocab") or {}
    anim_sp = _anim_spec(mv)
    pc_font = pc.get("font") if isinstance(pc.get("font"), dict) else {}
    for l in ct.get("lop") or []:
        if not isinstance(l, dict):
            continue
        vai = _vai_lop(l, pc_font)
        if not vai:
            continue
        if vai in ("tieu_de", "nhan") and l.get("kieu") != "khoi":      # khoi: AI đã ghi kiểu từng dòng — không điền mặc định khối (tránh tràn màu/gradient)
            kd = l.setdefault("kieu_dang", {}) if isinstance(l.get("kieu_dang"), dict) else l.setdefault("kieu_dang", {})
            truoc = len(kd); _tron_thieu(kd, _kieu_dang_chu(spec, vai, qd)); n += len(kd) - truoc
        elif vai == "the":
            kd = l.setdefault("kieu_dang", {}) if isinstance(l.get("kieu_dang"), dict) else l.setdefault("kieu_dang", {})
            truoc = len(kd); _tron_thieu(kd, _kieu_dang_the(spec, qd)); n += len(kd) - truoc
        if not isinstance(l.get("vi_tri"), dict) or not l["vi_tri"].get("anchor"):
            a = _anchor(spec, vai) or _anchor(spec, "nhan" if vai == "the" else vai)
            if a and not (l.get("vi_tri") or {}).get("nhom"):
                vt = l.setdefault("vi_tri", {}) if isinstance(l.get("vi_tri"), dict) else l.setdefault("vi_tri", {})
                truoc = len(vt); _tron_thieu(vt, a); n += len(vt) - truoc
        if anim_sp and not l.get("anim"):
            l["anim"] = copy.deepcopy(anim_sp); n += 1
    # phụ đề
    rr = spec.get("rhythm_rules") or {}
    pd = ct.setdefault("phu_de", {}) if isinstance(ct.get("phu_de"), dict) else ct.setdefault("phu_de", {})
    if rr.get("phu_de") in ("cum", "tu", "tat") and not pd.get("che_do"):
        if rr["phu_de"] == "tu":                           # mẫu hiện TỪNG TỪ theo lời (từ hiện rồi ở lại) → cụm + hiện dần
            pd["che_do"] = "cum"; pd.setdefault("hien", "dan")
        else:
            pd["che_do"] = rr["phu_de"]
        n += 1
    if rr.get("karaoke") is not None and pd.get("karaoke") is None:
        pd["karaoke"] = bool(rr["karaoke"]); n += 1
    if rr.get("phu_de_hien") in ("noi", "dan", "cum") and not pd.get("hien"):
        pd["hien"] = "dan" if rr["phu_de_hien"] == "dan" else "noi"
        if rr["phu_de_hien"] == "cum" and pd.get("karaoke") is None:
            pd["karaoke"] = False
        n += 1
    if rr.get("phu_de_toi_da_chu") and not pd.get("toi_da_chu"):
        pd["toi_da_chu"] = max(10, int(rr["phu_de_toi_da_chu"])) if pd.get("hien") == "dan" else int(rr["phu_de_toi_da_chu"]); n += 1
    ts_pd = (spec.get("type_scale") or {}).get("phu_de") or {}
    if ts_pd:
        kd = pd.setdefault("kieu_dang", {}) if isinstance(pd.get("kieu_dang"), dict) else pd.setdefault("kieu_dang", {})
        truoc = len(kd)
        them = {k: v for k, v in (("co", ts_pd.get("co")), ("dam", ts_pd.get("dam")), ("hoa", ts_pd.get("hoa")), ("mau", ts_pd.get("mau"))) if v is not None}
        qpd = ((qd or {}).get("phu_de") or {}).get("kieu_dang") if isinstance(qd, dict) else None
        if ts_pd.get("vien") is False:
            them["vien"] = []
        elif ts_pd.get("vien") is True and isinstance(qpd, dict) and qpd.get("vien"):
            them["vien"] = copy.deepcopy(qpd["vien"])            # spec chỉ nói "có viền" → bề dày/màu theo quyết định kênh
        if ts_pd.get("bong") is False:
            them["bong"] = []
        if ts_pd.get("nen_mau"):
            them["nen"] = {"mau": ts_pd["nen_mau"]}               # dem/bo theo quyết định phu_de.kieu_dang.nen
        _tron_thieu(kd, them)
        n += len(kd) - truoc
    a_pd = _anchor(spec, "phu_de")
    if a_pd and not (pd.get("vi_tri") or {}).get("anchor"):
        pd["vi_tri"] = a_pd; n += 1
    # nhạc, cắt
    am_sp = spec.get("am_nhac") or {}
    am = ct.setdefault("am", {}) if isinstance(ct.get("am"), dict) else ct.setdefault("am", {})
    if am_sp and not am.get("nhac"):
        if am_sp.get("co") is False or am_sp.get("muc") == "khong":
            am["nhac"] = {"muc": "khong"}; n += 1
        else:
            nh = {"muc": am_sp["muc"]} if am_sp.get("muc") else {}     # R2: spec không ghi mức → để trống (cong_thuc lấy quyết định am.nhac.db), không mặc định "nhe"
            if am_sp.get("nghia") or (spec.get("sfx_vocab") or {}).get("nhac"):
                nh["id"] = am_sp.get("nghia") or (spec.get("sfx_vocab") or {}).get("nhac")
            if nh.get("id"):
                am["nhac"] = nh; n += 1
    elif isinstance(am.get("nhac"), dict) and not am["nhac"].get("muc") and am["nhac"].get("db") is None and am_sp.get("muc"):
        am["nhac"]["muc"] = am_sp["muc"]; n += 1
    c_sp = spec.get("cat") or {}
    if c_sp.get("nhip") and not ct.get("cat") and not (ct.get("cat_tu_dong") or {}).get("nhip"):
        ct["cat_tu_dong"] = {"nhip": c_sp["nhip"]}; n += 1
    if ghi is not None and n:
        ghi.append({"lop": "phong_cach", "sua": "ban_sac", "mo_ta": f"điền {n} trường AI bỏ trống theo bản sắc kênh (spec)"})
    return n


# ------------------------------------------------------------------ công thức THỬ từ spec (vòng đo tự động, không AI)
MAU_THEO_DO_MAY = {"doi_ky_tu": "mau.giai-ma", "mask_reveal": "mau.viet-tay", "typewriter": "mau.go-may"}


def _phan_bo_vao(mv, n):
    """n lớp → danh sách động tác VÀO theo đúng tỉ lệ tan_suat của mẫu (mỗi lớp một kiểu), có kiểu máy gốc do_may"""
    ds = [x for x in (mv.get("vao") or []) if isinstance(x, dict) and x.get("kieu")]
    if not ds:
        return [None] * n
    tong = sum(float(x.get("tan_suat", 0) or 0) for x in ds) or 1.0
    ra, dem = [], [0.0] * len(ds)
    for i in range(n):
        j = max(range(len(ds)), key=lambda k: float(ds[k].get("tan_suat", 0) or 0) / tong * (i + 1) - dem[k])
        dem[j] += 1
        ra.append(ds[j])
    return ra


def _lop_theo_dong_tac(dt, text, kd, vt, t0, t1, lid, spec):
    """một động tác VÀO (của spec) → lớp phù hợp: kiểu máy đặc trưng → mẫu đồ hoạ tương ứng; còn lại → lớp chữ + anim"""
    do_may = (dt or {}).get("do_may") or (dt or {}).get("kieu")
    pal = spec.get("palette") or {}
    if do_may in MAU_THEO_DO_MAY:
        ts = {"chu": text, "font": kd.get("font", "nhan"), "mau_chu": kd.get("mau") or pal.get("nhan") or "#FFFFFF", "hoa": bool(kd.get("hoa"))}
        if kd.get("co"):
            ts["co"] = kd["co"]
        if kd.get("dam"):
            ts["dam"] = kd["dam"]
        if kd.get("vien") == []:
            ts["vien"] = 0
        if (dt or {}).get("dai"):
            ts["dai"] = float(dt["dai"])
        l = {"id": lid, "kieu": "mau", "t0": t0, "t1": t1, "noi_dung": {"mau": MAU_THEO_DO_MAY[do_may], "tham_so": ts},
             "vi_tri": dict(vt, w=vt.get("w", 0.86), h=vt.get("h", 0.14))}
        return l
    l = {"id": lid, "kieu": "chu", "t0": t0, "t1": t1, "noi_dung": {"text": text}, "kieu_dang": kd, "vi_tri": dict(vt)}
    a = {}
    v = _dong_tac({"vao": [dt]}, "vao") if dt else None
    if v:
        a["vao"] = v
    r = _dong_tac(spec.get("motion_vocab") or {}, "ra")
    if r:
        a["ra"] = r
    if do_may == "word_by_word":
        a["tach"] = "tu"
        n_tu = max(1, len(text.split()))
        a["so_le"] = round(min(0.5, float((dt or {}).get("dai", 1.0) or 1.0) / n_tu), 3)
    elif (spec.get("motion_vocab") or {}).get("tach") in ("tu", "ky_tu"):
        a["tach"] = spec["motion_vocab"]["tach"]
    if a:
        l["anim"] = a
    return l


def cong_thuc_tu_spec(spec, du_an, so_lop=8, dai_lop=2.6, ghi_chu="công thức thử từ spec", qd=None):
    """lời của clip thử (doc/loi.json + cat-de-xuat) → chọn câu có từ khoá → lớp chữ/thẻ theo spec, đúng giây thành phẩm"""
    from doc import cat as _cat
    loi = chung.doc_json(os.path.join(du_an, "doc", "loi.json"), {}) or {}
    dx = chung.doc_json(os.path.join(du_an, "doc", "cat-de-xuat.json"), {}) or {}
    giu = dx.get("giu") or []
    f_tp, _ = _cat.tao_anh_xa(giu) if giu else (lambda a: a, None)
    dur_tp = float(dx.get("dur_sau") or loi.get("dur") or 30)
    cau = [c for c in (loi.get("cau") or []) if c.get("txt")]
    lop = []
    mv = spec.get("motion_vocab") or {}
    anim = _anim_spec(mv)
    n_tieu = 0
    buoc = max(1, len(cau) // max(1, so_lop))
    chon = cau[::buoc][:so_lop]
    pb_vao = _phan_bo_vao(mv, len(chon))
    for i, c in enumerate(chon):
        tu = [w for w in re.findall(r"\w+", c["txt"]) if len(w) > 2]
        if not tu:
            continue
        text = " ".join(tu[:3]) if i % 2 else " ".join(tu[:2])
        t0 = round(f_tp(c["a"]), 2)
        t1 = round(min(dur_tp - 0.2, t0 + dai_lop), 2)
        if t1 - t0 < 0.8:
            continue
        vai = "tieu_de" if i % 3 == 0 else ("the" if i % 3 == 1 else "nhan")
        if vai == "the":
            l = {"id": f"s{i}", "kieu": "the", "t0": t0, "t1": t1, "noi_dung": {"text": text.capitalize()}, "kieu_dang": _kieu_dang_the(spec, qd)}
            vt = _anchor(spec, "the") or _anchor(spec, "nhan") or {"anchor": "tc", "x": 0.5, "y": 0.14}
        else:
            kd = _kieu_dang_chu(spec, vai, qd)
            vt = _anchor(spec, vai) or {"anchor": "tc", "x": 0.5, "y": 0.1}
            l = _lop_theo_dong_tac(pb_vao[i], text.upper() if kd.get("hoa") else text, kd, vt, t0, t1, f"s{i}", spec)
            n_tieu += vai == "tieu_de"
            lop.append(l)
            continue
        l["vi_tri"] = dict(vt)
        if anim:
            l["anim"] = copy.deepcopy(anim)
        lop.append(l)
    pal = spec.get("palette") or {}
    ct = {"y_do": {"video_ve": "thử áp bản sắc học được", "ngon_ngu_hinh_anh": spec.get("ghi_chu", "")[:200]},
          "phong_cach": {"mau_nhan": pal.get("nhan") or "#FFFFFF", "mau_nhan2": pal.get("nhan2") or pal.get("sang") or "#FFFFFF",
                         "mau_sang": pal.get("sang") or "#FFFFFF", "mau_toi": pal.get("toi") or "#111111"},
          "lop": lop, "phu_de": {}, "am": {}, "ghi_chu": ghi_chu}
    ap_vao_cong_thuc(ct, spec, qd=qd)
    if not ct["phu_de"].get("che_do"):
        ct["phu_de"]["che_do"] = "cum"
    return ct


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("du_an"); ap.add_argument("--ra")
    a = ap.parse_args()
    sp = chung.doc_json(a.spec)
    ct = cong_thuc_tu_spec(sp, a.du_an)
    p = a.ra or os.path.join(a.du_an, "cong-thuc.json")
    chung.ghi_json(p, ct)
    print(p, len(ct["lop"]), "lớp")
