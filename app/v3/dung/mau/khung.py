# -*- coding: utf-8 -*-
"""MẪU KHUNG (mũi Mẫu 2) — biến đổi/viền cả khung hoặc khối khung đặc biệt: khung hình lồng trên nền lụa, đếm ngược 3-2-1,
khung ống kính quay phim (REC), dải phim điện ảnh (letterbox).
"""
import math

import cv2
import numpy as np
import skia

from dung import chu as _chu
from dung.mau import dang_ky
from dung.mau.chu_hieu_ung import (kep, pha, e_out, e_in_out, e_back, lo_xo, rgba, mau_sk, be_mat, ra_np, kieu_dang, bo_chu,
                                   chuoi, but_net, nen_hop, nhoe_np, np_premul, unpremul_rgba, s_px, toi_di)

HOP_KHUNG = {"anchor": "tl", "x": 0, "y": 0, "w": 1, "h": 1}


# ---------------------------------------------------------------- nền lụa ----
def _nen_lua(W, H, toi, nhan, t, troi=0.12, do_nhan=0.18, hat=7, nho=False):
    """nền tối dạng lụa: sóng sáng mềm trên màu tối của phong cách, ánh màu nhấn rất nhẹ, trôi chậm theo t.
    nho=True → trả ảnh float32 ở 1/8 (để ghép bóng trước khi phóng)"""
    sw, sh = max(8, W // 8), max(8, H // 8)
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
    xx /= sw; yy /= sh
    rng = np.random.RandomState(hat)
    f = np.zeros((sh, sw), np.float32)
    for _ in range(5):
        a, b, c_, ph, v = rng.uniform(2, 7), rng.uniform(2, 7), rng.uniform(0.3, 1.0), rng.uniform(0, 6.3), rng.uniform(-1, 1)
        f += c_ * np.sin(xx * a + yy * b + ph + v * troi * t * 2 * math.pi)
    f = (f - f.min()) / (f.max() - f.min() + 1e-6)
    f = cv2.GaussianBlur(f, (0, 0), 2.0)
    base = np.array(toi[:3], np.float32)
    acc = np.array(nhan[:3], np.float32)
    img = base[None, None, :] * (0.65 + 0.7 * f[..., None]) + acc[None, None, :] * (do_nhan * f[..., None] ** 3) + 22 * f[..., None] ** 4
    if nho:
        return img
    return cv2.resize(np.clip(img, 0, 255).astype(np.uint8), (W, H), interpolation=cv2.INTER_CUBIC)


_MN = {}


def _mat_na_bo(w, h, r):
    """mặt nạ bo góc khử răng cưa (uint8 h×w) — cache"""
    k = (w, h, int(r))
    m = _MN.get(k)
    if m is None:
        s, cv = be_mat(w, h)
        pt = skia.Paint(AntiAlias=True); pt.setColor(skia.ColorBLACK)
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeWH(w, h), r, r), pt)
        m = np_premul(s.makeImageSnapshot())[..., 3].copy()
        if len(_MN) > 40:
            _MN.clear()
        _MN[k] = m
    return m


@dang_ky(id="mau.man-hinh-long", nhom="khung", ten="Khung hình lồng trên nền lụa",
         mo_ta="cả khung thu vào thành thẻ bo góc nổi bóng trên nền tối dạng lụa (tự tạo theo màu phong cách), chừa chỗ cho tiêu đề — tạo 'cảnh mới' khi chỉ có một góc máy",
         hop_nghia=["đổi cảnh", "quy trình", "liệt kê", "bằng chứng", "tiêu đề", "trình bày"],
         tham_so={"ti_le": "cỡ thẻ so với khung 0.5..0.9 (0.74)", "y": "tâm thẻ theo chiều dọc 0..1 (0.58)", "bo": "bo góc px@1080 (40)",
                  "vao": "giây thu vào (0.35)", "ra": "giây trả về cuối lớp (0.3; 0 = không)", "mau_nen": "màu tối của nền (toi)",
                  "mau_anh": "ánh màu trên nền (nhan)", "do_anh": "0..1 độ ánh màu (0.18)", "troi": "tốc độ trôi lụa (0.12)",
                  "vien": "viền thẻ px@1080 (0)", "mau_vien": "sang", "bong": "0..1 bóng thẻ (0.6)", "anh_nen": "id kho / đường dẫn ảnh nền thay lụa (tuỳ)"},
         mac_dinh={"ti_le": 0.74, "y": 0.58, "bo": 40, "vao": 0.35, "ra": 0.3, "mau_nen": "toi", "mau_anh": "nhan", "do_anh": 0.18,
                   "troi": 0.12, "vien": 0, "mau_vien": "sang", "bong": 0.6},
         hop=HOP_KHUNG, toan_khung=True, lam_nen=True, dong=True,
         sfx_goi_y=["whoosh thu nhỏ", "trượt mềm"],
         vi_du={"vien": 4})
