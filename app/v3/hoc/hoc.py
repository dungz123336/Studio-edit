# -*- coding: utf-8 -*-
"""HỌC NGÔN NGỮ THỊ GIÁC từ video mẫu → style-spec.json của hồ sơ (không học timeline).
Máy: bảng khung đều + dải khung quanh cắt cảnh + mặt + bảng khung dày toàn video (doc/khung.py trên proxy 540p)
+ mỗi sự kiện tiêu biểu: dải SOI 12 khung/s quanh lúc vào/ra + ảnh CẬN CHỮ từ video gốc (_bang_chung) + ĐỘNG HỌC ĐO MÁY (hoc/dong_hoc.py: kiểu vào/ra, thời lượng, easing,
neo so với mặt, cỡ/HOA/màu/viền/bóng/nền thẻ, đồ hoạ) → AI XÁC NHẬN bằng mắt và viết Style Spec từ SỐ ĐO
(hướng dẫn: hoc/HUONG-DAN-AI.md; điểm xuất phát: spec-may.json).
    python v3/hoc/hoc.py --video mau.mp4 --ho-so <id> [--ten "tên bài học"]
    python v3/hoc/hoc.py --video mau.mp4 --chi-chuan-bi <thư mục>      # chỉ máy đo, không gọi AI
"""
import os, sys, json, time, glob, shutil, math
import numpy as np
import cv2

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
import chung as C


def _yc_khung(info, ts, rong, nhan):
    """yêu cầu khung cả hình tại các giây ts, thu về rộng `rong` → {(nhan, i): (t, hộp cả khung, (w, h))} cho _doc_goc_nhieu
    (1.2.21: thay N lần ffmpeg mỗi khung bằng MỘT lượt đọc tuần tự cùng với dải soi / cận chữ)"""
    W, H = int(info.get("w") or 1080), int(info.get("h") or 1920)
    h = max(2, int(round(rong * H / float(W) / 2)) * 2)
    return {(nhan, i): (t, [0.0, 0.0, 1.0, 1.0], (int(rong), h)) for i, t in enumerate(ts)}


