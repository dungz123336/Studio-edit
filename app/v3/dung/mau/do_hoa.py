# -*- coding: utf-8 -*-
"""MẪU ĐỒ HOẠ CHỈ DẪN (mũi Mẫu 2) — tín hiệu chọn lọc chỉ cho mắt chỗ cần nhìn: mũi tên vẽ dần, khoanh tay, gạch chân,
đóng khung, viền ôm + nhãn viết tay, làm tối ngoài vùng, bút dạ quét, gạch xoá, mũi tên cong vẽ tay, lấp lánh, sticker nhãn.

QUY ƯỚC HỘP: hộp của lớp (vi_tri) = VÙNG được chỉ dẫn (khoanh/khung/gạch nằm trong hộp, chừa lề cho nét + bóng).
Ngoại lệ: lam-toi-ngoai chiếm cả khung (vùng sáng = tham số `vung` theo toạ độ khung 0..1).
Độ dày nét `day` tính bằng px ở khung rộng 1080 (tự co theo khung thật). Màu mặc định = vai nhấn của phong cách.
"""
import math, random

import cv2
import numpy as np
import skia

from dung.mau import dang_ky
from dung.mau.chu_hieu_ung import (
    SAMP, SAMP_NONE, kep, pha, e_out, e_in_out, e_back, lo_xo, tron, s_px, rgba, mau_sk, be_mat, ra_np, rong,
    kieu_dang, bo_chu, chuoi, duong_muot, cat_duong, but_net, mau_tuong_phan, nen_hop, nhoe_np, np_premul, sk_premul,
    unpremul_rgba, bong_np, anh_mo, _elip_tay, ve_xoay)

TS_NET = {"mau": "màu nét: vai (nhan|nhan2|sang|toi) hoặc #hex", "day": "độ dày nét px@1080 (10)", "ve": "giây vẽ (0.45)",
          "tre": "giây trước khi vẽ (0)", "bong": "0..1 bóng mềm dưới nét (0.4)", "run": "0..2 độ run tay (1)", "hat": "hạt ngẫu nhiên (1)"}


def _ts(**kw):
    d = dict(TS_NET)
    d.update(kw)
    return d


def _md(**kw):
    d = {"mau": "nhan", "day": 10, "ve": 0.45, "tre": 0.0, "bong": 0.4, "run": 1.0, "hat": 1}
    d.update(kw)
    return d


def _day(c, p, md=10):
    return max(1.5, s_px(c, p.get("day", md)))


def _ra(s, p, day):
    b = float(p.get("bong", 0.4))
    return ra_np(s, bong=(day * 0.45, day * 0.7, b * 0.8) if b > 0 else None)


def _u(t, p):
    return e_in_out(pha(t, float(p.get("tre", 0)), float(p.get("ve", 0.45))))


def _ve_nhan(c, cv, text, cx, cy, w_max, h_max, u, nen="nhan", mau_chu=None, font="nhan", ax=0.5, ay=0.5, p=None):
    """nhãn pill: chữ vừa (w_max,h_max), nền màu `nen`, bật vào theo u → hộp (x0,y0,x1,y1)"""
    p = p or {}
    mc = mau_chu or mau_tuong_phan(c, nen)
    kd = kieu_dang(c, {"mau_chu": mc, "font": p.get("font_nhan", font), "co": p.get("co_nhan"), "bong": 0,
                       "kieu_dang": p.get("kieu_dang_nhan")}, font, mc)
    bc = bo_chu(c, text, kd, w_max / 1.5, h_max / 1.45)
    cao = bc.duoi - bc.tren
    dx, dy = bc.co * 0.45, bc.co * 0.22
    bw, bh = bc.w + 2 * dx, cao + 2 * dy
    x0, y0 = cx - bw * ax, cy - bh * ay
    if u <= 0:
        return (x0, y0, x0 + bw, y0 + bh)
    sc = 0.7 + 0.3 * e_back(u, 1.8) if u < 1 else 1.0
    pcx, pcy = x0 + bw / 2, y0 + bh / 2
    cv.save()
    cv.translate(pcx, pcy); cv.scale(sc, sc); cv.translate(-pcx, -pcy)
    pt = skia.Paint(AntiAlias=True)
    pt.setColor(mau_sk(c, nen, "nhan", kep(u * 3)))
    r = min(bh / 2, bc.co * 0.6)
    cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x0, y0, bw, bh), r, r), pt)
    bc.ve_khoi(cv, round(x0 + dx), round(y0 + dy - bc.tren), op=kep(u * 3))
    cv.restore()
    return (x0, y0, x0 + bw, y0 + bh)


def _hop_nhan(c, p, W, H, text, font="nhan"):
    """chiều cao dải dành cho nhãn (0 nếu không có nhãn)"""
    if not text:
        return 0.0
    return min(H * 0.32, max(s_px(c, 70), H * 0.16)) if p.get("co_nhan") is None else s_px(c, float(p["co_nhan"]) * 1.6)


# ---------------------------------------------------------------- khoanh tay ----
@dang_ky(id="mau.khoanh", nhom="do_hoa", ten="Khoanh tròn vẽ tay",
         mo_ta="vòng elip vẽ tay chạy quanh đúng vùng đang được gọi tên (hộp = vùng cần khoanh), vượt điểm đầu một chút như nét thật",
         hop_nghia=["chỉ chỗ", "chú ý", "đây", "khoanh", "quan trọng", "nút bấm"],
         tham_so=_ts(vong="số vòng (1.12)", nhan="nhãn ngắn phía trên (tuỳ)", mau_nhan_nen="màu nền nhãn (= mau)", le="lề trong hộp (0..0.3, 0.06)"),
         mac_dinh=_md(vong=1.12, le=0.06),
         hop={"anchor": "mc", "x": 0.5, "y": 0.45, "w": 0.5, "h": 0.16}, dong=True,
         sfx_goi_y=["bút vẽ vòng", "sột soạt bút dạ"],
         vi_du={"nhan": "Bấm vào đây"})
