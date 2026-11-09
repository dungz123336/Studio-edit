# -*- coding: utf-8 -*-
"""ĐỘNG HỌC của video mẫu (D2 chữ + D3 đồ hoạ) — MÁY ĐO, không đoán.

    python v3/hoc/dong_hoc.py <video> <thu_muc> [--fps 30] [--canh 600] [--khong-do-hoa]

1) Quét thô (4 khung/s, cạnh ngắn 360): cắt cảnh (histogram HSV), OCR dò khối chữ mỗi 0,5 s → vệt chữ (xuất hiện → biến mất,
   tách khi nội dung đổi tại chỗ) → tách PHỤ ĐỀ (dải y lặp nhiều vệt ngắn) với CHỮ PHỦ; đồ hoạ không phải chữ = vùng đổi
   rồi đứng yên (trước/sau đều tĩnh) không trùng chữ.
2) Mỗi sự kiện: giải mã DÀY (mặc định 30 khung/s, cạnh ngắn 600) cửa sổ ±1 s quanh lúc vào và lúc ra → mỗi khung đo
   (t, x, y, w, h, độ đục ước α, phần đã hiện, số ký tự/từ OCR) → phân loại kiểu vào/ra:
   pop (scale, có/không vượt) · slide (hướng) · fade · blur · typewriter · word_by_word · mask_reveal (hướng) · none,
   thời lượng + easing (khớp đường cong linear/in/out/in_out/back/spring/expo của engine `dung/anim.ease`).
3) Thuộc tính tĩnh lúc đã hiện đủ: neo SO VỚI MẶT (YuNet; toạ độ mặt = TÂM) — trên đầu / dưới cằm / ngang ngực / ngang mặt,
   căn trái/giữa/phải, cao chữ theo khung (px trên 1920), chữ HOA/thường, độ đậm ước, màu chữ, viền, bóng, nền khối
   (pill/chữ nhật/bo góc — đo bằng màu quanh chữ), đồ hoạ: hình dạng, bo góc ước, bóng, màu nền, nền mờ (loại vùng người bằng MODNet).
Ra: <thu_muc>/dong_hoc.json (+ dai-dong-hoc-N.jpg: mỗi hàng một sự kiện, khung trước→giữa→đủ có hộp đo + chú thích + đường cong).
`spec_may(dh)` → Style Spec dựng THUẦN từ số đo (đúng schema) — AI dùng làm điểm xuất phát; `so_spec.py` dùng để so 2 video.
"""
import os, sys, json, math, time, re, unicodedata
import numpy as np
import cv2

V3 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if V3 not in sys.path:
    sys.path.insert(0, V3)
import chung as C

HINH_HOC_TRUOC = True         # 1.2.21: hình học (scale/dịch tâm) quyết kiểu vào trước α/OCR; False = cách cũ (chỉ để so trong bộ thử nen_that)
PHIEN_BAN = 3                 # 1.2.21: quét thô ghi thêm dấu hiệu vật lý (trôi cùng nền / không mặt nhiều khối) → cache _quet-tho cũ không dùng lại
_OCR = None
_YUNET = {}


# ════════════════════════════════════════════════════════════════ tiện ích
import threading as _th
_OCR_LUONG = _th.local()          # 1.2.21: RapidOCR giữ trạng thái tiền xử lý theo lần gọi → mỗi luồng một máy OCR
_KHOA = _th.RLock()               # khoá cache LRU (ngắn)
_KHOA_OCR = _th.Lock()            # R5: tạo phiên ORT có khoá RIÊNG — không giữ _KHOA (cache) vài giây khi nạp mô hình
_KHOA_MAT = _th.Lock()            # R5: YuNet (cv2.dnn) KHÔNG an toàn khi nhiều luồng detect cùng một đối tượng


def _ocr_may():
    m = getattr(_OCR_LUONG, "may", None)
    if m is None:
        from rapidocr_onnxruntime import RapidOCR
        with _KHOA_OCR:                   # tạo phiên ORT từng luồng một (tạo đồng thời khi card lỗi có thể treo)
            # limit_type=max: KHÔNG phóng ảnh nhỏ lên 736 (mặc định "min" làm chậm 5×)
            m = RapidOCR(det_limit_side_len=736, det_limit_type="max", print_verbose=False)
        _OCR_LUONG.may = m
    return m


def so_luong():
    """số luồng xử lý cửa sổ song song: cau_hinh hoc_luong, không có → nửa số luồng máy (1..3). ORT đã đa luồng bên trong nên không lấy hết."""
    cfg = C.cau_hinh() or {}
    n = int(cfg.get("hoc_luong", 0) or 0)
    if n > 0:
        return n
    try:
        luong = int((C.phan_cung() or {}).get("luong") or os.cpu_count() or 4)
    except Exception:
        luong = os.cpu_count() or 4
    return max(1, min(3, luong // 2))


def xu_ly_song_song(nguon, lam, n_luong=None, log=None):
    """nguon: generator (wid, ts, crops, nho, roi, WH) với wid = (i, "vao"|"ra") — chạy `lam(...)` trong hồ luồng; cửa sổ RA của i
    chỉ chạy sau khi VÀO của i xong. Số cửa sổ đang giữ trong bộ nhớ ≤ n_luong + 2 (đọc trước chặn khi hồ đầy)."""
    from concurrent.futures import ThreadPoolExecutor
    import threading
    n = max(1, int(n_luong or so_luong()))
    if n == 1:
        for wid, ts, crops, nho, roi, WH in nguon:
            lam(wid, ts, crops, nho, roi, WH)
        return
    pool = ThreadPoolExecutor(max_workers=n)
    cho = threading.BoundedSemaphore(n + 2)
    fut_vao = {}
    tat_ca = []

    def _viec(wid, ts, crops, nho, roi, WH):
        try:
            if wid[1] == "ra":
                f = fut_vao.get(wid[0])
                if f is not None:
                    f.result()
            lam(wid, ts, crops, nho, roi, WH)
        finally:
            cho.release()
    try:
        for wid, ts, crops, nho, roi, WH in nguon:
            cho.acquire()
            f = pool.submit(_viec, wid, ts, crops, nho, roi, WH)
            if wid[1] == "vao":
                fut_vao[wid[0]] = f
            tat_ca.append(f)
        for f in tat_ca:
            f.result()
    finally:
        pool.shutdown(wait=True)


def ocr(anh_bgr, nhan_dang=True):
    """→ [{"hop": [x0,y0,x1,y1] px, "chu": str, "diem": float}] (nhan_dang=False: chỉ dò hộp, nhanh ~3×)"""
    if anh_bgr is None or anh_bgr.size == 0 or min(anh_bgr.shape[:2]) < 8:
        return []
    try:
        res, _ = _ocr_may()(np.ascontiguousarray(anh_bgr), use_det=True, use_cls=False, use_rec=nhan_dang)
    except Exception:
        return []
    ra = []
    for r in res or []:
        if nhan_dang and len(r) == 3 and isinstance(r[1], str):
            box, txt, sc = r[0], r[1], float(r[2])
        else:
            box, txt, sc = r, "", 1.0
        b = np.asarray(box, np.float32).reshape(-1, 2)
        ra.append({"hop": [float(b[:, 0].min()), float(b[:, 1].min()), float(b[:, 0].max()), float(b[:, 1].max())], "chu": txt, "diem": sc})
    return ra


def _kich_thuoc(info, canh_ngan):
    w0, h0 = int(info["w"]), int(info["h"])
    if w0 <= h0:
        w = int(canh_ngan) // 2 * 2
        h = int(round(h0 * w / w0 / 2)) * 2
    else:
        h = int(canh_ngan) // 2 * 2
        w = int(round(w0 * h / h0 / 2)) * 2
    return w, h


def _doc(video, info, a=0.0, b=None, fps=4.0, canh_ngan=360):
    """sinh (t, khung BGR) từ a..b ở fps, cạnh ngắn canh_ngan (ffmpeg pipe, seek chính xác)"""
    w, h = _kich_thuoc(info, canh_ngan)
    a = max(0.0, float(a))
    cmd = [C.duong("ffmpeg"), "-v", "error", "-nostdin"]
    if a > 0:
        cmd += ["-ss", f"{a:.3f}"]
    cmd += ["-i", video]
    if b is not None:
        cmd += ["-t", f"{max(0.05, b - a):.3f}"]
    # 1.2.21: HDR / 10-bit → chung.loc_mau_vao(info) (A1) đặt TRƯỚC scale; chưa có hàm → format=yuv420p khi không phải 8-bit
    loc = ""
    try:
        f_loc = getattr(C, "loc_mau_vao", None)
        loc = f_loc(info) if f_loc else ("format=yuv420p" if (info.get("bit_depth") or 8) != 8 or info.get("hdr") else "")
    except Exception:
        loc = ""
    vf = (loc + "," if loc else "") + f"fps={fps},scale={w}:{h}:flags=area"
    cmd += ["-an", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    cfg = C.cau_hinh() or {}
    p = C.popen(cmd, stdout=-1, uu_tien_thap=bool(cfg.get("hoc_ffmpeg_uu_tien_thap", False)))
    n = w * h * 3
    # 1.2.21: luồng đọc trước (hàng đợi có trần) — ffmpeg giải mã song song lúc python đang đo; ống Windows chỉ 64 KB nên không có luồng này
    # thì ffmpeg phải chờ từng khung (giải mã thành nối tiếp với OCR/MODNet).
    import threading, queue
    q = queue.Queue(maxsize=int(cfg.get("hoc_doc_truoc_khung", 24) or 24))
    HET = object()

    def _doc_luong():
        k = 0
        try:
            while True:
                buf = p.stdout.read(n)
                if len(buf) < n:
                    break
                q.put((a + k / fps, np.frombuffer(buf, np.uint8).reshape(h, w, 3)))
                k += 1
        except Exception:
            pass
        finally:
            q.put(HET)
    th = threading.Thread(target=_doc_luong, daemon=True); th.start()
    try:
        while True:
            it = q.get()
            if it is HET:
                break
            yield it
    finally:
        # R5: giết ffmpeg TRƯỚC, rồi rút cạn hàng đợi để luồng đọc trước (có thể đang chặn ở q.put khi hàng đầy) thoát ra —
        # trước đây người dùng dừng sớm (break / lỗi) → luồng kẹt ở q.put, join chờ 5 s rồi bỏ rơi luồng + 24 khung trong RAM.
        try:
            p.kill()
        except Exception:
            pass
        while th.is_alive():
            try:
                q.get(timeout=0.2)
            except queue.Empty:
                pass
        p.wait()
        try:
            p.stdout.close()
        except Exception:
            pass


def _hist(bgr):
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    hs = cv2.calcHist([hsv], [0, 1], None, [16, 8], [0, 180, 0, 256])
    v = cv2.calcHist([hsv], [2], None, [8], [0, 256])
    hs = cv2.normalize(hs, None, alpha=1, norm_type=cv2.NORM_L1).flatten()
    v = cv2.normalize(v, None, alpha=1, norm_type=cv2.NORM_L1).flatten()
    return np.concatenate([hs, v]).astype(np.float32)


def _hex(bgr):
    b, g, r = [int(max(0, min(255, round(float(x))))) for x in bgr[:3]]
    return "#%02X%02X%02X" % (r, g, b)


def _lab(bgr):
    a = np.uint8([[[int(max(0, min(255, round(float(x))))) for x in bgr[:3]]]])
    L, A, B = cv2.cvtColor(a, cv2.COLOR_BGR2LAB)[0, 0].astype(float)
    return L * 100 / 255, A - 128, B - 128


def delta_e(hex1, hex2):
    """ΔE CIE76 giữa 2 màu #RRGGBB"""
    def bgr(h):
        h = h.lstrip("#")
        return int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)
    a, b = _lab(bgr(hex1)), _lab(bgr(hex2))
    return float(math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b))))


def _bao_hoa(bgr):
    a = np.uint8([[[int(max(0, min(255, round(float(x))))) for x in bgr[:3]]]])
    h, s, v = cv2.cvtColor(a, cv2.COLOR_BGR2HSV)[0, 0]
    return float(s) / 255 * float(v) / 255, float(v) / 255


def _kmeans(px, k=3):
    """px Nx3 → (tâm kx3, tỉ lệ k) sắp theo tỉ lệ giảm"""
    px = np.asarray(px, np.float32).reshape(-1, 3)
    if len(px) > 6000:
        px = px[np.random.default_rng(0).choice(len(px), 6000, replace=False)]
    k = max(1, min(k, len(px) // 10))
    if k <= 1 or len(px) < 20:
        return (np.median(px, 0).reshape(1, 3) if len(px) else np.zeros((1, 3), np.float32)), np.ones(1)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, lab, cen = cv2.kmeans(px, k, None, crit, 2, cv2.KMEANS_PP_CENTERS)
    dem = np.bincount(lab.flatten(), minlength=k).astype(float)
    tt = np.argsort(-dem)
    return cen[tt], dem[tt] / dem.sum()


def _khong_dau(s):
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D")
    return re.sub(r"[^A-Za-z0-9]", "", s).upper()


def _so_tu(s):
    return len([w for w in re.split(r"\s+", (s or "").strip()) if re.search(r"\w", w)])


def _ty_le_hoa(s):
    chu = [c for c in (s or "") if c.isalpha()]
    if not chu:
        return None
    return sum(1 for c in chu if c.isupper()) / len(chu)


def _iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0.0


def _chong_nho(a, b):
    """giao / diện tích hộp nhỏ hơn"""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    m = min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]))
    return ix * iy / m if m > 0 else 0.0


def _hop_chung(a, b):
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def _font_ve(co=16):
    from PIL import ImageFont
    for p in (os.path.join(C.duong("font_mac_dinh"), "BeVietnamPro-Regular.ttf"), "arial.ttf"):
        try:
            return ImageFont.truetype(p, co)
        except Exception:
            pass
    return ImageFont.load_default()


def _mat(anh_bgr):
    """→ mặt lớn nhất {"x","y","w","h"} (TÂM, chuẩn hoá) hoặc None — YuNet v3/mo-hinh"""
    try:
        h0, w0 = anh_bgr.shape[:2]
        sw = 320
        sh = int(round(h0 * sw / w0 / 2)) * 2
        nho = cv2.resize(anh_bgr, (sw, sh), interpolation=cv2.INTER_AREA)
        with _KHOA_MAT:                   # R5: một đối tượng YuNet dùng chung → detect từng luồng một (1.2.21 gọi _mat từ hồ luồng)
            if (sw, sh) not in _YUNET:
                md = C.duong_ascii(os.path.join(C.duong("mo_hinh"), "yunet.onnx"))
                _YUNET[(sw, sh)] = cv2.FaceDetectorYN.create(md, "", (sw, sh), score_threshold=0.6, nms_threshold=0.3, top_k=20)
            _, f = _YUNET[(sw, sh)].detect(nho)
        if f is None or not len(f):
            return None
        f = max(f, key=lambda r: r[2] * r[3])
        x, y, w, h = [float(v) for v in f[:4]]
        return {"x": round((x + w / 2) / sw, 4), "y": round((y + h / 2) / sh, 4), "w": round(w / sw, 4), "h": round(h / sh, 4)}
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════ 0) CACHE DÙNG CHUNG (1.2.21) — dong_hoc + ban_ghi + dung_lai
# Trần dung lượng theo cau_hinh().get("cache_anh_mb", 300). Ba cache: cửa sổ giải mã (khoá a,b,hộp,fps,cạnh), OCR (khoá t, roi),
# mặt nạ người (MODNet một lần mỗi ô lưới `hoc_alpha_fps` khung/giây trên khung 540p, cắt theo thời điểm khi cần).
class _CacheLRU:
    """cache có trần byte: khoá bất kỳ → (giá trị, cỡ ước); đầy thì bỏ mục ít dùng nhất"""

    def __init__(self, tran_mb):
        from collections import OrderedDict
        self.d = OrderedDict(); self.tong = 0; self.tran = max(1, int(tran_mb * 1024 * 1024)); self.trung = 0; self.truot = 0

    def lay(self, k):
        with _KHOA:
            if k in self.d:
                self.d.move_to_end(k); self.trung += 1
                return self.d[k][0]
            self.truot += 1
            return None

    def dat(self, k, v, co):
        with _KHOA:
            if k in self.d:
                self.tong -= self.d.pop(k)[1]
            self.d[k] = (v, int(co)); self.tong += int(co)
            while self.tong > self.tran and len(self.d) > 1:
                _, (_, c) = self.d.popitem(last=False); self.tong -= c

    def xoa(self):
        with _KHOA:
            self.d.clear(); self.tong = 0


class _Cache:
    def __init__(self):
        cfg = C.cau_hinh() or {}
        self.mb = float(cfg.get("cache_anh_mb", 300) or 300)
        self.fps_alpha = float(cfg.get("hoc_alpha_fps", 2) or 2)
        self.cua_so = _CacheLRU(self.mb * 0.55)        # cửa sổ giải mã
        self.ocr = _CacheLRU(self.mb * 0.05)           # kết quả OCR
        self.alpha = _CacheLRU(self.mb * 0.28)         # mặt nạ người uint8 540p theo ô lưới
        self.khung_alpha = _CacheLRU(self.mb * 0.12)   # khung 540p (JPEG) cho MODNet, theo ô lưới
        self.video = None                              # khoá video đang học (C.bam)
        self.kich_thuoc_alpha = None
        self.giay_alpha = 0.0; self.so_alpha = 0        # đo: MODNet chạy bao nhiêu lần, bao lâu


_CACHE = None


def cache():
    global _CACHE
    if _CACHE is None:
        _CACHE = _Cache()
    return _CACHE


def dat_video(video):
    """đặt video đang học cho cache (khoá theo băm đường dẫn+size+mtime); đổi video → bỏ mọi mục cũ"""
    cs = cache()
    k = C.bam(video)
    if cs.video != k:
        for c in (cs.cua_so, cs.ocr, cs.alpha, cs.khung_alpha):
            c.xoa()
        cs.video = k; cs.kich_thuoc_alpha = None
    return k


def thong_ke_cache():
    cs = cache()
    r = {t: {"muc": len(c.d), "mb": round(c.tong / 1048576, 1), "trung": c.trung, "truot": c.truot}
         for t, c in (("cua_so", cs.cua_so), ("ocr", cs.ocr), ("alpha", cs.alpha), ("khung_alpha", cs.khung_alpha))}
    r["modnet"] = {"lan": cs.so_alpha, "giay": round(cs.giay_alpha, 1)}
    return r