def _rgb(bgr):
    return None if bgr is None else cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def _bang(khung_list, nhan, cot, duong, ten_tren=None):
    """ghép lưới ảnh có nhãn → jpg"""
    from PIL import Image, ImageDraw, ImageFont
    ks = [k for k in khung_list if k is not None]
    if not ks:
        return None
    w, h = ks[0].shape[1], ks[0].shape[0]
    hang = (len(khung_list) + cot - 1) // cot
    dau = 36 if ten_tren else 0
    im = Image.new("RGB", (cot * (w + 6) + 6, dau + hang * (h + 26) + 6), (18, 18, 22))
    d = ImageDraw.Draw(im)
    try:
        ft = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        ft = ImageFont.load_default()
    if ten_tren:
        d.text((8, 8), ten_tren, fill=(240, 240, 240), font=ft)
    for i, k in enumerate(khung_list):
        x = 6 + (i % cot) * (w + 6); y = dau + 6 + (i // cot) * (h + 26)
        if k is not None:
            im.paste(Image.fromarray(k), (x, y))
        d.text((x + 4, y + h + 4), str(nhan[i]), fill=(255, 210, 0), font=ft)
    im.save(duong, quality=88)
    return duong


# ═════════════════════════════════════════════ BẰNG CHỨNG NHÌN RÕ (cho AI tự nhìn font/viền/bóng/nền thẻ/cách chữ hiện)
# Máy KHÔNG kết luận gì ở đây — chỉ đưa ảnh đủ to. Các số là KỸ THUẬT (cỡ ảnh AI đọc được, mật độ khung), không phải gu.
BC = {
    "proxy_cao": 540,          # proxy cho doc/khung.py (tầng 1 + 2) và dải soi
    "bang_muc": "day",         # mức tầng 2 cho video mẫu
    "toi_da_su_kien": 12,      # số sự kiện có dải soi + cận chữ
    "soi_fps": 12.0,           # khung/giây dải soi
    "o_soi": 260,              # cạnh ngắn tối thiểu một ô soi (px)
    "canh_bang": 1568,         # cạnh dài tối đa một ảnh (AI thu ảnh về cỡ này)
    "vao_truoc": 0.3, "vao_sau": 0.8, "vao_toi_da": 1.6,      # cửa sổ soi lúc VÀO (giây)
    "ra_truoc": 0.4, "ra_sau": 0.3, "ra_toi_da": 1.0,         # cửa sổ soi lúc RA
    "can_rong": 600, "can_cao": 180, "can_rong_max": 1400, "can_cao_max": 820, "can_phong_max": 6.0,   # ảnh cận chữ (video GỐC)
}
_DEN = (18, 18, 22)


def _fnt(co, dam=False):
    from PIL import ImageFont
    for p in (os.path.join(C.duong("font_mac_dinh"), "BeVietnamPro-Bold.ttf" if dam else "BeVietnamPro-Regular.ttf"),
              "arialbd.ttf" if dam else "arial.ttf"):
        try:
            return ImageFont.truetype(p, co)
        except Exception:
            pass
    return ImageFont.load_default()


def _nap_khung_doc():
    from doc import khung as K
    return K


def _proxy_mau(video, thu_muc, info, log=print):
    """proxy 540p (cache thu_muc/cache) + thu_muc/doc/nguon.json {"chinh": {"proxy"}} để doc/khung.py dùng được → (proxy, fps)"""
    from doc import proxy as PX
    cache = os.path.join(thu_muc, "cache")
    os.makedirs(cache, exist_ok=True)
    os.makedirs(os.path.join(thu_muc, "doc"), exist_ok=True)
    dst = os.path.join(cache, f"proxy{BC['proxy_cao']}-{C.bam(video)}.mp4")
    dur = float(info.get("dur") or 0)

    def _du_dai(p):
        """R5: proxy phải dài ≥ 97 % nguồn — card lỗi giữa chừng (cuda) → ffmpeg vẫn thoát mã 0 với tệp CỤT (gặp thật: 29,9/71,7 s),
        tầng 1–2 + lưới mặt nạ người chỉ phủ nửa video mà không ai báo"""
        d = float((C.ffprobe(p) or {}).get("dur") or 0)
        return d >= 0.97 * dur - 0.5, d

    hw = (C.phan_cung() or {}).get("hwaccel", "none")
    if PX._ok(dst):
        ok, d = _du_dai(dst)
        if not ok:
            log(f"(proxy mẫu cũ cụt {d:.1f}/{dur:.1f}s → tạo lại bằng CPU)")
            os.remove(dst)
    if not PX._ok(dst):
        ok, err = PX._ffmpeg_proxy(video, dst, info, BC["proxy_cao"], 30, hw, False, None)
        if ok and hw != "none":
            ok, d = _du_dai(dst)
            if not ok:
                log(f"(proxy mẫu ({hw}) cụt {d:.1f}/{dur:.1f}s → tạo lại bằng CPU)")
                err = f"proxy {hw} cụt {d:.1f}/{dur:.1f}s"
        if not ok and hw != "none":
            ok, err = PX._ffmpeg_proxy(video, dst, info, BC["proxy_cao"], 30, "none", False, None)
        if not ok:
            raise RuntimeError(f"ffmpeg proxy lỗi: {str(err)[-300:]}")
        ok, d = _du_dai(dst)
        if not ok:
            log(f"(proxy mẫu chỉ dài {d:.1f}/{dur:.1f}s — nguồn có thể hỏng/cụt; học trên phần giải mã được)")
    pi = C.ffprobe(dst) or {}
    C.ghi_json(os.path.join(thu_muc, "doc", "nguon.json"),
               {"nguon": [{"src": 0, "duong": video, "vai": "chinh", "ffprobe": info, "proxy": dst,
                           "proxy_w": pi.get("w"), "proxy_h": pi.get("h"), "proxy_fps": pi.get("fps")}],
                "chinh": {"proxy": dst, "am16": None, "am48": None, "fps": pi.get("fps")}})
    return dst, float(pi.get("fps") or 30.0)


def _chon_su_kien(dh, toi_da, toi_da_vet=3):
    """→ tối đa `toi_da` sự kiện để soi + cận:
    · VỆT CHỮ thô (OCR mỗi 0,5 s) mà máy CHƯA đo dày được (bỏ qua/lỗi — thường là chữ hook to nhất), tối đa `toi_da_vet`, ưu tiên chữ cao,
      bỏ vệt trùng chỗ/giờ với sự kiện đo được;
    · phần còn lại: sự kiện đo được (có tinh.hop), ưu tiên ĐA DẠNG (vai, kiểu vào, kiểu ra), rải theo thời gian; kiểu không đo được xếp sau."""
    ds = []
    for s in dh.get("su_kien") or []:
        if s.get("bo_qua") or s.get("loi") or not (s.get("tinh") or {}).get("hop"):
            continue
        h = _hop_su_kien(s)
        if (h[2] - h[0]) < 0.012 or (h[3] - h[1]) < 0.008:
            continue
        ds.append(s)

    def trung(h1, a1, b1, h2, a2, b2):
        x = max(0.0, min(h1[2], h2[2]) - max(h1[0], h2[0])) * max(0.0, min(h1[3], h2[3]) - max(h1[1], h2[1]))
        nho = min((h1[2] - h1[0]) * (h1[3] - h1[1]), (h2[2] - h2[0]) * (h2[3] - h2[1])) or 1e-6
        return x / nho > 0.3 and min(b1, b2) - max(a1, a2) > -0.05

    da = [(_hop_su_kien(s), float(s.get("t_vao") or 0), float(s.get("t_ra") or (s.get("t_vao") or 0) + 1.0)) for s in ds]
    vet_chon = []
    for v in sorted(dh.get("vet_chu") or [], key=lambda v: (-float(v.get("cao_dong") or 0), v.get("t_dau") or 0)):
        if len(vet_chon) >= min(toi_da_vet, toi_da):
            break
        h = v.get("hop")
        if not h or (h[2] - h[0]) < 0.03 or float(v.get("t_ra") or 0) - float(v.get("t_dau") or 0) < 0.4:
            continue
        a1, b1 = float(v["t_dau"]), float(v["t_ra"])
        if any(hd and trung(h, a1, b1, hd, a2, b2) for hd, a2, b2 in da):
            continue
        vet_chon.append({"id": f"v{len(vet_chon) + 1:02d}", "vai": f"vet_{v.get('vai')}", "t_vao": round(a1, 2), "t_ra": round(b1, 2), "_vet": True,
                         "tinh": {"hop": [float(x) for x in h]}, "vao": {"t_bat_dau": round(max(0.0, a1 - 0.45), 2), "t_du": round(a1 + 0.05, 2)}})
        da.append((h, a1, b1))
    nhom = {}
    for s in sorted(ds, key=lambda s: s.get("t_vao") or 0):
        k = (s["vai"], (s.get("vao") or {}).get("kieu"), (s.get("ra") or {}).get("kieu"))
        nhom.setdefault(k, []).append(s)

    def rai(l):                                   # đầu, cuối, rồi giữa ra
        n = len(l)
        if n <= 2:
            return l
        return [l[0], l[-1]] + [l[i] for i in sorted(range(1, n - 1), key=lambda i: abs(i - (n - 1) / 2.0))]

    hang = {k: rai(v) for k, v in nhom.items()}
    thu_tu = {"tieu_de": 0, "nhan": 1, "do_hoa": 2, "phu_de": 3}
    keys = sorted(hang, key=lambda k: (k[1] in (None, "khong_do_duoc"), thu_tu.get(k[0], 9), hang[k][0].get("t_vao") or 0))
    chon, r, con = [], 0, toi_da - len(vet_chon)
    while len(chon) < con and any(r < len(hang[k]) for k in keys):
        for k in keys:
            if r < len(hang[k]) and len(chon) < con:
                chon.append(hang[k][r])
        r += 1
    return sorted(chon + vet_chon, key=lambda s: s.get("t_vao") or 0)


def _moc(sk, dur):
    """các mốc giây của một sự kiện: (t_bd, t_du, t_ra|None, t_ra_bd|None, t_ra_het|None, t_du_hien)"""
    v = sk.get("vao") or {}
    t_vao = float(sk.get("t_vao") or 0)
    t_bd = v.get("t_bat_dau"); t_du = v.get("t_du")
    t_bd = float(t_bd) if t_bd is not None else t_vao
    t_du = float(t_du) if t_du is not None else t_bd + 0.4
    t_ra = sk.get("t_ra")
    t_ra = float(t_ra) if t_ra is not None and float(t_ra) < dur - 0.1 else None
    r = sk.get("ra") or {}
    r_bd = float(r["t_bat_dau"]) if r.get("t_bat_dau") is not None else None
    r_het = float(r["t_het"]) if r.get("t_het") is not None else None
    tran = (r_bd if r_bd is not None else t_ra) if t_ra is not None else dur
    hien = max(t_du + 0.12, t_vao + 0.3)               # lúc chữ ĐỦ (đã chốt), chưa ra
    hien = max(min(hien, tran - 0.08, dur - 0.05), min(t_du, dur - 0.05))
    return t_bd, t_du, t_ra, r_bd, r_het, hien


def _hop_su_kien(sk):
    """hộp cần nhìn = hộp đo lúc đủ ∪ thẻ nền ∪ hộp OCR thô (hộp đo có lúc chỉ bám một mẩu nét/vai áo; hộp OCR thô giữ đủ dòng chữ)"""
    t = sk.get("tinh") or {}
    h = list(t.get("hop"))
    for nh in ((t.get("nen") or {}).get("hop"), sk.get("hop_tho")):
        if nh:
            h = [min(h[0], nh[0]), min(h[1], nh[1]), max(h[2], nh[2]), max(h[3], nh[3])]
    return [min(max(x, 0.0), 1.0) for x in h]


def _roi_soi(sk, W, H):
    """vùng soi (px video gốc W×H) quanh chữ + lề ~0,6 cao chữ, gồm đường vào (slide/pop), tỉ lệ rộng/cao 0,75–1,48"""
    h = _hop_su_kien(sk)
    x0, y0, x1, y1 = h[0] * W, h[1] * H, h[2] * W, h[3] * H
    bw, bh = x1 - x0, y1 - y0
    p = max(0.6 * bh, 0.03 * W)
    x0 -= p; x1 += p; y0 -= p; y1 += p
    v = sk.get("vao") or {}
    kieu, huong = v.get("kieu"), v.get("huong")
    if kieu == "slide":
        if huong == "tu_phai": x1 += 0.6 * bw
        elif huong == "tu_trai": x0 -= 0.6 * bw
        elif huong == "tu_duoi": y1 += 1.5 * bh
        elif huong == "tu_tren": y0 -= 1.5 * bh
    elif kieu == "pop":
        x0 -= 0.15 * bw; x1 += 0.15 * bw; y0 -= 0.3 * bh; y1 += 0.3 * bh
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, h_ = x1 - x0, y1 - y0
    can = 0.15 * min(W, H)                             # tối thiểu một chút bối cảnh quanh chữ/icon nhỏ
    w, h_ = max(w, can), max(h_, can)
    if w / h_ > 1.48:                                  # 1,48 × 260 px → 4 ô một hàng trong 1568 px
        h_ = w / 1.48
    elif w / h_ < 0.75:
        w = h_ * 0.75
    w, h_ = min(w, W), min(h_, H)
    x0 = int(min(max(cx - w / 2, 0), W - w)) // 2 * 2; y0 = int(min(max(cy - h_ / 2, 0), H - h_)) // 2 * 2
    return x0, y0, min(int(w) // 2 * 2, W - x0), min(int(h_) // 2 * 2, H - y0)


def _luoi_ts(a, b, fps, dur):
    a, b = max(0.0, a), min(dur - 0.02, b)
    if b <= a:
        return []
    n = int(math.floor((b - a) * fps + 1e-6)) + 1
    return [round(a + k / fps, 3) for k in range(n)]


def _cua_so_soi(sk, dur):
    """→ [("VÀO", [ts]), ("RA", [ts])] theo mốc máy đo"""
    t_bd, t_du, t_ra, r_bd, r_het, _ = _moc(sk, dur)
    t_vao = float(sk.get("t_vao") or t_bd)
    a = min(t_vao, t_bd) - BC["vao_truoc"]
    b = max(t_vao + BC["vao_sau"], t_du + 0.15)
    b = min(b, a + BC["vao_toi_da"])
    ra = [("VÀO", _luoi_ts(a, b, BC["soi_fps"], dur))]
    if t_ra is not None:
        if r_bd is not None and r_het is not None:
            a2, b2 = min(r_bd, r_het) - 0.3, max(r_bd, r_het) + 0.25
        else:
            a2, b2 = t_ra - BC["ra_truoc"], t_ra + BC["ra_sau"]
        if b2 - a2 > BC["ra_toi_da"]:
            a2 = b2 - BC["ra_toi_da"]
        a2 = max(a2, b + 1.0 / BC["soi_fps"])          # không lặp lại khung của cửa sổ VÀO
        ts2 = _luoi_ts(a2, b2, BC["soi_fps"], dur) if b < t_ra + 0.2 else []   # cửa sổ VÀO đã phủ lúc ra → khỏi tách
        if len(ts2) >= 3:
            ra.append(("RA", ts2))
    return ra


def _ghi_trang(khoi, rong, duong_ham, tieu_de, chat=88):
    """khoi: list ảnh numpy RGB (mỗi khối là một hàng đã dựng) → phân trang cao ≤ canh_bang, tiêu đề lặp mỗi trang → [đường]"""
    from PIL import Image
    tran = BC["canh_bang"]
    trang, cur, cao = [], [], tieu_de.shape[0]
    for k in khoi:
        if cur and cao + k.shape[0] > tran:
            trang.append(cur); cur, cao = [], tieu_de.shape[0]
        cur.append(k); cao += k.shape[0]
    if cur:
        trang.append(cur)
    ra = []
    for i, ks in enumerate(trang):
        tong = np.full((tieu_de.shape[0] + sum(k.shape[0] for k in ks), rong, 3), _DEN, np.uint8)
        tong[:tieu_de.shape[0], :tieu_de.shape[1]] = tieu_de
        y = tieu_de.shape[0]
        for k in ks:
            tong[y:y + k.shape[0], :k.shape[1]] = k
            y += k.shape[0]
        p = duong_ham(i)
        Image.fromarray(tong).save(p, quality=chat)
        ra.append(p)
    return ra


def _khoi_chu(dong, rong, co=18, mau=(235, 235, 235), dam_dau=True):
    """các dòng chữ → ảnh RGB rộng `rong` (tự xuống dòng theo bề rộng)"""
    from PIL import Image, ImageDraw
    f0, f1 = _fnt(co + 2, True), _fnt(co)
    tmp = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    hang = []
    for i, d in enumerate(dong):
        f = f0 if (i == 0 and dam_dau) else f1
        tu, cur = d.split(" "), ""
        for w in tu:
            thu = (cur + " " + w).strip()
            if tmp.textlength(thu, font=f) > rong - 16 and cur:
                hang.append((cur, f)); cur = w
            else:
                cur = thu
        hang.append((cur, f))
    lh = co + 9
    im = Image.new("RGB", (rong, 8 + lh * len(hang) + 4), _DEN)
    dr = ImageDraw.Draw(im)
    for i, (s, f) in enumerate(hang):
        dr.text((8, 6 + i * lh), s, font=f, fill=(255, 210, 0) if f is f0 else mau)
    return np.asarray(im)


def _hang_o(o_ds, cw, ch, rong, nhan_co=15):
    """o_ds: [(BGR|None, nhãn, màu viền|None)] cùng cỡ cw×ch → list khối hàng RGB"""
    from PIL import Image, ImageDraw
    gap = 4
    cot = max(1, (rong - gap) // (cw + gap))
    f = _fnt(nhan_co, True)
    ra = []
    for r0 in range(0, len(o_ds), cot):
        phan = o_ds[r0:r0 + cot]
        im = np.full((ch + gap, rong, 3), _DEN, np.uint8)
        for c, (bgr, _, vien) in enumerate(phan):
            x = gap + c * (cw + gap)
            if bgr is None:
                continue
            o = cv2.resize(bgr, (cw, ch), interpolation=cv2.INTER_AREA if bgr.shape[1] >= cw else cv2.INTER_CUBIC)
            o = cv2.cvtColor(o, cv2.COLOR_BGR2RGB)
            if vien:
                cv2.rectangle(o, (0, 0), (cw - 1, ch - 1), vien, 3)
            im[0:ch, x:x + cw] = o
        pi = Image.fromarray(im)
        dr = ImageDraw.Draw(pi)
        for c, (_, nh, vien) in enumerate(phan):
            if not nh:
                continue
            x = gap + c * (cw + gap)
            x0, y0, x1, y1 = dr.textbbox((x + 5, 3), nh, font=f)
            dr.rectangle((x + 1, 1, x1 + 4, y1 + 3), fill=vien if vien else (0, 0, 0))
            dr.text((x + 5, 3), nh, font=f, fill=(0, 0, 0) if vien else (255, 255, 255))
        ra.append(np.asarray(pi))
    return ra


def _doc_goc_nhieu(video, info, yeu_cau):
    """MỘT lượt đọc tuần tự VIDEO GỐC (độ phân giải đầy đủ; tránh seek — GOP dài thì mỗi lần seek phải giải mã lại vài giây).
    yeu_cau: {khoá: (giây, hộp chuẩn hoá [x0,y0,x1,y1], (rộng, cao) đích | None)} → {khoá: BGR đã cắt (và thu/phóng nếu có đích)}"""
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        raise RuntimeError(f"cv2 không mở được {video}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or info.get("fps") or 30.0) or 30.0
    n_v = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    theo_khung = {}
    for k, (t, hop, dich) in yeu_cau.items():
        j = int(round(float(t) * fps))
        j = max(0, min(j, n_v - 1)) if n_v else max(0, j)
        theo_khung.setdefault(j, []).append((k, hop, dich))
    ra = {}
    cuoi = max(theo_khung) if theo_khung else -1
    j = 0
    while j <= cuoi:
        if not cap.grab():
            break
        if j in theo_khung:
            ok, f = cap.retrieve()
            if ok and f is not None:
                H, W = f.shape[:2]
                for k, hop, dich in theo_khung[j]:
                    x0, y0 = int(hop[0] * W), int(hop[1] * H)
                    x1, y1 = max(x0 + 2, int(math.ceil(hop[2] * W))), max(y0 + 2, int(math.ceil(hop[3] * H)))
                    c = f[y0:y1, x0:x1]
                    if dich:
                        c = cv2.resize(c, dich, interpolation=cv2.INTER_AREA if c.shape[1] >= dich[0] else cv2.INTER_CUBIC)
                    ra[k] = np.ascontiguousarray(c)
        j += 1
    cap.release()
    return ra


def _crop_goc(sk, Wo, Ho):
    """hộp chữ (+ thẻ nền) lúc đủ, px video gốc, có lề để thấy viền/bóng/bo góc"""
    h = _hop_su_kien(sk)
    x0, y0, x1, y1 = h[0] * Wo, h[1] * Ho, h[2] * Wo, h[3] * Ho
    bh = y1 - y0
    p = max(0.35 * bh, 0.015 * Wo)
    x0 = max(0, int(x0 - p)) // 2 * 2; y0 = max(0, int(y0 - p)) // 2 * 2
    x1 = min(Wo, int(math.ceil(x1 + p))); y1 = min(Ho, int(math.ceil(y1 + p)))
    w = max(16, (x1 - x0) // 2 * 2); hh = max(16, (y1 - y0) // 2 * 2)
    w = min(w, Wo - x0); hh = min(hh, Ho - y0)
    return x0, y0, w, hh


def _phong(bgr, s):
    if abs(s - 1.0) < 1e-3:
        return bgr
    w, h = max(2, int(round(bgr.shape[1] * s))), max(2, int(round(bgr.shape[0] * s)))
    return cv2.resize(bgr, (w, h), interpolation=cv2.INTER_LANCZOS4 if s > 1 else cv2.INTER_AREA)


def _nhan_sk(sk, t_bd, t_du):
    t = sk.get("tinh") or {}
    v = sk.get("vao") or {}
    r = sk.get("ra") or {}
    nen = t.get("nen") or {}
    if sk.get("_vet"):
        return [f"{sk['id']} · {sk['vai']} (vệt chữ OCR thô, máy CHƯA đo dày — chỉ có mắt bạn)",
                f"có chữ trong khoảng {sk['t_vao']}–{sk['t_ra']}s (bước dò 0,5 s: lúc vào thật nằm trong ~0,5 s trước {sk['t_vao']}s)",
                "không có số đo kiểu vào/ra, font, màu — tự nhìn"]
    d1 = f"{sk['id']} · {sk['vai']} · OCR «{(t.get('chu_ocr') or '').strip()[:70]}»"
    d2 = (f"VÀO {v.get('kieu')}{('/' + v['huong']) if v.get('huong') else ''} {v.get('dai', '?')}s {v.get('ease') or ''}"
          f" (máy: bắt đầu {t_bd:.2f}s → đủ {t_du:.2f}s)"
          + (f" · RA {r.get('kieu')} {r.get('dai', '')}s" if r else (f" · RA ? (chưa đo, biến mất ~{sk['t_ra']}s)" if sk.get("t_ra") else ""))
          + (f" · THẺ vào {sk['vao_nen'].get('kieu')} {sk['vao_nen'].get('dai', '')}s" if sk.get("vao_nen") else ""))
    d3 = ("máy đo: " + ", ".join(x for x in (
        f"mực {t.get('cao_muc_px_1920')}px/1920" if t.get("cao_muc_px_1920") else "",
        f"{t.get('hoa')}" if t.get("hoa") else "", f"đậm~{t.get('dam_uoc')}" if t.get("dam_uoc") else "",
        f"chữ {t.get('mau_chu')}" if t.get("mau_chu") else "", f"viền={t.get('vien_chu')}" if "vien_chu" in t else "",
        f"bóng={t.get('bong_chu')}" if "bong_chu" in t else "",
        f"nền {nen.get('hinh')} bo{nen.get('bo_px_1080')} {nen.get('mau')}" if nen else "nền: không đo thấy",
        f"{(t.get('so_voi_mat') or {}).get('vi_tri')}" if t.get("so_voi_mat") else "") if x))
    return [d1, d2, d3]


def _lien_ket(p, q):
    """đặt tệp p ở tên q mà KHÔNG chép đôi: hardlink (cùng ổ) → không được thì dời"""
    try:
        if os.path.exists(q):
            os.remove(q)
        os.link(p, q)
    except OSError:
        os.replace(p, q)
    return q


def _bang_chung(video, thu_muc, dh, info, log=print, yc_them=None):
    """proxy 540p → khung.do + khung.bang(day); mỗi sự kiện tiêu biểu: dải SOI (12 khung/s, ô ≥ 260 px) + CẬN CHỮ — cả hai cắt từ
    VIDEO GỐC trong một lượt đọc → {"khung": [jpg], "soi": [jpg], "chi_tiet": [jpg], "su_kien": [id], "giay": {...}, "goc_them": {...}}
    yc_them: yêu cầu khung thêm (bảng đều / bảng sự kiện của chuan_bi) đọc chung lượt → trả ở "goc_them"."""
    t0 = time.time()
    g = {}
    for m in ("bang-su-kien-khung-*.jpg", "bang-su-kien-soi-*.jpg", "bang-su-kien-chi-tiet-chu-*.jpg"):
        for p in glob.glob(os.path.join(glob.escape(thu_muc), m)):
            try:
                os.remove(p)
            except OSError:
                pass
    ra = {"khung": [], "soi": [], "chi_tiet": [], "su_kien": [], "goc_them": {}}
    dur = float(info.get("dur") or 0)
    proxy, fps_p = _proxy_mau(video, thu_muc, info, log)
    g["proxy"] = round(time.time() - t0, 1)
    K = _nap_khung_doc()
    # ---- tầng 1 + 2 của mắt ba tầng: toàn video dày
    try:
        t1 = time.time()
        K.do(thu_muc, proxy)
        g["tang1"] = round(time.time() - t1, 1)
        t1 = time.time()
        bk = K.bang(thu_muc, BC["bang_muc"], ten="bang-khung")
        for i, p in enumerate(bk.get("anh") or []):
            # 1.2.21: không chép đôi — doc/bang-khung*.jpg ghi một lần, tên bang-su-kien-khung-N là hardlink (hoặc dời)
            ra["khung"].append(_lien_ket(p, os.path.join(thu_muc, f"bang-su-kien-khung-{i + 1}.jpg")))
        g["tang2"] = round(time.time() - t1, 1)
        ra["khung_meta"] = {"so_khung": bk.get("so_khung"), "muc": bk.get("muc"),
                            "khoang": [[b.get("tu"), b.get("den")] for b in bk.get("bang") or []]}
    except Exception as e:
        log(f"(bảng khung tầng 1–2 chưa chạy được: {str(e)[:200]})")
    chon = _chon_su_kien(dh or {}, BC["toi_da_su_kien"])
    if not chon:
        if yc_them:
            t1 = time.time()
            ra["goc_them"] = _doc_goc_nhieu(video, info, dict(yc_them))
            g["doc_goc"] = round(time.time() - t1, 1)
        g["tong"] = round(time.time() - t0, 1)
        ra["giay"] = g
        return ra
    cap = cv2.VideoCapture(proxy)
    Wp, Hp = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_p = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    cap.release()
    Wo, Ho = int(info["w"]), int(info["h"])
    fps_o = float(info.get("fps") or 30.0) or 30.0
    jt = lambda t: max(0, min(n_p - 1 if n_p else 10 ** 9, int(round(t * fps_p))))
    # ---- kế hoạch: mọi khung cần cắt từ video gốc (một lượt đọc)
    ke_hoach, yc, can_j = [], {}, set()
    for sk in chon:
        moc = _moc(sk, dur)
        t_bd, t_du, t_ra, r_bd, r_het, t_hien = moc
        cs = _cua_so_soi(sk, dur)
        x, y, w, h = _roi_soi(sk, Wo, Ho)
        s = BC["o_soi"] / float(min(w, h))                 # cạnh ngắn ô soi = o_soi
        cw, ch = max(2, int(round(w * s))), max(2, int(round(h * s)))
        roi_n = [x / Wo, y / Ho, (x + w) / Wo, (y + h) / Ho]
        for pha, ts in cs:
            for t in ts:
                yc[(sk["id"], "soi", pha, t)] = (t, roi_n, (cw, ch))
        cx, cy, cw2, ch2 = _crop_goc(sk, Wo, Ho)
        crop_n = [cx / Wo, cy / Ho, (cx + cw2) / Wo, (cy + ch2) / Ho]
        dai = t_du - t_bd
        if sk.get("_vet"):
            t30, t70 = t_bd, float(sk["t_vao"])
            n30, n70 = f"~0,45 s trước khi máy dò thấy · {t30:.2f}s", f"lúc máy dò thấy · {t70:.2f}s"
        elif dai >= 2.0 / fps_o:
            t30, t70 = t_bd + 0.3 * dai, t_bd + 0.7 * dai
            n30, n70 = f"30% quá trình vào · {t30:.2f}s", f"70% quá trình vào · {t70:.2f}s"
        else:
            t30, t70 = max(0.0, t_bd - 0.1), t_du
            n30, n70 = f"trước khi vào · {t30:.2f}s (máy: bật ngay)", f"khung vừa hiện · {t70:.2f}s"
        for ten, t in (("du", t_hien), ("30", t30), ("70", t70)):
            yc[(sk["id"], "can", ten, 0)] = (t, crop_n, None)
        can_j.add(jt(t_hien))
        ke_hoach.append(dict(sk=sk, moc=moc, cs=cs, o=(cw, ch, s), can=(cx, cy, cw2, ch2), t3=(t30, t70, n30, n70)))
    t1 = time.time()
    if yc_them:
        yc.update(yc_them)
    goc = _doc_goc_nhieu(video, info, yc)
    if yc_them:
        ra["goc_them"] = {k: goc.pop(k) for k in list(yc_them) if k in goc}
    g["doc_goc"] = round(time.time() - t1, 1)
    t1 = time.time()
    kh = K._doc_khung(proxy, sorted(can_j))
    g["doc_proxy"] = round(time.time() - t1, 1)
    t1 = time.time()
    rong = BC["canh_bang"]
    for kh_ in ke_hoach:
        sk = kh_["sk"]
        sid = sk["id"]
        try:
            t_bd, t_du, t_ra, r_bd, r_het, t_hien = kh_["moc"]
            nhan = _nhan_sk(sk, t_bd, t_du)
            # (a) dải SOI
            cw, ch, s = kh_["o"]
            tieu = _khoi_chu(nhan + [f"DẢI SOI {BC['soi_fps']:.0f} khung/s, vùng quanh chữ cắt từ video gốc (×{s:.2f}) "
                                     f"(vàng = máy đo bắt đầu, xanh = máy đo đủ, đỏ = hết lúc ra)"], rong)
            khoi = []
            for pha, ts in kh_["cs"]:
                khoi.append(_khoi_chu([f"— {pha} —"], rong, co=15))
                if pha == "VÀO":
                    kb = min(ts, key=lambda t: abs(t - t_bd)); kd = min(ts, key=lambda t: abs(t - t_du))
                    mb, md = (255, 215, 0), (60, 220, 90)
                else:
                    kb = min(ts, key=lambda t: abs(t - r_bd)) if r_bd is not None else None
                    kd = min(ts, key=lambda t: abs(t - (r_het if r_het is not None else t_ra)))
                    mb, md = (255, 215, 0), (240, 70, 60)
                if sk.get("_vet"):
                    kb = kd = None
                o = [(goc.get((sid, "soi", pha, t)), f"{t:.2f}s", mb if t == kb else md if t == kd else None) for t in ts]
                khoi += _hang_o(o, cw, ch, rong)
            ra["soi"] += _ghi_trang(khoi, rong, lambda i: os.path.join(thu_muc, f"bang-su-kien-soi-{sid}.jpg" if i == 0 else f"bang-su-kien-soi-{sid}-{i + 1}.jpg"), tieu)
            # (b) CẬN CHỮ
            cx, cy, cw2, ch2 = kh_["can"]
            t30, t70, n30, n70 = kh_["t3"]
            du = goc.get((sid, "can", "du", 0))
            if du is None:
                raise RuntimeError("không đọc được khung gốc lúc đủ")
            cw2, ch2 = du.shape[1], du.shape[0]
            sc = max(BC["can_rong"] / float(cw2), BC["can_cao"] / float(ch2), 1.0)
            sc = min(sc, BC["can_rong_max"] / float(cw2), BC["can_cao_max"] / float(ch2), BC["can_phong_max"])
            to = _phong(du, sc)
            sc2 = sc if 2 * to.shape[1] + 24 <= rong else (rong - 24) / (2.0 * cw2)
            if ch2 > cw2:                                      # cận dọc (đồ hoạ cao): 30%/70% nửa cỡ, đứng cạnh ảnh đủ
                sc2 = 0.5 * sc
            nho = [(_phong(goc[(sid, "can", k, 0)], sc2) if goc.get((sid, "can", k, 0)) is not None else None) for k in ("30", "70")]
            fp = kh.get(jt(t_hien))
            toan = None
            if fp is not None:
                fp = fp.copy()
                cv2.rectangle(fp, (int(cx * Wp / Wo), int(cy * Hp / Ho)), (int((cx + cw2) * Wp / Wo), int((cy + ch2) * Hp / Ho)), (0, 140, 255), 2)
                th = int(min(560, max(300, to.shape[0])))
                toan = cv2.resize(fp, (max(2, int(round(th * Wp / float(Hp)))), th), interpolation=cv2.INTER_AREA)
            khoi, cur, cur_w = [], [], 6
            for anh, nh in ((to, f"ĐỦ · {t_hien:.2f}s · gốc {Wo}×{Ho}, phóng ×{sc:.1f}"), (toan, "toàn khung (proxy) · ô cam = vùng cận"),
                            (nho[0], n30), (nho[1], n70)):
                if anh is None:
                    continue
                wo = max(anh.shape[1], int(_fnt(15, True).getlength(nh)) + 4)
                if cur and cur_w + wo + 6 > rong:
                    khoi.append(_ghep_ngang(cur, cur_w)); cur, cur_w = [], 6
                cur.append((anh, nh)); cur_w += wo + 6
            if cur:
                khoi.append(_ghep_ngang(cur, cur_w))
            rong2 = min(rong, max(900, max(k.shape[1] for k in khoi)))
            khoi = [_le_phai(k, rong2) for k in khoi]
            tieu2 = _khoi_chu(nhan + ["CẬN CHỮ từ VIDEO GỐC: nhìn font (có chân/không chân, đậm, HOA), viền, bóng, nền thẻ, bo góc, màu, "
                                      "cách chữ hiện (từng ký tự / từng từ / mặt nạ / mờ / phóng)"], rong2)
            ra["chi_tiet"] += _ghi_trang(khoi, rong2, lambda i: os.path.join(thu_muc, f"bang-su-kien-chi-tiet-chu-{sid}.jpg" if i == 0 else f"bang-su-kien-chi-tiet-chu-{sid}-{i + 1}.jpg"), tieu2, chat=92)
            ra["su_kien"].append(sid)
        except Exception:
            import traceback
            log(f"  (bằng chứng {sid} lỗi: {traceback.format_exc(limit=2)[-300:]})")
    g["ve"] = round(time.time() - t1, 1)
    g["tong"] = round(time.time() - t0, 1)
    ra["giay"] = g
    log(f"  bằng chứng nhìn rõ: {len(ra['khung'])} bảng khung, {len(ra['soi'])} dải soi, {len(ra['chi_tiet'])} cận chữ "
        f"({len(ra['su_kien'])} sự kiện) trong {g['tong']}s {g}")
    return ra


def _ghep_ngang(ds, rong):
    """[(BGR, nhãn)] → một hàng RGB: nhãn trên, ảnh dưới; mỗi ô rộng = max(ảnh, nhãn) để nhãn không chồng nhau"""
    from PIL import Image, ImageDraw
    f = _fnt(15, True)
    cao = max(a.shape[0] for a, _ in ds) + 26
    o = [max(a.shape[1], int(f.getlength(nh)) + 4) for a, nh in ds]
    rong = int(min(BC["canh_bang"], max(rong, 6 + sum(w + 6 for w in o))))
    im = np.full((cao, rong, 3), _DEN, np.uint8)
    x = 6
    for (a, _), w in zip(ds, o):
        ww = min(a.shape[1], rong - x)
        if ww > 0:
            im[22:22 + a.shape[0], x:x + ww] = cv2.cvtColor(a[:, :ww], cv2.COLOR_BGR2RGB)
        x += w + 6
    pi = Image.fromarray(im)
    dr = ImageDraw.Draw(pi)
    x = 6
    for (a, nh), w in zip(ds, o):
        dr.text((x, 2), nh, font=f, fill=(255, 210, 0))
        x += w + 6
    return np.asarray(pi)


def _le_phai(k, rong):
    if k.shape[1] == rong:
        return k
    if k.shape[1] > rong:
        return k[:, :rong]
    ra = np.full((k.shape[0], rong, 3), _DEN, np.uint8)
    ra[:, :k.shape[1]] = k
    return ra


HUONG_DAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "HUONG-DAN-AI.md")


def chuan_bi(video, thu_muc, log=print, dong_hoc=True, bang_chung=True):
    """→ {"bang_deu": jpg, "bang_su_kien": [jpg...], "so_lieu": {...}, "dong_hoc": json, "spec_may": json,
          "bang_khung": [jpg], "soi": [jpg], "chi_tiet_chu": [jpg]} — máy đo, chưa gọi AI.
    bang_su_kien (thứ tự mở): bang-su-kien-N (quanh cắt cảnh) → bang-su-kien-khung-N (khung dày toàn video, tầng 2 mức "day")
    → bang-su-kien-dong-hoc-N (dải động học) → mỗi sự kiện tiêu biểu: bang-su-kien-soi-<id> + bang-su-kien-chi-tiet-chu-<id>
    1.2.21: cắt cảnh lấy từ quét thô của dong_hoc (không còn ffmpeg scene-detect riêng); bảng đều + bảng sự kiện + dải soi + cận chữ
    đọc video gốc trong MỘT lượt; proxy 540p tạo trước để dong_hoc/ban_ghi dùng cho mặt nạ người."""
    os.makedirs(thu_muc, exist_ok=True)
    t_all = time.time()
    g = {}
    info = C.ffprobe(video) or {}
    dur = float(info.get("dur") or 0)
    if dur <= 0:
        raise SystemExit("không đọc được video mẫu")
    so_lieu = {"dur": dur, "w": info.get("w"), "h": info.get("h"), "fps": info.get("fps")}
    # 0) proxy 540p trước (dong_hoc/ban_ghi tách người trên proxy; bằng chứng dùng lại)
    try:
        t1 = time.time()
        _proxy_mau(video, thu_muc, info, log)
        g["proxy"] = round(time.time() - t1, 1)
    except Exception as e:
        log(f"(proxy mẫu chưa tạo được: {str(e)[:160]})")
    # 1) mặt trung bình nếu có doc.mat
    try:
        t1 = time.time()
        from doc import mat as M
        tmp = os.path.join(thu_muc, "_mat")
        os.makedirs(tmp, exist_ok=True)
        M.quet(tmp, video)
        mj = C.doc_json(os.path.join(tmp, "doc", "mat.json"), {}) or {}
        so_lieu["mat_tb"] = mj.get("mat_tb")
        so_lieu["nguoi_ti_le"] = mj.get("nguoi_ti_le")
        g["mat"] = round(time.time() - t1, 1)
    except Exception as e:
        so_lieu["mat_tb"] = None
        log(f"(mắt máy chưa sẵn sàng: {e})")
    # 2) ĐỘNG HỌC đo máy (D2 chữ + D3 đồ hoạ) — cũng cho cắt cảnh (histogram quét thô). Ảnh "bang-su-kien-dong-hoc-N.jpg" để cau_noi in cho AI mở.
    kq = {"bang_deu": None, "bang_su_kien": [], "so_lieu": so_lieu}
    dh = None
    cat = []
    if dong_hoc:
        try:
            t1 = time.time()
            DH = nap_dong_hoc()
            tm = thu_muc.replace("\\", "/")
            hd = HUONG_DAN.replace("\\", "/")
            dh = DH.phan_tich(video, thu_muc, log=log, ten_anh="bang-su-kien-dong-hoc",
                              dong_dau_anh=f"AI: đọc {hd} · số đo {tm}/dong_hoc.json · spec máy {tm}/spec-may.json — viết spec TỪ SỐ ĐO, mắt chỉ xác nhận")
            C.ghi_json(os.path.join(thu_muc, "spec-may.json"), dh["spec_may"])
            tt = dh.get("tong_hop") or {}
            so_lieu["dong_hoc"] = {
                "duong": dh["duong"], "spec_may": os.path.join(thu_muc, "spec-may.json"), "huong_dan_ai": HUONG_DAN,
                "vao_chu": [f"{r['kieu']} {r['tan_suat']:.0%} {r['dai_tv']}s {r.get('ease') or ''}".strip() for r in (tt.get("vao_chu") or [])[:4]],
                "ra_chu": [f"{r['kieu']} {r['tan_suat']:.0%} {r['dai_tv']}s" for r in (tt.get("ra_chu") or [])[:3]],
                "vao_phu_de": [f"{r['kieu']} {r['tan_suat']:.0%}" for r in (tt.get("vao_phu_de") or [])[:2]],
                "so_lop_chu": tt.get("so_lop_chu"), "giay": dh.get("giay"),
                "so_vet_nghi_ngo": sum(1 for v in (dh.get("vet_chu") or []) if v.get("nghi_ngo"))}
            kq["dong_hoc"] = dh["duong"]
            kq["spec_may"] = os.path.join(thu_muc, "spec-may.json")
            cat = [float(c["t"]) if isinstance(c, dict) else float(c) for c in (dh.get("cat") or [])]
            g["dong_hoc"] = round(time.time() - t1, 1)
        except Exception as e:
            import traceback
            dh = None
            so_lieu["dong_hoc"] = {"loi": str(e)[:300]}
            log(f"(động học chưa chạy được: {traceback.format_exc(limit=3)[-400:]})")
    cat = sorted(t for t in cat if 0.3 < t < dur - 0.3)
    so_lieu.update({"so_cat": len(cat), "canh_tb_s": round(dur / (len(cat) + 1), 2), "cat": [round(t, 2) for t in cat]})
    # 3) kế hoạch khung: bảng đều 24 khung + dải 4 khung quanh mỗi sự kiện (−0.3 / 0 / +0.4 / +1.0 s, tối đa 16 sự kiện) — đọc gốc MỘT lượt
    ts = [dur * (i + 0.5) / 24 for i in range(24)]
    su_kien = cat[:16] if cat else [dur * i / 8 for i in range(1, 8)]
    ts2 = [max(0.0, min(dur - 0.05, x)) for t in su_kien for x in (t - 0.3, t, t + 0.4, t + 1.0)]
    yc = _yc_khung(info, ts, 270, "deu")
    yc.update(_yc_khung(info, ts2, 220, "sk"))
    # 4) BẰNG CHỨNG NHÌN RÕ: bảng khung dày toàn video (doc/khung.py tầng 1+2 trên proxy 540p) + mỗi sự kiện tiêu biểu một dải SOI
    # (12 khung/s quanh lúc vào/ra) và một ảnh CẬN CHỮ từ video gốc — chung lượt đọc với (3).
    goc = {}
    bc = None
    if bang_chung:
        try:
            t1 = time.time()
            bc = _bang_chung(video, thu_muc, dh if dong_hoc else None, info, log=log, yc_them=yc)
            goc = bc.get("goc_them") or {}
            g["bang_chung"] = round(time.time() - t1, 1)
        except Exception as e:
            import traceback
            so_lieu["bang_chung"] = {"loi": str(e)[:300]}
            log(f"(bằng chứng nhìn rõ chưa chạy được: {traceback.format_exc(limit=3)[-400:]})")
    if not goc:
        t1 = time.time()
        goc = _doc_goc_nhieu(video, info, yc)
        g["doc_goc"] = round(time.time() - t1, 1)
    t1 = time.time()
    ks = [_rgb(goc.get(("deu", i))) for i in range(len(ts))]
    bang_deu = _bang(ks, [f"{t:.1f}s" for t in ts], 6, os.path.join(thu_muc, "bang-deu.jpg"), f"{os.path.basename(video)} · {dur:.0f}s · 24 khung đều")
    bangs = []
    for j in range(0, len(su_kien), 8):
        nhom = su_kien[j:j + 8]
        ks2, nhan = [], []
        for jj, t in enumerate(nhom):
            for kk, x in enumerate((t - 0.3, t, t + 0.4, t + 1.0)):
                ks2.append(_rgb(goc.get(("sk", (j + jj) * 4 + kk)))); nhan.append(f"{x:.2f}s")
        p = _bang(ks2, nhan, 4, os.path.join(thu_muc, f"bang-su-kien-{j // 8 + 1}.jpg"), "mỗi hàng = một sự kiện: −0.3s · 0 · +0.4s · +1.0s")
        if p:
            bangs.append(p)
    g["ve_bang"] = round(time.time() - t1, 1)
    kq["bang_deu"] = bang_deu
    kq["bang_su_kien"] = bangs + list((dh or {}).get("anh") or [])
    if bc is not None:
        theo_sk = []
        for sid in bc["su_kien"]:
            theo_sk += [p for p in bc["soi"] if os.path.basename(p).startswith(f"bang-su-kien-soi-{sid}")]
            theo_sk += [p for p in bc["chi_tiet"] if os.path.basename(p).startswith(f"bang-su-kien-chi-tiet-chu-{sid}")]
        kq["bang_su_kien"] = bangs + bc["khung"] + list((dh or {}).get("anh") or []) + theo_sk
        kq["bang_khung"], kq["soi"], kq["chi_tiet_chu"] = bc["khung"], bc["soi"], bc["chi_tiet"]
        so_lieu["bang_chung"] = {"su_kien": bc["su_kien"], "bang_khung": bc.get("khung_meta"), "giay": bc.get("giay"),
                                 "so_anh": {"khung": len(bc["khung"]), "soi": len(bc["soi"]), "chi_tiet_chu": len(bc["chi_tiet"])}}
    g["tong"] = round(time.time() - t_all, 1)
    so_lieu["giay"] = g
    log(f"  chuẩn bị xong {g['tong']}s {g}")
    C.ghi_json(os.path.join(thu_muc, "so-lieu.json"), so_lieu)
    return kq


def nap_dong_hoc():
    """nạp hoc/dong_hoc.py theo đường dẫn (an toàn cả khi `hoc` trên sys.path là tệp hoc.py chứ không phải gói)"""
    try:
        from hoc import dong_hoc as DH
        return DH
    except Exception:
        import importlib.util
        if "hoc_dong_hoc" in sys.modules:
            return sys.modules["hoc_dong_hoc"]
        sp = importlib.util.spec_from_file_location("hoc_dong_hoc", os.path.join(os.path.dirname(os.path.abspath(__file__)), "dong_hoc.py"))
        m = importlib.util.module_from_spec(sp)
        sys.modules["hoc_dong_hoc"] = m
        sp.loader.exec_module(m)
        return m


class _AnToan(dict):
    def __missing__(self, k):
        return "{" + k + "}"


def prompt_ai(ra, schema, cu, nl, anh):
    """prompt cho AI viết Style Spec: HUONG-DAN-AI.md (phần sau dấu ---8<---) + số đo máy, spec_may làm điểm xuất phát"""
    mau = open(HUONG_DAN, encoding="utf-8").read() if os.path.isfile(HUONG_DAN) else "Viết {ra} theo schema {schema}. Số đo: {so_lieu}. Ảnh: {anh}"
    if "---8<---" in mau:
        mau = mau.rsplit("---8<---", 1)[1]
    sm = C.doc_json(nl.get("spec_may") or "", None)
    du = {"ra": ra.replace("\\", "/"), "schema": json.dumps(schema, ensure_ascii=False), "cu": json.dumps(cu, ensure_ascii=False) if cu else "chưa có",
          "so_lieu": json.dumps(nl.get("so_lieu"), ensure_ascii=False), "anh": "\n".join("- " + a.replace("\\", "/") for a in anh),
          "dong_hoc": (nl.get("dong_hoc") or "(không có)").replace("\\", "/"), "spec_may": json.dumps(sm, ensure_ascii=False) if sm else "(không có)",
          "huong_dan": HUONG_DAN.replace("\\", "/")}
    return mau.format_map(_AnToan(du))


def hoc(video, ho_so, ten=None, log=print):
    """toàn bộ: chuẩn bị → AI viết style-spec.json → lưu vào hồ sơ (gộp nếu đã có: AI nhận spec cũ để hợp nhất)"""
    from ai import dong_co as DC
    hs_dir = os.path.join(C.duong("ho_so"), ho_so)
    if not os.path.isdir(hs_dir):
        raise SystemExit(f"không có hồ sơ {ho_so}")
    ten = ten or C.slug(os.path.splitext(os.path.basename(video))[0])
    thu_muc = os.path.join(hs_dir, "hoc", ten)
    with C.DoThoiGian(None, "hoc.chuan_bi"):
        nl = chuan_bi(video, thu_muc, log)
    schema = C.doc_json(os.path.join(APP, "nao", "style_spec.schema.json"), {}) or {}
    cu = C.doc_json(os.path.join(hs_dir, "style-spec.json"))
    ra = os.path.join(thu_muc, "style-spec.json")
    anh = [nl["bang_deu"]] + nl["bang_su_kien"]
    p = prompt_ai(ra, schema, cu, nl, anh)          # (ai/prompt_hoc.md của Engine dùng khoá khác — không dùng ở đây)
    with C.DoThoiGian(None, "hoc.ai"):
        kq = DC.goi(p, thu_muc, anh=anh)
    spec = C.doc_json(ra)
    if not spec:
        raise SystemExit("AI chưa ghi style-spec.json: " + str(kq.get("text", ""))[:500])
    spec["_nguon"] = {"video": video, "luc": time.strftime("%Y-%m-%d %H:%M"), "ten": ten}
    C.ghi_json(os.path.join(hs_dir, "style-spec.json"), spec)
    log(f"đã lưu style-spec vào hồ sơ {ho_so} (bài {ten}); chi phí {kq.get('usd')} USD")
    return spec


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True); ap.add_argument("--ho-so"); ap.add_argument("--ten")
    ap.add_argument("--chi-chuan-bi", metavar="THU_MUC", help="chỉ chạy máy đo vào thư mục này (không gọi AI)")
    ap.add_argument("--khong-bang-chung", action="store_true", help="bỏ bảng khung dày / dải soi / cận chữ")
    a = ap.parse_args()
    if a.chi_chuan_bi:
        r = chuan_bi(a.video, a.chi_chuan_bi, bang_chung=not a.khong_bang_chung)
        print(json.dumps({k: v for k, v in r.items() if k != "so_lieu"}, ensure_ascii=False, indent=1))
        print(json.dumps(r["so_lieu"].get("dong_hoc"), ensure_ascii=False, indent=1))
        print(json.dumps(r["so_lieu"].get("bang_chung"), ensure_ascii=False))
    else:
        if not a.ho_so:
            raise SystemExit("cần --ho-so (hoặc --chi-chuan-bi <thư mục>)")
        hoc(a.video, a.ho_so, a.ten)
