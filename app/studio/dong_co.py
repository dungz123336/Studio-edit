# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Động cơ Claude của Studio — mỗi VIỆC là một cuộc trò chuyện Claude Code riêng (claude -p --resume),
gắn với một HỒ SƠ. Studio chỉ chuyển lời; mọi quyết định dựng do Claude làm theo skill + phiếu 12 bước.

Cần Claude Code đã đăng nhập. Chưa có thì Studio có nút "Đăng nhập Claude" (tự cài Claude Code nếu thiếu).
"""
import json, os, re, shutil, socket, subprocess, sys, threading, time

import bac_si
import du_lieu as D

CONG_CU = "Bash,Read,Write,Edit,Glob,Grep,Skill,TodoWrite"
LOI_MANG = re.compile(r"ENOTFOUND|ECONNRESET|ECONNREFUSED|ETIMEDOUT|EAI_AGAIN|Can.t reach|socket hang up|fetch failed|"
                      r"network|Connection error|overloaded|\b(502|503|504|529)\b", re.I)


def co_mang():
    try:
        socket.getaddrinfo("api.anthropic.com", 443)
        return True
    except OSError:
        return False


def gio_mo_lai(kq):
    """giờ mở lại lượt Claude từ thông báo hết lượt → epoch (None nếu không đọc được → Studio thử lại mỗi 20 phút).
    Dạng gặp: '…limit reached|1736272800' · '…resets 3pm' · 'resets 10:30am' · 'resets at 15:00'."""
    import datetime as _dt
    m = re.search(r"\|(\d{10})\b", kq or "")
    if m:
        return float(m.group(1))
    m = re.search(r"resets?\s*(?:at\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", kq or "", re.I)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), (m.group(3) or "").lower()
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if h > 23 or mi > 59:
        return None
    bay_gio = _dt.datetime.now()
    den = bay_gio.replace(hour=h, minute=mi, second=0, microsecond=0)
    if den <= bay_gio:
        den += _dt.timedelta(days=1)
    return den.timestamp()


CHU_VIET = re.compile(r"[àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]", re.I)

_CO_GON = {}


def _co_gon(exe):
    """1.2.15: cờ thu gọn ngữ cảnh (chỉ công cụ Studio, không MCP/plugin/skill khác) — CHỈ những cờ bản Claude Code trên máy này có
    (bản cũ gặp cờ lạ là báo lỗi, Studio đứng). Đọc `claude --help` một lần cho mỗi đường dẫn exe."""
    if exe not in _CO_GON:
        try:
            h = subprocess.run([exe, "--help"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
                               creationflags=0x08000000 if os.name == "nt" else 0).stdout
        except Exception:
            h = ""
        ra = []
        if "--tools " in h or "--tools <" in h:
            ra += ["--tools", CONG_CU]
        if "--strict-mcp-config" in h and "--mcp-config" in h:
            ra += ["--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}']
        if "--disable-slash-commands" in h:
            ra += ["--disable-slash-commands"]
        _CO_GON[exe] = ra
        _HO_TRO[exe] = {"max_turns": "--max-turns" in h}
    return list(_CO_GON[exe])


_HO_TRO = {}


def _co_tran(exe, cd):
    """1.2.21 (1a): TRẦN mỗi lượt chỉ còn số bước công cụ (cai_dat.toi_da_buoc, mặc định 0 = không giới hạn).
    Bỏ hẳn --max-budget-usd / tran_usd_luot. Chỉ thêm khi Claude Code có cờ đó."""
    _co_gon(exe)
    ht = _HO_TRO.get(exe) or {}
    try:
        buoc = int(cd.get("toi_da_buoc", 0) or 0)
    except (TypeError, ValueError):
        buoc = 0
    return ["--max-turns", str(buoc)] if ht.get("max_turns") and buoc > 0 else []


def _du_an_cua(vid):
    """thư mục dự án của việc (phiếu 1.x + mọi phiếu 2.0)"""
    ds = []
    try:
        p = D.doc_json(D.p_phieu(vid)) or {}
        if p.get("viec") == vid and p.get("du_an"):
            ds.append(p["du_an"])
    except Exception:
        pass
    try:
        for ph in D.ds_phieu2(vid):
            if ph.get("du_an"):
                ds.append(ph["du_an"])
    except Exception:
        pass
    return [d for i, d in enumerate(ds) if d and d not in ds[:i] and os.path.isdir(d)]


def _pid_song(pid):
    """tiến trình còn sống? 1.2.21: Windows đọc `tasklist /FO CSV` (bản cũ regex sai khi tên tiến trình có khoảng trắng → không giết được)"""
    try:
        pid = int(pid)
        if D.WIN:
            import csv, io
            r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=20, creationflags=D.KHONG_CUA_SO)
            for hang in csv.reader(io.StringIO(r.stdout or "")):
                if len(hang) >= 2 and hang[1].strip().isdigit() and int(hang[1]) == pid:
                    return True
            return False
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _la_tien_trinh_dung(pid):
    """1.2.19: PID trong .v3-*.json có thể đã bị hệ cấp cho tiến trình khác (sau khởi động lại) → chỉ giết khi dòng lệnh đúng là
    cầu nối dựng (cau_noi.py). Không hỏi được → None (giữ hành vi cũ)."""
    try:
        if D.WIN:
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"],
                               capture_output=True, text=True, timeout=20, creationflags=D.KHONG_CUA_SO)
        else:
            r = subprocess.run(["ps", "-o", "args=", "-p", str(int(pid))], capture_output=True, text=True, timeout=20)
        s = (r.stdout or "").strip()
        return ("cau_noi" in s or "alpha.py" in s) if s else None
    except Exception:
        return None


def _giet_cay(pid):
    if _la_tien_trinh_dung(pid) is False:
        return
    try:
        if D.WIN:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(int(pid))], capture_output=True, creationflags=D.KHONG_CUA_SO)
        else:
            import signal
            try:
                os.killpg(int(pid), signal.SIGKILL)
            except Exception:
                os.kill(int(pid), signal.SIGKILL)
    except Exception:
        pass


def _buoc_nang(vid):
    """[(tệp .v3-<buoc>.json, dict, du_an)] các bước máy nặng đang ghi 'chay' của việc"""
    ra = []
    for d in _du_an_cua(vid):
        try:
            for f in os.listdir(d):
                if f.startswith(".v3-") and f.endswith(".json"):
                    p = os.path.join(d, f)
                    st = D.doc_json(p) or {}
                    if isinstance(st, dict) and st.get("trang_thai") == "chay":
                        ra.append((p, st, d))
        except OSError:
            pass
    return ra


def _giet_nang(vid, ly_do):
    """1.2.19 (B2): giết tiến trình dựng/đọc tách rời của việc (Dừng / tắt Studio) và ghi trạng thái lỗi để lần sau không chờ mồ côi"""
    n = 0
    for p, st, d in _buoc_nang(vid):
        pid = st.get("pid")
        if pid and _pid_song(pid):
            _giet_cay(pid); n += 1
        try:
            D.ghi_json(p, dict(st, trang_thai="loi", loi=ly_do, luc=time.time()))
        except Exception:
            pass
    return n


def _nhat_ky_im(d):
    """giây kể từ dòng nhật ký / trạng thái mới nhất của dự án"""
    moc = 0.0
    for f in ("nhat-ky.txt",):
        try:
            moc = max(moc, os.path.getmtime(os.path.join(d, f)))
        except OSError:
            pass
    try:
        for f in os.listdir(d):
            if f.startswith(".v3-") and f.endswith(".json"):
                moc = max(moc, os.path.getmtime(os.path.join(d, f)))
    except OSError:
        pass
    return (time.time() - moc) if moc else 0.0


HUONG_DAN_V3 = """[STUDIO 1.3] Bạn là ĐẠO DIỄN dựng video, chạy NGẦM sau Studio (app trên máy người dùng). Người dùng chỉ thấy câu trả lời cuối của bạn.
Hồ sơ: `{ho_so}` (kênh “{kenh}”). Thư mục app: {skill} (đang ở đây). Python: `{py}` — LUÔN gọi đúng đường dẫn này.
Studio KHÔNG có gu: mọi lựa chọn hình ảnh (màu, font, bố cục, cách chữ hiện, đồ hoạ, nhạc, nhịp cắt, bìa) phải SINH RA TỪ video này
+ yêu cầu + hồ sơ kênh (gu, khoá màu/font, góp ý, bản sắc/Style Spec — có trong bản tóm tắt). Mỗi kênh một bản sắc; kênh đã có bản sắc thì giữ nhất quán.
Máy lo phần cơ học và luật đo được (đè mặt, vùng an toàn, đọc kịp, chồng chữ, dấu Việt, âm lượng, mật độ) — máy chặn/báo thì sửa đúng lỗi.
LUẬT: không đọc/sửa mã (.py) hay tài liệu của app; không đụng ~/.claude/skills; chỉ làm trong thư mục dự án của việc này; không kill tiến trình.
Giữ màu gốc video (không LUT/đen trắng) trừ khi người dùng yêu cầu. Không bịa số. Lớp riêng (`kieu:"py"`) viết trong <dự án>/lop-rieng/.
CÁC BƯỚC (lệnh dài đặt timeout 600000; in "VẪN ĐANG CHẠY" → chạy lại ĐÚNG lệnh đó):
1. MỘT lệnh: `"{py}" v2/st.py bat-dau <ten-ngan> --video "<clip người nói>" ["<clip 2>"…] [--phu "<quay màn hình/B-roll>"…] [--mau "<video mẫu>"] [--goi <phong cách người dùng chọn>] --ho-so {ho_so} --yeu-cau "<lời người dùng>" && "{py}" v2/st.py nhanh doc`
   Nhiều clip người nói = MỘT video (máy nối). Clip không lời → --phu. Nó in BẢN TÓM TẮT (lời theo giây thành phẩm, mặt + vùng trống, hồ sơ/bản sắc, gói kho, QUYẾT ĐỊNH KÊNH) + TỪ ĐIỂN CÔNG CỤ.
