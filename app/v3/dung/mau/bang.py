# -*- coding: utf-8 -*-
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
"""BẢNG MẪU ĐỒ HOẠ cho mắt AI: mỗi mẫu trong thư viện một ô ảnh (trạng thái giữa/cuối) trên nền khung thật, xếp theo nhóm,
24 ô một bảng → AI THẤY công cụ trông thế nào trước khi chọn (dữ liệu, không gợi ý). Vẽ một lần cho mỗi phiên bản engine,
cache du_lieu/bang-mau/<băm>/bang-mau-N.jpg. Muốn xem kỹ một mẫu (6 thời điểm): dai(mid) → ảnh dải.

    dam_bao(ep=False, log=None) -> {"anh": [...], "thu_muc", "so_mau", "moi": bool}
    dai(mid) -> đường ảnh dải 6 thời điểm của một mẫu (cache cùng thư mục)
    python v3/dung/mau/bang.py [--ep]
"""
import os, sys, json, hashlib, traceback, time
import numpy as np
from PIL import Image, ImageDraw, ImageFont

V3 = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if V3 not in sys.path:
    sys.path.insert(0, V3)
import chung

O_W, O_H, COT, HANG = 180, 320, 6, 4          # ô 180×320 (đọc được chữ trên mẫu), 24 ô/bảng, bảng 1080×(4×344+40)
PC_TRUNG_TINH = {"mau_nhan": "#FFFFFF", "mau_nhan2": "#BBBBBB", "mau_sang": "#FFFFFF", "mau_toi": "#111111"}
# 1.2.21: quyet-dinh.json TRUNG TÍNH chỉ cho bảng xem trước / bộ thử (engine không còn số riêng — ctx dựng thật nhận quyết định của KÊNH từ dung.tao_ctx).
# Đủ mọi trường engine đọc (Kế hoạch 1.2.21 §1c + trường A3 thêm) — A7/A4 dùng làm khuôn kiểm tra tên trường.
QUYET_DINH_XEM_TRUOC = {
    "phien": 1, "ly_do": "bộ xem trước/thử — trung tính, không phải gu kênh nào",
    "font": {"tieu_de": "tieu_de", "phu_de": "phu_de", "nhan": "nhan"},
    "bang_mau": {"nhan": "#FFFFFF", "nhan2": "#BBBBBB", "sang": "#FFFFFF", "toi": "#111111"},
    "chu": {"co": 72, "dam": 700, "dong": 1.15, "can": "giua", "rong_max": 0.86, "mau": "#FFFFFF", "font": "tieu_de",
            "vien": [{"w": 4, "mau": "#000000"}], "bong": [{"x": 0, "y": 4, "mo": 12, "mau": "#00000088"}], "nen": None, "gradient": None},
    "khoi": {"cach_dong": 0.95},
    "the": {"hinh": "pill", "mau": "#111111CC", "bo": 24, "dem": [32, 20], "bong": None, "vien": None,
            "chu": {"co": 48, "dam": 700, "mau": "#FFFFFF", "font": "nhan", "vien": None, "bong": None}},
    "phu_de": {"che_do": "cum", "toi_da_chu": 22, "karaoke": True, "keo_dai": 0.15, "lang_ngat": 0.5, "tween": 0.2, "nhuong_cho": 0.2,
               "kieu_dang": {"font": "phu_de", "co": 60, "dam": 700, "dong": 1.15, "can": "giua", "mau": "#FFFFFF", "vien": [{"w": 8, "mau": "#000000"}],
                             "bong": None, "nen": None, "gradient": None},
               "vi_tri": {"anchor": "bc", "x": 0.5, "y": 0.72, "so_voi": "khung"},
               "anim": {"vao": {"kieu": "pop", "dai": 0.12, "ease": "out", "tu": {"scale": 0.9, "opacity": 0}}, "ra": {"kieu": "none"}},
               "mau_noi": "#FFFFFF"},
    "anim": {"vao": {"kieu": "fade", "dai": 0.25, "ease": "out"}, "ra": {"kieu": "fade", "dai": 0.2, "ease": "in"},
             "so_le": 0.05, "keyframe_dai": 0.25, "keyframe_ease": "in_out", "ken_burns": [1.0, 1.06],
             "kieu": {"slide": {"x": -40, "opacity": 0}, "pop": {"scale": 0.6, "opacity": 0}, "blur": {"blur": 12, "opacity": 0},
                      "flip": {"rot_y": -80, "opacity": 0}, "tilt": {"rot_x": 70, "opacity": 0}}},
    "camera": {"ease": "out"},
    "duong": {"w": 8, "ve": 0.4, "ease": "out"},
    "vi_tri": {"hop_mac_dinh": {"hinh": [0.8, 0.4], "py": [0.5, 0.3], "mau": [0.8, 0.4], "web": [0.8, 0.3], "video": [1.0, 1.0]}, "cach_nhom": 0.012},
    "ne_mat": {"thu_toi": 0.7, "noi": 0.10},
    "am": {"nhac": {"db": -22, "vao": 1.0, "ra": 2.0, "ne_giong": True}, "sfx": {"db": -8}, "giong_lufs": -16, "dinh_dbtp": -2.0},
    "nen_moi": {"mau": "#111111", "mo_sigma": 24, "toi": 0.15},
    "chuyen_canh": {"flash_dai": 0.2},
    "bia": {"so_phuong_an": 3, "nen": {"kieu": "khung_mo", "mo": 0.4, "toi": 0.3},
            "nguoi": {"co": 1.1, "x": 0.5, "y": 0.62, "vien_sang": {"w": 6, "mau": "#FFFFFF"}, "bong": {"x": 0, "y": 24, "mo": 40, "mau": "#000000AA"}},
            "chu": {"co": 120, "dam": 900, "mau": "#FFFFFF", "font": "tieu_de", "vien": [{"w": 10, "mau": "#000000"}], "bong": None, "nen": None, "gradient": None},
            "tuong_phan_toi_thieu": 3.0, "de_mat_toi_da": 0.12},
}


