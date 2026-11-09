# -*- coding: utf-8 -*-
"""KHUNG ỨNG VIÊN BÌA — máy đo, AI chọn. Không chọn hộ khung nào "đẹp": chỉ loại cái không dùng được về vật lý (không mặt, nhoè chuyển động, quá tối)
rồi đưa NHIỀU khung rải đều thời gian kèm số đo để AI nhìn và tự quyết `bia.phuong_an[].khung_t`.

Số đo mỗi khung (0..1): net (độ sắc vùng mặt), mieng_mo (miệng há — vùng tối giữa hai mép), mat_mo (mắt mở — độ tương phản quanh hai mắt),
dong (chuyển động), mat_co (cỡ mặt), lang (nằm trong khoảng lặng lời — thường môi khép, nét mặt nghỉ), cuoi (khoé miệng cao hơn giữa môi).

  quet(du_an, proxy, log) → doc/bia-ung-vien.json + doc/bia-ung-vien.jpg (+ -2.jpg)
  python v3/doc/bia_ung_vien.py <du_an>
"""
import os, sys, json, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
import cv2
import chung

BUOC_GIAY = 0.2            # 5 khung/giây như mat.json
TOI_DA = 30                # số ứng viên đưa cho AI
O_RONG = 300


def _yunet(w, h):
    try:
        from bia import bia as B
        return B._yunet(w, h)
    except Exception:
        return None


def _nguon_chinh(du_an):
    n = chung.doc_json(os.path.join(du_an, "doc", "nguon.json"), {}) or {}
    ds = n.get("nguon") or []
    c = next((x for x in ds if x.get("vai") == "chinh"), ds[0] if ds else None)
    return (c or {}).get("duong")


def _proxy(du_an):
    try:
        from doc import khung as K
        return K._proxy(du_an)
    except Exception:
        return None


def _do_khung(bgr, f):
    """f = hàng YuNet (x,y,w,h, 5 mốc, điểm) trên ảnh bgr → số đo (đã hiệu chỉnh trên khung thật: miệng khép dải ≈ 0–0,06 cỡ miệng, há ≈ 0,2–0,35)"""
    H, W = bgr.shape[:2]
    x, y, w, h = [float(v) for v in f[:4]]
    ex1, ey1, ex2, ey2 = float(f[4]), float(f[5]), float(f[6]), float(f[7])          # hai mắt
    mx1, my1, mx2, my2 = float(f[10]), float(f[11]), float(f[12]), float(f[13])      # hai mép miệng
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    def cat(x0, y0, x1, y1):
        x0, y0 = max(0, int(x0)), max(0, int(y0)); x1, y1 = min(W, int(x1)), min(H, int(y1))
        return gray[y0:y1, x0:x1] if (x1 > x0 + 2 and y1 > y0 + 2) else None

    mat_vung = cat(x, y, x + w, y + h)
    net = float(min(1.0, cv2.Laplacian(mat_vung, cv2.CV_64F).var() / 400.0)) if mat_vung is not None else 0.0
    kc = max(4.0, math.hypot(mx2 - mx1, my2 - my1))
    ed = max(4.0, math.hypot(ex2 - ex1, ey2 - ey1))
    cx, cy = (mx1 + mx2) / 2, (my1 + my2) / 2
    # miệng: hộp giữa hai mép; dải hàng khác màu LIÊN TỤC quanh hàng nối mép (khoang miệng tối / răng sáng) tính theo cỡ miệng
    mieng_mo = 0.0
    y0 = int(cy - kc * 0.5)
    box = cat(cx - kc * 0.35, y0, cx + kc * 0.35, cy + kc * 0.6)
    if box is not None and box.shape[0] > 6:
        rows = box.astype(np.float32).mean(axis=1); lech = np.abs(rows - float(np.median(box)))
        c = min(len(rows) - 1, max(0, int(cy) - max(0, y0)))
        if lech[c] > 16:
            a = c
            while a > 0 and lech[a - 1] > 16:
                a -= 1
            b = c
            while b < len(rows) - 1 and lech[b + 1] > 16:
                b += 1
            mieng_mo = float(min(1.0, ((b - a + 1) / kc) / 0.35))
    # mắt: năng lượng gradient dọc quanh mắt so với má ngay dưới (mắt nhắm → vùng phẳng)
    r = max(3.0, kc * 0.28)

    def nang(px, py, rw, rh):
        o = cat(px - rw, py - rh, px + rw, py + rh)
        return float(np.abs(cv2.Sobel(o, cv2.CV_32F, 0, 1, ksize=3)).mean()) if (o is not None and o.size > 16) else 0.0
    e_ = (nang(ex1, ey1, r, r * 0.6) + nang(ex2, ey2, r, r * 0.6)) / 2
    ma_ = (nang(ex1, ey1 + r * 1.6, r, r * 0.6) + nang(ex2, ey2 + r * 1.6, r, r * 0.6)) / 2
    mat_mo = float(min(1.0, max(0.0, (e_ / max(ma_, 1.0) - 2.0) / 5.0)))
    cuoi = float(min(1.0, max(0.0, (kc / ed - 0.85) / 0.25)))                     # miệng rộng ra so với khoảng hai mắt
    sang = float(mat_vung.mean() / 255.0) if mat_vung is not None else 0.0
    return {"net": round(net, 2), "mieng_mo": round(mieng_mo, 2), "mat_mo": round(mat_mo, 2), "cuoi": round(cuoi, 2), "sang": round(sang, 2),
            "mat": {"x": round(x / W, 4), "y": round(y / H, 4), "w": round(w / W, 4), "h": round(h / H, 4)}}


