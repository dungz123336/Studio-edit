# -*- coding: utf-8 -*-
"""MẪU CHUYỂN CẢNH (mũi Mẫu 2) — toan_khung, đặt NGẮN (0,2–0,6 s) quanh nhát cắt: t0 ≈ nhát cắt − dur/2.
Hai loại:
- loại PHỦ (vẽ trực tiếp, không cần nền): chớp trắng, qua đen, wipe tròn, wipe chéo, vệt sáng quét, light leak.
- loại BIẾN DẠNG khung thật (lam_nen=True, dùng c.nen(t)): zoom mờ → trắng, lia nhoè, nhoè chuyển, đẩy vào, glitch RGB.
  Engine chưa cấp nền → mẫu vẽ bản thay thế dạng phủ (không biến dạng được) để vẫn có nhịp chuyển.
Nên đặt anim vào/ra của lớp = none (mẫu tự lo đường cong cường độ).
"""
import math, random

import cv2
import numpy as np

from dung.mau import dang_ky
from dung.mau.chu_hieu_ung import kep, pha, e_out, e_in_out, e_expo, rgba, nen_hop, nhoe_np, s_px

HOP_KHUNG = {"anchor": "tl", "x": 0, "y": 0, "w": 1, "h": 1}


def _env(u, dinh=0.5, len_=1.0, xuong=1.0):
    """đường cường độ 0→1→0, đỉnh tại `dinh`"""
    u = kep(u)
    if u <= dinh:
        return kep(u / max(dinh, 1e-4)) ** len_
    return kep((1 - u) / max(1 - dinh, 1e-4)) ** xuong


def _u(t, dur):
    return kep(t / max(dur, 1e-3))


def _phu_hang(W, H, rgba_):
    """khung RGBA một màu (điền kiểu uint32 — nhanh)"""
    r, g, b, a = [int(kep(v, 0, 255)) for v in rgba_]
    v = np.uint32(r | (g << 8) | (b << 16) | (a << 24))
    return np.full((H, W), v, np.uint32).view(np.uint8).reshape(H, W, 4)


def _phu(W, H, rgb, a):
    """lớp phủ một màu; a: số 0..1 hoặc map alpha float (độ phân giải bất kỳ — dựng RGBA nhỏ rồi phóng)"""
    if np.isscalar(a):
        return _phu_hang(W, H, (rgb[0], rgb[1], rgb[2], round(255 * kep(a))))
    al = np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8)
    h, w = al.shape
    nho = cv2.merge([np.full((h, w), int(v), np.uint8) for v in rgb[:3]] + [al])
    if (h, w) == (H, W):
        return nho
    return cv2.resize(nho, (W, H), interpolation=cv2.INTER_LINEAR)


def _dac(rgb, he_so=1.0, cong=(0, 0, 0)):
    """ảnh RGB (H,W,3) → RGBA đục, tuỳ chọn out = rgb·he_so + cong (một lượt cv2.transform)"""
    rgb = np.ascontiguousarray(rgb)
    if he_so == 1.0 and not any(cong):
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2RGBA)
    M = np.array([[he_so, 0, 0, cong[0]], [0, he_so, 0, cong[1]], [0, 0, he_so, cong[2]], [0, 0, 0, 255]], np.float32)
    return cv2.transform(rgb, M)


_LUOI = {}


