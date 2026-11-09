#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""ẢNH BÌA THEO HỒ SƠ — màu, font, kiểu bố cục lấy từ hồ sơ đang dùng (cau-hinh.json → bia.kieu, mau, chu, phong_cach).
Không hồ sơ nào mượn kiểu bìa của hồ sơ khác: mỗi hồ sơ khai `bia.kieu` riêng + mô tả trong anh-bia.md.

    python3 bia.py <video-hoặc-ảnh> --giay 12.5 --dong1 "SẮP CHẠY THỬ" [--dong2 "…"] [--nhan "…"] [--goc "…"]
                   --ra <thư-mục>/thumb-<tên>.png [--watermark "Edit AI"] [--kieu <đè kiểu của hồ sơ>]

Kiểu bố cục (bia.kieu):
  hai-dong      2 dòng chữ khối ở dưới (dòng 1 trắng, dòng 2 màu nhấn), viền đen dày, thanh màu thương hiệu dưới cùng
  bang-nghieng  băng màu thương hiệu nghiêng ở 1/3 trên + nhãn màu nhấn bên dưới + chữ góc dưới   (bộ soi-dong)
  the-goc       thẻ tối bo góc ở trên-trái, dòng 1 serif nghiêng to, dòng 2 sans nhỏ màu nhấn           (bộ bien-tap)
  neon          nền tối dần ở dưới, chữ phát sáng màu nhấn, khung mảnh                                    (bộ neon)