def man_hinh_long(t, dur, W, H, c, p):
    vao, ra = float(p.get("vao", 0.35)), float(p.get("ra", 0.3))
    u = e_in_out(pha(t, 0, vao))
    if ra > 0 and t > dur - ra:
        u = min(u, e_in_out((dur - t) / ra))
    s_cuoi = kep(float(p.get("ti_le", 0.74)), 0.3, 1.0)
    s = 1 - (1 - s_cuoi) * u
    w, h = max(2, int(round(W * s))), max(2, int(round(H * s)))
    cy = H / 2 + (float(p.get("y", 0.58)) - 0.5) * H * u
    x0, y0 = int(round(W / 2 - w / 2)), int(round(cy - h / 2))
    nen = nen_hop(c, t, W, H)
    if nen is not None and u <= 0.002:
        return cv2.cvtColor(np.ascontiguousarray(nen[..., :3]), cv2.COLOR_RGB2RGBA)
    # nền: ảnh kho hoặc lụa; bóng thẻ ghép ở độ phân giải thấp rồi mới phóng (nhanh)
    b = float(p.get("bong", 0.6)) * u
    anh = _anh_nen(c, p["anh_nen"], W, H) if p.get("anh_nen") else None
    if anh is None:
        nho = _nen_lua(W, H, rgba(c, p.get("mau_nen"), "toi"), rgba(c, p.get("mau_anh"), "nhan"), t, float(p.get("troi", 0.12)),
                       float(p.get("do_anh", 0.18)), nho=True)
    else:
        nho = cv2.resize(anh, (max(8, W // 8), max(8, H // 8)), interpolation=cv2.INTER_AREA).astype(np.float32)
    if b > 0.01:
        k = W / nho.shape[1]
        sm = np.zeros(nho.shape[:2], np.float32)
        dy = H * 0.012
        cv2.rectangle(sm, (int(x0 / k), int((y0 + dy) / k)), (int((x0 + w) / k), int((y0 + h + dy) / k)), 1.0, -1)
        sm = cv2.GaussianBlur(sm, (0, 0), max(0.8, H * 0.014 / k))
        nho = nho * (1 - b * 0.75 * sm)[..., None]
    bg = cv2.resize(np.clip(nho, 0, 255).astype(np.uint8), (W, H), interpolation=cv2.INTER_CUBIC) if anh is None or b > 0.01 else anh
    if nen is not None and u < 0.999:
        bg = cv2.addWeighted(bg, u, np.ascontiguousarray(nen[..., :3]), 1 - u, 0)
    out = cv2.cvtColor(bg, cv2.COLOR_RGB2RGBA)
    r = s_px(c, float(p.get("bo", 40))) * u
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w), min(H, y0 + h)
    if xb > xa and yb > ya:
        m = _mat_na_bo(w, h, r)[ya - y0:yb - y0, xa - x0:xb - x0]
        if nen is not None:
            the = cv2.resize(np.ascontiguousarray(nen[..., :3]), (w, h), interpolation=cv2.INTER_AREA)[ya - y0:yb - y0, xa - x0:xb - x0]
            the = cv2.cvtColor(the, cv2.COLOR_RGB2RGBA)
            mf = m.astype(np.float32) * (1 / 255.0)
            out[ya:yb, xa:xb] = cv2.blendLinear(the, np.ascontiguousarray(out[ya:yb, xa:xb]), mf, 1 - mf)
        else:                                   # thiếu nền thật: khoét lỗ (thấy video bên dưới, không thu nhỏ được)
            out[ya:yb, xa:xb, 3] = 255 - m
    vw = float(p.get("vien", 0))
    if vw > 0 and u > 0.02:
        q = skia.Path()
        q.addRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x0, y0, w, h), r, r))
        pm = skia.PathMeasure(q, True)
        L = pm.getLength()
        n = max(16, int(L / 6))
        pts = np.array([[pm.getPosTan(L * i / n)[0].fX, pm.getPosTan(L * i / n)[0].fY] for i in range(n)])
        col = rgba(c, p.get("mau_vien"), "sang")
        cv2.polylines(out, [np.round(pts * 4).astype(np.int32)], True, (col[0], col[1], col[2], 255),
                      max(1, int(round(s_px(c, vw)))), cv2.LINE_AA, 2)
    return out


