# -*- coding: utf-8 -*-
"""Xem trước tài nguyên kho → kho-chi-muc/xem-truoc/<id>.*  (cache theo mtime nguồn)

tao(muc, ep=False, chi_muc_dir=None) → đường dẫn ảnh xem trước (png/jpg) hoặc None
    font  → PNG 900×220 nền tối, chữ sáng, bằng CHÍNH font đó (skia): tên họ + câu mẫu đủ dấu
    lut   → JPG 480×270 chia đôi trái = gốc, phải = áp LUT (ffmpeg lut3d) trên ảnh mẫu
    nhac/sfx → PNG dạng sóng 600×80 (ffmpeg → PCM → PIL)
    nen/video → JPG khung giây 1, rộng 480 (ep=True: thêm mp4 xem thử, xem thu())
    icon/anh/preset_capcut → PNG/JPG thumbnail (icon 240 giữ alpha; nền/ảnh/preset rộng 480)
nghe(muc) → file nghe thử: nhạc = mp3 64k 30 s đầu; sfx = file gốc nếu < 1 MB, nếu không chuyển mp3
thu(muc)  → mp4 480p 4 s đầu không tiếng (nen/video)
"""
import os, sys, re, json, time, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung

def _clip_mau():
    """1.2.19 (E14): clip người thật để xem thử LUT/nền — tìm trong dự án gần nhất của máy này (proxy), không trỏ cứng máy người bán"""
    import glob as _g
    try:                                           # thư mục dự án trên ổ không gắn / proxy vừa bị xoá → không làm chết import của kho/api
        ds = []
        for p in _g.glob(os.path.join(chung.duong("du_an"), "*", "cache", "proxy*.mp4")):
            try:
                ds.append((os.path.getmtime(p), p))
            except OSError:
                pass
        if ds:
            return max(ds)[1]
        for p in sorted(_g.glob(os.path.join(chung.SKILL, "tai-nguyen", "**", "*.mp4"), recursive=True))[:1]:
            return p
    except Exception:
        pass
    return ""


_CLIP = {}


def clip_mau():
    """1.2.21: tìm lười khi cần (import kho/api không quét thư mục dự án nữa); nhớ kết quả trong tiến trình"""
    if "p" not in _CLIP:
        _CLIP["p"] = _clip_mau()
    return _CLIP["p"]
CAU_MAU = "Tiếng Việt có dấu: Ấ Ệ Ở Ỡ Ữ Đ 0123 — Edit video nhanh"
MAU_NEN = (18, 18, 24)
MAU_SONG = (255, 200, 87)


def _thu_muc(chi_muc_dir=None):
    d = os.path.join(chi_muc_dir or chung.duong("kho_chi_muc"), "xem-truoc")
    os.makedirs(d, exist_ok=True)
    return d


def _moi(dich, nguon):
    """dich đã có và mới hơn nguồn?"""
    try:
        return os.path.getsize(dich) > 0 and os.path.getmtime(dich) >= os.path.getmtime(nguon)
    except OSError:
        return False


def _ff():
    return chung.duong("ffmpeg")


def _esc(p):
    """escape đường dẫn cho tham số filter ffmpeg"""
    return p.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


# ----------------------------------------------------------------------------- font
def _font_png(muc, dich):
    import skia
    tf = skia.Typeface.MakeFromFile(muc["duong"])
    if tf is None:
        raise RuntimeError("skia không đọc được font")
    W, H = 900, 220
    surf = skia.Surface(W, H)
    c = surf.getCanvas()
    c.clear(skia.Color(*MAU_NEN))
    so_do = muc.get("so_do", {})
    ho = so_do.get("ho") or muc["ten"]
    kieu = so_do.get("kieu") or ""
    dong1 = ho if not kieu or kieu.lower() == "regular" else f"{ho} {kieu}"

    def ve(text, y, co, mau):
        font = skia.Font(tf, co)
        font.setSubpixel(True)
        w = font.measureText(text)
        if w > W - 60:
            co = max(18, co * (W - 60) / w)
            font = skia.Font(tf, co)
        paint = skia.Paint(AntiAlias=True, Color=mau)
        c.drawString(text, 30, y, font, paint)

    ve(dong1, 82, 58, skia.Color(255, 255, 255))
    ve(CAU_MAU, 172, 44, skia.Color(255, 220, 140))
    # nhãn nhỏ bằng font hệ thống
    tf2 = skia.Typeface("Segoe UI") or skia.Typeface.MakeDefault()
    f2 = skia.Font(tf2, 15)
    nhan = f"{muc['ten']}  ·  {so_do.get('dam', '')}" + ("  ·  nghiêng" if so_do.get("nghieng") else "") + ("  ·  variable" if so_do.get("var") else "")
    c.drawString(nhan, 30, 206, f2, skia.Paint(AntiAlias=True, Color=skia.Color(120, 125, 140)))
    img = surf.makeImageSnapshot()
    img.save(dich, skia.kPNG)
    return dich


