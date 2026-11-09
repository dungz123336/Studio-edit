# -*- coding: utf-8 -*-
"""MẪU THẺ (nhóm "the") — đồ hoạ thông tin đặt trong một hộp cạnh người nói: số lớn, danh sách, quy trình, so sánh, chương,
bình luận, nhãn, tiêu đề ghim, thanh tiến trình, bảng giá, đánh giá sao, đếm ngược, lower-third, trích dẫn, mã giảm giá, mục tiêu.

Mỗi mẫu tự KHỚP HỘP: bố cục thiết kế theo đơn vị u rồi phóng/thu cho vừa khít hộp W×H AI đặt (vi_tri.w/h) — muốn to/nhỏ thì đổi
hộp, không có cỡ hàn chết. Màu theo vai màu video (tham số mau/mau2/tong_mau). Vào/ra tổng thể do engine lo (anim của lớp);
mẫu chỉ diễn nội dung bên trong (đếm số, tích từng dòng, gõ chữ, lộ tấm…).
"""
import math
import skia
from dung.mau import dang_ky
from dung.mau.canh import (kep, e_out, e_io, e_back, tien, lich, muc, so, so_vn, le_cua, tron, voi_alpha, sk, chu_tren,
                           bang_mau, anh_chu, vua, kich, dat, p_to, p_net, rr, hop, bong, the_noi, dau_tich, sao,
                           be_mat, ra, khop, nho, khoa_p, bong_chu, don_vi_goc, _kd as _kd_chu)

THAM_SO_CHUNG = {
    "tong_mau": "toi | sang | kinh — tông tấm thẻ (toi)", "mau": "màu nhấn (vai nhan|nhan2|sang|toi hoặc #hex)", "mau2": "màu nhấn phụ",
    "font": "vai/id font chữ (nhan)", "font_tieu_de": "vai/id font số/tiêu đề lớn (tieu_de)",
    "phong": "hệ số phóng tối đa để lấp hộp (3) — khối luôn tự thu cho khỏi tràn hộp",
}


def _the(**kw):
    ts = dict(THAM_SO_CHUNG); ts.update(kw.pop("tham_so", {}))
    md = {"tong_mau": "toi"}; md.update(kw.pop("mac_dinh", {}))
    return dict(nhom="the", tham_so=ts, mac_dinh=md, **kw)


def _bo_cuc(mid, W, H, p, B, c, bo, chi_cao=False):
    """bố cục bo(u) → dict có w, h (px, gồm lề bóng) · trả (u, L) đã khớp hộp"""
    kh = khoa_p(mid, W, H, p, B)

    def wh(x):
        L = nho(kh, x, bo)
        return (0 if chi_cao else L["w"], L["h"])
    u = khop(kh, don_vi_goc(c), wh, W, H, p)
    return u, nho(kh, u, bo)


def _f(p):
    return p.get("font") or "nhan", p.get("font_tieu_de") or "tieu_de"


# ---------------------------------------------------------------- số lớn đếm lên
@dang_ky(**_the(
    id="mau.so-lon", ten="Số lớn đếm lên",
    mo_ta="Con số THẬT trong lời phóng to và đếm lên tới đích, dòng giải thích bên dưới — mắt bám số, nhớ số.",
    hop_nghia=["số liệu", "kết quả", "con số ấn tượng", "doanh thu", "phần trăm", "bao nhiêu"],
    tham_so={"so": "số đích (12 | \"4,9\" | \"1.200\")", "tien_to": "trước số (+, $…)", "don_vi": "sau số (%, triệu, k…)",
             "nhan": "dòng giải thích dưới số", "dem": "giây đếm (0.9; 0 = hiện luôn)", "le": "số lẻ hiển thị (tự theo số đích)",
             "nen": "khong | the — có tấm nền (khong: chữ có bóng trên video)"},
    mac_dinh={"dem": 0.9, "nen": "khong", "tien_to": "", "don_vi": ""},
    hop={"anchor": "mc", "x": 0.5, "y": 0.63, "w": 0.86, "h": 0.2}, dong=True, sfx_goi_y=["tick đếm số", "ding", "whoosh lên"],
    vi_du={"so": 1250, "tien_to": "+", "don_vi": " đơn", "nhan": "chỉ trong 7 ngày đầu tiên"}))