_ANH = _chu.CacheAnh("mau.khung._ANH")      # 1.2.21: trần RAM chung (cau_hinh cache_anh_mb)


def _anh_nen(c, id_, W, H):
    k = (str(id_), W, H)
    if k in _ANH:
        return _ANH[k]
    a = None
    try:
        pth = c.tai_nguyen(id_) or (id_ if isinstance(id_, str) else None)
        if pth:
            im = cv2.imdecode(np.fromfile(pth, np.uint8), cv2.IMREAD_COLOR)
            if im is not None:
                ih, iw = im.shape[:2]
                sc = max(W / iw, H / ih)
                im = cv2.resize(im, (int(iw * sc + 1), int(ih * sc + 1)), interpolation=cv2.INTER_AREA)
                y0, x0 = (im.shape[0] - H) // 2, (im.shape[1] - W) // 2
                a = cv2.cvtColor(im[y0:y0 + H, x0:x0 + W], cv2.COLOR_BGR2RGB)
    except Exception:
        a = None
    _ANH[k] = a
    return a


# ---------------------------------------------------------------- đếm ngược ----
@dang_ky(id="mau.dem-3-2-1", nhom="khung", ten="Đếm ngược 3-2-1",
         mo_ta="số đếm ngược to bật lò xo giữa vòng tròn, cung tiến độ quét hết mỗi nhịp; kết bằng một chữ chốt (tuỳ) — mở màn, thử thách, sắp tiết lộ",
         hop_nghia=["đếm ngược", "sắp bắt đầu", "thử thách", "chuẩn bị", "hồi hộp"],
         tham_so={"tu": "số bắt đầu (3)", "nhip": "giây mỗi số (1.0)", "chu_cuoi": "chữ chốt sau số 1 (tuỳ, vd 'Bắt đầu!')",
                  "mau_so": "màu số (sang)", "mau_vong": "màu cung tiến độ (nhan)", "nen": "màu nền tròn (toi; null = không)", "do_nen": "độ đục nền (0.6)",
                  "day_vong": "dày vòng (× bán kính, 0.07)", "font": "font số (tieu_de)", "mau_chu_cuoi": "màu chữ chốt (nhan)"},
         mac_dinh={"tu": 3, "nhip": 1.0, "mau_so": "sang", "mau_vong": "nhan", "nen": "toi", "do_nen": 0.6, "day_vong": 0.07, "font": "tieu_de",
                   "mau_chu_cuoi": "nhan"},
         hop={"anchor": "mc", "x": 0.5, "y": 0.45, "w": 0.6, "h": 0.34}, dong=True,
         sfx_goi_y=["tích tắc đếm ngược", "bíp đếm", "gong bắt đầu"],
         vi_du={"tu": 3, "nhip": 0.75, "chu_cuoi": "Bắt đầu!"})
