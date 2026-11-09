# -*- coding: utf-8 -*-
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Bản đồ KHO — biết mình có những gì, nằm ở đâu, dùng vào việc gì.

Quét các thư mục tài nguyên (bộ mua + kho máy), phân loại từng file, đo thời lượng/khổ hình, gắn thẻ từ tên
thư mục (mood nhạc, loại SFX, loại LUT…), kiểm font có dấu tiếng Việt. Ghi ra:
  <kho>/ban-do-kho/kho.json       — dữ liệu máy đọc (mỗi file một dòng)
  <kho>/ban-do-kho/BAN-DO-KHO.md  — bản tóm tắt người đọc: có gì, bao nhiêu, ở đâu

    python3 ban_do_kho.py lap                         # quét lại (chạy khi thêm tài nguyên mới)
    python3 ban_do_kho.py tim sfx "chuyển cảnh"       # tìm theo loại + từ khoá (khớp tên/thư mục/thẻ)
    python3 ban_do_kho.py tim nhac "hồi hộp" --dai 20-200
    from ban_do_kho import tim; tim("sfx", "camera flash", toi_da=5)
"""
import json, os, re, subprocess, sys, unicodedata
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit
KHO, MUA = kit.kho(), kit.bo_mua()          # cau-hinh.json → kho.duong_dan, kho.bo_mua
NGUON = [g for g in (MUA, KHO) if g]
BO_QUA = {"nguon", "du-an", "phan-tich", "phat-hanh", "ban-do-kho", "__MACOSX", ".git", "doan", "lop"}
BO_QUA_TIEN_TO = ("_",)                 # thư mục dự án tạm: _phan12, _v1…
RA = os.path.join(KHO, "ban-do-kho")

AM = {".wav", ".mp3", ".aif", ".aiff", ".m4a", ".ogg", ".flac"}
HINH = {".mp4", ".mov", ".m4v", ".webm"}
ANH = {".png", ".jpg", ".jpeg", ".webp"}
FONT = {".ttf", ".otf"}
LUT = {".cube", ".3dl"}
NEN = {".zip", ".rar", ".7z"}


def khong_dau(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


def phan_loai(p):
    ext = os.path.splitext(p)[1].lower()
    duong = khong_dau(p)
    if ext in AM:
        if re.search(r"sound effect|/sfx/|sfx trending|update lan 2/", duong):
            return "sfx"
        if re.search(r"nhac ban quyen|/music|nhac nen|/music-pixabay", duong):
            return "nhac"
        return "sfx"
    if ext in HINH:
        if "filmburn" in duong or "overlay" in duong or "chói" in p.lower() or "choi loa" in duong:
            return "chong"        # lớp chồng: film burn, ánh sáng
        if "grid" in duong or "luoi" in duong or "background" in duong or "texture" in duong or "/bg" in duong:
            return "nen"
        return "video"
    if ext in ANH:
        if "character" in duong or "icon" in duong:
            return "icon"
        if "grid" in duong or "luoi" in duong or "texture" in duong or "/grids/" in duong:
            return "nen"
        if "overlay" in duong or "phu-" in duong:
            return "chong"
        return "anh"
    if ext in FONT:
        return "font"
    if ext in LUT:
        return "lut"
    if ext in NEN:
        return "chua_giai_nen"
    if ext in {".xmp", ".lrtemplate", ".dng"}:
        return "preset_anh"
    return None


THE = [  # (mẫu trong đường dẫn không dấu, thẻ)
    (r"cam dong|cam xuc|emotional|sad|piano", "cảm xúc"), (r"quang cao|corporate|commercial", "quảng cáo"),
    (r"lofi|chill|vlog", "chill"), (r"rap|rock|trap", "mạnh"), (r"gay can|hoi hop|suspense|tension|dramatic", "hồi hộp"),
    (r"funky|zui|vui|happy|upbeat|comical|cartoon", "vui"), (r"cinematic|epic|trailer", "điện ảnh"),
    (r"transition|chuyen canh|whoosh|swoosh|swish|movement|chuyen dong", "chuyển cảnh"),
    (r"hit|impact|boom|bass drop|subdrop|cao trao", "nhấn"), (r"riser|swell|build", "dâng lên"),
    (r"click|mouse|typing|keyboard|go phim|\bui\b|interface|hud", "giao diện"), (r"notification|thong bao|\bding\b|bell", "thông báo"),
    (r"camera|shutter|flash", "máy ảnh"), (r"glitch|digital|static", "glitch"), (r"paper|giay", "giấy"),
    (r"pop|bubble|bong bong", "bật"), (r"money|cash|coin", "tiền"), (r"ket qua|bat ngo|surprise|reveal|correct|wrong", "kết quả"),
    (r"slog|s-log|\blog\b|apple log|log to", "đầu vào log"), (r"rec709|natural|dailies", "rec709"), (r"apple log", "apple log"),
    (r"\bfilm|movie|cinema", "phim"), (r"topograph", "địa hình"), (r"neon", "neon"), (r"dots|cham", "chấm"),
    (r"purple|/tim", "tím"), (r"black|/den|/toi", "tối"), (r"green|luc", "xanh lá"), (r"blue|lam", "xanh dương"),
]


def gan_the(p):
    for g in NGUON:                         # chỉ gắn thẻ theo phần đường dẫn bên trong kho
        p = p.replace(g, "")
    d = khong_dau(p)
    return sorted({t for m, t in THE if re.search(m, d)})


def do(p, loai):
    r = {"duong": p, "loai": loai, "the": gan_the(p), "mb": round(os.path.getsize(p) / 1e6, 2)}
    if loai in ("nhac", "sfx", "nen", "chong", "video"):
        try:
            o = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                "format=duration:stream=codec_type,width,height,pix_fmt,codec_name",
                                "-of", "json", p], capture_output=True, text=True, timeout=30).stdout
            j = json.loads(o or "{}")
            r["giay"] = round(float(j.get("format", {}).get("duration", 0) or 0), 2)
            v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), None)
            if v:
                r["kho"] = f'{v.get("width")}x{v.get("height")}'
                r["alpha"] = bool(re.search(r"a|rgba|argb|yuva", v.get("pix_fmt", "") or "")) or v.get("codec_name") == "prores"
        except Exception:
            pass
    if loai == "font":
        try:
            from fontTools.ttLib import TTFont
            f = TTFont(p, fontNumber=0, lazy=True)
            cmap = f.getBestCmap() or {}
            r["co_dau_viet"] = all(ord(c) in cmap for c in "ẮẶỆỮỢđ")
            nm = f["name"]
            r["ho"] = str(nm.getDebugName(1) or "")
            r["kieu"] = str(nm.getDebugName(2) or "")
        except Exception:
            r["co_dau_viet"] = None
    return r


def _an_toan(p, loai):
    try:
        return do(p, loai)
    except Exception:
        return None


def lap():
    ds = []
    for goc in NGUON:
        if not os.path.isdir(goc):
            continue
        for d, cac_thu_muc, files in os.walk(goc):
            cac_thu_muc[:] = [x for x in cac_thu_muc if x not in BO_QUA and not x.startswith(BO_QUA_TIEN_TO)]
            for f in files:
                if f.startswith(".") or f.startswith("._"):
                    continue
                p = os.path.join(d, f)
                if not os.path.isfile(p) or (d == KHO and f.startswith(("SRC_", "sfx_"))):   # link hỏng / file thô ở gốc
                    continue
                loai = phan_loai(p)
                if loai:
                    ds.append((p, loai))
    with ThreadPoolExecutor(8) as ex:
        kq = [r for r in ex.map(lambda x: _an_toan(*x), ds) if r]
    os.makedirs(RA, exist_ok=True)
    json.dump(kq, open(os.path.join(RA, "kho.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    tom_tat(kq)
    return kq


def tom_tat(kq):
    from collections import Counter, defaultdict
    dem = Counter(r["loai"] for r in kq)
    the = defaultdict(Counter)
    thu_muc = defaultdict(Counter)
    for r in kq:
        for t in r["the"]:
            the[r["loai"]][t] += 1
        rel = r["duong"]
        for g in NGUON:
            rel = rel.replace(g, "[" + ("BỘ MUA" if g == MUA else "KHO MÁY") + "]")
        thu_muc[r["loai"]][os.path.dirname(rel)] += 1
    ten = {"nhac": "Nhạc nền", "sfx": "Tiếng động (SFX)", "nen": "Nền (lưới, giấy, texture, động)", "chong": "Lớp chồng (film burn, ánh sáng)",
           "lut": "LUT màu", "font": "Font", "icon": "Icon / nhân vật", "anh": "Ảnh khác", "video": "Video khác",
           "preset_anh": "Preset ảnh (Lightroom)", "chua_giai_nen": "File nén CHƯA giải nén"}
    L = ["# Bản đồ kho tài nguyên", "",
         f"Tự sinh bởi `scripts/ban_do_kho.py lap`. Gốc quét: " + " · ".join(f"`{g}`" for g in NGUON), "",
         "| Loại | Số file | Thẻ nhiều nhất |", "|---|---|---|"]
    for k, n in dem.most_common():
        L.append(f"| {ten.get(k, k)} | {n} | {', '.join(f'{t} ({c})' for t, c in the[k].most_common(6))} |")
    fv = [r for r in kq if r["loai"] == "font"]
    L += ["", f"Font có đủ dấu tiếng Việt: **{sum(1 for r in fv if r.get('co_dau_viet'))} / {len(fv)}**", ""]
    for k, _ in dem.most_common():
        L += [f"## {ten.get(k, k)}", ""]
        for dthu, n in thu_muc[k].most_common(14):
            L.append(f"- `{dthu}` — {n}")
        L.append("")
    L += ["## Cách tìm nhanh", "```", "python3 scripts/ban_do_kho.py tim sfx \"chuyển cảnh\"",
          "python3 scripts/ban_do_kho.py tim nhac \"hồi hộp\" --dai 30-240", "python3 scripts/ban_do_kho.py tim font \"script\" --viet", "```"]
    open(os.path.join(RA, "BAN-DO-KHO.md"), "w", encoding="utf-8").write("\n".join(L))


def tim(loai=None, tu="", dai=None, viet=False, toi_da=15):
    try:
        import quy_trinh
        quy_trinh.ghi_nhap(7, f"tra kho: {loai or ''} {tu}")   # chỉ nháp — bước 7 do Claude tự `xong 7` có lý do
    except Exception:
        pass
    kq = json.load(open(os.path.join(RA, "kho.json"), encoding="utf-8"))
    tk = [khong_dau(x) for x in tu.split()] if tu else []
    ra = []
    for r in kq:
        if loai and r["loai"] != loai:
            continue
        chuoi = khong_dau(r["duong"] + " " + " ".join(r["the"]) + " " + r.get("ho", ""))
        if not all(t in chuoi for t in tk):
            continue
        if dai and r.get("giay") is not None and not (dai[0] <= r["giay"] <= dai[1]):
            continue
        if viet and not r.get("co_dau_viet"):
            continue
        ra.append(r)
    return ra[:toi_da]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "lap":
        kq = lap()
        print(open(os.path.join(RA, "BAN-DO-KHO.md"), encoding="utf-8").read()[:3000])
    elif len(sys.argv) > 1 and sys.argv[1] == "tim":
        loai = sys.argv[2] if len(sys.argv) > 2 else None
        tu = sys.argv[3] if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else ""
        dai = None
        if "--dai" in sys.argv:
            a, b = sys.argv[sys.argv.index("--dai") + 1].split("-"); dai = (float(a), float(b))
        for r in tim(loai, tu, dai, "--viet" in sys.argv, 20):
            print(f"{r.get('giay', ''):>7}s  {', '.join(r['the'])[:40]:40}  {r['duong']}")
