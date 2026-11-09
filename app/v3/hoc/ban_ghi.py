# -*- coding: utf-8 -*-
"""BẢN GHI THI CÔNG (tầng 1 của bộ học 1.2.20) — video mẫu → dòng thời gian ĐẦY ĐỦ viết bằng đúng ngôn ngữ lớp của máy dựng
(cong-thuc.json), chạy lại được. Máy đo mọi vệt chữ (không giới hạn 24 sự kiện như dong_hoc), gom thành CỤM (nhiều dòng hiện
gần nhau), mỗi dòng: vai trong cụm, cỡ/màu/đậm/HOA, góc xoay, cách vào/ra ở mức ĐƯỜNG CONG (hướng, quãng px, thời lượng, ease,
vượt đích, nhoè theo hướng), trễ so với dòng đầu cụm, nằm trước/sau người, neo so với mặt. Thêm: cắt/punch-in/flash của nền,
tiếng động gắn lúc lớp vào, cụm bám từ nào của lời.

Máy chỉ ĐO và DỊCH sang khoá engine; không chọn gu, không bịa số. Chỗ máy không thấy được (họ font) ghi `font_goi_y` + "AI:" để
AI xác nhận bằng ảnh cận chữ. Chữ của video mẫu chỉ nằm trong bản ghi để DỰNG LẠI SO VỚI GỐC — ngữ pháp (tầng 2) không mang chữ.

1.2.21: · MỘT lượt giải mã cho mọi cửa sổ (dong_hoc.cua_so_hang_loat), OCR/mặt nạ người qua cache dùng chung với dong_hoc
        · 15 khung/s cho vệt không "lớn dần" (gõ chữ / từng từ vẫn 30 để đếm từ)
        · chỉ đo dày vệt ĐẠI DIỆN mỗi chữ ký (cùng hộp/cỡ/vai); vệt còn lại nhận số đo của đại diện + OCR chữ riêng (`_do.gan_tu`)
        · nhiễu chữ web/cảnh/áo: KHÔNG bỏ — ghi `nguon_nghi_ngo` ("web" | "canh" | "ao") theo dấu hiệu vật lý, ngữ pháp bỏ qua nhưng vẫn liệt kê
        · giá trị gu của engine (viền/bóng/cách dòng/đậm 800-600-400) không ghi vào dòng — dòng mang SỐ ĐO (`_do`), bản engine
          (ban-ghi-lop.json) dịch từ số đo lúc ghi ra

  tao(video, thu_muc, loi=None, log=print, dh=None, fps_day=None, canh_day=None) → {"json": ban-ghi.json, "lop": ban-ghi-lop.json, "md": ban-ghi.md, "ban_ghi"}
"""
import os, sys, json, math, time, re, wave, subprocess
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung as C

PHIEN_BAN = 2
FPS_DAY = 15                     # 1.2.21: 30 → 15 cho vệt không "lớn dần"
FPS_LON_DAN = 30                 # vệt lớn dần (gõ chữ / từng từ / mặt nạ) giữ 30 để đếm từ/ký tự từng khung
CANH_DAY = 600
MAX_VET = 140                    # mặc định; chạy thật đọc cau_hinh().get("hoc_max_vet", 140)

VAI_CUM = ("nhan", "tu_khoa", "cam_xuc", "phu")


_DH = None


def _dh():
    """nạp hoc/dong_hoc.py theo đường dẫn (an toàn cả khi `hoc` trên sys.path là tệp hoc.py); dùng chung mô-đun với hoc.py để chung cache"""
    global _DH
    if _DH is None:
        import importlib.util
        if "hoc_dong_hoc" in sys.modules:
            _DH = sys.modules["hoc_dong_hoc"]
            return _DH
        try:
            from hoc import dong_hoc as m            # cùng tiến trình với hoc.py → cùng một mô-đun, cùng cache
            _DH = m
            return _DH
        except Exception:
            pass
        sp = importlib.util.spec_from_file_location("hoc_dong_hoc", os.path.join(os.path.dirname(os.path.abspath(__file__)), "dong_hoc.py"))
        m = importlib.util.module_from_spec(sp); sys.modules["hoc_dong_hoc"] = m; sp.loader.exec_module(m)
        _DH = m
    return _DH


def _cfg():
    try:
        return C.cau_hinh() or {}
    except Exception:
        return {}


# ─────────────────────────────────────────────────────────────── 1) đo dày từng vệt
def _goc_nghieng(muc):
    """mặt nạ mực chữ → góc nghiêng (độ, dương = xoay theo chiều kim đồng hồ) của dòng chữ; None nếu không đủ dài"""
    ys, xs = np.nonzero(muc)
    if len(xs) < 80:
        return None
    pts = np.stack([xs, ys], 1).astype(np.float32)
    (cx, cy), (w, h), ang = cv2.minAreaRect(pts)
    if w < h:
        w, h = h, w; ang += 90
    if w < 2.2 * max(h, 1):
        return None
    ang = ((ang + 90) % 180) - 90
    if ang > 45:
        ang -= 90
    if ang < -45:
        ang += 90
    return round(float(ang), 1)


def _muc_chu(truoc, sau, hop_roi, nguoi=None):
    """mặt nạ mực chữ lúc đủ (điểm đổi so với vắng, trong hộp, không tính người)"""
    x0, y0, x1, y1 = [int(v) for v in hop_roi]
    dn = np.abs(sau.astype(np.int16) - truoc.astype(np.int16)).max(2)
    m = np.zeros(dn.shape, bool)
    m[y0:y1, x0:x1] = dn[y0:y1, x0:x1] > 45
    if nguoi is not None and nguoi.shape == dn.shape:
        m &= ~(nguoi > 0.5)
    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
    return m


def _nhoe_dong(do, kieu):
    """chuỗi `net` (độ nét tương đối từng khung) trong lúc chuyển → hệ số nhoè theo hướng (0, 1, 2, 3) — chỉ với slide/pop"""
    if kieu not in ("slide", "pop") or not do.get("chuoi"):
        return 0.0
    ch = [c for c in do["chuoi"] if c.get("alpha", 0) > 0.3 and c.get("net") is not None]
    if len(ch) < 2:
        return 0.0
    giua = [c["net"] for c in ch[:-1]]
    if not giua:
        return 0.0
    nmin = min(giua)
    if nmin < 0.25:
        return 3.0
    if nmin < 0.45:
        return 2.0
    if nmin < 0.7:
        return 1.0
    return 0.0


def _dich_chuyen(do, hop_px_1080, kieu):
    """chuỗi hộp (chuẩn hoá theo hộp đủ) → quãng dịch (px@1080) từ khung hiện đầu tới đủ: (dx, dy)"""
    ch = [c for c in (do.get("chuoi") or []) if c.get("x") is not None and c.get("alpha", 0) > 0.15]
    if not ch:
        return 0.0, 0.0
    w, h = hop_px_1080[2] - hop_px_1080[0], hop_px_1080[3] - hop_px_1080[1]
    c0 = ch[0]
    dx, dy = -c0["x"] * w, -c0["y"] * h          # vị trí đầu so với đích (đích = 0) → tu{x,y} = -(đích − đầu)
    if kieu != "slide":
        return 0.0, 0.0
    return round(float(-dx), 0), round(float(-dy), 0)


