# -*- coding: utf-8 -*-
"""GẮN NGHĨA KHO bằng AI — một lần, có cache, chạy lại chỉ làm mục mới/đổi.

Vì sao: tên file kho là tiếng Anh/viết tắt ("RH-SWOOSH2", "img029") nên tra theo nghĩa tiếng Việt trượt, AI đạo diễn
không "thấy" kho và chỉ dùng vài món. Bước này cho Claude NHÌN (bảng ảnh) hoặc ĐỌC (danh sách âm thanh + số đo) để gắn:
  mo_ta (tiếng Việt ngắn) · tu_khoa [5–12, Việt + Anh] · cam_xuc [] · cong_dung [] · phong_cach [] · mau_chu_dao ·
  nang_luong 1–5 · hop_khung doc|ngang|ca_hai  (font thêm hop_vai [tieu_de|nhan|phu_de] · de_doc 1–5)

Cách gọi AI: Claude Code CLI không tương tác (đã đăng nhập sẵn):
  claude -p "<lệnh>" --output-format json --allowedTools "Read,Write" --add-dir <thư mục bảng> --model <m> ...
  (dữ liệu dài đi qua stdin; mô hình Read ảnh bảng; trả JSON trong `result`; chi phí đọc từ `total_cost_usd`).

Nhóm việc (ưu tiên theo thứ tự): icon → nen (ảnh/video nền, lớp phủ ánh sáng) → font → sfx (gói kèm + "Trending" + phổ biến
trước) → lut → nhac → video.  Hình: bảng 5×6 có số thứ tự + tên tệp (font 3×8 vì ảnh mẫu dài). Âm thanh: lô 150 dòng
(thư mục + tên + dài/LUFS/BPM/đỉnh + đo thêm rẻ trên 3 s: độ sáng phổ Hz, độ dốc tấn công ms).

Lưu (1.2.21): bảng `ai_nghia` trong kho-chi-muc/kho.sqlite {id: {"dau": size-mtime, "ai": {...}, "do": {...}}} — upsert từng mục
(kho/csdl.py; trước là ai-nghia.json ghi cả tệp) → gắn vào bảng `muc` (trường "ai", số đo âm thêm vào so_do).
Nhật ký chi phí: kho-chi-muc/ai-chi-phi.jsonl (xoay khi > 1 MB → .1). Bảng ảnh: kho-chi-muc/bang-ai/ — xoá ngay sau khi gắn nghĩa xong.

    python v3/kho/gan_nghia.py --uoc                    # chỉ ước số lượt + chi phí
    python v3/kho/gan_nghia.py --ngan-sach 3            # chạy thật (dừng trước khi vượt ngân sách USD)
    python v3/kho/gan_nghia.py --loai icon,nen --toi-da 2 --song-song 3
"""
import os, sys, re, json, time, math, shutil, threading, subprocess, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung
from kho import lap as _lap

THU_TU = ["icon", "nen", "font", "sfx", "lut", "nhac", "video"]
MODEL_MAC_DINH = {"icon": "sonnet", "nen": "sonnet", "video": "haiku", "font": "haiku", "lut": "haiku", "sfx": "haiku", "nhac": "haiku"}
UOC_USD = {("sonnet", "hinh"): 0.08, ("haiku", "hinh"): 0.03, ("sonnet", "chu"): 0.35, ("haiku", "chu"): 0.14,
           ("opus", "hinh"): 0.15, ("opus", "chu"): 0.5}        # đo thật 23/10 (tắt thinking): sonnet bảng 30 ô ≈ 0,08–0,10 · haiku lô 150 âm ≈ 0,13
LO_AM = 100
LUOI = {"hinh": (5, 6), "font": (3, 8)}
CONG_DUNG_SFX = ["chữ hiện ra", "thẻ bật", "chuyển cảnh", "nhấn số liệu", "hook mở đầu", "kết", "dâng trước cao trào", "đập nhấn",
                 "gõ phím", "thông báo", "đúng/thành công", "sai/lỗi", "tiền", "chụp ảnh", "đếm/tích tắc", "hài hước", "căng thẳng",
                 "không khí nền", "giao diện bấm"]
CONG_DUNG_NHAC = ["nhạc nền talking head", "nhạc hook mở đầu", "nhạc kết", "nhạc quảng cáo sản phẩm", "nhạc vlog", "nhạc kể chuyện",
                  "nhạc hài", "nhạc kịch tính", "nhạc cảm động", "nhạc sôi động/nhảy"]
CONG_DUNG_HINH = ["nền cảnh trám", "nền sau người (tách nền)", "nền thẻ/khối chữ", "lớp phủ ánh sáng", "lớp phủ chuyển cảnh",
                  "lớp phủ kết cấu", "khung/viền", "nhân vật biểu cảm", "minh hoạ khái niệm", "icon minh hoạ từ '<từ>'"]

_khoa = threading.Lock()
_NO = chung._NO_WINDOW


# ----------------------------------------------------------------------------- đường dẫn
def _dm():
    return chung.duong("kho_chi_muc")


def _p_cache():
    """(giữ cho mã cũ tham chiếu) — cache nay nằm trong bảng ai_nghia của kho.sqlite"""
    return os.path.join(_dm(), "ai-nghia.json")


CHI_PHI_TOI_DA = 1_000_000       # byte: ai-chi-phi.jsonl vượt → xoay sang .1 (giữ 1 bản cũ)


def _p_chi_phi():
    return os.path.join(_dm(), "ai-chi-phi.jsonl")