def khoanh(t, dur, W, H, c, p):
    day = _day(c, p)
    s, cv = be_mat(W, H)
    nhan = chuoi(p.get("nhan"))
    hn = _hop_nhan(c, p, W, H, nhan)
    m = day * 1.6 + float(p.get("le", 0.06)) * min(W, H)
    run = float(p.get("run", 1.0))
    pts = _elip_tay(m, hn + m, W - m, H - m, hat=int(p.get("hat", 1)), vong=float(p.get("vong", 1.12)), run=0.03 * run)
    d, _, _ = cat_duong(duong_muot(pts), _u(t, p))
    cv.drawPath(d, but_net(mau_sk(c, p.get("mau"), "nhan"), day))
    if nhan:
        _ve_nhan(c, cv, nhan, W / 2, hn / 2, W * 0.9, hn * 0.9, e_out(pha(t, float(p.get("tre", 0)) + 0.25, 0.3)),
                 nen=p.get("mau_nhan_nen") or p.get("mau", "nhan"), p=p)
    return _ra(s, p, day)


# ---------------------------------------------------------------- gạch chân ----
@dang_ky(id="mau.gach-chan", nhom="do_hoa", ten="Gạch chân vẽ tay",
         mo_ta="nét gạch dưới chân dòng chữ/ô đang được đọc (hộp = dòng cần gạch), vẽ trái→phải: lượn sóng, thẳng run tay, đôi, hoặc cong cười",
         hop_nghia=["nhấn mạnh", "gạch chân", "dòng này", "lưu ý", "từ khoá"],
         tham_so=_ts(kieu="song|thang|doi|cong (song)", song="biên độ sóng (× dày, 0.6)", so_song="số sóng (4)", y="vị trí dọc trong hộp 0..1 (0.86)"),
         mac_dinh=_md(kieu="song", song=0.6, so_song=4, y=0.86),
         hop={"anchor": "mc", "x": 0.5, "y": 0.6, "w": 0.7, "h": 0.06}, dong=True,
         sfx_goi_y=["bút gạch nhanh", "vút bút"],
         vi_du={"kieu": "song"})
def gach_chan(t, dur, W, H, c, p):
    day = _day(c, p)
    s, cv = be_mat(W, H)
    m = day * 1.4
    yb = kep(float(p.get("y", 0.86)) * H, m + day, H - m - day)
    x0, x1 = m, W - m
    kieu = p.get("kieu", "song")
    rnd = random.Random(int(p.get("hat", 1)))
    run = float(p.get("run", 1.0))
    n = 40
    A = float(p.get("song", 0.6)) * day
    ns = float(p.get("so_song", 4))
    duongs = []
    if kieu == "cong":                       # nét cong "cười": hai đầu cao, giữa võng
        hc = min(H * 0.5, A * 4)
        duongs.append([(x0 + (x1 - x0) * k / n, yb - hc * (1 - math.sin(math.pi * k / n))) for k in range(n + 1)])
    else:
        lan = 2 if kieu == "doi" else 1
        for l in range(lan):
            yy = yb - l * day * 1.9
            ph = rnd.uniform(0, 6.28)
            pts = []
            for k in range(n + 1):
                f = k / n
                y = yy + (A * math.sin(2 * math.pi * ns * f + ph) if kieu == "song" else 0)
                y += run * day * 0.25 * math.sin(f * 5.3 + ph) - run * day * 0.5 * f
                pts.append((x0 + (x1 - x0) * f + (l * day * 2 if l else 0), y))
            duongs.append(pts)
    u = _u(t, p)
    for k, pts in enumerate(duongs):
        uk = kep(u * len(duongs) - k)
        d, _, _ = cat_duong(duong_muot(pts), uk)
        cv.drawPath(d, but_net(mau_sk(c, p.get("mau"), "nhan"), day))
    return _ra(s, p, day)


# ---------------------------------------------------------------- đóng khung ----
def _rrect_path(x0, y0, x1, y1, r, bat="tl"):
    """đường bo góc liền một nét, bắt đầu ở góc trên-trái (bat="tl") hoặc giữa cạnh trên (bat="tc"), chạy thuận chiều kim đồng hồ"""
    r = max(0.0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
    p = skia.Path()
    if bat == "tc":
        p.moveTo((x0 + x1) / 2, y0)
    else:
        p.moveTo(x0 + r, y0)
    p.lineTo(x1 - r, y0)
    p.arcTo(skia.Rect.MakeLTRB(x1 - 2 * r, y0, x1, y0 + 2 * r), -90, 90, False)
    p.lineTo(x1, y1 - r)
    p.arcTo(skia.Rect.MakeLTRB(x1 - 2 * r, y1 - 2 * r, x1, y1), 0, 90, False)
    p.lineTo(x0 + r, y1)
    p.arcTo(skia.Rect.MakeLTRB(x0, y1 - 2 * r, x0 + 2 * r, y1), 90, 90, False)
    p.lineTo(x0, y0 + r)
    p.arcTo(skia.Rect.MakeLTRB(x0, y0, x0 + 2 * r, y0 + 2 * r), 180, 90, False)
    if bat == "tc":
        p.lineTo((x0 + x1) / 2 + 0.5, y0)
    return p


@dang_ky(id="mau.dong-khung", nhom="do_hoa", ten="Đóng khung chạy viền",
         mo_ta="viền chạy vòng quanh một vùng (ô nhập, nút, kết quả — hộp = vùng), rồi gắn nhãn ở mép trên; kiểu liền, nét đứt hoặc chỉ 4 góc",
         hop_nghia=["đóng khung", "vùng này", "kết quả", "ô nhập", "khu vực"],
         tham_so=_ts(kieu="lien|net_dut|goc (lien)", bo="bo góc (0..0.5 của cạnh ngắn, 0.08)", nhan="nhãn (tuỳ)", mau_nhan_nen="màu nền nhãn (= mau)",
                     dai_goc="độ dài nét góc khi kieu=goc (0..0.5, 0.22)"),
         mac_dinh=_md(kieu="lien", bo=0.08, dai_goc=0.22),
         hop={"anchor": "mc", "x": 0.5, "y": 0.45, "w": 0.8, "h": 0.2}, dong=True,
         sfx_goi_y=["vẽ khung", "tick xác nhận"],
         vi_du={"nhan": "Kết quả"})
def dong_khung(t, dur, W, H, c, p):
    day = _day(c, p)
    s, cv = be_mat(W, H)
    nhan = chuoi(p.get("nhan"))
    hn = _hop_nhan(c, p, W, H, nhan) * 0.8
    m = day * 1.4
    x0, y0, x1, y1 = m, m + hn / 2, W - m, H - m
    r = kep(float(p.get("bo", 0.08)), 0, 0.5) * min(x1 - x0, y1 - y0)
    u = _u(t, p)
    pt = but_net(mau_sk(c, p.get("mau"), "nhan"), day)
    kieu = p.get("kieu", "lien")
    if kieu == "goc":
        L = kep(float(p.get("dai_goc", 0.22)), 0.05, 0.5) * min(x1 - x0, y1 - y0) * u
        for (cx, cy, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x1, y1, -1, -1), (x0, y1, 1, -1)):
            q = skia.Path()
            q.moveTo(cx, cy + sy * L); q.lineTo(cx, cy + sy * r); q.quadTo(cx, cy, cx + sx * r, cy); q.lineTo(cx + sx * L, cy)
            cv.drawPath(q, pt)
    else:
        if kieu == "net_dut":
            pt.setPathEffect(skia.DashPathEffect.Make([day * 2.6, day * 1.8], 0))
        d, _, _ = cat_duong(_rrect_path(x0, y0, x1, y1, r), u)
        cv.drawPath(d, pt)
    if nhan:
        _ve_nhan(c, cv, nhan, x0 + max(r, day * 2), y0, W * 0.7, hn * 1.0, e_out(pha(t, float(p.get("tre", 0)) + float(p.get("ve", 0.45)) * 0.6, 0.3)),
                 nen=p.get("mau_nhan_nen") or p.get("mau", "nhan"), ax=0.0, ay=0.5, p=p)
    return _ra(s, p, day)


