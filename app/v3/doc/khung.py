# -*- coding: utf-8 -*-
"""MẮT ba tầng — máy chỉ ĐO và ĐƯA ẢNH; AI tự quyết nhìn gì, nhìn bao nhiêu.

TẦNG 1  do(du_an)                 đo 100% khung của proxy (cv2, một lượt): thay đổi so với khung trước, cắt cảnh, độ sáng,
                                  mặt (YuNet — mọi khung ở hạng A/B, mỗi 2 khung hạng C, mỗi 3 khung hạng D), chuyển động nửa dưới,
                                  dấu hiệu có chữ → doc/khung-so.json (mảng theo khung) + doc/khung-giay.json (gộp theo giây)
TẦNG 2  bang(du_an, muc=None)     bảng ảnh cho AI, mật độ theo LƯỢNG THAY ĐỔI: cộng dồn thay_doi, đủ ngưỡng thì lấy một khung.
                                  Ngưỡng tính từ ngân sách khung = f(thời lượng, mức nhìn thua|vua|day) → doc/bang-khung.jpg, -2, -3 …
TẦNG 3  soi(du_an, tu, den, fps=None, o_lon=False)   AI xin nhìn kỹ một đoạn (giây gốc) → doc/soi-<tu>-<den>.jpg (+ -2 …)
tom_tat(du_an) -> str             ≤ 900 ký tự số đo chuyển động cho bản tóm tắt (người điều phối chèn)
muc_nhin(du_an) -> str            viec.json "nhin" → hồ sơ kênh "nhin" → cau-hinh v3.nhin → "vua"

Không có hằng số thẩm mỹ: các số dưới đây là KỸ THUẬT (cỡ ảnh mà AI thu về, đơn vị đo, ngưỡng nhiễu đo từ chính video),
ghi đè được trong cau-hinh.json {"v3": {"khung_nhin": {...}}}.
"""
import json, math, os, sys, threading, time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung

MUC = ("thua", "vua", "day")
HE_SO_MUC = {"thua": 0.5, "vua": 1.0, "day": 2.0}
KY_THUAT = {
    "o_bang": 160,            # cạnh ngắn một ô bảng tầng 2 (px) — nhỏ hơn thì AI không đọc được chi tiết
    "canh_bang": 1568,        # cạnh dài tối đa của một bảng (px) — AI thu ảnh về cỡ này
    "giay_moi_bang": 30.0,    # mức "vua": khoảng một bảng cho mỗi chừng này giây video
    "khoang_toi_da": 2.0,     # luôn có ít nhất 1 khung mỗi chừng này giây (không có khoảng AI chưa thấy)
    "doi_moi": 1.0,           # ĐƠN VỊ lấy khung ở mức "vua": cộng dồn tỉ lệ điểm ảnh đổi = 1 khung hình (mức khác chia theo hệ số)
    "o_soi": 260,             # cạnh ngắn ô bảng soi (tầng 3)
    "o_soi_lon": 390,         # --o-lon
    "soi_toi_da": 360,        # trần số khung một lần soi (tránh tràn ảnh); vượt → hạ fps và báo
    "canh_mat": 320,          # cạnh ngắn ảnh đưa YuNet (như doc/mat.py)
    "canh_do": 144,           # cạnh ngắn ảnh đo thay đổi
    "canh_chu": 270,          # cạnh ngắn ảnh đo dấu hiệu chữ
}
BUOC_MAT = {"A": 1, "B": 1, "C": 2, "D": 3}
NGUONG_THU = np.array([4, 6, 8, 10, 12, 16, 20, 24, 32], np.int32)   # các mức chênh xám thử để tách nhiễu nén/cảm biến


def _kt():
    k = dict(KY_THUAT)
    k.update(chung.cau_hinh().get("khung_nhin") or {})
    return k


def _r(x, n=3):
    return None if x is None else round(float(x), n)


def _ghi_gon(p, obj):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, p)


def _proxy(du_an):
    n = chung.doc_json(os.path.join(du_an, "doc", "nguon.json")) or {}
    p = (n.get("chinh") or {}).get("proxy")
    if not p or not os.path.isfile(p):
        raise RuntimeError("chưa có proxy (doc/nguon.json → chinh.proxy) — chạy bước đọc trước")
    return p