def _luoi(W, H, k):
    """lưới toạ độ (x,y) float32 ở độ phân giải 1/k (cache)"""
    key = (W, H, k)
    r = _LUOI.get(key)
    if r is None:
        w, h = max(1, W // k), max(1, H // k)
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = (xx * (W / w), yy * (H / h), w, h)
        _LUOI[key] = r
    return r


def _ghep(W, H, lop, k):
    """lop: [(alpha map 1/k, (r,g,b))] dưới → trên → RGBA cỡ khung (alpha thẳng)"""
    A = None
    C = None
    for a, col in lop:
        col = np.array(col[:3], np.float32)
        if A is None:
            A = a.copy()
            C = a[..., None] * col
        else:
            C = a[..., None] * col + C * (1 - a[..., None])
            A = a + A * (1 - a)
    rgb = C / np.maximum(A[..., None], 1e-4)
    out = np.dstack([rgb, A[..., None] * 255]).clip(0, 255).astype(np.uint8)
    if k != 1:
        out = cv2.resize(out, (W, H), interpolation=cv2.INTER_LINEAR)
    return out


def _mau_list(c, v, md):
    if isinstance(v, str) or v is None:
        v = [v] if v else md
    return [rgba(c, x) for x in v] or [rgba(c, md[0])]


# ---------------------------------------------------------------- chớp trắng ----
@dang_ky(id="mau.chop-trang", nhom="chuyen_canh", ten="Chớp trắng (loé phơi sáng)",
         mo_ta="loé sáng 3–6 khung như đèn flash: khung thật cháy sáng rồi trắng (có nền) hoặc phủ màu sáng — đổi trạng thái, tiết lộ",
         hop_nghia=["tiết lộ", "bùng nổ", "đổi cảnh", "bất ngờ", "flash", "chụp ảnh"],
         tham_so={"mau": "màu loé (sang)", "do": "0..1 cường độ (0.95)", "dinh": "vị trí đỉnh 0..1 (0.35)", "phoi": "0..3 cháy sáng khung thật trước khi trắng (1.5)"},
         mac_dinh={"mau": "sang", "do": 0.95, "dinh": 0.35, "phoi": 1.5},
         hop=HOP_KHUNG, toan_khung=True, lam_nen=True, dong=True,
         sfx_goi_y=["chớp máy ảnh", "bùm sáng", "whoosh ngắn"],
         vi_du={})
def chop_trang(t, dur, W, H, c, p):
    k = float(p.get("do", 0.95)) * _env(_u(t, dur), float(p.get("dinh", 0.35)), 0.7, 1.6)
    col = rgba(c, p.get("mau"), "sang")
    nen = nen_hop(c, t, W, H)
    phoi = float(p.get("phoi", 1.5))
    if nen is None or phoi <= 0:
        return _phu(W, H, col, k)
    w = kep((k - 0.35) / 0.65) ** 1.3
    return _dac(nen[..., :3], (1 + phoi * k) * (1 - w), tuple(v * w for v in col[:3]))


# ---------------------------------------------------------------- qua đen ----
@dang_ky(id="mau.qua-den", nhom="chuyen_canh", ten="Qua đen (dip to black)",
         mo_ta="tối dần về đen (hoặc màu) rồi sáng lại, có thể giữ đen một nhịp ở giữa — khép một ý, sang chương, điện ảnh",
         hop_nghia=["khép lại", "sang chương", "thời gian trôi", "điện ảnh", "lắng"],
         tham_so={"mau": "màu (#000000)", "do": "0..1 độ tối ở giữa (1)", "giu": "phần thời gian giữ đen ở giữa 0..0.6 (0.15)"},
         mac_dinh={"mau": "#000000", "do": 1.0, "giu": 0.15},
         hop=HOP_KHUNG, toan_khung=True, dong=True,
         sfx_goi_y=["trầm dài", "whoosh chậm"],
         vi_du={})
def qua_den(t, dur, W, H, c, p):
    u = _u(t, dur)
    g = kep(float(p.get("giu", 0.15)), 0, 0.6)
    a = (1 - g) / 2
    if u < a:
        k = e_in_out(u / a)
    elif u > 1 - a:
        k = e_in_out((1 - u) / a)
    else:
        k = 1.0
    return _phu(W, H, rgba(c, p.get("mau"), "toi"), float(p.get("do", 1.0)) * k)


# ---------------------------------------------------------------- zoom mờ → trắng ----
def _zoom_mo(img, amt, tam, n=6):
    h, w = img.shape[:2]
    acc = img
    for j in range(1, n):
        s = 1 + amt * j / max(1, n - 1)
        M = cv2.getRotationMatrix2D(tam, 0, s)
        acc = cv2.addWeighted(acc, j / (j + 1), cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT), 1 / (j + 1), 0)
    return acc


@dang_ky(id="mau.zoom-mo-trang", nhom="chuyen_canh", ten="Zoom mờ toả tâm → trắng",
         mo_ta="khung thật phóng nhoè toả từ tâm (zoom blur) rồi bùng trắng — đẩy người xem sang chế độ mới; thiếu nền thì chỉ bùng sáng toả tâm",
         hop_nghia=["bùng nổ", "chuyển chế độ", "dồn nén", "tăng tốc", "lao vào"],
         tham_so={"tam": "[x,y] tâm 0..1 ([0.5,0.45])", "zoom": "độ phóng nhoè tối đa (0.22)", "mau": "màu trắng cuối (sang)", "trang_tu": "từ đâu bắt đầu trắng 0..1 (0.55)"},
         mac_dinh={"tam": [0.5, 0.45], "zoom": 0.22, "mau": "sang", "trang_tu": 0.55},
         hop=HOP_KHUNG, toan_khung=True, lam_nen=True, dong=True,
         sfx_goi_y=["whoosh lao tới", "bùm sáng"],
         vi_du={})