def _roi_cua(hop, W, H, mo_rong=(0.45, 1.0)):
    bw, bh = (hop[2] - hop[0]) * W, (hop[3] - hop[1]) * H
    mx = max(bw * mo_rong[0], 0.08 * W); my = max(bh * mo_rong[1], 0.04 * H)
    x0 = int(max(0, hop[0] * W - mx)); x1 = int(min(W, hop[2] * W + mx))
    y0 = int(max(0, hop[1] * H - my)); y1 = int(min(H, hop[3] * H + my))
    return (x0, y0, x1, y1)


def _khoa_cua_so(vk, a, b, hop, fps, canh, mo_rong):
    return (vk, round(float(a), 3), round(float(b), 3), tuple(round(float(x), 4) for x in hop), float(fps), int(canh), tuple(mo_rong))


def ocr_cs(anh_bgr, t, roi, nhan_dang=True):
    """OCR qua cache khoá (video, t, roi, nhận dạng?) — cùng khung cùng vùng chỉ nhận dạng MỘT lần (lần đo "thẻ nền" dùng lại)"""
    cs = cache()
    k = (cs.video, round(float(t), 3), tuple(int(v) for v in roi), bool(nhan_dang))
    r = cs.ocr.lay(k)
    if r is None:
        r = ocr(anh_bgr, nhan_dang)
        cs.ocr.dat(k, r, 200 + 120 * len(r))
    return [dict(x, hop=list(x["hop"])) for x in r]


def cua_so_hang_loat(video, info, ds, fps, canh, mo_rong=(0.45, 1.0), khe=2.0, ghi_cache=False, log=None):
    """MỘT lượt giải mã cho nhiều cửa sổ. ds = [{"id", "a", "b", "hop"}] → sinh (id, ts, crops, nho, roi, (W,H)) khi cửa sổ đã đủ khung,
    theo thứ tự `b` tăng dần (cửa sổ RA của một vệt luôn kết thúc sau cửa sổ VÀO của nó). Khoảng trống > `khe` giây giữa các cửa sổ
    → mở ffmpeg mới (seek) thay vì giải mã phần không cần. Khung nhỏ 320 dùng chung giữa các cửa sổ cùng thời điểm (không chép).
    R5: · mọi cửa sổ trong ds đều được trả đúng MỘT lần (cửa sổ không nhận khung nào → trả rỗng), không mất cửa sổ khi a ≥ b hay lệch đoạn
        · id dạng (i, "ra") luôn trả SAU (i, "vao") (xu_ly_song_song dựa vào thứ tự này để RA chờ VÀO)
        · ghi_cache mặc định False: cache cửa sổ chỉ có ghi, không ai đọc lại (dong_hoc 30/s, ban_ghi 15/s → khoá khác) → giữ ~160 MB vô ích"""
    W, H = _kich_thuoc(info, canh)
    dur = float(info.get("dur") or 0)
    cs = cache()
    vk = cs.video or dat_video(video)
    muc = []
    for d in ds:
        a = max(0.0, float(d["a"])); b = min(dur, float(d["b"])) if dur else float(d["b"])
        muc.append({"id": d["id"], "a": a, "b": b, "hop": d["hop"], "roi": _roi_cua(d["hop"], W, H, mo_rong), "ts": [], "crops": [], "nho": [],
                    "_tra": False})
    muc.sort(key=lambda m: (m["a"], m["b"]))
    co_vao = {m["id"][0] for m in muc if isinstance(m["id"], tuple) and len(m["id"]) == 2 and m["id"][1] == "vao"}
    da_vao = set()
    cho_ra = {}

    def _tra(m):
        """trả một cửa sổ, giữ RA lại tới khi VÀO cùng i đã trả"""
        if m["_tra"]:
            return
        wid = m["id"]
        if isinstance(wid, tuple) and len(wid) == 2 and wid[1] == "ra" and wid[0] in co_vao and wid[0] not in da_vao:
            cho_ra[wid[0]] = m
            return
        m["_tra"] = True
        yield _tra_cua_so(m, cs, vk, fps, canh, mo_rong, W, H, ghi_cache)
        if isinstance(wid, tuple) and len(wid) == 2 and wid[1] == "vao":
            da_vao.add(wid[0])
            r = cho_ra.pop(wid[0], None)
            if r is not None:
                r["_tra"] = True
                yield _tra_cua_so(r, cs, vk, fps, canh, mo_rong, W, H, ghi_cache)
    # đoạn giải mã liên tục
    doan = []
    for m in muc:
        if doan and m["a"] - doan[-1][1] <= khe:
            doan[-1][1] = max(doan[-1][1], m["b"])
        else:
            doan.append([m["a"], m["b"]])
    i_tiep = 0
    dang = []
    hn = int(round(320 * H / W))
    so_khung = 0
    for a_d, b_d in doan:
        if b_d <= a_d:
            continue
        for t, f in _doc(video, info, a_d, b_d, fps, canh):
            so_khung += 1
            while i_tiep < len(muc) and muc[i_tiep]["a"] - 0.5 / fps <= t:
                if muc[i_tiep]["a"] >= a_d - 1e-6 and muc[i_tiep]["a"] <= b_d + 1e-6:
                    dang.append(muc[i_tiep])
                i_tiep += 1
            # cửa sổ đã đủ khung → trả
            xong = [m for m in dang if t >= m["b"] - 1e-6]
            if xong:
                dang = [m for m in dang if m not in xong]
                for m in sorted(xong, key=lambda m: m["b"]):
                    yield from _tra(m)
            if not dang:
                continue
            nho = None
            for m in dang:
                m["ts"].append(t)
                x0, y0, x1, y1 = m["roi"]
                m["crops"].append(f[y0:y1, x0:x1].copy())
                if nho is None:
                    nho = cv2.resize(f, (320, hn), interpolation=cv2.INTER_AREA)
                m["nho"].append(nho)
        # hết đoạn → mọi cửa sổ đang mở trong đoạn trả nốt
        for m in sorted(dang, key=lambda m: m["b"]):
            yield from _tra(m)
        dang = []
    # cửa sổ chưa bao giờ nhận khung (ngoài đoạn / rỗng / bị bỏ qua) → trả rỗng, theo thứ tự a
    for m in muc:
        if not m["_tra"]:
            yield from _tra(m)
    for r in list(cho_ra.values()):                        # RA mà VÀO không có trong ds (không thể xảy ra, phòng hờ)
        if not r["_tra"]:
            r["_tra"] = True
            yield _tra_cua_so(r, cs, vk, fps, canh, mo_rong, W, H, ghi_cache)
    if log:
        log(f"  giải mã một lượt: {len(muc)} cửa sổ, {len(doan)} đoạn, {so_khung} khung ({fps:g} khung/s, cạnh {canh})")


def _tra_cua_so(m, cs, vk, fps, canh, mo_rong, W, H, ghi_cache):
    ts, crops, nho, roi = m["ts"], m["crops"], m["nho"], m["roi"]
    if ghi_cache and crops:
        co = sum(c.nbytes for c in crops) + (nho[0].nbytes * len(nho) if nho else 0)
        cs.cua_so.dat(_khoa_cua_so(vk, m["a"], m["b"], m["hop"], fps, canh, mo_rong), (ts, crops, nho, roi, (W, H)), co)
    m["ts"] = []; m["crops"] = []; m["nho"] = []
    return m["id"], ts, crops, nho, roi, (W, H)


def proxy_cua(thu_muc, video=None):
    """proxy 540p mà hoc.py đã tạo trong <thu_muc>/cache (nếu có) — giải mã rẻ hơn video gốc.
    R5: có `video` → chỉ nhận proxy mang băm của chính video đó (proxy<cao>-<bam>.mp4); thư mục học lại với video đã đổi
    còn proxy cũ thì không lấy nhầm (glob trả thứ tự bất kỳ)."""
    import glob as _g
    ung = [p for p in _g.glob(os.path.join(_g.escape(thu_muc), "cache", "proxy*.mp4")) if os.path.getsize(p) > 1000]
    if not ung:
        return None
    if video:
        k = C.bam(video)
        ung = [p for p in ung if k in os.path.basename(p)]
        if not ung:
            return None
    return max(ung, key=os.path.getmtime)


def _nap_khung_alpha(video, info, cs, nguon=None, log=None, a=0.0, b=None):
    """một lượt đọc khung lưới fps_alpha (cạnh ngắn 540) → JPEG trong cache (≈ 60 KB/khung).
    a/b: chỉ đọc đoạn [a, b) (R5: nạp lại MỘT ô lưới bị đẩy khỏi cache thay vì đọc lại cả video); cả video → ghi kich_thuoc_alpha."""
    src = nguon if (nguon and os.path.isfile(nguon)) else video
    inf = (C.ffprobe(src) or info) if src != video else info
    n = 0
    w, h = _kich_thuoc(inf, 540)
    for t, f in _doc(src, inf, a, b, cs.fps_alpha, 540):
        j = int(round(t * cs.fps_alpha))
        ok, buf = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if ok:
            cs.khung_alpha.dat((cs.video, "jpg", j), buf.tobytes(), len(buf) + 64)
            n += 1
    if b is None and a <= 0:
        cs.kich_thuoc_alpha = (w, h, n)
        if log:
            log(f"  khung lưới mặt nạ người: {n} khung ({cs.fps_alpha:g}/s, 540p) từ {os.path.basename(src)}")


_KHOA_ALPHA = _th.Lock()


