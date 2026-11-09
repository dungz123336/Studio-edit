# -*- coding: utf-8 -*-
"""TỪ ĐIỂN CÔNG CỤ ĐỘNG cho AI (thay cho in nguyên ai/cheat_sheet.md):
tu_dien(khung=(W, H)) -> str = phần cố định (cheat_sheet.md, điền đúng KHUNG + VÙNG AN TOÀN của khung này) + DANH MỤC MẪU sinh từ
dung.mau.danh_sach() (nhóm theo `nhom`, mỗi mẫu một dòng: id · tên · tham số chính · hợp nghĩa) + hợp đồng lớp `web` (dung.web.tu_dien_web()).
Tổng ≤ 9.000 ký tự: thiếu chỗ thì rút gọn danh mục theo bậc (bỏ hợp nghĩa → bớt tham số → chỉ id + tên).
tu_dien_gon(khung, phan=("Lớp", "anim", "am"), toi_da=TOI_DA_GON) -> str: CHỈ các mục cheat_sheet được chọn (lượt 2 tiếp phiên, không gửi lại 9.000 ký tự).
    python v3/ai/tu_dien.py [W H]      → in ra (kèm số ký tự ở stderr)
    python v3/ai/tu_dien.py --gon [W H] → bản rút gọn lượt 2"""
import os, sys

AI = os.path.dirname(os.path.abspath(__file__))
V3 = os.path.dirname(AI)
if V3 not in sys.path:
    sys.path.insert(0, V3)

TOI_DA = 22000           # lượt 1 gửi một lần; lượt 2 tiếp phiên chỉ gửi tu_dien_gon (≤ TOI_DA_GON)
TOI_DA_GON = 7000          # R2: đủ 3 mục Lớp (~3.8k) + anim (~1.2k) + am (~1.5k) cho lượt 2 (trước 2.500 chỉ còn mục Lớp)
TEN_NHOM = {"canh": "cảnh (toàn khung, cảnh trám)", "the": "thẻ / khối thông tin", "chu": "chữ hiệu ứng", "do_hoa": "đồ hoạ chỉ dẫn",
            "giao_dien": "giao diện giả", "chen": "chèn / khung", "chuyen_canh": "chuyển cảnh", "khung": "khung / lớp phủ"}
_BO_THAM_SO = {"tong_mau", "mau", "mau2", "font", "font_tieu_de", "co", "dam", "mau_chu", "hoa", "kieu_nen", "anh_nen", "do_toi",
               "ti_le_chu", "phong", "le", "bong", "gian", "day", "ve", "tre", "nhip", "bat_dau", "le_ngang", "le_doc"}       # tham số kiểu dáng chung — không lặp mỗi dòng

KHO_VIDEO = ("## KHO CHO VIDEO NÀY — TRƯỚC khi viết: MỞ ảnh doc/kho-video.jpg + đọc doc/kho-video.json (BẢNG SỐ ĐO của kho, máy không chọn hộ). "
             "`kho` = có gì/bao nhiêu; `sfx` = dict theo CHỮ KÝ vật lý (it_dung|bat_kho|bat_ngan|dang|cao|tram|chuoi|nhieu|ngan|dai), mỗi mục có `chu_ky` "
             "(cao/trầm · bật ngay/dâng dần · dài · ngân/khô · chuỗi · nhiễu/âm sắc · dB) và `da_dung` (số video trên máy này đã dùng — số đếm, không phải lời khuyên) "
             "→ chọn id theo ý đồ của bạn ở từng chỗ. Hoặc ghi TÍNH CHẤT TIẾNG bằng lời / từ tượng thanh Việt (\"tinh chuông cao trong ngắn ngân\", \"bùm trầm\", "
             "\"vút dài\", \"tách khô\", \"bíp\", \"rè\") → máy tra cả kho theo số đo, trả top-5 kèm số đo (diem, diem_td, khop, chu_ky, da_dung, dur) vào "
             "ke-hoach.json (tra_kho[].ung_vien), dựng bằng top-1; điểm ngang nhau thì tệp ít dùng xếp trước. "
             "Tra thêm bằng lệnh: `python v3/kho/tim.py sfx \"<tính chất>\"` (in 8 tệp + chữ ký + đã dùng). "
             "Vẫn ghi được TÊN NHÓM = khoá chữ ký trong bảng → máy xoay vòng tệp trong nhóm.")


def _vung_an_toan_md(W, H):
    try:
        import chung
        v = chung.vung_an_toan(W, H)
        return (f"Vùng an toàn khung {W}×{H} (máy chặn ngoai_vung_an_toan, trừ lớp toàn khung): trên {v['tren']}, dưới {v['duoi']}, "
                f"trái {v['trai']}, phải {v['phai']} (tỉ lệ cạnh khung).")
    except Exception:
        return f"Vùng an toàn: theo khung {W}×{H} (chung.vung_an_toan)."


