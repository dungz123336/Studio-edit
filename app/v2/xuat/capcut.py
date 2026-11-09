# -*- coding: utf-8 -*-
"""XUẤT PROJECT CAPCUT — Studio 2.

Từ một dự án đã dựng xong (4-dung/nhat-ky-dung.json), sinh một project CapCut (bản quốc tế, PC) mở được và SỬA được:
  - Track video chính : clip GỐC cắt đúng từng đoạn kịch bản + keyframe camera (zoom/lia) — sửa nhịp cắt thoải mái.
  - Track "Khung"     : các đoạn lớp khung (cảnh trám, màn hình lồng, chuyển cảnh) dựng sẵn — clip đặc, xoá/dời được.
  - Track "Đồ hoạ"    : MỖI hiệu ứng chữ / thẻ / đồ hoạ = một clip TRONG SUỐT riêng (ProRes 4444), giữ đúng hình bản Studio.
  - Track chữ ẩn      : bản CHỮ CAPCUT THẬT của từng hiệu ứng chữ (đang ẩn) — bật lên để thay chữ / đổi font.
  - Track phụ đề      : chữ CapCut thật theo lời, đúng font / màu / vị trí — sửa chính tả trực tiếp.
  - Track nhạc + SFX  : file thật trong kho, đúng thời điểm và mức âm.
  - Track tham chiếu  : bản Studio đã dựng (ẩn, tắt tiếng) để so.

CapCut 9.x chỉ nhận project "gieo" từ một project THẬT do chính app tạo → dùng mẫu ở <STUDIO_DATA>/capcut-mau
(tự chép từ project mới nhất trong thư mục project của CapCut nếu chưa có). CapCut 10.x hiện từ chối project do tool ghi.

1.2.21 (rà soát #18): mẫu gieo CHỈ chép tệp json/cấu hình (không Resources/, vật liệu, ảnh bìa của khách); draft_root_path cũng
posix; keyframes/relationships/extra_info/draft_materials của mẫu được rỗng hoá (không còn id treo); clip .mov đặt tên theo
BĂM NỘI DUNG concat (sửa khung → tên mới, không còn cache theo mtime), .mov cũ không dùng bị xoá, danh sách ghi vào
7-capcut/.da-xuat để dọn rác (studio/don_rac.py) xoá do-hoa/ sau khi khách xác nhận; lớp Preset (hoạt ảnh chữ CapCut do AI
chọn trong ke-hoach.capcut) được gọi cho phụ đề; viền phụ đề lấy từ lớp / quyết định kênh, không còn hằng #000000 0.08;
Linux: CapCut không có bản Linux → chỉ ra gói tách lớp; ffmpeg dài đi qua v3/chung.chay_ffmpeg (tiến độ + watchdog) nếu có.
1.2.21 (B2) lớp SAU NGƯỜI: sprite không còn nướng mặt nạ (B1) → thêm clip "nguoi-<băm>.mov" = người cắt từ base bằng alpha-tl
(alphamerge, ProRes 4444, chỉ khoảng hợp của các lớp sau người), track "Người (cắt từ base)" nằm TRÊN các track "Sau người n"
và DƯỚI "Đồ hoạ n" + phụ đề; capcut.json["nguoi"] = {mov, tu, den, mb}; không có alpha-tl → xếp như lớp thường + loi_xuat.sau_nguoi.
ĐỀ XUẤT (chưa đổi, giữ an toàn): .mov ProRes 4444 0,5–1,5 GB/dự án — bản sau cân nhắc qtrle/png-alpha hoặc ProRes 4444 ở 540p
khi khung ≤ 1080 (CapCut tự phóng), giảm ~60–70 %.

    python v2/xuat/capcut.py <thư mục dự án> [--ten "Tên project"] [--khong-do-hoa]
"""
import copy, glob, hashlib, json, math, os, platform, re, shutil, subprocess, sys, time, uuid

V2 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if V2 not in sys.path:
    sys.path.insert(0, V2)
import chung as C  # noqa: E402

WIN = os.name == "nt"
MAC = platform.system() == "Darwin"
LINUX = not WIN and not MAC                       # 1.2.21: CapCut không có bản Linux
HERE = os.path.dirname(os.path.abspath(__file__))
_C3 = None


def _c3():
    """v3/chung nạp dưới tên riêng (v2/chung đã chiếm tên `chung`) — lấy chay_ffmpeg (A1 1.2.21) + duong('ffmpeg'); thiếu → None"""
    global _C3
    if _C3 is None:
        try:
            import importlib.util
            p = os.path.join(os.path.dirname(V2), "v3", "chung.py")
            spec = importlib.util.spec_from_file_location("v3_chung_capcut", p)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            _C3 = m
        except Exception:
            _C3 = False
    return _C3 or None


def _ffmpeg_exe():
    c3 = _c3()
    try:
        return c3.duong("ffmpeg") if c3 else (shutil.which("ffmpeg") or "ffmpeg")
    except Exception:
        return shutil.which("ffmpeg") or "ffmpeg"


def _chay_ffmpeg(args, du_an, buoc, dai=None):
    """ffmpeg dài → v3/chung.chay_ffmpeg (tiến độ, watchdog treo, nhớ lỗi hwaccel) nếu A1 đã có; dự phòng chung.sh / subprocess.
    → (mã, stderr)"""
    cmd = [_ffmpeg_exe(), "-y", "-v", "error", *args]
    c3 = _c3()
    ham = getattr(c3, "chay_ffmpeg", None) if c3 else None
    if ham:
        try:
            kq = ham(cmd, du_an, buoc, dur=dai)
            ma, err = (kq if isinstance(kq, (tuple, list)) and len(kq) >= 2 else (kq, ""))
            return int(ma or 0), str(err or "")
        except TypeError:
            pass                                                 # chữ ký khác → dự phòng
    sh = getattr(c3, "sh", None) if c3 else None
    if sh:
        try:
            ma, _, err = sh(cmd, timeout=3600)
            return int(ma), err
        except Exception:
            pass
    r = subprocess.run(cmd, capture_output=True, creationflags=0x08000000 if WIN else 0)
    return r.returncode, r.stderr.decode("utf-8", "replace")


def _bam_tep(p, n=10):
    """sha256[:n] NỘI DUNG tệp — khung đổi → tên .mov đổi. 1.2.21 (B2): tệp .ffconcat băm thêm size+mtime của TỪNG PNG nó liệt kê
    (lop.ffconcat chỉ ghi k0000N.png + thời lượng → hai lớp chữ khác nhau cùng số khung từng trùng băm, đổi chữ trúng cache cũ)."""
    h = hashlib.sha256()
    try:
        with open(p, "rb") as f:
            for khoi in iter(lambda: f.read(1 << 20), b""):
                h.update(khoi)
        if str(p).lower().endswith(".ffconcat"):
            goc = os.path.dirname(os.path.abspath(p))
            for dong in open(p, encoding="utf-8", errors="replace"):
                m = re.match(r"\s*file\s+'(.+?)'\s*$", dong) or re.match(r"\s*file\s+(\S+)\s*$", dong)
                if m:
                    try:
                        st = os.stat(os.path.join(goc, m.group(1)))
                        h.update(f"|{st.st_size}|{int(st.st_mtime)}".encode("utf-8"))
                    except OSError:
                        h.update(b"|?")
    except OSError:
        h.update(str(p).encode("utf-8"))
    return h.hexdigest()[:n]
MAU = json.load(open(os.path.join(HERE, "capcut_mau.json"), encoding="utf-8"))
DATA = os.path.expanduser(os.environ.get("STUDIO_DATA") or "~/.studio-edit-video")
FPS_DO_HOA = 30                   # clip đồ hoạ trong suốt: 30 khung/giây là đủ (CapCut tự khớp fps dự án)
CANH_DAI_DO_HOA = 1080            # cạnh ngắn tối đa của clip đồ hoạ (CapCut tự phóng theo khung)
TRAN_AM = 3.98                    # CapCut: âm lượng tối đa ~ +12 dB


# ───────────────────────── tiện ích
def _id():
    p = str(uuid.uuid4()).upper().split("-")
    p[2] = p[2].lower()
    return "-".join(p)


def US(t):
    return int(round(float(t) * 1_000_000))


def _posix(p):
    return os.path.abspath(p).replace("\\", "/")


def _db(g):
    return max(0.0, min(TRAN_AM, 10 ** (g / 20.0)))


def _ghi_json(p, o):
    tam = p + ".tam"
    with open(tam, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tam, p)


def _cau_hinh(*duong, mac_dinh=None):
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(V2), "scripts"))
        import config
        return config.lay(*duong, mac_dinh=mac_dinh)
    except Exception:
        return mac_dinh


