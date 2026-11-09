# -*- coding: utf-8 -*-
"""Luật chất lượng + luật gu.

kiem(du_an, ke_hoach) -> kiem.json {"loi":[{id,lop,t,mo_ta}], "may_sua":[...], "canh_bao":[...]}
    đo bằng hộp đã giải (ke_hoach["lop"][i]["hop"] nếu dung.lop đã ghi; chưa có → ước từ vi_tri + 0.6×co×số ký tự)
    so với mat.json (mặt trung vị trong [t0,t1]); không giải mã video. Máy dời/thu được thì sửa vi_tri và ghi may_sua.
1.2.21: ngưỡng luật chặn đọc từ luat_chat_luong.json, `cau_hinh()["luat"][id][khoá]` đè được; không đo được mặt → cảnh báo `khong_mat`
    (không dùng vị trí mặt giả); phụ đề ước theo ke_hoach["phu_de"] (đã điền từ quyết định kênh), không có số riêng; luật nghề
    (sfx_lap, mat_do_lop_moi, khoang_tho, so_kieu, trinh_dien) mặc định TẮT, bật thì chỉ in SỐ ĐO so với ngưỡng hồ sơ, không câu khuyên;
    `so_do_nghe` luôn in số đo (thông tin). Lỗi/cảnh báo của chuẩn hoá (loi_chuan_hoa, canh_bao_chuan_hoa) gộp vào kết quả.
kiem_ky_thuat(video) -> {"khung_den","dong_bang","lufs","peak","loi","canh_bao"}  (1 lượt ffmpeg 540p 4 fps + ebur128)
"""
import json, math, os, re, statistics, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung

NAO = os.path.dirname(os.path.abspath(__file__))
try:
    from ai.cong_thuc import tp_sang_goc, goc_sang_tp, font_du_dau
except Exception:  # dự phòng nếu ai/ chưa import được
    def tp_sang_goc(cat, t):
        d = 0.0
        for c in cat:
            l = c["b"] - c["a"]
            if t <= d + l + 1e-6:
                return c.get("src", 0), c["a"] + max(0.0, t - d)
            d += l
        return 0, t

    def goc_sang_tp(cat, t_goc, src=0):
        d = 0.0
        for c in cat:
            if c.get("src", 0) == src and c["a"] - 1e-6 <= t_goc <= c["b"] + 1e-6:
                return d + (t_goc - c["a"])
            d += c["b"] - c["a"]
        return None

    def font_du_dau(p):
        return True


def luat_chat_luong():
    return chung.doc_json(os.path.join(NAO, "luat_chat_luong.json"), {}) or {}


def _ho_tieng(so_do):
    """chữ ký vật lý của kho → họ tiếng (nhãn đo được, không phải gu): gió/nhiễu · tách/khô · ngân/chuông · trầm/bùm · khác"""
    try:
        from kho import tai as _TAI
        ck = _TAI.chu_ky(so_do or {})
    except Exception:
        ck = {}
    if not ck:
        return "chưa đo"
    if ck.get("chat") == "nhieu":
        return "gió/nhiễu"
    if ck.get("cao") == "tram":
        return "trầm/bùm"
    if ck.get("chat") == "am_sac" and ck.get("ngan") == "ngan":
        return "ngân/chuông"
    if ck.get("bat") == "bat" and ck.get("ngan") == "kho":
        return "tách/khô"
    return "khác"


def _phan_bo_tieng_dong(kh, dur):
    """→ dict mô tả phân bố tiếng động trong kế hoạch (dữ liệu cho AI soi với ý đồ của mình) hoặc None khi không có tiếng và không ghi ý đồ"""
    sfx = sorted([s for s in ((kh.get("am") or {}).get("sfx") or []) if isinstance(s, dict)], key=lambda s: float(s.get("t", 0)))
    y_do = (kh.get("y_do") or {}) if isinstance(kh.get("y_do"), dict) else {}
    y_tieng = y_do.get("tieng_dong")
    if not sfx and not y_tieng:
        return None
    try:
        from kho import tim as _TIM
    except Exception:
        _TIM = None
    ho, tep = [], {}
    for s in sfx:
        mid = s.get("id_kho") or s.get("id")
        m = _TIM.lay(mid) if (_TIM and isinstance(mid, str)) else None
        h = _ho_tieng((m or {}).get("so_do")) if m else "chưa đo"
        ho.append(h); tep[mid] = tep.get(mid, 0) + 1
    dem = {}
    for h in ho:
        dem[h] = dem.get(h, 0) + 1
    # chuỗi cùng họ dài nhất
    chuoi, cmax, h_max = 0, 0, None
    for i, h in enumerate(ho):
        chuoi = chuoi + 1 if i and h == ho[i - 1] else 1
        if chuoi > cmax:
            cmax, h_max = chuoi, h
    ts = [float(s.get("t", 0)) for s in sfx]
    chong = sum(1 for a, b in zip(ts, ts[1:]) if b - a < 0.3)
    khe = [b - a for a, b in zip(ts, ts[1:])]
    khe_max = max(khe) if khe else (float(dur) if dur else 0)
    lap = {k: v for k, v in tep.items() if v >= 3}
    mo_ta = (f"{len(sfx)} mốc" + (f" / {float(dur):.0f} s ({len(sfx) / float(dur) * 10:.1f} mốc mỗi 10 s)" if dur else "")
             + (" · họ: " + ", ".join(f"{k} {v}" for k, v in sorted(dem.items(), key=lambda kv: -kv[1])) if dem else "")
             + (f" · chuỗi cùng họ dài nhất: {cmax} ({h_max})" if cmax >= 2 else "")
             + (f" · {chong} cặp cách nhau < 0,3 s" if chong else "")
             + (f" · khoảng không tiếng dài nhất {khe_max:.1f} s" if sfx else "")
             + (" · tệp lặp ≥ 3: " + ", ".join(f"{k}×{v}" for k, v in lap.items()) if lap else "")
             + (f" · ý đồ bạn ghi: «{str(y_tieng)[:160]}»" if y_tieng else " · y_do.tieng_dong chưa ghi"))
    return {"mo_ta": mo_ta, "so_moc": len(sfx), "ho": dem, "chuoi_cung_ho": [cmax, h_max], "chong": chong, "khe_max": round(khe_max, 2), "lap": lap, "y_do": y_tieng}


def luat_gu():
    return chung.doc_json(os.path.join(NAO, "luat_gu.json"), {}) or {}


