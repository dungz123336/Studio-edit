# -*- coding: utf-8 -*-
"""Tách người (MODNet ONNX, DirectML|CPU) → rãnh alpha xám alpha-<hash>.mp4 (cạnh ngắn 720) và tach_anh() cho 1 khung.
Chất lượng: letterbox bội 32, alpha mềm (không ngưỡng cứng, không lọc mảng rời), nhất quán thời gian bằng
optical flow Farneback (256 px) + trộn theo độ tin cậy, guided filter (boxFilter, r=4 @720) bám mép ảnh thật.
1.2.21 (B3): KHÔNG TREO khi GPU hỏng — mọi lời gọi ORT (mở phiên, suy luận) chạy trong luồng có hạn (GPU 20 s / CPU 60 s mỗi khung,
cau_hinh alpha_khung_toi_da_giay / alpha_khung_cpu_toi_da_giay); GPU lỗi/quá hạn → _GPU_HONG cho phiên + nhớ phan-cung.json ort_loi
(tới khi "Đo lại"), rơi về CPU; CPU quá hạn → RuntimeError "tách người treo". tao_ranh đo tốc độ thật 30 khung đầu: GPU chậm > 5×
nang_luc → chuyển CPU nếu CPU nhanh hơn."""
import os, sys, time, threading, queue, ctypes
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung

PHIEN_BAN = 3          # đổi khi thuật toán đổi → cache mới
_SESS = {}             # provider → session
_KHOA = threading.Lock()
_CPU = "CPUExecutionProvider"
_GPU_HONG = False      # 1.2.21 (B3): provider GPU (DML/CUDA/CoreML) đã ném lỗi hoặc không trả về trong hạn ở PHIÊN này → mọi lời gọi sau dùng CPU
_GPU_HONG_LY_DO = ""


# ---------------------------------------------------------------- hạn giờ (1.2.21 B3) — không còn lời gọi ORT nào được đứng im vô hạn
def _la_gpu(pv):
    return bool(pv) and pv != _CPU


def _han_khung(provider):
    """hạn một lần suy luận (giây): GPU alpha_khung_toi_da_giay (20) · CPU alpha_khung_cpu_toi_da_giay (60, lớn hơn vì CPU chậm thật)"""
    cfg = chung.cau_hinh() or {}
    if _la_gpu(provider):
        return max(1.0, float(cfg.get("alpha_khung_toi_da_giay", 20) or 20))
    return max(1.0, float(cfg.get("alpha_khung_cpu_toi_da_giay", 60) or 60))


def _han_mo_phien(provider):
    """hạn mở phiên ORT (giây): mở DML trên card đã chết cũng có thể treo"""
    cfg = chung.cau_hinh() or {}
    return max(5.0, float(cfg.get("alpha_mo_phien_toi_da_giay", 30 if _la_gpu(provider) else 90) or 30))


def _chay_co_han(fn, han, ten):
    """chạy fn() trong luồng daemon, chờ tối đa `han` giây → kết quả. Quá hạn → TimeoutError (luồng kẹt bị bỏ lại — ORT không huỷ
    được lệnh đang chạy trên card — nhưng luồng gọi KHÔNG đứng im); fn ném lỗi → ném lại ở luồng gọi."""
    kq = {}

    def _w():
        try:
            kq["r"] = fn()
        except BaseException as ex:      # noqa — mọi lỗi (kể cả lỗi C++ ORT bọc thành RuntimeError) chuyển về luồng gọi
            kq["e"] = ex
    t = threading.Thread(target=_w, daemon=True, name=ten)
    t.start()
    t.join(han)
    if t.is_alive():
        raise TimeoutError(f"{ten} không trả về sau {han:.0f} s (treo)")
    if "e" in kq:
        raise kq["e"]
    return kq["r"]


def _danh_dau_gpu_hong(du_an, provider, loi):
    """provider GPU lỗi/treo → (1) _GPU_HONG cho PHIÊN (tiến trình) này: _session/provider_mac_dinh trả CPU; (2) bỏ phiên GPU đã mở;
    (3) ghi nhat-ky.txt; (4) nhớ BỀN phan-cung.json["ort_loi"][provider] + ort_loi_luc → lần chạy sau dùng CPU tới khi khách bấm
    "Đo lại" (phan_cung(lam_moi=True) ghi "luc" mới hơn lỗi → provider_mac_dinh thử card lại)."""
    global _GPU_HONG, _GPU_HONG_LY_DO
    if not _la_gpu(provider):
        return
    ly_do = str(loi)[-240:]
    moi = not _GPU_HONG
    _GPU_HONG, _GPU_HONG_LY_DO = True, ly_do
    with _KHOA:
        _SESS.pop(provider, None)
    if moi:
        chung.log(du_an, f"alpha: {provider} HỎNG ({ly_do}) → tách người bằng CPU cho hết phiên; đã nhớ vào phan-cung.json (bấm Đo lại máy để thử card lại)")
    try:
        chung.nho_loi_phan_cung("ort_loi", provider, ly_do)
        luc = time.strftime("%Y-%m-%d %H:%M:%S")

        def _f(d):
            d.setdefault("ort_loi_luc", {})[provider] = {"luc": luc, "loi": ly_do[-200:]}
        chung.cap_nhat_phan_cung(_f)
    except Exception:
        pass


def _ort_loi_con_hieu_luc(pc, pv):
    """phan-cung.json ghi pv từng hỏng và chưa "Đo lại" từ đó (pc["luc"] — giờ đo phần cứng — không mới hơn giờ lỗi)"""
    if not _la_gpu(pv) or not (pc.get("ort_loi") or {}).get(pv):
        return False
    luc_loi = ((pc.get("ort_loi_luc") or {}).get(pv) or {}).get("luc") or ""
    luc_do = str(pc.get("luc") or "")
    return not (luc_loi and luc_do and luc_do > luc_loi)