# ---------------------------------------------------------------- viền ôm + nhãn viết tay ----
@dang_ky(id="mau.vien-om", nhom="do_hoa", ten="Khung bo góc ôm vùng + nhãn viết tay",
         mo_ta="khung bo góc lớn, dày, chạy viền từ giữa cạnh trên ôm một vùng/clip/kết quả, kèm nhãn chữ viết tay gắn giữa mép dưới — mềm, có gu",
         hop_nghia=["kết quả", "bằng chứng", "vùng này", "trước sau", "điểm nhấn"],
         tham_so=_ts(bo="bo góc (0..0.5 cạnh ngắn, 0.14)", nhan="nhãn ngắn (chữ viết tay)", font_nhan="font nhãn (script)",
                     mau_nhan_chu="màu chữ nhãn (tự tương phản)"),
         mac_dinh=_md(day=12, bo=0.14, ve=0.5, font_nhan="script"),
         hop={"anchor": "mc", "x": 0.5, "y": 0.45, "w": 0.84, "h": 0.3}, dong=True,
         sfx_goi_y=["vẽ khung mềm", "pop nhãn"],
         vi_du={"nhan": "Trước khi sửa"})
def vien_om(t, dur, W, H, c, p):
    day = _day(c, p, 12)
    s, cv = be_mat(W, H)
    nhan = chuoi(p.get("nhan"))
    hn = _hop_nhan(c, p, W, H, nhan, "script")
    m = day * 1.4
    x0, y0, x1, y1 = m, m, W - m, H - m - hn * 0.5
    r = kep(float(p.get("bo", 0.14)), 0, 0.5) * min(x1 - x0, y1 - y0)
    u = _u(t, p)
    d, _, _ = cat_duong(_rrect_path(x0, y0, x1, y1, r, bat="tc"), u)
    cv.drawPath(d, but_net(mau_sk(c, p.get("mau"), "nhan"), day))
    if nhan:
        _ve_nhan(c, cv, nhan, W / 2, y1, W * 0.8, hn, e_out(pha(t, float(p.get("tre", 0)) + float(p.get("ve", 0.5)) * 0.65, 0.3)),
                 nen=p.get("mau", "nhan"), mau_chu=p.get("mau_nhan_chu"), font="script", p=p)
    return _ra(s, p, day)


# ---------------------------------------------------------------- mũi tên ----
def _dau_mui(cv, pt_paint, tip, tan, L, goc=28, u=1.0, kieu="v", mau=None):
    if u <= 0 or tan is None:
        return
    ax, ay = tip
    tx, ty = tan
    n = math.hypot(tx, ty) or 1.0
    tx, ty = tx / n, ty / n
    L *= e_out(u)
    a = math.radians(goc)
    pts = []
    for s_ in (1, -1):
        ca, sa = math.cos(a), math.sin(a) * s_
        bx, by = -(tx * ca - ty * sa), -(tx * sa + ty * ca)
        pts.append((ax + bx * L, ay + by * L))
    if kieu == "tam_giac":
        q = skia.Path(); q.moveTo(ax + tx * L * 0.15, ay + ty * L * 0.15); q.lineTo(*pts[0]); q.lineTo(*pts[1]); q.close()
        f = skia.Paint(AntiAlias=True); f.setColor(mau)
        cv.drawPath(q, f)
        cv.drawPath(q, pt_paint)
    else:
        q = skia.Path(); q.moveTo(*pts[0]); q.lineTo(ax, ay); q.lineTo(*pts[1])
        cv.drawPath(q, pt_paint)


def _diem_cong(p0, p1, cong, n=40, run=0.0, hat=1):
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    cx, cy = mx - dy * cong, my + dx * cong
    L = math.hypot(dx, dy)
    rnd = random.Random(hat)
    ph = rnd.uniform(0, 6.28)
    pts = []
    for k in range(n + 1):
        f = k / n
        x = (1 - f) ** 2 * p0[0] + 2 * (1 - f) * f * cx + f * f * p1[0]
        y = (1 - f) ** 2 * p0[1] + 2 * (1 - f) * f * cy + f * f * p1[1]
        j = run * L * 0.006 * math.sin(f * 9 + ph) * math.sin(math.pi * f)
        pts.append((x - dy / max(L, 1) * j, y + dx / max(L, 1) * j))
    return pts


