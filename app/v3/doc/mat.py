# -*- coding: utf-8 -*-
"""Quét mặt (YuNet, 5 khung/s, 320 px) + cắt cảnh (hist HSV) + độ nét + màu chủ đạo → mat.json, canh.json, bang-khung.jpg.
Đọc proxy bằng ffmpeg pipe rawvideo (không dùng cv2.VideoCapture)."""
import os, sys, math
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung

FPS_MAU = 5
RONG_YUNET = 320


def _doc_khung(proxy, fps_mau):
    """sinh (t, khung BGR) từ proxy ở fps_mau, kích thước proxy gốc"""
    info = chung.ffprobe(proxy)
    w, h = info["w"], info["h"]
    cmd = [chung.duong("ffmpeg"), "-v", "error", "-nostdin", "-i", proxy, "-vf", f"fps={fps_mau}", "-f", "rawvideo",
           "-pix_fmt", "bgr24", "-"]
    p = chung.popen(cmd, stdout=-1)
    n = w * h * 3
    i = 0
    try:
        while True:
            buf = p.stdout.read(n)
            if len(buf) < n:
                break
            yield i / fps_mau, np.frombuffer(buf, np.uint8).reshape(h, w, 3)
            i += 1
    finally:
        p.stdout.close()
        p.wait()


def _yunet(w, h):
    md = chung.duong_ascii(os.path.join(chung.duong("mo_hinh"), "yunet.onnx"))     # 1.2.19 (E2): tên người dùng có dấu → OpenCV không nạp được model
    return cv2.FaceDetectorYN.create(md, "", (w, h), score_threshold=0.6, nms_threshold=0.3, top_k=50)


def _hist(hsv):
    hs = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
    v = cv2.calcHist([hsv], [2], None, [8], [0, 256])
    hs = cv2.normalize(hs, None, alpha=1, norm_type=cv2.NORM_L1).flatten()
    v = cv2.normalize(v, None, alpha=1, norm_type=cv2.NORM_L1).flatten()
    return np.concatenate([hs, v]).astype(np.float32)


def _bhatt(h1, h2):
    return float(cv2.compareHist(h1, h2, cv2.HISTCMP_BHATTACHARYYA))


def _canh_thang(gray):
    """tỉ lệ cạnh thẳng (ngang/dọc) trên tổng cạnh + mật độ cạnh → đặc trưng màn hình"""
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.hypot(gx, gy)
    m = mag > 60
    if m.sum() < 50:
        return 0.0, 0.0
    ax, ay = np.abs(gx[m]), np.abs(gy[m])
    thang = ((ax > 4 * ay) | (ay > 4 * ax)).mean()
    return float(thang), float(m.mean())