2. MỞ (Read) HẾT: các bảng khung nó in (khung lấy theo lượng thay đổi; ô ghi giây gốc → giây thành phẩm), doc/kho-video.jpg, các BẢNG MẪU ĐỒ HOẠ (toàn bộ công cụ vẽ sẵn trông thế nào) và ảnh video mẫu nếu có.
   Cần nhìn kỹ đoạn nào → `"{py}" v2/st.py nhanh khung --tu <giây gốc> --den <giây gốc> [--fps N] [--o-lon]`; xem kỹ một mẫu → `"{py}" v2/st.py nhanh mau --id mau.<id>`; rồi MỞ ảnh nó in. Định đổi nền (tách người) → `"{py}" v2/st.py nhanh mat-na` rồi MỞ doc/mat-na.jpg.
3. QUYẾT ĐỊNH KÊNH — máy không còn số thẩm mỹ riêng; mọi mặc định (font, bảng màu, chữ, thẻ, phụ đề, anim, vị trí, né mặt, âm, nền mới, chuyển cảnh, bìa) nằm trong `quyet-dinh.json` của kênh (bản tóm tắt in nó). Tóm tắt báo "KÊNH CHƯA CÓ QUYẾT ĐỊNH" → Write `<dự án>/quyet-dinh-kenh.json` đúng khuôn tóm tắt chỉ TRƯỚC khi viết công thức (máy kiểm khuôn, lưu vào hồ sơ, dùng cho cả kênh về sau). Kênh đã có → giữ nhất quán; muốn đổi cho cả kênh thì Write lại tệp đó kèm `ly_do`.
   Máy báo `thieu_truong` (kèm đường dẫn trường, vd `lop[3].kieu_dang.co`) → bạn bổ sung: vào quyết định kênh (áp cho cả kênh) hoặc vào công thức (chỉ video này). Máy không tự điền.
4. TƯ DUY TRƯỚC, VIẾT SAU — ghi ngắn vào `y_do` của công thức, rồi mọi lớp phải bám y_do đó:
   • Video về gì, người xem là ai, cần NHỚ điều gì; cảm xúc và nhịp của người nói.
   • Ngôn ngữ hình ảnh của VIDEO NÀY (màu, font, cách chữ hiện, kiểu đồ hoạ chủ đạo, nhạc có/không và mức, nhịp cắt) — do bạn quyết từ nội dung + bối cảnh
     trong khung + quyết định/góp ý của kênh. Không có mức "đúng" sẵn: nhiều hay ít đồ hoạ, sôi động hay tĩnh, đều được nếu mỗi lớp có lý do nằm trong lời.
   • Hai câu hỏi cho từng chỗ: "người xem cần THẤY gì mà chỉ đang nghe?" (→ chọn công cụ đúng: mẫu đồ hoạ, hình, nền mới, camera, chuyển cảnh, lớp phủ…) và "bỏ lớp này đi thì mất gì?" (→ bỏ lớp thừa). Toàn bộ bộ công cụ đều được dùng; bản sắc kênh là màu/font/nhịp/cách chữ hiện, KHÔNG giới hạn loại công cụ.
   • Bìa: các phương án trong `bia.phuong_an` (số phương án do bạn quyết — máy vẽ đúng bấy nhiêu bìa), khác nhau về BỐ CỤC và Ý — hướng nào do bạn rút từ nội dung và kênh. Khung mặt cho bìa: MỞ `doc/bia-ung-vien.jpg` (máy đưa ~30 khung rải đều kèm số đo nét / miệng há / mắt mở / lặng) và tự chọn `khung_t` bằng mắt cho từng bìa — khung nào biểu cảm, mắt mở, miệng không há dở là việc của bạn, không phải của máy; cần thêm khung quanh một giây thì `nhanh khung --tu --den --fps 10`. Thiếu thiết kế bìa → máy báo lỗi, không tự vẽ bìa thay bạn.
   Rồi Write `<dự án>/cong-thuc.json` MỘT lần, đúng từ điển. Trường bạn BỎ TRỐNG (cỡ, màu, vị trí, anim, phụ đề, nhạc) máy điền theo thứ tự lớp → bài học/Style Spec đang bật → quyết định kênh; không có ở đâu → lỗi `thieu_truong` cho bạn. Font, kiểu chữ, cách chữ hiện trong bản sắc (kể cả viết tay, serif, giải mã) là LỰA CHỌN CỦA KÊNH — dùng đúng, không tự thay bằng font "dễ đọc"; chỉ đổi khi người dùng yêu cầu hoặc font thiếu dấu tiếng Việt. Font không có trong kho: ghi TÊN HỌ (Google Fonts, vd "Montserrat", "Playfair Display") — máy tự tải và dùng; KHÔNG BAO GIỜ bảo người dùng tải/cài font hay dừng việc vì font. Bài học có DÒNG THỜI GIAN MẪU: đó là nhịp, thứ tự lớp, cách bố trí thật của mẫu (cái gì hiện lúc nào, ở đâu, trước/sau cái gì) — đọc nó để quyết TRÌNH TỰ cho video này theo lời nói thật, không lặp một kiểu khối cho mọi câu. Lớp SAU NGƯỜI: `sau_nguoi:true` cho bất kỳ lớp nào (chữ sau đầu, thẻ sau vai) — dòng thời gian mẫu ghi "nằm SAU người" khi mẫu làm vậy. Chiều sâu/3D là công cụ sẵn có khi nội dung cần: rot_x/rot_y/flip/tilt cho MỌI lớp (chữ, khối, thẻ, ảnh, B-roll), chữ nổi khối `noi_3d`, chuyển cảnh lật/lập phương (mau.lat-3d, mau.lap-phuong), và lớp `web` có three.js (viết THREE) cho vật thể, thẻ/ảnh/B-roll bay trong không gian, camera 3D. Video phụ / B-roll / thư mục tư liệu: máy đã quét (mục B-ROLL trong tóm tắt — mở ảnh bảng khung để chọn đúng giây); thư mục người dùng kết nối có video mà chưa có trong tóm tắt → `nhanh broll "<thư mục>"` rồi mở ảnh. Ghép B-roll vào A-roll, montage nhiều B-roll, tiếng B-roll: xem từ điển (lớp video).