@dang_ky(id="mau.mui-ten", nhom="do_hoa", ten="Mũi tên cong vẽ dần",
         mo_ta="mũi tên cong vẽ dần từ điểm A tới điểm B (toạ độ 0..1 trong hộp), đầu mũi bật ra khi nét tới nơi — dẫn mắt người xem",
         hop_nghia=["chỉ hướng", "nhìn đây", "từ đây tới đây", "dẫn mắt", "mũi tên"],
         tham_so=_ts(tu="[x,y] điểm đầu 0..1 trong hộp ([0.1,0.85])", toi="[x,y] đầu mũi 0..1 ([0.88,0.18])", cong="độ cong (−0.6..0.6, 0.25)",
                     dau="v|tam_giac (v)", co_dau="độ dài đầu mũi (× dày, 4.2)", goc_dau="độ mở đầu mũi (độ, 30)"),
         mac_dinh=_md(tu=[0.1, 0.85], toi=[0.88, 0.18], cong=0.25, dau="v", co_dau=4.2, goc_dau=30),
         hop={"anchor": "mc", "x": 0.5, "y": 0.5, "w": 0.5, "h": 0.2}, dong=True,
         sfx_goi_y=["vút mũi tên", "bút vẽ nhanh"],
         vi_du={})
def mui_ten(t, dur, W, H, c, p):
    day = _day(c, p)
    s, cv = be_mat(W, H)
    m = day * 1.5
    a, b = p.get("tu", [0.1, 0.85]), p.get("toi", [0.88, 0.18])
    p0 = (kep(a[0] * W, m, W - m), kep(a[1] * H, m, H - m))
    p1 = (kep(b[0] * W, m, W - m), kep(b[1] * H, m, H - m))
    pts = _diem_cong(p0, p1, float(p.get("cong", 0.25)), run=float(p.get("run", 1.0)), hat=int(p.get("hat", 1)))
    u = _u(t, p)
    path = duong_muot(pts)
    d, L, pt_ = cat_duong(path, u)
    mau = mau_sk(c, p.get("mau"), "nhan")
    paint = but_net(mau, day)
    cv.drawPath(d, paint)
    if pt_ is not None and u > 0.7:
        _dau_mui(cv, paint, (pt_[0].fX, pt_[0].fY), (pt_[1].fX, pt_[1].fY), day * float(p.get("co_dau", 4.2)),
                 float(p.get("goc_dau", 30)), pha(u, 0.7, 0.3), p.get("dau", "v"), mau)
    return _ra(s, p, day)


@dang_ky(id="mau.mui-ten-tay", nhom="do_hoa", ten="Mũi tên vẽ tay có vòng xoắn",
         mo_ta="mũi tên nguệch ngoạc kiểu ghi chú tay: thân cong có một vòng xoắn giữa đường rồi lao tới đích, đầu mũi chữ V",
         hop_nghia=["ghi chú", "nhìn kìa", "chỗ này", "vui", "viết tay"],
         tham_so=_ts(tu="[x,y] điểm đầu 0..1 ([0.08,0.8])", toi="[x,y] đầu mũi 0..1 ([0.9,0.3])", cong="độ cong thân (0.2)",
                     vong="số vòng xoắn (1)", co_vong="bán kính vòng (× cạnh ngắn hộp, 0.18)", vi_tri_vong="vị trí vòng trên thân 0..1 (0.45)",
                     co_dau="độ dài đầu mũi (× dày, 4)"),
         mac_dinh=_md(tu=[0.08, 0.8], toi=[0.9, 0.3], cong=0.2, vong=1, co_vong=0.18, vi_tri_vong=0.45, co_dau=4.0, ve=0.6),
         hop={"anchor": "mc", "x": 0.5, "y": 0.5, "w": 0.6, "h": 0.2}, dong=True,
         sfx_goi_y=["bút vẽ xoắn", "vút"],
         vi_du={})
def mui_ten_tay(t, dur, W, H, c, p):
    day = _day(c, p)
    s, cv = be_mat(W, H)
    a, b = p.get("tu", [0.08, 0.8]), p.get("toi", [0.9, 0.3])
    m = day * 1.5
    p0 = (kep(a[0] * W, m, W - m), kep(a[1] * H, m, H - m))
    p1 = (kep(b[0] * W, m, W - m), kep(b[1] * H, m, H - m))
    base = _diem_cong(p0, p1, float(p.get("cong", 0.2)), n=160, run=float(p.get("run", 1.0)), hat=int(p.get("hat", 1)))
    R = float(p.get("co_vong", 0.18)) * min(W, H)
    nv = float(p.get("vong", 1))
    s0 = float(p.get("vi_tri_vong", 0.45))
    w = 0.22
    pts = []
    n = len(base) - 1
    for k, (x, y) in enumerate(base):
        f = k / n
        q = kep((f - (s0 - w / 2)) / w)
        if 0 < q < 1:
            k0, k1 = max(0, k - 1), min(n, k + 1)
            tx, ty = base[k1][0] - base[k0][0], base[k1][1] - base[k0][1]
            L = math.hypot(tx, ty) or 1
            tx, ty = tx / L, ty / L
            nx, ny = ty, -tx
            ph = 2 * math.pi * nv * (q * q * (3 - 2 * q))
            x += R * (-math.sin(ph) * tx + (1 - math.cos(ph)) * nx * 0.9)
            y += R * (-math.sin(ph) * ty + (1 - math.cos(ph)) * ny * 0.9)
        pts.append((kep(x, m, W - m), kep(y, m, H - m)))
    u = _u(t, p)
    d, L, pt_ = cat_duong(duong_muot(pts), u)
    mau = mau_sk(c, p.get("mau"), "nhan")
    paint = but_net(mau, day)
    cv.drawPath(d, paint)
    if pt_ is not None and u > 0.8:
        _dau_mui(cv, paint, (pt_[0].fX, pt_[0].fY), (pt_[1].fX, pt_[1].fY), day * float(p.get("co_dau", 4.0)), 32, pha(u, 0.8, 0.2), "v", mau)
    return _ra(s, p, day)