def _nguong(id_, khoa, mac_dinh):
    """ngưỡng luật chặn: cau_hinh()["luat"][id_][khoa] (cấu hình khách) → luat_chat_luong.json → mac_dinh"""
    try:
        de = ((chung.cau_hinh().get("luat") or {}).get(id_) or {})
        if khoa in de:
            return de[khoa]
    except Exception:
        pass
    for l in luat_chat_luong().get("luat", []):
        if l["id"] == id_:
            return (l.get("nguong") or {}).get(khoa, mac_dinh)
    return mac_dinh


def _so(x, mac_dinh=None):
    try:
        return float(x)
    except Exception:
        return mac_dinh


# ---------------------------------------------------------------- hình học
def _giao(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _dt(a):
    return max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])


def _so_tu(text):
    return max(1, len([w for w in re.split(r"\s+", (text or "").strip()) if w]))


def kich_thuoc_uoc(lop, W, H):
    """ước (w,h) px của lớp khi chưa có hộp thật."""
    k = lop["kieu"]
    kd = lop.get("kieu_dang") or {}
    nd = lop.get("noi_dung") or {}
    vt = lop.get("vi_tri") or {}
    ti_le = W / 1080.0
    if k == "chu":
        if _so(kd.get("co")) is None:
            return None                          # thiếu cỡ (thieu_truong) → không ước được, lớp đã có lỗi chặn
        co = _so(kd.get("co")) * ti_le
        dong = _so(kd.get("dong"), 1.0)
        rong_max = _so(kd.get("rong_max"), 1.0) * W
        lines = (nd.get("text") or "").split("\n")
        rong_dong = [0.6 * co * len(l) * (1 + _so(kd.get("gian"), 0)) for l in lines]
        tong_dong = 0
        w = 0
        for r in rong_dong:
            n = max(1, math.ceil(r / rong_max)) if rong_max > 0 else 1
            tong_dong += n
            w = max(w, min(r, rong_max))
        h = tong_dong * co * dong
        nen = kd.get("nen")
        if nen:
            w += 2 * float(nen["dem"][0]); h += 2 * float(nen["dem"][1])
        vien = max([float(v.get("w", 0)) for v in kd.get("vien") or []] + [0])
        return w + 2 * vien, h + 2 * vien, co
    if k == "khoi":
        w = h = 0.0; co_max = 0.0
        ds = [d for d in (nd.get("dong") or []) if isinstance(d, dict)]
        cd = _so(kd.get("cach_dong"), 1.0) or 1.0
        for j, d in enumerate(ds):
            k2 = d.get("kieu_dang") or {}
            if _so(k2.get("co")) is None:
                return None
            co = _so(k2.get("co")) * ti_le
            w = max(w, 0.6 * co * len(str(d.get("text") or "")) * (1 + _so(k2.get("gian"), 0)))
            h += co * _so(k2.get("dong"), 1.0) * (cd if j < len(ds) - 1 else 1.0)
            co_max = max(co_max, co)
        return w, h, co_max
    if k == "the":
        chu = kd.get("chu") or {}
        if _so(chu.get("co")) is None:
            return None
        co = _so(chu.get("co")) * ti_le
        dem = kd.get("dem") or [0, 0]
        w = 0.6 * co * len(nd.get("text") or "") + 2 * float(dem[0]) + (co + float(dem[0]) if nd.get("icon_duong") else 0)
        h = co * 1.3 + 2 * float(dem[1])
        if kd.get("hinh") == "circle":
            w = h = max(w, h)
        return w, h, co
    if k == "duong":
        return max(0.01, vt.get("w", 0.1)) * W + float(kd.get("w", 8)) * 2, max(0.01, vt.get("h", 0.01)) * H + float(kd.get("w", 8)) * 2, 0
    if _so(vt.get("w")) is None or _so(vt.get("h")) is None:
        return None
    w, h = _so(vt.get("w")), _so(vt.get("h"))
    return (w if w > 1 else w * W), (h if h > 1 else h * H), 0          # web: w/h > 1 là px


def _neo(anchor, ax, ay, w, h):
    dy = {"t": 0, "m": 0.5, "b": 1}[anchor[0]]
    dx = {"l": 0, "c": 0.5, "r": 1}[anchor[1]]
    x0, y0 = ax - dx * w, ay - dy * h
    return [x0, y0, x0 + w, y0 + h]


def _diem_neo(anchor, hop):
    dy = {"t": 0, "m": 0.5, "b": 1}[anchor[0]]
    dx = {"l": 0, "c": 0.5, "r": 1}[anchor[1]]
    return hop[0] + dx * (hop[2] - hop[0]), hop[1] + dy * (hop[3] - hop[1])


ANCHOR_Y = {"tl": 0, "tc": 0, "tr": 0, "ml": 0.5, "mc": 0.5, "mr": 0.5, "bl": 1, "bc": 1, "br": 1}


def mat_trong_khoang(mat, cat, t0, t1, W, H):
    """mặt trung vị (px, toạ độ khung thành phẩm = khung gốc đã scale) trong [t0,t1] thành phẩm; None nếu không có."""
    if not mat:
        return None
    khung = mat.get("khung") or []
    fps_mau = float(mat.get("fps_mau") or 5)
    buoc = max(0.2, (t1 - t0) / 12)
    ts, t = [], t0
    while t <= t1 + 1e-6:
        ts.append(t); t += buoc
    xs, ys, ws, hs = [], [], [], []
    idx = {}
    for k in khung:
        idx.setdefault(k.get("src", 0), []).append(k)
    for t in ts:
        src, tg = tp_sang_goc(cat, t)
        ds = idx.get(src) or khung
        gan = None
        for k in ds:
            if abs(k.get("t", 0) - tg) <= 0.6 / fps_mau:
                if gan is None or abs(k["t"] - tg) < abs(gan["t"] - tg):
                    gan = k
        if gan and gan.get("mat"):
            m = max(gan["mat"], key=lambda f: f.get("diem", 0) * f.get("w", 0))
            xs.append(m["x"]); ys.append(m["y"]); ws.append(m["w"]); hs.append(m["h"])
    if not xs:
        tb = mat.get("mat_tb")
        if tb and tb.get("w") and (mat.get("nguoi_ti_le", 1) or 0) >= 0.5:
            xs, ys, ws, hs = [tb["x"]], [tb["y"]], [tb["w"]], [tb["h"]]
        else:
            return None
    x, y, w, h = statistics.median(xs), statistics.median(ys), statistics.median(ws), statistics.median(hs)
    # mat.json ghi TÂM mặt → hộp px vùng CẤM che (lông mày→cằm, nới 0.12 cao lên trên, 0.05 rộng hai bên) — khớp dung/lop.Ctx.mat_tai
    return {"x": x, "y": y, "w": w, "h": h, "px": [(x - w * 0.55) * W, (y - h * 0.62) * H, (x + w * 0.55) * W, (y + h * 0.5) * H], "so_mau": len(xs)}


