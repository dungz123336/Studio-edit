#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Server của Studio — chỉ nghe 127.0.0.1, chỉ dùng thư viện chuẩn. Bật bằng `studio/mo.py`."""
import unicodedata, glob, json, mimetypes, os, re, shutil, socket, subprocess, sys, threading, time, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import du_lieu as D  # noqa: E402
import dong_co  # noqa: E402
import bac_si  # noqa: E402
import don_rac  # noqa: E402

sys.path.insert(0, D.SCRIPTS)
try:
    import kit  # noqa: E402
except Exception:  # skill hỏng cấu hình vẫn mở được Studio để báo lỗi
    kit = None

CONG = int(os.environ.get("STUDIO_PORT", "4777"))
WEB = os.path.join(HERE, "web")
DONG_CO = None
DUOI_VIDEO = (".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".mts", ".insv")
# /media chỉ phát tệp đa phương tiện — không bao giờ trả mã nguồn, cấu hình, thẻ bản quyền
DUOI_MEDIA = DUOI_VIDEO + (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".aif", ".aiff", ".png", ".jpg", ".jpeg",
                           ".webp", ".gif", ".ttf", ".otf", ".woff", ".woff2")
# 1.2.11: Studio nhận đủ loại tư liệu — ảnh, âm thanh, kịch bản (sheet/văn bản), thư mục, video mẫu
DUOI_ANH = (".png", ".jpg", ".jpeg", ".webp", ".heic", ".bmp", ".gif")
DUOI_AM = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".aif", ".aiff")
DUOI_TL = (".xlsx", ".xlsm", ".xls", ".docx", ".pptx", ".csv", ".tsv", ".txt", ".md", ".srt", ".vtt", ".rtf", ".pdf")
DUOI_LUT = (".cube", ".3dl")
DUOI_FONT = (".ttf", ".otf")
DUOI_NHAN = DUOI_VIDEO + DUOI_ANH + DUOI_AM + DUOI_TL + DUOI_LUT + DUOI_FONT


def loai_tep(p):
    d = os.path.splitext(str(p))[1].lower()
    return ("video" if d in DUOI_VIDEO else "anh" if d in DUOI_ANH else "am" if d in DUOI_AM
            else "tai_lieu" if d in DUOI_TL else "lut" if d in DUOI_LUT else "font" if d in DUOI_FONT else None)


def p_ket_noi():
    return os.path.join(D.DATA, "thu-muc-ket-noi.json")


def ket_noi_ds():
    try:
        return [x for x in json.load(open(p_ket_noi(), encoding="utf-8")) if os.path.isdir(x)]
    except Exception:
        return []


def ket_noi_them(ds):
    cu = ket_noi_ds()
    for x in ds:
        x = os.path.normpath(x)
        if os.path.isdir(x) and x not in cu:
            cu.append(x)
    try:
        with open(p_ket_noi(), "w", encoding="utf-8") as f:
            json.dump(cu[-60:], f, ensure_ascii=False)
    except OSError:
        pass


GHEP = re.compile(r"gh[ée]p|g[ộo]p|n[ốo]i (c[áa]c|l[ạa]i|th[àa]nh)|th[àa]nh (1|m[ộo]t) video|chung (1|m[ộo]t) video|1 video duy nh[ấa]t")
# 1.2.15: CHỈ tách thành nhiều việc khi người dùng NÓI RÕ là nhiều video thành phẩm riêng. Mặc định nhiều clip = tư liệu của MỘT video
# (khách hay quay nhiều đoạn cho một video — 1.2.14 tách nhầm mỗi clip thành một đoạn chat).
TACH = re.compile(r"m[ỗo]i (video|clip|file|t[ệe]p|c[áa]i)[^.\n]{0,25}(ri[êe]ng|m[ộo]t video|1 video|th[àa]nh ph[ẩa]m)"
                  r"|t[ừu]ng (video|clip|file)[^.\n]{0,20}ri[êe]ng|ri[êe]ng (t[ừu]ng|l[ẻe]|bi[ệe]t)|(video|clip) ri[êe]ng (bi[ệe]t|l[ẻe])"
                  r"|(\d+|hai|ba|b[ốo]n|n[ăa]m|nhi[ềe]u) video (ri[êe]ng|kh[áa]c nhau|đ[ộo]c l[ậa]p)|t[áa]ch (ra |th[àa]nh )?(t[ừu]ng|nhi[ềe]u|\d+) video"
                  r"|kh[ôo]ng gh[ée]p|đ[ừu]ng gh[ée]p|edit (ri[êe]ng|l[ầa]n l[ưu][ợo]t)|l[ầa]n l[ưu][ợo]t t[ừu]ng")


def xuat_capcut_nen(vid, du_an, ten):
    """chạy `st.py capcut` cho một dự án đã giao (chạy nền), báo kết quả vào khung chat của việc"""
    def bao(chu):
        if vid:
            try:
                D.them_tin(vid, "he_thong", chu)
            except Exception:
                pass
    co_lop = os.path.isdir(os.path.join(du_an, "4-dung", "_capcut_lop"))
    bao("🎬 Đang xuất sang CapCut… " + ("(khoảng 1–3 phút)" if co_lop else
        "(video đã giao xong nên máy phải vẽ lại các lớp hiệu ứng: thường 5–15 phút, đoạn có xoá nền lâu hơn — "
        "cứ để chạy, xong sẽ báo ở đây. Máy có CapCut thì lần sau Studio tự xuất ngay lúc dựng, chỉ 1–3 phút)"))
    try:
        r = subprocess.run([D.py_skill(), os.path.join(D.SKILL, "v2", "st.py"), "capcut", "--du-an", du_an, "--ten", ten],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=D.SKILL, timeout=1800,
                           env=D.env_con(), creationflags=D.KHONG_CUA_SO)
        xong = next((l for l in r.stdout.splitlines() if l.startswith("XONG CAPCUT")), None)
        if r.returncode == 0 and xong:
            ten_cc = os.path.basename(xong.split(" ", 2)[-1].strip())
            dang_mo = "CapCut đang mở" in r.stdout
            lech = "LỆCH BẢN" in r.stdout
            tl = next((l.split("gói tách lớp:", 1)[-1].strip() for l in r.stdout.splitlines() if "gói tách lớp:" in l), "")
            bao(f"🎬 Đã tạo project CapCut «{ten_cc}». Mở CapCut → Dự án → chọn project đó"
                + (" (CapCut đang mở: thoát hẳn rồi mở lại để thấy)" if dang_mo else "") + "."
                + (" ⚠ Mẫu gieo chưa cùng bản với CapCut đang cài: nếu CapCut không mở được, tạo một dự án trống trong CapCut, thoát CapCut, rồi bấm Xuất lại." if lech else "")
                + (f" Kèm GÓI TÁCH LỚP (phụ đề .srt + từng lớp .mov trong suốt + âm thanh, có HUONG-DAN.txt) ở {tl} — dùng được với CapCut 10.x, Premiere, DaVinci." if tl else ""))
        else:
            bao("⚠ Chưa xuất được CapCut: " + ((r.stdout + r.stderr).strip().splitlines() or ["không rõ lỗi"])[-1][:300])
    except Exception as e:
        bao(f"⚠ Xuất CapCut lỗi: {type(e).__name__}: {e}")


def tach_lo(vid, noi, tep, thu):
    """MỘT việc giao NHIỀU video → danh sách video để tách thành từng việc riêng chạy song song.
    1.2.15: CHỈ tách khi người dùng nói rõ mỗi file là một video riêng (TACH) — mặc định nhiều clip là tư liệu của MỘT video.
    Không tách khi: việc đã có tin trước (đang trao đổi dở), không phải việc dựng, hoặc người dùng muốn GHÉP."""
    try:
        v = D.doc_viec(vid)
    except KeyError:
        return None
    s = (noi or "").lower()
    if v.get("loai", "dung") != "dung":
        return None
    vids = [x for x in tep if x.lower().endswith(DUOI_VIDEO)]
    for d_ in thu:
        for goc, dirs, files in os.walk(d_):
            dirs[:] = sorted(x for x in dirs if not x.startswith("."))
            vids += [os.path.join(goc, f) for f in sorted(files) if f.lower().endswith(DUOI_VIDEO) and not f.startswith(".")]
    vids = list(dict.fromkeys(os.path.normpath(x) for x in vids))
    if len(vids) < 2:
        return None
    # 1.2.17: "dựng/làm/edit/ra/xuất thành N video" với N = đúng số clip gửi → cũng là nói rõ mỗi clip một video
    SO = {"hai": 2, "ba": 3, "bốn": 4, "bon": 4, "năm": 5, "nam": 5, "sáu": 6, "sau": 6, "bảy": 7, "bay": 7, "tám": 8, "tam": 8, "chín": 9, "chin": 9, "mười": 10, "muoi": 10}
    m_so = re.search(r"(?:th[àa]nh|ra|l[àa]m|d[ựu]ng|edit|xu[ấa]t|c[ắa]t|t[ạa]o)\s+(?:th[àa]nh\s+|ra\s+)?(\d+|hai|ba|b[ốo]n|n[ăa]m|s[áa]u|b[ảa]y|t[áa]m|ch[íi]n|m[ưu][ờo]i)\s+video", s)
    n_noi = None
    if m_so:
        g = m_so.group(1)
        n_noi = int(g) if g.isdigit() else SO.get(g)
    khop_so = n_noi is not None and n_noi >= 2 and n_noi == len(vids)
    # 1.2.15: tách được cả khi đoạn chat đã có tin trước (người dùng NÓI RÕ "riêng từng video" — không còn tách nhầm)
    s_ghep = re.sub(r"c[ắa]t\s*gh[ée]p", "cat-xxxx", s)           # "cắt ghép" = dựng video, không phải "ghép thành một"
    if not (TACH.search(s) or khop_so) or (GHEP.search(s_ghep) and not re.search(r"kh[ôo]ng gh[ée]p|đ[ừu]ng gh[ée]p", s)):
        return None
    return vids


def liet_ke_thu_muc(d, toi_da=400):
    """thư mục người dùng kết nối → danh sách tư liệu dùng được (đệ quy, bỏ thư mục/tệp ẩn)"""
    ra, bo = [], 0
    for goc, dirs, files in os.walk(d):
        dirs[:] = sorted(x for x in dirs if not x.startswith(".") and x not in ("node_modules", "__pycache__"))
        for f in sorted(files):
            if f.startswith(".") or not loai_tep(f):
                continue
            if len(ra) >= toi_da:
                bo += 1
                continue
            p = os.path.join(goc, f)
            try:
                mb = round(os.path.getsize(p) / 1e6, 1)
            except OSError:
                mb = None
            ra.append((loai_tep(f), p, mb))
    return ra, bo


def media_hop_le(f, goc_ds):
    """đúng đuôi media, nằm trong một vùng được phép, và phần đường dẫn BÊN TRONG vùng đó không có thư mục/tệp ẩn"""
    if not f.lower().endswith(DUOI_MEDIA):
        return False
    for g in goc_ds:
        if trong(f, g):
            rel = os.path.relpath(chuan(f), chuan(g))
            if not any(x.startswith(".") for x in rel.split(os.sep)):
                return True
    return False


for ext, mt in ((".cube", "text/plain"), (".ttf", "font/ttf"), (".otf", "font/otf"), (".woff2", "font/woff2"),
                (".m4a", "audio/mp4"), (".mov", "video/quicktime"), (".js", "text/javascript"),
                (".css", "text/css"), (".svg", "image/svg+xml")):
    mimetypes.add_type(mt, ext)


# ---------------------------------------------------------------- bác sĩ máy (kiểm + tự sửa môi trường)
BS = {"kq": None, "luc": 0, "dang_kiem": False, "dang_sua": False, "log": []}
BS_RE = ("ffmpeg", "claude_cai", "claude", "ban_quyen", "o_dia")     # 1.2.21: mục RẺ — kiểm định kỳ; mục nặng chỉ lúc mở / bấm nút


def bs_kiem(ep=False):
    """ep=True (lúc mở, bấm "Kiểm tra lại"): kiểm đủ mọi mục. Định kỳ 10 phút (từ /api/tong-quan): CHỈ mục rẻ (ffmpeg, claude, bản quyền,
    ổ) — bản cũ chạy ~15 tiến trình con mỗi 600 s (import faster_whisper, quét Downloads) làm máy yếu khựng khi đang dựng."""
    if BS["dang_kiem"] or BS["dang_sua"] or (not ep and BS["kq"] and time.time() - BS["luc"] < 600):
        return
    BS["dang_kiem"] = True
    day_du = ep or not BS["kq"]

    def lam():
        try:
            if day_du:
                BS["kq"] = bac_si.kiem()
            else:
                bac_si.them_path()
                moi = {}
                for ma, ten, fk, fs, bat_buoc in bac_si.MUC:
                    if ma not in BS_RE:
                        continue
                    try:
                        ok, ct = fk()
                    except Exception as e:
                        ok, ct = False, f"lỗi khi kiểm: {e}"
                    moi[ma] = {"ma": ma, "ten": ten, "ok": ok, "chi_tiet": ct, "sua_duoc": fs is not None, "bat_buoc": bat_buoc}
                BS["kq"] = [moi.get(x.get("ma"), x) for x in (BS["kq"] or [])]
            BS["luc"] = time.time()
        finally:
            BS["dang_kiem"] = False
    threading.Thread(target=lam, daemon=True).start()


def bs_sua():
    if BS["dang_sua"]:
        return
    BS["dang_sua"], BS["log"] = True, []

    def lam():
        try:
            p = subprocess.Popen([sys.executable, os.path.join(HERE, "bac_si.py"), "--sua"], stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, creationflags=D.KHONG_CUA_SO, env=D.env_con())
            for dong in p.stdout:
                BS["log"].append(dong.decode("utf-8", "replace").rstrip())
            p.wait()
        finally:
            BS["dang_sua"] = False
            D._CACHE.pop("bq", None)
            bs_kiem(ep=True)
    threading.Thread(target=lam, daemon=True).start()


