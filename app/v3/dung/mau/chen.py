# -*- coding: utf-8 -*-
"""MẪU CHÈN (nhóm "chen") — đưa TƯ LIỆU vào khung: chồng thẻ đánh giá bay quanh người (né mặt), trang dài nghiêng 3D cuộn,
icon từ KHO bật vào (sticker), ảnh trong khung (polaroid / điện thoại / trình duyệt / bo góc + Ken Burns), so sánh trước–sau kéo
thanh trượt. Ảnh/icon lấy qua c.tai_nguyen (id kho | đường dẫn | nghĩa cho icon); thiếu tài nguyên → vẽ chỗ trống gọn, không lỗi.
Video phủ / ảnh trần do engine lo (lớp video/hinh). Vào/ra tổng thể do engine; mẫu diễn nội dung theo t."""
import math, random
import numpy as np
import cv2
import skia
from dung import chu as _chu
from dung.mau import dang_ky
from dung.mau.canh import (kep, e_out, e_io, e_back, tien, lich, muc, so, tron, voi_alpha, sk, chu_tren,
                           bang_mau, anh_chu, vua, kich, dat, p_to, p_net, rr, hop, bong, the_noi, sao, duong_gap,
                           be_mat, ra, anh, ve_anh_phu, don_vi_goc, skia_tu_bgra, bong_chu, SAMP_LIN, SAMP_CUBIC)

THAM_SO_CHUNG = {"tong_mau": "toi | sang | kinh (toi)", "mau": "màu nhấn (vai hoặc #hex)", "mau2": "màu nhấn phụ",
                 "font": "vai/id font (nhan)",
                 "mau_sao": "màu sao đánh giá (vai|#hex, mặc định nhan)", "mau_but": "màu bút dạ tô dòng (vai|#hex, mặc định nhan)"}


def _the(**kw):
    ts = dict(THAM_SO_CHUNG); ts.update(kw.pop("tham_so", {}))
    md = {"tong_mau": "toi"}; md.update(kw.pop("mac_dinh", {}))
    return dict(nhom="chen", tham_so=ts, mac_dinh=md, **kw)


def _cho_trong(cv, c, B, x0, y0, x1, y1, r, u, chu="thiếu ảnh"):
    """ô thay ảnh khi không tìm thấy tài nguyên"""
    pg = p_to(B["the2"])
    pg.setShader(skia.GradientShader.MakeLinear([skia.Point(x0, y0), skia.Point(x1, y1)], [sk(B["the2"]), sk(tron(B["the2"], B["nhan"], 0.25))]))
    cv.drawRRect(rr(x0, y0, x1, y1, r), pg)
    s = min(x1 - x0, y1 - y0) * 0.18
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 - s * 0.3
    cv.drawRRect(rr(cx - s, cy - s * 0.75, cx + s, cy + s * 0.75, s * 0.15), p_net(B["mo"], max(2, s * 0.08)))
    pa = duong_gap([(cx - s * 0.8, cy + s * 0.55), (cx - s * 0.2, cy - s * 0.05), (cx + s * 0.2, cy + s * 0.3), (cx + s * 0.8, cy - s * 0.3)])
    cv.drawPath(pa, p_net(B["mo"], max(2, s * 0.08)))
    dat(cv, anh_chu(c, chu, s * 0.42, B["mo"], vai="than"), cx, cy + s * 1.1, "tc")


def _hop_mat(c, W, H):
    """hộp mặt (px trong hộp lớp) hoặc None — từ c.mat() (toạ độ khung) đổi sang toạ độ hộp"""
    m = c.mat()
    if not m:
        return None
    try:
        bx, by, bw, bh = c.lop.khoi() if c.lop is not None else (0, 0, c.W, c.H)
    except Exception:
        bx, by, bw, bh = 0, 0, c.W, c.H
    sx, sy = W / max(1.0, bw), H / max(1.0, bh)
    return ((m["x0"] * c.W - bx) * sx, (m["y0"] * c.H - by) * sy, (m["x1"] * c.W - bx) * sx, (m["y1"] * c.H - by) * sy)


# ---------------------------------------------------------------- thẻ đánh giá (dùng chung chồng thẻ + cuộn 3D)
_THE = {}


