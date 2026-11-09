#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Mở Studio.

    python studio/mo.py            # bật server (nếu chưa) + mở cửa sổ app riêng
    python studio/mo.py --chi-bat  # chỉ bật server
    python studio/mo.py --tat      # tắt server
    python studio/mo.py --loi-tat  # tạo lối tắt "Studio dựng video" ngoài Desktop
"""
import json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONG = int(os.environ.get("STUDIO_PORT", "4777"))
URL = f"http://127.0.0.1:{CONG}"
DATA = os.path.expanduser(os.environ.get("STUDIO_DATA") or "~/.studio-edit-video")
WIN = os.name == "nt"


def dang_chay():
    try:
        with urllib.request.urlopen(URL + "/api/ping", timeout=0.8) as r:
            return json.load(r).get("app") == "studio-edit-video"
    except Exception:
        return False


def xoay_log(p, toi_da=2 * 1024 * 1024, giu=2):
    """1.2.21 (1h): server.log quá 2 MB → đổi tên .1 (.2), không để nhật ký phình vô hạn"""
    try:
        if os.path.isfile(p) and os.path.getsize(p) > toi_da:
            for i in range(giu, 0, -1):
                cu, moi = (p if i == 1 else f"{p}.{i - 1}"), f"{p}.{i}"
                if os.path.isfile(cu):
                    os.replace(cu, moi)
    except OSError:
        pass


def bat():
    if dang_chay():
        return
    os.makedirs(DATA, exist_ok=True)
    xoay_log(os.path.join(DATA, "server.log"))
    log = open(os.path.join(DATA, "server.log"), "ab")
    py = sys.executable
    if WIN and py.lower().endswith("pythonw.exe"):
        py = py[:-5] + ".exe" if os.path.isfile(py[:-5] + ".exe") else py
    lenh = [py, os.path.join(HERE, "server.py")]
    kw = dict(stdout=log, stderr=log, stdin=subprocess.DEVNULL, close_fds=True,
              env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"))
    if WIN:
        subprocess.Popen(lenh, creationflags=0x00000200 | 0x08000000, **kw)  # nhóm tiến trình mới + console ẩn (không hiện cửa sổ CMD)
    else:
        subprocess.Popen(lenh, start_new_session=True, **kw)
    for _ in range(80):
        time.sleep(0.1)
        if dang_chay():
            return
    sys.exit(f"Studio không bật được — xem {os.path.join(DATA, 'server.log')}")


def tat():
    """1.2.21: /api/tat của server tắt sạch (cây tiến trình việc, kho, daemon lời, trình duyệt lớp web) rồi mới dừng — chờ tới 20 s"""
    try:
        urllib.request.urlopen(urllib.request.Request(URL + "/api/tat", data=b"{}", method="POST",
                                                      headers={"Content-Type": "application/json"}), timeout=5)
    except Exception:
        return
    for _ in range(40):
        time.sleep(0.5)
        if not dang_chay():
            return


def cua_so():
    """Cửa sổ app riêng (Edge/Chrome --app), không có thì trình duyệt mặc định."""
    ung = []
    if WIN:
        for g in (os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", ""),
                  os.environ.get("LOCALAPPDATA", "")):
            ung += [os.path.join(g, "Microsoft", "Edge", "Application", "msedge.exe"),
                    os.path.join(g, "Google", "Chrome", "Application", "chrome.exe")]
    elif sys.platform == "darwin":
        ung += ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    for exe in ung:
        if exe and os.path.isfile(exe):
            p = subprocess.Popen([exe, f"--app={URL}", "--window-size=1480,920", "--no-first-run",
                                  "--disk-cache-size=52428800",                     # 1.2.21 (1h): cache trình duyệt ≤ 50 MB (máy anh đo 0,7 GB)
                                  f"--user-data-dir={os.path.join(DATA, 'cua-so')}"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:                                                                    # 1.2.21: tiến trình con có chủ — ghi PID
                with open(os.path.join(DATA, "cua-so.pid"), "w", encoding="utf-8") as f:
                    f.write(str(p.pid))
            except OSError:
                pass
            return
    import webbrowser
    webbrowser.open(URL)


def loi_tat():
    script = os.path.abspath(__file__)
    if WIN:
        # 1.2.12: lối tắt chạy BỘ MỞ TỰ CHỮA (wscript + mo_studio.vbs) — không trỏ thẳng pythonw của .venv: uv nâng/gỡ bản
        # Python 3.12.x là .venv mất gốc → "Python Launcher is sorry to say… No Python at …". Bộ mở tự trỏ lại rồi mở Studio.
        vbs = os.path.join(HERE, "mo_studio.vbs")
        wscript = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "wscript.exe")
        if os.path.isfile(vbs) and os.path.isfile(wscript):
            py, script = wscript, vbs
        else:
            py = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            py = py if os.path.isfile(py) else sys.executable
        ico = os.path.join(HERE, "web", "studio.ico")
        ps = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8;$d=[Environment]::GetFolderPath('Desktop');"
              "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'Studio-dung-video.lnk'));"
              "$s.TargetPath=$env:PY;$s.Arguments=$env:ARGS;$s.WorkingDirectory=$env:WD;"
              "$s.Description='Studio dung video';$s.IconLocation=$env:ICO;$s.Save();$d")
        env = dict(os.environ, PY=py, ARGS=f'"{script}"', WD=HERE, ICO=ico + ",0")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, check=True, capture_output=True)
        desk = r.stdout.decode("utf-8", "replace").strip().splitlines()[-1]
        dich = os.path.join(desk, "Studio dựng video.lnk")
        os.replace(os.path.join(desk, "Studio-dung-video.lnk"), dich)
        return dich
    p = os.path.join(os.path.expanduser("~/Desktop"), "Studio dựng video.command")
    with open(p, "w", encoding="utf-8") as f:
        f.write(f'#!/bin/bash\n"{sys.executable}" "{script}"\n')
    os.chmod(p, 0o755)
    return p


def doi_loi_tat_cu(thu_muc=None):
    """1.2.12: lối tắt kiểu cũ (trỏ thẳng pythonw + studio\\mo.py) ở Desktop / Start Menu / ghim Taskbar → SỬA TẠI CHỖ sang bộ mở
    tự chữa (giữ tên, giữ ghim). Chỉ làm khi .venv của skill có thật — máy khách đã tự sửa bằng Python hệ thống (không .venv)
    thì để nguyên lối tắt đang chạy được. Một lần (dấu ~/.studio-edit-video/.loi-tat-tu-chua). → số lối tắt đã đổi"""
    if not WIN:
        return 0
    dau = os.path.join(DATA, ".loi-tat-tu-chua")
    mac_dinh = thu_muc is None
    if mac_dinh and os.path.exists(dau):
        return 0
    skill = os.path.dirname(HERE)
    pyw = os.path.join(skill, ".venv", "Scripts", "pythonw.exe")
    vbs = os.path.join(HERE, "mo_studio.vbs")
    wscript = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "wscript.exe")
    if not (os.path.isfile(pyw) and os.path.isfile(vbs) and os.path.isfile(wscript)):
        return 0
    if thu_muc is None:
        ad = os.environ.get("APPDATA", "")
        thu_muc = [os.path.join(os.path.expanduser("~"), "Desktop"),
                   os.path.join(ad, "Microsoft", "Windows", "Start Menu", "Programs"),
                   os.path.join(ad, "Microsoft", "Internet Explorer", "Quick Launch", "User Pinned", "TaskBar")]
    ps = ("$n=0; $sh=New-Object -ComObject WScript.Shell; $ds=@($env:DS -split '\\|'); "
          "if($env:THEM_DESK -eq '1'){ try{ $ds += [Environment]::GetFolderPath('Desktop') }catch{} }; "
          "foreach($d in ($ds | Select-Object -Unique)){ if(-not (Test-Path -LiteralPath $d)){continue}; "
          "Get-ChildItem -LiteralPath $d -Filter '*.lnk' -Recurse -Depth 3 -ErrorAction SilentlyContinue | ForEach-Object { "
          "$s=$sh.CreateShortcut($_.FullName); "
          "if(($s.Arguments -like ('*'+$env:SK+'*mo.py*')) -or ($s.TargetPath -like ($env:SK+'*pythonw.exe'))){ "
          "$s.TargetPath=$env:WS; $s.Arguments=('\"'+$env:VBS+'\"'); $s.WorkingDirectory=$env:WD; $s.IconLocation=$env:ICO; "
          "$s.Save(); $n++ } } }; $n")
    env = dict(os.environ, DS="|".join(thu_muc), SK=skill, WS=wscript, VBS=vbs, WD=HERE,
               ICO=os.path.join(HERE, "web", "studio.ico") + ",0", THEM_DESK="1" if mac_dinh else "0")
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], env=env, capture_output=True, timeout=60,
                           creationflags=0x08000000)
        n = int((r.stdout.decode("utf-8", "replace").strip().splitlines() or ["0"])[-1])
    except Exception:
        return 0
    if mac_dinh:
        os.makedirs(DATA, exist_ok=True)
        open(dau, "w").write(f"ok {n}")
    return n


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--tat" in a:
        tat(); print("đã tắt Studio")
    elif "--loi-tat" in a:
        print("Đã tạo lối tắt:", loi_tat())
    else:
        bat()
        if "--chi-bat" not in a:
            cua_so()
        print(f"Studio: {URL}")
