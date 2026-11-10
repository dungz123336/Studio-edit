# -*- coding: utf-8 -*-
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Studio 1.3 — lệnh của giao diện + AI. Lõi dựng là v3/ (engine mở); tệp này chỉ giữ PHIẾU (mốc, hồ sơ, con trỏ việc)
và chuyển lệnh sang v3/cau_noi.py.

  python v2/st.py bat-dau <ten> --video a.mp4 [b.mp4] --ho-so <hs> [--phu c.mp4] [--mau mau.mp4] [--goi review]
                  [--yeu-cau "..."] [--chinh-mau] [--4k] [--nhin thua|vua|day]
  python v2/st.py nhanh doc                 # máy đọc hết → in BẢN TÓM TẮT + TỪ ĐIỂN CÔNG CỤ
  python v2/st.py nhanh tron                # kiểm luật + dựng + 8 khung xem lại + 3 bìa (sửa công thức rồi chạy lại: chỉ dựng phần đổi)
  python v2/st.py nhanh giao --bia 1        # giao + bìa chính
  python v2/st.py nhanh mat-na [--luc 3,7]  # xem trước mặt nạ tách người (doc/mat-na.jpg)
  python v2/st.py nhanh khung --tu A --den B [--fps N] [--o-lon]   # nhìn kỹ một đoạn (giây gốc) → doc/soi-A-B.jpg
  python v2/st.py gop-y "chữ to hơn"        # góp ý → sửa Style Spec của hồ sơ (hoàn tác: gop-y --hoan-tac)
  python v2/st.py phong-cach [ds | xem /review]
  python v2/st.py kho <loai|-> "<nghĩa>"    # tra kho theo nghĩa
  python v2/st.py capcut [--du-an D]        # xuất project CapCut
  python v2/st.py cho <log> [--chu XONG]    # chờ lệnh nền
  python v2/st.py xem | tiep