def zoom_mo_trang(t, dur, W, H, c, p):
    u = _u(t, dur)
    tam = p.get("tam", [0.5, 0.45])
    col = rgba(c, p.get("mau"), "sang")
    tt = float(p.get("trang_tu", 0.55))
    kt = kep((u - tt) / max(1e-3, 1 - tt)) ** 1.5 if u > tt else 0.0
    nen = nen_hop(c, t, W, H)
    if nen is None:
        xx, yy, w, h = _luoi(W, H, 4)
        d = np.sqrt((xx - tam[0] * W) ** 2 + (yy - tam[1] * H) ** 2) / math.hypot(W, H)
        R = 0.05 + 1.1 * e_in_out(u)
        a = np.clip(1 - d / max(R, 1e-3), 0, 1) ** 1.5 * (0.35 + 0.65 * e_in_out(u))
        a = np.maximum(a, kt)
        return _phu(W, H, col, a.astype(np.float32))
    k = 2
    nho = cv2.resize(np.ascontiguousarray(nen[..., :3]), (W // k, H // k), interpolation=cv2.INTER_AREA)
    z = _zoom_mo(nho, float(p.get("zoom", 0.22)) * e_in_out(u), (tam[0] * W / k, tam[1] * H / k))
    z = cv2.resize(z, (W, H), interpolation=cv2.INTER_LINEAR)
    return _dac(z, 1 - kt, tuple(v * kt for v in col[:3]))


# ---------------------------------------------------------------- lia nhoè ----
@dang_ky(id="mau.lia-nhoe", nhom="chuyen_canh", ten="Lia nhoè (whip pan)",
         mo_ta="khung lao ngang/dọc như máy lia nhanh, nhoè chuyển động mạnh ở giữa — nối hai cảnh cùng nhịp nhanh; thiếu nền thì phủ vệt nhoè sáng",
         hop_nghia=["nhanh", "năng động", "chuyển ý nhanh", "lướt", "tiếp theo"],
         tham_so={"huong": "trai|phai|len|xuong (trai)", "do": "độ nhoè tối đa (× rộng khung, 0.09)", "dich": "quãng lia (× khung, 0.3)"},
         mac_dinh={"huong": "trai", "do": 0.09, "dich": 0.3},
         hop=HOP_KHUNG, toan_khung=True, lam_nen=True, dong=True,
         sfx_goi_y=["whoosh lia", "vút nhanh"],
         vi_du={})
def lia_nhoe(t, dur, W, H, c, p):
    u = _u(t, dur)
    huong = p.get("huong", "trai")
    doc = huong in ("len", "xuong")
    dau = -1 if huong in ("trai", "len") else 1
    env = _env(u, 0.5, 1.4, 1.4)
    L = H if doc else W
    kb = int(max(1, float(p.get("do", 0.09)) * L * env))
    X = float(p.get("dich", 0.3)) * L                  # cảnh cũ tăng tốc rời đi → nhát cắt → cảnh mới hãm lại vào chỗ
    d = dau * (X * (2 * u) ** 3 if u < 0.5 else -X * (1 - (2 * u - 1)) ** 3)
    nen = nen_hop(c, t, W, H)
    if nen is None:
        rnd = random.Random(int(u * 6))
        xx, yy, w, h = _luoi(W, H, 4)
        q = (xx / W) if doc else (yy / H)
        a = np.zeros_like(q)
        for _ in range(14):
            y0 = rnd.random()
            a += np.exp(-((q - y0) / rnd.uniform(0.004, 0.02)) ** 2) * rnd.uniform(0.3, 1.0)
        a = np.clip(a * 0.55 * env, 0, 0.85).astype(np.float32)
        return _phu(W, H, rgba(c, "sang"), a)
    img = np.ascontiguousarray(nen[..., :3])
    M = np.float32([[1, 0, 0 if doc else d], [0, 1, d if doc else 0]])
    img = cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_WRAP)
    if kb > 2:
        img = cv2.blur(img, (1, kb) if doc else (kb, 1))
    return _dac(img)


# ---------------------------------------------------------------- nhoè chuyển ----
@dang_ky(id="mau.nhoe-chuyen", nhom="chuyen_canh", ten="Nhoè chuyển (hoà tan mềm)",
         mo_ta="khung nhoè dần lên đỉnh ở nhát cắt rồi nét lại, sáng nhẹ và phóng rất nhẹ — nối hai cảnh êm như hoà tan",
         hop_nghia=["mềm", "trôi", "chuyển nhẹ", "hồi tưởng", "thời gian"],
         tham_so={"do": "độ nhoè tối đa px@1080 (36)", "phong": "phóng thêm ở đỉnh (0.03)", "sang": "0..1 sáng thêm ở đỉnh (0.12)"},
         mac_dinh={"do": 36, "phong": 0.03, "sang": 0.12},
         hop=HOP_KHUNG, toan_khung=True, lam_nen=True, dong=True,
         sfx_goi_y=["whoosh mềm", "gió nhẹ"],
         vi_du={})
def nhoe_chuyen(t, dur, W, H, c, p):
    env = e_in_out(_env(_u(t, dur)))
    nen = nen_hop(c, t, W, H)
    if nen is None:
        return _phu(W, H, rgba(c, "sang"), 0.22 * env)
    img = np.ascontiguousarray(nen[..., :3])
    z = float(p.get("phong", 0.03)) * env
    if z > 1e-3:
        img = cv2.warpAffine(img, cv2.getRotationMatrix2D((W / 2, H / 2), 0, 1 + z), (W, H), borderMode=cv2.BORDER_REFLECT)
    sg = s_px(c, float(p.get("do", 36))) * env
    img = nhoe_np(img, sg) if sg > 0.3 else img
    sa = float(p.get("sang", 0.12)) * env
    return _dac(img, 1 + sa, (sa * 40,) * 3)


# ---------------------------------------------------------------- đẩy vào ----
@dang_ky(id="mau.day-vao", nhom="chuyen_canh", ten="Đẩy vào nhanh (punch-in)",
         mo_ta="cú phóng khung 100→112% trong ~0,15 s rồi giữ (tuỳ chọn rung nhẹ lúc chạm) — nhấn câu chốt; kéo dài lớp bao lâu thì giữ bấy lâu",
         hop_nghia=["nhấn mạnh", "câu chốt", "bất ngờ", "zoom", "chú ý"],
         tham_so={"z": "tỉ lệ phóng (1.12)", "dai": "giây phóng (0.15)", "tam": "[x,y] tâm phóng 0..1 ([0.5,0.4])", "rung": "biên độ rung lúc chạm px@1080 (6)",
                  "ra": "true = thả về 100% ở cuối lớp", "dai_ra": "giây thả (0.15)"},
         mac_dinh={"z": 1.12, "dai": 0.15, "tam": [0.5, 0.4], "rung": 6, "ra": False, "dai_ra": 0.15},
         hop=HOP_KHUNG, toan_khung=True, lam_nen=True, dong=True,
         sfx_goi_y=["bụp trầm", "whoosh ngắn"],
         vi_du={})
def day_vao(t, dur, W, H, c, p):
    nen = nen_hop(c, t, W, H)
    if nen is None:
        return np.zeros((H, W, 4), np.uint8)
    dai = float(p.get("dai", 0.15))
    u = e_out(pha(t, 0, dai), 4)
    if p.get("ra"):
        dr = float(p.get("dai_ra", 0.15))
        u *= 1 - e_in_out(pha(t, dur - dr, dr))
    z = 1 + (float(p.get("z", 1.12)) - 1) * u
    tam = p.get("tam", [0.5, 0.4])
    M = cv2.getRotationMatrix2D((tam[0] * W, tam[1] * H), 0, z)
    r = s_px(c, float(p.get("rung", 6))) * math.exp(-max(0.0, t - dai) * 14) if t > dai * 0.6 else 0.0
    if r > 0.3:
        M[0, 2] += r * math.sin(t * 90)
        M[1, 2] += r * math.cos(t * 77)
    img = cv2.warpAffine(np.ascontiguousarray(nen[..., :3]), M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)
    return _dac(img)


# ---------------------------------------------------------------- glitch RGB ----
def _dich(a, dx, dy=0):
    return np.roll(np.roll(a, int(round(dy)), axis=0), int(round(dx)), axis=1)


@dang_ky(id="mau.glitch-rgb", nhom="chuyen_canh", ten="Glitch RGB tách kênh",
         mo_ta="khung nhiễu số: tách kênh đỏ/xanh lệch nhau, cắt lát trượt ngang, vạch quét — chuyển cảnh công nghệ/lỗi; thiếu nền thì phủ khối nhiễu màu",
         hop_nghia=["lỗi", "công nghệ", "hack", "game", "nhiễu", "kỹ thuật số"],
         tham_so={"tach": "độ tách kênh tối đa (× rộng khung, 0.035)", "lat": "số lát cắt (9)", "lech": "độ trượt lát (× rộng, 0.08)",
                  "vach": "0..1 vạch quét tối (0.25)", "hat": "hạt ngẫu nhiên (1)", "nhip": "số lần đổi mẫu nhiễu/giây (20)"},
         mac_dinh={"tach": 0.035, "lat": 9, "lech": 0.08, "vach": 0.25, "hat": 1, "nhip": 20},
         hop=HOP_KHUNG, toan_khung=True, lam_nen=True, dong=True,
         sfx_goi_y=["glitch điện tử", "nhiễu sóng", "bíp lỗi"],
         vi_du={})
def glitch_rgb(t, dur, W, H, c, p):
    u = _u(t, dur)
    env = _env(u, 0.5, 0.8, 0.8)
    rnd = random.Random(int(p.get("hat", 1)) * 7777 + int(t * float(p.get("nhip", 20))))
    nen = nen_hop(c, t, W, H)
    if nen is None:
        out = np.zeros((H, W, 4), np.uint8)
        for _ in range(int(14 * env) + 1):
            y = rnd.randrange(H); h = int(H * rnd.uniform(0.005, 0.05))
            x = rnd.randrange(W); w = int(W * rnd.uniform(0.2, 1.0))
            col = rgba(c, rnd.choice(["nhan", "nhan2", "sang", "toi"]))
            out[y:y + h, max(0, x - w // 2):x + w // 2] = (col[0], col[1], col[2], int(255 * env * rnd.uniform(0.4, 0.9)))
        return out
    img = np.ascontiguousarray(nen[..., :3])
    d = float(p.get("tach", 0.035)) * W * env * rnd.uniform(0.4, 1.0)
    r_ = _dich(img[..., 0], -d, d * 0.1)
    b_ = _dich(img[..., 2], d, -d * 0.1)
    out = cv2.merge([r_, img[..., 1], b_])
    for _ in range(int(p.get("lat", 9))):
        if rnd.random() > env:
            continue
        y0 = rnd.randrange(H); h = int(H * rnd.uniform(0.01, 0.08))
        out[y0:y0 + h] = _dich(out[y0:y0 + h], rnd.uniform(-1, 1) * float(p.get("lech", 0.08)) * W)
    v = float(p.get("vach", 0.25)) * env
    if v > 0:
        out[::4] = cv2.convertScaleAbs(out[::4], alpha=1 - v)
    return _dac(out)


# ---------------------------------------------------------------- vệt sáng quét ----
@dang_ky(id="mau.vet-sang", nhom="chuyen_canh", ten="Vệt sáng quét (shine)",
         mo_ta="một vệt sáng chéo (lõi sáng + quầng mềm) quét ngang cả khung như ánh phản chiếu kính — chuyển cảnh mềm có không khí, làm 'bóng' sản phẩm",
         hop_nghia=["sáng bóng", "cao cấp", "mới", "sản phẩm", "chuyển mềm", "ánh sáng"],
         tham_so={"mau": "màu vệt (sang)", "goc": "góc vệt (độ so với phương dọc, 25)", "rong": "bề rộng lõi (× khung, 0.05)",
                  "quang": "bề rộng quầng (× khung, 0.22)", "do": "0..1 cường độ (0.75)", "huong": "trai_phai|phai_trai (trai_phai)"},
         mac_dinh={"mau": "sang", "goc": 25, "rong": 0.05, "quang": 0.22, "do": 0.75, "huong": "trai_phai"},
         hop=HOP_KHUNG, toan_khung=True, dong=True,
         sfx_goi_y=["ting sáng", "whoosh sáng"],
         vi_du={})
def vet_sang(t, dur, W, H, c, p):
    u = _u(t, dur)
    k = 4
    xx, yy, w, h = _luoi(W, H, k)
    g = math.radians(float(p.get("goc", 25)))
    D = W * math.cos(g) + H * math.sin(g)
    s = (xx * math.cos(g) + yy * math.sin(g)) / D
    if p.get("huong") == "phai_trai":
        s = 1 - s
    pos = -0.3 + 1.6 * e_in_out(u)
    r1, r2 = float(p.get("rong", 0.05)), float(p.get("quang", 0.22))
    a = np.exp(-((s - pos) / r1) ** 2) + 0.4 * np.exp(-((s - pos) / r2) ** 2)
    a = np.clip(a * float(p.get("do", 0.75)) * _env(u, 0.5, 0.5, 0.5) ** 0.3, 0, 1).astype(np.float32)
    return _phu(W, H, rgba(c, p.get("mau"), "sang"), a)


# ---------------------------------------------------------------- light leak ----
@dang_ky(id="mau.light-leak", nhom="chuyen_canh", ten="Light leak (loá sáng phim)",
         mo_ta="các mảng sáng màu ấm/loá phim trôi chéo qua khung, bừng lên rồi tắt — chuyển cảnh cảm xúc, hoài niệm, mùa hè, vlog",
         hop_nghia=["ấm áp", "hoài niệm", "vlog", "cảm xúc", "điện ảnh", "mùa hè"],
         tham_so={"mau": "list màu các mảng (['nhan','sang','nhan2'])", "so": "số mảng (4)", "do": "0..1 cường độ (0.85)",
                  "huong": "[dx,dy] hướng trôi (× khung, [0.5,-0.25])", "co": "cỡ mảng (× cạnh dài, 0.45)", "hat": "hạt ngẫu nhiên (3)"},
         mac_dinh={"mau": ["nhan", "sang", "nhan2"], "so": 4, "do": 0.85, "huong": [0.5, -0.25], "co": 0.45, "hat": 3},
         hop=HOP_KHUNG, toan_khung=True, dong=True,
         sfx_goi_y=["ngân ấm", "whoosh mềm"],
         vi_du={})
def light_leak(t, dur, W, H, c, p):
    u = _u(t, dur)
    k = 6
    xx, yy, w, h = _luoi(W, H, k)
    rnd = random.Random(int(p.get("hat", 3)))
    cols = _mau_list(c, p.get("mau"), ["nhan", "sang", "nhan2"])
    hd = p.get("huong", [0.5, -0.25])
    L = max(W, H)
    rgb = np.zeros((h, w, 3), np.float32)
    env = _env(u, 0.45, 0.8, 1.2)
    for i in range(int(p.get("so", 4))):
        cx = (rnd.uniform(-0.2, 1.0) + hd[0] * (u - 0.5) * rnd.uniform(0.6, 1.4)) * W
        cy = (rnd.uniform(0.0, 1.0) + hd[1] * (u - 0.5) * rnd.uniform(0.6, 1.4)) * H
        r = float(p.get("co", 0.45)) * L * rnd.uniform(0.45, 1.1)
        dai = rnd.uniform(1.8, 3.2)                         # mảng loá dài, nghiêng — không phải chấm tròn
        g_ = rnd.uniform(-0.9, 0.9) + 0.6
        ca, sa = math.cos(g_), math.sin(g_)
        X = (xx - cx) * ca + (yy - cy) * sa
        Y = -(xx - cx) * sa + (yy - cy) * ca
        nh = rnd.uniform(0.6, 1.0) * (0.55 + 0.45 * math.sin(math.pi * kep(u * 1.3 - rnd.uniform(0, 0.3))))
        g = np.exp(-((X / (r * dai)) ** 2 + (Y / r) ** 2) * 2.2) * nh
        g += 0.5 * np.exp(-((X / (r * dai * 0.35)) ** 2 + (Y / (r * 0.18)) ** 2) * 2.2) * nh     # lõi gắt
        col = np.array(cols[i % len(cols)][:3], np.float32) / 255
        rgb += g[..., None] * col
    rgb *= float(p.get("do", 0.85)) * env
    a = np.clip(rgb.max(axis=2), 0, 1)
    rgb = np.clip(rgb / np.maximum(a[..., None], 1e-4), 0, 1)
    out = np.dstack([rgb * 255, a[..., None] * 255]).astype(np.uint8)
    return cv2.resize(out, (W, H), interpolation=cv2.INTER_LINEAR)


# ---------------------------------------------------------------- wipe tròn ----
def _pha_che_mo(u, kieu, i, tre, n):
    """→ (đang che?, tiến độ lớp i) cho kiểu che_mo|che|mo"""
    if kieu == "che":
        return True, kep(u * (1 + tre * (n - 1)) - i * tre)
    if kieu == "mo":
        return False, kep(u * (1 + tre * (n - 1)) - (n - 1 - i) * tre)
    if u < 0.5:
        return True, kep(2 * u * (1 + tre * (n - 1)) - i * tre)
    return False, kep((2 * u - 1) * (1 + tre * (n - 1)) - (n - 1 - i) * tre)


@dang_ky(id="mau.wipe-tron", nhom="chuyen_canh", ten="Wipe tròn (mở/đóng ống kính)",
         mo_ta="các vòng tròn màu nở từ một điểm che kín khung rồi khoét lỗ tròn mở ra cảnh mới (nhiều lớp màu lệch nhịp tạo viền)",
         hop_nghia=["chuyển cảnh", "vui", "năng động", "mở ra", "tiếp theo", "hoạt hình"],
         tham_so={"mau": "list màu các lớp (dưới → trên) (['nhan2','nhan'])", "tam": "[x,y] tâm 0..1 ([0.5,0.5])", "tre": "lệch nhịp giữa lớp (0.18)",
                  "kieu": "che_mo|che|mo (che_mo)", "mem": "độ mềm mép (× khung, 0.002)"},
         mac_dinh={"mau": ["nhan2", "nhan"], "tam": [0.5, 0.5], "tre": 0.18, "kieu": "che_mo", "mem": 0.002},
         hop=HOP_KHUNG, toan_khung=True, dong=True,
         sfx_goi_y=["whoosh tròn", "pop lớn"],
         vi_du={})
def wipe_tron(t, dur, W, H, c, p):
    u = _u(t, dur)
    tam = p.get("tam", [0.5, 0.5])
    cx, cy = tam[0] * W, tam[1] * H
    R = max(math.hypot(cx, cy), math.hypot(W - cx, cy), math.hypot(cx, H - cy), math.hypot(W - cx, H - cy)) + 4
    cols = _mau_list(c, p.get("mau"), ["nhan2", "nhan"])
    n = len(cols)
    tre = float(p.get("tre", 0.18))
    ban = []
    che = True
    for i in range(n):
        che, q = _pha_che_mo(u, p.get("kieu", "che_mo"), i, tre, n)
        ban.append(R * e_in_out(q))
    # tô vòng đồng tâm từ ngoài vào trong (vùng ngoài cùng = nền), cv2 khử răng cưa, toạ độ dưới-pixel (shift 3)
    S = 8
    if che:
        out = np.zeros((H, W, 4), np.uint8)
        thu_tu = [(ban[i], cols[i] + ()) for i in range(n)]
    else:
        out = _phu_hang(W, H, (*cols[-1][:3], 255))
        thu_tu = [(ban[i], cols[i - 1]) if i > 0 else (ban[0], None) for i in range(n - 1, -1, -1)]
    for r, col in thu_tu:
        if r <= 0.5:
            continue
        mau = (0, 0, 0, 0) if col is None else (int(col[0]), int(col[1]), int(col[2]), 255)
        cv2.circle(out, (int(cx * S), int(cy * S)), int(r * S), mau, -1, cv2.LINE_AA, 3)
    return out


def _nua_phang(W, H, ca, sa, nguong):
    """đa giác = khung ∩ {x·ca + y·sa ≤ nguong}"""
    pts = [(0, 0), (W, 0), (W, H), (0, H)]
    out = []
    for k in range(4):
        a, b = pts[k], pts[(k + 1) % 4]
        fa, fb = a[0] * ca + a[1] * sa - nguong, b[0] * ca + b[1] * sa - nguong
        if fa <= 0:
            out.append(a)
        if (fa < 0) != (fb < 0) and fa != fb:
            r = fa / (fa - fb)
            out.append((a[0] + (b[0] - a[0]) * r, a[1] + (b[1] - a[1]) * r))
    return out


# ---------------------------------------------------------------- wipe chéo ----
@dang_ky(id="mau.wipe-cheo", nhom="chuyen_canh", ten="Wipe chéo nhiều dải màu",
         mo_ta="các dải màu chéo quét ngang che kín khung rồi trượt tiếp để lộ cảnh mới, lệch nhịp nhau tạo sọc — chuyển cảnh gọn, hiện đại",
         hop_nghia=["chuyển cảnh", "hiện đại", "gọn", "tiếp theo", "năng động", "tin tức"],
         tham_so={"mau": "list màu các dải (dưới → trên) (['nhan','toi'])", "goc": "góc quét (độ, 30 = chéo xuống)", "tre": "lệch nhịp giữa dải (0.16)",
                  "kieu": "che_mo|che|mo (che_mo)", "huong": "trai_phai|phai_trai (trai_phai)", "mem": "độ mềm mép (× khung, 0.002)"},
         mac_dinh={"mau": ["nhan", "toi"], "goc": 30, "tre": 0.16, "kieu": "che_mo", "huong": "trai_phai", "mem": 0.002},
         hop=HOP_KHUNG, toan_khung=True, dong=True,
         sfx_goi_y=["whoosh quét", "vút"],
         vi_du={"mau": ["nhan2", "nhan", "toi"]})
def wipe_cheo(t, dur, W, H, c, p):
    u = _u(t, dur)
    g = math.radians(float(p.get("goc", 30)))
    ca, sa = math.cos(g), math.sin(g)
    if p.get("huong") == "phai_trai":
        ca, sa = -ca, -sa
    vals = [0, W * ca, H * sa, W * ca + H * sa]
    s0, s1 = min(vals), max(vals)
    cols = _mau_list(c, p.get("mau"), ["nhan", "toi"])
    n = len(cols)
    tre = float(p.get("tre", 0.16))
    ban = []
    che = True
    for i in range(n):
        che, q = _pha_che_mo(u, p.get("kieu", "che_mo"), i, tre, n)
        ban.append(s0 + (s1 - s0 + 2) * e_in_out(q) - 1)
    S = 8
    if che:
        out = np.zeros((H, W, 4), np.uint8)
        thu_tu = [(ban[i], cols[i]) for i in range(n)]
    else:
        out = _phu_hang(W, H, (*cols[-1][:3], 255))
        thu_tu = [(ban[i], cols[i - 1]) if i > 0 else (ban[0], None) for i in range(n - 1, -1, -1)]
    for e, col in thu_tu:
        da = _nua_phang(W, H, ca, sa, e)
        if len(da) < 3:
            continue
        mau = (0, 0, 0, 0) if col is None else (int(col[0]), int(col[1]), int(col[2]), 255)
        cv2.fillPoly(out, [np.round(np.array(da) * S).astype(np.int32)], mau, cv2.LINE_AA, 3)
    return out


# ---------------------------------------------------------------- 3D: lật / lập phương (dùng khung nền thật) ----
def _quad_3d(pts3, cx, cy, f):
    """điểm 3D (x,y,z) quanh tâm (0,0,0), camera nhìn -z từ z=f → toạ độ ảnh"""
    out = []
    for x, y, z in pts3:
        k = f / max(1.0, f - z)
        out.append((cx + x * k, cy + y * k))
    return np.float32(out)


def _warp_mat(img_rgb, quad, W, H, toi=0.0):
    """ảnh (H,W,3) → RGBA đã kéo về tứ giác `quad` (4 điểm ảnh: trái-trên, phải-trên, phải-dưới, trái-dưới); toi 0..1 làm tối mặt"""
    src = np.float32([[0, 0], [W, 0], [W, H], [0, H]])
    x, y = quad[:, 0], quad[:, 1]                          # mặt gần vuông góc với mắt (diện tích ~0) → không vẽ (tránh rác warp)
    if abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))) * 0.5 < 0.002 * W * H:
        return np.zeros((H, W, 4), np.uint8)
    M = cv2.getPerspectiveTransform(src, quad)
    rgba_ = cv2.cvtColor(np.ascontiguousarray(img_rgb), cv2.COLOR_RGB2RGBA)
    if toi > 0.01:
        rgba_[..., :3] = (rgba_[..., :3].astype(np.float32) * (1.0 - toi)).astype(np.uint8)
    return cv2.warpPerspective(rgba_, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))