# ----------------------------------------------------------------------------- lut
def mau_anh(chi_muc_dir=None):
    """ảnh mẫu 480×270 cho LUT: chụp giây 12 của clip mẫu (1 lần); không có clip → testsrc2 + gradient"""
    d = _thu_muc(chi_muc_dir)
    p = os.path.join(d, "_mau.jpg")
    if os.path.isfile(p) and os.path.getsize(p) > 0:
        return p
    if os.path.isfile(clip_mau()):
        ma, _, err = chung.sh([_ff(), "-v", "error", "-y", "-ss", "12", "-i", clip_mau(), "-frames:v", "1",
                               "-vf", "scale=480:-2,crop=480:270:0:'max(0,(ih-270)*0.28)'", "-q:v", "2", p], timeout=120)
        if ma == 0 and os.path.isfile(p):
            return p
    chung.sh([_ff(), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=480x270:rate=1", "-frames:v", "1", "-q:v", "2", p], timeout=60)
    return p


def _lut_jpg(muc, dich, chi_muc_dir=None):
    mau = mau_anh(chi_muc_dir)
    fc = f"[0:v]split[a][b];[b]lut3d='{_esc(muc['duong'])}'[c];[a]crop=iw/2:ih:0:0[l];[c]crop=iw/2:ih:iw/2:0[r];[l][r]hstack"
    ma, _, err = chung.sh([_ff(), "-v", "error", "-y", "-i", mau, "-filter_complex", fc, "-q:v", "3", dich], timeout=120)
    if ma != 0 or not os.path.isfile(dich):
        raise RuntimeError("lut3d lỗi: " + err.strip()[-200:])
    return dich


# ----------------------------------------------------------------------------- âm thanh
def _pcm(p, giay=None, sr=8000):
    cmd = [_ff(), "-v", "error"] + (["-t", str(giay)] if giay else []) + ["-i", p, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
    e = dict(os.environ); e.setdefault("PYTHONUTF8", "1")
    r = subprocess.run(cmd, capture_output=True, timeout=120, env=e, creationflags=chung._NO_WINDOW)
    return r.stdout


def _song_png(muc, dich):
    import numpy as np
    from PIL import Image, ImageDraw
    pcm = _pcm(muc["duong"], 30 if muc["loai"] == "nhac" else None)
    x = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
    W, H, COT = 600, 80, 200
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    if len(x) > 0:
        n = len(x) // COT or 1
        x = x[:n * COT] if len(x) >= COT else np.pad(x, (0, COT - len(x)))
        seg = x.reshape(COT, -1) if len(x) >= COT else x.reshape(COT, 1)
        mx = np.abs(seg).max(1)
        rms = np.sqrt((seg ** 2).mean(1))
        dinh = max(float(mx.max()), 1e-4)
        mx = mx / dinh; rms = rms / dinh
        bw = W / COT
        for i in range(COT):
            cx = i * bw
            h1 = max(1.5, mx[i] * (H / 2 - 2))
            h2 = max(1.0, rms[i] * (H / 2 - 2))
            dr.rectangle([cx + 0.5, H / 2 - h1, cx + bw - 1, H / 2 + h1], fill=MAU_SONG + (120,))
            dr.rectangle([cx + 0.5, H / 2 - h2, cx + bw - 1, H / 2 + h2], fill=MAU_SONG + (255,))
    else:
        dr.line([0, H / 2, W, H / 2], fill=MAU_SONG + (90,), width=1)
    im.save(dich)
    return dich


def nghe(muc, chi_muc_dir=None):
    """file nghe thử (mp3 64k): nhạc 30 s đầu; sfx giữ nguyên nếu < 1 MB và là mp3/wav phát được, không thì chuyển mp3"""
    p = muc["duong"]
    duoi = os.path.splitext(p)[1].lower()
    if muc["loai"] == "sfx" and os.path.getsize(p) < 1_000_000 and duoi in (".mp3", ".wav", ".aac", ".m4a", ".ogg"):
        return p
    dich = os.path.join(_thu_muc(chi_muc_dir), muc["id"] + ".nghe.mp3")
    if _moi(dich, p):
        return dich
    cmd = [_ff(), "-v", "error", "-y", "-i", p] + (["-t", "30"] if muc["loai"] == "nhac" else []) + ["-vn", "-ac", "2", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "64k", dich]
    ma, _, err = chung.sh(cmd, timeout=120)
    if ma != 0:
        raise RuntimeError("chuyển mp3 lỗi: " + err.strip()[-200:])
    return dich


# ----------------------------------------------------------------------------- video / nền
def _khung_jpg(muc, dich):
    dur = float(muc.get("so_do", {}).get("dur") or 0)
    ss = "1" if dur >= 1.5 else "0"
    ma, _, err = chung.sh([_ff(), "-v", "error", "-y", "-ss", ss, "-i", muc["duong"], "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "4", dich], timeout=120)
    if ma != 0 or not os.path.isfile(dich):
        # video alpha / lạ: thử không -ss
        ma, _, err = chung.sh([_ff(), "-v", "error", "-y", "-i", muc["duong"], "-frames:v", "1", "-vf", "scale=480:-2,format=yuvj420p", "-q:v", "4", dich], timeout=120)
        if ma != 0:
            raise RuntimeError("khung jpg lỗi: " + err.strip()[-200:])
    return dich


def thu(muc, chi_muc_dir=None):
    """mp4 xem thử 480p, 4 s đầu, không tiếng (h264 nhanh)"""
    p = muc["duong"]
    dich = os.path.join(_thu_muc(chi_muc_dir), muc["id"] + ".thu.mp4")
    if _moi(dich, p):
        return dich
    sd = muc.get("so_do", {})
    w, h = int(sd.get("w") or 0), int(sd.get("h") or 0)
    scale = "scale=-2:480" if h > w else "scale=480:-2"
    vf = scale + ",format=yuv420p"
    ma, _, err = chung.sh([_ff(), "-v", "error", "-y", "-t", "4", "-i", p, "-an", "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
                           "-movflags", "+faststart", dich], timeout=180)
    if ma != 0:
        raise RuntimeError("mp4 xem thử lỗi: " + err.strip()[-200:])
    return dich


# ----------------------------------------------------------------------------- ảnh
def _thumb(muc, dich, canh, giu_alpha):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(muc.get("bia") or muc["duong"]) as im:
        im.load()
        if giu_alpha and (im.mode in ("RGBA", "LA", "P")):
            im = im.convert("RGBA")
            im.thumbnail((canh, canh), Image.LANCZOS)
            im.save(dich, "PNG", optimize=True)
        else:
            im = im.convert("RGB")
            w, h = im.size
            if w > canh:
                im = im.resize((canh, max(1, round(h * canh / w))), Image.LANCZOS)
            im.save(dich, "JPEG", quality=82)
    return dich


# ----------------------------------------------------------------------------- điều phối
def tao(muc, ep=False, chi_muc_dir=None):
    """→ đường dẫn ảnh xem trước (tạo nếu chưa có / nguồn mới hơn) hoặc None nếu loại không có ảnh"""
    loai = muc.get("loai")
    nguon = muc.get("bia") or muc["duong"]
    d = _thu_muc(chi_muc_dir)
    mid = muc["id"]
    if loai == "font":
        dich = os.path.join(d, mid + ".png")
        return dich if _moi(dich, nguon) else _font_png(muc, dich)
    if loai == "lut":
        dich = os.path.join(d, mid + ".jpg")
        return dich if _moi(dich, nguon) else _lut_jpg(muc, dich, chi_muc_dir)
    if loai in ("nhac", "sfx"):
        dich = os.path.join(d, mid + ".png")
        if not _moi(dich, nguon):
            _song_png(muc, dich)
        if ep:
            nghe(muc, chi_muc_dir)
        return dich
    if loai in ("nen", "video"):
        duoi = os.path.splitext(muc["duong"])[1].lower()
        if duoi in (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"):
            alpha = bool(muc.get("so_do", {}).get("alpha"))
            dich = os.path.join(d, mid + (".png" if alpha else ".jpg"))
            return dich if _moi(dich, nguon) else _thumb(muc, dich, 480, alpha)
        dich = os.path.join(d, mid + ".jpg")
        if not _moi(dich, nguon):
            _khung_jpg(muc, dich)
        if ep:
            thu(muc, chi_muc_dir)
        return dich
    if loai == "icon":
        dich = os.path.join(d, mid + ".png")
        return dich if _moi(dich, nguon) else _thumb(muc, dich, 240, True)
    if loai in ("anh", "preset_capcut"):
        if loai == "preset_capcut" and not muc.get("bia"):
            return None
        alpha = bool(muc.get("so_do", {}).get("alpha"))
        dich = os.path.join(d, mid + (".png" if alpha else ".jpg"))
        return dich if _moi(dich, nguon) else _thumb(muc, dich, 480, alpha)
    return None


if __name__ == "__main__":
    from kho import tim
    for mid in sys.argv[1:]:
        m = tim.lay(mid)
        print(mid, "→", tao(m, ep=True) if m else "không có")
