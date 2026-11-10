#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""TỰ CHỮA môi trường Python của skill (.venv) khi "gốc" Python biến mất (1.2.12).

Lỗi khách hay gặp: bấm app ngoài Desktop → "Python Launcher is sorry to say… No Python at
…\\uv\\python\\cpython-3.12.15-windows-x86_64-none\\pythonw.exe". Nguyên nhân: .venv do uv tạo ghi cứng ĐƯỜNG DẪN BẢN VÁ
(3.12.15) vào pyvenv.cfg; khi uv nâng/gỡ bản đó, .venv mất gốc dù toàn bộ thư viện vẫn còn.
Cách chữa: trỏ pyvenv.cfg sang một Python 3.12 khác còn trên máy (ưu tiên thư mục "3.12" cố định của uv — không đổi khi
nâng bản vá); thiếu hẳn thì `uv python install 3.12`. Cùng 3.12 nên thư viện đã cài dùng lại được, không phải cài lại.

    python studio/sua_venv.py          # kiểm + chữa, in kết quả
    python studio/sua_venv.py --kiem   # chỉ kiểm
Studio ngoài Desktop dùng bộ mở studio/mo_studio.vbs (cùng logic, không cần Python) nên tự chữa trước khi mở.
"""
import os, re, glob, shutil, subprocess, sys
from moi_truong import python_da_chon

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELECTED_PYTHON = python_da_chon()
VENV = os.path.dirname(os.path.dirname(SELECTED_PYTHON)) if SELECTED_PYTHON else os.path.join(SKILL, ".venv")
CFG = os.path.join(VENV, "pyvenv.cfg")
WIN = os.name == "nt"
EXE = "python.exe" if WIN else os.path.join("bin", "python3")
MINOR = "3.12"


def doc_cfg():
    try:
        with open(CFG, encoding="utf-8") as stream:
            return stream.read()
    except OSError:
        return ""


def goc():
    m = re.search(r"(?m)^\s*home\s*=\s*(.+?)\s*$", doc_cfg())
    return m.group(1) if m else None


def goc_ok():
    g = goc()
    return bool(g) and os.path.isfile(os.path.join(g, "python.exe" if WIN else "python3"))


def _thu_muc_uv():
    ds = [os.environ.get("UV_PYTHON_INSTALL_DIR", "")]
    if WIN:
        ds.append(os.path.join(os.environ.get("APPDATA", ""), "uv", "python"))
    else:
        ds.append(os.path.expanduser("~/.local/share/uv/python"))
    return [d for d in ds if d and os.path.isdir(d)]


def _vi(ten):
    m = re.search(r"cpython-3\.12\.(\d+)", ten)
    return int(m.group(1)) if m else -1


def ung_vien():
    """các thư mục Python 3.12 còn chạy được — thư mục 'cpython-3.12-…' cố định của uv đứng đầu"""
    out = []
    for d in _thu_muc_uv():
        co_dinh = [p for p in glob.glob(os.path.join(d, "cpython-3.12-*")) if os.path.isfile(os.path.join(p, EXE))]
        va = sorted((p for p in glob.glob(os.path.join(d, "cpython-3.12.*")) if os.path.isfile(os.path.join(p, EXE))),
                    key=lambda p: _vi(os.path.basename(p)), reverse=True)
        out += [p for p in co_dinh if "freethreaded" not in p] + [p for p in va if "freethreaded" not in p]
    if WIN:
        he = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python312")
        if os.path.isfile(os.path.join(he, "python.exe")):
            out.append(he)
    return out


def _phien_ban(thu_muc):
    try:
        r = subprocess.run([os.path.join(thu_muc, EXE), "-c", "import sys;print('%d.%d.%d'%sys.version_info[:3])"],
                           capture_output=True, text=True, timeout=30, creationflags=0x08000000 if WIN else 0)
        return r.stdout.strip() or None
    except Exception:
        return None


def ghi_goc(thu_muc):
    s = doc_cfg()
    s = re.sub(r"(?m)^(\s*home\s*=\s*).*$", lambda m: m.group(1) + thu_muc, s)
    v = _phien_ban(thu_muc)
    if v:
        s = re.sub(r"(?m)^(\s*version_info\s*=\s*).*$", lambda m: m.group(1) + v, s)
    open(CFG, "w", encoding="utf-8", newline="\n").write(s)
    return v


def _uv():
    ds = [shutil.which("uv")]
    if WIN:
        la = os.environ.get("LOCALAPPDATA", "")
        ds += [os.path.join(la, "Microsoft", "WinGet", "Links", "uv.exe"), os.path.expanduser(r"~\.local\bin\uv.exe")]
        ds += glob.glob(os.path.join(la, "Microsoft", "WinGet", "Packages", "astral-sh.uv*", "uv.exe"))
    return next((d for d in ds if d and os.path.isfile(d)), None)


def chua(cai_neu_thieu=True):
    """→ (ok, mô tả). Gốc còn → chỉ 'chốt' sang thư mục 3.12 cố định nếu có; mất → trỏ sang ứng viên / cài 3.12 bằng uv."""
    if SELECTED_PYTHON:
        ok = goc_ok()
        return ok, ("gốc Python đã chọn còn: " if ok else "gốc Python đã chọn bị thiếu: ") + str(goc())
    if not os.path.isfile(CFG):
        return False, "chưa có môi trường Python của skill (.venv) — chạy bộ cài"
    if goc_ok():
        g = goc()
        cd = [p for p in ung_vien() if os.path.basename(p).startswith("cpython-3.12-")]
        if cd and re.search(r"cpython-3\.12\.\d+", os.path.basename(g)) and os.path.normcase(cd[0]) != os.path.normcase(g):
            ghi_goc(cd[0])
            return True, f"đã chốt gốc sang {os.path.basename(cd[0])} (không gãy khi uv nâng bản vá)"
        return True, f"gốc Python còn: {g}"
    cu = goc()
    uv_ = ung_vien()
    if not uv_ and cai_neu_thieu:
        uv = _uv()
        if uv:
            subprocess.run([uv, "python", "install", MINOR], capture_output=True, timeout=900,
                           creationflags=0x08000000 if WIN else 0)
            uv_ = ung_vien()
    if not uv_:
        return False, f"gốc Python mất ({cu}) và không tìm/cài được Python {MINOR}"
    v = ghi_goc(uv_[0])
    try:
        os.makedirs(os.path.expanduser("~/.studio-edit-video"), exist_ok=True)
        with open(os.path.expanduser("~/.studio-edit-video/sua-loi.md"), "a", encoding="utf-8") as f:
            import time
            f.write(f"- {time.strftime('%Y-%m-%d %H:%M')} · TỰ CHỮA .venv: gốc {cu} mất → {uv_[0]} ({v})\n")
    except Exception:
        pass
    return True, f"gốc cũ mất ({os.path.basename(cu or '?')}) → đã trỏ sang {os.path.basename(uv_[0])} ({v})"


if __name__ == "__main__":
    if "--kiem" in sys.argv:
        print("ok" if goc_ok() else "HỎNG", goc())
    else:
        ok, mt = chua()
        print(("✓ " if ok else "✗ ") + mt)
        sys.exit(0 if ok else 1)
