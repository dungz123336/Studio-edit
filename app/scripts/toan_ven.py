#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""TOÀN VẸN — kiểm các file quan trọng của gói CÓ BỊ SỬA không.

TEP-GOI.json liệt kê mã băm sha256 từng file của gói, và mang CHỮ KÝ SỐ của người bán (ky_so.KHOA_CAP_NHAT)
trên phần {phien_ban, tep}. Kẻ muốn sửa một file (vd gỡ đoạn kiểm bản quyền) phải sửa luôn mã băm trong TEP-GOI.json,
mà sửa TEP-GOI.json thì chữ ký không còn khớp — ký lại cần khoá bí mật của người bán (không nằm trong máy khách).

Vì vậy: sửa bất kỳ file nào trong danh sách canh gác → kiểm này báo HỎNG. Chạy được khi và chỉ khi gói còn nguyên.

    python3 toan_ven.py            # in KẾT QUẢ: NGUYÊN VẸN / BỊ SỬA: <file>
    python3 toan_ven.py --json

Giới hạn: đây là kiểm phía máy khách, người rành code có thể vô hiệu hoá. Mục tiêu là làm KHÓ, không phải bất khả xâm phạm;
phần giá trị nhất được bảo vệ thêm bằng mã hoá mở khoá từ máy chủ (xem bo_nao_khoa.py).
"""
import hashlib, json, os, sys

DIR = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(DIR)
sys.path.insert(0, DIR)
import ky_so

TEP_GOI = os.path.join(SKILL, "TEP-GOI.json")


def _canh_gac(tep):
    """Những file BẮT BUỘC đúng mã băm: mọi script .py, bộ não gốc, mã Studio, và các file bảo mật."""
    ra = set()
    for rel in tep:
        r = rel.replace("\\", "/")
        if r.startswith("scripts/") and r.endswith(".py"):
            ra.add(rel)
        elif r.startswith("nao/goc/"):
            ra.add(rel)
        elif r.startswith("studio/") and r.endswith(".py"):
            ra.add(rel)
        elif r.startswith("cong-thuc/") and r.endswith(".py"):
            ra.add(rel)
    return ra


def _bam(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def kiem():
    """→ (ok, thong_bao). Máy người bán (có NGUOI-BAN) luôn ok."""
    if os.path.exists(os.path.join(SKILL, "NGUOI-BAN")):
        return True, "máy người bán"
    try:
        g = json.load(open(TEP_GOI, encoding="utf-8"))
    except Exception:
        return False, "thiếu/hỏng TEP-GOI.json — cài lại từ link chính chủ"
    nd = {"phien_ban": g.get("phien_ban", ""), "tep": g.get("tep", {})}
    if not ky_so.kiem(ky_so.KHOA_CAP_NHAT, ky_so.chuan(nd), g.get("chu_ky", "")):
        return False, "TEP-GOI.json sai chữ ký (bị sửa?) — cài lại từ link chính chủ"
    tep = g.get("tep", {})
    for rel in sorted(_canh_gac(tep)):
        p = os.path.join(SKILL, rel)
        if not os.path.isfile(p):
            return False, f"thiếu file {rel} — cài lại từ link chính chủ"
        if _bam(p) != tep[rel]:
            return False, f"file {rel} đã bị sửa — cài lại từ link chính chủ"
    return True, "nguyên vẹn"


if __name__ == "__main__":
    ok, tb = kiem()
    if "--json" in sys.argv:
        print(json.dumps({"ok": ok, "tb": tb}, ensure_ascii=False))
    else:
        print(("NGUYÊN VẸN · " if ok else "BỊ SỬA · ") + tb)
    sys.exit(0 if ok else 1)