def giai_hop(lop, W, H, mat_px):
    """hộp px từ vi_tri + kích thước ước (chưa áp vùng an toàn). → (hop, co) | (None, "ly_do") khi không ước được
    (thiếu cỡ/vị trí = thieu_truong, hoặc so_voi theo mặt mà không đo được mặt — không dùng vị trí mặt giả)."""
    vt = lop.get("vi_tri") or {}
    kt = kich_thuoc_uoc(lop, W, H)
    if kt is None or _so(vt.get("x")) is None or _so(vt.get("y")) is None:
        return None, "thieu_truong"
    w, h, co = kt
    sv = vt.get("so_voi") or "khung"
    ax, ay = _so(vt.get("x")) * W, _so(vt.get("y")) * H
    if sv != "khung" and not mat_px:
        return None, "khong_mat"
    if sv != "khung" and mat_px:
        fx0, fy0, fx1, fy1 = mat_px
        cx, cy = (fx0 + fx1) / 2, (fy0 + fy1) / 2
        if sv == "mat":
            ax, ay = cx + vt["x"] * W, cy + vt["y"] * H
        elif sv == "duoi_cam":
            ay = fy1 + vt["y"] * H
        elif sv == "tren_dau":
            ay = fy0 - vt["y"] * H
    return _neo(vt.get("anchor") or "mc", ax, ay, w, h), co


def _trong_an_toan(hop, at):
    return hop[0] >= at[0] - 0.5 and hop[1] >= at[1] - 0.5 and hop[2] <= at[2] + 0.5 and hop[3] <= at[3] + 0.5


def _ep_vao(hop, at):
    """dời hộp vào vùng an toàn (giữ kích thước). Trả hộp mới hoặc None nếu không vừa."""
    w, h = hop[2] - hop[0], hop[3] - hop[1]
    if w > (at[2] - at[0]) + 1 or h > (at[3] - at[1]) + 1:
        return None
    x0 = min(max(hop[0], at[0]), at[2] - w)
    y0 = min(max(hop[1], at[1]), at[3] - h)
    return [x0, y0, x0 + w, y0 + h]


def _thu(hop, ti_le, anchor):
    ax, ay = _diem_neo(anchor, hop)
    w, h = (hop[2] - hop[0]) * ti_le, (hop[3] - hop[1]) * ti_le
    return _neo(anchor, ax, ay, w, h)


