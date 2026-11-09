# -*- coding: utf-8 -*-
"""MẪU GIAO DIỆN GIẢ LẬP (nhóm "giao_dien") — dựng lại thao tác người nói kể: khung chat với trợ lý AI, tin nhắn 2 chiều,
ô tìm kiếm gõ chữ + gợi ý, con trỏ bấm, trang cá nhân, thông báo điện thoại. Không logo/nhãn hiệu thật của nền tảng nào.
Kích thước theo hộp (u = cạnh hộp / thang thiết kế × ti_le_chu); màu theo vai màu video; nội dung diễn theo t (gõ chữ,
"đang soạn…", bong bóng nối nhau, cuộn khi đầy, con trỏ bay/bấm). Vào/ra tổng thể do engine lo."""
import math
import skia
from dung.mau import dang_ky
from dung.mau.canh import (kep, e_out, e_io, e_back, tien, lich, muc, so_vn, tron, voi_alpha, sk, chu_tren,
                           bang_mau, anh_chu, vua, kich, dat, p_to, p_net, rr, hop, bong, the_noi, duong_gap,
                           be_mat, ra, ve_nen, anh, ve_anh_phu, SAMP_LIN)

THAM_SO_CHUNG = {
    "tong_mau": "toi | sang | kinh — tông giao diện (toi)", "mau": "màu nhấn (vai nhan|nhan2|sang|toi hoặc #hex)", "mau2": "màu nhấn phụ",
    "font": "vai/id font giao diện (than; đậm dùng nhan)", "ti_le_chu": "nhân cỡ chữ/khối (1.0)",
    "mau_cham": "3 màu chấm cửa sổ [vai|#hex ×3] (mặc định [nhan, nhan2, phụ của tông])", "mau_online": "màu chấm 'đang hoạt động' (vai|#hex, mặc định nhan)",
}


def _cham_cua_so(c, p, B):
    """1.2.21: màu 3 chấm cửa sổ là tham số mau_cham — không còn #FF5F57/#FEBC2E/#28C840 hàn trong mẫu"""
    m = p.get("mau_cham")
    if isinstance(m, (list, tuple)) and len(m) >= 3:
        return [c.mau(x) for x in m[:3]]
    return [B["nhan"], B["nhan2"], B["phu"]]


def _the(**kw):
    ts = dict(THAM_SO_CHUNG); ts.update(kw.pop("tham_so", {}))
    md = {"tong_mau": "toi", "ti_le_chu": 1.0}; md.update(kw.pop("mac_dinh", {}))
    return dict(nhom="giao_dien", tham_so=ts, mac_dinh=md, **kw)


def _rr_goc(x0, y0, x1, y1, r_tl, r_tr, r_br, r_bl):
    o = skia.RRect()
    o.setRectRadii(skia.Rect.MakeLTRB(x0, y0, x1, y1), [skia.Point(r_tl, r_tl), skia.Point(r_tr, r_tr), skia.Point(r_br, r_br), skia.Point(r_bl, r_bl)])
    return o


def _cham_go(cv, x, y, u, mau, t):
    """3 chấm 'đang soạn…' nhún lần lượt"""
    for k in range(3):
        nh = max(0.0, math.sin(t * 7.5 - k * 0.9))
        cv.drawCircle(x + k * 22 * u, y - nh * 7 * u, 7 * u, p_to(mau, 0.45 + 0.55 * nh))


def _ben_phai(ai):
    return str(ai or "").strip().lower() in ("toi", "tôi", "minh", "mình", "me", "user", "nguoi_dung", "phai", "b")


def _cao_hoi_thoai(c, p, B, rong_vung, u, avatar_ai):
    """chiều cao cả chuỗi khi mọi tin đã hiện đủ — để khung co theo nội dung (tin ít thì khung gọn)"""
    font = p.get("font") or "than"
    co = 44 * u * float(p.get("co_chu", 1.0))
    av = 46 * u if avatar_ai else 0
    rong = rong_vung * 0.74 - 2 * 24 * u - av
    h = 0.0
    for x in (p.get("dong") or [])[:10]:
        d = muc(x, ("ai", "chu", "t"))
        h += kich(anh_chu(c, str(d.get("chu") or " "), co, "#ffffff", vai=font, dam=500, rong=rong))[1] + 2 * 16 * u + 14 * u
    return h + 10 * u