def _thu_bang():
    d = os.path.join(_dm(), "bang-ai")
    os.makedirs(d, exist_ok=True)
    return d


def _claude_exe():
    """đường tới claude.exe thật (tránh .cmd: cmd.exe phá tham số dài/có xuống dòng)"""
    c = (chung.cau_hinh().get("ai") or {}).get("claude") or ""
    if c and os.path.isfile(c):
        return c
    w = shutil.which("claude")
    if not w:
        raise RuntimeError("không thấy lệnh claude (Claude Code CLI) trong PATH")
    if w.lower().endswith((".cmd", ".bat", ".ps1")) or not os.path.splitext(w)[1]:
        d = os.path.dirname(w)
        exe = os.path.join(d, "node_modules", "@anthropic-ai", "claude-code", "bin", "claude.exe")
        if os.path.isfile(exe):
            return exe
        w2 = shutil.which("claude.exe")
        if w2:
            return w2
    return w


def _model(loai):
    ai = chung.cau_hinh().get("ai") or {}
    ghi = ai.get("model_gan_nghia") or {}
    if isinstance(ghi, str):
        return ghi
    return ghi.get(loai) or MODEL_MAC_DINH.get(loai, "haiku")


# ----------------------------------------------------------------------------- cache
def doc_cache():
    from kho import csdl
    return csdl.ai_nghia_tat_ca()


def _ghi_cache(cache, ids=None):
    """1.2.21: upsert vào bảng ai_nghia CHỈ các id vừa đổi (ids); không ghi cả tệp. ids=None → upsert hết (chỉ khi nhập tay)."""
    from kho import csdl
    ds = {k: cache[k] for k in (ids if ids is not None else cache) if k in cache}
    return csdl.upsert_ai_nghia(ds) if ds else 0


def _nhat_ky_chi_phi(d):
    with _khoa:
        p = _p_chi_phi()
        try:                                     # 1.2.21: xoay 1 MB (append vô hạn → rác)
            if os.path.isfile(p) and os.path.getsize(p) > CHI_PHI_TOI_DA:
                os.replace(p, p + ".1")
        except OSError:
            pass
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")


def tong_chi_phi():
    t = 0.0
    for p in (_p_chi_phi(), _p_chi_phi() + ".1"):
        for d in chung.doc_jsonl(p):
            t += float(d.get("usd") or 0)
    return t


# ----------------------------------------------------------------------------- chọn việc
_PHO_BIEN = ("whoosh", "swoosh", "swish", "pop", "click", "ding", "bell", "riser", "impact", "hit", "transition", "glitch", "typing",
             "notification", "cash", "money", "camera", "shutter", "boom", "bass", "drop", "tick", "clock", "vut", "bup", "chuong",
             "dam", "dang len", "go phim", "subdrop", "trending", "chuyen", "xuat hien")


def _uu_tien(m):
    """khoá sắp: gói kèm trước, rồi 'Trending', rồi tên/thư mục chứa từ phổ biến, rồi ngắn"""
    ten = chung.khong_dau(m.get("rel", ""))
    g = 0 if m.get("goc") == "goi_kem" else 1
    tr = 0 if "trending" in ten else 1
    pb = 0 if any(k in ten for k in _PHO_BIEN) else 1
    return (g, tr, pb, ten)


def can_gan(muc, cache, loai_ds=None):
    """→ {loai: [muc...]} mục cần gắn (chưa có cache đúng dấu vân tay)"""
    ra = {}
    for m in muc:
        l = m.get("loai")
        if l not in THU_TU or (loai_ds and l not in loai_ds):
            continue
        if l == "nen" or l == "video":
            pass
        c = cache.get(m["id"])
        if c and c.get("dau") == _lap.dau_muc(m) and c.get("ai"):
            continue
        ra.setdefault(l, []).append(m)
    for l in ra:
        ra[l].sort(key=_uu_tien if l in ("sfx", "nhac") else (lambda m: chung.khong_dau(m.get("rel", ""))))
    return ra


def ho_bien_the(m):
    """khoá họ biến thể: cùng loại + thư mục (bỏ mp3/wav) + tên bỏ số đuôi/định dạng/copy → 'notification-alerts-01..100' là 1 họ"""
    t = chung.khong_dau(m.get("ten", ""))
    t = re.sub(r"[\(\[]?\b(mp3|wav|copy|ban sao|final)\b[\)\]]?", " ", t)
    t = re.sub(r"[\s_\-.#]*\(?\d+\)?\s*$", "", t)
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    tm = "/".join(x for x in (m.get("rel") or "").split("/")[:-1] if chung.khong_dau(x) not in ("mp3", "wav"))
    return (m.get("loai"), m.get("goc", "bo_mua"), tm, t)


def _ho_am(muc_loai, cache):
    """→ (ho_can_gan: list[list[muc]], ke_thua: list[(muc, id_nguon)]) — họ đã có 1 thành viên được gắn thì thành viên khác kế thừa"""
    ho = {}
    for m in muc_loai:
        ho.setdefault(ho_bien_the(m), []).append(m)
    can, ke = [], []
    for k, ds in ho.items():
        co = [m for m in ds if (cache.get(m["id"]) or {}).get("ai") and cache[m["id"]].get("dau") == _lap.dau_muc(m)]
        chua = [m for m in ds if m not in co]
        if not chua:
            continue
        if co:
            ke.extend((m, co[0]["id"]) for m in chua)
        else:
            can.append(chua)
    can.sort(key=lambda ds: _uu_tien(ds[0]))
    return can, ke