def _xoay_y(pts, a, zc=0.0):
    """xoay quanh trục dọc qua (0,0,zc)"""
    ca, sa = math.cos(a), math.sin(a)
    return [(x * ca + (z - zc) * sa, y, -x * sa + (z - zc) * ca + zc) for x, y, z in pts]


def _xoay_x(pts, a, zc=0.0):
    ca, sa = math.cos(a), math.sin(a)
    return [(x, y * ca - (z - zc) * sa, y * sa + (z - zc) * ca + zc) for x, y, z in pts]


def _nen_truoc_sau(c, t, dur, W, H):
    """(khung cảnh cũ = ngay trước nhát cắt, khung cảnh mới = ngay sau nhát cắt, khung hiện tại) — nhát cắt ở giữa lớp"""
    fps = max(1.0, float(getattr(c, "fps", 30) or 30))
    cu = nen_hop(c, max(0.0, dur / 2 - 1.5 / fps), W, H)
    moi = nen_hop(c, min(dur, dur / 2 + 1.5 / fps), W, H)
    hien = nen_hop(c, t, W, H)
    return cu, moi, hien


def _ghep_rgba(duoi, tren):
    a = tren[..., 3:4].astype(np.float32) / 255.0
    ra = duoi.copy()
    ra[..., :3] = (tren[..., :3].astype(np.float32) * a + duoi[..., :3].astype(np.float32) * (1 - a)).astype(np.uint8)
    ra[..., 3] = np.maximum(duoi[..., 3], tren[..., 3])
    return ra


