# -*- coding: utf-8 -*-
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Bộ não — nạp, tra, kiểm bài học, quản lý hồ sơ cá nhân. Xem nao/NAO.md.

    python3 nao.py nap                 # in: gốc (đề mục) + hồ sơ hiện tại + danh mục kiến thức — đọc trước khi dựng
    python3 nao.py tim "hook"          # tìm đoạn liên quan trong gốc + kiến thức + hồ sơ (theo từ khoá/thẻ)
    python3 nao.py kiem <file.md>      # kiểm bài học mới: đủ mục, có phần chống sao chép, không đè cái cũ
    python3 nao.py chi-muc             # dựng lại nao/kien-thuc/CHI-MUC.md
    python3 nao.py noi-hoc             # thư mục ghi bài học mới (người dùng: cua-toi · người bán: nguoi-ban)
    python3 nao.py ho-so               # hồ sơ đang dùng
    python3 nao.py ho-so tao <ten>     # tạo hồ sơ mới từ mẫu trống
    python3 nao.py ho-so tao <ten> --tu neon   # tạo hồ sơ từ bộ phong cách mẫu (soi-dong · bien-tap · neon)
    python3 nao.py ho-so dung <ten>    # chuyển hồ sơ
"""
import copy, json, os, re, shutil, sys, unicodedata, uuid

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAO = os.path.join(SKILL, "nao")
GOC, KT, CN, PCM = (os.path.join(NAO, x) for x in ("goc", "kien-thuc", "ca-nhan", "phong-cach-mau"))


def bo_phong_cach():
    return sorted(x for x in os.listdir(PCM) if os.path.isdir(os.path.join(PCM, x))) if os.path.isdir(PCM) else []


def kd(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


def ho_so():
    if os.environ.get("HO_SO", "").strip():       # Studio ghim hồ sơ theo việc
        return os.environ["HO_SO"].strip()
    try:
        return open(os.path.join(CN, "HIEN-TAI"), encoding="utf-8").read().strip()
    except OSError:
        return ""


def dau(p):
    """đọc front matter --- ... --- thành dict"""
    s = open(p, encoding="utf-8").read()
    m = re.match(r"---\n(.*?)\n---\n", s, re.S)
    d = {}
    if m:
        for ln in m.group(1).splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                d[k.strip()] = v.strip()
    return d, s


LOP_KT = ("nguoi-ban", "cua-toi")      # bài người bán (theo bản cập nhật) · bài người dùng tự học (không bao giờ bị đè)


def bai_hoc():
    """→ danh sách đường dẫn tương đối 'nguoi-ban/2026-…md', 'cua-toi/…md'"""
    ds = []
    for lop in LOP_KT:
        d = os.path.join(KT, lop)
        if os.path.isdir(d):
            ds += [f"{lop}/{f}" for f in sorted(os.listdir(d)) if f.endswith(".md") and f[0].isdigit()]
    return ds


def noi_hoc():
    """thư mục ghi bài học mới: máy người bán (có file NGUOI-BAN) → nguoi-ban, còn lại → cua-toi"""
    lop = "nguoi-ban" if os.path.exists(os.path.join(SKILL, "NGUOI-BAN")) else "cua-toi"
    d = os.path.join(KT, lop); os.makedirs(d, exist_ok=True)
    return d


def _phieu(so, dau_ra):
    try:
        sys.path.insert(0, os.path.join(SKILL, "scripts"))
        import quy_trinh
        quy_trinh.danh_dau(so, dau_ra)
    except Exception:
        pass


def nap():
    _phieu(2, f"đã nạp gốc + hồ sơ {ho_so()} + góp ý gần nhất")
    print("══ BỘ NÃO — nạp theo thứ tự: GỐC → CÁ NHÂN → (đọc video) → KIẾN THỨC theo vấn đề → KHO ══\n")
    print("① GỐC (luôn áp dụng)")
    for f in sorted(os.listdir(GOC)):
        s = open(os.path.join(GOC, f), encoding="utf-8").read()
        tieu = re.findall(r"^## (.+)$", s, re.M)
        print(f"  · nao/goc/{f}: " + " | ".join(tieu[:6]))
    hs = ho_so()
    print(f"\n② CÁ NHÂN — hồ sơ đang dùng: {hs or '(chưa có)'}")
    if hs:
        d = os.path.join(CN, hs)
        for f in sorted(os.listdir(d)):
            print(f"  · nao/ca-nhan/{hs}/{f}")
        gy = os.path.join(d, "gop-y.md")
        if os.path.exists(gy):
            dong = [l for l in open(gy, encoding="utf-8") if l.startswith("| ") and not l.startswith("| Ngày")]
            print("  góp ý gần nhất:")
            for l in dong[-4:]:
                print("    " + l.strip()[:150])
    print("\n③ KIẾN THỨC (chỉ mượn bài khớp vấn đề — `nao.py tim <chủ đề>`)")
    for f in bai_hoc():
        d, _ = dau(os.path.join(KT, f))
        tb = " [ĐÃ THAY bởi " + d["thay_boi"] + "]" if d.get("thay_boi") else ""
        print(f"  · {f}  ({d.get('do_tin_cay', '?')[:20]})  thẻ {d.get('the', '')}{tb}")
    print("\n④ KHO — tra sau khi đã biên kịch: kho/kho-hieu-ung.md (44 hiệu ứng) · "
          "<kho>/ban-do-kho/BAN-DO-KHO.md (nhạc, SFX, LUT, nền, font — `ban_do_kho.py tim`)")
    print("   ĐI CHỢ như editor (bước 7, bắt buộc): `scripts/tham_kho.py <ban-chu.json> --mood \"…\"` → phiếu đi chợ;"
          " luật chọn ở nao/goc/6-di-cho-kho.md")
    print()
    try:                       # thuộc kho: mọi công cụ, hiệu ứng, kiểu chữ, tài nguyên đang có — tự sinh, luôn mới
        import ban_ke_kho
        ban_ke_kho.main(ngan=True)
    except Exception as e:
        print(f"(không in được bản kê kho: {e} — chạy scripts/ban_ke_kho.py)")


def tim(tu):
    try:                       # chỉ ghi nháp — bước 5 do Claude tự `quy_trinh.py xong 5 "<bài mượn + lý do>"`
        sys.path.insert(0, os.path.join(SKILL, "scripts"))
        import quy_trinh
        quy_trinh.ghi_nhap(5, f"tra kiến thức: {tu}")
    except Exception:
        pass
    tk = [kd(x) for x in tu.split()]
    nguon = [os.path.join(GOC, f) for f in sorted(os.listdir(GOC))] + [os.path.join(KT, f) for f in bai_hoc()]
    hs = ho_so()
    if hs:
        nguon += [os.path.join(CN, hs, f) for f in sorted(os.listdir(os.path.join(CN, hs))) if f.endswith(".md")]
    for p in nguon:
        s = open(p, encoding="utf-8").read()
        doan = re.split(r"\n(?=#{2,3} )", s)
        for d in doan:
            if all(t in kd(d) for t in tk):
                tieu = d.strip().splitlines()[0][:90]
                print(f"── {os.path.relpath(p, SKILL)} › {tieu}")
                than = [l for l in d.strip().splitlines()[1:] if l.strip()][:6]
                for l in than:
                    print("   " + l[:160])
                print()


def kiem(p):
    loi = []
    d, s = dau(p)
    for k in ("nguon", "ngay", "the", "do_tin_cay"):
        if not d.get(k) or d[k].startswith("<"):
            loi.append(f"thiếu/chưa điền `{k}` ở phần đầu")
    for muc in ("## Nguyên tắc rút ra", "## Đối chiếu với não cũ", "## Dấu ấn riêng của nguồn"):
        if muc not in s:
            loi.append(f"thiếu mục «{muc}»")
    if re.search(r"#[0-9A-Fa-f]{6}", s.split("## Dấu ấn riêng")[0]):   # kể cả khi bài thiếu hẳn mục Dấu ấn
        loi.append("có mã màu cụ thể trong phần nguyên tắc — màu của nguồn là dấu ấn, chuyển xuống mục «Dấu ấn riêng»")
    if os.path.dirname(os.path.abspath(p)) not in [os.path.join(KT, l) for l in LOP_KT]:
        loi.append("bài học phải nằm trong nao/kien-thuc/cua-toi/ (hoặc nguoi-ban/ trên máy người bán) — xem `nao.py noi-hoc`")
    ten = os.path.basename(p)
    cung_ten = [b for b in bai_hoc() if os.path.basename(b) == ten and os.path.join(KT, b) != os.path.abspath(p)]
    if cung_ten:
        loi.append(f"trùng tên bài cũ {cung_ten[0]} — đặt tên mới, không ghi đè")
    print("ĐẠT — bài học hợp lệ" if not loi else "CHƯA ĐẠT:\n  - " + "\n  - ".join(loi))
    return not loi


def chi_muc():
    L = ["# Danh mục kiến thức (tự sinh — `scripts/nao.py chi-muc`)", "",
         "| Bài học | Nguồn | Ngày | Thẻ | Độ tin cậy | Trạng thái |", "|---|---|---|---|---|---|"]
    for f in bai_hoc():
        d, _ = dau(os.path.join(KT, f))
        tt = "thay bởi " + d["thay_boi"] if d.get("thay_boi") else "đang dùng"
        L.append(f"| `{f}` | {d.get('nguon', '')[:60]} | {d.get('ngay', '')} | {d.get('the', '')} | "
                 f"{d.get('do_tin_cay', '')[:30]} | {tt} |")
    open(os.path.join(KT, "CHI-MUC.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
    print("\n".join(L))


def _doc_cau_hinh_mau(duong):
    if not os.path.isfile(duong):
        return {}
    with open(duong, encoding="utf-8") as f:
        cau_hinh = json.load(f)
    if not isinstance(cau_hinh, dict):
        raise ValueError(f"Cấu hình mẫu phải là một đối tượng JSON: {duong}")
    return cau_hinh


def _tron_cau_hinh_mau(cu, moi, bo_qua_ghi_chu=False):
    for k, v in moi.items():
        if bo_qua_ghi_chu and (k.startswith("_") or k == "quyet_dinh"):
            continue
        cu[k] = {**cu[k], **copy.deepcopy(v)} if isinstance(v, dict) and isinstance(cu.get(k), dict) else copy.deepcopy(v)
    return cu


def tao_ho_so_moi(ten, bo=None):
    """Chuẩn bị hồ sơ trong thư mục ẩn, chỉ công bố khi mọi tệp đã ghi xong."""
    if not re.fullmatch(r"[\w-]+", ten or "") or ten.startswith("_"):
        raise ValueError("Mã hồ sơ chỉ gồm chữ, số, dấu gạch ngang; không bắt đầu bằng dấu gạch dưới")
    dich = os.path.join(CN, ten)
    if os.path.exists(dich):
        raise ValueError(f"Hồ sơ {ten} đã có — không ghi đè.")
    mau_trong = os.path.join(CN, "_mau")
    if not os.path.isdir(mau_trong):
        raise ValueError("Không tìm thấy thư mục mẫu hồ sơ nao/ca-nhan/_mau")
    if bo and (not re.fullmatch(r"[\w-]+", bo) or bo.startswith("_") or not os.path.isdir(os.path.join(PCM, bo))):
        raise ValueError(f"Không có bộ phong cách '{bo}'. Có: {', '.join(bo_phong_cach())}")

    from config import MAC_DINH
    cau_hinh = copy.deepcopy(MAC_DINH)
    # Đường dẫn kho, sức máy và máy chủ cập nhật thuộc cấu hình máy dùng chung.
    for k in ("kho", "may", "cap_nhat"):
        cau_hinh.pop(k, None)
    _tron_cau_hinh_mau(cau_hinh, _doc_cau_hinh_mau(os.path.join(mau_trong, "cau-hinh.json")))
    phong_cach_bo = ""
    cau_hinh_bo = {}
    if bo:
        goc_bo = os.path.join(PCM, bo)
        cau_hinh_bo = _doc_cau_hinh_mau(os.path.join(goc_bo, "cau-hinh.json"))
        _tron_cau_hinh_mau(cau_hinh, cau_hinh_bo, True)
        cau_hinh["_tu_bo"] = bo
        p = os.path.join(goc_bo, "phong-cach.md")
        if os.path.isfile(p):
            with open(p, encoding="utf-8") as f:
                noi_dung = f.read()
            phong_cach_bo = noi_dung.split("\n", 1)[-1].strip()

    tam = os.path.join(CN, ".tao-ho-so-" + uuid.uuid4().hex)
    os.mkdir(tam)
    try:
        shutil.copytree(mau_trong, tam, dirs_exist_ok=True)
        with open(os.path.join(tam, "cau-hinh.json"), "w", encoding="utf-8") as f:
            json.dump(cau_hinh, f, ensure_ascii=False, indent=2)
        if phong_cach_bo:
            pc = os.path.join(tam, "phong-cach.md")
            noi_dung = ""
            if os.path.isfile(pc):
                with open(pc, encoding="utf-8") as f:
                    noi_dung = f.read()
            with open(pc, "w", encoding="utf-8") as f:
                f.write(noi_dung.rstrip() + f"\n\n## Gu gốc từ bộ `{bo}` (chỉnh/xoá tuỳ khách)\n\n" + phong_cach_bo + "\n")
        if bo:
            # 1.2.21: giữ khả năng nhận quyết định kênh hợp lệ từ bộ mẫu.
            qd = cau_hinh_bo.get("quyet_dinh")
            if isinstance(qd, dict):
                import time
                sys.path.insert(0, os.path.join(SKILL, "v3"))
                try:
                    from ai import hop_dong as _HD
                    loi_qd = _HD.kiem_quyet_dinh(qd)
                except Exception as ex:
                    loi_qd = [{"duong": "quyet_dinh", "goi_y": f"không nạp được ai/hop_dong: {ex}"}]
                if loi_qd:
                    print("CẢNH BÁO: quyet_dinh của bộ sai khuôn, không chép:", "; ".join(f"{l['duong']}: {l['goi_y']}" for l in loi_qd[:5]))
                else:
                    p_qd = os.path.join(tam, "quyet-dinh.json")
                    with open(p_qd, "w", encoding="utf-8") as f:
                        json.dump(dict(qd, _nguon=f"bo:{bo}", _luc=time.strftime("%Y-%m-%d %H:%M:%S")), f, ensure_ascii=False, indent=1)
                    print(f"Đã chép quyết định kênh của bộ `{bo}` (phiên {qd.get('phien')}).")
            else:
                print(f"Bộ `{bo}` chưa có quyet_dinh — kênh sẽ phải Write quyet-dinh-kenh.json ở video đầu.")
        if os.path.exists(dich):
            raise ValueError(f"Hồ sơ {ten} đã có — không ghi đè.")
        os.rename(tam, dich)
        tam = None
        return dich
    finally:
        # Chỉ dọn đường dẫn tạm do lời gọi này tạo, không bao giờ dọn hồ sơ đích.
        if tam and os.path.normcase(os.path.dirname(os.path.realpath(tam))) == os.path.normcase(os.path.realpath(CN)):
            shutil.rmtree(tam)


def lenh_ho_so(args):
    if not args:
        hs = ho_so()
        print(f"Hồ sơ đang dùng: {hs or '(chưa có)'}")
        print("Có:", ", ".join(x for x in sorted(os.listdir(CN)) if os.path.isdir(os.path.join(CN, x)) and x != "_mau"))
        print("Bộ phong cách mẫu:", ", ".join(bo_phong_cach()), " (tạo hồ sơ từ bộ: ho-so tao <ten> --tu <bo>)")
        return
    if args[0] == "tao" and len(args) > 1:
        bo = args[args.index("--tu") + 1] if "--tu" in args and args.index("--tu") + 1 < len(args) else None
        try:
            dich = tao_ho_so_moi(args[1], bo)
        except (OSError, ValueError) as e:
            sys.exit(str(e))
        print(f"Đã tạo {dich}{' từ bộ ' + bo if bo else ''}. Hỏi người dùng theo HOI.md rồi chỉnh cau-hinh.json + phong-cach.md.")
    elif args[0] == "dung" and len(args) > 1:
        if not os.path.isdir(os.path.join(CN, args[1])):
            sys.exit(f"Không có hồ sơ {args[1]}.")
        open(os.path.join(CN, "HIEN-TAI"), "w", encoding="utf-8").write(args[1] + "\n")
        print(f"Đang dùng hồ sơ: {args[1]}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "nap":
        nap()
    elif a[0] == "tim":
        tim(" ".join(a[1:]))
    elif a[0] == "kiem":
        kiem(a[1])
    elif a[0] == "noi-hoc":
        print(noi_hoc())
    elif a[0] == "chi-muc":
        chi_muc()
    elif a[0] == "quy-trinh":
        print(open(os.path.join(NAO, "QUY-TRINH-CHUAN.md"), encoding="utf-8").read())
    elif a[0] == "ho-so":
        lenh_ho_so(a[1:])
