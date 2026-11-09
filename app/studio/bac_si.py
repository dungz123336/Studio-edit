#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""BÁC SĨ MÁY — kiểm mọi thứ skill cần, tự cài / tự sửa được gì thì sửa luôn. Người dùng không cần biết code.

    python studio/bac_si.py            # kiểm, in bảng
    python studio/bac_si.py --sua      # kiểm rồi tự sửa mọi mục sửa được (cài ffmpeg, uv, thư viện, kho…)
    python studio/bac_si.py --json     # kết quả dạng JSON (Studio đọc)

Không bao giờ: nhập mật khẩu / mã bản quyền hộ, đụng file bản quyền, tắt bảo mật hệ điều hành.
Việc cần người dùng tự làm (đăng nhập Claude, nhập mã) thì in hướng dẫn một dòng.
"""
import glob, json, os, platform, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
WIN = platform.system() == "Windows"
MAC = platform.system() == "Darwin"
MAC_ARM = MAC and platform.machine() == "arm64"
LINUX = platform.system() == "Linux"
WIN_ARM = WIN and platform.machine().upper() in ("ARM64", "AARCH64")          # 1.2.19 (E5)


def tep_yeu_cau():
    """1.2.19 (E1/E4): yêu cầu theo hệ — Windows: win · Mac Apple Silicon: mac · Mac Intel / Linux: linux (không có DirectML)"""
    if MAC_ARM:
        return os.path.join(SKILL, "yeu-cau-mac.txt")
    if WIN:
        return os.path.join(SKILL, "yeu-cau-win.txt")
    p = os.path.join(SKILL, "yeu-cau-linux.txt")
    return p if os.path.isfile(p) else os.path.join(SKILL, "yeu-cau-win.txt")
VENV_PY = os.path.join(SKILL, ".venv", "Scripts", "python.exe") if WIN else os.path.join(SKILL, ".venv", "bin", "python")
KHONG_CUA_SO = 0x08000000 if WIN else 0
GOI = ["faster_whisper", "av"] + (["mediapipe"] if WIN else []) + \
      ["numpy", "PIL", "scipy", "fontTools", "requests", "cryptography", "skia", "onnxruntime"]      # 1.2.19: lõi 1.3 cần faster-whisper trên MỌI hệ


def them_path():
    """winget / brew cài xong thì PATH của tiến trình đang chạy chưa có — tự thêm các chỗ quen thuộc."""
    ds = []
    if WIN:
        la = os.environ.get("LOCALAPPDATA", "")
        ds += [os.path.join(la, "Microsoft", "WinGet", "Links"), os.path.expanduser(r"~\.local\bin")]
        ds += glob.glob(os.path.join(la, "Microsoft", "WinGet", "Packages", "astral-sh.uv*"))
        ds += glob.glob(os.path.join(la, "Microsoft", "WinGet", "Packages", "Gyan.FFmpeg*", "*", "bin"))
        ds += [os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Git", "cmd"),
               os.path.join(os.environ.get("APPDATA", ""), "npm")]
    else:
        ds += ["/opt/homebrew/bin", "/usr/local/bin", os.path.expanduser("~/.local/bin")]
    cu = os.environ.get("PATH", "")
    moi = [d for d in ds if os.path.isdir(d) and d not in cu]
    if moi:
        os.environ["PATH"] = os.pathsep.join(moi + [cu])


def chay(lenh, toi_da=900, **kw):
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    try:
        r = subprocess.run(lenh, capture_output=True, timeout=toi_da, env=env, creationflags=KHONG_CUA_SO, **kw)
        return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace")
    except FileNotFoundError as e:
        return 127, str(e)
    except subprocess.TimeoutExpired:
        return 124, "quá thời gian"


def py_skill(*args, toi_da=900):
    return chay([VENV_PY, *args], toi_da=toi_da, cwd=SKILL)


def ghi(chu):
    print(chu, flush=True)


# ------------------------------------------------------------------ từng mục kiểm
def k_utf8():
    if not WIN:
        return True, "không cần trên máy này"
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment")
        v = winreg.QueryValueEx(k, "PYTHONUTF8")[0]
        return str(v) == "1", "đã bật" if str(v) == "1" else f"đang là {v}"
    except OSError:
        return False, "chưa bật — script đọc chữ có dấu từ lệnh con sẽ lỗi bảng mã cp1252"


def s_utf8():
    return chay(["setx", "PYTHONUTF8", "1"])


def k_ffmpeg():
    a, b = shutil.which("ffmpeg"), shutil.which("ffprobe")
    return bool(a and b), a or "chưa có ffmpeg"


def _linux_goi(goi):
    """1.2.21: Linux không có brew — không tự cài, in lệnh theo bản phân phối để khách chạy"""
    return 1, (f"Linux: cài {goi} bằng trình quản lý gói của hệ, ví dụ  sudo apt install {goi}   (Debian/Ubuntu)  ·  "
               f"sudo dnf install {goi}   (Fedora)  ·  sudo pacman -S {goi}   (Arch) — rồi bấm 'Tự sửa tất cả' lại")


def s_ffmpeg():
    if WIN:
        return chay(["winget", "install", "--id", "Gyan.FFmpeg", "-e", "--silent",
                     "--accept-source-agreements", "--accept-package-agreements"])
    if MAC:
        return chay(["brew", "install", "ffmpeg"])
    return _linux_goi("ffmpeg")


def k_uv():
    return bool(shutil.which("uv")), shutil.which("uv") or "chưa có uv (trình cài Python)"


def s_uv():
    if WIN:
        return chay(["winget", "install", "--id", "astral-sh.uv", "-e", "--silent",
                     "--accept-source-agreements", "--accept-package-agreements"])
    if MAC:
        return chay(["brew", "install", "uv"])
    r = chay(["sh", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"], toi_da=600)     # Linux: bộ cài chính thức của uv
    return r if r[0] == 0 else _linux_goi("uv")


def k_venv():
    if not os.path.isfile(VENV_PY):
        return False, "chưa tạo môi trường Python của skill"
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import sua_venv                                  # 1.2.12: .venv còn file nhưng mất "gốc" Python (uv nâng/gỡ 3.12.x)
    if not sua_venv.goc_ok():
        return False, f"môi trường Python mất gốc ({sua_venv.goc()}) — app ngoài Desktop báo 'No Python at…'"
    return True, VENV_PY


def s_venv():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import sua_venv
    if os.path.isfile(VENV_PY) and os.path.isfile(sua_venv.CFG):
        ok, mt = sua_venv.chua()
        print("  " + mt)
        if ok:
            return 0
    return s_cai_dat()


def s_cai_dat():
    """bộ cài chính thức của skill: venv, gói, model, kho, font tĩnh, bản đồ kho"""
    return chay([sys.executable, os.path.join(SCRIPTS, "cai_dat.py")], toi_da=3600, cwd=SKILL)


def k_goi():
    if not os.path.isfile(VENV_PY):
        return False, "chưa có môi trường Python"
    ma = ";".join(f"__import__('{g}')" for g in GOI)
    rc, out = py_skill("-c", ma + ";print('ok')", toi_da=120)
    if rc:
        return False, "thiếu thư viện: " + out.strip().splitlines()[-1][:160]
    if True:
        rc, v = py_skill("-c", "import av;print(av.__version__)", toi_da=60)
        try:
            if int(v.strip().split(".")[0]) >= 15:
                return False, f"av {v.strip()} không hợp với faster-whisper 1.2.1 (cần 14.2.0)"
        except ValueError:
            pass
    return True, "đủ " + ", ".join(GOI)


def s_goi():
    uv = shutil.which("uv")
    yc = tep_yeu_cau()
    if not uv:
        return 1, "chưa có uv"
    rc, out = chay([uv, "pip", "install", "--python", VENV_PY, "-r", yc], toi_da=1800)
    if rc == 0 and WIN:
        # 1.3: faster-whisper/rapidocr kéo bản onnxruntime CPU → cài lại bản DirectML (cùng mô-đun, thêm chạy trên card) cho tách người
        rc2, out2 = chay([uv, "pip", "install", "--python", VENV_PY, "--reinstall", "--no-deps", "onnxruntime-directml"], toi_da=900)
        out += out2
    return rc, out


def k_nhan_giong():
    """thử giải mã 1 giây âm thanh đúng như máy dựng làm — bắt lỗi kiểu av/faster-whisper"""
    if not os.path.isfile(VENV_PY) or not shutil.which("ffmpeg"):
        return False, "chưa đủ điều kiện để thử"
    wav = os.path.join(tempfile.gettempdir(), "bac-si-thu.wav")
    chay(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-ar", "16000", "-ac", "1", wav])
    if MAC_ARM:
        rc, out = py_skill("-c", "import mlx_whisper;print('ok')", toi_da=120)
    else:
        rc, out = py_skill("-c", f"from faster_whisper.audio import decode_audio;a=decode_audio(r'{wav}');print(len(a))", toi_da=120)
    return rc == 0, "giải mã âm thanh được" if rc == 0 else out.strip().splitlines()[-1][:200]


def k_kho():
    if not os.path.isfile(VENV_PY):
        return False, "chưa có môi trường Python"
    rc, out = py_skill(os.path.join(SCRIPTS, "kit.py"), toi_da=60)
    if "kho đủ dùng" in out:
        return True, (out.strip().splitlines() or ["?"])[0][:160]
    # 1.2.12: khách tự xoá kho sạch để lấy chỗ trống → Studio vẫn chạy đủ: font dự phòng đi kèm skill (v2/font-them)
    # + danh mục kho 2.0 (tài nguyên còn file thật, tra theo nghĩa). Chỉ báo lỗi khi cả hai cùng thiếu.
    ft = os.path.join(SKILL, "v2", "font-them")
    co_font = os.path.isdir(ft) and sum(f.lower().endswith((".ttf", ".otf")) for f in os.listdir(ft)) >= 3
    ok_dm, dm = k_kho_v3()
    if co_font and ok_dm:
        return True, f"kho sạch đã gỡ — dùng font đi kèm skill + chỉ mục kho ({dm})"
    return False, "kho thiếu: " + " ".join(out.split("THIẾU:")[-1].split())[:200]


def k_kho_v3():
    """1.3: chỉ mục kho của lõi mới (v3/kho) — tài nguyên có nghĩa tiếng Việt để gói kho cho từng video"""
    if not os.path.isfile(VENV_PY):
        return False, "chưa có môi trường Python"
    # 1.2.21 (1g): chỉ mục kho là SQLite kho-chi-muc/kho.sqlite (danh-muc.jsonl/ai-nghia.json nhập một lần, giữ nguyên tệp cũ);
    # chưa có SQLite thì đếm tệp cũ như trước (0 = chưa lập)
    ma = ("import sys,os,json;sys.path.insert(0,'v3');import chung;d=chung.duong('kho_chi_muc')\n"
          "if os.path.isfile(os.path.join(d,'kho.sqlite')):\n"
          "    from kho import csdl;t=csdl.thong_ke(d);print(t['muc'],t['ai_nghia'])\n"
          "else:\n"
          "    p=os.path.join(d,'danh-muc.jsonl');n=sum(1 for _ in open(p,encoding='utf-8')) if os.path.isfile(p) else 0\n"
          "    a=json.load(open(os.path.join(d,'ai-nghia.json'),encoding='utf-8')) if os.path.isfile(os.path.join(d,'ai-nghia.json')) else {}\n"
          "    print(n,len(a))")
    rc, out = py_skill("-c", ma, toi_da=120)
    try:
        n, co_nghia = [int(x) for x in out.strip().splitlines()[-1].split()]
    except Exception:
        return False, "không đọc được chỉ mục kho: " + (out.strip().splitlines() or ["?"])[-1][:160]
    if n == 0:
        return False, "chưa lập chỉ mục kho"
    return True, f"{n} tài nguyên, {co_nghia} đã gắn nghĩa" + ("" if co_nghia else " (tìm theo tên tệp — gắn nghĩa tuỳ chọn)")


def s_kho_v3():
    return py_skill(os.path.join(SKILL, "v3", "kho", "lap.py"), toi_da=3600)


def k_bo_qua():
    if not os.path.isfile(VENV_PY):
        return False, "chưa có môi trường Python"
    rc, out = py_skill("-c", "import sys;sys.path.insert(0,'scripts');import kit;print(kit.bo_mua() or '-')", toi_da=60)
    d = out.strip().splitlines()[-1] if out.strip() else "-"
    if d != "-":
        return True, d
    rc, out = py_skill(os.path.join(SCRIPTS, "kit.py"), "tim-bo-mua", toi_da=300)
    if "Đã thấy" in out:
        return False, "đã tải về nhưng chưa nối vào skill"
    return None, "chưa có bộ quà tặng ~10 GB (tuỳ chọn) — tải từ link trong thư giao hàng, giải nén vào Tải xuống"


def s_bo_qua():
    rc, out = py_skill(os.path.join(SCRIPTS, "kit.py"), "tim-bo-mua", "--ghi", toi_da=300)
    if rc == 0 and "Đã thấy" in out:
        rc2, out2 = s_kho_v3()
        return rc2, out + out2
    return rc, out


def tim_claude():
    """Đường dẫn THẬT của Claude Code. Bộ cài chính thức đặt ở ~/.local/bin/claude(.exe), bản npm là claude.cmd —
    cửa sổ PowerShell mới thường chưa có ~/.local/bin trong PATH, nên không bắt người dùng gõ tên lệnh."""
    them_path()
    exe = shutil.which("claude")
    if exe:
        return exe
    for p in ([os.path.expanduser(r"~\.local\bin\claude.exe"), os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd")] if WIN
              else [os.path.expanduser("~/.local/bin/claude"), "/opt/homebrew/bin/claude", "/usr/local/bin/claude"]):
        if os.path.isfile(p):
            return p
    return None


def tim_git_bash():
    pf = [os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", ""),
          os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")]
    for d in pf:
        b = os.path.join(d, "Git", "bin", "bash.exe")
        if d and os.path.isfile(b):
            return b
    g = shutil.which("git")
    if g:
        b = os.path.join(os.path.dirname(os.path.dirname(g)), "bin", "bash.exe")
        return b if os.path.isfile(b) else g
    return None


def k_git():
    """Claude Code trên Windows cần Git for Windows (Git Bash) để chạy lệnh."""
    if not WIN:
        return None, "không cần trên Mac"
    b = tim_git_bash()
    return (True, b) if b else (False, "chưa có Git for Windows — Claude Code cần nó để chạy lệnh")


def s_git():
    return chay(["winget", "install", "--id", "Git.Git", "-e", "--silent",
                 "--accept-source-agreements", "--accept-package-agreements"])


def k_claude_cai():
    exe = tim_claude()
    if not exe:
        return False, "chưa cài Claude Code"
    rc, out = chay([exe, "--version"], toi_da=60)
    return (rc == 0), (out.strip().splitlines() or [exe])[0] if rc == 0 else f"có {exe} nhưng không chạy được"


def s_claude_cai():
    """bộ cài chính thức của Anthropic — tự tải, không hỏi gì"""
    if WIN:
        return chay(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                     "irm https://claude.ai/install.ps1 | iex"], toi_da=1200)
    return chay(["bash", "-c", "curl -fsSL https://claude.ai/install.sh | bash"], toi_da=1200)


def k_claude():
    exe = tim_claude()
    if not exe:
        return False, "chưa cài Claude Code"
    rc, out = chay([exe, "auth", "status"], toi_da=30)
    try:
        j = json.loads(out[out.index("{"):out.rindex("}") + 1])
    except Exception:
        j = {}
    if j.get("loggedIn"):
        goi = j.get("subscriptionType") or ("API key" if "api" in str(j.get("authMethod", "")).lower() else "")
        return True, "đã đăng nhập" + (f" · gói {goi}" if goi else "")
    return False, "chưa đăng nhập — bấm “Đăng nhập Claude” trong Studio (đăng nhập bằng tài khoản Claude Pro/Max)"


def k_ban_quyen():
    if os.path.exists(os.path.join(SKILL, "NGUOI-BAN")):
        return True, "máy người bán"
    if not os.path.isfile(VENV_PY):
        return False, "chưa có môi trường Python"
    rc, out = py_skill(os.path.join(SCRIPTS, "ban_quyen.py"), "kiem", toi_da=60)
    dong = out.strip().splitlines()[-1] if out.strip() else "?"
    return dong.startswith("HỢP LỆ"), dong.split("·", 1)[-1].strip() + ("" if dong.startswith("HỢP LỆ") else " — nhập mã trong thư giao hàng ở Studio")


_THU_GPU = ("import sys,json;sys.path.insert(0,r'%s');import nen_tang as NT;"
            "tb=NT.whisper_thiet_bi();c=NT._pc_doc();"
            "print(json.dumps({'nvidia':NT.nvidia(),'whisper':tb,'ly_do':(c.get('whisper') or {}).get('ly_do',''),'ma_hoa':NT._bo_ma_hoa()}))")


def _gpu_tt():
    if not os.path.isfile(VENV_PY):
        return None
    rc, out = py_skill("-c", _THU_GPU % SCRIPTS, toi_da=300)
    try:
        return json.loads(out.strip().splitlines()[-1])
    except Exception:
        return None


def k_gpu():
    """1.2.12: tăng tốc phần cứng — đã THỬ thật: nhận giọng GPU/CPU, mã hoá video phần cứng/CPU. Không bắt buộc."""
    tt = _gpu_tt()
    if not tt:
        return None, "chưa kiểm được (thiếu môi trường Python)"
    nv, (tb, _) = tt.get("nvidia") or {}, tt.get("whisper") or ["cpu", ""]
    mo_ta = f"nhận giọng: {'GPU' if tb == 'cuda' else 'CPU'} · mã hoá video: {tt.get('ma_hoa')}"
    try:                                                   # 1.3: hạng máy → công suất Studio dùng (Whisper, proxy, luồng, preset)
        rc_, out_ = py_skill("-c", _DOC_HANG, toi_da=60)
        j = _json_dong(out_, "HANG")
        if j:
            h, c = j["h"], j.get("c") or {}
            mo_ta += (f" · hạng máy {h['hang']}: nhận giọng {h['whisper']}, {h['sprite_luong']} luồng vẽ, proxy {h['proxy_cao']}p,"
                      f" x264 {h['x264_preset']} — vì {h.get('ly_do', '')}")
            if c:
                mo_ta += " · đo: " + _so_chuan(c)
    except Exception:
        pass
    if nv:
        mo_ta = f"{nv.get('ten')} (driver {nv.get('driver')}) · " + mo_ta
    try:
        drv = float((nv.get("driver") or "0").split(".")[0])
    except ValueError:
        drv = 0
    if nv and tb != "cuda" and drv >= 525:                 # card + driver đủ cho CUDA 12 mà nhận giọng vẫn CPU → thiếu thư viện CUDA
        return None, mo_ta + f" — có thể bật GPU cho nhận giọng (thiếu thư viện CUDA: {tt.get('ly_do', '')[:80]})"
    return True, mo_ta


def s_gpu():
    """cài cuBLAS + cuDNN (bản pip, ~1 GB) vào .venv cho faster-whisper chạy GPU — chỉ khi ổ còn ≥ 6 GB"""
    if shutil.disk_usage(os.path.expanduser("~")).free / 1e9 < 6:
        return 0, "ổ đĩa còn < 6 GB — không cài thư viện GPU (vẫn chạy CPU bình thường)"
    uv = shutil.which("uv")
    if not uv:
        return 1, "chưa có uv"
    rc = chay([uv, "pip", "install", "--python", VENV_PY, "nvidia-cublas-cu12", "nvidia-cudnn-cu12==9.*"], toi_da=3600)
    try:                                                   # bỏ kết quả thử cũ → lần sau thử lại với thư viện mới
        p = os.path.join(os.path.expanduser("~"), ".studio-edit-video", "phan-cung.json")
        d = json.load(open(p, encoding="utf-8")); d.pop("whisper", None); json.dump(d, open(p, "w", encoding="utf-8"))
    except Exception:
        pass
    return rc


_DOC_HANG = ("import sys,json;sys.path.insert(0,'v3');import chung;h=chung.hang_may();c=chung.phan_cung().get('chuan');"
             "print('HANG'+json.dumps({'h':h,'c':c if chung.chuan_con_dung(c) else None},ensure_ascii=False))")
_DOC_CHUAN = ("import sys,json;sys.path.insert(0,'v3');import chung;c=chung.phan_cung().get('chuan');"
              "print('CHUAN'+json.dumps({'c':c,'dung':chung.chuan_con_dung(c)},ensure_ascii=False))")
_DO_CHUAN = ("import sys,json,os;sys.path.insert(0,'v3');import chung;"
             "p=os.path.join(chung.duong('du_lieu'),'phan-cung.json');d=chung.doc_json(p) or {};"
             "d.pop('hwaccel_loi',None) and chung.ghi_json(p,d);"           # 1.2.19: đo lại = thử lại hwaccel với mọi nguồn
             "c=chung.do_chuan(lam_moi=True,log=lambda m:print(m,flush=True));"
             "h=chung.hang_may(ha_luong=False);print('CHUAN'+json.dumps({'c':c,'h':h},ensure_ascii=False))")
_PV = {"DmlExecutionProvider": "DirectML", "CoreMLExecutionProvider": "CoreML", "CPUExecutionProvider": "CPU", "CUDAExecutionProvider": "CUDA"}


def _json_dong(out, tien_to):
    for d in reversed((out or "").strip().splitlines()):
        if d.startswith(tien_to):
            try:
                return json.loads(d[len(tien_to):])
            except ValueError:
                return None
    return None


def _so_chuan(c):
    """4 số đo tốc độ → một dòng"""
    f = lambda x: f"{x:.1f}".replace(".", ",")
    ds = [f"x264 {f(c['x264_fps'])} fps" if c.get("x264_fps") else "x264 lỗi",
          f"MODNet {f(c['modnet_ms'])} ms/khung ({_PV.get(c.get('modnet_provider'), c.get('modnet_provider'))})" if c.get("modnet_ms") else "MODNet lỗi",
          (f"Whisper {f(c['whisper_giay'])} s/8 s lời (nạp {f(c.get('whisper_nap_giay') or 0)} s)" if c.get("whisper_giay")
           else f"Whisper quá {f(c['whisper_qua_han'])} s" if c.get("whisper_qua_han") else "Whisper: " + str(c.get("whisper_loi", "lỗi"))[:60]),
          f"ổ ghi {c['o_ghi_mb_s']} / đọc {c.get('o_doc_mb_s', '?')} MB/s" if c.get("o_ghi_mb_s") else "ổ lỗi"]
    return " · ".join(ds)


def k_chuan():
    """1.3: tốc độ THẬT của máy (đo một lần ~25 s) — hạng máy xếp theo đó thay vì chỉ theo thông số"""
    if not os.path.isfile(VENV_PY):
        return None, "chưa có môi trường Python"
    rc, out = py_skill("-c", _DOC_CHUAN, toi_da=60)
    j = _json_dong(out, "CHUAN")
    if j is None:
        return None, "không đọc được: " + (out.strip().splitlines() or ["?"])[-1][:160]
    c = j.get("c")
    if not c:
        return False, "chưa đo — bấm Sửa để đo (~25 giây, nên để máy rảnh); hạng máy đang xếp theo thông số"
    if not j.get("dung"):
        return False, f"số đo lúc {c.get('luc')} đã cũ (đổi ffmpeg / driver card / CPU) — đo lại"
    if c.get("do_luc_may_ban"):
        ban = max(c.get("ban_truoc") or 0, c.get("ban_sau") or 0)
        return None, (f"đã đo {c.get('luc')} nhưng lúc máy bận {ban:.0%} CPU — số có thể thấp hơn thật; "
                      f"đo lại khi rảnh: python studio/bac_si.py --chuan · " + _so_chuan(c))
    return True, f"đã đo {c.get('luc')} ({c.get('tong_giay')} s) · " + _so_chuan(c)


def s_chuan():
    """đo tốc độ thật (x264, MODNet, Whisper, ổ) → phan-cung.json mục "chuan"; hạng máy xếp lại theo đó"""
    rc, out = py_skill("-c", _DO_CHUAN, toi_da=180)
    j = _json_dong(out, "CHUAN")
    if j:
        h = j["h"]
        out = _so_chuan(j["c"]) + f"\nhạng máy {h['hang']}: {h.get('ly_do', '')}"
    return rc, out


def _duong_du_an():
    try:
        c = json.load(open(os.path.join(SKILL, "cau-hinh.json"), encoding="utf-8"))
        return os.path.expanduser(c.get("du_an") or "~/Videos/studio-du-an"), c
    except Exception:
        return os.path.expanduser("~/Videos/studio-du-an"), {}


def k_o_dia():
    tu_do = shutil.disk_usage(os.path.expanduser("~")).free / 1e9
    da, _ = _duong_du_an()
    chu = f"ổ hệ thống còn trống {tu_do:.0f} GB"
    try:
        d = da
        while d and not os.path.exists(d):
            nd = os.path.dirname(d)
            if nd == d:                       # 1.2.19: gốc ổ ngoài đã rút không tồn tại → dirname trả chính nó → không lặp vô hạn
                raise OSError(f"ổ chứa dự án không gắn: {da}")
            d = nd
        t2 = shutil.disk_usage(d).free / 1e9
        if os.path.splitdrive(d)[0].lower() != os.path.splitdrive(os.path.expanduser("~"))[0].lower():
            chu += f" · ổ dự án ({os.path.splitdrive(d)[0]}) còn {t2:.0f} GB"
        tu_do = min(tu_do, t2)
    except Exception:
        pass
    return (True if tu_do >= 10 else None if tu_do >= 4 else False), chu + (" — dưới 4 GB sẽ không dựng được video dài" if tu_do < 4 else "")


def k_he_may():
    """1.2.19 (E5): hệ máy có hỗ trợ không"""
    he = f"{platform.system()} {platform.release()} {platform.machine()}"
    if WIN_ARM:
        return False, he + " — Windows ARM chưa được hỗ trợ (thiếu thư viện tách người/nhận giọng bản ARM); dùng máy Windows x64 hoặc Mac M1+"
    if MAC and not MAC_ARM:
        return None, he + " — Mac Intel: chạy được, tách người bằng CPU (chậm)"
    if LINUX:
        return None, he + " — Linux: chạy được bằng CPU; lớp web cần Chrome/Chromium"
    return True, he


def k_kho_bo_mua():
    """1.2.19 (E): thư mục kho mua thêm còn ở đúng chỗ không (dời ổ / rút USB → mọi nhạc, SFX mất mà không ai báo)"""
    _, c = _duong_du_an()
    bm = (c.get("kho") or {}).get("bo_mua")
    if not bm:
        return None, "không khai báo kho mua thêm (chỉ dùng bộ đi kèm)"
    bm = os.path.expanduser(bm)
    if os.path.isdir(bm):
        return True, f"kho mua thêm ở {bm}"
    return False, f"KHÔNG THẤY thư mục kho mua thêm {bm} — đã dời/rút ổ? Sửa cau-hinh.json → kho.bo_mua rồi Lập lại chỉ mục ở tab Kho"


def k_onedrive():
    """1.2.19 (E11): thư mục dự án nằm trong OneDrive → đồng bộ hàng GB cache lên mây, chậm và đầy"""
    da, _ = _duong_du_an()
    if "onedrive" in da.lower():
        return None, f"thư mục dự án {da} nằm trong OneDrive — nên đổi cau-hinh.json du_an sang ổ ngoài OneDrive (một ổ khác, ngoài thư mục OneDrive)"
    return True, "thư mục dự án không bị OneDrive đồng bộ"


def k_trinh_duyet():
    """1.2.19 (E7): lớp web (3D three.js) cần Edge/Chrome/Chromium"""
    ung = []
    if WIN:
        for p in (os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
                  os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Chrome", "Application", "chrome.exe"),
                  os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe")):
            if p and os.path.isfile(p):
                ung.append(p)
    elif MAC:
        for p in ("/Applications/Google Chrome.app", "/Applications/Microsoft Edge.app", "/Applications/Chromium.app"):
            if os.path.exists(p):
                ung.append(p)
    else:
        for c in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge"):
            if shutil.which(c):
                ung.append(c)
    return (True, "có " + os.path.basename(ung[0])) if ung else (None, "không thấy Edge/Chrome — lớp web 3D sẽ bị bỏ, video vẫn dựng được")


# ma, tên, hàm kiểm, hàm sửa (None = người dùng tự làm), bắt buộc
MUC = [
    ("utf8", "Python đọc chữ có dấu (UTF-8)", k_utf8, s_utf8, True),
    ("ffmpeg", "ffmpeg (cắt ghép video)", k_ffmpeg, s_ffmpeg, True),
    ("uv", "uv (cài Python cho skill)", k_uv, s_uv, True),
    ("venv", "Môi trường Python của skill", k_venv, s_venv, True),
    ("goi", "Thư viện Python đúng phiên bản", k_goi, s_goi, True),
    ("nhan_giong", "Nhận dạng giọng nói", k_nhan_giong, s_goi, True),
    ("kho", "Kho tài nguyên sạch", k_kho, s_cai_dat, True),
    ("kho_v3", "Chỉ mục kho (tra tài nguyên theo nghĩa)", k_kho_v3, s_kho_v3, True),
    ("bo_qua", "Bộ tài nguyên quà tặng", k_bo_qua, s_bo_qua, False),
    ("git", "Git for Windows (Claude Code cần)", k_git, s_git, True),
    ("claude_cai", "Claude Code đã cài", k_claude_cai, s_claude_cai, True),
    ("claude", "Đăng nhập Claude", k_claude, None, True),
    ("ban_quyen", "Bản quyền skill", k_ban_quyen, None, True),
    ("o_dia", "Dung lượng ổ đĩa", k_o_dia, None, False),
    ("he_may", "Hệ máy", k_he_may, None, False),
    ("kho_bo_mua", "Thư mục kho mua thêm", k_kho_bo_mua, None, False),
    ("onedrive", "Thư mục dự án ngoài OneDrive", k_onedrive, None, False),
    ("trinh_duyet", "Trình duyệt cho lớp web 3D", k_trinh_duyet, None, False),
    ("chuan_may", "Đo tốc độ máy (xếp hạng công suất)", k_chuan, s_chuan, False),
    ("gpu", "Tăng tốc phần cứng (GPU / mã hoá)", k_gpu, s_gpu, False),
]


def kiem():
    them_path()
    kq = []
    for ma, ten, fk, fs, bat_buoc in MUC:
        try:
            ok, chi_tiet = fk()
        except Exception as e:
            ok, chi_tiet = False, f"lỗi khi kiểm: {e}"
        kq.append({"ma": ma, "ten": ten, "ok": ok, "chi_tiet": chi_tiet, "sua_duoc": fs is not None, "bat_buoc": bat_buoc})
    return kq


def sua():
    """sửa lần lượt, kiểm lại sau mỗi lần — thứ tự đã sắp để mục sau dựa vào mục trước"""
    them_path()
    da_cai_dat = False
    for ma, ten, fk, fs, _ in MUC:
        try:
            ok, ct = fk()
        except Exception as e:
            ok, ct = False, str(e)
        if ok or ok is None or fs is None:          # None = tuỳ chọn / chưa áp dụng
            ghi(f"{'✓' if ok else '·' if ok is None else '✗'} {ten}: {ct}")
            continue
        if fs is s_cai_dat and da_cai_dat:
            ghi(f"✗ {ten}: {ct} (bộ cài đã chạy nhưng chưa khắc phục được)")
            continue
        ghi(f"→ Đang sửa: {ten} ({ct})…")
        rc, out = fs()
        da_cai_dat = da_cai_dat or fs is s_cai_dat
        them_path()
        ok2, ct2 = fk()
        ghi(f"{'✓ Đã sửa' if ok2 else '✗ Chưa sửa được'}: {ten} — {ct2}")
        if not ok2 and out.strip():
            ghi("   " + "\n   ".join(out.strip().splitlines()[-6:]))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    if "--sua" in sys.argv:
        sua()
        ghi("XONG")
    elif "--chuan" in sys.argv:                          # đo lại tốc độ máy (kể cả khi đã đo) — nên chạy lúc máy rảnh
        rc, out = s_chuan()
        ghi(out.strip())
        ok, ct = k_chuan()
        ghi(f"{'✓' if ok else '·' if ok is None else '✗'} Đo tốc độ máy: {ct}")
    else:
        kq = kiem()
        if "--json" in sys.argv:
            print(json.dumps(kq, ensure_ascii=False))
        else:
            for x in kq:
                ghi(f"{'✓' if x['ok'] else '·' if x['ok'] is None else '✗'} {x['ten']}: {x['chi_tiet']}")