def _bam():
    """băm theo mã engine + danh sách mẫu (đổi mẫu → vẽ lại)"""
    from dung import dung as D, mau as M
    M.nap_tat_ca()
    ids = sorted(M.REGISTRY)
    h = hashlib.md5()
    h.update(str(D._phien_engine()).encode("utf-8"))
    for mid in ids:
        h.update(mid.encode("utf-8"))
    return h.hexdigest()[:12], ids


def _thu_muc(bam):
    d = os.path.join(chung.duong("du_lieu"), "bang-mau", bam)
    os.makedirs(d, exist_ok=True)
    return d


def _nen(W, H):
    """nền khung thật trung tính: lấy từ clip thử nếu có, không thì xám"""
    for src in (os.path.join(chung.duong("du_lieu"), "clip-thu", "nguoi-noi-74s.mp4"),):
        if os.path.isfile(src):
            try:
                import subprocess
                r = subprocess.run([chung.duong("ffmpeg"), "-v", "error", "-ss", "12", "-i", src, "-frames:v", "1", "-vf",
                                    f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                   capture_output=True, timeout=60, creationflags=(0x08000000 if os.name == "nt" else 0))
                if len(r.stdout) == W * H * 3:
                    return np.frombuffer(r.stdout, np.uint8).reshape(H, W, 3).copy()
            except Exception:
                pass
    return np.full((H, W, 3), 48, np.uint8)


def _ctx(W=1080, H=1920):
    from dung import lop as L
    ctx = L.Ctx(W, H, 30, font={}, mat=None, kho=None, du_an=chung.duong("nhat_ky"), quyet_dinh=json.loads(json.dumps(QUYET_DINH_XEM_TRUOC)))
    ctx.pc = dict(PC_TRUNG_TINH)
    return ctx


def _khung_mau(mid, ctx, nen, t_ti_le=0.75, dur=3.0):
    """ảnh RGB khung đầy đủ của mẫu tại t = t_ti_le·dur (None nếu lỗi)"""
    from dung import lop as L, mau as M
    r = M.lay(mid)
    the = r["the"]
    sp = {"id": "thu", "kieu": "mau", "t0": 0.0, "t1": dur, "noi_dung": {"mau": mid, "tham_so": dict(the.get("vi_du") or {})},
          "anim": {"vao": {"kieu": "none", "dai": 0}, "ra": {"kieu": "none", "dai": 0}}}
    if the.get("nhom") == "chuyen_canh":
        sp["t1"] = dur = 0.6
    ctx.lay_nen = lambda lop_, t_: nen
    lop = L.tao_lop(sp, ctx)
    t = dur * t_ti_le
    khung = Image.fromarray(nen).convert("RGBA")
    a, (x, y) = lop.ve_khung(t) if hasattr(lop, "ve_khung") else (None, (0, 0))
    if a is None:
        arr = L.numpy_tu_skia(lop.noi_dung(t)[0])
        x0, y0, w, h = lop.khoi()
        khung.alpha_composite(Image.fromarray(arr, "RGBA"), (int(x0), int(y0)))
    else:
        khung.alpha_composite(Image.fromarray(a, "RGBA"), (int(x), int(y)))
    return khung.convert("RGB")


def _font(co):
    for f in (os.path.join(chung.duong("app"), "v2", "font-them", "BeVietnamPro-Bold.ttf"), os.path.join(chung.duong("font_mac_dinh"), "BeVietnamPro-Bold.ttf")):
        if os.path.isfile(f):
            try:
                return ImageFont.truetype(f, co)
            except Exception:
                pass
    return ImageFont.load_default()


def dam_bao(ep=False, log=None):
    """vẽ bảng mẫu nếu chưa có cho phiên engine này → {"anh": [...], "thu_muc", "so_mau", "moi"}"""
    from dung import mau as M
    bam, ids = _bam()
    d = _thu_muc(bam)
    p_idx = os.path.join(d, "bang-mau.json")
    cu = chung.doc_json(p_idx)
    if cu and not ep and all(os.path.isfile(x) for x in cu.get("anh", [])):
        return dict(cu, moi=False)
    t0 = time.time()
    W, H = 1080, 1920
    nen = _nen(W, H)
    ctx = _ctx(W, H)
    TEN_NHOM = {"canh": "CẢNH TRÁM", "the": "THẺ", "chu": "CHỮ HIỆU ỨNG", "do_hoa": "ĐỒ HOẠ CHỈ DẪN", "giao_dien": "GIAO DIỆN GIẢ",
                "chen": "CHÈN / KHUNG", "chuyen_canh": "CHUYỂN CẢNH", "khung": "LỚP PHỦ"}
    thu_tu = ["canh", "the", "chu", "do_hoa", "giao_dien", "chen", "chuyen_canh", "khung"]
    ds = sorted(ids, key=lambda m: (thu_tu.index(M.REGISTRY[m]["the"].get("nhom")) if M.REGISTRY[m]["the"].get("nhom") in thu_tu else 99, m))
    o = []
    f_nho, f_nhom = _font(15), _font(18)
    for mid in ds:
        the = M.REGISTRY[mid]["the"]
        try:
            im = _khung_mau(mid, ctx, nen).resize((O_W, O_H), Image.LANCZOS)
        except Exception:
            if log:
                log(f"bảng mẫu: {mid} lỗi {traceback.format_exc(limit=1).strip()[-120:]}")
            im = Image.new("RGB", (O_W, O_H), (60, 20, 20))
        o.append((mid, the, im))
    anh = []
    moi_bang = COT * HANG
    for i in range(0, len(o), moi_bang):
        s = Image.new("RGB", (COT * O_W, HANG * (O_H + 24) + 40), (14, 14, 18))
        dr = ImageDraw.Draw(s)
        dr.text((8, 8), f"BẢNG MẪU ĐỒ HOẠ {i // moi_bang + 1}/{(len(o) + moi_bang - 1) // moi_bang} — màu trung tính, mẫu nào cũng đổi được màu/font/tham số", fill=(230, 230, 230), font=f_nhom)
        for j, (mid, the, im) in enumerate(o[i:i + moi_bang]):
            c, r_ = j % COT, j // COT
            x, y = c * O_W, 40 + r_ * (O_H + 24)
            s.paste(im, (x, y))
            nhan = f"{mid.replace('mau.', '', 1)} [{TEN_NHOM.get(the.get('nhom'), the.get('nhom'))[:12]}]"
            dr.rectangle([x, y + O_H, x + O_W, y + O_H + 24], fill=(14, 14, 18))
            dr.text((x + 4, y + O_H + 4), nhan[:30], fill=(255, 255, 255), font=f_nho)
        p = os.path.join(d, f"bang-mau-{i // moi_bang + 1}.jpg")
        s.save(p, quality=88)
        anh.append(p)
    kq = {"anh": anh, "thu_muc": d, "so_mau": len(o), "bam": bam, "giay": round(time.time() - t0, 1), "luc": time.strftime("%Y-%m-%d %H:%M")}
    chung.ghi_json(p_idx, kq)
    if log:
        log(f"bảng mẫu: {len(o)} mẫu → {len(anh)} bảng trong {kq['giay']}s")
    return dict(kq, moi=True)


def dai(mid, n=6, dur=3.0):
    """ảnh dải 6 thời điểm của MỘT mẫu (xem kỹ chuyển động) — cache theo phiên engine"""
    from dung import lop as L, mau as M
    bam, _ = _bam()
    d = _thu_muc(bam)
    p = os.path.join(d, "dai-" + mid.replace(".", "_") + ".jpg")
    if os.path.isfile(p):
        return p
    W, H = 1080, 1920
    nen = _nen(W, H)
    ctx = _ctx(W, H)
    r = M.lay(mid)
    if not r:
        raise KeyError(f"không có mẫu {mid}")
    the = r["the"]
    sp = {"id": "thu", "kieu": "mau", "t0": 0.0, "t1": dur, "noi_dung": {"mau": mid, "tham_so": dict(the.get("vi_du") or {})},
          "anim": {"vao": {"kieu": "fade", "dai": 0.2}, "ra": {"kieu": "none", "dai": 0}}}
    if the.get("nhom") == "chuyen_canh":
        sp["t1"] = dur = 0.6; sp["anim"] = {"vao": {"kieu": "none", "dai": 0}, "ra": {"kieu": "none", "dai": 0}}
    ctx.lay_nen = lambda lop_, t_: nen
    lop = L.tao_lop(sp, ctx)
    o = []
    for i in range(n):
        t = dur * (i + 0.5) / n
        khung = Image.fromarray(nen).convert("RGBA")
        a, (x, y) = lop.ve_khung(t) if hasattr(lop, "ve_khung") else (None, (0, 0))
        if a is None:
            arr = L.numpy_tu_skia(lop.noi_dung(t)[0]); x0, y0, w, h = lop.khoi()
            khung.alpha_composite(Image.fromarray(arr, "RGBA"), (int(x0), int(y0)))
        else:
            khung.alpha_composite(Image.fromarray(a, "RGBA"), (int(x), int(y)))
        o.append(khung.convert("RGB").resize((W // 4, H // 4)))
    s = Image.new("RGB", (len(o) * (W // 4), H // 4 + 28), (14, 14, 18))
    dr = ImageDraw.Draw(s)
    for i, im in enumerate(o):
        s.paste(im, (i * (W // 4), 28))
    ts = {k: v for k, v in (the.get("tham_so") or {}).items()}
    dr.text((6, 6), f"{mid} · {the.get('ten', '')} · tham số: {', '.join(list(ts)[:8])}", fill=(255, 255, 255), font=_font(14))
    s.save(p, quality=88)
    return p


if __name__ == "__main__":
    kq = dam_bao(ep="--ep" in sys.argv, log=print)
    print(json.dumps({k: kq[k] for k in ("anh", "so_mau", "giay", "moi") if k in kq}, ensure_ascii=False, indent=1))