# ---------------------------------------------------------------- kiểm chính
def kiem(du_an, ke_hoach):
    du_an = os.path.abspath(du_an)
    if isinstance(ke_hoach, str):
        ke_hoach = chung.doc_json(ke_hoach) or {}
    kh = ke_hoach
    W, H = kh.get("khung") or [1080, 1920]
    dur = float(kh.get("dur") or 0)
    cat = kh.get("cat") or []
    at_tl = kh.get("vung_an_toan") or chung.vung_an_toan(W, H)
    AT = [at_tl["trai"] * W, at_tl["tren"] * H, (1 - at_tl["phai"]) * W, (1 - at_tl["duoi"]) * H]
    mat = chung.doc_json(os.path.join(du_an, "doc", "mat.json")) or {}
    loi_j = chung.doc_json(os.path.join(du_an, "doc", "loi.json")) or {}
    loi = list(kh.get("loi_chuan_hoa") or [])
    may_sua = list(kh.get("may_sua") or [])
    canh_bao = list(kh.get("canh_bao_chuan_hoa") or [])
    doi_ke_hoach = False
    hop_cua = {}
    ng_giao = float(_nguong("de_mat", "ti_le_giao_toi_da", 0.05))
    thu_min = float(_nguong("de_mat", "thu_toi_thieu", 0.8))
    qd = kh.get("quyet_dinh") if isinstance(kh.get("quyet_dinh"), dict) else {}
    if _so((qd.get("ne_mat") or {}).get("thu_toi")) is not None:        # AI quyết thu tới đâu khi né mặt (1.0 = không thu, chỉ báo)
        thu_min = float((qd.get("ne_mat") or {}).get("thu_toi"))

    # ---- lớp xếp nhóm (vi_tri.nhom): hộp THẬT theo bố cục xếp chồng của engine (không ước từng lớp rời)
    if any((l.get("vi_tri") or {}).get("nhom") for l in kh.get("lop") or []):
        try:
            import copy
            from dung import dung as _DG, lop as _LP
            ctx = _DG.tao_ctx(du_an, copy.deepcopy(kh))
            specs, ms = _LP.xep_nhom(copy.deepcopy(kh.get("lop") or []), ctx)
            may_sua += [dict(m, mo_ta=f"xếp nhóm `{m.get('nhom')}` ({m.get('xep')}): {m.get('lop')}" + (f" — né mặt: {m['ne_mat']}" if m.get("ne_mat") else ""))
                        for m in ms]
            for lop, sp in zip(kh.get("lop") or [], specs):
                if (lop.get("vi_tri") or {}).get("nhom"):
                    L = _LP.tao_lop(sp, ctx)
                    x, y, w, h = L.khoi()
                    lop["hop"] = [round(x, 1), round(y, 1), round(x + w, 1), round(y + h, 1)]
                    # ghi vị trí đã xếp vào kế hoạch (xep_xong) → bước dựng / kiểm chồng hộp thật dùng đúng ô, không xếp lại
                    lop["vi_tri"] = dict(sp.get("vi_tri") or {}, xep_xong=True)
                    if sp.get("ne_mat") is False:
                        lop["ne_mat"] = False
                    loi += [dict(l, mo_ta=l.get("mo_ta", "") + " (lớp trong nhóm xếp chồng)") for l in L.loi if l.get("id") == "de_mat"]
        except Exception as ex:
            if hasattr(ex, "loi") and getattr(ex, "ma", "") == "thieu_truong":          # dung.chu.ThieuTruong → lỗi có `duong` cho AI
                loi.append(ex.loi())
            else:
                canh_bao.append({"id": "xep_nhom", "lop": "*", "mo_ta": f"không đo được bố cục nhóm bằng engine ({ex}) — ước từng lớp"})

    # ---- hộp, vùng an toàn, mặt
    for lop in kh.get("lop") or []:
        lid = lop["id"]
        toan_khung = bool(lop.get("toan_khung")) or (lop["kieu"] in ("video", "hinh") and lop["vi_tri"].get("w", 0) >= 0.9 and lop["vi_tri"].get("h", 0) >= 0.9)
        m = mat_trong_khoang(mat, cat, lop["t0"], lop["t1"], W, H)
        mat_px = m["px"] if m else None
        if lop.get("hop") and len(lop["hop"]) == 4:
            hop = [float(v) for v in lop["hop"]]
            co = 0
            uoc = False
        else:
            hop, co = giai_hop(lop, W, H, mat_px)
            uoc = True
            if hop is None:
                if co == "khong_mat":
                    canh_bao.append({"id": "khong_mat", "lop": lid, "t": lop["t0"], "mo_ta": f"vi_tri.so_voi={(lop.get('vi_tri') or {}).get('so_voi')} nhưng không đo được mặt trong [{lop['t0']}, {lop['t1']}] (mat.json) — không kiểm hộp lớp này; lúc dựng engine báo lại"})
                lop["mat_trong_khoang"] = None
                continue
        hop0 = list(hop)
        anchor = (lop.get("vi_tri") or {}).get("anchor") or "mc"
        rong_max_px = W * _so(lop["kieu_dang"].get("rong_max"), 1.0)
        if lop["kieu"] == "chu" and hop[2] - hop[0] > rong_max_px + 2:
            # chữ tràn rong_max: thu cỡ tới ngưỡng vật lý (thu_toi_thieu / ne_mat.thu_toi), ghi may_sua
            tl = max(thu_min, rong_max_px / (hop[2] - hop[0]))
            if tl < 1:
                hop = _thu(hop, tl, anchor)
                if uoc:
                    lop["kieu_dang"]["co"] = round(float(lop["kieu_dang"]["co"]) * tl, 1)
                may_sua.append({"lop": lid, "sua": "thu_chu", "tu": round(hop0[2] - hop0[0]), "den": round(hop[2] - hop[0]), "mo_ta": f"khối chữ rộng hơn rong_max → thu cỡ ×{tl:.2f}"})
                doi_ke_hoach = True
            if hop[2] - hop[0] > W + 2:
                loi.append({"id": "chu_tran_khung", "lop": lid, "t": lop["t0"], "mo_ta": f"khối chữ rộng {hop[2] - hop[0]:.0f}px > khung {W}px sau khi thu ×{tl:.2f}"})
        mau_tran = lop["kieu"] in ("mau", "web") and ((hop[2] - hop[0]) > (AT[2] - AT[0]) + 1 or (hop[3] - hop[1]) > (AT[3] - AT[1]) + 1)
        if mau_tran and not toan_khung:          # mẫu/web cố ý sát mép (thanh tiến trình, băng chữ…): engine vẽ đúng hộp, không dời/thu
            canh_bao.append({"id": "ngoai_vung_an_toan", "lop": lid, "mo_ta": f"hộp {[round(v) for v in hop]} rộng hơn vùng an toàn — phần sát mép có thể bị giao diện app che"})
        elif not toan_khung:
            if not _trong_an_toan(hop, AT):
                h2 = _ep_vao(hop, AT)
                if h2 is None:
                    tl = max(thu_min, min((AT[2] - AT[0]) / (hop[2] - hop[0]), (AT[3] - AT[1]) / (hop[3] - hop[1])))
                    h2 = _ep_vao(_thu(hop, tl, anchor), AT)
                    if h2:
                        may_sua.append({"lop": lid, "sua": "thu", "tu": None, "den": round(tl, 2), "mo_ta": f"hộp lớn hơn vùng an toàn → thu ×{tl:.2f}"})
                if h2 is None:
                    loi.append({"id": "ngoai_vung_an_toan", "lop": lid, "t": lop["t0"], "mo_ta": f"hộp {[round(v) for v in hop]} không vừa vùng an toàn {[round(v) for v in AT]} kể cả khi thu ×{thu_min:.2f}"})
                else:
                    if [round(v) for v in h2] != [round(v) for v in hop]:
                        may_sua.append({"lop": lid, "sua": "doi", "tu": [round(v) for v in hop], "den": [round(v) for v in h2], "mo_ta": "dời vào vùng an toàn"})
                    hop = h2
                    doi_ke_hoach = True
            if mat_px and lop.get("ne_mat") is not False and _giao(hop, mat_px) > ng_giao * _dt(mat_px):
                # KHÔNG tự dời ở đây — engine (dung/lop) đặt vị trí cuối theo luật: dời về phía NEO, rồi thu dần (≥ ×0.7).
                # Máy kiểm chỉ CHẶN khi chắc chắn engine không cứu được (không đủ chỗ phía neo kể cả khi thu ×0.7).
                ay_ = ANCHOR_Y.get(anchor, 0.5)
                cao = (hop[3] - hop[1]) * thu_min
                cho_len = mat_px[1] - AT[1]
                cho_xuong = AT[3] - mat_px[3]
                duoc = (cho_len >= cao) if ay_ <= 0.34 else (cho_xuong >= cao) if ay_ >= 0.66 else max(cho_len, cho_xuong) >= cao     # R2: neo giữa cũng chặn khi không phía nào đủ chỗ (bỏ `or True`)
                if not duoc:
                    loi.append({"id": "de_mat", "lop": lid, "t": lop["t0"], "mo_ta": f"khối che mặt (mắt–cằm) trong [{lop['t0']}, {lop['t1']}]; phía neo `{anchor}` còn {(cho_len if ay_ <= 0.34 else cho_xuong):.0f}px, khối cao {hop[3] - hop[1]:.0f}px (thu tới ×{thu_min:.2f} vẫn không vừa)"})
                else:
                    may_sua.append({"lop": lid, "sua": "ne_mat", "mo_ta": f"chạm mặt → lúc dựng engine dời về phía neo / thu tới ×{thu_min:.2f} (ne_mat.thu_toi)"})
        if [round(v) for v in hop] != [round(v) for v in hop0]:
            ax, ay = _diem_neo(anchor, hop)
            lop["vi_tri"] = dict(lop["vi_tri"], so_voi="khung", x=round(ax / W, 4), y=round(ay / H, 4))
            if lop.get("hop"):
                lop["hop"] = [round(v, 1) for v in hop]
        if uoc:
            lop["hop_uoc"] = [round(v, 1) for v in hop]
        hop_cua[lid] = hop
        lop["mat_trong_khoang"] = m and {k: round(m[k], 4) for k in ("x", "y", "w", "h")}

    # ---- chồng lớp (chữ/thẻ + mẫu/web không phủ cả khung; lớp cùng nhóm xếp chồng đã được engine xếp không chồng)
    chu_lop = [l for l in kh.get("lop") or [] if l["id"] in hop_cua and (l["kieu"] in ("chu", "khoi", "the") or (l["kieu"] in ("mau", "web") and not l.get("toan_khung")))]
    ng_cl = float(_nguong("chong_lop", "ti_le", 0.3))
    for i in range(len(chu_lop)):
        for j in range(i + 1, len(chu_lop)):
            a, b = chu_lop[i], chu_lop[j]
            na, nb = (a.get("vi_tri") or {}).get("nhom"), (b.get("vi_tri") or {}).get("nhom")
            if na and na == nb:
                continue
            giao_t = min(a["t1"], b["t1"]) - max(a["t0"], b["t0"])
            if giao_t <= float(_nguong("chong_lop", "giao_giay_toi_thieu", 0.1)):
                continue
            ha, hb = hop_cua[a["id"]], hop_cua[b["id"]]
            nho = min(_dt(ha), _dt(hb)) or 1
            tl = _giao(ha, hb) / nho
            if tl > ng_cl:
                x_ = {"id": "chong_lop", "lop": f"{a['id']}+{b['id']}", "t": round(max(a["t0"], b["t0"]), 2), "mo_ta": f"hai lớp chữ chồng {tl * 100:.0f}% trong {giao_t:.1f}s (ngưỡng {ng_cl * 100:.0f}%)"}
                (canh_bao if (a.get("co_y") or b.get("co_y")) else loi).append(x_)   # 1.2.19 (D10): cố ý chồng (collage) → cảnh báo
    # phụ đề vs lớp chữ
    pd = kh.get("phu_de") or {}
    hp = None
    if pd.get("che_do") and pd.get("che_do") != "tat" and pd.get("toi_da_chu") and pd.get("kieu_dang") and pd.get("vi_tri"):
        gia = {"kieu": "chu", "noi_dung": {"text": "M" * int(pd["toi_da_chu"])}, "kieu_dang": pd["kieu_dang"], "vi_tri": pd["vi_tri"]}
        hp, _ = giai_hop(gia, W, H, None)
    if hp:
        for a in chu_lop:
            nho = min(_dt(hp), _dt(hop_cua[a["id"]])) or 1
            tl = _giao(hp, hop_cua[a["id"]]) / nho
            if tl > ng_cl:
                may_sua.append({"lop": f"phu_de+{a['id']}", "sua": "nhuong_cho", "mo_ta": f"phụ đề chồng lớp {a['id']} {tl * 100:.0f}% → lúc dựng phụ đề tự dời lên/xuống cạnh lớp"})
        m_pd = mat_trong_khoang(mat, cat, 0, dur or 1, W, H) if mat else None
        if m_pd and _giao(hp, m_pd["px"]) > ng_giao * _dt(m_pd["px"]):
            loi.append({"id": "de_mat", "lop": "phu_de", "t": 0, "mo_ta": f"hộp phụ đề {[round(v) for v in hp]} đè mặt trung bình {[round(v) for v in m_pd['px']]} > {ng_giao * 100:.0f}% diện tích mặt"})

    # ---- đọc không kịp
    ng_chu = float(_nguong("doc_khong_kip", "giay_moi_tu_chu", 0.3))
    for l in kh.get("lop") or []:
        if l["kieu"] in ("chu", "khoi", "the"):
            n = _so_tu(" ".join(str(d.get("text") or "") for d in (l["noi_dung"].get("dong") or []) if isinstance(d, dict)) if l["kieu"] == "khoi" else l["noi_dung"].get("text"))
            spt = (l["t1"] - l["t0"]) / n
            if spt < ng_chu:
                x_ = {"id": "doc_khong_kip", "lop": l["id"], "t": l["t0"], "mo_ta": f"{n} từ trong {l['t1'] - l['t0']:.2f}s = {spt:.2f} s/từ (ngưỡng {ng_chu})"}
                (canh_bao if l.get("co_y") else loi).append(x_)          # 1.2.19 (D10): co_y:true → cảnh báo, không chặn
    if pd.get("che_do") == "cum" and loi_j.get("tu"):
        ng_pd = float(_nguong("doc_khong_kip", "giay_moi_tu_phu_de", 0.18))
        cum, hien, vi_pham, tong = [], [], 0, 0
        toi_da = int(pd.get("toi_da_chu") or 0) or 10 ** 6
        lang_ngat = _so(pd.get("lang_ngat"), 0.8)          # R2: khoảng lặng ngắt cụm = quyết định kênh phu_de.lang_ngat (engine gom_cum dùng), không số riêng
        for w in loi_j["tu"]:
            a = goc_sang_tp(cat, w["a"], w.get("src", 0))
            if a is None:
                continue
            if hien and (len(" ".join(x["w"] for x in hien)) + 1 + len(w["w"]) > toi_da or a - hien[-1]["b_tp"] > lang_ngat):
                cum.append(hien); hien = []
            hien.append({"w": w["w"], "a": a, "b_tp": goc_sang_tp(cat, w["b"], w.get("src", 0)) or a})
        if hien:
            cum.append(hien)
        # Phụ đề bám lời: người nói nhanh thì phụ đề nhanh theo — đó là nhịp của lời, không phải lỗi. CHẶN chỉ khi cụm hiện quá
        # ngắn để mắt kịp bắt (< 0.45 s mà ≥ 3 từ); nhanh hơn ngưỡng s/từ thì CẢNH BÁO (AI tự cân nhắc, không bắt gọi lại).
        cuc_ngan = 0
        for i, c in enumerate(cum):
            ket = cum[i + 1][0]["a"] if i + 1 < len(cum) else c[-1]["b_tp"]
            d = max(ket, c[-1]["b_tp"]) - c[0]["a"]
            tong += 1
            if d / len(c) < ng_pd:
                vi_pham += 1
            if d < float(_nguong("doc_khong_kip", "cum_toi_thieu_giay", 0.45)) and len(c) >= 3:
                cuc_ngan += 1
        if tong:
            if cuc_ngan / tong > float(_nguong("doc_khong_kip", "ti_le_cum_vi_pham", 0.25)):
                loi.append({"id": "doc_khong_kip", "lop": "phu_de", "t": 0, "mo_ta": f"{cuc_ngan}/{tong} cụm phụ đề hiện < {_nguong('doc_khong_kip', 'cum_toi_thieu_giay', 0.45)} s mà ≥ 3 từ (ngưỡng {float(_nguong('doc_khong_kip', 'ti_le_cum_vi_pham', 0.25)) * 100:.0f}% số cụm; toi_da_chu hiện {pd.get('toi_da_chu')})"})
            elif vi_pham:
                canh_bao.append({"id": "doc_khong_kip", "lop": "phu_de", "mo_ta": f"{vi_pham}/{tong} cụm phụ đề < {ng_pd} s/từ (nhịp của người nói; toi_da_chu hiện {pd.get('toi_da_chu')})"})

    # ---- font
    fonts = set()
    for l in kh.get("lop") or []:
        fd = (l.get("kieu_dang") or {}).get("font_duong") or ((l.get("kieu_dang") or {}).get("chu") or {}).get("font_duong")
        if fd:
            fonts.add(fd)
            if not font_du_dau(fd):
                loi.append({"id": "font_thieu_dau", "lop": l["id"], "t": l["t0"], "mo_ta": f"font {os.path.basename(fd)} thiếu dấu tiếng Việt"})
        elif l["kieu"] in ("chu", "the"):
            loi.append({"id": "font_thieu_dau", "lop": l["id"], "t": l["t0"], "mo_ta": "không giải được font"})
    if (pd.get("kieu_dang") or {}).get("font_duong"):
        fonts.add(pd["kieu_dang"]["font_duong"])

    # ---- thời gian / cat
    for c in cat:
        src = c.get("src", 0)
        ng = (kh.get("nguon") or [])
        if src < len(ng) and ng[src].get("dur") and c["b"] > ng[src]["dur"] + 0.05:
            loi.append({"id": "thoi_gian", "lop": "cat", "t": c["a"], "mo_ta": f"cat [{c['a']}, {c['b']}] vượt thời lượng nguồn {src} ({ng[src]['dur']:.2f}s)"})
    for s in (kh.get("am") or {}).get("sfx") or []:
        if dur and s["t"] > dur:
            loi.append({"id": "thoi_gian", "lop": "am.sfx", "t": s["t"], "mo_ta": "sfx ngoài thời lượng"})

    # ---- luật gu / luật nghề (mặc định TẮT; hồ sơ bật và đặt số) — vi phạm chỉ in SỐ ĐO so với ngưỡng hồ sơ, không câu khuyên
    ho_so = chung.doc_json(os.path.join(chung.duong("ho_so"), kh.get("ho_so") or "", "ho-so.json")) or {}
    gu_hs = ho_so.get("luat_gu") or {}
    gu_md = {l["id"]: l for l in luat_gu().get("luat", [])}
    bat = {k: float(v.get("gia_tri", gu_md.get(k, {}).get("gia_tri", 0))) for k, v in gu_hs.items() if isinstance(v, dict) and v.get("bat") and k in gu_md}

    def cb(id_, mo_ta, lop_="*", **them):
        canh_bao.append(dict({"id": id_, "lop": lop_, "mo_ta": mo_ta, "gu": True}, **them))

    # ---- TIẾNG ĐỘNG: máy chỉ ĐO và BÁO phân bố (không ngưỡng, không gu) — có/không, bao nhiêu, họ nào là quyết định của AI ở y_do.tieng_dong
    try:
        pb = _phan_bo_tieng_dong(kh, dur)
        if pb:
            canh_bao.append(dict(pb, id="tieng_dong_phan_bo", lop="am.sfx", thong_tin=True))
    except Exception as ex:
        canh_bao.append({"id": "tieng_dong_phan_bo", "lop": "am.sfx", "thong_tin": True, "mo_ta": f"(không đo được phân bố tiếng: {str(ex)[:80]})"})

    # ---- SỐ ĐO NGHỀ (luôn in, chỉ thông tin): mật độ lớp mới/10 s, % thời lượng không đồ hoạ, số kiểu/phút, hiệu ứng trình diễn/phút, sfx lặp
    so_do = {}
    dem_sfx = {}
    for s_ in (kh.get("am") or {}).get("sfx") or []:
        k_ = s_.get("id_kho") or s_.get("id")
        dem_sfx[k_] = dem_sfx.get(k_, 0) + 1
    so_do["sfx_lap"] = {k: v for k, v in dem_sfx.items() if v >= 2}
    do_hoa = [l for l in kh.get("lop") or [] if l.get("kieu") in ("chu", "khoi", "the", "hinh", "mau", "web", "video", "duong", "py")
              and not str(l.get("id", "")).startswith("pd")]
    if do_hoa and dur:
        t0s = sorted(float(l["t0"]) for l in do_hoa)
        dinh, luc = 0, 0.0
        for i, a in enumerate(t0s):
            n = sum(1 for b in t0s[i:] if b < a + 10)
            if n > dinh:
                dinh, luc = n, a
        so_do["mat_do_lop_moi"] = {"toi_da_10s": dinh, "tai_giay": round(luc, 1)}
        ds = sorted((float(l["t0"]), float(l["t1"])) for l in do_hoa if not (l.get("kieu") == "video" and (l.get("kieu_dang") or {}).get("hoa_tron") not in (None, "normal")))
        phu, cuoi = 0.0, 0.0
        for a, b in ds:
            if b > cuoi:
                phu += b - max(a, cuoi); cuoi = b
        so_do["khoang_tho"] = {"phan_tram_khong_do_hoa": round(100.0 * (1 - phu / dur), 1)}
        kieu = {((l.get("noi_dung") or {}).get("mau") if l.get("kieu") == "mau" else l.get("kieu")) for l in do_hoa}
        so_do["so_kieu"] = {"so_kieu": len(kieu), "moi_phut": round(len(kieu) / max(0.5, dur / 60), 2)}
        tu_khoa = ("glitch", "leak", "vet-sang", "chop", "3d", "phat-sang", "shine", "flash")
        td = [l for l in do_hoa if l.get("kieu") == "mau" and any(k in str((l.get("noi_dung") or {}).get("mau", "")).lower() for k in tu_khoa)]
        so_do["trinh_dien"] = {"so": len(td), "moi_phut": round(len(td) / max(0.5, dur / 60), 2), "lop": [str(l.get("id")) for l in td[:8]]}
    canh_bao.append({"id": "so_do_nghe", "lop": "*", "thong_tin": True, "so_do": so_do,
                     "mo_ta": "số đo (không ngưỡng): " + json.dumps(so_do, ensure_ascii=False, separators=(",", ":"))[:600]})
    if "sfx_lap_toi_da" in bat:
        for k_, n_ in dem_sfx.items():
            if n_ > bat["sfx_lap_toi_da"]:
                cb("sfx_lap_toi_da", f"sfx {k_} dùng {n_} lần (hồ sơ: ≤ {bat['sfx_lap_toi_da']:.0f})", "am.sfx", tranh=sorted(dem_sfx))
    if "mat_do_lop_moi" in bat and so_do.get("mat_do_lop_moi") and so_do["mat_do_lop_moi"]["toi_da_10s"] > bat["mat_do_lop_moi"]:
        cb("mat_do_lop_moi", f"{so_do['mat_do_lop_moi']['toi_da_10s']} lớp đồ hoạ mới trong 10 s quanh giây {so_do['mat_do_lop_moi']['tai_giay']} (hồ sơ: ≤ {bat['mat_do_lop_moi']:.0f})")
    if "khoang_tho_toi_thieu" in bat and so_do.get("khoang_tho") and so_do["khoang_tho"]["phan_tram_khong_do_hoa"] < bat["khoang_tho_toi_thieu"]:
        cb("khoang_tho_toi_thieu", f"{so_do['khoang_tho']['phan_tram_khong_do_hoa']:.0f}% thời lượng không có đồ hoạ (hồ sơ: ≥ {bat['khoang_tho_toi_thieu']:.0f}%)")
    if "so_kieu_do_hoa_toi_da" in bat and so_do.get("so_kieu") and so_do["so_kieu"]["moi_phut"] > bat["so_kieu_do_hoa_toi_da"]:
        cb("so_kieu_do_hoa_toi_da", f"{so_do['so_kieu']['so_kieu']} kiểu đồ hoạ ({so_do['so_kieu']['moi_phut']}/phút; hồ sơ: ≤ {bat['so_kieu_do_hoa_toi_da']:.0f})")
    if "trinh_dien_toi_da" in bat and so_do.get("trinh_dien") and so_do["trinh_dien"]["moi_phut"] > bat["trinh_dien_toi_da"]:
        cb("trinh_dien_toi_da", f"{so_do['trinh_dien']['so']} hiệu ứng trình diễn ({so_do['trinh_dien']['moi_phut']}/phút; hồ sơ: ≤ {bat['trinh_dien_toi_da']:.0f}): " + ", ".join(so_do["trinh_dien"]["lop"]))

    if bat:
        chu_the = [l for l in kh.get("lop") or [] if l["kieu"] in ("chu", "the")]
        if "mat_do_toi_da" in bat and chu_the:
            moc = sorted(set([l["t0"] for l in chu_the] + [l["t1"] for l in chu_the]))
            dinh = max(sum(1 for l in chu_the if l["t0"] <= t < l["t1"]) for t in moc)
            if dinh > bat["mat_do_toi_da"]:
                cb("mat_do_toi_da", f"có lúc {dinh} lớp chữ cùng hiện (hồ sơ: ≤ {bat['mat_do_toi_da']:.0f})")
        if "khoang_trong_toi_da" in bat and dur:
            ds = sorted([(l["t0"], l["t1"]) for l in kh.get("lop") or []])
            cuoi, lon = 0.0, 0.0
            for a, b in ds:
                lon = max(lon, a - cuoi); cuoi = max(cuoi, b)
            lon = max(lon, dur - cuoi)
            if lon > bat["khoang_trong_toi_da"]:
                cb("khoang_trong_toi_da", f"khoảng trống dài nhất {lon:.1f}s (hồ sơ: ≤ {bat['khoang_trong_toi_da']:.0f}s)")
        if "so_font_toi_da" in bat and len(fonts) > bat["so_font_toi_da"]:
            cb("so_font_toi_da", f"dùng {len(fonts)} font (hồ sơ: ≤ {bat['so_font_toi_da']:.0f})")
        if "so_mau_toi_da" in bat:
            ms = set()
            for l in chu_the:
                kd = l["kieu_dang"]
                for m in (kd.get("mau"), (kd.get("nen") or {}).get("mau"), (kd.get("chu") or {}).get("mau")):
                    if m and m[:7].upper() not in ("#FFFFFF", "#000000"):
                        ms.add(m[:7].upper())
            if len(ms) > bat["so_mau_toi_da"]:
                cb("so_mau_toi_da", f"dùng {len(ms)} màu chữ/nền (hồ sơ: ≤ {bat['so_mau_toi_da']:.0f})")
        if "co_chu_toi_thieu" in bat:
            for l in chu_the:
                co = _so(l["kieu_dang"].get("co") or (l["kieu_dang"].get("chu") or {}).get("co"), 0) * W / 1080
                if co and co < bat["co_chu_toi_thieu"]:
                    cb("co_chu_toi_thieu", f"cỡ chữ {co:.0f}px (hồ sơ: ≥ {bat['co_chu_toi_thieu']:.0f}px)", l["id"])
        if "bia_so_chu" in bat and (kh.get("bia") or {}).get("thiet_ke"):
            n = sum(_so_tu(c.get("text")) for c in (kh["bia"]["thiet_ke"].get("chu") or []) if isinstance(c, dict))
            if n > bat["bia_so_chu"]:
                cb("bia_so_chu", f"bìa có {n} từ (hồ sơ: ≤ {bat['bia_so_chu']:.0f})", "bia")
        if "giay_moi_tu_chu" in bat:
            for l in chu_the:
                spt = (l["t1"] - l["t0"]) / _so_tu(l["noi_dung"].get("text"))
                if spt < bat["giay_moi_tu_chu"]:
                    cb("giay_moi_tu_chu", f"{spt:.2f} s/từ (hồ sơ: ≥ {bat['giay_moi_tu_chu']})", l["id"])
        if "hook_toi_da" in bat and chu_the and min(l["t0"] for l in chu_the) > bat["hook_toi_da"]:
            cb("hook_toi_da", f"lớp chữ đầu ở {min(l['t0'] for l in chu_the):.1f}s (hồ sơ: ≤ {bat['hook_toi_da']}s)")
        if "phu_de_toi_da_chu" in bat and pd.get("toi_da_chu") and int(pd["toi_da_chu"]) > bat["phu_de_toi_da_chu"]:
            cb("phu_de_toi_da_chu", f"phụ đề {pd.get('toi_da_chu')} ký tự/cụm (hồ sơ: ≤ {bat['phu_de_toi_da_chu']:.0f})", "phu_de")
        if "camera_toi_da" in bat and dur and len(kh.get("camera") or []) / (dur / 60) > bat["camera_toi_da"]:
            cb("camera_toi_da", f"{len(kh['camera'])} keyframe camera / {dur / 60:.1f} phút (hồ sơ: ≤ {bat['camera_toi_da']:.0f}/phút)")
        if "sfx_toi_da" in bat and dur and len((kh.get("am") or {}).get("sfx") or []) / (dur / 60) > bat["sfx_toi_da"]:
            cb("sfx_toi_da", f"{len(kh['am']['sfx'])} sfx / {dur / 60:.1f} phút (hồ sơ: ≤ {bat['sfx_toi_da']:.0f}/phút)")
        if "khong_nen_moi" in bat and kh.get("nen_moi"):
            cb("khong_nen_moi", "hồ sơ bật khong_nen_moi nhưng công thức có nen_moi")

    # ---- kết quả
    if doi_ke_hoach or True:
        kh["may_sua"] = may_sua
        chung.ghi_json(os.path.join(du_an, "ke-hoach.json"), kh)
    kq = {"loi": loi, "may_sua": may_sua, "canh_bao": canh_bao, "tra_kho": kh.get("tra_kho") or [],
          "tom_tat": {"so_loi": len(loi), "so_may_sua": len(may_sua), "so_canh_bao": len(canh_bao), "so_lop": len(kh.get("lop") or []), "dur": dur},
          "luc": time.strftime("%Y-%m-%d %H:%M:%S")}
    cu = chung.doc_json(os.path.join(du_an, "kiem.json")) or {}
    if cu.get("ky_thuat"):
        kq["ky_thuat"] = cu["ky_thuat"]
    chung.ghi_json(os.path.join(du_an, "kiem.json"), kq)
    return kq


