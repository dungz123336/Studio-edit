#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""BẢN KÊ KHO CÔNG CỤ — biết mình đang nắm gì trước khi nghĩ cách dựng. Tự sinh từ chính skill, không sửa tay.

    python scripts/ban_ke_kho.py          # in bản kê (nao.py nap tự gọi ở bước 2)
    python scripts/ban_ke_kho.py --ngan   # bản rút gọn

Editor giỏi không bắt đầu bằng "kho có gì" mà bằng "video cần gì" (nao/goc/1) — nhưng phải THUỘC kho để biết
cái mình cần có sẵn hay phải tự chế. Bản kê này là phần "thuộc kho".
"""
import ast, glob, json, os, re, sys
from collections import Counter, defaultdict

DIR = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(DIR)
sys.path.insert(0, DIR)

# bước nào dùng công cụ nào — để không quên công cụ ở đúng lúc cần
THEO_BUOC = [
    ("1 Nhận việc", "quy_trinh.py bat-dau <ten> --ho-so <hs> · cap_nhat.py kiem --im-lang"),
    ("2 Nạp não", "nao.py nap (in cả bản kê này)"),
    ("3 Đọc video", "dung.py <kb> --chi-cat (nghe lời) · soi_hinh.py (rung) · xem_video_mau.py / ffmpeg tile (bảng khung) — NHÌN ảnh"),
    ("4 Cảm xúc + cấu trúc", "4 dòng nhật ký trong video_*.py · đọc 2–3 video_*.py gần nhất"),
    ("5 Mượn kiến thức", "nao.py tim \"<vấn đề>\" (nhiều lượt) → quy_trinh.py xong 5 \"<bài .md + lý do>\""),
    ("6 Biên kịch + cắt", "dung.py <kb> --chi-cat · soi_tu_dai.py · sua_chu chỉ khi có bằng chứng (nao/goc/3)"),
    ("7 Đi chợ kho", "tham_kho.py <loi.json> --mood \"…\" → nghe/nhìn ứng viên → ban_do_kho.py tim … → quy_trinh.py xong 7 \"…\""),
    ("8 Dựng", "dung.py <kb> (hiệu ứng khai trong bien_kich(): hieu_ung=[dict(ham=…)]) · kieu_chu.py · ve2.py · cards.py"),
    ("9 Chấm", "check.py 3 lượt · cham_bo_cuc.py · duyet_chu.py (dung.py tự chạy)"),
    ("10 Nhìn lại", "trích khung ffmpeg → NHÌN → sửa video_*.py → dựng lại"),
    ("11 Giao", "bia.py (kiểu bìa hồ sơ) · quy_trinh.py giao <thư mục> · Studio: studio/bao.py video <mp4> --bia <png>"),
    ("12 Góp ý", "ghi nao/ca-nhan/<hs>/gop-y.md · quy_trinh.py xong 12 \"…\""),
]


def dong_dau(p):
    """dòng đầu docstring của một script"""
    try:
        doc = ast.get_docstring(ast.parse(open(p, encoding="utf-8", errors="replace").read())) or ""
    except SyntaxError:
        doc = ""
    return (doc.strip().splitlines() or [""])[0][:110]


def hieu_ung():
    p = os.path.join(SKILL, "kho", "kho-hieu-ung.md")
    nhom = defaultdict(list)
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8"):
            m = re.match(r"\|\s*(\d+)\s*\|", ln)
            if not m:
                continue
            c = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(c) < 5:
                continue
            ham = re.sub(r"[`\[\]\"]|^B", "", c[2]).split("(")[0].strip()
            ten = re.sub(r"[*~⚠]", "", c[1]).strip()
            che = " ✗chê" if ("chê" in ln or "~~" in ln) else ""
            nhom[c[3]].append(f"`{ham}` {ten[:26]} — {c[4][:48]}{che}")
    return nhom


def tai_nguyen():
    try:
        import kit
        p = os.path.join(kit.kho(), "ban-do-kho", "kho.json")
        ds = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []
        return ds, kit.kho(), kit.bo_mua()
    except Exception:
        return [], "", ""


def main(ngan=False):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    import config
    L = ["══ BẢN KÊ KHO CÔNG CỤ — thuộc kho trước, rồi mới chọn theo nghĩa câu ══", ""]

    L.append("① QUY TRÌNH → CÔNG CỤ ở từng bước")
    L += [f"  {b:<20} {c}" for b, c in THEO_BUOC]

    L += ["", "② CÔNG CỤ (scripts/ + công thức) — gọi bằng python của skill"]
    for p in sorted(glob.glob(os.path.join(DIR, "*.py"))):
        ten = os.path.basename(p)
        if ten.startswith("_") or ten in ("tao_font_tinh.py", "sinh_kieu_tu_capcut.py", "ky_so.py"):
            continue
        L.append(f"  {ten:<20} {dong_dau(p)}")
    for d in sorted(glob.glob(os.path.join(SKILL, "cong-thuc", "*"))):
        if os.path.isdir(d):
            doc = os.path.join(d, "DOC-TRUOC.md")
            mo = open(doc, encoding="utf-8").read().strip().splitlines()[0][:100] if os.path.exists(doc) else ""
            L.append(f"  cong-thuc/{os.path.basename(d):<22} {mo or dong_dau(os.path.join(d, 'dung.py'))}")

    nhom = hieu_ung()
    tong = sum(len(v) for v in nhom.values())
    L += ["", f"③ HIỆU ỨNG — {tong} hàm (kho/kho-hieu-ung.md) · chọn theo NGHĨA câu, mỗi video một bộ riêng"]
    for k, ds in sorted(nhom.items(), key=lambda x: -len(x[1])):
        L.append(f"  [{k}] {len(ds)}")
        L += [f"     {x}" for x in (ds[:4] if ngan else ds)]

    try:
        import kit
        kc = json.load(open(kit.find("kieu-chu-day-du.json"), encoding="utf-8"))
    except Exception:
        kc = []
    tay = re.findall(r'^\s*"([a-z0-9-]+)":\s*dict\(ham=_k_', open(os.path.join(DIR, "kieu_chu.py"), encoding="utf-8").read(), re.M)
    L += ["", f"④ KIỂU CHỮ có tên — {len(kc)} kiểu CapCut + {len(tay)} kiểu chỉnh tay (kieu_chu.py; K.bang() xem hết)",
          "  chỉnh tay: " + ", ".join(tay),
          "  CapCut (vài kiểu): " + ", ".join(x.get("ma", "") for x in kc[:18]) + " …",
          "  nền chữ ve2.py: bang_giay · gach_cheo · cat_goc · but_da · ngoac"]

    ds, kho, mua = tai_nguyen()
    dem, the = Counter(r["loai"] for r in ds), defaultdict(Counter)
    for r in ds:
        the[r["loai"]].update(r.get("the") or [])
    ten_loai = {"nhac": "Nhạc nền", "sfx": "Tiếng động", "font": "Font", "nen": "Nền", "chong": "Lớp chồng (film burn, ánh sáng)",
                "lut": "LUT (chỉ D-Log)", "icon": "Icon (KHÔNG dùng nhân vật vector)", "video": "Video", "anh": "Ảnh"}
    L += ["", f"⑤ TÀI NGUYÊN — {len(ds)} file · kho sạch {kho} · bộ quà tặng {'CÓ' if mua else 'chưa có'}"]
    for k, n in dem.most_common():
        if k in ten_loai:
            L.append(f"  {ten_loai[k]:<34} {n:>5}  " + ", ".join(f"{t}({c})" for t, c in the[k].most_common(8)))
    L += ["  tra: ban_do_kho.py tim <nhac|sfx|nen|chong|font|lut> \"<từ>\" [--dai a-b] [--viet] · phiếu đi chợ: tham_kho.py",
          "  nhạc/SFX bộ quà tặng có giấy phép riêng → video kiếm tiền: nói rõ khi bàn giao, ưu tiên kho sạch khi không chắc"]

    L += ["", f"⑥ HỒ SƠ ĐANG DÙNG: {config.ho_so_hien_tai() or '(chưa)'} · màu nhấn {config.lay('mau', 'nhan')} · "
          f"phụ đề {config.lay('chu', 'phu_de')} · tiêu đề {config.lay('chu', 'title_to')} · bìa {config.lay('chu', 'bia')} · "
          f"kiểu bìa {config.lay('bia', 'kieu') or '(thiết kế theo anh-bia.md)'} · từ giữ: {', '.join(config.lay('tu_giu') or []) or '—'}"]
    L += ["", "⑦ DÙNG HẾT SỨC, KHÔNG DÙNG HẾT KHO: thuộc kho để biết đủ phương án; chọn ít mà đúng (nao/goc/1, 6-di-cho-kho.md)."]
    print("\n".join(L))


if __name__ == "__main__":
    main("--ngan" in sys.argv)