def _co_dinh(W, H):
    try:
        with open(os.path.join(AI, "cheat_sheet.md"), encoding="utf-8") as f:
            s = f.read().strip()
    except Exception:
        s = "# Từ điển công cụ — cong-thuc.json {KHUNG} {VUNG_AN_TOAN}"
    khung = f"Khung của việc này: {W}×{H} ({'dọc' if H > W else 'ngang' if W > H else 'vuông'}); toạ độ 0..1 tính theo khung này."
    return s.replace("{KHUNG}", khung).replace("{VUNG_AN_TOAN}", _vung_an_toan_md(W, H))


def _ds_mau():
    try:
        from dung import mau as M
        return M.danh_sach()
    except Exception:
        return []


def _dong(m, bac):
    """bac 0: tên + tham số chính + hợp nghĩa · 1: tên + ≤3 tham số · 2: tên + 1 hợp nghĩa · 3: chỉ tên"""
    mid = str(m.get("id") or "").replace("mau.", "", 1)
    ten = str(m.get("ten") or "")
    if bac >= 2 and " (" in ten:            # gọn: bỏ phần giải thích trong ngoặc
        ten = ten.split(" (")[0]
    if bac >= 3 and len(ten) > 24:
        ten = ten[:23].rstrip() + "…"
    co = []
    if m.get("toan_khung"):
        co.append("K")
    if not m.get("dong", True) and bac < 3:
        co.append("tĩnh")
    dau = f"- {mid}" + (f"[{','.join(co)}]" if co else "") + f" {ten}"
    ts = [k for k in (m.get("tham_so") or {}) if k not in _BO_THAM_SO]
    bb = [str(x) for x in (m.get("bat_buoc") or m.get("tham_so_bat_buoc") or [])]
    ts = [("*" + k if k in bb else k) for k in ts]
    hn = [str(x) for x in (m.get("hop_nghia") or [])]
    if bac == 0:
        return dau + (f" · {', '.join(ts[:6])}" if ts else "") + (" · ≈ " + ", ".join(hn[:2]) if hn else "")
    if bac == 1:
        return dau + (f" · {', '.join(ts[:3])}" if ts else "")
    if bac == 2:
        return dau + (" · ≈ " + hn[0] if hn else "")
    return dau


def danh_muc_mau(bac=0):
    """bac 0..3: một dòng mỗi mẫu (càng cao càng gọn) · 4: các id liền một dòng mỗi nhóm"""
    ds = _ds_mau()
    if not ds:
        return ""
    nhom = {}
    for m in ds:
        nhom.setdefault(m.get("nhom") or "khac", []).append(m)
    dong = [f"## DANH MỤC MẪU ({len(ds)}) — kieu \"mau\", noi_dung{{mau:\"mau.<id>\",tham_so}}. Chi tiết: `python v3/ai/tu_dien.py --mau <id>`",
            "[K]=toàn khung. Tham số chung: mau/mau2 (vai|#hex), font, co, tong_mau toi|sang|kinh, kieu_nen toan|noi|trong, nhip, bat_dau. "
            "Mẫu chuyển cảnh: anim vào/ra bỏ = none (mẫu tự lo đường cong). go-theo-loi/phu-de-chay/karaoke-nen: bỏ moc → máy lấy mốc từ lời.",
            "Mọi mẫu chữ nhận le_ngang/le_doc (px lề) và bong (0..1 | list bóng như lớp chu | 0); chu-3d thêm phong_vao, tho. Tham số BẮT BUỘC "
            "(không có mặc định, thiếu → thieu_truong; đánh dấu * khi mẫu khai): khung-chat-ai.nhan_ai, tin-nhan.da_xem, trang-ca-nhan.nut2 — xem `--mau <id>`."]
    for n in sorted(nhom):
        ms = sorted(nhom[n], key=lambda x: str(x.get("id")))
        if bac >= 4:
            dong.append(f"### {TEN_NHOM.get(n, n)}: " + " · ".join(str(m.get("id")).replace("mau.", "", 1) + ("[K]" if m.get("toan_khung") else "") for m in ms))
        else:
            dong.append(f"### {TEN_NHOM.get(n, n)}")
            dong += [_dong(m, bac) for m in ms]
    return "\n".join(dong)