def _hoi_thoai(cv, c, p, B, t, dur, x0, y0, x1, y1, u, go_chu, avatar_ai):
    """vẽ chuỗi bong bóng trong vùng (x0,y0,x1,y1), tự cuộn khi đầy. go_chu: bên trái hiện kiểu gõ từng ký tự."""
    font = p.get("font") or "than"
    ds = [muc(x, ("ai", "chu", "t")) for x in (p.get("dong") or [])][:10]
    ts = lich(len(ds), dur, p.get("nhip", 1.0), p.get("bat_dau", 0.3), [d.get("t") for d in ds], cuoi=0.8)
    soan = float(p.get("soan", 0.55))
    toc = float(p.get("toc_go", 45))
    co = 44 * u * float(p.get("co_chu", 1.0))
    pad_x, pad_y = 24 * u, 16 * u
    av = 46 * u if avatar_ai else 0
    rong = (x1 - x0) * 0.74 - 2 * pad_x - av
    m_trai, c_trai = (B["the2"], B["chu"]) if B["tong"] != "sang" else (tron("#ffffff", B["toi"], 0.07), B["chu"])
    m_phai, c_phai = B["nhan"], B["tren_nhan"]
    bb = []
    for i, d in enumerate(ds):
        ti = ts[i]
        if t < ti:
            break
        phai = _ben_phai(d.get("ai"))
        chu = str(d.get("chu") or "")
        dang_soan = (not phai) and soan > 0 and t < ti + soan
        if dang_soan:
            w, h = 3 * 22 * u + 2 * pad_x, co * 1.2 + 2 * pad_y
            im = None
        else:
            n = len(chu) if (phai or not go_chu) else int(kep((t - ti - soan) * toc, 0, len(chu)))
            im = anh_chu(c, chu[:n] if n else " ", co, c_phai if phai else c_trai, vai=font, dam=500, rong=rong)
            w, h = kich(im)[0] + 2 * pad_x, kich(im)[1] + 2 * pad_y
        k = e_out(tien(t, ti, 0.28))
        bb.append(dict(i=i, phai=phai, im=im, w=w, h=h, k=k, soan=dang_soan, chu=chu))
    khe = 14 * u
    tong = sum((b["h"] + khe) * b["k"] for b in bb)
    cao = y1 - y0
    lech = max(0.0, tong - cao + 10 * u)
    cv.save(); cv.clipRect(skia.Rect.MakeLTRB(x0 - 4, y0, x1 + 4, y1))
    y = y0 - lech
    for j, b in enumerate(bb):
        k = b["k"]
        if y + b["h"] > y0 - 50 and y < y1:
            tiep = j + 1 < len(bb) and bb[j + 1]["phai"] == b["phai"]
            r = 24 * u
            if b["phai"]:
                bx1 = x1 - 4 * u; bx0 = bx1 - b["w"]
                hinh = _rr_goc(bx0, y, bx1, y + b["h"], r, r, r if tiep else 6 * u, r)
                mau = m_phai
            else:
                bx0 = x0 + 4 * u + av; bx1 = bx0 + b["w"]
                hinh = _rr_goc(bx0, y, bx1, y + b["h"], r, r, r, r if tiep else 6 * u)
                mau = m_trai
                if avatar_ai and not tiep:
                    ax, ay = x0 + 4 * u + av / 2 - 4 * u, y + b["h"] - av / 2 + 6 * u
                    cv.drawCircle(ax, ay, av / 2 - 4 * u, p_to(B["nhan2"], k))
                    nhan_ai = p.get("nhan_ai")                       # 1.2.21: chữ trong avatar là tham số (bắt buộc với mẫu chat AI) — hết "AI" hàn chết
                    if nhan_ai is None:
                        raise c.thieu("lop.noi_dung.tham_so.nhan_ai", "chữ trong avatar trợ lý (vd \"AI\"; \"\" = không chữ)")
                    if str(nhan_ai):
                        dat(cv, anh_chu(c, str(nhan_ai), av * 0.34, B["tren_nhan2"], vai="nhan"), ax, ay, "mc", k)
            s = 0.9 + 0.1 * k
            cx = bx1 if b["phai"] else bx0
            cv.save(); cv.translate(cx, y + b["h"]); cv.scale(s, s); cv.translate(-cx, -(y + b["h"]))
            pb = p_to(mau, k)
            cv.drawRRect(hinh, pb)
            if b["soan"]:
                _cham_go(cv, bx0 + pad_x + 7 * u, y + b["h"] / 2, u, B["phu"] if not b["phai"] else c_phai, t)
            elif b["im"] is not None:
                dat(cv, b["im"], bx0 + pad_x, y + pad_y, "tl", k)
            cv.restore()
            b["y1"] = y + b["h"]; b["bx1"] = bx1
        y += (b["h"] + khe) * k
    if p.get("da_xem") and bb and bb[-1]["phai"] and "y1" in bb[-1]:
        b = bb[-1]
        ka = e_out(tien(t, ts[b["i"]] + 0.8, 0.3))
        if ka > 0 and b["y1"] + 6 * u < y1:
            if not isinstance(p.get("da_xem"), str):           # 1.2.21: chuỗi "Đã xem" không còn hàn trong máy — AI ghi da_xem là chuỗi
                raise c.thieu("lop.noi_dung.tham_so.da_xem", "chữ dưới tin cuối (chuỗi; \"\" = bỏ)")
            dat(cv, anh_chu(c, str(p.get("da_xem")), 22 * u, B["phu"], vai=font), b["bx1"], b["y1"] + 6 * u, "tr", ka)
    cv.restore()


# ---------------------------------------------------------------- khung chat AI
@dang_ky(**_the(
    id="mau.khung-chat-ai", ten="Khung chat với trợ lý AI",
    mo_ta="Dựng lại cảnh nhắn với trợ lý AI: cửa sổ app, câu hỏi bật lên, AI 'đang soạn…' rồi gõ câu trả lời từng chữ, tự cuộn.",
    hop_nghia=["hỏi AI", "chatgpt", "nhắn tin", "trợ lý ảo", "prompt", "câu lệnh", "hỏi máy"],
    tham_so={"dong": "list [ai|toi, chữ, giây?] (≤ 10) — toi = bên phải", "ten_app": "tên trên thanh cửa sổ (Trợ lý AI)",
             "nhip": "giây giữa 2 tin khi không ghi giây (1.0)", "bat_dau": "giây tin đầu (0.3)", "soan": "giây 'đang soạn' trước tin AI (0.55)",
             "toc_go": "ký tự/giây AI gõ (45)", "co_chu": "nhân cỡ chữ tin (1.0)", "o_nhap": "chữ mờ ô nhập (Nhắn cho trợ lý…)",
             "nhan_ai": "chữ trong avatar trợ lý (vd \"AI\"; \"\" = không) — BẮT BUỘC", "kieu_nen": "trong | noi | toan — nền dưới cửa sổ (trong)"},
    mac_dinh={"ten_app": "Trợ lý AI", "nhip": 1.0, "bat_dau": 0.3, "soan": 0.55, "toc_go": 45, "o_nhap": "Nhắn cho trợ lý…", "kieu_nen": "trong"},
    hop={"anchor": "mc", "x": 0.5, "y": 0.45, "w": 0.9, "h": 0.46}, dong=True, sfx_goi_y=["gõ phím", "pop tin nhắn", "ting nhẹ"],
    vi_du={"dong": [["toi", "Viết giúp mình 3 tiêu đề video bán áo khoác"], ["ai", "1. Áo khoác mặc cả mùa đông không lo lạnh\n2. Mặc lên là ấm, nhìn là mê"]],
           "nhip": 0.9, "toc_go": 60, "nhan_ai": "AI"}))
