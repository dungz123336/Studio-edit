# -*- coding: utf-8 -*-
"""Lớp (layer) → sprite theo thời gian, CHỈ vẽ trong hộp của lớp.
Kiểu: chu · khoi · the · hinh · video · duong · py · mau · web. Giải vị trí (anchor 9 điểm, so_voi khung|mat|duoi_cam|tren_dau, vùng an toàn,
không đè mặt → dời → thu tới ne_mat.thu_toi của KÊNH → lỗi de_mat (ti_le đặt lại 1)), ket_xuat_sprite (PNG dedup + ffconcat), phu_de_sang_lop (cụm + karaoke).
1.2.21: máy không còn số thẩm mỹ riêng — mọi mặc định đọc ctx.quyet_dinh (quyet-dinh.json của kênh, Kế hoạch 1.2.21 §1c); thiếu → ThieuTruong
{"duong","ma":"thieu_truong"}. Lớp có vi_tri.w,h ≥ 0.9 = toàn khung (không né mặt/vùng an toàn/thu). Cache ảnh có trần RAM (CacheAnh, cau_hinh cache_anh_mb)."""
import unicodedata, os, io, math, json, hashlib, importlib.util, threading, statistics, subprocess
import numpy as np
import cv2
import skia

try:
    import chung
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import chung
from dung import anim as _anim
from dung import chu as _chu

ANCHOR = {"tl": (0, 0), "tc": (0.5, 0), "tr": (1, 0), "ml": (0, 0.5), "mc": (0.5, 0.5), "mr": (1, 0.5), "bl": (0, 1), "bc": (0.5, 1), "br": (1, 1)}
VI_TRI_MAC_DINH = {"anchor": "mc", "x": 0.5, "y": 0.5, "so_voi": "khung"}      # không ghi vị trí = tâm khung (cấu trúc, không phải gu)
TOAN_KHUNG_TU = 0.9               # 1.2.21: lớp có vi_tri.w ≥ 0.9 và h ≥ 0.9 (tỉ lệ khung) = lớp TOÀN KHUNG — không né mặt, không vùng an toàn, không thu
# 1.2.21: MỌI mặc định thẩm mỹ (phụ đề, thẻ, hộp mặc định, nới mặt, thu khi đè mặt, mặt giả) đã bỏ — đọc ctx.quyet_dinh (quyet-dinh.json của kênh);
# thiếu → ThieuTruong {"duong": "<đường trường>", "ma": "thieu_truong"}. Các hằng số còn lại dưới đây là VẬT LÝ (hình học mặt YuNet, lề sprite).


# ======================================================================== quyết định của kênh (ctx.quyet_dinh) ====
ThieuTruong = _chu.ThieuTruong          # định nghĩa ở dung/chu.py (chu.py không import lop) — cùng một lớp lỗi


_THIEU = object()


def quyet(ctx, duong, mac_dinh=_THIEU, lop=None):
    """đọc ctx.quyet_dinh theo đường "a.b.c" (quyet-dinh.json của kênh, dung.tao_ctx gán từ ke_hoach["quyet_dinh"]).
    Thiếu → ThieuTruong(duong). mac_dinh CHỈ truyền cho giá trị vật lý (không phải gu)."""
    qd = getattr(ctx, "quyet_dinh", None) if ctx is not None else None
    if not isinstance(qd, dict):
        if mac_dinh is not _THIEU:
            return mac_dinh
        raise ThieuTruong(duong, "ctx.quyet_dinh chưa có (kênh chưa có quyet-dinh.json)", lop)
    cur = qd
    for k in str(duong).split("."):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        elif isinstance(cur, list) and k.isdigit() and int(k) < len(cur):
            cur = cur[int(k)]
        else:
            if mac_dinh is not _THIEU:
                return mac_dinh
            raise ThieuTruong(duong, lop=lop)
    if cur is None and mac_dinh is _THIEU:
        raise ThieuTruong(duong, "giá trị null", lop)
    return cur


def co_quyet(ctx, duong):
    try:
        quyet(ctx, duong)
        return True
    except ThieuTruong:
        return False


def dien_tu_quyet(d, ctx, bang, duong_goc, lop=None):
    """điền vào dict d các khoá còn thiếu từ quyet_dinh: bang = {khoa_trong_d: đường trong quyet_dinh}; thiếu cả hai → ThieuTruong"""
    d = dict(d or {})
    for k, duong in bang.items():
        if d.get(k) is None:
            d[k] = quyet(ctx, duong, lop=lop)
    return d


CacheAnh = _chu.CacheAnh                # cache ảnh có trần RAM (cau_hinh cache_anh_mb) — định nghĩa ở dung/chu.py


# ======================================================================== Ctx ====
MAT_NOI_TREN = 0.12      # khung mặt (lông mày→cằm của YuNet) nới lên trên × cao mặt — vùng CẤM che (mắt, miệng) — hình học YuNet (vật lý)
MAT_NOI_NGANG = 0.05     # nới hai bên × rộng mặt — hình học YuNet (vật lý)


class Ctx:
    """ngữ cảnh dựng: W,H,fps · font(vai|id)→file · mat.json · kho.lay(id) · cat · camera · nguồn"""

    def __init__(self, W=1080, H=1920, fps=30, font=None, mat=None, kho=None, du_an=None, cat=None, camera=None,
                 nguon=None, kich_thuoc=None, quyet_dinh=None):
        self.W, self.H, self.fps = int(W), int(H), float(fps)
        self.font = font or {}            # dict vai→file hoặc callable
        self.mat = mat
        self.kho = kho
        self.du_an = du_an
        self.cat = cat or []
        self.camera = camera or []
        self.nguon = nguon or []          # [đường dẫn video nguồn]
        self.kich_thuoc = kich_thuoc or {}  # {src: (w,h)}
        self.quyet_dinh = quyet_dinh      # 1.2.21: quyet-dinh.json của kênh (dict theo Kế hoạch 1.2.21 §1c) — dung.tao_ctx gán
        self.may_sua = []
        self.loi = []
        self.vung = chung.vung_an_toan(self.W, self.H)
        self.ti_le_px = 1.0               # khổ ra / khổ thiết kế (xuất 1440p/4K: số px trong công thức đã nhân sẵn)
        self.base = None                  # base.mp4 đã dựng (cắt + camera + màu + nền mới) — cho lay_nen
        self.alpha_tl = None              # rãnh alpha xám W×H theo dòng thời gian thành phẩm — cho lay_alpha
        self.tao_alpha = None             # callable() → alpha_tl (dung.py gắn: tách người lười khi mẫu cần)
        self._doc = {}
        self._khoa_alpha = threading.Lock()

    # ---- font
    def font_file(self, ten):
        if callable(self.font):
            try:
                p = self.font(ten)
                if p:
                    return p
            except Exception:
                pass
        elif isinstance(self.font, dict) and ten in self.font and self.font[ten]:
            return self.font[ten]
        # 1.2.21: vai chưa có trong bảng font của video → font của KÊNH (quyet-dinh.json "font": {vai: id kho|đường|họ})
        try:
            f = quyet(self, "font." + str(ten))
            p = self.tai_nguyen(f) if isinstance(f, str) else None
            if p:
                return p
        except ThieuTruong:
            pass
        return _chu.giai_font(ten)

    # ---- kho / tài nguyên
    def tai_nguyen(self, id_or_path):
        """id kho | đường dẫn → đường dẫn file (None nếu không có)"""
        if not id_or_path:
            return None
        if isinstance(id_or_path, str) and os.path.isfile(id_or_path):
            return id_or_path
        if self.du_an and isinstance(id_or_path, str):
            p = os.path.join(self.du_an, id_or_path)
            if os.path.isfile(p):
                return p
        if self.kho is not None:
            try:
                m = self.kho.lay(id_or_path) if hasattr(self.kho, "lay") else self.kho(id_or_path)
                if m and m.get("duong") and os.path.isfile(m["duong"]):
                    return m["duong"]
            except Exception:
                pass
        return None

    # ---- thời gian: thành phẩm → gốc
    def goc(self, t):
        """giây thành phẩm → (src, giây gốc) theo cat; không có cat → (0, t)"""
        if not self.cat:
            return 0, t
        off = 0.0
        for seg in self.cat:
            d = float(seg["b"]) - float(seg["a"])
            if t < off + d or seg is self.cat[-1]:
                return int(seg.get("src", 0)), float(seg["a"]) + (t - off)
            off += d
        return int(self.cat[-1].get("src", 0)), float(self.cat[-1]["b"])

    def tong_dai(self):
        if self.cat:
            return sum(float(s["b"]) - float(s["a"]) for s in self.cat)
        return 0.0

    # ---- camera tại t → (z, cx, cy)
    def camera_tai(self, t):
        kfs = sorted(self.camera or [], key=lambda k: float(k.get("t", 0)))
        if not kfs:
            return 1.0, 0.5, 0.5
        z, cx, cy = 1.0, 0.5, 0.5
        for k in kfs:
            kt = float(k.get("t", 0)); dai = float(k.get("dai", 0))
            if t < kt:
                break
            # 1.2.21: ease camera không còn mặc định "out" — keyframe thiếu ease → quyet_dinh camera.ease → thieu_truong
            u = _anim.ease(k.get("ease") or quyet(self, "camera.ease"), (t - kt) / dai) if dai > 0 else 1.0
            z = z + (float(k.get("z", z)) - z) * u
            cx = cx + (float(k.get("x", cx)) - cx) * u
            cy = cy + (float(k.get("y", cy)) - cy) * u
        return z, cx, cy

    def _nguon_sang_khung(self, src, x, y, t):
        """toạ độ 0..1 của khung nguồn → 0..1 của khung thành phẩm (cover + camera)"""
        sw, sh = self.kich_thuoc.get(src, (self.W, self.H))
        s = max(self.W / sw, self.H / sh)
        cw, ch = (self.W / s) / sw, (self.H / s) / sh
        x = (x - (1 - cw) / 2) / cw; y = (y - (1 - ch) / 2) / ch
        z, cx, cy = self.camera_tai(t)
        return (x - (cx - 0.5 / z)) * z, (y - (cy - 0.5 / z)) * z

    # ---- mặt
    def mat_tai(self, t0, t1):
        """mặt (lớn nhất mỗi khung) trung vị trong [t0,t1] giây thành phẩm → {"x","y","w","h","x0","y0","x1","y1","co"} toạ độ khung; None nếu không có dữ liệu"""
        if not self.mat or not self.mat.get("khung"):
            return None
        ds = []
        n = max(2, int((t1 - t0) * 5) + 1)
        for i in range(n):
            t = t0 + (t1 - t0) * i / max(1, n - 1)
            src, tg = self.goc(t)
            tot = None
            for k in self.mat["khung"]:
                if k.get("src", 0) != src:
                    continue
                if tot is None or abs(float(k["t"]) - tg) < abs(float(tot["t"]) - tg):
                    tot = k
            if tot is None or abs(float(tot["t"]) - tg) > 1.0 / max(1, self.mat.get("fps_mau", 5)) + 0.3:
                continue
            ms = tot.get("mat") or []
            if not ms:
                continue
            m = max(ms, key=lambda f: float(f.get("w", 0)) * float(f.get("h", 0)) * float(f.get("diem", 1)))
            z, _, _ = self.camera_tai(t)
            # mat.json ghi TÂM mặt (x, y) + cỡ (w, h) của khung nguồn; khung YuNet chỉ từ lông mày tới cằm → nới lên trán/tóc + hai bên
            mw, mh = float(m["w"]), float(m["h"])
            x0, y0 = self._nguon_sang_khung(src, float(m["x"]) - mw * (0.5 + MAT_NOI_NGANG), float(m["y"]) - mh * (0.5 + MAT_NOI_TREN), t)
            sw, sh = self.kich_thuoc.get(src, (self.W, self.H)); s = max(self.W / sw, self.H / sh)
            w = mw * (1 + 2 * MAT_NOI_NGANG) * sw * s / self.W * z; h = mh * (1 + MAT_NOI_TREN) * sh * s / self.H * z
            ds.append((x0, y0, w, h))
        if not ds:
            return None
        x = statistics.median(d[0] for d in ds); y = statistics.median(d[1] for d in ds)
        w = statistics.median(d[2] for d in ds); h = statistics.median(d[3] for d in ds)
        return {"x": x, "y": y, "w": w, "h": h, "x0": min(d[0] for d in ds), "y0": min(d[1] for d in ds),
                "x1": max(d[0] + d[2] for d in ds), "y1": max(d[1] + d[3] for d in ds), "co": True}

    def mat_hoac_mac_dinh(self, t0, t1):
        """1.2.21: KHÔNG còn mặt giả — không có mặt (chưa quét / không thấy) → None; nơi gọi báo lỗi `khong_mat` và neo theo khung"""
        return self.mat_tai(t0, t1)

    # ---- nền đã dựng / mặt nạ người (cho mẫu lam_nen) — đọc tuần tự qua ffmpeg pipe, cache khung gần
    def _bo_doc(self, loai, lop):
        p = self.base if loai == "nen" else self.alpha_tl
        k = (loai, id(lop) if lop is not None else None, threading.get_ident(), p)
        d = self._doc.get(k)
        if d is None:
            if not p or not os.path.isfile(p):
                return None
            d = _DocKhung(p, self.W, self.H, self.fps, 3 if loai == "nen" else 1)
            self._doc[k] = d
        return d

    def _cat_hop(self, fr, lop):
        x0, y0, w, h = lop.khoi()
        x0, y0, w, h = int(round(x0)), int(round(y0)), max(1, int(round(w))), max(1, int(round(h)))
        if x0 >= 0 and y0 >= 0 and x0 + w <= self.W and y0 + h <= self.H:
            return np.ascontiguousarray(fr[y0:y0 + h, x0:x0 + w])
        ra = np.zeros((h, w) + fr.shape[2:], fr.dtype)
        ax0, ay0, ax1, ay1 = max(0, x0), max(0, y0), min(self.W, x0 + w), min(self.H, y0 + h)
        if ax1 > ax0 and ay1 > ay0:
            ra[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0] = fr[ay0:ay1, ax0:ax1]
        return ra

    def lay_nen(self, lop, t, ca_khung=True):
        """RGB uint8 CỠ KHUNG (H, W, 3) của NỀN đã dựng (cắt + camera + màu + nền mới, chưa có lớp nào) tại giây t TÍNH TỪ t0 của lớp
        (đúng t mà CongCu.nen(t) truyền). ca_khung=False → cắt đúng hộp lớp (h, w, 3). Chưa có base → None."""
        d = self._bo_doc("nen", lop)
        if d is None:
            return None
        fr = d.lay(int(round((float(lop.t0 if lop is not None else 0) + float(t)) * self.fps)))
        if fr is None:
            return None
        return fr if (ca_khung or lop is None) else self._cat_hop(fr, lop)

    def lay_alpha(self, t, lop=None, ca_khung=True):
        """mặt nạ NGƯỜI uint8 0..255 CỠ KHUNG (H, W). lop=None: t là giây THÀNH PHẨM; có lop: t tính từ t0 của lớp
        (ca_khung=False → cắt đúng hộp lớp). Chưa có rãnh alpha → engine tách người (đoạn lớp cần, một lần) rồi đọc; không tách được → None."""
        can = (float(lop.t0), float(lop.t1)) if lop is not None else (0.0, max(self.tong_dai(), float(t) + 0.1))
        kh = getattr(self, "_alpha_khoang", None)
        if self.tao_alpha is not None and (kh is None or can[0] < kh[0] - 1e-3 or can[1] > kh[1] + 1e-3):
            with self._khoa_alpha:                    # chỉ tách người đoạn lớp CẦN (hợp các đoạn đã cần) — một lần mỗi lớp
                kh = getattr(self, "_alpha_khoang", None)
                if self.tao_alpha is not None and (kh is None or can[0] < kh[0] - 1e-3 or can[1] > kh[1] + 1e-3):
                    moi = (min(can[0], kh[0]), max(can[1], kh[1])) if kh else can
                    try:
                        p = self.tao_alpha(moi)
                        if p:
                            self.alpha_tl, self._alpha_khoang = p, moi
                        else:
                            self.tao_alpha = None
                    except Exception as ex:
                        self.tao_alpha = None
                        self.loi.append({"id": "tai_nguyen_khong_co", "lop": getattr(lop, "id", "alpha"), "mo_ta": f"không tách được người: {ex}"})
        d = self._bo_doc("alpha", lop)
        if d is None:
            return None
        t_tp = (float(lop.t0) + float(t)) if lop is not None else float(t)
        fr = d.lay(int(round(t_tp * self.fps)))
        if fr is None:
            return None
        fr = fr[:, :, 0]
        return fr if (ca_khung or lop is None) else self._cat_hop(fr, lop)

    def nguoi(self, lop, t):
        """cho mẫu: mặt nạ người uint8 tại giây t TỪ t0 của lớp, CẮT ĐÚNG HỘP lớp (h, w) — mẫu toàn khung thì = cỡ khung.
        (alpha_nguoi trong dung/mau/chu_hieu_ung.py resize — không cắt — khi khác cỡ hộp, nên trả đúng hộp; cả khung: lay_alpha(t, lop))"""
        return self.lay_alpha(t, lop, ca_khung=False)

    lay_nguoi = nguoi

    def dong_doc(self, lop=None):
        for k in [k for k in list(self._doc) if lop is None or k[1] == id(lop)]:
            try:
                self._doc.pop(k).dong()
            except Exception:
                pass

    def xuat(self):
        """dict thuần để gửi sang tiến trình con"""
        return {"W": self.W, "H": self.H, "fps": self.fps, "font": self.font if isinstance(self.font, dict) else {},
                "mat": self.mat, "du_an": self.du_an, "cat": self.cat, "camera": self.camera, "nguon": self.nguon,
                "kich_thuoc": {str(k): v for k, v in self.kich_thuoc.items()}, "pc": getattr(self, "pc", None) or {},
                "ti_le_px": self.ti_le_px, "base": self.base, "alpha_tl": self.alpha_tl, "quyet_dinh": self.quyet_dinh}

    @staticmethod
    def tu_dict(d, kho=None):
        c = Ctx(d["W"], d["H"], d["fps"], d.get("font"), d.get("mat"), kho, d.get("du_an"), d.get("cat"), d.get("camera"), d.get("nguon"),
                {int(k): tuple(v) for k, v in (d.get("kich_thuoc") or {}).items()}, quyet_dinh=d.get("quyet_dinh"))
        c.pc = d.get("pc") or {}
        c.ti_le_px = float(d.get("ti_le_px") or 1.0)
        c.base, c.alpha_tl = d.get("base"), d.get("alpha_tl")
        return c