--giay: chọn khung có mặt/đồ vật rõ (đã NHÌN ở bước 3). Chữ luôn nằm trong vùng TikTok giữ lại (bia.cat_tiktok).
"""
import argparse, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import config, kit, nen_tang as NT

W, H = 1080, 1920
KIEU = ("hai-dong", "bang-nghieng", "the-goc", "neon")


def hx(h, a=255):
    h = (h or "#FFFFFF").lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (a,)


def tim_font(ten, lui="BeVietnamPro-Black.ttf"):
    for t in (ten, lui):
        if not t:
            continue
        try:
            return kit.find(t)
        except Exception:
            pass
    return kit.find("BeVietnamPro-Bold.ttf")


def vua(path, chu, toi_da, rong):
    s = toi_da
    while s > 30 and ImageFont.truetype(path, s).getlength(chu) > rong:
        s -= 4
    return ImageFont.truetype(path, s)


def nen(src, giay):
    p = NT.tam("bia_nen.png")
    if src.lower().endswith((".png", ".jpg", ".jpeg")):
        im = Image.open(src).convert("RGB")
    else:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(giay), "-i", src, "-frames:v", "1", p], check=True)
        im = Image.open(p).convert("RGB")
    r = max(W / im.width, H / im.height)
    im = im.resize((int(im.width * r + .5), int(im.height * r + .5)), Image.LANCZOS)
    x, y = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((x, y, x + W, y + H)).convert("RGBA")


def toi_dan(im, tu, den=210, mau=(0, 0, 0)):
    lop = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(lop)
    for y in range(tu, H):
        d.line([(0, y), (W, y)], fill=mau + (min(den, int((y - tu) * den / 420)),))
    im.alpha_composite(lop)


def ve(a):
    pc = config.lay("phong_cach") or {}
    nhan = config.lay("mau", "nhan") or pc.get("bo_3_mau", [None, None, "#FFD200"])[2]
    th = config.lay("mau", "thuong_hieu") or pc.get("mau_thuong_hieu") or nhan
    toi = (pc.get("bo_3_mau") or ["#FFFFFF", "#111111"])[1]
    f_khoi = tim_font(config.lay("chu", "bia"), "Anton-Regular.ttf")
    f_nhan = tim_font(pc.get("font_phu_de"), "BeVietnamPro-Bold.ttf")
    f_serif = tim_font(pc.get("font_serif"), "BeVietnamPro-Black.ttf")
    kieu = a.kieu or config.lay("bia", "kieu")
    if kieu not in KIEU:
        sys.exit(f"Hồ sơ '{config.ho_so_hien_tai()}' chưa khai bia.kieu hợp lệ ({', '.join(KIEU)}). "
                 "Chọn kiểu RIÊNG cho hồ sơ này (ghi cả vào anh-bia.md) — không mượn kiểu của hồ sơ khác.")
    tren, duoi = config.lay("bia", "cat_tiktok") or [240, 1680]
    im = nen(a.nguon, a.giay); d = ImageDraw.Draw(im)

    if kieu == "hai-dong":
        toi_dan(im, duoi - 560)
        for chu, y, mau in ((a.dong1, duoi - 330, (255, 255, 255, 255)), (a.dong2, duoi - 150, hx(nhan))):
            if chu:
                d.text((W / 2, y), chu, font=vua(f_khoi, chu, 210, 960), anchor="mm", fill=mau, stroke_width=12, stroke_fill=(0, 0, 0))
        d.rectangle((55, duoi - 55, W - 55, duoi - 38), fill=hx(th))
    elif kieu == "bang-nghieng":
        bang = Image.new("RGBA", (1180, 250), (0, 0, 0, 0)); db = ImageDraw.Draw(bang)
        db.rectangle((0, 0, 1179, 249), fill=hx(th))
        db.rectangle((0, 12, 1179, 19), fill=(255, 255, 255, 230)); db.rectangle((0, 230, 1179, 237), fill=(255, 255, 255, 230))
        db.text((590, 125), a.dong1, font=vua(f_khoi, a.dong1, 170, 1040), anchor="mm", fill=(255, 255, 255, 255))
        bang = bang.rotate(4, expand=True, resample=Image.BICUBIC)
        bong = Image.new("RGBA", bang.size, (0, 0, 0, 0)); bong.putalpha(bang.split()[3].point(lambda v: v * 0.45))
        y0 = tren + 15
        im.alpha_composite(bong.filter(ImageFilter.GaussianBlur(18)), ((W - bang.width) // 2 + 10, y0 + 18))
        im.alpha_composite(bang, ((W - bang.width) // 2, y0))
        if a.nhan:
            fb = vua(f_nhan, a.nhan, 62, 900); w = d.textlength(a.nhan, font=fb)
            nen_nhan = (255, 255, 255, 255) if hx(th) == hx(nhan) else hx(nhan)     # băng và nhãn cùng màu → nhãn trắng
            d.rounded_rectangle((W / 2 - w / 2 - 40, y0 + 360, W / 2 + w / 2 + 40, y0 + 455), 22, fill=nen_nhan)
            d.text((W / 2, y0 + 407), a.nhan, font=fb, anchor="mm", fill=hx(toi))
        if a.dong2:
            d.text((W / 2, duoi - 260), a.dong2, font=vua(f_khoi, a.dong2, 130, 960), anchor="mm", fill=(255, 255, 255), stroke_width=9, stroke_fill=(0, 0, 0))
    elif kieu == "the-goc":
        fs = vua(f_serif, a.dong1, 150, 800); w1 = d.textlength(a.dong1, font=fs)
        f2 = vua(f_nhan, a.dong2 or "", 64, 800) if a.dong2 else None
        cao = 70 + 170 + (100 if a.dong2 else 0)
        lop = Image.new("RGBA", (W, H), (0, 0, 0, 0)); dl = ImageDraw.Draw(lop)
        dl.rounded_rectangle((60, tren + 40, 60 + max(w1, f2.getlength(a.dong2) if f2 else 0) + 100, tren + 40 + cao), 36, fill=hx(toi, 225))
        im.alpha_composite(lop); d = ImageDraw.Draw(im)
        d.text((110, tren + 90), a.dong1, font=fs, anchor="lt", fill=(255, 255, 255))
        if a.dong2:
            d.text((112, tren + 90 + 190), a.dong2, font=f2, anchor="lt", fill=hx(nhan))
        if a.nhan:
            d.text((W / 2, duoi - 140), a.nhan, font=vua(f_nhan, a.nhan, 58, 900), anchor="mm", fill=(255, 255, 255), stroke_width=5, stroke_fill=hx(toi))
    elif kieu == "neon":
        toi_dan(im, duoi - 700, 235, hx(toi)[:3])
        for chu, y, co in ((a.dong1, duoi - 360, 190), (a.dong2, duoi - 180, 110)):
            if not chu:
                continue
            ff = vua(f_khoi, chu, co, 960)
            glow = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(glow).text((W / 2, y), chu, font=ff, anchor="mm", fill=hx(nhan))
            im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(22))); im.alpha_composite(glow.filter(ImageFilter.GaussianBlur(8)))
            d = ImageDraw.Draw(im); d.text((W / 2, y), chu, font=ff, anchor="mm", fill=(255, 255, 255) if co > 150 else hx(nhan))
        d.rectangle((50, tren + 30, W - 50, duoi - 30), outline=hx(nhan, 160), width=3)
        if a.nhan:
            d.text((W / 2, tren + 110), a.nhan, font=vua(f_nhan, a.nhan, 56, 900), anchor="mm", fill=hx(nhan))
    if a.goc:
        d.text((W / 2, duoi - 70 if kieu != "hai-dong" else tren + 80), a.goc, font=vua(f_nhan, a.goc, 56, 900), anchor="mm",
               fill=(255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0))
    if a.watermark:
        wm = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(wm).text((W / 2, H / 2), a.watermark, font=ImageFont.truetype(tim_font("Anton-Regular.ttf"), 190),
                                anchor="mm", fill=(255, 255, 255, 92), stroke_width=4, stroke_fill=(0, 0, 0, 60))
        im.alpha_composite(wm)
    os.makedirs(os.path.dirname(os.path.abspath(a.ra)), exist_ok=True)
    im.convert("RGB").save(a.ra)
    print(f"bìa {kieu} · hồ sơ {config.ho_so_hien_tai()} → {a.ra}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("nguon"); ap.add_argument("--giay", type=float, default=1.0)
    ap.add_argument("--dong1", required=True); ap.add_argument("--dong2", default="")
    ap.add_argument("--nhan", default=""); ap.add_argument("--goc", default="")
    ap.add_argument("--ra", required=True); ap.add_argument("--watermark", default="")
    ap.add_argument("--kieu", default="")
    ve(ap.parse_args())