# ---------------------------------------------------------------- phiên ONNX
def provider_mac_dinh():
    """Windows: DirectML (theo phan_cung) · Mac: CoreML nếu onnxruntime có (Neural Engine/GPU) · còn lại CPU.
    1.2.21 (B3): card đã hỏng trong phiên (_GPU_HONG) hoặc phan-cung.json ghi ort_loi chưa "Đo lại" → CPU."""
    pc = chung.phan_cung()
    pv = pc.get("ort", _CPU)
    if sys.platform == "darwin":
        try:
            import onnxruntime as ort
            if "CoreMLExecutionProvider" in ort.get_available_providers():
                pv = "CoreMLExecutionProvider"
            else:
                pv = _CPU
        except Exception:
            pv = _CPU
    if _GPU_HONG or _ort_loi_con_hieu_luc(pc, pv):
        return _CPU
    return pv


def _session(provider=None):
    """session MODNet theo provider ("DmlExecutionProvider"|"CoreMLExecutionProvider"|"CPUExecutionProvider"); dùng lại nếu đã mở.
    1.2.21 (B3): mở phiên trong luồng có hạn (_han_mo_phien); GPU lỗi/treo → _danh_dau_gpu_hong → phiên CPU. Không giữ _KHOA lúc mở
    (mở DML trên card chết có thể treo — không được khoá cả mô-đun)."""
    import onnxruntime as ort
    pc = chung.phan_cung()
    if provider is None:
        provider = provider_mac_dinh()
    if provider not in ort.get_available_providers():
        provider = _CPU
    if _GPU_HONG and _la_gpu(provider):
        provider = _CPU
    with _KHOA:
        s = _SESS.get(provider)
    if s is not None:
        return s, provider
    so = ort.SessionOptions()
    so.log_severity_level = 3
    if provider == "DmlExecutionProvider":
        so.enable_mem_pattern = False
        so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    else:
        so.intra_op_num_threads = max(2, int(pc.get("luong", 8)) - 2)
    md = os.path.join(chung.duong("mo_hinh"), "modnet.onnx")
    # CoreML không đỡ hết toán tử → kèm CPU để ORT tự chia đồ thị; DML/CPU giữ một provider như cũ
    pvs = [provider, _CPU] if provider == "CoreMLExecutionProvider" else [provider]
    try:
        s = _chay_co_han(lambda: ort.InferenceSession(md, so, providers=pvs), _han_mo_phien(provider), f"mở phiên MODNet {provider}")
    except Exception as ex:
        if provider != _CPU:
            _danh_dau_gpu_hong(None, provider, ex)
            # R5 (1.2.21): gọi lại _session("CPU") NGOÀI _KHOA — Lock không tái nhập, gọi đệ quy bên trong = tự khoá chết
            return _session(_CPU)
        if isinstance(ex, TimeoutError):
            raise RuntimeError(f"tách người treo: {ex}")
        raise
    with _KHOA:
        s = _SESS.setdefault(provider, s)     # luồng khác vừa mở xong trước → dùng bản đó
    return s, provider


def _kich_thuoc_mang(w, h, ref):
    """cạnh ngắn → ref, cạnh dài theo tỉ lệ; trả (rw, rh) trước đệm và (pw, ph) bội 32 sau đệm"""
    if w <= h:
        rw, rh = ref, int(round(h * ref / w))
    else:
        rh, rw = ref, int(round(w * ref / h))
    pw, ph = (rw + 31) // 32 * 32, (rh + 31) // 32 * 32
    return rw, rh, pw, ph


def _tien_xu_ly(bgr_ds, rw, rh, pw, ph):
    """danh sách BGR → NCHW float32 [-1,1] (letterbox: resize giữ tỉ lệ + đệm lặp biên tới bội 32)"""
    n = len(bgr_ds)
    x = np.empty((n, 3, ph, pw), np.float32)
    for i, bgr in enumerate(bgr_ds):
        im = cv2.resize(bgr, (rw, rh), interpolation=cv2.INTER_AREA if bgr.shape[1] > rw else cv2.INTER_LINEAR)
        if pw != rw or ph != rh:
            im = cv2.copyMakeBorder(im, 0, ph - rh, 0, pw - rw, cv2.BORDER_REPLICATE)
        im = cv2.cvtColor(im, cv2.COLOR_BGR2RGB).astype(np.float32)
        im = (im - 127.5) / 127.5
        x[i] = im.transpose(2, 0, 1)
    return x


def _provider_cua(sess):
    try:
        return (sess.get_providers() or [_CPU])[0]
    except Exception:
        return _CPU


def _suy_luan(sess, x, provider=None, han=None):
    """→ alpha (n, ph, pw) float32 0..1. 1.2.21 (B3): sess.run chạy trong luồng có hạn (GPU 20 s / CPU 60 s — _han_khung);
    quá hạn → TimeoutError (người gọi đổi provider hoặc báo "tách người treo"), KHÔNG đứng im vô hạn như 1.2.20."""
    pv = provider or _provider_cua(sess)
    if han is None:
        han = _han_khung(pv)
    ten = sess.get_inputs()[0].name
    y = _chay_co_han(lambda: sess.run(None, {ten: x}), han, f"MODNet {pv}")[0]
    return np.clip(y[:, 0], 0.0, 1.0)


def _suy_luan_an_toan(sess, provider, x, du_an=None):
    """suy luận có rơi về CPU: GPU ném lỗi / quá hạn → _danh_dau_gpu_hong, mở phiên CPU, chạy lại; CPU quá hạn → RuntimeError
    "tách người treo" rõ ràng (không treo im). → (alpha, sess, provider) — sess/provider có thể đã đổi sang CPU."""
    try:
        return _suy_luan(sess, x, provider), sess, provider
    except Exception as ex:
        if not _la_gpu(provider):
            if isinstance(ex, TimeoutError):
                raise RuntimeError(f"tách người treo: {ex}") from None
            raise
        _danh_dau_gpu_hong(du_an, provider, ex)
        chung.log(du_an, f"alpha: {provider} lỗi/treo ({str(ex)[-160:]}) → chuyển CPU, chạy tiếp")
    sess, provider = _session(_CPU)
    try:
        return _suy_luan(sess, x, provider), sess, provider
    except TimeoutError as ex:
        raise RuntimeError(f"tách người treo: {ex}") from None


# ---------------------------------------------------------------- guided filter
def _box(x, r):
    return cv2.boxFilter(x, -1, (2 * r + 1, 2 * r + 1), normalize=True, borderType=cv2.BORDER_REFLECT)


