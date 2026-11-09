#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Bộ cài 1 lệnh — Mac và Windows. Chạy bằng python bất kỳ (≥ 3.9) trên máy:

    Mac:      python3 ~/.claude/skills/tro-ly-edit-video/scripts/cai_dat.py
    Windows:  py %USERPROFILE%\\.claude\\skills\\tro-ly-edit-video\\scripts\\cai_dat.py

Làm: kiểm ffmpeg → tạo .venv Python 3.12 (qua uv) → cài gói đúng hệ điều hành → tải trước model nhận giọng →
ghi đường dẫn kho vào cau-hinh.json nếu chưa có → in báo cáo `nen_tang.py`. Chạy lại nhiều lần cũng an toàn.
"""
import json, os, platform, shutil, subprocess, sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIN = platform.system() == "Windows"
MAC_ARM = platform.system() == "Darwin" and platform.machine() == "arm64"
VENV = os.path.join(SKILL, ".venv")
PY = os.path.join(VENV, "Scripts", "python.exe") if WIN else os.path.join(VENV, "bin", "python")


def buoc(t):
    print(f"\n▶ {t}")


def chay(c, **kw):
    print("  $ " + " ".join(c))
    return subprocess.run(c, **kw)


def main():
    sys.stdout.reconfigure(line_buffering=True)   # in xen kẽ đúng thứ tự với lệnh con
    buoc("Kiểm ffmpeg")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("  THIẾU ffmpeg. Cài rồi chạy lại:")
        print("    Windows: winget install Gyan.FFmpeg   (mở lại cửa sổ dòng lệnh sau khi cài)" if WIN
              else "    Mac:     brew install ffmpeg")
        return 1
    print("  có")

    buoc("Kiểm uv (trình cài Python)")
    uv = shutil.which("uv")
    if not uv:
        print("  THIẾU uv. Cài rồi chạy lại:")
        print("    Windows: winget install astral-sh.uv" if WIN else "    Mac:     brew install uv")
        return 1
    print("  có")

    buoc("Tạo môi trường Python 3.12 riêng cho skill")
    if not os.path.exists(PY):
        if chay([uv, "venv", "--python", "3.12", VENV]).returncode:
            return 1
    else:
        print("  đã có")
    try:                                    # 1.2.12: chốt gốc .venv sang thư mục 3.12 cố định của uv (không gãy khi uv nâng bản vá)
        sys.path.insert(0, os.path.join(SKILL, "studio"))
        import sua_venv
        print("  " + sua_venv.chua()[1])
    except Exception as e:
        print("  (chưa chốt được gốc Python:", e, ")")

    buoc("Cài gói Python cho " + ("Mac Apple Silicon" if MAC_ARM else "Windows" if WIN else platform.system()))
    yc = os.path.join(SKILL, "yeu-cau-mac.txt" if MAC_ARM else "yeu-cau-win.txt" if WIN else "yeu-cau-linux.txt")   # 1.2.19 (E4)
    if not os.path.isfile(yc):
        yc = os.path.join(SKILL, "yeu-cau-win.txt")
    if chay([uv, "pip", "install", "--python", PY, "-r", yc]).returncode:
        return 1

    buoc("Tải trước model nhận giọng (~1,5 GB, một lần)")
    tai = "from faster_whisper import WhisperModel; WhisperModel('mobiuslabsgmbh/faster-whisper-large-v3-turbo', device='cpu', compute_type='int8')"
    chay([PY, "-c", tai])                     # 1.2.19 (E1): lõi 1.3 dùng faster-whisper trên MỌI hệ (Mac M1+ trước đây chỉ tải mlx → không dựng được)
    if MAC_ARM:
        chay([PY, "-c", "import mlx_whisper, huggingface_hub as h; h.snapshot_download('mlx-community/whisper-large-v3-turbo')"])

    buoc("Cấu hình máy (cau-hinh.json)")
    p = os.path.join(SKILL, "cau-hinh.json")
    mau = os.path.join(SKILL, "cau-hinh.mau.json")
    if not os.path.exists(p) and os.path.exists(mau):     # lần cài đầu: tạo từ mẫu; cập nhật về sau không đụng file này
        shutil.copy(mau, p)
    cfg = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    kho = cfg.setdefault("kho", {})
    mac_dinh = os.path.expanduser("~/Videos/VideoKit-Free" if WIN else "~/Movies/VideoKit-Free")
    kem = os.path.join(SKILL, "tai-nguyen")
    if not kho.get("duong_dan") or not os.path.isdir(os.path.expanduser(kho["duong_dan"])):
        # 1.2.14: cấu hình ĐÃ ghi đường kho (chưa tạo) → tạo ĐÚNG chỗ đó; không lặng lẽ đổi sang thư mục mặc định
        # (bản 1.2.13 chuyển tài nguyên vào ~/Videos/VideoKit-Free của bản cài khác trên cùng máy và XOÁ kho đi kèm).
        dich = os.path.expanduser(kho["duong_dan"]) if kho.get("duong_dan") else mac_dinh
        if os.path.isdir(kem) and not os.path.isdir(os.path.join(dich, "fonts")):
            if os.path.isdir(dich) and os.listdir(dich):
                print(f"  ! {dich} đã có dữ liệu khác — không ghi vào; dùng kho đi kèm gói tại chỗ")
                dich = kem
            else:
                os.makedirs(os.path.dirname(dich), exist_ok=True)
                shutil.copytree(kem, dich, dirs_exist_ok=True)   # CHÉP (không chuyển, không xoá kho đi kèm)
                print(f"  đã chép kho tài nguyên đi kèm ra {dich}")
        kho["duong_dan"] = dich
        json.dump(cfg, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"  kho: {kho['duong_dan']}")
    if not os.path.isdir(os.path.join(os.path.expanduser(kho["duong_dan"]), "fonts")):
        buoc("Dựng kho tài nguyên sạch bản quyền (~8 phút, ~240 MB, chỉ làm 1 lần)")
        print("  Font miễn phí OFL tải từ Google Fonts; tiếng động, nhạc, nền lưới, LUT tự tổng hợp — không lấy của ai.")
        if chay([PY, os.path.join(SKILL, "scripts", "dung_kho.py"), os.path.expanduser(kho["duong_dan"])]).returncode:
            print("  Dựng kho lỗi (thường do mất mạng khi tải font) — chạy lại cai_dat.py là được.")
            return 1

    buoc("Tìm bộ tài nguyên quà tặng ~10 GB (nhạc, SFX, 405 font Việt hoá, LUT, nền động)")
    r = subprocess.run([PY, os.path.join(SKILL, "scripts", "kit.py"), "tim-bo-mua", "--ghi"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("  " + (r.stdout.strip().splitlines() or ["(không có kết quả)"])[0])
    if "Chưa thấy" in r.stdout:
        print("  → Không bắt buộc. Tải về sau rồi nói với Claude: \"tìm bộ tài nguyên quà tặng\".")

    buoc("Font tĩnh cho phụ đề và bộ phong cách")
    chay([PY, os.path.join(SKILL, "scripts", "tao_font_tinh.py")])
    buoc("Bản đồ kho (để tra nhạc/tiếng động theo mood)")
    chay([PY, os.path.join(SKILL, "scripts", "ban_do_kho.py"), "lap"], stdout=subprocess.DEVNULL)

    buoc("Báo cáo máy")
    chay([PY, os.path.join(SKILL, "scripts", "nen_tang.py")])
    buoc("Bản quyền")
    r = subprocess.run([PY, os.path.join(SKILL, "scripts", "ban_quyen.py"), "kiem"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("  " + r.stdout.strip())
    if "CHƯA" in r.stdout:
        print("  → Kích hoạt bằng mã nhận khi mua:  <python của skill> scripts/ban_quyen.py kich-hoat <MÃ>")
    print("\nXong. Mở Claude Code, kéo file quay vào và gõ: \"dựng video này\".")
    return 0


if __name__ == "__main__":
    sys.exit(main())