@dang_ky(id="mau.lat-3d", nhom="chuyen_canh", ten="Lật 3D (khung quay như tấm thẻ)",
         mo_ta="cả khung cũ quay quanh trục giữa (dọc hoặc ngang) như lật tấm thẻ, mặt sau là cảnh mới quay tới phẳng; nền phía sau tối mờ — đổi ý rõ, có chiều sâu",
         hop_nghia=["lật", "mặt khác", "đổi ý", "trước sau", "3D", "thẻ"],
         tham_so={"truc": "doc|ngang (doc)", "huong": "1|-1 chiều quay (1)", "nen_toi": "0..1 độ tối nền sau (0.75)", "ease": "in_out|out (in_out)"},
         mac_dinh={"truc": "doc", "huong": 1, "nen_toi": 0.75, "ease": "in_out"},
         hop=HOP_KHUNG, toan_khung=True, lam_nen=True, dong=True,
         sfx_goi_y=["whoosh lật", "vút"],
         vi_du={})
def lat_3d(t, dur, W, H, c, p):
    u = _u(t, dur)
    cu, moi, hien = _nen_truoc_sau(c, t, dur, W, H)
    if cu is None or moi is None:
        return _phu(W, H, rgba(c, "toi"), 0.6 * _env(u))
    from dung import anim as _anim
    e = _anim.ease(p.get("ease", "in_out"), u)
    a = math.pi * e * (1 if float(p.get("huong", 1)) >= 0 else -1)      # 0 → 180°
    cx, cy, f = W / 2.0, H / 2.0, max(W, H) * 1.3
    goc = [(-W / 2, -H / 2, 0), (W / 2, -H / 2, 0), (W / 2, H / 2, 0), (-W / 2, H / 2, 0)]
    xoay = _xoay_x if p.get("truc", "doc") == "ngang" else _xoay_y
    nen = cv2.cvtColor(np.ascontiguousarray((hien if hien is not None else moi)[..., :3]), cv2.COLOR_RGB2RGBA)
    toi = float(p.get("nen_toi", 0.75)) * _env(u, 0.5, 0.8, 0.8)
    nen[..., :3] = (nen[..., :3].astype(np.float32) * (1 - toi)).astype(np.uint8)
    if a < math.pi / 2 if a >= 0 else a > -math.pi / 2:                  # nửa đầu: mặt trước = cảnh cũ
        q = _quad_3d(xoay(goc, a), cx, cy, f)
        mat = _warp_mat(cu[..., :3], q, W, H, toi=0.5 * abs(math.sin(a)))
    else:                                                                # nửa sau: mặt sau = cảnh mới (lật gương để đúng chiều)
        a2 = a - math.pi if a >= 0 else a + math.pi
        q = _quad_3d(xoay(goc, a2), cx, cy, f)
        mat = _warp_mat(moi[..., :3], q, W, H, toi=0.5 * abs(math.sin(a2)))
    return _ghep_rgba(nen, mat)