def guided(I, p, r=4, eps=5e-4):
    """guided filter xám: I = ảnh dẫn 0..1 float32, p = alpha 0..1 → alpha bám mép ảnh"""
    mI, mp = _box(I, r), _box(p, r)
    cI, cIp = _box(I * I, r), _box(I * p, r)
    vI = cI - mI * mI
    cov = cIp - mI * mp
    a = cov / (vI + eps)
    b = mp - a * mI
    return _box(a, r) * I + _box(b, r)


# ---------------------------------------------------------------- nhất quán thời gian
class _NhatQuan:
    """warp alpha khung trước theo flow Farneback (tính ở 256 px) rồi trộn theo độ tin cậy của alpha mới"""

    def __init__(self, rw, rh):
        self.rw, self.rh = rw, rh
        if rw <= rh:
            self.fw, self.fh = int(round(256 * rw / rh)), 256
        else:
            self.fw, self.fh = 256, int(round(256 * rh / rw))
        self.fw, self.fh = max(32, self.fw), max(32, self.fh)
        self.truoc_gray = None
        self.truoc_alpha = None
        gx, gy = np.meshgrid(np.arange(rw, dtype=np.float32), np.arange(rh, dtype=np.float32))
        self.gx, self.gy = gx, gy

    def ap(self, bgr_nho, alpha):
        """bgr_nho: khung ở (rh, rw); alpha: (rh, rw) float32 → alpha đã trộn"""
        g = cv2.cvtColor(cv2.resize(bgr_nho, (self.fw, self.fh), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        ra = alpha
        if self.truoc_gray is not None:
            khac = float(np.abs(g.astype(np.int16) - self.truoc_gray.astype(np.int16)).mean())
            if khac < 40:   # không phải cắt cảnh
                flow = cv2.calcOpticalFlowFarneback(g, self.truoc_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                sx, sy = self.rw / self.fw, self.rh / self.fh
                flow = cv2.resize(flow, (self.rw, self.rh), interpolation=cv2.INTER_LINEAR)
                mx = self.gx + flow[:, :, 0] * sx
                my = self.gy + flow[:, :, 1] * sy
                cu = cv2.remap(self.truoc_alpha, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                # độ "mép": 1 ở vùng alpha 0.2..0.8, 0 khi chắc chắn (≤0.05 / ≥0.95)
                mep = 1.0 - np.clip((np.abs(alpha - 0.5) - 0.3) / 0.15, 0.0, 1.0)
                # bất đồng lớn (che khuất/chuyển động nhanh) → tin khung mới
                dong_y = 1.0 - np.clip((np.abs(cu - alpha) - 0.35) / 0.25, 0.0, 1.0)
                w_cu = 0.3 * mep * dong_y
                ra = (1.0 - w_cu) * alpha + w_cu * cu
        self.truoc_gray, self.truoc_alpha = g, ra
        return ra


# ---------------------------------------------------------------- tiện ích
def _uu_tien_thap_luong():
    try:
        if os.name == "nt":
            k = ctypes.windll.kernel32
            k.SetThreadPriority(k.GetCurrentThread(), -1)      # THREAD_PRIORITY_BELOW_NORMAL
    except Exception:
        pass


def _kich_thuoc_ra(w, h, canh_ngan):
    if w <= h:
        ow, oh = canh_ngan, int(round(h * canh_ngan / w))
    else:
        oh, ow = canh_ngan, int(round(w * canh_ngan / h))
    return ow // 2 * 2, oh // 2 * 2


# ---------------------------------------------------------------- khoá GPU giữa các tiến trình (1.2.19)
def _khoa_gpu(du_an, cho_toi_da=7200):
    """khoá tệp <du_lieu>/alpha-gpu.lock: chỉ MỘT tiến trình chạy MODNet một lúc (DML/CoreML và cả CPU — tránh giẫm nhau).
    Tiến trình chết tự nhả. Chờ tối đa 2 giờ rồi chạy luôn (không chặn vĩnh viễn)."""
    p = os.path.join(chung.duong("du_lieu"), "alpha-gpu.lock")
    t0, da_bao, t_bao = time.time(), False, time.time()
    while True:
        f = open(p, "a+")
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return f
        except OSError:
            f.close()
        if not da_bao:
            chung.log(du_an, "alpha: tiến trình khác đang tách người trên card → chờ lượt (không chạy chồng để GPU không treo)")
            da_bao, t_bao = True, time.time()
        elif time.time() - t_bao > 60:          # nhịp tim: watchdog (cha đếm im 5 phút / Studio 45 phút) không coi chờ lượt là treo
            chung.log(du_an, f"alpha: vẫn chờ lượt card… ({int((time.time() - t0) // 60)} phút)")
            t_bao = time.time()
        if time.time() - t0 > cho_toi_da:
            return None
        time.sleep(2.0)


def _nha_gpu(f):
    if not f:
        return
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    try:
        f.close()
    except OSError:
        pass


# ---------------------------------------------------------------- chỉ mục khoảng alpha (1.2.19 — chạy lại không tách lại)
def _p_chi_muc(du_an):
    return os.path.join(du_an, "cache", "alpha-index.json")


def _doc_chi_muc(du_an, proxy):
    """[{a, b, duong}] các rãnh alpha đã tạo cho proxy này (cùng ref/cạnh ngắn hiện tại), bỏ tệp đã mất"""
    cm = chung.doc_json(_p_chi_muc(du_an)) or {}
    k = _khoa_chi_muc(proxy)
    ra = [x for x in (cm.get(k) or []) if x.get("duong") and os.path.isfile(x["duong"]) and os.path.getsize(x["duong"]) > 1024]
    return ra


def _khoa_chi_muc(proxy):
    cfg = chung.cau_hinh(); hm = chung.hang_may()
    canh_ngan = int(cfg.get("alpha_canh_ngan") or 0) or int(hm["alpha_canh_ngan"])
    ref = int(cfg.get("alpha_ref") or 0) or int(hm["alpha_ref"])
    return f"{chung.bam(proxy)}|{PHIEN_BAN}|{ref}|{canh_ngan}"


def _ghi_chi_muc(du_an, proxy, a, b, duong):
    import json as _j
    p = _p_chi_muc(du_an)
    cm = chung.doc_json(p) or {}
    k = _khoa_chi_muc(proxy)
    ds = [x for x in (cm.get(k) or []) if x.get("duong") != duong]
    ds.append({"a": round(float(a), 3), "b": round(float(b), 3), "duong": duong, "luc": time.strftime("%Y-%m-%d %H:%M:%S")})
    cm[k] = ds[-40:]
    chung.ghi_json(p, cm)


def _cat_alpha(du_an, nguon, a_nguon, a, b, dst):
    """cắt [a,b] (giây gốc) từ rãnh alpha `nguon` bắt đầu ở a_nguon → dst (mã hoá lại cùng tham số, vài giây)"""
    ff = chung.duong("ffmpeg")
    ma, err = chung.chay_ffmpeg([ff, "-v", "error", "-y", "-nostdin", "-ss", f"{max(0.0, a - a_nguon):.3f}", "-i", nguon, "-t", f"{b - a:.3f}",
                                 "-c:v", "libx264", "-preset", "fast", "-crf", "12", "-g", "30", "-pix_fmt", "gray", "-movflags", "+faststart", dst],
                                du_an, f"cắt rãnh alpha {a:.1f}–{b:.1f}s", dur=b - a)
    return ma == 0 and os.path.isfile(dst) and os.path.getsize(dst) > 1024


def _noi_alpha(du_an, manh, dst):
    """nối các mảnh rãnh alpha (cùng cỡ/fps) theo thứ tự thời gian → dst"""
    ff = chung.duong("ffmpeg")
    lst = dst + ".txt"
    with open(lst, "w", encoding="utf-8") as f:
        for m in manh:
            f.write("file '" + m.replace("\\", "/").replace("'", "'\\''") + "'\n")
    ma, err = chung.chay_ffmpeg([ff, "-v", "error", "-y", "-nostdin", "-f", "concat", "-safe", "0", "-i", lst, "-c:v", "libx264", "-preset", "fast", "-crf", "12",
                                 "-g", "30", "-pix_fmt", "gray", "-movflags", "+faststart", dst], du_an, f"nối {len(manh)} mảnh rãnh alpha")
    try:
        os.remove(lst)
    except OSError:
        pass
    return ma == 0 and os.path.isfile(dst) and os.path.getsize(dst) > 1024


def tao_ranh_tai_su_dung(du_an, proxy, a, b, **kw):
    """1.2.19: như tao_ranh(du_an, proxy, a, b) nhưng DÙNG LẠI rãnh đã có trong cache/alpha-index.json:
    - khoảng [a,b] nằm trong rãnh đã có → cắt ra (vài giây) thay vì chạy MODNet lại;
    - chờm ≥ 1 s với rãnh đã có → chỉ tách phần thiếu (đầu/cuối) rồi nối;
    - còn lại → tách mới. Mọi kết quả ghi vào chỉ mục. → đường rãnh (bắt đầu đúng tại a) hoặc None nếu huỷ."""
    a = max(0.0, float(a)); b = float(b)
    if b - a <= 0.05:
        return tao_ranh(du_an, proxy, a, b, **kw)
    ds = _doc_chi_muc(du_an, proxy)
    cache = os.path.join(du_an, "cache"); os.makedirs(cache, exist_ok=True)
    h = chung.bam({"proxy": chung.bam(proxy), "a": round(a, 3), "b": round(b, 3), "v": PHIEN_BAN, "tsd": 1, "k": _khoa_chi_muc(proxy)})
    dst = os.path.join(cache, f"alpha-{h}.mp4")
    if os.path.isfile(dst) and os.path.getsize(dst) > 1024:
        return dst
    eps = 0.05                                             # ≥ 1 khung (24–30 fps): phần thiếu < 1 khung không tách riêng (ffmpeg -t ra 0 khung)
    for x in ds:                                           # 1) nằm trọn trong rãnh đã có
        if x["a"] <= a + eps and x["b"] >= b - eps:
            if abs(x["a"] - a) <= eps and abs(x["b"] - b) <= eps:
                return x["duong"]
            chung.log(du_an, f"alpha: dùng lại rãnh {x['a']:.1f}–{x['b']:.1f}s (cắt {a:.1f}–{b:.1f}s, không tách lại)")
            if _cat_alpha(du_an, x["duong"], x["a"], a, b, dst):
                _ghi_chi_muc(du_an, proxy, a, b, dst)
                return dst
            break
    tot = None
    for x in ds:                                           # 2) chờm nhiều nhất
        giao = min(b, x["b"]) - max(a, x["a"])
        if giao >= 1.0 and (tot is None or giao > tot[0]):
            tot = (giao, x)
    if tot:
        x = tot[1]
        chung.log(du_an, f"alpha: chờm rãnh {x['a']:.1f}–{x['b']:.1f}s → chỉ tách phần thiếu của {a:.1f}–{b:.1f}s")
        manh = []
        if a < x["a"] - eps:
            p1 = tao_ranh(du_an, proxy, a, x["a"], **kw)
            if not p1:
                return None
            manh.append(p1)
        giua = os.path.join(cache, f"alpha-{h}-giua.mp4")
        ga, gb = max(a, x["a"]), min(b, x["b"])
        if not _cat_alpha(du_an, x["duong"], x["a"], ga, gb, giua):
            return tao_ranh(du_an, proxy, a, b, **kw)
        manh.append(giua)
        if b > x["b"] + eps:
            p2 = tao_ranh(du_an, proxy, x["b"], b, **kw)
            if not p2:
                return None
            manh.append(p2)
        if len(manh) == 1:
            os.replace(giua, dst)
        elif not _noi_alpha(du_an, manh, dst):
            return tao_ranh(du_an, proxy, a, b, **kw)
        try:
            os.remove(giua)
        except OSError:
            pass
        _ghi_chi_muc(du_an, proxy, a, b, dst)
        return dst
    p = tao_ranh(du_an, proxy, a, b, **kw)                 # 3) tách mới
    if p:
        _ghi_chi_muc(du_an, proxy, a, b, p)
    return p


# ---------------------------------------------------------------- rãnh alpha
def tao_ranh(du_an, proxy, a=None, b=None, uu_tien_thap=True, huy=None, provider=None, batch=None, ref=None, do_toc_do=None, rieng=True):
    """→ du_an/cache/alpha-<hash>.mp4 (xám 8-bit, cạnh ngắn 720, libx264 crf 12 -g 30) hoặc None nếu huỷ.
    rieng=True: chạy trong tiến trình Python riêng ưu tiên thấp (GPU treo/reset chỉ chết tiến trình con; DML lỗi → tự chạy lại CPU).
    do_toc_do: dict (tuỳ) nhận {"ms_khung","ms_suy_luan","ms_hau_ky","provider","khung"}."""
    if rieng:
        return _tao_ranh_rieng(du_an, proxy, a, b, uu_tien_thap, huy, provider, batch, ref, do_toc_do)
    return _tao_ranh_trong(du_an, proxy, a, b, uu_tien_thap, huy, provider, batch, ref, do_toc_do)


def _tao_ranh_rieng(du_an, proxy, a, b, uu_tien_thap, huy, provider, batch, ref, do_toc_do):
    import json, subprocess
    pv = provider or provider_mac_dinh()
    thu = [pv] + (["CPUExecutionProvider"] if pv != "CPUExecutionProvider" else [])
    for p_ in thu:
        cmd = [chung.duong("python"), os.path.abspath(__file__), "--ranh", du_an, proxy, "" if a is None else str(a), "" if b is None else str(b),
               p_, "" if batch is None else str(batch), "" if ref is None else str(ref)]
        p = chung.popen(cmd, stdout=subprocess.PIPE, uu_tien_thap=uu_tien_thap)
        dong = []

        def _doc():
            for d in p.stdout:
                d = d.decode("utf-8", "replace").rstrip()
                dong.append(d)
                if not d.startswith("@@KQ ") and d.strip():
                    print(d, flush=True)     # tiến độ của tiến trình con (đã ghi nhat-ky.txt ở con)
        t = threading.Thread(target=_doc, daemon=True); t.start()
        t_bat, n_dong, t_dong = time.time(), 0, time.time()
        while p.poll() is None:
            if huy and huy():
                try:
                    p.terminate()
                except Exception:
                    pass
                p.wait()
                chung.log(du_an, "alpha: đã huỷ (tiến trình con)")
                return None
            if len(dong) != n_dong:
                n_dong, t_dong = len(dong), time.time()
            # 1.2.19 (B3): WATCHDOG — con không in tiến độ > 5 phút (GPU kẹt: 887A0006 / CUDA) hoặc chạy quá trần (GPU 4 giờ; CPU 12 giờ
            # vì video dài tách cả cuộn trên CPU có thể > 4 giờ — 1.2.18 không có trần) → giết, thử provider kế
            tran = 12 * 3600 if (p_ or "").startswith("CPU") else 4 * 3600
            if time.time() - t_dong > 300 or time.time() - t_bat > tran:
                try:
                    p.kill()
                except Exception:
                    pass
                p.wait()
                chung.log(du_an, f"alpha: tiến trình con ({p_}) TREO (im {int(time.time() - t_dong)} s) → đã tắt, thử cách khác")
                dong.append("@@TREO")
                break
            time.sleep(0.3)
        if dong and dong[-1] == "@@TREO":
            continue
        t.join(timeout=5)
        kq = next((d for d in reversed(dong) if d.startswith("@@KQ ")), None)
        if p.returncode == 0 and kq:
            j = json.loads(kq[5:])
            if isinstance(do_toc_do, dict):
                do_toc_do.update(j.get("toc_do", {}))
            return j.get("duong")
        chung.log(du_an, f"alpha: tiến trình con ({p_}) lỗi mã {p.returncode}: {(dong[-1] if dong else '')[:160]}")
    raise RuntimeError("alpha: không tạo được rãnh alpha")


def _tao_ranh_trong(du_an, proxy, a=None, b=None, uu_tien_thap=True, huy=None, provider=None, batch=None, ref=None, do_toc_do=None):
    """phiên bản chạy trong tiến trình hiện tại (tiến trình con gọi hàm này)"""
    cfg = chung.cau_hinh()
    hm = chung.hang_may()
    canh_ngan = int(cfg.get("alpha_canh_ngan") or 0) or int(hm["alpha_canh_ngan"])
    ref = ref or int(cfg.get("alpha_ref") or 0) or int(hm["alpha_ref"])
    info = chung.ffprobe(proxy)
    if not info:
        raise RuntimeError("không đọc được proxy")
    W, H, fps = info["w"], info["h"], info["fps"]
    canh_ngan = min(int(canh_ngan), int(min(W, H)))          # 1.2.21: rãnh ra không to hơn proxy (phóng to mặt nạ chỉ tốn CPU, không thêm nét)
    a = 0.0 if a is None else max(0.0, float(a))
    b = info["dur"] if b is None else min(info["dur"], float(b))
    cache = os.path.join(du_an, "cache")
    os.makedirs(cache, exist_ok=True)
    try:                                                     # 1.2.21: .tmp.mp4 mồ côi của lần bị giết trước (không chạm > 2 phút) → xoá
        for ten in os.listdir(cache):
            if ten.startswith("alpha-") and ten.endswith(".tmp.mp4"):
                p_ = os.path.join(cache, ten)
                if time.time() - os.path.getmtime(p_) > 120:
                    os.remove(p_)
    except OSError:
        pass
    h = chung.bam({"proxy": chung.bam(proxy), "a": round(a, 3), "b": round(b, 3), "v": PHIEN_BAN, "ref": ref, "ra": canh_ngan})
    dst = os.path.join(cache, f"alpha-{h}.mp4")
    if os.path.isfile(dst) and os.path.getsize(dst) > 1024:
        chung.log(du_an, f"alpha: dùng cache {os.path.basename(dst)}")
        return dst
    if uu_tien_thap:
        _uu_tien_thap_luong()
    khoa_gpu = None
    try:
        # 1.2.19: hai tiến trình cùng dùng DML (tách sớm + tách theo mẫu, hoặc 2 việc) → GPU 887A0006 → xếp lượt
        # 1.2.21 (B3): chờ quá alpha_cho_khoa_gpu_giay (7200) → không chờ nữa, chạy CPU (không khoá) — không treo
        cho_khoa = float(cfg.get("alpha_cho_khoa_gpu_giay", 7200) or 7200)
        khoa_gpu = _khoa_gpu(du_an, cho_toi_da=cho_khoa)
        if khoa_gpu is None:
            chung.log(du_an, f"alpha: chờ lượt card quá {cho_khoa / 60:.0f} phút → chạy CPU, không chờ nữa")
            provider = _CPU
        sess, provider = _session(provider)
    except Exception:
        _nha_gpu(khoa_gpu)
        raise
    if batch is None:   # DML trên card 2 GB: batch > 1 ở 512 làm GPU treo (887A0006) → 1; CoreML: shape cố định nhanh nhất → 1; CPU: 2
        batch = 1 if provider in ("DmlExecutionProvider", "CoreMLExecutionProvider") else 2
        # 1.2.19: KHÔNG dùng batch 4 cho DML — đo chuẩn nhanh hơn ~22 % nhưng dựng thật trên card 6 GB GPU báo 887A0006
        # "will not respond" sau vài trăm khung ở MỌI đoạn, rơi về batch 1/CPU còn chậm hơn. Giữ batch 1 như 1.2.18 (ổn định).
    rw, rh, pw, ph = _kich_thuoc_mang(W, H, ref)
    ow, oh = _kich_thuoc_ra(W, H, canh_ngan)
    r_guided = max(2, int(round(4 * min(ow, oh) / 720)))
    n_du_kien = max(1, int(round((b - a) * fps)))
    chung.log(du_an, f"alpha: {provider} mạng {pw}x{ph} → ra {ow}x{oh}, {a:.1f}–{b:.1f}s ≈{n_du_kien} khung, batch {batch}")
    ff = chung.duong("ffmpeg")
    cmd_doc = [ff, "-v", "error", "-nostdin"]
    if a > 0:
        cmd_doc += ["-ss", f"{a:.3f}"]
    cmd_doc += ["-i", proxy, "-t", f"{b - a:.3f}", "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    tam = dst + ".tmp.mp4"
    try:
        os.remove(tam)       # dọn lần huỷ dở trước
    except FileNotFoundError:
        pass
    cmd_ghi = [ff, "-v", "error", "-nostdin", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{ow}x{oh}", "-r", f"{fps:.4f}",
               "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "12", "-g", "30", "-pix_fmt", "gray", "-movflags", "+faststart", tam]
    p_doc = chung.popen(cmd_doc, stdout=-1, uu_tien_thap=uu_tien_thap)
    p_ghi = chung.popen(cmd_ghi, stdin=-1, uu_tien_thap=uu_tien_thap)
    q_vao, q_ra = queue.Queue(maxsize=batch * 6), queue.Queue(maxsize=batch * 6)     # 1.2.21: hàng đợi sâu hơn → suy luận không chờ đọc/ghi
    dung = threading.Event()
    loi = []
    n_gf = 2 if int(chung.phan_cung().get("luong") or 0) >= 8 else 1       # 1.2.21: guided filter (độc lập từng khung) chạy 2 luồng khi máy ≥ 8 luồng

    def doc_luong():
        n = W * H * 3
        try:
            while not dung.is_set():
                buf = p_doc.stdout.read(n)
                if len(buf) < n:
                    break
                q_vao.put(np.frombuffer(buf, np.uint8).reshape(H, W, 3))
        except Exception as ex:
            loi.append(ex)
        finally:
            q_vao.put(None)

    nq = _NhatQuan(rw, rh)
    dem = {"n": 0, "post": 0.0}

    def _guided_khung(bgr, al):
        """phần độc lập từng khung: phóng alpha + ảnh dẫn xám (INTER_LINEAR — 1.2.21, CUBIC không thêm nét cho ảnh dẫn) + guided → bytes"""
        al = cv2.resize(al, (ow, oh), interpolation=cv2.INTER_LINEAR)
        dan = cv2.cvtColor(cv2.resize(bgr, (ow, oh), interpolation=cv2.INTER_LINEAR), cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
        al = np.clip(guided(dan, al, r_guided, 5e-4), 0.0, 1.0)
        return (al * 255.0 + 0.5).astype(np.uint8).tobytes()

    def hau_ky_luong():
        """nhất quán thời gian (tuần tự — cần alpha khung trước) → guided filter n_gf luồng (giữ thứ tự bằng future) → ghi ffmpeg"""
        from concurrent.futures import ThreadPoolExecutor
        _uu_tien_thap_luong()
        cho = []                                             # [(t0, future)] theo thứ tự khung
        try:
            with ThreadPoolExecutor(max_workers=n_gf, initializer=_uu_tien_thap_luong) as ex:
                def _xa(toi_da):
                    while len(cho) > toi_da:
                        t0_, f_ = cho.pop(0)
                        p_ghi.stdin.write(f_.result())
                        dem["n"] += 1
                        dem["post"] += time.time() - t0_
                while True:
                    m = q_ra.get()
                    if m is None:
                        break
                    bgr, al = m
                    t0 = time.time()
                    nho = cv2.resize(bgr, (rw, rh), interpolation=cv2.INTER_AREA)
                    al = nq.ap(nho, al)
                    cho.append((t0, ex.submit(_guided_khung, bgr, al)))
                    _xa(n_gf * 2)                            # giữ ≤ 2×n_gf khung đang lọc; ghi theo đúng thứ tự
                _xa(0)
        except Exception as ex:
            loi.append(ex)

    t_doc = threading.Thread(target=doc_luong, daemon=True); t_doc.start()
    t_hau = threading.Thread(target=hau_ky_luong, daemon=True); t_hau.start()
    t_bd, t_sl, n_sl, t_bao = time.time(), 0.0, 0, time.time()
    bi_huy = False
    # 1.2.21 (B3): ĐO TỐC ĐỘ THẬT — sau 30 khung đầu, GPU chậm > 5× số đo nang_luc.tach_nguoi.ms_khung_540 (card "sống" nhưng kẹt
    # sau lỗi CUDA: 0,9 s/khung thay vì 46 ms) → thử 5 khung CPU, CPU nhanh hơn → chuyển CPU cho phần còn lại
    kiem_cham = _la_gpu(provider)
    try:
        het = False
        while not het:
            lo = []
            while len(lo) < batch:
                f = q_vao.get()
                if f is None:
                    het = True
                    break
                lo.append(f)
            if huy and huy():
                bi_huy = True
                break
            if not lo:
                break
            n_that = len(lo)
            while len(lo) < batch:      # giữ shape cố định cho DML
                lo.append(lo[-1])
            x = _tien_xu_ly(lo, rw, rh, pw, ph)
            t0 = time.time()
            al = None
            # 1.2.19: DML lỗi giữa chừng với batch > 1 (card 6 GB sau vài trăm khung) → thử lại DML batch 1 trước khi rơi về CPU (chậm ~8×)
            # 1.2.21 (B3): chỉ khi lỗi THẬT (không phải quá hạn); vẫn lỗi → _suy_luan_an_toan đánh dấu card hỏng + CPU, không treo
            if provider == "DmlExecutionProvider" and batch > 1:
                try:
                    al = _suy_luan(sess, x, provider)
                except TimeoutError:
                    pass
                except Exception as ex:
                    chung.log(du_an, f"alpha: {provider} lỗi ({str(ex)[-300:]}) → thử lại DML batch 1")
                    with _KHOA:
                        _SESS.pop(provider, None)
                    try:
                        sess, provider = _session("DmlExecutionProvider")
                        if provider == "DmlExecutionProvider":
                            al = np.concatenate([_suy_luan(sess, x[i:i + 1], provider) for i in range(n_that)], 0)
                            batch = 1
                    except Exception as ex2:
                        chung.log(du_an, f"alpha: DML batch 1 cũng lỗi ({str(ex2)[-200:]})")
            if al is None:
                al, sess, provider = _suy_luan_an_toan(sess, provider, x, du_an)
            t_sl += time.time() - t0
            n_sl += n_that
            for i in range(n_that):
                q_ra.put((lo[i], np.ascontiguousarray(al[i, :rh, :rw])))
            if kiem_cham and n_sl >= 30:
                kiem_cham = False
                if _la_gpu(provider):
                    ms_gpu = 1000.0 * t_sl / max(1, n_sl)
                    nl_tn = ((chung.phan_cung().get("nang_luc") or {}).get("tach_nguoi") or {})
                    ms_chuan = float(nl_tn.get("ms_khung_540") or 0)
                    mang = nl_tn.get("mang") or []
                    if ms_chuan and len(mang) == 2 and mang[0] and mang[1]:
                        ms_chuan *= (pw * ph) / float(mang[0] * mang[1])      # quy về cỡ mạng đang chạy
                    if ms_chuan and ms_gpu > 5 * ms_chuan:
                        chung.log(du_an, f"alpha: GPU chậm bất thường ({ms_gpu:.0f} ms/khung, chuẩn {ms_chuan:.0f}) → chuyển CPU nếu CPU nhanh hơn")
                        ms_cpu = None
                        if nl_tn.get("provider") == _CPU and ms_chuan:
                            ms_cpu = ms_chuan
                        else:
                            try:                                       # đo 5 khung CPU trên lô vừa chạy (kết quả bỏ, chỉ lấy giờ)
                                s_cpu, _ = _session(_CPU)
                                t1 = time.time()
                                for _ in range(5):
                                    _suy_luan(s_cpu, x[:1], _CPU)
                                ms_cpu = 1000.0 * (time.time() - t1) / 5
                            except Exception as ex:
                                chung.log(du_an, f"alpha: đo CPU lỗi ({str(ex)[-120:]}) — giữ {provider}")
                        if ms_cpu is not None and ms_cpu < ms_gpu:
                            chung.log(du_an, f"alpha: GPU chậm bất thường ({ms_gpu:.0f} ms/khung) → chuyển CPU ({ms_cpu:.0f} ms/khung) cho phần còn lại")
                            sess, provider = _session(_CPU)
                        elif ms_cpu is not None:
                            chung.log(du_an, f"alpha: CPU {ms_cpu:.0f} ms/khung không nhanh hơn → giữ {provider}")
            if time.time() - t_bao > 2.0:
                t_bao = time.time()
                chung.log(du_an, f"alpha: {n_sl}/{n_du_kien} khung, {1000 * t_sl / max(1, n_sl):.0f} ms/khung suy luận")
            if loi:
                raise loi[0]
    finally:
        dung.set()
        _nha_gpu(khoa_gpu)
        if bi_huy:
            try:
                p_doc.kill()
            except Exception:
                pass
        q_ra.put(None)
        t_hau.join()
        try:
            p_ghi.stdin.close()
        except Exception:
            pass
        p_ghi.wait()
        p_doc.wait()
        # dọn hàng đợi để luồng đọc thoát
        try:
            while True:
                q_vao.get_nowait()
        except queue.Empty:
            pass
        t_doc.join(timeout=5)
    if loi:
        raise loi[0]
    tong = time.time() - t_bd
    kq = {"provider": provider, "khung": n_sl, "ms_suy_luan": round(1000 * t_sl / max(1, n_sl), 1),
          "ms_khung": round(1000 * tong / max(1, n_sl), 1), "ms_hau_ky": round(1000 * dem["post"] / max(1, dem["n"]), 1)}
    if isinstance(do_toc_do, dict):
        do_toc_do.update(kq)
    if bi_huy:
        chung.log(du_an, f"alpha: đã huỷ sau {n_sl} khung")
        try:
            os.remove(tam)
        except Exception:
            pass
        return None
    if n_sl == 0 or not os.path.isfile(tam) or os.path.getsize(tam) < 256:
        raise RuntimeError(f"alpha: không có khung nào trong {a:.2f}–{b:.2f}s (ffmpeg không trả khung / ghi lỗi)")
    os.replace(tam, dst)
    chung.log(du_an, f"alpha: xong {n_sl} khung {tong:.1f}s — {kq['ms_khung']} ms/khung (suy luận {kq['ms_suy_luan']}, hậu kỳ {kq['ms_hau_ky']}) [{provider}]")
    return dst


# ---------------------------------------------------------------- 1 khung (bìa)
def tach_anh(rgb, muc="cao", provider=None):
    """rgb: HxWx3 uint8 (RGB) → alpha float32 HxW 0..1. muc "cao" = MODNet cạnh ngắn 1024 + guided; "thuong" = 512."""
    H, W = rgb.shape[:2]
    bgr = cv2.cvtColor(np.ascontiguousarray(rgb), cv2.COLOR_RGB2BGR)
    ref = 1024 if muc == "cao" else 512
    # 1.2.19: ảnh đơn xếp lượt card; 1.2.20: chờ quá alpha_cho_khoa_anh_giay (60 s, card treo) → chạy CPU, không khoá
    cho = float((chung.cau_hinh() or {}).get("alpha_cho_khoa_anh_giay", 60) or 60)
    khoa = _khoa_gpu(None, cho_toi_da=cho)
    try:
        if khoa is None:
            chung.log(None, f"tach_anh: chờ lượt card quá {cho:.0f} s → chạy CPU")
            return _tach_anh_1(bgr, W, H, ref, muc, _CPU)
        return _tach_anh_1(bgr, W, H, ref, muc, provider)
    finally:
        _nha_gpu(khoa)


def _tach_anh_1(bgr, W, H, ref, muc, provider):
    """1.2.21 (B3): mỗi lần suy luận có hạn (GPU 20 s / CPU 60 s). GPU lỗi/quá hạn → đánh dấu hỏng, các lần thử còn lại chạy CPU;
    CPU quá hạn → RuntimeError "tách người treo" ngay (không thử thêm 3 cỡ nữa, mỗi cỡ lại chờ 60 s)."""
    al = None
    for thu_ref, thu_pv in ((ref, provider), (768, provider), (512, provider), (512, _CPU)):
        if _GPU_HONG:
            thu_pv = _CPU
        pv = thu_pv or provider_mac_dinh()
        try:
            sess, pv = _session(thu_pv)
            rw, rh, pw, ph = _kich_thuoc_mang(W, H, thu_ref)
            x = _tien_xu_ly([bgr], rw, rh, pw, ph)
            al = _suy_luan(sess, x, pv)[0, :rh, :rw]
            break
        except Exception as ex:
            if _la_gpu(pv):
                _danh_dau_gpu_hong(None, pv, ex)
                chung.log(None, f"tach_anh: {pv} @{thu_ref} lỗi/treo ({str(ex)[:80]}) → thử lại bằng CPU")
                continue
            if isinstance(ex, TimeoutError):
                raise RuntimeError(f"tách người treo: {ex}") from None
            chung.log(None, f"tach_anh: {pv} @{thu_ref} lỗi ({str(ex)[:80]}) → thử lại")
            with _KHOA:          # phiên có thể đã chết → mở lại lần sau
                _SESS.pop(pv, None)
    if al is None:
        raise RuntimeError("tach_anh: MODNet không chạy được")
    al = cv2.resize(al, (W, H), interpolation=cv2.INTER_LINEAR)
    if muc == "cao":
        # MODNet ở 1024 có mép tóc/ngón tay đẹp nhưng hay THỦNG mảng tối, ít tương phản (áo đen, ghế) → lấy LÕI người từ bản 512
        # (đặc, như rãnh video) và NỀN chắc chắn từ bản 512; chỉ dùng bản 1024 ở dải mép.
        try:
            rw, rh, pw, ph = _kich_thuoc_mang(W, H, 512)
            a5 = None
            for pv5 in (provider, _CPU):          # card bận/lỗi → CPU (ảnh đơn ~1 s)
                if _GPU_HONG:
                    pv5 = _CPU
                try:
                    sess, pv5 = _session(pv5)
                    a5 = _suy_luan(sess, _tien_xu_ly([bgr], rw, rh, pw, ph), pv5)[0, :rh, :rw]
                    break
                except Exception as ex5:
                    if _la_gpu(pv5):
                        _danh_dau_gpu_hong(None, pv5, ex5)
                    elif isinstance(ex5, TimeoutError):
                        raise RuntimeError(f"tách người treo: {ex5}") from None
                    else:
                        with _KHOA:
                            _SESS.pop(pv5, None)
            if a5 is None:
                raise RuntimeError("512 không chạy được")
            a5 = cv2.resize(a5, (W, H), interpolation=cv2.INTER_LINEAR)
            k = max(3, int(round(min(W, H) / 120))) | 1
            loi = cv2.erode((a5 >= 0.9).astype(np.uint8), np.ones((k, k), np.uint8)) > 0
            nen = cv2.erode((a5 <= 0.05).astype(np.uint8), np.ones((k, k), np.uint8)) > 0
            al = np.where(loi, np.maximum(al, a5), np.where(nen, np.minimum(al, a5), al))
        except Exception as ex:
            chung.log(None, f"tach_anh: bù lõi 512 lỗi ({str(ex)[:80]}) — dùng bản 1024")
    dan = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    r = max(2, int(round(4 * min(W, H) / 720)))
    return np.clip(guided(dan, al, r, 5e-4), 0.0, 1.0).astype(np.float32)


if __name__ == "__main__":
    import json
    if len(sys.argv) > 1 and sys.argv[1] == "--ranh":   # tiến trình con: --ranh du_an proxy a b provider batch ref
        _, _, da, px, a, b, pv, bt, rf = sys.argv[:9]
        kq = {}
        try:
            d = _tao_ranh_trong(da, px, float(a) if a else None, float(b) if b else None, provider=pv or None,
                                batch=int(bt) if bt else None, ref=int(rf) if rf else None, do_toc_do=kq)
        except Exception as ex:
            print(f"LOI {ex}", flush=True)
            sys.exit(2)
        print("@@KQ " + json.dumps({"duong": d, "toc_do": kq}, ensure_ascii=False), flush=True)
        sys.exit(0)
    da, px = sys.argv[1], sys.argv[2]
    a = float(sys.argv[3]) if len(sys.argv) > 3 else None
    b = float(sys.argv[4]) if len(sys.argv) > 4 else None
    kq = {}
    print(tao_ranh(da, px, a, b, do_toc_do=kq), kq)