def _ve_the_danh_gia(c, B, x, cw, u, nen, to_u=0.0, so_thu_tu=0):
    """một thẻ đánh giá (tên + sao + lời khen, bút dạ tuỳ chọn) hoặc thẻ ảnh → (skia.Image có bóng, lề bóng)"""
    k = (repr(sorted(x.items())), int(cw), round(u, 3), nen, round(to_u, 2), B["nhan"], str(c.p.get("mau_sao")), str(c.p.get("mau_but")))
    if k in _THE:
        return _THE[k]
    le = int(40 * u)
    pad = 28 * u
    if x.get("anh"):
        img = anh(c, x["anh"], int(cw * 1.5))
        if img is None:
            return None
        s = cw / img.width()
        w, h = cw, img.height() * s
        surf = skia.Surface(int(w + 2 * le), int(h + 2 * le)); cv = surf.getCanvas(); cv.clear(skia.Color4f(0, 0, 0, 0))
        bong(cv, le, le, le + w, le + h, 22 * u, 36 * u, 0.4, dy=10 * u)
        ve_anh_phu(cv, img, le, le, le + w, le + h, r=22 * u)
        cv.drawRRect(rr(le, le, le + w, le + h, 22 * u), p_net("#ffffff", 3 * u, 0.9, False))
    else:
        mau_nen = {"trang": "#ffffff", "hong": "#FFE3E8"}.get(nen) or (B["the"] if nen == "the" else c.mau(nen))
        chu = chu_tren(mau_nen, "#1c1c20", "#ffffff")
        phu = tron(chu, mau_nen, 0.45)
        ten = str(x.get("ten") or "")
        av = 52 * u
        r_sao = 10 * u
        n_sao = min(5, int(so(x.get("sao"), 5)))
        rong_ten = cw - 2 * pad - av - 16 * u - n_sao * r_sao * 2.3 - 10 * u
        i_t = anh_chu(c, ten, vua(c, ten, 32 * u, rong_ten, 1, 1, co_min=18 * u, vai="nhan"), chu, vai="nhan") if ten else None
        rong = cw - 2 * pad
        i_c = anh_chu(c, str(x.get("chu") or ""), 30 * u, chu, vai="than", rong=rong)
        hd = max(av, kich(i_t)[1] if i_t else 0) if (ten or x.get("sao")) else 0
        h = 2 * pad + hd + (14 * u if hd else 0) + kich(i_c)[1]
        w = cw
        surf = skia.Surface(int(w + 2 * le), int(h + 2 * le)); cv = surf.getCanvas(); cv.clear(skia.Color4f(0, 0, 0, 0))
        bong(cv, le, le, le + w, le + h, 24 * u, 40 * u, 0.38, dy=12 * u)
        hop(cv, le, le, le + w, le + h, 24 * u, mau_nen)
        y = le + pad
        if hd:
            mau_av = (B["nhan"], B["nhan2"], tron(B["nhan"], B["nhan2"], 0.5))[so_thu_tu % 3]
            cv.drawCircle(le + pad + av / 2, y + hd / 2, av / 2, p_to(mau_av))
            dat(cv, anh_chu(c, (ten.split()[-1][:1] if ten.split() else "★").upper(), av * 0.48, chu_tren(mau_av), vai="nhan"),
                le + pad + av / 2, y + hd / 2, "mc")
            if i_t:
                dat(cv, i_t, le + pad + av + 16 * u, y + hd / 2, "ml")
            n, r = n_sao, r_sao
            m_sao = c.mau(c.p.get("mau_sao") or "nhan") if n else None        # 1.2.21: màu sao là tham số mẫu (mau_sao), mặc định vai nhan — không còn #FFB800
            for j in range(n):
                sao(cv, le + w - pad - r - (n - 1 - j) * r * 2.3, y + hd / 2, r, m_sao, m_sao)
            y += hd + 14 * u
        to = x.get("to")
        if to is not None and to_u > 0:                       # bút dạ quét sau dòng `to`
            meta = i_c[1]
            dong_i = int(to[0] if isinstance(to, (list, tuple)) else to)
            tus = [b for b in meta["tu"]]
            if tus:
                ys = sorted(set(round(b[1]) for b in tus))
                if 0 <= dong_i < len(ys):
                    hang = [b for b in tus if round(b[1]) == ys[dong_i]]
                    ox, oy = le + pad - meta["khoi"][0], y - meta["khoi"][1]
                    bx0 = min(b[0] for b in hang) + ox; bx1 = max(b[0] + b[2] for b in hang) + ox
                    by0 = hang[0][1] + oy + hang[0][3] * 0.2; by1 = hang[0][1] + oy + hang[0][3] * 0.95
                    hop(cv, bx0 - 6 * u, by0, bx0 - 6 * u + (bx1 - bx0 + 12 * u) * to_u, by1, 6 * u, c.mau(c.p.get("mau_but") or "nhan"), 0.85)   # 1.2.21: màu bút dạ = tham số mau_but (nhan)
        dat(cv, i_c, le + pad, y, "tl")
    r_ = (surf.makeImageSnapshot(), le)
    if len(_THE) > 300:
        _THE.clear()
    _THE[k] = r_
    return r_


def _ds_the(p):
    ra_ = []
    for x in (p.get("the") or [])[:7]:
        if isinstance(x, str):
            x = {"chu": x, "sao": 5}
        elif isinstance(x, (list, tuple)):
            x = {"ten": x[0] if x else "", "chu": x[1] if len(x) > 1 else "", "sao": x[2] if len(x) > 2 else 5}
        ra_.append(dict(x))
    return ra_


_NP = {}


def _np_the(img):
    k = id(img)
    a = _NP.get(k)
    if a is None or a[0] is not img:
        a = (img, np.ascontiguousarray(img.toarray(colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType)))
        if len(_NP) > 200:
            _NP.clear()
        _NP[k] = a
    return a[1]