def chi_tiet_mau(mid):
    """thẻ đầy đủ một mẫu: mô tả, tham số (mô tả), mặc định của mẫu, hộp, sfx gợi ý, ví dụ"""
    import json
    mid = mid if mid.startswith("mau.") else "mau." + mid
    for m in _ds_mau():
        if m.get("id") == mid:
            d = [f"{mid} — {m.get('ten')} (nhóm {m.get('nhom')}{', toàn khung' if m.get('toan_khung') else ''})", str(m.get("mo_ta") or "")]
            for k, v in (m.get("tham_so") or {}).items():
                d.append(f"  {k}: {v}")
            if m.get("bat_buoc") or m.get("tham_so_bat_buoc"):
                d.append("bắt buộc: " + ", ".join(str(x) for x in (m.get("bat_buoc") or m.get("tham_so_bat_buoc"))))
            d.append("mặc định của mẫu: " + json.dumps(m.get("mac_dinh") or {}, ensure_ascii=False))
            d.append("hộp: " + json.dumps(m.get("hop") or {}, ensure_ascii=False) + " · sfx_goi_y: " + ", ".join(m.get("sfx_goi_y") or []))
            d.append("ví dụ tham_so: " + json.dumps(m.get("vi_du") or {}, ensure_ascii=False))
            return "\n".join(d)
    return f"không có mẫu {mid}"


TOI_DA_WEB = 2200


def _web(toi_da=TOI_DA_WEB):
    """hợp đồng lớp web (dung.web.tu_dien_web) — cắt ở ranh dòng để tổng từ điển ≤ TOI_DA (bản đầy đủ: `python v3/dung/web.py --tu-dien`)"""
    try:
        from dung import web as _W
        f = getattr(_W, "tu_dien_web", None)
        s = ("## " + f().strip()) if f else ""
    except Exception:
        return ""
    if len(s) <= toi_da:
        return s
    giu, n = [], 0
    for d in s.splitlines():
        if n + len(d) + 1 > toi_da - 80:
            break
        giu.append(d); n += len(d) + 1
    return "\n".join(giu) + "\n… (hợp đồng lớp web đầy đủ: dung.web.tu_dien_web() trong v3/)"


def tu_dien(khung=(1080, 1920)):
    W, H = (int(khung[0]), int(khung[1])) if khung else (1080, 1920)
    co_dinh = _co_dinh(W, H)
    web = _web()
    con = TOI_DA - len(co_dinh) - len(KHO_VIDEO) - len(web) - 6
    dm = ""
    for bac in range(5):
        dm = danh_muc_mau(bac)
        if len(dm) <= con:
            break
    if len(dm) > con:                                   # vẫn thừa: cắt theo dòng, báo số mẫu bị bỏ
        dong = dm.splitlines(); giu = []; n = 0
        for d in dong:
            if n + len(d) + 1 > con - 60:
                break
            giu.append(d); n += len(d) + 1
        bo = sum(1 for d in dong[len(giu):] if d.startswith("- "))
        dm = "\n".join(giu) + (f"\n… (+{bo} mẫu — xem web kho)" if bo else "")
    return "\n\n".join(x for x in (co_dinh, KHO_VIDEO, dm, web) if x)


def _muc(s, ten):
    """nội dung một mục `## <ten>…` của cheat_sheet (tới mục `## ` kế tiếp)"""
    ra, lay = [], False
    for d in s.splitlines():
        if d.startswith("## "):
            if lay:
                break
            lay = d[3:].strip().lower().startswith(ten.lower())
            if not lay:
                continue
        if lay:
            ra.append(d)
    return "\n".join(ra).strip()


def tu_dien_gon(khung=(1080, 1920), phan=("Lớp", "anim", "am"), toi_da=TOI_DA_GON):
    """lượt 2 (tiếp phiên lượt 1): chỉ các mục cheat_sheet được chọn + 1 dòng nhắc thieu_truong/tra_kho, ≤ toi_da ký tự (cắt ở ranh dòng)"""
    W, H = (int(khung[0]), int(khung[1])) if khung else (1080, 1920)
    s = _co_dinh(W, H)
    dau = (f"(khung {W}×{H}; mọi trường bỏ trống → quyết định kênh; thiếu → thieu_truong có `duong`: ghi trường đó vào công thức, hoặc thêm khoá "
           "vào quyet-dinh-kenh.json nếu muốn làm mặc định kênh; tra_kho[].ung_vien = top-5 kèm số đo, đổi bằng cách ghi id kho vào trường đó)")
    ds = [dau] + [m for m in (_muc(s, p) for p in phan) if m]
    ra = "\n".join(ds)
    if len(ra) > toi_da:
        dong = ra.splitlines(); giu = []; n = 0
        for d in dong:
            if n + len(d) + 1 > toi_da - 20:
                break
            giu.append(d); n += len(d) + 1
        ra = "\n".join(giu) + "\n…"
    return ra


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) > 1 and a[0] == "--mau":
        print(chi_tiet_mau(a[1]))
        sys.exit(0)
    gon = False
    if a and a[0] == "--gon":
        gon = True; a = a[1:]
    k = (int(a[0]), int(a[1])) if len(a) > 1 else (1080, 1920)
    s = tu_dien_gon(k) if gon else tu_dien(k)
    print(s)
    print(f"[{len(s)} ký tự]", file=sys.stderr)