# ---------------------------------------------------------------- làm tối ngoài vùng ----
@dang_ky(id="mau.lam-toi-ngoai", nhom="do_hoa", ten="Làm tối phần ngoài (spotlight)",
         mo_ta="làm tối (và tuỳ chọn làm nhoè) mọi thứ trừ vùng đang nói — lỗ sáng bo góc mép mềm thu dần từ cả khung về đúng vùng; có viền sáng tuỳ chọn",
         hop_nghia=["tập trung", "chỗ này", "spotlight", "màn hình nhiều chữ", "vùng quan trọng"],
         tham_so={"vung": "[x0,y0,x1,y1] vùng sáng theo khung 0..1", "do_toi": "0..1 độ tối ngoài (0.62)", "bo": "bo góc lỗ (× cạnh ngắn khung, 0.03)",
                  "mem": "độ mềm mép (× cạnh ngắn khung, 0.012)", "mo": "nhoè phần ngoài px@1080 (0 = không; cần ảnh nền engine)",
                  "vien": "viền quanh lỗ px@1080 (0)", "mau_vien": "nhan", "thu": "true = lỗ thu từ cả khung về vùng", "dai": "giây vào (0.4)",
                  "hinh": "bo|elip (bo)"},
         mac_dinh={"vung": [0.12, 0.34, 0.88, 0.58], "do_toi": 0.62, "bo": 0.03, "mem": 0.012, "mo": 0, "vien": 0, "mau_vien": "nhan",
                   "thu": True, "dai": 0.4, "hinh": "bo"},
         toan_khung=True, lam_nen=True, dong=True,
         sfx_goi_y=["tối dần", "whoosh trầm"],
         vi_du={"vung": [0.1, 0.4, 0.9, 0.62], "mo": 14, "vien": 4})
def lam_toi_ngoai(t, dur, W, H, c, p):
    v = p.get("vung") or [0.12, 0.34, 0.88, 0.58]
    u = e_in_out(pha(t, 0, float(p.get("dai", 0.4))))
    if p.get("thu", True):
        r = [tron(0, v[0], u) * W, tron(0, v[1], u) * H, tron(1, v[2], u) * W, tron(1, v[3], u) * H]
    else:
        r = [v[0] * W, v[1] * H, v[2] * W, v[3] * H]
    mn = min(W, H)
    bo = float(p.get("bo", 0.03)) * mn
    # mặt nạ ngoài (vẽ ở 1/2 độ phân giải — mép mềm nên không mất nét, nhanh gấp 4)
    k = 2
    km = (W, H, tuple(round(x, 1) for x in r), round(bo, 1), p.get("hinh"), float(p.get("mem", 0.012)))
    m = _MAT_NA.get(km)
    if m is None:
        m = _mat_na_ngoai(W, H, r, bo, k, p, mn)
        if len(_MAT_NA) > 8:
            _MAT_NA.clear()
        _MAT_NA[km] = m
    do = kep(float(p.get("do_toi", 0.62)))
    return _lam_toi_ghep(c, t, W, H, p, u, m, do, r, bo)


_MAT_NA = {}