def _dan_xoay(acc, src, cx, cy, goc, sc, al):
    """dán ảnh BGRA nhân trước alpha `src` xoay `goc` độ, phóng `sc`, tâm (cx,cy), độ mờ al — chồng lên acc (cùng kiểu)"""
    h, w = src.shape[:2]
    H, W = acc.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), -goc, sc)
    M[0, 2] += cx - w / 2; M[1, 2] += cy - h / 2
    goc4 = np.array([[0, 0, 1], [w, 0, 1], [w, h, 1], [0, h, 1]], np.float64) @ M.T
    x0, y0 = max(0, int(goc4[:, 0].min()) - 1), max(0, int(goc4[:, 1].min()) - 1)
    x1, y1 = min(W, int(goc4[:, 0].max()) + 2), min(H, int(goc4[:, 1].max()) + 2)
    if x1 <= x0 or y1 <= y0 or al <= 0.003:
        return
    M[0, 2] -= x0; M[1, 2] -= y0
    m = cv2.warpAffine(src, M, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    if al < 0.997:
        m = cv2.convertScaleAbs(m, alpha=al)
    vung = acc[y0:y1, x0:x1]
    nguoc = cv2.cvtColor(255 - m[..., 3], cv2.COLOR_GRAY2BGRA)
    acc[y0:y1, x0:x1] = cv2.add(m, cv2.multiply(vung, nguoc, scale=1 / 255.0))


VI_TRI_CHONG = {"quanh_nguoi": [(0.27, 0.3), (0.73, 0.4), (0.26, 0.52), (0.75, 0.62), (0.3, 0.72), (0.7, 0.24), (0.5, 0.78)],
                "coc": [(0.5, 0.42), (0.47, 0.47), (0.53, 0.52), (0.49, 0.57), (0.52, 0.62), (0.48, 0.67), (0.5, 0.72)],
                "cot": [(0.27, 0.26), (0.27, 0.37), (0.27, 0.48), (0.27, 0.59), (0.27, 0.7), (0.27, 0.32), (0.27, 0.64)]}


@dang_ky(**_the(
    id="mau.chong-the", ten="Chồng thẻ đánh giá bay quanh người",
    mo_ta="Bằng chứng xã hội: nhiều thẻ đánh giá (hoặc ảnh chụp tin nhắn khách) bay vào so le quanh người, né mặt, chồng dần rồi giữ.",
    hop_nghia=["đánh giá", "khách khen", "feedback", "review", "bằng chứng", "nhiều người nói", "phản hồi"],
    tham_so={"the": "list {ten, sao 1–5, chu, anh? (ảnh chụp), t? giây hiện, to? [dòng, giây] bút dạ} | chuỗi (3–7) — lời THẬT",
             "kieu": "quanh_nguoi | coc (chồng giữa) | cot (một cột) (quanh_nguoi)", "ben": "cot: trai | phai (trai)",
             "so_le": "giây giữa 2 thẻ (0.35)", "rong": "rộng thẻ, phần rộng hộp (0.44)", "nen": "trang | hong | the | #hex (trang)",
             "vao": "bat | truot (bat)", "nghieng": "độ nghiêng ngẫu nhiên tối đa (4.5)"},
    mac_dinh={"kieu": "quanh_nguoi", "ben": "trai", "so_le": 0.35, "rong": 0.44, "nen": "trang", "vao": "bat", "nghieng": 4.5},
    toan_khung=True, dong=True, sfx_goi_y=["pop nhẹ", "whoosh nhẹ", "bubble"],
    vi_du={"the": [{"ten": "Thu Trang", "sao": 5, "chu": "Áo đẹp hơn ảnh, vải mát lắm shop ơi!"},
                   {"ten": "Minh Anh", "sao": 5, "chu": "Giao nhanh, đóng gói cẩn thận. Sẽ ủng hộ tiếp.", "to": [0, 1.4]},
                   {"ten": "Hoàng Nam", "sao": 5, "chu": "Mua lần 3 rồi, chất lượng vẫn y như cũ."}], "so_le": 0.45}))
def chong_the(t, dur, W, H, c, p):
    B = bang_mau(c, p)
    ds = _ds_the(p)
    acc = np.zeros((H, W, 4), np.uint8)                 # ghép bằng OpenCV (ảnh nhân trước alpha): skia CPU xoay ảnh rất chậm
    if not ds:
        return acc
    u = W * float(p.get("rong", 0.44)) / 400.0
    kieu = str(p.get("kieu") or "quanh_nguoi")
    vt = VI_TRI_CHONG.get(kieu, VI_TRI_CHONG["quanh_nguoi"])
    cw = W * float(p.get("rong", 0.44 if kieu != "coc" else 0.62))
    u = cw / 400.0
    so_le = float(p.get("so_le", 0.35))
    ts = lich(len(ds), dur, so_le, 0.05, [d.get("t") for d in ds])
    rng = random.Random(len(ds) * 7919 + int(cw))
    goc = [rng.uniform(-1, 1) * float(p.get("nghieng", 4.5)) for _ in range(8)]
    mat = _hop_mat(c, W, H)
    vung_ve = [W, H, 0, 0]
    for i, x in enumerate(ds):
        if t < ts[i]:
            continue
        k = tien(t, ts[i], 0.34)
        to = x.get("to")
        to_u = 0.0
        if isinstance(to, (list, tuple)) and len(to) > 1:
            to_u = round(e_out(tien(t, float(to[1]), 0.45)), 2)
        r_ = _ve_the_danh_gia(c, B, x, cw, u, str(p.get("nen") or "trang"), to_u, i)
        if r_ is None:
            continue
        img, le = r_
        iw, ih = img.width(), img.height()
        px, py = vt[i % len(vt)]
        if kieu == "cot" and str(p.get("ben")) == "phai":
            px = 1 - px
        cx, cy = px * W, py * H
        sc = (0.55 + 0.45 * e_back(k)) if str(p.get("vao")) != "truot" else 1.0
        dx = 0.0 if str(p.get("vao")) != "truot" else (1 - e_out(k)) * W * 0.5 * (-1 if px < 0.5 else 1)
        w_t, h_t = iw - 2 * le, ih - 2 * le
        if mat:                                             # né mặt: áp sát bên cạnh, không đủ chỗ thì hạ xuống dưới cằm
            mx0, my0, mx1, my1 = mat
            if cy + h_t / 2 > my0 and cy - h_t / 2 < my1 and cx + w_t / 2 > mx0 and cx - w_t / 2 < mx1:
                cho = (mx0 if px < 0.5 else W - mx1) - 8 * u
                k2 = min(1.0, cho * 1.1 / w_t)
                if k2 >= 0.62:
                    sc *= k2
                    cx = (mx0 - w_t * k2 / 2 - 4 * u) if px < 0.5 else (mx1 + w_t * k2 / 2 + 4 * u)
                else:
                    cy = min(max(cy, my1 + h_t / 2 + 12 * u) + (i // 2) * h_t * 0.5, H * 0.9 - h_t / 2)
        g = goc[i] * (1.6 - 0.6 * e_out(k))
        a = kep(k * 2.2)
        _dan_xoay(acc, _np_the(img), cx + dx, cy, g, sc, a)
        rmax = math.hypot(iw, ih) / 2 * max(1.0, sc)
        vung_ve = [min(vung_ve[0], cx + dx - rmax), min(vung_ve[1], cy - rmax), max(vung_ve[2], cx + dx + rmax), max(vung_ve[3], cy + rmax)]
    x0, y0 = max(0, int(vung_ve[0])), max(0, int(vung_ve[1]))
    x1, y1 = min(W, int(math.ceil(vung_ve[2]))), min(H, int(math.ceil(vung_ve[3])))
    out = np.zeros((H, W, 4), np.uint8)
    if x1 > x0 and y1 > y0:
        b, g_, r_, al = cv2.split(np.ascontiguousarray(acc[y0:y1, x0:x1]))
        out[y0:y1, x0:x1] = cv2.merge([cv2.divide(r_, al, scale=255.0), cv2.divide(g_, al, scale=255.0), cv2.divide(b, al, scale=255.0), al])
    return out


# ---------------------------------------------------------------- trang nghiêng 3D cuộn
_TRANG = _chu.CacheAnh("mau.chen._TRANG")      # 1.2.21: trần RAM chung (cau_hinh cache_anh_mb) — trước đây ~400 MB không giới hạn


def _trang(c, B, p, cw, u):
    """ảnh trang dài: ảnh chụp (anh) hoặc trang dựng từ thẻ đánh giá"""
    k = (str(p.get("anh")), repr(p.get("the")), int(cw), round(u, 3), str(p.get("nen")), B["nhan"])
    if k in _TRANG:
        return _TRANG[k]
    img = anh(c, p.get("anh"), 2600) if p.get("anh") else None
    if img is not None:
        s = cw / img.width()
        surf = skia.Surface(int(cw), max(2, int(img.height() * s))); cv = surf.getCanvas()
        cv.drawImageRect(img, skia.Rect.MakeWH(cw, img.height() * s), SAMP_CUBIC)
        r_ = surf.makeImageSnapshot()
    else:
        ds = _ds_the(p) or [{"chu": "…"}]
        anhs = [_ve_the_danh_gia(c, B, x, cw * 0.88, u, str(p.get("nen") or "trang"), 0, i) for i, x in enumerate(ds)]
        anhs = [a for a in anhs if a is not None]
        cao = sum(a[0].height() - a[1] * 1.4 for a in anhs) + 40 * u
        lap = 1 if cao >= cw * 1.6 else int(math.ceil(cw * 1.6 / max(cao, 1)))
        H_ = int(max(cao * lap, cw * 1.6))
        surf = skia.Surface(int(cw), H_); cv = surf.getCanvas()
        nen = tron(B["the"], "#ffffff", 0.9) if str(p.get("nen") or "trang") == "trang" else B["the"]
        cv.clear(sk(nen))
        y = 20 * u
        for _ in range(lap):
            for img, le in anhs:
                cv.drawImage(img, (cw - img.width()) / 2, y - le * 0.7)
                y += img.height() - le * 1.4
        r_ = surf.makeImageSnapshot()
    _TRANG[k] = r_
    return r_


@dang_ky(**_the(
    id="mau.cuon-3d", ten="Trang dài nghiêng 3D cuộn chậm",
    mo_ta="Cho thấy NHIỀU nội dung một lúc: ảnh chụp dài (trang đánh giá, bài viết, kết quả) nghiêng phối cảnh, cuộn chậm, mờ hai đầu.",
    hop_nghia=["rất nhiều", "hàng trăm đánh giá", "danh sách dài", "kết quả tìm kiếm", "bài viết", "lướt"],
    tham_so={"anh": "ảnh chụp dài (id kho / đường dẫn)", "the": "không có ảnh: list thẻ {ten, sao, chu} | chuỗi — dựng thành trang",
             "nghieng": "ngả ra sau, độ (32)", "xoay": "lệch ngang, độ (-10)", "cuon": "phần trang cuộn qua 0..1 (0.6)",
             "mo_mep": "phần mờ ở mép trên/dưới (0.18)", "nen": "trang | the (trang) — nền trang dựng"},
    mac_dinh={"nghieng": 32, "xoay": -10, "cuon": 0.6, "mo_mep": 0.18, "nen": "trang"},
    hop={"anchor": "mc", "x": 0.5, "y": 0.74, "w": 0.9, "h": 0.42}, dong=True, sfx_goi_y=["whoosh dài", "lướt giấy"],
    vi_du={"the": [{"ten": "Lan Phương", "sao": 5, "chu": "Đóng gói đẹp, giao nhanh."}, {"ten": "Quốc Huy", "sao": 5, "chu": "Chất vải dày dặn, đúng mô tả."},
                   {"ten": "Bảo Ngọc", "sao": 5, "chu": "Shop tư vấn nhiệt tình lắm."}, {"ten": "Tuấn Kiệt", "sao": 4, "chu": "Giá tốt so với chất lượng."}]}))
def cuon_3d(t, dur, W, H, c, p):
    B = bang_mau(c, p)
    ng = math.radians(kep(float(p.get("nghieng", 32)), 0, 70))
    xo = math.radians(float(p.get("xoay", -10)))
    thu = 1 - 0.6 * math.sin(ng)
    cao = H * 0.98                                        # hình thang đặt khít hộp
    rong_day = min(W * 0.96, W - abs(W * 0.4 * math.sin(xo)))
    cw = int(rong_day)
    u = cw / 900.0
    tr = _trang_np(c, B, p, cw, u)
    wh = int(min(cw * cao / rong_day / max(0.35, math.cos(ng)) * 0.75, tr.shape[0]))
    tong = max(0.0, tr.shape[0] - wh)
    off = int(tong * float(p.get("cuon", 0.6)) * e_io(kep(t / max(dur, 1e-3))))
    cua = tr[off:off + wh]
    mm = float(p.get("mo_mep", 0.18))
    k = ("mo", wh, mm)
    g = _TRANG.get(k)
    if g is None:
        y = np.linspace(0, 1, wh, dtype=np.float32)
        g = np.clip(np.minimum(y / max(mm, 1e-3), (1 - y) / max(mm * 0.6, 1e-3)), 0, 1)
        g = (g * g * (3 - 2 * g))[:, None, None]
        _TRANG[k] = g
    cua = (cua * g).astype(np.uint8)                      # ảnh nhân trước alpha → nhân cả 4 kênh
    lech = rong_day * 0.4 * math.sin(xo)
    cx = W / 2
    y1 = (H + cao) / 2; y0 = y1 - cao
    dst = np.float32([[cx - rong_day * thu / 2 + lech, y0], [cx + rong_day * thu / 2 + lech, y0], [cx + rong_day / 2, y1], [cx - rong_day / 2, y1]])
    src = np.float32([[0, 0], [cw, 0], [cw, wh], [0, wh]])
    Mx = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(cua, Mx, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    b, g_, r_, al = cv2.split(out)
    return cv2.merge([cv2.divide(r_, al, scale=255.0), cv2.divide(g_, al, scale=255.0), cv2.divide(b, al, scale=255.0), al])


def _trang_np(c, B, p, cw, u):
    """trang dạng numpy BGRA nhân trước alpha (warp bằng OpenCV — phối cảnh trên CPU của skia chậm 5–10×)"""
    img = _trang(c, B, p, cw, u)
    k = ("np", id(img))
    a = _TRANG.get(k)
    if a is None:
        a = np.ascontiguousarray(img.toarray(colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType))
        _TRANG[k] = a
    return a


# ---------------------------------------------------------------- icon kho
_STICKER = _chu.CacheAnh("mau.chen._STICKER")      # 1.2.21: trần RAM chung


def _icon(c, ref, canh, vien_px, mau_vien):
    """icon kho (cắt viền trong suốt) + viền sticker (giãn alpha) — cache"""
    k = (str(ref), int(canh), int(vien_px), mau_vien)
    if k in _STICKER:
        return _STICKER[k]
    img = anh(c, ref, int(canh), loai="icon", cat_trong=True)
    if img is None:
        _STICKER[k] = None
        return None
    if vien_px > 0:
        a = img.toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType)
        v = int(vien_px)
        a = cv2.copyMakeBorder(a, v + 2, v + 2, v + 2, v + 2, cv2.BORDER_CONSTANT, value=(0, 0, 0, 0))
        al = a[..., 3]
        ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * v + 1, 2 * v + 1))
        gian = cv2.GaussianBlur(cv2.dilate((al > 40).astype(np.uint8) * 255, ker), (0, 0), max(0.6, v * 0.08))
        r_, g_, b_, _ = [int(x) for x in _chu.mau(mau_vien)]
        nen = np.zeros_like(a); nen[..., 0], nen[..., 1], nen[..., 2], nen[..., 3] = r_, g_, b_, gian
        fa = a[..., 3:4].astype(np.float32) / 255
        out = nen.astype(np.float32)
        out[..., :3] = a[..., :3] * fa + out[..., :3] * (1 - fa)
        out[..., 3:4] = np.maximum(a[..., 3:4], nen[..., 3:4])
        out = np.ascontiguousarray(np.clip(out, 0, 255).astype(np.uint8))
        img = skia_tu_bgra(cv2.cvtColor(out, cv2.COLOR_RGBA2BGRA))
    _STICKER[k] = img
    return img


@dang_ky(**_the(
    id="mau.icon-kho", ten="Icon / hình minh hoạ từ KHO (+ nhãn)",
    mo_ta="Minh hoạ MỘT khái niệm bằng hình trong kho (id hoặc nghĩa: túi tiền, điện thoại, đám đông…), kiểu sticker viền trắng, nhãn dưới.",
    hop_nghia=["minh hoạ", "khái niệm", "tiền", "điện thoại", "ví dụ", "hình ảnh"],
    tham_so={"icon": "id kho icon.* HOẶC nghĩa tiếng Việt/Anh (vd 'túi tiền')", "nhan": "chữ dưới icon (tuỳ)",
             "vien": "viền sticker, phần cạnh icon (0.035; 0 = không)", "mau_vien": "màu viền sticker (#ffffff)",
             "bong_san": "bóng đổ dưới chân true/false (true)"},
    mac_dinh={"vien": 0.035, "mau_vien": "#ffffff", "bong_san": True},
    hop={"anchor": "mc", "x": 0.5, "y": 0.3, "w": 0.5, "h": 0.24}, dong=False, sfx_goi_y=["pop", "bubble", "boing"],
    vi_du={"icon": "icon.bag-of-money-8631", "nhan": "Lãi gấp đôi"}))
def icon_kho(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font = p.get("font") or "nhan"
    u = min(W, H) / 500.0
    nh = str(p.get("nhan") or "")
    i_n = None
    hn = 0
    if nh:
        co = vua(c, nh, H * 0.12, W * 0.9, 1, 2, co_min=H * 0.06, vai=font)
        i_n = anh_chu(c, nh, co, c.mau("sang") if B["tong"] != "sang" else B["chu"], vai=font, rong=W * 0.9, can="giua")
        hn = kich(i_n)[1] + co * 0.55 + 14 * u
    vung_h = H - hn - 10 * u
    canh = max(64, min(W, vung_h) * 1.4)
    vien = float(p.get("vien", 0.035))
    img = _icon(c, p.get("icon"), canh, canh * vien, str(p.get("mau_vien") or "#ffffff"))
    if img is not None:
        s = min(W * 0.96 / img.width(), vung_h * 0.94 / img.height())
        w, h = img.width() * s, img.height() * s
        x0, y0 = (W - w) / 2, (vung_h - h) / 2
        if p.get("bong_san", True):
            pb = p_to("#000000", 0.32); pb.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, h * 0.03))
            cv.drawOval(skia.Rect.MakeLTRB(W / 2 - w * 0.36, y0 + h * 0.95, W / 2 + w * 0.36, y0 + h * 1.03), pb)
        cv.drawImageRect(img, skia.Rect.MakeLTRB(x0, y0, x0 + w, y0 + h), SAMP_LIN)
    else:
        r = min(W, vung_h) * 0.4
        cv.drawCircle(W / 2, vung_h / 2, r, p_to(B["nhan"]))
        dat(cv, anh_chu(c, (nh or str(p.get("icon") or "?"))[:1].upper(), r, B["tren_nhan"], vai=font), W / 2, vung_h / 2, "mc")
    if i_n:
        tw, th = kich(i_n)
        co = th / 1.15
        yy = H - hn + 14 * u
        hop(cv, W / 2 - tw / 2 - co * 0.5, yy, W / 2 + tw / 2 + co * 0.5, yy + th + co * 0.5, (th + co * 0.5) / 2,
            B["toi"] if B["tong"] != "sang" else "#ffffff", 0.88)
        dat(cv, i_n, W / 2, yy + co * 0.25, "tc")
    return ra(surf)