class _DocKhung:
    """đọc khung video W×H (rgb24 | gray) tuần tự qua ffmpeg pipe; nhảy lùi / xa > 3 s thì mở lại ở -ss. Giữ khung vừa đọc."""

    def __init__(self, path, W, H, fps, kenh=3):
        self.path, self.W, self.H, self.fps, self.kenh = path, int(W), int(H), float(fps), kenh
        self.proc = None; self.idx = -1; self.cur = None; self.het = False

    def _mo(self, idx):
        self.dong()
        if not hasattr(self, "_loc"):
            self._loc = loc_mau_vao(self.path) if self.kenh == 3 else ""    # 1.2.21: nguồn 10-bit/HDR → ép về yuv420p/bt709 TRƯỚC scale
        vf = (self._loc + "," if self._loc else "") + f"scale={self.W}:{self.H}"
        cmd = [chung.duong("ffmpeg"), "-v", "error", "-nostdin", "-ss", "%.6f" % (max(0, idx) / self.fps), "-i", self.path,
               "-vf", vf, "-colorspace", "bt709", "-f", "rawvideo", "-pix_fmt", "rgb24" if self.kenh == 3 else "gray", "-"]
        self.proc = chung.popen(cmd, stdout=subprocess.PIPE)
        self.idx = idx - 1; self.het = False

    def lay(self, idx):
        idx = max(0, int(idx))
        if self.cur is not None and idx == self.idx:
            return self.cur
        if self.proc is None or idx < self.idx or idx > self.idx + 3 * self.fps:
            if self.het and self.cur is not None and idx > self.idx:
                return self.cur                       # đã hết file: giữ khung cuối
            self._mo(idx)
        n = self.W * self.H * self.kenh
        while self.idx < idx:
            buf = self.proc.stdout.read(n) if self.proc else b""
            if len(buf) < n:
                self.het = True
                break
            self.idx += 1
            self.cur = np.frombuffer(buf, np.uint8).reshape(self.H, self.W, self.kenh)
        return self.cur

    def dong(self):
        if self.proc:
            try:
                self.proc.stdout.close(); self.proc.kill(); self.proc.wait(timeout=5)
            except Exception:
                pass
            self.proc = None


# ======================================================================== màu nguồn (1.2.21, §1f) ====
def loc_mau_vao(info_hoac_duong):
    """chuỗi filter đặt TRƯỚC scale khi đọc nguồn: chung.loc_mau_vao(info) (A1: HDR→tonemap bt709, 10-bit→yuv420p, 8-bit→"").
    chung chưa có hàm → dự phòng: 10-bit/HDR → format=yuv420p, còn lại ""."""
    info = info_hoac_duong
    if isinstance(info, str):
        info = chung.ffprobe(info) if info and os.path.isfile(info) else None
    if not info:
        return ""
    f = getattr(chung, "loc_mau_vao", None)
    if f is not None:
        try:
            return str(f(info) or "")
        except Exception:
            pass
    pf = str(info.get("pix_fmt") or "")
    if info.get("hdr") or int(info.get("bit_depth") or 0) > 8 or "10" in pf or "12" in pf or "16" in pf:
        return "format=yuv420p"
    return ""


# ======================================================================== tiện ích ảnh ====
def anh_skia_tu_numpy(arr, bgra=False):
    """numpy RGBA (hoặc BGRA nếu bgra=True) thẳng (h,w,4) → skia.Image premul N32 (BGRA): Skia chỉ nhanh với N32 (đo: 8–10×)"""
    if not bgra:
        arr = cv2.cvtColor(np.ascontiguousarray(arr), cv2.COLOR_RGBA2BGRA)
    arr = np.ascontiguousarray(arr)
    # nhân trước alpha MỘT lần ở đây: ảnh kUnpremul mỗi lần vẽ Skia phải tự nhân → chậm ~40× (đo 84 ms so với 2 ms)
    a = arr[..., 3]
    if a.min() < 255:
        b, g, r = cv2.split(arr[..., :3])
        arr = cv2.merge([cv2.multiply(b, a, scale=1 / 255.0), cv2.multiply(g, a, scale=1 / 255.0), cv2.multiply(r, a, scale=1 / 255.0), a])
    return skia.Image.fromarray(np.ascontiguousarray(arr), skia.kBGRA_8888_ColorType, skia.kPremul_AlphaType)


def doc_anh(path):
    """đọc ảnh → numpy BGRA thẳng (giữ alpha) — thứ tự kênh của OpenCV/N32"""
    try:
        a = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_UNCHANGED)
    except Exception:
        return None
    if a is None:
        return None
    if a.ndim == 2:
        a = cv2.cvtColor(a, cv2.COLOR_GRAY2BGRA)
    elif a.shape[2] == 3:
        a = cv2.cvtColor(a, cv2.COLOR_BGR2BGRA)
    if a.dtype != np.uint8:
        a = (a.astype(np.float32) / max(float(a.max()), 1) * 255).astype(np.uint8)
    return np.ascontiguousarray(a)