def _engine_vao(do, hop_px, dai_dong):
    """số đo _do_chuyen_dong → anim.vao của engine + nhoe_dong"""
    kieu = do.get("kieu")
    dai = float(do.get("dai") or 0.0)
    ease = do.get("ease") or "out"
    dac = do.get("dac_trung") or {}
    v = {"kieu": "fade", "dai": round(max(0.08, dai), 2), "ease": ease, "tu": {"opacity": 0}}
    nhoe = 0.0
    if kieu in (None, "khong_do_duoc"):
        return None, 0.0
    if kieu == "none":
        return {"kieu": "none", "dai": 0}, 0.0
    if kieu == "pop":
        s0 = float(dac.get("ti_le_dau") or (1.25 if do.get("huong") == "tu_to" else 0.6))
        v = {"kieu": "pop", "dai": round(max(0.1, dai), 2), "ease": ("back" if dac.get("vuot", 0) > 0.03 else ease), "tu": {"scale": round(s0, 2), "opacity": 0}}
        nhoe = _nhoe_dong(do, "pop")
    elif kieu == "slide":
        dx, dy = _dich_chuyen(do, hop_px, "slide")
        if abs(dx) < 8 and abs(dy) < 8:               # máy ghi slide nhưng không đo được quãng → theo hướng, quãng = 2 cao dòng
            hd = {"tu_tren": (0, -2 * dai_dong), "tu_duoi": (0, 2 * dai_dong), "tu_trai": (-2 * dai_dong, 0), "tu_phai": (2 * dai_dong, 0)}
            dx, dy = hd.get(do.get("huong"), (0, -2 * dai_dong))
        v = {"kieu": "slide", "dai": round(max(0.1, dai), 2), "ease": ("back" if dac.get("vuot", 0) > 0.03 else ease), "tu": {"x": int(dx), "y": int(dy), "opacity": 0}}
        nhoe = _nhoe_dong(do, "slide")
    elif kieu == "blur":
        v = {"kieu": "blur", "dai": round(max(0.1, dai), 2), "ease": ease, "tu": {"blur": 14, "opacity": 0}}
    elif kieu == "typewriter":
        v = {"kieu": "typewriter", "dai": round(max(0.15, dai), 2), "ease": "linear"}
    elif kieu == "word_by_word":
        v = {"kieu": "fade", "dai": round(max(0.08, min(0.3, dac.get("giay_moi_tu") or 0.15)), 2), "ease": "out", "tu": {"opacity": 0, "y": 10},
             "_tach": "tu", "_so_le": round(float(dac.get("giay_moi_tu") or 0.2), 2)}
    elif kieu == "mask_reveal":
        hd = {"trai_sang_phai": "phai", "phai_sang_trai": "trai", "tren_xuong": "xuong", "duoi_len": "len"}
        v = {"kieu": "wipe", "dai": round(max(0.1, dai), 2), "ease": ease, "huong": hd.get(do.get("huong"), "phai")}
    elif kieu == "doi_ky_tu":
        v = {"kieu": "typewriter", "dai": round(max(0.15, dai), 2), "ease": "linear", "_do_may": "doi_ky_tu"}
    elif kieu == "fade":
        v = {"kieu": "fade", "dai": round(max(0.08, dai), 2), "ease": ease, "tu": {"opacity": 0}}
    if dac.get("kem_fade") and "tu" in v:
        v["tu"]["opacity"] = 0
    return v, nhoe


def _engine_ra(do, hop_px, dai_dong):
    if not do or do.get("kieu") in (None, "khong_do_duoc"):
        return None
    kieu = do.get("kieu"); dai = float(do.get("dai") or 0.0); ease = do.get("ease") or "in"
    if kieu == "none":
        return {"kieu": "none", "dai": 0}
    if kieu == "slide":
        dx, dy = _dich_chuyen(do, hop_px, "slide")
        if abs(dx) < 8 and abs(dy) < 8:
            hd = {"tu_tren": (0, -2 * dai_dong), "tu_duoi": (0, 2 * dai_dong), "tu_trai": (-2 * dai_dong, 0), "tu_phai": (2 * dai_dong, 0)}
            dx, dy = hd.get(do.get("huong"), (-3 * dai_dong, 0))
        return {"kieu": "slide", "dai": round(max(0.1, dai), 2), "ease": ease, "toi": {"x": int(dx), "y": int(dy), "opacity": 0}}
    if kieu == "pop":
        s0 = float((do.get("dac_trung") or {}).get("ti_le_dau") or 0.7)
        return {"kieu": "pop", "dai": round(max(0.1, dai), 2), "ease": ease, "toi": {"scale": round(s0, 2), "opacity": 0}}
    if kieu == "blur":
        return {"kieu": "blur", "dai": round(max(0.1, dai), 2), "ease": ease, "toi": {"blur": 14, "opacity": 0}}
    if kieu == "mask_reveal":
        return {"kieu": "wipe", "dai": round(max(0.1, dai), 2), "ease": ease}
    return {"kieu": "fade", "dai": round(max(0.08, dai), 2), "ease": ease, "toi": {"opacity": 0}}


def _lon_dan(v):
    return (v["hop_dau"][2] - v["hop_dau"][0]) < 0.8 * (v["hop"][2] - v["hop"][0]) or (v["hop_dau"][3] - v["hop_dau"][1]) < 0.75 * (v["hop"][3] - v["hop"][1])


def _cua_so_vet(v, dur):
    """mốc cửa sổ VÀO (a, b, t_co) và RA (a2, b2 | None) của một vệt — cùng công thức với dong_hoc"""
    lon_dan = _lon_dan(v)
    a = v["t_dau"] - 1.0
    b = (min(v["t_cuoi"] + 0.15, v["t_dau"] + 3.5) if lon_dan else min(v["t_dau"] + 1.0, v["t_cuoi"] + 0.1))
    b = max(b, v["t_dau"] + 0.3)
    t_co = b - 0.02 if lon_dan else min(v["t_dau"] + 0.8, v["t_cuoi"])
    ra = None
    if v["t_ra"] < dur - 0.15:
        ra = (max(v["t_dau"] + 0.1, v["t_cuoi"] - 0.8), min(dur, v["t_ra"] + 0.4))
    return lon_dan, a, b, t_co, ra


def _so_voi_mat(hb, mat):
    """hộp chuẩn hoá + mặt (TÂM) → so_voi_mat như dong_hoc._thuoc_tinh (dùng cho vệt nhận số đo từ đại diện)"""
    if not mat:
        return None
    cx = (hb[0] + hb[2]) / 2
    tren_dau, cam = mat["y"] - mat["h"] / 2, mat["y"] + mat["h"] / 2
    if hb[3] <= tren_dau + 0.15 * mat["h"]:
        vt = "tren_dau"; kc = (tren_dau - hb[3]) / mat["h"]
    elif hb[1] >= cam - 0.1 * mat["h"]:
        kc = (hb[1] - cam) / mat["h"]
        vt = "duoi_cam" if kc < 1.0 else "ngang_nguc" if kc < 3.5 else "duoi_xa"
    else:
        vt = "ngang_mat"; kc = 0.0
    che = hb[0] < mat["x"] + mat["w"] / 2 and hb[2] > mat["x"] - mat["w"] / 2 and vt == "ngang_mat"
    return {"vi_tri": vt, "khoang_theo_cao_mat": round(kc, 2), "lech_x_theo_rong_mat": round((cx - mat["x"]) / max(mat["w"], 1e-3), 2), "che_mat": bool(che)}