# ---------------------------------------------------------------- ảnh trong khung
@dang_ky(**_the(
    id="mau.anh-khung", ten="Ảnh trong khung (polaroid / điện thoại / trình duyệt / bo góc)",
    mo_ta="Đặt ẢNH người dùng gửi đúng câu đang nói: trong khung polaroid có chú thích, màn hình điện thoại, cửa sổ trình duyệt hoặc bo góc; ảnh trôi chậm (Ken Burns).",
    hop_nghia=["ảnh sản phẩm", "ảnh chụp màn hình", "minh hoạ", "kết quả", "bằng chứng", "website", "app"],
    tham_so={"anh": "id kho / đường dẫn ảnh", "khung": "polaroid | dien_thoai | trinh_duyet | bo_goc (bo_goc)", "chu": "chú thích (polaroid) / địa chỉ (trình duyệt)",
             "zoom": "zoom cuối Ken Burns (1.08; 1 = đứng yên)", "lia": "[x, y] điểm lia tới 0..1 ([0.5, 0.5])", "nghieng": "độ nghiêng khung (polaroid -3, khác 0)",
             "mau_giay": "màu giấy polaroid (vai|#hex, sang)", "mau_ghi": "màu chữ ghi dưới ảnh polaroid (toi)",
             "mau_vo": "màu vỏ điện thoại (toi)", "mau_vien_vo": "màu viền vỏ (viền tông)", "mau_khe": "màu khe loa/tai thỏ (toi)",
             "mau_cham": "3 màu chấm cửa sổ trình duyệt [vai|#hex ×3] ([nhan, nhan2, phụ])"},
    mac_dinh={"khung": "bo_goc", "zoom": 1.08, "lia": [0.5, 0.5]},
    hop={"anchor": "mc", "x": 0.5, "y": 0.42, "w": 0.8, "h": 0.4}, dong=True, sfx_goi_y=["chụp ảnh", "whoosh nhẹ", "pop"],
    vi_du={"anh": "anh.benj-villena-custom-presets-3d69", "khung": "polaroid", "chu": "Bộ màu mới ra mắt"}))
