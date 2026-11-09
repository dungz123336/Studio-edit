#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Tạo font TĨNH (một độ đậm, tên họ riêng) từ font biến thiên trong kho → <kho>/fonts/tinh/.

libass (phụ đề) và PIL chọn độ đậm của font biến thiên không ổn định; mỗi độ đậm phải là một file có tên họ riêng
("Lexend SemiBold") thì hồ sơ phong cách mới gọi đúng. Bộ cài tự chạy; chạy lại an toàn (có rồi thì bỏ qua).

    python3 tao_font_tinh.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kit

# (file biến thiên, {trục: giá trị}, tên file ra, tên họ) — font OFL, đã kiểm đủ dấu tiếng Việt
CAN = [
    ("Manrope-Var.ttf",                {"wght": 500}, "Manrope-Medium.ttf",        "Manrope Medium"),
    ("Manrope-Var.ttf",                {"wght": 700}, "Manrope-Bold.ttf",          "Manrope Bold"),
    ("Manrope-Var.ttf",                {"wght": 600}, "Manrope-SemiBold.ttf",      "Manrope SemiBold"),
    ("PlayfairDisplay-Italic-Var.ttf", {"wght": 500}, "PlayfairDisplay-MediumItalic.ttf", "Playfair Display MI"),
    ("Lexend-Var.ttf",                 {"wght": 400}, "Lexend-Regular.ttf",        "Lexend Regular"),
    ("Lexend-Var.ttf",                 {"wght": 600}, "Lexend-SemiBold.ttf",       "Lexend SemiBold"),
    ("SpaceGrotesk-Var.ttf",           {"wght": 700}, "SpaceGrotesk-Bold.ttf",     "Space Grotesk Bold"),
    ("SpaceGrotesk-Var.ttf",           {"wght": 500}, "SpaceGrotesk-Medium.ttf",   "Space Grotesk Medium"),
    ("Lora-Italic-Var.ttf",            {"wght": 600}, "Lora-SemiBoldItalic.ttf",   "Lora SemiBold Italic"),
    ("Lora-Italic-Var.ttf",            {"wght": 400}, "Lora-Italic.ttf",           "Lora Italic"),
    ("Baloo2-Var.ttf",                 {"wght": 800}, "Baloo2-ExtraBold.ttf",      "Baloo 2 ExtraBold"),
]


def doi_ten(f, ho):
    n = f["name"]
    for rec in list(n.names):
        if rec.nameID in (16, 17, 25):
            n.removeNames(nameID=rec.nameID)
    for nid, val in ((1, ho), (2, "Regular"), (4, ho), (6, ho.replace(" ", "-"))):
        n.setName(val, nid, 3, 1, 0x409)
        n.setName(val, nid, 1, 0, 0)


def main():
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    nguon = os.path.join(kit.kho(), "fonts")
    ra = os.path.join(nguon, "tinh"); os.makedirs(ra, exist_ok=True)
    tao = bo = thieu = 0
    for src, truc, ten, ho in CAN:
        dich = os.path.join(ra, ten)
        if os.path.exists(dich):
            bo += 1; continue
        p = os.path.join(nguon, src)
        if not os.path.exists(p):
            print(f"  thiếu font gốc {src} — bỏ qua {ten}"); thieu += 1; continue
        f = TTFont(p)
        day = {a.axisTag: a.defaultValue for a in f["fvar"].axes}
        day.update(truc)
        g = instancer.instantiateVariableFont(f, day)
        doi_ten(g, ho)
        g.save(dich); tao += 1
        print(f"  + {ten}  ({ho})")
    print(f"font tĩnh: tạo {tao} · đã có {bo} · thiếu gốc {thieu}  → {ra}")


if __name__ == "__main__":
    main()