def nguoi_tai(video, info, t, W, H, roi=None, nguon=None, log=None):
    """mặt nạ người tại giây t → float32 0..1 cỡ W×H (cắt roi nếu có). MODNet 512 chạy MỘT lần mỗi ô lưới (hoc_alpha_fps, mặc định 2/s)
    trên khung 540p; dong_hoc và ban_ghi dùng chung; ô lưới chưa tách thì tách lúc gọi (lười) — chỉ tốn ở chỗ có chữ."""
    cs = cache()
    if cs.video is None:
        dat_video(video)
    with _KHOA_ALPHA:
        if cs.kich_thuoc_alpha is None:
            _nap_khung_alpha(video, info, cs, nguon=nguon, log=log)
    wa, ha, n = cs.kich_thuoc_alpha
    # R5: kẹp j theo THỜI LƯỢNG nguồn, không theo số khung lưới đọc được — lưới cụt (proxy cụt / ffmpeg bị giết) thì mọi t sau đó
    # dính khung cuối (gặp thật: proxy 29,9 s → t > 30 s đều lấy mặt nạ khung 59); ô thiếu sẽ nạp lại đúng ô bên dưới
    n_dur = int(math.floor(max(0.0, float(info.get("dur") or 0) - 1e-3) * cs.fps_alpha)) + 1
    if n < n_dur - 1 and not getattr(cs, "_bao_luoi_ngan", False):
        cs._bao_luoi_ngan = True
        if log:
            log(f"  (lưới mặt nạ người chỉ có {n}/{n_dur} khung — nguồn/proxy cụt? ô thiếu sẽ đọc lại từ video gốc)")
    j = int(round(float(t) * cs.fps_alpha))
    j = max(0, min(j, max(0, max(n, n_dur) - 1)))
    al = cs.alpha.lay((cs.video, "al", j))
    if al is None:
        with _KHOA_ALPHA:                                  # mỗi ô lưới tách MỘT lần dù nhiều luồng cùng hỏi
            al = cs.alpha.lay((cs.video, "al", j))
            if al is None:
                buf = cs.khung_alpha.lay((cs.video, "jpg", j))
                if buf is None:                                   # bị đẩy khỏi cache → đọc lại ĐÚNG ô lưới này (R5: trước đọc lại cả video,
                    ta = j / cs.fps_alpha                         # video dài hơn trần cache lại bị đẩy tiếp → lỗi "không có khung lưới")
                    _nap_khung_alpha(video, info, cs, nguon=nguon, a=ta, b=ta + 1.5 / cs.fps_alpha)
                    buf = cs.khung_alpha.lay((cs.video, "jpg", j))
                    if buf is None and nguon:                     # proxy cụt → lấy từ video gốc
                        _nap_khung_alpha(video, info, cs, nguon=None, a=ta, b=ta + 1.5 / cs.fps_alpha)
                        buf = cs.khung_alpha.lay((cs.video, "jpg", j))
                if buf is None:                                   # ô cuối video (t ≈ dur) không giải mã được → lấy ô gần nhất phía trước
                    for j2 in range(j - 1, max(-1, j - 4), -1):
                        al2 = cs.alpha.lay((cs.video, "al", j2))
                        if al2 is not None:
                            cs.alpha.dat((cs.video, "al", j), al2, al2.nbytes); al = al2; break
                        buf = cs.khung_alpha.lay((cs.video, "jpg", j2))
                        if buf is not None:
                            break
                if al is None and buf is None:
                    raise RuntimeError("không có khung lưới mặt nạ")
            if al is None:
                bgr = cv2.imdecode(np.frombuffer(buf, np.uint8), cv2.IMREAD_COLOR)
                from doc import alpha as AL
                t_ = time.time()
                hb, wb = bgr.shape[:2]
                # mặt nạ chỉ để LOẠI vùng người khi đo chữ (không ghép hình) → mạng cạnh ngắn `hoc_alpha_ref` (mặc định 320, ≈ 3× nhanh hơn 512 trên CPU)
                ref = int((C.cau_hinh() or {}).get("hoc_alpha_ref", 320) or 320)
                # R5: hỏi phiên MỘT lần → provider thật (DML không khởi tạo được → alpha._session đã rơi về CPU) rồi ghim cho cả lượt học;
                # trước đây mỗi ô lưới lại thử DML 3 lần (ref/768/512) mới tới CPU — card lỗi thì mỗi lần vài giây, có lúc treo
                pv = getattr(cs, "pv_alpha", None)
                if pv is None:
                    # R5: mặc định CPU như ban_ghi 1.2.20 (ảnh 540p @320 ≈ 0,3 s, không xếp lượt card). Card DML lỗi "GPU will not respond"
                    # trên máy thử trả mặt nạ SAI mà không báo (t=50 s không có người: DML 0,169 · CPU 0,000) → chỉ dùng GPU khi
                    # cau_hinh hoc_alpha_gpu = true
                    pv = "CPUExecutionProvider"
                    if (C.cau_hinh() or {}).get("hoc_alpha_gpu"):
                        try:
                            _, pv = AL._session(AL.provider_mac_dinh())
                        except Exception:
                            pv = "CPUExecutionProvider"
                    cs.pv_alpha = pv
                    if log:
                        log(f"  mặt nạ người: {pv} (ref {ref})")
                try:
                    a = AL._tach_anh_1(bgr, wb, hb, ref, "thuong", pv)
                except Exception:
                    cs.pv_alpha = "CPUExecutionProvider"
                    a = AL._tach_anh_1(bgr, wb, hb, ref, "thuong", "CPUExecutionProvider")
                al = np.clip(a * 255.0, 0, 255).astype(np.uint8)
                cs.alpha.dat((cs.video, "al", j), al, al.nbytes)
                cs.giay_alpha += time.time() - t_; cs.so_alpha += 1
    out = cv2.resize(al, (int(W), int(H)), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
    if roi is not None:
        x0, y0, x1, y1 = [int(v) for v in roi]
        out = out[y0:y1, x0:x1]
    return out


# ════════════════════════════════════════════════════════════════ 1) quét thô
def _gom_khoi(hops):
    """hộp dòng (chuẩn hoá) → khối nhiều dòng (dòng kề dọc, chồng ngang)"""
    hops = sorted(hops, key=lambda b: b[1])
    khoi = []
    for b in hops:
        h = b[3] - b[1]
        gan = None
        for k in khoi:
            kb = k["hop"]
            hk = k["dong"][-1][3] - k["dong"][-1][1]
            khe = b[1] - kb[3]
            ngang = min(b[2], kb[2]) - max(b[0], kb[0])
            if -0.5 * h < khe < 0.75 * min(h, hk) and (ngang > 0 or abs((b[0] + b[2]) / 2 - (kb[0] + kb[2]) / 2) < 0.12) and 0.55 < h / max(hk, 1e-6) < 1.8:
                gan = k
                break
        if gan:
            gan["hop"] = _hop_chung(gan["hop"], b); gan["dong"].append(b)
        else:
            khoi.append({"hop": list(b), "dong": [b]})
    return khoi


def _quet_tho(video, info, fps_tho=4.0, buoc_ocr=0.5, cao_min=0.016, log=print):
    nho, ts, hists = [], [], []
    k_ocr = max(1, int(round(buoc_ocr * fps_tho)))
    vet, dang = [], []
    t_dem = time.time()
    so_ocr = 0
    g_truoc = None                      # 1.2.21: dấu hiệu vật lý — dịch chuyển NỀN giữa hai lượt dò (phase correlation) + có mặt + số khối
    for k, (t, f) in enumerate(_doc(video, info, 0, None, fps_tho, 360)):
        H, W = f.shape[:2]
        n_ = cv2.resize(f, (W // 2, H // 2), interpolation=cv2.INTER_AREA)
        nho.append(n_); ts.append(t); hists.append(_hist(n_))
        if k % k_ocr:
            continue
        so_ocr += 1
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        g_pc = cv2.cvtColor(n_, cv2.COLOR_BGR2GRAY).astype(np.float32)
        dich_nen = (0.0, 0.0)
        if g_truoc is not None and g_truoc.shape == g_pc.shape:
            try:
                (dx_, dy_), dap = cv2.phaseCorrelate(g_truoc, g_pc)
                if dap > 0.08:                      # có đỉnh tương quan rõ → nền dịch (lắc máy / pan); không rõ (cắt cảnh) → 0
                    dich_nen = (float(dx_) / g_pc.shape[1], float(dy_) / g_pc.shape[0])
            except Exception:
                pass
        g_truoc = g_pc
        co_mat = _mat(f) is not None
        hops = [[o["hop"][0] / W, o["hop"][1] / H, o["hop"][2] / W, o["hop"][3] / H] for o in ocr(f, nhan_dang=False)]
        hops = [b for b in hops if (b[3] - b[1]) >= cao_min and (b[2] - b[0]) >= 0.02]
        khoi = _gom_khoi(hops)
        n_khoi = len(khoi)
        da = set()
        for tr in dang:
            tot, j_tot = 0.0, None
            for j, kb in enumerate(khoi):
                if j in da:
                    continue
                sc = _chong_nho(tr["hop_cuoi"], kb["hop"])
                hy = max(tr["hop_cuoi"][3] - tr["hop_cuoi"][1], kb["hop"][3] - kb["hop"][1])
                if sc > 0.5 and abs((tr["hop_cuoi"][1] + tr["hop_cuoi"][3]) / 2 - (kb["hop"][1] + kb["hop"][3]) / 2) < 0.75 * hy and sc > tot:
                    tot, j_tot = sc, j
            if j_tot is None:
                tr["mien"] += 1
                continue
            kb = khoi[j_tot]
            # nội dung có đổi tại chỗ không (phụ đề thay cụm): so pixel xám trong phần giao (khung 360)
            gi = [max(tr["hop_cuoi"][0], kb["hop"][0]), max(tr["hop_cuoi"][1], kb["hop"][1]), min(tr["hop_cuoi"][2], kb["hop"][2]), min(tr["hop_cuoi"][3], kb["hop"][3])]
            x0, y0, x1, y1 = int(gi[0] * W), int(gi[1] * H), int(math.ceil(gi[2] * W)), int(math.ceil(gi[3] * H))
            doi = 0.0
            if x1 > x0 + 2 and y1 > y0 + 2:
                doi = float((np.abs(g[y0:y1, x0:x1].astype(np.int16) - tr["xam"][y0:y1, x0:x1].astype(np.int16)) > 45).mean())
            if doi > 0.2 and (_iou(tr["hop_cuoi"], kb["hop"]) < 0.88 or doi > 0.45):   # nền zoom/động dưới chữ đứng yên ≠ đổi chữ
                tr["mien"] = 99            # đóng vệt cũ; khối này mở vệt mới
                tr["t_ra"] = t
                continue
            da.add(j_tot)
            tr["mien"] = 0
            tr["t_cuoi"] = t
            tr["hop"] = _hop_chung(tr["hop"], kb["hop"])
            tr["hop_dau_cuoi"] = tr.get("hop_dau_cuoi") or tr["hop_cuoi"]
            # dấu hiệu vật lý: hộp dịch bao nhiêu so với lượt trước, nền dịch bao nhiêu cùng lúc
            cx_, cy_ = (kb["hop"][0] + kb["hop"][2]) / 2, (kb["hop"][1] + kb["hop"][3]) / 2
            cx0, cy0 = (tr["hop_cuoi"][0] + tr["hop_cuoi"][2]) / 2, (tr["hop_cuoi"][1] + tr["hop_cuoi"][3]) / 2
            tr["buoc"].append([round(cx_ - cx0, 4), round(cy_ - cy0, 4), round(dich_nen[0], 4), round(dich_nen[1], 4), int(co_mat), n_khoi])
            tr["hop_cuoi"] = kb["hop"]
            tr["n"] += 1
            tr["xam"] = g
            tr["so_dong"] = max(tr["so_dong"], len(kb["dong"]))
            tr["cao_dong"].append(float(np.median([d[3] - d[1] for d in kb["dong"]])))
        con = []
        for tr in dang:
            if tr["mien"] >= 2 or tr["mien"] == 99:
                tr.setdefault("t_ra", tr["t_cuoi"] + buoc_ocr)
                vet.append(tr)
            else:
                con.append(tr)
        dang = con
        for j, kb in enumerate(khoi):
            if j not in da:
                dang.append({"t_dau": t, "t_cuoi": t, "hop": list(kb["hop"]), "hop_dau": list(kb["hop"]), "hop_cuoi": list(kb["hop"]), "n": 1, "mien": 0,
                             "xam": g, "so_dong": len(kb["dong"]), "cao_dong": [float(np.median([d[3] - d[1] for d in kb["dong"]]))],
                             "buoc": [[0.0, 0.0, 0.0, 0.0, int(co_mat), n_khoi]]})
    for tr in dang:
        tr.setdefault("t_ra", tr["t_cuoi"] + buoc_ocr)
        vet.append(tr)
    for tr in vet:
        tr.pop("xam", None)
        tr["cao_dong"] = float(np.median(tr["cao_dong"]))
        tr["t_ra"] = min(tr["t_ra"], float(info["dur"]))
        _dau_hieu_vet(tr)
    log(f"  quét thô: {len(ts)} khung, {so_ocr} lượt dò chữ, {len(vet)} vệt chữ ({time.time() - t_dem:.0f}s)")
    return nho, ts, hists, vet


def _dau_hieu_vet(tr):
    """dấu hiệu VẬT LÝ (không ngưỡng gu) cho một vệt → tr["nghi_ngo"] = "canh" | "web" | None và tr["dau_hieu"] = số đo:
    · canh: hộp chữ TRÔI CÙNG NỀN giữa các lượt dò (dịch hộp ≈ dịch nền đo bằng phase correlation khi nền có dịch) — chữ nằm trong cảnh quay
    · web: phần lớn lượt dò KHÔNG có mặt và ≥ 3 khối chữ cùng lúc — màn hình / trang web quay lại
    Chỉ GHI dấu hiệu; bỏ hay giữ là việc của AI khi dùng ngữ pháp."""
    b = tr.get("buoc") or []
    dh = {"n": len(b)}
    tr["nghi_ngo"] = None
    if len(b) >= 2:
        sau = b[1:]                                            # bước đầu tiên không có dịch
        co_nen = [x for x in sau if math.hypot(x[2], x[3]) > 0.004]
        if co_nen:
            khop = [x for x in co_nen if math.hypot(x[0] - x[2], x[1] - x[3]) < max(0.004, 0.5 * math.hypot(x[2], x[3]))]
            dh["buoc_nen_dich"] = len(co_nen); dh["buoc_troi_cung_nen"] = len(khop)
            troi = sum(math.hypot(x[0], x[1]) for x in khop)
            dh["troi_tong_theo_cao"] = round(troi / max(tr["cao_dong"][0] if isinstance(tr["cao_dong"], list) else tr["cao_dong"], 1e-4), 2)
            if len(khop) >= 2 and len(khop) >= 0.6 * len(co_nen) and dh["troi_tong_theo_cao"] >= 0.5:
                tr["nghi_ngo"] = "canh"
    if b:
        kh_mat = [x for x in b if not x[4] and x[5] >= 3]
        dh["buoc_khong_mat_nhieu_khoi"] = len(kh_mat); dh["ti_le_khong_mat_nhieu_khoi"] = round(len(kh_mat) / len(b), 2)
        if tr["nghi_ngo"] is None and len(kh_mat) >= max(1, 0.5 * len(b)):
            tr["nghi_ngo"] = "web"
    tr["dau_hieu"] = dh
    tr.pop("buoc", None)
    return tr


def _cat_canh(hists, ts, nguong=0.45, khoang=0.5):
    cat = []
    for i in range(1, len(hists)):
        d = float(cv2.compareHist(hists[i - 1], hists[i], cv2.HISTCMP_BHATTACHARYYA))
        if d > nguong and (not cat or ts[i] - cat[-1][0] >= khoang):
            cat.append((ts[i], i, round(d, 3)))
    return cat


def _phan_vai(vet, dur):
    """vệt → vai: phu_de (dải y lặp nhiều vệt ngắn liên tiếp) | chu (chữ phủ). Bỏ vệt rác (1 lần thấy, nhỏ)."""
    tot = []
    for tr in vet:
        tr["dai"] = round(tr["t_ra"] - tr["t_dau"], 2)
        tr["cy"] = (tr["hop"][1] + tr["hop"][3]) / 2
        if tr["n"] < 2 and (tr["cao_dong"] < 0.03 or tr["cao_dong"] > 0.14):
            continue
        tot.append(tr)
    # nối vệt bị tách vì nội dung đổi TẠI CHỖ ngay lúc vào (scale/giải mã/nảy): vệt ngắn + vệt kế liền, cùng chỗ
    tot.sort(key=lambda r: r["t_dau"])
    gop = []
    for tr in tot:
        cha = None
        for g in gop:
            if abs(tr["t_dau"] - g["t_ra"]) < 0.05 and g.get("_so_tach", 0) < 3 and (tr["t_dau"] - g["t_dau"]) <= 1.1                     and _iou(g["hop_cuoi"], tr["hop"]) > 0.5:
                cha = g; break
        if cha:
            cha["t_cuoi"], cha["t_ra"] = tr["t_cuoi"], tr["t_ra"]
            cha["hop"] = _hop_chung(cha["hop"], tr["hop"]); cha["hop_cuoi"] = tr["hop_cuoi"]
            cha["n"] += tr["n"]; cha["_so_tach"] = cha.get("_so_tach", 0) + 1
            cha["dai"] = round(cha["t_ra"] - cha["t_dau"], 2)
            cha["cy"] = (cha["hop"][1] + cha["hop"][3]) / 2
            cha["doi_tai_cho"] = cha["_so_tach"]
        else:
            gop.append(tr)
    tot = gop
    # cụm dải y
    dai = []
    for tr in sorted(tot, key=lambda r: r["cy"]):
        for d in dai:
            if abs(d["cy"] - tr["cy"]) < 0.07:
                d["vet"].append(tr); d["cy"] = float(np.median([x["cy"] for x in d["vet"]])); break
        else:
            dai.append({"cy": tr["cy"], "vet": [tr]})
    for d in dai:
        vs = sorted(d["vet"], key=lambda r: r["t_dau"])
        n = len(vs)
        # độ phủ thời gian (hợp các đoạn) + khe trung vị giữa các vệt liên tiếp
        phu, cuoi = 0.0, -1.0
        for x in vs:
            a, b = max(x["t_dau"], cuoi), x["t_ra"]
            phu += max(0.0, b - a); cuoi = max(cuoi, b)
        phu /= max(dur, 1e-6)
        khe = [max(0.0, vs[i + 1]["t_dau"] - max(y["t_ra"] for y in vs[:i + 1])) for i in range(n - 1)]
        cao_tv = float(np.median([x["cao_dong"] for x in vs]))
        trung_vi = float(np.median([x["dai"] for x in vs]))
        la_phu_de = n >= max(5, dur / 12) and phu >= 0.3 and (float(np.median(khe)) if khe else 9) <= 1.0 and trung_vi <= 3.2
        d["phu_de"] = la_phu_de
        for x in vs:
            # chữ phủ đặt trùng dải phụ đề: dài hẳn VÀ to hẳn → vẫn là chữ phủ
            rieng = x["dai"] > 2.0 * trung_vi and x["dai"] >= 2.0 and x["cao_dong"] > 1.3 * cao_tv
            x["vai"] = "phu_de" if (la_phu_de and not rieng) else "chu"
            x["dai_y"] = round(d["cy"], 3)
    return tot


def _do_hoa_tho(nho, ts, cat_idx, vet, dur):
    """vùng đổi rồi ĐỨNG YÊN (trước & sau đều tĩnh), không trùng chữ → ứng viên đồ hoạ; vùng > 40% khung = cắt/zoom camera"""
    n = len(nho)
    if n < 10:
        return [], []
    Hs, Ws = nho[0].shape[:2]
    N = Hs * Ws
    gan_cat = set()
    for _, i, _ in cat_idx:
        gan_cat.update(range(i - 4, i + 5))
    k3 = np.ones((3, 3), np.uint8); k5 = np.ones((5, 5), np.uint8)
    ung, zoom = [], []
    F = [x.astype(np.int16) for x in nho]
    for i in range(3, n - 4):
        if i in gan_cat:
            continue
        ch = np.abs(F[i + 2] - F[i - 1]).max(2) > 40
        if ch.mean() < 0.003:
            continue
        st = (np.abs(F[i - 1] - F[i - 3]).max(2) < 25) & (np.abs(F[i + 2] - F[i + 4]).max(2) < 25)
        m = (ch & st).astype(np.uint8)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k3)
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k5)
        if m.mean() > 0.4:
            zoom.append((ts[i], i)); continue
        nc, lab, stt, _ = cv2.connectedComponentsWithStats(m)
        for c in range(1, nc):
            x, y, w, h, a = stt[c]
            if a < 0.004 * N or w < 6 or h < 6:
                continue
            hop = [x / Ws, y / Hs, (x + w) / Ws, (y + h) / Hs]
            ung.append({"i": i, "t": ts[i], "hop": hop, "dien_tich": a / N, "lap_day": a / float(w * h)})
    # gộp theo thời gian (cùng vùng trong 0,75 s → giữ cái lớn nhất)
    ung.sort(key=lambda r: -r["dien_tich"])
    giu = []
    for u in ung:
        if any(_iou(u["hop"], g["hop"]) > 0.35 and abs(u["t"] - g["t"]) < 0.8 for g in giu):
            continue
        giu.append(u)
    # bỏ vùng là chữ (trùng vệt chữ đang hiện quanh thời điểm đó)
    ra = []
    for u in sorted(giu, key=lambda r: r["t"]):
        chu = [tr for tr in vet if tr["t_dau"] - 1.0 <= u["t"] <= tr["t_ra"] + 0.5 and _chong_nho(u["hop"], tr["hop"]) > 0.45]
        dt_chu = sum((tr["hop"][2] - tr["hop"][0]) * (tr["hop"][3] - tr["hop"][1]) for tr in chu)
        dt_u = (u["hop"][2] - u["hop"][0]) * (u["hop"][3] - u["hop"][1])
        if chu and dt_chu > 0.55 * dt_u:
            continue                     # chính là chữ (đã đo ở phần chữ)
        u["co_chu"] = bool(chu)
        ra.append(u)
    # xuất hiện hay biến mất: so với trung vị cảnh
    bien = [0] + [i for _, i, _ in cat_idx] + [n]
    for u in ra:
        a = max(b for b in bien if b <= u["i"]); b = min(b for b in bien if b > u["i"])
        idx = np.linspace(a, b - 1, num=min(30, max(1, b - a))).astype(int)
        med = np.median(np.stack([nho[j] for j in idx]), 0)
        x0, y0, x1, y1 = int(u["hop"][0] * Ws), int(u["hop"][1] * Hs), int(math.ceil(u["hop"][2] * Ws)), int(math.ceil(u["hop"][3] * Hs))
        sau = nho[min(n - 1, u["i"] + 2)][y0:y1, x0:x1].astype(float); truoc = nho[u["i"] - 1][y0:y1, x0:x1].astype(float)
        m = med[y0:y1, x0:x1]
        u["xuat_hien"] = bool(np.abs(sau - m).mean() > np.abs(truoc - m).mean())
    return ra, zoom


# ════════════════════════════════════════════════════════════════ 2) đo dày một cửa sổ
def _cua_so(video, info, a, b, hop, fps, canh, mo_rong=(0.45, 1.0)):
    """giải mã [a,b] → (ts, crops ROI, khung nhỏ 320, roi px, kích thước khung dày). 1.2.21: qua cache khoá (a, b, hộp, fps, cạnh)."""
    W, H = _kich_thuoc(info, canh)
    cs = cache()
    vk = cs.video or dat_video(video)
    k = _khoa_cua_so(vk, a, b, hop, fps, canh, mo_rong)
    r = cs.cua_so.lay(k)
    if r is not None:
        return r
    x0, y0, x1, y1 = _roi_cua(hop, W, H, mo_rong)
    ts, crops, nho = [], [], []
    for t, f in _doc(video, info, a, b, fps, canh):
        ts.append(t)
        crops.append(f[y0:y1, x0:x1].copy())
        nho.append(cv2.resize(f, (320, int(round(320 * H / W))), interpolation=cv2.INTER_AREA))
    r = (ts, crops, nho, (x0, y0, x1, y1), (W, H))
    if crops:
        cs.cua_so.dat(k, r, sum(c.nbytes for c in crops) + sum(n.nbytes for n in nho))
    return r


def _hop_mask(m, phan=1.0):
    ys, xs = np.nonzero(m)
    if len(xs) < 12:
        return None
    lo, hi = (1.5, 98.5) if phan else (0, 100)
    return [float(np.percentile(xs, lo)), float(np.percentile(ys, lo)), float(np.percentile(xs, hi)) + 1, float(np.percentile(ys, hi)) + 1]


def _khop_ease(u, p):
    """→ [(ten, rmse, giãn)] tốt nhất trước; giãn = hệ số kéo dài thời lượng (đường 'out' tới 0,9 sớm hơn đích)"""
    try:
        from dung import anim
        e = anim.ease
    except Exception:
        def e(ten, x):
            x = min(1.0, max(0.0, x))
            return {"linear": x, "in": x ** 3, "out": 1 - (1 - x) ** 3, "in_out": 4 * x ** 3 if x < 0.5 else 1 - ((-2 * x + 2) ** 3) / 2,
                    "back": 1 + 2.70158 * (x - 1) ** 3 + 1.70158 * (x - 1) ** 2, "expo": 1 - 2 ** (-10 * x),
                    "spring": 1 - math.exp(-6 * x) * math.cos(4 * math.pi * x)}.get(ten, x)
    u = np.asarray(u, float); p = np.asarray(p, float)
    kq = []
    for ten in ("linear", "in", "out", "in_out", "back", "spring", "expo"):
        tot = None
        for gian in (1.0, 1.15, 1.35, 1.6):
            q = np.array([e(ten, x / gian) for x in u])
            r = float(np.sqrt(np.mean((q - p) ** 2)))
            if tot is None or r < tot[0]:
                tot = (r, gian)
        kq.append((ten, round(tot[0], 4), tot[1]))
    kq.sort(key=lambda r: r[1])
    return kq


def _do_chuyen_dong(ts, crops, k_sau, hop_roi, fps, ocr_on=True, nguoc=False, dong_sau=None, truoc_mau=None, vung=None, nguoi=None, hop_khac=None, roi=None):
    """crops[0] = trạng thái VẮNG, crops[k_sau] = trạng thái ĐỦ (đã đảo nếu đo lúc ra) → số đo + phân loại.
    roi (px cửa sổ): có thì OCR đi qua cache (t, roi) — khung nào đã nhận dạng rồi không nhận dạng lại."""
    if nguoc:
        ts = ts[::-1]; crops = crops[::-1]; k_sau = len(crops) - 1 - k_sau
    n = len(crops)
    if n < 4 or k_sau < 2:
        return {"kieu": "khong_do_duoc", "ly_do": "cửa sổ quá ngắn"}
    sau = crops[k_sau].astype(np.int16)
    if truoc_mau is None:
        truoc = crops[0].astype(np.int16)
    else:                      # đo CHỮ trong thẻ/pill: trạng thái vắng = màu nền khối
        truoc = np.empty_like(sau); truoc[:] = np.asarray(truoc_mau, np.int16).reshape(1, 1, 3)
    d = sau - truoc
    dn = np.abs(d).max(2)
    x0, y0, x1, y1 = [int(v) for v in hop_roi]
    M = np.zeros(dn.shape, bool)
    M[y0:y1, x0:x1] = dn[y0:y1, x0:x1] > 40
    if vung is not None:
        M &= vung
    # vùng tìm điểm ảnh lớp phủ khi đang chuyển: hộp ± lề (không ăn sang lớp phủ khác cạnh đó)
    VC = np.zeros(dn.shape, bool)
    hh_, ww_ = y1 - y0, x1 - x0
    VC[max(0, int(y0 - 0.6 * hh_)):int(y1 + 0.6 * hh_) + 1, max(0, int(x0 - 0.3 * ww_)):int(x1 + 0.3 * ww_) + 1] = True
    if vung is not None:
        VC &= cv2.dilate(vung.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    if nguoi is not None and nguoi.shape == dn.shape:
        # người (mặt/tay cử động) không phải lớp phủ — trừ chỗ chính lớp phủ đè lên người
        VC &= ~((nguoi > 0.5) & ~cv2.dilate(M.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool))
    if hop_khac:
        # lớp phủ KHÁC cùng lúc trong khung cắt (vd từ khoá to ngay dưới dòng nhỏ) — không tính vào lớp này
        K = np.zeros(dn.shape, bool)
        for hx in hop_khac:
            mw_, mh_ = 0.2 * (hx[2] - hx[0]), 0.25 * (hx[3] - hx[1])
            K[max(0, int(hx[1] - mh_)):max(0, int(hx[3] + mh_)) + 1, max(0, int(hx[0] - mw_)):max(0, int(hx[2] + mw_)) + 1] = True
        VC &= ~(K & ~cv2.dilate(M.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool))
    # chữ/đồ hoạ phủ ĐỨNG YÊN quanh lúc đủ; nền động (tay, người) thì không → loại
    on = np.ones(dn.shape, bool)
    sau_u8 = crops[k_sau]
    for k in (k_sau - 2, k_sau - 1, k_sau + 1, k_sau + 2):
        if 0 < k < n and k != k_sau:
            ad_ = cv2.absdiff(crops[k], sau_u8)
            b_, g_, r_ = cv2.split(ad_)
            on &= cv2.max(cv2.max(b_, g_), r_) < 24
    if (M & on).sum() >= 40:
        M &= on
    if dong_sau:
        R = np.zeros(dn.shape, bool)
        for o in dong_sau:
            hx = o["hop"]; pd = 0.25 * (hx[3] - hx[1])
            R[max(0, int(hx[1] - pd)):int(hx[3] + pd) + 1, max(0, int(hx[0] - pd)):int(hx[2] + pd) + 1] = True
        if (M & R).sum() >= 40:
            M &= R
    M = cv2.morphologyEx(M.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
    if M.sum() < 40:
        return {"kieu": "khong_do_duoc", "ly_do": "không thấy khác biệt vắng/đủ"}
    dd = (d.astype(np.float32) ** 2).sum(2)
    tam, tl_ = _kmeans(sau[M], 3)
    tam = tam.astype(np.int16)
    # bỏ màu trùng nền (vd áo đen sau chữ có bóng đen) — giữ màu đặc trưng của lớp phủ
    tr_px = truoc.reshape(-1, 3)
    pho = [float((np.abs(tr_px - c.reshape(1, 3)).max(1) < 48).mean()) for c in tam]
    giu_ = [c for c, f in zip(tam, pho) if f < 0.12]
    tam = np.array(giu_ if giu_ else [tam[int(np.argmin(pho))]], np.int16)

    # 1.2.21: vòng theo khung dùng cv2 (inRange / absdiff / max kênh — SIMD) thay numpy int16 cả khung; phần tích vô hướng chỉ trên điểm M
    tam_u8 = [np.clip(c.astype(int), 0, 255).astype(np.uint8) for c in tam]
    truoc_u8 = np.clip(truoc, 0, 255).astype(np.uint8)
    # 1.2.21: DẢI MÀU PHA — điểm ảnh nằm GIỮA nền (khung vắng, từng điểm) và màu lớp ± 32 mỗi kênh ⇒ bắt được chữ đang MỜ / NHỎ / TRƯỢT
    # (độ đục < 1, engine pop/slide luôn kèm opacity 0→1); dải màu cứng ±47 quanh màu lớp trước đây chỉ thấy chữ khi đã gần đục hẳn
    # → quỹ đạo tâm/tỉ lệ co giãn trống rỗng, pop/slide bị gọi là fade. Biên theo từng điểm tính MỘT lần mỗi màu (cv2.inRange nhận mảng biên).
    lo_hi = []
    for c in tam_u8:
        c_img = np.empty_like(truoc_u8); c_img[:] = c
        lo = cv2.subtract(cv2.min(truoc_u8, c_img), (32, 32, 32, 0)); hi = cv2.add(cv2.max(truoc_u8, c_img), (32, 32, 32, 0))
        lo_hi.append((lo, hi))

    def gan_bang_mau(f_u8):
        m = None
        for lo, hi in lo_hi:
            r = cv2.inRange(f_u8, lo, hi)
            m = r if m is None else cv2.bitwise_or(m, r)
        return m.astype(bool)

    def khac_nen(f_u8):
        ad = cv2.absdiff(f_u8, truoc_u8)
        b_, g_, r_ = cv2.split(ad)
        return cv2.max(cv2.max(b_, g_), r_) > 40

    Ms = M.sum()
    dM = d[M].astype(np.float32); ddM = dd[M]
    truoc_M = truoc[M].astype(np.float32)
    dd_tong = max(float(ddM.sum()), 1.0); dd_max = np.maximum(ddM, 1.0)
    al, ar, hop, deu, net = [], [], [], [], []
    lap_sau = cv2.Laplacian(cv2.cvtColor(sau.astype(np.uint8), cv2.COLOR_BGR2GRAY), cv2.CV_32F)
    net_sau = float(np.var(lap_sau[M])) + 1e-6
    C_sau = None
    Cs = []
    for k in range(n):
        f_u8 = crops[k]
        gM = f_u8[M].astype(np.float32) - truoc_M
        tich = (gM * dM).sum(1)
        ap = tich / dd_max
        al.append(float(np.clip(tich.sum() / dd_tong, -0.5, 1.5)))
        deu.append(float(((ap > 0.2) & (ap < 0.8)).mean()))
        Ck = khac_nen(f_u8) & gan_bang_mau(f_u8) & VC
        Cs.append(Ck)
        lap = cv2.Laplacian(cv2.cvtColor(f_u8, cv2.COLOR_BGR2GRAY), cv2.CV_32F)
        net.append(float(np.var(lap[M])) / net_sau / max(0.05, al[-1]) ** 2)
    C_sau = Cs[k_sau]
    A_sau = max(1, int(C_sau.sum()))
    hop_sau = _hop_mask(C_sau) or [x0, y0, x1, y1]
    ws, hs = max(1.0, hop_sau[2] - hop_sau[0]), max(1.0, hop_sau[3] - hop_sau[1])
    cxs, cys = (hop_sau[0] + hop_sau[2]) / 2, (hop_sau[1] + hop_sau[3]) / 2
    for k in range(n):
        ar.append(float(Cs[k].sum()) / A_sau)
        hop.append(_hop_mask(Cs[k]))
    # đủ: α ≥ 0,9 và giữ tới k_sau ; vắng: trước đó α < 0,08 và gần như chưa có điểm ảnh chữ
    k_full = None
    for k in range(1, k_sau + 1):
        if al[k] >= 0.88 and min(al[k:k_sau + 1]) >= 0.78:
            hb = hop[k]
            if hb is None or (abs(hb[2] - hb[0] - ws) < 0.08 * ws + 2 and abs(hb[3] - hb[1] - hs) < 0.08 * hs + 2):
                k_full = k; break
    if k_full is None:
        k_full = k_sau
    # 1.2.21: MẶT NẠ PHA — ≤ 0,4 s trước lúc đủ, nửa phân giải trong hộp VC: điểm ảnh p nằm trên ĐOẠN nền→màu lớp (p ≈ nền + a·(c − nền),
    # 0,2 ≤ a ≤ 1,15, dư < 30) ⇒ thấy chữ đang mờ/nhỏ/trượt (engine pop/slide kèm opacity 0→1); dải màu cứng chỉ thấy khi gần đục hẳn,
    # làm quỹ đạo tâm/tỉ lệ rỗng và pop/slide bị gọi là fade. Hộp/ar của các khung đó thay bằng bản pha nếu thấy nhiều điểm hơn.
    if HINH_HOC_TRUOC:
        try:
            ys_, xs_ = np.nonzero(VC)
            if len(xs_):
                by0, by1, bx0, bx1 = int(ys_.min()), int(ys_.max()) + 1, int(xs_.min()), int(xs_.max()) + 1
                tr2 = truoc_u8[by0:by1:2, bx0:bx1:2].astype(np.int16)
                vc2 = VC[by0:by1:2, bx0:bx1:2]
                vs_ = [(c.astype(np.int16) - tr2).astype(np.int32) for c in tam_u8]
                vvs_ = [np.maximum((v_ ** 2).sum(2), 1) for v_ in vs_]
                kr0 = max(0, k_full - int(round(0.4 * fps)) - 1)
                for k in range(kr0, k_full + 1):
                    d_ = (crops[k][by0:by1:2, bx0:bx1:2].astype(np.int16) - tr2).astype(np.int32)
                    dd_ = (d_ ** 2).sum(2)
                    m_ = np.zeros(d_.shape[:2], bool)
                    for v_, vv_ in zip(vs_, vvs_):
                        dv_ = (d_ * v_).sum(2)
                        t_ = dv_ / vv_
                        res2 = dd_ - (dv_.astype(np.float64) ** 2) / vv_
                        m_ |= (t_ >= 0.2) & (t_ <= 1.15) & (res2 < 900) & (dd_ > 1600)
                    m_ &= vc2
                    m_ = cv2.morphologyEx(m_.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
                    a_pha = float(m_.sum()) * 4.0 / A_sau
                    if a_pha > ar[k] * 1.15 and a_pha >= 0.06:
                        hb_ = _hop_mask(m_)
                        if hb_:
                            hop[k] = [bx0 + 2 * hb_[0], by0 + 2 * hb_[1], bx0 + 2 * hb_[2], by0 + 2 * hb_[3]]
                            ar[k] = a_pha
        except Exception:
            pass
    # vắng: lùi từ lúc đủ tới khung cuối CHƯA có điểm ảnh lớp phủ, rồi lùi tiếp khi α còn giảm đều (đoạn fade mờ)
    k_on = None
    k1 = k_full
    while k1 > 0 and ((ar[k1 - 1] >= 0.06 and al[k1 - 1] >= 0.04) or ar[k1 - 1] >= 0.5):
        k1 -= 1
    if k1 > 0:
        k = k1 - 1
        while k > 0 and al[k] - al[k - 1] > 0.03 and al[k] > 0.05:
            k -= 1
        if al[k] < 0.35:
            k_on = k
    thay_the = False
    if k_on is None:
        k_min = int(np.argmin(al[:k_full])) if k_full > 0 else 0
        if k_full > 0 and al[k_min] < 0.35:
            k_on, thay_the = k_min, True          # thay chỗ chữ cũ (phụ đề nối tiếp) — đo từ lúc khác nhất
        else:
            return {"kieu": "khong_do_duoc", "ly_do": "đã hiện từ đầu cửa sổ", "alpha": [round(x, 3) for x in al[:k_sau + 1]]}
    T = list(range(k_on + 1, k_full))
    dai = (k_full - k_on) / fps
    ra = {"t_bat_dau": round(ts[k_on] + (0.5 / fps), 3), "t_du": round(ts[k_full], 3), "khung": k_full - k_on}
    if thay_the:
        ra["thay_the"] = True

    # chuỗi số đo (t, x, y, w, h trong toạ độ ROI chuẩn hoá theo hộp đủ; α; phần đã hiện)
    chuoi = []
    for k in range(max(0, k_on - 2), min(n, k_full + 3)):
        hb = hop[k]
        chuoi.append({"t": round(ts[k], 3), "x": None if hb is None else round(((hb[0] + hb[2]) / 2 - cxs) / ws, 3),
                      "y": None if hb is None else round(((hb[1] + hb[3]) / 2 - cys) / hs, 3),
                      "w": None if hb is None else round((hb[2] - hb[0]) / ws, 3), "h": None if hb is None else round((hb[3] - hb[1]) / hs, 3),
                      "alpha": round(al[k], 3), "phan_hien": round(min(ar[k], 2.0), 3), "deu": round(deu[k], 3), "net": round(min(net[k], 3.0), 3)})
    ra["chuoi"] = chuoi
    if not T:
        ra.update(kieu="none", dai=0.0, ease=None)
        return ra
    # OCR các khung chuyển (≤ 8) + khung đủ → số ký tự / từ
    chu_k = {}
    hop_ocr_k = {}
    hinh_hoc_ocr = None
    dac_ocr = {}
    vis0 = [k for k in T if ar[k] > 0.05 and hop[k] is not None]
    nghi_lon = bool(vis0) and (min((hop[k][2] - hop[k][0]) / ws for k in vis0) < 0.8 or min((hop[k][3] - hop[k][1]) / hs for k in vis0) < 0.8)
    if ocr_on and T:
        sk_ = 6 if nghi_lon else 3
        chon = T if len(T) <= sk_ else [T[int(round(i))] for i in np.linspace(0, len(T) - 1, sk_)]
        for k in chon + [k_full]:
            o = ocr_cs(crops[k], ts[k], roi, True) if roi is not None else ocr(crops[k], True)
            o = [x for x in o if _chong_nho([x["hop"][0], x["hop"][1], x["hop"][2], x["hop"][3]], [hop_roi[0], hop_roi[1], hop_roi[2], hop_roi[3]]) > 0.3]
            s = " ".join(x["chu"] for x in sorted(o, key=lambda r: (round(r["hop"][1] / 12), r["hop"][0])))
            chu_k[k] = s
            if o:
                hop_ocr_k[k] = [min(x["hop"][0] for x in o), min(x["hop"][1] for x in o), max(x["hop"][2] for x in o), max(x["hop"][3] for x in o)]
        for c in chuoi:
            k = ts.index(c["t"]) if c["t"] in ts else None
            if k is not None and k in chu_k:
                c["ky_tu"] = len(_khong_dau(chu_k[k])); c["tu"] = _so_tu(chu_k[k])
    # 1.2.21: HÌNH HỌC từ HỘP OCR các khung chuyển — máy dò chữ thấy chữ đang mờ/nhỏ/trượt và không bị nền chuyển động đánh lừa như mặt nạ màu.
    # scale tăng từ < 1 (tâm yên) → pop · dịch có hướng, cỡ đủ → slide · cao đủ, rộng lớn dần → lớn dần (gõ/từng từ/mặt nạ)
    hinh_hoc_ocr = None
    if HINH_HOC_TRUOC and k_full in hop_ocr_k and len(hop_ocr_k) >= 2:
        hf_ = hop_ocr_k[k_full]
        wf_, hf2 = max(1.0, hf_[2] - hf_[0]), max(1.0, hf_[3] - hf_[1]); cxf_, cyf_ = (hf_[0] + hf_[2]) / 2, (hf_[1] + hf_[3]) / 2
        ks_o = sorted(k for k in hop_ocr_k if k < k_full)
        if ks_o:
            wr_o = [(hop_ocr_k[k][2] - hop_ocr_k[k][0]) / wf_ for k in ks_o] + [1.0]
            hr_o = [(hop_ocr_k[k][3] - hop_ocr_k[k][1]) / hf2 for k in ks_o] + [1.0]
            dx_o = [((hop_ocr_k[k][0] + hop_ocr_k[k][2]) / 2 - cxf_) / hf2 for k in ks_o] + [0.0]
            dy_o = [((hop_ocr_k[k][1] + hop_ocr_k[k][3]) / 2 - cyf_) / hf2 for k in ks_o] + [0.0]
            sc_o = [(a_ + b_) / 2 for a_, b_ in zip(wr_o, hr_o)]
            di_o = [math.hypot(a_, b_) for a_, b_ in zip(dx_o, dy_o)]
            n1 = max(1, len(sc_o) - 1)
            tang = sum(1 for a_, b_ in zip(sc_o, sc_o[1:]) if b_ >= a_ - 0.03) >= 0.7 * n1
            cung = all(abs(a_ - b_) < 0.25 * max(a_, b_, 1e-3) for a_, b_ in zip(wr_o, hr_o))
            if cung and max(di_o) < 0.35 and sc_o[0] <= 0.9 and (sc_o[-1] - sc_o[0]) >= 0.07 and tang:
                hinh_hoc_ocr = "pop"
            elif all(0.75 < w_ < 1.3 and 0.75 < h_ < 1.3 for w_, h_ in zip(wr_o, hr_o)) and di_o[0] > 0.3 and di_o[-2] < 0.6 * di_o[0]                     and sum(1 for a_, b_ in zip(di_o, di_o[1:]) if b_ <= a_ + 0.05) >= 0.7 * n1                     and (all(v >= -0.05 for v in dx_o) or all(v <= 0.05 for v in dx_o)) and (all(v >= -0.05 for v in dy_o) or all(v <= 0.05 for v in dy_o)):
                hinh_hoc_ocr = "slide"
            elif all(0.75 < h_ < 1.3 for h_ in hr_o) and wr_o[0] < 0.6 and sum(1 for a_, b_ in zip(wr_o, wr_o[1:]) if b_ >= a_ - 0.03) >= 0.7 * n1:
                hinh_hoc_ocr = "lon_dan"
            dac_ocr.update(ocr_sc0=round(sc_o[0], 2), ocr_dich0=round(di_o[0], 2), ocr_wr0=round(wr_o[0], 2))
            if hinh_hoc_ocr in ("pop", "slide"):            # hộp OCR thay hộp mặt nạ ở các khung chuyển (mặt nạ màu nhiễu khi nền động)
                for k in ks_o + [k_full]:
                    hop[k] = list(hop_ocr_k[k]); ar[k] = max(ar[k], 0.5)
                hop_sau = list(hf_); ws, hs = wf_, hf2; cxs, cys = cxf_, cyf_
    dac_ocr["hinh_hoc_ocr"] = hinh_hoc_ocr
    # ---- đặc trưng
    vis = [k for k in T if ar[k] > 0.1 and hop[k] is not None]
    wr = {k: (hop[k][2] - hop[k][0]) / ws for k in vis}
    hr = {k: (hop[k][3] - hop[k][1]) / hs for k in vis}
    dx = {k: ((hop[k][0] + hop[k][2]) / 2 - cxs) for k in vis}
    dy = {k: ((hop[k][1] + hop[k][3]) / 2 - cys) for k in vis}
    deu_tb = float(np.mean([deu[k] for k in T])) if T else 0.0
    dac = {"deu_tb": round(deu_tb, 3)}
    dac.update(dac_ocr)
    kieu, huong, p, u = None, None, None, None
    # 1.2.21: HÌNH HỌC quyết trước — quỹ đạo tâm + tỉ lệ co giãn trên các khung đã hiện rõ (α ≥ 0,25). Engine pop/slide luôn kèm
    # opacity 0→1 nên "α điểm ảnh đều" không đủ để gọi là fade; OCR đọc thiếu từ lúc chữ đang trượt/mờ không được kéo thành "lớn dần".
    k_ro = list(vis)                                   # khung có ≥ 10 % điểm ảnh lớp (ar) — α chiếu (al) với pop/slide thấp tới gần cuối nên không dùng để lọc
    hinh_hoc = hinh_hoc_ocr
    if HINH_HOC_TRUOC and hinh_hoc is None and len(k_ro) >= 2:
        sc_k = [(wr[k] + hr[k]) / 2 for k in k_ro]
        dich_k = [math.hypot(dx[k], dy[k]) / hs for k in k_ro]
        cung_ti_le = all(abs(wr[k] - hr[k]) < 0.2 * max(wr[k], hr[k]) for k in k_ro)
        co_du = all(0.8 < wr[k] < 1.25 and 0.8 < hr[k] < 1.25 for k in k_ro)
        n1 = max(1, len(sc_k) - 1)
        tang = sum(1 for a_, b_ in zip(sc_k, sc_k[1:]) if b_ >= a_ - 0.03) >= 0.7 * n1
        giam = sum(1 for a_, b_ in zip(sc_k, sc_k[1:]) if b_ <= a_ + 0.03) >= 0.7 * n1
        if cung_ti_le and max(dich_k) < 0.35 and ((sc_k[0] < 0.85 and sc_k[-1] > 0.9 and tang) or (sc_k[0] > 1.12 and sc_k[-1] < 1.08 and giam)):
            hinh_hoc = "pop"                       # scale tăng từ < 1 (hoặc giảm từ > 1) tới đích, tâm đứng yên
        elif co_du and dich_k[0] > 0.3 and dich_k[-1] < 0.5 * dich_k[0] and sum(1 for a_, b_ in zip(dich_k, dich_k[1:]) if b_ <= a_ + 0.05) >= 0.7 * n1:
            hx_ = [dx[k] for k in k_ro]; hy_ = [dy[k] for k in k_ro]
            if (all(v >= -0.05 * hs for v in hx_) or all(v <= 0.05 * hs for v in hx_)) and (all(v >= -0.05 * hs for v in hy_) or all(v <= 0.05 * hs for v in hy_)):
                hinh_hoc = "slide"                 # dịch chuyển có hướng nhất quán, cỡ đã đủ, tiến dần về đích
        if hinh_hoc is None and all(0.8 < hr[k] < 1.3 for k in k_ro) and wr[k_ro[0]] < 0.6 and wr[k_ro[-1]] > 0.85                 and sum(1 for a_, b_ in zip(k_ro, k_ro[1:]) if wr[b_] >= wr[a_] - 0.03) >= 0.7 * n1:
            hinh_hoc = "lon_dan"                   # cao đủ ngay, rộng lớn dần một chiều → gõ chữ / theo từ / mặt nạ
        dac["ti_le_dau_ro"] = round(sc_k[0], 2); dac["dich_dau_theo_cao"] = round(dich_k[0], 2)
    dac["hinh_hoc"] = hinh_hoc
    # fade: α từng điểm ảnh ĐỀU ở mức giữa, hình học gần như không đổi
    if vis:
        lech_hh = max(max(abs(hr[k] - 1), abs(wr[k] - 1)) for k in vis)
        dich_hh = max(math.hypot(dx[k], dy[k]) for k in vis) / hs
    else:
        lech_hh, dich_hh = 0.0, 0.0
    # α điểm ảnh ĐỀU ở mức giữa (mỗi điểm cùng mờ) = fade; pop/slide thì điểm ảnh hoặc trùng hoặc không (α 0/1)
    giua_ = [deu[k] for k in T if 0.25 <= al[k] <= 0.85]
    deu_giua = float(np.mean(giua_)) if giua_ else 0.0
    dac["deu_giua"] = round(deu_giua, 3)
    if hinh_hoc is None and ((deu_giua >= 0.55 and dich_hh < 0.35) or (deu_tb >= 0.4 and lech_hh < 0.2 and dich_hh < 0.3)):
        kieu = "fade"
        u = [0.0] + [(k - k_on) / (k_full - k_on) for k in T] + [1.0]
        p = [0.0] + [al[k] for k in T] + [1.0]
    # số từ OCR tăng dần qua các khung chuyển → họ "lớn dần" (ưu tiên trước slide/pop: dòng mới làm tâm hộp dời)
    tu_seq = [_so_tu(chu_k[k]) for k in sorted(chu_k) if k != k_full]
    tang_tu_som = bool(chu_k) and _so_tu(chu_k.get(k_full, "")) >= 2 and len(set(x for x in tu_seq if x > 0)) >= 2         and (min(x for x in tu_seq if x > 0) < _so_tu(chu_k.get(k_full, "")))
    # hoặc số KÝ TỰ tăng dần mà chữ từng khung là phần đầu chữ đủ (gõ / lộ dần) — trước khi hộp lẫn tay/người làm thành "pop"
    du_k = _khong_dau(chu_k.get(k_full, "")) if chu_k else ""
    tien_k = [_khong_dau(chu_k[k]) for k in sorted(chu_k) if k != k_full and _khong_dau(chu_k[k])] if chu_k else []
    if len(du_k) >= 3 and len(tien_k) >= 2 and len({len(x) for x in tien_k if len(x) < len(du_k)}) >= 2             and sum(1 for x in tien_k if len(x) < len(du_k) and du_k.startswith(x[:max(1, len(x) - 1)])) >= 2:
        tang_tu_som = True
    if kieu is None and (hinh_hoc == "lon_dan" or (tang_tu_som and hinh_hoc is None)):
        kieu = "_lon_dan"
    # slide: dời tâm rõ khi kích thước ~ đủ
    lon = [k for k in vis if 0.82 < wr[k] < 1.22 and 0.82 < hr[k] < 1.22 and ar[k] > 0.45]
    if hinh_hoc == "slide" and not lon:
        lon = list(k_ro)
    dich = [(k, math.hypot(dx[k], dy[k])) for k in lon]
    if kieu is None and dich and (hinh_hoc == "slide" or max(v for _, v in dich) > max(0.3 * hs, 0.02 * max(crops[0].shape[:2]))):
        k0 = max(dich, key=lambda r: r[1])[0]
        kieu = "slide"
        if abs(dx[k0]) > abs(dy[k0]):
            huong = "tu_phai" if dx[k0] > 0 else "tu_trai"
        else:
            huong = "tu_duoi" if dy[k0] > 0 else "tu_tren"
        d0 = max(v for _, v in dich)
        ks = [k for k in lon]
        u = [(k - k_on) / (k_full - k_on) for k in ks]
        p = [1 - math.hypot(dx[k], dy[k]) / d0 for k in ks]
        dac["dich_max_theo_cao"] = round(d0 / hs, 2)
    # pop/scale: cả w và h đổi cùng tỉ lệ, tâm gần đứng yên
    if kieu is None and len(vis) >= 1:
        sc = [k for k in vis if abs(wr[k] - hr[k]) < 0.18 * max(wr[k], hr[k]) and math.hypot(dx[k], dy[k]) < 0.45 * hs + 0.25 * abs(1 - hr[k]) * hs * 4]
        if hinh_hoc == "pop" and len(sc) < 2:
            sc = list(k_ro)
        lech = [abs((hr[k] + wr[k]) / 2 - 1) for k in sc]
        bao_toan = [ar[k] / max(1e-3, ((wr[k] + hr[k]) / 2) ** 2) for k in sc]
        dac["bao_toan_dien_tich"] = round(float(np.median(bao_toan)), 2) if bao_toan else None
        if hinh_hoc != "pop" and sc and max(lech) > 0.08 and len(sc) >= max(1, 0.5 * len(vis)) and float(np.median(bao_toan)) < 0.55 and deu_tb >= 0.15:
            kieu = "fade"                          # hộp co/giãn chỉ vì nét mờ dưới ngưỡng → thực ra là mờ dần
            u = [0.0] + [(k - k_on) / (k_full - k_on) for k in T] + [1.0]
            p = [0.0] + [al[k] for k in T] + [1.0]
        elif sc and (hinh_hoc == "pop" or (max(lech) > 0.08 and len(sc) >= max(1, 0.5 * len(vis)))):
            kieu = "pop"
            s = [(k, (wr[k] + hr[k]) / 2) for k in sc]
            s0 = s[0][1]
            dac["ti_le_dau"] = round(s0, 2)
            if s0 >= 1.04:
                huong = "tu_to"
                u = [(k - k_on) / (k_full - k_on) for k, _ in s]
                p = [(s0 - v) / max(1e-3, s0 - 1) for _, v in s]
                dac["vuot"] = round(max(0.0, 1 - min(v for _, v in s)), 3)
            else:
                huong = "tu_nho"
                u = [0.0] + [(k - k_on) / (k_full - k_on) for k, _ in s]
                p = [0.0] + [v for _, v in s]
                dac["vuot"] = round(max(0.0, max(v for _, v in s) - 1), 3)
            cat_1 = sum(1 for (a1, v1), (a2, v2) in zip(s, s[1:]) if (v1 - 1) * (v2 - 1) < 0)
            dac["so_lan_qua_dich"] = cat_1
    # lớn dần theo 1 chiều (gõ chữ / theo từ / mặt nạ)
    if kieu == "_lon_dan":
        kieu = None
        ep_lon = True
    else:
        ep_lon = False
    if kieu is None and vis:
        mw, mh = min(wr.values()), min(hr.values())
        tw = [abs(hr[k] - 1) for k in vis]
        tu_ocr = [_so_tu(chu_k[k]) for k in sorted(chu_k) if k != k_full]
        tu_du = _so_tu(chu_k.get(k_full, "")) if chu_k else 0
        tang_tu = len(set(x for x in tu_ocr if x > 0)) >= 2 and tu_du >= 2
        ngang = mw < 0.8 and float(np.median(tw)) < 0.2
        doc = mh < 0.8 and float(np.median([abs(wr[k] - 1) for k in vis])) < 0.25
        if ngang or doc or tang_tu or ep_lon:
            if ngang or (tang_tu and not doc):
                l0 = float(np.std([hop[k][0] for k in vis] + [hop_sau[0]])); r0 = float(np.std([hop[k][2] for k in vis] + [hop_sau[2]]))
                huong = "trai_sang_phai" if l0 < r0 * 0.6 else "phai_sang_trai" if r0 < l0 * 0.6 else "giua_ra"
            else:
                t0_ = float(np.std([hop[k][1] for k in vis] + [hop_sau[1]])); b0 = float(np.std([hop[k][3] for k in vis] + [hop_sau[3]]))
                huong = "tren_xuong" if t0_ < b0 * 0.6 else "duoi_len" if b0 < t0_ * 0.6 else "giua_ra"
            u = [0.0] + [(k - k_on) / (k_full - k_on) for k in T]
            p = [0.0] + [min(1.2, ar[k]) for k in T]
            # bậc thang hay trơn (bề rộng phần hiện theo khung)
            mep = [(hop[k][2] - hop[k][0]) if hop[k] is not None else 0.0 for k in [k_on] + T + [k_full]]
            dm = np.diff(np.asarray(mep, float))
            buoc = dm[dm > 0.5]
            dung_yen = float((np.abs(dm) <= 0.5).mean()) if len(dm) else 0.0
            tron = float(np.mean(np.abs(np.diff(dm))) / max(1e-6, np.mean(np.abs(dm)))) if len(dm) > 2 else 0.0
            dac.update(dung_yen=round(dung_yen, 2), do_gap=round(tron, 2), buoc_tb_px=round(float(buoc.mean()), 1) if len(buoc) else 0)
            ky_du = len(_khong_dau(chu_k.get(k_full, ""))) if chu_k else 0
            # tiền tố: chữ từng khung là phần đầu chữ đủ?
            du_s = _khong_dau(chu_k.get(k_full, ""))
            tien = [1.0 if (_khong_dau(chu_k[k]) and du_s.startswith(_khong_dau(chu_k[k])[:max(1, len(_khong_dau(chu_k[k])) - 1)])) else 0.0 for k in chu_k if k != k_full and _khong_dau(chu_k[k])]
            tien_to = float(np.mean(tien)) if tien else 0.0
            dac.update(tien_to=round(tien_to, 2), ky_tu_du=ky_du, tu_du=tu_du)
            giay_moi_tu = dai / max(1, tu_du - 1) if tu_du >= 2 else None
            tk_du = [_khong_dau(w) for w in (chu_k.get(k_full, "") or "").split() if _khong_dau(w)]
            giua_tu = []
            for k in chu_k:
                if k == k_full:
                    continue
                tk = [_khong_dau(w) for w in chu_k[k].split() if _khong_dau(w)]
                if tk and len(tk) <= len(tk_du):
                    giua_tu.append(1.0 if tk[-1] != tk_du[len(tk) - 1] else 0.0)
            ti_giua = float(np.mean(giua_tu)) if giua_tu else 0.0
            dac["cat_giua_tu"] = round(ti_giua, 2)
            if tu_du <= 1 and tien_to >= 0.4 and dung_yen < 0.3:
                kieu = "mask_reveal"          # một từ lộ dần mượt (không khựng theo ký tự) — vd chữ viết tay quét mặt nạ
            elif ti_giua >= 0.4 and tien_to >= 0.4:
                kieu = "typewriter"
                dac["ky_tu_moi_giay"] = round(ky_du / max(dai, 1e-3), 1) if ky_du else None
            elif (tang_tu and giay_moi_tu and giay_moi_tu >= 0.12) or (tu_du >= 2 and dung_yen >= 0.45 and dai >= 0.25 * tu_du):
                kieu = "word_by_word"
                dac["giay_moi_tu"] = round(giay_moi_tu or dai / max(1, tu_du), 3)
            elif (tien_to >= 0.6 and (dung_yen >= 0.25 or tron >= 0.9)) or dung_yen >= 0.4:
                kieu = "typewriter"
                dac["ky_tu_moi_giay"] = round(ky_du / max(dai, 1e-3), 1) if ky_du else None
            else:
                kieu = "mask_reveal"
    # blur / fade
    if kieu is None:
        net_dau = [net[k] for k in T if al[k] > 0.4]
        if net_dau and min(net_dau) < 0.45 and deu_tb < 0.5:
            kieu = "blur"
            u = [(k - k_on) / (k_full - k_on) for k in T]
            p = [min(1.0, net[k]) for k in T]
        elif deu_tb >= 0.3 or len(T) >= 2:
            kieu = "fade"
            u = [0.0] + [(k - k_on) / (k_full - k_on) for k in T] + [1.0]
            p = [0.0] + [al[k] for k in T] + [1.0]
        else:
            kieu = "none"
    # giải mã / đổi ký tự tại chỗ: chữ khung chuyển dài ~ bằng chữ đủ nhưng KHÁC, hộp gần đứng yên
    if chu_k and kieu not in ("typewriter", "word_by_word", "mask_reveal", "slide"):
        du_s = _khong_dau(chu_k.get(k_full, ""))
        khac = [k for k in chu_k if k != k_full and _khong_dau(chu_k[k]) and abs(len(_khong_dau(chu_k[k])) - len(du_s)) <= max(1, 0.35 * len(du_s))
                and _khong_dau(chu_k[k]) != du_s and not du_s.startswith(_khong_dau(chu_k[k])[:max(1, len(_khong_dau(chu_k[k])) - 1)])]
        if du_s and len(du_s) >= 3 and len(khac) >= 2 and lech_hh < 0.25 and deu_giua < 0.5:
            kieu, huong = "doi_ky_tu", None
            u = [(k - k_on) / (k_full - k_on) for k in sorted(chu_k) if k != k_full] + [1.0]
            p = [sum(1 for a_, b_ in zip(_khong_dau(chu_k[k]), du_s) if a_ == b_) / len(du_s) for k in sorted(chu_k) if k != k_full] + [1.0]
            dac["khung_khac_chu"] = len(khac)
    if kieu in ("pop", "slide") and deu_tb >= 0.3:
        dac["kem_fade"] = True
    ra.update(kieu=kieu, huong=huong, dai=round(dai, 3), dac_trung=dac)
    if p is not None and u is not None and len(p) >= 2:
        ke = _khop_ease(u, p)
        ten, rm, gian = ke[0]
        if kieu == "pop" and dac.get("vuot", 0) > 0.03 and ten not in ("back", "spring"):
            ten = "spring" if dac.get("so_lan_qua_dich", 0) >= 2 else "back"
        if kieu in ("typewriter", "word_by_word"):
            ten = "linear" if ten in ("in", "out", "in_out", "expo") and rm > 0.08 else ten
        ra.update(ease=ten, ease_rmse=rm, dai=round(dai * gian, 3), ease_thu=[{"ease": a, "rmse": b} for a, b, _ in ke[:3]],
                  duong=[[round(a, 3), round(b, 3)] for a, b in zip(u, p)])
    else:
        ra.update(ease=None)
    if chu_k:
        ra["ocr_chuyen"] = [{"t": round(ts[k], 3), "ky_tu": len(_khong_dau(chu_k[k])), "tu": _so_tu(chu_k[k])} for k in sorted(chu_k)]
    ra["_k"] = (k_on, k_full, T)
    ra["_hop"] = hop
    ra["_hop_sau"] = hop_sau
    return ra


# ════════════════════════════════════════════════════════════════ 3) thuộc tính tĩnh
def _hinh_dang(m):
    """mặt nạ một vùng (uint8/bool) → {"hinh","bo_px","lap_day","rong","cao"} — bo góc ước r = √((wh − A)/(4 − π))"""
    m = m.astype(np.uint8)
    nc, lab, stt, _ = cv2.connectedComponentsWithStats(m)
    if nc <= 1:
        return None
    c = 1 + int(np.argmax(stt[1:, 4]))
    x, y, w, h, A = [int(v) for v in stt[c]]
    vung = (lab == c).astype(np.uint8)
    cnts, _ = cv2.findContours(vung, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    lap = cv2.drawContours(np.zeros_like(vung), cnts, -1, 1, -1)       # lấp lỗ (chữ trong thẻ)
    A2 = int(lap.sum())
    fill = A2 / float(w * h)
    r = math.sqrt(max(0.0, w * h - A2) / (4 - math.pi))
    rr = r / max(1, min(w, h))
    hinh = None
    if fill < 0.45:
        hinh = "duong" if max(w, h) / max(1, min(w, h)) > 5 else "khung_rong" if A / float(max(A2, 1)) < 0.5 else "tu_do"
    elif abs(w / float(h) - 1) < 0.18 and 0.68 < fill < 0.86:
        hinh = "tron"
    elif rr > 0.36 and max(w, h) / max(1, min(w, h)) > 1.3:
        hinh = "pill"
    elif rr < 0.06:
        hinh = "chu_nhat"
    else:
        hinh = "bo_goc"
    return {"hinh": hinh, "bo": round(r, 1), "bo_ti_le": round(rr, 3), "lap_day": round(fill, 3), "hop": [x, y, x + w, y + h], "vung": lap}


def _thuoc_tinh(truoc, sau, hop_roi, roi, Wd, Hd, mat, nguoi=None, ocr_dong=None):
    """số đo tĩnh của chữ/đồ hoạ lúc ĐỦ (toạ độ ROI → chuẩn hoá khung). nguoi: alpha người (ROI) để loại."""
    x0, y0, x1, y1 = [int(v) for v in hop_roi]
    t16 = truoc.astype(np.int16); s16 = sau.astype(np.int16)
    dn = np.abs(s16 - t16).max(2)
    vung = np.zeros(dn.shape, np.uint8)
    pad = int(0.35 * (y1 - y0)) + 4
    a0, b0, a1, b1 = max(0, x0 - pad), max(0, y0 - pad), min(dn.shape[1], x1 + pad), min(dn.shape[0], y1 + pad)
    vung[b0:b1, a0:a1] = (dn[b0:b1, a0:a1] > 30)
    if nguoi is not None:
        vung[nguoi > 0.5] = 0
    vung = cv2.morphologyEx(vung, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    tho = vung.copy()
    lap_tho = float(tho[y0:y1, x0:x1].mean()) if (y1 > y0 and x1 > x0) else 0.0
    kin = cv2.morphologyEx(vung, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    ra = {}
    hd = _hinh_dang(kin)
    # nền khối: vùng đổi gần như đặc (≥ 0,7) và rộng hơn mực chữ
    co_nen = lap_tho >= 0.62 and hd is not None and hd["lap_day"] > 0.75
    if co_nen:
        vm0 = hd["vung"].astype(bool)
        L = cv2.cvtColor(sau, cv2.COLOR_BGR2LAB)[:, :, 0].astype(float)
        Lv = L[vm0]
        med = float(np.median(Lv))
        nen_px = np.abs(Lv - med) < 25                    # bỏ điểm ảnh mực chữ
        ra["nen_lech_chuan"] = round(float(Lv[nen_px].std()) if nen_px.sum() > 20 else 99.0, 1)
        if ra["nen_lech_chuan"] > 7.5:
            co_nen = False                                # dải bóng/quầng mờ, không phải thẻ đặc
    ra["lap_day_doi"] = round(lap_tho, 3)
    px_nen = None
    if co_nen and hd:
        ra["nen"] = {k: hd[k] for k in ("hinh", "bo", "bo_ti_le", "lap_day")}
        ra["nen"]["bo_px_1080"] = round(hd["bo"] / Wd * 1080, 1)
        vm = hd["vung"].astype(bool)
        ra["_vung_nen"] = vm
        tam, tl = _kmeans(sau[vm], 2)
        px_nen = tam[0]
        ra["_mau_nen_bgr"] = [float(x) for x in tam[0]]
        ra["nen"]["mau"] = _hex(tam[0])
        # nền mờ: điểm ảnh nền tương quan với ảnh trước (nhìn xuyên)
        g_s = cv2.cvtColor(sau, cv2.COLOR_BGR2GRAY)[vm].astype(float); g_t = cv2.cvtColor(truoc, cv2.COLOR_BGR2GRAY)[vm].astype(float)
        if g_s.std() > 3 and g_t.std() > 3:
            ra["nen"]["nen_mo"] = bool(np.corrcoef(g_s, g_t)[0, 1] > 0.55)
        else:
            ra["nen"]["nen_mo"] = False
        # bóng: dải ngay dưới vùng tối hơn ảnh trước
        hx = hd["hop"]; dày = max(3, int(0.12 * (hx[3] - hx[1])))
        duoi = (slice(min(dn.shape[0] - 1, hx[3]), min(dn.shape[0], hx[3] + dày)), slice(hx[0], hx[2]))
        tren = (slice(max(0, hx[1] - dày), hx[1]), slice(hx[0], hx[2]))
        def toi(sl):
            a = cv2.cvtColor(sau[sl], cv2.COLOR_BGR2GRAY).astype(float); b = cv2.cvtColor(truoc[sl], cv2.COLOR_BGR2GRAY).astype(float)
            return float((a - b).mean()) if a.size else 0.0
        ra["nen"]["bong"] = bool(toi(duoi) < -10 and toi(duoi) < toi(tren) - 6)
        # viền: dải trong mép khác màu lõi
        er = cv2.erode(vm.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        mep = vm & ~er
        if mep.sum() > 20 and er.sum() > 20:
            ra["nen"]["co_vien"] = bool(np.abs(np.median(sau[mep], 0) - np.median(sau[er], 0)).max() > 60)
    # mực chữ: trong hộp chữ, khác nền khối (nếu có) hoặc là vùng đổi
    hop_chu = np.zeros(dn.shape, bool); hop_chu[y0:y1, x0:x1] = True
    if ocr_dong:                       # chỉ trong dòng OCR (tránh quầng bóng xa)
        hop_chu = np.zeros(dn.shape, bool)
        for o in ocr_dong:
            hx = o["hop"]
            hop_chu[max(0, int(hx[1])):int(math.ceil(hx[3])), max(0, int(hx[0])):int(math.ceil(hx[2]))] = True
    if px_nen is not None:
        doi = hop_chu & (np.abs(s16 - px_nen.astype(np.int16)).max(2) > 60)
    else:
        doi = hop_chu & (tho > 0)
    muc = doi
    if doi.sum() > 30:
        # mực chữ = cụm màu có MÉP SẮC nhất (bóng/quầng thì mép nhoè) — tách mực khỏi bóng đổ
        tam, tl = _kmeans(sau[doi], 3)
        xam = cv2.cvtColor(sau.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
        grad = np.hypot(cv2.Sobel(xam, cv2.CV_32F, 1, 0, ksize=3), cv2.Sobel(xam, cv2.CV_32F, 0, 1, ksize=3))
        gan = np.argmin(np.stack([np.abs(s16 - c.astype(np.int16).reshape(1, 1, 3)).max(2) for c in tam]), 0)
        tot, chon = -1.0, None
        for j in range(len(tam)):
            mj = doi & (gan == j)
            if mj.sum() < max(20, 0.12 * doi.sum()):
                continue
            bien = mj & ~cv2.erode(mj.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
            sc = float(grad[bien].mean()) if bien.sum() else 0.0
            if sc > tot:
                tot, chon = sc, j
        if chon is not None:
            muc = doi & (gan == chon)
            ra["mau_chu"] = _hex(tam[chon])
            khac = [j for j in range(len(tam)) if j != chon and tl[j] > 0.15 and np.abs(tam[j] - tam[chon]).max() > 70]
            if khac:
                ra["mau_chu_2"] = _hex(tam[khac[0]])
    if muc.sum() > 30:
        # viền chữ: vành ngoài mực khác màu lõi mực
        mu = muc.astype(np.uint8)
        loi = cv2.erode(mu, np.ones((3, 3), np.uint8)).astype(bool)
        vanh = muc & ~loi
        if loi.sum() > 20 and vanh.sum() > 20:
            ra["vien_chu"] = bool(np.abs(np.median(sau[vanh], 0).astype(float) - np.median(sau[loi], 0).astype(float)).max() > 90)
        # bóng chữ: vùng ngay dưới-phải mực tối đi so với trước
        dich = np.zeros_like(muc); s = max(2, int(0.04 * (y1 - y0)) + 1)
        dich[s:, s:] = muc[:-s, :-s]
        bong = dich & ~muc
        if bong.sum() > 20 and px_nen is None:
            a = cv2.cvtColor(sau, cv2.COLOR_BGR2GRAY).astype(float)[bong]; b = cv2.cvtColor(truoc, cv2.COLOR_BGR2GRAY).astype(float)[bong]
            ra["bong_chu"] = bool((a - b).mean() < -12)
        # độ đậm ước: nét = 2 × khoảng cách xa nhất trong mực (trung vị) / cao dòng
        dt = cv2.distanceTransform(mu, cv2.DIST_L2, 3)
        song = (dt > 0.9) & (dt >= cv2.dilate(dt, np.ones((3, 3), np.uint8)) - 1e-3)      # sống nét (cực đại địa phương)
        if song.sum() > 15:
            ra["net_px"] = round(2 * float(np.median(dt[song])), 1)
    # dòng OCR → cỡ, căn lề, HOA/thường
    if ocr_dong:
        cao = []
        for o in ocr_dong:
            hx = [int(o["hop"][0]), int(o["hop"][1]), int(math.ceil(o["hop"][2])), int(math.ceil(o["hop"][3]))]
            sub = muc[hx[1]:hx[3], hx[0]:hx[2]] if muc.sum() else None
            if sub is not None and sub.size and sub.sum() > 10:
                rows = np.nonzero(sub.sum(1) > max(1, 0.03 * sub.shape[1]))[0]
                cao.append(float(rows.max() - rows.min() + 1) if len(rows) else float(hx[3] - hx[1]))
            else:
                cao.append(float(hx[3] - hx[1]) * 0.7)
        cao_tv = float(np.median(cao))
        ra["cao_muc_ti_le"] = round(cao_tv / Hd, 4)
        ra["cao_muc_px_1920"] = round(cao_tv / Hd * 1920, 1)
        chu = " ".join(o["chu"] for o in ocr_dong)
        hoa = _ty_le_hoa(chu)
        ra["hoa"] = None if hoa is None else ("hoa" if hoa > 0.85 else "thuong" if hoa < 0.35 else "hon_hop")
        # cỡ font ước (px @1080×1920): chữ HOA ~0,72 em mực; thường có đầu/đuôi ~0,92 em
        ra["co_uoc_1920"] = round(cao_tv / Hd * 1920 / (0.8 if ra["hoa"] == "hoa" else 0.95), 0)
        if ra.get("net_px"):
            r_ = ra["net_px"] / max(1.0, cao_tv)
            ra["net_ti_le"] = round(r_, 3)
            ra["dam_uoc"] = int(min(900, max(300, round((300 + (r_ - 0.04) / 0.12 * 600) / 100) * 100)))
        ra["so_dong"] = len(ocr_dong)
        if len(ocr_dong) >= 2:
            L = [o["hop"][0] for o in ocr_dong]; R = [o["hop"][2] for o in ocr_dong]; M_ = [(o["hop"][0] + o["hop"][2]) / 2 for o in ocr_dong]
            sd = {"trai": np.std(L), "phai": np.std(R), "giua": np.std(M_)}
            ra["can_le"] = min(sd, key=sd.get)
        ra["chu_ocr"] = chu[:80]
        ra["so_ky_tu"] = len(_khong_dau(chu)); ra["so_tu"] = _so_tu(chu)
    # so với NGƯỜI: khối chồng lên người bao nhiêu, và mực chữ trong phần chồng còn thấy không (thấy = đè TRƯỚC người, mất = nằm SAU người)
    if nguoi is not None:
        try:
            ng = np.asarray(nguoi, np.float32)
            if ng.shape[:2] != sau.shape[:2]:
                ng = cv2.resize(ng, (sau.shape[1], sau.shape[0]), interpolation=cv2.INTER_LINEAR)
            vung = np.zeros(ng.shape[:2], bool); vung[y0:y1, x0:x1] = True
            tren = vung & (ng > 0.5); ngoai = vung & (ng <= 0.5)
            chong = float(tren.sum()) / max(1.0, float(vung.sum()))
            if chong >= 0.04 and ngoai.sum() > 50 and tren.sum() > 50:
                md_tren = float(muc[tren].mean()); md_ngoai = float(muc[ngoai].mean())
                ra["so_voi_nguoi"] = {"chong": round(chong, 3), "lop": "sau" if md_tren < 0.35 * max(md_ngoai, 1e-6) else "truoc",
                                      "muc_tren_nguoi": round(md_tren, 3), "muc_ngoai": round(md_ngoai, 3)}
            else:
                ra["so_voi_nguoi"] = {"chong": round(chong, 3), "lop": "khong_cham"}
        except Exception:
            pass
    # hộp trên khung (chuẩn hoá)
    X0, Y0 = roi[0], roi[1]
    hb = [(X0 + x0) / Wd, (Y0 + y0) / Hd, (X0 + x1) / Wd, (Y0 + y1) / Hd]
    if muc.sum() > 30:
        mh = _hop_mask(muc, 0)
        if mh:
            hb = [(X0 + mh[0]) / Wd, (Y0 + mh[1]) / Hd, (X0 + mh[2]) / Wd, (Y0 + mh[3]) / Hd]
    if ra.get("nen"):
        hx = hd["hop"]
        ra["nen"]["hop"] = [round((X0 + hx[0]) / Wd, 4), round((Y0 + hx[1]) / Hd, 4), round((X0 + hx[2]) / Wd, 4), round((Y0 + hx[3]) / Hd, 4)]
    ra["hop"] = [round(v, 4) for v in hb]
    cx, cy = (hb[0] + hb[2]) / 2, (hb[1] + hb[3]) / 2
    ra["tam"] = [round(cx, 4), round(cy, 4)]
    ra["rong_ti_le"] = round(hb[2] - hb[0], 4)
    if "can_le" not in ra:
        ra["can_le"] = "giua" if abs(cx - 0.5) < 0.07 else ("trai" if cx < 0.5 else "phai")
    ra["anchor"] = ("t" if cy < 0.34 else "m" if cy < 0.66 else "b") + ("l" if ra["can_le"] == "trai" else "r" if ra["can_le"] == "phai" else "c")
    # so với mặt (toạ độ mặt = TÂM)
    if mat:
        tren_dau, cam = mat["y"] - mat["h"] / 2, mat["y"] + mat["h"] / 2
        if hb[3] <= tren_dau + 0.15 * mat["h"]:
            vt = "tren_dau"; kc = (tren_dau - hb[3]) / mat["h"]
        elif hb[1] >= cam - 0.1 * mat["h"]:
            kc = (hb[1] - cam) / mat["h"]
            vt = "duoi_cam" if kc < 1.0 else "ngang_nguc" if kc < 3.5 else "duoi_xa"
        else:
            vt = "ngang_mat"; kc = 0.0
        che = hb[0] < mat["x"] + mat["w"] / 2 and hb[2] > mat["x"] - mat["w"] / 2 and vt == "ngang_mat"
        ra["so_voi_mat"] = {"vi_tri": vt, "khoang_theo_cao_mat": round(kc, 2), "lech_x_theo_rong_mat": round((cx - mat["x"]) / max(mat["w"], 1e-3), 2), "che_mat": bool(che)}
        ra["mat"] = mat
    return ra


# ════════════════════════════════════════════════════════════════ 4) ảnh dải động học
def _ve_dai(hangs, duong, tieu_de):
    from PIL import Image, ImageDraw
    if not hangs:
        return None
    ft = _font_ve(15); ft2 = _font_ve(13)
    cao_o = 150
    rong = 6 * 128 + 170 + 20
    dong_tt = []
    for d0 in tieu_de.split("\n"):
        while len(d0) > 105:
            cat_ = d0.rfind(" ", 0, 105)
            cat_ = cat_ if cat_ > 40 else 105
            dong_tt.append(d0[:cat_]); d0 = "   " + d0[cat_:].lstrip()
        dong_tt.append(d0)
    dau = 14 + 20 * len(dong_tt)
    im = Image.new("RGB", (rong, dau + len(hangs) * (cao_o + 44)), (16, 16, 20))
    d = ImageDraw.Draw(im)
    for j, dt_ in enumerate(dong_tt):
        d.text((8, 6 + 20 * j), dt_, fill=(235, 235, 235) if j == 0 else (120, 220, 255), font=ft)
    for i, h in enumerate(hangs):
        y = dau + i * (cao_o + 44)
        d.text((8, y), h["nhan"], fill=(255, 210, 0), font=ft)
        x = 8
        for j, (anh, nhan) in enumerate(h["khung"]):
            if anh is None:
                continue
            a = Image.fromarray(cv2.cvtColor(anh, cv2.COLOR_BGR2RGB))
            s = min(124 / a.width, cao_o / a.height)
            a = a.resize((max(1, int(a.width * s)), max(1, int(a.height * s))))
            im.paste(a, (x, y + 20))
            d.text((x + 2, y + 22 + a.height - 16), nhan, fill=(120, 255, 160), font=ft2)
            x += 128
        # đường cong đo được + ease khớp
        if h.get("duong"):
            ox, oy, cw, ch = 6 * 128 + 14, y + 20, 160, cao_o - 6
            d.rectangle((ox, oy, ox + cw, oy + ch), outline=(80, 80, 90))
            pts = h["duong"]
            ymax = max(1.2, max(p for _, p in pts) + 0.05)
            def P(u, p):
                return ox + u * cw, oy + ch - (p / ymax) * ch
            d.line([P(0, 1), P(1, 1)], fill=(60, 60, 70))
            if h.get("ease"):
                try:
                    from dung import anim
                    q = [P(k / 40, anim.ease(h["ease"], k / 40 / h.get("gian", 1.0))) for k in range(41)]
                    d.line(q, fill=(255, 120, 60), width=2)
                except Exception:
                    pass
            for u, p in pts:
                cx, cy = P(min(1, u), p)
                d.ellipse((cx - 2.5, cy - 2.5, cx + 2.5, cy + 2.5), fill=(120, 220, 255))
            d.text((ox + 4, oy + 2), (h.get("ease") or "") + " (cam=khớp)", fill=(255, 150, 90), font=ft2)
    im.save(duong, quality=88)
    return duong


def _khung_ve(crop, hop_c, hop_du):
    a = crop.copy()
    if hop_du:
        cv2.rectangle(a, (int(hop_du[0]), int(hop_du[1])), (int(hop_du[2]), int(hop_du[3])), (0, 200, 255), 1)
    if hop_c:
        cv2.rectangle(a, (int(hop_c[0]), int(hop_c[1])), (int(hop_c[2]), int(hop_c[3])), (60, 255, 60), 2)
    return a


def _hang_dai(nhan, ts, crops, do, nguoc=False):
    """6 khung: vắng → (4 khung chuyển) → đủ, có hộp đo (xanh lá) và hộp đủ (cam)"""
    if not do or "_k" not in do:
        return None
    k_on, k_full, T = do["_k"]
    if nguoc:
        ts = ts[::-1]; crops = crops[::-1]
    chon = [k_on] + ([T[int(round(i))] for i in np.linspace(0, len(T) - 1, min(4, len(T)))] if T else []) + [k_full]
    khung = []
    hops = do.get("_hop") or []
    for k in chon:
        hb = hops[k] if k < len(hops) else None
        khung.append((_khung_ve(crops[k], hb, do.get("_hop_sau")), f"{ts[k]:.2f}s"))
    return {"nhan": nhan, "khung": khung, "duong": do.get("duong"), "ease": do.get("ease"), "gian": 1.0}


# ════════════════════════════════════════════════════════════════ 5) tổng hợp + spec máy
def _tom_tat(su_kien, vet, cat, zoom, dur, cat_kieu):
    chu = [s for s in su_kien if s["vai"] in ("tieu_de", "nhan")]
    phu = [s for s in su_kien if s["vai"] == "phu_de"]
    dh = [s for s in su_kien if s["vai"] == "do_hoa"]

    def phan_bo(ds, khoa):
        dem = {}
        for s in ds:
            k = (s.get(khoa) or {}).get("kieu")
            if not k or k == "khong_do_duoc":
                continue
            r = dem.setdefault(k, {"so": 0, "dai": [], "ease": {}, "huong": {}})
            r["so"] += 1
            r["dai"].append((s[khoa] or {}).get("dai") or 0)
            e = (s[khoa] or {}).get("ease")
            if e:
                r["ease"][e] = r["ease"].get(e, 0) + 1
            hg = (s[khoa] or {}).get("huong")
            if hg:
                r["huong"][hg] = r["huong"].get(hg, 0) + 1
        tong = sum(r["so"] for r in dem.values()) or 1
        return sorted([{"kieu": k, "so": r["so"], "tan_suat": round(r["so"] / tong, 2), "dai_tv": round(float(np.median(r["dai"])), 3),
                        "ease": max(r["ease"], key=r["ease"].get) if r["ease"] else None,
                        "huong": max(r["huong"], key=r["huong"].get) if r["huong"] else None} for k, r in dem.items()], key=lambda r: -r["so"])

    tt = {"vao_chu": phan_bo(chu, "vao"), "ra_chu": phan_bo(chu, "ra"), "vao_phu_de": phan_bo(phu, "vao"), "ra_phu_de": phan_bo(phu, "ra"),
          "vao_do_hoa": phan_bo(dh, "vao")}
    # nhịp lớp chữ phủ (từ vệt thô — đủ mọi vệt, không chỉ vệt đã đo dày)
    vchu = sorted([v for v in vet if v.get("vai") == "chu"], key=lambda v: v["t_dau"])
    if vchu:
        dais = [v["t_ra"] - v["t_dau"] for v in vchu]
        tt["chu_giay_tv"] = round(float(np.median(dais)), 2)
        dong = 0
        for v in vchu:
            dong = max(dong, sum(1 for w in vchu if w["t_dau"] < v["t_ra"] - 0.05 and w["t_ra"] > v["t_dau"] + 0.05))
        tt["chu_dong_thoi_max"] = dong
        moc = [0.0] + sum([[v["t_dau"], v["t_ra"]] for v in vchu], []) + [dur]
        khe = [vchu[0]["t_dau"]] + [max(0.0, vchu[i + 1]["t_dau"] - max(w["t_ra"] for w in vchu[:i + 1])) for i in range(len(vchu) - 1)]
        tt["khoang_trong_max"] = round(max(khe + [dur - max(v["t_ra"] for v in vchu)]), 2)
        tt["chu_dau_tien_giay"] = round(vchu[0]["t_dau"], 2)
        tt["so_lop_chu"] = len(vchu)
    vp = [v for v in vet if v.get("vai") == "phu_de"]
    tt["co_phu_de"] = bool(vp)
    if vp:
        tt["phu_de_y_tv"] = round(float(np.median([v["cy"] for v in vp])), 3)
        tt["phu_de_cum_giay_tv"] = round(float(np.median([v["t_ra"] - v["t_dau"] for v in vp])), 2)
    tt["so_cat"] = len(cat); tt["canh_tb_giay"] = round(dur / (len(cat) + 1), 2); tt["zoom_cat"] = len(zoom)
    tt["chuyen_canh"] = cat_kieu
    return tt


def _ve_vai(s):
    return {"tieu_de": "tieu_de", "nhan": "nhan", "phu_de": "phu_de", "do_hoa": "the"}.get(s["vai"], "khac")


def spec_may(dh):
    """dong_hoc.json (dict) → Style Spec dựng THUẦN từ số đo, đúng schema (AI xác nhận/sửa; so_spec dùng để so)."""
    sk = dh.get("su_kien") or []
    tt = dh.get("tong_hop") or {}
    chu = [s for s in sk if s["vai"] in ("tieu_de", "nhan")]
    phu = [s for s in sk if s["vai"] == "phu_de"]
    dh_ = [s for s in sk if s["vai"] == "do_hoa"]
    # ---- palette: màu chữ/nền đo được
    mau = []
    for s in chu + phu + dh_:
        tc = s.get("tinh") or {}
        w = 3 if s["vai"] != "phu_de" else 1
        for k in ("mau_chu", "mau_chu_2"):
            if tc.get(k):
                mau.append((tc[k], w))
        if (tc.get("nen") or {}).get("mau"):
            mau.append((tc["nen"]["mau"], w))
    def hb(h):
        h = h.lstrip("#"); return [int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)]
    pal = {}
    if mau:
        bh = sorted(mau, key=lambda m: -_bao_hoa(hb(m[0]))[0] * m[1])
        sang = sorted(mau, key=lambda m: -(_lab(hb(m[0]))[0] + 3 * m[1]))
        toi = sorted(mau, key=lambda m: _lab(hb(m[0]))[0] - 3 * m[1])
        pal["nhan"] = bh[0][0] if _bao_hoa(hb(bh[0][0]))[0] > 0.25 else sang[0][0]
        pal["sang"] = sang[0][0]
        pal["toi"] = toi[0][0] if _lab(hb(toi[0][0]))[0] < 40 else "#111111"
        n2 = [m for m, _ in bh[1:] if _bao_hoa(hb(m))[0] > 0.25 and delta_e(m, pal["nhan"]) > 25]
        if n2:
            pal["nhan2"] = n2[0]
    else:
        pal = {"nhan": "#FFFFFF", "sang": "#FFFFFF", "toi": "#111111"}

    # ---- type scale
    def co(ds):
        cs = [(s.get("tinh") or {}).get("co_uoc_1920") for s in ds]
        cs = [c for c in cs if c]
        if not cs:
            return None
        hoa = [(s.get("tinh") or {}).get("hoa") for s in ds]
        dam = [(s.get("tinh") or {}).get("dam_uoc") for s in ds if (s.get("tinh") or {}).get("dam_uoc")]
        r = {"co": round(float(np.median(cs)) * 1080 / 1080, 0)}
        if dam:
            r["dam"] = int(np.median(dam) // 100 * 100)
        hh = [h for h in hoa if h]
        if hh:
            r["hoa"] = sum(1 for h in hh if h == "hoa") / len(hh) > 0.5
        # màu/viền/bóng/nền theo vai (đo được) — ap_spec áp lại đúng từng vai, không suy từ palette chung
        from collections import Counter as _Ct
        def _sat(h):
            try:
                h = h.lstrip("#"); rr_, gg_, bb_ = (int(h[i:i + 2], 16) for i in (0, 2, 4))
                mx, mn = max(rr_, gg_, bb_), min(rr_, gg_, bb_)
                return (mx - mn) / mx if mx else 0.0, mx
            except Exception:
                return 0.0, 0
        ms = []
        for s_ in ds:
            tc_ = s_.get("tinh") or {}
            ung = [m_ for m_ in (tc_.get("mau_chu"), tc_.get("mau_chu_2")) if m_]
            if ung:                                   # màu chữ thật thường là màu bão hoà hơn / sáng hơn; màu còn lại hay là viền/bóng
                ms.append(max(ung, key=lambda m_: (_sat(m_)[0] > 0.25, _sat(m_)[1])))
        if ms:
            # gom màu gần nhau (lượng tử 24) rồi lấy nhóm phổ biến nhất
            def _q(h):
                h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) // 24 for i in (0, 2, 4))
            nhom_ = _Ct(_q(m_) for m_ in ms).most_common(1)[0][0]
            r["mau"] = next(m_ for m_ in ms if _q(m_) == nhom_)
        for k_, kk in (("vien_chu", "vien"), ("bong_chu", "bong")):
            v = [(s.get("tinh") or {}).get(k_) for s in ds if (s.get("tinh") or {}).get(k_) is not None]
            if v:
                r[kk] = sum(1 for x in v if x) > len(v) / 2
        nm = [((s.get("tinh") or {}).get("nen") or {}).get("mau") for s in ds if ((s.get("tinh") or {}).get("nen") or {}).get("mau")]
        if nm and len(nm) > len(ds) / 2:
            r["nen_mau"] = _Ct(nm).most_common(1)[0][0]
        return r
    ts_ = {}
    for vai, ds in (("tieu_de", [s for s in chu if s["vai"] == "tieu_de"]), ("nhan", [s for s in chu if s["vai"] == "nhan"]), ("phu_de", phu)):
        c = co(ds)
        if c:
            c["co"] = max(10, c["co"])
            ts_[vai] = c
    # ---- layout anchors
    anchors = []
    tong_chu = max(1, len(chu))
    nhom = {}
    for s in chu + phu + dh_:
        tc = s.get("tinh") or {}
        if not tc.get("tam"):
            continue
        sv = (tc.get("so_voi_mat") or {}).get("vi_tri")
        so_voi = {"tren_dau": "tren_dau", "duoi_cam": "duoi_cam", "ngang_nguc": "duoi_cam", "ngang_mat": "mat"}.get(sv, "khung")
        key = (_ve_vai(s), tc.get("anchor"), so_voi)
        nhom.setdefault(key, []).append(tc)
    for (vai, anc, so_voi), ds in sorted(nhom.items(), key=lambda r: -len(r[1])):
        a = {"vai": vai, "anchor": anc or "mc", "x": round(float(np.median([d["tam"][0] for d in ds])), 3), "y": round(float(np.median([d["tam"][1] for d in ds])), 3),
             "so_voi": so_voi, "tan_suat": round(len(ds) / max(1, len([s for s in chu + phu + dh_ if _ve_vai(s) == vai])), 2)}
        kc = [(d.get("so_voi_mat") or {}).get("khoang_theo_cao_mat") for d in ds if d.get("so_voi_mat")]
        if kc:
            a["khoang_theo_cao_mat"] = round(float(np.median(kc)), 2)
        anchors.append(a)
    rong = [(s.get("tinh") or {}).get("rong_ti_le") for s in chu if (s.get("tinh") or {}).get("rong_ti_le")]
    layout = {"anchors": anchors[:8]}
    if rong:
        layout["rong_max_chu"] = round(min(1.0, max(0.2, max(rong))), 2)

    # ---- motion vocab
    def ds_dong(pb):
        ra = []
        for r in pb[:5]:
            k = r["kieu"]
            m = {"pop": "pop", "slide": "slide", "fade": "fade", "blur": "blur", "typewriter": "typewriter", "word_by_word": "pop",
                 "mask_reveal": "wipe", "none": "none", "doi_ky_tu": "typewriter"}.get(k, "fade")
            x = {"kieu": m, "dai": round(min(2.0, max(0.0, r["dai_tv"] or 0)), 2), "tan_suat": r["tan_suat"], "do_may": k}
            if r.get("ease"):
                x["ease"] = r["ease"]
            if r.get("huong"):
                x["huong"] = r["huong"]
            if k == "word_by_word":
                x["tach"] = "tu"
            ra.append(x)
        return ra
    vao, rr = ds_dong(tt.get("vao_chu") or []), ds_dong(tt.get("ra_chu") or [])
    mv = {"vao": vao, "ra": rr}
    kieu_vao = [r["kieu"] for r in (tt.get("vao_chu") or [])]
    mv["tach"] = "tu" if kieu_vao and kieu_vao[0] == "word_by_word" else "ky_tu" if kieu_vao and kieu_vao[0] == "typewriter" else "none"
    dts = [r["dai_tv"] for r in (tt.get("vao_chu") or []) if r["kieu"] not in ("none",)]
    if dts:
        m = float(np.median(dts))
        mv["nhip_dong"] = "rat_nhanh" if m < 0.2 else "nhanh" if m < 0.35 else "vua" if m < 0.6 else "cham"

    # ---- graphics vocab
    gv = {}
    nens = [(s.get("tinh") or {}).get("nen") for s in chu + dh_ if (s.get("tinh") or {}).get("nen")]
    if nens:
        hinh = [n["hinh"] for n in nens if n.get("hinh") in ("pill", "chu_nhat", "bo_goc", "tron")]
        h0 = max(set(hinh), key=hinh.count) if hinh else "rect"
        gv["the"] = {"hinh": {"pill": "pill", "tron": "circle"}.get(h0, "rect"), "bo": round(float(np.median([n.get("bo_px_1080", 0) for n in nens])), 1),
                     "nen_mo": sum(1 for n in nens if n.get("nen_mo")) > len(nens) / 2, "co_vien": bool(sum(1 for n in nens if n.get("co_vien")) > len(nens) / 2)}
    tcs = [s.get("tinh") or {} for s in chu]
    if tcs:
        def da_so(k):
            v = [t.get(k) for t in tcs if t.get(k) is not None]
            return (sum(1 for x in v if x) > len(v) / 2) if v else False
        gv["chu"] = {"vien": da_so("vien_chu"), "bong": da_so("bong_chu"), "nen_khoi": sum(1 for t in tcs if t.get("nen")) > len(tcs) / 2,
                     "hoa": sum(1 for t in tcs if t.get("hoa") == "hoa") > len(tcs) / 2}
    gv["hinh_minh_hoa"] = "khong" if not dh_ else "it" if len(dh_) <= 3 else "nhieu"

    # ---- rhythm
    rh = {}
    if tt.get("chu_giay_tv"):
        rh["giay_moi_lop_chu"] = max(0.3, tt["chu_giay_tv"])
    if tt.get("chu_dong_thoi_max"):
        rh["so_lop_dong_thoi_toi_da"] = max(1, int(tt["chu_dong_thoi_max"]))
    if tt.get("khoang_trong_max") is not None:
        rh["khoang_trong_toi_da_giay"] = max(0.0, tt["khoang_trong_max"])
    if tt.get("co_phu_de"):
        vp = tt.get("vao_phu_de") or []
        rh["phu_de"] = "tu" if vp and vp[0]["kieu"] == "word_by_word" else "cum"
        # karaoke (2 màu chữ trong cụm) / hiện dần (word_by_word) / cả cụm không tô
        hai_mau = sum(1 for s_ in phu if (s_.get("tinh") or {}).get("mau_chu_2"))
        rh["karaoke"] = hai_mau > len(phu) / 2 if phu else False
        rh["phu_de_hien"] = "dan" if rh["phu_de"] == "tu" else ("noi" if rh["karaoke"] else "cum")
        st = [(s.get("tinh") or {}).get("so_ky_tu") for s in phu if (s.get("tinh") or {}).get("so_ky_tu")]
        if st:
            rh["phu_de_toi_da_chu"] = max(8, int(max(st)))          # KÝ TỰ mỗi cụm (ap_spec → phu_de.toi_da_chu, engine gom theo ký tự)
    else:
        rh["phu_de"] = "tat"
    if tt.get("chu_dau_tien_giay") is not None:
        rh["hook_giay"] = tt["chu_dau_tien_giay"]
    ck = tt.get("chuyen_canh") or {}
    cc = [k for k in ("flash", "zoom", "cut") if ck.get(k)]
    rh["chuyen_canh"] = cc or ["cut"]
    dau = sorted({(s.get("tinh") or {}).get("chu_ocr", "") for s in chu if (s.get("tinh") or {}).get("chu_ocr")})
    spec = {"phien_ban": 1, "nguon": os.path.basename(dh.get("video", "")), "palette": pal, "type_scale": ts_, "layout": layout,
            "motion_vocab": mv, "graphics_vocab": gv, "rhythm_rules": rh,
            "dau_an_khong_chep": ["câu chữ trong video mẫu: " + "; ".join(d for d in dau[:12] if d)] if dau else [],
            "ghi_chu": "spec MÁY dựng thuần từ số đo dong_hoc (không phải gu) — AI xác nhận bằng mắt rồi sửa."}
    return spec


# ════════════════════════════════════════════════════════════════ 6) chuyển cảnh
def _kieu_cat(video, info, t):
    """cắt cứng / flash (chớp sáng) / nhoè (mờ chuyển động) / hoà tan — đo ±0,4 s ở 30 khung/s, cạnh 180"""
    sang, net, khac = [], [], []
    truoc = None
    for _, f in _doc(video, info, t - 0.4, t + 0.4, 30, 180):
        g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
        sang.append(float(g.mean())); net.append(float(cv2.Laplacian(g, cv2.CV_32F).var()))
        khac.append(float(np.abs(g.astype(np.int16) - truoc).mean()) if truoc is not None else 0.0)
        truoc = g.astype(np.int16)
    if len(sang) < 6:
        return "cut"
    sang, net, khac = np.array(sang), np.array(net), np.array(khac)
    nen = np.median(sang)
    if sang.max() - nen > 45:
        return "flash"
    if net.min() < 0.35 * np.median(net):
        return "nhoe"
    lon = (khac > 0.5 * khac.max()).sum()
    return "hoa_tan" if lon >= 4 else "cut"


# ════════════════════════════════════════════════════════════════ chính
def phan_tich(video, thu_muc, log=print, fps_day=30, canh_day=600, toi_da_chu=24, toi_da_phu_de=4, toi_da_do_hoa=6, do_hoa=True,
              ve_anh=True, toi_da_cat=6, tach_nguoi=True, ten_anh="dai-dong-hoc", dong_dau_anh=None):
    """video mẫu → <thu_muc>/dong_hoc.json (+ dai-dong-hoc-N.jpg). Trả dict (có "duong", "anh")."""
    t_bat_dau = time.time()
    os.makedirs(thu_muc, exist_ok=True)
    info = C.ffprobe(video) or {}
    dur = float(info.get("dur") or 0)
    if dur <= 0 or not info.get("w"):
        raise RuntimeError("không đọc được video")
    p_tho = os.path.join(thu_muc, "_quet-tho.json")
    khoa = C.bam({"v": C.bam(video), "pb": PHIEN_BAN, "dh": bool(do_hoa)})
    tho = C.doc_json(p_tho) or {}
    if tho.get("khoa") == khoa:
        vet, cat, g_dh, zoom = tho["vet"], [tuple(x) for x in tho["cat"]], tho["g_dh"], [tuple(x) for x in tho["zoom"]]
        log("  quét thô: dùng lại kết quả đã lưu")
    else:
        nho, ts, hists, vet = _quet_tho(video, info, log=log)
        cat = _cat_canh(hists, ts)
        g_dh, zoom = (_do_hoa_tho(nho, ts, cat, vet, dur) if do_hoa else ([], []))
        del nho
        C.ghi_json(p_tho, {"khoa": khoa, "vet": vet, "cat": cat, "g_dh": g_dh, "zoom": zoom})
    vet = _phan_vai(vet, dur)
    t_tho = time.time() - t_bat_dau
    # ---- chọn sự kiện đo dày
    chu_all = sorted([v for v in vet if v["vai"] == "chu"], key=lambda v: v["t_dau"])
    cum = []
    for v in chu_all:
        if cum and v["t_dau"] - cum[-1][0]["t_dau"] <= 0.6:
            cum[-1].append(v)
        else:
            cum.append([v])
    chu = []
    for c in cum:                                  # mỗi cụm cùng lúc: to nhất + (nếu có) một dòng phụ khác cỡ
        c = sorted(c, key=lambda v: -v["cao_dong"])
        chu.append(c[0])
        if len(c) > 1 and c[1]["cao_dong"] < 0.7 * c[0]["cao_dong"]:
            chu.append(c[1])
    chu.sort(key=lambda v: v["t_dau"])
    if len(chu) > toi_da_chu:                      # rải đều theo thời gian
        idx = np.linspace(0, len(chu) - 1, toi_da_chu).round().astype(int)
        chu = [chu[i] for i in sorted(set(idx))]
    cao_tv = float(np.median([v["cao_dong"] for v in chu])) if chu else 0
    for v in chu:
        v["vai_chi_tiet"] = "tieu_de" if v["cao_dong"] >= max(0.035, 1.3 * cao_tv) else "nhan"
    phu = sorted([v for v in vet if v["vai"] == "phu_de" and v["dai"] >= 0.6], key=lambda v: v["t_dau"])
    if len(phu) > toi_da_phu_de:
        idx = np.linspace(0, len(phu) - 1, toi_da_phu_de + 2)[1:-1].round().astype(int)
        phu = [phu[i] for i in sorted(set(idx))]
    dh_vao = [g for g in g_dh if g.get("xuat_hien")][:toi_da_do_hoa]
    dat_video(video)
    nguon_alpha = proxy_cua(thu_muc, video)
    # ---- 1.2.21: kế hoạch MỌI cửa sổ (vào + ra) trước, rồi MỘT lượt giải mã; mỗi cửa sổ xử lý ngay khi đủ khung (bộ nhớ chỉ giữ cửa sổ đang mở)
    muc = [(x, x["vai_chi_tiet"]) for x in chu] + [(x, "phu_de") for x in phu] + [(g, "do_hoa") for g in dh_vao]
    ke, trang = [], []
    for so, (it, vai) in enumerate(muc):
        sk = {"id": f"e{so + 1:02d}", "vai": vai}
        if vai == "do_hoa":
            hop = it["hop"]
            t_co = it["t"] + 0.5
            a, b = it["t"] - 1.0, it["t"] + 1.0
            sk.update(t_vao=round(it["t"], 2), hop_tho=[round(x, 3) for x in hop], co_chu=it.get("co_chu", False))
        else:
            hop = it["hop"]
            sk.update(t_vao=round(it["t_dau"], 2), t_ra=round(it["t_ra"], 2), hop_tho=[round(x, 3) for x in hop], so_dong_tho=it["so_dong"])
            lon_dan = (it["hop_dau"][2] - it["hop_dau"][0]) < 0.8 * (it["hop"][2] - it["hop"][0]) or (it["hop_dau"][3] - it["hop_dau"][1]) < 0.75 * (it["hop"][3] - it["hop"][1])
            a = it["t_dau"] - 1.0
            b = (min(it["t_cuoi"] + 0.15, it["t_dau"] + 3.5) if lon_dan else min(it["t_dau"] + 1.0, it["t_cuoi"] + 0.1))
            b = max(b, it["t_dau"] + 0.3)
            t_co = b - 0.02 if lon_dan else min(it["t_dau"] + 0.8, it["t_cuoi"])
            sk["lon_dan_tho"] = bool(lon_dan)
            if it.get("nghi_ngo"):
                sk["nghi_ngo"] = it["nghi_ngo"]
        ke.append({"id": (so, "vao"), "a": a, "b": b, "hop": hop})
        if vai != "do_hoa" and it["t_ra"] < dur - 0.15 and (vai != "phu_de" or so % 2 == 0):
            a2 = max(it["t_dau"] + 0.1, it["t_cuoi"] - 0.8); b2 = min(dur, it["t_ra"] + 0.4)
            ke.append({"id": (so, "ra"), "a": a2, "b": b2, "hop": hop})
        trang.append({"sk": sk, "it": it, "vai": vai, "t_co": t_co, "a": a, "b": b, "ctx": None, "hang": None, "t0": None})
    su_kien, hangs = [], []
    khoa_hang = __import__("threading").Lock()

    def _xu_ly(wid, ts_, crops, nho_, roi, WH):
        Wd, Hd = WH
        so, pha = wid
        st = trang[so]; sk = st["sk"]; it = st["it"]; vai = st["vai"]
        try:
            if pha == "ra":
                if sk.get("bo_qua") or sk.get("loi") or not st["ctx"]:
                    return
                hr, roi0, o_du, nguoi, khac = st["ctx"]
                if len(crops) >= 4 and roi == roi0:
                    a2 = ts_[0]
                    k2 = int(np.argmin([abs(t - it["t_cuoi"] + 0.05) for t in ts_])) if it["t_cuoi"] > a2 else 0
                    do_ra = _do_chuyen_dong(ts_, crops, k2, hr, fps_day, ocr_on=False, nguoc=True, dong_sau=o_du or None, nguoi=nguoi, hop_khac=khac, roi=roi)
                    sk["ra"] = {k: v for k, v in do_ra.items() if not k.startswith("_")}
                    if sk["ra"].get("t_bat_dau") is not None:
                        sk["ra"]["t_het"] = sk["ra"].pop("t_bat_dau"); sk["ra"]["t_bat_dau"] = sk["ra"].pop("t_du")
                    sk["nhan"] += f" · RA {sk['ra'].get('kieu')} {sk['ra'].get('dai', '')}s"
                    if st["hang"]:
                        st["hang"]["nhan"] = sk["nhan"]
                    sk["giay_do"] = round(sk.get("giay_do", 0) + time.time() - st["t0"], 1)
                    log(f"    {sk['id']} RA {sk['ra'].get('kieu')} {sk['ra'].get('dai', '')}s")
                return
            st["t0"] = time.time()
            t0 = st["t0"]; t_co = st["t_co"]; hop = it["hop"]; a, b = st["a"], st["b"]
            if len(crops) < 4:
                raise RuntimeError("cửa sổ rỗng")
            k_sau = int(np.argmin([abs(t - t_co) for t in ts_]))
            # hộp ROI của mục (toạ độ crop)
            hr = [hop[0] * Wd - roi[0], hop[1] * Hd - roi[1], hop[2] * Wd - roi[0], hop[3] * Hd - roi[1]]
            pad = 0.15 * (hr[3] - hr[1])
            hr = [max(0, hr[0] - pad), max(0, hr[1] - pad), min(crops[0].shape[1], hr[2] + pad), min(crops[0].shape[0], hr[3] + pad)]
            khac = []
            for v2 in vet:
                if v2 is it or v2["t_ra"] < a or v2["t_dau"] > b or _iou(v2["hop"], hop) > 0.5:
                    continue
                hx = [v2["hop"][0] * Wd - roi[0], v2["hop"][1] * Hd - roi[1], v2["hop"][2] * Wd - roi[0], v2["hop"][3] * Hd - roi[1]]
                if hx[2] > 0 and hx[3] > 0 and hx[0] < crops[0].shape[1] and hx[1] < crops[0].shape[0]:
                    khac.append(hx)
            o_du = ocr_cs(crops[k_sau], ts_[k_sau], roi, True)
            o_du = [o for o in o_du if _chong_nho(o["hop"], hr) > 0.4 and (o["hop"][3] - o["hop"][1]) > 0.012 * Hd and o["diem"] >= 0.6]

            if vai != "do_hoa" and not o_du:
                sk["bo_qua"] = "không đọc được chữ lúc đủ (chữ trong cảnh/màn hình?)"
                sk["giay_do"] = round(time.time() - t0, 1)
                log(f"  {sk['id']} {vai} {sk['t_vao']}s · bỏ: {sk['bo_qua']}")
                return
            nguoi = None
            if tach_nguoi:
                try:                             # 1.2.21: mặt nạ người từ lưới MODNet dùng chung (một lần mỗi ô lưới), cắt theo roi
                    al = nguoi_tai(video, info, ts_[k_sau], Wd, Hd, nguon=nguon_alpha, log=log)
                    if vai == "do_hoa":
                        al = np.maximum(al, nguoi_tai(video, info, ts_[0], Wd, Hd, nguon=nguon_alpha))
                    nguoi = al[roi[1]:roi[3], roi[0]:roi[2]]
                except Exception as ex:
                    sk["canh_bao"] = f"không tách người: {str(ex)[:80]}"
            do_vao = _do_chuyen_dong(ts_, crops, k_sau, hr, fps_day, ocr_on=(vai != "do_hoa"), dong_sau=o_du or None, nguoi=nguoi, hop_khac=khac, roi=roi)
            mat = _mat(nho_[k_sau])
            tinh = _thuoc_tinh(crops[0], crops[k_sau], hr, roi, Wd, Hd, mat, nguoi=nguoi, ocr_dong=o_du or None)
            if vai == "do_hoa":
                tinh["co_chu"] = bool(o_du)
                if not tinh.get("nen"):
                    hd = _hinh_dang(cv2.morphologyEx(((np.abs(crops[k_sau].astype(np.int16) - crops[0].astype(np.int16)).max(2) > 30) & (nguoi is None or True)).astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)))
                    if hd:
                        tinh["hinh"] = {k: hd[k] for k in ("hinh", "bo", "bo_ti_le", "lap_day")}
                        tinh["hinh"]["bo_px_1080"] = round(hd["bo"] / Wd * 1080, 1)
                        tinh["hinh"]["loai"] = "icon" if (hd["hop"][2] - hd["hop"][0]) * (hd["hop"][3] - hd["hop"][1]) / float(Wd * Hd) < 0.015 and not o_du else "the" if o_du else "hinh"
            vung_nen = tinh.pop("_vung_nen", None); mau_nen = tinh.pop("_mau_nen_bgr", None)
            if vung_nen is not None and mau_nen is not None and vai != "do_hoa":
                sk["vao_nen"] = {k: v for k, v in do_vao.items() if not k.startswith("_") and k != "chuoi"}
                trong = cv2.erode(vung_nen.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
                do_chu = _do_chuyen_dong(ts_, crops, k_sau, hr, fps_day, ocr_on=True, dong_sau=o_du or None, truoc_mau=mau_nen, vung=trong, nguoi=nguoi, hop_khac=khac, roi=roi)
                if do_chu.get("kieu") not in (None, "khong_do_duoc"):
                    do_vao = do_chu
            sk["tinh"] = tinh
            sk["vao"] = {k: v for k, v in do_vao.items() if not k.startswith("_")}
            if vai == "do_hoa" and tinh.get("nen"):
                sk["loai_do_hoa"] = "the" if o_du else ("icon" if tinh["nen"].get("hinh") in ("tron",) else "hinh")
            st["ctx"] = (hr, roi, o_du, nguoi, khac)
            sk["giay_do"] = round(time.time() - t0, 1)
            # nhãn dải
            vt = (tinh.get("so_voi_mat") or {}).get("vi_tri") or "không mặt"
            nen = tinh.get("nen") or {}
            vv = sk["vao"]
            nhan = (f"{sk['id']} {vai} {sk['t_vao']}s · VÀO {vv.get('kieu')}{('/' + vv['huong']) if vv.get('huong') else ''} {vv.get('dai', '')}s {vv.get('ease') or ''}"
                    + (f" · THẺ vào {sk['vao_nen'].get('kieu')} {sk['vao_nen'].get('dai', '')}s" if sk.get("vao_nen") else "")
                    + f" · {vt}, {tinh.get('can_le')} · mực {tinh.get('cao_muc_px_1920', '?')}px/1920 (~{tinh.get('co_uoc_1920', '?')}px) · {tinh.get('hoa') or ''}"
                    + (f" · nền {nen.get('hinh')} bo{nen.get('bo_px_1080')} {nen.get('mau')}" if nen else "")
                    + (f" · {tinh['hinh']['loai']} {tinh['hinh']['hinh']}" if tinh.get("hinh") else "")
                    + (f" · nghi ngờ {sk['nghi_ngo']}" if sk.get("nghi_ngo") else ""))
            sk["nhan"] = nhan
            if ve_anh:
                h1 = _hang_dai(nhan, ts_, crops, do_vao)
                if h1:
                    with khoa_hang:
                        hangs.append((so, h1)); st["hang"] = h1
            log(f"  {nhan}  ({sk['giay_do']}s)")
        except Exception as ex:
            import traceback
            sk["loi"] = str(ex)[:200]
            log(f"  {sk['id']} lỗi: {traceback.format_exc(limit=2)[-300:]}")

    xu_ly_song_song(cua_so_hang_loat(video, info, ke, fps_day, canh_day, log=log), _xu_ly, log=log)
    hangs = [h for _, h in sorted(hangs, key=lambda x: x[0])]
    su_kien = [st["sk"] for st in trang]
    # ---- chuyển cảnh
    cat_kieu = {}
    for t, _, _ in cat[:toi_da_cat]:
        try:
            k = _kieu_cat(video, info, t)
        except Exception:
            k = "cut"
        cat_kieu[k] = cat_kieu.get(k, 0) + 1
    if zoom:
        cat_kieu["zoom"] = len(zoom)
    tt = _tom_tat(su_kien, vet, cat, zoom, dur, cat_kieu)
    dh = {"phien_ban": PHIEN_BAN, "video": video, "dur": dur, "w": info.get("w"), "h": info.get("h"), "fps": info.get("fps"),
          "cau_hinh": {"fps_day": fps_day, "canh_day": canh_day},
          "cat": [{"t": round(t, 2), "do": d, } for t, _, d in cat], "zoom_cat": [round(t, 2) for t, _ in zoom],
          "vet_chu": [{"t_dau": round(v["t_dau"], 2), "t_ra": round(v["t_ra"], 2), "vai": v.get("vai"), "hop": [round(x, 3) for x in v["hop"]],
                       "cao_dong": round(v["cao_dong"], 4), "so_dong": v["so_dong"], "nghi_ngo": v.get("nghi_ngo"), "dau_hieu": v.get("dau_hieu")}
                      for v in sorted(vet, key=lambda r: r["t_dau"])],
          "do_hoa_tho": [{"t": round(g["t"], 2), "hop": [round(x, 3) for x in g["hop"]], "xuat_hien": g.get("xuat_hien"), "co_chu": g.get("co_chu")} for g in g_dh],
          "su_kien": su_kien, "tong_hop": tt}
    dh["spec_may"] = spec_may(dh)
    dh["giay"] = {"tho": round(t_tho, 1), "tong": round(time.time() - t_bat_dau, 1), "cache": thong_ke_cache()}
    p = os.path.join(thu_muc, "dong_hoc.json")
    C.ghi_json(p, dh)
    anh = []
    if ve_anh and hangs:
        for j in range(0, len(hangs), 7):
            q = _ve_dai(hangs[j:j + 7], os.path.join(thu_muc, f"{ten_anh}-{j // 7 + 1}.jpg"),
                        f"{os.path.basename(video)[:60]} · ĐỘNG HỌC ĐO MÁY (hàng = sự kiện: vắng → chuyển → đủ; xanh = hộp đo, cam = hộp đủ; ô phải: chấm = đo, cam = ease khớp)"
                        + (("\n" + dong_dau_anh) if dong_dau_anh else ""))
            if q:
                anh.append(q)
    dh["anh"] = anh
    dh["duong"] = p
    C.ghi_json(p, dh)
    log(f"  động học: {len(su_kien)} sự kiện đo dày, {len(cat)} cắt, tổng {dh['giay']['tong']}s → {p}")
    return dh


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("thu_muc")
    ap.add_argument("--fps", type=float, default=30); ap.add_argument("--canh", type=int, default=600)
    ap.add_argument("--khong-do-hoa", action="store_true")
    a = ap.parse_args()
    kq = phan_tich(a.video, a.thu_muc, fps_day=a.fps, canh_day=a.canh, do_hoa=not a.khong_do_hoa)
    print(json.dumps(kq["tong_hop"], ensure_ascii=False, indent=1))