def _do_vet_vao(DH, video, info, v, ts_, crops, nho_, roi, Wd, Hd, fps, log, nguon_alpha=None):
    """pha VÀO của một vệt (cửa sổ đã giải mã) → (kết quả, ngữ cảnh cho pha RA) ; kết quả có "bo_qua" nếu không đo được"""
    hop = v["hop"]
    lon_dan, a, b, t_co, _ = _cua_so_vet(v, float(info.get("dur") or 0))
    if len(crops) < 4:
        return {"bo_qua": "cửa sổ rỗng"}, None
    k_sau = int(np.argmin([abs(t - t_co) for t in ts_]))
    hr = [hop[0] * Wd - roi[0], hop[1] * Hd - roi[1], hop[2] * Wd - roi[0], hop[3] * Hd - roi[1]]
    pad = 0.15 * (hr[3] - hr[1])
    hr = [max(0, hr[0] - pad), max(0, hr[1] - pad), min(crops[0].shape[1], hr[2] + pad), min(crops[0].shape[0], hr[3] + pad)]
    o_du = DH.ocr_cs(crops[k_sau], ts_[k_sau], roi, True)
    o_du = [o for o in o_du if DH._chong_nho(o["hop"], hr) > 0.4 and (o["hop"][3] - o["hop"][1]) > 0.012 * Hd and o["diem"] >= 0.5]
    if not o_du:
        return {"bo_qua": "không đọc được chữ lúc đủ"}, None
    nguoi = None
    try:                                   # 1.2.21: mặt nạ người từ lưới MODNet dùng chung (một lần mỗi ô lưới), cắt theo roi
        nguoi = DH.nguoi_tai(video, info, ts_[k_sau], Wd, Hd, roi=roi, nguon=nguon_alpha, log=log)
    except Exception as ex:
        log(f"    (không tách người: {str(ex)[:60]})")
    do_vao = DH._do_chuyen_dong(ts_, crops, k_sau, hr, fps, ocr_on=True, dong_sau=o_du or None, nguoi=nguoi, roi=roi)
    mat = DH._mat(nho_[k_sau])
    tinh = DH._thuoc_tinh(crops[0], crops[k_sau], hr, roi, Wd, Hd, mat, nguoi=nguoi, ocr_dong=o_du)
    vung_nen = tinh.pop("_vung_nen", None); mau_nen = tinh.pop("_mau_nen_bgr", None)
    vao_nen = None
    if vung_nen is not None and mau_nen is not None:
        vao_nen = {k: x for k, x in do_vao.items() if not k.startswith("_") and k != "chuoi"}
        trong = cv2.erode(vung_nen.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        do_chu = DH._do_chuyen_dong(ts_, crops, k_sau, hr, fps, ocr_on=True, dong_sau=o_du or None, truoc_mau=mau_nen, vung=trong, nguoi=nguoi, roi=roi)
        if do_chu.get("kieu") not in (None, "khong_do_duoc"):
            do_vao = do_chu
    muc = _muc_chu(crops[0], crops[k_sau], hr, nguoi)
    goc = _goc_nghieng(muc)
    chu = " ".join(o["chu"] for o in sorted(o_du, key=lambda r: (round(r["hop"][1] / 12), r["hop"][0])))
    r = {"tinh": tinh, "vao": {k: x for k, x in do_vao.items() if not k.startswith("_")}, "ra": None, "vao_nen": vao_nen,
         "goc": goc, "chu": chu, "mat": mat, "Wd": Wd, "Hd": Hd, "fps": fps}
    return r, {"hr": hr, "roi": roi, "o_du": o_du, "nguoi": nguoi}


def _do_vet_ra(DH, v, ctx, ts2, crops2, roi2, fps):
    """pha RA (cửa sổ quanh lúc biến mất) → số đo ra hoặc None"""
    if not ctx or len(crops2) < 4 or roi2 != ctx["roi"]:
        return None
    a2 = ts2[0]
    k2 = int(np.argmin([abs(t - v["t_cuoi"] + 0.05) for t in ts2])) if v["t_cuoi"] > a2 else 0
    do_ra = DH._do_chuyen_dong(ts2, crops2, k2, ctx["hr"], fps, ocr_on=False, nguoc=True, dong_sau=ctx["o_du"] or None, nguoi=ctx["nguoi"], roi=roi2)
    do_ra = {k: x for k, x in do_ra.items() if not k.startswith("_")}
    if do_ra.get("t_bat_dau") is not None:
        do_ra["t_het"] = do_ra.pop("t_bat_dau"); do_ra["t_bat_dau"] = do_ra.pop("t_du")
    return do_ra


def _chu_ky_vet(v):
    """chữ ký vật lý của vệt: vai · cỡ dòng (bước 0,5 % khung) · tâm hộp (bước 5 %) · rộng (bước 10 %) → vệt cùng chữ ký chỉ đo dày một lần"""
    h = v["hop"]
    return (v.get("vai"), int(round(v["cao_dong"] / 0.005)), int(round((h[0] + h[2]) / 2 / 0.05)), int(round((h[1] + h[3]) / 2 / 0.05)), int(round((h[2] - h[0]) / 0.1)))


def _gan_tu_dai_dien(DH, dd, v, ts_, crops, nho_, roi, Wd, Hd, v_dd):
    """vệt cùng chữ ký với đại diện đã đo: không đo dày lại — OCR một khung lấy CHỮ + hộp riêng, mặt riêng; số đo vào/ra/tĩnh chép từ đại diện"""
    if len(crops) < 2:
        return {"bo_qua": "cửa sổ rỗng"}
    hop = v["hop"]
    _, a, b, t_co, _ = _cua_so_vet(v, 1e9)
    k_sau = int(np.argmin([abs(t - t_co) for t in ts_]))
    hr = [hop[0] * Wd - roi[0], hop[1] * Hd - roi[1], hop[2] * Wd - roi[0], hop[3] * Hd - roi[1]]
    pad = 0.15 * (hr[3] - hr[1])
    hr = [max(0, hr[0] - pad), max(0, hr[1] - pad), min(crops[0].shape[1], hr[2] + pad), min(crops[0].shape[0], hr[3] + pad)]
    o_du = DH.ocr_cs(crops[k_sau], ts_[k_sau], roi, True)
    o_du = [o for o in o_du if DH._chong_nho(o["hop"], hr) > 0.4 and (o["hop"][3] - o["hop"][1]) > 0.012 * Hd and o["diem"] >= 0.5]
    if not o_du:
        return {"bo_qua": "không đọc được chữ lúc đủ"}
    chu = " ".join(o["chu"] for o in sorted(o_du, key=lambda r: (round(r["hop"][1] / 12), r["hop"][0])))
    tinh = json.loads(json.dumps(dd["tinh"]))
    x0 = min(o["hop"][0] for o in o_du); y0 = min(o["hop"][1] for o in o_du); x1 = max(o["hop"][2] for o in o_du); y1 = max(o["hop"][3] for o in o_du)
    hb = [round((roi[0] + x0) / Wd, 4), round((roi[1] + y0) / Hd, 4), round((roi[0] + x1) / Wd, 4), round((roi[1] + y1) / Hd, 4)]
    # hộp mực của đại diện hẹp hơn hộp OCR một chút (OCR có lề) → thu hộp OCR theo cùng tỉ lệ đại diện
    hd_ocr = (dd.get("_hop_ocr") or hb)
    hd_muc = dd["tinh"].get("hop") or hd_ocr
    if (hd_ocr[3] - hd_ocr[1]) > 1e-4:
        ty = (hd_muc[3] - hd_muc[1]) / (hd_ocr[3] - hd_ocr[1])
        cy = (hb[1] + hb[3]) / 2; hh = (hb[3] - hb[1]) * min(1.0, max(0.5, ty))
        hb = [hb[0], round(cy - hh / 2, 4), hb[2], round(cy + hh / 2, 4)]
    tinh["hop"] = hb
    tinh["tam"] = [round((hb[0] + hb[2]) / 2, 4), round((hb[1] + hb[3]) / 2, 4)]
    tinh["rong_ti_le"] = round(hb[2] - hb[0], 4)
    tinh["chu_ocr"] = chu[:80]; tinh["so_dong"] = len(o_du)
    tinh["so_ky_tu"] = len(DH._khong_dau(chu)); tinh["so_tu"] = DH._so_tu(chu)
    mat = DH._mat(nho_[k_sau])
    svm = _so_voi_mat(hb, mat)
    if svm:
        tinh["so_voi_mat"] = svm; tinh["mat"] = mat
    else:
        tinh.pop("so_voi_mat", None); tinh.pop("mat", None)
    # mốc thời gian vào của vệt này = mốc đại diện dịch theo t_dau
    lech = v["t_dau"] - v_dd["t_dau"]
    vao = json.loads(json.dumps(dd["vao"]))
    for k in ("t_bat_dau", "t_du"):
        if vao.get(k) is not None:
            vao[k] = round(float(vao[k]) + lech, 3)
    vao.pop("chuoi", None)
    return {"tinh": tinh, "vao": vao, "ra": dd.get("ra"), "vao_nen": dd.get("vao_nen"), "goc": dd.get("goc"), "chu": chu, "mat": mat,
            "Wd": Wd, "Hd": Hd, "fps": dd.get("fps"), "gan_tu": dd.get("_id")}


def _phan_lai_phu_de(vet):
    """dải dong_hoc gán 'phu_de' chỉ là PHỤ ĐỀ THẬT khi cỡ chữ đồng đều (cv ≤ 0.22) và hiếm khi có 2 cỡ cùng lúc;
    video kiểu chữ-nhấn-theo-lời (nhãn nhỏ + từ khoá lớn cùng dải) thì đó là CHỮ PHỦ, phải ghi từng dòng"""
    bands = {}
    for v in vet:
        if v.get("vai") == "phu_de":
            bands.setdefault(v.get("dai_y"), []).append(v)
    for cy, vs in bands.items():
        cao = np.array([v["cao_dong"] for v in vs], float)
        cv = float(cao.std() / max(cao.mean(), 1e-6))
        vs2 = sorted(vs, key=lambda v: v["t_dau"]); chong = 0
        for i, a in enumerate(vs2):
            for b in vs2[i + 1:]:
                if b["t_dau"] >= a["t_ra"] - 0.1:
                    break
                if abs(a["cao_dong"] - b["cao_dong"]) > 0.3 * max(a["cao_dong"], b["cao_dong"]):
                    chong += 1
        if cv > 0.22 or chong > max(1, 0.05 * len(vs)):
            for v in vs:
                v["vai"] = "chu"; v["_tu_dai_phu_de"] = True
    return vet


def _rac_ocr(chu):
    """OCR rác: < 2 chữ/số Latin, hoặc có ký tự CJK"""
    if re.search(r"[　-鿿가-힯]", chu or ""):
        return True
    return len(re.findall(r"[A-Za-z0-9À-ỹ]", chu or "")) < 2


# ─────────────────────────────────────────────────────────────── 2) gom cụm
def _gom_cum(dong):
    """dòng đã đo (có t0, t1, hop) → cụm: dòng vào cách nhau ≤ 1.3 s, hộp gần nhau (khe ≤ 1.6 × cao dòng lớn), thời gian chồng"""
    dong = sorted(dong, key=lambda d: d["t0"])
    cum = []
    for d in dong:
        h = d["hop"][3] - d["hop"][1]
        gan = None
        for c in cum:
            if d["t0"] - c["t0"] > 1.3 or d["t0"] > c["t1_min"] + 0.05:
                continue
            hc = c["hop"]
            hmax = max(h, max(x["hop"][3] - x["hop"][1] for x in c["dong"]))
            khe_y = max(d["hop"][1] - hc[3], hc[1] - d["hop"][3], 0.0)
            khe_x = max(d["hop"][0] - hc[2], hc[0] - d["hop"][2], 0.0)
            if khe_y <= 1.6 * hmax and khe_x <= 2.5 * hmax:
                gan = c; break
        if gan:
            gan["dong"].append(d); gan["hop"] = DH_hop_chung(gan["hop"], d["hop"])
            gan["t1_min"] = min(gan["t1_min"], d["t1"]); gan["t1"] = max(gan["t1"], d["t1"])
        else:
            cum.append({"t0": d["t0"], "t1": d["t1"], "t1_min": d["t1"], "hop": list(d["hop"]), "dong": [d]})
    for i, c in enumerate(cum, 1):
        c["id"] = f"c{i:02d}"
        c.pop("t1_min", None)
        c["dong"].sort(key=lambda d: (d["t0"], d["hop"][1]))
        # vai trong cụm theo cỡ mực: lớn nhất = từ khoá; ≤ 0.6 lớn nhất = nhãn; còn lại = cảm xúc/phụ
        cao = [d["cao_muc"] for d in c["dong"]]
        cmax = max(cao) if cao else 1
        for d in c["dong"]:
            r = d["cao_muc"] / max(cmax, 1e-6)
            d["vai_cum"] = "tu_khoa" if r >= 0.85 else ("nhan" if r <= 0.6 else "cam_xuc")
        if len(c["dong"]) == 1:
            c["dong"][0]["vai_cum"] = "tu_khoa"
    return cum


def DH_hop_chung(a, b):
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


# ─────────────────────────────────────────────────────────────── 3) nền: flash / light leak / punch
def _quet_nen(video, info, log):
    """độ sáng & sắc trung bình 10 khung/s (proxy 160 px) → flash (sáng vọt rồi về), ám màu (light-leak)"""
    DH = _dh()
    sang, sac, ts = [], [], []
    for t, f in DH._doc(video, info, 0, None, 10.0, 160):
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        ts.append(t); sang.append(float(hsv[..., 2].mean())); sac.append(float(hsv[..., 1].mean()))
    sang = np.asarray(sang); sac = np.asarray(sac)
    ra = {"flash": [], "am_mau": []}
    if len(sang) < 10:
        return ra
    nen = cv2.blur(sang.reshape(-1, 1).astype(np.float32), (1, 15)).flatten()
    for i in range(1, len(sang) - 1):
        if sang[i] - nen[i] > 45 and sang[i] >= sang[i - 1] and sang[i] >= sang[i + 1]:
            if not ra["flash"] or ts[i] - ra["flash"][-1]["t"] > 0.5:
                ra["flash"].append({"t": round(ts[i], 2), "manh": round(float(sang[i] - nen[i]), 0)})
    nen_s = cv2.blur(sac.reshape(-1, 1).astype(np.float32), (1, 25)).flatten()
    dang = None
    for i in range(len(sac)):
        if sac[i] - nen_s[i] > 18:
            if dang is None:
                dang = i
        elif dang is not None:
            if ts[i] - ts[dang] >= 0.25:
                ra["am_mau"].append({"t0": round(ts[dang], 2), "t1": round(ts[i], 2)})
            dang = None
    return ra


# ─────────────────────────────────────────────────────────────── 4) tiếng động (onset) quanh lúc lớp vào
def _onset_am(video, log):
    """wav mono 16k → mốc bật tiếng (spectral flux dải 2–8 kHz, nơi whoosh/click/ting nổi hơn giọng) + độ mạnh. Tệp tạm xoá sau khi dùng."""
    tmp = os.path.join(os.environ.get("TEMP") or "/tmp", f"bg-am-{C.bam(video)[:10]}-{os.getpid()}.wav")
    try:
        try:
            subprocess.run([C.duong("ffmpeg"), "-v", "error", "-y", "-i", video, "-ac", "1", "-ar", "16000", "-vn", tmp], check=True,
                           creationflags=(0x08000000 if os.name == "nt" else 0))
            with wave.open(tmp) as w:
                n = w.getnframes(); x = np.frombuffer(w.readframes(n), np.int16).astype(np.float32) / 32768.0
        except Exception as ex:
            log(f"  (onset âm: {ex})")
            return []
    finally:
        try:
            if os.path.isfile(tmp):
                os.remove(tmp)
        except OSError:
            pass
    N, H = 512, 160                      # 10 ms bước
    if len(x) < N * 4:
        return []
    win = np.hanning(N).astype(np.float32)
    nfr = (len(x) - N) // H
    fr = np.lib.stride_tricks.as_strided(x, shape=(nfr, N), strides=(x.strides[0] * H, x.strides[0]))
    S = np.abs(np.fft.rfft(fr * win, axis=1))
    f = np.fft.rfftfreq(N, 1 / 16000)
    cao = (f >= 2000) & (f <= 8000); thap = (f >= 80) & (f < 2000)
    e_cao = S[:, cao].sum(1); e_thap = S[:, thap].sum(1)
    flux = np.maximum(0, np.diff(e_cao, prepend=e_cao[0]))
    nen = np.convolve(flux, np.ones(50) / 50, mode="same") + 1e-6
    r = flux / nen
    ra = []
    i = 1
    while i < len(r) - 1:
        if r[i] > 4.0 and r[i] >= r[i - 1] and r[i] >= r[i + 1] and e_cao[i] > 1.5 * np.median(e_cao):
            ti = i * H / 16000
            ti_le = float(e_cao[i] / max(e_thap[i], 1e-6))
            ra.append({"t": round(ti, 2), "manh": round(float(min(r[i], 30.0)), 1), "cao_so_thap": round(ti_le, 2)})
            i += 12
        else:
            i += 1
    return ra


# ─────────────────────────────────────────────────────────────── 5) dịch sang lớp engine
# CHỖ GIỮ cho BẢN CHÉP DỰNG LẠI SO GỐC (dung_lai) — họ font theo độ đậm đo được (TÊN HỌ, không phải id băm trong kho):
# KHÔNG phải gu và KHÔNG đi vào video của khách: ngữ pháp chỉ mang "đậm/vừa/mảnh" + font_goi_y, AI tự chọn họ font khi dựng.
FONT_THEO_DAM = {"dam": "Be Vietnam Pro", "vua": "Be Vietnam Pro", "manh": "Be Vietnam Pro"}


def _font_goi_y(d):
    """mô tả font NHÌN THẤY được từ số đo (đậm, HOA, nghiêng) — AI xác nhận họ font bằng ảnh cận chữ"""
    t = d["tinh"]
    dam = t.get("dam_uoc") or 500
    goc = d.get("goc") or 0
    phan = []
    phan.append("rất đậm" if dam >= 800 else "đậm" if dam >= 650 else "vừa" if dam >= 450 else "mảnh")
    if t.get("hoa") == "hoa":
        phan.append("HOA")
    elif t.get("hoa") == "thuong":
        phan.append("thường")
    if abs(goc) >= 4:
        phan.append(f"nghiêng {goc:+.0f}°")
    return " ".join(phan) + " — AI: xác nhận họ (sans/serif/script) bằng ảnh cận chữ"


def _font_engine(d):
    """→ (TÊN HỌ font cho bản chép, độ đậm = SỐ ĐO dam_uoc làm tròn trăm; thiếu số đo → theo bậc đậm/vừa/mảnh)"""
    t = d["tinh"]
    dam = t.get("dam_uoc")
    if dam:
        dam = int(min(900, max(300, round(float(dam) / 100) * 100)))
        ho = FONT_THEO_DAM["dam" if dam >= 650 else "vua" if dam >= 450 else "manh"]
        return ho, dam
    return FONT_THEO_DAM["vua"], None            # không đo được nét → KHÔNG bịa số đậm (bản engine điền lúc ghi ra, có ghi may_sua)


def _cach_dong_do(c, W, H):
    """cách dòng ĐO được của cụm: khoảng tâm hai dòng kề (px@1920) / cỡ chữ dòng trên → trung vị; None nếu < 2 dòng chồng dọc"""
    ds = sorted(c["dong"], key=lambda d: d["hop"][1])
    r = []
    for a, b in zip(ds, ds[1:]):
        ngang = min(a["hop"][2], b["hop"][2]) - max(a["hop"][0], b["hop"][0])
        if ngang <= 0:
            continue
        co = float(a["tinh"].get("co_uoc_1920") or 0)
        if co <= 0:
            continue
        dy = ((b["hop"][1] + b["hop"][3]) / 2 - (a["hop"][1] + a["hop"][3]) / 2) * 1920
        if dy > 0:
            r.append(dy / co)
    return round(float(np.median(r)), 2) if r else None


def _lop_cum(c, W, H, mat_tb):
    """cụm → lớp `khoi` của engine (mỗi dòng anim riêng, tre, xoay, dx/dy so với dòng đầu). Dòng mang SỐ ĐO trong `_do`;
    viền/bóng/cách dòng KHÔNG ghi giá trị gu vào dòng — ghi_ra dịch sang engine từ số đo."""
    d0 = c["dong"][0]
    t0 = c["t0"]
    t1 = c["t1"]
    hop = c["hop"]
    # neo theo căn lề của dòng lớn nhất
    lon = max(c["dong"], key=lambda d: d["cao_muc"])
    can = lon["tinh"].get("can_le") or "giua"
    ax = "l" if can == "trai" else "r" if can == "phai" else "c"
    cx = {"l": hop[0], "r": hop[2], "c": (hop[0] + hop[2]) / 2}[ax]
    cy = (hop[1] + hop[3]) / 2
    vi_tri = {"anchor": "m" + ax, "x": round(cx, 3), "y": round(cy, 3), "w": round(min(0.96, hop[2] - hop[0] + 0.04), 3), "h": round(min(0.6, hop[3] - hop[1] + 0.04), 3)}
    svm = lon["tinh"].get("so_voi_mat") or {}
    mat = lon.get("mat") or mat_tb
    if mat and svm.get("vi_tri") in ("tren_dau", "duoi_cam", "ngang_nguc"):
        if svm["vi_tri"] == "tren_dau":
            vi_tri.update({"so_voi": "tren_dau", "theo_mat": True, "y": round(float(svm.get("khoang_theo_cao_mat") or 0), 2), "anchor": "b" + ax})
        else:
            vi_tri.update({"so_voi": "duoi_cam", "theo_mat": True, "y": round(float(svm.get("khoang_theo_cao_mat") or 0), 2), "anchor": "t" + ax})
        vi_tri["x"] = round(cx, 3)
    dong_e = []
    sau_nguoi = False
    nhoe_max = 0.0
    for d in c["dong"]:
        t = d["tinh"]
        hp = [d["hop"][0] * 1080, d["hop"][1] * 1080 * H / W, d["hop"][2] * 1080, d["hop"][3] * 1080 * H / W]
        cao_px = max(10.0, hp[3] - hp[1])
        vao, nhoe = _engine_vao(d["vao"], hp, cao_px)
        ra = _engine_ra(d.get("ra"), hp, cao_px)
        font, dam = _font_engine(d)
        co = int(t.get("co_uoc_1920") or cao_px * 1.1)
        e = {"text": d["chu"], "font": font, "co": co, "dam": dam, "mau": t.get("mau_chu"),      # màu/đậm = SỐ ĐO; None = máy không đo được
             "hoa": t.get("hoa") == "hoa", "tre": round(max(0.0, d["t0"] - t0), 2),
             "font_goi_y": _font_goi_y(d)}
        if d.get("goc") and abs(d["goc"]) >= 2:
            e["xoay"] = d["goc"]
        # dịch dòng so với neo cụm (px@1080): tâm dòng − tâm cụm (ngang theo căn lề)
        dcx = {"l": d["hop"][0] - hop[0], "r": d["hop"][2] - hop[2], "c": (d["hop"][0] + d["hop"][2]) / 2 - (hop[0] + hop[2]) / 2}[ax]
        if abs(dcx) * 1080 >= 12:
            e["dx"] = int(round(dcx * 1080))
        nen = t.get("nen") or {}
        if isinstance(nen, dict) and nen.get("mau"):
            e["nen"] = {"mau": nen["mau"], "dem": [int(0.5 * cao_px), int(0.3 * cao_px)], "bo": int(nen.get("bo_px_1080") or 12)}
        an = {}
        if vao:
            if vao.get("_tach"):
                an["tach"] = vao.pop("_tach"); an["so_le"] = vao.pop("_so_le")
            vao.pop("_do_may", None)
            an["vao"] = vao
        if ra:
            an["ra"] = ra
        if nhoe:
            an["nhoe_dong"] = nhoe; nhoe_max = max(nhoe_max, nhoe)
        if an:
            e["anim"] = an
        if (t.get("so_voi_nguoi") or {}).get("lop") == "sau":
            sau_nguoi = True
        if d.get("nguon_nghi_ngo"):
            e["nguon_nghi_ngo"] = d["nguon_nghi_ngo"]
        e["_do"] = {"vai_cum": d["vai_cum"], "cao_muc_px": round(cao_px, 1), "cao_muc_px_1920": t.get("cao_muc_px_1920"),
                    "net_px": t.get("net_px"), "net_ti_le": t.get("net_ti_le"), "dam_uoc": t.get("dam_uoc"),
                    "mau_chu": t.get("mau_chu"), "mau_chu_2": t.get("mau_chu_2"),
                    "vien_chu": t.get("vien_chu"), "bong_chu": t.get("bong_chu"),
                    "vao": d["vao"].get("kieu"), "ra": (d.get("ra") or {}).get("kieu"),
                    "t_bat_dau": d["vao"].get("t_bat_dau"), "t_du": d["vao"].get("t_du"),
                    "vuot": (d["vao"].get("dac_trung") or {}).get("vuot"), "ti_le_dau": (d["vao"].get("dac_trung") or {}).get("ti_le_dau"),
                    "so_voi_nguoi": (t.get("so_voi_nguoi") or {}).get("lop"), "chong_nguoi": (t.get("so_voi_nguoi") or {}).get("chong"),
                    "hop": [round(x, 3) for x in d["hop"]], "t0": d["t0"], "t1": d["t1"], "dau_hieu": d.get("dau_hieu")}
        if d.get("gan_tu"):
            e["_do"]["gan_tu"] = d["gan_tu"]
        dong_e.append(e)
    lop = {"id": c["id"], "kieu": "khoi", "t0": round(t0, 2), "t1": round(t1, 2), "co_y": True,
           "noi_dung": {"dong": dong_e}, "kieu_dang": {"can": can}, "vi_tri": vi_tri,
           "anim": {"tach": "dong", "so_le": 0.0}, "_do": {"cach_dong": _cach_dong_do(c, W, H)}}
    if nhoe_max:
        lop["anim"]["nhoe_dong"] = nhoe_max
    if sau_nguoi:
        lop["sau_nguoi"] = True; lop["ne_mat"] = False
    # ra của cụm = ra của dòng lớn nhất (các dòng đã có ra riêng)
    return lop


# ─────────────────────────────────────────────────────────────── 6) lời
def _loi_cua_cum(loi, t0, t1):
    if not loi:
        return None
    tu = [w for w in loi if float(w.get("t", w.get("a", 0))) < t1 and float(w.get("e", w.get("b", 0))) > t0 - 0.05]
    if not tu:
        return {"tu": [], "lech_tu_dau": None}
    dau = min(tu, key=lambda w: abs(float(w.get("t", w.get("a", 0))) - t0))
    return {"tu": [w.get("w") or w.get("tu") for w in tu][:12], "lech_tu_dau": round(t0 - float(dau.get("t", dau.get("a", 0))), 2),
            "so_tu": len(tu)}


# ─────────────────────────────────────────────────────────────── 7) tổng
def tao(video, thu_muc, loi=None, log=print, dh=None, fps_day=None, canh_day=None):
    """video mẫu + dong_hoc.json/_quet-tho.json (dong_hoc.phan_tich đã chạy; thiếu thì chạy) → ban-ghi.json / ban-ghi-lop.json / ban-ghi.md.
    Không cần AI. fps_day/canh_day: None = FPS_DAY/CANH_DAY (bộ kiểm thử nen_that truyền số riêng)."""
    t_bd = time.time()
    _log0 = log
    log = lambda m: _log0(m) if _log0 is not print else print(m, flush=True)
    DH = _dh()
    os.makedirs(thu_muc, exist_ok=True)
    fps_day = float(fps_day or FPS_DAY); canh_day = int(canh_day or CANH_DAY)
    fps_lon = max(fps_day, float(FPS_LON_DAN))
    info = C.ffprobe(video) or {}
    dur = float(info.get("dur") or 0)
    W, H = int(info.get("w") or 1080), int(info.get("h") or 1920)
    DH.dat_video(video)
    nguon_alpha = DH.proxy_cua(thu_muc, video)
    if dh is None:
        dh = C.doc_json(os.path.join(thu_muc, "dong_hoc.json"), {}) or {}
    if not dh.get("vet_chu") and not os.path.isfile(os.path.join(thu_muc, "_quet-tho.json")):
        log("  bản ghi: chưa có dong_hoc.json → chạy dong_hoc.phan_tich (không ảnh)")
        dh = DH.phan_tich(video, thu_muc, log=log, fps_day=int(fps_lon), canh_day=canh_day, ve_anh=False)
    vet = dh.get("vet_chu") or []
    # vệt thô chỉ có hop/cao_dong; cần hop_dau/t_cuoi → đọc lại từ _quet-tho.json (có đủ)
    tho = C.doc_json(os.path.join(thu_muc, "_quet-tho.json"), {}) or {}
    vet_day = tho.get("vet") or []
    if vet_day:
        vet_day = DH._phan_vai([dict(v) for v in vet_day], dur)
    else:
        vet_day = [dict(v, hop_dau=v["hop"], t_cuoi=v["t_ra"]) for v in vet]
    vet_day = _phan_lai_phu_de(vet_day)
    chu = [v for v in vet_day if v.get("vai") == "chu" and v.get("dai", 0) >= 0.25]
    phu = [v for v in vet_day if v.get("vai") == "phu_de"]
    toi_da = int(_cfg().get("hoc_max_vet", MAX_VET) or MAX_VET)
    if len(chu) > toi_da:
        chu.sort(key=lambda v: -(v["cao_dong"] * v["dai"]))
        chu = sorted(chu[:toi_da], key=lambda v: v["t_dau"])
    g = {"tho": round(time.time() - t_bd, 1)}
    # tái dùng sự kiện dong_hoc đã đo (cùng hop/t_dau) để đỡ đo lại
    da = {}
    for e in dh.get("su_kien") or []:
        if e.get("tinh") and e.get("vao") and e.get("vai") in ("tieu_de", "nhan"):
            da[(round(e["t_vao"], 1), tuple(round(x, 2) for x in e["hop_tho"]))] = e
    mat_tb = (dh.get("so_lieu") or {}).get("mat_tb")
    # ---- kế hoạch cửa sổ: vào + ra cho MỌI vệt (vệt cùng chữ ký sau đại diện chỉ OCR 1 khung từ cùng cửa sổ)
    ke = {fps_day: [], fps_lon: []}
    trang = []
    nhom_dd = {}                                   # chữ ký → kết quả đại diện đã đo
    n_dh = 0
    for i, v in enumerate(chu):
        k = (round(v["t_dau"], 1), tuple(round(x, 2) for x in v["hop"]))
        st = {"i": i, "v": v, "ck": _chu_ky_vet(v), "r": None, "ctx": None, "dh": None}
        if k in da:
            e = da[k]
            st["dh"] = {"tinh": e["tinh"], "vao": e["vao"], "ra": e.get("ra"), "vao_nen": e.get("vao_nen"), "goc": None,
                        "chu": e["tinh"].get("chu_ocr") or "", "mat": e["tinh"].get("mat"), "fps": (dh.get("cau_hinh") or {}).get("fps_day")}
            n_dh += 1
        lon_dan, a, b, t_co, ra = _cua_so_vet(v, dur)
        fps_v = fps_lon if lon_dan else fps_day
        st["fps"] = fps_v
        if st["dh"] is None:
            ke[fps_v].append({"id": (i, "vao"), "a": a, "b": b, "hop": v["hop"]})
            if ra:
                ke[fps_v].append({"id": (i, "ra"), "a": ra[0], "b": ra[1], "hop": v["hop"]})
        trang.append(st)
    log(f"  bản ghi: {len(chu)} vệt chữ phủ + {len(phu)} vệt phụ đề → {n_dh} dùng lại dong_hoc, "
        f"{sum(1 for s in trang if s['dh'] is None and s['fps'] == fps_day)} đo ở {fps_day:g}/s, "
        f"{sum(1 for s in trang if s['dh'] is None and s['fps'] == fps_lon)} lớn dần ở {fps_lon:g}/s · {len(set(s['ck'] for s in trang))} chữ ký")
    so_dai_dien = so_gan = 0
    t1 = time.time()

    def _in_dong(st, r):
        vv = r["vao"]
        log(f"    d{st['i'] + 1:02d} {st['v']['t_dau']:.2f}–{st['v']['t_ra']:.2f}s «{(r.get('chu') or '')[:28]}» vào {vv.get('kieu')} {vv.get('dai')}s {vv.get('ease') or ''}"
            + (f" xoay {r['goc']}°" if r.get("goc") else "") + (" · SAU người" if (r['tinh'].get('so_voi_nguoi') or {}).get('lop') == 'sau' else "")
            + (f" · gán từ {r['gan_tu']}" if r.get("gan_tu") else ""))

    import threading
    khoa = threading.Lock()
    dem = {"dai_dien": 0, "gan": 0}

    def _xu_ly(fps_v):
        def lam(wid, ts_, crops, nho_, roi, WH):
            Wd, Hd = WH
            i, pha = wid
            st = trang[i]; v = st["v"]
            try:
                if pha == "ra":
                    if st["r"] and not st["r"].get("bo_qua") and st["ctx"]:
                        st["r"]["ra"] = _do_vet_ra(DH, v, st["ctx"], ts_, crops, roi, fps_v)
                        if st["r"].get("_dai_dien"):
                            with khoa:
                                nhom_dd[st["ck"]]["ra"] = st["r"]["ra"]
                    return
                with khoa:
                    dd = nhom_dd.get(st["ck"])
                if dd is not None and not dd.get("_dang"):
                    r = _gan_tu_dai_dien(DH, dd, v, ts_, crops, nho_, roi, Wd, Hd, trang[dd["_i"]]["v"])
                    st["r"] = r
                    if not r.get("bo_qua"):
                        with khoa:
                            dem["gan"] += 1
                        _in_dong(st, r)
                    else:
                        log(f"    vệt {i + 1}/{len(chu)} {v['t_dau']:.1f}s bỏ: {r['bo_qua']}")
                    return
                r, ctx = _do_vet_vao(DH, video, info, v, ts_, crops, nho_, roi, Wd, Hd, fps_v, log, nguon_alpha=nguon_alpha)
                st["r"] = r; st["ctx"] = ctx
                if r.get("bo_qua"):
                    log(f"    vệt {i + 1}/{len(chu)} {v['t_dau']:.1f}s bỏ: {r['bo_qua']}")
                    return
                r["_dai_dien"] = True; r["_id"] = f"d{i + 1:02d}"; r["_i"] = i
                o_du = ctx["o_du"]
                r["_hop_ocr"] = [round((roi[0] + min(o["hop"][0] for o in o_du)) / Wd, 4), round((roi[1] + min(o["hop"][1] for o in o_du)) / Hd, 4),
                                 round((roi[0] + max(o["hop"][2] for o in o_du)) / Wd, 4), round((roi[1] + max(o["hop"][3] for o in o_du)) / Hd, 4)]
                with khoa:
                    dem["dai_dien"] += 1
                    if st["ck"] not in nhom_dd:
                        nhom_dd[st["ck"]] = r
                _in_dong(st, r)
            except Exception as ex:
                st["r"] = {"bo_qua": f"lỗi đo: {str(ex)[:80]}"}
                log(f"    vệt {i + 1}/{len(chu)} {v['t_dau']:.1f}s bỏ: {st['r']['bo_qua']}")
        return lam

    for fps_v in sorted(ke, reverse=False):
        ds = ke[fps_v]
        if not ds:
            continue
        DH.xu_ly_song_song(DH.cua_so_hang_loat(video, info, ds, fps_v, canh_day, log=log), _xu_ly(fps_v), log=log)
    so_dai_dien, so_gan = dem["dai_dien"], dem["gan"]
    # R5: vệt gán theo chữ ký chép `ra` của đại diện LÚC gán; đại diện đo RA sau (cửa sổ RA kết thúc muộn hơn) → vệt gán mất RA.
    # Sau khi mọi cửa sổ xong, điền lại từ đại diện.
    for st in trang:
        r = st["r"]
        if r and r.get("gan_tu") and r.get("ra") is None:
            dd = nhom_dd.get(st["ck"])
            if dd and dd.get("ra") is not None:
                r["ra"] = dd["ra"]
    g["do_vet"] = round(time.time() - t1, 1)
    # ---- gom dòng
    dong = []
    for st in trang:
        v = st["v"]; i = st["i"]
        r = st["dh"] if st["dh"] is not None else st["r"]
        if r is None:
            r = {"bo_qua": "không có cửa sổ"}
        if r.get("bo_qua"):
            if st["dh"] is None and st["r"] is None:
                log(f"    vệt {i + 1}/{len(chu)} {v['t_dau']:.1f}s bỏ: {r['bo_qua']}")
            continue
        if st["dh"] is not None:
            _in_dong(st, r)
        hop = r["tinh"].get("hop") or v["hop"]
        dong.append({"id": f"d{i + 1:02d}", "t0": round(float(r["vao"].get("t_bat_dau") or v["t_dau"]), 2), "t1": round(float(v["t_ra"]), 2),
                     "hop": hop, "cao_muc": float(r["tinh"].get("cao_muc_ti_le") or (hop[3] - hop[1]) * 0.7), "tinh": r["tinh"],
                     "vao": r["vao"], "ra": r.get("ra"), "vao_nen": r.get("vao_nen"), "goc": r.get("goc"), "chu": r.get("chu") or "", "mat": r.get("mat"),
                     "gan_tu": r.get("gan_tu"), "nghi_ngo_vet": v.get("nghi_ngo"), "dau_hieu": v.get("dau_hieu")})
    log(f"  đo dày: {so_dai_dien} vệt đại diện, {so_gan} vệt gán theo chữ ký, {n_dh} từ dong_hoc ({g['do_vet']}s)")
    # ---- nhiễu chữ web / cảnh / áo: dấu hiệu VẬT LÝ → nguon_nghi_ngo (KHÔNG bỏ; chỉ OCR rác mới bỏ)
    def _khoa(d):                          # khoá mờ: 6 ký tự đầu không dấu — OCR đọc "THINK GREE"/"THINK GREEN" vẫn trùng
        return re.sub(r"[^A-Z0-9]", "", (d.get("chu") or "").upper())[:6]
    dem = {}
    for d in dong:
        k = _khoa(d)
        if k:
            dem[k] = dem.get(k, 0) + 1
    giu = []
    for d in dong:
        if _rac_ocr(d.get("chu")):
            log(f"    {d['id']} bỏ: OCR rác «{d.get('chu', '')[:20]}»"); continue
        if d.get("goc") is not None and abs(d["goc"]) > 20:        # góc ước quá lớn = mặt nạ mực lẫn vật khác
            d["goc"] = None
        sn = d["tinh"].get("so_voi_nguoi") or {}
        ng = d.get("nghi_ngo_vet")                                   # (a) trôi cùng nền → "canh"; (b) không mặt + ≥ 3 khối → "web"
        if not ng and sn.get("lop") == "truoc" and float(sn.get("chong") or 0) >= 0.6 and (dem.get(_khoa(d), 0) >= 3 or float(sn.get("chong") or 0) >= 0.85):
            ng = "ao"                                                # (c) mực nằm trên mặt nạ người (áo / vật cầm) — lặp nhiều lần hoặc chồng gần hết
        if ng:
            d["nguon_nghi_ngo"] = ng
        giu.append(d)
    dong = giu
    cum = _gom_cum(dong)
    t1 = time.time()
    nen = _quet_nen(video, info, log)
    onset = _onset_am(video, log)
    g["nen_am"] = round(time.time() - t1, 1)
    lops = []
    for c in cum:
        lop = _lop_cum(c, W, H, mat_tb)
        # tiếng động gắn lúc vào: onset trong ±0.12 s quanh t0
        gan = [o for o in onset if abs(o["t"] - c["t0"]) <= 0.12]
        if gan:
            lop["am"] = {"vao": "tu_dong", "_onset": gan[0]}
        lop["_loi"] = _loi_cua_cum(loi, c["t0"], c["t1"])
        lops.append(lop)
    # cắt / punch
    cat = [{"t": c["t"] if isinstance(c, dict) else float(c)} for c in (dh.get("cat") or [])]
    zoom = [float(z) for z in (dh.get("zoom_cat") or [])]
    # phụ đề (tóm tắt — ngữ pháp dùng; bản ghi dựng lại không chép phụ đề)
    pd = None
    if phu:
        cao = float(np.median([v["cao_dong"] for v in phu])); cy = float(np.median([(v["hop"][1] + v["hop"][3]) / 2 for v in phu]))
        pd = {"so_cum": len(phu), "cao_dong_ti_le": round(cao, 4), "y": round(cy, 3), "dai_tv": round(float(np.median([v["dai"] for v in phu])), 2)}
    g["tong"] = round(time.time() - t_bd, 1)
    try:
        g["cache"] = DH.thong_ke_cache()
    except Exception:
        pass
    bg = {"phien_ban": PHIEN_BAN, "nguon": video, "khung": [W, H], "dur": round(dur, 2), "fps": info.get("fps"), "mat_tb": mat_tb,
          "cau_hinh": {"fps_day": fps_day, "fps_lon_dan": fps_lon, "canh_day": canh_day, "max_vet": toi_da},
          "cum": lops, "so_dong": len(dong), "cat": cat, "punch": zoom, "flash": nen["flash"], "am_mau": nen["am_mau"],
          "onset_am": onset, "phu_de": pd, "giay": g["tong"], "giay_buoc": g,
          "do": {"dai_dien": so_dai_dien, "gan": so_gan, "dong_hoc": n_dh}}
    bg = loc(bg, log)
    kq = ghi_ra(bg, thu_muc, log)
    p, pl, pm = kq["json"], kq["lop"], kq["md"]; lops = bg["cum"]
    log(f"  bản ghi: {len(lops)} cụm / {len(dong)} dòng ({bg.get('so_dong_nghi_ngo', 0)} dòng nghi ngờ), {len(nen['flash'])} flash, {len(onset)} onset tiếng, {bg['giay']}s → {p}")
    return {"json": p, "lop": pl, "md": pm, "ban_ghi": bg}


def loc(bg, log=print):
    """lọc lại bản ghi đã đo (không đo lại). 1.2.21: KHÔNG bỏ dòng theo số cứng (chữ nhỏ / lặp / nhiều dòng) — chỉ gom thống kê nghi ngờ:
    dòng mang `nguon_nghi_ngo` ("web" | "canh" | "ao") từ dấu hiệu vật lý; cụm mà mọi dòng đều nghi ngờ → cụm `nghi_ngo`.
    Cụm rỗng (không dòng) mới bỏ."""
    giu, bo_cum, so_nn = [], 0, 0
    dem = {}
    for c in bg.get("cum") or []:
        ds = c["noi_dung"]["dong"]
        if not ds:
            bo_cum += 1; continue
        nn = [d.get("nguon_nghi_ngo") for d in ds]
        so_nn += sum(1 for x in nn if x)
        for x in nn:
            if x:
                dem[x] = dem.get(x, 0) + 1
        if all(nn):
            c["nghi_ngo"] = max(set(nn), key=nn.count)
        else:
            c.pop("nghi_ngo", None)
        giu.append(c)
    bg["cum"] = giu
    bg["so_dong"] = sum(len(c["noi_dung"]["dong"]) for c in giu)
    bg["so_dong_nghi_ngo"] = so_nn
    bg["nghi_ngo_theo_nguon"] = dem
    log(f"  lọc bản ghi: {bg['so_dong']} dòng, {so_nn} dòng nghi ngờ {dem} (vẫn giữ — AI quyết), bỏ {bo_cum} cụm rỗng → {len(giu)} cụm")
    return bg


def _dong_engine(d, dien=None, may_sua=None, lid=None):
    """dòng bản ghi → dòng engine: bỏ số đo, dịch viền/bóng từ SỐ ĐO (có/không + màu đo) sang khoá engine cho bản chép dựng lại.
    màu/đậm máy không đo được → điền trung vị của bản ghi (`dien`) và ghi may_sua (không lặng lẽ)"""
    do = d.get("_do") or {}
    e = {k: v for k, v in d.items() if k not in ("_do", "font_goi_y", "nguon_nghi_ngo")}
    dien = dien or {}
    for k in ("mau", "dam"):
        if e.get(k) is None:
            e[k] = dien.get(k) if dien.get(k) is not None else ("#FFFFFF" if k == "mau" else 500)
            if may_sua is not None:
                may_sua.append({"lop": lid, "dong": d.get("text", "")[:20], "sua": "dien_" + k, "den": e[k], "mo_ta": f"máy không đo được {k} → trung vị bản ghi"})
    cao = float(do.get("cao_muc_px") or d.get("co") or 40)
    if do.get("vien_chu"):
        e["vien"] = [{"w": max(2, int(round(cao * 0.06))), "mau": do.get("mau_chu_2") or "#111111"}]
    if do.get("bong_chu"):
        e["bong"] = [{"x": 0, "y": max(2, int(round(cao * 0.05))), "mo": max(4, int(round(cao * 0.15))), "mau": "#00000099"}]
    return e


def ghi_ra(bg, thu_muc, log=print):
    """ghi ban-ghi.json + ban-ghi-lop.json (bản engine thuần: viền/bóng/cách dòng dịch từ số đo) + ban-ghi.md"""
    p = os.path.join(thu_muc, "ban-ghi.json")
    C.ghi_json(p, bg)
    lop_engine = []
    ds_ = [d for c in (bg.get("cum") or []) for d in c["noi_dung"]["dong"]]
    mau_ = [d.get("mau") for d in ds_ if d.get("mau")]; dam_ = [d.get("dam") for d in ds_ if d.get("dam")]
    dien = {"mau": max(set(mau_), key=mau_.count) if mau_ else None, "dam": int(np.median(dam_)) if dam_ else None}
    may_sua = []
    for l in bg.get("cum") or []:
        l2 = json.loads(json.dumps(l))
        cd = (l2.get("_do") or {}).get("cach_dong")
        for k in list(l2.keys()):
            if k.startswith("_") or k == "nghi_ngo":
                l2.pop(k)
        if isinstance(l2.get("am"), dict):
            l2["am"].pop("_onset", None)
        if cd:
            l2.setdefault("kieu_dang", {})["cach_dong"] = cd
        l2["noi_dung"]["dong"] = [_dong_engine(d, dien, may_sua, l2.get("id")) for d in l2["noi_dung"]["dong"]]
        lop_engine.append(l2)
    W, H = bg.get("khung") or [1080, 1920]
    pl = os.path.join(thu_muc, "ban-ghi-lop.json")
    C.ghi_json(pl, {"khung": [1080, 1920] if H >= W else [1920, 1080], "lop": lop_engine, "cat": [{"src": 0, "a": 0, "b": round(float(bg.get("dur") or 0), 2)}],
                    "camera": [{"t": z, "z": 1.08, "dai": 0.15, "ease": "out"} for z in (bg.get("punch") or [])[:20]],
                    "chuyen_canh": [{"t": f["t"], "kieu": "flash", "dai": 0.2} for f in (bg.get("flash") or [])[:20]], "phu_de": {"che_do": "tat"},
                    "may_sua": may_sua, "dien_tu_trung_vi": dien})
    pm = os.path.join(thu_muc, "ban-ghi.md")
    with open(pm, "w", encoding="utf-8") as f:
        f.write("\n".join(doc_duoc(bg)))
    return {"json": p, "lop": pl, "md": pm}


def loc_lai(thu_muc, log=print):
    bg = C.doc_json(os.path.join(thu_muc, "ban-ghi.json"), {}) or {}
    if not bg:
        return None
    bg = loc(bg, log)
    return ghi_ra(bg, thu_muc, log)


def doc_duoc(bg):
    """bản ghi → dòng đọc được (AI/người)"""
    L = [f"# Bản ghi thi công — {os.path.basename(str(bg.get('nguon')))} · {bg.get('dur')}s · {len(bg.get('cum') or [])} cụm / {bg.get('so_dong')} dòng chữ"
         + (f" · {bg.get('so_dong_nghi_ngo')} dòng nghi ngờ {bg.get('nghi_ngo_theo_nguon')} (web = màn hình/trang web quay lại, canh = chữ trong cảnh trôi cùng nền, ao = chữ in trên người; máy KHÔNG bỏ — bạn quyết)" if bg.get("so_dong_nghi_ngo") else "")]
    for c in bg.get("cum") or []:
        vt = c.get("vi_tri") or {}
        neo = f"{vt.get('anchor')} ({vt.get('x')}, {vt.get('y')})" + (f" so với {vt['so_voi']} ×cao mặt" if vt.get("so_voi") else "")
        loi = c.get("_loi") or {}
        cd = (c.get("_do") or {}).get("cach_dong")
        L.append(f"\n## {c['id']} {c['t0']}–{c['t1']}s · neo {neo}" + (" · SAU NGƯỜI" if c.get("sau_nguoi") else "")
                 + (f" · cách dòng đo {cd}" if cd else "") + (f" · NGHI NGỜ {c['nghi_ngo']}" if c.get("nghi_ngo") else "")
                 + (f" · tiếng động lúc vào" if c.get("am") else "") + (f" · lời: «{' '.join(loi.get('tu') or [])[:60]}» (lệch {loi.get('lech_tu_dau')}s)" if loi.get("tu") else ""))
        for d in c["noi_dung"]["dong"]:
            do = d.get("_do") or {}
            an = d.get("anim") or {}
            v = an.get("vao") or {}; r = an.get("ra") or {}
            tu = v.get("tu") or {}
            mo = f"{v.get('kieu')} {v.get('dai')}s {v.get('ease') or ''}"
            if tu.get("x") or tu.get("y"):
                mo += f" từ ({tu.get('x', 0)}, {tu.get('y', 0)})px"
            if tu.get("scale"):
                mo += f" scale {tu['scale']}"
            if an.get("nhoe_dong"):
                mo += f" nhoè {an['nhoe_dong']}"
            if an.get("tach"):
                mo += f" tách {an['tach']} so le {an.get('so_le')}"
            L.append(f"- [{do.get('vai_cum')}] «{d['text'][:40]}» {d['co']}px đậm {d.get('dam') or '?'} {d.get('mau') or 'màu ?'}{' HOA' if d.get('hoa') else ''}"
                     + (f" mực {do.get('cao_muc_px_1920')}px/1920" if do.get("cao_muc_px_1920") else "")
                     + (f" viền({do.get('mau_chu_2') or '?'})" if do.get("vien_chu") else "") + (" bóng" if do.get("bong_chu") else "")
                     + (f" xoay {d['xoay']}°" if d.get("xoay") else "") + (f" dx {d['dx']}" if d.get("dx") else "")
                     + f" · trễ {d['tre']}s · vào {mo}" + (f" · ra {r.get('kieu')} {r.get('dai')}s" if r else "")
                     + (f" · NGHI NGỜ {d['nguon_nghi_ngo']}" if d.get("nguon_nghi_ngo") else "")
                     + (f" · gán từ {do['gan_tu']}" if do.get("gan_tu") else "")
                     + f" · {d.get('font_goi_y', '')}")
    if bg.get("punch"):
        L.append("\n- punch-in (cắt cận) tại: " + ", ".join(f"{z:.1f}s" for z in bg["punch"][:20]))
    if bg.get("flash"):
        L.append("- flash sáng tại: " + ", ".join(f"{f['t']:.1f}s" for f in bg["flash"][:20]))
    if bg.get("am_mau"):
        L.append("- ám màu / light-leak: " + ", ".join(f"{a['t0']:.1f}–{a['t1']:.1f}s" for a in bg["am_mau"][:10]))
    if bg.get("cat"):
        L.append("- cắt cảnh tại: " + ", ".join(f"{c['t']:.1f}s" for c in bg["cat"][:30]))
    if bg.get("phu_de"):
        p = bg["phu_de"]
        L.append(f"- phụ đề: {p['so_cum']} cụm, cao dòng {p['cao_dong_ti_le']:.3f} khung, y {p['y']}, mỗi cụm ~{p['dai_tv']}s")
    return L


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("thu_muc"); ap.add_argument("--loi")
    ap.add_argument("--fps", type=float, default=None, help="khung/giây đo dày (mặc định 15; lớn dần luôn 30)")
    ap.add_argument("--canh", type=int, default=None, help="cạnh ngắn khung đo dày (mặc định 600)")
    ap.add_argument("--loc-lai", action="store_true", help="chỉ lọc lại bản ghi đã có (không đo lại)")
    a = ap.parse_args()
    if a.loc_lai:
        print(loc_lai(a.thu_muc)); raise SystemExit(0)
    loi = C.doc_json(a.loi) if a.loi else None
    if isinstance(loi, dict):
        loi = loi.get("tu") or loi.get("words") or []
    kq = tao(a.video, a.thu_muc, loi=loi, fps_day=a.fps, canh_day=a.canh)
    print(kq["json"])
