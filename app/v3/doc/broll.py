# -*- coding: utf-8 -*-
"""MẮT B-ROLL — máy nhìn mọi video phụ / thư mục tư liệu người dùng đưa vào để AI biết CÓ GÌ, Ở GIÂY NÀO, rồi tự quyết ghép.
Không chọn hộ, không gợi ý: chỉ đo (thời lượng, khổ, tiếng, cắt cảnh, độ động, mặt người) và vẽ bảng khung có mốc giây.

  quet(du_an, duong_ds, log) → doc/b-roll.json + doc/b-roll/<n>.jpg (bảng 16 khung đều, có giây)
  soi(du_an, nguon, tu, den, fps) → doc/b-roll/soi-<n>-<tu>-<den>.jpg (dải khung dày một đoạn)
  python v3/doc/broll.py <du_an> <video|thư mục>…
"""
import os, sys, re, json, glob, hashlib, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung
import cv2

DUOI = (".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".mts", ".m2ts", ".ts", ".3gp")
TOI_DA_TEP = 16            # mỗi lần quét
TOI_DA_GIAY_PHAN_TICH = 240  # cắt cảnh/độ động chỉ đo trong 4 phút đầu (bảng khung vẫn cả video)
O_RONG = 270


def _ffprobe(p):
    try:
        return chung.ffprobe(p) or {}
    except Exception:
        return {}


def _bam(p):
    try:
        st = os.stat(p)
        return hashlib.md5(f"{os.path.abspath(p)}|{st.st_size}|{int(st.st_mtime)}".encode("utf-8")).hexdigest()[:10]
    except OSError:
        return hashlib.md5(p.encode("utf-8")).hexdigest()[:10]


def liet_ke(duong_ds, toi_da=TOI_DA_TEP):
    """đường dẫn tệp / thư mục → [tệp video] (đệ quy 1 cấp cho thư mục, bỏ tệp ẩn), giữ thứ tự, không trùng"""
    ra, bo = [], 0
    for d in duong_ds or []:
        d = os.path.expanduser(str(d))
        if os.path.isfile(d):
            if d.lower().endswith(DUOI) and d not in ra:
                ra.append(d)
            continue
        if os.path.isdir(d):
            for goc, dirs, files in os.walk(d):
                dirs[:] = sorted(x for x in dirs if not x.startswith("."))
                for f in sorted(files):
                    if f.startswith(".") or not f.lower().endswith(DUOI):
                        continue
                    p = os.path.join(goc, f)
                    if p in ra:
                        continue
                    if len(ra) >= toi_da:
                        bo += 1
                    else:
                        ra.append(p)
                if goc.count(os.sep) - d.count(os.sep) >= 1:
                    dirs[:] = []
    return ra, bo


def _nhan_giay(ra, n, cot, hang, moc):
    """ghi mốc giây lên từng ô của bảng đã ghép (PIL — không phụ thuộc fontconfig của ffmpeg)"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        im = Image.open(ra).convert("RGB"); W, H = im.size
        cw = (W - 3 * 2 - 3 * (cot - 1)) / cot; ch = (H - 3 * 2 - 3 * (hang - 1)) / hang
        try:
            f = ImageFont.truetype(os.path.join(chung.duong("font_mac_dinh"), sorted(x for x in os.listdir(chung.duong("font_mac_dinh")) if x.lower().endswith(".ttf"))[0]), 15)
        except Exception:
            f = ImageFont.load_default()
        d = ImageDraw.Draw(im)
        for i, t in enumerate(moc[:n]):
            x = 3 + (i % cot) * (cw + 3); y = 3 + (i // cot) * (ch + 3)
            txt = f"{int(t // 60)}:{t % 60:04.1f}" if t >= 60 else f"{t:.1f}s"
            d.rectangle([x + 2, y + 2, x + 2 + 7.5 * len(txt) + 8, y + 22], fill=(0, 0, 0))
            d.text((x + 6, y + 4), txt, fill=(255, 255, 255), font=f)
        im.save(ra, quality=88)
    except Exception:
        pass


def _phan_tich(p, info, ra_anh, n=16, cot=8, hwaccel=None, khung_chinh=True):
    """MỘT lượt giải mã (ffmpeg, hwaccel nếu có) ở 2 khung/giây khổ 320 → bảng khung có giây, cắt cảnh, độ động, mặt người. → (cat, dong, mat)"""
    import numpy as np
    dur = max(0.2, float(info.get("dur") or 0))
    fps_q = 2.0
    t_max = min(dur, TOI_DA_GIAY_PHAN_TICH)
    w0, h0 = float(info.get("w") or 9), float(info.get("h") or 16)
    w_ = 320; h_ = max(2, int(round(w_ * h0 / w0 / 2)) * 2)
    hw = hwaccel if hwaccel is not None else ((chung.phan_cung() or {}).get("hwaccel") or "none")
    ff = chung.duong("ffmpeg")
    lm = chung.loc_mau_vao(info)                                   # 1.2.21: B-roll HDR/10-bit → bảng khung đúng màu (AI nhìn đúng)
    # chỉ giải mã KHUNG CHÍNH (-skip_frame nokey): 3K HEVC 88 s từ 145 s còn 18 s; đủ cho bảng khung 16 ô, cắt cảnh, mặt, độ động thô
    cmd = [ff, "-v", "error"] + (["-skip_frame", "nokey"] if khung_chinh else []) + (["-hwaccel", hw] if hw and hw != "none" else []) + ["-i", p, "-an", "-t", f"{dur:.2f}",
           "-vf", f"fps={fps_q}," + (lm + "," if lm else "") + f"scale={w_}:{h_}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    pr_ = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=0x08000000 if os.name == "nt" else 0)
    kich = w_ * h_ * 3
    n_t = n if dur >= 1.0 else 4
    moc_thumb = [dur * (i + 0.5) / n_t for i in range(n_t)]
    thumbs = {}
    cat, dong_ds, mat_co, hist_truoc, nho_truoc = [], [], [], None, None
    det = None
    i = 0; khac = 0
    while True:
        buf = pr_.stdout.read(kich)
        if len(buf) < kich:
            break
        fr = np.frombuffer(buf, np.uint8).reshape(h_, w_, 3)
        t = i / fps_q
        for j, mt in enumerate(moc_thumb):
            if j not in thumbs and t >= mt - 0.5 / fps_q:
                thumbs[j] = (t, fr.copy())
        if t <= t_max:
            hsv = cv2.cvtColor(fr, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256]); cv2.normalize(hist, hist)
            nho = cv2.resize(fr, (64, max(2, int(64 * h_ / w_))), interpolation=cv2.INTER_AREA).astype(np.int16)
            if hist_truoc is not None:
                tq = cv2.compareHist(hist_truoc, hist, cv2.HISTCMP_CORREL)
                d_ = float(np.abs(nho - nho_truoc).mean()) / 255.0
                if d_ > 0.004:
                    khac += 1
                dong_ds.append(d_)
                if tq < 0.55 and d_ > 0.08 and (not cat or t - cat[-1] >= 0.4):
                    cat.append(round(t, 2))
            hist_truoc, nho_truoc = hist, nho
            if i % int(fps_q) == 0:                           # mặt: 1 khung/giây
                if det is None:
                    try:
                        from bia import bia as B
                        det = B._yunet(w_, h_)
                    except Exception:
                        det = None
                if det is not None:
                    det.setInputSize((w_, h_))
                    _, faces = det.detect(np.ascontiguousarray(fr))
                    mat_co.append(1 if (faces is not None and len(faces)) else 0)
        i += 1
    pr_.stdout.close(); pr_.wait()
    if i == 0 and hw != "none":                              # hwaccel lỗi với tệp này → giải mã CPU
        return _phan_tich(p, info, ra_anh, n, cot, hwaccel="none", khung_chinh=khung_chinh)
    if khung_chinh and t_max > 2 and khac / max(1.0, min(dur, t_max)) < 0.8:   # GOP dài (ít khung chính) → bảng/cắt cảnh thưa → giải mã đủ
        return _phan_tich(p, info, ra_anh, n, cot, hwaccel=hw, khung_chinh=False)
    dong = round(min(1.0, (sum(dong_ds) / len(dong_ds)) / 0.12), 3) if dong_ds else None
    mat = round(sum(mat_co) / len(mat_co), 2) if mat_co else None
    try:
        from PIL import Image
        ds = [thumbs[j][1] for j in sorted(thumbs)]
        if ds:
            hang = max(1, (len(ds) + cot - 1) // cot)
            bang = Image.new("RGB", (cot * w_ + (cot + 1) * 3, hang * h_ + (hang + 1) * 3), (32, 32, 32))
            for k, fr in enumerate(ds):
                bang.paste(Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)), (3 + (k % cot) * (w_ + 3), 3 + (k // cot) * (h_ + 3)))
            bang.save(ra_anh, quality=86)
            _nhan_giay(ra_anh, len(ds), cot, hang, [thumbs[j][0] for j in sorted(thumbs)])
    except Exception:
        pass
    return cat, dong, mat


def quet(du_an, duong_ds, log=None, ten_goc=None):
    """→ dict {"muc": [...], "anh": [...]} và ghi doc/b-roll.json; mỗi mục: n, duong, ten, dur, w, h, fps, co_am, cat_canh, dong, mat, anh"""
    log = log or (lambda m: None)
    tep, bo = liet_ke(duong_ds)
    thu = os.path.join(du_an, "doc", "b-roll")
    os.makedirs(thu, exist_ok=True)
    p_json = os.path.join(du_an, "doc", "b-roll.json")
    cu = chung.doc_json(p_json, {}) or {}
    cu_muc = {m.get("bam"): m for m in (cu.get("muc") or []) if m.get("bam")}
    muc = []
    for i, p in enumerate(tep):
        b = _bam(p)
        if b in cu_muc and os.path.isfile(cu_muc[b].get("anh") or ""):
            m = dict(cu_muc[b]); m["n"] = i
            muc.append(m)
            continue
        info = _ffprobe(p)
        ten = os.path.splitext(os.path.basename(p))[0]
        anh = os.path.join(thu, f"{i:02d}-{chung.slug(ten, 24)}-{b}.jpg")
        cat, dong, mat_ = _phan_tich(p, info, anh)
        ok = os.path.isfile(anh)
        m = {"n": i, "bam": b, "duong": os.path.abspath(p), "ten": os.path.basename(p), "dur": round(float(info.get("dur") or 0), 2),
             "w": info.get("w"), "h": info.get("h"), "fps": round(float(info.get("fps") or 0), 2), "co_am": bool(info.get("co_am")),
             "cat_canh": cat, "so_canh": len(cat) + 1, "dong": dong, "mat": mat_, "anh": anh if ok else None}
        muc.append(m)
        log(f"b-roll {i}: {m['ten']} {m['dur']}s {m['w']}x{m['h']} · {m['so_canh']} cảnh · động {m['dong']} · mặt {m['mat']}")
    kq = {"muc": muc, "bo": bo, "goc": [str(d) for d in (duong_ds or [])], "ten_goc": ten_goc}
    chung.ghi_json(p_json, kq)
    return kq


def soi(du_an, nguon, tu, den, fps=None):
    """dải khung dày của một B-roll (nguon = chỉ số n trong b-roll.json hoặc đường dẫn) trong [tu, den] giây → ảnh"""
    kq = chung.doc_json(os.path.join(du_an, "doc", "b-roll.json"), {}) or {}
    p = None
    if isinstance(nguon, str) and os.path.isfile(nguon):
        p = nguon
    else:
        try:
            n = int(nguon)
            p = next((m["duong"] for m in kq.get("muc") or [] if m.get("n") == n), None)
        except Exception:
            p = None
    if not p:
        raise ValueError(f"không có B-roll `{nguon}` — chạy `nhanh broll <đường dẫn>` trước hoặc đưa đường dẫn tệp")
    tu, den = max(0.0, float(tu)), float(den)
    dai = max(0.2, den - tu)
    fps = float(fps or min(8.0, max(2.0, 24.0 / dai)))
    n = int(dai * fps)
    cot = 6 if n > 12 else 4
    hang = max(1, (n + cot - 1) // cot)
    thu = os.path.join(du_an, "doc", "b-roll"); os.makedirs(thu, exist_ok=True)
    ra = os.path.join(thu, f"soi-{_bam(p)}-{tu:.1f}-{den:.1f}.jpg")
    ff = chung.duong("ffmpeg")
    lm = chung.loc_mau_vao(_ffprobe(p))
    vf = f"fps={fps}," + (lm + "," if lm else "") + f"scale={O_RONG}:-2,tile={cot}x{hang}:padding=3:margin=3:color=0x202020"
    hw = (chung.phan_cung() or {}).get("hwaccel") or "none"
    cmd = [ff, "-v", "error", "-y", "-nostdin"] + (["-hwaccel", hw] if hw != "none" else []) + ["-ss", f"{tu:.3f}", "-t", f"{dai:.3f}", "-i", p, "-vf", vf, "-frames:v", "1", "-q:v", "4", ra]
    ma, err = chung.chay_ffmpeg(cmd, du_an, f"soi b-roll {tu:.1f}–{den:.1f}s", dur=dai)      # 1.2.21: có tiến độ/treo, hwaccel lỗi → CPU
    if ma != 0 and hw != "none":
        cmd = [c for c in cmd if c not in ("-hwaccel", hw)]
        ma, err = chung.chay_ffmpeg(cmd, du_an, f"soi b-roll {tu:.1f}–{den:.1f}s (CPU)", dur=dai)
    if os.path.isfile(ra):
        _nhan_giay(ra, n, cot, hang, [tu + (i + 0.5) / fps for i in range(n)])
    return {"anh": ra, "so_khung": n, "fps": fps, "duong": p}


def dong_tom_tat(du_an, toi_da=16):
    """các dòng cho bản tóm tắt AI (đọc được, có đường ảnh) — [] nếu chưa quét"""
    kq = chung.doc_json(os.path.join(du_an, "doc", "b-roll.json"), {}) or {}
    muc = kq.get("muc") or []
    if not muc:
        return []
    L = [f"## B-ROLL / VIDEO PHỤ sẵn có ({len(muc)} tệp" + (f", còn {kq.get('bo')} tệp chưa quét" if kq.get("bo") else "") + ") — mỗi tệp một bảng 16 khung có mốc giây (MỞ ảnh để chọn đúng đoạn)"]
    for m in muc[:toi_da]:
        cc = m.get("cat_canh") or []
        L.append(f"- b-roll {m['n']}: {m['ten']} · {m['dur']}s {m.get('w')}×{m.get('h')} {m.get('fps')}fps · {'có tiếng' if m.get('co_am') else 'không tiếng'} · "
                 f"{m.get('so_canh', 1)} cảnh" + (f" (cắt tại {', '.join(f'{c:.1f}' for c in cc[:10])}{'…' if len(cc) > 10 else ''}s)" if cc else "")
                 + (f" · động {m['dong']}" if m.get('dong') is not None else "") + (f" · mặt người {int(m['mat'] * 100)}%" if m.get("mat") is not None else "")
                 + f"\n  đường: {m['duong']}" + (f"\n  ảnh: {m['anh']}" if m.get("anh") else ""))
    L.append("Dùng: lớp `video` {noi_dung:{duong:\"<đường>\", a:<giây trong b-roll>}, vi_tri:{w,h…}} — toàn khung w=h=1 (A-roll vẫn nghe tiếng), hoặc hộp nhỏ/nghiêng 3D (rot_x/rot_y); "
             "nhiều B-roll nối nhau = nhiều lớp video liền giờ; tiếng của B-roll: kieu_dang.am_db (dB so với giọng, vd -14). "
             "Nhìn kỹ một đoạn: `nhanh khung --nguon <n|đường> --tu <giây> --den <giây> [--fps]`.")
    return L


if __name__ == "__main__":
    kq = quet(sys.argv[1], sys.argv[2:], log=print)
    print("\n".join(dong_tom_tat(sys.argv[1])))
