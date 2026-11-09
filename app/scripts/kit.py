#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Tra đường dẫn tài nguyên trong kho. Kho ở đâu do cau-hinh.json quyết định,
biến môi trường VIDEOKIT ghi đè được."""
import os, functools
import nen_tang as NT
import config

SUB = ["", "fonts", "fonts/tinh", "sfx", "music", "grids", "overlays", "luts",
       "characters", "titles", "cards", "nguon", "presets"]


KEM_THEO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "tai-nguyen")      # kho tài nguyên giải nén kèm gói (khác `kho/` = tài liệu công cụ)


def kho():
    """Thứ tự tìm: biến môi trường VIDEOKIT → cau-hinh.json → kho đi kèm trong gói.

    Bản bán kèm kho giải nén ra `<skill>/tai-nguyen`. Nếu đường dẫn trong cấu hình chưa có
    mà kho đi kèm thì có, dùng luôn kho đi kèm — người mua chạy được ngay, không
    phải sửa gì.
    """
    mt = os.environ.get("VIDEOKIT")
    if mt:
        return os.path.expanduser(mt)
    d = os.path.expanduser(config.lay("kho", "duong_dan",
                                      mac_dinh=NT.kho_mac_dinh()))
    if not os.path.isdir(d) and os.path.isdir(KEM_THEO):
        return KEM_THEO
    return d


def bo_mua():
    """Thư mục bộ tài nguyên mua thêm (cau-hinh.json → kho.bo_mua, biến môi trường BO_MUA ghi đè).
    Trả về chuỗi rỗng nếu người dùng không có bộ này — nơi gọi phải tự lùi về kho chính."""
    d = os.path.expanduser(os.environ.get("BO_MUA") or config.lay("kho", "bo_mua", mac_dinh="") or "")
    return d if d and os.path.isdir(d) else ""


# ───────── bộ tài nguyên quà tặng (~10 GB, tải từ Drive của người bán) — nhận theo thư mục con, không theo tên
BO_QUA = ("1.Kho nhạc và SFX", "1-1. SFX Trending Chọn Lọc", "2. Back Ground - Icon Trending",
          "3. 405 FONT Việt Hóa Edit Không Khó", "4. Lut màu", "5. Background động + Hiệu ứng chói lòa")


def _nfc(s):
    import unicodedata
    return unicodedata.normalize("NFC", s)


def tim_bo_mua(goc=None, sau=3):
    """Tìm bộ quà tặng đã tải về. Drive chia 10 GB thành nhiều zip → giải nén ra nhiều thư mục, mỗi thư mục chứa
    một phần → gộp lại bằng liên kết (không chép thêm dung lượng). Trả về đường dẫn dùng được, '' nếu chưa có."""
    ky = {_nfc(x) for x in BO_QUA}
    goc = goc or [os.path.expanduser(x) for x in ("~/Downloads", "~/Desktop", "~/Documents", "~/Movies", "~/Videos", "~")]
    phan, da = [], set()

    def quet(d, muc):
        if muc > sau or d in da:
            return
        da.add(d)
        try:
            con = [x for x in os.listdir(d) if not x.startswith(".")]
        except OSError:
            return
        if any(_nfc(x) in ky for x in con):
            phan.append(d); return
        for x in con:
            p = os.path.join(d, x)
            if os.path.isdir(p) and not os.path.islink(p) and x not in ("Library", "node_modules", ".Trash", "AppData"):
                quet(p, muc + 1)
    for g in goc:
        if os.path.isdir(g):
            quet(g, 0 if g != os.path.expanduser("~") else 2)
    if not phan:
        return ""
    du = [p for p in phan if ky <= {_nfc(x) for x in os.listdir(p)}]
    if len(phan) == 1 or (du and len(phan) == len(du)):
        return (du or phan)[0]
    return gop_bo_mua(phan)


def gop_bo_mua(phan, dich=None):
    """gộp nhiều phần giải nén thành 1 cây thư mục: thư mục thật, tệp là liên kết (Windows: liên kết cứng)"""
    import shutil
    dich = dich or os.path.join(os.path.dirname(kho()), "BoQuaTang-gop")
    hong = []
    for p in phan:
        for r, ds, fs in os.walk(p):
            rel = os.path.relpath(r, p)
            os.makedirs(os.path.join(dich, rel), exist_ok=True)
            for f in fs:
                d, s = os.path.join(dich, rel, f), os.path.join(r, f)
                if os.path.lexists(d):
                    if os.path.islink(d) and not os.path.exists(d):      # 1.2.21: liên kết hỏng (ổ/thư mục nguồn đã dời) → làm lại
                        try:
                            os.remove(d)
                        except OSError:
                            continue
                    else:
                        continue
                try:
                    os.symlink(s, d)
                except OSError:
                    try:
                        os.link(s, d)
                    except OSError:
                        try:
                            shutil.copy2(s, d)                          # 1.2.21: không liên kết được (khác ổ, không quyền) → chép thật
                        except OSError as e:
                            hong.append(f"{s}: {e}")
    if hong:
        print(f"  ! {len(hong)} tệp không gộp được vào {dich} (ví dụ: {hong[0][:120]})")
    return dich


@functools.lru_cache(maxsize=None)
def find(ten):
    """Tìm theo tên file. Không thấy thì báo rõ đã tìm ở đâu."""
    k = kho()
    for s in SUB:
        p = os.path.join(k, s, ten)
        if os.path.exists(p):
            return p
    if not os.path.isdir(k):
        raise FileNotFoundError(
            f"Chưa có kho tài nguyên ở {k}.\n"
            f"Dựng kho: python3 scripts/dung_kho.py {NT.kho_mac_dinh()}\n"
            f"Hoặc sửa 'kho.duong_dan' trong cau-hinh.json cho trỏ đúng chỗ.")
    raise FileNotFoundError(f"Không thấy '{ten}' trong {k} (đã tìm: {', '.join(s or '.' for s in SUB[1:])})")


def font(vai_tro):
    """font('phu_de') -> đường dẫn font phụ đề trong cau-hinh.json"""
    ten = config.lay("chu", vai_tro)
    if not ten:
        raise KeyError(f"cau-hinh.json chưa khai font cho vai trò '{vai_tro}'")
    return find(ten)


def preset(loai):
    """preset('kieu-chu') -> danh sách mẫu trong presets/kieu-chu.json"""
    import json
    return json.load(open(find(f"{loai}.json"), encoding="utf-8"))


def kiem_tra():
    """Soát kho trước khi dựng. Trả về danh sách thiếu."""
    thieu = []
    k = kho()
    if not os.path.isdir(k):
        return [f"không có thư mục kho: {k}"]
    for vai in ("phu_de", "title_to", "bia"):
        try:
            font(vai)
        except (FileNotFoundError, KeyError) as e:
            thieu.append(f"font {vai}: {e}")
    for s in ("fonts", "sfx", "music", "grids", "overlays", "presets"):
        d = os.path.join(k, s)
        if not os.path.isdir(d) or not os.listdir(d):
            thieu.append(f"thư mục rỗng hoặc thiếu: {s}/")
    for f in ("kieu-chu.json", "chuyen-canh.json", "canh-tram.json",
              "do-am-luong.json"):
        if not os.path.exists(os.path.join(k, "presets", f)):
            thieu.append(f"thiếu presets/{f}")
    return thieu


def _ghi_bo_mua(duong):
    import json
    if not duong or not os.path.isdir(duong) or not any(os.scandir(duong)):        # 1.2.21: không ghi bo_mua rỗng/không tồn tại
        print(f"  ! không ghi kho.bo_mua: thư mục rỗng hoặc không tồn tại ({duong!r})"); return
    p = config.MAY
    d = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    d.setdefault("kho", {})["bo_mua"] = duong
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "tim-bo-mua":
        b = tim_bo_mua()
        if b:
            print(f"Đã thấy bộ tài nguyên quà tặng: {b}")
            if "--ghi" in sys.argv:
                _ghi_bo_mua(b); print("Đã ghi vào cau-hinh.json (kho.bo_mua). Chạy: ban_do_kho.py lap để cập nhật bản đồ kho.")
        else:
            print("Chưa thấy bộ quà tặng. Tải từ link trong thư giao hàng, giải nén vào thư mục Tải xuống (Downloads) rồi chạy lại.")
        sys.exit(0)
    print("Kho:", kho())
    t = kiem_tra()
    if t:
        print("\nTHIẾU:")
        for x in t:
            print("  -", x)
    else:
        print("kho đủ dùng")
        for s in SUB[1:]:
            d = os.path.join(kho(), s)
            if os.path.isdir(d):
                print(f"  {s:12} {len(os.listdir(d)):4} file")