def _mat_na_ngoai(W, H, r, bo, k, p, mn):
    s, cv = be_mat(W // k, H // k)
    pa = skia.Path()
    pa.setFillType(skia.PathFillType.kEvenOdd)
    pa.addRect(skia.Rect.MakeWH(W // k + 2, H // k + 2))
    rr = skia.Rect.MakeLTRB(r[0] / k, r[1] / k, r[2] / k, r[3] / k)
    if p.get("hinh") == "elip":
        pa.addOval(rr)
    else:
        pa.addRRect(skia.RRect.MakeRectXY(rr, bo / k, bo / k))
    pt = skia.Paint(AntiAlias=True); pt.setColor(skia.ColorBLACK)
    cv.drawPath(pa, pt)
    m = np_premul(s.makeImageSnapshot())[..., 3]
    mem = float(p.get("mem", 0.012)) * mn / k
    if mem > 0.3:
        m = nhoe_np(m, mem)
    return cv2.resize(m, (W, H), interpolation=cv2.INTER_LINEAR)


def _lam_toi_ghep(c, t, W, H, p, u, m, do, r, bo):
    nen = nen_hop(c, t, W, H) if float(p.get("mo", 0)) > 0 else None
    if nen is not None:
        mo = s_px(c, float(p["mo"])) * u
        b = nhoe_np(np.ascontiguousarray(nen[..., :3]), mo) if mo > 0.3 else np.ascontiguousarray(nen[..., :3])
        b = cv2.convertScaleAbs(b, alpha=1 - do * u)
        out = cv2.merge([b[..., 0], b[..., 1], b[..., 2], m])
    else:
        z = np.zeros((H, W), np.uint8)
        out = cv2.merge([z, z, z, cv2.convertScaleAbs(m, alpha=do * u)])
    vw = float(p.get("vien", 0))
    if vw > 0 and u > 0.02:
        # viền vẽ thẳng bằng cv2 (AA, toạ độ dưới-pixel) — nhanh hơn ghép một mặt Skia cỡ cả vùng
        q = skia.Path()
        rr2 = skia.Rect.MakeLTRB(*r)
        if p.get("hinh") == "elip":
            q.addOval(rr2)
        else:
            q.addRRect(skia.RRect.MakeRectXY(rr2, bo, bo))
        pm = skia.PathMeasure(q, True)
        L = pm.getLength()
        n = max(16, int(L / 6))
        pts = np.array([[pm.getPosTan(L * k / n)[0].fX, pm.getPosTan(L * k / n)[0].fY] for k in range(n)], np.float64)
        r_, g_, b_, _ = rgba(c, p.get("mau_vien"), "nhan")
        a_ = int(255 * u)
        cv2.polylines(out, [np.round(pts * 4).astype(np.int32)], True, (r_, g_, b_, a_), max(1, int(round(s_px(c, vw)))),
                      cv2.LINE_AA, 2)
    return out


# ---------------------------------------------------------------- bút dạ ----
def _vet_but(x0, y0, x1, y1, rnd, gai=0.08):
    """vệt bút dạ: mép trên/dưới hơi gợn, hai đầu bo nghiêng"""
    h = y1 - y0
    n = 18
    tren, duoi = [], []
    for k in range(n + 1):
        f = k / n
        x = x0 + (x1 - x0) * f
        tren.append((x, y0 + h * gai * (rnd.random() - 0.5)))
        duoi.append((x, y1 + h * gai * (rnd.random() - 0.5)))
    p = skia.Path()
    p.moveTo(x0 + h * 0.12, tren[0][1])
    for x, y in tren[1:]:
        p.lineTo(x, y)
    p.quadTo(x1 + h * 0.18, (y0 + y1) / 2, duoi[-1][0] - h * 0.05, duoi[-1][1])
    for x, y in reversed(duoi[:-1]):
        p.lineTo(x, y)
    p.quadTo(x0 - h * 0.15, (y0 + y1) / 2, x0 + h * 0.12, tren[0][1])
    p.close()
    return p


def xoay_np(pre, goc, tam=None):
    """xoay cả lớp numpy premul quanh tâm (cv2) — Skia raster xoay quá chậm"""
    if not goc:
        return pre
    h, w = pre.shape[:2]
    M = cv2.getRotationMatrix2D(tam or (w / 2, h / 2), -goc, 1.0)
    return cv2.warpAffine(pre, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)


@dang_ky(id="mau.but-da", nhom="do_hoa", ten="Bút dạ quét",
         mo_ta="vệt bút dạ màu quét ngang phía sau cụm chữ quan trọng (kiểu tô sách, mép gợn tự nhiên); bỏ chữ trống = quét mờ lên dòng có sẵn trong hộp",
         hop_nghia=["tô sáng", "nhấn mạnh", "từ khoá", "đánh dấu", "đọc dòng này"],
         tham_so={"chu": "cụm chữ (≤ 6 từ) — trống = chỉ quét vệt lên vùng hộp", "mau": "màu vệt (nhan)", "quet": "giây quét (0.45)",
                  "tre": "giây trước khi quét (0)", "do_dac": "0..1 độ đục vệt (0.92 có chữ / 0.45 không chữ)", "nghieng": "độ nghiêng (−2)",
                  "mau_chu": "màu chữ (tự tương phản)", "font": "font chữ (tieu_de)", "co": "cỡ chữ px (tự)", "hoa": "IN HOA",
                  "dem": "đệm vệt quanh chữ (em, [0.25, 0.12])", "hat": "hạt ngẫu nhiên mép (1)", "kieu_dang": "kieu_dang chữ (ghi đè)"},
         mac_dinh={"mau": "nhan", "quet": 0.45, "tre": 0.0, "nghieng": -2, "font": "tieu_de", "dem": [0.25, 0.12], "hat": 1},
         hop={"anchor": "mc", "x": 0.5, "y": 0.62, "w": 0.88, "h": 0.12}, dong=True,
         sfx_goi_y=["bút dạ quét", "sột soạt"],
         vi_du={"chu": "Không cần vốn lớn"})
def but_da(t, dur, W, H, c, p):
    s, cv = be_mat(W, H)
    u = e_in_out(pha(t, float(p.get("tre", 0)), float(p.get("quet", 0.45))))
    rnd = random.Random(int(p.get("hat", 1)))
    chu = chuoi(p.get("chu"))
    pt = skia.Paint(AntiAlias=True)
    goc = float(p.get("nghieng", -2))
    if chu:
        dem = p.get("dem", [0.25, 0.12])
        if isinstance(dem, (int, float)):
            dem = [dem, dem]
        mc = p.get("mau_chu") or mau_tuong_phan(c, p.get("mau", "nhan"))
        kd = kieu_dang(c, dict(p, mau_chu=mc, bong=0), "tieu_de", mc)
        fx = 1 + 2 * float(dem[0]) * 0.5
        bc = bo_chu(c, chu, kd, W / fx - abs(math.sin(math.radians(goc))) * H, H / (1 + 2 * float(dem[1]) + 0.3))
        ox, oy = bc.goc(W, H)
        dx, dy = float(dem[0]) * bc.co, float(dem[1]) * bc.co
        for li, d in enumerate(bc.dong):
            y = oy + d["y"]
            x0 = ox + d["x"] - dx
            x1 = ox + d["x"] + d["w"] + dx
            ya = y + bc.base - bc.co * 0.78 - dy
            yb = y + bc.base + bc.co * 0.22 + dy
            ul = kep(u * len(bc.dong) - li)
            if ul <= 0:
                continue
            cv.save()
            cv.clipRect(skia.Rect.MakeLTRB(x0 - bc.co, ya - bc.co, x0 + (x1 - x0 + bc.co * 0.3) * ul, yb + bc.co))
            pt.setColor(mau_sk(c, p.get("mau"), "nhan", float(p.get("do_dac", 0.92))))
            cv.drawPath(_vet_but(x0, ya, x1, yb, rnd), pt)
            cv.restore()
        bc.ve_khoi(cv, ox, oy, op=e_out(pha(t, float(p.get("tre", 0)) + float(p.get("quet", 0.45)) * 0.35, 0.25)))
    else:
        m = H * 0.08
        cv.save()
        cv.clipRect(skia.Rect.MakeLTRB(0, 0, m + (W - m) * u, H))
        pt.setColor(mau_sk(c, p.get("mau"), "nhan", float(p.get("do_dac", 0.45))))
        cv.drawPath(_vet_but(m, m, W - m, H - m, rnd, 0.05), pt)
        cv.restore()
    pre = np_premul(s.makeImageSnapshot())
    return unpremul_rgba(xoay_np(pre, goc))


# ---------------------------------------------------------------- gạch xoá ----
@dang_ky(id="mau.gach-xoa", nhom="do_hoa", ten="Gạch đỏ xoá chữ",
         mo_ta="nét gạch (một, đôi hoặc nguệch ngoạc) quét ngang xoá một cụm chữ/vùng — sai, bỏ, không còn đúng; chữ mờ đi sau khi bị gạch",
         hop_nghia=["sai", "xoá", "bỏ", "không nên", "lỗi thời", "giá cũ"],
         tham_so=_ts(chu="cụm chữ bị gạch (trống = gạch lên vùng hộp)", kieu="mot|hai|nguech (mot)", goc="nghiêng nét (độ, −4)",
                     mo_chu="độ đục chữ sau khi gạch (0.55)", mau_chu="màu chữ (sang)", font="font chữ (tieu_de)", co="cỡ chữ px (tự)",
                     vuot="nét vượt hai đầu (× cỡ, 0.15)", kieu_dang="kieu_dang chữ (ghi đè)"),
         mac_dinh=_md(mau="nhan", day=11, ve=0.3, tre=0.35, kieu="mot", goc=-4, mo_chu=0.55, mau_chu="sang", vuot=0.15, bong=0.35),   # 1.2.21: màu nét = vai nhan (hết #FF3B30)
         hop={"anchor": "mc", "x": 0.5, "y": 0.5, "w": 0.8, "h": 0.14}, dong=True,
         sfx_goi_y=["gạch bút mạnh", "sai buzzer"],
         vi_du={"chu": "Giá 990.000đ", "kieu": "hai"})
def gach_xoa(t, dur, W, H, c, p):
    day = _day(c, p, 11)
    s, cv = be_mat(W, H)
    chu = chuoi(p.get("chu"))
    tre = float(p.get("tre", 0.35))
    u = _u(t, p)
    if chu:
        kd = kieu_dang(c, p, "tieu_de", "sang")
        bc = bo_chu(c, chu, kd, W * 0.86, H * 0.8)
        ox, oy = bc.goc(W, H)
        mo = 1 - (1 - float(p.get("mo_chu", 0.55))) * e_out(pha(t, tre + float(p.get("ve", 0.3)) * 0.6, 0.3))
        bc.ve_khoi(cv, ox, oy, op=mo * e_out(pha(t, 0, 0.15)))
        dong = [(ox + d["x"], oy + d["y"] + bc.base - bc.co * 0.37, d["w"], bc.co) for d in bc.dong]
    else:
        dong = [(W * 0.06, H / 2, W * 0.88, H * 0.6)]
    kieu = p.get("kieu", "mot")
    g = math.radians(float(p.get("goc", -6)))
    rnd = random.Random(int(p.get("hat", 1)))
    duongs = []
    for (x, y, w, co) in dong:
        v = float(p.get("vuot", 0.15)) * co
        xa, xb = x - v, x + w + v
        if kieu == "nguech":
            pts = []
            n = max(3, int(w / (co * 0.35)))
            for k in range(n + 1):
                f = k / n
                pts.append((xa + (xb - xa) * f + rnd.uniform(-1, 1) * co * 0.05, y + (co * 0.32) * (1 if k % 2 else -1) + rnd.uniform(-1, 1) * co * 0.06))
            duongs.append(pts)
        else:
            lan = [0.0] if kieu == "mot" else [-co * 0.11, co * 0.11]
            for o in lan:
                dyg = math.tan(g) * min(xb - xa, co * 4) / 2
                duongs.append([(xa, y + o - dyg + rnd.uniform(-1, 1) * day * 0.3), ((xa + xb) / 2, y + o + rnd.uniform(-1, 1) * day * 0.5),
                               (xb, y + o + dyg + rnd.uniform(-1, 1) * day * 0.3)])
    paint = but_net(mau_sk(c, p.get("mau"), "nhan"), day)
    n = len(duongs)
    for k, pts in enumerate(duongs):
        uk = kep(u * n - k)
        if uk <= 0:
            continue
        d, _, _ = cat_duong(duong_muot(pts), e_out(uk, 2))
        cv.drawPath(d, paint)
    return _ra(s, p, day)


# ---------------------------------------------------------------- lấp lánh ----
_SAO = {}


def _sao(c, r, mau, glow):
    """sprite ngôi sao 4 cánh + hào quang (cache)"""
    k = (round(r), mau, round(glow, 2))
    im = _SAO.get(k)
    if im is not None:
        return im
    R = int(r * (1 + 2.2 * glow)) + 4
    s, cv = be_mat(2 * R, 2 * R)
    q = skia.Path()
    cx = cy = R
    th = r * 0.16
    q.moveTo(cx, cy - r)
    q.quadTo(cx + th * 0.35, cy - th * 0.35, cx + r, cy)
    q.quadTo(cx + th * 0.35, cy + th * 0.35, cx, cy + r)
    q.quadTo(cx - th * 0.35, cy + th * 0.35, cx - r, cy)
    q.quadTo(cx - th * 0.35, cy - th * 0.35, cx, cy - r)
    q.close()
    pt = skia.Paint(AntiAlias=True)
    pt.setColor(_chu_mau(mau))
    cv.drawPath(q, pt)
    a = np_premul(s.makeImageSnapshot())
    if glow > 0:
        g = nhoe_np(a, r * 0.35 * glow)
        a = cv2.add(a, cv2.convertScaleAbs(g, alpha=1.2))
    im = sk_premul(a)
    _SAO[k] = im
    return im


def _chu_mau(hex_):
    from dung import chu as _c
    return _c.mau_skia(hex_)


@dang_ky(id="mau.lap-lanh", nhom="do_hoa", ten="Tia lấp lánh quanh vùng",
         mo_ta="các ngôi sao 4 cánh nhấp nháy, xoay nhẹ quanh viền vùng (hoặc rải trong vùng) — mới, sạch, đẹp, giá trị, phép màu",
         hop_nghia=["lấp lánh", "mới tinh", "sạch", "đẹp", "phép màu", "giá trị", "nổi bật"],
         tham_so={"so": "số sao (8)", "co": "cỡ sao (× cạnh ngắn hộp, 0.1)", "mau": "màu chính (sang)", "mau2": "màu xen kẽ (nhan)",
                  "vung": "vien|trong (vien)", "chu_ky": "giây một lần nhấp nháy (1.1)", "so_le": "giây giữa 2 sao xuất hiện (0.06)",
                  "hao_quang": "0..1 độ toả sáng (0.6)", "xoay": "độ xoay mỗi nhịp (45)", "hat": "hạt ngẫu nhiên (1)"},
         mac_dinh={"so": 8, "co": 0.1, "mau": "sang", "mau2": "nhan", "vung": "vien", "chu_ky": 1.1, "so_le": 0.06, "hao_quang": 0.6,
                   "xoay": 45, "hat": 1},
         hop={"anchor": "mc", "x": 0.5, "y": 0.45, "w": 0.7, "h": 0.25}, dong=True,
         sfx_goi_y=["ting lấp lánh", "chuông nhỏ"],
         vi_du={})
def lap_lanh(t, dur, W, H, c, p):
    s, cv = be_mat(W, H)
    rnd = random.Random(int(p.get("hat", 1)) * 31 + 7)
    n = max(1, int(p.get("so", 8)))
    co = float(p.get("co", 0.1)) * min(W, H)
    ck = max(0.2, float(p.get("chu_ky", 1.1)))
    glow = float(p.get("hao_quang", 0.6))
    m1, m2 = c.mau(p.get("mau", "sang")), c.mau(p.get("mau2", "nhan"))
    for i in range(n):
        r = co * rnd.uniform(0.55, 1.15)
        if p.get("vung", "vien") == "vien":
            a = 2 * math.pi * (i / n) + rnd.uniform(-0.25, 0.25)
            rx, ry = W / 2 - co * 1.3, H / 2 - co * 1.3
            k = rnd.uniform(0.82, 1.0)
            x, y = W / 2 + rx * k * math.cos(a), H / 2 + ry * k * math.sin(a)
        else:
            x, y = rnd.uniform(co, W - co), rnd.uniform(co, H - co)
        t0 = i * float(p.get("so_le", 0.06))
        ph = rnd.uniform(0, 0.6)
        if t < t0:
            continue
        f = ((t - t0) / ck + ph) % 1.0 if t - t0 > ck * (1 - ph) else (t - t0) / ck + ph
        if t - t0 < 0.25:
            f = max(f, 0.5 * (t - t0) / 0.25)
        sc = math.sin(math.pi * kep(f)) ** 1.4
        if sc <= 0.02:
            continue
        im = _sao(c, r, m1 if i % 3 else m2, glow)
        ve_xoay(cv, im, x, y, float(p.get("xoay", 45)) * f, sc)
    return ra_np(s)


# ---------------------------------------------------------------- sticker nhãn ----
_STK = {}


@dang_ky(id="mau.sticker-nhan", nhom="do_hoa", ten="Sticker nhãn bo tròn xoay nhẹ",
         mo_ta="nhãn kiểu sticker dán (nền màu, viền trắng dày, bóng) bật vào bằng lò xo rồi lắc lư nhẹ — mới, hot, giảm giá, mẹo",
         hop_nghia=["mới", "hot", "giảm giá", "mẹo", "lưu ý", "nhãn", "tag"],
         tham_so={"chu": "chữ nhãn (1–4 từ)", "mau_nen": "màu nền (nhan)", "mau_chu": "màu chữ (tự tương phản)", "vien_dan": "màu viền sticker (#FFFFFF; null = không)",
                  "day_vien": "dày viền (em, 0.16)", "hinh": "pill|bo (pill)", "goc": "góc nghiêng (độ, −6)", "lac": "biên độ lắc (độ, 3)",
                  "toc_lac": "Hz lắc (0.7)", "dai": "giây bật vào (0.55)", "font": "font (tieu_de)", "co": "cỡ chữ px (tự)", "hoa": "IN HOA (true)",
                  "bong": "0..1 bóng (0.5)", "kieu_dang": "kieu_dang chữ (ghi đè)"},
         mac_dinh={"mau_nen": "nhan", "vien_dan": "#FFFFFF", "day_vien": 0.16, "hinh": "pill", "goc": -6, "lac": 3, "toc_lac": 0.7, "dai": 0.55,
                   "font": "tieu_de", "hoa": True, "bong": 0.5},
         hop={"anchor": "mc", "x": 0.5, "y": 0.4, "w": 0.6, "h": 0.12}, dong=True,
         sfx_goi_y=["pop sticker", "boing"],
         vi_du={"chu": "Mẹo hay"})
def sticker_nhan(t, dur, W, H, c, p):
    goc = float(p.get("goc", -6))
    lac = float(p.get("lac", 3))
    gmax = math.radians(abs(goc) + abs(lac))
    mc = p.get("mau_chu") or mau_tuong_phan(c, p.get("mau_nen", "nhan"))
    kd = kieu_dang(c, dict(p, mau_chu=mc, bong=0, vien=0), "tieu_de", mc)
    dv = float(p.get("day_vien", 0.16)) if p.get("vien_dan") else 0.0
    # cỡ chữ: khối sticker (chữ + đệm + viền) xoay gmax vẫn nằm trong hộp
    fx, fy = 1.0 + 0.9 + 2 * dv, 1.0
    cs, sn = math.cos(gmax), math.sin(gmax)
    bc = bo_chu(c, chuoi(p.get("chu")), kd, W * 0.92 / (cs + sn * 0.6) / 1.35, H * 0.92 / (cs + sn * 2.5) / (1.55 + 2 * dv))
    k = (bc._kd_js, bc.text, p.get("mau_nen"), p.get("vien_dan"), dv, p.get("hinh"), W, H)
    r = _STK.get(k)
    if r is None:
        cao = bc.duoi - bc.tren
        dx, dy = bc.co * 0.55, bc.co * 0.28
        vw = dv * bc.co
        bw, bh = bc.w + 2 * dx, cao + 2 * dy
        Wi, Hi = int(bw + 2 * vw + 4), int(bh + 2 * vw + 4)
        s, cv = be_mat(Wi, Hi)
        x0, y0 = vw + 2, vw + 2
        rr = bh / 2 if p.get("hinh", "pill") == "pill" else bc.co * 0.25
        pt = skia.Paint(AntiAlias=True)
        if vw > 0:
            pt.setColor(mau_sk(c, p.get("vien_dan"), "sang"))
            cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x0 - vw, y0 - vw, bw + 2 * vw, bh + 2 * vw), rr + vw, rr + vw), pt)
        pt.setColor(mau_sk(c, p.get("mau_nen"), "nhan"))
        cv.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x0, y0, bw, bh), rr, rr), pt)
        bc.ve_khoi(cv, round(x0 + dx), round(y0 + dy - bc.tren))
        r = np_premul(s.makeImageSnapshot()).copy()
        if len(_STK) > 50:
            _STK.clear()
        _STK[k] = r
    u = pha(t, 0, float(p.get("dai", 0.55)))
    sc = max(0.0, lo_xo(u, 5.0, 1.4))
    if sc <= 0.01:
        return rong(W, H)
    g = goc * (0.4 + 0.6 * e_out(u)) + lac * math.sin(2 * math.pi * float(p.get("toc_lac", 0.7)) * t)
    h, w = r.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), -g, sc)
    M[0, 2] += W / 2 - w / 2
    M[1, 2] += H / 2 - h / 2
    out = cv2.warpAffine(r, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    b = float(p.get("bong", 0.5))
    if b > 0:
        out = bong_np(out, bc.co * 0.08 * sc, bc.co * 0.12, b * 0.8)
    return unpremul_rgba(out)