CHON_TEP = r'''
import json, sys, tkinter as tk
from tkinter import filedialog
loai = sys.argv[1] if len(sys.argv) > 1 else "video"
r = tk.Tk(); r.withdraw(); r.attributes("-topmost", 1); r.update()
if loai == "thu-muc":
    try:
        x = filedialog.askdirectory(parent=r, title="Chọn thư mục tư liệu để Claude đọc", mustexist=True)
        print(json.dumps([x] if x else []))
    finally:
        r.destroy()
    sys.exit(0)
if loai == "audio":
    ft = [("Âm thanh", "*.mp3 *.wav *.m4a *.aac *.ogg"), ("Tất cả", "*.*")]
    tieu_de = "Chọn giọng mẫu (.mp3)"
    nhieu = False
elif loai == "mau":
    ft = [("Video mẫu", "*.mp4 *.mov *.m4v *.mkv *.avi *.webm"), ("Tất cả", "*.*")]
    tieu_de = "Chọn VIDEO MẪU để copy phong cách edit"
    nhieu = False
elif loai == "tat-ca":
    ft = [("Video, ảnh, âm thanh, kịch bản", "*.mp4 *.mov *.m4v *.mkv *.avi *.webm *.mts *.insv *.png *.jpg *.jpeg *.webp *.heic *.gif "
           "*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.xlsx *.xls *.docx *.pptx *.csv *.txt *.md *.srt *.pdf *.rtf"),
          ("Video", "*.mp4 *.mov *.m4v *.mkv *.avi *.webm *.mts *.insv"), ("Ảnh", "*.png *.jpg *.jpeg *.webp *.heic *.gif"),
          ("Âm thanh", "*.mp3 *.wav *.m4a *.aac *.flac *.ogg"),
          ("Kịch bản / tài liệu", "*.xlsx *.xls *.docx *.pptx *.csv *.txt *.md *.srt *.pdf *.rtf"), ("Tất cả", "*.*")]
    tieu_de = "Chọn video, ảnh, âm thanh hoặc file kịch bản"
    nhieu = True
else:
    ft = [("Video", "*.mp4 *.mov *.m4v *.mkv *.avi *.webm *.mts *.insv"), ("Tất cả", "*.*")]
    tieu_de = "Chọn video quay thô"
    nhieu = True
try:
    if nhieu:
        p = filedialog.askopenfilenames(parent=r, title=tieu_de, filetypes=ft)
    else:
        x = filedialog.askopenfilename(parent=r, title=tieu_de, filetypes=ft)
        p = [x] if x else []
    print(json.dumps(list(p)))
finally:
    r.destroy()
'''
DUOI_AUDIO = (".mp3", ".wav", ".m4a", ".aac", ".ogg")
KHOA_CHON_TEP = threading.Lock()


def chon_tep(loai="video"):
    """Chỉ mở một hộp chọn; trả lỗi rõ nếu hệ điều hành không mở được hộp."""
    if not KHOA_CHON_TEP.acquire(blocking=False):
        raise RuntimeError("Hộp chọn tệp đang mở. Chọn tệp hoặc bấm Huỷ trong hộp đó trước.")
    try:
        r = subprocess.run([sys.executable, "-c", CHON_TEP, loai], capture_output=True, timeout=900,
                           env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1"),
                           creationflags=0x08000000 if os.name == "nt" else 0)
        if r.returncode:
            detail = (r.stderr or r.stdout or b"").decode("utf-8", "replace").strip().splitlines()
            detail = (detail[-1] if detail else f"mã lỗi {r.returncode}")[:240]
            raise RuntimeError("Không mở được hộp chọn tệp của Windows: " + detail)
        lines = r.stdout.decode("utf-8", "replace").strip().splitlines()
        try:
            ds = json.loads(lines[-1]) if lines else None
        except (ValueError, TypeError):
            ds = None
        if not isinstance(ds, list) or any(not isinstance(p, str) for p in ds):
            raise RuntimeError("Hộp chọn tệp không trả kết quả hợp lệ. Thử mở Studio bằng start.bat.")
    except subprocess.TimeoutExpired as e:
        raise RuntimeError("Hộp chọn tệp đã hết thời gian chờ. Bấm thêm tệp để mở lại.") from e
    except OSError as e:
        raise RuntimeError("Không chạy được hộp chọn tệp: " + str(e)) from e
    finally:
        KHOA_CHON_TEP.release()
    if loai == "thu-muc":
        return [os.path.normpath(p) for p in ds if os.path.isdir(p)]
    duoi = DUOI_AUDIO if loai == "audio" else (DUOI_NHAN if loai == "tat-ca" else DUOI_VIDEO)
    return [os.path.normpath(p) for p in ds if os.path.isfile(p) and p.lower().endswith(duoi)]


def _giong_json(out, mac):
    try:
        return json.loads((out or "").strip().splitlines()[-1])
    except Exception:
        return mac


def _giong_tep(ten):
    import re as _re
    d = os.path.join(D.DATA, "giong")
    os.makedirs(d, exist_ok=True)
    s = _re.sub(r"[^0-9A-Za-zÀ-ỹ ]+", "", str(ten)).strip().replace(" ", "-")[:40] or "giong"
    return os.path.join(d, f"{s}-{time.strftime('%H%M%S')}.mp3")


def mo_dang_nhap_claude():
    """Mở một cửa sổ chạy Claude Code (chưa có thì cài trước) để khách đăng nhập — Studio tự nhận sau ~15 giây."""
    exe = bac_si.tim_claude()
    loi = "Cửa sổ Claude vừa mở: làm theo hướng dẫn trên màn hình (gõ /login nếu được hỏi), đăng nhập tài khoản Claude, xong gõ /exit."
    if D.WIN:
        if exe:
            lenh = f"Write-Host '{loi}' -ForegroundColor Cyan; & '{exe.replace(chr(39), chr(39) * 2)}'"
        else:
            lenh = ("Write-Host 'Đang cài Claude Code (bộ cài chính thức của Anthropic)…' -ForegroundColor Cyan; "
                    "irm https://claude.ai/install.ps1 | iex; "
                    f"Write-Host '{loi}' -ForegroundColor Cyan; & \"$env:USERPROFILE\\.local\\bin\\claude.exe\"")
        subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit", "-Command",
                          "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + lenh],
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
    elif sys.platform == "darwin":
        sh = f"'{exe}'" if exe else "curl -fsSL https://claude.ai/install.sh | bash && ~/.local/bin/claude"
        subprocess.Popen(["osascript", "-e", f'tell application "Terminal" to do script "echo \\"{loi}\\"; {sh}"',
                          "-e", 'tell application "Terminal" to activate'])
    else:                                       # 1.2.21: Linux không có osascript — in hướng dẫn, không nổ lỗi
        sh = f"'{exe}'" if exe else "curl -fsSL https://claude.ai/install.sh | bash && ~/.local/bin/claude"
        return {"ok": False, "co_san": bool(exe),
                "chu": f"Trên Linux: mở Terminal, chạy  {sh}  → đăng nhập tài khoản Claude (gõ /login nếu được hỏi), xong gõ /exit. Studio tự nhận sau ~15 giây."}
    return {"ok": True, "co_san": bool(exe)}


def kiem_ban_moi():
    """Hỏi máy chủ có bản mới không (chữ ký đã kiểm trong cap_nhat.py). Lưu vào bộ nhớ để giao diện hiện dòng báo."""
    try:
        rc, out = D.chay_script("cap_nhat.py", "kiem", toi_da=30)
    except subprocess.TimeoutExpired:
        rc, out = 124, "Không kiểm được bản mới (máy chủ không phản hồi trong 30 giây) — dùng tiếp bản " + D.phien_ban() + "."
    except Exception as e:
        rc, out = 1, f"Không kiểm được bản mới ({type(e).__name__}) — dùng tiếp bản {D.phien_ban()}."
    m = re.search(r"CÓ BẢN MỚI\s+([\d.]+)", out)
    kq = {"chu": out, "co_moi": bool(m), "ban": m.group(1) if m else ""}
    cd = D.cai_dat() or {}
    # 1.2.19 (Thêm 5): bản mới là BẮT BUỘC (khách phải lên bản mới mới dùng tiếp) — trừ khi cai-dat ghi cap_nhat_tuy_chon=true,
    # hoặc 1.2.21: người bán ghi `bat_buoc: false` trong phat-hanh.json/latest cho bản đó (cap_nhat.py in "BẮT BUỘC: 0")
    nguoi_ban_ep = not re.search(r"^BẮT BUỘC:\s*0\b", out, re.M)
    kq["bat_buoc"] = bool(m) and nguoi_ban_ep and not bool(cd.get("cap_nhat_tuy_chon"))
    try:
        hoan = float(cd.get("cn_hoan") or 0)                 # 1.2.21: lưu trong cai-dat.json (bản cũ chỉ RAM → mở lại là quên)
    except (TypeError, ValueError):
        hoan = 0
    if kq["bat_buoc"] and hoan > time.time():                # 1.2.19: cài bản mới hỏng ≥ 2 lần → tạm không ép 24 giờ (khách không bị khoá chết)
        kq["bat_buoc"] = False
        kq["chu"] += "\n(Cập nhật tự động chưa cài được trên máy này — tạm cho dùng tiếp tới " + time.strftime("%H:%M %d/%m", time.localtime(hoan)) + "; liên hệ người bán.)"
    D._CACHE["cn"] = (time.time(), kq)
    return kq


def tu_kiem_ban_moi():
    """Mở Studio là tự kiểm (sau 20 giây), rồi 6 giờ một lần. Chỉ BÁO — cài là do người dùng bấm, không cài ngầm."""
    time.sleep(20)
    while True:
        try:
            kiem_ban_moi()
        except Exception:
            pass
        time.sleep(6 * 3600)


# ---------------------------------------------------------------- 1.2.21: tiến trình con có chủ — tắt sạch, khởi động lại đúng
KHO_PROC = {"proc": None}


def _pid_theo_lenh(*mau):
    """[(pid, ppid, dòng lệnh)] các tiến trình có dòng lệnh chứa MỌI chuỗi trong mau (không phân biệt hoa thường)"""
    ra = []
    try:
        if D.WIN:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
                                "Get-CimInstance Win32_Process | ForEach-Object { '' + $_.ProcessId + '|' + $_.ParentProcessId + '|' + $_.CommandLine }"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=40, creationflags=D.KHONG_CUA_SO)
            dong = (r.stdout or "").splitlines()
        else:
            r = subprocess.run(["ps", "-eo", "pid=,ppid=,args="], capture_output=True, text=True, timeout=20)
            dong = [re.sub(r"^\s*(\d+)\s+(\d+)\s+", r"\1|\2|", l) for l in (r.stdout or "").splitlines()]
        for l in dong:
            p = l.split("|", 2)
            if len(p) == 3 and p[0].strip().isdigit() and p[2] and all(m.lower() in p[2].lower() for m in mau):
                ra.append((int(p[0]), int(p[1]) if p[1].strip().isdigit() else 0, p[2]))
    except Exception:
        pass
    return ra


def _giet(pid):
    """giết cả cây tiến trình (không qua kiểm "là tiến trình dựng" của dong_co — dùng cho kho / trình duyệt do Studio mở)"""
    try:
        if D.WIN:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(int(pid))], capture_output=True, timeout=30, creationflags=D.KHONG_CUA_SO)
        else:
            import signal
            try:
                os.killpg(int(pid), signal.SIGKILL)
            except Exception:
                os.kill(int(pid), signal.SIGKILL)
    except Exception:
        pass


def _tat_daemon_loi():
    """gửi lệnh `thoat` cho daemon Whisper của lõi (v3/doc/loi_daemon.py: nghe 127.0.0.1:<port> ghi ở <du_lieu v3>/loi-daemon.json)"""
    p = os.path.join(don_rac.du_lieu_v3(), "loi-daemon.json")
    d = D.doc_json(p) or {}
    if not d.get("port"):
        return False
    try:
        s = socket.create_connection(("127.0.0.1", int(d["port"])), timeout=3)
        s.settimeout(5)
        s.sendall(b'{"lenh": "thoat"}\n')
        try:
            s.recv(4096)
        except Exception:
            pass
        s.close()
        return True
    except Exception:
        if d.get("pid") and dong_co._pid_song(d["pid"]):
            for pid, _, cmd in _pid_theo_lenh("loi_daemon.py", "--chay"):
                if pid == int(d["pid"]):
                    _giet(pid)
                    return True
        return False
    finally:
        try:
            if os.path.isfile(p) and not (d.get("pid") and dong_co._pid_song(d["pid"])):
                os.remove(p)
        except OSError:
            pass


_DA_TAT_SACH = {"roi": False}