@dang_ky(id="mau.lap-phuong", nhom="chuyen_canh", ten="Lập phương 3D (cube spin)",
         mo_ta="hai cảnh là hai mặt kề của một khối lập phương, khối xoay sang mặt mới (ngang hoặc dọc); góc cạnh tối dần — chuyển mục, chuyển bước",
         hop_nghia=["bước tiếp", "mục mới", "đổi cảnh", "3D", "khối"],
         tham_so={"huong": "trai|phai|len|xuong (trai)", "ease": "in_out|out (in_out)", "sang_canh": "0..1 độ tối ở góc xoay (0.45)"},
         mac_dinh={"huong": "trai", "ease": "in_out", "sang_canh": 0.45},
         hop=HOP_KHUNG, toan_khung=True, lam_nen=True, dong=True,
         sfx_goi_y=["whoosh nặng", "khối xoay"],
         vi_du={})
def lap_phuong(t, dur, W, H, c, p):
    u = _u(t, dur)
    cu, moi, hien = _nen_truoc_sau(c, t, dur, W, H)
    if cu is None or moi is None:
        return _phu(W, H, rgba(c, "toi"), 0.6 * _env(u))
    from dung import anim as _anim
    e = _anim.ease(p.get("ease", "in_out"), u)
    huong = p.get("huong", "trai")
    doc = huong in ("len", "xuong")
    dau = 1 if huong in ("trai", "len") else -1
    cx, cy, f = W / 2.0, H / 2.0, max(W, H) * 1.4
    L = H if doc else W                                  # cạnh khối theo hướng xoay
    zc = -L / 2.0                                        # tâm khối nằm sau mặt trước nửa cạnh
    a = dau * (math.pi / 2) * e
    goc = [(-W / 2, -H / 2, 0), (W / 2, -H / 2, 0), (W / 2, H / 2, 0), (-W / 2, H / 2, 0)]
    if doc:
        # mặt mới nằm dưới (lên) / trên (xuống), vuông góc mặt trước, kéo sâu theo z; thứ tự góc = TL, TR, BR, BL khi đã quay ra trước
        if dau > 0:
            moi0 = [(-W / 2, H / 2, 0), (W / 2, H / 2, 0), (W / 2, H / 2, -H), (-W / 2, H / 2, -H)]
        else:
            moi0 = [(-W / 2, -H / 2, -H), (W / 2, -H / 2, -H), (W / 2, -H / 2, 0), (-W / 2, -H / 2, 0)]
        xoay = _xoay_x
    else:
        moi0 = [(dau * W / 2, -H / 2, 0), (dau * W / 2, -H / 2, -W), (dau * W / 2, H / 2, -W), (dau * W / 2, H / 2, 0)]
        if dau < 0:
            moi0 = [moi0[1], moi0[0], moi0[3], moi0[2]]
        xoay = _xoay_y
        a = -a                                           # xoay âm: mặt trước trôi sang trái, mặt mới từ phải vào đúng chiều chữ
    toi = float(p.get("sang_canh", 0.45)) * math.sin(abs(a))
    q_cu = _quad_3d(xoay(goc, a, zc), cx, cy, f)
    q_moi = _quad_3d(xoay(moi0, a, zc), cx, cy, f)
    nen = np.zeros((H, W, 4), np.uint8); nen[..., 3] = 255
    m1 = _warp_mat(cu[..., :3], q_cu, W, H, toi=toi)
    m2 = _warp_mat(moi[..., :3], q_moi, W, H, toi=toi * 0.6)
    return _ghep_rgba(_ghep_rgba(nen, m1 if u < 0.5 else m2), m2 if u < 0.5 else m1)

