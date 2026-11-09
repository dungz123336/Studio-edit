# -*- coding: utf-8 -*-
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Bộ kiểu dựng mới học từ kênh mẫu (04/10/2026) — xem nao/kien-thuc/nguoi-ban/2026-10-04_kenh-kênh mẫu-talking-head.md.

Bộ 3 font: Manrope (không chân) · Playfair Display Italic (có chân) · SVN-Flamingo Script (viết tay).
Bộ 3 màu: SANG #FAFAFA · TOI #111111 · NHAN #8C6CFF.

Mọi hàm chỉ sinh ra lớp (ASS, PNG, MP4, MOV có alpha); việc ghép do công thức
`cong-thuc/talking-head-cao-cap/dung.py` làm.
"""
import json, math, os, re, subprocess, shutil, random
import nen_tang as NT
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

try:
    import kit, config
    KHO, MUA = kit.kho(), kit.bo_mua()      # kho chính + bộ mua thêm (có thể rỗng) — đọc từ cau-hinh.json
except Exception:
    KHO, MUA = NT.kho_mac_dinh(), ""

DIR = os.path.dirname(os.path.abspath(__file__))
FD = os.path.join(KHO, "fonts", "tinh")
F_SANS = os.path.join(FD, "Manrope-Medium.ttf")
F_SANS_B = os.path.join(FD, "Manrope-Bold.ttf")
F_SERIF = os.path.join(FD, "PlayfairDisplay-MediumItalic.ttf")
F_SCRIPT = os.path.join(FD, "SVN-Flamingo Script.otf")
F_KHOI = os.path.join(KHO, "fonts", "BeVietnamPro-Black.ttf")
F_CHAY = os.path.join(KHO, "fonts", "BeVietnamPro-SemiBold.ttf")
HO = {"sans": "Manrope Medium", "sansb": "Manrope Bold", "serif": "Playfair Display MI",
      "script": "SVN-Flamingo Script"}
SANG, TOI, NHAN, NHAN2 = "#FAFAFA", "#111111", "#8C6CFF", "#C9BBFF"
try:   # màu + font là GU CỦA HỒ SƠ (tầng cá nhân), không phải của não — mỗi người dùng một bộ
    _pc = config.lay("phong_cach") or {}
    if _pc.get("bo_3_mau"):
        SANG, TOI, NHAN = _pc["bo_3_mau"]
    NHAN2 = _pc.get("mau_nhan_sang", NHAN2)
    for _k, _bien in (("font_sans", "F_SANS"), ("font_sans_dam", "F_SANS_B"), ("font_serif", "F_SERIF"),
                      ("font_viet_tay", "F_SCRIPT"), ("font_khoi", "F_KHOI"), ("font_phu_de", "F_CHAY")):
        for _d in (FD, os.path.join(KHO, "fonts")):      # font tĩnh trước, rồi font chung của kho
            if _pc.get(_k) and os.path.exists(os.path.join(_d, _pc[_k])):
                globals()[_bien] = os.path.join(_d, _pc[_k]); break
except Exception:
    _pc = {}
MAU_PHU_DE = _pc.get("mau_phu_de", NHAN2)     # màu chữ đang nói trong phụ đề chạy
for _bien, _lui in (("F_SANS", "BeVietnamPro-SemiBold.ttf"), ("F_SANS_B", "BeVietnamPro-Bold.ttf"),
                    ("F_SERIF", "BeVietnamPro-Bold.ttf"), ("F_SCRIPT", "BeVietnamPro-Bold.ttf"),
                    ("F_KHOI", "BeVietnamPro-Black.ttf"), ("F_CHAY", "BeVietnamPro-SemiBold.ttf")):
    if not os.path.exists(globals()[_bien]):     # máy khách thiếu font (vd font mua) → lùi, không nổ
        globals()[_bien] = os.path.join(KHO, "fonts", _lui)


def _ho(p, mac_dinh):
    """tên họ font (name ID 1) để libass tìm đúng file — đổi font trong hồ sơ thì phụ đề đổi theo"""
    try:
        from fontTools.ttLib import TTFont
        n = TTFont(p, lazy=True)["name"]
        # kiểu Bold/Bold Italic dùng chung tên họ với bản Regular → gọi bằng tên đầy đủ (ID 4) để libass không chọn nhầm độ đậm
        return (n.getDebugName(4) if (n.getDebugName(2) or "").startswith("Bold") else n.getDebugName(1)) or mac_dinh
    except Exception:
        return mac_dinh


HO = {"sans": _ho(F_SANS, HO["sans"]), "sansb": _ho(F_SANS_B, HO["sansb"]), "serif": _ho(F_SERIF, HO["serif"]),
      "script": _ho(F_SCRIPT, HO["script"]), "chay": _ho(F_CHAY, "Be Vietnam Pro SemiBold")}
W, H, FPS = 1080, 1920, 30
TACH = os.path.join(DIR, "tach_nguoi")

STOP = set("""thì là mà của những các cái một và với cho để có được này đó nó bạn mình
rất cũng như hay hoặc nhưng nhé nha luôn thôi rồi ở trong trên vào ra lên từ đã đang sẽ
vẫn phải không chứ thế vậy ấy đây kia nào gì khi nếu vì nên bằng về""".split())
AO_GIAC = ["subscribe cho kênh", "ghiền mì gõ", "cảm ơn các bạn đã theo dõi",
           "đăng ký kênh", "hẹn gặp lại các bạn trong"]


def sh(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode:
        raise RuntimeError(f"lệnh lỗi: {' '.join(map(str, cmd))[:300]}\n{r.stderr[-1500:]}")
    return r


def hex_rgb(h, a=255):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def font(p, s):
    return ImageFont.truetype(p, int(s))


def do_rong(p, s, chu):
    return font(p, s).getlength(chu)


def loc_ao_giac(segments):
    """bỏ các đoạn whisper bịa ra (thường ở đoạn chỉ có nhạc)"""
    return [s for s in segments if not any(k in s["text"].lower() for k in AO_GIAC)]


# ============================================================== phụ đề "cặp chữ" (ASS)
def _tc(t):
    t = max(0.0, t)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def _c(hx, a=0):
    r, g, b, _ = hex_rgb(hx)
    return f"&H{a:02X}{b:02X}{g:02X}{r:02X}&"


ASS_DAU = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sans,{HO['sans']},40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,-1,0,1,0,0,7,0,0,0,1
Style: Serif,{HO['serif']},110,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,-2,0,1,0,0,5,0,0,0,1
Style: Chay,{HO['chay']},62,{_c(MAU_PHU_DE).rstrip('&')},&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,4.5,1.5,2,60,60,0,1
Style: ChayHop,{HO['chay']},60,{_c(MAU_PHU_DE).rstrip('&')},&H00FFFFFF,&H50120E1A,&H50120E1A,0,0,0,0,100,100,0,0,3,14,0,2,60,60,0,1
Style: Script,{HO['script']},120,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _sk(a, b, style, chu, tag, lop=1):
    return f"Dialogue: {lop},{_tc(a)},{_tc(b)},{style},,0,0,0,,{{{tag}}}{chu}"


def _vao(x, y, an, co, mau, a=0.0, dy=16, mo=10):
    """thẻ vào: mờ -> nét + trượt lên nhẹ (giả motion blur), ra mờ dần"""
    return (f"\\an{an}\\move({x:.0f},{y + dy:.0f},{x:.0f},{y:.0f},0,170)\\fs{co:.0f}\\c{_c(mau)}"
            f"\\blur{mo}\\fad(110,150)\\t(0,170,\\blur0.6)")


def _bong(x, y, an, co, a=0.0, dy=16):
    """lớp bóng mềm nằm dưới (kênh mẫu đổ bóng nhẹ thay vì viền)"""
    return (f"\\an{an}\\move({x + 3:.0f},{y + dy + 4:.0f},{x + 3:.0f},{y + 4:.0f},0,170)\\fs{co:.0f}"
            f"\\c&H000000&\\alpha&H48&\\blur7\\fad(110,150)")


def _chia_cum(tu, toi_da=4, ky_tu=24, nghi=0.35):
    cum, cur = [], []
    for w in tu:
        dai = sum(len(x["word"]) + 1 for x in cur)
        if cur and (w["start"] - cur[-1]["end"] > nghi or len(cur) >= toi_da or dai + len(w["word"]) > ky_tu):
            cum.append(cur); cur = []
        cur.append(w)
        if re.search(r"[.,!?;:]$", w["word"]):
            cum.append(cur); cur = []
    if cur:
        cum.append(cur)
    return cum


def _sach(s):
    return re.sub(r"[^\w%]", "", s.lower())


def _chon_khoa(c):
    def diem(i):
        s = _sach(c[i]["word"])
        return (0 if s in STOP else 10) + len(s) + (8 if re.search(r"\d", s) else 0) + i * 0.1
    return max(range(len(c)), key=diem)


VI_TRI = [(540, 1210), (470, 1160), (610, 1250), (540, 1130), (500, 1270), (590, 1180)]


def phu_de_cap(tu, tranh=(), nhan=(), tren=(), co_nho=64, co_to=156, mau_khoa=SANG, co_dinh=(),
               chon_loc=False, moi=3, vi_tri=(540, 1210)):
    """chon_loc=True (góp ý 05/10: phụ đề không cần lúc nào cũng hiện, không nhảy lung tung):
    chỉ hiện cụm có từ nhấn / con số, thêm 1 cụm mỗi `moi` cụm để không trống quá lâu, đứng yên ở `vi_tri`."""
    """tu: [{word,start,end}] theo thời gian THÀNH PHẨM.
    tranh: các khoảng (a,b) không đặt phụ đề (đang có thẻ toàn khung).
    nhan: tập từ (đã hạ chữ thường) muốn tô màu nhấn. tren: khoảng (a,b) đẩy phụ đề lên đầu, chữ rất to.
    Trả danh sách dòng Dialogue."""
    ev = []
    cum = _chia_cum([w for w in tu if w["word"].strip()])
    for k, c in enumerate(cum):
        a0 = c[0]["start"]
        if any(x - 0.35 <= a0 <= y for x, y in tranh):
            continue
        sau = cum[k + 1][0]["start"] if k + 1 < len(cum) else c[-1]["end"] + 0.6
        b0 = sau if sau - c[-1]["end"] < 0.8 else c[-1]["end"] + 0.45
        for x, y in tranh:
            if a0 < x < b0:
                b0 = x
        if chon_loc:
            co_nhan = any(_sach(w["word"]) in nhan or re.search(r"\d", w["word"]) for w in c)
            if not co_nhan and k % moi:
                continue
        ki = _chon_khoa(c)
        khoa = c[ki]["word"].strip(".,!?;:")
        o_tren = any(x <= a0 <= y for x, y in tren)
        to = co_to * (1.4 if o_tren else 1.0)
        while do_rong(F_SERIF, to, khoa) > 940 and to > 50:
            to *= 0.92
        nho = co_nho * (1.1 if o_tren else 1.0)
        cx, cy = (540, 560) if o_tren else (vi_tri if chon_loc else VI_TRI[k % len(VI_TRI)])
        for x_, y_, gx, gy in co_dinh:          # ghim vị trí (vd đoạn quay màn hình: chữ nằm thấp)
            if x_ <= a0 <= y_:
                cx, cy = (gx, gy) if chon_loc else (gx + (k % 3 - 1) * 70, gy)
        mau = NHAN if (_sach(khoa) in nhan or re.search(r"\d", khoa) or o_tren) else mau_khoa
        kw = do_rong(F_SERIF, to, khoa)
        # từ khoá
        ta = c[ki]["start"]
        if ta >= b0 - 0.04:
            continue
        ev.append(_sk(ta, b0, "Serif", khoa, _bong(cx, cy, 5, to), 0))
        if mau == NHAN:
            # chữ tím đậm chìm trên áo/nền tối (anh xem bản 05/10) -> chữ tím sáng, quầng tím đậm phía sau
            ev.append(_sk(ta, b0, "Serif", khoa, _vao(cx, cy, 5, to, NHAN, mo=10)
                          + f"\\bord6\\3c{_c(NHAN)}\\blur16\\alpha&H50&", 0))
            mau = NHAN2
        ev.append(_sk(ta, b0, "Serif", khoa, _vao(cx, cy, 5, to, mau)))
        # các từ trước: dòng nhỏ lệch trên-trái
        truoc = c[:ki]
        if truoc:
            dai = do_rong(F_SANS, nho, " ".join(w["word"].strip(",;") for w in truoc))
            x0 = min(max(50, cx - kw / 2 + 14), W - 50 - dai)
            y0 = cy - to * 0.42
            x = x0
            for w in truoc:
                if w["start"] >= b0 - 0.04:
                    break
                chu = w["word"].strip(",;")
                ev.append(_sk(w["start"], b0, "Sans", chu, _bong(x, y0, 1, nho), 0))
                ev.append(_sk(w["start"], b0, "Sans", chu, _vao(x, y0, 1, nho, SANG, mo=6)))
                x += do_rong(F_SANS, nho, chu + " ")
        # các từ sau: dòng nhỏ lệch dưới-phải
        sau_tu = c[ki + 1:]
        if sau_tu:
            chuoi = " ".join(w["word"].strip(",;") for w in sau_tu)
            tong = do_rong(F_SANS, nho, chuoi)
            x = max(50, min(cx + kw / 2 - 14, W - 50) - tong)
            y0 = cy + to * 0.30
            for w in sau_tu:
                if w["start"] >= b0 - 0.04:
                    break
                chu = w["word"].strip(",;")
                ev.append(_sk(w["start"], b0, "Sans", chu, _bong(x, y0, 7, nho), 0))
                ev.append(_sk(w["start"], b0, "Sans", chu, _vao(x, y0, 7, nho, SANG, mo=6)))
                x += do_rong(F_SANS, nho, chu + " ")
    return ev


def chu_rieng(chu, a, b, x, y, kieu="serif", co=120, mau=SANG, an=5):
    """một dòng chữ đặt tay (tiêu đề phụ, CTA). kieu: sans | serif | script"""
    st = {"sans": "Sans", "serif": "Serif", "script": "Script", "chay": "Chay"}[kieu]
    return [_sk(a, b, st, chu, _bong(x, y, an, co), 0), _sk(a, b, st, chu, _vao(x, y, an, co, mau, mo=12))]


def tao_ass(ev, ra):
    with open(ra, "w", encoding="utf-8") as f:
        f.write(ASS_DAU + "\n".join(ev) + "\n")
    return ra


def thu_muc_font_ass(tam):
    """libass cần một thư mục chứa đúng các font: gom symlink vào <tam>/fonts"""
    d = os.path.join(tam, "fonts")
    os.makedirs(d, exist_ok=True)
    for p in (F_SANS, F_SANS_B, F_SERIF, F_SCRIPT, F_KHOI, F_CHAY):
        q = os.path.join(d, os.path.basename(p))
        if not os.path.exists(q):
            NT.lien_ket(p, q)          # Windows cấm symlink khi chưa bật Developer Mode → tự lùi về chép
    return d


# ============================================================== nền thẻ (PIL)
def _nen(kieu, t=0.0, seed=7):
    if kieu == "sang":
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        cx, cy = W * (0.5 + 0.08 * math.sin(t * 0.6)), H * 0.42
        d = np.sqrt(((x - cx) / W) ** 2 + ((y - cy) / H) ** 2)
        a = np.clip(d * 1.6, 0, 1)[..., None]
        c0, c1 = np.array([255, 255, 255]), np.array([226, 214, 246])
        img = (c0 * (1 - a) + c1 * a).astype(np.uint8)
        return Image.fromarray(img, "RGB")
    if kieu == "tim":
        y, x = np.mgrid[0:H, 0:W].astype(np.float32)
        g = np.clip(y / H, 0, 1)[..., None]
        top, bot = np.array([34, 6, 92]), np.array([118, 44, 240])
        img = top * (1 - g) + bot * g
        d = np.sqrt(((x - W * (0.3 + 0.1 * math.sin(t))) / W) ** 2 + ((y - H * 0.3) / H) ** 2)
        img += (np.clip(1 - d * 2.2, 0, 1)[..., None] * np.array([90, 40, 120]))
        return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")
    # khói: nền gần đen + vệt sáng cong mờ trôi chậm
    im = Image.new("RGB", (W, H), (12, 12, 14))
    lop = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(lop)
    rng = random.Random(seed)
    for i in range(5):
        x0 = rng.uniform(-200, W) + 40 * math.sin(t * 0.7 + i)
        pts = []
        for k in range(30):
            u = k / 29
            pts.append((x0 + 260 * math.sin(u * 3 + i + t * 0.5), H * (0.25 + 0.75 * u)))
        d.line(pts, fill=rng.randint(90, 170), width=rng.randint(30, 70))
    lop = lop.filter(ImageFilter.GaussianBlur(55))
    im.paste((215, 215, 222), mask=lop)
    return im


def _ghi(ra, khung, n, alpha=False):
    """ghi chuỗi khung PIL ra video. alpha=True -> .mov png có kênh trong suốt"""
    if alpha:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{W}x{H}",
               "-r", str(FPS), "-i", "-", "-c:v", "png", ra]
    else:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "16",
               "-pix_fmt", "yuv420p", ra]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        im = khung(i)
        p.stdin.write(im.convert("RGBA" if alpha else "RGB").tobytes())
    p.stdin.close()
    p.wait()
    return ra


def _de(u):
    return 1 - (1 - min(max(u, 0), 1)) ** 3


def _chu_hien(im, xy, chu, f, mau, u, an="la", bong=True, mo_toi_da=14):
    """vẽ chữ hiện dần: mờ -> nét + từng chữ cái sáng lên trái sang phải (u: 0..1)"""
    while an == "giua" and f.getlength(chu) > W - 100 and f.size > 30:   # không bao giờ tràn mép khung
        f = font(f.path, f.size - 4)
    rong = int(f.getlength(chu)) + 80
    cao = int(f.size * 1.6) + 60
    lop = Image.new("RGBA", (rong, cao), (0, 0, 0, 0))
    d = ImageDraw.Draw(lop)
    x = 40
    n = max(1, len(chu))
    for i, ch in enumerate(chu):
        a = _de((u * 1.6 - i / n * 0.6))
        if a > 0:
            d.text((x, 30), ch, font=f, fill=hex_rgb(mau, int(255 * a)))
        x += f.getlength(ch)
    mo = mo_toi_da * (1 - _de(u * 1.4))
    if mo > 0.3:
        lop = lop.filter(ImageFilter.GaussianBlur(mo))
    px, py = xy
    if an == "giua":
        px -= rong // 2
    elif an == "phai":
        px -= rong
    py -= 30
    if bong:
        b = lop.split()[3].filter(ImageFilter.GaussianBlur(8)).point(lambda v: v * 0.35)
        sh_ = Image.new("RGBA", lop.size, (0, 0, 0, 255)); sh_.putalpha(b)
        im.alpha_composite(sh_, (int(px) + 3, int(py) + 5))
    im.alpha_composite(lop, (int(px), int(py)))


# ============================================================== thẻ toàn khung
def the_danh_sach(ra, nhan, muc, moc, giay, nen="sang"):
    """Danh sách đánh số kiểu kênh mẫu. muc: tên các mục; moc: giây bắt đầu từng mục (tính từ đầu thẻ)."""
    if nen == "sang":
        f_to, mau_to, mau_nho = font(F_SANS, 142), NHAN, NHAN
    elif nen == "tim":
        f_to, mau_to, mau_nho = font(F_SCRIPT, 200), SANG, NHAN2
    else:
        f_to, mau_to, mau_nho = font(F_SERIF, 146), SANG, "#BDBDC4"
    f_nho, f_so = font(F_SANS, 42), font(F_SANS, 46)
    nen_cache = {}
    vt = [(130, 880), (110, 1060), (150, 760), (120, 960)]
    f_muc = []
    for k, ten in enumerate(muc):  # thu nhỏ mục dài cho vừa khung
        f = f_to
        while f.getlength(ten) > W - 2 * vt[k % len(vt)][0] and f.size > 40:
            f = font(f.path, f.size * 0.92)
        f_muc.append(f)

    def khung(i):
        t = i / FPS
        k = int(t * 2) % 8
        if k not in nen_cache:
            nen_cache[k] = _nen(nen, k / 2).convert("RGBA")
        im = nen_cache[k].copy()
        j = max([q for q, m in enumerate(moc) if m <= t] or [0])
        u = (t - moc[j]) / 0.45
        x, y = vt[j % len(vt)]
        so_lop = Image.new("RGBA", (W, H), (0, 0, 0, 0))  # đối trọng tầng dưới: số mờ to (tư duy bố cục)
        ImageDraw.Draw(so_lop).text((W - 60, 1180), f"{j + 1:02d}", font=font(F_SANS_B, 460), anchor="ra",
                                    fill=hex_rgb(mau_nho, int(34 * min(1, max(0, u)))))
        im.alpha_composite(so_lop)
        _chu_hien(im, (x, y - 80), nhan, font(F_SANS, 50), mau_nho, u, bong=False)
        ten, ft = muc[j], f_muc[j]
        _chu_hien(im, (x - 10, y), ten, ft, mau_to, u, bong=(nen != "sang"))
        so = f"{j + 1:02d}"
        _chu_hien(im, (x + ft.getlength(ten) - 20, y + int(ft.size * 1.25)), so, f_so, mau_nho, u - 0.2,
                  an="phai", bong=False)
        return im
    return _ghi(ra, khung, int(giay * FPS))


def the_doi_font(ra, chu, giay=1.0, buoc=0.18):
    """một từ đổi kiểu chữ liên tục trên nền trắng"""
    ds = [(F_SANS, 240, TOI), (F_SERIF, 270, TOI), (F_KHOI, 210, TOI), (F_SCRIPT, 340, TOI),
          (F_SANS_B, 240, NHAN), (F_SERIF, 300, NHAN)]
    nen = _nen("sang", 0).convert("RGBA")

    def khung(i):
        im = nen.copy()
        p, s, m = ds[int(i / FPS / buoc) % len(ds)]
        f = font(p, s)
        d = ImageDraw.Draw(im)
        d.text((W / 2, H * 0.47), chu, font=f, fill=hex_rgb(m), anchor="mm")
        return im
    return _ghi(ra, khung, int(giay * FPS))


def the_dem_so(ra, so, tren, duoi, giay=2.6, nen="khoi", don_vi=""):
    """bộ đếm số lăn kiểu đồng hồ cơ (học từ reel FB)"""
    s = str(so)
    f = font(F_SANS_B, 330)
    f_t, f_d = font(F_SANS, 40), font(F_SANS_B, 46)
    cw = max(f.getlength(str(d)) for d in range(10))
    rong = cw * len(s)
    x0 = (W - rong) / 2
    y0 = H * 0.43
    nen_cache = {}

    def khung(i):
        t = i / FPS
        k = int(t * 2)
        if k not in nen_cache:
            nen_cache[k] = _nen(nen, k / 2).convert("RGBA")
        im = nen_cache[k].copy()
        # khung kính bo góc sau số
        lop = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(lop)
        pad = 60
        d.rounded_rectangle((x0 - pad, y0 - 230, x0 + rong + pad, y0 + 230), 46,
                            fill=(255, 255, 255, 18), outline=(255, 255, 255, 60), width=2)
        im.alpha_composite(lop)
        # từng chữ số lăn từ 0 lên đích, chữ số bên phải lăn lâu hơn
        so_lop = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(so_lop)
        for k2, ch in enumerate(s):
            dich = int(ch) + 10 * (len(s) - k2 + 1)
            u = _de(t / (1.1 + 0.15 * k2))
            v = dich * u
            for q in (math.floor(v), math.floor(v) + 1):
                dy = (q - v) * 300
                a = max(0, 1 - abs(dy) / 300)
                d2.text((x0 + k2 * cw + cw / 2, y0 + dy), str(q % 10), font=f,
                        fill=hex_rgb(SANG, int(255 * a)), anchor="mm")
        mo = 6 * (1 - _de(t / 1.2))
        if mo > 0.4:
            so_lop = so_lop.filter(ImageFilter.GaussianBlur(mo))
        im.alpha_composite(so_lop)
        _chu_hien(im, (W / 2, y0 - 330), tren, f_t, NHAN2, t / 0.5, an="giua", bong=False)
        _chu_hien(im, (W / 2, y0 + 270), duoi, f_d, SANG, (t - 0.9) / 0.5, an="giua", bong=False)
        return im
    return _ghi(ra, khung, int(giay * FPS))


def the_khung_nguoi(ra, base, t0, giay, ten, dong_tren="", chip=(), tam="."):
    """người nói thu nhỏ trong thẻ bo góc trên nền tím nhạt, tên viết tay chồng mép thẻ"""
    cw, chh, r = 640, 720, 48
    cx, cy = (W - cw) // 2, 640
    nen = _nen("sang", 0).convert("RGBA")
    # quầng tím sau thẻ
    q = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(q).rounded_rectangle((cx - 6, cy + 10, cx + cw + 6, cy + chh + 22), r,
                                        fill=hex_rgb(NHAN, 150))
    nen.alpha_composite(q.filter(ImageFilter.GaussianBlur(40)))
    p_nen = os.path.join(tam, "kn_nen.png"); nen.save(p_nen)
    mask = Image.new("L", (cw, chh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, cw - 1, chh - 1), r, fill=255)
    p_mask = os.path.join(tam, "kn_mask.png"); mask.save(p_mask)
    chu = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if dong_tren:   # tầng trên phải có khối to — chữ nhỏ 44 px từng để nửa trên trống (góp ý 05/10)
        ft = font(F_SERIF, 104)
        while ft.getlength(dong_tren) > 940 and ft.size > 60:
            ft = font(F_SERIF, ft.size - 6)
        _chu_hien(chu, (W / 2, 330), dong_tren, ft, NHAN, 1, an="giua", bong=False)
    _chu_hien(chu, (cx - 40, cy + chh - 150), ten, font(F_SCRIPT, 200), SANG, 1)
    p_chu = os.path.join(tam, "kn_chu.png"); chu.save(p_chu)
    # chip hiện lần lượt dưới thẻ
    chips = []
    y = cy + chh + 150
    for k, (txt, moc) in enumerate(chip):
        f = font(F_SANS, 36)
        w_ = int(f.getlength(txt)) + 60
        c = Image.new("RGBA", (w_ + 20, 100), (0, 0, 0, 0))
        dc = ImageDraw.Draw(c)
        dc.rounded_rectangle((10, 10, w_ + 10, 86), 38, fill=(255, 255, 255, 235), outline=hex_rgb(NHAN, 160), width=2)
        dc.text((10 + w_ / 2, 48), txt, font=f, fill=hex_rgb(TOI), anchor="mm")
        p = os.path.join(tam, f"kn_chip{k}.png"); c.save(p)
        chips.append((p, moc))
    xs, tong = [], sum(Image.open(p).width for p, _ in chips) + 6 * max(0, len(chips) - 1)
    x = (W - tong) // 2
    for p, _ in chips:
        xs.append(x); x += Image.open(p).width + 6
    vao = ["-loop", "1", "-t", f"{giay}", "-i", p_nen,
           "-ss", f"{t0}", "-t", f"{giay}", "-i", base,
           "-loop", "1", "-t", f"{giay}", "-i", p_mask,
           "-loop", "1", "-t", f"{giay}", "-i", p_chu]
    for p, _ in chips:
        vao += ["-loop", "1", "-t", f"{giay}", "-i", p]
    # cắt phần đầu + vai của người nói rồi đưa vào thẻ, thẻ nảy nhẹ khi vào
    fc = (f"[1:v]crop=1080:1215:0:220,scale={cw}:{chh},setsar=1,format=rgba[v];"
          f"[2:v]format=gray[m];[v][m]alphamerge[vc];"
          f"[0:v][vc]overlay={cx}:{cy}:shortest=1[a0];"
          f"[3:v]fade=t=in:st=0.25:d=0.35:alpha=1[ch];[a0][ch]overlay=0:0[a1]")
    cur = "a1"
    for k, (p, moc) in enumerate(chips):
        fc += (f";[{4 + k}:v]fade=t=in:st={moc}:d=0.25:alpha=1[c{k}];"
               f"[{cur}][c{k}]overlay={xs[k]}:{y}:enable='gte(t,{moc})'[b{k}]")
        cur = f"b{k}"
    fc += f";[{cur}]fps={FPS},format=yuv420p[out]"
    sh(["ffmpeg", "-y", "-loglevel", "error", *vao, "-filter_complex", fc, "-map", "[out]",
        "-t", f"{giay}", "-c:v", "libx264", "-crf", "16", "-preset", "medium", "-an", ra])
    return ra


# ============================================================== lớp chồng (PNG trong suốt)
def o_tron(tam, ds, y=360, co=150):
    """các ô vuông bo góc xếp hàng ngang, mỗi ô 1 PNG riêng (hiện lần lượt) — kiểu bảng màu.
    ds: [(màu_nền, chữ_trong_ô, nhãn_dưới)] -> [(png, x, y)]"""
    ra = []
    n = len(ds)
    khoang = 60
    x = (W - (n * co + (n - 1) * khoang)) // 2
    for k, (mau, trong, nhan) in enumerate(ds):
        im = Image.new("RGBA", (co + 120, co + 120), (0, 0, 0, 0))
        b = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(b).rounded_rectangle((60, 66, 60 + co, 66 + co), 30, fill=(0, 0, 0, 120))
        im.alpha_composite(b.filter(ImageFilter.GaussianBlur(12)))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((60, 60, 60 + co, 60 + co), 30, fill=hex_rgb(mau))
        mau_chu = TOI if mau.upper() in ("#FAFAFA", "#FFFFFF") else SANG
        if trong:
            d.text((60 + co / 2, 60 + co / 2), trong, font=font(F_SANS_B, 46), fill=hex_rgb(mau_chu), anchor="mm")
        p = os.path.join(tam, f"o{k}_{abs(hash(nhan)) % 9999}.png")
        im.save(p)
        ra.append((p, x - 60, y - 60))
        # nhãn dưới ô
        f = font(F_SANS, 40)
        lb = Image.new("RGBA", (int(f.getlength(nhan)) + 40, 70), (0, 0, 0, 0))
        dl = ImageDraw.Draw(lb)
        dl.text((22, 22), nhan, font=f, fill=(0, 0, 0, 140))
        dl.text((20, 18), nhan, font=f, fill=hex_rgb(SANG))
        pl = os.path.join(tam, f"ol{k}_{abs(hash(nhan)) % 9999}.png")
        lb.save(pl)
        ra.append((pl, x + co // 2 - lb.width // 2, y + co + 14))
        x += co + khoang
    return ra


def nhan_luu(tam, chu="Lưu lại", phu="để xem khi cần"):
    """CTA lưu: chữ viết tay vàng ánh tím + icon bookmark (kênh mẫu đặt ở giây 4–15)"""
    f = font(F_SCRIPT, 150)
    f2 = font(F_SANS, 36)
    rong = int(f.getlength(chu)) + 220
    im = Image.new("RGBA", (rong, 300), (0, 0, 0, 0))
    _chu_hien(im, (40, 60), chu, f, "#FFD76A", 1)
    d = ImageDraw.Draw(im)
    bx = int(f.getlength(chu)) + 70
    d.polygon([(bx, 80), (bx + 50, 80), (bx + 50, 150), (bx + 25, 128), (bx, 150)], fill=hex_rgb("#FFD76A"))
    _chu_hien(im, (int(f.getlength(chu)) - 260, 210), phu, f2, SANG, 1)
    p = os.path.join(tam, "nhan_luu.png")
    im.save(p)
    return p


def chu_khoi_png(tam, chu, co=300, mau=SANG, quang=NHAN, ten="khoi"):
    """chữ khối đậm có quầng màu — dùng cho chữ sau lưng người"""
    f = font(F_KHOI, co)
    while f.getlength(chu) > 1000:
        co *= 0.92; f = font(F_KHOI, co)
    rong, cao = int(f.getlength(chu)) + 200, int(co * 1.5) + 120
    lop = Image.new("RGBA", (rong, cao), (0, 0, 0, 0))
    d = ImageDraw.Draw(lop)
    d.text((rong / 2, cao / 2), chu, font=f, fill=hex_rgb(mau), anchor="mm")
    q = Image.new("RGBA", lop.size, hex_rgb(quang, 0))
    q.putalpha(lop.split()[3].filter(ImageFilter.GaussianBlur(28)).point(lambda v: min(255, v * 1.4)))
    out = Image.new("RGBA", lop.size, (0, 0, 0, 0))
    out.alpha_composite(q)
    out.alpha_composite(lop)
    p = os.path.join(tam, f"{ten}.png")
    out.save(p)
    return p, out.size


# ============================================================== chiều sâu (cần tách người)
def mat_na_nguoi(base, t0, t1, tam, ten, muc="balanced"):
    """trích khung [t0,t1] ở 540x960 -> tách người (Mac: Apple Vision · Windows: MediaPipe) -> thư mục mặt nạ PNG"""
    vao, ra = os.path.join(tam, f"{ten}_vao"), os.path.join(tam, f"{ten}_mn")
    for d in (vao, ra):
        shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    sh(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0}", "-t", f"{t1 - t0}", "-i", base,
        "-vf", f"fps={FPS},scale=540:960", os.path.join(vao, "%04d.png")])
    NT.tach_nguoi(vao, ra, muc)
    return ra


def dinh_dau(mn_dir):
    """toạ độ y (khung 1920) của đỉnh đầu ở khung đầu tiên"""
    f = sorted(os.listdir(mn_dir))[0]
    a = np.asarray(Image.open(os.path.join(mn_dir, f)).convert("L")).astype(np.float32) / 255
    hang = np.where(a[:, a.shape[1] // 3: 2 * a.shape[1] // 3].mean(1) > 0.25)[0]
    return int((hang[0] if len(hang) else a.shape[0] * 0.2) * H / a.shape[0])


def lop_nguoi(base, t0, t1, mn_dir, ra):
    """video người đã tách nền (có alpha) cho khoảng [t0,t1]"""
    sh(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0}", "-t", f"{t1 - t0}", "-i", base,
        "-framerate", str(FPS), "-i", os.path.join(mn_dir, "%04d.png"),
        "-filter_complex", f"[1:v]scale={W}:{H},gblur=sigma=1.2,format=gray[m];[0:v]format=rgba[v];"
                           f"[v][m]alphamerge,format=rgba[o]",
        "-map", "[o]", "-t", f"{t1 - t0}", "-c:v", "png", ra])
    return ra


def nen_keo_diem_anh(base, t0, t1, ra, hang=None):
    """nền thành vệt dọc 'kéo dài điểm ảnh' + lệch màu nhẹ (người sẽ được đặt lại lên trên)"""
    y = hang if hang is not None else 260
    sh(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0}", "-t", f"{t1 - t0}", "-i", base,
        "-vf", f"crop={W}:6:0:'{y}+40*sin(t*7)',scale={W}:{H}:flags=neighbor,"
               f"rgbashift=rh=-8:bh=8,noise=alls=14:allf=t,eq=contrast=1.1:saturation=1.25,fps={FPS}",
        "-t", f"{t1 - t0}", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p", "-an", ra])
    return ra


def chu_vao_dong(ra, png, giay, x, y, phong=1.18):
    """PNG -> MOV alpha: thu từ to về (phong -> 1) + mờ -> nét trong 0,28 s"""
    src = Image.open(png).convert("RGBA")

    def khung(i):
        t = i / FPS
        u = _de(t / 0.28)
        s = phong + (1 - phong) * u
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        w_, h_ = int(src.width * s), int(src.height * s)
        a = src.resize((w_, h_), Image.LANCZOS)
        mo = 10 * (1 - u)
        if mo > 0.3:
            a = a.filter(ImageFilter.GaussianBlur(mo))
        if u < 1:
            al = a.split()[3].point(lambda v: v * min(1, u * 1.6))
            a.putalpha(al)
        im.alpha_composite(a, (int(x - w_ / 2), int(y - h_ / 2)))
        return im
    return _ghi(ra, khung, int(giay * FPS), alpha=True)


# ============================================================== nền lưới sau lưng người (thay vệt kéo điểm ảnh)
GRID = f"{MUA}/2. Back Ground - Icon Trending/Grid Backgrounds" if MUA else ""
LUOI = {
    "tim": f"{GRID}/Still Grids/Vertical Small Grids/purple.mp4",
    "den": f"{GRID}/Still Grids/Vertical Large Grids/black.mp4",
    "xoan": f"{GRID}/Extras/Twister grid.mp4",
    "cham": f"{GRID}/Extras/Dots.mp4",
    "cham_song": f"{GRID}/Extras/Wavy Dots BG.mov",
}


def nen_luoi(t0, t1, ra, kieu="tim", nhuom=None):
    """nền lưới động toàn khung cho đoạn [t0,t1] (người sẽ được đặt lại lên trên).
    kieu: tim | den | xoan | cham | cham_song. nhuom: màu hex nhuộm lưới trắng (vd NHAN)."""
    src = LUOI.get(kieu, kieu)
    d = t1 - t0
    if not os.path.exists(src):
        # không có bộ lưới mua thêm → tự vẽ lưới (người dùng nào cũng chạy được)
        nen = {"tim": "0x1A1030", "den": "0x0E0E0E"}.get(kieu, "0x111111")
        o = 54 if kieu in ("tim", "cham", "cham_song") else 108
        src = f"color=c={nen}:s={W}x{H}:r={FPS},drawgrid=w={o}:h={o}:t=2:c=white@0.18"
        sh(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", src, "-t", f"{d:.3f}",
            "-vf", f"zoompan=z='1.0+0.0009*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={W}x{H}:fps={FPS},format=yuv420p",
            "-an", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", ra])
        return ra
    loc = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
           f"zoompan=z='1.0+0.0009*on':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={W}x{H}:fps={FPS}")
    if nhuom:
        r, g, b, _ = hex_rgb(nhuom)
        loc += f",colorchannelmixer=rr={r/255:.2f}:gg={g/255:.2f}:bb={b/255:.2f}"
    loc += ",eq=brightness=0.02,format=yuv420p"
    sh(["ffmpeg", "-y", "-loglevel", "error", "-stream_loop", "-1", "-i", src, "-t", f"{d:.3f}",
        "-vf", loc, "-an", "-c:v", "libx264", "-crf", "17", "-pix_fmt", "yuv420p", ra])
    return ra


def vien_nguoi(base, t0, t1, mn_dir, ra, mau="#FFFFFF", day=7):
    """viền sticker quanh người (lớp alpha đặt ngay dưới người)"""
    gian = ",".join(["dilation"] * day)
    r, g, b, _ = hex_rgb(mau)
    sh(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", os.path.join(mn_dir, "%04d.png"),
        "-f", "lavfi", "-i", f"color=c=0x{r:02X}{g:02X}{b:02X}:s={W}x{H}:r={FPS}:d={t1 - t0:.3f}",
        "-filter_complex", f"[0:v]format=gray,lut=y='if(gt(val,110),255,0)',{gian},scale={W}:{H},gblur=sigma=1.5[m];"
                           f"[1:v]format=rgba[c];[c][m]alphamerge,format=rgba[o]",
        "-map", "[o]", "-t", f"{t1 - t0:.3f}", "-c:v", "png", ra])
    return ra


# ============================================================== thông báo kiểu iPhone (học từ reel FB "Trước & Sau AI")
def thong_bao(ra, ds, giay, y0=360):
    """các thẻ thông báo kính mờ trượt xuống lần lượt và xếp chồng.
    ds: [(tiêu_đề, dòng_phụ, chữ_trong_icon, giây_xuất_hiện)] -> MOV alpha dài `giay`."""
    f1, f2, fi = font(F_SANS_B, 40), font(F_SANS, 32), font(F_SANS_B, 40)
    rong, cao = 860, 128
    the = []
    for tieu, phu, ic, _ in ds:
        im = Image.new("RGBA", (rong + 60, cao + 60), (0, 0, 0, 0))
        bong = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(bong).rounded_rectangle((30, 38, 30 + rong, 38 + cao), 40, fill=(0, 0, 0, 110))
        im.alpha_composite(bong.filter(ImageFilter.GaussianBlur(16)))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((30, 30, 30 + rong, 30 + cao), 40, fill=(246, 244, 252, 236),
                            outline=(255, 255, 255, 255), width=2)
        d.rounded_rectangle((56, 54, 56 + 80, 54 + 80), 22, fill=hex_rgb(NHAN))
        d.text((96, 94), ic, font=fi, fill=hex_rgb(SANG), anchor="mm")
        d.text((162, 58), tieu, font=f1, fill=hex_rgb(TOI))
        d.text((162, 106), phu, font=f2, fill=(90, 86, 104, 255))
        d.text((30 + rong - 30, 62), "bây giờ", font=f2, fill=(140, 136, 150, 255), anchor="ra")
        the.append(im)
    x = (W - the[0].width) // 2

    def khung(i):
        t = i / FPS
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        hien = [k for k, (*_, m) in enumerate(ds) if m <= t]
        for vt, k in enumerate(reversed(hien)):          # thẻ mới nhất ở trên cùng
            u = _de((t - ds[k][3]) / 0.35)
            y = y0 + vt * (cao + 22) - (1 - u) * 60
            a = the[k].copy()
            if u < 1:
                a.putalpha(a.split()[3].point(lambda v: v * u))
            im.alpha_composite(a, (x, int(y)))
        return im
    return _ghi(ra, khung, int(giay * FPS), alpha=True)


# ============================================================== phụ đề chạy + chữ nhấn thưa (tư duy chữ 06/10)
CHO_CHAY = [1330, 1150]               # phụ đề chạy chỉ ở dưới/ngực, KHÔNG nhảy lên đầu (đụng tiêu đề, mắt phải tìm)
CHO_NHAN = [400, 560, 1150]           # chữ nhấn: thử mảng trống trên đầu trước, rồi mới xuống ngực


def _cum_chay(tu, toi_da_tu=7, ky_tu=30, nghi=0.45, toi_thieu=1.0):
    """cụm 1 dòng ≤ 30 ký tự; cụm đứng chưa đủ thời gian đọc thì gộp với cụm sau"""
    cum, cur = [], []
    for w in tu:
        dai = sum(len(x["word"]) + 1 for x in cur)
        if cur and (w["start"] - cur[-1]["end"] > nghi or len(cur) >= toi_da_tu or dai + len(w["word"]) > ky_tu):
            cum.append(cur); cur = []
        cur.append(w)
        if re.search(r"[.!?]$", w["word"]):
            cum.append(cur); cur = []
    if cur:
        cum.append(cur)
    gon = []
    for c in cum:
        can = max(toi_thieu, 0.32 * len(c))
        if gon and (gon[-1][-1]["end"] - gon[-1][0]["start"] < max(toi_thieu, 0.32 * len(gon[-1])))                 and sum(len(x["word"]) + 1 for x in gon[-1] + c) <= ky_tu + 8:
            gon[-1] = gon[-1] + c
        else:
            gon.append(c)
    return gon


def phu_de_chay(tu, tranh=(), ban=None, nhan_tu=(), chu_nhan=None, khoang_nhan=8.0, co=62, tieu_de=(), vung_co_dinh=()):
    """Phụ đề chạy 1 font 1 cỡ ở dải dưới, chữ đang nói sáng nhẹ (karaoke). Chọn chỗ bằng `ban(t, y)` —
    mắt nhìn khung nền (duyet_chu.vung_ban): dải đang rối (mặt/tay/chữ màn hình) thì dời cả đoạn lên dải khác.
    Chữ nhấn: chu_nhan=[(a,b,"chữ")] đặt tay, hoặc tự chọn cụm có từ nhấn, cách nhau ≥ khoang_nhan giây.
    Trả (ev, khoảng_chữ_nhấn)."""
    tu = [w for w in tu if w["word"].strip()]
    ev, nhan_kh = [], []
    cum = _cum_chay(tu)
    # --- chữ nhấn thưa
    if chu_nhan is None:
        chu_nhan, cuoi = [], -99
        for c in cum:
            a0 = c[0]["start"]
            if any(x - 0.3 <= a0 <= y + 0.3 for x, y in list(tranh) + list(tieu_de)) or a0 - cuoi < khoang_nhan:
                continue
            idx = [i for i, w in enumerate(c) if _sach(w["word"]) in nhan_tu or re.search(r"\d", w["word"])]
            if idx:
                # lấy trọn CỤM có nghĩa (từ nhấn liền nhau, số kéo theo danh từ) — không bốc chữ cụt kiểu "kiến"
                i0 = max(idx, key=lambda i: len(c[i]["word"]))
                a_, b_ = i0, i0
                while a_ - 1 in idx:
                    a_ -= 1
                while b_ + 1 in idx:
                    b_ += 1
                if b_ == a_ and re.search(r"\d", c[a_]["word"]):
                    b_ = min(len(c) - 1, a_ + 2)          # "250" -> "250 tin nhắn"
                if b_ == a_:
                    continue                              # chỉ một chữ lẻ -> không đủ nghĩa để nhấn
                chu = " ".join(w["word"].strip(".,!?") for w in c[a_:b_ + 1])
                chu_nhan.append((c[a_]["start"], max(c[-1]["end"] + 0.3, c[a_]["start"] + 1.4), chu))
                cuoi = a0
    for a0, b0, chu in chu_nhan:
        for x, y in tranh:                 # chữ nhấn tắt trước khi thẻ/lớp chồng hiện — không lọt sang thẻ
            if a0 < x < b0:
                b0 = x - 0.04
        if b0 - a0 < 1.0:
            continue
        to = 150
        while do_rong(F_SERIF, to, chu) > 920 and to > 90:
            to -= 8
        y = 560
        if ban:   # chọn chỗ trống nhất trong vùng an toàn, ưu tiên mảng tường phía trên đầu
            y = min(CHO_NHAN, key=lambda yy: ban((a0 + b0) / 2, yy, 200) + (0.15 if yy == 1150 else 0))
        ev.append(_sk(a0, b0, "Serif", chu, _bong(540, y, 5, to), 0))
        ev.append(_sk(a0, b0, "Serif", chu, _vao(540, y, 5, to, NHAN2, mo=8)
                      + f"\\bord5\\3c{_c(NHAN)}", 1))
        nhan_kh.append((a0, b0))
    # --- phụ đề chạy
    y_cu = CHO_CHAY[0]
    for ci, c in enumerate(cum):
        a0, b0 = c[0]["start"], c[-1]["end"] + 0.25
        if ci + 1 < len(cum):                       # tắt trước khi cụm sau hiện — không bao giờ 2 dòng chồng nhau
            b0 = min(b0, cum[ci + 1][0]["start"] - 0.02)
        if any(x - 0.05 <= a0 <= y for x, y in list(tranh) + nhan_kh):
            continue
        for x, y in list(tranh) + nhan_kh:
            if a0 < x < b0:
                b0 = x
        can = max(1.0, 0.32 * len(c))
        if b0 - a0 < min(can, 1.0):                         # bị thẻ chen còn < 1 s -> bỏ, đừng để chớp qua
            continue
        y, kieu = y_cu, "Chay"
        ghim = next((yy for x, z, yy in vung_co_dinh if x <= a0 <= z), None)
        if ghim:                                            # vùng đã thiết kế sẵn chỗ chữ (vd dưới khung màn hình)
            k = "".join(f"{{\\kf{max(1, int(round((w['end'] - w['start']) * 100)))}}}{w['word']} " for w in c).strip()
            ev.append(f"Dialogue: 2,{_tc(a0)},{_tc(b0)},Chay,,0,0,0,,{{\\an2\\pos(540,{ghim})\\fad(60,80)}}{k}")
            continue
        if ban:
            tm = (a0 + b0) / 2
            if ban(tm, y - co * 0.6) > 1.9:                 # chỗ cũ bị chiếm -> tìm dải trống nhất
                y = min(CHO_CHAY, key=lambda yy: ban(tm, yy - co * 0.6))
                if ban(tm, y - co * 0.6) > 1.9:             # chỗ nào cũng rối (quay màn hình) -> hộp nền tối ở dải dưới
                    y, kieu = CHO_CHAY[0], "ChayHop"
        y_cu = y if kieu == "Chay" else y_cu
        k = "".join(f"{{\\kf{max(1, int(round((w['end'] - w['start']) * 100)))}}}{w['word']} " for w in c).strip()
        ev.append(f"Dialogue: 2,{_tc(a0)},{_tc(b0)},{kieu},,0,0,0,,{{\\an2\\pos(540,{y})\\fad(60,80)}}{k}")
    return ev, nhan_kh