def tat_sach(ly_do="tắt Studio"):
    """1.2.21: /api/tat, mo.py --tat, main() finally, trước khởi động lại — giết cây tiến trình mọi việc (claude/ffmpeg/cau_noi),
    tắt máy chủ kho (server_thu.py), bảo daemon Whisper thoát, đóng trình duyệt lớp web mồ côi (profile studio-web-trinh-duyet).
    R1: chạy MỘT lần — /api/tat và khoi_dong_lai đã gọi rồi thì `finally` của main() không chạy lại (mỗi lần ~10 s PowerShell,
    giữ cổng thêm → tiến trình chờ cổng rảnh của khoi_dong_lai (30 s) có thể hết hạn → mo.py bật server mới khi cổng chưa rảnh)."""
    if _DA_TAT_SACH["roi"]:
        return
    _DA_TAT_SACH["roi"] = True
    try:
        if DONG_CO:
            DONG_CO.dung()
    except Exception:
        pass
    # R1: chỉ tắt kho DO STUDIO NÀY bật — KHO_PROC, hoặc pid trong server_thu.pid khi dòng 2 (cổng) == cong_kho() của Studio này
    # và dòng lệnh thật là `server_thu.py <cổng đó>`; KHÔNG quét giết mọi server_thu.py (hai Studio trên một máy từng tắt kho của nhau).
    # server_thu.pid chỉ xoá khi là của mình (đã tắt / đã chết).
    p = KHO_PROC.get("proc")
    pid_cua_toi = set()
    if p is not None:
        pid_cua_toi.add(p.pid)
        if p.poll() is None:
            _giet(p.pid)
    pf = os.path.join(don_rac.du_lieu_v3(), "kho-chi-muc", f"server_thu-{cong_kho()}.pid")   # 1.2.21: pid theo cổng (khớp v3/kho/server_thu.py)
    try:
        with open(pf, encoding="utf-8") as f:
            pid_kho = int((f.readline() or "0").strip() or 0)
            cong_pf = (f.readline() or "").strip()
        cua_toi = pid_kho in pid_cua_toi
        if not cua_toi and pid_kho and pid_kho != os.getpid() and cong_pf == str(cong_kho()) and dong_co._pid_song(pid_kho):
            for p_, _, cmd in _pid_theo_lenh("server_thu.py", cong_pf):
                if p_ == pid_kho and re.search(r"server_thu\.py\"?\s+" + re.escape(cong_pf) + r"\b", cmd):
                    _giet(pid_kho); cua_toi = True
                    break
        if cua_toi and not dong_co._pid_song(pid_kho):
            os.remove(pf)
    except (OSError, ValueError):
        pass
    try:
        _tat_daemon_loi()
    except Exception:
        pass
    for pid, ppid, _ in _pid_theo_lenh("studio-web-trinh-duyet"):
        if not dong_co._pid_song(ppid):                 # chỉ đóng cái không còn cha (cây việc đang chạy đã bị giết ở trên)
            _giet(pid)
    print(f"đã tắt sạch tiến trình con ({ly_do})", flush=True)