def so_lon(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, ftd = _f(p)
    dich = so(p.get("so"))
    le = int(p["le"]) if p.get("le") is not None else le_cua(p.get("so"))
    tt, dv = str(p.get("tien_to") or ""), str(p.get("don_vi") or "")
    co_nen = str(p.get("nen")) == "the"
    m_so = B["nhan"] if (co_nen or B["tong"] == "sang") else c.mau(p.get("mau") or "nhan")
    m_nhan = B["chu"] if co_nen else c.mau("sang")
    nhan = str(p.get("nhan") or "")

    def bo(u):
        bc = None if co_nen else bong_chu(u)
        im_s = anh_chu(c, tt + so_vn(dich, le) + dv, 220 * u, m_so, vai=ftd, bong=bc)
        ws, hs = kich(im_s)
        im_n = anh_chu(c, nhan, 54 * u, m_nhan, vai=font, rong=max(ws, 760 * u), can="giua", bong=bc) if nhan else None
        wn, hn = kich(im_n) if im_n else (0, 0)
        pad = 50 * u if co_nen else 24 * u
        return dict(u=u, im_n=im_n, hs=hs, hn=hn, pad=pad, w=max(ws, wn) + 2 * pad, h=hs + (hn + 6 * u if im_n else 0) + 2 * pad)
    u, L = _bo_cuc("so-lon", W, H, p, B, c, bo)
    x0, y0 = (W - L["w"]) / 2, (H - L["h"]) / 2
    if co_nen:
        the_noi(cv, B, x0, y0, x0 + L["w"], y0 + L["h"], 40 * u, u)
    dem = float(p.get("dem", 0.9))
    k = e_out(tien(t, 0, dem)) if dem > 0 else 1.0
    im = anh_chu(c, tt + so_vn(dich * k, le) + dv, 220 * u, m_so, vai=ftd, bong=None if co_nen else bong_chu(u))
    dat(cv, im, W / 2, y0 + L["pad"], "tc")
    if L["im_n"]:
        dat(cv, L["im_n"], W / 2, y0 + L["pad"] + L["hs"] + 6 * u, "tc", e_out(tien(t, 0.2, 0.35)))
    return ra(surf)


# ---------------------------------------------------------------- danh sách cộng dồn
@dang_ky(**_the(
    id="mau.danh-sach", ten="Danh sách cộng dồn (số thứ tự)",
    mo_ta="Liệt kê N điều: mỗi mục là một viên có số thứ tự, hiện đúng lúc nói và giữ lại — người xem đếm được tiến độ.",
    hop_nghia=["liệt kê", "các ý", "lý do", "mẹo", "bước", "điều cần nhớ"],
    tham_so={"muc": "list: \"chữ\" | [chữ, giây từ đầu lớp] (≤ 8, mỗi mục ngắn)", "tieu_de": "dòng nhỏ phía trên (tuỳ)",
             "can": "trai | giua (trai)", "nhip": "giây giữa 2 mục (0.55)", "bat_dau": "giây mục đầu (0.15)"},
    mac_dinh={"can": "trai", "nhip": 0.55, "bat_dau": 0.15},
    hop={"anchor": "mc", "x": 0.5, "y": 0.6, "w": 0.86, "h": 0.32}, dong=True, sfx_goi_y=["pop nhẹ", "click", "bubble"],
    vi_du={"tieu_de": "3 lý do khách quay lại", "muc": ["Giao hàng trong 2 giờ", "Đổi trả miễn phí", "Tư vấn tận tâm"], "nhip": 0.5}))
def danh_sach(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, ftd = _f(p)
    ds = [muc(x) for x in (p.get("muc") or [])][:8]
    ts = lich(len(ds), dur, p.get("nhip", 0.55), p.get("bat_dau", 0.15), [d.get("t") for d in ds])
    td = str(p.get("tieu_de") or "")

    def bo(u):
        m = 22 * u
        co0 = 54 * u
        rong = W - 2 * m - co0 * 2.6
        co = min([vua(c, str(d.get("chu", "")), co0, rong, 1, 2, co_min=28 * u, vai=font) for d in ds] or [co0])
        ims = [anh_chu(c, str(d.get("chu", "")), co, B["chu"], vai=font, rong=rong) for d in ds]
        im_td = anh_chu(c, td, co * 0.56, B["tren_nhan"], vai=font, hoa=True, gian=0.08) if td else None
        hh = [max(kich(im)[1], co) + co * 0.62 for im in ims]
        ww = [kich(im)[0] + co * 2.5 for im in ims]
        khe = co * 0.3
        h_td = kich(im_td)[1] + co * 0.5 + co * 0.35 if im_td else 0
        return dict(m=m, co=co, ims=ims, im_td=im_td, hh=hh, ww=ww, khe=khe, h_td=h_td,
                    w=max(ww + [kich(im_td)[0] + co if im_td else 0]) + 2 * m, h=h_td + sum(hh) + khe * max(0, len(hh) - 1) + 2 * m)
    u, L = _bo_cuc("danh-sach", W, H, p, B, c, bo)
    giua = str(p.get("can")) == "giua"
    y = (H - L["h"]) / 2 + L["m"]
    bx = (W - L["w"]) / 2 + L["m"] if not giua else None
    if L["im_td"]:
        a = e_out(tien(t, 0, 0.3))
        tw, th = kich(L["im_td"])
        px = (W - tw) / 2 - L["co"] * 0.5 if giua else bx
        hop(cv, px, y, px + tw + L["co"], y + th + L["co"] * 0.5, (th + L["co"] * 0.5) / 2, B["nhan"], a)
        dat(cv, L["im_td"], px + L["co"] * 0.5, y + L["co"] * 0.25, "tl", a)
        y += L["h_td"]
    co = L["co"]
    for i, im in enumerate(L["ims"]):
        h, w = L["hh"][i], L["ww"][i]
        k = tien(t, ts[i], 0.32)
        if k > 0:
            x0 = (W - w) / 2 if giua else bx
            wc = h + (w - h) * e_out(k)
            a = e_out(k * 2)
            the_noi(cv, B, x0, y, x0 + wc, y + h, h * 0.3, u, al=a, vien=False)
            r = co * 0.42
            cv.drawCircle(x0 + h / 2, y + h / 2, r, p_to(B["nhan"], a))
            dat(cv, anh_chu(c, str(i + 1), co * 0.56, B["tren_nhan"], vai=ftd), x0 + h / 2, y + h / 2, "mc", a)
            cv.save(); cv.clipRect(skia.Rect.MakeLTRB(x0, y, x0 + wc, y + h))
            dat(cv, im, x0 + co * 1.75 + (1 - e_out(k)) * 20 * u, y + h / 2, "ml", e_out(tien(t, ts[i] + 0.12, 0.25)))
            cv.restore()
        y += h + L["khe"]
    return ra(surf)


# ---------------------------------------------------------------- quy trình
@dang_ky(**_the(
    id="mau.quy-trinh", ten="Sơ đồ các bước (ô nối mũi tên)",
    mo_ta="Quy trình / nguyên nhân → kết quả: các ô nối bằng mũi tên chạy xuống, hiện theo lời.",
    hop_nghia=["quy trình", "nguyên nhân kết quả", "các bước", "dẫn tới", "chuỗi", "luồng"],
    tham_so={"buoc": "list: \"chữ\" | [chữ, giây] (≤ 5)", "nhip": "giây giữa 2 ô (0.6)", "bat_dau": "giây ô đầu (0.15)"},
    mac_dinh={"nhip": 0.6, "bat_dau": 0.15},
    hop={"anchor": "mc", "x": 0.5, "y": 0.58, "w": 0.8, "h": 0.38}, dong=True, sfx_goi_y=["whoosh nhẹ", "pop nhẹ", "click"],
    vi_du={"buoc": ["Video đúng nỗi đau", "Khách nhắn tin hỏi", "Chốt đơn trong ngày"], "nhip": 0.55}))
def quy_trinh(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, ftd = _f(p)
    ds = [muc(x) for x in (p.get("buoc") or [])][:5]
    ts = lich(len(ds), dur, p.get("nhip", 0.6), p.get("bat_dau", 0.15), [d.get("t") for d in ds])

    def bo(u):
        m = 24 * u
        rong = W - 2 * m - 190 * u
        co = min([vua(c, str(d.get("chu", "")), 50 * u, rong, 1, 2, co_min=28 * u, vai=font) for d in ds] or [50 * u])
        ims = [anh_chu(c, str(d.get("chu", "")), co, B["chu"], vai=font, rong=rong, can="giua") for d in ds]
        bh = [kich(im)[1] + 52 * u for im in ims]
        bw = [kich(im)[0] + 170 * u for im in ims]
        gap = 70 * u
        return dict(m=m, ims=ims, bh=bh, bw=bw, gap=gap, w=max(bw + [0]) + 2 * m, h=sum(bh) + gap * max(0, len(bh) - 1) + 2 * m)
    u, L = _bo_cuc("quy-trinh", W, H, p, B, c, bo)
    y = (H - L["h"]) / 2 + L["m"]
    cx = W / 2
    lw = max(2.0, 5 * u)
    for i, im in enumerate(L["ims"]):
        h, w = L["bh"][i], L["bw"][i]
        if i > 0:                                   # mũi tên từ ô trước chạy xuống
            ya, yb = y - L["gap"] + 8 * u, y - 10 * u
            k = e_io(tien(t, ts[i] - 0.28, 0.28))
            if k > 0:
                ye = ya + (yb - ya) * k
                cv.drawLine(cx, ya, cx, ye - 6 * u, p_net(B["nhan"], lw))
                pa = skia.Path(); s_ = 14 * u
                pa.moveTo(cx - s_, ye - s_ * 1.1); pa.lineTo(cx, ye); pa.lineTo(cx + s_, ye - s_ * 1.1)
                cv.drawPath(pa, p_net(B["nhan"], lw))
        k = tien(t, ts[i], 0.35)
        if k > 0:
            a = e_out(k)
            s = 0.9 + 0.1 * e_back(k)
            cy = y + h / 2
            cv.save(); cv.translate(cx, cy); cv.scale(s, s); cv.translate(-cx, -cy)
            the_noi(cv, B, cx - w / 2, y, cx + w / 2, y + h, 22 * u, u, al=a, vien=False)
            hop(cv, cx - w / 2, y, cx + w / 2, y + h, 22 * u, "#00000000", a, B["nhan"], 3 * u)
            r = min(h * 0.32, 34 * u)
            bxc = cx - w / 2 + 26 * u + r
            cv.drawCircle(bxc, cy, r, p_to(B["nhan"], a))
            dat(cv, anh_chu(c, str(i + 1), r * 1.1, B["tren_nhan"], vai=ftd), bxc, cy, "mc", a)
            dat(cv, im, cx + (r + 13 * u), cy, "mc", a)
            cv.restore()
        y += h + L["gap"]
    return ra(surf)


# ---------------------------------------------------------------- thẻ so sánh A|B
@dang_ky(**_the(
    id="mau.the-so-sanh", ten="Thẻ đối đầu A | B (bên thắng tô màu)",
    mo_ta="Hai lựa chọn / trước–sau đặt cạnh nhau với VS ở giữa; tới lúc chốt, bên thắng đổ màu nhấn, bên kia dịu xuống.",
    hop_nghia=["so sánh", "đối lập", "lựa chọn", "nên hay không", "trước sau", "thay vì"],
    tham_so={"a": "chữ bên trái", "b": "chữ bên phải", "nhan_a": "nhãn nhỏ trên a", "nhan_b": "nhãn nhỏ trên b",
             "thang": "a | b (b)", "thang_luc": "giây đổ màu bên thắng (0.9)", "vs": "chữ giữa (VS; \"\" = bỏ)", "nhip": "giây b hiện sau a (0.25)"},
    mac_dinh={"thang": "b", "thang_luc": 0.9, "vs": "VS", "nhip": 0.25},
    hop={"anchor": "mc", "x": 0.5, "y": 0.6, "w": 0.92, "h": 0.2}, dong=True, sfx_goi_y=["swoosh", "ding", "pop nhẹ"],
    vi_du={"nhan_a": "Cách cũ", "a": "Tự quay tự dựng", "nhan_b": "Cách mới", "b": "Studio dựng hộ", "thang_luc": 1.2}))
def the_so_sanh(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, ftd = _f(p)
    thang_b = str(p.get("thang", "b")) != "a"

    def bo(u):
        m = 22 * u
        gap = 36 * u
        cw = (W - 2 * m - gap) / 2
        pad = 30 * u
        co = min(vua(c, str(p.get(k) or ""), 80 * u, cw - 2 * pad, 1, 2, co_min=30 * u, vai=ftd) for k in ("a", "b"))
        im = {}
        for k, ten_nhan in (("a", "nhan_a"), ("b", "nhan_b")):
            im[k] = [anh_chu(c, str(p.get(k) or ""), co, mau, vai=ftd, rong=cw - 2 * pad, can="giua") for mau in (B["chu"], B["tren_nhan"])]
            im[ten_nhan] = [anh_chu(c, str(p.get(ten_nhan) or ""), 32 * u, mau, vai=font, hoa=True, gian=0.08, rong=cw - 2 * pad, can="giua")
                            for mau in (B["phu"], voi_alpha(B["tren_nhan"], 0.8))] if p.get(ten_nhan) else None
        hl = max([kich(im[k][0])[1] + 10 * u for k in ("nhan_a", "nhan_b") if im[k]] + [0])
        hb = max(kich(im["a"][0])[1], kich(im["b"][0])[1])
        ch = hl + hb + 2 * pad + 10 * u
        return dict(m=m, gap=gap, cw=cw, pad=pad, im=im, hl=hl, ch=ch, w=W, h=ch + 2 * m)
    u, L = _bo_cuc("the-so-sanh", W, H, p, B, c, bo, chi_cao=True)
    y0 = (H - L["ch"]) / 2
    kt = e_out(tien(t, float(p.get("thang_luc", 0.9)), 0.4))
    for j, k in enumerate(("a", "b")):
        x0 = L["m"] + j * (L["cw"] + L["gap"])
        kv = tien(t, j * float(p.get("nhip", 0.25)), 0.35)
        if kv <= 0:
            continue
        a = e_out(kv)
        dy = (1 - a) * 30 * u
        la_thang = (j == 1) == thang_b
        do = kt if la_thang else 0.0
        al = a * (1 - 0.35 * kt * (not la_thang))
        the_noi(cv, B, x0, y0 + dy, x0 + L["cw"], y0 + L["ch"] + dy, 28 * u, u, al=al)
        if do > 0:
            bong(cv, x0, y0 + dy, x0 + L["cw"], y0 + L["ch"] + dy, 28 * u, 40 * u, 0.4 * do, mau=B["nhan"] if B["tong"] == "toi" else None)
            hop(cv, x0, y0 + dy, x0 + L["cw"], y0 + L["ch"] + dy, 28 * u, B["nhan"], do * a)
        xc = x0 + L["cw"] / 2
        yy = y0 + dy + L["pad"]
        nk = L["im"]["nhan_" + k]
        if nk:
            dat(cv, nk[0], xc, yy, "tc", al * (1 - do)); dat(cv, nk[1], xc, yy, "tc", al * do)
        yy += L["hl"]
        hb = kich(L["im"][k][0])[1]
        yb = yy + (L["ch"] - 2 * L["pad"] - L["hl"] - hb) / 2
        dat(cv, L["im"][k][0], xc, yb, "tc", al * (1 - do)); dat(cv, L["im"][k][1], xc, yb, "tc", al * do)
    vs = str(p.get("vs") or "")
    if vs and t > 0.1:
        a = e_out(tien(t, 0.15, 0.3))
        r = 40 * u * (0.7 + 0.3 * e_back(tien(t, 0.15, 0.35)))
        cx, cy = W / 2, y0 + L["ch"] / 2
        bong(cv, cx - r, cy - r, cx + r, cy + r, r, 24 * u, 0.4 * a)
        cv.drawCircle(cx, cy, r, p_to(B["toi"] if B["tong"] != "sang" else B["chu"], a))
        cv.drawCircle(cx, cy, r, p_net(B["nhan2"], 3 * u, a))
        dat(cv, anh_chu(c, vs, r * 0.72, "#ffffff", vai=ftd), cx, cy, "mc", a)
    return ra(surf)


# ---------------------------------------------------------------- thanh tiến trình + chương
@dang_ky(**_the(
    id="mau.tien-trinh", ten="Thanh tiến trình + nhãn chương",
    mo_ta="Lớp nền suốt video dài: thanh mảnh chạy theo thời gian + tên chương hiện tại — người xem biết đang ở đâu, còn bao lâu.",
    hop_nghia=["chương", "mục lục", "video dài", "phần", "tiến độ xem"],
    tham_so={"chuong": "list [giây từ đầu lớp, tên chương]", "tong": "tổng giây thanh chạy hết (mặc định = độ dài lớp)",
             "day": "độ dày thanh, phần cao hộp (0.06)", "vach": "vạch mốc chương trên thanh true/false (true)"},
    mac_dinh={"day": 0.06, "vach": True},
    hop={"anchor": "tl", "x": 0.0, "y": 0.0, "w": 1.0, "h": 0.12}, dong=True, sfx_goi_y=["click nhẹ"],
    vi_du={"chuong": [[0, "1 · Vì sao video ít view"], [1.5, "2 · Cách sửa hook"]], "tong": 3}))
def tien_trinh(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, _ = _f(p)
    tong = float(p.get("tong") or dur) or 1.0
    day = max(3.0, H * float(p.get("day", 0.06)))
    u = min(don_vi_goc(c), H / 230.0)
    cv.drawRect(skia.Rect.MakeLTRB(0, 0, W, day), p_to("#000000", 0.35))
    k = kep(t / tong)
    pf = p_to(B["nhan"])
    pf.setShader(skia.GradientShader.MakeLinear([skia.Point(0, 0), skia.Point(W, 0)], [sk(tron(B["nhan"], B["nhan2"], 0.35)), sk(B["nhan"])]))
    cv.drawRect(skia.Rect.MakeLTRB(0, 0, W * k, day), pf)
    ch = sorted([(float(a), str(b)) for a, b in (p.get("chuong") or [])])
    if p.get("vach", True):
        for a, _ in ch[1:]:
            x = W * kep(a / tong)
            cv.drawRect(skia.Rect.MakeLTRB(x - 1.5 * u, 0, x + 1.5 * u, day), p_to("#000000", 0.55))
    cv.drawCircle(W * k, day / 2, day * 0.9, p_to(B["nhan"], 0.35))
    hien = [i for i, (a, _) in enumerate(ch) if a <= t]
    if hien:
        i = hien[-1]
        for j, al in ((i, e_out(tien(t, ch[i][0], 0.3))), (i - 1, 1 - e_out(tien(t, ch[i][0], 0.3)))):
            if j < 0 or al <= 0.01:
                continue
            im = anh_chu(c, ch[j][1], 34 * u, B["chu"], vai=font, rong=W * 0.8)
            w_, h_ = kich(im)
            x0, y0 = 26 * u, day + 22 * u
            the_noi(cv, B, x0, y0, x0 + w_ + 40 * u, y0 + h_ + 20 * u, 12 * u, u, al=al * 0.94, vien=False)
            cv.drawRRect(rr(x0, y0, x0 + 6 * u, y0 + h_ + 20 * u, 3 * u), p_to(B["nhan"], al))
            dat(cv, im, x0 + 22 * u, y0 + 10 * u, "tl", al)
    return ra(surf)


# ---------------------------------------------------------------- thẻ chương
@dang_ky(**_the(
    id="mau.chuong", ten="Thẻ chương 3 tầng",
    mo_ta="Báo sang ý lớn mới: nhãn số nhỏ · dòng mảnh · CHỮ ĐẬM trên dải tối (hoặc phủ cả hộp) — đổi 'không gian' 1–3 giây.",
    hop_nghia=["chuyển ý", "phần mới", "chương", "tiếp theo", "bước sang"],
    tham_so={"nhan": "nhãn nhỏ (01, PHẦN 2…)", "mong": "dòng mảnh", "dam": "chữ đậm chính", "toan_man": "phủ tối cả hộp true/false (false)",
             "do_toi": "độ đặc dải tối 0..1 (0.88)"},
    mac_dinh={"toan_man": False, "do_toi": 0.88},
    hop={"anchor": "mc", "x": 0.5, "y": 0.45, "w": 1.0, "h": 0.3}, dong=False, sfx_goi_y=["whoosh", "boom nhẹ", "riser ngắn"],
    vi_du={"nhan": "Phần 02", "mong": "Bí quyết thứ hai", "dam": "Giữ chân 3 giây đầu"}))
def chuong(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, ftd = _f(p)
    sang = c.mau("sang")

    def bo(u):
        rong = W * 0.86
        i1 = anh_chu(c, str(p.get("nhan") or ""), 36 * u, B["nhan"], vai=font, hoa=True, gian=0.25) if p.get("nhan") else None
        i2 = anh_chu(c, str(p.get("mong") or ""), vua(c, str(p.get("mong") or ""), 56 * u, rong, 1, 2, vai="than"), sang, vai="than",
                     rong=rong, can="giua") if p.get("mong") else None
        i3 = anh_chu(c, str(p.get("dam") or ""), vua(c, str(p.get("dam") or ""), 128 * u, rong, 1, 2, co_min=50 * u, vai=ftd), sang,
                     vai=ftd, rong=rong, can="giua", dong=1.05) if p.get("dam") else None
        hs = [kich(i)[1] for i in (i1, i2, i3) if i]
        pad = 60 * u
        return dict(i1=i1, i2=i2, i3=i3, pad=pad, w=max([kich(i)[0] for i in (i1, i2, i3) if i] + [1]),
                    h=sum(hs) + 22 * u * max(0, len(hs) - 1) + (26 * u if i1 else 0) + 2 * pad)
    u, L = _bo_cuc("chuong", W, H, p, B, c, bo)
    dt = float(p.get("do_toi", 0.88))
    nen = B["toi"] if B["tong"] != "sang" else B["chu"]
    if p.get("toan_man"):
        cv.drawRect(skia.Rect.MakeWH(W, H), p_to(nen, dt))
    else:
        y0, y1 = (H - L["h"]) / 2, (H + L["h"]) / 2
        cv.drawRect(skia.Rect.MakeLTRB(0, y0, W, y1), p_to(nen, dt))
        cv.drawRect(skia.Rect.MakeLTRB(0, y0, W, y0 + 3 * u), p_to(B["nhan"], 0.9))
    y = (H - L["h"]) / 2 + L["pad"]
    if L["i1"]:
        b = dat(cv, L["i1"], W / 2, y, "tc")
        y = b[3] + 10 * u
        cv.drawRRect(rr(W / 2 - 40 * u, y, W / 2 + 40 * u, y + 5 * u, 2.5 * u), p_to(B["nhan"]))
        y += 5 * u + 22 * u
    for im in (L["i2"], L["i3"]):
        if im:
            b = dat(cv, im, W / 2, y, "tc")
            y = b[3] + 22 * u
    return ra(surf)


# ---------------------------------------------------------------- ô bình luận gõ chữ
@dang_ky(**_the(
    id="mau.binh-luan", ten="Ô bình luận tự gõ từ khoá",
    mo_ta="Kêu gọi bình luận cụ thể: ô bình luận tự gõ từ khoá từng chữ rồi nút gửi bật lên.",
    hop_nghia=["bình luận", "comment", "để lại từ khoá", "nhắn", "kêu gọi", "cta"],
    tham_so={"tu_khoa": "chữ được gõ", "goi_y": "chữ mờ khi ô trống (Thêm bình luận…)", "bat_dau": "giây bắt đầu gõ (0.4)",
             "toc_go": "ký tự/giây (9)"},
    mac_dinh={"goi_y": "Thêm bình luận…", "bat_dau": 0.4, "toc_go": 9},
    hop={"anchor": "mc", "x": 0.5, "y": 0.68, "w": 0.84, "h": 0.075}, dong=True, sfx_goi_y=["gõ phím", "pop gửi", "whoosh nhẹ"],
    vi_du={"tu_khoa": "Mình cần file mẫu", "toc_go": 10}))
def binh_luan(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, _ = _f(p)
    m = H * 0.08
    x0, y0, x1, y1 = m, m, W - m, H - m
    ph = y1 - y0
    u = ph / 120.0
    nen, chu = (c.mau("sang"), c.mau("toi")) if B["tong"] != "kinh" else (voi_alpha("#ffffff", 0.2), c.mau("sang"))
    bong(cv, x0, y0, x1, y1, ph / 2, 30 * u, 0.4, dy=8 * u)
    hop(cv, x0, y0, x1, y1, ph / 2, nen)
    tk = str(p.get("tu_khoa") or "")
    bd, toc = float(p.get("bat_dau", 0.4)), max(1.0, float(p.get("toc_go", 9)))
    n = int(kep((t - bd) * toc, 0, len(tk))) if t > bd else 0
    rong = (x1 - x0) - ph * 1.6
    co = vua(c, tk or str(p.get("goi_y")), ph * 0.4, rong, 1, 1, co_min=ph * 0.22, vai=font)
    if n:
        im = anh_chu(c, tk[:n], co, chu, vai=font)
        b = dat(cv, im, x0 + ph * 0.45, (y0 + y1) / 2, "ml")
        if n < len(tk) or int(t * 2.2) % 2 == 0:
            cv.drawRect(skia.Rect.MakeLTRB(b[2] + 4 * u, (y0 + y1) / 2 - co * 0.55, b[2] + 4 * u + max(2, 3 * u), (y0 + y1) / 2 + co * 0.55), p_to(B["nhan"]))
    else:
        dat(cv, anh_chu(c, str(p.get("goi_y") or ""), co, tron(chu, nen, 0.55), vai=font), x0 + ph * 0.45, (y0 + y1) / 2, "ml")
    gui = bd + len(tk) / toc + 0.25
    kp = tien(t, gui, 0.35)
    pop = 1 + 0.22 * math.sin(math.pi * kp)
    r = ph * 0.34 * pop
    cx, cy = x1 - ph * 0.5, (y0 + y1) / 2
    cv.drawCircle(cx, cy, r, p_to(B["nhan"] if n else tron(chu, nen, 0.7)))
    s = r * 0.5
    pa = skia.Path(); pa.moveTo(cx - s * 0.7, cy - s * 0.8); pa.lineTo(cx + s * 0.9, cy); pa.lineTo(cx - s * 0.7, cy + s * 0.8)
    pa.lineTo(cx - s * 0.35, cy); pa.close()
    cv.drawPath(pa, p_to(B["tren_nhan"] if n else "#ffffff"))
    if kp > 0:
        cv.drawCircle(cx, cy, ph * 0.34 * (1 + 0.9 * e_out(kp)), p_net(B["nhan"], 3 * u, 1 - kp))
    return ra(surf)


# ---------------------------------------------------------------- kết nhẹ
@dang_ky(**_the(
    id="mau.ket-thuc", ten="Kết nhẹ (chữ ký / lời mời ngắn)",
    mo_ta="Hạ cường độ cuối video: một dòng chữ ký hoặc lời mời ngắn + dòng nhỏ màu nhấn — không ép CTA.",
    hop_nghia=["kết thúc", "cảm ơn", "hẹn gặp lại", "chữ ký", "theo dõi"],
    tham_so={"dong1": "dòng chính", "dong2": "dòng nhỏ màu nhấn (tên kênh…)"},
    hop={"anchor": "mc", "x": 0.5, "y": 0.68, "w": 0.86, "h": 0.12}, dong=False, sfx_goi_y=["chuông nhẹ", "whoosh mềm"],
    vi_du={"dong1": "Cảm ơn bạn đã xem hết", "dong2": "@studio.dung.video"}))
def ket_thuc(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, _ = _f(p)

    def bo(u):
        i1 = anh_chu(c, str(p.get("dong1") or ""), 70 * u, c.mau("sang"), vai=font, rong=W * 0.95, can="giua", bong=bong_chu(u))
        i2 = anh_chu(c, str(p.get("dong2") or ""), 46 * u, c.mau(p.get("mau") or "nhan"), vai=font, gian=0.06, bong=bong_chu(u, 1.4)) \
            if p.get("dong2") else None
        h = kich(i1)[1] + (kich(i2)[1] + 14 * u if i2 else 0)
        return dict(i1=i1, i2=i2, w=max(kich(i1)[0], kich(i2)[0] if i2 else 0) + 40 * u, h=h + 40 * u)
    u, L = _bo_cuc("ket-thuc", W, H, p, B, c, bo)
    y = (H - L["h"]) / 2 + 20 * u
    b = dat(cv, L["i1"], W / 2, y, "tc")
    if L["i2"]:
        dat(cv, L["i2"], W / 2, b[3] + 14 * u, "tc")
    return ra(surf)


# ---------------------------------------------------------------- nhãn chip
@dang_ky(**_the(
    id="mau.nhan-dan", ten="Nhãn từ khoá (chip quét vào)",
    mo_ta="Gắn tên cho thứ đang thấy/đang nói: vạch màu mọc lên, dải tối quét ngang, chữ hiện — nhẹ, không che.",
    hop_nghia=["từ khoá", "tên gọi", "chú thích", "đây là", "nhãn"],
    tham_so={"chu": "chữ nhãn (ngắn)", "quet": "giây quét (0.3)"},
    mac_dinh={"quet": 0.3},
    hop={"anchor": "mc", "x": 0.5, "y": 0.7, "w": 0.6, "h": 0.05}, dong=True, sfx_goi_y=["swoosh nhẹ", "click"],
    vi_du={"chu": "Ánh sáng tự nhiên"}))
def nhan_dan(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, _ = _f(p)

    def bo(u):
        im = anh_chu(c, str(p.get("chu") or ""), 56 * u, c.mau("sang") if B["tong"] != "sang" else B["chu"], vai=font)
        w, h = kich(im)
        return dict(im=im, bar=12 * u, pad=28 * u, hh=h + 30 * u, w=w + 12 * u + 56 * u + 30 * u, h=h + 30 * u + 30 * u)
    u, L = _bo_cuc("nhan-dan", W, H, p, B, c, bo)
    q = max(0.05, float(p.get("quet", 0.3)))
    u1, u2 = e_out(tien(t, 0, q * 0.5)), e_out(tien(t, q * 0.3, q))
    x0 = (W - L["w"]) / 2 + 15 * u
    y0 = (H - L["hh"]) / 2
    hh = L["hh"]
    if u2 > 0:
        wr = (L["w"] - 30 * u - L["bar"]) * u2
        bong(cv, x0 + L["bar"], y0, x0 + L["bar"] + wr, y0 + hh, 4 * u, 22 * u, 0.35 * u2)
        cv.drawRect(skia.Rect.MakeLTRB(x0 + L["bar"], y0, x0 + L["bar"] + wr, y0 + hh), p_to(B["the"] if B["tong"] != "toi" else B["toi"], 0.92))
        cv.save(); cv.clipRect(skia.Rect.MakeLTRB(x0, y0, x0 + L["bar"] + wr, y0 + hh))
        dat(cv, L["im"], x0 + L["bar"] + L["pad"], y0 + hh / 2, "ml", e_out(tien(t, q * 0.5, q * 0.8)))
        cv.restore()
    cv.drawRect(skia.Rect.MakeLTRB(x0, y0, x0 + L["bar"], y0 + hh * u1), p_to(B["nhan"]))
    return ra(surf)


# ---------------------------------------------------------------- tiêu đề ghim
@dang_ky(**_the(
    id="mau.tieu-de-ghim", ten="Tiêu đề bước ghim",
    mo_ta="Video hướng dẫn nhiều bước: số bước lớn màu nhấn + tên bước ghim suốt chương — lỡ một câu vẫn bắt lại được.",
    hop_nghia=["bước", "hướng dẫn", "phần", "đang làm gì", "thao tác"],
    tham_so={"so": "số bước (1, 2…; \"\" = bỏ)", "chu": "tên bước"},
    hop={"anchor": "tl", "x": 0.06, "y": 0.1, "w": 0.8, "h": 0.075}, dong=False, sfx_goi_y=["click", "pop nhẹ"],
    vi_du={"so": "2", "chu": "Chọn nhạc nền"}))
def tieu_de_ghim(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, ftd = _f(p)

    def bo(u):
        m = 16 * u
        i1 = anh_chu(c, str(p.get("so")), 120 * u, c.mau(p.get("mau") or "nhan"), vai=ftd, bong=bong_chu(u)) if str(p.get("so") or "") else None
        w1 = kich(i1)[0] + 24 * u if i1 else 0
        rong = max(100 * u, W - 2 * m - w1)
        co = vua(c, str(p.get("chu") or ""), 64 * u, rong, 1, 2, co_min=34 * u, vai=font)
        i2 = anh_chu(c, str(p.get("chu") or ""), co, c.mau("sang"), vai=font, rong=rong, bong=bong_chu(u))
        return dict(m=m, i1=i1, i2=i2, w1=w1, w=w1 + kich(i2)[0] + 2 * m, h=max(kich(i1)[1] if i1 else 0, kich(i2)[1]) + 2 * m)
    u, L = _bo_cuc("tieu-de-ghim", W, H, p, B, c, bo)
    x, cy = L["m"], H / 2
    if L["i1"]:
        dat(cv, L["i1"], x, cy, "ml")
    dat(cv, L["i2"], x + L["w1"], cy, "ml")
    return ra(surf)


# ---------------------------------------------------------------- bảng giá
@dang_ky(**_the(
    id="mau.bang-gia", ten="Bảng giá / các gói",
    mo_ta="1–3 gói đặt cạnh nhau: tên, giá, quyền lợi tích dần; gói nổi bật viền màu nhấn + ruy băng (Phổ biến / Tiết kiệm).",
    hop_nghia=["giá", "gói", "bảng giá", "ưu đãi", "combo", "bao nhiêu tiền", "lựa chọn gói"],
    tham_so={"goi": "list {ten, gia, ky (\"/tháng\"), y: [quyền lợi], noi_bat: true, nhan: \"Phổ biến\"} (≤ 3)",
             "nhip": "giây giữa 2 gói (0.35)", "nhip_y": "giây giữa 2 quyền lợi (0.12)", "bat_dau": "giây gói đầu (0.1)"},
    mac_dinh={"nhip": 0.35, "nhip_y": 0.12, "bat_dau": 0.1},
    hop={"anchor": "mc", "x": 0.5, "y": 0.57, "w": 0.92, "h": 0.4}, dong=True, sfx_goi_y=["pop nhẹ", "tích", "ka-ching"],
    vi_du={"goi": [{"ten": "Cơ bản", "gia": "199k", "ky": "/tháng", "y": ["10 video", "Phụ đề tự động"]},
                   {"ten": "Chuyên nghiệp", "gia": "499k", "ky": "/tháng", "y": ["Không giới hạn", "Nhạc bản quyền", "Hỗ trợ 24/7"],
                    "noi_bat": True, "nhan": "Phổ biến"}]}))
def bang_gia(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, ftd = _f(p)
    ds = []
    for x in (p.get("goi") or [])[:3]:
        if isinstance(x, (list, tuple)):
            x = {"ten": x[0] if x else "", "gia": x[1] if len(x) > 1 else "", "y": x[2] if len(x) > 2 else []}
        ds.append(dict(x))
    n = max(1, len(ds))
    ts = lich(len(ds), dur, p.get("nhip", 0.35), p.get("bat_dau", 0.1))

    def bo(u):
        m = 24 * u
        gap = 22 * u
        cw = (W - 2 * m - gap * (n - 1)) / n
        pad = 30 * u
        rong = cw - 2 * pad
        co_y0 = 32 * u
        co_g = min([vua(c, str(d.get("gia", "")), 80 * u, rong, 1, 1, co_min=30 * u, vai=ftd) for i, d in enumerate(ds)] or [80 * u])
        co_y = min([vua(c, str(y), 32 * u, rong - 44 * u, 1, 3, co_min=20 * u, vai="than") for d in ds for y in (d.get("y") or [])] or [32 * u])
        co_t = min([vua(c, str(d.get("ten", "")), 36 * u, rong, 1, 2, co_min=22 * u, vai=font) for d in ds] or [36 * u])
        the = []
        for d in ds:
            nb = bool(d.get("noi_bat"))
            i_t = anh_chu(c, str(d.get("ten", "")), co_t, B["nhan"] if nb else B["phu"], vai=font, rong=rong)
            i_g = anh_chu(c, str(d.get("gia", "")), co_g, B["chu"], vai=ftd)
            i_k = anh_chu(c, str(d.get("ky", "")), co_y0 * 0.95, B["phu"], vai="than") if d.get("ky") else None
            i_y = [anh_chu(c, str(y), co_y, B["chu"], vai="than", rong=rong - 44 * u) for y in (d.get("y") or [])]
            h = pad + kich(i_t)[1] + 10 * u + kich(i_g)[1] + 40 * u + \
                sum(kich(i)[1] + 16 * u for i in i_y) + pad
            k_duoi = bool(i_k) and kich(i_g)[0] + kich(i_k)[0] + 8 * u > rong
            if k_duoi:
                h += kich(i_k)[1]
            the.append(dict(i_t=i_t, i_g=i_g, i_k=i_k, i_y=i_y, h=h, nb=nb, k_duoi=k_duoi))
        ch = max([x["h"] for x in the] + [1])
        rb = 34 * u if any(x["nb"] for x in the) else 0
        return dict(m=m, gap=gap, cw=cw, pad=pad, co_y=co_y, the=the, ch=ch, rb=rb, w=W, h=ch + rb + 2 * m)
    u, L = _bo_cuc("bang-gia", W, H, p, B, c, bo, chi_cao=True)
    y0 = (H - L["ch"] - L["rb"]) / 2 + L["rb"]
    for i, d in enumerate(L["the"]):
        k = tien(t, ts[i], 0.4)
        if k <= 0:
            continue
        a = e_out(k)
        x0 = L["m"] + i * (L["cw"] + L["gap"])
        dy = (1 - a) * 40 * u
        yt = y0 + dy
        if d["nb"]:
            bong(cv, x0, yt, x0 + L["cw"], yt + L["ch"], 28 * u, 46 * u, 0.45 * a, mau=B["nhan"] if B["tong"] == "toi" else None)
        the_noi(cv, B, x0, yt, x0 + L["cw"], yt + L["ch"], 28 * u, u, al=a, mau=B["the2"] if d["nb"] else B["the"], vien=not d["nb"])
        if d["nb"]:
            hop(cv, x0, yt, x0 + L["cw"], yt + L["ch"], 28 * u, "#00000000", a, B["nhan"], 3.5 * u)
            nh = ds[i].get("nhan")
            if nh:
                ir = anh_chu(c, str(nh), 26 * u, B["tren_nhan"], vai=font, hoa=True, gian=0.06)
                rw, rh = kich(ir)
                cxr = x0 + L["cw"] / 2
                hop(cv, cxr - rw / 2 - 18 * u, yt - rh / 2 - 9 * u, cxr + rw / 2 + 18 * u, yt + rh / 2 + 9 * u, rh, B["nhan"], a)
                dat(cv, ir, cxr, yt, "mc", a)
        xx = x0 + L["pad"]
        yy = yt + L["pad"]
        b = dat(cv, d["i_t"], xx, yy, "tl", a)
        b = dat(cv, d["i_g"], xx, b[3] + 10 * u, "tl", a)
        if d["i_k"] and d["k_duoi"]:
            b = dat(cv, d["i_k"], xx, b[3], "tl", a)
        elif d["i_k"]:
            dat(cv, d["i_k"], b[2] + 8 * u, b[3] - 0.18 * (b[3] - b[1]), "bl", a)
        yy = b[3] + 20 * u
        cv.drawLine(xx, yy, x0 + L["cw"] - L["pad"], yy, p_net(B["vien"], max(1, 2 * u), a, False))
        yy += 20 * u
        for j, iy in enumerate(d["i_y"]):
            ky = tien(t, ts[i] + 0.25 + j * float(p.get("nhip_y", 0.12)), 0.3)
            h = kich(iy)[1]
            if ky > 0:
                r = 14 * u
                cv.drawCircle(xx + r, yy + h / 2, r, p_to(B["nhan"] if d["nb"] else B["vien"], e_out(ky)))
                dau_tich(cv, xx + r, yy + h / 2, r * 1.3, B["tren_nhan"] if d["nb"] else B["chu"], e_io(ky))
                dat(cv, iy, xx + 44 * u, yy, "tl", e_out(ky))
            yy += h + 16 * u
    return ra(surf)


# ---------------------------------------------------------------- đánh giá sao
@dang_ky(**_the(
    id="mau.danh-gia-sao", ten="Điểm đánh giá sao",
    mo_ta="Bằng chứng xã hội: điểm lớn đếm lên, 5 sao tô dần theo điểm, số lượt đánh giá, (tuỳ) thanh phân bố 5→1 sao mọc dần.",
    hop_nghia=["đánh giá", "review", "sao", "khách khen", "uy tín", "chất lượng"],
    tham_so={"diem": "điểm (4,9)", "thang": "thang điểm (5)", "so_luot": "dòng số lượt (\"1.248 đánh giá\")",
             "phan_bo": "list % 5 sao → 1 sao (tuỳ)", "dem": "giây đếm điểm (1.0)", "nhan": "dòng nhỏ trên (tuỳ)"},
    mac_dinh={"thang": 5, "dem": 1.0},
    hop={"anchor": "mc", "x": 0.5, "y": 0.62, "w": 0.9, "h": 0.18}, dong=True, sfx_goi_y=["ting sao", "tick đếm số", "pop nhẹ"],
    vi_du={"diem": "4,9", "so_luot": "1.248 đánh giá", "phan_bo": [86, 9, 3, 1, 1], "nhan": "Shopee Mall"}))
def danh_gia_sao(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, ftd = _f(p)
    diem, thang = so(p.get("diem")), max(1, int(so(p.get("thang"), 5)))
    le = le_cua(p.get("diem")) or 1
    pb = [so(x) for x in (p.get("phan_bo") or [])][:thang]
    vang = c.mau(p.get("mau") or "nhan")

    def bo(u):
        pad = 40 * u
        i_d = anh_chu(c, so_vn(diem, le), 150 * u, B["chu"], vai=ftd)
        i_n = anh_chu(c, str(p.get("nhan")), 28 * u, B["nhan"], vai=font, hoa=True, gian=0.1) if p.get("nhan") else None
        i_l = anh_chu(c, str(p.get("so_luot")), 32 * u, B["phu"], vai="than") if p.get("so_luot") else None
        r = 30 * u
        w_sao = thang * 2 * r + (thang - 1) * 10 * u
        wl = max(kich(i_d)[0], w_sao, kich(i_l)[0] if i_l else 0)
        hl = (kich(i_n)[1] + 8 * u if i_n else 0) + kich(i_d)[1] + 2 * r + 14 * u + (kich(i_l)[1] + 10 * u if i_l else 0)
        wr = 440 * u if pb else 0
        hr = len(pb) * 46 * u
        return dict(pad=pad, i_d=i_d, i_n=i_n, i_l=i_l, r=r, w_sao=w_sao, wl=wl, hl=hl, wr=wr, hr=hr,
                    w=wl + (60 * u + wr if pb else 0) + 2 * pad + 40 * u, h=max(hl, hr) + 2 * pad + 40 * u)
    u, L = _bo_cuc("danh-gia", W, H, p, B, c, bo)
    x0, y0 = (W - L["w"]) / 2 + 20 * u, (H - L["h"]) / 2 + 20 * u
    x1, y1 = x0 + L["w"] - 40 * u, y0 + L["h"] - 40 * u
    the_noi(cv, B, x0, y0, x1, y1, 32 * u, u)
    k = e_out(tien(t, 0.1, float(p.get("dem", 1.0))))
    hien = diem * k
    cxl = x0 + L["pad"] + L["wl"] / 2
    y = y0 + L["pad"] + (max(L["hl"], L["hr"]) - L["hl"]) / 2
    if L["i_n"]:
        b = dat(cv, L["i_n"], cxl, y, "tc"); y = b[3] + 8 * u
    b = dat(cv, anh_chu(c, so_vn(hien, le), 150 * u, B["chu"], vai=ftd), cxl, y, "tc")
    y = b[3] + 4 * u
    r = L["r"]
    sx = cxl - L["w_sao"] / 2 + r
    for j in range(thang):
        sao(cv, sx + j * (2 * r + 10 * u), y + r, r, vang, B["vien"], kep(hien * thang / max(thang, 1) - j) if thang else 0)
    y += 2 * r + 14 * u
    if L["i_l"]:
        dat(cv, L["i_l"], cxl, y, "tc", e_out(tien(t, 0.4, 0.3)))
    if pb:
        xr = x0 + L["pad"] + L["wl"] + 60 * u
        yr = y0 + L["pad"] + (max(L["hl"], L["hr"]) - L["hr"]) / 2
        cv.drawLine(xr - 30 * u, yr, xr - 30 * u, yr + L["hr"], p_net(B["vien"], max(1, 2 * u), 1, False))
        for j, v in enumerate(pb):
            cy = yr + j * 46 * u + 23 * u
            im = anh_chu(c, str(thang - j), 28 * u, B["phu"], vai=font)
            dat(cv, im, xr, cy, "ml")
            sao(cv, xr + 36 * u, cy, 11 * u, vang, vang)
            bx0, bx1 = xr + 60 * u, xr + L["wr"]
            hop(cv, bx0, cy - 7 * u, bx1, cy + 7 * u, 7 * u, B["vien"])
            kb = e_io(tien(t, 0.3 + j * 0.1, 0.7))
            if kb > 0 and v > 0:
                hop(cv, bx0, cy - 7 * u, bx0 + max(14 * u, (bx1 - bx0) * kep(v / 100.0) * kb), cy + 7 * u, 7 * u, vang)
    return ra(surf)


# ---------------------------------------------------------------- đếm ngược
def _nhom_so(gia_tri, co_gio):
    s = int(max(0, gia_tri))
    h, m, x = s // 3600, (s % 3600) // 60, s % 60
    return ([h, m, x] if co_gio else [m + h * 60, x])


@dang_ky(**_the(
    id="mau.dem-nguoc", ten="Đồng hồ đếm ngược ưu đãi",
    mo_ta="Khan hiếm thời gian: nhãn + các ô số giờ/phút/giây đếm lùi (số lật khi đổi) + thanh thời gian còn lại co dần.",
    hop_nghia=["đếm ngược", "sắp hết", "ưu đãi có hạn", "flash sale", "chỉ còn", "nhanh tay"],
    tham_so={"tu": "giây trên đồng hồ lúc bắt đầu (900 = 15:00)", "toc": "giây đồng hồ chạy mỗi giây thật (1)",
             "nhan": "dòng trên (Ưu đãi kết thúc sau)", "thanh": "hiện thanh thời gian true/false (true)",
             "tong": "giây ứng với thanh đầy (mặc định = tu)", "chu_don_vi": "list chữ dưới ô (tự: giờ/phút/giây)"},
    mac_dinh={"tu": 900, "toc": 1, "nhan": "Ưu đãi kết thúc sau", "thanh": True},
    hop={"anchor": "mc", "x": 0.5, "y": 0.22, "w": 0.84, "h": 0.17}, dong=True, sfx_goi_y=["tích tắc", "tick đồng hồ", "chuông báo"],
    vi_du={"tu": 754, "toc": 1, "nhan": "Flash sale kết thúc sau", "tong": 3600}))
def dem_nguoc(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, ftd = _f(p)
    tu, toc = float(so(p.get("tu"), 900)), float(so(p.get("toc"), 1))
    co_gio = tu >= 3600
    ng = len(_nhom_so(tu, co_gio))
    dvs = list(p.get("chu_don_vi") or (["giờ", "phút", "giây"] if co_gio else ["phút", "giây"]))

    def bo(u):
        pad = 34 * u
        i_n = anh_chu(c, str(p.get("nhan") or ""), 34 * u, B["chu"], vai=font) if p.get("nhan") else None
        co = 96 * u
        mau_o = anh_chu(c, "88", co, B["chu"], vai=ftd)
        bw, bh = kich(mau_o)[0] + 44 * u, kich(mau_o)[1] + 30 * u
        cw = 34 * u
        w_o = ng * bw + (ng - 1) * cw
        h = 2 * pad + (kich(i_n)[1] + 20 * u if i_n else 0) + bh + 40 * u + (34 * u if p.get("thanh", True) else 0)
        return dict(pad=pad, i_n=i_n, co=co, bw=bw, bh=bh, cw=cw, w_o=w_o, w=max(w_o, kich(i_n)[0] if i_n else 0) + 2 * pad + 40 * u, h=h + 40 * u)
    u, L = _bo_cuc("dem-nguoc", W, H, p, B, c, bo)
    x0, y0 = (W - L["w"]) / 2 + 20 * u, (H - L["h"]) / 2 + 20 * u
    x1, y1 = x0 + L["w"] - 40 * u, y0 + L["h"] - 40 * u
    the_noi(cv, B, x0, y0, x1, y1, 30 * u, u)
    y = y0 + L["pad"]
    if L["i_n"]:
        b = dat(cv, L["i_n"], (x0 + x1) / 2, y, "tc"); y = b[3] + 20 * u
    dong_ho = tu - t * toc
    hien, truoc = _nhom_so(math.ceil(dong_ho - 1e-6), co_gio), _nhom_so(math.ceil(dong_ho - 1e-6) + 1, co_gio)
    phan = (t * toc) % 1.0
    lat = e_out(kep(phan / 0.22)) if toc > 0 else 1.0
    ox = (x0 + x1) / 2 - L["w_o"] / 2
    for g in range(ng):
        bx = ox + g * (L["bw"] + L["cw"])
        hop(cv, bx, y, bx + L["bw"], y + L["bh"], 18 * u, B["the2"])
        cv.save(); cv.clipRRect(rr(bx, y, bx + L["bw"], y + L["bh"], 18 * u), True)
        cy = y + L["bh"] / 2
        if hien[g] != truoc[g] and lat < 1:
            dat(cv, anh_chu(c, "%02d" % truoc[g], L["co"], B["chu"], vai=ftd), bx + L["bw"] / 2, cy + lat * L["bh"] * 0.6, "mc", 1 - lat)
            dat(cv, anh_chu(c, "%02d" % hien[g], L["co"], B["chu"], vai=ftd), bx + L["bw"] / 2, cy - (1 - lat) * L["bh"] * 0.6, "mc", lat)
        else:
            dat(cv, anh_chu(c, "%02d" % hien[g], L["co"], B["chu"], vai=ftd), bx + L["bw"] / 2, cy, "mc")
        cv.restore()
        cv.drawLine(bx + 6 * u, cy, bx + L["bw"] - 6 * u, cy, p_net(B["nen"] if B["tong"] != "sang" else "#ffffff", max(1, 2 * u), 0.5, False))
        if g < len(dvs):
            dat(cv, anh_chu(c, str(dvs[g]), 24 * u, B["phu"], vai="than"), bx + L["bw"] / 2, y + L["bh"] + 8 * u, "tc")
        if g < ng - 1:
            for s_ in (-1, 1):
                cv.drawCircle(bx + L["bw"] + L["cw"] / 2, cy + s_ * L["bh"] * 0.16, 5 * u, p_to(B["nhan"], 0.6 + 0.4 * (phan < 0.5)))
    if p.get("thanh", True):
        yb = y1 - L["pad"] - 12 * u
        tong = float(so(p.get("tong"), tu)) or tu or 1
        kk = kep(dong_ho / tong)
        hop(cv, x0 + L["pad"], yb, x1 - L["pad"], yb + 12 * u, 6 * u, B["vien"])
        if kk > 0:
            pf = p_to(B["nhan"])
            pf.setShader(skia.GradientShader.MakeLinear([skia.Point(x0, 0), skia.Point(x1, 0)], [sk(B["nhan"]), sk(tron(B["nhan"], "#ffffff", 0.25))]))
            cv.drawRRect(rr(x0 + L["pad"], yb, x0 + L["pad"] + (x1 - x0 - 2 * L["pad"]) * kk, yb + 12 * u, 6 * u), pf)
    return ra(surf)


# ---------------------------------------------------------------- lower third
@dang_ky(**_the(
    id="mau.lower-third", ten="Lower-third tên người",
    mo_ta="Giới thiệu người nói: vạch màu mọc lên, tấm tên quét ra, tấm chức danh màu nhấn trượt theo.",
    hop_nghia=["giới thiệu", "tên", "tôi là", "chuyên gia", "khách mời", "chức danh"],
    tham_so={"ten": "tên người", "chuc_danh": "chức danh / mô tả ngắn", "hien": "giây lộ hết (0.7)", "can": "trai | phai (trai)"},
    mac_dinh={"hien": 0.7, "can": "trai"},
    hop={"anchor": "bl", "x": 0.05, "y": 0.76, "w": 0.72, "h": 0.1}, dong=True, sfx_goi_y=["swoosh", "whoosh nhẹ"],
    vi_du={"ten": "Nguyễn Thu Hà", "chuc_danh": "Chủ shop thời trang 8 năm"}))
def lower_third(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, ftd = _f(p)

    def bo(u):
        m = 16 * u
        i1 = anh_chu(c, str(p.get("ten") or ""), 58 * u, B["chu"], vai=ftd)
        i2 = anh_chu(c, str(p.get("chuc_danh") or ""), 32 * u, B["tren_nhan"], vai=font) if p.get("chuc_danh") else None
        w1, h1 = kich(i1)[0] + 56 * u, kich(i1)[1] + 30 * u
        w2, h2 = (kich(i2)[0] + 40 * u, kich(i2)[1] + 18 * u) if i2 else (0, 0)
        return dict(m=m, i1=i1, i2=i2, w1=w1, h1=h1, w2=w2, h2=h2, bar=10 * u, w=10 * u + max(w1, w2 + 20 * u) + 2 * m, h=h1 + h2 + 2 * m)
    u, L = _bo_cuc("lower-third", W, H, p, B, c, bo)
    hien = max(0.1, float(p.get("hien", 0.7)))
    phai = str(p.get("can")) == "phai"
    x0 = L["m"] if not phai else W - L["w"] + L["m"]
    y0 = (H - L["h"]) / 2 + L["m"]
    if phai:
        cv.save(); cv.translate(W, 0); cv.scale(-1, 1); cv.translate(-W, 0)
        x0 = L["m"]
    hb = L["h1"] + L["h2"]
    kb = e_out(tien(t, 0, hien * 0.3))
    k1 = e_out(tien(t, hien * 0.15, hien * 0.55))
    k2 = e_out(tien(t, hien * 0.4, hien * 0.6))
    xa = x0 + L["bar"]
    if k1 > 0:
        bong(cv, xa, y0, xa + L["w1"] * k1, y0 + L["h1"], 6 * u, 26 * u, 0.4 * k1)
        hop(cv, xa, y0, xa + L["w1"] * k1, y0 + L["h1"], 4 * u, B["the"] if B["tong"] != "toi" else B["toi"], 0.94)
    if k2 > 0 and L["i2"]:
        hop(cv, xa, y0 + L["h1"], xa + L["w2"] * k2, y0 + L["h1"] + L["h2"], 4 * u, B["nhan"])
    if phai:
        cv.restore()
        xa = W - xa
    if k1 > 0:
        cv.save(); cv.clipRect(skia.Rect.MakeLTRB(min(xa, xa + (L["w1"] * k1) * (-1 if phai else 1)), y0,
                                                  max(xa, xa + (L["w1"] * k1) * (-1 if phai else 1)), y0 + L["h1"]))
        dat(cv, L["i1"], xa + (28 * u + (1 - k1) * -30 * u) * (-1 if phai else 1), y0 + L["h1"] / 2, "mr" if phai else "ml")
        cv.restore()
    if k2 > 0 and L["i2"]:
        cv.save(); cv.clipRect(skia.Rect.MakeLTRB(min(xa, xa + L["w2"] * k2 * (-1 if phai else 1)), y0 + L["h1"],
                                                  max(xa, xa + L["w2"] * k2 * (-1 if phai else 1)), y0 + hb))
        dat(cv, L["i2"], xa + 20 * u * (-1 if phai else 1), y0 + L["h1"] + L["h2"] / 2, "mr" if phai else "ml")
        cv.restore()
    xb = x0 if not phai else W - x0 - L["bar"]
    cv.drawRect(skia.Rect.MakeLTRB(xb, y0 + hb * (1 - kb), xb + L["bar"], y0 + hb), p_to(B["nhan"]))
    return ra(surf)


# ---------------------------------------------------------------- trích dẫn lớn
@dang_ky(**_the(
    id="mau.trich-dan", ten="Câu trích dẫn lớn",
    mo_ta="Câu nói đáng nhớ: dấu ngoặc kép lớn màu nhấn, chữ hiện dần từng từ, dòng tác giả có gạch màu.",
    hop_nghia=["trích dẫn", "câu nói", "châm ngôn", "lời khách", "nhận xét", "như ai đó nói"],
    tham_so={"cau": "câu trích (lấy đúng lời)", "tac_gia": "tên người nói (tuỳ)", "mo_ta": "dòng nhỏ dưới tên (tuỳ)",
             "hien": "tu (từng từ) | ca (cả câu) (tu)", "nhip_tu": "giây giữa 2 từ (0.07)", "bat_dau": "giây từ đầu (0.15)",
             "nen": "khong | the (khong)", "can": "trai | giua (trai)"},
    mac_dinh={"hien": "tu", "nhip_tu": 0.07, "bat_dau": 0.15, "nen": "khong", "can": "trai"},
    hop={"anchor": "mc", "x": 0.5, "y": 0.62, "w": 0.88, "h": 0.26}, dong=True, sfx_goi_y=["whoosh mềm", "gõ chữ nhẹ"],
    vi_du={"cau": "Khách không mua sản phẩm, họ mua phiên bản tốt hơn của chính mình.", "tac_gia": "Chị Mai", "mo_ta": "khách quen 3 năm"}))
def trich_dan(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, ftd = _f(p)
    co_nen = str(p.get("nen")) == "the"
    m_chu = B["chu"] if co_nen else c.mau("sang")
    giua = str(p.get("can")) == "giua"
    cau = str(p.get("cau") or "")

    def bo(u):
        m = 30 * u
        pad = 44 * u if co_nen else 10 * u
        rong = W - 2 * m - 2 * pad
        bc = None if co_nen else bong_chu(u)
        co = vua(c, cau, 66 * u, rong, 3, 6, co_min=30 * u, vai=font)
        kd = _kd_chu(c, co, m_chu, font, 700, "giua" if giua else "trai", False, 0.0, 1.15, bc, None)
        im = anh_chu(c, cau, co, m_chu, vai=font, rong=rong, can="giua" if giua else "trai", bong=bc)
        i_q = anh_chu(c, "“", 200 * u, c.mau(p.get("mau") or "nhan"), vai=ftd)
        i_a = anh_chu(c, "— " + str(p.get("tac_gia")), 38 * u, c.mau(p.get("mau") or "nhan") if not co_nen else B["nhan"], vai=font, bong=bc) \
            if p.get("tac_gia") else None
        i_m = anh_chu(c, str(p.get("mo_ta")), 30 * u, tron(m_chu, "#808080", 0.3), vai="than", bong=bc) if p.get("mo_ta") else None
        hq = kich(i_q)[1] * 0.5
        h = hq + kich(im)[1] + (24 * u + kich(i_a)[1] if i_a else 0) + (kich(i_m)[1] + 4 * u if i_m else 0)
        return dict(m=m, pad=pad, rong=rong, co=co, kd=kd, im=im, i_q=i_q, i_a=i_a, i_m=i_m, hq=hq, w=W, h=h + 2 * m + 2 * pad)
    u, L = _bo_cuc("trich-dan", W, H, p, B, c, bo, chi_cao=True)
    y0 = (H - L["h"]) / 2 + L["m"]
    if co_nen:
        the_noi(cv, B, L["m"], y0, W - L["m"], y0 + L["h"] - 2 * L["m"], 30 * u, u)
    x = L["m"] + L["pad"]
    xa = W / 2 if giua else x
    y = y0 + L["pad"]
    kq = e_out(tien(t, 0, 0.35))
    dat(cv, L["i_q"], xa, y - kich(L["i_q"])[1] * 0.18, "tc" if giua else "tl", kq)
    y += L["hq"]
    tus = cau.split()
    nhip = float(p.get("nhip_tu", 0.07)); bd = float(p.get("bat_dau", 0.15))
    het = bd + nhip * len(tus) + 0.3
    if str(p.get("hien")) == "tu" and t < het:
        up = [e_out(tien(t, bd + i * nhip, 0.3)) for i in range(len(tus))]
        im = c.ve_chu(cau, L["kd"], rong_max_px=L["rong"], tach="tu", u_phan=up, tra_skia=True)
    else:
        im = L["im"]
    b = dat(cv, im, xa, y, "tc" if giua else "tl")
    y = b[3] + 24 * u
    ka = e_out(tien(t, het if str(p.get("hien")) == "tu" else 0.3, 0.35))
    if L["i_a"]:
        b = dat(cv, L["i_a"], xa, y, "tc" if giua else "tl", ka)
        y = b[3] + 4 * u
    if L["i_m"]:
        dat(cv, L["i_m"], xa, y, "tc" if giua else "tl", ka)
    return ra(surf)


# ---------------------------------------------------------------- mã giảm giá
@dang_ky(**_the(
    id="mau.ma-giam-gia", ten="Vé mã giảm giá",
    mo_ta="Chiếc vé ưu đãi: cuống màu nhấn ghi mức giảm, phần thân ghi MÃ trong khung nét đứt + điều kiện, khấc tròn hai mép.",
    hop_nghia=["mã giảm giá", "voucher", "coupon", "ưu đãi", "nhập mã", "khuyến mãi"],
    tham_so={"giam": "mức giảm (-30%, 50k…)", "ma": "mã", "nhan_ma": "chữ nhỏ trên mã (NHẬP MÃ)", "mo_ta": "điều kiện (tuỳ)", "han": "hạn dùng (tuỳ)"},
    mac_dinh={"nhan_ma": "Nhập mã"},
    hop={"anchor": "mc", "x": 0.5, "y": 0.62, "w": 0.86, "h": 0.14}, dong=False, sfx_goi_y=["ka-ching", "pop nhẹ", "ting"],
    vi_du={"giam": "-30%", "ma": "TET2026", "mo_ta": "Cho đơn từ 199k", "han": "HSD 31/01"}))
def ma_giam_gia(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, ftd = _f(p)

    def bo(u):
        m = 26 * u
        i_g = anh_chu(c, str(p.get("giam") or ""), 92 * u, B["tren_nhan"], vai=ftd)
        i_n = anh_chu(c, str(p.get("nhan_ma") or ""), 24 * u, B["phu"], vai=font, hoa=True, gian=0.14)
        i_c = anh_chu(c, str(p.get("ma") or ""), 56 * u, B["chu"], vai=ftd, gian=0.06)
        i_d = anh_chu(c, str(p.get("mo_ta")), 28 * u, B["phu"], vai="than") if p.get("mo_ta") else None
        i_h = anh_chu(c, str(p.get("han")), 24 * u, B["nhan"], vai=font) if p.get("han") else None
        ws = kich(i_g)[0] + 72 * u
        wr = max(kich(i_c)[0] + 40 * u, kich(i_n)[0], kich(i_d)[0] if i_d else 0, kich(i_h)[0] if i_h else 0) + 64 * u
        hr = kich(i_n)[1] + 10 * u + kich(i_c)[1] + 24 * u + (kich(i_d)[1] + 10 * u if i_d else 0) + (kich(i_h)[1] + 4 * u if i_h else 0)
        h = max(kich(i_g)[1] + 50 * u, hr + 56 * u)
        return dict(m=m, i_g=i_g, i_n=i_n, i_c=i_c, i_d=i_d, i_h=i_h, ws=ws, wr=wr, hr=hr, hh=h, w=ws + wr + 2 * m, h=h + 2 * m)
    u, L = _bo_cuc("ma-giam-gia", W, H, p, B, c, bo)
    x0, y0 = (W - L["w"]) / 2 + L["m"], (H - L["h"]) / 2 + L["m"]
    x1, y1 = x0 + L["ws"] + L["wr"], y0 + L["hh"]
    xs = x0 + L["ws"]
    r = 26 * u
    kh = 16 * u
    ve = skia.Path(); ve.addRRect(rr(x0, y0, x1, y1, r))
    for cy in (y0, y1):
        o = skia.Path(); o.addCircle(xs, cy, kh); ve = skia.Op(ve, o, skia.PathOp.kDifference_PathOp) or ve
    bong(cv, x0, y0, x1, y1, r, 40 * u, B["bong_al"] + 0.1, dy=10 * u)
    cv.save(); cv.clipPath(ve, True)
    cv.drawRect(skia.Rect.MakeLTRB(x0, y0, x1, y1), p_to(B["the"] if B["tong"] != "kinh" else B["toi"]))
    pf = p_to(B["nhan"])
    pf.setShader(skia.GradientShader.MakeLinear([skia.Point(x0, y0), skia.Point(xs, y1)], [sk(tron(B["nhan"], "#ffffff", 0.12)), sk(B["nhan"])]))
    cv.drawRect(skia.Rect.MakeLTRB(x0, y0, xs, y1), pf)
    cv.restore()
    pd = p_net(B["vien"] if B["tong"] != "toi" else B["mo"], max(1.5, 3 * u), 0.8, False)
    pd.setPathEffect(skia.DashPathEffect.Make([10 * u, 8 * u], 0))
    cv.drawLine(xs, y0 + kh + 8 * u, xs, y1 - kh - 8 * u, pd)
    dat(cv, L["i_g"], x0 + L["ws"] / 2, (y0 + y1) / 2, "mc")
    xc = xs + L["wr"] / 2
    y = (y0 + y1) / 2 - L["hr"] / 2
    b = dat(cv, L["i_n"], xc, y, "tc")
    y = b[3] + 10 * u
    cw, chh = kich(L["i_c"])
    pv = p_net(B["nhan"], max(1.5, 3 * u), 1, False); pv.setPathEffect(skia.DashPathEffect.Make([12 * u, 7 * u], 0))
    hop(cv, xc - cw / 2 - 20 * u, y, xc + cw / 2 + 20 * u, y + chh + 24 * u, 12 * u, voi_alpha(B["nhan"], 0.12))
    cv.drawRRect(rr(xc - cw / 2 - 20 * u, y, xc + cw / 2 + 20 * u, y + chh + 24 * u, 12 * u), pv)
    b = dat(cv, L["i_c"], xc, y + 12 * u, "tc")
    y = b[3] + 22 * u
    if L["i_d"]:
        b = dat(cv, L["i_d"], xc, y, "tc"); y = b[3] + 10 * u
    if L["i_h"]:
        dat(cv, L["i_h"], xc, y, "tc")
    return ra(surf)


# ---------------------------------------------------------------- tiến độ mục tiêu
@dang_ky(**_the(
    id="mau.tien-do-muc-tieu", ten="Tiến độ mục tiêu (đã bán / còn lại)",
    mo_ta="Khan hiếm số lượng / gây quỹ: thanh chạy tới tỉ lệ đã đạt, số đếm lên 'đã bán 873/1.000', % ở cuối thanh.",
    hop_nghia=["đã bán", "còn lại", "sắp hết hàng", "mục tiêu", "chỉ tiêu", "số lượng có hạn"],
    tham_so={"hien_tai": "số đã đạt", "muc_tieu": "số mục tiêu", "nhan": "chữ bên trái (Đã bán)", "don_vi": "đơn vị sau số (suất…)",
             "chay": "giây thanh chạy (1.2)", "phan_tram": "hiện % true/false (true)"},
    mac_dinh={"nhan": "Đã bán", "don_vi": "", "chay": 1.2, "phan_tram": True},
    hop={"anchor": "mc", "x": 0.5, "y": 0.66, "w": 0.86, "h": 0.1}, dong=True, sfx_goi_y=["whoosh lên", "tick đếm số", "ding"],
    vi_du={"hien_tai": 873, "muc_tieu": 1000, "nhan": "Đã bán", "don_vi": " suất"}))
def tien_do_muc_tieu(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font, ftd = _f(p)
    ht, mt = so(p.get("hien_tai")), max(1e-9, so(p.get("muc_tieu"), 1))
    dv = str(p.get("don_vi") or "")

    def bo(u):
        m, pad = 22 * u, 30 * u
        i_n = anh_chu(c, str(p.get("nhan") or ""), 38 * u, B["chu"], vai=font)
        i_s = anh_chu(c, so_vn(mt) + "/" + so_vn(mt) + dv, 40 * u, B["chu"], vai=ftd)
        hb = 26 * u
        hd = max(kich(i_n)[1], kich(i_s)[1])
        return dict(m=m, pad=pad, i_n=i_n, hb=hb, hd=hd, w=W, h=2 * m + 2 * pad + hd + 20 * u + hb)
    u, L = _bo_cuc("tien-do", W, H, p, B, c, bo, chi_cao=True)
    x0, y0 = L["m"], (H - L["h"]) / 2 + L["m"]
    x1, y1 = W - L["m"], y0 + L["h"] - 2 * L["m"]
    the_noi(cv, B, x0, y0, x1, y1, 26 * u, u)
    k = e_io(tien(t, 0.1, float(p.get("chay", 1.2))))
    cy = y0 + L["pad"] + L["hd"] / 2
    dat(cv, L["i_n"], x0 + L["pad"], cy, "ml")
    txt = so_vn(ht * k) + "/" + so_vn(mt) + dv
    dat(cv, anh_chu(c, txt, 40 * u, B["chu"], vai=ftd), x1 - L["pad"], cy, "mr")
    bx0, bx1 = x0 + L["pad"], x1 - L["pad"]
    by = y1 - L["pad"] - L["hb"]
    hb = L["hb"]
    hop(cv, bx0, by, bx1, by + hb, hb / 2, B["vien"])
    tl = kep(ht / mt)
    xe = bx0 + (bx1 - bx0) * tl * k
    if xe - bx0 > 2:
        pf = p_to(B["nhan"])
        pf.setShader(skia.GradientShader.MakeLinear([skia.Point(bx0, 0), skia.Point(bx1, 0)], [sk(tron(B["nhan"], B["nhan2"], 0.45)), sk(B["nhan"])]))
        cv.drawRRect(rr(bx0, by, max(xe, bx0 + hb), by + hb, hb / 2), pf)
        cv.drawRRect(rr(bx0 + hb * 0.3, by + hb * 0.18, max(xe, bx0 + hb) - hb * 0.3, by + hb * 0.42, hb * 0.12), p_to("#ffffff", 0.28))
        if p.get("phan_tram", True) and xe - bx0 > 90 * u:
            dat(cv, anh_chu(c, so_vn(tl * k * 100, 0) + "%", hb * 0.66, B["tren_nhan"], vai=ftd), xe - 14 * u, by + hb / 2, "mr")
    return ra(surf)