def tu_xuat():
    """1.3: giao xong có TỰ xuất CapCut không — cấu hình capcut.tu_dong: "neu_co" (mặc định: chỉ khi máy có CapCut) | "luon" | "tat"
    (chỉ xuất khi bấm nút "Xuất sang CapCut" trên thẻ video). Máy không tự xuất thì lúc dựng cũng không ghi lớp CapCut (dựng nhanh hơn)."""
    if os.environ.get("STUDIO_KHONG_CAPCUT") == "1":
        return False
    che_do = str(_cau_hinh("capcut", "tu_dong", mac_dinh="neu_co") or "neu_co")
    if che_do == "tat":
        return False
    if che_do == "luon":
        return True
    try:
        return os.path.isdir(goc_capcut())
    except Exception:
        return False


def goc_capcut():
    """thư mục chứa project của CapCut (com.lveditor.draft)"""
    d = os.environ.get("CAPCUT_DU_AN")
    if not d:
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(V2), "scripts"))
            import config
            d = config.lay("capcut", "thu_muc_du_an", mac_dinh="") or ""
        except Exception:
            d = ""
    if not d:
        d = (os.path.join(os.environ.get("LOCALAPPDATA", ""), "CapCut", "User Data", "Projects", "com.lveditor.draft") if WIN
             else os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft"))
        try:
            r = json.load(open(os.path.join(d, "root_meta_info.json"), encoding="utf-8")).get("root_path")
            if r and os.path.isdir(r):
                d = r
        except Exception:
            pass
    return os.path.expanduser(d)


def capcut_dang_mo():
    try:
        if WIN:
            o = subprocess.run(["tasklist", "/FI", "IMAGENAME eq CapCut.exe", "/NH"], capture_output=True, text=True,
                               creationflags=0x08000000).stdout
            return "CapCut.exe" in o
        return subprocess.run(["pgrep", "-x", "CapCut"], capture_output=True).returncode == 0
    except Exception:
        return False


def _noi_dung_mau(d):
    for p in [os.path.join(d, "draft_content.json")] + glob.glob(os.path.join(d, "Timelines", "*", "draft_content.json")):
        try:
            j = json.load(open(p, encoding="utf-8"))
            if isinstance(j, dict) and "tracks" in j and "materials" in j:
                return j
        except Exception:
            continue
    return None


def phien_ban_capcut():
    """1.2.19: bản CapCut đang cài (Windows: Apps/ProductInfo.xml <full_appver>; dự phòng tên thư mục Apps/<ver>) → "9.7.0" | "" """
    try:
        if WIN:
            goc = os.path.join(os.environ.get("LOCALAPPDATA", ""), "CapCut", "Apps")
            p = os.path.join(goc, "ProductInfo.xml")
            if os.path.isfile(p):
                m = re.search(r'<(?:full_)?appver value="([\d.]+)"', open(p, encoding="utf-8", errors="replace").read())
                if m:
                    return m.group(1)
            ds = sorted((b for b in os.listdir(goc) if re.fullmatch(r"\d+(\.\d+)+", b)),
                        key=lambda v: tuple(int(x) for x in v.split("."))) if os.path.isdir(goc) else []      # 10.0 > 9.7 (không so chuỗi)
            return ds[-1] if ds else ""
        p = "/Applications/CapCut.app/Contents/Info.plist"
        if os.path.isfile(p):
            m = re.search(r"CFBundleShortVersionString</key>\s*<string>([\d.]+)", open(p, encoding="utf-8", errors="replace").read())
            return m.group(1) if m else ""
    except Exception:
        pass
    return ""


def _ban_cua_project(d):
    """bản CapCut đã tạo project d: platform.app_version (hoặc new_version) trong draft_content"""
    j = _noi_dung_mau(d)
    if not j:
        return ""
    return str((j.get("platform") or {}).get("app_version") or "")      # new_version là bản ĐỊNH DẠNG draft, không phải bản app → không dùng


def _cung_dong(a, b):
    """cùng dòng bản (so 2 số đầu: 9.7 == 9.7.0.4153)"""
    aa, bb = (a or "").split("."), (b or "").split(".")
    return bool(aa and bb) and aa[:2] == bb[:2]


def tim_mau():
    """project mẫu (gieo) của CapCut đang cài → thư mục. 1.2.19: mẫu phải CÙNG BẢN với CapCut đang cài (9.7 bỏ thư mục Timelines/,
    đổi new_version…) — khách cập nhật CapCut thì mẫu cũ bị CapCut từ chối ("unconventional path"); lệch bản → gieo lại từ project
    mới nhất do chính bản đang cài tạo. Không có project nào của bản mới → vẫn dùng mẫu cũ và báo rõ."""
    dich = os.path.join(DATA, "capcut-mau")
    ban_cai = phien_ban_capcut()
    co_mau = _noi_dung_mau(dich) is not None
    if co_mau and (not ban_cai or not _ban_cua_project(dich) or _cung_dong(_ban_cua_project(dich), ban_cai)):   # không rõ bản → chấp nhận (như 1.2.18)
        return dich
    goc = goc_capcut()
    ung = []
    for d in glob.glob(os.path.join(goc, "*")):
        b = os.path.basename(d)
        if b.startswith(".") or not os.path.isdir(d) or os.path.exists(os.path.join(d, "_studio_xuat")):
            continue
        if _noi_dung_mau(d) is not None and (not ban_cai or not _ban_cua_project(d) or _cung_dong(_ban_cua_project(d), ban_cai)):
            ung.append((os.path.getmtime(d), d))
    if not ung:
        if co_mau:
            print(f"  ! mẫu gieo là bản CapCut {_ban_cua_project(dich)}, máy đang cài {ban_cai}: chưa có project nào của bản mới để gieo lại "
                  "— mở CapCut, bấm \"Tạo dự án\" (để trống cũng được), thoát CapCut rồi xuất lại. Tạm dùng mẫu cũ.")
            return dich
        raise SystemExit("CHƯA CÓ PROJECT MẪU CAPCUT — mở CapCut, bấm \"Tạo dự án\", thoát CapCut rồi xuất lại "
                         "(CapCut chỉ mở project gieo từ project thật của chính bản đang cài).")
    src = max(ung)[1]
    if os.path.isdir(dich):
        shutil.rmtree(dich, ignore_errors=True)
    shutil.copytree(src, dich, dirs_exist_ok=True, ignore=_chi_cau_hinh)      # 1.2.21: chỉ json/cấu hình, giữ cây thư mục rỗng
    print(f"  mẫu CapCut: chép từ {src} (bản {_ban_cua_project(src) or '?'}, máy cài {ban_cai or '?'}) — chỉ tệp cấu hình")
    return dich


DUOI_CAU_HINH = (".json", ".tmp", ".bak", "draft_settings", ".xml", ".ini", ".txt")


def _chi_cau_hinh(d, ten):
    """ignore cho copytree: bỏ MỌI tệp không phải cấu hình (video/ảnh/âm thanh/vật liệu của project khách, ảnh bìa, tệp > 8 MB)
    và nội dung Resources/ — thư mục vẫn được tạo (rỗng) để CapCut thấy đúng bố cục project."""
    bo = []
    goc_res = os.path.basename(d) == "Resources" or f"{os.sep}Resources{os.sep}" in d + os.sep
    for t in ten:
        p = os.path.join(d, t)
        if os.path.isdir(p):
            continue                                              # thư mục: giữ (rỗng nếu bên trong bị bỏ hết)
        if goc_res or t == "draft_cover.jpg" or not t.endswith(DUOI_CAU_HINH):
            bo.append(t); continue
        try:
            if os.path.isfile(p) and os.path.getsize(p) > 8_000_000:
                bo.append(t)
        except OSError:
            pass
    return set(bo)


def _srt_time(t):
    t = max(0.0, float(t)); h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def goi_tach_lop(ra_dir, kq, vi, W, H, fps, dur, nguoi=None):
    """1.2.19: GÓI TÁCH LỚP dùng cho MỌI bản CapCut (kể cả 10.x chặn project ngoài) và Premiere/Resolve:
    7-capcut/ phu-de.srt (nhập Subtitles) · lop.json + HUONG-DAN.txt (từng lớp: tệp .mov trong suốt, giây vào/ra, vị trí/cỡ) ·
    am-thanh.wav · nền = dung/base… Khách kéo từng .mov vào CapCut, đặt theo bảng.
    1.2.21 (B2): lớp có "sau_nguoi" + `nguoi` {mov, tu, den} (người cắt từ base) → lop.json ghi cờ + mục "nguoi", HUONG-DAN có bước xếp track."""
    srt = []
    ds_pd = sorted((l for l in (kq.get("lop") or []) if l.get("phu_de") and l.get("text")), key=lambda l: float((l.get("meta") or {}).get("t0") or 0))
    for i, L in enumerate(ds_pd):
        m = L.get("meta") or {}
        srt.append(f"{i + 1}\n{_srt_time(m.get('t0', 0))} --> {_srt_time(m.get('t1', 0))}\n{str(L['text']).strip()}\n")
    p_srt = os.path.join(ra_dir, "phu-de.srt")
    open(p_srt, "w", encoding="utf-8").write("\n".join(srt))
    lop = []
    for t0, t1, v in vi:
        x0, y0, x1, y1 = v["hop"]
        lop.append({"id": v.get("id"), "tep": os.path.basename(v["file"]), "vao": round(t0, 3), "ra": round(t1, 3),
                    "hop_px": [int(x0), int(y0), int(x1), int(y1)], "rong_pct": round((x1 - x0) / W * 100, 1), "cao_pct": round((y1 - y0) / H * 100, 1),
                    "tam_pct": [round((x0 + x1) / 2 / W * 100, 1), round((y0 + y1) / 2 / H * 100, 1)], "do_trong": v.get("alpha", 1.0),
                    "sau_nguoi": bool(v.get("sn"))})
    ng = None
    if nguoi and nguoi.get("mov"):
        hx0, hy0, hx1, hy1 = nguoi.get("hop") or [0, 0, W, H]
        ng = {"tep": os.path.basename(nguoi["mov"]), "vao": round(float(nguoi["tu"]), 3), "ra": round(float(nguoi["den"]), 3), "mb": nguoi.get("mb"),
              "hop_px": [int(hx0), int(hy0), int(hx1), int(hy1)], "rong_pct": round((hx1 - hx0) / W * 100, 1), "cao_pct": round((hy1 - hy0) / H * 100, 1),
              "tam_pct": [round((hx0 + hx1) / 2 / W * 100, 1), round((hy0 + hy1) / 2 / H * 100, 1)]}
    C.ghi(os.path.join(ra_dir, "lop.json"), {"khung": [W, H], "fps": fps, "dur": round(dur, 3), "lop": lop, "phu_de": len(srt), "nguoi": ng})
    hd = [f"GÓI TÁCH LỚP — Studio dựng video (khung {W}×{H}, {fps} fps, dài {dur:.1f} s)", "",
          "Dùng khi CapCut không mở được project tự tạo (CapCut 10.x) hoặc dựng tiếp ở Premiere / DaVinci:",
          "1. Kéo video nền (dung/base… trong thư mục dự án, hoặc thanh-pham.mp4 nếu muốn giữ cả chữ) vào track dưới cùng.",
          "2. Kéo am-thanh.wav vào track âm thanh (giọng + nhạc + SFX đã trộn).",
          "3. Nhập phu-de.srt: CapCut → Văn bản → Phụ đề → Nhập (Import SRT). Chữ sửa được trực tiếp.",
          "4. Mỗi lớp đồ hoạ là một tệp .mov TRONG SUỐT trong do-hoa/: kéo vào track trên, đặt đúng giây vào/ra và vị trí theo bảng dưới",
          "   (tâm % = vị trí tâm so với khung; rộng % = cỡ so với bề ngang khung — CapCut: Scale theo rộng %, Position theo tâm %)."]
    if ng:
        hd += [f"5. LỚP SAU NGƯỜI: các lớp ghi 'SAU NGƯỜI' bên dưới phải nằm DƯỚI tệp {ng['tep']} (người cắt từ nền, trong suốt phần còn lại):",
               f"   kéo do-hoa/{ng['tep']} vào track ngay TRÊN các lớp sau người và DƯỚI lớp thường / phụ đề, đặt {ng['vao']:.2f}s → {ng['ra']:.2f}s,",
               f"   tâm ({ng['tam_pct'][0]}%, {ng['tam_pct'][1]}%) · rộng {ng['rong_pct']}% · cao {ng['cao_pct']}%. Thứ tự từ dưới lên: nền → lớp sau người → người → lớp thường → phụ đề.",
               "   Clip người CHỈ phủ vùng quanh chữ sau người (hộp hợp + lề 15 %) — kéo chữ ra ngoài vùng này thì chữ sẽ đè người."]
    hd.append("")
    for l in lop:
        hd.append(f"- {l['tep']}: {l['vao']:.2f}s → {l['ra']:.2f}s · tâm ({l['tam_pct'][0]}%, {l['tam_pct'][1]}%) · rộng {l['rong_pct']}% · cao {l['cao_pct']}%"
                  + (f" · độ trong {l['do_trong']}" if l.get("do_trong", 1.0) != 1.0 else "")
                  + (f" · SAU NGƯỜI (dưới {ng['tep']})" if (l.get("sau_nguoi") and ng) else ""))
    open(os.path.join(ra_dir, "HUONG-DAN.txt"), "w", encoding="utf-8").write("\n".join(hd) + "\n")
    return {"srt": p_srt, "lop": len(lop)}


# ───────────────────────── vật liệu (bám đúng khuôn project thật của CapCut)
def _aux(loai, **sua):
    m = copy.deepcopy(MAU["mat"][loai])
    m["id"] = _id()
    if loai == "material_animations":
        m["animations"] = []
    if loai == "beats":
        m["ai_beats"] = {k: ("" if isinstance(v, str) else v) for k, v in (m.get("ai_beats") or {}).items()}
        m["user_beats"] = []
    m.update(sua)
    return m


class Bo:
    """bộ gom vật liệu + track của một project"""
    def __init__(self):
        self.mat = {}
        self.tracks = []

    def them(self, loai, m):
        self.mat.setdefault(loai, []).append(m)
        return m["id"]

    def video_mat(self, p, info, loai="video"):
        m = copy.deepcopy(MAU["mat"]["video"])
        m.update({"id": _id(), "path": _posix(p), "media_path": "", "type": loai, "material_name": os.path.basename(p),
                  "duration": 10800000000 if loai == "photo" else US(info["dai"]), "width": int(info["w"] or 0),
                  "height": int(info["h"] or 0), "has_audio": bool(info.get("co_am")), "local_material_id": "",
                  "local_id": "", "material_id": "", "unique_id": ""})
        return self.them("videos", m)

    def audio_mat(self, p, dai):
        m = copy.deepcopy(MAU["mat"]["audio"])
        m.update({"id": _id(), "path": _posix(p), "name": os.path.splitext(os.path.basename(p))[0], "duration": US(dai),
                  "type": "extract_music", "music_id": "", "category_name": "local", "category_id": "", "app_id": 0,
                  "wave_points": [], "local_material_id": "", "check_flag": 1, "source_platform": 0, "resource_id": ""})
        return self.them("audios", m)

    def refs_video(self, toc=1.0):
        return [self.them("speeds", _aux("speeds", speed=float(toc))), self.them("placeholder_infos", _aux("placeholder_infos")),
                self.them("canvases", _aux("canvases")), self.them("sound_channel_mappings", _aux("sound_channel_mappings")),
                self.them("material_colors", _aux("material_colors")), self.them("vocal_separations", _aux("vocal_separations"))]

    def refs_audio(self, mo_vao=0.0, mo_ra=0.0):
        r = [self.them("speeds", _aux("speeds")), self.them("placeholder_infos", _aux("placeholder_infos")),
             self.them("beats", _aux("beats")), self.them("sound_channel_mappings", _aux("sound_channel_mappings")),
             self.them("vocal_separations", _aux("vocal_separations"))]
        if mo_vao or mo_ra:
            r.append(self.them("audio_fades", {"id": _id(), "fade_in_duration": US(mo_vao), "fade_out_duration": US(mo_ra),
                                               "fade_type": 0, "type": "audio_fade"}))
        return r

    def track(self, loai, ten, segs):
        if not segs:
            return None
        t = {"attribute": 0, "flag": 0, "id": _id(), "is_default_name": not ten, "name": ten or "", "segments": segs,
             "type": loai}
        self.tracks.append(t)
        return t


def _seg(loai, mat_id, refs, t0, dai, src0=None, src_dai=None, toc=1.0, am=1.0, clip=None, hien=True, kf=None,
         render=0, track_render=0):
    s = copy.deepcopy(MAU["seg"][loai])
    s.update({"id": _id(), "material_id": mat_id, "extra_material_refs": refs,
              "target_timerange": {"start": US(t0), "duration": max(1, US(dai))},
              "source_timerange": None if src0 is None else {"start": US(src0), "duration": max(1, US(src_dai))},
              "speed": float(toc), "volume": float(am), "last_nonzero_volume": float(am) if am > 0 else 1.0,
              "visible": bool(hien), "common_keyframes": kf or [], "keyframe_refs": [],
              "render_index": render, "track_render_index": track_render})
    if loai == "video":
        s["hdr_settings"] = {"mode": 1, "intensity": 1.0, "nits": 1000}
        s["enable_lut"] = s["enable_adjust"] = False
    if clip is not None and s.get("clip") is not None:
        s["clip"] = clip
    return s


def _clip(scale=1.0, x=0.0, y=0.0, alpha=1.0):
    return {"scale": {"x": float(scale), "y": float(scale)}, "rotation": 0.0, "transform": {"x": float(x), "y": float(y)},
            "flip": {"vertical": False, "horizontal": False}, "alpha": float(alpha)}


def _kf(loai, diem):
    """diem: [(giây trong đoạn, giá trị)]"""
    return {"id": _id(), "material_id": "", "property_type": loai,
            "keyframe_list": [{"id": _id(), "curveType": "Line", "time_offset": US(t), "left_control": {"x": 0.0, "y": 0.0},
                               "right_control": {"x": 0.0, "y": 0.0}, "values": [float(v)], "string_value": "", "graphID": ""}
                              for t, v in diem]}


def _chia_track(viec):
    """viec: [(t0, t1, ...)] → danh sách track, mỗi track không chồng đoạn"""
    tracks = []
    for v in sorted(viec, key=lambda x: x[0]):
        for tr in tracks:
            if tr[-1][1] <= v[0] + 1e-3:
                tr.append(v); break
        else:
            tracks.append([v])
    return tracks


# ───────────────────────── preset CapCut thật (danh mục lập từ project CapCut có sẵn — v2/xuat/lap_preset.py)
P_PRESET = os.path.join(HERE, "capcut_preset.json")
NHE = ("Aparición", "Mini zoom", "Entrada borrosa", "Deslizar hacia arriba", "Pegado hacia arriba", "Aparición con onda",
       "Alejar con desenfoque", "Desenfoque a la izquierda", "Deslizar hacia abajo")      # vào nhẹ — hợp phụ đề


class Preset:
    """1.2.16: hoạt ảnh chữ CapCut do AI chọn (ke-hoach.capcut: {"phu_de_vao": tên, "chu_vao": tên|[tên…], "chu_ra": tên|[tên…]|"khong"},
    tên lấy từ danh mục `capcut_preset.json`). AI không ghi → hoạt ảnh trung tính (hiện dần), máy KHÔNG bốc ngẫu nhiên.
    1.2.21: lõi 1.3 xuất đồ hoạ chữ thành clip .mov (không còn track chữ ẩn) nên chỉ `phu_de_vao` được áp (track phụ đề = chữ CapCut
    thật); `chu_vao`/`chu_ra` giữ cho bản có track chữ ẩn sau này. Chỉ tạo khi ke-hoach.capcut là dict (xuat_v3 gọi)."""
    TRUNG_TINH = "Aparición"

    def __init__(self, du_an, kh=None):
        self.ds = C.doc(P_PRESET, {}) if os.path.exists(P_PRESET) else {}
        try:                                       # đường bộ nhớ đệm CapCut quy về MÁY ĐANG CHẠY (danh mục lập trên máy khác)
            from xuat.lap_preset import cache_may
        except Exception:
            sys.path.insert(0, HERE)
            from lap_preset import cache_may
        for ds in self.ds.values():
            for x in (ds if isinstance(ds, list) else []):
                if isinstance(x, dict) and x.get("path"):
                    x["path"] = cache_may(x["path"])
                    x["_co_san"] = os.path.exists(x["path"])
        self.ai = (kh or {}).get("capcut") if isinstance((kh or {}).get("capcut"), dict) else {}
        self.p_lich = os.path.join(DATA, "capcut-preset-gan-day.json")
        self.dung, self._luot = [], {}

    def _ten(self, khoa, mac_dinh):
        v = self.ai.get(khoa)
        if isinstance(v, list) and v:                  # AI ghi danh sách → xoay vòng theo thứ tự chữ xuất hiện
            i = self._luot.get(khoa, 0); self._luot[khoa] = i + 1
            return v[i % len(v)]
        return v if isinstance(v, str) and v else mac_dinh

    def _chon(self, nhom, ten):
        if not ten or str(ten).lower() in ("khong", "không", "none"):
            return None
        x = next((x for x in self.ds.get(nhom, []) if x.get("_co_san") and x.get("name") == ten), None)
        if x is not None:
            self.dung.append(x.get("resource_id"))
        return x

    def ten_co(self):
        return {k: sorted({x.get("name") for x in v if isinstance(x, dict) and x.get("_co_san") and x.get("name")})
                for k, v in self.ds.items() if isinstance(v, list)}

    def bo_phu_de(self):
        return self._chon("chu_vao", self._ten("phu_de_vao", self.TRUNG_TINH))

    def bo_chu(self):
        return self._chon("chu_vao", self._ten("chu_vao", self.TRUNG_TINH)), self._chon("chu_ra", self._ten("chu_ra", None))

    def ghi(self, du_an):
        if not self.dung:
            return
        lich = (C.doc(self.p_lich, []) or [])[-30:]
        lich.append({"du_an": os.path.basename(du_an), "ho_so": os.environ.get("HO_SO", ""), "dung": self.dung})
        C.ghi(self.p_lich, lich)


def anim_mat(bo, dai, vao=None, ra=None, d_vao=0.35, d_ra=0.3):
    """vật liệu hoạt ảnh chữ CapCut (vào ở đầu đoạn, ra ở cuối đoạn) — đúng khuôn project thật"""
    m = _aux("material_animations")
    an = []
    if vao:
        a = {k: v for k, v in vao.items() if not k.startswith("_")}
        dv = min(d_vao, dai * 0.4)
        a.update({"start": 0, "duration": US(dv)}); an.append(a)
    if ra:
        a = {k: v for k, v in ra.items() if not k.startswith("_")}
        dr = min(d_ra, dai * 0.3)
        a.update({"start": US(max(0.0, dai - dr)), "duration": US(dr)}); an.append(a)
    m["animations"] = an
    return bo.them("material_animations", m)


# ───────────────────────── chữ CapCut
def _hex(c):
    if isinstance(c, (list, tuple)):
        return "#%02X%02X%02X" % tuple(int(x) for x in c[:3])
    return c if isinstance(c, str) and c.startswith("#") else "#FFFFFF"


def _rgb01(h):
    h = _hex(h).lstrip("#")
    return [round(int(h[i:i + 2], 16) / 255, 4) for i in (0, 2, 4)]


def _co_capcut(px, W, H):
    """cỡ chữ CapCut từ chiều cao chữ (px ở khung W×H). Đo trên CapCut PC: 1 đơn vị ≈ 7 px ở cạnh ngắn 1080."""
    return max(4.0, round(px / (7.0 * min(W, H) / 1080.0), 2))


def _vien_phu_de(k2, kd, qd_pd, co_px):
    """1.2.21: viền phụ đề → (màu, bề rộng CapCut = px viền / cỡ chữ px). Thứ tự: lớp → ke-hoach.phu_de → quyết định kênh
    (ke-hoach.quyet_dinh.phu_de, A4 ghi). Không chỗ nào ghi viền → không viền (máy không tự thêm #000000 0.08 như trước)."""
    for nguon in (k2, kd, (qd_pd.get("kieu_dang") or {}), qd_pd):
        v = (nguon or {}).get("vien")
        if v is None:
            continue
        v0 = v[0] if isinstance(v, list) and v else (v if isinstance(v, dict) else None)
        if not v0 or not v0.get("mau") or float(v0.get("w") or 0) <= 0:
            return None, 0.0                                      # ghi rõ "không viền" ([] / {}) → tôn trọng
        return v0["mau"], round(max(0.01, min(0.5, float(v0["w"]) / max(co_px, 1.0))), 3)
    return None, 0.0


def text_mat(bo, chu, font, co, mau, vien=None, vien_rong=0.08, loai="text"):
    chu = chu.strip()
    n = len(chu.encode("utf-16-le")) // 2
    st = {"fill": {"content": {"render_type": "solid", "solid": {"color": _rgb01(mau)}}},
          "font": {"path": _posix(font) if font else "", "id": ""}, "size": float(co), "useLetterColor": True, "range": [0, n]}
    if vien:
        st["strokes"] = [{"content": {"render_type": "solid", "solid": {"color": _rgb01(vien)}}, "width": float(vien_rong)}]
    m = copy.deepcopy(MAU["mat"]["texts"])
    m.update({"id": _id(), "type": loai, "content": json.dumps({"text": chu, "styles": [st]}, ensure_ascii=False),
              "font_path": _posix(font) if font else "", "font_size": float(co), "text_color": _hex(mau),
              "border_color": _hex(vien) if vien else "", "border_width": float(vien_rong) if vien else 0.0,
              "font_id": "", "font_resource_id": "", "font_title": "none", "font_name": "", "fonts": [],
              "recognize_text": "", "base_content": "", "words": {"start_time": [], "end_time": [], "text": []},
              "current_words": {"start_time": [], "end_time": [], "text": []}, "alignment": 1, "typesetting": 0,
              "text_to_audio_ids": [], "check_flag": 7, "add_type": 0, "preset_id": "", "text_preset_resource_id": ""})
    return bo.them("texts", m)


# ───────────────────────── dựng lại bối cảnh máy dựng (KHÔNG sửa loi.py — chép phần chuẩn bị)
def _dat_hop(bx0, by0, bx1, by1, W, H):
    """clip media đúng tỉ lệ hộp (bx…) → (scale, x, y) CapCut để hiện đúng hộp đó trên khung W×H"""
    bw, bh = bx1 - bx0, by1 - by0
    rong1 = W if bw / bh > W / H else H * bw / bh
    return bw / rong1, ((bx0 + bx1) / 2 - W / 2) / (W / 2), -((by0 + by1) / 2 - H / 2) / (H / 2)


# ───────────────────────── dựng clip đồ hoạ (trong suốt) + khung (đặc)
def _ve_lai_sprite(du_an):
    """A1 1.2.21: dung.dung(du_an, ke_hoach, giu_sprite=True) — vẽ lại PNG sprite đã dọn, KHÔNG dựng lại khúc; chạy ở tiến trình riêng
    (lõi v3 import `chung` của v3 — không nạp chung tiến trình với v2/chung). Lỗi → báo, vẫn xuất (lớp thiếu concat bị bỏ qua)."""
    ma = ("import sys, os, json; sys.path.insert(0, os.path.join(sys.argv[1], 'v3')); import chung; from dung import dung as D; "
          "da = sys.argv[2]; kh = chung.doc_json(os.path.join(da, 'ke-hoach.json'), {}) or {}; "
          "D.dung(da, kh, giu_sprite=True); print('SPRITE OK')")
    try:
        r = subprocess.run([C.python_skill(), "-c", ma, os.path.dirname(V2), du_an], cwd=os.path.dirname(V2), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=3600, env=dict(os.environ, PYTHONUTF8="1", STUDIO_KHONG_CAPCUT="1"),
                           creationflags=0x08000000 if WIN else 0)
        if "SPRITE OK" not in (r.stdout or ""):
            dong = ((r.stderr or r.stdout) or "").strip().splitlines()
            loi = (dong[-1] if dong else "không rõ")[:300]
            print("  ! vẽ lại sprite cho CapCut lỗi:", loi)
            return loi
        return None
    except Exception as e:
        print("  ! vẽ lại sprite cho CapCut lỗi:", e)
        return f"{type(e).__name__}: {e}"[:300]


def _hop_nguoi(vi_sn, W, H, le=0.15):
    """1.2.21 (B2): HỘP HỢP của các lớp sau người + lề `le` mỗi phía (theo rộng/cao hộp), kẹp trong khung, chẵn 2 px → [x0, y0, x1, y1]"""
    x0 = min(v[2]["hop"][0] for v in vi_sn); y0 = min(v[2]["hop"][1] for v in vi_sn)
    x1 = max(v[2]["hop"][2] for v in vi_sn); y1 = max(v[2]["hop"][3] for v in vi_sn)
    lx, ly = (x1 - x0) * le, (y1 - y0) * le
    x0 = max(0, int(x0 - lx) // 2 * 2); y0 = max(0, int(y0 - ly) // 2 * 2)
    x1 = min(int(W) // 2 * 2, int(math.ceil(x1 + lx)) // 2 * 2 + 2); y1 = min(int(H) // 2 * 2, int(math.ceil(y1 + ly)) // 2 * 2 + 2)
    return [x0, y0, max(x1, x0 + 2), max(y1, y0 + 2)]


def _clip_nguoi(du_an, thu, base, alpha_tl, tu, den, fps, hop=None):
    """1.2.21 (B2): NGƯỜI cắt từ base bằng mặt nạ alpha-tl (xám W×H, cùng dòng thời gian base) → <thu>/nguoi-<băm>.mov ProRes 4444
    (trong suốt ngoài người), CHỈ khoảng [tu, den] hợp của các lớp sau người (-ss/-t ở cả hai input, setpts về 0 → khớp khung như
    ghep.dung_khuc) và CHỈ trong hộp `hop` [x0, y0, x1, y1] (hộp hợp lớp sau người + lề — ngoài hộp đã là base nên không cần; ~−90 % MB
    so với toàn khung). Tên theo băm NỘI DUNG base + alpha-tl + khoảng + hộp + fps (cache). → (đường|None, tu, den, lỗi|None)"""
    ib, ia = (C.ffprobe(base) or {}), (C.ffprobe(alpha_tl) or {})
    het = min(float(ib.get("dai") or 0), float(ia.get("dai") or 0))
    tu = max(0.0, float(tu))
    den = min(float(den), het) if het > 0 else float(den)
    dai = den - tu
    if dai <= 1.0 / max(float(fps), 1.0):
        return None, tu, den, "khoảng lớp sau người nằm ngoài base / alpha-tl"
    W, H = int(ib.get("w") or 0), int(ib.get("h") or 0)
    hop = [int(v) for v in hop] if hop else None
    cw, ch = (hop[2] - hop[0], hop[3] - hop[1]) if hop else (0, 0)
    if hop and (cw < 2 or ch < 2):
        return None, tu, den, f"hộp người không hợp lệ {hop}"
    bam = hashlib.sha256(f"{_bam_tep(base)}|{_bam_tep(alpha_tl)}|{tu:.3f}|{den:.3f}|{hop}|{fps}|v2".encode("utf-8")).hexdigest()[:10]
    dich = os.path.join(thu, f"nguoi-{bam}.mov")
    if not (os.path.exists(dich) and os.path.getsize(dich) > 1000):
        cat = f",crop={cw}:{ch}:{hop[0]}:{hop[1]}" if hop else ""
        fc = (f"[0:v]setpts=PTS-STARTPTS,fps={fps}{cat},format=rgba[b];"
              f"[1:v]setpts=PTS-STARTPTS,fps={fps},format=gray" + (f",scale={W}:{H}:flags=neighbor" if W and H else "") + f"{cat}[a];"
              "[b][a]alphamerge,format=yuva444p10le[v]")
        ma, err = _chay_ffmpeg(["-ss", f"{tu:.3f}", "-t", f"{dai:.3f}", "-i", base, "-ss", f"{tu:.3f}", "-t", f"{dai:.3f}", "-i", alpha_tl,
                                "-filter_complex", fc, "-map", "[v]", "-an", "-t", f"{dai:.3f}",
                                "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0", "-alpha_bits", "8", dich],
                               du_an, "capcut-nguoi", dai)
        if ma or not os.path.exists(dich) or os.path.getsize(dich) <= 1000:
            try:
                os.remove(dich)
            except OSError:
                pass
            return None, tu, den, (err or "ffmpeg lỗi").strip()[-300:]
    return dich, tu, den, None


def xuat_v3(du_an, ten=None, do_hoa=True):
    """1.3: dự án dựng bằng lõi mới (v3) → project CapCut: video nền (đã cắt + camera + nền mới) · mỗi lớp chữ/thẻ/hình một clip
    TRONG SUỐT đúng hộp (khớp từng điểm ảnh bản MP4) · phụ đề = CHỮ CAPCUT THẬT (sửa trực tiếp) · âm thanh đã trộn."""
    t_bd = time.time()
    p_kq = os.path.join(du_an, "dung", "ket-qua-dung.json")
    if not os.path.isfile(p_kq):
        raise SystemExit("dự án lõi 1.3 chưa có kết quả dựng (dung/ket-qua-dung.json) — dựng xong (nhanh tron) mới xuất CapCut")
    loi_sprite = None
    if do_hoa:
        loi_sprite = _ve_lai_sprite(du_an)                    # A1 1.2.21: sprite PNG bị dọn ngay sau khúc → vẽ lại (không dựng lại khúc); R3: gọi TRƯỚC khi đọc ket-qua-dung.json (dung.dung ghi lại tệp này)
    kq = C.doc(p_kq, {}) or {}
    if not kq.get("lop") and not kq.get("base"):
        raise SystemExit("dự án lõi 1.3 chưa có kết quả dựng (dung/ket-qua-dung.json) — dựng xong (nhanh tron) mới xuất CapCut")
    kh = C.doc(os.path.join(du_an, "ke-hoach.json"), {}) or {}
    W, H = int(kq.get("W") or 1080), int(kq.get("H") or 1920)
    fps = int(round(float(kq.get("fps") or 30)))
    ban = os.path.join(du_an, "dung", "thanh-pham.mp4")
    dur = float(kq.get("dur") or (C.ffprobe(ban) or {}).get("dai") or 0)
    mau = None if LINUX else tim_mau()                       # 1.2.21: Linux không có CapCut → chỉ gói tách lớp
    if LINUX:
        print("  ! CapCut không có bản Linux — không ghi project, chỉ ra gói tách lớp (7-capcut/HUONG-DAN.txt) cho Kdenlive/Resolve.")
    bo = Bo()
    ra_dir = os.path.join(du_an, "7-capcut"); os.makedirs(ra_dir, exist_ok=True)
    bao = {"du_an": du_an, "khung": [W, H], "fps": fps, "dur": round(dur, 3), "track": {}, "loi": "1.3"}
    preset = Preset(du_an, kh) if isinstance(kh.get("capcut"), dict) else None    # 1.2.21: hoạt ảnh chữ CapCut do AI chọn (nếu có)
    qd_pd = ((kh.get("quyet_dinh") or {}).get("phu_de") or {})                    # 1.2.21: quyết định kênh (A4 ghi) — viền phụ đề
    dung_mov = set()
    # 1) video nền
    base = kq.get("base")
    if base and os.path.exists(base):
        info = C.ffprobe(base)
        mid = bo.video_mat(base, dict(info, co_am=False))
        bo.track("video", "Video (đã cắt + camera + nền)", [_seg("video", mid, bo.refs_video(), 0, min(dur, info["dai"]), src0=0,
                                                                   src_dai=min(dur, info["dai"]), am=0.0, clip=_clip())])
    # 2) lớp đồ hoạ — clip trong suốt
    vi = []
    thu = os.path.join(ra_dir, "do-hoa"); os.makedirs(thu, exist_ok=True)
    thieu_sprite = []                                         # R3 1.2.21: lớp đồ hoạ không có concat/sprite → ĐẾM + báo, không bỏ lặng lẽ
    for L in (kq.get("lop") or []) if do_hoa else []:        # 1.2.21: --khong-do-hoa thật sự bỏ clip đồ hoạ (trước bị bỏ qua)
        m = L.get("meta") or {}
        if L.get("truc_tiep") and m.get("duong") and os.path.exists(m["duong"]):
            # 1.3: video/ảnh phủ trực tiếp (B-roll, nền động, ánh sáng) → clip đúng hộp, độ trong suốt giữ ở CapCut
            dai = float(m["t1"]) - float(m["t0"]); w2, h2 = int(m["w"]) // 2 * 2, int(m["h"]) // 2 * 2
            try:                                                  # 1.2.21: tên theo băm nguồn + tham số (không theo mtime)
                st_ = os.stat(m["duong"]); khoa_n = f"{st_.st_size}|{int(st_.st_mtime)}"
            except OSError:
                khoa_n = "?"
            bam_tt = hashlib.sha256(json.dumps([m["duong"], khoa_n, m.get("a"), m.get("toc_do"), m.get("fit"), m.get("lap"), w2, h2, round(dai, 3), fps],
                                               sort_keys=True).encode("utf-8")).hexdigest()[:10]
            dich = os.path.join(thu, f"{re.sub(r'[^A-Za-z0-9_-]+', '-', str(m.get('id')))}-{int(float(m['t0']) * 1000)}-{bam_tt}-tt.mov")
            if not (os.path.exists(dich) and os.path.getsize(dich) > 1000):
                anh = (m.get("loai_nguon") == "anh") or m["duong"].lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
                toc = float(m.get("toc_do") or 1.0)
                vao = (["-loop", "1"] if anh else (["-stream_loop", "-1"] if m.get("lap") else []) + ["-ss", f"{float(m.get('a') or 0):.3f}"])
                if m.get("fit") == "contain":
                    vf = f"scale={w2}:{h2}:force_original_aspect_ratio=decrease,format=yuva444p10le,pad={w2}:{h2}:(ow-iw)/2:(oh-ih)/2:color=black@0"
                else:
                    vf = f"scale={w2}:{h2}:force_original_aspect_ratio=increase,crop={w2}:{h2},format=yuva444p10le"
                vf = (f"setpts=PTS/{toc}," if (not anh and abs(toc - 1) > 1e-3) else "") + vf + f",fps={fps}"
                ma, err = _chay_ffmpeg([*vao, "-i", m["duong"], "-an", "-vf", vf, "-t", f"{dai:.3f}",
                                        "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0", "-alpha_bits", "8", dich],
                                       du_an, f"capcut-phu-{m.get('id')}", dai)      # 1.2.21: đồng bộ -alpha_bits 8 với lớp concat
                if ma or not os.path.exists(dich):
                    print(f"  ! đóng gói lớp phủ {m.get('id')} lỗi: {err[-200:]}"); continue
            dung_mov.add(os.path.basename(dich))
            x0, y0 = float(m["x"]), float(m["y"])
            ht = m.get("hoa_tron") or "normal"
            if ht != "normal":
                bao.setdefault("ghi_chu", []).append(f"lớp {m.get('id')}: hoà trộn `{ht}` — đặt lại Blend trong CapCut nếu cần (project để Normal)")
            vi.append((float(m["t0"]), float(m["t1"]), {"file": dich, "hop": [x0, y0, x0 + w2, y0 + h2], "id": m.get("id"),
                                                        "alpha": float(m.get("do_trong") if m.get("do_trong") is not None else 1.0)}))
            continue
        if L.get("phu_de"):
            continue
        if not m.get("concat") or not os.path.exists(m["concat"]):
            thieu_sprite.append(str(m.get("id") or L.get("id") or "?")); continue
        # 1.2.21: tên .mov theo BĂM NỘI DUNG concat (danh sách khung sprite) — sửa khung là tên mới, không còn cache sai theo mtime
        dich = os.path.join(thu, f"{re.sub(r'[^A-Za-z0-9_-]+', '-', str(m.get('id')))}-{int(float(m['t0']) * 1000)}-{_bam_tep(m['concat'])}.mov")
        if not (os.path.exists(dich) and os.path.getsize(dich) > 1000):
            w2, h2 = int(m["w"]) // 2 * 2, int(m["h"]) // 2 * 2
            dai_l = float(m["t1"]) - float(m["t0"])
            ma, err = _chay_ffmpeg(["-f", "concat", "-safe", "0", "-i", m["concat"], "-vf", f"fps={fps},crop={w2}:{h2}:0:0",
                                    "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le", "-vendor", "apl0", "-alpha_bits", "8",
                                    "-t", f"{dai_l:.3f}", dich], du_an, f"capcut-lop-{m.get('id')}", dai_l)
            if ma or not os.path.exists(dich):
                print(f"  ! đóng gói lớp {m.get('id')} lỗi: {err[-200:]}"); continue
        dung_mov.add(os.path.basename(dich))
        x0, y0 = float(m["x"]), float(m["y"])
        vi.append((float(m["t0"]), float(m["t1"]), {"file": dich, "hop": [x0, y0, x0 + int(m["w"]) // 2 * 2, y0 + int(m["h"]) // 2 * 2], "id": m.get("id"),
                                                    "sn": bool(L.get("sau_nguoi"))}))      # 1.2.21 (B2): lớp sau người → track dưới clip người
    if thieu_sprite or loi_sprite:                            # R3 1.2.21: báo rõ, ghi capcut.json, vẫn xuất phần có
        ly_do = ("dự án dựng bằng bản cũ (chưa có quyết định kênh / sprite đã bị dọn) — chạy `nhanh tron` lại trước khi xuất CapCut"
                 if (loi_sprite and "thieu_truong" in loi_sprite.lower()) or thieu_sprite else "vẽ lại sprite lỗi")
        bao["loi_xuat"] = {"lop_thieu_sprite": thieu_sprite, "so_lop_thieu": len(thieu_sprite), "ve_lai_sprite": loi_sprite, "ly_do": ly_do}
        if thieu_sprite:
            print(f"  ! THIẾU {len(thieu_sprite)} lớp đồ hoạ trong project CapCut (không có sprite): {', '.join(thieu_sprite[:8])}"
                  + (" …" if len(thieu_sprite) > 8 else "") + f" — {ly_do}")
        else:
            print(f"  ! vẽ lại sprite lỗi nhưng mọi lớp còn sprite cũ — {ly_do}")
    # 1.2.21 (B2): lớp SAU NGƯỜI — sprite không nướng mặt nạ (B1) → project CapCut cần clip "người cắt từ base" (base × alpha-tl) nằm TRÊN
    # các lớp sau người và DƯỚI lớp thường + phụ đề. Không có alpha-tl → lớp sau người xếp như lớp thường + cảnh báo loi_xuat.sau_nguoi.
    vi_sn = [v for v in vi if v[2].get("sn")]
    nguoi = None
    if vi_sn:
        alpha_tl = kq.get("alpha_tl")
        ids_sn = [str(v[2].get("id")) for v in vi_sn]
        if alpha_tl and os.path.isfile(alpha_tl) and base and os.path.exists(base):
            hop_ng = _hop_nguoi(vi_sn, W, H)                      # hộp hợp lớp sau người + lề 15 % (như ghep.dung_khuc, thêm lề)
            p_ng, tu_ng, den_ng, loi_ng = _clip_nguoi(du_an, thu, base, alpha_tl, min(v[0] for v in vi_sn), max(v[1] for v in vi_sn), fps, hop=hop_ng)
            if p_ng:
                nguoi = {"mov": p_ng, "tu": round(tu_ng, 3), "den": round(den_ng, 3), "mb": round(os.path.getsize(p_ng) / 1e6, 1), "hop": hop_ng}
                dung_mov.add(os.path.basename(p_ng))
                print(f"  người (cắt từ base) cho {len(vi_sn)} lớp sau người: {os.path.basename(p_ng)} {nguoi['tu']:.2f}→{nguoi['den']:.2f}s"
                      f" · hộp {hop_ng} · {nguoi['mb']} MB")
        else:
            loi_ng = "dự án không có mặt nạ người (ket-qua-dung.json thiếu alpha_tl hoặc tệp đã bị dọn)"
        if not nguoi:
            bao.setdefault("loi_xuat", {})["sau_nguoi"] = {
                "lop": ids_sn, "ly_do": loi_ng,
                "hau_qua": "chữ sau người sẽ ĐÈ lên người trong project CapCut (xếp như lớp thường) — dựng lại (nhanh tron) để có alpha-tl rồi xuất lại"}
            print(f"  ! {len(vi_sn)} lớp sau người KHÔNG có clip người ({loi_ng}) → xếp như lớp thường, chữ sẽ đè lên người: {', '.join(ids_sn[:8])}")
            for _, _, v in vi_sn:
                v["sn"] = False
            vi_sn = []
    k = 0                                                     # chỉ số render chung: cao hơn = nằm trên

    def _track_do_hoa(ds, ten_goc):
        nonlocal k
        for i, tr in enumerate(_chia_track(ds)):
            segs = []
            for t0, t1, v in tr:
                info = C.ffprobe(v["file"])
                mid = bo.video_mat(v["file"], dict(info, co_am=False))
                sc, x, y = _dat_hop(*v["hop"], W, H)
                sg = _seg("video", mid, bo.refs_video(), t0, t1 - t0, src0=0, src_dai=t1 - t0, am=0.0, clip=_clip(sc, x, y, v.get("alpha", 1.0)), render=2 + k, track_render=2 + k)
                sg["desc"] = str(v["id"]); segs.append(sg)
            bo.track("video", f"{ten_goc} {i + 1}", segs); k += 1
    _track_do_hoa(vi_sn, "Sau người")
    if nguoi:
        info = C.ffprobe(nguoi["mov"]) or {}
        dai_ng = nguoi["den"] - nguoi["tu"]
        if float(info.get("dai") or 0) > 0:
            dai_ng = min(dai_ng, float(info["dai"]))
        mid = bo.video_mat(nguoi["mov"], dict(info, co_am=False))
        sc, x, y = _dat_hop(*nguoi["hop"], W, H)                  # clip chỉ là vùng hộp → đặt đúng chỗ như lớp đồ hoạ
        sg = _seg("video", mid, bo.refs_video(), nguoi["tu"], dai_ng, src0=0, src_dai=dai_ng, am=0.0, clip=_clip(sc, x, y), render=2 + k, track_render=2 + k)
        sg["desc"] = "nguoi"
        bo.track("video", "Người (cắt từ base)", [sg]); k += 1
        bao["nguoi"] = dict(nguoi)
    _track_do_hoa([v for v in vi if not v[2].get("sn")], "Đồ hoạ")
    bao["track"]["do_hoa"] = len(vi)
    bao["track"]["sau_nguoi"] = len(vi_sn)
    bao["track"]["nguoi"] = 1 if nguoi else 0
    # 3) phụ đề — chữ CapCut thật
    pd = kh.get("phu_de") or {}
    kd = pd.get("kieu_dang") or {}
    font_pd = kd.get("font_duong")
    segs = []
    for L in kq.get("lop") or []:
        m = L.get("meta") or {}
        if not L.get("phu_de") or not L.get("text"):
            continue
        k2 = L.get("kieu_dang") or kd
        chu = str(L["text"]).upper() if k2.get("hoa") else str(L["text"])
        co_px = float(k2.get("co") or kd.get("co") or (qd_pd.get("kieu_dang") or {}).get("co") or 58)
        vien_mau, vien_rong = _vien_phu_de(k2, kd, qd_pd, co_px)           # 1.2.21: viền từ lớp / quyết định kênh, không hằng
        mid = text_mat(bo, chu, k2.get("font_duong") or font_pd, _co_capcut(co_px, W, H), k2.get("mau") or "#FFFFFF",
                       vien=vien_mau, vien_rong=vien_rong, loai="subtitle")
        yc = float(m["y"]) + float(m["h"]) / 2
        dai_pd = float(m["t1"]) - float(m["t0"])
        vao_pd = preset.bo_phu_de() if preset else None                      # 1.2.21: hoạt ảnh phụ đề AI chọn (ke-hoach.capcut.phu_de_vao)
        segs.append(_seg("text", mid, [anim_mat(bo, dai_pd, vao_pd, None)], float(m["t0"]), dai_pd,
                         clip=_clip(1.0, 0.0, -(yc - H / 2) / (H / 2)), render=14000, track_render=0))
    bo.track("text", "Phụ đề (sửa chữ trực tiếp)", segs)
    bao["track"]["phu_de"] = len(segs)
    if preset:
        bao["preset"] = {"phu_de_vao": preset.ai.get("phu_de_vao"), "dung": preset.dung[:1], "co": preset.ten_co().get("chu_vao", [])[:30]}
        preset.ghi(du_an)
    # 4) âm thanh đã trộn (giọng + nhạc + SFX)
    if os.path.exists(ban):
        wav = os.path.join(ra_dir, "am-thanh.wav")
        if not (os.path.exists(wav) and os.path.getmtime(wav) >= os.path.getmtime(ban)):
            _chay_ffmpeg(["-i", ban, "-vn", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", wav], du_an, "capcut-am", dur)
        if os.path.exists(wav):
            mid = bo.audio_mat(wav, dur)
            bo.track("audio", "Âm thanh (giọng + nhạc + SFX đã trộn)", [_seg("audio", mid, bo.refs_audio(), 0, dur, src0=0, src_dai=dur, am=1.0)])
    ten = ten or os.path.basename(du_an)
    try:                                                     # 1.2.19: gói tách lớp luôn kèm (đường lùi cho CapCut 10.x / phần mềm khác)
        bao["tach_lop"] = goi_tach_lop(ra_dir, kq, vi, W, H, fps, dur, nguoi=nguoi)      # 1.2.21 (B2): kèm nguoi-*.mov (Linux cũng có)
    except Exception as e:
        print("  ! gói tách lớp lỗi:", e)
    # 1.2.21: .mov không còn dùng (khung đổi → băm đổi) xoá ngay; ghi .da-xuat để studio/don_rac.py (A2) dọn do-hoa/ sau khi khách xác nhận
    xoa_mb = 0.0
    for f in (os.listdir(thu) if do_hoa else []):            # --khong-do-hoa: không đụng .mov đã có
        if f.lower().endswith(".mov") and f not in dung_mov:
            try:
                xoa_mb += os.path.getsize(os.path.join(thu, f)) / 1e6; os.remove(os.path.join(thu, f))
            except OSError:
                pass
    if xoa_mb:
        print(f"  xoá {xoa_mb:.0f} MB clip đồ hoạ cũ không còn dùng")
    if LINUX:
        ra = None
    else:
        ra = ghi_project(mau, bo, ten, W, H, fps, dur, du_an)
    try:
        C.ghi(os.path.join(ra_dir, ".da-xuat"), {"luc": int(time.time()), "project": ra, "do_hoa": sorted(dung_mov),
                                                 "mb": round(sum(os.path.getsize(os.path.join(thu, f)) for f in dung_mov if os.path.exists(os.path.join(thu, f))) / 1e6, 1),
                                                 "ghi_chu": "do-hoa/*.mov tái tạo được bằng `st.py capcut` — dọn rác được xoá sau khi khách xác nhận project mở tốt"})
    except Exception:
        pass
    bao.update({"project": ra, "ten": os.path.basename(ra) if ra else None, "giay": round(time.time() - t_bd), "capcut_dang_mo": capcut_dang_mo(),
                "ban_capcut": phien_ban_capcut(), "ban_mau": _ban_cua_project(mau) if mau else "", "goi_tach_lop": ra_dir})
    C.ghi(os.path.join(ra_dir, "capcut.json"), bao)
    if LINUX:
        print(f"XONG GÓI TÁCH LỚP {ra_dir} (CapCut không hỗ trợ Linux — không có project)")
        return bao
    print(f"XONG CAPCUT {ra}")
    print("  track: " + ", ".join(f"{k} {v}" for k, v in bao["track"].items()) + f" · {bao['giay']}s")
    print(f"  CapCut đang cài: {bao['ban_capcut'] or '?'} · mẫu gieo: {bao['ban_mau'] or '?'} · gói tách lớp: {ra_dir}")
    if bao["ban_capcut"] and not _cung_dong(bao["ban_capcut"], bao["ban_mau"]):
        print("  ! LỆCH BẢN: mẫu gieo khác bản CapCut đang cài — nếu CapCut từ chối mở, tạo một dự án trống trong CapCut, thoát, xuất lại; hoặc dùng gói tách lớp (HUONG-DAN.txt).")
    for g in bao.get("ghi_chu") or []:
        print("  ·", g)
    if bao["capcut_dang_mo"]:
        print("  CapCut đang mở → THOÁT hẳn CapCut rồi mở lại để thấy project mới.")
    return bao


def xuat(du_an, ten=None, do_hoa=True):
    """1.3: chỉ còn dự án dựng bằng lõi mới (dung/ket-qua-dung.json)"""
    return xuat_v3(os.path.abspath(du_an), ten, do_hoa)


def _bia(du_an):
    c = C.doc(os.path.join(du_an, "6-bia", "chon.json"), {}) or {}
    for p in [c.get("file") and os.path.join(du_an, "6-bia", os.path.basename(c["file"]))] + sorted(
            glob.glob(os.path.join(du_an, "6-bia", "bia-*.png"))) + sorted(glob.glob(os.path.join(du_an, "dung", "bia-*.png"))):
        if p and os.path.exists(p):
            return p
    return None


def ghi_project(mau, bo, ten, W, H, fps, dur, du_an):
    goc = goc_capcut()
    os.makedirs(goc, exist_ok=True)
    tien_to = _cau_hinh("capcut", "tien_to", mac_dinh="Studio") or "Studio"
    sach = re.sub(r'[\\/:*?"<>|]+', " ", f"{tien_to} {ten}").strip()[:80]
    dich, n = os.path.join(goc, sach), 2
    while os.path.exists(dich):
        dich = os.path.join(goc, f"{sach} ({n})"); n += 1
    shutil.copytree(mau, dich, ignore=_chi_cau_hinh)          # 1.2.21: mẫu cũ (chép trọn project khách) cũng chỉ lấy phần cấu hình
    open(os.path.join(dich, "_studio_xuat"), "w", encoding="utf-8").write("project do Studio xuất — không dùng làm mẫu gieo")
    # id mới (project, timeline, draft) — không trùng project mẫu
    nd_mau = _noi_dung_mau(mau)
    tl_cu = nd_mau["id"]
    pj = C.doc(os.path.join(dich, "Timelines", "project.json"), {}) or {}
    pj_cu = pj.get("id")
    meta = C.doc(os.path.join(dich, "draft_meta_info.json"), {}) or {}
    dr_cu = meta.get("draft_id")
    tl, pj_moi, dr = _id(), _id(), _id()
    thay = {k: v for k, v in ((tl_cu, tl), (pj_cu, pj_moi), (dr_cu, dr)) if k}
    if os.path.isdir(os.path.join(dich, "Timelines", tl_cu)):
        os.rename(os.path.join(dich, "Timelines", tl_cu), os.path.join(dich, "Timelines", tl))
    for r, _, fs in os.walk(dich):
        for f in fs:
            p = os.path.join(r, f)
            if os.path.getsize(p) > 8_000_000 or not f.endswith((".json", ".tmp", ".bak", "draft_settings")):
                continue
            try:
                s = open(p, encoding="utf-8").read()
            except Exception:
                continue
            s2 = s
            for a, b in thay.items():
                s2 = s2.replace(a, b)
            if s2 != s:
                open(p, "w", encoding="utf-8").write(s2)
    # nội dung
    nd = copy.deepcopy(nd_mau)
    nd["id"] = tl
    nd["tracks"] = bo.tracks
    nd["materials"] = {k: ([] if isinstance(v, list) else v) for k, v in nd["materials"].items()}
    for k, v in bo.mat.items():
        nd["materials"][k] = v
    nd["duration"] = US(dur)
    nd["fps"] = float(fps)
    # 1.2.21: mọi tham chiếu id của project mẫu phải rỗng — keyframes/relationships/extra_info trỏ id vật liệu đã bị thay → CapCut treo/từ chối
    kf = nd.get("keyframes")
    nd["keyframes"] = {k: [] for k in kf} if isinstance(kf, dict) else []
    nd["relationships"] = []
    nd["extra_info"] = None
    nd["canvas_config"] = {**(nd.get("canvas_config") or {}), "width": int(W), "height": int(H),
                           "ratio": "9:16" if abs(W / H - 9 / 16) < 0.01 else ("16:9" if abs(W / H - 16 / 9) < 0.01 else "original")}
    nd["create_time"] = nd["update_time"] = int(time.time())
    co_tl = os.path.isdir(os.path.join(mau, "Timelines"))        # 1.2.19: CapCut 9.7 bố cục phẳng (không Timelines/) → không tạo thêm thư mục lạ
    for p in [os.path.join(dich, "draft_content.json"), os.path.join(dich, "template-2.tmp"), os.path.join(dich, "template.tmp")] + ([
              os.path.join(dich, "Timelines", tl, "draft_content.json"), os.path.join(dich, "Timelines", tl, "template-2.tmp"),
              os.path.join(dich, "Timelines", tl, "template.tmp")] if co_tl else []):
        if os.path.exists(p) or p.endswith("draft_content.json"):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            _ghi_json(p, nd)
    for p in glob.glob(os.path.join(dich, "**", "*.bak"), recursive=True):
        if os.path.basename(p).startswith("draft_content"):
            _ghi_json(p, nd)
    # ảnh bìa
    b = _bia(du_an)
    if b:
        try:
            from PIL import Image
            im = Image.open(b).convert("RGB"); im.thumbnail((720, 1280))
            for p in [os.path.join(dich, "draft_cover.jpg")] + ([os.path.join(dich, "Timelines", tl, "draft_cover.jpg")] if co_tl else []):
                im.save(p, quality=88)
        except Exception as e:
            print("  ! không gắn được ảnh bìa:", e)
    # meta
    bay = int(time.time() * 1_000_000)
    ten_tm = os.path.basename(dich)
    # 1.2.21: draft_root_path cũng posix (trước giữ backslash trong khi mọi trường khác posix — rà soát #18); draft_materials của
    # project mẫu (vật liệu khách đã nhập) rỗng hoá — chỉ còn khung {type, value: []}
    dm = meta.get("draft_materials")
    meta["draft_materials"] = ([{"type": x.get("type", i), "value": []} for i, x in enumerate(dm) if isinstance(x, dict)]
                               if isinstance(dm, list) else [{"type": t, "value": []} for t in (0, 1, 2, 3, 6, 7, 8)])
    meta["draft_materials_copied_info"] = []
    meta.update({"draft_id": dr, "draft_name": ten_tm, "draft_fold_path": _posix(dich), "draft_root_path": _posix(goc),
                 "tm_duration": US(dur), "tm_draft_create": bay, "tm_draft_modified": bay, "draft_cover": "draft_cover.jpg",
                 "draft_timeline_materials_size_": sum(os.path.getsize(m["path"]) for m in bo.mat.get("videos", []) + bo.mat.get("audios", [])
                                                       if os.path.exists(m["path"]))})
    _ghi_json(os.path.join(dich, "draft_meta_info.json"), meta)
    # đăng ký vào danh sách project của CapCut (CapCut đang mở sẽ ghi đè file này khi thoát → khi đó chỉ cần mở lại CapCut)
    if not capcut_dang_mo():
        try:
            p = os.path.join(goc, "root_meta_info.json")
            r = C.doc(p, {}) or {"all_draft_store": [], "draft_ids": 0, "root_path": goc}
            r.setdefault("all_draft_store", [])
            mau_e = copy.deepcopy(r["all_draft_store"][0]) if r["all_draft_store"] else {}
            mau_e.update({"draft_cover": _posix(os.path.join(dich, "draft_cover.jpg")), "draft_fold_path": _posix(dich),
                          "draft_id": dr, "draft_json_file": _posix(os.path.join(dich, "draft_content.json")),
                          "draft_name": ten_tm, "draft_root_path": _posix(goc), "tm_draft_create": bay, "tm_draft_modified": bay,
                          "tm_duration": US(dur), "draft_is_invisible": False, "cloud_draft_sync": False,
                          "draft_timeline_materials_size": meta["draft_timeline_materials_size_"]})
            r["all_draft_store"].insert(0, mau_e)
            r["draft_ids"] = int(r.get("draft_ids", 0)) + 1
            _ghi_json(p, r)
        except Exception as e:
            print("  ! chưa đăng ký được vào danh sách CapCut (mở CapCut vẫn tự quét):", e)
    return dich


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("du_an")
    ap.add_argument("--ten")
    ap.add_argument("--khong-do-hoa", action="store_true")
    a = ap.parse_args()
    xuat(a.du_an, a.ten, do_hoa=not a.khong_do_hoa)


if __name__ == "__main__":
    main()
