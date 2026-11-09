#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""PHIẾU QUY TRÌNH 12 BƯỚC — máy giữ quy trình, không dựa vào trí nhớ.

MỌI việc (dựng / học kênh / hồ sơ khách — kể cả "edit nhanh", "làm thử", "demo") BẮT ĐẦU bằng:

    python3 quy_trinh.py bat-dau <ten-viec> --ho-so <hồ sơ> [--loai dung|hoc|ho-so]

  --ho-so là câu hỏi "VIDEO NÀY CỦA AI?": của người dùng chính → hồ sơ của họ; của KHÁCH/người lạ → hồ sơ riêng
  của khách (chưa có thì tạo: nao.py ho-so tao <ten> --tu <bo>). Không bao giờ dựng cho khách bằng hồ sơ người dùng.

Các lệnh khác tự đánh dấu bước của chúng (nao.py nap → 2, nao.py tim → 5, ban_do_kho.py tim → 7, dung.py --chi-cat → 6,
dung.py → 8·9). Còn lại đánh dấu tay, PHẢI kèm đầu ra:

    python3 quy_trinh.py xong 3 "bản đồ đoạn: 0–4s hook trước quán, 4–50s đi trong quán…"
    python3 quy_trinh.py xong 10 "đã nhìn 16 khung; sửa con dấu, giữ phụ đề 1,1 s vì nói nhanh"
    python3 quy_trinh.py giao <thư-mục-giao>     # bước 11: kiểm video + bìa, in khung báo cáo, trả hồ sơ mặc định
    python3 quy_trinh.py xong 12 "không có góp ý" | "ghi gop-y.md: …"
    python3 quy_trinh.py xem                      # phiếu đang mở, bước nào còn thiếu