def numpy_bgra_tu_skia(img):
    """skia.Image (N32 premul) → numpy BGRA thẳng. Đọc premul (3 ms) rồi un-premultiply bằng cv2.divide (≈6 ms, khớp 100%)
    thay vì toarray(kUnpremul) của skia (≈30–65 ms)."""
    p = img.toarray(colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
    b, g, r, a = cv2.split(p)
    return cv2.merge([cv2.divide(b, a, scale=255.0), cv2.divide(g, a, scale=255.0), cv2.divide(r, a, scale=255.0), a])


def numpy_tu_skia(img):
    """skia.Image premul → numpy RGBA thẳng"""
    return cv2.cvtColor(numpy_bgra_tu_skia(img), cv2.COLOR_BGRA2RGBA)


_SAMP_CUBIC = skia.SamplingOptions(skia.CubicResampler.Mitchell())
_SAMP_LIN = skia.SamplingOptions(skia.FilterMode.kLinear)              # không mipmap: MipmapMode.kLinear chậm 10–50× (đo trên máy yếu)
_SAMP_NONE = skia.SamplingOptions()
_SAMP_LIN_NM = skia.SamplingOptions(skia.FilterMode.kLinear)


# ======================================================================== Lop ====
class Lop:
    """lớp cơ sở. Con lớp cài: kich_thuoc() → (w,h) px khối nhìn thấy; noi_dung(lt) → (skia.Image premul, (dx,dy) lệch gốc khối trong ảnh);
    khoa_noi_dung(lt) → khoá băm nội dung (None = tĩnh)."""
    kieu = "lop"

    def __init__(self, spec, ctx):
        self.spec = spec; self.ctx = ctx
        self.id = spec.get("id", "lop")
        self.t0 = float(spec.get("t0", 0)); self.t1 = float(spec.get("t1", self.t0 + 1))
        self.dur = max(self.t1 - self.t0, 1.0 / ctx.fps)
        self.may_sua = []; self.loi = []
        # 1.2.21: anim điền đủ vao/ra/so_le/keyframe từ quyet_dinh["anim"] (anim.py không còn số riêng) — thiếu → thieu_truong
        self.anim = _anim.day_du(spec.get("anim") or {}, getattr(ctx, "quyet_dinh", None), lop=self.id)
        self.vi_tri = dict(VI_TRI_MAC_DINH); self.vi_tri.update(spec.get("vi_tri") or {})
        self.kd = spec.get("kieu_dang") or {}
        try:
            self.do_trong = max(0.0, min(1.0, float(self.kd.get("do_trong", 1.0))))
        except Exception:
            self.do_trong = 1.0
        self.tween = None                 # (dx, dy, dai) dịch từ vị trí cụm trước (phụ đề)
        self.ti_le = 1.0                  # thu nhỏ khi đè mặt
        self._hop = None; self._khoi = None
        self.n_phan = 1
        self.toan_khung = la_toan_khung(spec)   # 1.2.21: w,h ≥ 0.9 → không né mặt / vùng an toàn / thu

    # ---- quyết định của kênh
    def quyet(self, duong, mac_dinh=_THIEU):
        return quyet(self.ctx, duong, mac_dinh, lop=self.id)

    # ---- con lớp cài
    def kich_thuoc(self):
        return (100.0, 100.0)

    def noi_dung(self, lt):
        raise NotImplementedError

    def khoa_noi_dung(self, lt):
        return None

    def le_noi_dung(self):
        """lề (px) của nội dung vượt khối (viền/bóng) → {"trai","phai","tren","duoi"}"""
        return {"trai": 0, "phai": 0, "tren": 0, "duoi": 0}

    def tinh(self):
        """True nếu nội dung tĩnh ngoài vào/ra (dedup)"""
        return not self.anim.get("keyframes") and self.khoa_noi_dung(self.dur / 2) is None

    # ---- vị trí
    def khoi(self):
        """(x0, y0, w, h) px hộp nhìn thấy đã giải anchor/so_voi/vùng an toàn/không đè mặt"""
        if self._khoi is None:
            self._khoi = self._giai_vi_tri()
        return self._khoi

    def _diem_neo(self, w, h):
        v = self.vi_tri; W, H = self.ctx.W, self.ctx.H
        sv = v.get("so_voi", "khung"); x = float(v.get("x", 0.5)); y = float(v.get("y", 0.5))
        if sv == "khung":
            return x * W, y * H
        m = self.ctx.mat_tai(self.t0, self.t1)
        if not m:                             # 1.2.21: không có mặt → KHÔNG dùng mặt giả: báo khong_mat, neo theo khung tại (x, y)
            if not any(l.get("id") == "khong_mat" for l in self.loi):
                self.loi.append({"id": "khong_mat", "lop": self.id, "t": self.t0,
                                 "mo_ta": f"vi_tri.so_voi={sv} nhưng không có mặt trong {self.t0:.1f}–{self.t1:.1f}s (chưa quét mat.json hoặc không thấy mặt) — dùng so_voi=khung"})
            return x * W, y * H
        if v.get("theo_mat"):                 # khoảng cách tính theo CHIỀU CAO MẶT (x theo rộng mặt) — học từ mẫu, mặt to nhỏ khác vẫn đúng
            y = y * m["h"]
            if sv == "mat":
                x = x * m["w"]
        if sv == "mat":                       # x,y = lệch so với tâm mặt
            return (m["x"] + m["w"] / 2 + x) * W, (m["y"] + m["h"] / 2 + y) * H
        if sv == "duoi_cam":                  # y tính từ cằm xuống
            return x * W, (m["y1"] + y) * H
        if sv == "tren_dau":                  # y tính từ đỉnh đầu lên
            return x * W, (m["y0"] - y) * H
        return x * W, y * H

    def _giai_vi_tri(self):
        W, H = self.ctx.W, self.ctx.H
        vung = self.ctx.vung
        sx0, sy0 = vung["trai"] * W, vung["tren"] * H
        sx1, sy1 = (1 - vung["phai"]) * W, (1 - vung["duoi"]) * H
        ax, ay = ANCHOR.get(self.vi_tri.get("anchor", "mc"), (0.5, 0.5))
        px, py = self._diem_neo(0, 0)
        ti_le = 1.0
        if self.toan_khung:                   # 1.2.21: lớp toàn khung — không vùng an toàn, không né mặt, không thu
            self.ti_le = 1.0
            w, h = self.kich_thuoc()
            return (px - ax * w, py - ay * h, w, h)
        mat = self.ctx.mat_tai(self.t0, self.t1) if (self.spec.get("ne_mat", True) and not self.spec.get("sau_nguoi")) else None
        hop_mat = None
        if mat:
            hop_mat = hop_mat_noi(mat, W, H, self.ctx)
        # hướng được phép dời khi đè mặt: theo phía NEO của lớp (neo trên → chỉ lên; neo dưới → chỉ xuống; giữa → gần nhất)
        if ay <= 0.34:
            huong_duoc = ("len",)
        elif ay >= 0.66:
            huong_duoc = ("xuong",)
        else:
            huong_duoc = ("len", "xuong", "trai", "phai")
        cac_ti_le = [1.0]
        x0 = y0 = w = h = 0
        for lan in range(64):
            if lan >= len(cac_ti_le):
                break
            ti_le = cac_ti_le[lan]
            self.ti_le = ti_le
            w, h = self.kich_thuoc()
            x0, y0 = px - ax * w, py - ay * h
            # vùng an toàn: đẩy vào (nếu khối to hơn vùng thì căn theo cạnh gần anchor)
            nx0, ny0 = x0, y0
            if w <= sx1 - sx0:
                nx0 = min(max(x0, sx0), sx1 - w)
            if h <= sy1 - sy0:
                ny0 = min(max(y0, sy0), sy1 - h)
            if (abs(nx0 - x0) > 0.5 or abs(ny0 - y0) > 0.5) and lan == 0:
                self.may_sua.append({"lop": self.id, "sua": "vung_an_toan", "tu": [round(x0), round(y0)], "toi": [round(nx0), round(ny0)]})
            x0, y0 = nx0, ny0
            if not (hop_mat and self._de(x0, y0, w, h, hop_mat)):
                if lan > 0:
                    self.may_sua.append({"lop": self.id, "sua": "thu", "ti_le": ti_le, "tu": 1.0, "toi": ti_le, "mo_ta": f"thu ×{ti_le} để không che mặt"})
                break
            cu = {"xuong": (x0, hop_mat[3] + 4), "len": (x0, hop_mat[1] - h - 4), "phai": (hop_mat[2] + 4, y0), "trai": (hop_mat[0] - w - 4, y0)}
            cu = [(abs(cx - x0) + abs(cy - y0), ten, cx, cy) for ten, (cx, cy) in cu.items() if ten in huong_duoc
                  and sx0 - 0.5 <= cx and cx + w <= sx1 + 0.5 and sy0 - 0.5 <= cy and cy + h <= sy1 + 0.5]
            if cu:
                cu.sort()
                _, ten, cx, cy = cu[0]
                self.may_sua.append({"lop": self.id, "sua": "doi_khoi_mat", "huong": ten, "tu": [round(x0), round(y0)], "toi": [round(cx), round(cy)],
                                     "mo_ta": f"dời {ten} khỏi mặt" + (f" (thu ×{ti_le})" if ti_le < 1 else "")})
                x0, y0 = cx, cy
                break
            # 1.2.21: có thu hay không và thu tới đâu do KÊNH quyết (quyet_dinh ne_mat.thu_toi; 1.0 = không thu, chỉ báo) — bước ×0.9
            if lan == 0:
                thu_toi = float(self.quyet("ne_mat.thu_toi"))
                r = 1.0
                while r * 0.9 >= thu_toi - 1e-6 and r > thu_toi + 1e-6:
                    r = round(r * 0.9, 4); cac_ti_le.append(r)
                if thu_toi < 1.0 - 1e-6 and (not cac_ti_le[1:] or cac_ti_le[-1] > thu_toi + 1e-6):
                    cac_ti_le.append(round(thu_toi, 4))
            if lan == len(cac_ti_le) - 1:
                if ti_le < 1.0:                           # thu rồi vẫn đè → ĐẶT LẠI 1.0 (không để lớp bé đi vô ích), chỉ báo lỗi
                    self.ti_le = 1.0
                    w, h = self.kich_thuoc()
                    x0, y0 = px - ax * w, py - ay * h
                    if w <= sx1 - sx0:
                        x0 = min(max(x0, sx0), sx1 - w)
                    if h <= sy1 - sy0:
                        y0 = min(max(y0, sy0), sy1 - h)
                self.loi.append({"id": "de_mat", "lop": self.id, "t": self.t0,
                                 "mo_ta": f"khối che mặt (mắt–cằm), không dời về phía neo được (đã thử thu tới ×{min(cac_ti_le):.2f} theo ne_mat.thu_toi) — đổi vi_tri (neo phía khác) hoặc bớt chữ"})
        return (x0, y0, w, h)

    @staticmethod
    def _de(x0, y0, w, h, m):
        return not (x0 + w <= m[0] or x0 >= m[2] or y0 + h <= m[1] or y0 >= m[3])

    def hop(self):
        """(x0,y0,x1,y1) px hộp sprite = khối + lề nội dung + lề chuyển động (int)"""
        if self._hop is None:
            x0, y0, w, h = self.khoi()
            le = self.le_noi_dung()
            bd = _anim.bien_do(self.anim, self.n_phan)
            so_le = float(self.anim.get("so_le") or 0) if self.n_phan > 1 else 0
            mx = bd["x"] + bd["blur"] * 3 + (bd["scale"] - 1) * w / 2 + 2
            my = bd["y"] + bd["blur"] * 3 + (bd["scale"] - 1) * h / 2 + 2
            if bd.get("rot3d"):               # phối cảnh: cạnh gần phóng to → nới hộp
                mx += w * 0.35 + 8; my += h * 0.35 + 8
            vet = _anim.vet_nhoe_toi_da(self.anim, self.ctx.fps)      # 1.2.20: nhoè theo hướng → vệt kéo ra ngoài khối
            if vet > 0:
                mx += vet + 2; my += vet + 2
            if self.tween:
                mx += abs(self.tween[0]); my += abs(self.tween[1])
            hx0 = math.floor(x0 - le["trai"] - mx); hy0 = math.floor(y0 - le["tren"] - my)
            hx1 = math.ceil(x0 + w + le["phai"] + mx); hy1 = math.ceil(y0 + h + le["duoi"] + my)
            # cắt trong khung (dư ra ngoài vô ích) nhưng giữ ít nhất 1 px
            hx0 = max(hx0, -int(mx) - 4); hy0 = max(hy0, -int(my) - 4)
            hx1 = min(hx1, self.ctx.W + int(mx) + 4); hy1 = min(hy1, self.ctx.H + int(my) + 4)
            self._hop = (hx0, hy0, max(hx1, hx0 + 1), max(hy1, hy0 + 1))
        return self._hop

    # ---- trạng thái
    def trang_thai(self, lt):
        tt = _anim.trang_thai(self.anim, lt, self.dur)
        if self.tween and lt < self.tween[2]:
            u = _anim.ease("out", lt / self.tween[2])
            tt["x"] += self.tween[0] * (1 - u); tt["y"] += self.tween[1] * (1 - u)
        return tt

    def khoa(self, lt):
        """khoá khung: giống nhau ⇒ không cần vẽ lại"""
        dong = _anim.dang_chuyen_dong(self.anim, lt, self.dur, self.n_phan) or (self.tween and lt < self.tween[2])
        return (self.khoa_noi_dung(lt), round(lt * self.ctx.fps) if dong else None)

    # ---- vẽ
    def ve(self, lt, tra_skia=False, tra_bgra=False):
        """→ np.uint8 RGBA thẳng (h,w,4) kích thước hộp (tra_bgra=True: BGRA — đường nhanh cho PNG)"""
        hx0, hy0, hx1, hy1 = self.hop()
        x0, y0, w, h = self.khoi()
        tt = self.trang_thai(lt)
        surf = skia.Surface(hx1 - hx0, hy1 - hy0)
        c = surf.getCanvas(); c.clear(skia.Color4f(0, 0, 0, 0))
        if tt["opacity"] > 0.001 and tt["scale"] > 0.001:
            img, (dx, dy) = self.noi_dung(lt)
            ax, ay = ANCHOR.get(self.vi_tri.get("anchor", "mc"), (0.5, 0.5))
            cx, cy = x0 - hx0 + ax * w, y0 - hy0 + ay * h       # điểm neo trong hộp
            c.translate(tt["x"], tt["y"])
            bien_doi = tt["scale"] != 1.0 or tt["rot"] != 0.0
            if bien_doi:
                c.translate(cx, cy); c.rotate(tt["rot"]); c.scale(tt["scale"], tt["scale"]); c.translate(-cx, -cy)
            if tt["wipe"] < 1.0:
                c.clipRect(skia.Rect.MakeLTRB(x0 - hx0 - 1000, y0 - hy0 - 1000, x0 - hx0 + w * tt["wipe"], y0 - hy0 + h + 1000))
            paint = skia.Paint(); paint.setAlphaf(tt["opacity"] * self.do_trong)
            if tt["blur"] > 0.01:
                paint.setImageFilter(skia.ImageFilters.Blur(tt["blur"] / 2, tt["blur"] / 2))
            px, py = x0 - hx0 - dx, y0 - hy0 - dy
            if bien_doi and tt["wipe"] >= 1.0 and img.width() * img.height() > 300000:
                # ảnh lớn xoay/phóng: Skia CPU ~200 ms/khung → cv2.warpAffine (cùng ma trận), rồi vẽ không biến đổi
                import math as _m
                a_ = _m.radians(tt["rot"]); s_ = tt["scale"]
                M = np.array([[1, 0, tt["x"] + cx], [0, 1, tt["y"] + cy], [0, 0, 1]], np.float64) @                     np.array([[_m.cos(a_) * s_, -_m.sin(a_) * s_, 0], [_m.sin(a_) * s_, _m.cos(a_) * s_, 0], [0, 0, 1]]) @                     np.array([[1, 0, px - cx], [0, 1, py - cy], [0, 0, 1]])
                src = img.toarray(colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
                dst = cv2.warpAffine(src, M[:2], (hx1 - hx0, hy1 - hy0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
                c.resetMatrix()
                c.drawImage(skia.Image.fromarray(np.ascontiguousarray(dst), skia.kBGRA_8888_ColorType, skia.kPremul_AlphaType), 0, 0, _SAMP_NONE, paint)
            elif bien_doi:          # scale/xoay: linear (cubic Mitchell ~100 ms / khung 800×250 trên máy yếu; linear khác biệt không thấy)
                c.drawImage(img, px, py, _SAMP_LIN_NM, paint)
            elif abs(tt["x"] - round(tt["x"])) > 1e-3 or abs(tt["y"] - round(tt["y"])) > 1e-3:
                c.drawImage(img, px, py, skia.SamplingOptions(skia.FilterMode.kLinear), paint)   # dịch lẻ pixel: linear đủ đẹp, rẻ
            else:
                c.drawImage(img, round(px), round(py), _SAMP_NONE, paint)
        out = surf.makeImageSnapshot()
        k_nhoe = _anim.he_so_nhoe_dong(self.anim)
        if k_nhoe > 0 and tt["opacity"] > 0.001 and not getattr(self, "tach", None):
            vx, vy = _anim.van_toc(self.anim, lt, self.dur, self.ctx.fps)
            if self.tween and lt < self.tween[2]:
                vx, vy = vx, vy          # tween phụ đề: không nhoè (dịch nhỏ)
            out = nhoe_theo_huong(out, vx * k_nhoe, vy * k_nhoe)
        rx, ry = float(tt.get("rot_x", 0) or 0), float(tt.get("rot_y", 0) or 0)
        if (abs(rx) > 0.05 or abs(ry) > 0.05) and tt["opacity"] > 0.001:
            out = _phoi_canh(out, rx, ry, x0 - hx0 + ax * w + tt["x"], y0 - hy0 + ay * h + tt["y"], max(self.ctx.W, self.ctx.H) * 1.1)
        if tra_skia:
            return out
        return numpy_bgra_tu_skia(out) if tra_bgra else numpy_tu_skia(out)


def nhoe_theo_huong(img, dx, dy):
    """1.2.20: nhoè CHUYỂN ĐỘNG theo vectơ (dx, dy) px — nhân chập đường thẳng (box) dài |v| trên ảnh premul, giữ nguyên kích thước ảnh
    (hộp sprite đã nới sẵn). |v| < 1.5 px → trả nguyên (không tốn)."""
    L = math.hypot(dx, dy)
    if L < 1.5:
        return img
    L = min(L, _anim.MAC_DINH["nhoe_dong_toi_da"])
    n = int(math.ceil(L)) | 1
    k = np.zeros((n, n), np.float32)
    cx = cy = n // 2
    ux, uy = dx / math.hypot(dx, dy), dy / math.hypot(dx, dy)
    # vẽ đoạn thẳng qua tâm, dài L, chống răng cưa bằng chia nhỏ bước 0.5 px
    m = int(L * 2) + 1
    for i in range(m):
        s = -L / 2 + L * i / max(m - 1, 1)
        x, y = cx + ux * s, cy + uy * s
        x0, y0 = int(math.floor(x)), int(math.floor(y))
        fx, fy = x - x0, y - y0
        for (xx, yy, w_) in ((x0, y0, (1 - fx) * (1 - fy)), (x0 + 1, y0, fx * (1 - fy)), (x0, y0 + 1, (1 - fx) * fy), (x0 + 1, y0 + 1, fx * fy)):
            if 0 <= xx < n and 0 <= yy < n:
                k[yy, xx] += w_
    k /= max(k.sum(), 1e-6)
    a = img.toarray(colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
    b = cv2.filter2D(a, -1, k, borderType=cv2.BORDER_CONSTANT)
    return skia.Image.fromarray(np.ascontiguousarray(b), skia.kBGRA_8888_ColorType, skia.kPremul_AlphaType)


def _phoi_canh(img, rot_x, rot_y, cx, cy, f):
    """xoay sprite quanh trục ngang (rot_x) / dọc (rot_y) qua tâm (cx, cy) với tiêu cự f → ảnh cùng cỡ (phối cảnh 3D một mặt phẳng)"""
    import math as _m
    src = img.toarray(colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
    Hh, Ww = src.shape[:2]
    ax_, ay_ = _m.radians(rot_x), _m.radians(rot_y)
    Rx = np.array([[1, 0, 0], [0, _m.cos(ax_), -_m.sin(ax_)], [0, _m.sin(ax_), _m.cos(ax_)]])
    Ry = np.array([[_m.cos(ay_), 0, _m.sin(ay_)], [0, 1, 0], [-_m.sin(ay_), 0, _m.cos(ay_)]])
    goc = np.array([[0, 0], [Ww, 0], [Ww, Hh], [0, Hh]], np.float64)
    p3 = np.c_[goc - [cx, cy], np.zeros(4)] @ (Rx @ Ry).T
    z = f + p3[:, 2]
    if np.any(z <= 1):
        return img
    proj = p3[:, :2] * (f / z)[:, None] + [cx, cy]
    M = cv2.getPerspectiveTransform(goc.astype(np.float32), proj.astype(np.float32))
    dst = cv2.warpPerspective(src, M, (Ww, Hh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    return skia.Image.fromarray(np.ascontiguousarray(dst), skia.kBGRA_8888_ColorType, skia.kPremul_AlphaType)


def _noi_3d(img, kd, ti_le=1.0):
    """chữ nổi khối: vẽ `sau` bản sao tô màu `mau` lệch dần theo góc `goc` (độ, 0 = phải, 90 = xuống) rồi chữ gốc lên trên.
    → (ảnh mới, dx, dy) với (dx, dy) = gốc ảnh cũ nằm ở đâu trong ảnh mới."""
    n3 = kd.get("noi_3d") if isinstance(kd.get("noi_3d"), dict) else None
    if not n3:
        return img, 0, 0
    import math as _m
    sau = int(round(float(n3.get("sau", 0) or 0) * ti_le))
    if sau <= 0:
        return img, 0, 0
    goc = _m.radians(float(n3.get("goc", 45) or 0))
    ux, uy = _m.cos(goc), _m.sin(goc)
    r_, g_, b_, a_ = _chu.mau(n3.get("mau"), (0, 0, 0, 170))
    m2 = _chu.mau(n3["mau2"], (r_, g_, b_, a_)) if n3.get("mau2") else None     # 1.2.20: màu cạnh XA (chuyển sắc gần→xa theo độ sâu)
    W_, H_ = img.width(), img.height()
    ox = int(_m.ceil(sau * max(0.0, -ux))); oy = int(_m.ceil(sau * max(0.0, -uy)))
    surf = skia.Surface(W_ + sau + 2, H_ + sau + 2); c = surf.getCanvas(); c.clear(skia.Color4f(0, 0, 0, 0))
    paint = skia.Paint(); paint.setColorFilter(skia.ColorFilters.Blend(skia.ColorSetARGB(a_, r_, g_, b_), skia.BlendMode.kSrcIn))
    buoc = 1.0 if sau <= 24 else sau / 24.0                   # tối đa ~24 lát: mắt không phân biệt, vẽ nhanh
    i = float(sau)
    while i > 0.0:
        if m2:
            q = i / float(sau)                                 # 0 = sát mặt chữ, 1 = xa nhất
            goc_ = (r_, g_, b_, a_)
            col = [max(0, min(255, int(round(goc_[j] + (m2[j] - goc_[j]) * q)))) for j in range(4)]   # 1.2.20: pha từng kênh, kẹp 0..255
            paint.setColorFilter(skia.ColorFilters.Blend(skia.ColorSetARGB(col[3], col[0], col[1], col[2]), skia.BlendMode.kSrcIn))
        c.drawImage(img, ox + ux * i, oy + uy * i, _SAMP_LIN_NM, paint)
        i -= buoc
    c.drawImage(img, ox, oy, _SAMP_NONE)
    return surf.makeImageSnapshot(), ox, oy


def _le_noi_3d(kd, le, ti_le=1.0):
    n3 = kd.get("noi_3d") if isinstance(kd.get("noi_3d"), dict) else None
    if n3 and float(n3.get("sau", 0) or 0) > 0:
        sau = float(n3["sau"]) * ti_le + 2
        for k in le:
            le[k] = float(le[k]) + sau
    return le


# ======================================================================== chu ====
class LopChu(Lop):
    kieu = "chu"

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        nd = spec.get("noi_dung") or {}
        self.text = nd.get("text", "") if isinstance(nd, dict) else str(nd)
        # 1.2.21: kiểu dáng thiếu → quyet_dinh["chu"] (co/dam/dong/can/mau/vien/bong/font) — không còn mặc định trong máy
        self.kd = kd_tu_quyet(self.kd, ctx, "chu", lop=self.id)
        self.kd["font"] = ctx.font_file(self.kd.get("font") or quyet(ctx, "chu.font", "tieu_de", lop=self.id))
        self.tach = self.anim.get("tach") if self.anim.get("tach") in ("tu", "ky_tu") else None
        if (self.anim.get("vao") or {}).get("kieu") == "typewriter" and not self.tach:
            self.tach = "ky_tu"
        self.noi_tai = None               # callable lt → chỉ số từ đang nói (karaoke)
        self.hien_dan = False             # phụ đề hiện DẦN theo lời: từ chưa nói tới thì ẩn (word_by_word của mẫu)
        self.to_noi = True                # tô màu từ đang nói (karaoke); False → chỉ dùng chỉ số từ để hiện dần
        self._kd0 = dict(self.kd)
        self._rm0 = self.kd.get("rong_max", (self.vi_tri.get("w") if self.vi_tri.get("w") else None))
        if self._rm0 is None:
            self._rm0 = quyet(ctx, "chu.rong_max", lop=self.id)      # 1.2.21: bề rộng xếp dòng mặc định do kênh quyết (§1c chu.rong_max)
        self._cache = CacheAnh("LopChu." + str(self.id))
        self.n_phan = _chu.so_phan(self.text, self._kd_hien(), self._rong_max(), self.tach, ctx.W) if self.tach else 1

    def _kd_hien(self):
        kd = dict(self._kd0)
        if self.ti_le != 1.0:
            kd["co"] = float(kd["co"]) * self.ti_le
        kd.pop("rong_max", None)
        return kd

    def _rong_max(self):
        rm = self._rm0
        if rm is None or self.toan_khung and self.vi_tri.get("w") is None:
            return float(self.ctx.W)
        rm = float(rm) * self.ctx.W if float(rm) <= 1 else float(rm)
        return rm * self.ti_le

    def _ghi_thieu_dau(self, meta):
        """1.2.21: font thiếu glyph tiếng Việt → may_sua font_thieu_dau (họ dự phòng nào đã dùng) thay vì lặng lẽ"""
        td = (meta or {}).get("thieu_glyph")
        if td and not any(m.get("sua") == "font_thieu_dau" and m.get("font") == td.get("font") for m in self.may_sua):
            self.may_sua.append(dict({"lop": self.id, "sua": "font_thieu_dau"}, **td))

    def kich_thuoc(self):
        return _chu.do_kich_thuoc(self.text, self._kd_hien(), self._rong_max(), self.ctx.W)

    def le_noi_dung(self):
        return _le_noi_3d(self._kd_hien(), _chu.le_kd(self._kd_hien()), self.ti_le)

    def khoa_noi_dung(self, lt):
        k = []
        if self.noi_tai:
            k.append(("noi", self.noi_tai(lt)))
        if self.tach:
            so_le = float(self.anim.get("so_le") or 0)
            dv, dr = _anim.dai_vao_ra(self.anim)
            if lt < dv + so_le * self.n_phan or lt > self.dur - dr or self.anim.get("keyframes"):
                k.append(("tach", round(lt * self.ctx.fps)))
        return tuple(k) if k else None

    def trang_thai(self, lt):
        tt = super().trang_thai(lt)
        if self.tach:      # vào/ra/scale/opacity/x/y xử lý từng phần trong chu.ve_chu; lớp chỉ giữ rot/blur/wipe/tween
            cu = tt
            tt = dict(_anim.TRANG_THAI_GOC); tt["rot"], tt["blur"], tt["wipe"] = cu["rot"], cu["blur"], cu["wipe"]
            tt["rot_x"], tt["rot_y"] = cu.get("rot_x", 0.0), cu.get("rot_y", 0.0)
            if self.tween and lt < self.tween[2]:
                u = _anim.ease("out", lt / self.tween[2]); tt["x"] += self.tween[0] * (1 - u); tt["y"] += self.tween[1] * (1 - u)
        return tt

    def noi_dung(self, lt):
        noi = self.noi_tai(lt) if self.noi_tai else None
        phan_tt = None
        if self.tach:
            phan_tt = _anim.trang_thai_phan(self.anim, self.n_phan, lt, self.dur)
            key = ("tach", round(lt * self.ctx.fps), noi) if self.khoa_noi_dung(lt) else ("tinh", noi)
            if key[0] == "tinh":
                phan_tt = None
        else:
            key = ("tinh", noi)
        r = self._cache.get(key)
        if r is None:
            img, meta = _chu.ve_chu(self.text, self._kd_hien(), self.ctx.W, self.ctx.H, self._rong_max(), tach=self.tach,
                                   phan_tt=phan_tt, noi=(noi if self.to_noi else None), tra_skia=True, an_sau=(noi if (self.hien_dan and noi is not None) else None))
            self._ghi_thieu_dau(meta)
            kx0, ky0, _, _ = meta["khoi"]
            img, ox3, oy3 = _noi_3d(img, self._kd_hien(), self.ti_le)
            r = (img, (kx0 + ox3, ky0 + oy3))
            self._cache[key] = r
        return r


# ======================================================================== khoi ====
class LopKhoi(Lop):
    """khối chữ NHIỀU DÒNG, mỗi dòng kiểu dáng riêng (font, cỡ, màu, đậm, nghiêng, HOA, viền, bóng, gradient, nền) — tiêu đề trộn font
    (dòng dẫn mảnh + từ khoá đậm + từ cảm xúc script), dòng chồng sát (cach_dong < 1), lệch so le (lech). noi_dung.dong = [{text, kieu_dang, lech}];
    kieu_dang{can trai|giua|phai, cach_dong, rong_max}. anim.tach = "dong": từng dòng vào so le (so_le)."""
    kieu = "khoi"

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        nd = spec.get("noi_dung") or {}
        self.dong = []
        for d in nd.get("dong") or []:
            if not isinstance(d, dict) or not str(d.get("text") or "").strip():
                continue
            kd = kd_tu_quyet(dict(d.get("kieu_dang") or {}), ctx, "chu", lop=self.id)     # 1.2.21: dòng thiếu co/dam/dong/can → quyet_dinh["chu"]
            kd["font"] = ctx.font_file(kd.get("font") or quyet(ctx, "chu.font", "tieu_de", lop=self.id))
            kd.pop("rong_max", None)
            # 1.2.20: mỗi dòng có thể xoay (độ), lệch tuyệt đối dx/dy (px@1080), trễ vào riêng (tre, giây) và anim vào/ra riêng
            an_d = d.get("anim") if isinstance(d.get("anim"), dict) else (kd.pop("anim", None) if isinstance(kd.get("anim"), dict) else None)
            self.dong.append({"text": str(d["text"]), "kd": kd, "lech": float(d.get("lech", 0) or 0),
                              "xoay": float(d.get("xoay", kd.pop("xoay", 0)) or 0), "dx": float(d.get("dx", kd.pop("dx", 0)) or 0),
                              "dy": float(d.get("dy", kd.pop("dy", 0)) or 0), "tre": max(0.0, float(d.get("tre", kd.pop("tre", 0)) or 0)),
                              "anim": an_d})
        self.can = self.kd.get("can") if self.kd.get("can") in ("trai", "giua", "phai") else quyet(ctx, "chu.can", lop=self.id)
        self.cach_dong = float(self.kd.get("cach_dong") or quyet(ctx, "khoi.cach_dong", lop=self.id))   # 1.2.21: khối chồng sát do kênh quyết (§1c khoi)
        self._rm0 = self.kd.get("rong_max")
        if self._rm0 is None:
            self._rm0 = quyet(ctx, "chu.rong_max", lop=self.id)
        self.tach = "dong" if self.anim.get("tach") == "dong" and (len(self.dong) > 1 or any(d["anim"] or d["tre"] for d in self.dong)) else None
        self.n_phan = len(self.dong) if self.tach else 1
        self._bc_cache = {}
        self._cache = CacheAnh("LopKhoi." + str(self.id))

    def _anim_dong(self, i):
        """anim hợp nhất cho dòng i: anim của lớp + ghi đè vao/ra/nhoe_dong riêng của dòng"""
        a = self.anim
        r = self.dong[i]["anim"]
        if not r:
            return a
        m = dict(a)
        for k in ("vao", "ra", "nhoe_dong"):
            if k in r:
                m[k] = r[k]
        return _anim.day_du(m, getattr(self.ctx, "quyet_dinh", None), lop=self.id)

    def _tre_dong(self, i):
        so_le = float(self.anim.get("so_le") or 0)
        return i * so_le + self.dong[i]["tre"]

    def _dai_vao_ra_max(self):
        """(giây vào dài nhất kể cả trễ, giây ra dài nhất) trên mọi dòng"""
        dv = dr = 0.0
        for i in range(len(self.dong)):
            v, r = _anim.dai_vao_ra(self._anim_dong(i))
            dv = max(dv, v + self._tre_dong(i)); dr = max(dr, r)
        return dv, dr

    def _kd(self, i):
        kd = dict(self.dong[i]["kd"])
        if self.ti_le != 1.0:
            kd["co"] = float(kd["co"]) * self.ti_le
        return kd

    def _rong_max(self):
        rm = self._rm0
        if rm is None or self.toan_khung and self.vi_tri.get("w") is None:
            return float(self.ctx.W)
        rm = float(rm) * self.ctx.W if float(rm) <= 1 else float(rm)
        return rm * self.ti_le

    _ghi_thieu_dau = LopChu._ghi_thieu_dau

    def _bo_cuc(self):
        """→ ([(x, y, w, h) từng dòng trong khối], W_khoi, H_khoi)"""
        key = round(self.ti_le, 4)
        r = self._bc_cache.get(key)
        if r is not None:
            return r
        rm = self._rong_max()
        kt = [_chu.do_kich_thuoc(d["text"], self._kd(i), rm, self.ctx.W) for i, d in enumerate(self.dong)]
        bw = max([w for w, _ in kt] + [1.0])
        hop = []
        y = 0.0
        for i, (w, h) in enumerate(kt):
            if self.can == "trai":
                x = 0.0
            elif self.can == "phai":
                x = bw - w
            else:
                x = (bw - w) / 2
            d_ = self.dong[i]
            x += d_["lech"] * bw + d_["dx"] * self.ti_le
            hop.append((x, y + d_["dy"] * self.ti_le, w, h))
            y += h * (self.cach_dong if i < len(kt) - 1 else 1.0)
        # 1.2.20: khối bao = hợp các hộp dòng (kể cả dòng xoay → hộp bao của hình chữ nhật đã xoay, dòng dy âm/dương)
        xs, ys = [0.0, bw], [0.0, y]
        for i, (x, y_, w, h) in enumerate(hop):
            g = abs(math.radians(self.dong[i]["xoay"]))
            bw_, bh_ = (w * math.cos(g) + h * math.sin(g), w * math.sin(g) + h * math.cos(g)) if g else (w, h)
            cx_, cy_ = x + w / 2, y_ + h / 2
            xs += [cx_ - bw_ / 2, cx_ + bw_ / 2]; ys += [cy_ - bh_ / 2, cy_ + bh_ / 2]
        x_min, x_max, y_min, y_max = min(xs), max(xs), min(ys), max(ys)
        hop = [(x - x_min, y_ - y_min, w, h) for (x, y_, w, h) in hop]
        r = (hop, x_max - x_min, y_max - y_min)
        self._bc_cache[key] = r
        return r

    def kich_thuoc(self):
        _, w, h = self._bo_cuc()
        return (w, h)

    def le_noi_dung(self):
        le = {"trai": 0.0, "phai": 0.0, "tren": 0.0, "duoi": 0.0}
        for i in range(len(self.dong)):
            l = _le_noi_3d(self._kd(i), _chu.le_kd(self._kd(i)), self.ti_le)
            for k in le:
                le[k] = max(le[k], float(l[k]))
        return le

    def khoa_noi_dung(self, lt):
        if not self.tach:
            return None
        dv, dr = self._dai_vao_ra_max()
        if lt < dv + 1.0 / self.ctx.fps or lt > self.dur - dr or self.anim.get("keyframes"):
            return ("tach", round(lt * self.ctx.fps))
        return None

    def trang_thai(self, lt):
        tt = super().trang_thai(lt)
        if self.tach:      # vào/ra/scale/opacity/x/y từng dòng trong noi_dung; lớp chỉ giữ rot/blur/wipe/tween
            cu = tt
            tt = dict(_anim.TRANG_THAI_GOC); tt["rot"], tt["blur"], tt["wipe"] = cu["rot"], cu["blur"], cu["wipe"]
            tt["rot_x"], tt["rot_y"] = cu.get("rot_x", 0.0), cu.get("rot_y", 0.0)
            if self.tween and lt < self.tween[2]:
                u = _anim.ease("out", lt / self.tween[2]); tt["x"] += self.tween[0] * (1 - u); tt["y"] += self.tween[1] * (1 - u)
        return tt

    def noi_dung(self, lt):
        phan_tt = None; van_toc = None
        key = ("tinh",)
        if self.tach and self.khoa_noi_dung(lt):
            phan_tt = [_anim.trang_thai(self._anim_dong(i), lt, self.dur, tre=self._tre_dong(i)) for i in range(self.n_phan)]
            van_toc = [(_anim.van_toc(self._anim_dong(i), lt, self.dur, self.ctx.fps, tre=self._tre_dong(i)), _anim.he_so_nhoe_dong(self._anim_dong(i)))
                       for i in range(self.n_phan)]
            key = ("tach", round(lt * self.ctx.fps))
        r = self._cache.get(key)
        if r is not None:
            return r
        hop, bw, bh = self._bo_cuc()
        le = self.le_noi_dung()
        # 1.2.20: lề mặt chữ tràn hộp (dấu trên chữ HOA Ấ/Ộ/Ừ, chữ nghiêng) — ảnh từng dòng do ve_chu đã đệm (_pad_phan) nhưng khối
        # trước đây chỉ chừa lề viền/bóng → DÒNG ĐẦU bị cắt mất dấu phía trên (dòng sau có dòng trước làm chỗ). Lấy đệm lớn nhất các dòng.
        try:
            pads = [_chu._pad_phan(_chu._kd(self._kd(i), self.ctx.W)) for i in range(len(self.dong))]
        except Exception:
            pads = []
        pl = max([p[0] for p in pads] + [le["trai"]]); pr = max([p[1] for p in pads] + [le["phai"]])
        pt = max([p[2] for p in pads] + [le["tren"]]); pb = max([p[3] for p in pads] + [le["duoi"]])
        mx = my = 0.0; ms = 1.0
        for s in (phan_tt or []):
            mx = max(mx, abs(float(s.get("x", 0)))); my = max(my, abs(float(s.get("y", 0)))); ms = max(ms, float(s.get("scale", 1)))
        for i in range(len(self.dong)):                       # 1.2.20: vệt nhoè + xoay dòng tràn ra ngoài hộp dòng
            vet = _anim.vet_nhoe_toi_da(self._anim_dong(i), self.ctx.fps) if self.tach else 0.0
            mx = max(mx, vet); my = max(my, vet)
            if self.dong[i]["xoay"]:
                x_, y_, w_, h_ = hop[i]
                mx = max(mx, h_ * 0.5); my = max(my, w_ * 0.5)
        ox = pl + mx + (ms - 1) * bw / 2; oy = pt + my + (ms - 1) * bh / 2
        IW = int(math.ceil(bw + ox + pr + mx + (ms - 1) * bw / 2)); IH = int(math.ceil(bh + oy + pb + my + (ms - 1) * bh / 2))
        surf = skia.Surface(max(IW, 1), max(IH, 1)); c = surf.getCanvas(); c.clear(skia.Color4f(0, 0, 0, 0))
        for i, d in enumerate(self.dong):
            tt = (phan_tt[i] if phan_tt and i < len(phan_tt) else None) or {}
            op = float(tt.get("opacity", 1.0))
            if op <= 0.001:
                continue
            x, y, w, h = hop[i]
            img, meta = _chu.ve_chu(d["text"], self._kd(i), self.ctx.W, self.ctx.H, self._rong_max(), tra_skia=True)
            self._ghi_thieu_dau(meta)
            kx0, ky0, _, _ = meta["khoi"]
            img, ox3, oy3 = _noi_3d(img, self._kd(i), self.ti_le)
            kx0 += ox3; ky0 += oy3
            sc = float(tt.get("scale", 1.0)); tx = float(tt.get("x", 0)); ty = float(tt.get("y", 0))
            bl = float(tt.get("blur", 0) or 0); xo = float(tt.get("rot", 0) or 0) + d["xoay"]
            paint = skia.Paint(); paint.setAlphaf(min(op, 1.0))
            if bl > 0.01:
                paint.setImageFilter(skia.ImageFilters.Blur(bl / 2, bl / 2))
            if van_toc and i < len(van_toc) and van_toc[i][1] > 0:            # nhoè theo hướng riêng từng dòng
                (vx, vy), k_ = van_toc[i]
                img = nhoe_theo_huong(img, vx * k_, vy * k_)
            c.save()
            cx = ox + x + w / 2 + tx; cy = oy + y + h / 2 + ty
            if sc != 1.0 or xo:
                c.translate(cx, cy); c.rotate(xo); c.scale(sc, sc); c.translate(-cx, -cy)
                c.drawImage(img, ox + x - kx0 + tx, oy + y - ky0 + ty, _SAMP_LIN_NM, paint)
            else:
                c.drawImage(img, round(ox + x - kx0 + tx), round(oy + y - ky0 + ty), _SAMP_NONE, paint)
            c.restore()
        r = (surf.makeImageSnapshot(), (ox, oy))
        self._cache[key] = r
        return r


# ======================================================================== the ====
class LopThe(Lop):
    kieu = "the"

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        nd = spec.get("noi_dung") or {}
        self.text = nd.get("text", "")
        self.icon = ctx.tai_nguyen(nd.get("icon")) if nd.get("icon") else None
        # 1.2.21: thẻ thiếu hình/màu/bo/đệm/bóng/chữ → quyet_dinh["the"] (§1c) — không còn pill #111111CC / 48 / 700 trong máy
        kd = dien_tu_quyet(self.kd, ctx, {"hinh": "the.hinh", "mau": "the.mau", "bo": "the.bo", "dem": "the.dem"}, "the", lop=self.id)
        if "bong" not in kd:
            kd["bong"] = quyet(ctx, "the.bong", None, lop=self.id)
        if "vien" not in kd:
            kd["vien"] = quyet(ctx, "the.vien", None, lop=self.id)
        self.kd = kd
        self.kd_chu = dien_tu_quyet(kd.get("chu") or {}, ctx, {"co": "the.chu.co", "mau": "the.chu.mau", "dam": "the.chu.dam", "font": "the.chu.font"}, "the.chu", lop=self.id)
        for k in ("vien", "bong", "gradient"):                     # viền/bóng chữ thẻ: the.chu.<k> (tuỳ chọn), không lấy của chữ tiêu đề
            self.kd_chu.setdefault(k, quyet(ctx, "the.chu." + k, None, lop=self.id))
        self.kd_chu = kd_tu_quyet(self.kd_chu, ctx, "chu", lop=self.id)      # dong/can còn thiếu → chu.dong/chu.can
        self.kd_chu["font"] = ctx.font_file(self.kd_chu["font"])
        self.kd_chu.pop("nen", None)
        d = kd["dem"]; d = [d, d] if isinstance(d, (int, float)) else d
        self.dem = (float(d[0]), float(d[1]))
        self.hinh = kd["hinh"]
        self._img = None
        self._icon_img = None
        if self.icon:
            a = doc_anh(self.icon)
            if a is not None:
                self._icon_img = anh_skia_tu_numpy(a, bgra=True)

    def _kd_chu(self):
        kd = dict(self.kd_chu)
        if self.ti_le != 1:
            kd["co"] = float(kd["co"]) * self.ti_le
        return kd

    def _bo_cuc(self):
        kd = self._kd_chu()
        rm = float(self.vi_tri["w"]) * self.ctx.W - 2 * self.dem[0] if self.vi_tri.get("w") else None
        tw, th = _chu.do_kich_thuoc(self.text, kd, rm, self.ctx.W) if self.text else (0.0, 0.0)
        ih = th if self._icon_img is not None else 0.0
        iw = ih * self._icon_img.width() / self._icon_img.height() if self._icon_img is not None else 0.0
        kh = (iw + (th * 0.3 if iw and tw else 0)) if iw else 0.0
        w = tw + kh + 2 * self.dem[0]; h = max(th, ih) + 2 * self.dem[1]
        if self.hinh == "circle":
            w = h = max(w, h)
        if self.vi_tri.get("w"):
            w = max(w, float(self.vi_tri["w"]) * self.ctx.W)
        if self.vi_tri.get("h"):
            h = max(h, float(self.vi_tri["h"]) * self.ctx.H)
        return w, h, tw, th, iw, ih, kd

    def kich_thuoc(self):
        w, h, *_ = self._bo_cuc()
        return (w, h)

    def le_noi_dung(self):
        le = {"trai": 2.0, "phai": 2.0, "tren": 2.0, "duoi": 2.0}
        v = float((self.kd.get("vien") or {}).get("w", 0))
        for b in self.kd.get("bong") or []:
            mo = float(b.get("mo", 0)) * 1.5
            le["trai"] = max(le["trai"], abs(float(b.get("x", 0))) + mo); le["phai"] = le["trai"]
            le["tren"] = max(le["tren"], abs(float(b.get("y", 0))) + mo); le["duoi"] = le["tren"]
        for k in le:
            le[k] += v
        return le

    def noi_dung(self, lt):
        if self._img is None:
            w, h, tw, th, iw, ih, kd = self._bo_cuc()
            le = self.le_noi_dung()
            IW, IH = int(math.ceil(w + le["trai"] + le["phai"])), int(math.ceil(h + le["tren"] + le["duoi"]))
            surf = skia.Surface(IW, IH); c = surf.getCanvas(); c.clear(skia.Color4f(0, 0, 0, 0))
            ox, oy = le["trai"], le["tren"]
            nen = {"mau": self.kd["mau"], "bo": self.kd["bo"], "hinh": self.hinh, "vien": self.kd.get("vien"),
                   "bong": self.kd.get("bong"), "gradient": self.kd.get("gradient")}
            _chu.ve_khoi(c, (ox, oy, ox + w, oy + h), nen)
            noi_w = iw + (th * 0.3 if iw and tw else 0) + tw
            x = ox + (w - noi_w) / 2; y = oy + (h - max(th, ih)) / 2
            if self._icon_img is not None and iw:
                c.drawImageRect(self._icon_img, skia.Rect.MakeXYWH(x, oy + (h - ih) / 2, iw, ih), _SAMP_CUBIC)
                x += iw + th * 0.3
            if self.text:
                img, meta = _chu.ve_chu(self.text, kd, self.ctx.W, self.ctx.H, None, tra_skia=True)
                LopChu._ghi_thieu_dau(self, meta)
                kx0, ky0, _, _ = meta["khoi"]
                c.drawImage(img, round(x - kx0), round(y - ky0), _SAMP_NONE)
            self._img = (surf.makeImageSnapshot(), (ox, oy))
        return self._img


# ======================================================================== hinh ====
class LopHinh(Lop):
    kieu = "hinh"

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        nd = spec.get("noi_dung") or {}
        p = ctx.tai_nguyen(nd.get("duong_giai")) or ctx.tai_nguyen(nd.get("duong") or nd.get("id") or nd.get("src"))
        self.path = p
        self._src = None
        if p:
            a = doc_anh(p)
            if a is not None:
                self._src = anh_skia_tu_numpy(a, bgra=True)
        if self._src is None:
            self.loi.append({"id": "tai_nguyen_khong_co", "lop": self.id, "t": self.t0, "mo_ta": "không đọc được ảnh: %s" % (nd.get("duong") or nd.get("id"))})
        self.fit = self.kd.get("fit", "cover")
        self.kb = (self.anim.get("ken_burns") or self.kd.get("ken_burns"))
        self._cache = {}

    def kich_thuoc(self):
        W, H = self.ctx.W, self.ctx.H
        w = float(self.vi_tri["w"]) * W if self.vi_tri.get("w") else None
        h = float(self.vi_tri["h"]) * H if self.vi_tri.get("h") else None
        ar = (self._src.width() / self._src.height()) if self._src is not None else 1.0
        if w is None and h is None:                           # 1.2.21: hộp mặc định do kênh quyết (vi_tri.hop_mac_dinh.hinh = [w, h] tỉ lệ khung)
            hm = quyet(self.ctx, "vi_tri.hop_mac_dinh.hinh", lop=self.id)
            w = float(hm[0]) * W
            h_max = float(hm[1]) * H if len(hm) > 1 and hm[1] else None
            h = w / ar
            if h_max and h > h_max:                           # giữ tỉ lệ ảnh, không vượt chiều cao hộp mặc định
                h = h_max; w = h * ar
        if w is None:
            w = h * ar
        if h is None:
            h = w / ar
        if self.fit == "contain" and self._src is not None:   # hộp co theo ảnh
            s = min(w / self._src.width(), h / self._src.height())
            w, h = self._src.width() * s, self._src.height() * s
        return (w * self.ti_le, h * self.ti_le)

    def le_noi_dung(self):
        v = float((self.kd.get("vien") or {}).get("w", 0))
        le = {"trai": v + 2, "phai": v + 2, "tren": v + 2, "duoi": v + 2}
        for b in self.kd.get("bong") or []:
            mo = float(b.get("mo", 0)) * 1.5
            le["trai"] = max(le["trai"], abs(float(b.get("x", 0))) + mo + v); le["phai"] = le["trai"]
            le["tren"] = max(le["tren"], abs(float(b.get("y", 0))) + mo + v); le["duoi"] = le["tren"]
        return le

    def _zoom(self, lt):
        if not self.kb:
            return 1.0
        z = self.kb.get("z", [1.0, 1.0])
        u = min(max(lt / self.dur, 0), 1)
        return float(z[0]) + (float(z[1]) - float(z[0])) * _anim.ease(self.kb.get("ease", "linear"), u)

    def khoa_noi_dung(self, lt):
        return round(lt * self.ctx.fps) if self.kb else None

    def _chuan_bi(self):
        """vẽ 1 lần: lớp bóng (tĩnh) + ảnh nguồn đã thu về cỡ cần (zoom lớn nhất) để mỗi khung chỉ drawImage rẻ"""
        if getattr(self, "_san", None) is not None:
            return self._san
        w, h = self.kich_thuoc(); le = self.le_noi_dung()
        IW, IH = int(math.ceil(w + le["trai"] + le["phai"])), int(math.ceil(h + le["tren"] + le["duoi"]))
        ox, oy = le["trai"], le["tren"]
        rect = skia.Rect.MakeXYWH(ox, oy, w, h)
        bo = float(self.kd.get("bo", 0)); rr = skia.RRect.MakeRectXY(rect, bo, bo)
        bong = None
        if self.kd.get("bong"):
            surf = skia.Surface(max(IW, 1), max(IH, 1)); c = surf.getCanvas(); c.clear(skia.Color4f(0, 0, 0, 0))
            for b in self.kd.get("bong") or []:
                mo = float(b.get("mo", 0)); lp = skia.Paint()
                if mo > 0:
                    lp.setImageFilter(skia.ImageFilters.Blur(mo / 2, mo / 2))
                c.saveLayer(None, lp); c.translate(float(b.get("x", 0)), float(b.get("y", 0)))
                p = skia.Paint(AntiAlias=True); p.setColor(_chu.mau_skia(b.get("mau", "#0008"))); c.drawRRect(rr, p); c.restore()
            bong = surf.makeImageSnapshot()
        src = None
        if self._src is not None:
            zmax = max([1.0] + [float(z) for z in (self.kb or {}).get("z", [1.0])])
            sw, sh = self._src.width(), self._src.height()
            s = (max(w / sw, h / sh) if self.fit == "cover" else min(w / sw, h / sh)) * zmax
            dw, dh = max(1, int(round(sw * s))), max(1, int(round(sh * s)))
            src = self._src.resize(dw, dh, _SAMP_CUBIC if s > 1 else _SAMP_LIN) if (dw, dh) != (sw, sh) else self._src
            src = (src, zmax)
        self._san = (IW, IH, ox, oy, rr, bong, src)
        return self._san

    def noi_dung(self, lt):
        key = round(lt * self.ctx.fps) if self.kb else 0
        if key in self._cache:
            return self._cache[key]
        IW, IH, ox, oy, rr, bong, src = self._chuan_bi()
        w, h = self.kich_thuoc()
        surf = skia.Surface(max(IW, 1), max(IH, 1)); c = surf.getCanvas(); c.clear(skia.Color4f(0, 0, 0, 0))
        if bong is not None:
            c.drawImage(bong, 0, 0, _SAMP_NONE)
        if src is not None:
            img, zmax = src
            c.save(); c.clipRRect(rr, True)
            z = self._zoom(lt) / zmax
            dw, dh = img.width() * z, img.height() * z
            dst = skia.Rect.MakeXYWH(ox + (w - dw) / 2, oy + (h - dh) / 2, dw, dh)
            if abs(z - 1) < 1e-6:
                c.drawImage(img, ox + (w - dw) / 2, oy + (h - dh) / 2, _SAMP_NONE)
            else:
                c.drawImageRect(img, dst, _SAMP_LIN)
            c.restore()
        v = self.kd.get("vien")
        if v and float(v.get("w", 0)) > 0:
            p = skia.Paint(AntiAlias=True); p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(float(v["w"])); p.setColor(_chu.mau_skia(v.get("mau", "#fff")))
            c.drawRRect(rr, p)
        r = (surf.makeImageSnapshot(), (ox, oy))
        if len(self._cache) > 8:
            self._cache.clear()
        self._cache[key] = r
        return r


# ======================================================================== video ====
class LopVideo(LopHinh):
    """clip phụ: đọc khung qua ffmpeg pipe đúng kích thước hộp (tuần tự, cache gần)"""
    kieu = "video"

    def __init__(self, spec, ctx):
        Lop.__init__(self, spec, ctx)
        nd = spec.get("noi_dung") or {}
        self.src = None
        if nd.get("duong_giai") or nd.get("duong") or nd.get("id"):
            self.src = ctx.tai_nguyen(nd.get("duong_giai")) or ctx.tai_nguyen(nd.get("duong") or nd.get("id"))
        elif nd.get("src") is not None and int(nd["src"]) < len(ctx.nguon):
            self.src = ctx.nguon[int(nd["src"])]
        self.a = float(nd.get("a", 0))
        self.fit = self.kd.get("fit", "cover"); self.kb = None
        self.toc_do = max(0.1, float(self.kd.get("toc_do", 1.0) or 1.0))
        self.lap = bool(self.kd.get("lap", False))
        self.info = chung.ffprobe(self.src) if self.src else None
        if not self.info:
            self.loi.append({"id": "tai_nguyen_khong_co", "lop": self.id, "t": self.t0, "mo_ta": "không đọc được video: %s" % nd})
        self._src = None
        self._proc = None; self._idx = -1; self._khung = {}; self._size = None
        self._cache = {}

    def kich_thuoc(self):
        W, H = self.ctx.W, self.ctx.H
        w = float(self.vi_tri["w"]) * W if self.vi_tri.get("w") else None
        h = float(self.vi_tri["h"]) * H if self.vi_tri.get("h") else None
        ar = (self.info["w"] / self.info["h"]) if self.info and self.info["h"] else 16 / 9
        if w is None and h is None:
            w = W
        if w is None:
            w = h * ar
        if h is None:
            h = w / ar
        return (w * self.ti_le, h * self.ti_le)

    def _mo(self, bat_dau_idx):
        self._dong()
        w, h = self.kich_thuoc(); w, h = int(round(w)), int(round(h))
        self._size = (w, h)
        fit = "increase" if self.fit == "cover" else "decrease"
        loc = loc_mau_vao(self.info)                          # 1.2.21 (§1f): nguồn phụ 10-bit/HDR → yuv420p/bt709 TRƯỚC scale (hết bạc màu)
        vf = (loc + "," if loc else "") + f"setpts=(PTS-STARTPTS)/{self.toc_do:.5f},fps={self.ctx.fps},scale={w}:{h}:force_original_aspect_ratio={fit}:flags=bicubic"
        vf += f",crop={w}:{h}" if self.fit == "cover" else f",pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black@0"
        ss = self.a + bat_dau_idx / self.ctx.fps * self.toc_do
        lap = []
        if self.lap and self.info and self.info.get("dur"):
            ss = ss % float(self.info["dur"]); lap = ["-stream_loop", "-1"]
        cmd = [chung.duong("ffmpeg"), "-v", "error"] + lap + ["-ss", "%.4f" % ss, "-i", self.src, "-vf", vf, "-colorspace", "bt709",
                                                            "-f", "rawvideo", "-pix_fmt", "bgra", "-"]
        self._proc = chung.popen(cmd, stdout=subprocess.PIPE)
        self._idx = bat_dau_idx - 1

    def _dong(self):
        if self._proc:
            try:
                self._proc.stdout.close(); self._proc.kill()
            except Exception:
                pass
            self._proc = None

    def _khung_tai(self, idx):
        if idx in self._khung:
            return self._khung[idx]
        if self._proc is None or idx < self._idx or idx > self._idx + 60:
            self._mo(idx)
        w, h = self._size
        n = w * h * 4
        while self._idx < idx:
            buf = self._proc.stdout.read(n)
            if len(buf) < n:
                self._dong()
                break
            self._idx += 1
            if self._idx == idx:
                a = np.frombuffer(buf, np.uint8).reshape(h, w, 4).copy()
                self._khung = {k: v for k, v in self._khung.items() if k > idx - 4}
                self._khung[idx] = a
                return a
        return self._khung.get(idx, np.zeros((h, w, 4), np.uint8))

    def khoa_noi_dung(self, lt):
        return int(lt * self.ctx.fps)

    def noi_dung(self, lt):
        idx = int(lt * self.ctx.fps)
        if idx in self._cache:
            return self._cache[idx]
        w, h = self.kich_thuoc(); le = self.le_noi_dung()
        IW, IH = int(math.ceil(w + le["trai"] + le["phai"])), int(math.ceil(h + le["tren"] + le["duoi"]))
        surf = skia.Surface(IW, IH); c = surf.getCanvas(); c.clear(skia.Color4f(0, 0, 0, 0))
        ox, oy = le["trai"], le["tren"]
        rect = skia.Rect.MakeXYWH(ox, oy, w, h); bo = float(self.kd.get("bo", 0)); rr = skia.RRect.MakeRectXY(rect, bo, bo)
        if self.info:
            fr = self._khung_tai(idx)
            img = anh_skia_tu_numpy(fr, bgra=True)
            c.save(); c.clipRRect(rr, True); c.drawImage(img, ox, oy, _SAMP_NONE); c.restore()
        v = self.kd.get("vien")
        if v and float(v.get("w", 0)) > 0:
            p = skia.Paint(AntiAlias=True); p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(float(v["w"])); p.setColor(_chu.mau_skia(v.get("mau", "#fff")))
            c.drawRRect(rr, p)
        r = (surf.makeImageSnapshot(), (ox, oy))
        self._cache = {idx: r}
        return r

    def __del__(self):
        try:
            self._dong()
        except Exception:
            pass


# ======================================================================== duong ====
class LopDuong(Lop):
    """gach_chan | mui_ten | khung | khoanh — vẽ dần trong "ve" giây"""
    kieu = "duong"

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        nd = spec.get("noi_dung") or {}
        self.loai = nd.get("loai", "gach_chan")
        W, H = ctx.W, ctx.H
        tu = nd.get("tu"); den = nd.get("den")
        if not tu or not den:
            raise ThieuTruong("lop.noi_dung.tu/den", "lớp duong cần 2 điểm [x, y] 0..1", self.id)
        self.p0 = (float(tu[0]) * W, float(tu[1]) * H); self.p1 = (float(den[0]) * W, float(den[1]) * H)
        # 1.2.21: dày nét / giây vẽ / ease / màu do kênh quyết (quyet_dinh duong.w, duong.ve, duong.ease; màu → bang_mau.nhan)
        kd = dien_tu_quyet(self.kd, ctx, {"w": "duong.w", "ve": "duong.ve", "ease": "duong.ease"}, "duong", lop=self.id)
        if not kd.get("mau"):
            kd["mau"] = (getattr(ctx, "pc", None) or {}).get("mau_nhan") or quyet(ctx, "bang_mau.nhan", lop=self.id)
        self.kd = kd
        self.w = float(kd["w"]); self.ve_giay = float(kd["ve"])
        self.vi_tri = {"anchor": "tl", "x": 0, "y": 0, "so_voi": "khung"}
        self.spec["ne_mat"] = False
        self._cache = {}

    def _bbox(self):
        x0, y0 = min(self.p0[0], self.p1[0]), min(self.p0[1], self.p1[1])
        x1, y1 = max(self.p0[0], self.p1[0]), max(self.p0[1], self.p1[1])
        if self.loai == "khoanh":
            x0 -= self.w * 2; y0 -= self.w * 2; x1 += self.w * 2; y1 += self.w * 2
        return x0, y0, max(x1 - x0, 1), max(y1 - y0, 1)

    def _giai_vi_tri(self):
        return self._bbox()

    def kich_thuoc(self):
        _, _, w, h = self._bbox(); return (w, h)

    def le_noi_dung(self):
        m = self.w * 3 + 4
        return {"trai": m, "phai": m, "tren": m, "duoi": m}

    def _path(self):
        x0, y0, w, h = self._bbox()
        p = skia.Path()
        if self.loai in ("gach_chan", "mui_ten"):
            p.moveTo(self.p0[0] - x0, self.p0[1] - y0); p.lineTo(self.p1[0] - x0, self.p1[1] - y0)
        elif self.loai == "khung":
            p.addRect(skia.Rect.MakeXYWH(self.w / 2, self.w / 2, w - self.w, h - self.w))
        else:  # khoanh: elip vẽ tay (lệch nhẹ, vòng 1.08)
            cx, cy = w / 2, h / 2; rx, ry = (w - 4 * self.w) / 2, (h - 4 * self.w) / 2
            n = 48; pts = []
            for i in range(n + 5):
                a = -math.pi / 2 + 2 * math.pi * 1.08 * i / n
                j = 1 + 0.03 * math.sin(a * 3)
                pts.append((cx + rx * j * math.cos(a) + self.w * 0.5 * math.sin(a * 2), cy + ry * j * math.sin(a)))
            p.moveTo(*pts[0])
            for q in pts[1:]:
                p.lineTo(*q)
        return p

    def khoa_noi_dung(self, lt):
        return round(min(lt, self.ve_giay) * self.ctx.fps)

    def noi_dung(self, lt):
        u = min(lt / self.ve_giay, 1.0) if self.ve_giay > 0 else 1.0
        key = round(u * 200)
        if key in self._cache:
            return self._cache[key]
        _, _, w, h = self._bbox(); le = self.le_noi_dung()
        IW, IH = int(math.ceil(w + 2 * le["trai"])), int(math.ceil(h + 2 * le["tren"]))
        surf = skia.Surface(IW, IH); c = surf.getCanvas(); c.clear(skia.Color4f(0, 0, 0, 0))
        c.translate(le["trai"], le["tren"])
        p = skia.Paint(AntiAlias=True); p.setStyle(skia.Paint.kStroke_Style); p.setStrokeWidth(self.w)
        p.setStrokeCap(skia.Paint.kRound_Cap); p.setStrokeJoin(skia.Paint.kRound_Join); p.setColor(_chu.mau_skia(self.kd["mau"]))
        path = self._path()
        pm = skia.PathMeasure(path, False); L = pm.getLength()
        seg = skia.Path()
        if u >= 1.0:
            seg = path
        elif u > 0:
            pm.getSegment(0, L * _anim.ease(self.kd["ease"], u), seg, True)
        c.drawPath(seg, p)
        if self.loai == "mui_ten" and u > 0.5:
            x0, y0, _, _ = self._bbox()
            ex, ey = self.p1[0] - x0, self.p1[1] - y0
            ang = math.atan2(self.p1[1] - self.p0[1], self.p1[0] - self.p0[0])
            k = self.w * 3 * min(1.0, (u - 0.5) * 2)
            head = skia.Path()
            head.moveTo(ex - k * math.cos(ang - 0.5), ey - k * math.sin(ang - 0.5)); head.lineTo(ex, ey)
            head.lineTo(ex - k * math.cos(ang + 0.5), ey - k * math.sin(ang + 0.5))
            c.drawPath(head, p)
        r = (surf.makeImageSnapshot(), (le["trai"], le["tren"]))
        self._cache[key] = r
        return r


# ======================================================================== py ====
class LopPy(Lop):
    """file Python do AI viết trong du_an/lop-rieng/: ve(t, W, H, ctx) -> numpy RGBA (h,w,4) thẳng, kích thước hộp"""
    kieu = "py"

    def __init__(self, spec, ctx):
        super().__init__(spec, ctx)
        nd = spec.get("noi_dung") or {}
        f = nd.get("file", "")
        p = f if os.path.isabs(f) else os.path.join(ctx.du_an or "", f)
        self.mod = None
        try:
            sp = importlib.util.spec_from_file_location("lop_rieng_" + hashlib.md5(p.encode()).hexdigest()[:8], p)
            m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
            if not hasattr(m, "ve"):
                raise AttributeError("thiếu hàm ve(t, W, H, ctx)")
            self.mod = m
        except Exception as ex:
            self.loi.append({"id": "tai_nguyen_khong_co", "lop": self.id, "t": self.t0, "mo_ta": "lớp py lỗi: %s" % ex})

    def kich_thuoc(self):
        w, h = hop_mac_dinh(self, "py")
        return (w * self.ti_le, h * self.ti_le)

    def khoa_noi_dung(self, lt):
        return round(lt * self.ctx.fps)

    def noi_dung(self, lt):
        w, h = self.kich_thuoc(); w, h = int(round(w)), int(round(h))
        if self.mod is None:
            return skia.Surface(w, h).makeImageSnapshot(), (0, 0)
        a = self.mod.ve(lt, w, h, self.ctx)
        a = np.ascontiguousarray(np.asarray(a, np.uint8))
        if a.ndim != 3 or a.shape[2] != 4:
            raise ValueError("lớp py phải trả RGBA (h,w,4)")
        return anh_skia_tu_numpy(a), (0, 0)


# ======================================================================== mẫu (thư viện dung/mau) ====
class LopMau(Lop):
    """mẫu dựng sẵn trong thư viện dung/mau: noi_dung{"mau": id, "tham_so": {...}}; hộp mặc định theo thẻ của mẫu"""
    kieu = "mau"

    def __init__(self, spec, ctx):
        from dung import mau as _M
        nd = spec.get("noi_dung") or {}
        self.mid = str(nd.get("mau") or "")
        self.ban = _M.lay(self.mid)
        the = (self.ban or {}).get("the") or {}
        spec = dict(spec)
        vt = dict(the.get("hop") or {})           # hộp riêng của mẫu (nếu mẫu khai); không khai → quyet_dinh vi_tri.hop_mac_dinh.mau (kich_thuoc)
        vt.update(spec.get("vi_tri") or {})
        spec["vi_tri"] = vt
        if the.get("toan_khung"):
            spec["toan_khung"] = True
        p = dict(the.get("mac_dinh") or {})
        p.update(nd.get("tham_so") or {})
        lam_nen = lam_nen_cua(the, p)
        ne = the.get("ne_mat")
        if ne is None:              # cả khung / cần nền (chữ sau người, làm tối ngoài vùng…) → mẫu tự xử lý người, không dời khỏi mặt
            ne = not (the.get("toan_khung") or lam_nen)
        if not ne:
            spec.setdefault("ne_mat", False)
        super().__init__(spec, ctx)
        self.p = p
        self.dong = bool(the.get("dong", True))
        self.lam_nen = lam_nen
        self.cc = _M.CongCu(ctx, self)
        self.cc.p = p
        if self.ban is None:
            self.loi.append({"id": "tai_nguyen_khong_co", "lop": self.id, "t": self.t0, "mo_ta": f"không có mẫu `{self.mid}` trong thư viện"})

    def kich_thuoc(self):
        w, h = hop_mac_dinh(self, "mau")
        return (w * self.ti_le, h * self.ti_le)

    def khoa_noi_dung(self, lt):
        return round(lt * self.ctx.fps) if (self.dong or self.lam_nen) else 0

    def noi_dung(self, lt):
        w, h = self.kich_thuoc(); w, h = max(2, int(round(w))), max(2, int(round(h)))
        if self.ban is None:
            return skia.Surface(w, h).makeImageSnapshot(), (0, 0)
        a = self.ban["ham"](lt, float(self.t1 - self.t0), w, h, self.cc, self.p)
        a = np.ascontiguousarray(np.asarray(a, np.uint8))
        if a.ndim != 3 or a.shape[2] != 4:
            raise ValueError(f"mẫu {self.mid} phải trả RGBA (h,w,4)")
        # chỉ đổi phần CÓ HÌNH (bbox alpha>0) sang skia — mẫu thưa trên hộp cả khung (con trỏ, chồng thẻ…) đỡ chuyển cả 1080×1920
        bx, by, bw, bh = cv2.boundingRect(a[..., 3])
        if bw == 0 or bh == 0:
            return skia.Surface(2, 2).makeImageSnapshot(), (0, 0)
        if bw * bh < 0.9 * a.shape[0] * a.shape[1]:
            return anh_skia_tu_numpy(a[by:by + bh, bx:bx + bw]), (-bx, -by)
        return anh_skia_tu_numpy(a), (0, 0)


KIEU = {"chu": LopChu, "khoi": LopKhoi, "the": LopThe, "hinh": LopHinh, "video": LopVideo, "duong": LopDuong, "py": LopPy, "mau": LopMau}
try:                                   # lớp mở HTML/CSS/SVG (Chromium headless) — dung/web.py, có thì cắm
    from dung.web import LopWeb as _LopWeb
    KIEU["web"] = _LopWeb
except Exception:
    pass


def tao_lop(spec, ctx):
    k = spec.get("kieu", "chu")
    if k not in KIEU:
        raise ValueError("kiểu lớp không biết: %s" % k)
    return KIEU[k](spec, ctx)


# ======================================================================== phân loại / tiện ích cho dung.py ====
def la_toan_khung(spec):
    """1.2.21: lớp TOÀN KHUNG = spec.toan_khung | thẻ mẫu toan_khung | vi_tri.w ≥ 0.9 và h ≥ 0.9 (tỉ lệ khung, ≤ 1) — mọi kiểu (web/py/mau/hinh/video/khoi/chu)"""
    spec = spec or {}
    if spec.get("toan_khung"):
        return True
    if spec.get("kieu") == "mau" and the_mau(spec).get("toan_khung"):
        return True
    vt = spec.get("vi_tri") or {}
    try:
        w, h = float(vt.get("w") or 0), float(vt.get("h") or 0)
    except Exception:
        return False
    return 0 < w <= 1 and 0 < h <= 1 and w >= TOAN_KHUNG_TU and h >= TOAN_KHUNG_TU


def hop_mac_dinh(lop, kieu):
    """(w, h) px của lớp py/mau/web: vi_tri.w/h (≤ 1 tỉ lệ, > 1 px) — thiếu → quyet_dinh vi_tri.hop_mac_dinh.<kieu> = [w, h]"""
    W, H = lop.ctx.W, lop.ctx.H
    vt = lop.vi_tri
    w, h = vt.get("w"), vt.get("h")
    if w is None or h is None:
        hm = quyet(lop.ctx, "vi_tri.hop_mac_dinh." + kieu, lop=lop.id)
        w = hm[0] if w is None else w
        h = hm[1] if h is None else h
    w, h = float(w), float(h)
    w = w * W if w <= 1 else w
    h = h * H if h <= 1 else h
    return max(2.0, w), max(2.0, h)


def hop_mat_noi(mat, W, H, ctx=None):
    """hộp mặt (px) nới thêm ne_mat.noi (× cỡ mặt) để xét đè — ne_mat.noi tuỳ chọn trong quyet_dinh, mặc định 0.10 là dung sai đo (vật lý)"""
    noi = float(quyet(ctx, "ne_mat.noi", 0.10)) if ctx is not None else 0.10
    nx, ny = mat["w"] * noi * W, mat["h"] * noi * H
    return (mat["x0"] * W - nx, mat["y0"] * H - ny, mat["x1"] * W + nx, mat["y1"] * H + ny)


_KD_QUYET = {"co": "chu.co", "dam": "chu.dam", "dong": "chu.dong", "can": "chu.can", "mau": "chu.mau"}


def kd_tu_quyet(kd, ctx, goc="chu", lop=None):
    """kieu_dang chữ thiếu co/dam/dong/can/mau → điền từ quyet_dinh[goc] (§1c "chu"); vien/bong/nen/gradient chỉ điền khi khoá KHÔNG có mặt
    (AI ghi null = cố ý không viền/bóng). Thiếu cả hai → ThieuTruong(goc.<khoá>)."""
    kd = dict(kd or {})
    for k in _KD_QUYET:
        if kd.get(k) is None:
            kd[k] = quyet(ctx, goc + "." + k, lop=lop)
    for k in ("vien", "bong", "nen", "gradient"):
        if k not in kd:
            kd[k] = quyet(ctx, goc + "." + k, None, lop=lop)
    return kd


def the_mau(spec):
    """thẻ của mẫu (dict) nếu lớp là kiểu mau, không thì {}"""
    if (spec or {}).get("kieu") != "mau":
        return {}
    try:
        from dung import mau as _M
        r = _M.lay(str((spec.get("noi_dung") or {}).get("mau") or ""))
        return (r or {}).get("the") or {}
    except Exception:
        return {}


def lam_nen_cua(the, p):
    """thẻ mẫu lam_nen: True | False | "tham_so:k=v[|v2]" (bật theo tham số) · cảnh kieu_nen="noi" (phủ tối/mờ hình dưới) luôn cần nền"""
    ln = (the or {}).get("lam_nen")
    p = p or {}
    if isinstance(ln, str) and ln.startswith("tham_so:") and "=" in ln:
        k, v = ln[8:].split("=", 1)
        return str(p.get(k.strip(), ((the or {}).get("mac_dinh") or {}).get(k.strip()))) in [x.strip() for x in v.split("|")]
    if ln:
        return True
    return str(p.get("kieu_nen", ((the or {}).get("mac_dinh") or {}).get("kieu_nen", ""))) == "noi"


def can_nen(spec):
    """lớp cần ảnh nền đã dựng (mẫu lam_nen, cảnh kiểu nổi…) → phải vẽ SAU base.
    1.2.21 (B1): lớp `sau_nguoi` KHÔNG còn cần nền/mặt nạ lúc vẽ sprite — ghep.dung_khuc chồng người (cắt từ base bằng alpha-tl) lên
    nhóm lớp sau người trong ffmpeg; sprite vẽ như lớp thường (song song, dedup)."""
    nd = spec.get("noi_dung") or {}
    the = the_mau(spec)
    if the:
        p = dict(the.get("mac_dinh") or {}); p.update(nd.get("tham_so") or {})
        if lam_nen_cua(the, p):
            return True
    return bool(nd.get("lam_nen"))


def _anim_don_gian(anim):
    """vào/ra chỉ là mờ (fade/none, không dịch/scale), không keyframe/tách → dựng được bằng ffmpeg trực tiếp"""
    anim = anim or {}
    if anim.get("keyframes") or anim.get("ken_burns") or (anim.get("tach") not in (None, "none")):
        return False
    for k, kk in (("vao", "tu"), ("ra", "toi")):
        v = anim.get(k)
        if v is None:
            continue                                     # chưa ghi → day_du sẽ điền từ quyet_dinh; dung.py gọi với spec thô nên xét sau khi tạo lớp
        if isinstance(v, str):
            v = {"kieu": v}
        if (v.get("kieu") or "none") not in ("fade", "none"):
            return False
        if any(x != "opacity" for x in (v.get(kk) or {})):
            return False
    return True


def la_truc_tiep(spec):
    """video/ảnh dựng THẲNG bằng ffmpeg (không ra PNG từng khung): mọi lớp có hoa_tron ≠ normal; video thường không bo/viền/bóng và
    anim chỉ mờ vào/ra. Nhanh hơn rất nhiều cho video toàn khung (nền động, ánh sáng, khói…)."""
    k = (spec or {}).get("kieu")
    if k not in ("video", "hinh") or spec.get("sau_nguoi"):
        return False
    kd = spec.get("kieu_dang") or {}
    ht = kd.get("hoa_tron")
    if ht and ht != "normal":
        return True
    if k == "video":
        return _anim_don_gian(spec.get("anim")) and not float(kd.get("bo") or 0) and not kd.get("vien") and not kd.get("bong")
    return False


def muc_truc_tiep(lop):
    """Lop (video/hinh) → mô tả lớp trực tiếp cho ghep (toạ độ px đã giải vị trí)"""
    x0, y0, w, h = lop.khoi()
    an = lop.anim or {}                                  # đã qua anim.day_du → vao/ra là dict đủ kieu/dai
    v = an.get("vao") if isinstance(an.get("vao"), dict) else {"kieu": an.get("vao") or "none", "dai": 0.0}
    r = an.get("ra") if isinstance(an.get("ra"), dict) else {"kieu": an.get("ra") or "none", "dai": 0.0}
    dv = float(v.get("dai") or 0) if v.get("kieu") == "fade" else 0.0
    dr = float(r.get("dai") or 0) if r.get("kieu") == "fade" else 0.0
    kd = lop.kd or {}
    if lop.kieu == "video":
        f, nguon, a = lop.src, "video", lop.a
        dfile = float((lop.info or {}).get("dur") or 0)
    else:
        f, nguon, a, dfile = lop.path, "anh", 0.0, 0.0
    return {"loai": "truc_tiep", "id": lop.id, "kieu": lop.kieu, "file": f, "loai_nguon": nguon, "a": a, "dur_file": dfile,
            "lap": bool(kd.get("lap", False)), "toc_do": float(kd.get("toc_do", 1.0) or 1.0), "fit": kd.get("fit", "cover"),
            "x": round(x0, 2), "y": round(y0, 2), "w": round(w, 2), "h": round(h, 2), "t0": lop.t0, "t1": lop.t1,
            "hoa_tron": kd.get("hoa_tron") or "normal", "do_trong": float(kd.get("do_trong", 1.0) if kd.get("do_trong") is not None else 1.0),
            "dv": min(dv, lop.dur / 2), "dr": min(dr, lop.dur / 2)}


def nhan_px(spec, s):
    """xuất khổ lớn (1440p/4K): nhân mọi số đo PIXEL trong lớp (cỡ chữ, viền, bóng, đệm, bo, dịch chuyển anim) với s.
    Toạ độ/khung 0..1 giữ nguyên ⇒ bố cục y hệt bản 1080, chỉ nét hơn."""
    if not s or abs(s - 1) < 1e-6:
        return spec
    sp = json.loads(json.dumps(spec))

    def kd_(kd):
        if not isinstance(kd, dict):
            return kd
        for k in ("co", "bo", "w"):
            if isinstance(kd.get(k), (int, float)):
                kd[k] = kd[k] * s
        if isinstance(kd.get("dem"), (int, float)):
            kd["dem"] = kd["dem"] * s
        elif isinstance(kd.get("dem"), list):
            kd["dem"] = [float(v) * s for v in kd["dem"]]
        v = kd.get("vien")
        for x in (v if isinstance(v, list) else [v] if isinstance(v, dict) else []):
            if isinstance(x.get("w"), (int, float)):
                x["w"] = x["w"] * s
        for b in kd.get("bong") or []:
            if isinstance(b, dict):
                for k in ("x", "y", "mo"):
                    if isinstance(b.get(k), (int, float)):
                        b[k] = b[k] * s
        for k in ("nen", "chu"):
            if isinstance(kd.get(k), dict):
                kd_(kd[k])
        return kd

    if isinstance(sp.get("kieu_dang"), dict):
        kd_(sp["kieu_dang"])
    vt = sp.get("vi_tri") or {}
    for k in ("w", "h"):                              # lớp web: w/h > 1 là px
        if sp.get("kieu") == "web" and isinstance(vt.get(k), (int, float)) and vt[k] > 1:
            vt[k] = vt[k] * s
    an = sp.get("anim") or {}
    for blk in [(an.get("vao") or {}).get("tu"), (an.get("ra") or {}).get("toi")] + list(an.get("keyframes") or []):
        if isinstance(blk, dict):
            for k in ("x", "y", "blur"):
                if isinstance(blk.get(k), (int, float)):
                    blk[k] = blk[k] * s
    return sp


def xep_nhom(specs, ctx):
    """BỐ CỤC XẾP CHỒNG: lớp cùng vi_tri.nhom đang hiện cùng lúc → xếp thành cột (xep "doc") / hàng ("ngang") không chồng nhau,
    cách nhau `cach` (0..1 theo H/W, >1 = px), neo theo anchor/x/y của lớp đầu nhóm; cả khối né mặt về phía neo + vào vùng an toàn.
    Mỗi "đợt" = các lớp nối nhau về thời gian; trong một đợt mỗi lớp giữ một ô cố định (hiện dần như danh sách).
    → (specs mới, may_sua)"""
    W, H = ctx.W, ctx.H
    nhom = {}
    for i, sp in enumerate(specs):
        n = (sp.get("vi_tri") or {}).get("nhom")
        if n and not (sp.get("vi_tri") or {}).get("xep_xong"):          # xep_xong: nao/kiem đã xếp và ghi ô vào kế hoạch
            nhom.setdefault(str(n), []).append(i)
    if not nhom:
        return specs, []
    specs = [dict(sp) for sp in specs]
    may_sua = []
    vung = ctx.vung
    sx0, sy0, sx1, sy1 = vung["trai"] * W, vung["tren"] * H, (1 - vung["phai"]) * W, (1 - vung["duoi"]) * H
    for ten, ds in nhom.items():
        ds = sorted(ds, key=lambda i: (float(specs[i].get("t0", 0)), i))
        dot, cuoi = [], -1e9
        for i in ds:
            t0, t1 = float(specs[i].get("t0", 0)), float(specs[i].get("t1", 0))
            if dot and t0 < cuoi - 1e-3:
                dot[-1].append(i); cuoi = max(cuoi, t1)
            else:
                dot.append([i]); cuoi = t1
        ref = specs[ds[0]]; vt0 = dict(ref.get("vi_tri") or {})        # neo của cả nhóm = lớp đầu nhóm
        for d in dot:
            xep = vt0.get("xep", "doc") if vt0.get("xep") in ("doc", "ngang") else "doc"
            cach = float(vt0.get("cach") if vt0.get("cach") is not None else quyet(ctx, "vi_tri.cach_nhom", lop=ref.get("id")))   # 1.2.21: khoảng cách nhóm do kênh quyết
            cach_px = cach * (H if xep == "doc" else W) if cach <= 1 else cach * getattr(ctx, "ti_le_px", 1.0)
            anchor = vt0.get("anchor", "mc")
            ax, ay = ANCHOR.get(anchor, (0.5, 0.5))
            co = []
            for i in d:
                sp = dict(specs[i]); sp["ne_mat"] = False
                v = dict(sp.get("vi_tri") or {}); v.update({"anchor": anchor, "so_voi": "khung", "x": 0.5, "y": 0.5}); sp["vi_tri"] = v
                try:
                    co.append(tao_lop(sp, ctx).kich_thuoc())
                except Exception:
                    co.append((0.3 * W, 0.06 * H))
            if xep == "doc":
                bw, bh = max(w for w, _ in co), sum(h for _, h in co) + cach_px * (len(co) - 1)
            else:
                bw, bh = sum(w for w, _ in co) + cach_px * (len(co) - 1), max(h for _, h in co)
            try:
                px, py = tao_lop(dict(ref, ne_mat=False), ctx)._diem_neo(0, 0)
            except Exception:
                px, py = float(vt0.get("x", 0.5)) * W, float(vt0.get("y", 0.5)) * H
            X0, Y0 = px - ax * bw, py - ay * bh
            ghi = {"lop": ",".join(str(specs[i].get("id")) for i in d), "sua": "xep_nhom", "nhom": ten, "xep": xep}
            # vùng an toàn cho cả khối
            if bw <= sx1 - sx0:
                X0 = min(max(X0, sx0), sx1 - bw)
            if bh <= sy1 - sy0:
                Y0 = min(max(Y0, sy0), sy1 - bh)
            # né mặt cho cả khối, về phía neo
            t_a = min(float(specs[i]["t0"]) for i in d); t_b = max(float(specs[i]["t1"]) for i in d)
            ne_rieng = False
            mat = ctx.mat_tai(t_a, t_b) if any(specs[i].get("ne_mat", True) and not la_toan_khung(specs[i]) for i in d) else None
            if mat:
                hm = hop_mat_noi(mat, W, H, ctx)
                if Lop._de(X0, Y0, bw, bh, hm):
                    uu = ("len",) if ay <= 0.34 else ("xuong",) if ay >= 0.66 else ("len", "xuong")
                    ung = []
                    if hm[1] - 4 - bh >= sy0 - 0.5:
                        ung.append((0 if "len" in uu else 1, abs(hm[1] - 4 - bh - Y0), "len", hm[1] - 4 - bh))
                    if hm[3] + 4 + bh <= sy1 + 0.5:
                        ung.append((0 if "xuong" in uu else 1, abs(hm[3] + 4 - Y0), "xuong", hm[3] + 4))
                    if ung:                      # ưu tiên phía neo; không đủ chỗ thì cả khối sang phía còn lại (giữ nguyên chồng)
                        ung.sort(); uu_, _, h_, Y0 = ung[0]
                        ghi["ne_mat"] = h_ + ("" if uu_ == 0 else " (phía neo không đủ chỗ cho cả khối)")
                    else:
                        ne_rieng = True
                        ghi["ne_mat"] = "không đủ chỗ trên/dưới mặt cho cả khối — từng lớp tự né (khối có thể tách)"
            o = 0.0
            for (w, h), i in zip(co, d):
                if xep == "doc":
                    x, y = X0 + ax * (bw - w), Y0 + o; o += h + cach_px
                else:
                    x, y = X0 + o, Y0 + ay * (bh - h); o += w + cach_px
                sp = dict(specs[i])
                v = dict(sp.get("vi_tri") or {})
                v.update({"anchor": anchor, "so_voi": "khung", "x": round((x + ax * w) / W, 5), "y": round((y + ay * h) / H, 5)})
                sp["vi_tri"] = v
                if not ne_rieng:
                    sp["ne_mat"] = False
                specs[i] = sp
            ghi["hop"] = [round(X0), round(Y0), round(X0 + bw), round(Y0 + bh)]
            may_sua.append(ghi)
    return specs, may_sua


# ======================================================================== sprite ====
def _che_nguoi(bgra, lop, lt, hop):
    """lớp SAU NGƯỜI: nhân alpha của sprite với (1 − mặt nạ người) tại giây lt (từ t0 lớp) — phần chồng người bị che.
    Mặt nạ người = ctx.lay_alpha (engine tách người lười đúng đoạn lớp cần); chưa có/không tách được → trả nguyên.
    1.2.21 (B1): KHÔNG còn dùng trên đường dựng chính (ghep.dung_khuc chồng người cắt từ base lên lớp sau người → 0 PNG/khung).
    Giữ cho xuất riêng cần PNG đã che người (vd CapCut): ket_xuat_sprite(..., nuong_mat_na=True) — chưa nơi nào gọi."""
    try:
        m = lop.ctx.lay_alpha(lt, lop, ca_khung=True)
    except Exception as ex:
        lop.loi.append({"id": "tai_nguyen_khong_co", "lop": lop.id, "mo_ta": f"sau_nguoi: không lấy được mặt nạ người: {ex}"})
        return bgra
    if m is None:
        return bgra
    hx0, hy0, hx1, hy1 = [int(round(v)) for v in hop]
    h, w = bgra.shape[:2]
    H, W = m.shape[:2]
    vung = np.zeros((h, w), np.float32)
    ax0, ay0, ax1, ay1 = max(0, hx0), max(0, hy0), min(W, hx0 + w), min(H, hy0 + h)
    if ax1 > ax0 and ay1 > ay0:
        vung[ay0 - hy0:ay1 - hy0, ax0 - hx0:ax1 - hx0] = m[ay0:ay1, ax0:ax1].astype(np.float32) / 255.0
    if vung.max() <= 0.002:
        return bgra
    bgra = bgra.copy()
    bgra[:, :, 3] = np.clip(bgra[:, :, 3].astype(np.float32) * (1.0 - vung) + 0.5, 0, 255).astype(np.uint8)
    return bgra


def ket_xuat_sprite(lop, thu_muc, tien_do=None, nuong_mat_na=False):
    """vẽ từng khung fps trong [t0,t1], dedup → PNG + lop.ffconcat + meta.json. → meta dict.
    1.2.21 (B1): lớp `sau_nguoi` vẽ NHƯ LỚP THƯỜNG (dedup theo trạng thái lớp, không nhân mặt nạ, không khoá theo chỉ số khung) — người được
    chồng lại trong ffmpeg (ghep.dung_khuc). nuong_mat_na=True = đường cũ (1 PNG/khung, mặt nạ nướng vào PNG) cho xuất riêng nếu cần."""
    os.makedirs(thu_muc, exist_ok=True)
    fps = lop.ctx.fps
    n = max(1, int(round(lop.dur * fps)))
    hx0, hy0, hx1, hy1 = lop.hop()
    sau_nguoi = bool(nuong_mat_na) and bool((lop.spec or {}).get("sau_nguoi"))
    t_bd = __import__("time").time()
    muc = []                         # [(file, số khung)]
    bam_file = {}                    # sha1 bytes → file
    khoa_truoc = object(); file_truoc = None; so_ve = 0
    for i in range(n):
        lt = i / fps
        k = lop.khoa(lt)
        if sau_nguoi:
            k = (k, i)               # người cử động từng khung → không dedup theo trạng thái lớp (dedup theo nội dung PNG vẫn còn)
        if k == khoa_truoc and file_truoc is not None:
            muc[-1][1] += 1
            continue
        khoa_truoc = k
        bgra = lop.ve(lt, tra_bgra=True)
        if sau_nguoi:
            bgra = _che_nguoi(bgra, lop, lt, (hx0, hy0, hx1, hy1))
        so_ve += 1
        ok, buf = cv2.imencode(".png", bgra, [cv2.IMWRITE_PNG_COMPRESSION, 1])
        b = buf.tobytes()
        h = hashlib.sha1(b).hexdigest()[:16]
        f = bam_file.get(h)
        if f is None:
            f = "k%05d.png" % len(bam_file)
            with open(os.path.join(thu_muc, f), "wb") as fh:
                fh.write(b)
            bam_file[h] = f
        if muc and muc[-1][0] == f:
            muc[-1][1] += 1
        else:
            muc.append([f, 1])
        file_truoc = f
        if tien_do and i % 30 == 0:
            tien_do(lop.id, i, n)
    dong = ["ffconcat version 1.0"]
    for f, so in muc:
        dong.append("file '%s'" % f); dong.append("duration %.6f" % (so / fps))
    dong.append("file '%s'" % muc[-1][0])        # lặp khung cuối để concat tôn trọng duration cuối
    with open(os.path.join(thu_muc, "lop.ffconcat"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(dong) + "\n")
    try:
        lop.ctx.dong_doc(lop)
    except Exception:
        pass
    meta = {"id": lop.id, "kieu": lop.kieu, "concat": os.path.join(thu_muc, "lop.ffconcat"), "x": hx0, "y": hy0, "w": hx1 - hx0, "h": hy1 - hy0,
            "t0": lop.t0, "t1": lop.t1, "khung": n, "ve": so_ve, "png": len(bam_file), "khoi": [round(v, 1) for v in lop.khoi()],
            "may_sua": lop.may_sua + lop.ctx.may_sua, "loi": lop.loi, "giay": round(__import__("time").time() - t_bd, 2)}
    chung.ghi_json(os.path.join(thu_muc, "meta.json"), meta)
    return meta


# ======================================================================== phụ đề ====
def _tu_theo_cat(loi_json, cat):
    """từ trong loi.json (giây gốc) → [{"w","a","b"}] giây thành phẩm theo cat"""
    tus = loi_json.get("tu") or []
    if not cat:
        return [{"w": t["w"], "a": float(t["a"]), "b": float(t["b"])} for t in tus]
    ra = []; off = 0.0
    for seg in cat:
        a, b = float(seg["a"]), float(seg["b"]); src = int(seg.get("src", 0))
        for t in tus:
            if int(t.get("src", 0)) != src:
                continue
            m = (float(t["a"]) + float(t["b"])) / 2
            if a <= m < b:
                ra.append({"w": t["w"], "a": off + max(float(t["a"]), a) - a, "b": off + min(float(t["b"]), b) - a})
        off += b - a
    ra.sort(key=lambda t: t["a"])
    return ra


_DAU_CUOI = ".!?;:…,"


def gom_cum(tus, toi_da_chu=22, lang_ngat=0.5, che_do="cum"):
    """gom từ thành cụm: ≤ toi_da_chu ký tự, ngắt ở dấu câu/khoảng lặng"""
    if che_do == "tu":
        return [[t] for t in tus]
    cum = []; hien = []
    for t in tus:
        w = t["w"].strip()
        if not w:
            continue
        dai = len(" ".join(x["w"] for x in hien)) + (1 if hien else 0) + len(w)
        if hien and (dai > toi_da_chu or t["a"] - hien[-1]["b"] > lang_ngat):
            cum.append(hien); hien = []
        hien.append(t)
        if w[-1] in _DAU_CUOI and len(" ".join(x["w"] for x in hien)) >= toi_da_chu * 0.4:
            cum.append(hien); hien = []
    if hien:
        cum.append(hien)
    # cụm 1 từ rất ngắn phía sau → nhập vào cụm trước nếu vẫn vừa
    ra = []
    for c in cum:
        if ra and len(c) == 1 and len(" ".join(x["w"] for x in ra[-1])) + 1 + len(c[0]["w"]) <= toi_da_chu and c[0]["a"] - ra[-1][-1]["b"] <= lang_ngat:
            ra[-1].extend(c)
        else:
            ra.append(c)
    return ra


def _giao_hop(a, b):
    """a, b = (x0,y0,x1,y1) → diện tích giao"""
    return max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))


def _ne_lop(lop, ls, hop_lop, ctx):
    """cụm phụ đề chồng ≥20% lên một lớp đang hiện cùng lúc → đặt lại ngay trên/dưới lớp đó (bên còn chỗ trong vùng an toàn).
    Không đổi kiểu dáng; ghi may_sua để AI/người dùng thấy. → LopChu mới hoặc None."""
    if not hop_lop:
        return None
    x0, y0, w, h = lop.khoi()
    me = (x0, y0, x0 + w, y0 + h)
    dt = max(1.0, w * h)
    W, H = ctx.W, ctx.H
    va = chung.vung_an_toan(W, H)
    tren_min, duoi_max = va["tren"] * H, (1 - va["duoi"]) * H
    # 1.2.21: ngưỡng chồng để nhường chỗ (phu_de.nhuong_cho, phần diện tích 0..1) và lề cách lớp (vi_tri.cach_nhom) do kênh quyết
    nguong = float(quyet(ctx, "phu_de.nhuong_cho", lop=ls.get("id")))
    le = float(quyet(ctx, "vi_tri.cach_nhom", lop=ls.get("id"))) * H
    for (a, b, hb, lid) in hop_lop:
        if b <= ls["t0"] or a >= ls["t1"]:
            continue
        if _giao_hop(me, hb) < nguong * min(dt, max(1.0, (hb[2] - hb[0]) * (hb[3] - hb[1]))):
            continue
        cho_duoi = duoi_max - (hb[3] + le)
        cho_tren = (hb[1] - le) - tren_min
        ls2 = json.loads(json.dumps(ls))
        if cho_duoi >= h:
            ls2["vi_tri"] = {"anchor": "tc", "x": ls["vi_tri"].get("x", 0.5), "y": (hb[3] + le) / H, "so_voi": "khung"}; huong = "duoi"
        elif cho_tren >= h:
            ls2["vi_tri"] = {"anchor": "bc", "x": ls["vi_tri"].get("x", 0.5), "y": (hb[1] - le) / H, "so_voi": "khung"}; huong = "tren"
        else:
            return None
        moi = LopChu(ls2, ctx)
        moi.may_sua.append({"lop": ls["id"], "sua": "nhuong_cho", "cho": lid, "huong": huong})
        return moi
    return None


def _sua_tu(tus, sua):
    """phu_de.sua {"cụm sai": "cụm đúng"} — sửa lỗi nhận dạng giọng theo CỤM TỪ liền nhau (không phân biệt hoa thường/dấu câu).
    Cùng số từ → thay từng từ (giữ nhịp karaoke); khác số từ → gộp vào một từ trải đúng khoảng thời gian cụm cũ."""
    if not sua or not isinstance(sua, dict) or not tus:
        return tus
    import re as _re

    def k(w):
        return _re.sub(r"[^\w]+", "", unicodedata.normalize("NFC", str(w)).lower())
    ra = list(tus)
    for sai, dung in sua.items():
        a_ = [k(x) for x in str(sai).split() if k(x)]
        b_ = [x for x in str(dung).split()]
        if not a_:
            continue
        i = 0
        while i + len(a_) <= len(ra):
            if [k(t["w"]) for t in ra[i:i + len(a_)]] == a_:
                cu = ra[i:i + len(a_)]
                if len(b_) == len(a_):
                    moi = [dict(t, w=w) for t, w in zip(cu, b_)]
                else:
                    moi = [dict(cu[0], w=" ".join(b_), b=cu[-1]["b"])] if b_ else []
                ra[i:i + len(a_)] = moi
                i += max(1, len(moi))
            else:
                i += 1
    return ra


def phu_de_sang_lop(loi_json, cat, phu_de_spec, ctx):
    """→ [LopChu] mỗi cụm một lớp, karaoke theo từ; vị trí né mặt một lần/cụm, tween khi đổi vị trí.
    1.2.21: KHÔNG còn PHU_DE_MAC_DINH — trường thiếu trong phu_de_spec lấy từ quyet_dinh["phu_de"] (§1c); thiếu cả hai → thieu_truong."""
    spec = json.loads(json.dumps(phu_de_spec or {}))
    if spec.get("che_do") is None:
        spec["che_do"] = quyet(ctx, "phu_de.che_do", lop="phu_de")
    if spec["che_do"] == "tat" or not loi_json:
        return []
    for k in ("toi_da_chu", "karaoke", "keo_dai", "lang_ngat", "tween"):
        if spec.get(k) is None:
            spec[k] = quyet(ctx, "phu_de." + k, lop="phu_de")
    for k in ("kieu_dang", "vi_tri", "anim"):                  # dict: trường con thiếu → quyet_dinh phu_de.<k>.<con>
        goc = quyet(ctx, "phu_de." + k, lop="phu_de")
        d = dict(goc if isinstance(goc, dict) else {}); d.update(spec.get(k) or {})
        spec[k] = d
    kd = spec["kieu_dang"]
    if not kd.get("mau_noi"):                                   # màu nổi karaoke: AI ghi trong công thức → quyet_dinh phu_de.mau_noi
        kd["mau_noi"] = spec.get("mau_noi") or quyet(ctx, "phu_de.mau_noi", lop="phu_de")
    if not kd.get("font"):
        kd["font"] = quyet(ctx, "phu_de.kieu_dang.font", "phu_de", lop="phu_de")
    spec["kieu_dang"] = kd_tu_quyet(kd, ctx, "phu_de.kieu_dang", lop="phu_de")
    tus = _sua_tu(_tu_theo_cat(loi_json, cat), spec.get("sua"))
    tong = ctx.tong_dai() or (tus[-1]["b"] + 1 if tus else 0)
    cums = gom_cum(tus, int(spec["toi_da_chu"]), float(spec["lang_ngat"]), spec["che_do"])
    keo = float(spec["keo_dai"]); tw = float(spec["tween"])
    lops = []
    for i, c in enumerate(cums):
        t0 = c[0]["a"]; t1 = c[-1]["b"] + keo
        if i + 1 < len(cums):
            t1 = min(t1, cums[i + 1][0]["a"])
        if tong:
            t1 = min(t1, tong)
        if t1 - t0 < 2.0 / ctx.fps:
            continue
        text = " ".join(t["w"].strip() for t in c)
        ls = {"id": "pd%03d" % i, "kieu": "chu", "t0": round(t0, 3), "t1": round(t1, 3), "noi_dung": {"text": text},
              "kieu_dang": dict(spec["kieu_dang"]), "vi_tri": dict(spec["vi_tri"]), "anim": json.loads(json.dumps(spec.get("anim") or {}))}
        lop = LopChu(ls, ctx)
        if spec.get("an_khi_lop_chu") and any(a < ls["t1"] and b > ls["t0"] for (a, b) in (getattr(ctx, "hop_lop_chu", None) or [])):
            continue                                                            # AI chọn: có lớp chữ/khối/thẻ đang hiện → không phụ đề
        ne = _ne_lop(lop, ls, getattr(ctx, "hop_lop", None) or [], ctx)       # phụ đề nhường chỗ cho thẻ/chữ đang hiện
        if ne is not None:
            if spec.get("khi_chong") == "an":                                   # AI chọn: chồng lớp → ẩn cụm thay vì dời
                continue
            lop = ne
        if spec.get("hien") == "dan":
            lop.hien_dan = True
        lop.to_noi = bool(spec.get("karaoke", True))
        if spec.get("karaoke", True) or spec.get("hien") == "dan":
            moc = [(t["a"] - t0, t["b"] - t0) for t in c]

            def noi_tai(lt, moc=moc):
                k = 0
                for j, (a, b) in enumerate(moc):
                    if lt >= a:
                        k = j
                return k
            lop.noi_tai = noi_tai
        x0, y0, w, h = lop.khoi()
        if lops:
            px0, py0, pw, ph = lops[-1].khoi()
            # tween theo điểm neo (giữa dưới) nếu vị trí lệch rõ
            dx = (px0 + pw / 2) - (x0 + w / 2); dy = (py0 + ph) - (y0 + h)
            if (abs(dx) > 2 or abs(dy) > 2) and tw > 0 and abs(lops[-1].t1 - t0) < 0.5:
                lop.tween = (dx, dy, tw)
        lops.append(lop)
    return lops