def _mau_chu_dao(mau, k=4):
    """k-means nhỏ trên mẫu pixel → 2 màu hex nhiều nhất"""
    if len(mau) < k * 10:
        return []
    data = np.asarray(mau, np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, lab, cen = cv2.kmeans(data, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    dem = np.bincount(lab.flatten(), minlength=k)
    thu_tu = np.argsort(-dem)
    ra = []
    for i in thu_tu[:2]:
        b, g, r = [int(round(c)) for c in cen[i]]
        ra.append("#%02X%02X%02X" % (r, g, b))
    return ra


def _ve_nhan(anh, txt):
    cv2.putText(anh, txt, (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 4, cv2.LINE_AA)
    cv2.putText(anh, txt, (8, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)


def quet(du_an, proxy, fps_mau=FPS_MAU):
    """→ (mat.json, canh.json); kèm bang-khung.jpg 12 khung 3×4 có nhãn giây"""
    tm = os.path.join(du_an, "doc")
    os.makedirs(tm, exist_ok=True)
    p_mat, p_canh = os.path.join(tm, "mat.json"), os.path.join(tm, "canh.json")
    bam = chung.bam(proxy)
    cu = chung.doc_json(p_mat) or {}
    if cu.get("bam") == bam and cu.get("fps_mau") == fps_mau and os.path.isfile(p_canh) and os.path.isfile(os.path.join(tm, "bang-khung.jpg")):
        chung.log(du_an, "mặt: dùng cache mat.json (proxy không đổi)")      # 1.2.21 (1j): chạy lại không quét lại
        return p_mat, p_canh
    info = chung.ffprobe(proxy)
    W, H, dur = info["w"], info["h"], info["dur"]
    sw = RONG_YUNET
    sh_ = int(round(H * sw / W / 2)) * 2
    det = _yunet(sw, sh_)
    # 12 khung bảng: mốc giữa 12 đoạn đều
    moc = [(i + 0.5) * dur / 12 for i in range(12)]
    chi_so_bang = {int(round(t * fps_mau)): t for t in moc}
    bang_khung = {}
    khung, hists, net_ds, thang_ds, mau_mau, luong_tb = [], [], [], [], [], []
    truoc_gray = None
    n_mat_khung = 0
    for t, bgr in _doc_khung(proxy, fps_mau):
        i = len(khung)
        nho = cv2.resize(bgr, (sw, sh_), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(nho, cv2.COLOR_BGR2GRAY)
        # mặt
        _, faces = det.detect(nho)
        ds = []
        if faces is not None:
            for f in faces:
                x, y, w, h, diem = float(f[0]), float(f[1]), float(f[2]), float(f[3]), float(f[-1])
                ds.append({"x": round(min(max((x + w / 2) / sw, 0), 1), 4), "y": round(min(max((y + h / 2) / sh_, 0), 1), 4),
                           "w": round(w / sw, 4), "h": round(h / sh_, 4), "diem": round(diem, 3)})
            ds.sort(key=lambda d: -d["w"] * d["h"])
        if ds:
            n_mat_khung += 1
        # độ nét
        var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        net = 1.0 - math.exp(-var / 300.0)
        # cảnh
        hsv = cv2.cvtColor(nho, cv2.COLOR_BGR2HSV)
        hists.append(_hist(hsv))
        thang_ds.append(_canh_thang(gray))
        sang = float(hsv[:, :, 2].mean() / 255.0)
        dong = float(np.abs(gray.astype(np.int16) - truoc_gray.astype(np.int16)).mean() / 255.0) if truoc_gray is not None else 0.0
        truoc_gray = gray
        # màu: lấy mẫu 64 pixel/khung
        m32 = cv2.resize(nho, (8, 8), interpolation=cv2.INTER_AREA).reshape(-1, 3)
        mau_mau.extend(m32.tolist())
        khung.append({"t": round(t, 3), "mat": ds, "net": round(net, 3), "sang": round(sang, 3), "dong": round(dong, 4)})
        if i in chi_so_bang:
            bang_khung[i] = bgr.copy()
    n = len(khung)
    if n == 0:
        raise RuntimeError("không đọc được khung nào từ proxy")
    # ---- cắt cảnh
    cat = []
    khoang_toi_thieu = 1.0
    for i in range(1, n):
        d = _bhatt(hists[i - 1], hists[i])
        if d > 0.45 and (not cat or khung[i]["t"] - cat[-1] >= khoang_toi_thieu):
            cat.append(khung[i]["t"])
    bien = [0.0] + cat + [round(dur, 3)]
    canh = []
    for a, b in zip(bien[:-1], bien[1:]):
        ids = [i for i in range(n) if a <= khung[i]["t"] < b] or [min(n - 1, int(a * fps_mau))]
        co_mat = sum(1 for i in ids if khung[i]["mat"]) / len(ids)
        thang = float(np.mean([thang_ds[i][0] for i in ids]))
        mat_do = float(np.mean([thang_ds[i][1] for i in ids]))
        if co_mat >= 0.5:
            kieu = "mat"
        elif co_mat < 0.3 and thang > 0.55 and mat_do > 0.04:
            kieu = "man_hinh"
        else:
            kieu = "khac"
        canh.append({"a": round(a, 3), "b": round(b, 3), "kieu": kieu,
                     "sang": round(float(np.mean([khung[i]["sang"] for i in ids])), 3),
                     "dong": round(float(np.mean([khung[i]["dong"] for i in ids])), 4),
                     "co_mat": round(co_mat, 2)})
    canh_json = {"cat": [round(t, 3) for t in cat], "canh": canh, "mau_chu_dao": _mau_chu_dao(mau_mau)}
    # ---- mặt trung vị
    xs = [k["mat"][0] for k in khung if k["mat"]]
    mat_tb = None
    if xs:
        mat_tb = {kk: round(float(np.median([m[kk] for m in xs])), 4) for kk in ("x", "y", "w", "h")}
        mat_tb["ti_le_co"] = mat_tb["h"]
    mat_json = {"fps_mau": fps_mau, "kich_thuoc": [W, H], "khung": khung, "mat_tb": mat_tb, "bam": bam,
                "nguoi_ti_le": round(n_mat_khung / n, 3), "net_tb": round(float(np.mean([k["net"] for k in khung])), 3)}
    chung.ghi_json(p_mat, mat_json)
    chung.ghi_json(p_canh, canh_json)
    # ---- bảng 12 khung
    ow = 270
    oh = int(round(H * ow / W))
    bang = np.zeros((oh * 4, ow * 3, 3), np.uint8)
    for k, t in enumerate(moc):
        idx = int(round(t * fps_mau))
        f = bang_khung.get(idx)
        if f is None:
            # lấy khung gần nhất có trong bảng
            if bang_khung:
                idx = min(bang_khung, key=lambda j: abs(j - idx))
                f = bang_khung[idx]
            else:
                continue
        o = cv2.resize(f, (ow, oh), interpolation=cv2.INTER_AREA)
        _ve_nhan(o, f"{t:.1f}s")
        r, c = divmod(k, 3)
        bang[r * oh:(r + 1) * oh, c * ow:(c + 1) * ow] = o
    chung.cv_ghi(os.path.join(tm, "bang-khung.jpg"), bang, [cv2.IMWRITE_JPEG_QUALITY, 85])    # 1.2.19 (E2)
    chung.log(du_an, f"mặt: {n} khung, người {mat_json['nguoi_ti_le'] * 100:.0f}%, {len(cat)} cắt cảnh, "
                     f"mặt TB {mat_tb}, màu {canh_json['mau_chu_dao']}")
    return p_mat, p_canh


if __name__ == "__main__":
    print(quet(sys.argv[1], sys.argv[2]))
