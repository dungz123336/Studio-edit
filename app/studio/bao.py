#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Claude báo lên Studio (chạy trong việc do Studio giao — biến môi trường STUDIO_VIEC có sẵn).

    python studio/bao.py video <file.mp4> [--bia <thumb.png>] [--ghi-chu "…"]   # thẻ video đã giao
    python studio/bao.py anh <a.png> [b.png …] [--ghi-chu "…"]                   # cho người dùng xem ảnh
    python studio/bao.py noi "…"                                                 # một câu ngắn giữa chừng

Không có STUDIO_VIEC (đang chạy ngoài Studio) thì im lặng bỏ qua — không làm hỏng việc dựng.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _lay(a, ten):
    if ten in a:
        i = a.index(ten)
        gt = a[i + 1] if i + 1 < len(a) else ""
        del a[i:i + 2]
        return gt
    return None


def main():
    a = sys.argv[1:]
    vid = os.environ.get("STUDIO_VIEC")
    if not a:
        print(__doc__)
        return
    if not vid:
        print("(không chạy trong Studio — bỏ qua)")
        return
    import du_lieu as D
    lenh = a.pop(0)
    ghi_chu = _lay(a, "--ghi-chu") or ""
    if lenh == "video" and a:
        bia = _lay(a, "--bia")
        p = os.path.abspath(a[0])
        if not os.path.isfile(p):
            sys.exit(f"không thấy {p}")
        D.them_tin(vid, "video", ghi_chu, tep=p, bia=os.path.abspath(bia) if bia else None,
                   thu_muc=os.path.dirname(p))
    elif lenh == "anh" and a:
        D.them_tin(vid, "anh", ghi_chu, anh=[os.path.abspath(x) for x in a if os.path.isfile(x)])
    elif lenh == "noi" and a:
        D.them_tin(vid, "claude", " ".join(a))
    else:
        sys.exit(__doc__)
    print("đã báo lên Studio")


if __name__ == "__main__":
    main()