"""
import os, sys, argparse, time, json, subprocess, re
_SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_SKILL, "studio"))
from moi_truong import python_da_chon
_SELECTED_PYTHON = python_da_chon()
_VENV = _SELECTED_PYTHON or os.path.join(_SKILL, ".venv",
                     "Scripts" if os.name == "nt" else "bin", "python.exe" if os.name == "nt" else "python")
if __name__ == "__main__" and not _SELECTED_PYTHON and os.path.exists(_VENV) and os.path.normcase(os.path.abspath(sys.executable)) != os.path.normcase(_VENV) \
        and not os.environ.get("_ST_DA_CHUYEN"):
    # gọi nhầm Python hệ thống → tự chạy lại bằng Python của Studio, cùng tham số
    sys.exit(subprocess.call([_VENV, os.path.abspath(__file__)] + sys.argv[1:], env=dict(os.environ, _ST_DA_CHUYEN="1")))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chung as C
import buoc as B
import quy_trinh2 as Q

V3 = os.path.join(C.SKILL, "v3")


def _env():
    return dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")


def _v3(*args):
    """chạy một lệnh của lõi 1.3 (tiến trình riêng) và thoát cùng mã"""
    sys.exit(subprocess.run([C.python_skill(), *args], cwd=C.SKILL, env=_env()).returncode)


# ───────── nhận diện yêu cầu từ lời người dùng
_KHONG_MAU = re.compile(r"(?<!\w)(không|khong|ko|k|khỏi|đừng|chẳng)\s*(cần|được|phải)?\s*(chỉnh|sửa|đổi|làm|grade|đụng)\s*(màu|mau|tone|tông)|"
                        r"giữ\s*(nguyên)?\s*màu", re.I)
_CHINH_MAU = re.compile(r"(chỉnh|sửa|đổi|làm|nâng|cân|chỉnh sửa)\s*(lại\s*)?(màu|mau|tone|tông|sáng|độ sáng|da)|màu\s*(điện ảnh|phim|cinematic|ấm|lạnh|"
                        r"vintage|film|retro)|tone\s*màu|tông\s*màu|\bgrade\b|\bgrading\b|color\s*grad|\blut\b|blend\s*màu|"
                        r"làm\s*(đẹp|tươi|rực)\s*(màu|hình)?|tăng\s*(sáng|màu|bão hoà|tương phản)", re.I)


def chinh_mau_tu_loi(loi):
    """LUẬT CỨNG giữ màu gốc: chỉ chỉnh màu khi người dùng YÊU CẦU ("chỉnh màu", "màu điện ảnh", "tone ấm", "grade"…)"""
    if not loi:
        return False
    s = " ".join(str(loi).lower().split())
    return bool(_CHINH_MAU.search(_KHONG_MAU.sub(" ", s)))


def _tim_goi(lenh):
    sys.path.insert(0, V3)
    try:
        from phong_cach import ap
        return ap.tim(lenh)
    finally:
        sys.path.remove(V3)


# ───────── lệnh
def lenh_bat_dau(a):
    tt = {"video": [os.path.abspath(v) for v in a.video], "goi": None, "yeu_cau": a.yeu_cau, "muc_dich": a.muc_dich,
          "nen_tang": a.nen_tang, "can_duyet": bool(a.can_duyet),
          "mau_video": os.path.abspath(a.mau) if a.mau else None,
          # chỉ chỉnh màu khi người dùng yêu cầu hoặc CHỌN phong cách cho video này (video mẫu KHÔNG tính)
          "cho_chinh_mau": bool(a.chinh_mau) or bool(a.goi) or chinh_mau_tu_loi(a.yeu_cau),
          "phu": [os.path.abspath(v) for v in (a.phu or [])], "quy_trinh": "nhanh"}
    if a.nhin:
        tt["nhin"] = a.nhin                       # mức nhìn khung cho AI (lõi 1.3 doc/khung.py); bỏ = hồ sơ kênh / cấu hình / vua
    for v in tt["video"] + tt["phu"] + ([tt["mau_video"]] if tt["mau_video"] else []):
        if not os.path.exists(v):
            Q.chan(f"không thấy tệp {v}")
    if a.goi:
        g = _tim_goi(a.goi)
        if not g:
            Q.chan(f"không có phong cách `{a.goi}` — xem: python v2/st.py phong-cach ds")
        tt["goi"] = g
    yc = a.yeu_cau or ""
    tt["xuat_4k"] = bool(a.xuat_4k) or bool(re.search(
        r"\b(4k|2160p?|uhd)\b|chất lượng (gốc|nguyên|bằng)|nguyên (bản|chất lượng)|bằng (với )?(video|file) gốc|độ phân giải gốc", yc, re.I))
    tt["giu_fps"] = bool(re.search(r"\b(50|60) ?fps\b|nguyên (bản|chất lượng)|bằng (với )?(video|file) gốc|giữ (nguyên )?fps", yc, re.I))
    Q.mo(a.ten, a.ho_so, a.thu_muc, tt, de=a.de)
    lenh_nap(a)
    print("▶ Chạy tiếp `python v2/st.py nhanh doc` (máy đọc hết + in bản tóm tắt cho AI)")


def lenh_nap(a=None):
    ph = Q.doc_phieu()
    t0 = time.time()
    C.ghi(os.path.join(ph["du_an"], "01-ho-so.json"), {"ho_so": ph["ho_so"], "loi": "1.3", "yeu_cau": (ph.get("thong_tin") or {}).get("yeu_cau")})
    Q.danh_dau("0.2", "01-ho-so.json", "st.py nap (1.3)", time.time() - t0)


def lenh_nhanh(a):
    lenh_ = [os.path.join(V3, "cau_noi.py"), a.viec]
    if a.viec == "giao" and a.bia:
        lenh_ += ["--bia", str(a.bia)]
    if a.viec == "mau" and getattr(a, "id", None):
        lenh_ += ["--id", a.id]
    if a.viec == "mat-na" and a.luc:
        lenh_ += ["--luc", a.luc]
    if a.viec == "khung":
        for co, gt in (("--tu", a.tu), ("--den", a.den), ("--fps", a.fps), ("--nguon", getattr(a, "nguon", None))):
            if gt is not None:
                lenh_ += [co, str(gt)]
        if a.o_lon:
            lenh_ += ["--o-lon"]
    if a.viec == "broll":
        lenh_ += list(getattr(a, "duong", None) or [])
    _v3(*lenh_)


def lenh_cho(a):
    """chờ CHẶN tới khi file log có chữ đích (mặc định XONG) hoặc có lỗi — tối đa a.toi_da giây (≤ 590)"""
    t0 = time.time()
    het = min(float(a.toi_da or 590), 590)
    while time.time() - t0 < het:
        try:
            s = open(a.file, encoding="utf-8", errors="replace").read() if os.path.exists(a.file) else ""
        except OSError:
            s = ""
        if a.chu in s or any(x in s for x in ("Traceback", "CHẶN", "Lỗi:")):
            break
        if not os.path.exists(a.file) and time.time() - t0 > 30:
            print(f"✗ CHƯA CÓ LOG sau 30s — lệnh nền không chạy (thư mục {os.path.dirname(a.file)} có tồn tại không?)"); return
        time.sleep(5)
    s = open(a.file, encoding="utf-8", errors="replace").read() if os.path.exists(a.file) else "(chưa có log)"
    xong = a.chu in s
    print(("✓ XONG" if xong else ("✗ CÓ LỖI" if "Traceback" in s else "… CHƯA XONG — gọi lại `st.py cho` để chờ tiếp"))
          + f" sau {time.time() - t0:.0f}s")
    for dong in s.strip().splitlines()[-8:]:
        print(dong)


def lenh_capcut(a):
    from xuat import capcut as CC
    d = a.du_an or Q.doc_phieu()["du_an"]
    CC.xuat(d, a.ten)


def lenh_gop_y(a):
    """góp ý của người dùng → diff trên Style Spec của hồ sơ (v3/hoc/gop_y.py)"""
    ph = Q.doc_phieu(bat_buoc=False)
    hs = a.ho_so or (ph or {}).get("ho_so") or os.environ.get("HO_SO")
    if not hs:
        Q.chan("gop-y cần hồ sơ: --ho-so <hs> (hoặc có phiếu đang mở)")
    if a.hoan_tac:
        _v3(os.path.join(V3, "hoc", "gop_y.py"), "hoan-tac", hs)
    if a.khong is not None or not a.noi_dung:
        print("  Không có góp ý — giữ nguyên hồ sơ."); return
    _v3(os.path.join(V3, "hoc", "gop_y.py"), "ap", hs, a.noi_dung, *(["--thu"] if a.thu else []))


def lenh_phong_cach(a):
    lenh_ = [os.path.join(V3, "phong_cach", "ap.py"), a.viec or "ds"]
    if a.goi_ten:
        lenh_.append(a.goi_ten)
    _v3(*lenh_)


def lenh_kho(a):
    _v3(os.path.join(V3, "kho", "tim.py"), *(a.con or []))


def lenh_tiep(a):
    """1.2.21 (1j): nối đúng bước theo viec.json["buoc_xong"] của lõi 1.3 (doc → tron → giao); tiến trình nền còn chạy thì bảo chờ"""
    ph = Q.doc_phieu()
    if ph.get("dong"):
        print("Phiếu đã giao xong."); return
    d = ph.get("du_an") or ""
    try:
        v = json.load(open(os.path.join(d, "viec.json"), encoding="utf-8"))
    except Exception:
        v = {}
    bx = set((v or {}).get("buoc_xong") or [])
    cu_1220 = "buoc_xong" not in (v or {})                 # R4a: dự án 1.2.20 chưa có buoc_xong → suy từ .v3-<bước>.json trang_thai=xong
    for buoc in ("doc", "tron"):                           # tiến trình nền đang chạy / bị ngắt dở
        try:
            st = json.load(open(os.path.join(d, f".v3-{buoc}.json"), encoding="utf-8"))
        except Exception:
            st = {}
        if st.get("trang_thai") == "chay":
            print(f"Bước `{buoc}` đang chạy nền → chạy lại `python v2/st.py nhanh {buoc}` để chờ tiếp (máy không làm lại từ đầu)."); return
        if cu_1220 and st.get("trang_thai") == "xong":
            bx.add(buoc)
    if "giao" in bx:
        print("Đã giao. Sửa thêm: sửa cong-thuc.json → nhanh tron → nhanh giao."); return
    if "tron" in bx and os.path.isfile(os.path.join(d, "dung", "thanh-pham.mp4")):
        phan, l = 2, "mở dung/xem-lai.jpg + bìa → sửa công thức + `python v2/st.py nhanh tron`, hoặc `python v2/st.py nhanh giao --bia <n>`"
    elif "doc" in bx and os.path.isfile(os.path.join(d, "doc", "tom-tat.md")):
        phan, l = 1, ("sửa cong-thuc.json rồi `python v2/st.py nhanh tron` (lần trước dừng giữa chừng — proxy/lời/base/khúc đã có sẽ dùng lại)"
                      if os.path.isfile(os.path.join(d, "cong-thuc.json")) else "viết cong-thuc.json theo từ điển công cụ → `python v2/st.py nhanh tron`")
    else:
        phan, l = 0, "python v2/st.py nhanh doc" + (" (lần trước dừng giữa chừng — proxy/lời đã có sẽ dùng lại)" if os.path.isdir(os.path.join(d, "cache")) else "")
    print(f"Phần {phan + 1}/3 · {B.PHAN[phan][0]}" + (f" · đã xong: {', '.join(sorted(bx))}" if bx else ""))
    print(f"  → {l}")


def main():
    ap = argparse.ArgumentParser(prog="st.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="lenh")
    p = sp.add_parser("bat-dau"); p.add_argument("ten"); p.add_argument("--video", nargs="+", required=True)
    p.add_argument("--ho-so", required=True); p.add_argument("--goi"); p.add_argument("--yeu-cau"); p.add_argument("--muc-dich")
    p.add_argument("--nen-tang"); p.add_argument("--thu-muc"); p.add_argument("--de", action="store_true")
    p.add_argument("--can-duyet", action="store_true", help="người dùng muốn xem/duyệt trước khi dựng")
    p.add_argument("--mau", help="video MẪU để học cách làm (bố cục, chữ, đồ hoạ, nhịp) — KHÔNG đổi màu video")
    p.add_argument("--nhanh", action="store_true", help=argparse.SUPPRESS)          # tương thích lời dặn cũ
    p.add_argument("--loi-co-san", help=argparse.SUPPRESS)
    p.add_argument("--chinh-mau", action="store_true", help="người dùng YÊU CẦU chỉnh màu (mặc định giữ 100%% màu gốc)")
    p.add_argument("--4k", dest="xuat_4k", action="store_true", help="người dùng YÊU CẦU xuất 4K")
    p.add_argument("--phu", nargs="*", default=[], help="video PHỦ (B-roll, quay màn hình) — đặt lên video chính, không nối tiếp")
    p.add_argument("--nhin", choices=["thua", "vua", "day"], help="mức nhìn khung cho AI (bỏ = theo hồ sơ kênh / cấu hình)")
    p = sp.add_parser("nhanh"); p.add_argument("viec", choices=["doc", "tron", "giao", "mat-na", "khung", "mau", "broll"])
    p.add_argument("duong", nargs="*", help="(broll) tệp video / thư mục B-roll")
    p.add_argument("--nguon", default=None, help="(khung) chỉ số hoặc đường dẫn B-roll")
    p.add_argument("--bia", default=None, help="(giao) số bìa chính 1|2|3")
    p.add_argument("--luc", default=None, help="(mat-na) các giây cần xem, cách nhau dấu phẩy")
    p.add_argument("--id", default=None, help="(mau) id mẫu cần xem kỹ")
    p.add_argument("--tu", type=float, default=None, help="(khung) từ giây gốc")
    p.add_argument("--den", type=float, default=None, help="(khung) đến giây gốc")
    p.add_argument("--fps", type=float, default=None, help="(khung) số khung mỗi giây, tới 30 (bỏ = vừa một bảng)")
    p.add_argument("--o-lon", action="store_true", help="(khung) ô lớn hơn")
    p = sp.add_parser("capcut"); p.add_argument("--du-an"); p.add_argument("--ten"); p.add_argument("--khong-do-hoa", action="store_true")
    p = sp.add_parser("cho"); p.add_argument("file"); p.add_argument("--chu", default="XONG"); p.add_argument("--toi-da", type=float, default=590)
    p = sp.add_parser("gop-y"); p.add_argument("noi_dung", nargs="?"); p.add_argument("--khong"); p.add_argument("--ho-so")
    p.add_argument("--hoan-tac", action="store_true"); p.add_argument("--thu", action="store_true")
    p.add_argument("--loai", help=argparse.SUPPRESS); p.add_argument("--khoa", help=argparse.SUPPRESS); p.add_argument("--gia-tri", help=argparse.SUPPRESS)
    p = sp.add_parser("phong-cach"); p.add_argument("viec", nargs="?"); p.add_argument("goi_ten", nargs="?")
    p = sp.add_parser("kho"); p.add_argument("con", nargs=argparse.REMAINDER)
    sp.add_parser("nap"); sp.add_parser("tiep"); sp.add_parser("xem")
    a = ap.parse_args()
    bang = {"bat-dau": lenh_bat_dau, "nap": lenh_nap, "nhanh": lenh_nhanh, "cho": lenh_cho, "capcut": lenh_capcut,
            "gop-y": lenh_gop_y, "phong-cach": lenh_phong_cach, "kho": lenh_kho, "tiep": lenh_tiep, "xem": lambda a: Q.trang_thai()}
    if a.lenh not in bang:
        ap.print_help(); return
    try:
        bang[a.lenh](a)
    except Q.Chan as e:
        if e.code not in (1, None):
            print(e.code)
        sys.exit(2)


if __name__ == "__main__":
    main()