def _chia(ds, k):
    return [ds[i:i + k] for i in range(0, len(ds), k)]


def ke_hoach(muc, cache, loai_ds=None, ke_thua=None):
    """→ list việc [{"loai","kieu":hinh|chu,"muc":[...]}] theo thứ tự ưu tiên. Âm thanh: mỗi phần tử "muc" là 1 HỌ (list mục).
    ke_thua (list) nhận [(muc, id_nguồn)] cho mục chỉ cần chép nghĩa từ anh em cùng họ."""
    ra = []
    can = can_gan(muc, cache, loai_ds)
    for l in THU_TU:
        ds = can.get(l) or []
        if not ds:
            continue
        if l in ("sfx", "nhac"):
            ids = {m["id"] for m in ds}
            ho, ke = _ho_am(ds + [m for m in muc if m.get("loai") == l and m["id"] not in ids and (cache.get(m["id"]) or {}).get("ai")], cache)
            if ke_thua is not None:
                ke_thua.extend(ke)
            for lo in _chia(ho, LO_AM):
                ra.append({"loai": l, "kieu": "chu", "muc": lo})
        else:
            c, h = LUOI["font"] if l == "font" else LUOI["hinh"]
            for lo in _chia(ds, c * h):
                ra.append({"loai": l, "kieu": "hinh", "muc": lo})
    return ra


def uoc(viec):
    tong, theo = 0.0, {}
    for v in viec:
        md = _model(v["loai"])
        k = (md if md in ("sonnet", "haiku", "opus") else "sonnet", v["kieu"])
        u = UOC_USD.get(k, 0.1)
        tong += u
        t = theo.setdefault(v["loai"], {"luot": 0, "muc": 0, "usd": 0.0, "model": md})
        t["luot"] += 1; t["muc"] += sum(len(x) if isinstance(x, list) else 1 for x in v["muc"]); t["usd"] = round(t["usd"] + u, 3)
    return round(tong, 2), theo