def quet(du_an, proxy=None, log=None, toi_da=TOI_DA):
    log = log or (lambda m: None)
    proxy = proxy or _proxy(du_an)
    if not proxy or not os.path.isfile(proxy):
        return None
    loi = chung.doc_json(os.path.join(du_an, "doc", "loi.json"), {}) or {}
    lang = [(float(a), float(b)) for a, b in (loi.get("lang") or []) if isinstance((a, b), tuple) or True] if loi.get("lang") else []
    lang = [(float(x[0]), float(x[1])) for x in (loi.get("lang") or []) if isinstance(x, (list, tuple)) and len(x) >= 2]
    # giải mã MỘT lượt bằng ffmpeg ở 5 khung/giây, khổ proxy (đo miệng/mắt đủ nét), dò mặt trên bản 320 cho nhanh
    import subprocess
    inf = chung.ffprobe(proxy) or {}
    W0, H0 = int(inf.get("w") or 540), int(inf.get("h") or 960)
    cmd = [chung.duong("ffmpeg"), "-v", "error", "-i", proxy, "-vf", f"fps=1/{BUOC_GIAY}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    pr_ = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=0x08000000 if os.name == "nt" else 0)
    det = None
    uv, truoc, i = [], None, 0
    kich = W0 * H0 * 3
    while True:
        buf = pr_.stdout.read(kich)
        if len(buf) < kich:
            break
        bgr = np.frombuffer(buf, np.uint8).reshape(H0, W0, 3)
        t = i * BUOC_GIAY
        H, W = H0, W0
        ty = 320.0 / W
        nho_d = cv2.resize(bgr, (320, int(H * ty)), interpolation=cv2.INTER_AREA)
        if det is None:
            det = _yunet(nho_d.shape[1], nho_d.shape[0])
            if det is None:
                pr_.kill(); return None
        det.setInputSize((nho_d.shape[1], nho_d.shape[0]))
        _, faces = det.detect(nho_d)
        if faces is not None and len(faces):
            faces = faces.copy(); faces[:, :14] = faces[:, :14] / ty
        nho = cv2.resize(bgr, (96, int(96 * H / W)), interpolation=cv2.INTER_AREA).astype(np.int16)
        dong = float(np.abs(nho - truoc).mean() / 40.0) if truoc is not None else 0.0
        truoc = nho
        if faces is not None and len(faces):
            f = max(faces, key=lambda r: r[2] * r[3])
            d = _do_khung(bgr, f)
            d.update({"t": round(t, 2), "dong": round(min(1.0, dong), 2), "mat_co": round(float(f[2] * f[3]) / (W * H), 4),
                      "lang": any(a <= t <= b for a, b in lang)})
            uv.append(d)
        i += 1
    pr_.stdout.close(); pr_.wait()
    if not uv:
        return None
    # loại vật lý: nhoè chuyển động mạnh / mặt quá nhỏ / quá tối; rồi rải đều theo thời gian (mỗi ô thời gian lấy khung nét nhất, ưu tiên không há miệng CHỈ khi cùng ô)
    dung = [d for d in uv if d["dong"] < 0.35 and d["mat_co"] > 0.004 and d["sang"] > 0.12] or uv
    dur = uv[-1]["t"] + BUOC_GIAY
    so_o = min(toi_da, max(6, len(dung)))
    o_dai = dur / so_o
    chon = []
    for k in range(so_o):
        trong_o = [d for d in dung if k * o_dai <= d["t"] < (k + 1) * o_dai]
        if not trong_o:
            continue
        trong_o.sort(key=lambda d: (-(d["net"] * (1 - 0.5 * d["dong"])), d["mieng_mo"]))
        chon.append(trong_o[0])
    chon = chon[:toi_da]
    for j, d in enumerate(chon):
        d["n"] = j
    # vẽ bảng (lấy khung ở độ phân giải proxy; bìa thật máy lấy từ nguồn gốc khi vẽ)
    anh_ds = _ve_bang(du_an, proxy, chon)
    kq = {"ung_vien": chon, "anh": anh_ds, "tong_quet": len(uv), "dung_duoc": len(dung), "buoc": BUOC_GIAY}
    chung.ghi_json(os.path.join(du_an, "doc", "bia-ung-vien.json"), kq)
    log(f"bìa: {len(chon)} khung ứng viên (quét {len(uv)}, dùng được {len(dung)}) → {os.path.basename(anh_ds[0]) if anh_ds else '?'}")
    return kq


def _ve_bang(du_an, proxy, chon, cot=6, moi_bang=18):
    from PIL import Image, ImageDraw, ImageFont
    ra = []
    cap = cv2.VideoCapture(proxy)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    try:
        f = ImageFont.truetype(os.path.join(chung.duong("font_mac_dinh"), sorted(x for x in os.listdir(chung.duong("font_mac_dinh")) if x.lower().endswith(".ttf"))[0]), 15)
    except Exception:
        f = ImageFont.load_default()
    for b in range(0, len(chon), moi_bang):
        nhom = chon[b:b + moi_bang]
        o_anh = []
        for d in nhom:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(d["t"] * fps)))
            ok, bgr = cap.read()
            if not ok:
                continue
            H, W = bgr.shape[:2]
            s = O_RONG / W
            im = Image.fromarray(cv2.cvtColor(cv2.resize(bgr, (O_RONG, int(H * s)), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB))
            dr = ImageDraw.Draw(im)
            m = d["mat"]
            dr.rectangle([m["x"] * O_RONG, m["y"] * im.height, (m["x"] + m["w"]) * O_RONG, (m["y"] + m["h"]) * im.height], outline=(80, 220, 120), width=2)
            nhan = [f"#{d['n']}  t={d['t']:.1f}s", f"nét {d['net']:.2f}  động {d['dong']:.2f}", f"miệng {d['mieng_mo']:.2f}  mắt {d['mat_mo']:.2f}", f"{'LẶNG' if d['lang'] else 'đang nói'}  cười {d['cuoi']:.2f}"]
            dr.rectangle([0, 0, O_RONG, 4 + 17 * len(nhan)], fill=(0, 0, 0))
            for k, s_ in enumerate(nhan):
                dr.text((5, 3 + 17 * k), s_, fill=(255, 255, 255) if k else (255, 220, 80), font=f)
            o_anh.append(im)
        if not o_anh:
            continue
        cw, ch = O_RONG, max(x.height for x in o_anh)
        hang = (len(o_anh) + cot - 1) // cot
        bang = Image.new("RGB", (cot * cw + (cot + 1) * 4, hang * ch + (hang + 1) * 4), (32, 32, 32))
        for k, im in enumerate(o_anh):
            bang.paste(im, (4 + (k % cot) * (cw + 4), 4 + (k // cot) * (ch + 4)))
        p = os.path.join(du_an, "doc", "bia-ung-vien" + ("" if b == 0 else f"-{b // moi_bang + 1}") + ".jpg")
        bang.save(p, quality=88)
        ra.append(p)
    cap.release()
    return ra


def dong_tom_tat(du_an):
    kq = chung.doc_json(os.path.join(du_an, "doc", "bia-ung-vien.json"), {}) or {}
    uv = kq.get("ung_vien") or []
    if not uv:
        return []
    L = [f"## KHUNG ỨNG VIÊN BÌA — máy đo {kq.get('tong_quet')} khung, đưa {len(uv)} khung rải đều (MỞ ảnh, chọn `khung_t` cho TỪNG bìa theo mắt bạn; số đo chỉ để đối chiếu, máy không chọn)"]
    for p in kq.get("anh") or []:
        L.append(f"  ảnh: {p}")
    L.append("  #: t(giây gốc) · nét · miệng há (0 = khép) · mắt mở · động · lặng/nói · cười · cỡ mặt")
    L.append("  " + " | ".join(f"#{d['n']} {d['t']:.1f}s n{d['net']:.2f} m{d['mieng_mo']:.2f} e{d['mat_mo']:.2f} d{d['dong']:.2f} {'L' if d['lang'] else 'N'} c{d['cuoi']:.2f} s{d['mat_co']:.3f}" for d in uv))
    L.append("  Cần khung khác quanh một giây: `nhanh khung --tu <a> --den <b> --fps 10` (dải khung dày, giây gốc).")
    return L


if __name__ == "__main__":
    kq = quet(sys.argv[1], log=print)
    print("\n".join(dong_tom_tat(sys.argv[1])))