def _co_nho(w, h, canh_ngan):
    """(w, h) chẵn giữ tỉ lệ với cạnh ngắn = canh_ngan"""
    s = canh_ngan / float(min(w, h))
    return max(2, int(round(w * s / 2)) * 2), max(2, int(round(h * s / 2)) * 2)


# ═════════════════════════════════════════════ TẦNG 1 — đo mọi khung
def _hist_hsv(bgr_nho):
    hsv = cv2.cvtColor(bgr_nho, cv2.COLOR_BGR2HSV)
    hs = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
    v = cv2.calcHist([hsv], [2], None, [8], [0, 256])
    hs = cv2.normalize(hs, None, alpha=1, norm_type=cv2.NORM_L1).flatten()
    v = cv2.normalize(v, None, alpha=1, norm_type=cv2.NORM_L1).flatten()
    return np.concatenate([hs, v]).astype(np.float32)


def _dem_tren(diff):
    """→ (số điểm có chênh > mỗi mức NGUONG_THU, trung vị chênh) — dùng histogram 256 mức (nhanh)"""
    h = cv2.calcHist([diff], [0], None, [256], [0, 256]).flatten()
    tong = h.sum() or 1.0
    cs = np.cumsum(h)
    tren = tong - cs[NGUONG_THU]                       # số điểm > mức
    trung_vi = int(np.searchsorted(cs, tong / 2.0))
    return tren.astype(np.float32), trung_vi


def _diem_chu(gray):
    """dấu hiệu có chữ: vùng cạnh dọc dày, xếp thành dải ngang (dòng chữ) → tỉ lệ diện tích các dải đó (0..1). CHỈ là dấu hiệu."""
    h, w = gray.shape
    gx = cv2.convertScaleAbs(cv2.Sobel(gray, cv2.CV_16S, 1, 0, ksize=3))
    _, b = cv2.threshold(gx, 100, 255, cv2.THRESH_BINARY)
    kx = max(3, int(round(min(w, h) * 0.03)))
    b = cv2.morphologyEx(b, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (kx, 1)))
    n, _, st, _ = cv2.connectedComponentsWithStats(b, connectivity=8)
    if n <= 1:
        return 0.0
    st = st[1:]
    bw, bh, ar = st[:, 2].astype(np.float32), st[:, 3].astype(np.float32), st[:, 4].astype(np.float32)
    chon = (bw >= 2.0 * bh) & (bh >= 0.012 * h) & (bh <= 0.10 * h) & (bw >= 0.05 * w) & (ar >= 0.45 * bw * bh)
    return float((bw[chon] * bh[chon]).sum() / (w * h))


_TL = threading.local()


def _yunet(w, h):
    d = getattr(_TL, "det", None)
    if d is None or getattr(_TL, "co", None) != (w, h):
        md = chung.duong_ascii(os.path.join(chung.duong("mo_hinh"), "yunet.onnx"))
        d = cv2.FaceDetectorYN.create(md, "", (w, h), score_threshold=0.6, nms_threshold=0.3, top_k=50)
        _TL.det, _TL.co = d, (w, h)
    return d