# ----------------------------------------------------------------------------- bảng ảnh
def _font_nhan(co):
    from PIL import ImageFont
    for p in (os.path.join(chung.duong("font_mac_dinh"), "BeVietnamPro-Bold.ttf"), "C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(p, co)
        except Exception:
            pass
    return ImageFont.load_default()


def _caro(w, h, o=16):
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (w, h), (58, 58, 64))
    d = ImageDraw.Draw(im)
    for y in range(0, h, o):
        for x in range(0, w, o):
            if (x // o + y // o) % 2:
                d.rectangle([x, y, x + o - 1, y + o - 1], fill=(84, 84, 92))
    return im


def _la_video(m):
    return os.path.splitext(m.get("duong", ""))[1].lower() in (".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi")


def _khung_video(m, w, h):
    """2 khung (25 % và 65 % thời lượng) đặt cạnh nhau trên nền caro (video alpha) — cache xem-truoc/<id>.hai.png"""
    from PIL import Image
    d = os.path.join(_dm(), "xem-truoc")
    os.makedirs(d, exist_ok=True)
    dich = os.path.join(d, m["id"] + ".hai.png")
    if not (os.path.isfile(dich) and os.path.getmtime(dich) >= os.path.getmtime(m["duong"])):
        dur = float((m.get("so_do") or {}).get("dur") or 0) or 4.0
        anh = []
        for i, f in enumerate((0.25, 0.65)):
            tam = os.path.join(d, f"_{m['id']}.{i}.png")
            chung.sh([chung.duong("ffmpeg"), "-v", "error", "-y", "-ss", f"{dur * f:.2f}", "-i", m["duong"], "-frames:v", "1",
                      "-vf", "scale=320:-2:flags=bilinear,format=rgba", tam], timeout=120)
            if os.path.isfile(tam):
                with Image.open(tam) as im:
                    anh.append(im.convert("RGBA"))
                os.remove(tam)
        if not anh:
            return None
        W = sum(a.width for a in anh) + 6 * (len(anh) - 1)
        H = max(a.height for a in anh)
        nen = _caro(W, H).convert("RGBA")
        x = 0
        for a in anh:
            nen.alpha_composite(a, (x, 0))
            x += a.width + 6
        nen.convert("RGB").save(dich)
    from PIL import Image as I2
    with I2.open(dich) as im:
        return im.convert("RGB").copy()


def _anh_o(m):
    """ảnh đại diện 1 mục cho ô bảng → PIL RGB/RGBA hoặc None"""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    l = m["loai"]
    if l in ("nen", "video") and _la_video(m):
        return _khung_video(m, 0, 0)
    try:
        from kho import xem_truoc
        p = xem_truoc.tao(m)
    except Exception:
        p = None
    nguon = p or (m["duong"] if l in ("icon", "nen", "anh") else None)
    if not nguon or not os.path.isfile(nguon):
        return None
    with Image.open(nguon) as im:
        im.load()
        return im.convert("RGBA") if im.mode in ("RGBA", "LA", "P") else im.convert("RGB")


def dung_bang(muc, kieu_luoi, dich, o_w=None, o_h=None):
    """bảng lưới có số thứ tự + tên tệp → dich (jpg). kieu_luoi: 'hinh' 5×6 ô vuông | 'font' 3×8 ô dài"""
    from PIL import Image, ImageDraw
    cot, hang = LUOI[kieu_luoi]
    if kieu_luoi == "font":
        o_w, o_h = o_w or 600, o_h or 146
    else:
        o_w, o_h = o_w or 256, o_h or 256
    nhan_h = 30
    pad = 6
    W, H = cot * (o_w + pad) + pad, math.ceil(len(muc) / cot) * (o_h + nhan_h + pad) + pad
    bang = Image.new("RGB", (W, H), (24, 24, 28))
    dr = ImageDraw.Draw(bang)
    f1, f2 = _font_nhan(20), _font_nhan(15)
    for i, m in enumerate(muc):
        r, c = divmod(i, cot)
        x0, y0 = pad + c * (o_w + pad), pad + r * (o_h + nhan_h + pad)
        try:
            a = _anh_o(m)
        except Exception:
            a = None
        o = Image.new("RGB", (o_w, o_h), (40, 40, 46))
        if a is not None:
            a = a.copy()
            a.thumbnail((o_w, o_h), Image.LANCZOS)
            xx, yy = (o_w - a.width) // 2, (o_h - a.height) // 2
            if a.mode == "RGBA":
                ca = _caro(a.width, a.height).convert("RGBA"); ca.alpha_composite(a)
                o.paste(ca.convert("RGB"), (xx, yy))
            else:
                o.paste(a, (xx, yy))
        else:
            ImageDraw.Draw(o).text((10, o_h // 2 - 10), "(không xem được)", font=f2, fill=(200, 120, 120))
        bang.paste(o, (x0, y0))
        so = f"#{i + 1}"
        dr.rectangle([x0, y0 + o_h, x0 + o_w, y0 + o_h + nhan_h], fill=(12, 12, 14))
        dr.text((x0 + 4, y0 + o_h + 4), so, font=f1, fill=(255, 210, 0))
        ten = m["ten"]
        sw = dr.textlength(so + " ", font=f1)
        while ten and dr.textlength(ten, font=f2) > o_w - sw - 8:
            ten = ten[:-2]
        dr.text((x0 + 4 + sw, y0 + o_h + 8), ten if ten == m["ten"] else ten + "…", font=f2, fill=(225, 225, 230))
    bang.save(dich, quality=86)
    return dich


# ----------------------------------------------------------------------------- đo âm thêm (rẻ)
def do_am_them(m):
    """3 s (sfx: đầu file; nhạc: từ 25 % bài) → {"pho_hz": trọng tâm phổ, "tan_cong_ms": thời gian tới đỉnh bao, "dot_ngot": dB/10ms}"""
    import numpy as np
    dur = float((m.get("so_do") or {}).get("dur") or 0)
    ss = max(0.0, min(dur * 0.25, dur - 3.0)) if m["loai"] == "nhac" and dur > 6 else 0.0
    sr = 22050
    cmd = [chung.duong("ffmpeg"), "-v", "error", "-ss", f"{ss:.2f}", "-t", "3", "-i", m["duong"], "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"]
    e = dict(os.environ); e.setdefault("PYTHONUTF8", "1")
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=60, env=e, creationflags=_NO)
    except Exception:
        return {}
    x = np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0
    if len(x) < sr // 20:
        return {}
    ra = {}
    n = 2048
    if len(x) >= n:
        k = len(x) // n
        fr = x[:k * n].reshape(k, n) * np.hanning(n)
        mag = np.abs(np.fft.rfft(fr, axis=1))
        en = mag.sum(1)
        song = en > (en.max() * 0.05)
        if song.any():
            f = np.fft.rfftfreq(n, 1 / sr)
            c = (mag[song] * f).sum(1) / np.maximum(mag[song].sum(1), 1e-9)
            ra["pho_hz"] = int(np.median(c))
    hop = int(sr * 0.01)
    k = len(x) // hop
    if k >= 3:
        env = np.sqrt((x[:k * hop].reshape(k, hop) ** 2).mean(1)) + 1e-7
        db = 20 * np.log10(env)
        dinh = int(np.argmax(db))
        nguong = db[dinh] - 40
        dau = int(np.argmax(db > nguong))
        ra["tan_cong_ms"] = int((dinh - dau) * 10)
        dd = np.diff(db[dau:dinh + 1]) if dinh > dau else np.array([db[dinh] - nguong])
        ra["dot_ngot"] = round(float(dd.max()) if len(dd) else 0.0, 1)
    return ra


# ----------------------------------------------------------------------------- lời nhắc
SYS = ("Bạn là biên tập viên kho tài nguyên của một app dựng video TikTok/Reels tiếng Việt. Nhiệm vụ: gắn nghĩa ngắn gọn, "
       "chính xác cho từng tài nguyên để AI đạo diễn tra cứu bằng tiếng Việt. Chỉ trả về MỘT mảng JSON hợp lệ NGAY TRONG CÂU TRẢ LỜI "
       "(không markdown, không giải thích). TUYỆT ĐỐI KHÔNG dùng công cụ Write/ghi file — Read chỉ để mở ảnh. Tiếng Việt có dấu đầy đủ.")


def _de_hinh(loai, ten_bang, dong):
    if loai == "font":
        return (f"Dùng công cụ Read mở ảnh `{ten_bang}` (trong thư mục làm việc). Ảnh là bảng mẫu FONT, mỗi ô có số `#n` + tên tệp; "
                "dòng trên của ô là tên họ font viết bằng chính font đó, dòng dưới là câu tiếng Việt có dấu (ô vuông/thiếu dấu = font thiếu dấu).\n"
                "Thông tin thêm từng ô (đậm/nghiêng/đủ dấu do máy đo):\n" + dong + "\n\n"
                "Trả mảng JSON, MỖI ô một phần tử, đúng khoá: "
                '{"so":n,"mo_ta":"≤12 từ tiếng Việt","tu_khoa":[5-10 từ Việt+Anh],"phong_cach":["sans đậm|sans thường|serif|viết tay|trang trí|hẹp|tròn|mảnh|cổ điển|kỹ thuật số|..."],'
                '"hop_vai":["tieu_de","nhan","phu_de"] (chọn các vai hợp),"de_doc":1-5 (5 = đọc phụ đề trên điện thoại rất dễ),"cam_xuc":["..."]}')
    if loai == "lut":
        return (f"Dùng công cụ Read mở ảnh `{ten_bang}`. Ảnh là bảng LUT màu: mỗi ô là 1 khung hình chia đôi — TRÁI = gốc, PHẢI = sau khi áp LUT; "
                "dưới ô có số `#n` + tên tệp. LUT có chữ log/slog/s-log/apple log/rec709 trong tên là LUT CHUYỂN máy quay log → thường: "
                "ghi cong_dung \"chuyển log sang thường\" và đừng chấm theo ảnh (ảnh gốc không phải log).\nThông tin thêm:\n" + dong + "\n\n"
                "Trả mảng JSON, MỖI ô một phần tử: "
                '{"so":n,"mo_ta":"≤14 từ: tông màu sau khi áp","tu_khoa":[5-10 từ Việt+Anh],"cam_xuc":["..."],'
                '"cong_dung":["chỉnh màu da ấm","điện ảnh","vlog sáng","tối kịch tính","chuyển log sang thường",...],"phong_cach":["..."],'
                '"mau_chu_dao":"tên màu tiếng Việt","nang_luong":1-5}')
    loai_txt = {"icon": "ICON / NHÂN VẬT (PNG nền trong suốt hiển thị trên caro)", "nen": "NỀN / LỚP PHỦ (ảnh tĩnh hoặc video; video hiện 2 khung cạnh nhau)",
                "video": "VIDEO", "anh": "ẢNH"}.get(loai, loai)
    return (f"Dùng công cụ Read mở ảnh `{ten_bang}` (trong thư mục làm việc). Ảnh là bảng {loai_txt}; mỗi ô có số `#n` + tên tệp. "
            "Nền caro = vùng trong suốt (lớp phủ alpha).\nThông tin thêm từng ô (kích thước, video/ảnh, alpha):\n" + dong + "\n\n"
            "Trả mảng JSON, MỖI ô một phần tử, đúng khoá: "
            '{"so":n,"mo_ta":"≤14 từ tiếng Việt, nói rõ thấy gì","tu_khoa":[5-12 từ Việt+Anh, gồm vật thể/cảm xúc/màu],"cam_xuc":["..."],'
            '"cong_dung":[chọn/viết theo mẫu: ' + ", ".join(f'"{x}"' for x in CONG_DUNG_HINH) + '],'
            '"phong_cach":["neon","giấy","tối giản","hoạt hình","3D","phim cũ","công nghệ",...],"mau_chu_dao":"tên màu tiếng Việt",'
            '"nang_luong":1-5,"hop_khung":"doc|ngang|ca_hai"}. hop_khung theo tỉ lệ + bố cục (nền ngang vẫn có thể "ca_hai" nếu cắt dọc được).')


def _de_am(loai, dong):
    if loai == "nhac":
        cd = ", ".join(f'"{x}"' for x in CONG_DUNG_NHAC)
        mo = "NHẠC NỀN (không nghe được: suy từ thư mục, tên, số đo — BPM, LUFS, độ sáng phổ Hz ở đoạn 25 % bài)"
    else:
        cd = ", ".join(f'"{x}"' for x in CONG_DUNG_SFX)
        mo = ("HIỆU ỨNG ÂM (SFX) (không nghe được: suy từ thư mục, tên, số đo — dài, đỉnh dB, độ sáng phổ Hz [cao = chói/sắc, thấp = trầm], "
              "tấn công ms [nhỏ = bật/đập ngay, lớn = dâng dần])")
    return (f"Dữ liệu stdin là danh sách {mo}. Mỗi dòng: `#n | thư mục | tên | số đo`.\n"
            "Trả mảng JSON, MỖI dòng một phần tử (đủ mọi #n), đúng khoá: "
            '{"so":n,"mo_ta":"≤12 từ tiếng Việt: nghe như thế nào","tu_khoa":[5-10 từ Việt+Anh],"cam_xuc":["..."],'
            f'"cong_dung":[1-4 mục, ưu tiên đúng các nhãn: {cd}],"nang_luong":1-5}}. '
            "Không bịa: nếu tên mơ hồ thì dựa vào thư mục + số đo, mô tả thận trọng.")


def _dong_hinh(muc):
    ra = []
    for i, m in enumerate(muc):
        sd = m.get("so_do") or {}
        bits = [f"#{i + 1}", m["ten"]]
        if m["loai"] == "font":
            bits += [f"đậm {sd.get('dam', '?')}", "nghiêng" if sd.get("nghieng") else "", "đủ dấu" if sd.get("du_dau") else "THIẾU DẤU", sd.get("ho", "")]
        else:
            if sd.get("w"):
                bits.append(f"{sd['w']}x{sd['h']}")
            if _la_video(m):
                bits.append(f"video {sd.get('dur', 0):.0f}s")
            if sd.get("alpha"):
                bits.append("alpha")
            bits.append("/".join((m.get("rel") or "").split("/")[-3:-1]))
        ra.append(" | ".join(b for b in bits if b))
    return "\n".join(ra)


def _khoang(vals, fmt):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    a, b = min(vals), max(vals)
    return fmt(a) if fmt(a) == fmt(b) else f"{fmt(a)}–{fmt(b)}"


def _dong_am(ho_ds):
    """ho_ds: list họ (list mục). Họ nhiều biến thể ghi 1 dòng kèm số biến thể + khoảng số đo"""
    ra = []
    for i, ho in enumerate(ho_ds):
        ho = ho if isinstance(ho, list) else [ho]
        m = ho[0]
        sds = [x.get("so_do") or {} for x in ho]
        tm = "/".join([p for p in (m.get("rel") or "").split("/")[:-1] if chung.khong_dau(p) not in ("mp3", "wav")][-2:])
        so = []
        d = _khoang([float(s["dur"]) for s in sds if s.get("dur") is not None],
                    lambda d: f"{int(d // 60)}:{int(d % 60):02d}" if d >= 60 else f"{d:.1f}s")
        for v in (d,
                  _khoang([s.get("bpm") for s in sds], lambda x: f"{x}BPM"),
                  _khoang([s.get("lufs") for s in sds], lambda x: f"{x}LUFS"),
                  _khoang([s.get("peak") for s in sds], lambda x: f"đỉnh {x}dB"),
                  _khoang([s.get("pho_hz") for s in sds], lambda x: f"phổ {x}Hz"),
                  _khoang([s.get("tan_cong_ms") for s in sds], lambda x: f"tấn công {x}ms")):
            if v:
                so.append(v)
        ten = m["ten"] if len(ho) == 1 else f"{m['ten']} (+{len(ho) - 1} biến thể cùng họ)"
        ra.append(f"#{i + 1} | {tm} | {ten} | {' '.join(so)}")
    return "\n".join(ra)


# ----------------------------------------------------------------------------- gọi Claude
def goi_claude(lenh, stdin_txt, model, thu_muc, ngan_sach_luot=0.8, timeout=900):
    """→ (ket_qua_text, usd, giay, loi)"""
    exe = _claude_exe()
    cmd = [exe, "-p", lenh, "--output-format", "json", "--model", model,
           "--tools", "Read,Write", "--allowedTools", "Read,Write", "--add-dir", thu_muc,
           "--strict-mcp-config", "--no-session-persistence", "--system-prompt", SYS,
           "--max-budget-usd", str(ngan_sach_luot)]
    e = dict(os.environ); e.setdefault("PYTHONUTF8", "1"); e.setdefault("PYTHONIOENCODING", "utf-8")
    e.setdefault("MAX_THINKING_TOKENS", "0")          # việc gắn nhãn không cần suy nghĩ dài: tắt thinking ≈ −45 % chi phí
    t0 = time.time()
    try:
        r = subprocess.run(cmd, input=(stdin_txt or "").encode("utf-8"), capture_output=True, timeout=timeout, cwd=thu_muc, env=e,
                           creationflags=_NO)
    except subprocess.TimeoutExpired:
        return "", 0.0, time.time() - t0, "TIMEOUT"
    out = r.stdout.decode("utf-8", "replace")
    try:
        j = json.loads(out.strip().splitlines()[-1] if out.strip() else "{}")
    except Exception:
        try:
            j = json.loads(out)
        except Exception:
            return "", 0.0, time.time() - t0, "không đọc được JSON CLI: " + (out[-300:] or r.stderr.decode("utf-8", "replace")[-300:])
    usd = float(j.get("total_cost_usd") or 0)
    loi = None if not j.get("is_error") else (j.get("subtype") or "lỗi") + ": " + str(j.get("result") or "")[:200]
    return j.get("result") or "", usd, time.time() - t0, loi


def _tach_json(txt):
    txt = (txt or "").strip()
    txt = re.sub(r"^```(?:json)?|```$", "", txt, flags=re.M).strip()
    a, b = txt.find("["), txt.rfind("]")
    if a >= 0 and b > a:
        for thu in (txt[a:b + 1], re.sub(r",\s*([\]}])", r"\1", txt[a:b + 1])):
            try:
                ds = json.loads(thu)
                if isinstance(ds, list):
                    return [x for x in ds if isinstance(x, dict)]
            except Exception:
                pass
    return _tung_doi_tuong(txt)


def _cuu_tu_file(thu, t0):
    """file .json mô hình tự ghi vào thư mục bảng sau t0 → danh sách phần tử (file được đổi tên .da-cuu)"""
    ra = []
    for f in sorted(os.listdir(thu)):
        p = os.path.join(thu, f)
        if not f.lower().endswith(".json") or os.path.getmtime(p) < t0 - 1:
            continue
        try:
            txt = open(p, encoding="utf-8").read()
            ds = _tach_json(txt)
            if ds:
                ra.extend(ds)
                os.replace(p, p + ".da-cuu")
        except Exception:
            pass
    return ra


def _tung_doi_tuong(txt):
    """cứu từng {…} cấp 1 (mảng bị cắt cụt / 1 phần tử hỏng không làm mất cả lô)"""
    ra, sau, bat, i0, trong_chuoi, thoat = [], 0, False, 0, False, False
    for i, ch in enumerate(txt):
        if trong_chuoi:
            if thoat:
                thoat = False
            elif ch == "\\":
                thoat = True
            elif ch == '"':
                trong_chuoi = False
            continue
        if ch == '"':
            trong_chuoi = True
        elif ch == "{":
            if sau == 0:
                i0 = i
            sau += 1
        elif ch == "}" and sau > 0:
            sau -= 1
            if sau == 0:
                try:
                    x = json.loads(txt[i0:i + 1])
                    if isinstance(x, dict) and "so" in x:
                        ra.append(x)
                except Exception:
                    pass
    return ra


def _chuan(x, loai):
    """chuẩn hoá 1 phần tử AI trả về"""
    def ds(v, n=12):
        if isinstance(v, str):
            v = [v]
        return [chung.NFC(str(t)).strip() for t in (v or []) if str(t).strip()][:n]
    ai = {"mo_ta": chung.NFC(str(x.get("mo_ta") or "")).strip()[:160], "tu_khoa": ds(x.get("tu_khoa"), 14)}
    for k in ("cam_xuc", "cong_dung", "phong_cach", "hop_vai"):
        if x.get(k):
            ai[k] = ds(x.get(k), 6)
    if x.get("mau_chu_dao"):
        ai["mau_chu_dao"] = chung.NFC(str(x["mau_chu_dao"]))[:40]
    for k in ("nang_luong", "de_doc"):
        try:
            if x.get(k) is not None:
                ai[k] = max(1, min(5, int(round(float(x[k])))))
        except Exception:
            pass
    hk = chung.khong_dau(str(x.get("hop_khung") or ""))
    if hk:
        ai["hop_khung"] = "doc" if hk.startswith("doc") else "ngang" if hk.startswith("ngang") else "ca_hai"
    if "hop_vai" in ai:
        ai["hop_vai"] = [chung.khong_dau(v).replace(" ", "_") for v in ai["hop_vai"]]
    return ai


def lam_viec(v, so_viec, cache, ngan_sach_con):
    """chạy 1 việc (1 bảng ảnh hoặc 1 lô âm) → số mục đã gắn"""
    loai, muc = v["loai"], v["muc"]
    model = _model(loai)
    thu = _thu_bang()
    if v["kieu"] == "hinh":
        ten = f"{loai}-{so_viec:03d}.jpg"
        dung_bang(muc, "font" if loai == "font" else "hinh", os.path.join(thu, ten))
        lenh = _de_hinh(loai, ten, _dong_hinh(muc))
        stdin = ""
    else:
        phang = [m for ho in muc for m in ho]
        can_do = [m for m in phang if "pho_hz" not in (m.get("so_do") or {})]
        if can_do:
            with ThreadPoolExecutor(max_workers=6) as ex:
                for m, d in zip(can_do, ex.map(do_am_them, can_do)):
                    if d:
                        m.setdefault("so_do", {}).update(d)
                        m["_do"] = d
        lenh = _de_am(loai, "")
        stdin = _dong_am(muc)
    t_goi = time.time()
    kq, usd, giay, loi = goi_claude(lenh, stdin, model, thu, ngan_sach_luot=min(1.0, max(0.2, ngan_sach_con)))
    ds = _tach_json(kq)
    if not ds:                                          # mô hình lỡ ghi JSON ra file thay vì trả lời → cứu từ file
        ds = _cuu_tu_file(thu, t_goi)
    if len(ds) < len(muc) * 0.9:                       # giữ bản thô để xem vì sao thiếu
        try:
            with open(os.path.join(thu, f"tho-{loai}-{so_viec:03d}.txt"), "w", encoding="utf-8") as f:
                f.write(f"loi={loi}\n---LENH---\n{lenh}\n---STDIN---\n{stdin}\n---KQ---\n{kq}")
        except Exception:
            pass
    gan, moi = 0, []
    with _khoa:
        for x in ds:
            try:
                i = int(x.get("so")) - 1
            except Exception:
                continue
            if 0 <= i < len(muc):
                ai = _chuan(x, loai)
                if not ai.get("mo_ta"):
                    continue
                ai["model"] = model
                nhom = muc[i] if isinstance(muc[i], list) else [muc[i]]
                for j, m in enumerate(nhom):
                    a2 = dict(ai)
                    if len(nhom) > 1:
                        a2["bien_the"] = f"{j + 1}/{len(nhom)}"
                    rec = {"dau": _lap.dau_muc(m), "dau2": _lap.dau_goi(m), "ai": a2, "luc": time.strftime("%Y-%m-%d %H:%M")}
                    do = m.get("_do") or {k: (m.get("so_do") or {}).get(k) for k in ("pho_hz", "tan_cong_ms", "dot_ngot") if (m.get("so_do") or {}).get(k) is not None}
                    if do:
                        rec["do"] = do
                    cache[m["id"]] = rec
                    moi.append(m["id"])
                    gan += 1
        _ghi_cache(cache, moi)
    if v["kieu"] == "hinh" and gan >= len(muc) * 0.9:       # 1.2.21: bảng ảnh đã gắn xong → xoá (rác 14 MB+ trên máy anh)
        try:
            os.remove(os.path.join(thu, ten))
        except OSError:
            pass
    _nhat_ky_chi_phi({"luc": time.strftime("%Y-%m-%d %H:%M:%S"), "loai": loai, "kieu": v["kieu"], "so_muc": sum(len(x) if isinstance(x, list) else 1 for x in muc),
                      "so_dong": len(muc), "gan": gan,
                      "model": model, "usd": round(usd, 4), "giay": round(giay, 1), "loi": loi})
    return gan, usd, loi


def _ke_thua(ke, cache):
    moi = []
    with _khoa:
        for m, nguon in ke:
            c = cache.get(nguon) or {}
            if not c.get("ai"):
                continue
            ai = dict(c["ai"]); ai["ke_thua"] = nguon
            rec = {"dau": _lap.dau_muc(m), "dau2": _lap.dau_goi(m), "ai": ai, "luc": time.strftime("%Y-%m-%d %H:%M")}
            sd = m.get("so_do") or {}
            if "pho_hz" not in sd and m.get("loai") in ("sfx", "nhac"):
                d = do_am_them(m)
                if d:
                    rec["do"] = d
            cache[m["id"]] = rec
            moi.append(m["id"])
        _ghi_cache(cache, moi)


def ghi_chi_muc():
    """gắn cache ai_nghia → bảng muc (trường ai + so_do âm thêm): 1.2.21 upsert CHỈ mục đổi"""
    from kho import csdl
    muc = csdl.tat_ca()
    truoc = {m["id"]: json.dumps(m, ensure_ascii=False, sort_keys=True) for m in muc}
    _lap._gan_ai_cache(muc, _dm())
    doi = [m for m in muc if json.dumps(m, ensure_ascii=False, sort_keys=True) != truoc.get(m["id"])]
    if doi:
        csdl.upsert_muc(doi)
    cm = os.path.join(_dm(), "chi-muc.json")
    tk = chung.doc_json(cm, {}) or {}
    tk["co_ai"] = sum(1 for m in muc if m.get("ai"))
    tk["ai_theo_loai"] = {}
    for m in muc:
        if m.get("ai"):
            tk["ai_theo_loai"][m["loai"]] = tk["ai_theo_loai"].get(m["loai"], 0) + 1
    tk["ai_usd"] = round(tong_chi_phi(), 3)
    tk["upsert"] = len(doi)
    chung.ghi_json(cm, tk)
    return tk


def chay(ngan_sach=3.0, loai_ds=None, toi_da=None, song_song=3, chi_uoc=False, in_ra=print):
    from kho import csdl
    muc = csdl.tat_ca()
    cache = doc_cache()
    ke = []
    viec = ke_hoach(muc, cache, loai_ds, ke)
    if ke and not chi_uoc:
        _ke_thua(ke, cache)
        in_ra(f"Kế thừa nghĩa trong họ biến thể (không gọi AI): {len(ke)} mục")
    if toi_da:
        viec = viec[:toi_da]
    usd_uoc, theo = uoc(viec)
    da_tieu = tong_chi_phi()
    in_ra(f"Kế hoạch: {len(viec)} lượt gọi AI, ước ≈ {usd_uoc} USD (đã tiêu trước đó {da_tieu:.3f} USD)")
    for l, t in theo.items():
        in_ra(f"  - {l:6s}: {t['muc']:5d} mục · {t['luot']:3d} lượt · model {t['model']} · ≈ {t['usd']} USD")
    if chi_uoc or not viec:
        return {"viec": len(viec), "uoc_usd": usd_uoc, "theo": theo}
    tieu = [0.0]
    gan_tong = [0]
    dung = [False]

    def mot(iv):
        i, v = iv
        con = ngan_sach - tieu[0]
        md = _model(v["loai"])
        du = UOC_USD.get((md if md in ("sonnet", "haiku", "opus") else "sonnet", v["kieu"]), 0.1)
        if dung[0] or con < du * 1.3:
            dung[0] = True
            return v, 0, 0.0, "bỏ: hết ngân sách"
        g, u, loi = lam_viec(v, i, cache, con)
        with _khoa:
            tieu[0] += u; gan_tong[0] += g
        return v, g, u, loi

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, song_song)) as ex:
        fut = [ex.submit(mot, (i + 1, v)) for i, v in enumerate(viec)]
        for k, f in enumerate(as_completed(fut)):
            v, g, u, loi = f.result()
            in_ra(f"[{k + 1}/{len(viec)}] {v['loai']:5s} {g}/{sum(len(x) if isinstance(x, list) else 1 for x in v['muc'])} mục · {u:.4f} USD · tổng {tieu[0]:.3f} USD"
                  + (f" · {loi}" if loi else "") + f" · {time.time() - t0:.0f}s")
    tk = ghi_chi_muc()
    in_ra(f"Xong: gắn {gan_tong[0]} mục, tiêu {tieu[0]:.3f} USD lần này; chỉ mục có ai: {tk.get('co_ai')} — {tk.get('ai_theo_loai')}")
    return {"gan": gan_tong[0], "usd": round(tieu[0], 4), "chi_muc": tk}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ngan-sach", type=float, default=3.0)
    ap.add_argument("--loai", default="")
    ap.add_argument("--toi-da", type=int, default=0)
    ap.add_argument("--song-song", type=int, default=3)
    ap.add_argument("--uoc", action="store_true")
    ap.add_argument("--ghi", action="store_true", help="chỉ gắn cache ai_nghia vào bảng muc (csdl)")
    a = ap.parse_args()
    if a.ghi:
        print(json.dumps(ghi_chi_muc(), ensure_ascii=False))
    else:
        chay(a.ngan_sach, set(a.loai.split(",")) if a.loai else None, a.toi_da or None, a.song_song, a.uoc,
             in_ra=lambda s: print(time.strftime("%H:%M:%S ") + s, flush=True))
