#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Thông số theo sức máy. Máy yếu vẫn chạy được, chỉ chậm hơn hoặc nhẹ hơn."""
import os, subprocess as sp
import config
import nen_tang as NT

BANG = {
    # chế độ:   (model nhận dạng,          preset x264, crf, lọc nặng, tỉ lệ dựng)
    "nhanh": ("mlx-community/whisper-small-mlx",           "veryfast", 24, False, 1),
    "chuan": ("mlx-community/whisper-large-v3-turbo",      "medium",   20, True,  1),
    "ky":    ("mlx-community/whisper-large-v3-turbo",      "slow",     18, True,  2),
}


def _suc_may_win():
    import ctypes, platform

    class M(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = M(); m.dwLength = ctypes.sizeof(M)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    ram = m.ullTotalPhys // (1024 ** 3)
    gpu = NT._bo_ma_hoa() == "h264_nvenc"          # có NVIDIA → whisper chạy GPU, dựng nhanh
    goi_y = "nhanh" if ram <= 8 else ("ky" if ram >= 32 and gpu else "chuan" if gpu or ram >= 16 else "nhanh")
    return {"chip": platform.processor() or "?", "ram": ram, "loi": os.cpu_count() or 0,
            "apple": False, "goi_y": goi_y}


def suc_may():
    """Đọc chip và RAM để gợi ý chế độ."""
    if NT.HE == "win":
        try:
            return _suc_may_win()
        except Exception:
            return {"chip": "?", "ram": 0, "loi": os.cpu_count() or 0, "apple": False, "goi_y": "nhanh"}
    try:
        chip = sp.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                      capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
        ram = int(sp.run(["sysctl", "-n", "hw.memsize"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()) // (1024 ** 3)
        loi = int(sp.run(["sysctl", "-n", "hw.ncpu"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip())
    except Exception:
        return {"chip": "?", "ram": 0, "loi": 0, "goi_y": "nhanh"}
    apple = "Apple" in chip
    if not apple or ram <= 8:
        goi_y = "nhanh"
    elif ram >= 32:
        goi_y = "ky"
    else:
        goi_y = "chuan"
    return {"chip": chip, "ram": ram, "loi": loi, "apple": apple, "goi_y": goi_y}


def hien_tai():
    cd = config.lay("may", "che_do", mac_dinh="chuan")
    if cd not in BANG:
        cd = "chuan"
    m, preset, crf, nang, _ = BANG[cd]
    return {"che_do": cd, "model": m, "preset": preset, "crf": crf, "loc_nang": nang}


def tham_so_xuat():
    """Cờ ffmpeg cho lần xuất cuối."""
    t = hien_tai()
    return ["-c:v", "libx264", "-preset", t["preset"], "-crf", str(t["crf"]),
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart"]


if __name__ == "__main__":
    m = suc_may()
    t = hien_tai()
    print(f"Máy      : {m['chip']}  ·  {m['ram']} GB RAM  ·  {m['loi']} lõi")
    print(f"Gợi ý    : {m['goi_y']}")
    print(f"Đang đặt : {t['che_do']}")
    print(f"  nhận dạng : {t['model'].split('/')[-1]} ({NT.bo_nhan_dang()})")
    print(f"  xuất      : preset {t['preset']}, crf {t['crf']}")
    print(f"  lọc nặng  : {'có' if t['loc_nang'] else 'không'}")
    if m["goi_y"] != t["che_do"]:
        print(f"\n→ Nên đổi may.che_do thành \"{m['goi_y']}\" trong cau-hinh.json")