def anh_khung(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font = p.get("font") or "nhan"
    img = anh(c, p.get("anh"), int(max(W, H) * 1.2))
    khung = str(p.get("khung") or "bo_goc")
    ar = img.width() / img.height() if img is not None else 4 / 3
    z = 1 + (float(p.get("zoom", 1.08)) - 1) * e_io(kep(t / max(dur, 1e-3)))
    lia = p.get("lia") or [0.5, 0.5]
    lx = 0.5 + (float(lia[0]) - 0.5) * e_io(kep(t / max(dur, 1e-3)))
    ly = 0.5 + (float(lia[1]) - 0.5) * e_io(kep(t / max(dur, 1e-3)))
    m = 0.05 * min(W, H)
    aw, ah = W - 2 * m, H - 2 * m
    g = float(p.get("nghieng", -3 if khung == "polaroid" else 0))

    def anh_vao(x0, y0, x1, y1, r):
        if img is not None:
            ve_anh_phu(cv, img, x0, y0, x1, y1, z, lx, ly, r=r)
        else:
            u_ = min(x1 - x0, y1 - y0) / 500
            _cho_trong(cv, c, B, x0, y0, x1, y1, r, u_)
    if abs(g) > 0.01:                                    # vẽ thẳng lên lớp phụ rồi xoay MỘT lần (xoay từng nét + clip AA rất chậm)
        surf2, cv = be_mat(W, H)
    # 1.2.21: màu khung (giấy polaroid, chữ ghi, vỏ/viền/khe điện thoại, chấm cửa sổ) là THAM SỐ mẫu, mặc định theo vai màu (sang/toi) — không còn hex hàn chết
    m_giay, m_ghi = c.mau(p.get("mau_giay") or "sang"), c.mau(p.get("mau_ghi") or "toi")
    m_vo, m_vien_vo, m_khe = c.mau(p.get("mau_vo") or "toi"), c.mau(p.get("mau_vien_vo") or B["vien"]), c.mau(p.get("mau_khe") or "toi")
    m_cham = p.get("mau_cham") if isinstance(p.get("mau_cham"), (list, tuple)) and len(p.get("mau_cham")) >= 3 else [B["nhan"], B["nhan2"], B["phu"]]
    if khung == "polaroid":
        w = min(aw * 0.92, ah * 0.9 / (1 / ar * 0.86 + 0.24))
        bd = w * 0.06
        iw = w - 2 * bd; ih = iw / ar
        h = ih + bd + w * 0.2
        x0, y0 = (W - w) / 2, (H - h) / 2
        bong(cv, x0, y0, x0 + w, y0 + h, 4, w * 0.05, 0.45, dy=w * 0.02)
        hop(cv, x0, y0, x0 + w, y0 + h, w * 0.008, m_giay)
        anh_vao(x0 + bd, y0 + bd, x0 + bd + iw, y0 + bd + ih, 2)
        if p.get("chu"):
            ch = str(p.get("chu"))
            co = vua(c, ch, w * 0.07, iw, 1, 2, co_min=w * 0.035, vai="script")
            dat(cv, anh_chu(c, ch, co, m_ghi, vai="script", rong=iw, can="giua"), W / 2, y0 + bd + ih + (h - bd - ih) / 2, "mc")
    elif khung == "dien_thoai":
        ty = 2.05
        h = min(ah, aw * ty)
        w = h / ty
        x0, y0 = (W - w) / 2, (H - h) / 2
        r = w * 0.16
        bong(cv, x0, y0, x0 + w, y0 + h, r, w * 0.08, 0.5, dy=w * 0.03)
        hop(cv, x0, y0, x0 + w, y0 + h, r, m_vo, 1, m_vien_vo, max(1.5, w * 0.008))
        bz = w * 0.035
        anh_vao(x0 + bz, y0 + bz, x0 + w - bz, y0 + h - bz, r - bz)
        cv.drawRRect(rr(W / 2 - w * 0.15, y0 + bz + w * 0.03, W / 2 + w * 0.15, y0 + bz + w * 0.03 + w * 0.085, w * 0.045), p_to(m_khe))
    elif khung == "trinh_duyet":
        w, h = aw, ah
        x0, y0 = m, m
        r = min(w, h) * 0.035
        th = min(w, h) * 0.1
        bong(cv, x0, y0, x0 + w, y0 + h, r, min(w, h) * 0.06, 0.45, dy=min(w, h) * 0.02)
        hop(cv, x0, y0, x0 + w, y0 + h, r, B["the"])
        for k_, mau in enumerate(m_cham[:3]):
            cv.drawCircle(x0 + th * (0.45 + 0.32 * k_), y0 + th / 2, th * 0.1, p_to(c.mau(mau)))
        ux0, ux1 = x0 + th * 1.6, x0 + w - th * 0.4
        hop(cv, ux0, y0 + th * 0.2, ux1, y0 + th * 0.8, th * 0.3, B["the2"])
        if p.get("chu"):
            dat(cv, anh_chu(c, str(p.get("chu")), th * 0.3, B["phu"], vai="than"), ux0 + th * 0.35, y0 + th / 2, "ml")
        cv.save(); cv.clipRRect(rr(x0, y0, x0 + w, y0 + h, r), True)
        anh_vao(x0, y0 + th, x0 + w, y0 + h, 0)
        cv.restore()
    else:
        w = min(aw, ah * ar); h = w / ar
        x0, y0 = (W - w) / 2, (H - h) / 2
        r = min(w, h) * 0.05
        bong(cv, x0, y0, x0 + w, y0 + h, r, min(w, h) * 0.07, 0.45, dy=min(w, h) * 0.025)
        anh_vao(x0, y0, x0 + w, y0 + h, r)
        cv.drawRRect(rr(x0, y0, x0 + w, y0 + h, r), p_net("#ffffff", max(1.5, min(w, h) * 0.006), 0.5, False))
    if abs(g) > 0.01:                                    # xoay bằng OpenCV trên ảnh nhân trước alpha (skia CPU xoay ảnh lớn ~200 ms)
        a = surf2.makeImageSnapshot().toarray(colorType=skia.kBGRA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
        Mx = cv2.getRotationMatrix2D((W / 2, H / 2), -g, 1.0)
        a = cv2.warpAffine(a, Mx, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
        b, g_, r_, al = cv2.split(a)
        return cv2.merge([cv2.divide(r_, al, scale=255.0), cv2.divide(g_, al, scale=255.0), cv2.divide(b, al, scale=255.0), al])
    return ra(surf)


# ---------------------------------------------------------------- trước – sau
@dang_ky(**_the(
    id="mau.truoc-sau", ten="So sánh trước – sau (kéo thanh trượt)",
    mo_ta="Hai ảnh chồng nhau, thanh trượt quét ngang lộ dần ảnh SAU rồi dừng giữa; nhãn TRƯỚC/SAU hai góc. Không có ảnh: hai mảng chữ.",
    hop_nghia=["trước sau", "thay đổi", "biến đổi", "kết quả", "chỉnh màu", "trước khi", "sau khi"],
    tham_so={"truoc": "ảnh trước (id kho / đường dẫn)", "sau": "ảnh sau", "chu_truoc": "chữ thay ảnh trước / nhãn (TRƯỚC)",
             "chu_sau": "chữ thay ảnh sau / nhãn (SAU)", "bat_dau": "giây bắt đầu quét (0.4)", "quet": "giây quét (1.4)",
             "dung": "vị trí thanh khi dừng 0..1 (0.5)", "bo": "bo góc, phần cạnh ngắn (0.05)"},
    mac_dinh={"chu_truoc": "Trước", "chu_sau": "Sau", "bat_dau": 0.4, "quet": 1.4, "dung": 0.5, "bo": 0.05},
    hop={"anchor": "mc", "x": 0.5, "y": 0.42, "w": 0.9, "h": 0.4}, dong=True, sfx_goi_y=["whoosh trượt", "click"],
    vi_du={"truoc": "nen.img020-6806", "sau": "anh.benj-villena-custom-presets-3d69", "chu_truoc": "Ảnh gốc", "chu_sau": "Sau chỉnh màu", "quet": 1.6}))
def truoc_sau(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font = p.get("font") or "nhan"
    m = 0.03 * min(W, H)
    x0, y0, x1, y1 = m, m, W - m, H - m
    r = float(p.get("bo", 0.05)) * min(W, H)
    u = min(W, H) / 500.0
    ia, ib = anh(c, p.get("truoc"), int(max(W, H) * 1.1)), anh(c, p.get("sau"), int(max(W, H) * 1.1))
    bong(cv, x0, y0, x1, y1, r, 30 * u, 0.45, dy=8 * u)

    def mat(img, chu, mau, x_a, x_b):
        cv.save(); cv.clipRRect(rr(x0, y0, x1, y1, r), True); cv.clipRect(skia.Rect.MakeLTRB(x_a, y0, x_b, y1))
        if img is not None:
            ve_anh_phu(cv, img, x0, y0, x1, y1)
        else:
            cv.drawRect(skia.Rect.MakeLTRB(x0, y0, x1, y1), p_to(mau))
            co = vua(c, chu, (y1 - y0) * 0.16, (x1 - x0) * 0.8, 1, 2, vai=font)
            dat(cv, anh_chu(c, chu, co, chu_tren(mau), vai=font, rong=(x1 - x0) * 0.8, can="giua"), (x0 + x1) / 2, (y0 + y1) / 2, "mc")
        cv.restore()
    k = e_io(tien(t, float(p.get("bat_dau", 0.4)), float(p.get("quet", 1.4))))
    dung = kep(float(p.get("dung", 0.5)), 0, 1)
    # thanh đi từ phải sang trái hết (lộ cả SAU) rồi lùi về vị trí dừng
    if k < 0.7:
        vt = 1 - e_out(k / 0.7)
    else:
        vt = dung * e_io((k - 0.7) / 0.3)
    xs = x0 + (x1 - x0) * kep(vt)
    mat(ia, str(p.get("chu_truoc") or ""), B["the2"], x0, xs)
    mat(ib, str(p.get("chu_sau") or ""), B["nhan"], xs, x1)
    cv.drawRRect(rr(x0, y0, x1, y1, r), p_net("#ffffff", max(1.5, 2.5 * u), 0.35, False))
    for chu, ben, al in ((str(p.get("chu_truoc") or ""), 0, kep((xs - x0) / ((x1 - x0) * 0.25))), (str(p.get("chu_sau") or ""), 1, kep((x1 - xs) / ((x1 - x0) * 0.25)))):
        if not chu:
            continue
        im = anh_chu(c, chu.upper(), 22 * u, "#ffffff", vai=font, gian=0.1)
        tw, th = kich(im)
        px = x0 + 18 * u if ben == 0 else x1 - 18 * u - tw - 28 * u
        hop(cv, px, y0 + 18 * u, px + tw + 28 * u, y0 + 18 * u + th + 16 * u, (th + 16 * u) / 2, "#000000", 0.55 * al)
        dat(cv, im, px + 14 * u, y0 + 26 * u, "tl", al)
    if 0.002 < vt < 0.998 or k > 0:
        cv.drawLine(xs, y0, xs, y1, p_net("#ffffff", max(2, 3.5 * u), 1, False))
        hr = 22 * u
        cy = (y0 + y1) / 2
        bong(cv, xs - hr, cy - hr, xs + hr, cy + hr, hr, 14 * u, 0.4)
        cv.drawCircle(xs, cy, hr, p_to("#ffffff"))
        for s_ in (-1, 1):
            cv.drawPath(duong_gap([(xs + s_ * hr * 0.2, cy - hr * 0.35), (xs + s_ * hr * 0.55, cy), (xs + s_ * hr * 0.2, cy + hr * 0.35)]),
                        p_net(B["nhan"] if B["tong"] != "sang" else B["chu"], max(1.5, 3 * u)))
    return ra(surf)