def dem_nguoc(t, dur, W, H, c, p):
    s, cv = be_mat(W, H)
    n0 = max(1, int(p.get("tu", 3)))
    nh = max(0.2, float(p.get("nhip", 1.0)))
    R = min(W, H) * 0.44
    cx, cy = W / 2, H / 2
    k = int(t // nh)
    tl = t - k * nh
    chot = chuoi(p.get("chu_cuoi"))
    xong = k >= n0
    if p.get("nen") and not (xong and chot):
        pt = skia.Paint(AntiAlias=True)
        pt.setColor(mau_sk(c, p.get("nen"), "toi", float(p.get("do_nen", 0.6)) * e_out(pha(t, 0, 0.2))))
        cv.drawCircle(cx, cy, R * (0.85 + 0.15 * e_out(pha(t, 0, 0.25))), pt)
    dv = float(p.get("day_vong", 0.07)) * R
    if not xong:
        # vòng nền + cung còn lại
        tr = but_net(mau_sk(c, p.get("mau_so"), "sang", 0.18), dv)
        cv.drawCircle(cx, cy, R - dv, tr)
        con = 1 - tl / nh
        q = skia.Path()
        q.addArc(skia.Rect.MakeLTRB(cx - R + dv, cy - R + dv, cx + R - dv, cy + R - dv), -90, -360 * con)
        cv.drawPath(q, but_net(mau_sk(c, p.get("mau_vong"), "nhan"), dv))
        so = str(n0 - k)
        kd = kieu_dang(c, {"mau_chu": p.get("mau_so", "sang"), "font": p.get("font", "tieu_de"), "bong": 0.5}, "tieu_de", "sang")
        bc = bo_chu(c, so, kd, R * 1.45, R * 1.3, co_hop=1.2)
        u = pha(tl, 0, 0.45)
        sc = 0.4 + 0.6 * lo_xo(u, 5.5, 1.3)
        ra = pha(tl, nh - 0.15, 0.15)
        sc *= 1 - 0.25 * ra
        ox, oy = bc.goc(W, H)
        bc.ve_khoi(cv, ox, oy, op=e_out(u * 3) * (1 - ra), sc=sc)
    elif chot:
        kd = kieu_dang(c, {"mau_chu": p.get("mau_chu_cuoi", "nhan"), "font": p.get("font", "tieu_de"), "bong": 0.6, "hoa": True}, "tieu_de", "nhan")
        bc = bo_chu(c, chot, kd, W * 0.95, H * 0.6)
        u = pha(tl if k == n0 else nh, 0, 0.5)
        ox, oy = bc.goc(W, H)
        bc.ve_khoi(cv, ox, oy, op=e_out(u * 3), sc=0.5 + 0.5 * lo_xo(u, 5, 1.2))
    return ra_np(s)


# ---------------------------------------------------------------- khung ống kính ----
_TINH = _chu.CacheAnh("mau.khung._TINH")      # 1.2.21: trần RAM chung


def _tc(t, fps):
    f = int(round(t * fps))
    s_, fr = divmod(f, int(round(fps)))
    m, s_ = divmod(s_, 60)
    h, m = divmod(m, 60)
    return "%02d:%02d:%02d:%02d" % (h, m, s_, fr)


@dang_ky(id="mau.ong-kinh", nhom="khung", ten="Khung ống kính quay (REC)",
         mo_ta="phủ khung máy quay: 4 góc ngắm, chấm REC nhấp nháy, mã thời gian chạy, lưới 1/3 mờ — cảnh hậu trường, vlog, 'đang quay', bằng chứng thật",
         hop_nghia=["quay phim", "hậu trường", "vlog", "đang quay", "camera", "thật"],
         tham_so={"mau": "màu nét (sang)", "mau_rec": "màu chấm REC (vai|#hex, mặc định nhan — màu nhấn của video)", "le": "lề góc ngắm (× cạnh ngắn, 0.06)", "dai_goc": "độ dài góc (× cạnh ngắn, 0.1)",
                  "day": "dày nét px@1080 (5)", "luoi": "true = lưới 1/3", "tam": "true = dấu + ở tâm", "nhan": "chữ cạnh REC (REC)",
                  "tc_bat_dau": "giây bắt đầu mã thời gian (0)", "nhap_nhay": "Hz chấm REC (1)", "do_dac": "0..1 độ đục (0.9)"},
         mac_dinh={"mau": "sang", "mau_rec": "nhan", "le": 0.06, "dai_goc": 0.1, "day": 5, "luoi": True, "tam": True, "nhan": "REC",
                   "tc_bat_dau": 0, "nhap_nhay": 1.0, "do_dac": 0.9},
         hop=HOP_KHUNG, toan_khung=True, dong=True,
         sfx_goi_y=["bíp máy quay", "tiếng màn trập"],
         vi_du={})
def ong_kinh(t, dur, W, H, c, p):
    mn = min(W, H)
    le, dg = float(p.get("le", 0.06)) * mn, float(p.get("dai_goc", 0.1)) * mn
    day = max(1.5, s_px(c, float(p.get("day", 5))))
    a = kep(float(p.get("do_dac", 0.9)))
    co = mn * 0.045
    key = (W, H, le, dg, day, p.get("mau"), bool(p.get("luoi", True)), bool(p.get("tam", True)), chuoi(p.get("nhan", "REC")), a)
    st = _TINH.get(key)
    if st is None:
        s, cv = be_mat(W, H)
        pt = but_net(mau_sk(c, p.get("mau"), "sang", a), day, cap=False)
        pt.setStrokeJoin(skia.Paint.kMiter_Join)
        for (x, y, sx, sy) in ((le, le, 1, 1), (W - le, le, -1, 1), (W - le, H - le, -1, -1), (le, H - le, 1, -1)):
            q = skia.Path(); q.moveTo(x, y + sy * dg); q.lineTo(x, y); q.lineTo(x + sx * dg, y)
            cv.drawPath(q, pt)
        if p.get("luoi", True):
            g = but_net(mau_sk(c, p.get("mau"), "sang", a * 0.22), max(1.0, day * 0.3), cap=False)
            for f in (1 / 3, 2 / 3):
                cv.drawLine(W * f, le, W * f, H - le, g)
                cv.drawLine(le, H * f, W - le, H * f, g)
        if p.get("tam", True):
            g = but_net(mau_sk(c, p.get("mau"), "sang", a * 0.8), max(1.0, day * 0.5), cap=False)
            L = mn * 0.03
            cv.drawLine(W / 2 - L, H / 2, W / 2 + L, H / 2, g)
            cv.drawLine(W / 2, H / 2 - L, W / 2, H / 2 + L, g)
        nhan = chuoi(p.get("nhan", "REC"))
        if nhan:
            kd = kieu_dang(c, {"mau_chu": p.get("mau", "sang"), "font": "phu_de", "co": round(co, 1), "bong": 0.4}, "phu_de", "sang")
            bc = bo_chu(c, nhan, kd, W * 0.4, co * 2)
            bc.ve_khoi(cv, round(le + dg * 0.35 + co * 1.3), round(le + dg * 0.35 - bc.tren), op=a)
        st = unpremul_rgba(np_premul(s.makeImageSnapshot()))
        _TINH[key] = st
    out = st.copy()
    # chấm REC
    if int(t * float(p.get("nhap_nhay", 1.0)) * 2) % 2 == 0:
        r_, g_, b_, _ = rgba(c, p.get("mau_rec"), "nhan")
        S = 8
        cxr, cyr = le + dg * 0.35 + co * 0.5, le + dg * 0.35 + co * 0.55
        cv2.circle(out, (int(cxr * S), int(cyr * S)), int(co * 0.36 * S), (r_, g_, b_, int(255 * a)), -1, cv2.LINE_AA, 3)
    # mã thời gian
    tc = _tc(float(p.get("tc_bat_dau", 0)) + t, c.fps or 30)
    kd = kieu_dang(c, {"mau_chu": p.get("mau", "sang"), "font": "phu_de", "co": round(co * 0.9, 1), "bong": 0.4}, "phu_de", "sang")
    bc = bo_chu(c, "00:00:00:00", kd, W * 0.6, co * 2, tach="ky_tu")
    w_, h_ = int(bc.w + co), int(bc.duoi - bc.tren + co)
    s2, cv2_ = be_mat(w_, h_)
    ox, oy = int(co * 0.5), int(co * 0.5 - bc.tren)
    for i, ch in enumerate(tc[:len(bc.phan)]):
        bc.ve_phan(cv2_, i, ox, oy, txt=ch, op=a)
    nho = unpremul_rgba(np_premul(s2.makeImageSnapshot()))
    x0, y0 = int(W - le - dg * 0.35 - w_), int(le + dg * 0.35 - co * 0.3)
    xa, ya, xb, yb = max(0, x0), max(0, y0), min(W, x0 + w_), min(H, y0 + h_)
    if xb > xa and yb > ya:
        sub = nho[ya - y0:yb - y0, xa - x0:xb - x0].astype(np.float32)
        al = sub[..., 3:4] / 255
        o = out[ya:yb, xa:xb].astype(np.float32)
        o[..., :3] = o[..., :3] * (1 - al) + sub[..., :3] * al
        o[..., 3:4] = np.maximum(o[..., 3:4], sub[..., 3:4])
        out[ya:yb, xa:xb] = o.astype(np.uint8)
    return out


# ---------------------------------------------------------------- dải phim điện ảnh ----
@dang_ky(id="mau.vien-phim", nhom="khung", ten="Dải phim điện ảnh (letterbox)",
         mo_ta="hai dải tối trượt vào trên/dưới (hoặc trái/phải) tạo khung hình điện ảnh — đoạn kể chuyện, hồi tưởng, cảnh 'phim'",
         hop_nghia=["điện ảnh", "kể chuyện", "hồi tưởng", "nghiêm túc", "cinematic"],
         tham_so={"day": "bề dày mỗi dải (× chiều cao khung, 0.1)", "ti_le": "tỉ lệ khung hình nhìn thấy (vd 2.39) — có thì thay day",
                  "mau": "màu dải (#000000)", "dai": "giây trượt vào (0.5)", "ra": "true = trượt ra ở cuối", "dai_ra": "giây ra (0.4)", "huong": "doc|ngang (doc = trên/dưới)"},
         mac_dinh={"day": 0.1, "mau": "#000000", "dai": 0.5, "ra": True, "dai_ra": 0.4, "huong": "doc"},
         hop=HOP_KHUNG, toan_khung=True, dong=True,
         sfx_goi_y=["trầm điện ảnh", "whoosh chậm"],
         vi_du={})
def vien_phim(t, dur, W, H, c, p):
    u = e_in_out(pha(t, 0, float(p.get("dai", 0.5))))
    if p.get("ra", True):
        dr = float(p.get("dai_ra", 0.4))
        u = min(u, e_in_out((dur - t) / max(dr, 1e-3)) if t > dur - dr else 1.0)
    doc = p.get("huong", "doc") != "ngang"
    if p.get("ti_le"):
        tl = float(p["ti_le"])
        b = max(0.0, (H - W / tl) / 2) if doc else max(0.0, (W - H * tl) / 2)
    else:
        b = float(p.get("day", 0.1)) * (H if doc else W)
    b *= u
    out = np.zeros((H, W, 4), np.uint8)
    r_, g_, b_, a_ = rgba(c, p.get("mau"), "toi")
    bi = int(b)
    fr = b - bi
    col = np.array([r_, g_, b_, a_], np.uint8)
    if doc:
        if bi > 0:
            out[:bi] = col; out[H - bi:] = col
        if fr > 0.01 and bi < H // 2:
            out[bi] = (r_, g_, b_, int(a_ * fr)); out[H - bi - 1] = (r_, g_, b_, int(a_ * fr))
    else:
        if bi > 0:
            out[:, :bi] = col; out[:, W - bi:] = col
        if fr > 0.01 and bi < W // 2:
            out[:, bi] = (r_, g_, b_, int(a_ * fr)); out[:, W - bi - 1] = (r_, g_, b_, int(a_ * fr))
    return out