def khoi_dong_lai(server):
    """Sau khi cài bản mới: tắt sạch tiến trình con, rồi một tiến trình nhỏ CHỜ CỔNG RẢNH THẬT (thử bind, tối đa 30 s) mới gọi mo.py
    (bản cũ ngủ 2 s rồi gọi — mo.py thấy server cũ còn trả lời ping nên tưởng đang chạy, không bật lại)."""
    tat_sach("khởi động lại sau cập nhật")
    ma = ("import socket, subprocess, sys, time\n"
          f"cong = {CONG}\n"
          "het = time.time() + 30\n"
          "while time.time() < het:\n"
          "    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
          "    try:\n"
          "        s.bind(('127.0.0.1', cong)); s.close(); break\n"
          "    except OSError:\n"
          "        s.close(); time.sleep(0.5)\n"
          f"subprocess.Popen([sys.executable, {os.path.join(HERE, 'mo.py')!r}, '--chi-bat'])\n")
    lenh = [sys.executable, "-c", ma]
    kw = dict(stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    if D.WIN:
        subprocess.Popen(lenh, creationflags=0x00000200 | 0x08000000, **kw)  # nhóm tiến trình mới + console ẩn (không hiện cửa sổ CMD)
    else:
        subprocess.Popen(lenh, start_new_session=True, **kw)
    threading.Thread(target=server.shutdown, daemon=True).start()


# ---------------------------------------------------------------- 1.2.21 (1b): năng lực máy — đo lại, hiện bản kê
MAY = {"dang_do": False, "luc": 0, "loi": ""}
_MA_DO_LAI = ("import sys, json; sys.path.insert(0, 'v3'); import chung; chung.do_chuan(lam_moi=True); "
              "print('MO_TA_MAY ' + json.dumps(chung.hang_may()['mo_ta_may'], ensure_ascii=False))")
_MA_MO_TA = "import sys, json; sys.path.insert(0, 'v3'); import chung; print('MO_TA_MAY ' + json.dumps(chung.hang_may()['mo_ta_may'], ensure_ascii=False))"


def _tep_phan_cung():
    try:
        sys.path.insert(0, os.path.join(D.SKILL, "v3"))
        import chung as _c
        return os.path.join(_c.duong("du_lieu"), "phan-cung.json")
    except Exception:
        return os.path.join(don_rac.du_lieu_v3(), "phan-cung.json")


def _mo_ta_may(out):
    m = re.search(r"^MO_TA_MAY (.+)$", out or "", re.M)
    try:
        return json.loads(m.group(1)) if m else ""
    except Exception:
        return ""


def thong_tin_may():
    """GET /api/may → nang_luc + mo_ta_may + encoder_loi/hwaccel_loi (phan-cung.json của lõi) + trạng thái đang đo"""
    pc = D.doc_json(_tep_phan_cung()) or {}

    def mo_ta():
        try:
            r = subprocess.run([D.py_skill(), "-c", _MA_MO_TA], capture_output=True, cwd=D.SKILL, env=D.env_con(), timeout=60, creationflags=D.KHONG_CUA_SO)
            return _mo_ta_may(r.stdout.decode("utf-8", "replace"))
        except Exception:
            return ""
    return {"nang_luc": pc.get("nang_luc") or {}, "encoder_loi": pc.get("encoder_loi") or {}, "hwaccel_loi": pc.get("hwaccel_loi") or {},
            "gpu": pc.get("gpu"), "encoder": pc.get("encoder"), "hwaccel": pc.get("hwaccel"), "luong": pc.get("luong"), "ram_gb": pc.get("ram_gb"),
            "mo_ta_may": D._nho("mo_ta_may", 600, mo_ta) if pc else "", "dang_do": MAY["dang_do"], "do_luc": MAY["luc"], "loi": MAY["loi"]}


def do_lai_may():
    """POST /api/may/do-lai → chạy chung.do_chuan(lam_moi=True) ở tiến trình con (trần 90 s), xoá encoder_loi/hwaccel_loi để thử lại GPU"""
    if MAY["dang_do"]:
        raise ValueError("đang đo máy — đợi xong (khoảng 1 phút)")
    if DONG_CO and DONG_CO.trang_thai()["viec_chay"]:
        raise ValueError("Claude đang làm việc — đo lúc máy rảnh mới đúng; đợi xong rồi bấm lại")
    MAY.update(dang_do=True, loi="")
    try:
        r = subprocess.run([D.py_skill(), "-c", _MA_DO_LAI], capture_output=True, cwd=D.SKILL, env=D.env_con(), timeout=90, creationflags=D.KHONG_CUA_SO)
        out = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
        if r.returncode:
            MAY["loi"] = (out.strip().splitlines() or ["đo lỗi"])[-1][:300]
        D._CACHE["mo_ta_may"] = (time.time(), _mo_ta_may(out))
    except subprocess.TimeoutExpired:
        MAY["loi"] = "đo quá 90 giây — máy đang bận hoặc card đồ hoạ treo; thử lại khi rảnh"
    except Exception as e:
        MAY["loi"] = f"{type(e).__name__}: {e}"
    finally:
        MAY.update(dang_do=False, luc=time.time())
    return thong_tin_may()


def gop_y_kenh(hs, cau, dung_ai=True):
    """A4: gọi v3/hoc/gop_y.gop_y(hs, cau) ở tiến trình con (AI chuyển góp ý thành quyết định kênh, ≤ 10 phút).
    → kết quả gop_y + can_ai (máy không có AI → chỉ là lời nhắc, không phải lỗi) + phien (quyết định kênh đã lưu)"""
    ma = ("import sys, json; sys.path.insert(0, 'v3'); from hoc import gop_y as G; "
          f"r = G.gop_y({hs!r}, {cau!r}, dung_ai={bool(dung_ai)!r}); print('GOP_Y ' + json.dumps(r, ensure_ascii=False, default=str))")
    try:
        r = subprocess.run([D.py_skill(), "-c", ma], capture_output=True, cwd=D.SKILL, env=D.env_con(), timeout=600, creationflags=D.KHONG_CUA_SO)
    except subprocess.TimeoutExpired:
        raise RuntimeError("góp ý quá 10 phút — AI không phản hồi, thử lại sau")
    out = r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")
    mm = re.search(r"^GOP_Y (.+)$", out, re.M)
    if not mm:
        raise RuntimeError("không chuyển được góp ý: " + (out.strip().splitlines() or ["không rõ"])[-1][:300])
    kq = json.loads(mm.group(1))
    kq["can_ai"] = bool(kq.get("can_ai")) or (not kq.get("quyet_dinh") and not kq.get("diff") and str(kq.get("tom_tat", "")).startswith("Cần AI"))
    qd = kq.get("quyet_dinh") or {}
    kq["phien"] = qd.get("phien") if isinstance(qd, dict) else None
    kq.pop("quyet_dinh", None)                              # giao diện chỉ cần tóm tắt + phiên; bản đầy đủ nằm trong hồ sơ
    return kq


def _thu_muc_du_an():
    """thư mục dự án lõi 1.3 (theo cau-hinh.json du_an; mặc định ~/Videos/studio-du-an)"""
    try:
        sys.path.insert(0, os.path.join(D.SKILL, "v3"))
        import chung as _c
        return _c.duong("du_an")
    except Exception:
        return os.path.expanduser("~/Videos/studio-du-an")


def goi_chan_doan():
    """zip: server.log, claude-*.log (5 mới nhất), viec/*.json (5 mới nhất), phan-cung.json, cai-dat.json (bỏ khoá), bác sĩ, VERSION,
    3 dự án mới nhất: nhat-ky.txt + .v3-*.json + v3-*.log (đuôi). → DATA/chan-doan/chan-doan-<giờ>.zip"""
    import zipfile
    ra_d = os.path.join(D.DATA, "chan-doan"); os.makedirs(ra_d, exist_ok=True)
    ra = os.path.join(ra_d, time.strftime("chan-doan-%Y%m%d-%H%M%S.zip"))
    for f in sorted(glob.glob(os.path.join(ra_d, "chan-doan-*.zip")))[:-4]:
        try:
            os.remove(f)
        except OSError:
            pass

    def duoi(p, n=200000):
        try:
            with open(p, "rb") as f:
                f.seek(0, 2); k = f.tell(); f.seek(max(0, k - n)); return f.read()
        except OSError:
            return b""
    with zipfile.ZipFile(ra, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("VERSION.txt", f"{D.phien_ban()}\n{sys.platform} {sys.version}\n{time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        for f in [os.path.join(D.DATA, "server.log")] + sorted(glob.glob(os.path.join(D.DATA, "claude-*.log")), key=os.path.getmtime)[-5:]:
            if os.path.isfile(f):
                z.writestr("log/" + os.path.basename(f), duoi(f))
        for f in sorted(glob.glob(os.path.join(D.VIEC, "*.json")), key=os.path.getmtime)[-5:]:
            z.writestr("viec/" + os.path.basename(f), duoi(f, 400000))
        for ten in ("phan-cung.json", "thoi-gian.json"):
            f = os.path.join(D.DATA, ten)
            if os.path.isfile(f):
                z.writestr(ten, duoi(f))
        cd = {k: v for k, v in (D.cai_dat() or {}).items() if "khoa" not in k and "key" not in k}
        z.writestr("cai-dat.json", json.dumps(cd, ensure_ascii=False, indent=1))
        z.writestr("bac-si.json", json.dumps({"kq": BS.get("kq"), "log": (BS.get("log") or [])[-60:]}, ensure_ascii=False, indent=1))
        try:
            goc = _thu_muc_du_an()
            for d in sorted(glob.glob(os.path.join(goc, "*")), key=os.path.getmtime)[-3:]:
                for f in glob.glob(os.path.join(d, "nhat-ky.txt")) + glob.glob(os.path.join(d, ".v3-*.json")) + glob.glob(os.path.join(d, "v3-*.log")):
                    z.writestr("du-an/" + os.path.basename(d) + "/" + os.path.basename(f), duoi(f))
        except Exception:
            pass
    return {"ok": True, "tep": ra, "mb": round(os.path.getsize(ra) / 1e6, 2)}


def _don_rac_dinh_ky():
    """1.2.21 (1h): thay don_tai_len/don_du_lieu — dọn lúc mở (sau 30 s) rồi mỗi 6 giờ: nhóm a + cache dự án đóng quá giu_cache_ngay
    (khi don_rac.tu_dong bật). Chỉ xoá thứ máy tạo lại được; mục đang dùng không bao giờ bị đụng."""
    time.sleep(30)
    while True:
        try:
            kq = don_rac.tu_dong_dinh_ky()
            if kq and (kq["so_muc"] or kq["loi"]):
                print(f"dọn rác: {kq['xoa_mb']} MB, {kq['so_tep']} tệp, {len(kq['loi'])} lỗi", flush=True)
        except Exception as e:
            print(f"dọn rác lỗi: {type(e).__name__}: {e}", flush=True)
        time.sleep(6 * 3600)


_DON_NEN = {"chay": False}


def _don_truoc_dung(vid, han_giay=5.0):
    """trước khi gửi việc DỰNG: ổ chứa dự án trống < don_rac.o_trong_toi_thieu_gb → dọn, báo một dòng hệ thống vào việc.
    R1: KHÔNG quét đồng bộ cả ổ trong request — dùng kết quả quet() còn mới (60 s) nếu có, không thì chỉ quét nhanh nhóm a tối đa
    han_giay; phần còn lại (a đầy đủ → b) dọn ở luồng nền và báo `he_thong` khi xong. Nút Gửi không chờ quá ~5 s vì dọn rác."""
    try:
        cfg = don_rac.cau_hinh()
        if not cfg["tu_dong"]:
            return
        o = don_rac.o_dia()
        if o["trong_gb"] is None or o["trong_gb"] >= cfg["o_trong_toi_thieu_gb"]:
            return
        nguong = f"{cfg['o_trong_toi_thieu_gb']:g}"
        ds = don_rac.quet(han_giay=0)                       # bộ nhớ 60 s còn mới → cả a/b/c ngay; không thì None (không chờ)
        ds_a = ds if ds is not None else don_rac.quet_nhanh_a(han_giay)
        if ds_a is not None:
            kq = don_rac.don(["a"], ds=ds_a)
            o2 = don_rac.o_dia()["trong_gb"]
            D.them_tin(vid, "he_thong", f"🧹 Ổ chứa dự án chỉ còn {o['trong_gb']} GB (dưới ngưỡng {nguong} GB) — Studio đã dọn nhanh "
                                        f"{kq['xoa_mb'] / 1000:.1f} GB thứ tạo lại được ({kq['so_tep']} tệp), còn {o2} GB."
                                        + (f" {len(kq['loi'])} mục chưa xoá được." if kq["loi"] else "")
                                        + (" Vẫn dưới ngưỡng — đang dọn tiếp cache dự án đã đóng ở nền." if (o2 or 0) < cfg["o_trong_toi_thieu_gb"] else ""))
        else:
            D.them_tin(vid, "he_thong", f"🧹 Ổ chứa dự án chỉ còn {o['trong_gb']} GB (dưới ngưỡng {nguong} GB) — ổ lớn, Studio dọn ở nền và báo khi xong.")
    except Exception as e:
        print(f"dọn rác trước dựng lỗi: {e}", flush=True)
        return
    if _DON_NEN["chay"]:
        return

    def nen():
        try:
            kq = don_rac.tu_dong_khi_thap()                 # quét đủ, dọn a rồi b nếu còn thấp
            if kq and (kq["so_muc"] or kq["loi"]):
                D.them_tin(vid, "he_thong", f"🧹 Dọn nền xong: {kq['xoa_mb'] / 1000:.1f} GB ({kq['so_tep']} tệp), ổ còn {kq['o_sau_gb']} GB."
                                            + (f" {len(kq['loi'])} mục chưa xoá được." if kq["loi"] else "")
                                            + (" Vẫn dưới ngưỡng — nên xoá bớt video/dự án cũ." if (kq["o_sau_gb"] or 0) < cfg["o_trong_toi_thieu_gb"] else ""))
        except Exception as e:
            print(f"dọn rác nền lỗi: {e}", flush=True)
        finally:
            _DON_NEN["chay"] = False
    _DON_NEN["chay"] = True
    threading.Thread(target=nen, daemon=True).start()


def kho_goc():
    try:
        return kit.kho() if kit else ""
    except Exception:
        return ""


def bo_mua():
    try:
        return kit.bo_mua() if kit else ""
    except Exception:
        return ""


# ---------------------------------------------------------------- đường dẫn được phép đọc
def chuan(p):
    p = os.path.realpath(p)
    if p.startswith("\\\\?\\"):
        p = p[4:]
    return os.path.normcase(p)


def trong(p, goc):
    try:
        return os.path.commonpath([chuan(p), chuan(goc)]) == chuan(goc)
    except ValueError:
        return False


def goc_duoc_doc():
    nha = os.path.expanduser("~")
    ds = [D.SKILL, D.DATA, kho_goc(), bo_mua()] + [os.path.join(nha, x) for x in
                                                   ("Downloads", "Videos", "Movies", "Desktop", "Documents")] + ket_noi_ds()
    return [d for d in ds if d and os.path.isdir(d)]


# ---------------------------------------------------------------- kho (chỉ đọc bản đồ kho của skill)
_KHO = {"mtime": 0, "ds": []}


def _kho_json():
    p = os.path.join(kho_goc(), "ban-do-kho", "kho.json")
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return []
    if mt != _KHO["mtime"]:
        ds = D.doc_json(p, [])
        mua = bo_mua()
        for x in ds:
            x["ten"] = os.path.basename(x.get("duong", ""))
            cha = os.path.dirname(x.get("duong", ""))
            x["nhom"] = os.path.basename(cha)
            x["nguon"] = "bộ quà tặng" if mua and trong(x.get("duong", ""), mua) else "kho sạch"
            x["_tim"] = D.khong_dau(x["duong"] + " " + " ".join(x.get("the") or [])).lower()
        _KHO.update(mtime=mt, ds=ds)
    return _KHO["ds"]


def hieu_ung():
    s = D.doc_chu(os.path.join(D.SKILL, "kho", "kho-hieu-ung.md"))
    kq = []
    for ln in s.splitlines():
        m = re.match(r"\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*`?([\w\[\]\"()]+?)`?.*?\|\s*(.+?)\s*\|\s*(.+?)\s*\|", ln)
        if m:
            ten = re.sub(r"[*~⚠]", "", m.group(2)).strip()
            kq.append({"loai": "hieu_ung", "so": int(m.group(1)), "ten": ten, "ham": m.group(3).split("(")[0],
                       "nhom": m.group(4).strip(), "dung_khi": m.group(5).strip(),
                       "che": "chê" in ln or "~~" in ln})
    return kq


def kieu_chu():
    kq = []
    nguon = [os.path.join(kho_goc(), "presets", "kieu-chu-day-du.json"),
             os.path.join(D.SKILL, "tai-nguyen", "presets", "kieu-chu-day-du.json"),
             os.path.join(D.SCRIPTS, "kieu-chu-day-du.json")]
    p = next((x for x in nguon if os.path.isfile(x)), "")
    for x in D.doc_json(p, []) or []:
        lop = x.get("lop") or []
        kq.append({"loai": "kieu_chu", "ten": x.get("ma"), "nhom": "CapCut", "dung_khi": x.get("goc", ""),
                   "mau": [l.get("mau") for l in lop[:3] if l.get("mau")],
                   "chu": " / ".join(dict.fromkeys(l.get("chu", "") for l in lop if l.get("chu")))[:40]})
    s = D.doc_chu(os.path.join(D.SCRIPTS, "kieu_chu.py"))
    tay = re.findall(r'^\s*"([a-z0-9-]+)":\s*dict\(ham=_k_\w+,.*?ten="([^"]+)",\s*goc="([^"]*)"', s, re.M)
    kq[:0] = [{"loai": "kieu_chu", "ten": ma, "nhom": "chỉnh tay", "dung_khi": f"{ten} — mẫu gốc: {goc}", "mau": [],
               "chu": goc} for ma, ten, goc in tay]
    return kq


LOAI_KHO = {"nhac": "Nhạc nền", "sfx": "Tiếng động", "font": "Font", "nen": "Nền", "chong": "Lớp chồng",
            "lut": "LUT màu", "video": "Video", "icon": "Icon", "anh": "Ảnh"}


def tim_kho(loai, q, trang=0, moi_trang=60):
    q = D.khong_dau(q or "").lower().split()
    if loai == "hieu_ung":
        ds = hieu_ung()
        ds = [x for x in ds if all(t in D.khong_dau(f"{x['ten']} {x['ham']} {x['dung_khi']}").lower() for t in q)]
    elif loai == "kieu_chu":
        ds = [x for x in kieu_chu() if all(t in D.khong_dau(f"{x['ten']} {x['dung_khi']} {x['chu']}").lower() for t in q)]
    else:
        ds = [x for x in _kho_json() if x.get("loai") == loai and all(t in x["_tim"] for t in q)]
        if not ds and not _kho_json():                   # 1.3: không còn bản đồ kho cũ → tra chỉ mục kho mới (máy chủ kho, cổng cai_dat.cong_kho)
            try:
                r = urllib.request.urlopen(f"http://127.0.0.1:{cong_kho()}/api/kho/tim?loai={urllib.parse.quote(loai)}&q={urllib.parse.quote(' '.join(q))}&n={moi_trang * (trang + 1)}", timeout=4)
                muc = json.loads(r.read().decode("utf-8")).get("muc") or []
                ds = [{"id": m.get("id"), "ten": m.get("ten"), "duong": m.get("duong"), "loai": m.get("loai"), "nhom": os.path.basename(os.path.dirname(m.get("duong") or "")),
                       "nguon": "kho mới", "the": (m.get("ai") or {}).get("tu_khoa") or []} for m in muc if m.get("loai") == loai]
                return {"tong": len(ds), "ds": ds[trang * moi_trang:(trang + 1) * moi_trang]}
            except Exception:
                ds = []
        if loai == "font":
            ds = [x for x in ds if x.get("viet", True) is not False]
        ds = [{k: v for k, v in x.items() if not k.startswith("_")} for x in ds]
    return {"tong": len(ds), "ds": ds[trang * moi_trang:(trang + 1) * moi_trang]}


def dem_kho():
    ds = _kho_json()
    dem = {}
    for x in ds:
        dem[x.get("loai")] = dem.get(x.get("loai"), 0) + 1
    kq = [{"ma": "hieu_ung", "ten": "Hiệu ứng", "so": len(hieu_ung())},
          {"ma": "kieu_chu", "ten": "Kiểu chữ", "so": len(kieu_chu())}]
    kq += [{"ma": k, "ten": v, "so": dem.get(k, 0)} for k, v in LOAI_KHO.items() if dem.get(k)]
    return {"nhom": kq, "co_ban_do": bool(ds), "goc": kho_goc(), "bo_mua": bo_mua()}


# ---------------------------------------------------------------- tin nhắn gửi Claude
def lenh_phong_cach(chu):
    """'/review …' → (gói phong cách, phần còn lại) — lệnh chọn phong cách nhanh của Studio 2.0"""
    m = re.match(r"^\s*/([\w-]+)\s*(.*)$", chu, re.S)
    if not m:
        return None, chu
    k = unicodedata.normalize("NFD", m.group(1).lower())
    k = "".join(c for c in k if unicodedata.category(c) != "Mn").replace("đ", "d")
    for g in D.phong_cach_nhanh():
        ds = {x.lstrip("/").lower() for x in g.get("lenh", [])} | {str(g.get("id"))}
        if k in ds:
            return g, m.group(2).strip()
    return None, chu


def soan_loi(noi_dung, tep, kho, giong=None, them=None):
    chu = noi_dung.strip()
    g, phan_con = lenh_phong_cach(chu)
    if g:
        chu = (f"Người dùng chọn PHONG CÁCH NHANH `{g['id']}` ({g['ten']}) bằng lệnh /{chu.split()[0].lstrip('/')}. "
               f"Mở phiếu với --goi {g['id']}: Style Spec của gói vào bản tóm tắt — làm theo nó, nội dung video vẫn quyết chi tiết.\n"
               + (phan_con or "Dựng video vừa thả theo phong cách này."))
    if tep and not chu:                                    # 1.2.19 (Thêm 3): thả video mà không ghi gì → vẫn dựng, theo hồ sơ kênh
        chu = ("Người dùng thả video và KHÔNG ghi yêu cầu. Hãy tự dựng video hoàn chỉnh theo hồ sơ kênh và nội dung video "
               "(mục đích, nền tảng, độ dài do bạn suy từ lời nói trong video). Chỉ hỏi lại bằng [HỎI] khi thật sự không thể quyết "
               "(vd nhiều video rời không rõ là một hay nhiều thành phẩm).")
    if tep:
        chu += "\n\nFile video người dùng vừa thả vào Studio (đã nằm trên máy):\n" + "\n".join(f"- {p}" for p in tep)
    chu += _phan_them(them or {})
    if giong:
        chu += ("\n\nFile GIỌNG NÓI (voiceover .mp3) người dùng đã tạo và muốn dùng cho video này — "
                "lồng vào đúng đoạn phù hợp (ffmpeg), cân âm lượng với nhạc nền theo hồ sơ:\n"
                + "\n".join(f"- {p}" for p in giong))
    if kho:
        chu += ("\n\nTài nguyên người dùng tự chọn từ kho — dùng đúng thứ này nếu hợp nghĩa câu/mood, "
                "không hợp thì nói lý do (luật não vẫn áp dụng):\n"
                + "\n".join(f"- {k.get('loai_ten') or k.get('loai')}: {k.get('ten')}"
                            + (f" — `{k['ham']}`" if k.get("ham") else "")
                            + (f" — {k['duong']}" if k.get("duong") else "") for k in kho))
    return chu or "(người dùng không ghi gì)"


TEN_LOAI = {"video": "video", "anh": "ảnh", "am": "âm thanh", "tai_lieu": "kịch bản/tài liệu", "lut": "LUT màu", "font": "font"}


def _phan_them(them):
    """1.2.11: lời nhắn cho Claude về video mẫu / ảnh / âm thanh / kịch bản / thư mục người dùng gửi kèm"""
    chu = ""
    if them.get("mau"):
        chu += ("\n\nVIDEO MẪU — người dùng muốn HỌC CÁCH LÀM của video này (bố cục, chữ hiện ra thế nào, đồ hoạ, nhịp, chuyển cảnh, "
                "SFX/nhạc), KHÔNG phải footage để dựng và KHÔNG theo timeline của mẫu. Mở phiếu với `--mau <file>`: `nhanh doc` tự đo mẫu "
                "và in đường dẫn bảng khung + số đo — MỞ HẾT ảnh, rút ra Style Spec cho video này rồi viết công thức theo đó bằng công cụ "
                "của Studio (mẫu đồ hoạ, lớp chữ/thẻ, web). Không chép chữ, logo, watermark, mặt người. Không đổi màu video theo mẫu "
                "trừ khi người dùng cho chỉnh màu.\n" + "\n".join(f"- {p}" for p in them["mau"]))
    if them.get("anh"):
        chu += ("\n\nẢNH người dùng gửi kèm — dùng làm B-roll/ảnh minh hoạ đúng câu đang nói về nó bằng lớp `hinh` "
                "(noi_dung.duong = đường dẫn ảnh; cần w,h; fit cover|contain; có thể anim.ken_burns) hoặc trong mẫu đồ hoạ nhận ảnh; "
                "ảnh không hợp thì nói lý do:\n" + "\n".join(f"- {p}" for p in them["anh"]))
    if them.get("am"):
        chu += ("\n\nÂM THANH người dùng gửi kèm (nhạc nền / SFX / lời đọc) — dùng THẲNG đường dẫn file làm `id` trong am.nhac, "
                "am.sfx hoặc trường am của lớp; không rõ là nhạc hay giọng thì hỏi:\n" + "\n".join(f"- {p}" for p in them["am"]))
    if them.get("lut"):
        chu += ("\n\nLUT MÀU người dùng gửi — đây là YÊU CẦU CHỈNH MÀU: mở phiếu với `--chinh-mau`, ghi công thức "
                "`mau_video: {lut: <đường dẫn LUT>, cuong_do: 0..1}`. Chỉ áp đúng LUT này. LUT cho footage Log (tên có log/slog/dlog) "
                "mà video quay màu thường → hỏi trước:\n" + "\n".join(f"- {p}" for p in them["lut"]))
    if them.get("font"):
        chu += ("\n\nFONT người dùng gửi — dùng cho chữ của video và bìa: `phong_cach.font = {tieu_de|phu_de|nhan: <đường dẫn font>}` "
                "đúng vai họ muốn. Máy kiểm đủ dấu tiếng Việt; thiếu dấu thì nói rõ và hỏi trước khi dùng:\n"
                + "\n".join(f"- {p}" for p in them["font"]))
    if them.get("tai_lieu"):
        chu += ("\n\nFILE KỊCH BẢN / TÀI LIỆU người dùng gửi — ĐỌC trước khi dựng (sheet/Word/PowerPoint đã chuyển sẵn sang bản chữ; "
                "PDF đọc thẳng). Bám kịch bản: thứ tự ý, chữ trên màn, cảnh cần chèn; lệch với lời nói thì nói rõ:\n"
                + "\n".join(f"- {p}" + (f"  (bản chữ: {q})" if q and q != p else "") for p, q in them["tai_lieu"]))
    for d, ds, bo in them.get("thu_muc") or []:
        dem = {}
        for l, _, _ in ds:
            dem[l] = dem.get(l, 0) + 1
        chu += (f"\n\nTHƯ MỤC người dùng KẾT NỐI để bạn đọc: {d}\n("
                + (", ".join(f"{n} {TEN_LOAI.get(l, l)}" for l, n in dem.items()) or "không có tư liệu dùng được")
                + (f", còn {bo} file nữa không liệt kê" if bo else "") + "). Được Read/Glob trong thư mục này. "
                "Tự xếp: video quay thô / B-roll / video mẫu, ảnh, nhạc, kịch bản — không rõ file nào là chính thì hỏi:\n"
                + "\n".join(f"- [{TEN_LOAI.get(l, l)}] {p}" + (f" · {mb} MB" if mb else "") for l, p, mb in ds[:150])
                + ("\n- … (xem thêm bằng Glob)" if len(ds) > 150 else ""))
    return chu


def loi_hoc_v3(ho_so, nguon, thu, ghi_chu):
    """1.3: tab Học — học NGÔN NGỮ THỊ GIÁC (bố cục so với mặt, chữ hiện ra thế nào, đồ hoạ, nhịp theo lời) → Style Spec,
    lưu thành bài trong thư viện học của hồ sơ; bài đang bật tự vào bản tóm tắt mỗi lần dựng."""
    py = D.py_skill()
    t = thu.replace("\\", "/")
    return (f"[HỌC CHO HỒ SƠ `{ho_so}` · lõi 1.3] Học CÁCH LÀM từ {len(nguon)} video — KHÔNG học theo dòng thời gian, KHÔNG chép chữ, logo, "
            "tên kênh, mặt/giọng. Không đọc mã .py. Các bước:\n"
            f"1. MỘT lệnh Bash (timeout 600000): `\"{py}\" v3/cau_noi.py hoc-chuan-bi --thu \"{t}\"` — máy tải/gắn video, dựng bảng khung đều "
            "+ dải khung quanh từng sự kiện (−0,3 s · 0 · +0,4 s · +1 s), in đường ảnh.\n"
            "2. MỞ (Read) HẾT ảnh nó in và ĐỌC `ban-ghi.md` + `ngu-phap.md` nó in (1.2.20: bản ghi thi công từng cụm chữ ở mức đường cong + ngữ pháp "
            "công thức có tham số — máy đo; bạn xác nhận họ font/chỗ máy đo sai bằng ảnh cận chữ, ghi vào bai-hoc.json). Với mỗi video viết `style-spec.json` đúng khuôn schema nó chỉ (palette, type_scale, layout: anchor "
            "so với MẶT, motion_vocab: kiểu chữ vào/ra + thời lượng + easing + tách từ/ký tự, graphics_vocab, camera_vocab, sfx_vocab, "
            "rhythm_rules theo LỜI) và `bai-hoc.json` (ten, ≥3 ý da_hoc là chi tiết kỹ thuật cụ thể, hop_noi_dung, cau_truc).\n"
            f"3. `\"{py}\" v3/cau_noi.py hoc-luu --thu \"{t}\" --ho-so {ho_so}`.\n"
            "4. Trả lời người dùng: mỗi video một mục — **Đã học** (gạch đầu dòng) và cách AI sẽ dùng khi dựng. Bài nằm trong tab Học, bật/tắt được.\n"
            + (f"Ghi chú của người dùng: {ghi_chu}\n" if ghi_chu else "")
            + "Nguồn:\n" + "\n".join(f"- {u}" for u in nguon))


# ---------------------------------------------------------------- HTTP
def chuan_bi_them(vid, tep, giong, anh, am, tl, mau, thu, lut=(), font=()):
    them = {"anh": anh, "am": am, "mau": mau, "tai_lieu": [], "thu_muc": [], "lut": list(lut), "font": list(font)}
    for p_ in tl:                          # sheet / Word / PowerPoint → bản chữ để Claude đọc được
        q = None
        try:
            v2 = os.path.join(D.SKILL, "v2")
            if v2 not in sys.path:
                sys.path.insert(0, v2)
            from doc import tai_lieu as TL
            ra = os.path.join(D.TAI_LEN, "doc-duoc", os.path.splitext(os.path.basename(p_))[0] + ".txt")
            os.makedirs(os.path.dirname(ra), exist_ok=True)
            q = TL.chuyen(p_, ra)
        except Exception:
            q = None
        them["tai_lieu"].append((p_, q))
    for d_ in thu:
        ds, bo = liet_ke_thu_muc(d_)
        them["thu_muc"].append((d_, ds, bo))
    # Claude chạy ngầm chỉ được đọc thư mục skill → cấp thêm thư mục chứa tư liệu (kể cả thư mục kết nối) qua --add-dir
    cap = set(thu) | {os.path.dirname(x) for x in tep + anh + am + tl + mau + giong + list(lut) + list(font)}
    cap = {c for c in cap if c and os.path.isdir(c) and not trong(c, D.SKILL)}
    if cap:
        ket_noi_them(sorted(cap))
        D.sua_viec(vid, lambda v: v.__setitem__("thu_muc_doc", sorted(set(v.get("thu_muc_doc") or []) | cap)[-30:]))
    return them


class XuLy(BaseHTTPRequestHandler):
    server_version = "Studio/2"

    def log_message(self, fmt, *a):
        if not self.path.startswith(("/api/tong-quan", "/api/viec/", "/media")):
            sys.stderr.write("%s %s\n" % (time.strftime("%H:%M:%S"), fmt % a))

    def host_ok(self):
        return (self.headers.get("Host") or "").split(":")[0] in ("127.0.0.1", "localhost")

    def json_(self, o, ma=200):
        b = json.dumps(o, ensure_ascii=False).encode("utf-8")
        self.send_response(ma)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def loi(self, ma, tb):
        self.json_({"loi": tb}, ma)

    def tep(self, p, cache=False):
        try:
            n = os.path.getsize(p)
        except OSError:
            return self.loi(404, "không thấy file")
        mt = mimetypes.guess_type(p)[0] or "application/octet-stream"
        a, b, ma = 0, n - 1, 200
        m = re.match(r"bytes=(\d*)-(\d*)", self.headers.get("Range") or "")
        if m and n:
            if m.group(1):
                a = int(m.group(1)); b = int(m.group(2)) if m.group(2) else n - 1
            else:
                a = max(0, n - int(m.group(2)))
            b = min(b, n - 1)
            if a > b:
                self.send_response(416); self.send_header("Content-Range", f"bytes */{n}"); self.end_headers(); return
            ma = 206
        self.send_response(ma)
        self.send_header("Content-Type", mt)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(b - a + 1 if n else 0))
        if ma == 206:
            self.send_header("Content-Range", f"bytes {a}-{b}/{n}")
        self.send_header("Cache-Control", "max-age=86400" if cache else "no-cache")
        self.end_headers()
        if self.command == "HEAD" or not n:
            return
        try:
            with open(p, "rb") as f:
                f.seek(a); con = b - a + 1
                while con > 0:
                    k = f.read(min(1 << 18, con))
                    if not k:
                        break
                    self.wfile.write(k); con -= len(k)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 4_000_000:
            raise ValueError("dữ liệu quá lớn")
        return json.loads(self.rfile.read(n) or b"{}")

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if not self.host_ok():
            return self.loi(403, "chỉ mở được từ máy này")
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        p = u.path
        try:
            if p == "/api/ping":
                return self.json_({"app": "studio-edit-video", "luc": time.time()})
            if p == "/api/tong-quan":
                bs_kiem()
                ht = D.he_thong()
                ht["o_dia"] = D._nho("o_dia", 60, don_rac.o_dia)            # 1.2.21: chân cột trái đỏ khi ổ dự án < 10 GB
                ht["o_trong_toi_thieu_gb"] = don_rac.cau_hinh()["o_trong_toi_thieu_gb"]
                return self.json_({"he_thong": ht, "dong_co": DONG_CO.trang_thai(),
                                   "ho_so": D.ds_ho_so(), "dang_dung": D.ho_so_dang_dung(),
                                   "phieu": D.phieu(q.get("viec")), "phieu_ds": D.ds_phieu(q.get("viec")),
                                   "phieu2_ds": D.ds_phieu2(q.get("viec")),
                                   "moc_viec": D.dau_moc_viec(),
                                   "bac_si": {"kq": BS["kq"], "dang_kiem": BS["dang_kiem"],
                                              "dang_sua": BS["dang_sua"], "log": BS["log"][-60:]}})
            if p == "/api/cai-dat":
                return self.json_({**D.cai_dat(), "ten_model": D.TEN_MODEL, "toi_da_nang": DONG_CO.tai.toi_da_nang(),
                                   "luong": os.cpu_count() or 1, "ram_gb": round(DONG_CO.tai.ram_trong_gb()[1] or 0, 1)})
            if p == "/api/khoi-dau":
                return self.json_({"bo": D.bo_phong_cach(), "ten_buoc": D.ten_buoc(), "kho": dem_kho(),
                                   "buoc2": D.buoc2(), "phong_cach_nhanh": D.phong_cach_nhanh(), "cong_kho": cong_kho()})
            if p == "/api/cau-hinh-kho":                  # 1.2.21 (A6): cấu hình kho mới cau-hinh.json → v3.kho
                return self.json_(cau_hinh_kho())
            if p == "/api/may":                           # 1.2.21 (1b): bản kê năng lực máy
                return self.json_(thong_tin_may())
            if p == "/api/don-rac":                       # 1.2.21 (1h): quét rác (nhớ 60 s; ?moi=1 quét lại)
                ds = don_rac.quet(moi=q.get("moi") == "1")
                muc = sorted(ds, key=lambda x: -x["mb"])[:300]
                return self.json_({"o": don_rac.o_dia(), "cau_hinh": don_rac.cau_hinh(), "tom_tat": don_rac.tom_tat(ds), "muc": muc,
                                   "so_muc": len(ds)})
            m = re.fullmatch(r"/api/ho-so/([\w-]+)", p)
            if m:
                return self.json_(D.chi_tiet_ho_so(m.group(1)))
            m = re.fullmatch(r"/api/ho-so/([\w-]+)/hoc/([\w.-]+)\.jpg", p)
            if m:                                   # 1.2.15: ảnh so sánh gốc | máy dựng lại của một bài học
                return self.tep(os.path.join(D.CN, m.group(1), "hoc", m.group(2) + ".jpg"), cache=True)
            if p == "/api/viec":
                return self.json_(D.ds_viec(q.get("ho_so")))
            m = re.fullmatch(r"/api/viec/([a-z0-9-]+)", p)
            if m:
                return self.json_(D.doc_viec(m.group(1)))
            if p == "/api/kho":
                return self.json_(tim_kho(q.get("loai", "nhac"), q.get("q", ""), int(q.get("trang", 0)),
                                          max(1, min(1000, int(q.get("n", 60))))))
            if p == "/api/cap-nhat":
                return self.json_(kiem_ban_moi())
            if p == "/api/giong":
                rc, out = D.chay_script("giong_noi.py", "trang-thai", toi_da=25)
                return self.json_(_giong_json(out, {"co_khoa": False}))
            if p == "/api/giong/voices":
                rc, out = D.chay_script("giong_noi.py", "voices", toi_da=25)
                j = _giong_json(out, [])
                return self.json_({"voices": j} if isinstance(j, list) else j)
            if p == "/api/thumb":
                a = anh_thu_nho(q.get("p", ""))
                return self.tep(a, cache=True) if a else self.loi(404, "không có ảnh thu nhỏ")
            if p == "/media":
                f = q.get("p", "")
                if not os.path.isfile(f):
                    return self.loi(404, "không thấy file")
                if not media_hop_le(f, goc_duoc_doc()):
                    return self.loi(403, "file nằm ngoài vùng Studio được đọc")
                return self.tep(f, cache="v" in q)
        except KeyError:
            return self.loi(404, "không có")
        if p.startswith("/api/"):
            return self.loi(404, "không có đường này")
        rel = p.lstrip("/") or "index.html"
        f = os.path.join(WEB, rel)
        if not trong(f, WEB) or not os.path.isfile(f):
            f = os.path.join(WEB, "index.html")
        return self.tep(f)

    def do_POST(self):
        if not self.host_ok():
            return self.loi(403, "chỉ mở được từ máy này")
        nguon = self.headers.get("Origin")
        if nguon and urllib.parse.urlparse(nguon).hostname not in ("127.0.0.1", "localhost"):
            return self.loi(403, "nguồn gọi không hợp lệ")
        u = urllib.parse.urlparse(self.path)
        p = u.path
        if p == "/api/tai-len":
            return self.tai_len({k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()})
        if "application/json" not in (self.headers.get("Content-Type") or ""):
            return self.loi(415, "cần JSON")
        try:
            b = self.body()
        except (ValueError, json.JSONDecodeError) as e:
            return self.loi(400, f"dữ liệu hỏng: {e}")
        try:
            return self.xu_ly_post(p, b)
        except KeyError:
            return self.loi(404, "không có")
        except (ValueError, RuntimeError) as e:
            return self.loi(400, str(e))

    def xu_ly_post(self, p, b):
        if p == "/api/ho-so":
            ten_kenh = str(b.get("kenh") or "").strip()
            if not ten_kenh:
                raise ValueError("cần tên kênh")
            ma = D.tao_ho_so(ten_kenh, str(b.get("mau") or ""), b.get("bo") or None, b.get("ma") or None,
                             gu=(b.get("gu") if isinstance(b.get("gu"), dict) else None))
            return self.json_({"ten": ma})
        m = re.fullmatch(r"/api/ho-so/([\w-]+)", p)
        if m:
            D.sua_ho_so(m.group(1), b.get("cau_hinh"), b.get("phong_cach"), b.get("anh_bia"), b.get("nguon_hoc"))
            return self.json_(D.chi_tiet_ho_so(m.group(1)))
        m = re.fullmatch(r"/api/ho-so/([\w-]+)/hoc", p)
        if m:
            hs = m.group(1)
            links = [str(x).strip() for x in (b.get("links") or []) if re.match(r"https?://", str(x).strip())]
            tep = [os.path.normpath(str(x)) for x in (b.get("tep") or []) if str(x).lower().endswith(DUOI_VIDEO) and os.path.isfile(str(x))]
            if not links and not tep:
                raise ValueError("chưa có video nào — dán link TikTok/Facebook/YouTube hoặc chọn video trên máy")
            D.chi_tiet_ho_so(hs)
            # 1.2.15: mỗi lần học một thư mục riêng trong dữ liệu Studio; nguon.txt = link + đường dẫn video máy (bộ học tự tải/gắn)
            thu = os.path.join(D.DATA, "hoc", hs, time.strftime("%Y%m%d-%H%M%S"))
            os.makedirs(thu, exist_ok=True)
            open(os.path.join(thu, "nguon.txt"), "w", encoding="utf-8").write("\n".join(links + tep) + "\n")
            nguon = links + [os.path.basename(x) for x in tep]
            v = D.tao_viec(hs, f"Học từ {len(nguon)} video", loai="hoc")
            D.them_tin(v["id"], "nguoi_dung", f"Học từ {len(nguon)} video cho hồ sơ này", links=links)
            loi_ = loi_hoc_v3(hs, links + tep, thu, str(b.get("ghi_chu") or ""))   # 1.3
            DONG_CO.gui(v["id"], loi_)
            return self.json_(v)
        m = re.fullmatch(r"/api/ho-so/([\w-]+)/hoc/([\w.-]+)", p)
        if m:                                       # 1.2.15: bật / tắt / xoá một bài trong thư viện học
            D.sua_bai_hoc(m.group(1), m.group(2), bat=b.get("bat"), xoa=bool(b.get("xoa")))
            return self.json_(D.chi_tiet_ho_so(m.group(1)))
        if p == "/api/viec":
            hs = str(b.get("ho_so") or "")
            D.chi_tiet_ho_so(hs)
            return self.json_(D.tao_viec(hs))
        m = re.fullmatch(r"/api/viec/([a-z0-9-]+)/(gui|dung|xoa|doi-ten)", p)
        if m:
            vid, lenh = m.groups()
            if lenh == "gui":
                cn = D._CACHE.get("cn", (0, None))[1] or {}
                dang_do = vid in DONG_CO.chay or bool((D.doc_viec(vid) or {}).get("cho_tra_loi"))
                if cn.get("co_moi") and cn.get("bat_buoc") and not dang_do:   # 1.2.19 (Thêm 5): có bản mới → phải cập nhật mới dùng tiếp (việc đang dở vẫn trả lời được)
                    raise ValueError(f"Có bản Studio mới {cn.get('ban') or ''} — bắt buộc cập nhật trước khi dùng tiếp (bấm “Cập nhật ngay” ở bảng trên).")
                if BS.get("dang_sua"):
                    raise ValueError("Studio đang cài/sửa thư viện cho máy (sau cập nhật) — đợi xong rồi gửi lại, thường 1–5 phút.")
                noi = str(b.get("noi_dung") or "")[:12000]
                tep = [str(x) for x in (b.get("tep") or [])][:20]
                kho = [x for x in (b.get("kho") or []) if isinstance(x, dict)][:30]
                giong = [str(x) for x in (b.get("giong") or []) if os.path.isfile(str(x))][:8]

                def ds_(k, n=40):
                    return [os.path.normpath(str(x)) for x in (b.get(k) or []) if os.path.isfile(str(x))][:n]
                anh, am, tl, mau = ds_("anh"), ds_("am"), ds_("tai_lieu", 12), ds_("mau", 3)
                lut, font = ds_("lut", 6), ds_("font", 12)
                thu = [os.path.normpath(str(x)) for x in (b.get("thu_muc") or []) if os.path.isdir(str(x))][:5]
                if not noi.strip() and not tep and not kho and not giong and not (anh or am or tl or mau or thu or lut or font):
                    raise ValueError("chưa có nội dung")
                g = D.gac()               # chưa kích hoạt / gói bị sửa → chặn ngay, không ghi tin, không chạy Claude
                if not g["ok"]:
                    raise ValueError(("Bộ cài đã bị thay đổi — cài lại Studio từ link chính chủ. " if g["loai"] == "toan-ven"
                                      else "Chưa kích hoạt bản quyền — nhập mã trong thư giao hàng ở bảng “Máy, bản quyền” (góc dưới bên trái). ") + g["chu"])
                D.doc_viec(vid)
                che_do = "nhanh" if b.get("nhanh") else None        # 1.3: công tắc "⚡ Làm nhanh" trong khung chat
                if che_do or D.doc_viec(vid).get("che_do"):
                    D.sua_viec(vid, lambda v: v.__setitem__("che_do", che_do))
                # 1.2.21: form Đơn giản đã ghi rõ vai từng clip → không dò chữ trong ghi chú để tách việc; đường cũ giữ nguyên
                lo = None if b.get("don_gian") is True else tach_lo(vid, noi, tep, thu)
                if lo:                    # 1.3: nhiều video → mỗi video một việc riêng (phiên AI riêng), chạy song song theo sức máy
                    hs_ = D.doc_viec(vid).get("ho_so")
                    them_anh, them_am, them_tl = list(anh), list(am), list(tl)
                    co_vid = {d_ for d_ in thu if any(p_.startswith(os.path.normpath(d_)) for p_ in lo)}
                    thu_tl = [d_ for d_ in thu if d_ not in co_vid]       # thư mục tư liệu (ảnh…) → giữ NGUYÊN thư mục, AI tự chọn
                    for d_ in co_vid:     # tư liệu lẻ nằm cùng thư mục video (ảnh, nhạc, kịch bản) → chia cho mọi video
                        for goc, dirs, files in os.walk(d_):
                            dirs[:] = [x for x in dirs if not x.startswith(".")]
                            for f in files:
                                lt, p_ = loai_tep(f), os.path.join(goc, f)
                                if lt == "anh" and len(them_anh) < 40:
                                    them_anh.append(p_)
                                elif lt == "am" and len(them_am) < 40:
                                    them_am.append(p_)
                                elif lt == "tai_lieu" and len(them_tl) < 12:
                                    them_tl.append(p_)
                    D.them_tin(vid, "nguoi_dung", noi, tep=[os.path.basename(x) for x in tep],
                               thu_muc=[os.path.basename(x.rstrip("\\/")) or x for x in thu])
                    con = []
                    for i, p_ in enumerate(lo):
                        ten_ = os.path.splitext(os.path.basename(p_))[0]
                        c = D.tao_viec(hs_, f"{i + 1}/{len(lo)} · {ten_[:48]}")
                        D.sua_viec(c["id"], lambda v, vid=vid: (v.__setitem__("lo", vid), v.__setitem__("che_do", che_do)))
                        ghi = (f"{noi}\n\n[LÔ {len(lo)} VIDEO — việc này là video {i + 1}/{len(lo)}: {os.path.basename(p_)}. Chỉ dựng ĐÚNG video này. "
                               "Các video khác trong lô chạy ở việc riêng song song — giữ ý tưởng, kiểu chữ, bìa KHÁC các video cùng lô.]")
                        D.them_tin(c["id"], "nguoi_dung", ghi, tep=[os.path.basename(p_)], anh=[os.path.basename(x) for x in them_anh],
                                   am=[os.path.basename(x) for x in them_am], tai_lieu=[os.path.basename(x) for x in them_tl])
                        DONG_CO.gui(c["id"], soan_loi(ghi, [p_], kho, giong,
                                                      chuan_bi_them(c["id"], [p_], giong, them_anh, them_am, them_tl, mau, thu_tl, lut, font)), nang=True)
                        con.append(c["id"])
                    k = DONG_CO.tai.toi_da_nang()
                    D.them_tin(vid, "he_thong", f"Đã tách thành {len(lo)} việc riêng (mỗi video một phiên AI) — máy này chạy {k} video cùng lúc, "
                                                "video còn lại tự chạy khi có chỗ trống. Trong lúc AI của video này nghĩ, máy dựng video kia — "
                                                "nhanh gần gấp đôi làm lần lượt. Theo dõi từng video ở cột trái.")
                    D.sua_viec(vid, lambda v: (v.__setitem__("ten", f"Lô {len(lo)} video — {noi[:40]}"), v.__setitem__("con", con)))
                    _don_truoc_dung(vid)                                  # 1.2.21: ổ thấp → dọn trước khi dựng
                    return self.json_({"ok": True, "tach": con})
                D.them_tin(vid, "nguoi_dung", noi, tep=[os.path.basename(x) for x in tep],
                           kho=[{"loai": k.get("loai"), "ten": k.get("ten")} for k in kho],
                           giong=[os.path.basename(x) for x in giong],
                           anh=[os.path.basename(x) for x in anh], am=[os.path.basename(x) for x in am],
                           tai_lieu=[os.path.basename(x) for x in tl], mau=[os.path.basename(x) for x in mau],
                           lut=[os.path.basename(x) for x in lut], font=[os.path.basename(x) for x in font],
                           thu_muc=[os.path.basename(x.rstrip("\\/")) or x for x in thu])
                loi_ = soan_loi(noi, tep, kho, giong, chuan_bi_them(vid, tep, giong, anh, am, tl, mau, thu, lut, font))
                if b.get("nang") or dong_co.NANG.search(loi_):
                    _don_truoc_dung(vid)                                  # 1.2.21: việc dựng + ổ thấp → dọn a→b trước, báo một dòng
                DONG_CO.gui(vid, loi_)
                return self.json_({"ok": True})
            if lenh == "dung":
                return self.json_({"ok": DONG_CO.dung(vid)})
            if lenh == "xoa":
                DONG_CO.dung(vid)
                da_xoa = None
                if b.get("xoa_du_an"):                                    # 1.2.21: ô "xoá cả thư mục dự án và bản tải lên"
                    da_xoa = don_rac.xoa_cua_viec(vid, dong_co._du_an_cua(vid))
                D.xoa_viec(vid)
                return self.json_({"ok": True, "da_xoa": da_xoa})
            ten = str(b.get("ten") or "").strip()[:80]
            D.sua_viec(vid, lambda v: v.__setitem__("ten", ten or v["ten"]))
            return self.json_({"ok": True})
        if p == "/api/bac-si/kiem":
            bs_kiem(ep=True)
            return self.json_({"ok": True})
        if p == "/api/bac-si/sua":
            bs_sua()
            return self.json_({"ok": True})
        if p == "/api/tai-mau":
            return self.json_(tai_video_mau(b.get("url")))
        if p == "/api/chon-tep":
            ds = chon_tep(b.get("loai") or "video")
            return self.json_({"tep": ds, "chi_tiet": [{"duong_dan": x, "ten": os.path.basename(x.rstrip("\\/")) or x,
                                                        "loai": "thu_muc" if os.path.isdir(x) else loai_tep(x)} for x in ds]})
        if p == "/api/cai-dat":                           # 1.2.21 (1a): mọi khoá kiểm ở D.kiem_cai_dat — sai → 400
            cd = D.luu_cai_dat(D.kiem_cai_dat(b))
            D._CACHE.pop("o_dia", None)
            return self.json_({**cd, "ten_model": D.TEN_MODEL, "toi_da_nang": DONG_CO.tai.toi_da_nang()})
        if p == "/api/cau-hinh-kho":                      # 1.2.21 (A6): ghi v3.kho vào cau-hinh.json (đọc-sửa-ghi); kho server đọc lúc bật → đổi xong mở lại Studio
            return self.json_(luu_cau_hinh_kho(b))
        if p == "/api/may/do-lai":                        # 1.2.21 (1b): nút "Đo lại máy" / "Thử lại GPU" (~55 s)
            return self.json_(do_lai_may())
        m = re.fullmatch(r"/api/ho-so/([\w-]+)/gop-y", p)
        if m:                                             # 1.2.21 (A4): góp ý kênh → v3/hoc/gop_y.gop_y → quyết định kênh (AI chuyển; không AI → "Cần AI…", không phải lỗi)
            cau = str(b.get("cau") or "").strip()[:600]
            if not cau:
                raise ValueError("chưa ghi góp ý")
            D.chi_tiet_ho_so(m.group(1))
            return self.json_(gop_y_kenh(m.group(1), cau, dung_ai=b.get("dung_ai", True) is not False))
        if p == "/api/don-rac":                           # 1.2.21 (1h): dọn — {nhom: "a"|["a","b"], ngay?, duong?: [...], xac_nhan?}
            nhom = b.get("nhom") or []
            nhom = list(nhom) if isinstance(nhom, (list, tuple)) else [c for c in str(nhom) if c in "abc"]
            if any(n not in ("a", "b", "c") for n in nhom):
                raise ValueError("nhóm phải là a, b hoặc c")
            duong = [str(x) for x in (b.get("duong") or [])][:500]
            if not nhom and not duong:
                raise ValueError("cần nhóm cần dọn (a/b/c) hoặc danh sách đường dẫn")
            ngay = b.get("ngay")
            if ngay is not None:
                try:
                    ngay = float(ngay)
                except (TypeError, ValueError):
                    raise ValueError("ngay phải là số")
                if ngay < 0:
                    raise ValueError("ngay phải ≥ 0")
            kq = don_rac.don(nhom, ngay=ngay, duong_ds=duong or None, xac_nhan=bool(b.get("xac_nhan")))
            D._CACHE.pop("o_dia", None)
            kq["o"] = don_rac.o_dia()
            return self.json_(kq)
        if p == "/api/giong/khoa":
            khoa = str(b.get("khoa") or "").strip()
            if not (20 <= len(khoa) <= 120):
                raise ValueError("khoá không hợp lệ")
            rc, out = D.chay_script("giong_noi.py", "luu-khoa", toi_da=40, nhap=khoa + "\n")
            return self.json_(_giong_json(out, {"ok": rc == 0}))
        if p == "/api/giong/nghe-thu":
            # 1.2.11: nghe thử giọng — ưu tiên mẫu đóng kèm gói (không tốn lượt); giọng mới thì tạo 1 lần rồi lưu trên máy
            idx = str(b.get("voice") or "0")
            if not re.fullmatch(r"\d{1,4}", idx):
                raise ValueError("giọng không hợp lệ")
            ten = str(b.get("ten") or "")
            goc = os.path.join(D.SKILL, "v2", "giong-thu")
            ds = D.doc_json(os.path.join(goc, "danh-sach.json"), {}) or {}
            x = ds.get(idx) or {}
            if x.get("tep") and (not ten or x.get("ten") == ten) and os.path.isfile(os.path.join(goc, x["tep"])):
                return self.json_({"ok": True, "tep": os.path.join(goc, x["tep"]), "mat_luot": False})
            nho = os.path.join(D.DATA, "giong-thu"); os.makedirs(nho, exist_ok=True)
            ra = os.path.join(nho, f"giong-{idx}.mp3")
            if os.path.isfile(ra) and os.path.getsize(ra) > 2000:
                return self.json_({"ok": True, "tep": ra, "mat_luot": False})
            rc, out = D.chay_script("giong_noi.py", "tao", "Xin chào, đây là giọng đọc thử. Bạn nghe xem giọng này có hợp với video "
                                    "của mình không nhé.", "--voice", idx, "--ra", ra, toi_da=180)
            kq = _giong_json(out, {"ok": False, "loi": "không tạo được mẫu nghe thử"})
            if os.path.isfile(ra):
                kq.update(ok=True, tep=ra, mat_luot=True)
            return self.json_(kq)
        if p == "/api/giong/tao":
            text = str(b.get("text") or "").strip()[:4000]
            if not text:
                raise ValueError("chưa nhập lời đọc")
            voice = str(b.get("voice") or "0")
            ra = _giong_tep(b.get("ten") or text)
            gioi_han = 1000                                             # 1.2.19: thư viện tự chờ theo độ dài (≤ 15 phút) — route không cắt trước
            try:
                if str(b.get("clone") or "") and b.get("mau"):
                    rc, out = D.chay_script("giong_noi.py", "clone", text, "--mau", str(b.get("mau")), "--ra", ra, toi_da=gioi_han)
                else:
                    rc, out = D.chay_script("giong_noi.py", "tao", text, "--voice", voice, "--ra", ra, toi_da=gioi_han)
            except subprocess.TimeoutExpired:
                return self.json_({"ok": False, "loi": "máy chủ giọng nói đang quá chậm — thử lại sau ít phút (văn bản ngắn hơn sẽ nhanh hơn)"})
            kq = _giong_json(out, {"ok": False, "loi": "không rõ kết quả"})
            if kq.get("ok") and os.path.isfile(ra):
                kq["tep"] = ra
            return self.json_(kq)
        m = re.fullmatch(r"/api/ho-so/([\w-]+)/xoa", p)
        if m:                                       # 1.2.15: xoá hẳn — phải gửi đúng tên hồ sơ để xác nhận
            if str(b.get("xac_nhan") or "") != m.group(1):
                raise ValueError("gõ đúng tên hồ sơ để xác nhận xoá")
            DONG_CO.dung_ho_so(m.group(1))
            return self.json_({"ok": D.xoa_ho_so(m.group(1))})
        m = re.fullmatch(r"/api/ho-so/([\w-]+)/luu-tru", p)
        if m:
            DONG_CO.dung_ho_so(m.group(1))
            return self.json_({"noi": D.luu_tru_ho_so(m.group(1))})
        if p == "/api/kich-hoat":
            ma = str(b.get("ma") or "").strip()
            if not re.fullmatch(r"[A-Za-z0-9-]{8,64}", ma):
                raise ValueError("mã bản quyền không đúng dạng (ví dụ EV123456-XXXX-XXXX-XXXX)")
            rc, out = D.chay_script("ban_quyen.py", "kich-hoat", ma, toi_da=60)
            D.ban_quyen(lam_moi=True)
            return self.json_({"ok": rc == 0, "chu": out})
        if p == "/api/nhip":
            D.nhip_dinh_ky(ep=True)                      # gói tháng: gọi về gia hạn ngay (nút "đã gia hạn")
            bq = D.ban_quyen(lam_moi=True)
            return self.json_({"ok": bool(bq.get("hop_le")), "chu": bq.get("chu", "")})
        if p == "/api/cap-nhat/cai":
            if DONG_CO.trang_thai()["viec_chay"]:
                raise ValueError("Claude đang làm việc — đợi xong (hoặc bấm Dừng) rồi cập nhật")
            if BS.get("dang_sua"):                                       # 1.2.21: bác sĩ đang `uv pip install` → không cài đè
                raise ValueError("Studio đang cài/sửa thư viện cho máy — đợi xong (1–5 phút) rồi bấm cập nhật lại")
            try:                                                         # 1.2.21: MỌI lỗi/timeout đều đếm là một lần hỏng (bản cũ nổ TimeoutExpired → khách mạng yếu bị khoá vĩnh viễn)
                rc, out = D.chay_script("cap_nhat.py", "cai", toi_da=1800)
            except subprocess.TimeoutExpired:
                rc, out = 124, "Tải/cài bản mới quá 30 phút (mạng chậm hoặc máy chủ không phản hồi) — thử lại sau; sau 2 lần hỏng Studio tạm cho dùng tiếp 24 giờ."
            except Exception as e:
                rc, out = 1, f"Không chạy được cập nhật: {type(e).__name__}: {e}"
            D._CACHE.pop("cn", None)
            ok = rc == 0 and "ĐÃ CẬP NHẬT" in out
            if not ok:                                                   # 1.2.19: đếm lần hỏng → hoãn ép cập nhật · 1.2.21: lưu cai-dat.json
                hong = int((D.cai_dat().get("cn_hong") or 0)) + 1
                moi = {"cn_hong": hong}
                if hong >= 2:
                    moi["cn_hoan"] = time.time() + 24 * 3600
                D.luu_cai_dat(moi)
            else:
                D.luu_cai_dat({"cn_hong": 0, "cn_hoan": 0})
            self.json_({"ok": ok, "chu": out, "khoi_dong_lai": ok})
            if ok:
                khoi_dong_lai(self.server)
            return
        if p == "/api/capcut":                # 1.3: nút "Xuất sang CapCut" trên thẻ video đã giao
            tm = os.path.normpath(str(b.get("thu_muc") or ""))
            f = os.path.join(tm, ".du-an")
            if not os.path.isfile(f):
                raise ValueError("không tìm thấy dự án của video này (thiếu .du-an trong thư mục giao)")
            du = open(f, encoding="utf-8").read().strip()
            if not os.path.isdir(du):
                raise ValueError("thư mục dự án của video này đã bị xoá — không xuất CapCut được")
            threading.Thread(target=xuat_capcut_nen, args=(str(b.get("viec") or ""), du, os.path.basename(tm)), daemon=True).start()
            return self.json_({"ok": True})
        if p == "/api/mo-thu-muc":
            f = str(b.get("p") or "")
            f = f if os.path.isdir(f) else os.path.dirname(f)
            if not os.path.isdir(f) or not any(trong(f, g) for g in goc_duoc_doc()):
                raise ValueError("không mở được thư mục này")
            if D.WIN:
                os.startfile(f)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", f])
            return self.json_({"ok": True})
        if p == "/api/claude/dang-nhap":
            return self.json_(mo_dang_nhap_claude())
        if p == "/api/chan-doan":                       # 1.2.19 (F6): gói chẩn đoán gửi người bán (log + việc gần nhất + máy), không chứa khoá
            return self.json_(goi_chan_doan())
        if p == "/api/tat":
            self.json_({"ok": True})

            def tat():
                tat_sach("/api/tat")                      # 1.2.21: giết cây tiến trình việc, kho, daemon lời, trình duyệt lớp web
                self.server.shutdown()
            threading.Thread(target=tat, daemon=True).start()
            return
        return self.loi(404, "không có đường này")

    def tai_len(self, q):
        ten = os.path.basename(q.get("ten", "")).strip()
        if not ten.lower().endswith(DUOI_NHAN):
            return self.loi(400, "chỉ nhận video, ảnh, âm thanh hoặc file kịch bản (xlsx, docx, csv, txt, pdf…)")
        n = int(self.headers.get("Content-Length") or 0)
        nguon = q.get("nguon") or ""                      # 1.2.21: khách đưa được ĐƯỜNG DẪN THẬT → hardlink cùng ổ / chép, không nhận thân
        if nguon and os.path.isfile(nguon) and os.path.basename(nguon) == ten:
            return self._tai_len_tu_duong(nguon, ten, n)
        if n <= 0:
            return self.loi(400, "file rỗng")
        thu = os.path.join(D.TAI_LEN, time.strftime("%Y-%m-%d"))
        os.makedirs(thu, exist_ok=True)
        goc_, duoi = os.path.splitext(ten)
        f, i = os.path.join(thu, ten), 1
        while os.path.exists(f):
            i += 1
            f = os.path.join(thu, f"{goc_}-{i}{duoi}")
        tam = f + ".dang-tai"
        try:
            with open(tam, "wb") as o:
                con = n
                while con > 0:
                    k = self.rfile.read(min(1 << 20, con))
                    if not k:
                        break
                    o.write(k); con -= len(k)
            if con:
                raise IOError("tải lên bị ngắt giữa chừng")
            os.replace(tam, f)
        except Exception as e:
            try:
                os.remove(tam)
            except OSError:
                pass
            return self.loi(500, f"không lưu được file: {e}")
        return self.json_({"duong_dan": f, "ten": os.path.basename(f), "mb": round(n / 1e6, 1), "loai": loai_tep(f)})

    def _tai_len_tu_duong(self, nguon, ten, n):
        """1.2.21 (1h): nguồn là đường dẫn thật trên máy → cùng ổ với tai-len thì HARDLINK (0 byte thêm), khác ổ thì chép; thân request bỏ"""
        try:
            con = n
            while con > 0:                               # bỏ thân (nếu trình duyệt vẫn gửi)
                k = self.rfile.read(min(1 << 20, con))
                if not k:
                    break
                con -= len(k)
        except Exception:
            pass
        thu = os.path.join(D.TAI_LEN, time.strftime("%Y-%m-%d"))
        os.makedirs(thu, exist_ok=True)
        goc_, duoi = os.path.splitext(ten)
        f, i = os.path.join(thu, ten), 1
        while os.path.exists(f):
            i += 1
            f = os.path.join(thu, f"{goc_}-{i}{duoi}")
        cach = "chép"
        try:
            cung_o = (os.path.splitdrive(os.path.abspath(nguon))[0].lower() == os.path.splitdrive(os.path.abspath(thu))[0].lower()) if D.WIN \
                else os.stat(nguon).st_dev == os.stat(thu).st_dev
            if cung_o:
                try:
                    os.link(nguon, f); cach = "hardlink"
                except OSError:
                    shutil.copy2(nguon, f)
            else:
                shutil.copy2(nguon, f)
        except Exception as e:
            return self.loi(500, f"không lấy được file: {e}")
        return self.json_({"duong_dan": f, "ten": os.path.basename(f), "mb": round(os.path.getsize(f) / 1e6, 1), "loai": loai_tep(f), "cach": cach})


def _tu_sua_sau_mo():
    """1.2.19 (F5): mở Studio (nhất là ngay sau cập nhật) mà thiếu thư viện/ffmpeg bắt buộc và sửa được → tự chạy Bác sĩ sửa,
    không chờ người dùng bấm; trong lúc sửa, gửi việc bị chặn với lời rõ (xem route gui)."""
    for _ in range(60):
        time.sleep(5)
        kq = BS.get("kq")
        if kq:
            break
    else:
        return
    # 1.2.21: bỏ `nhan_giong` khỏi danh sách tự sửa lúc mở (Mac kiểm mlx_whisper trong khi lõi dùng faster-whisper → mỗi lần mở lại
    # `uv pip install` và chặn gửi việc) — mục đó chỉ sửa khi người dùng bấm "Tự sửa máy"
    can = [x for x in kq if x.get("ok") is False and x.get("sua_duoc") and x.get("bat_buoc") and x.get("ma") in ("ffmpeg", "uv", "venv", "goi", "kho_v3")]
    if can and not DONG_CO.trang_thai()["viec_chay"]:
        print("Bác sĩ: thiếu " + ", ".join(x["ten"] for x in can) + " → tự sửa", flush=True)
        bs_sua()


def _tu_chua_moi_truong():
    """1.2.12: chốt gốc .venv vào thư mục Python 3.12 cố định của uv + đổi lối tắt Desktop cũ sang bộ mở tự chữa.
    1.3: lập CHỈ MỤC KHO lõi mới (v3/kho) ngầm nếu máy chưa có (bản cập nhật có hiệu ứng mới) — không bắt video đầu tiên chờ 5–15 phút."""
    try:
        # 1.2.21 (1g): chỉ mục là kho.sqlite (hoặc danh-muc.jsonl bản cũ chưa nhập) — có một trong hai thì KHÔNG chạy lap.py ngầm
        ma = ("import sys,os;sys.path.insert(0,'v3');import chung;d=chung.duong('kho_chi_muc');"
              "co=any(os.path.isfile(os.path.join(d,f)) for f in ('kho.sqlite','danh-muc.jsonl'));"
              "co or __import__('runpy').run_path('v3/kho/lap.py',run_name='__main__');"
              "from dung.mau import bang;bang.dam_bao()")
        subprocess.Popen([D.py_skill(), "-c", ma],
                         cwd=D.SKILL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=D.env_con(),
                         creationflags=0x08000000 if os.name == "nt" else 0)
    except Exception:
        pass
    try:
        import sua_venv
        sua_venv.chua(cai_neu_thieu=False)
    except Exception:
        pass
    try:
        import mo
        mo.doi_loi_tat_cu()
    except Exception:
        pass


MAC_DINH_KHO = {"bac_it_dung": 0.08, "so_ung_vien": 8, "n_lich_su": 30, "thang_dem": 12, "lam_nong": True}
MAC_DINH_AI_TOI_DA_LUOT = 2     # v3.ai.toi_da_luot — số lần nhắc AI khi JSON hỏng (chung.MAC_DINH)
P_CAU_HINH = os.path.join(D.SKILL, "cau-hinh.json")


def cau_hinh_kho():
    """cau-hinh.json → v3.kho (A6: bac_it_dung, so_ung_vien, n_lich_su, thang_dem, lam_nong) + mặc định"""
    c = D.doc_json(P_CAU_HINH) or {}
    k = ((c.get("v3") or {}).get("kho") or {}) if isinstance(c.get("v3"), dict) else {}
    ra = dict(MAC_DINH_KHO)
    ra.update({x: y for x, y in k.items() if x in MAC_DINH_KHO})
    ai = ((c.get("v3") or {}).get("ai") or {}) if isinstance(c.get("v3"), dict) else {}
    try:
        ra["toi_da_luot"] = max(1, int(ai.get("toi_da_luot") or MAC_DINH_AI_TOI_DA_LUOT))
    except (TypeError, ValueError):
        ra["toi_da_luot"] = MAC_DINH_AI_TOI_DA_LUOT
    return ra


def luu_cau_hinh_kho(b):
    moi = {}
    if "bac_it_dung" in b:
        try:
            v = float(b["bac_it_dung"])
        except (TypeError, ValueError):
            raise ValueError("bac_it_dung phải là số 0–1")
        if not (0 <= v <= 1):
            raise ValueError("bac_it_dung phải trong 0–1")
        moi["bac_it_dung"] = v
    for k, lo, cao in (("so_ung_vien", 1, 50), ("n_lich_su", 1, 500), ("thang_dem", 1, 120)):
        if k in b:
            try:
                v = int(b[k])
            except (TypeError, ValueError):
                raise ValueError(f"{k} phải là số nguyên")
            if not (lo <= v <= cao):
                raise ValueError(f"{k} phải trong {lo}–{cao}")
            moi[k] = v
    if "lam_nong" in b:
        moi["lam_nong"] = bool(b["lam_nong"])
    luot = None
    if "toi_da_luot" in b:
        try:
            luot = int(b["toi_da_luot"])
        except (TypeError, ValueError):
            raise ValueError("toi_da_luot phải là số nguyên")
        if not (1 <= luot <= 10):
            raise ValueError("toi_da_luot phải trong 1–10")
    c = D.doc_json(P_CAU_HINH) or {}
    v3 = c.setdefault("v3", {}) if isinstance(c.get("v3"), dict) or "v3" not in c else c["v3"]
    if not isinstance(v3, dict):
        raise ValueError("cau-hinh.json mục v3 không phải đối tượng")
    kho = v3.setdefault("kho", {})
    if not isinstance(kho, dict):
        kho = v3["kho"] = {}
    kho.update(moi)
    if luot is not None:
        ai = v3.setdefault("ai", {})
        if not isinstance(ai, dict):
            ai = v3["ai"] = {}
        ai["toi_da_luot"] = luot
    D.ghi_json(P_CAU_HINH, c)
    return cau_hinh_kho()


def cong_kho():
    """cổng máy chủ kho v3 — cai_dat.cong_kho (mặc định 4789); app.js nhận qua /api/khoi-dau"""
    try:
        c = int(D.cai_dat().get("cong_kho") or 4789)
        return c if 1024 <= c <= 65535 else 4789
    except (TypeError, ValueError):
        return 4789


def _tat_kho_ban_cu(c):
    """Bản 1.2.20 không tắt máy chủ kho khi cập nhật, nên nó còn giữ cổng và chạy mã cũ. Bản mới luôn ghi server_thu-<cổng>.pid:
    có tiến trình server_thu.py đúng cổng mà không có pid sống trong tệp đó → bản cũ, tắt để bật bản mới."""
    try:
        pf = os.path.join(don_rac.du_lieu_v3(), "kho-chi-muc", f"server_thu-{c}.pid")
        try:
            with open(pf, encoding="utf-8") as f:
                pid = int((f.readline() or "0").strip() or 0)
        except (OSError, ValueError):
            pid = 0
        if pid and dong_co._pid_song(pid):
            return
        for p_, _, cmd in _pid_theo_lenh("server_thu.py", str(c)):
            if re.search(r"server_thu\.py\"?\s+" + str(c) + r"\b", cmd):
                _giet(p_)
    except Exception as e:
        print("không kiểm được máy chủ kho cũ:", e, flush=True)


_KHOA_THUMB = threading.BoundedSemaphore(3)
DUOI_ANH_THUMB = (".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".heic")


def anh_thu_nho(f):
    """1.2.21: ảnh thu nhỏ cho tệp vừa đưa vào form/ô chat (video lấy một khung, ảnh thu lại). Cache trong thư mục tạm (dọn rác nhóm a). Không tạo được → None."""
    import hashlib, tempfile
    d_ = f.lower()
    if not os.path.isfile(f) or not d_.endswith(DUOI_VIDEO + DUOI_ANH_THUMB):
        return None
    st = os.stat(f)
    thu = os.path.join(tempfile.gettempdir(), "tro-ly-edit-video", "thumb")
    os.makedirs(thu, exist_ok=True)
    ra = os.path.join(thu, hashlib.md5(f"{f}|{st.st_mtime_ns}|{st.st_size}".encode("utf-8", "replace")).hexdigest() + ".jpg")
    if os.path.isfile(ra) and os.path.getsize(ra) > 0:
        return ra
    ff = shutil.which("ffmpeg") or os.path.join(D.DATA, "ffmpeg", "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    tam = f"{ra}.{os.getpid()}.{threading.get_ident()}.tmp.jpg"
    with _KHOA_THUMB:
        for ss in (("1", "0") if d_.endswith(DUOI_VIDEO) else ("0",)):
            try:
                r = subprocess.run([ff, "-v", "error", "-y", "-nostdin", "-ss", ss, "-i", f, "-frames:v", "1", "-vf", "scale=320:-2", "-q:v", "5", tam],
                                   capture_output=True, timeout=25, creationflags=0x08000000 if os.name == "nt" else 0)
            except (OSError, subprocess.TimeoutExpired):
                continue
            if r.returncode == 0 and os.path.isfile(tam) and os.path.getsize(tam) > 0:
                os.replace(tam, ra)
                return ra
    try:
        os.remove(tam)
    except OSError:
        pass
    return None


def _tim_tai_video():
    """công cụ tải video đi kèm gói (tai-video-kenh nằm cạnh thư mục skill)"""
    for g in (os.path.join(os.path.dirname(D.SKILL), "tai-video-kenh"), os.path.expanduser("~/.claude/skills/tai-video-kenh")):
        p = os.path.join(g, "scripts", "taivideo.py")
        if os.path.isfile(p):
            return p
    return ""


def tai_video_mau(url):
    """1.2.21: link video mẫu (TikTok, Facebook, YouTube) → tải về thư mục tải lên, trả đường dẫn như tệp người dùng chọn"""
    url = str(url or "").strip()
    if not re.fullmatch(r"https?://\S{4,2000}", url):
        raise ValueError("Link phải bắt đầu bằng http:// hoặc https://")
    tool = _tim_tai_video()
    if not tool:
        raise ValueError("Bộ cài thiếu công cụ tải video. Tải video về máy rồi bấm Thêm video mẫu.")
    thu = os.path.join(D.TAI_LEN, time.strftime("%Y-%m-%d"), "mau-" + time.strftime("%H%M%S") + "-" + os.urandom(2).hex())
    os.makedirs(thu, exist_ok=True)
    try:
        r = subprocess.run([D.py_skill(), tool, url, "--out", thu], capture_output=True, timeout=600, env=D.env_con(),
                           creationflags=0x08000000 if os.name == "nt" else 0)
        chi_tiet = (r.stderr or r.stdout or b"").decode("utf-8", "replace").strip()[-160:]
    except subprocess.TimeoutExpired:
        shutil.rmtree(thu, ignore_errors=True)
        raise ValueError("Tải link quá 10 phút. Tải video về máy rồi bấm Thêm video mẫu.")
    vs = [os.path.join(g, f) for g, _, fs in os.walk(thu) for f in fs if f.lower().endswith(DUOI_VIDEO)]
    if not vs:
        shutil.rmtree(thu, ignore_errors=True)
        raise ValueError("Không tải được video từ link này. Tải video về máy rồi bấm Thêm video mẫu." + (f" ({chi_tiet})" if chi_tiet else ""))
    f = max(vs, key=os.path.getsize)
    return {"duong_dan": os.path.normpath(f), "ten": os.path.basename(f), "mb": round(os.path.getsize(f) / 1e6, 1)}


def _bat_kho_moi():
    """1.3: máy chủ KHO mới (v3/kho/server_thu.py, cổng cai_dat.cong_kho) — giao diện xem/nghe tài nguyên nhúng trong khung Kho.
    1.2.21: nhớ tiến trình (KHO_PROC) để tắt sạch / khởi động lại."""
    c = cong_kho()
    _tat_kho_ban_cu(c)
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{c}/api/kho/thong-ke", timeout=2).read()
        return                                    # đã chạy
    except Exception:
        pass
    try:
        KHO_PROC["proc"] = subprocess.Popen([D.py_skill(), os.path.join(D.SKILL, "v3", "kho", "server_thu.py"), str(c), "-q"], cwd=D.SKILL,
                                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=D.env_con(),
                                            creationflags=0x08000000 if os.name == "nt" else 0)
    except Exception as e:
        print("không bật được máy chủ kho:", e, flush=True)


def main():
    global DONG_CO
    DONG_CO = dong_co.DongCo()
    don_rac.DANG_CHAY = lambda: set(DONG_CO.chay)                        # 1.2.21 (1h): dọn rác biết việc nào đang chạy
    don_rac.DU_AN_CUA = dong_co._du_an_cua
    threading.Thread(target=_don_rac_dinh_ky, daemon=True).start()       # thay don_tai_len/don_du_lieu
    bs_kiem(ep=True)
    threading.Thread(target=tu_kiem_ban_moi, daemon=True).start()
    threading.Thread(target=_tu_chua_moi_truong, daemon=True).start()
    threading.Thread(target=_tu_sua_sau_mo, daemon=True).start()         # 1.2.19 (F5)
    threading.Thread(target=_bat_kho_moi, daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", CONG), XuLy)
    srv.daemon_threads = True
    print(f"Studio: http://127.0.0.1:{CONG}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:                                                             # 1.2.21: tắt bằng cách nào cũng không để tiến trình con mồ côi
        try:
            tat_sach("server dừng")
        except Exception:
            pass
        try:
            srv.server_close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