def _viec_nang(bgr, do_mat, co_mat, co_chu):
    """chạy trong luồng phụ: mặt (nếu tới lượt) + dấu hiệu chữ"""
    mat = None
    so = None
    if do_mat:
        nho = cv2.resize(bgr, co_mat, interpolation=cv2.INTER_AREA)
        _, faces = _yunet(*co_mat).detect(nho)
        so = 0
        if faces is not None and len(faces):
            so = int(len(faces))
            f = max(faces, key=lambda f: float(f[2]) * float(f[3]))
            x, y, w, h = float(f[0]), float(f[1]), float(f[2]), float(f[3])
            sw, sh = co_mat
            mat = [_r(min(max((x + w / 2) / sw, 0), 1)), _r(min(max((y + h / 2) / sh, 0), 1)), _r(w / sw), _r(h / sh)]
    g = cv2.cvtColor(cv2.resize(bgr, co_chu, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    return so, mat, _diem_chu(g)


def do(du_an, proxy=None):
    """TẦNG 1 → {"so": khung-so.json, "giay": khung-giay.json, "n", "fps", "fps_mat", "giay_do"}"""
    t_bat_dau = time.time()
    proxy = proxy or _proxy(du_an)
    tm = os.path.join(du_an, "doc")
    p_so, p_giay = os.path.join(tm, "khung-so.json"), os.path.join(tm, "khung-giay.json")
    bam = chung.bam(proxy)
    cu = chung.doc_json(p_so) or {}
    if cu.get("bam") == bam and cu.get("phien") == 1 and os.path.isfile(p_giay):      # 1.2.21 (1j): chạy lại không đo lại
        chung.log(du_an, "khung (tầng 1): dùng cache khung-so.json (proxy không đổi)")
        return {"so": p_so, "giay": p_giay, "n": cu.get("n"), "fps": cu.get("fps"), "fps_mat": cu.get("fps_mat"), "giay_do": 0.0, "cache": True}
    kt = _kt()
    hm = chung.hang_may()
    buoc_mat = int(BUOC_MAT.get(hm.get("hang"), 1))
    cap = cv2.VideoCapture(proxy)
    if not cap.isOpened():
        raise RuntimeError(f"cv2 không mở được proxy {proxy}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0) or 30.0
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    co_do, co_mat, co_chu = _co_nho(W, H, kt["canh_do"]), _co_nho(W, H, kt["canh_mat"]), _co_nho(W, H, kt["canh_chu"])
    nua = co_do[1] // 2
    so_luong = max(1, min(4, int(hm.get("luong") or 4) // 2))
    ts, tren, tren_duoi, trung_vi, sang, hd = [], [], [], [], [], []
    nang = {}
    cho = deque()
    truoc_g, truoc_h = None, None
    i = 0
    with ThreadPoolExecutor(max_workers=so_luong, thread_name_prefix="khung") as ex:
        while True:
            if not cap.grab():
                break
            ok, bgr = cap.retrieve()
            if not ok or bgr is None:
                break
            t = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
            if not ts or t <= ts[-1]:
                t = (ts[-1] + 1.0 / fps) if ts else 0.0
            ts.append(t)
            nho = cv2.resize(bgr, co_do, interpolation=cv2.INTER_AREA)
            g = cv2.cvtColor(nho, cv2.COLOR_BGR2GRAY)
            hh = _hist_hsv(nho)
            if truoc_g is None:
                tren.append(np.zeros(len(NGUONG_THU), np.float32)); tren_duoi.append(np.zeros(len(NGUONG_THU), np.float32))
                trung_vi.append(0); hd.append(0.0)
            else:
                d = cv2.absdiff(g, truoc_g)
                a, tv = _dem_tren(d)
                b, _ = _dem_tren(np.ascontiguousarray(d[nua:]))
                tren.append(a); tren_duoi.append(b); trung_vi.append(tv)
                hd.append(float(cv2.compareHist(truoc_h, hh, cv2.HISTCMP_BHATTACHARYYA)))
            sang.append(float(g.mean()) / 255.0)
            truoc_g, truoc_h = g, hh
            cho.append((i, ex.submit(_viec_nang, bgr, i % buoc_mat == 0, co_mat, co_chu)))
            while len(cho) > 4 * so_luong + 8:
                j, f = cho.popleft()
                nang[j] = f.result()
            i += 1
        while cho:
            j, f = cho.popleft()
            nang[j] = f.result()
    cap.release()
    n = len(ts)
    if n == 0:
        raise RuntimeError("không đọc được khung nào từ proxy")
    # ---- ngưỡng nhiễu: đo từ những khung lặng nhất của chính video
    tv = np.array(trung_vi[1:] or [0], np.float32)
    nhieu = float(np.percentile(tv, 10)) if len(tv) else 0.0
    can = max(6.0, 3.0 * nhieu)
    k = int(np.searchsorted(NGUONG_THU, can))
    k = min(k, len(NGUONG_THU) - 1)
    nguong = int(NGUONG_THU[k])
    tong_diem = float(co_do[0] * co_do[1])
    td = np.array([x[k] for x in tren], np.float32) / tong_diem
    tay = np.array([x[k] for x in tren_duoi], np.float32) / float(co_do[0] * (co_do[1] - nua))
    hd = np.array(hd, np.float32)
    # ---- cắt cảnh = đỉnh thay đổi: (a) phần lớn điểm ảnh đổi ĐỘT NGỘT so với các khung ngay trước (lia nhanh đổi đều → không tính)
    #      hoặc (b) màu (histogram) khác hẳn và là đỉnh nổi trên vùng lân cận
    cat = []
    for j in range(1, n):
        dot_ngot = td[j] >= 0.4 and td[j] >= 3.0 * max(1e-3, float(np.median(td[max(1, j - 5):j])))             and (j + 1 >= n or td[j] >= td[j + 1])
        mau = hd[j] >= 0.4 and hd[j] >= hd[j - 1] and (j + 1 >= n or hd[j] >= hd[j + 1])             and hd[j] >= 2.5 * float(np.median(hd[max(1, j - 15):j + 16])) and td[j] >= 0.3
        if not (dot_ngot or mau):
            continue
        if cat and j - cat[-1] < 4:
            if td[j] > td[cat[-1]]:
                cat[-1] = j
            continue
        cat.append(j)
    so_mat = [nang[j][0] for j in range(n)]
    mat = [(nang[j][1] if nang[j][0] else (0 if nang[j][0] == 0 else None)) for j in range(n)]
    chu = np.array([nang[j][2] for j in range(n)], np.float32)
    dur = float(ts[-1] + 1.0 / fps)
    so = {"phien": 1, "proxy": proxy, "bam": bam, "kich_thuoc": [W, H], "fps": _r(fps), "n": n, "dur": _r(dur),
          "fps_mat": _r(fps / buoc_mat, 2), "buoc_mat": buoc_mat, "hang_may": hm.get("hang"), "nguong_nhieu": nguong,
          "mo_ta": {"t": "giây gốc của khung", "thay_doi": "tỉ lệ điểm ảnh đổi so với khung trước (0..1, sau khi bỏ nhiễu)",
                    "tay": "như thay_doi nhưng chỉ nửa dưới khung", "sang": "độ sáng trung bình 0..1",
                    "doi_mau": "khoảng cách histogram màu với khung trước 0..1", "chu": "dấu hiệu có chữ (tỉ lệ diện tích dải giống dòng chữ) — co_the_co_chu, không chắc",
                    "mat_so": "số mặt (null = khung không đo mặt)", "mat": "mặt lớn nhất [tâm x, tâm y, w, h] 0..1, 0 = không mặt, null = không đo",
                    "cat": "chỉ số khung ngay sau cắt cảnh"},
          "t": [_r(x) for x in ts], "thay_doi": [_r(x) for x in td], "tay": [_r(x) for x in tay], "sang": [_r(x) for x in sang],
          "doi_mau": [_r(x) for x in hd], "chu": [_r(x) for x in chu], "mat_so": so_mat, "mat": mat, "cat": cat}
    _ghi_gon(p_so, so)
    # ---- gộp theo giây
    ts_a = np.array(ts)
    cat_set = set(cat)
    giay = []
    for s in range(int(math.ceil(dur))):
        ids = np.nonzero((ts_a >= s) & (ts_a < s + 1))[0]
        if not len(ids):
            continue
        do_mat = [so_mat[j] for j in ids if so_mat[j] is not None]
        giay.append({"s": s, "thay_doi_tb": _r(td[ids].mean()), "thay_doi_max": _r(td[ids].max()),
                     "cat_canh": int(sum(1 for j in ids if j in cat_set)),
                     "mat": _r(sum(1 for x in do_mat if x) / len(do_mat), 2) if do_mat else None,
                     "sang": _r(np.mean([sang[j] for j in ids])), "tay": _r(tay[ids].mean()), "chu": _r(chu[ids].mean())})
    _ghi_gon(p_giay, {"fps": _r(fps), "fps_mat": _r(fps / buoc_mat, 2), "dur": _r(dur), "nguong_nhieu": nguong,
                      "cat_canh": [_r(ts[j]) for j in cat], "giay": giay})
    g_do = time.time() - t_bat_dau
    chung.log(du_an, f"khung (tầng 1): đo {n} khung ({fps:.0f} fps, mặt {fps / buoc_mat:.0f} fps, hạng {hm.get('hang')}, "
                     f"{so_luong} luồng) trong {g_do:.1f}s · {len(cat)} cắt cảnh · ngưỡng nhiễu {nguong}")
    return {"so": p_so, "giay": p_giay, "n": n, "fps": fps, "fps_mat": fps / buoc_mat, "giay_do": round(g_do, 2)}


# ═════════════════════════════════════════════ mức nhìn
def muc_nhin(du_an):
    v = chung.doc_json(os.path.join(du_an, "viec.json")) or {}
    for gt in (v.get("nhin"),
               (chung.doc_json(os.path.join(chung.duong("ho_so"), v.get("ho_so") or "_", "ho-so.json")) or {}).get("nhin") if v.get("ho_so") else None,
               chung.cau_hinh().get("nhin")):
        if isinstance(gt, str) and gt.strip().lower() in MUC:
            return gt.strip().lower()
    return "vua"


# ═════════════════════════════════════════════ giây gốc → giây thành phẩm (cat-de-xuat)
def _anh_xa(du_an):
    c = chung.doc_json(os.path.join(du_an, "doc", "cat-de-xuat.json"))
    if not c:
        return None
    ax = c.get("anh_xa")
    if not ax:
        ax, tp = [], 0.0
        for g in c.get("giu") or []:
            if int(g.get("src", 0)) != 0:
                continue
            ax.append([float(g["a"]), float(g["b"]), tp])
            tp += float(g["b"]) - float(g["a"])
    return [(float(a), float(b), float(t)) for a, b, t in ax] or None


def _tp(ax, t):
    """giây thành phẩm của giây gốc t; None = đoạn bị bỏ"""
    for a, b, t0 in ax:
        if a <= t < b:
            return t0 + (t - a)
    return None


# ═════════════════════════════════════════════ dựng bảng (dùng chung tầng 2 + 3)
_FONT = {}


def _font(co):
    from PIL import ImageFont
    if co not in _FONT:
        f = None
        for p in (os.path.join(chung.duong("font_mac_dinh"), "BeVietnamPro-Bold.ttf"),
                  os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arialbd.ttf")):
            try:
                f = ImageFont.truetype(p, co)
                break
            except Exception:
                continue
        _FONT[co] = f or ImageFont.load_default()
    return _FONT[co]


def _luoi(W, H, canh_ngan, canh_bang):
    cw, ch = _co_nho(W, H, canh_ngan)
    cot, hang = max(1, canh_bang // cw), max(1, canh_bang // ch)
    return cw, ch, cot, hang


def _doc_khung(proxy, chi_so):
    """{chỉ số khung: BGR} — đọc tuần tự (grab), chỉ giải ảnh khung cần; nhảy (seek) khi khoảng trống dài"""
    can = sorted(set(int(x) for x in chi_so))
    ra = {}
    if not can:
        return ra
    cap = cv2.VideoCapture(proxy)
    vi_tri = 0
    for j in can:
        if j - vi_tri > 90:
            cap.set(cv2.CAP_PROP_POS_FRAMES, j)
            vi_tri = j
        while vi_tri < j:
            if not cap.grab():
                break
            vi_tri += 1
        if vi_tri != j:
            break
        ok, f = cap.read()
        vi_tri += 1
        if not ok:
            break
        ra[j] = f
    cap.release()
    return ra


def _ve_bang(khung_ds, cw, ch, cot, hang_toi_da, nhan, ra_ds, chat=85):
    """khung_ds: [(BGR, nhãn1, nhãn2|None, là_cắt)] → ghi các ảnh ra_ds[i]; trả danh sách đường đã ghi"""
    from PIL import Image, ImageDraw
    moi = cot * hang_toi_da
    co1 = min(30, max(14, int(round(min(cw, ch) * 0.13))))
    co2 = max(12, int(round(co1 * 0.8)))
    f1, f2 = _font(co1), _font(co2)
    da_ghi = []
    for b in range(int(math.ceil(len(khung_ds) / float(moi)))):
        phan = khung_ds[b * moi:(b + 1) * moi]
        hang = int(math.ceil(len(phan) / float(cot)))
        cot_b = cot if hang > 1 else len(phan)
        bang = np.full((hang * ch, cot_b * cw, 3), 18, np.uint8)
        for k, (f, _, _, la_cat) in enumerate(phan):
            r, c = divmod(k, cot)
            o = cv2.resize(f, (cw, ch), interpolation=cv2.INTER_AREA)
            if la_cat:
                cv2.rectangle(o, (0, 0), (cw - 1, ch - 1), (0, 215, 255), max(2, cw // 60))
            bang[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = o
        im = Image.fromarray(cv2.cvtColor(bang, cv2.COLOR_BGR2RGB))
        dr = ImageDraw.Draw(im)
        for k, (_, n1, n2, la_cat) in enumerate(phan):
            r, c = divmod(k, cot)
            x, y = c * cw + 3, r * ch + 3
            for dong, ft in ((n1, f1), (n2, f2)):
                if not dong:
                    continue
                x0, y0, x1, y1 = dr.textbbox((x + 4, y + 1), dong, font=ft)
                dr.rectangle((x, y, x1 + 4, y1 + 3), fill=(255, 215, 0) if la_cat else (0, 0, 0))
                dr.text((x + 4, y + 1), dong, font=ft, fill=(0, 0, 0) if la_cat else (255, 255, 255))
                y = y1 + 4
        p = ra_ds(b)
        im.save(p, quality=chat)
        da_ghi.append(p)
    return da_ghi


def _nhan(t, ax, chi_tiet=1):
    n1 = f"{t:.{chi_tiet}f}s"
    if ax is None:
        return n1, None
    tp = _tp(ax, t)
    return n1, ("tp: bỏ" if tp is None else f"tp {tp:.{chi_tiet}f}s")     # dòng 2 = giây thành phẩm theo cat-de-xuat


# ═════════════════════════════════════════════ TẦNG 2 — bảng theo lượng thay đổi
def _chon(td, ts, bat_buoc, nguong, khoang):
    """cộng dồn td; đủ ngưỡng / khung bắt buộc / quá `khoang` giây chưa lấy → lấy khung"""
    chon, acc, t_cuoi = [], 0.0, -1e9
    for j in range(len(td)):
        acc += td[j]
        if j in bat_buoc or acc >= nguong or ts[j] - t_cuoi >= khoang:
            chon.append(j)
            acc, t_cuoi = 0.0, ts[j]
    return chon


def bang(du_an, muc=None, ten="bang-khung"):
    """TẦNG 2 → {"anh":[...], "so_khung", "muc", "ngan_sach", "nguong", "co_cat", "bang":[{"anh","tu","den","so"}]}"""
    t0 = time.time()
    so = chung.doc_json(os.path.join(du_an, "doc", "khung-so.json"))
    if not so:
        raise RuntimeError("chưa có doc/khung-so.json (tầng 1)")
    kt = _kt()
    muc = muc if muc in MUC else muc_nhin(du_an)
    he_so = HE_SO_MUC[muc]
    W, H = so["kich_thuoc"]
    ts = [float(x) for x in so["t"]]
    td = [float(x or 0) for x in so["thay_doi"]]
    dur = float(so.get("dur") or (ts[-1] if ts else 0))
    cw, ch, cot, hang = _luoi(W, H, int(kt["o_bang"]), int(kt["canh_bang"]))
    moi_bang = cot * hang
    ngan_sach = max(1, int(round(moi_bang * dur / float(kt["giay_moi_bang"]) * he_so)))
    bat_buoc = set([0] + list(so.get("cat") or []))
    khoang = float(kt["khoang_toi_da"])
    nguong_toi_thieu = float(kt["doi_moi"]) / he_so
    chon = _chon(td, ts, bat_buoc, nguong_toi_thieu, khoang)
    nguong = nguong_toi_thieu
    if len(chon) > ngan_sach:                         # nhiều thay đổi hơn ngân sách → nâng ngưỡng cho vừa (dồn khung vào đoạn đổi nhiều)
        lo, hi = nguong_toi_thieu, max(nguong_toi_thieu * 2, sum(td) + 1.0)
        for _ in range(40):
            mid = (lo + hi) / 2
            if len(_chon(td, ts, bat_buoc, mid, khoang)) > ngan_sach:
                lo = mid
            else:
                hi = mid
        nguong = hi
        chon = _chon(td, ts, bat_buoc, nguong, khoang)
    anh_khung = _doc_khung(so["proxy"], chon)
    ax = _anh_xa(du_an)
    cat_set = set(so.get("cat") or [])
    ds = [(anh_khung[j],) + _nhan(ts[j], ax) + (j in cat_set,) for j in chon if j in anh_khung]
    tm = os.path.join(du_an, "doc")
    ten_anh = lambda b: os.path.join(tm, f"{ten}.jpg" if b == 0 else f"{ten}-{b + 1}.jpg")
    anh = _ve_bang(ds, cw, ch, cot, hang, None, ten_anh)
    # xoá bảng thừa của lần trước
    b = len(anh)
    while os.path.isfile(ten_anh(b)):
        try:
            os.remove(ten_anh(b))
        except OSError:
            break
        b += 1
    chon_doc = [j for j in chon if j in anh_khung]
    bang_ds = []
    for k, p in enumerate(anh):
        phan = chon_doc[k * moi_bang:(k + 1) * moi_bang]
        bang_ds.append({"anh": p, "tu": _r(ts[phan[0]], 2), "den": _r(ts[phan[-1]], 2), "so": len(phan)})
    meta = {"muc": muc, "anh": anh, "so_khung": len(chon_doc), "ngan_sach": ngan_sach, "moi_bang": moi_bang,
            "o": [cw, ch], "nguong": _r(nguong, 4), "co_cat": ax is not None, "bang": bang_ds,
            "khung": [[j, _r(ts[j])] for j in chon_doc], "giay_ve": round(time.time() - t0, 2)}
    chung.ghi_json(os.path.join(tm, f"{ten}.json"), meta)
    chung.log(du_an, f"khung (tầng 2, mức {muc}): {len(chon_doc)} khung / {len(anh)} bảng (ngân sách {ngan_sach}) trong {meta['giay_ve']:.1f}s")
    return meta


# ═════════════════════════════════════════════ TẦNG 3 — AI xin nhìn kỹ
def _so_giay(x):
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s or "0"


def soi(du_an, tu, den, fps=None, o_lon=False):
    """→ {"anh":[...], "so_khung", "fps", "ghi_chu"} ; tu/den = giây GỐC"""
    kt = _kt()
    so = chung.doc_json(os.path.join(du_an, "doc", "khung-so.json")) or {}
    proxy = so.get("proxy") if so.get("proxy") and os.path.isfile(so.get("proxy")) else _proxy(du_an)
    cap = cv2.VideoCapture(proxy)
    fps_v = float(cap.get(cv2.CAP_PROP_FPS) or 30.0) or 30.0
    n_v = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    dur = float(so.get("dur") or (n_v / fps_v))
    tu, den = max(0.0, float(tu)), min(dur, float(den))
    if den <= tu:
        raise ValueError(f"--den phải lớn hơn --tu (video dài {dur:.2f}s)")
    cw, ch, cot, hang = _luoi(W, H, int(kt["o_soi_lon"] if o_lon else kt["o_soi"]), int(kt["canh_bang"]))
    moi_bang = cot * hang
    ghi_chu = []
    if fps:
        f_eff = min(float(fps), fps_v)
    else:                                              # không ghi fps → vừa một bảng cho cả đoạn
        f_eff = min(fps_v, max(1, moi_bang - 1) / (den - tu))
    so_k = int(math.floor((den - tu) * f_eff + 1e-6)) + 1
    if so_k > int(kt["soi_toi_da"]):
        f_eff = (int(kt["soi_toi_da"]) - 1) / (den - tu)
        ghi_chu.append(f"đoạn dài: hạ còn {f_eff:.2f} khung/giây (tối đa {int(kt['soi_toi_da'])} khung mỗi lần soi) — soi đoạn ngắn hơn để dày hơn")
        so_k = int(kt["soi_toi_da"])
    chi_so = []
    for k in range(so_k):
        j = int(round((tu + k / f_eff) * fps_v))
        if n_v:
            j = min(j, n_v - 1)
        if not chi_so or j != chi_so[-1]:
            chi_so.append(j)
    anh_khung = _doc_khung(proxy, chi_so)
    ts_so = so.get("t") or []
    ax = _anh_xa(du_an)
    cat_set = set(so.get("cat") or [])
    ds = []
    for j in chi_so:
        if j not in anh_khung:
            continue
        t = float(ts_so[j]) if j < len(ts_so) else j / fps_v
        ds.append((anh_khung[j],) + _nhan(t, ax, 2) + (j in cat_set,))
    tm = os.path.join(du_an, "doc")
    goc = f"soi-{_so_giay(tu)}-{_so_giay(den)}"
    ten_anh = lambda b: os.path.join(tm, f"{goc}.jpg" if b == 0 else f"{goc}-{b + 1}.jpg")
    anh = _ve_bang(ds, cw, ch, cot, hang, None, ten_anh, chat=88)
    return {"anh": anh, "so_khung": len(ds), "fps": round(f_eff, 2), "ghi_chu": ghi_chu}


# ═════════════════════════════════════════════ tóm tắt cho AI (≤ 900 ký tự)
def _doan(ds_giay, dieu_kien, it_nhat=1):
    """các đoạn liên tiếp (giây nguyên) thoả điều kiện → [(a, b)]"""
    ra, a = [], None
    for k, g in enumerate(ds_giay):
        if dieu_kien(g):
            if a is None:
                a = g["s"]
            b = g["s"] + 1
        elif a is not None:
            if b - a >= it_nhat:
                ra.append((a, b))
            a = None
    if a is not None and b - a >= it_nhat:
        ra.append((a, b))
    return ra


def _ds_doan(ds, toi_da=6):
    s = ", ".join(f"{a}–{b}s" for a, b in ds[:toi_da])
    return s + (f" (+{len(ds) - toi_da})" if len(ds) > toi_da else "")


def tom_tat(du_an):
    g = chung.doc_json(os.path.join(du_an, "doc", "khung-giay.json"))
    if not g or not g.get("giay"):
        return ""
    ds = g["giay"]
    tb = [float(x["thay_doi_tb"] or 0) for x in ds]
    dinh = max(tb) or 1e-6
    buoc = max(1, int(math.ceil(len(ds) / 120.0)))
    duong = ""
    for k in range(0, len(ds), buoc):
        v = max(tb[k:k + buoc])
        duong += str(min(9, int(round(9 * v / dinh))))
    L = [f"## Chuyển động (máy đo mọi khung {g.get('fps', 0):.0f} fps, mặt {g.get('fps_mat', 0):.0f} fps)",
         f"Đường cong thay đổi, mỗi ký tự {buoc} s, 0–9 theo đỉnh video này (đỉnh = {dinh:.2f} tỉ lệ điểm ảnh đổi/khung):", duong]
    cat = g.get("cat_canh") or []
    if cat:
        s = ", ".join(_so_giay(x) for x in cat[:24])
        L.append(f"Cắt cảnh ({len(cat)}, giây gốc): {s}" + (" …" if len(cat) > 24 else ""))
    else:
        L.append("Cắt cảnh: không có")
    manh = _doan(ds, lambda x: float(x["thay_doi_tb"] or 0) >= 0.5 * dinh)
    tinh = _doan(ds, lambda x: float(x["thay_doi_max"] or 0) <= 0.1 * dinh, it_nhat=2)
    chu = _doan(ds, lambda x: float(x.get("chu") or 0) >= 0.01)
    if manh:
        L.append("Đổi mạnh: " + _ds_doan(manh))
    if tinh:
        L.append("Gần như đứng yên: " + _ds_doan(tinh))
    if chu:
        L.append("Có thể có chữ trên hình: " + _ds_doan(chu))
    bk = chung.doc_json(os.path.join(du_an, "doc", "bang-khung.json")) or {}
    if bk.get("anh"):
        L.append(f"Bảng khung (mức {bk.get('muc')}): {bk.get('so_khung')} khung / {len(bk['anh'])} bảng, dày ở chỗ đổi nhiều")
    s = "\n".join(L)
    while len(s) > 900 and len(L) > 3:
        L.pop(-2 if len(L) > 4 else -1)
        s = "\n".join(L)
    return s[:900]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("du_an"); ap.add_argument("viec", choices=["do", "bang", "soi", "tom-tat"])
    ap.add_argument("--muc"); ap.add_argument("--tu", type=float); ap.add_argument("--den", type=float)
    ap.add_argument("--fps", type=float); ap.add_argument("--o-lon", action="store_true")
    a = ap.parse_args()
    if a.viec == "do":
        print(json.dumps(do(a.du_an), ensure_ascii=False))
    elif a.viec == "bang":
        print(json.dumps(bang(a.du_an, a.muc), ensure_ascii=False)[:2000])
    elif a.viec == "soi":
        print(json.dumps(soi(a.du_an, a.tu, a.den, a.fps, a.o_lon), ensure_ascii=False))
    else:
        print(tom_tat(a.du_an))