def ghi_loi_dung(du_an, loi):
    """lỗi engine phát hiện LÚC DỰNG (meta sprite: web_loi của lớp web, lớp py/mẫu lỗi, de_mat không cứu được, chu_tran_khung…)
    → kiem.json["loi_dung"] + chép vào "canh_bao" (tiền tố "lúc dựng") để bước trọn in ra cho AI sửa."""
    p = os.path.join(du_an, "kiem.json")
    d = chung.doc_json(p) or {"loi": [], "may_sua": [], "canh_bao": []}
    da, ds = set(), []
    for l in loi or []:
        if not isinstance(l, dict):
            continue
        k = (l.get("id"), l.get("lop"), l.get("mo_ta"))
        if k in da:
            continue
        da.add(k); ds.append({k2: l.get(k2) for k2 in ("id", "lop", "t", "mo_ta") if l.get(k2) is not None})
    d["loi_dung"] = ds
    d["canh_bao"] = [c for c in d.get("canh_bao") or [] if c.get("nguon") != "dung"] +         [dict(l, mo_ta="lúc dựng: " + str(l.get("mo_ta", "")), nguon="dung") for l in ds]
    chung.ghi_json(p, d)
    return ds


# ---------------------------------------------------------------- kiểm kỹ thuật sau dựng
def kiem_ky_thuat(video, timeout=600):
    """1 lượt ffmpeg: -vf scale=540:-2,fps=4,blackdetect,freezedetect + -af ebur128 → khung_den/dong_bang/lufs/peak."""
    ff = chung.duong("ffmpeg")
    ng_den = float(_nguong("khung_den", "giay", 0.5))
    ng_db = float(_nguong("dong_bang", "giay", 3))
    info = chung.ffprobe(video) or {}
    cmd = [ff, "-hide_banner", "-nostats", "-i", video, "-vf", f"scale=540:-2,fps=4,blackdetect=d={ng_den}:pic_th=0.98,freezedetect=n=-60dB:d={ng_db}"]
    if info.get("co_am", True):
        cmd += ["-af", "ebur128=peak=true"]
    cmd += ["-f", "null", "-"]
    ma, out, err = chung.sh(cmd, timeout=timeout)
    kq = {"khung_den": [], "dong_bang": [], "lufs": None, "peak": None, "lra": None, "loi": [], "canh_bao": [], "ma": ma}
    for m in re.finditer(r"black_start:([0-9.]+)\s+black_end:([0-9.]+)", err):
        kq["khung_den"].append([round(float(m.group(1)), 2), round(float(m.group(2)), 2)])
    fs = re.findall(r"freeze_start:\s*([0-9.]+)", err)
    fe = re.findall(r"freeze_end:\s*([0-9.]+)", err)
    for i, a in enumerate(fs):
        b = float(fe[i]) if i < len(fe) else float(info.get("dur") or a)
        kq["dong_bang"].append([round(float(a), 2), round(b, 2)])
    tk = err[err.rfind("Summary:"):] if "Summary:" in err else err      # chỉ đọc phần tổng kết (dòng đầu I: -70 lúc chưa có tiếng)
    m = re.search(r"I:\s*(-?[0-9.]+)\s*LUFS", tk)
    if m:
        kq["lufs"] = float(m.group(1))
    m = re.search(r"LRA:\s*(-?[0-9.]+)\s*LU", tk)
    if m:
        kq["lra"] = float(m.group(1))
    m = re.search(r"Peak:\s*(-?[0-9.]+)\s*dBFS", tk)
    if m:
        kq["peak"] = float(m.group(1))
    for a, b in kq["khung_den"]:
        kq["loi"].append({"id": "khung_den", "lop": "video", "t": a, "mo_ta": f"đoạn đen {a}–{b}s"})
    for a, b in kq["dong_bang"]:
        kq["canh_bao"].append({"id": "dong_bang", "lop": "video", "t": a, "mo_ta": f"hình đứng yên {a}–{b}s (ảnh chèn cố ý thì bỏ qua)"})
    if kq["peak"] is not None and kq["peak"] > float(_nguong("am_qua_to", "dbtp", -1.0)):
        kq["loi"].append({"id": "am_qua_to", "lop": "am", "t": 0, "mo_ta": f"true peak {kq['peak']} dBTP > −1"})
    if kq["lufs"] is not None:
        if kq["lufs"] > float(_nguong("am_qua_to", "lufs_toi_da", -12)):
            kq["loi"].append({"id": "am_qua_to", "lop": "am", "t": 0, "mo_ta": f"{kq['lufs']} LUFS quá to"})
        elif kq["lufs"] < float(_nguong("am_qua_nho", "lufs_toi_thieu", -22)):
            kq["canh_bao"].append({"id": "am_qua_nho", "lop": "am", "t": 0, "mo_ta": f"{kq['lufs']} LUFS hơi nhỏ"})
    if ma != 0 and not err.strip():
        kq["canh_bao"].append({"id": "kiem_ky_thuat", "lop": "video", "mo_ta": "ffmpeg không chạy được"})
    return kq


def ghi_ky_thuat(du_an, kt):
    p = os.path.join(du_an, "kiem.json")
    d = chung.doc_json(p) or {"loi": [], "may_sua": [], "canh_bao": []}
    d["ky_thuat"] = {k: kt.get(k) for k in ("khung_den", "dong_bang", "lufs", "peak", "lra")}
    d["loi"] = [l for l in d.get("loi") or [] if l.get("id") not in ("khung_den", "am_qua_to")] + kt.get("loi", [])
    d["canh_bao"] = [l for l in d.get("canh_bao") or [] if l.get("id") not in ("dong_bang", "am_qua_nho", "kiem_ky_thuat")] + kt.get("canh_bao", [])
    chung.ghi_json(p, d)
    return d


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "kt":
        print(json.dumps(kiem_ky_thuat(sys.argv[2]), ensure_ascii=False, indent=1))
    elif len(sys.argv) > 1:
        da = sys.argv[1]
        print(json.dumps(kiem(da, os.path.join(da, "ke-hoach.json")), ensure_ascii=False, indent=1))