Máy dựng (dung.py) DỪNG nếu: chưa mở phiếu · hồ sơ trên phiếu ≠ hồ sơ đang dùng · thiếu bước 1–5 · có biến CAU_HINH
(đường tắt đè hồ sơ).
"""
import json, os, sys, time

DIR = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(DIR)
# Studio chạy mỗi việc một phiếu: QUY_TRINH_PHIEU trỏ tới phiếu riêng của việc, HO_SO ghim hồ sơ của việc đó.
# Không có hai biến này (dùng qua chat) thì như cũ: một phiếu chung + nao/ca-nhan/HIEN-TAI.
PHIEU = os.environ.get("QUY_TRINH_PHIEU") or os.path.join(SKILL, ".phieu-hien-tai.json")
HO_SO_GHIM = os.environ.get("HO_SO", "").strip()
LUU = os.path.join(SKILL, ".phieu-cu")
BUOC = {1: "Nhận việc · phân loại · chọn hồ sơ", 2: "Nạp não (nao.py nap)", 3: "Đọc video: lời + hình + rung",
        4: "Cảm xúc + cấu trúc (nhật ký trong kịch bản)", 5: "Mượn kiến thức đúng vấn đề (nao.py tim)",
        6: "Biên kịch + cắt, đọc lại lời (--chi-cat)", 7: "Tra kho tài nguyên (ban_do_kho.py tim)",
        8: "Dựng (dung.py)", 9: "Chấm 3 lượt · bố cục · chữ", 10: "Trích khung ra NHÌN, sửa / giữ có lý do",
        11: "Giao: video + bìa theo hồ sơ + báo cáo", 12: "Góp ý → gop-y.md"}
CAN_TRUOC_DUNG = (1, 2, 3, 4, 5)
CAN_TRUOC_DUNG_THAT = (1, 2, 3, 4, 5, 6, 7)      # dựng thật (không --chi-cat) còn phải xong biên kịch + đi chợ kho
# Bước 5 và 7 là bước TƯ DUY: công cụ tra (nao.py tim, ban_do_kho.py tim, tham_kho.py) chỉ ghi NHÁP vào phiếu,
# không tự đánh dấu xong. Claude phải tự `xong 5` / `xong 7` với đầu ra đủ ý (xem kiem_dau_ra) — bài học 06/10:
# cả 3 video chỉ tra đúng 1 lần "nhạc chill" mà phiếu vẫn qua bước 7.


def doc():
    try:
        return json.load(open(PHIEU, encoding="utf-8"))
    except Exception:
        return None


def ghi(p):
    os.makedirs(os.path.dirname(os.path.abspath(PHIEU)), exist_ok=True)
    json.dump(p, open(PHIEU, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def ho_so_dang_dung():
    if HO_SO_GHIM:
        return HO_SO_GHIM
    try:
        return open(os.path.join(SKILL, "nao", "ca-nhan", "HIEN-TAI"), encoding="utf-8").read().strip()
    except OSError:
        return ""


def danh_dau(so, dau_ra="", im_lang=False):
    """gọi từ các script khác; không có phiếu thì bỏ qua (máy dựng sẽ chặn sau)"""
    p = doc()
    if not p:
        return False
    p["buoc"][str(so)] = {"luc": time.strftime("%H:%M:%S"), "dau_ra": dau_ra[:1500 if so in (5, 7) else 400]}
    ghi(p)
    if not im_lang:
        print(f"  [phiếu] ✓ bước {so} — {BUOC[so]}")
    return True


def ghi_nhap(so, noi_dung):
    """công cụ tra cứu gọi: lưu dấu vết đã tra vào phiếu (không đánh dấu xong bước)"""
    p = doc()
    if not p:
        return False
    ds = p.setdefault("nhap", {}).setdefault(str(so), [])
    ds.append(f"{time.strftime('%H:%M')} {noi_dung}"[:200])
    p["nhap"][str(so)] = ds[-60:]
    ghi(p)
    return True


VAT_LIEU_HINH = ("nền", "font", "kiểu chữ", "chữ", "hiệu ứng", "film", "loé", "lớp chồng", "overlay", "lut", "giấy",
                 "texture", "thẻ", "chuyển cảnh")


def kiem_dau_ra(p, so, dau_ra):
    """đầu ra bước tư duy phải đủ ý — trả chuỗi lỗi (rỗng = đạt)"""
    t = dau_ra.lower()
    if so == 5:
        if len(dau_ra) < 40 or not (".md" in t or "nao/" in t or t.startswith("không")):
            return ("Bước 5 phải ghi bài học mượn + lý do (tên file .md trong nao/kien-thuc hoặc nao/goc), "
                    "hoặc 'không, vì …' — ≥ 40 ký tự.")
    if so == 7:
        nhap = (p.get("nhap") or {}).get("7", [])
        loi = []
        if len(dau_ra) < 150:
            loi.append("ghi ≥ 150 ký tự: chọn gì, vì sao, đã loại gì")
        if "nhạc" not in t:
            loi.append("thiếu nhạc (bản chọn + mood + vì sao hợp)")
        if "sfx" not in t and "tiếng động" not in t:
            loi.append("thiếu SFX (theo từng hiệu ứng / chuyển cảnh)")
        if not any(w in t for w in VAT_LIEU_HINH):
            loi.append("thiếu lớp hình (kiểu chữ / font / nền / film burn / hiệu ứng nào, ở câu nào)")
        if len(nhap) < 3 and not any("tham_kho" in x for x in nhap):
            loi.append(f"mới tra kho {len(nhap)} lần — chạy scripts/tham_kho.py (phiếu đi chợ) hoặc tra ≥ 3 lượt nhạc/SFX/hình")
        if loi:
            return ("Bước 7 chưa đạt — " + "; ".join(loi) +
                    ".\nĐi chợ như editor: nao/goc/6-di-cho-kho.md · scripts/tham_kho.py <ban-chu.json> --mood \"…\"")
    return ""


def thieu(p, ds):
    return [s for s in ds if str(s) not in p["buoc"]]


def bat_dau(ten, ho_so, loai):
    import ban_quyen
    ok, loai_loi, tb = ban_quyen.gac()           # mọi phiếu đều cần: gói nguyên vẹn + bản quyền hợp lệ
    if not ok:
        sys.exit(f"DỪNG — {'gói không nguyên vẹn' if loai_loi == 'toan-ven' else 'bản quyền'}: {tb}. "
                 "Bảo người dùng kích hoạt trong Studio; đừng tìm cách bỏ qua bước kiểm.")
    cu = doc()
    if cu and "11" not in cu["buoc"] and "--de" not in sys.argv:
        sys.exit(f"Đang có phiếu '{cu['ten']}' chưa giao. Giao xong (quy_trinh.py giao …) hoặc thêm --de để bỏ phiếu cũ.")
    d = os.path.join(SKILL, "nao", "ca-nhan", ho_so)
    co = [x for x in os.listdir(os.path.join(SKILL, "nao", "ca-nhan")) if os.path.isdir(os.path.join(SKILL, "nao", "ca-nhan", x)) and x != "_mau"]
    if not co:
        sys.exit("LẦN ĐẦU DÙNG — chưa có hồ sơ nào. Làm hồ sơ cho người dùng trước (nao/ca-nhan/_mau/HOI.md):\n"
                 "  1) hỏi 6 câu trong HOI.md (hoặc học từ kênh của họ)\n"
                 "  2) python3 scripts/nao.py ho-so tao <ten> --tu <soi-dong|bien-tap|neon>   (chọn bộ gần gu nhất)\n"
                 "  3) điền cau-hinh.json + phong-cach.md + anh-bia.md theo câu trả lời, rồi mở phiếu lại.")
    if not os.path.isdir(d) or ho_so == "_mau":
        sys.exit(f"Chưa có hồ sơ '{ho_so}'. Video của khách/người lạ → tạo hồ sơ riêng trước:\n"
                 f"  python3 scripts/nao.py ho-so tao {ho_so} --tu <soi-dong|bien-tap|neon>")
    if HO_SO_GHIM and ho_so != HO_SO_GHIM:
        sys.exit(f"DỪNG — việc này trên Studio thuộc hồ sơ '{HO_SO_GHIM}'. Video của hồ sơ khác (khách, kênh khác) → "
                 f"bảo người dùng mở hồ sơ '{ho_so}' trong Studio rồi tạo việc mới ở đó.")
    truoc = ho_so_dang_dung()
    if not HO_SO_GHIM:
        open(os.path.join(SKILL, "nao", "ca-nhan", "HIEN-TAI"), "w", encoding="utf-8").write(ho_so + "\n")
    p = {"ten": ten, "loai": loai, "ho_so": ho_so, "ho_so_truoc": truoc, "mo_luc": time.strftime("%Y-%m-%d %H:%M"),
         "viec": os.environ.get("STUDIO_VIEC", ""),     # Studio gom các phiếu theo việc (một việc làm nhiều video)
         "buoc": {"1": {"luc": time.strftime("%H:%M:%S"), "dau_ra": f"việc {loai} · hồ sơ {ho_so}"}}}
    ghi(p)
    print(f"PHIẾU MỞ: {ten} · loại {loai} · hồ sơ {ho_so}" + (f" (đã chuyển từ {truoc})" if truoc and truoc != ho_so else ""))
    xem()


def xem():
    p = doc()
    if not p:
        print("Chưa có phiếu. Bắt đầu: python3 scripts/quy_trinh.py bat-dau <ten> --ho-so <hồ sơ>"); return
    print(f"Phiếu '{p['ten']}' · hồ sơ {p['ho_so']} · mở {p['mo_luc']}")
    for s, mo_ta in BUOC.items():
        b = p["buoc"].get(str(s))
        print(f"  {'✓' if b else '·'} {s:2}. {mo_ta}" + (f"  — {b['dau_ra'][:90]}" if b and b.get("dau_ra") else ""))
    for so, ds in (p.get("nhap") or {}).items():
        print(f"  nháp bước {so}: {len(ds)} lượt tra — " + " | ".join(x[6:60] for x in ds[-4:]))
    con = thieu(p, BUOC)
    if con:
        print(f"  → bước tiếp theo: {con[0]}. {BUOC[con[0]]}")


def kiem_truoc_dung(kich_ban_doc=""):
    """dung.py gọi trước khi dựng — sai là DỪNG"""
    p = doc()
    if not p:
        sys.exit("DỪNG — chưa mở phiếu quy trình. Chạy: python3 scripts/quy_trinh.py bat-dau <ten> --ho-so <hồ sơ>\n"
                 "(video của khách/người lạ → hồ sơ riêng của khách, KHÔNG dùng hồ sơ người dùng)")
    if os.environ.get("CAU_HINH"):
        sys.exit("DỪNG — đang có biến CAU_HINH đè hồ sơ (đường tắt). Bỏ biến đó; chọn hồ sơ bằng quy_trinh.py bat-dau.")
    if p["ho_so"] != ho_so_dang_dung():
        sys.exit(f"DỪNG — phiếu dựng cho hồ sơ '{p['ho_so']}' nhưng đang dùng '{ho_so_dang_dung()}'.")
    import re
    dong = kich_ban_doc.split("Hồ sơ:")[1].split("\n")[0] if "Hồ sơ:" in kich_ban_doc else ""
    if p["ho_so"] not in re.split(r"[^\w-]+", dong):
        sys.exit(f"DỪNG — docstring kịch bản thiếu dòng 'Hồ sơ: {p['ho_so']}' (khai rõ video của ai).")
    if "Mượn:" not in kich_ban_doc:
        sys.exit("DỪNG — docstring kịch bản thiếu dòng 'Mượn: …' (bước 5: bài học nào, vì sao — hoặc 'Mượn: không, vì …').")
    danh_dau(4, "nhật ký + hồ sơ + mượn có trong kịch bản", im_lang=True)
    p = doc()
    con = thieu(p, CAN_TRUOC_DUNG if "--chi-cat" in sys.argv else CAN_TRUOC_DUNG_THAT)
    if con:
        sys.exit("DỪNG — phiếu còn thiếu bước: " + ", ".join(f"{s}. {BUOC[s]}" for s in con)
                 + "\nXem: python3 scripts/quy_trinh.py xem"
                 + ("\n(bước 7: đi chợ kho bằng scripts/tham_kho.py rồi `quy_trinh.py xong 7 \"…\"` — nao/goc/6-di-cho-kho.md)"
                    if "7" in [str(s) for s in con] else ""))
    return p


def kiem_co_ban():
    """cho công thức không dùng video_*.py (vd demo màn hình + mặt): phiếu mở, đúng hồ sơ, đủ bước 1,2,3,5"""
    p = doc()
    if not p:
        sys.exit("DỪNG — chưa mở phiếu quy trình: python3 scripts/quy_trinh.py bat-dau <ten> --ho-so <hồ sơ>")
    if os.environ.get("CAU_HINH") or p["ho_so"] != ho_so_dang_dung():
        sys.exit("DỪNG — hồ sơ không khớp phiếu (hoặc đang có biến CAU_HINH đè hồ sơ).")
    con = thieu(p, (1, 2, 3, 5))
    if con:
        sys.exit("DỪNG — phiếu còn thiếu bước: " + ", ".join(f"{s}. {BUOC[s]}" for s in con))
    danh_dau(4, "công thức demo: cảm xúc + cấu trúc ghi trong cấu hình dự án", im_lang=True)
    return p


def giao(thu_muc):
    p = doc()
    if not p:
        sys.exit("Chưa có phiếu.")
    con = thieu(p, range(1, 11))
    if con:
        sys.exit("CHƯA GIAO ĐƯỢC — còn thiếu: " + ", ".join(f"{s}. {BUOC[s]}" for s in con))
    tep = os.listdir(thu_muc) if os.path.isdir(thu_muc) else []
    if p["loai"] == "dung":
        if not any(f.endswith(".mp4") for f in tep):
            sys.exit(f"CHƯA GIAO ĐƯỢC — {thu_muc} chưa có video .mp4")
        if not any(f.startswith("thumb-") and f.endswith((".png", ".jpg")) for f in tep):
            sys.exit(f"CHƯA GIAO ĐƯỢC — thiếu ảnh bìa thumb-*.png (scripts/bia.py — đọc kiểu bìa của hồ sơ '{p['ho_so']}', "
                     f"KHÔNG mượn kiểu bìa của hồ sơ khác)")
    danh_dau(11, thu_muc)
    p = doc()
    print("\n── KHUNG BÁO CÁO (điền vào trả lời người dùng) ──")
    for s in range(1, 12):
        b = p["buoc"].get(str(s), {})
        print(f"  {s:2}. {BUOC[s]}: {b.get('dau_ra', '')[:120]}")
    print("  + nói thẳng thứ cố ý giữ / chưa đạt")
    if not HO_SO_GHIM and p.get("ho_so_truoc") and p["ho_so_truoc"] != p["ho_so"]:
        open(os.path.join(SKILL, "nao", "ca-nhan", "HIEN-TAI"), "w", encoding="utf-8").write(p["ho_so_truoc"] + "\n")
        print(f"\nĐã trả hồ sơ đang dùng về '{p['ho_so_truoc']}'.")
    os.makedirs(LUU, exist_ok=True)
    json.dump(p, open(os.path.join(LUU, time.strftime("%Y%m%d-%H%M-") + p["ten"] + ".json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("Còn bước 12: python3 scripts/quy_trinh.py xong 12 \"…\" khi người dùng góp ý (hoặc 'không có góp ý').")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "xem":
        xem()
    elif a[0] == "bat-dau" and len(a) > 1:
        if "--ho-so" not in a:
            sys.exit("Thiếu --ho-so: video này của AI? (người dùng chính → hồ sơ của họ · khách/người lạ → hồ sơ riêng của khách)")
        bat_dau(a[1], a[a.index("--ho-so") + 1], a[a.index("--loai") + 1] if "--loai" in a else "dung")
    elif a[0] == "xong" and len(a) > 2:
        so = int(a[1])
        if len(a[2].strip()) < 8:
            sys.exit("Đầu ra quá sơ sài — ghi rõ đã làm gì (≥ 8 ký tự).")
        p = doc()
        if not p:
            sys.exit("Chưa có phiếu.")
        loi = kiem_dau_ra(p, so, a[2])
        if loi:
            sys.exit(loi)
        danh_dau(so, a[2])
    elif a[0] == "giao" and len(a) > 1:
        giao(a[1])
    else:
        print(__doc__)