def khung_chat_ai(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    duc = ve_nen(cv, c, p, B, t, dur, W, H)
    u = min(W, H * 1.25) / 1000.0 * float(p.get("ti_le_chu", 1.0))
    m = 22 * u
    th, nh = 78 * u, 84 * u
    x0, x1 = m, W - m
    can = th + 22 * u + _cao_hoi_thoai(c, p, B, x1 - x0 - 52 * u, u, True) + nh + 30 * u + 24 * u
    hh = kep(can, min(H - 2 * m, 420 * u), H - 2 * m)
    y0 = (H - hh) / 2; y1 = y0 + hh
    the_noi(cv, B, x0, y0, x1, y1, 34 * u, u)
    cv.save(); cv.clipRRect(rr(x0, y0, x1, y1, 34 * u), True)
    cv.drawRect(skia.Rect.MakeLTRB(x0, y0, x1, y0 + th), p_to(tron(B["the"], B["nhan"], 0.08)))
    cv.restore()
    cv.drawLine(x0, y0 + th, x1, y0 + th, p_net(B["vien"], max(1, 2 * u), 1, False))
    for k, mau in enumerate(_cham_cua_so(c, p, B)):
        cv.drawCircle(x0 + (36 + 30 * k) * u, y0 + th / 2, 9 * u, p_to(mau))
    dat(cv, anh_chu(c, str(p.get("ten_app") or ""), 30 * u, B["chu"], vai="nhan"), (x0 + x1) / 2, y0 + th / 2, "mc")
    hop(cv, x0 + 24 * u, y1 - nh - 20 * u + 10 * u, x1 - 24 * u, y1 - 24 * u, (nh - 14 * u) / 2, B["the2"], 1, B["vien"], 2 * u)
    yc = y1 - 24 * u - (nh - 14 * u) / 2
    dat(cv, anh_chu(c, str(p.get("o_nhap") or ""), 28 * u, B["mo"], vai=p.get("font") or "than"), x0 + 56 * u, yc, "ml")
    r = (nh - 14 * u) / 2 - 8 * u
    cv.drawCircle(x1 - 24 * u - r - 8 * u, yc, r, p_to(B["nhan"]))
    ax = x1 - 24 * u - r - 8 * u
    cv.drawPath(duong_gap([(ax, yc + r * 0.45), (ax, yc - r * 0.45)]), p_net(B["tren_nhan"], 4 * u))
    cv.drawPath(duong_gap([(ax - r * 0.38, yc - r * 0.08), (ax, yc - r * 0.48), (ax + r * 0.38, yc - r * 0.08)]), p_net(B["tren_nhan"], 4 * u))
    _hoi_thoai(cv, c, p, B, t, dur, x0 + 26 * u, y0 + th + 22 * u, x1 - 26 * u, y1 - nh - 30 * u, u, True, True)
    return ra(surf, duc)


# ---------------------------------------------------------------- tin nhắn 2 chiều
@dang_ky(**_the(
    id="mau.tin-nhan", ten="Tin nhắn 2 chiều (điện thoại)",
    mo_ta="Cuộc nhắn tin khách ↔ shop: đầu trang tên + 'đang hoạt động', bong bóng hai bên nối nhau, '…' trước tin bên kia, 'Đã xem'.",
    hop_nghia=["tin nhắn", "khách nhắn", "inbox", "nhắn tin", "hội thoại", "khách hỏi", "chốt đơn"],
    tham_so={"dong": "list [ho|toi, chữ, giây?] (≤ 10) — toi = bên phải", "ten": "tên người bên kia", "trang_thai": "dòng dưới tên (Đang hoạt động)",
             "anh": "ảnh đại diện (id kho/đường dẫn; tuỳ)", "khung": "có khung điện thoại + đầu trang true/false (true)",
             "nhip": "giây giữa 2 tin (0.9)", "bat_dau": "giây tin đầu (0.3)", "soan": "giây '…' trước tin bên kia (0.5)",
             "da_xem": "chữ dưới tin cuối của mình (chuỗi AI ghi, vd \"Đã xem\"; \"\" = bỏ) — BẮT BUỘC", "co_chu": "nhân cỡ chữ tin (1.0)"},
    mac_dinh={"ten": "Khách hàng", "trang_thai": "Đang hoạt động", "khung": True, "nhip": 0.9, "bat_dau": 0.3, "soan": 0.5},
    hop={"anchor": "mc", "x": 0.5, "y": 0.45, "w": 0.86, "h": 0.48}, dong=True, sfx_goi_y=["pop tin nhắn", "ting nhẹ", "gõ phím"],
    vi_du={"ten": "Chị Lan", "dong": [["ho", "Shop ơi váy này còn size M không?"], ["toi", "Dạ còn ạ, chị lấy màu nào ạ?"],
           ["ho", "Màu kem nha, ship luôn giúp chị"], ["toi", "Dạ em lên đơn ngay ạ"]], "nhip": 0.55, "soan": 0.3, "da_xem": "Đã xem"}))
def tin_nhan(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    u = min(W, H * 1.2) / 1000.0 * float(p.get("ti_le_chu", 1.0))
    m = 22 * u
    x0, y0, x1, y1 = m, m, W - m, H - m
    th, nh = 112 * u, 76 * u
    if p.get("khung", True):
        can = th + 20 * u + _cao_hoi_thoai(c, p, B, x1 - x0 - 52 * u, u, False) + 40 * u + nh + 32 * u
        hh = kep(can, min(H - 2 * m, 480 * u), H - 2 * m)
        y0 = (H - hh) / 2; y1 = y0 + hh
    if not p.get("khung", True):
        _hoi_thoai(cv, c, p, B, t, dur, x0, y0, x1, y1, u, False, False)
        return ra(surf)
    the_noi(cv, B, x0, y0, x1, y1, 44 * u, u)
    cv.drawLine(x0, y0 + th, x1, y0 + th, p_net(B["vien"], max(1, 2 * u), 1, False))
    cy = y0 + th / 2
    cv.drawPath(duong_gap([(x0 + 48 * u, cy - 16 * u), (x0 + 32 * u, cy), (x0 + 48 * u, cy + 16 * u)]), p_net(B["nhan"], 5 * u))
    ra_ = 34 * u
    ax = x0 + 96 * u
    img = anh(c, p.get("anh"), 256) if p.get("anh") else None
    if img is not None:
        ve_anh_phu(cv, img, ax - ra_, cy - ra_, ax + ra_, cy + ra_, r=ra_)
    else:
        pg = p_to(B["nhan2"])
        pg.setShader(skia.GradientShader.MakeLinear([skia.Point(ax - ra_, cy - ra_), skia.Point(ax + ra_, cy + ra_)], [sk(B["nhan2"]), sk(B["nhan"])]))
        cv.drawCircle(ax, cy, ra_, pg)
        ten = str(p.get("ten") or "?").strip()
        dat(cv, anh_chu(c, (ten.split()[-1][:1] if ten else "?").upper(), ra_ * 0.95, "#ffffff", vai="nhan"), ax, cy, "mc")
    cv.drawCircle(ax + ra_ * 0.72, cy + ra_ * 0.72, 9 * u, p_to(B["the"]))
    cv.drawCircle(ax + ra_ * 0.72, cy + ra_ * 0.72, 6.5 * u, p_to(c.mau(p.get("mau_online") or "nhan")))   # 1.2.21: chấm online = tham số (hết #2BD46B)
    b = dat(cv, anh_chu(c, str(p.get("ten") or ""), 32 * u, B["chu"], vai="nhan"), ax + ra_ + 20 * u, cy - 2 * u, "bl")
    if p.get("trang_thai"):
        dat(cv, anh_chu(c, str(p.get("trang_thai")), 24 * u, B["phu"], vai=p.get("font") or "than"), b[0], cy + 4 * u, "tl")
    hop(cv, x0 + 24 * u, y1 - nh - 18 * u, x1 - 24 * u, y1 - 18 * u, nh / 2, B["the2"])
    dat(cv, anh_chu(c, "Aa", 28 * u, B["mo"], vai=p.get("font") or "than"), x0 + 56 * u, y1 - 18 * u - nh / 2, "ml")
    cv.drawCircle(x1 - 24 * u - nh / 2, y1 - 18 * u - nh / 2, nh * 0.3, p_to(B["nhan"]))
    _hoi_thoai(cv, c, p, B, t, dur, x0 + 26 * u, y0 + th + 20 * u, x1 - 26 * u, y1 - nh - 32 * u, u, False, False)
    return ra(surf)


# ---------------------------------------------------------------- ô tìm kiếm gõ chữ
def _kinh_lup(cv, x, y, s, mau, w):
    cv.drawCircle(x - s * 0.12, y - s * 0.12, s * 0.32, p_net(mau, w))
    cv.drawLine(x + s * 0.12, y + s * 0.12, x + s * 0.4, y + s * 0.4, p_net(mau, w))


@dang_ky(**_the(
    id="mau.o-tim-kiem", ten="Ô tìm kiếm gõ chữ + gợi ý",
    mo_ta="Dựng lại thao tác tìm kiếm: ô tìm kiếm tự gõ từ khoá, gõ xong thả danh sách gợi ý, dòng đầu sáng lên như sắp bấm.",
    hop_nghia=["tìm kiếm", "search", "gõ từ khoá", "tra google", "từ khoá", "người ta tìm"],
    tham_so={"tu_khoa": "chữ được gõ", "goi_y": "list dòng gợi ý (≤ 5; tuỳ)", "o_trong": "chữ mờ khi ô trống (Tìm kiếm)",
             "bat_dau": "giây bắt đầu gõ (0.3)", "toc_go": "ký tự/giây (12)", "chon": "chỉ số gợi ý sáng lên (0; -1 = không)"},
    mac_dinh={"o_trong": "Tìm kiếm", "bat_dau": 0.3, "toc_go": 12, "chon": 0},
    hop={"anchor": "mc", "x": 0.5, "y": 0.36, "w": 0.9, "h": 0.32}, dong=True, sfx_goi_y=["gõ phím", "click", "whoosh nhẹ"],
    vi_du={"tu_khoa": "cách quay video bán hàng", "goi_y": ["cách quay video bán hàng bằng điện thoại", "cách quay video bán hàng tiktok",
                                                       "cách quay video bán hàng không lộ mặt"], "toc_go": 16}))
def o_tim_kiem(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font = p.get("font") or "than"
    gy = [str(x) for x in (p.get("goi_y") or [])][:5]
    u = min(W / 1000.0, H / (150 + 92 * len(gy) + 60) / 1.0) * float(p.get("ti_le_chu", 1.0))
    m = 20 * u
    x0, x1 = m, W - m
    oh = 104 * u
    tk = str(p.get("tu_khoa") or "")
    bd, toc = float(p.get("bat_dau", 0.3)), max(1.0, float(p.get("toc_go", 12)))
    n = int(kep((t - bd) * toc, 0, len(tk))) if t > bd else 0
    xong = bd + len(tk) / toc
    kg = e_out(tien(t, xong + 0.15, 0.35)) if gy else 0.0
    dong_h = 84 * u
    hg = (len(gy) * dong_h + 24 * u) * kg
    y0 = (H - (oh + (len(gy) * dong_h + 24 * u if gy else 0))) / 2
    y0 = max(m, y0)
    nen, chu = ("#ffffff", B["toi"]) if B["tong"] != "kinh" else (voi_alpha("#ffffff", 0.18), B["sang"])
    if B["tong"] == "sang":
        nen = "#ffffff"
    r = oh / 2
    bong(cv, x0, y0, x1, y0 + oh + hg, r if hg < 2 else 34 * u, 40 * u, 0.45, dy=12 * u)
    cv.drawRRect(rr(x0, y0, x1, y0 + oh + hg, r if hg < r else 34 * u), p_to(nen))
    if kg <= 0:
        cv.drawRRect(rr(x0 + 1.5 * u, y0 + 1.5 * u, x1 - 1.5 * u, y0 + oh - 1.5 * u, r), p_net(B["nhan"], 3 * u, 1, False))
    _kinh_lup(cv, x0 + 56 * u, y0 + oh / 2, 46 * u, tron(chu, nen, 0.35), 5 * u)
    rong = x1 - x0 - 200 * u
    co = vua(c, tk or str(p.get("o_trong")), 40 * u, rong, 1, 1, co_min=24 * u, vai=font)
    if n:
        bb = dat(cv, anh_chu(c, tk[:n], co, chu, vai=font, dam=500), x0 + 96 * u, y0 + oh / 2, "ml")
        xc = bb[2] + 4 * u
    else:
        dat(cv, anh_chu(c, str(p.get("o_trong") or ""), co, tron(chu, nen, 0.55), vai=font), x0 + 96 * u, y0 + oh / 2, "ml")
        xc = x0 + 94 * u
    if (n < len(tk) or int(t * 2.2) % 2 == 0) and kg < 1:
        cv.drawRect(skia.Rect.MakeLTRB(xc, y0 + oh / 2 - co * 0.6, xc + max(2, 3 * u), y0 + oh / 2 + co * 0.6), p_to(B["nhan"]))
    mx = x1 - 52 * u
    cv.drawCircle(mx, y0 + oh / 2, 24 * u, p_to(voi_alpha(B["nhan"], 0.14)))
    cv.drawRRect(rr(mx - 7 * u, y0 + oh / 2 - 15 * u, mx + 7 * u, y0 + oh / 2 + 5 * u, 7 * u), p_to(B["nhan"]))
    cv.drawLine(mx, y0 + oh / 2 + 9 * u, mx, y0 + oh / 2 + 15 * u, p_net(B["nhan"], 3 * u))
    if kg > 0:
        cv.drawLine(x0 + 30 * u, y0 + oh, x1 - 30 * u, y0 + oh, p_net(tron(chu, nen, 0.88), max(1, 2 * u), kg, False))
        cv.save(); cv.clipRect(skia.Rect.MakeLTRB(x0, y0 + oh, x1, y0 + oh + hg))
        chon = int(p.get("chon", 0))
        for i, g in enumerate(gy):
            yy = y0 + oh + 12 * u + i * dong_h
            ki = e_out(tien(t, xong + 0.2 + i * 0.08, 0.3))
            if i == chon:
                kh = e_out(tien(t, xong + 0.2 + len(gy) * 0.08 + 0.35, 0.3))
                if kh > 0:
                    cv.drawRRect(rr(x0 + 12 * u, yy + 4 * u, x1 - 12 * u, yy + dong_h - 4 * u, 18 * u), p_to(voi_alpha(B["nhan"], 0.13 * kh)))
            _kinh_lup(cv, x0 + 56 * u, yy + dong_h / 2, 34 * u, tron(chu, nen, 0.55), 4 * u)
            cg = vua(c, g, 34 * u, rong, 1, 1, co_min=20 * u, vai=font)
            im_g = anh_chu(c, g, cg, chu, vai=font)
            cv.save(); cv.clipRect(skia.Rect.MakeLTRB(x0, yy, x1 - 40 * u, yy + dong_h))
            dat(cv, im_g, x0 + 96 * u, yy + dong_h / 2, "ml", ki)
            cv.restore()
        cv.restore()
    return ra(surf)


# ---------------------------------------------------------------- con trỏ bấm
def _path_tro(x, y, s, kieu):
    pa = skia.Path()
    if kieu == "tay":
        k = s / 64.0
        pa.addRRect(rr(x + 18 * k, y, x + 31 * k, y + 40 * k, 6.5 * k))
        pa.addRRect(rr(x + 6 * k, y + 28 * k, x + 50 * k, y + 70 * k, 15 * k))
        for dx in (31, 41):
            pa.addRRect(rr(x + dx * k - 1, y + 22 * k, x + (dx + 11) * k, y + 46 * k, 5.5 * k))
        return skia.Op(pa, skia.Path(), skia.PathOp.kUnion_PathOp) or pa
    k = s / 64.0
    pts = [(0, 0), (0, 50), (12, 39), (21, 59), (31, 55), (22, 36), (38, 36)]
    pa.moveTo(x + pts[0][0] * k, y + pts[0][1] * k)
    for a, b in pts[1:]:
        pa.lineTo(x + a * k, y + b * k)
    pa.close()
    return pa


@dang_ky(**_the(
    id="mau.con-tro", ten="Con trỏ bay tới và bấm",
    mo_ta="Chỉ cách làm: con trỏ (mũi tên / bàn tay) bay qua các điểm trên màn hình rồi bấm — gợn tròn lan ra chỗ bấm.",
    hop_nghia=["bấm vào", "nhấn nút", "click", "link bio", "chọn", "hướng dẫn thao tác"],
    tham_so={"diem": "list [giây, x 0..1, y 0..1, \"bam\"?] — toạ độ trong hộp (mặc định hộp = cả khung)", "kieu": "mui_ten | tay (mui_ten)",
             "co": "cỡ con trỏ, phần cạnh ngắn hộp (0.065)", "mau": "màu gợn bấm (vai/#hex; mặc định sang)"},
    mac_dinh={"kieu": "mui_ten", "co": 0.065},
    toan_khung=True, dong=True, sfx_goi_y=["click chuột", "tap", "pop nhẹ"],
    vi_du={"diem": [[0.2, 0.3, 0.75], [1.2, 0.62, 0.55, "bam"], [2.2, 0.5, 0.7, "bam"]], "kieu": "tay"}))
def con_tro(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    ds = sorted([(float(d[0]), float(d[1]), float(d[2]), "bam" in [str(x) for x in d[3:]]) for d in (p.get("diem") or []) if len(d) >= 3])
    if not ds:
        return ra(surf)
    s = float(p.get("co", 0.065)) * min(W, H)
    if t <= ds[0][0]:
        k = e_out(kep(t / max(0.01, ds[0][0])))
        x, y = ds[0][1], ds[0][2] + 0.05 * (1 - k)
    elif t >= ds[-1][0]:
        x, y = ds[-1][1], ds[-1][2]
    else:
        for a, b in zip(ds, ds[1:]):
            if a[0] <= t < b[0]:
                k = e_io(kep((t - a[0]) / max(0.01, (b[0] - a[0]) * 0.75)))
                x, y = a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k
                break
    mau = c.mau(p.get("mau") or "sang")
    sc = 1.0
    for ti, xb, yb, bam in ds:
        if bam and 0 <= t - ti < 0.7:
            v = (t - ti) / 0.7
            r = s * (0.25 + 1.1 * e_out(v))
            cv.drawCircle(xb * W, yb * H, r, p_net(mau, max(2, s * 0.07), 0.9 * (1 - v)))
            cv.drawCircle(xb * W, yb * H, r * 0.6, p_to(mau, 0.25 * (1 - v)))
            if v < 0.2:
                sc = 0.84
    kieu = str(p.get("kieu") or "mui_ten")
    px, py = x * W, y * H
    ox = -s * 0.38 if kieu == "tay" else 0
    pa = _path_tro(px + ox, py, s * sc, kieu)
    cv.save(); cv.translate(2, s * 0.06)
    for i in range(3):
        cv.save(); cv.translate(0, i * 1.0); cv.drawPath(pa, p_to("#000000", 0.08)); cv.restore()
    cv.restore()
    cv.drawPath(pa, p_to("#ffffff"))
    pv = p_net("#111111", max(1.5, s * 0.045), 1, False); pv.setStrokeJoin(skia.Paint.kRound_Join)
    cv.drawPath(pa, pv)
    xs_, ys_ = [px - s, px + s * 1.4], [py - s * 0.2, py + s * 1.4]
    for ti, xb, yb, bam in ds:
        if bam and 0 <= t - ti < 0.7:
            xs_ += [xb * W - s * 1.5, xb * W + s * 1.5]; ys_ += [yb * H - s * 1.5, yb * H + s * 1.5]
    return ra(surf, vung=(min(xs_), min(ys_), max(xs_), max(ys_)))


# ---------------------------------------------------------------- trang cá nhân
@dang_ky(**_the(
    id="mau.trang-ca-nhan", ten="Trang cá nhân mạng xã hội (giả lập)",
    mo_ta="CTA 'ghé trang của tôi': thẻ trang cá nhân (ảnh đại diện, số liệu, bio, link, nút) — nút Theo dõi tự bấm đổi trạng thái.",
    hop_nghia=["theo dõi", "follow", "trang cá nhân", "link bio", "ghé kênh", "kênh của tôi"],
    tham_so={"ten": "@tên trang", "ten_that": "tên hiển thị", "so": "[bài, người theo dõi, đang theo dõi] (chuỗi — số THẬT)",
             "nhan_so": "3 chữ dưới số (bài viết, người theo dõi, đang theo dõi)", "bio": "list dòng bio (≤ 4)", "link": "dòng link (tuỳ)",
             "anh": "ảnh đại diện (id kho / đường dẫn; tuỳ)", "nut": "chữ nút chính (Theo dõi)", "nut_da": "chữ nút sau khi bấm (Đang theo dõi)",
             "nut2": "chữ nút phụ bên cạnh (vd \"Nhắn tin\"; \"\" = trống) — BẮT BUỘC", "bam": "giây nút tự bấm (tuỳ; bỏ trống = không bấm)"},
    mac_dinh={"nut": "Theo dõi", "nut_da": "Đang theo dõi", "nhan_so": ["bài viết", "người theo dõi", "đang theo dõi"]},
    hop={"anchor": "mc", "x": 0.5, "y": 0.62, "w": 0.8, "h": 0.3}, dong=True, sfx_goi_y=["click", "pop nhẹ", "ting"],
    vi_du={"ten": "@studio.dung.video", "ten_that": "Studio Dựng Video", "so": ["128", "45,2K", "36"],
           "bio": ["Dựng video bán hàng trong 10 phút", "Mẹo quay – dựng mỗi ngày"], "link": "studiodungvideo.vn", "bam": 1.6, "nut2": "Nhắn tin"}))
def trang_ca_nhan(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font = p.get("font") or "than"
    bio = [str(b) for b in (p.get("bio") or [])][:4]
    u = min(W / 700.0, H / (330 + 34 * len(bio) + (34 if p.get("link") else 0) + 60)) * float(p.get("ti_le_chu", 1.0))
    pad = 30 * u
    h = 2 * pad + 40 * u + 130 * u + 24 * u + 40 * u + 34 * u * len(bio) + (34 * u if p.get("link") else 0) + 20 * u + 66 * u
    w = min(W - 30 * u, 700 * u)
    x0, y0 = (W - w) / 2, (H - h) / 2
    x1, y1 = x0 + w, y0 + h
    the_noi(cv, B, x0, y0, x1, y1, 30 * u, u)
    y = y0 + pad
    dat(cv, anh_chu(c, str(p.get("ten") or ""), 28 * u, B["chu"], vai="nhan"), (x0 + x1) / 2, y + 16 * u, "mc")
    cv.drawPath(duong_gap([(x0 + pad + 12 * u, y + 4 * u), (x0 + pad, y + 16 * u), (x0 + pad + 12 * u, y + 28 * u)]), p_net(B["chu"], 4 * u))
    y += 40 * u
    ra_ = 62 * u
    ax, ay = x0 + pad + ra_ + 4 * u, y + 65 * u
    cv.drawCircle(ax, ay, ra_ + 6 * u, p_net(B["nhan"], 4 * u))
    img = anh(c, p.get("anh"), 300) if p.get("anh") else None
    if img is not None:
        ve_anh_phu(cv, img, ax - ra_, ay - ra_, ax + ra_, ay + ra_, r=ra_)
    else:
        pg = p_to(B["nhan"])
        pg.setShader(skia.GradientShader.MakeLinear([skia.Point(ax - ra_, ay - ra_), skia.Point(ax + ra_, ay + ra_)], [sk(B["nhan"]), sk(B["nhan2"])]))
        cv.drawCircle(ax, ay, ra_, pg)
        tt = str(p.get("ten_that") or p.get("ten") or "?").strip("@ ")
        dat(cv, anh_chu(c, (tt[:1] or "?").upper(), ra_ * 0.9, "#ffffff", vai="nhan"), ax, ay, "mc")
    so3 = (list(p.get("so") or []) + ["", "", ""])[:3]
    nh3 = (list(p.get("nhan_so") or []) + ["", "", ""])[:3]
    sx0 = ax + ra_ + 26 * u
    w3 = (x1 - pad - sx0) / 3
    for i in range(3):
        cx = sx0 + w3 * (i + 0.5)
        dat(cv, anh_chu(c, str(so3[i]), 34 * u, B["chu"], vai="nhan"), cx, ay - 4 * u, "bc")
        cn = vua(c, str(nh3[i]), 21 * u, w3 - 6 * u, 1, 2, co_min=15 * u, vai=font)
        dat(cv, anh_chu(c, str(nh3[i]), cn, B["phu"], vai=font, rong=w3 - 6 * u, can="giua"), cx, ay + 6 * u, "tc")
    y = ay + ra_ + 24 * u
    b = dat(cv, anh_chu(c, str(p.get("ten_that") or ""), 32 * u, B["chu"], vai="nhan"), x0 + pad, y, "tl")
    y = b[3] + 8 * u
    for s_ in bio:
        b = dat(cv, anh_chu(c, s_, 27 * u, B["chu"], vai=font, rong=w - 2 * pad), x0 + pad, y, "tl")
        y = b[3] + 4 * u
    if p.get("link"):
        b = dat(cv, anh_chu(c, str(p.get("link")), 27 * u, B["nhan2"], vai="nhan"), x0 + pad, y, "tl")
        y = b[3]
    y = y1 - pad - 66 * u
    bam = p.get("bam")
    kb = e_out(tien(t, float(bam), 0.25)) if bam not in (None, "") else 0.0
    bw = (w - 2 * pad - 16 * u) * 0.62
    pop = 1 - 0.06 * math.sin(math.pi * tien(t, float(bam), 0.25)) if bam not in (None, "") else 1.0
    cxb, cyb = x0 + pad + bw / 2, y + 33 * u
    cv.save(); cv.translate(cxb, cyb); cv.scale(pop, pop); cv.translate(-cxb, -cyb)
    hop(cv, x0 + pad, y, x0 + pad + bw, y + 66 * u, 14 * u, B["nhan"], 1 - kb)
    hop(cv, x0 + pad, y, x0 + pad + bw, y + 66 * u, 14 * u, B["the2"], kb)
    dat(cv, anh_chu(c, str(p.get("nut") or ""), 30 * u, B["tren_nhan"], vai="nhan"), cxb, cyb, "mc", 1 - kb)
    dat(cv, anh_chu(c, str(p.get("nut_da") or ""), 30 * u, B["chu"], vai="nhan"), cxb, cyb, "mc", kb)
    cv.restore()
    if bam not in (None, "") and 0 <= t - float(bam) < 0.6:
        v = (t - float(bam)) / 0.6
        cv.drawCircle(cxb, cyb, 30 * u + 120 * u * e_out(v), p_net(B["nhan"], 4 * u, 0.7 * (1 - v)))
    hop(cv, x0 + pad + bw + 16 * u, y, x1 - pad, y + 66 * u, 14 * u, B["the2"])
    nut2 = p.get("nut2")                                      # 1.2.21: chữ nút phụ là tham số (hết "Nhắn tin" hàn chết)
    if nut2 is None:
        raise c.thieu("lop.noi_dung.tham_so.nut2", "chữ nút phụ cạnh nút chính (vd \"Nhắn tin\"; \"\" = để trống)")
    if str(nut2):
        dat(cv, anh_chu(c, str(nut2), 28 * u, B["chu"], vai="nhan"), (x0 + pad + bw + 16 * u + x1 - pad) / 2, cyb, "mc")
    return ra(surf)


# ---------------------------------------------------------------- thông báo điện thoại
@dang_ky(**_the(
    id="mau.thong-bao", ten="Thông báo điện thoại (xếp chồng)",
    mo_ta="Bằng chứng/khẩn cấp: thông báo trượt xuống từ trên, cái mới đẩy cái cũ xuống — đơn mới, tiền về, tin nhắn khách.",
    hop_nghia=["thông báo", "đơn mới", "tiền về", "ting ting", "có đơn", "tin nhắn đến", "notification"],
    tham_so={"thong_bao": "list {app, tieu_de, noi_dung, t?, icon? (id kho), gio? (bây giờ)} hoặc [app, tiêu đề, nội dung] (≤ 6)",
             "nhip": "giây giữa 2 thông báo (0.6)", "bat_dau": "giây cái đầu (0.1)", "toi_da": "số cái còn thấy cùng lúc (4)"},
    mac_dinh={"nhip": 0.6, "bat_dau": 0.1, "toi_da": 4},
    hop={"anchor": "mc", "x": 0.5, "y": 0.24, "w": 0.92, "h": 0.32}, dong=True, sfx_goi_y=["ting thông báo", "rung điện thoại", "ka-ching"],
    vi_du={"thong_bao": [["Shop Bán Hàng", "Đơn hàng mới #2841", "Áo khoác kaki · 459.000đ"], ["Ngân hàng", "+459.000đ", "Số dư tài khoản vừa tăng"],
                         ["Tin nhắn", "Chị Lan", "Shop ơi ship giúp chị thêm 1 cái nha"]], "nhip": 0.6}))
def thong_bao(t, dur, W, H, c, p):
    surf, cv = be_mat(W, H)
    B = bang_mau(c, p)
    font = p.get("font") or "than"
    ds = []
    for x in (p.get("thong_bao") or [])[:6]:
        ds.append(muc(x, ("app", "tieu_de", "noi_dung", "t")))
    ts = lich(len(ds), dur, p.get("nhip", 0.6), p.get("bat_dau", 0.1), [d.get("t") for d in ds])
    u = min(W / 1000.0, H / 330.0) * float(p.get("ti_le_chu", 1.0))
    m = 18 * u
    x0, x1 = m, W - m
    pad = 26 * u
    ic = 76 * u
    rong = x1 - x0 - 2 * pad - ic - 22 * u
    nen = voi_alpha("#ffffff", 0.93) if B["tong"] != "toi" else voi_alpha(tron(B["toi"], "#ffffff", 0.12), 0.95)
    chu = B["toi"] if B["tong"] != "toi" else B["sang"]
    phu = tron(chu, "#808080", 0.55)
    the = []
    for i, d in enumerate(ds):
        i_a = anh_chu(c, str(d.get("app") or "").upper(), 22 * u, phu, vai="nhan", gian=0.06)
        i_g = anh_chu(c, str(d.get("gio") or "bây giờ"), 22 * u, phu, vai=font)
        i_t = anh_chu(c, str(d.get("tieu_de") or ""), 30 * u, chu, vai="nhan", rong=rong)
        i_n = anh_chu(c, str(d.get("noi_dung") or ""), vua(c, str(d.get("noi_dung") or ""), 28 * u, rong, 1, 2, co_min=22 * u, vai=font),
                      chu, vai=font, rong=rong) if d.get("noi_dung") else None
        h = 2 * pad + kich(i_a)[1] + 6 * u + kich(i_t)[1] + (kich(i_n)[1] + 2 * u if i_n else 0)
        the.append((i_a, i_g, i_t, i_n, max(h, ic + 2 * pad)))
    toi_da = int(p.get("toi_da", 4))
    hien = [i for i in range(len(ds)) if t >= ts[i]]
    y = m
    ve = []
    for i in reversed(hien):
        k = e_out(tien(t, ts[i], 0.4))
        h = the[i][4]
        ve.append((i, y - (1 - k) * 60 * u, k))
        y += (h + 14 * u) * k
    cv.save(); cv.clipRect(skia.Rect.MakeLTRB(0, 0, W, H))
    for j, (i, yy, k) in reversed(list(enumerate(ve))):
        if j >= toi_da:
            continue
        i_a, i_g, i_t, i_n, h = the[i]
        a = kep(k * 1.5) * (1 - 0.25 * max(0, j - 1) / max(1, toi_da))
        s = 1 - 0.02 * j
        cx = W / 2
        cv.save(); cv.translate(cx, yy); cv.scale(s, s); cv.translate(-cx, -yy)
        bong(cv, x0, yy, x1, yy + h, 30 * u, 40 * u, 0.35 * a, dy=10 * u)
        hop(cv, x0, yy, x1, yy + h, 30 * u, nen, a)
        ixc, iyc = x0 + pad + ic / 2, yy + pad + ic / 2
        img = anh(c, ds[i].get("icon"), 256, loai="icon") if ds[i].get("icon") else None
        if img is not None:
            ve_anh_phu(cv, img, ixc - ic / 2, iyc - ic / 2, ixc + ic / 2, iyc + ic / 2, al=a, r=ic * 0.24)
        else:
            mau_ic = (B["nhan"], B["nhan2"], tron(B["nhan"], B["nhan2"], 0.5))[i % 3]
            pg = p_to(mau_ic, a)
            pg.setShader(skia.GradientShader.MakeLinear([skia.Point(ixc, iyc - ic / 2), skia.Point(ixc, iyc + ic / 2)],
                                                        [sk(tron(mau_ic, "#ffffff", 0.2), a), sk(mau_ic, a)]))
            cv.drawRRect(rr(ixc - ic / 2, iyc - ic / 2, ixc + ic / 2, iyc + ic / 2, ic * 0.24), pg)
            ap = str(ds[i].get("app") or "?").strip()
            dat(cv, anh_chu(c, (ap[:1] or "?").upper(), ic * 0.5, chu_tren(mau_ic), vai="nhan"), ixc, iyc, "mc", a)
        tx = x0 + pad + ic + 22 * u
        b = dat(cv, i_a, tx, yy + pad, "tl", a)
        dat(cv, i_g, x1 - pad, yy + pad, "tr", a)
        b = dat(cv, i_t, tx, b[3] + 6 * u, "tl", a)
        if i_n:
            dat(cv, i_n, tx, b[3] + 2 * u, "tl", a)
        cv.restore()
    cv.restore()
    return ra(surf)
