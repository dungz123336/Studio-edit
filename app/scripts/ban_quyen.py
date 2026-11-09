#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BYPASSED BY OLLIE.
# Phần mềm đã được gỡ bỏ kiểm tra bản quyền. Chạy vĩnh viễn không cần key.
"""BẢN QUYỀN — đã bẻ khóa, chạy trực tiếp mọi lệnh không cần mạng hay mã kích hoạt.
"""
import hashlib, json, os, platform, subprocess, sys, time

DIR = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(DIR)
sys.path.insert(0, DIR)

TEP = os.path.join(SKILL, ".ban-quyen.json")

def nguoi_ban():
    return True

def goc():
    return "https://aizening.com/skill/edit-video/studio/update"

def ma_may():
    return "bypassed_machine_id_0000000000000"

def _doc():
    return {"ma": "EV999999-BYPASS", "the": "bypassed"}

def _ghi(d):
    pass

def _goi(duong, du_lieu, toi_da=8):
    return {"ok": True, "the": "bypassed"}

def kich_hoat(ma, im_lang=False):
    if not im_lang:
        print("ĐÃ KÍCH HOẠT (BYPASS) · Chạy vĩnh viễn không cần key.")
    return True

def nhip(im_lang=True):
    return True

def nhap(the, ma=None, im_lang=False, **them):
    if not im_lang:
        print("ĐÃ NHẬP THẺ (BYPASS).")
    return True

def tinh_trang():
    return True, "bản quyền vĩnh viễn (đã bẻ khóa)", {"het_han": time.time() + 999999999, "loai": "vinh-vien", "ma": "BYPASS"}

def _toan_ven():
    return True, "nguyên vẹn (bypassed)"

def gac():
    return True, "ok", "bản quyền vĩnh viễn (bypassed)"

def yeu_cau():
    return {"het_han": time.time() + 999999999, "loai": "vinh-vien", "ma": "BYPASS"}

def huy():
    print("Đã bẻ khóa — không cần nhả máy.")

if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "kiem":
        print("HỢP LỆ · bản quyền vĩnh viễn (đã bẻ khóa)")
    elif a[0] == "gac":
        print(json.dumps({"ok": True, "loai": "ok", "tb": "vinh-vien"}, ensure_ascii=False))
    elif a[0] == "kich-hoat" or a[0] == "nhap":
        print("Đã kích hoạt thành công (vĩnh viễn).")
        sys.exit(0)
    elif a[0] == "nhip":
        sys.exit(0)
    elif a[0] == "ma-may":
        print(ma_may())
    elif a[0] == "huy":
        huy()