5. `"{py}" v2/st.py nhanh tron` → máy kiểm khuôn (hợp đồng công thức + quyết định kênh), chuẩn hoá, kiểm luật đo được, dựng, in PHIẾU TỰ SOI (chỉ là SỐ ĐO để bạn đối chiếu với y_do, máy không phán) + vẽ bìa. "TRỌN: DỪNG" → sửa đúng lỗi in ra (kể cả `thieu_truong`), chạy lại.
{buoc_nhin}
7. `"{py}" v2/st.py nhanh giao --bia <số bìa bạn chọn>` → máy chép video + bìa ra thư mục giao và báo Studio.
Trả lời người dùng bằng tiếng Việt (xưng "mình", gọi "bạn"): video dài bao nhiêu; MỘT dòng «Mình chọn: màu … vì …, font …, nhịp …, nhạc …» để bạn sửa được; thời gian. Không hỏi lại.
Cần người dùng quyết thì cuối câu trả lời ghi `[HỎI] <câu hỏi>` + các dòng `- <lựa chọn>` rồi dừng.
Người dùng nhắn SỬA sau khi giao ("chữ to hơn", "bỏ nhạc", "giây 12 thêm…") → sửa cong-thuc.json của dự án vừa làm → `nhanh tron` → nhìn → `nhanh giao` (máy chỉ dựng lại phần đổi).
Góp ý cho CẢ KÊNH về sau ("lần sau phụ đề để giữa", "đừng dùng chữ viết tay", "bỏ nhạc") → sửa `quyet-dinh.json` của kênh qua `"{py}" v2/st.py gop-y "<câu của họ>"` (hoàn tác được) — không sửa mã.
"""
BUOC_NHIN_KY = """6. MỞ (Read) `dung/xem-lai.jpg` (8 khung thành phẩm) + các bìa nó in, ĐỌC phiếu tự soi. Soi: chữ đúng chỗ, đọc được, không che mặt, nhịp hợp lời, có đúng ý đồ đã ghi không, các bìa khác nhau thật.
   Chưa ưng → sửa cong-thuc.json → `nhanh tron` lại. Ưng → bước 7."""
BUOC_NHIN_NHANH = """6. ⚡ LÀM NHANH: không cần mở ảnh — "TRỌN: XEM" là bạn chọn bìa theo phiếu tự soi rồi giao (chỉ sửa khi máy chặn)."""


def _v3_bat():
    """1.3: lõi cũ đã gỡ — luôn là lõi mới (giữ hàm cho mã gọi cũ)"""
    return True


HOI = re.compile(r"^\s*\[H[ỎO]I\]\s*(.+)$", re.M | re.I)


def _dich_loi_cli(s):
    """1.2.19 (F4): lỗi stderr của Claude Code → một câu tiếng Việt chỉ việc cần làm"""
    s = s or ""
    if re.search(r"unknown (option|argument)|unrecognized|error: unknown", s, re.I):
        return "Claude Code trên máy quá cũ (không hiểu tham số mới) — mở PowerShell chạy `npm i -g @anthropic-ai/claude-code` rồi mở lại Studio."
    if re.search(r"not logged in|please (run )?/login|authentication|invalid api key|401", s, re.I):
        return "Claude Code chưa đăng nhập — bấm “Đăng nhập Claude” ở bảng Máy."
    if re.search(r"ENOENT|not recognized|is not recognized as", s, re.I):
        return "Không gọi được Claude Code — bấm “Tự sửa tất cả” ở bảng Máy để cài lại."
    if re.search(r"ENOTFOUND|EAI_AGAIN|ECONNRESET|ETIMEDOUT|fetch failed", s, re.I):
        return "Mất mạng khi gọi Claude — kiểm tra kết nối rồi gửi “tiếp tục”."
    if re.search(r"max turns|maximum number of turns", s, re.I):
        return "Lượt này chạm trần số bước (cài đặt toi_da_buoc) — gửi “tiếp tục” để làm nốt."
    return ""


def tach_hoi(chu):
    """'… [HỎI] câu hỏi\n- a\n- b' → (phần trước, câu hỏi, [lựa chọn]) ; không có khối hỏi → (chu, None, [])"""
    m = HOI.search(chu)
    if not m:
        return chu, None, []
    truoc, sau = chu[:m.start()].rstrip(), chu[m.start():]
    dong = sau.strip().splitlines()
    cau, lc = m.group(1).strip(), []
    for d in dong[1:]:
        x = re.match(r"^\s*(?:[-*•]|\d+[.)])\s+(.+)$", d)
        if x and len(lc) < 12:                      # 1.2.21: số lựa chọn do AI quyết (bản cũ cắt ở 4)
            lc.append(x.group(1).strip()[:120])
        elif d.strip() and not x:
            cau += " " + d.strip() if not lc else ""
    return truoc, cau, lc


def _tom_tat(ten, vao):
    vao = vao or {}
    if ten == "Bash":
        return vao.get("description") or (vao.get("command") or "")[:100]
    if ten in ("Read", "Write", "Edit"):
        return {"Read": "Đọc", "Write": "Ghi", "Edit": "Sửa"}[ten] + " " + os.path.basename(vao.get("file_path") or "")
    if ten == "Skill":
        return "Dùng skill " + str(vao.get("skill") or vao.get("name") or "")
    if ten in ("Glob", "Grep"):
        return "Tìm " + str(vao.get("pattern", ""))
    if ten == "TodoWrite":
        return None
    return ten


NANG = re.compile(r"File video người dùng vừa thả|PHONG CÁCH NHANH|Học từ các video sau|File GIỌNG NÓI|"
                  r"\b(dựng|edit|cắt|render|xuất video|làm video|ảnh bìa|thumbnail|học kênh|học video|làm tiếp)\b", re.I)


# ---------------------------------------------------------------- đo tải máy (không cần thư viện ngoài)
class TaiMay:
    def __init__(self):
        self._cpu_truoc = None

    def cpu(self):
        """% CPU đang dùng (0–100), None nếu không đo được"""
        try:
            if D.WIN:
                import ctypes
                from ctypes import wintypes
                ft = [wintypes.FILETIME() for _ in range(3)]
                ctypes.windll.kernel32.GetSystemTimes(*[ctypes.byref(f) for f in ft])
                v = [(f.dwHighDateTime << 32) | f.dwLowDateTime for f in ft]          # rảnh, nhân, người dùng
                if self._cpu_truoc is None:
                    self._cpu_truoc = v
                    time.sleep(0.4)
                    return self.cpu()
                r, k, u = (a - b for a, b in zip(v, self._cpu_truoc))
                self._cpu_truoc = v
                tong = k + u
                return max(0.0, min(100.0, 100.0 * (tong - r) / tong)) if tong else None
            return min(100.0, 100.0 * os.getloadavg()[0] / (os.cpu_count() or 1))
        except Exception:
            return None

    def ram_trong_gb(self):
        try:
            if D.WIN:
                import ctypes

                class MS(ctypes.Structure):
                    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                                ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                                ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                                ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
                m = MS(); m.dwLength = ctypes.sizeof(MS)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
                return m.ullAvailPhys / 1e9, m.ullTotalPhys / 1e9
            out = subprocess.run(["vm_stat"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
            m_ = re.search(r"page size of (\d+) bytes", out)    # 1.2.13: Apple Silicon = 16384
            trang = int(m_.group(1)) if m_ else 4096
            free = sum(int(x) for x in re.findall(r"Pages (?:free|inactive|speculative):\s+(\d+)", out)) * trang
            tong = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip() or 0)
            return free / 1e9, tong / 1e9
        except Exception:
            return None, None

    def toi_da_nang(self):
        """số việc NẶNG (dựng/học video) được chạy cùng lúc theo sức máy — cài đặt 'song_song' đè được"""
        cd = D.cai_dat()
        if str(cd.get("song_song", "")).isdigit() and int(cd["song_song"]) > 0:
            return int(cd["song_song"])                 # 1.2.21: số bất kỳ ≥ 1, không còn trần 4
        _, tong = self.ram_trong_gb()
        luong = os.cpu_count() or 2
        # 1.2.21 (1a): tự động = max(1, min(luồng // 2, RAM GB // 6)) — phần máy nặng đã xếp lượt qua v2/may_nang, mỗi việc
        # thêm chủ yếu là một phiên AI nghĩ (~0,3 GB) + một chỗ dựng khi máy đủ sức
        return max(1, min(luong // 2, int((tong or 8) // 6)))

    def qua_tai(self):
        """True khi KHÔNG nên mở thêm việc nặng: RAM trống < 2,5 GB. (CPU bận không chặn nữa — phần nặng đã xếp lượt
        qua chỗ nặng của máy, việc mới vẫn được bắt đầu phần AI nghĩ.)"""
        trong, _ = self.ram_trong_gb()
        if trong is None:
            return False
        # 1.3: máy chỉ có 1 CHỖ NẶNG (≤8 luồng / <16 GB) → phần dựng vẫn chạy từng cái một; mở thêm việc chỉ thêm một phiên AI
        # NGHĨ (~0,3 GB) chờ lượt dựng → chỉ cần 0,5 GB trống. Máy nhiều chỗ nặng (dựng chồng nhau thật) mới cần 2,5 GB.
        try:
            sys.path.insert(0, os.path.join(D.SKILL, "v2"))
            import may_nang
            cho = may_nang.so_cho()
        except Exception:
            cho = 2
        return trong < (0.5 if cho <= 1 else 2.5)


class DongCo:
    """Nhiều VIỆC chạy SONG SONG — mỗi việc một phiên Claude Code riêng.
    - Câu hỏi / trò chuyện (việc nhẹ): chạy ngay, không chờ ai.
    - Dựng / học video (việc nặng): chạy song song tới sức máy (toi_da_nang); máy quá tải thì chờ chỗ trống.
    - Trong CÙNG một việc: tin nhắn chạy nối tiếp (một phiên Claude không chạy hai lượt cùng lúc)."""

    def __init__(self):
        self.khoa = threading.RLock()
        self.chay = {}            # vid → {"proc", "bat_dau", "bi_dung", "loi_mang", "nang"}
        self.cho_viec = {}        # vid → [job…] tin nhắn đến khi việc đó đang chạy
        self.cho_nang = []        # job nặng chờ máy rảnh
        self.tai = TaiMay()
        self.exe = None
        self.da_kiem = False
        self.ly_do = "đang kiểm tra Claude Code…"
        threading.Thread(target=self._kiem_dinh_ky, daemon=True).start()
        threading.Thread(target=self._dieu_phoi, daemon=True).start()
        threading.Thread(target=self._canh_viec, daemon=True).start()

    # ── 1.3: CANH VIỆC — báo ngay trong khung chat, không cần ai ngồi canh
    DUNG_IM_PHUT = 15
    TREO_PHUT = 45            # 1.2.19: bước máy nặng không có tiến độ lâu hơn → coi là treo (ffmpeg 4K máy yếu có thể im 20-30 phút)
    CLAUDE_IM_PHUT = 45       # 1.2.19: Claude im (không máy nặng) lâu hơn → ngắt lượt

    def _canh_viec(self):
        """(1) lúc Studio bật: việc đang làm dở mà Studio tắt giữa chừng (mất điện, tắt máy, tắt app) → ghi tin báo BỊ NGẮT
        để người dùng biết gửi "tiếp tục"; (2) mỗi phút: việc đang chạy mà không có hoạt động mới > 15 phút → cảnh báo ĐỨNG IM
        (thường là một tiến trình dựng treo giữ chỗ máy, chặn cả hàng chờ) kèm cách xử lý. Chỉ BÁO — không tự làm gì thay người dùng."""
        time.sleep(5)
        try:
            for tom in D.ds_viec():
                if tom["id"] in self.chay:
                    continue
                v = D.doc_viec(tom["id"])
                cc = v.get("cho_chu")
                if isinstance(cc, dict) and cc.get("chu") and not v.get("dang_lam"):
                    # 1.2.19 (B1): việc còn xếp hàng lúc Studio tắt → nối lại hàng chờ (đủ lời gốc + tệp), không mất yêu cầu
                    with self.khoa:
                        self.cho_nang.append({"viec": v["id"], "chu": cc["chu"], "nang": True})
                    D.them_tin(v["id"], "he_thong", "Studio vừa mở lại — việc này vẫn trong hàng chờ, tự chạy khi máy có chỗ (yêu cầu và tệp đã lưu).")
                    continue
                if not v.get("dang_lam"):
                    continue
                n_giet = _giet_nang(v["id"], "ngắt khi Studio tắt")           # 1.2.19 (B2): tiến trình dựng mồ côi → dọn + ghi lỗi
                luc = time.strftime("%H:%M %d/%m", time.localtime(float(v.get("cap_nhat") or 0)))
                D.them_tin(v["id"], "he_thong", f"⚠ Việc này BỊ NGẮT giữa chừng (Studio tắt lúc {luc}). Phần đã làm vẫn còn — "
                                                "gửi “tiếp tục” để Claude làm nốt từ chỗ dừng." + (f" (đã dọn {n_giet} tiến trình dựng dở)" if n_giet else ""))
                D.sua_viec(v["id"], lambda x: x.__setitem__("dang_lam", False))
        except Exception:
            pass
        da_bao = {}
        while True:
            time.sleep(60)
            try:
                with self.khoa:
                    ds = list(self.chay.items())
                for vid, s in ds:
                    try:
                        v = D.doc_viec(vid)
                    except KeyError:
                        continue
                    if s.get("loi_mang") or s.get("cho_luot"):
                        continue                                        # đang chờ mạng / chờ lượt: không phải treo
                    moc = max(float(s.get("hoat_dong") or 0), float(s.get("bat_dau") or 0))
                    im = (time.time() - moc) / 60
                    if im < self.DUNG_IM_PHUT:
                        continue
                    # 1.2.19 (B3): WATCHDOG — bước máy nặng (dựng/đọc/tách người) còn 'chay' nhưng nhật ký im > TREO_PHUT → giết, ghi lỗi;
                    # Claude (đang chờ lệnh đó) sẽ thấy LỖI và chạy lại / Studio tự nhắc. Chỉ tin khi không ai còn hoạt động.
                    nang = _buoc_nang(vid)
                    treo = [(p, st, d) for p, st, d in nang if _nhat_ky_im(d) > self.TREO_PHUT * 60]
                    if treo:
                        for p, st, d in treo:
                            if st.get("pid") and _pid_song(st["pid"]):
                                _giet_cay(st["pid"])
                            D.ghi_json(p, dict(st, trang_thai="loi", loi=f"treo: không có tiến độ {self.TREO_PHUT} phút — Studio đã tắt tiến trình này", luc=time.time()))
                        s["hoat_dong"] = time.time()
                        D.them_tin(vid, "he_thong", f"⚠ Một bước dựng bị TREO (không có tiến độ {self.TREO_PHUT} phút) — Studio đã tắt tiến trình đó. "
                                                    "Claude sẽ chạy lại bước này (phần đã làm vẫn giữ, không làm lại từ đầu).")
                        continue
                    if nang:
                        continue                                        # máy đang dựng và còn tiến độ → không phải treo
                    if im >= self.CLAUDE_IM_PHUT and s.get("proc") is not None and s["proc"].poll() is None:
                        # Claude không trả lời gì > 45 phút và máy không dựng → coi là kẹt → tắt lượt; _chay_viec tự nhắc làm tiếp
                        _giet_cay(s["proc"].pid)
                        s["hoat_dong"] = time.time()
                        D.them_tin(vid, "he_thong", f"⚠ Claude không có hoạt động {int(im)} phút — Studio đã ngắt lượt này và sẽ nhắc làm tiếp (phần đã làm vẫn giữ).")
                        continue
                    if da_bao.get(vid) != int(moc):
                        da_bao[vid] = int(moc)
                        cho = len(self.cho_nang)
                        D.them_tin(vid, "he_thong", f"⚠ Việc này ĐỨNG IM {int(im)} phút (không có bước mới)"
                                                    + (f" và đang chặn {cho} video trong hàng chờ" if cho else "")
                                                    + ". Nếu không tự chạy tiếp, bấm Dừng rồi gửi “tiếp tục” — phần đã làm vẫn giữ.")
            except Exception:
                pass

    # ── tương thích chỗ cũ dùng 1 việc
    @property
    def viec_chay(self):
        with self.khoa:
            return next(iter(self.chay), None)

    def _kiem(self):
        exe = bac_si.tim_claude()
        if not exe:
            self.exe, self.ly_do, self.da_kiem = None, "máy chưa có Claude Code", True
            return
        try:
            r = subprocess.run([exe, "auth", "status"], capture_output=True, timeout=30, creationflags=D.KHONG_CUA_SO)
            dn = json.loads(r.stdout.decode("utf-8", "replace") or "{}").get("loggedIn")
        except Exception as e:
            dn, self.ly_do = False, f"không gọi được Claude Code ({e})"
        self.exe = exe if dn else None
        if dn:
            self.ly_do = ""
        elif not self.ly_do.startswith("không gọi"):
            self.ly_do = "Claude Code chưa đăng nhập"
        self.da_kiem = True

    def _kiem_dinh_ky(self):
        while True:
            self._kiem()
            time.sleep(120 if self.exe else 15)

    def trang_thai(self):
        with self.khoa:
            dang = {v: {"bat_dau": s["bat_dau"], "nang": s["nang"]} for v, s in self.chay.items()
                    if s.get("proc") is None or s["proc"].poll() is None}
            cho = [j["viec"] for j in self.cho_nang] + [v for v, ds in self.cho_viec.items() if ds]
        dau = next(iter(dang), None)
        return {"san_sang": bool(self.exe), "da_kiem": self.da_kiem, "ly_do": self.ly_do,
                "viec_chay": dau, "bat_dau": dang[dau]["bat_dau"] if dau else 0,
                "dang_chay": dang, "hang_doi": cho, "toi_da_nang": self.tai.toi_da_nang()}

    def gui(self, vid, chu, nang=None):
        # CỔNG GÁC: gói nguyên vẹn + bản quyền hợp lệ mới cho chạy Claude (chặn ngay ở chat, không chỉ ở bước dựng)
        try:
            import ban_quyen
            ok, loai, tb = ban_quyen.gac()
        except Exception as e:
            ok, loai, tb = False, "loi", f"không kiểm được bản quyền ({type(e).__name__})"
        if not ok:
            if loai == "toan-ven":
                raise RuntimeError("Bộ cài đã bị thay đổi — cài lại Studio từ link chính chủ trong thư giao hàng. " + tb)
            raise RuntimeError("Chưa kích hoạt bản quyền — nhập mã trong thư giao hàng ở bảng “Máy, bản quyền” "
                               "(góc dưới bên trái) rồi thử lại. " + tb)
        if not self.exe:
            raise RuntimeError(self.ly_do or "Claude Code chưa sẵn sàng")
        job = {"viec": vid, "chu": chu, "nang": bool(NANG.search(chu)) if nang is None else nang}
        if job["nang"]:
            try:                                        # 1.2.19 (B1): LỜI GỐC đầy đủ (kèm đường dẫn tệp) lưu vào việc → "tiếp tục" sau khi Studio
                D.sua_viec(vid, lambda x: x.__setitem__("loi_goc", chu))   # tắt/mở lại vẫn biết việc là gì (yêu cầu nặng mới nhất)
            except Exception:
                pass
        with self.khoa:
            if vid in self.chay:
                self.cho_viec.setdefault(vid, []).append(job)
                D.them_tin(vid, "he_thong", "Đã nhận — Claude làm xong lượt đang chạy của việc này sẽ đọc tin này ngay.")
                return
            if job["nang"] and not self._con_cho_nang():
                self.cho_nang.append(job)
                try:                                    # 1.2.19 (B1): hàng chờ ghi ĐĨA — Studio tắt/mở lại vẫn chạy tiếp, không mất yêu cầu
                    D.sua_viec(vid, lambda x: x.__setitem__("cho_chu", {"chu": chu, "nang": True, "luc": time.time()}))
                except Exception:
                    pass
                D.them_tin(vid, "he_thong", f"Máy đang dựng {self._so_nang()} video (tối đa {self.tai.toi_da_nang()} cùng lúc với máy này)"
                                            " — việc này tự chạy khi có chỗ trống. Câu hỏi ở việc khác vẫn trả lời bình thường.")
                return
            self._bat(job)

    def _so_nang(self):
        return sum(1 for s in self.chay.values() if s["nang"] and not s.get("cho_luot"))   # 1.2.19: đang chờ lượt/mạng → nhả chỗ

    def _con_cho_nang(self):
        return self._so_nang() < self.tai.toi_da_nang() and not (self._so_nang() and self.tai.qua_tai())

    def _bat(self, job):
        self.chay[job["viec"]] = {"proc": None, "bat_dau": time.time(), "bi_dung": False, "loi_mang": False, "nang": job["nang"], "hoat_dong": time.time()}
        try:
            D.sua_viec(job["viec"], lambda x: (x.__setitem__("dang_lam", True), x.pop("cho_chu", None)))   # 1.3: dấu "đang làm" — Studio tắt giữa chừng thì còn dấu
        except Exception:
            pass
        threading.Thread(target=self._chay_viec, args=(job,), daemon=True).start()

    def _dieu_phoi(self):
        """mỗi 3 giây: việc nặng đang chờ → chạy khi máy có chỗ"""
        while True:
            time.sleep(3)
            with self.khoa:
                while self.cho_nang and self._con_cho_nang() and self.exe:
                    job = self.cho_nang.pop(0)
                    if job["viec"] in self.chay:
                        self.cho_viec.setdefault(job["viec"], []).append(job)
                        continue
                    D.them_tin(job["viec"], "he_thong", "Máy đã có chỗ — bắt đầu làm việc này.")
                    self._bat(job)

    def dung(self, vid=None):
        with self.khoa:
            bo = [j for j in self.cho_nang if not (vid and j["viec"] != vid)]      # việc rời hàng chờ
            self.cho_nang = [j for j in self.cho_nang if vid and j["viec"] != vid]
            if vid:
                self.cho_viec.pop(vid, None)
                for j in bo:                                                     # 1.2.19: huỷ thật → xoá lời chờ trên đĩa (không tự sống lại khi mở Studio)
                    try:
                        D.sua_viec(j["viec"], lambda x: x.pop("cho_chu", None))
                    except Exception:
                        pass
            else:
                self.cho_viec.clear()
            ds = [vid] if vid else list(self.chay)
            da = False
            for v in ds:
                s = self.chay.get(v)
                if s:
                    s["bi_dung"] = True                 # 1.2.19: cả việc đang chờ lượt / chờ mạng / chờ chỗ (chưa có proc) cũng dừng được
                p = s and s.get("proc")
                if not p or p.poll() is not None:
                    continue
                if D.WIN:
                    subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True, creationflags=D.KHONG_CUA_SO)
                else:
                    try:                                    # 1.2.13: giết CẢ NHÓM (ffmpeg / st.py con) — không thì vẫn giữ chỗ nặng
                        import signal
                        os.killpg(p.pid, signal.SIGKILL)
                    except Exception:
                        p.kill()
                n_giet = _giet_nang(v, "người dùng bấm Dừng")      # 1.2.19 (B2): giết cả tiến trình dựng tách rời (trước đây sống mồ côi)
                D.them_tin(v, "he_thong", "Đã dừng Claude." + (f" Đã tắt {n_giet} tiến trình dựng đang chạy." if n_giet else ""))
                da = True
            if not vid:                                                  # tắt Studio: dọn mọi tiến trình nặng của việc đang chờ chỗ
                for j in bo:
                    _giet_nang(j["viec"], "ngắt khi Studio tắt")
        return da

    def dung_ho_so(self, ho_so):
        """lưu trữ hồ sơ → bỏ việc đang chờ và dừng việc đang chạy của hồ sơ đó"""
        cua = {v["id"] for v in D.ds_viec(ho_so)}
        for v in list(self.chay) + [j["viec"] for j in self.cho_nang]:
            if v in cua:
                self.dung(v)

    def _con_do(self, vid, st):
        """Lượt vừa kết thúc mà việc dựng CHƯA xong (Claude dừng giữa chừng, không hỏi gì) → nên tự nhắc làm tiếp."""
        if st["bi_dung"]:
            return False
        try:
            v = D.doc_viec(vid)
        except Exception:
            return False
        if v.get("cho_tra_loi"):
            return False
        cuoi = next((t for t in reversed(v["tin"]) if t["vai"] in ("claude", "hoi", "nguoi_dung", "video", "loi")), None)
        if not cuoi or cuoi["vai"] != "claude" or cuoi["noi_dung"].rstrip().endswith("?"):
            return False
        p = D.doc_json(D.p_phieu(vid)) or {}
        do_dang = p.get("loai") == "dung" and p.get("viec") == vid and "11" not in (p.get("buoc") or {})
        ds2 = D.ds_phieu2(vid)
        if ds2 and not ds2[-1].get("dong") and "7.1" not in (ds2[-1].get("buoc") or {}):
            do_dang = True
        if ds2 and ds2[-1].get("dong"):
            return False                                  # 1.2.19: video đã GIAO → không nhắc nữa (trước: câu "xong mình…" bị coi là dở)
        hen = re.search(r"đang (dựng|cắt|chạy|render|xuất)|chờ .{0,40}xong|mình sẽ (tự )?(chấm|giao|làm tiếp)|chạy nền",
                        cuoi["noi_dung"], re.I)
        return bool(do_dang or hen)

    def _chay_viec(self, job):
        vid = job["viec"]
        st = self.chay[vid]
        try:
            while True:
                chu, nhac = job["chu"], 0
                while True:
                    for lan in range(3):   # lỗi làm mới đăng nhập là tạm thời (app Claude desktop dùng chung token)
                        if not self._lam(vid, chu, st, im_loi_tam=lan < 2):
                            break
                        D.them_tin(vid, "he_thong", "Claude Code đang làm mới đăng nhập — tự thử lại sau 20 giây…")
                        time.sleep(20 + 7 * lan)
                    if st.get("het_luot") and st.get("so_cho_luot", 0) < 18 and not st["bi_dung"]:
                        # 1.2.12: HẾT LƯỢT Claude (giới hạn theo gói) → tự chờ tới giờ mở lại lượt rồi làm tiếp, khách không phải nhắn
                        st["het_luot"] = False
                        st["so_cho_luot"] = st.get("so_cho_luot", 0) + 1
                        den = st.pop("het_luot_den", None) or (time.time() + 20 * 60)
                        den = min(den + 60, time.time() + 6 * 3600)
                        D.them_tin(vid, "he_thong", "Tài khoản Claude tạm hết lượt — Studio tự chờ tới khoảng "
                                   + time.strftime("%H:%M", time.localtime(den)) + " rồi làm tiếp (không cần gõ gì, việc dở vẫn giữ nguyên).")
                        st["cho_luot"] = True                       # 1.2.19 (B2): nhả chỗ nặng cho việc khác trong lúc chờ lượt
                        while time.time() < den and not st["bi_dung"]:
                            time.sleep(30)
                        t_cho = time.time()
                        while not st["bi_dung"] and not self._con_cho_nang():   # có lượt lại → đợi máy có chỗ rồi mới tiếp
                            time.sleep(10)
                            if time.time() - t_cho > 3600:                   # 1.2.19: không im lặng vô hạn — báo mỗi giờ
                                D.them_tin(vid, "he_thong", "Đã có lượt Claude nhưng máy vẫn đầy (RAM/việc khác) — vẫn chờ chỗ; bấm Dừng nếu muốn huỷ.")
                                t_cho = time.time()
                        st["cho_luot"] = False
                        if st["bi_dung"]:
                            break
                        chu = ("[STUDIO] Lượt trước dừng vì tài khoản Claude tạm hết lượt; giờ đã có lượt lại: kiểm tra việc đang dở "
                               "(file đầu ra, phiếu) rồi làm tiếp từ đúng chỗ đó tới khi giao. Không làm lại phần đã xong.")
                        continue
                    if st["loi_mang"] and nhac < 6:
                        nhac += 1
                        st["loi_mang"] = False
                        D.them_tin(vid, "he_thong", "Mất kết nối tới Claude — Studio tự làm tiếp khi có mạng lại (không cần gõ gì).")
                        cho = 0
                        st["cho_luot"] = True                       # 1.2.19: chờ mạng cũng nhả chỗ nặng, và không bị coi là ĐỨNG IM
                        while not co_mang() and cho < 4 * 3600 and not st["bi_dung"]:
                            time.sleep(15); cho += 15
                        st["cho_luot"] = False
                        if not st["bi_dung"] and not co_mang():
                            D.them_tin(vid, "he_thong", "Mất mạng quá 4 giờ — Studio ngừng chờ. Khi có mạng, gửi “tiếp tục” là Claude làm nốt (phần đã làm vẫn giữ).")
                        if st["bi_dung"] or not co_mang():
                            break
                        time.sleep(5)
                        chu = ("[STUDIO] Mạng vừa bị ngắt giữa chừng nên lượt trước dừng. Giờ đã có mạng lại: kiểm tra việc đang dở "
                               "(file đầu ra, phiếu) rồi làm tiếp từ đúng chỗ đó tới khi giao. Không làm lại bước đã xong.")
                        continue
                    with self.khoa:
                        co_tin_moi = bool(self.cho_viec.get(vid))
                    if co_tin_moi or nhac >= 3 or not self._con_do(vid, st):
                        break
                    nhac += 1
                    D.them_tin(vid, "he_thong", f"Claude dừng khi việc dựng chưa xong — Studio tự nhắc làm tiếp (lần {nhac}/3).")
                    chu = ("[STUDIO] Lượt trước của bạn đã KẾT THÚC khi việc chưa xong — mọi lệnh chạy nền của lượt đó đã bị tắt theo. "
                           "Kiểm tra file đầu ra; chưa có hoặc dở dang thì chạy lại lệnh dựng THẲNG (timeout Bash 600000 ms, hoặc chạy nền "
                           "và tự chờ trong cùng lượt), rồi làm tiếp các bước còn lại tới khi giao. Đừng kết thúc lượt khi chưa giao "
                           "(trừ khi cần hỏi người dùng bằng khối [HỎI]).")
                with self.khoa:                     # tin nhắn đến trong lúc chạy → làm tiếp ngay trong cùng việc
                    ds = self.cho_viec.get(vid) or []
                    if not ds or st["bi_dung"]:
                        self.cho_viec.pop(vid, None)
                        break
                    job = ds.pop(0)
                    st["nang"] = st["nang"] or job["nang"]
                    st["bi_dung"] = False
        except Exception as e:
            D.them_tin(vid, "loi", f"Động cơ Claude lỗi: {e}")
        finally:
            with self.khoa:
                self.chay.pop(vid, None)
            try:
                D.sua_viec(vid, lambda x: x.__setitem__("dang_lam", False))     # 1.3: kết thúc bình thường → bỏ dấu "đang làm"
            except Exception:
                pass

    def _lam(self, vid, chu, st, im_loi_tam=False):
        """Trả True nếu gặp lỗi đăng nhập tạm thời (nên thử lại)."""
        v = D.doc_viec(vid)
        phien = v.get("phien")
        if not phien and v.get("loi_goc") and v.get("loi_goc") != chu and len(chu) < 400 and (v.get("luot") or v.get("dang_lam") is not None):
            # 1.2.19 (B1): mất phiên (Studio tắt/mở lại) mà người dùng chỉ nhắn "tiếp tục" → ghép LỜI GỐC (có đường dẫn tệp) để Claude biết việc
            chu = (v["loi_goc"] + "\n\n[STUDIO] Phiên Claude trước đã mất (Studio khởi động lại). Người dùng vừa nhắn: “" + chu.strip()[:300]
                   + "”. Mở phiếu/thư mục dự án của việc này (nếu đã có) để xem đã làm tới đâu rồi làm tiếp — KHÔNG làm lại phần đã xong.")
        if not phien:
            c = D.doc_json(os.path.join(D.CN, v["ho_so"], "cau-hinh.json"), {})
            kenh = (c.get("kenh") or {}).get("ten") or v["ho_so"]
            chu = HUONG_DAN_V3.format(ho_so=v["ho_so"], kenh=kenh, skill=D.SKILL.replace("\\", "/"), py=D.py_skill(),
                                      buoc_nhin=BUOC_NHIN_NHANH if v.get("che_do") == "nhanh" else BUOC_NHIN_KY) + "\n---\n" + chu
        lenh = [self.exe, "-p", "--output-format", "stream-json", "--verbose", "--allowedTools", CONG_CU]
        # 1.3: chỉ nạp đúng công cụ Studio dùng — không nạp MCP/plugin/skill người dùng cài cho việc khác: ngữ cảnh nền mỗi lượt
        # ~43k → ~7k token (đo 19/10), rẻ ~6× mà không mất khả năng nào của Studio
        lenh += _co_gon(self.exe)
        # 1.3: KHOÁ mã máy dựng — AI không được sửa v2/ studio/ scripts/ (bản khách có chữ ký TEP-GOI: sửa là gói hỏng, Studio
        # tự chặn "bộ cài bị thay đổi"); thư mục nao/ (hồ sơ, góp ý, công thức học) vẫn ghi được. Quy tắc tính từ cwd = thư mục app.
        lenh += ["--disallowedTools", "Edit(v2/**)", "Edit(v3/**)", "Write(v3/**)", "Edit(studio/**)", "Edit(scripts/**)", "Edit(SKILL.md)",
                 "Edit(TEP-GOI.json)", "Edit(VERSION)"]
        cd = D.cai_dat()
        # 1.2.19 (F3): ⚡Làm nhanh mặc định Sonnet (rẻ ~5×, đủ cho dựng nhanh); vẫn đè được bằng cài đặt model_nhanh
        mdl = (cd.get("model_nhanh") or "sonnet") if v.get("che_do") == "nhanh" else cd.get("model")
        if mdl:
            lenh += ["--model", mdl]                  # khoá model (mặc định Opus 5.5; làm nhanh dùng model_nhanh nếu đặt — vd Sonnet cho rẻ hơn nữa) — không để Claude Code tự chọn
        if cd.get("effort"):
            lenh += ["--effort", cd["effort"]]
        lenh += _co_tran(self.exe, cd)                # 1.2.19 (F1): trần bước + trần USD mỗi lượt
        if phien:
            lenh += ["--resume", phien]
        for d in (v.get("thu_muc_doc") or [])[-30:]:     # 1.2.11: thư mục tư liệu / thư mục người dùng kết nối → Claude đọc được
            if os.path.isdir(d):
                lenh += ["--add-dir", d]
        bac_si.them_path()          # ffmpeg / uv mới cài bằng winget chưa có trong PATH của tiến trình này
        env = D.env_con(STUDIO_VIEC=vid, HO_SO=v["ho_so"], QUY_TRINH_PHIEU=D.p_phieu(vid), QUY_TRINH_PHIEU2=D.p_phieu2(vid),
                        DISABLE_AUTOUPDATER="1")            # 1.2.19 (F4): Claude Code không tự cập nhật giữa lượt · 1.2.21: STUDIO_CPU_ONLY theo tang_toc
        if v.get("che_do") == "nhanh":                      # 1.3: CHẾ ĐỘ LÀM NHANH — mọi lệnh st.py của việc này đi đường nhanh
            env.update(STUDIO_CHE_DO="nhanh", STUDIO_NHANH="1")
        st["bat_dau"], st["bi_dung"] = time.time(), False
        st["proc"] = subprocess.Popen(lenh, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     cwd=D.SKILL, env=env, creationflags=D.KHONG_CUA_SO,
                                     **({} if D.WIN else {"start_new_session": True}))   # 1.2.13: nhóm riêng → Dừng giết được cả cây
        st["proc"].stdin.write(chu.encode("utf-8"))
        st["proc"].stdin.close()
        loi_cuoi, co_kq, tam = [], False, False
        st["loi_mang"] = False
        st["hoat_dong"] = time.time()

        def _doc_stderr():                               # 1.2.19 (F6): stderr của Claude Code lưu lại để chẩn đoán
            du = st["proc"].stderr.read().decode("utf-8", "replace")
            loi_cuoi.extend(du.splitlines()[-6:])
            if du.strip():
                try:
                    with open(os.path.join(D.DATA, f"claude-{vid}.log"), "a", encoding="utf-8") as f:
                        f.write(time.strftime("\n===== %Y-%m-%d %H:%M:%S =====\n") + du[-20000:])
                except Exception:
                    pass
        t_err = threading.Thread(target=_doc_stderr, daemon=True); t_err.start()
        for dong in st["proc"].stdout:
            st["hoat_dong"] = time.time()
            try:
                m = json.loads(dong.decode("utf-8", "replace"))
            except json.JSONDecodeError:
                continue
            t = m.get("type")
            if t == "system" and m.get("subtype") == "init" and m.get("session_id"):
                sid, mdl = m["session_id"], m.get("model")
                D.sua_viec(vid, lambda x: (x.__setitem__("phien", sid), x.__setitem__("model", mdl)))
            elif t == "assistant":
                if (m.get("message") or {}).get("model") == "<synthetic>":
                    continue          # lời báo lỗi do Claude Code tự sinh — đã có ở bản ghi result
                for c in (m.get("message") or {}).get("content") or []:
                    if c.get("type") == "text" and c.get("text", "").strip():
                        chu_, cau, lc = tach_hoi(c["text"].strip())
                        # câu tự nhủ bằng tiếng Anh khi gỡ lỗi công cụ → xếp vào nhóm thao tác, không nói với người dùng
                        if chu_:
                            D.them_tin(vid, "claude" if CHU_VIET.search(chu_) or len(chu_) > 300 else "cong_cu", chu_)
                        if cau:
                            D.them_tin(vid, "hoi", cau, lua_chon=lc)
                    elif c.get("type") == "tool_use" and c.get("name") == "AskUserQuestion":
                        for q in ((c.get("input") or {}).get("questions") or [])[:2]:
                            D.them_tin(vid, "hoi", str(q.get("question") or ""),
                                       lua_chon=[str(o.get("label") or "")[:80] for o in (q.get("options") or [])][:4])
                    elif c.get("type") == "tool_use":
                        tt = _tom_tat(c.get("name"), c.get("input"))
                        if tt:
                            D.them_tin(vid, "cong_cu", tt)
            elif t == "result":
                co_kq = True
                D.ghi_luot(vid, m)
                if m.get("is_error"):
                    kq = str(m.get("result") or "Claude gặp lỗi")
                    if im_loi_tam and ("OAuth" in kq or "refresh" in kq.lower()):
                        tam = True
                        continue
                    if LOI_MANG.search(kq) and not re.search(r"usage limit|rate limit", kq, re.I):
                        st["loi_mang"] = True
                        kq = "Mất kết nối tới Claude (mạng chập chờn). " + kq
                    if re.search(r"usage limit|rate limit|limit reached|quota|out of (extra )?usage", kq, re.I):
                        st["het_luot"] = True
                        st["het_luot_den"] = gio_mo_lai(kq)
                        kq = ("Tài khoản Claude đã hết lượt dùng trong khung giờ này (giới hạn theo gói). Việc đang dở vẫn giữ "
                              "nguyên — Studio TỰ CHỜ tới giờ mở lại lượt rồi làm tiếp (hoặc nâng gói Claude).\n\n" + kq)
                    D.them_tin(vid, "loi", kq)
                    if phien and "session" in kq.lower():
                        D.sua_viec(vid, lambda x: x.__setitem__("phien", None))
        ma = st["proc"].wait()
        try:
            t_err.join(2)
        except Exception:
            pass
        # lượt kết thúc bằng một câu hỏi thường (không theo mẫu) → vẫn báo Studio là Claude đang chờ trả lời
        try:
            cuoi = next((t for t in reversed(D.doc_viec(vid)["tin"]) if t["vai"] in ("claude", "hoi", "nguoi_dung", "video")), None)
            if cuoi and cuoi["vai"] == "claude" and cuoi["noi_dung"].rstrip().endswith("?"):
                D.sua_viec(vid, lambda x: x.__setitem__("cho_tra_loi", True))
        except Exception:
            pass
        try:                                                             # 1.2.19 (F6): mã thoát vào lượt gần nhất
            D.sua_viec(vid, lambda x: x["luot"][-1].__setitem__("ma", ma) if x.get("luot") else None)
        except Exception:
            pass
        if ma and not co_kq and not st["bi_dung"]:
            D.them_tin(vid, "loi", "Claude dừng giữa chừng. " + _dich_loi_cli(" ".join(loi_cuoi)) + " " + " ".join(loi_cuoi)[-500:])
        return tam
