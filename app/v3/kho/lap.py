# -*- coding: utf-8 -*-
"""Lập chỉ mục kho tài nguyên (CHỈ ĐỌC kho gốc) → bảng `muc` trong kho-chi-muc/kho.sqlite (kho/csdl.py; 1.2.21) + chi-muc.json.
UPSERT từng mục đổi / xoá mục mất — không ghi lại cả tệp (trước 1.2.21: danh-muc.jsonl).

NHIỀU GỐC (cac_goc()): goi_kem = app/tai-nguyen (bộ miễn phí đi kèm) · bo_mua = cau-hinh kho.bo_mua ·
  rieng = kho.duong_dan (nếu khác gói kèm) · them-xxxx = v3.kho_them[] (thư mục khách tự thêm).
  Mỗi mục có "goc"; "rel" tương đối với gốc đó. id ổn định: bo_mua băm rel (tương thích chỉ mục cũ), gốc khác băm "goc:rel".
  File trùng (tên + cỡ) giữa các gốc chỉ lập 1 lần (gốc đứng trước thắng).
  Trường "ai" (gắn nghĩa, kho/gan_nghia.py) được giữ/gắn lại từ bảng ai_nghia mỗi lần lập.
lap_tep(duong_ds, goc_khoa, goc_duong, chi_muc_dir=None) → [mục]  chỉ lập/đo các TỆP cho trước (font tải về…) và upsert — không quét cả kho.

lap(kho_goc=None, chi_muc_dir, tien_do=None) → thống kê dict   (kho_goc=None → mọi gốc; chuỗi → 1 gốc kiểu bo_mua)
  - quét đệ quy, bỏ rác (.DS_Store, ._*, __MACOSX, .tmp/.bak/.zip/.rar/.url/.ini/.dat/.extra)
  - phân loại: nhac | sfx | font | lut | nen | icon | video | anh | preset_capcut | khac
  - đo: dur, w, h, lufs (nhạc 20 s đầu, ebur128), bpm (ước nhanh), peak (sfx), họ/đậm/nghiêng/variable/đủ dấu (font)
  - lập lại chỉ làm mục mới/đổi (so mtime + size); ThreadPool 6 luồng cho ffmpeg/ffprobe
  - xem trước nhanh (font/lut/icon/nen/preset) sinh ngay; nhạc/sfx sinh lười khi UI hỏi (xem_truoc.py)
"""
import os, sys, re, json, time, wave, hashlib, threading, unicodedata
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung
from kho import dong_nghia, csdl

NFC = chung.NFC
SO_LUONG = 6
PHIEN_BAN = 3            # đổi khi thay cách tạo từ khoá/nhóm → mục cũ được dựng lại từ khoá (không đo lại)
BO_TEN = {".ds_store", "thumbs.db", "desktop.ini"}
BO_DUOI = {".ds_store", ".tmp", ".bak", ".zip", ".rar", ".7z", ".url", ".ini", ".dat", ".extra", ".lnk", ".db", ".exe", ".dll", ".part"}
BO_THU_MUC = {"__macosx", ".git", "node_modules", "ban-do-kho", "xem-truoc", "cache-anh"}
DUOI_AM = {".wav", ".mp3", ".aac", ".m4a", ".ogg", ".flac", ".aiff", ".aif", ".wma"}
DUOI_FONT = {".ttf", ".otf", ".ttc"}
DUOI_FONT_WEB = {".woff", ".woff2"}
DUOI_LUT = {".cube", ".3dl"}
DUOI_ANH = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}
DUOI_VIDEO = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}
DUOI_LIGHTROOM = {".xmp", ".lrtemplate", ".dng"}
DUOI_TAI_LIEU = {".pdf", ".txt", ".md", ".doc", ".docx", ".rtf"}
NHAC_DAI = 25.0           # giây: ≥ → nhạc (khi thư mục không nói rõ)
TU_BO = {"utc", "the", "and", "of", "for", "version", "ver", "sec", "min", "cut", "mix", "full", "main", "mp3", "wav", "extra", "short",
         "reduced", "take", "vol", "pack", "update", "lan", "kho", "va", "ban", "quyen", "sound", "file", "copy", "new", "final", "v1", "v2"}
DAU_VIET = "ệởẳẫỡữđĐắộ"   # mã cần có trong cmap để coi là đủ dấu

_khoa = threading.Lock()


# ----------------------------------------------------------------------------- tiện ích
def _tokens(*phan):
    ra, seen = [], set()
    for s in phan:
        s = NFC(s or "")
        s = re.sub(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}", " ", s)       # bỏ dấu thời gian trong tên gói
        for t in dong_nghia.tach(s):
            if t in TU_BO or (t.isdigit() and len(t) > 2):
                continue
            if t not in seen:
                seen.add(t); ra.append(t)
    return ra


def _hash4(s):
    return hashlib.sha1(NFC(s).encode("utf-8")).hexdigest()[:4]


def _co(duong_thu_muc, *tu):
    """thư mục (bỏ dấu) có chứa 1 trong các từ (bỏ dấu)?"""
    s = chung.khong_dau(duong_thu_muc)
    return any(chung.khong_dau(t) in s for t in tu)


def _thu_muc_gan_nhat(rel_dir, bang):
    """xét từng cấp thư mục từ gần → xa; bang = [(nhãn, [từ...]), ...]; trả nhãn đầu tiên khớp hoặc None"""
    phan = [p for p in re.split(r"[\\/]+", rel_dir) if p]
    for p in reversed(phan):
        for nhan, tu in bang:
            if _co(p, *tu):
                return nhan
    return None


def _nhom(rel_dir):
    phan = [NFC(p) for p in re.split(r"[\\/]+", rel_dir) if p]
    phan = [p for p in phan if chung.khong_dau(p) not in ("mp3", "wav", "__macosx")]
    ra = []
    for p in reversed(phan[-3:]):
        ra.append(p)
    return ra[:2] if ra else []


def cac_goc():
    """→ [(khoá gốc, đường dẫn)] theo thứ tự ưu tiên khi trùng file. Đọc cau-hinh.json (kho.*, v3.kho_them)."""
    g = chung.doc_json(os.path.join(chung.SKILL, "cau-hinh.json"), {}) or {}
    kho = g.get("kho") or {}
    v3 = g.get("v3") or {}
    ra = []

    def them(k, p):
        if not p or not isinstance(p, str):
            return
        p = os.path.abspath(os.path.expanduser(p))
        if not os.path.isdir(p):
            return
        if any(os.path.normcase(p) == os.path.normcase(q) for _, q in ra):
            return
        ra.append((k, p))
    them("goi_kem", os.path.join(chung.SKILL, "tai-nguyen"))
    them("google", os.path.join(chung.duong("du_lieu"), "kho-them", "google-fonts"))      # font tải theo tên (kho/font_mang.py)
    them("bo_mua", kho.get("bo_mua"))
    them("rieng", kho.get("duong_dan"))
    for p in (v3.get("kho_them") or kho.get("them") or []):
        if isinstance(p, str) and p:
            them("them-" + _hash4(os.path.abspath(os.path.expanduser(p)).lower()), p)
    return ra


def _tao_id(loai, ten, rel, da_co, goc_khoa="bo_mua"):
    goc = f"{loai}.{chung.slug(ten, 40)}-{_hash4(rel if goc_khoa == 'bo_mua' else goc_khoa + ':' + rel)}"
    i, mid = 1, goc
    while mid in da_co:
        i += 1; mid = f"{goc}{i}"
    da_co.add(mid)
    return mid


def _ffprobe_video(p):
    ma, out, _ = chung.sh([chung.duong("ffprobe"), "-v", "error", "-print_format", "json", "-show_streams", "-show_format", p], timeout=60)
    if ma != 0:
        return None
    try:
        j = json.loads(out)
    except Exception:
        return None
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in j.get("streams", []) if s.get("codec_type") == "audio"), None)
    ra = {"dur": round(float(j.get("format", {}).get("duration") or 0), 2), "co_am": a is not None}
    if v:
        ra["w"], ra["h"] = int(v.get("width") or 0), int(v.get("height") or 0)
        rot = 0
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(float(sd["rotation"]))
        if rot % 180 == 90:
            ra["w"], ra["h"] = ra["h"], ra["w"]
        pf = v.get("pix_fmt") or ""
        ra["alpha"] = bool(re.search(r"^(yuva|rgba|bgra|argb|abgr|gbrap|ya)", pf)) or v.get("codec_name") in ("prores", "qtrle", "png") and "a" in pf
        num, _, den = (v.get("r_frame_rate") or "30/1").partition("/")
        try:
            ra["fps"] = round(float(num) / float(den or 1), 2)
        except Exception:
            pass
    return ra


def _dur_am(p, duoi):
    if duoi == ".wav":
        try:
            with wave.open(p) as w:
                fr = w.getframerate()
                if fr:
                    return round(w.getnframes() / fr, 3)
        except Exception:
            pass
    info = chung.ffprobe(p)
    return round(float(info["dur"]), 3) if info else None


def _bpm(pcm, sr=11025, hop=256):
    """ước BPM bằng autocorrelation của đường bao onset (20 s, mono 11 kHz) → int hoặc None"""
    try:
        import numpy as np
        x = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
        n = len(x) // hop
        if n < 200:
            return None
        env = np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1))
        onset = np.maximum(np.diff(env), 0)
        onset = onset - onset.mean()
        if not np.any(onset):
            return None
        ac = np.correlate(onset, onset, "full")[len(onset) - 1:]
        fps = sr / hop
        lo, hi = int(fps * 60 / 200), int(fps * 60 / 60)
        if hi >= len(ac):
            return None
        seg = ac[lo:hi]
        if seg.max() <= 0:
            return None
        lag = lo + int(np.argmax(seg))
        bpm = 60.0 * fps / lag
        # chuẩn về 70..180 (gấp đôi/một nửa)
        while bpm < 70:
            bpm *= 2
        while bpm > 180:
            bpm /= 2
        return int(round(bpm))
    except Exception:
        return None


def _do_nhac(p):
    """20 s đầu: ebur128 (LUFS) + PCM mono 11 kHz (BPM) trong 1 lệnh"""
    ff = chung.duong("ffmpeg")
    ma, out, err = _sh_bytes([ff, "-v", "info", "-nostats", "-t", "20", "-i", p, "-af", "ebur128", "-ac", "1", "-ar", "11025", "-f", "s16le", "-"], 90)
    ra = {}
    m = re.search(r"I:\s+(-?[\d.]+|-inf)\s+LUFS", err[err.rfind("Summary:"):] if "Summary:" in err else err)
    if m and m.group(1) != "-inf":
        ra["lufs"] = round(float(m.group(1)), 1)
    if out:
        b = _bpm(out)
        if b:
            ra["bpm"] = b
    return ra


def _do_sfx(p):
    ff = chung.duong("ffmpeg")
    ma, _, err = chung.sh([ff, "-v", "info", "-nostats", "-i", p, "-af", "astats=measure_perchannel=none:measure_overall=Peak_level+RMS_level", "-f", "null", "-"], timeout=90)
    ra = {}
    m = re.search(r"Peak level dB:\s*(-?[\d.]+|-inf)", err)
    if m and m.group(1) != "-inf":
        ra["peak"] = round(float(m.group(1)), 1)
    m = re.search(r"RMS level dB:\s*(-?[\d.]+|-inf)", err)
    if m and m.group(1) != "-inf":
        ra["rms"] = round(float(m.group(1)), 1)
    return ra


def _sh_bytes(cmd, timeout):
    import subprocess
    e = dict(os.environ); e.setdefault("PYTHONUTF8", "1")
    try:
        r = subprocess.run([str(c) for c in cmd], capture_output=True, timeout=timeout, env=e, creationflags=chung._NO_WINDOW)
        return r.returncode, r.stdout, r.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return 124, b"", ""


def _doc_font(p):
    from fontTools.ttLib import TTFont
    import logging
    logging.getLogger("fontTools").setLevel(logging.ERROR)
    tt = TTFont(p, lazy=True, fontNumber=0)
    try:
        cmap = tt.getBestCmap() or {}
        du = all(ord(c) in cmap for c in DAU_VIET)
        os2 = tt["OS/2"] if "OS/2" in tt else None
        dam = int(os2.usWeightClass) if os2 else 400
        nghieng = bool(os2.fsSelection & 1) if os2 else False
        try:
            ho = NFC(tt["name"].getBestFamilyName() or "")
            kieu = NFC(tt["name"].getBestSubFamilyName() or "")
        except Exception:
            ho, kieu = "", ""
        if not nghieng and re.search(r"italic|oblique", kieu, re.I):
            nghieng = True
        var = "fvar" in tt
        truc = []
        if var:
            try:
                truc = [a.axisTag for a in tt["fvar"].axes]
            except Exception:
                pass
        so_glyph = len(cmap)
    finally:
        tt.close()
    return {"ho": ho.strip(), "kieu": kieu.strip(), "dam": dam, "nghieng": nghieng, "var": var, "truc": truc, "du_dau": du, "so_ky_tu": so_glyph}


def _doc_anh(p):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(p) as im:
        w, h = im.size
        alpha = im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)
    return {"w": w, "h": h, "alpha": bool(alpha)}


# ----------------------------------------------------------------------------- quét
def _quet(kho_goc, goc="bo_mua"):
    """→ danh sách ứng viên {"duong","rel","rel_dir","ten","duoi","size","mtime","loai","phu":{},"goc"}"""
    ra = []
    kho_goc = os.path.abspath(kho_goc)
    for root, ds, fs in os.walk(kho_goc):
        ds[:] = sorted(d for d in ds if chung.khong_dau(d) not in BO_THU_MUC and not d.startswith("._"))
        fs_set = set(fs)
        rel_dir = os.path.relpath(root, kho_goc)
        rel_dir = "" if rel_dir == "." else rel_dir
        # ---- dự án CapCut: thư mục gốc có draft_meta_info.json → chỉ đi vào subdraft
        if "draft_meta_info.json" in fs_set and "draft_content.json" in fs_set:
            ds[:] = [d for d in ds if d.lower() == "subdraft"]
            if not ds:   # không có subdraft: coi cả dự án là 1 preset
                _them_preset(ra, root, kho_goc, rel_dir, os.path.basename(root), fs_set)
            continue
        # ---- subdraft CapCut: 1 preset / thư mục
        if "sub_draft_config.json" in fs_set and "draft_content.json" in fs_set:
            ten = os.path.basename(root)
            try:
                cfg = chung.doc_json(os.path.join(root, "sub_draft_config.json"), {}) or {}
                ten = NFC(cfg.get("name") or ten)
            except Exception:
                pass
            _them_preset(ra, root, kho_goc, rel_dir, ten, fs_set)
            ds[:] = []
            continue
        for f in sorted(fs):
            if f.startswith("._") or f.lower() in BO_TEN:
                continue
            ten_goc, duoi = os.path.splitext(f)
            duoi = duoi.lower()
            if duoi in BO_DUOI or duoi == "":
                continue
            p = os.path.join(root, f)
            try:
                st = os.stat(p)
            except OSError:
                continue
            loai, phu = _phan_loai_so_bo(duoi, rel_dir, st.st_size)
            if not loai:
                continue
            ra.append({"duong": p, "rel": os.path.relpath(p, kho_goc), "rel_dir": rel_dir, "ten": NFC(ten_goc), "duoi": duoi,
                       "size": st.st_size, "mtime": int(st.st_mtime), "loai": loai, "phu": phu, "goc": goc})
    for x in ra:
        x.setdefault("goc", goc)
    return ra


def _them_preset(ra, root, kho_goc, rel_dir, ten, fs_set):
    p = os.path.join(root, "draft_content.json")
    try:
        st = os.stat(p)
    except OSError:
        return
    bia = os.path.join(root, "draft_cover.jpg") if "draft_cover.jpg" in fs_set else ""
    ra.append({"duong": p, "rel": os.path.relpath(p, kho_goc), "rel_dir": rel_dir, "ten": NFC(ten), "duoi": ".json",
               "size": st.st_size, "mtime": int(st.st_mtime), "loai": "preset_capcut", "phu": {"bia": bia, "nhom": ["capcut"]}})


def _phan_loai_so_bo(duoi, rel_dir, size):
    """phân loại theo đuôi + thư mục (chưa đo). Trả (loai|None, phụ)"""
    if duoi in DUOI_AM:
        nhan = _thu_muc_gan_nhat(rel_dir, [("sfx", ["sound effect", "sfx", "sound fx", "soundfx", "hieu ung am", "am thanh"]),
                                           ("nhac", ["nhac", "music", "bgm", "soundtrack", "beat"])])
        return "am", {"goi_y": nhan}
    if duoi in DUOI_FONT:
        return "font", {}
    if duoi in DUOI_FONT_WEB:
        return "khac", {"nhom": ["font_web"]}
    if duoi in DUOI_LUT:
        return "lut", {}
    if duoi in DUOI_ANH:
        return "anh", {}
    if duoi in DUOI_VIDEO:
        nen = _co(rel_dir, "background", "nen", "grid", "overlay", "texture", "hieu ung", "effect", "particle", "bokeh", "light leak", "filmburn", "film burn")
        return "video", {"nen": nen}
    if duoi == ".json":
        return "khac", {"nhom": ["tai_lieu"]}            # preset CapCut thật đi đường _them_preset (draft_content.json)
    if duoi in DUOI_LIGHTROOM:
        return "khac", {"nhom": ["lightroom"]}
    if duoi in DUOI_TAI_LIEU:
        return "khac", {"nhom": ["tai_lieu"]}
    return None, {}


# ----------------------------------------------------------------------------- đo từng mục
def _do(uv):
    """đo 1 ứng viên → (loai cuối, so_do dict). Chạy trong ThreadPool; mọi lỗi đều nuốt (ghi 'loi')."""
    loai, p, so_do = uv["loai"], uv["duong"], {}
    try:
        if loai == "am":
            dur = _dur_am(p, uv["duoi"])
            if dur is not None:
                so_do["dur"] = dur
            goi_y = uv["phu"].get("goi_y")
            if goi_y == "sfx":
                loai = "sfx"
            elif goi_y == "nhac":
                loai = "nhac"
            else:
                loai = "nhac" if (dur or 0) >= NHAC_DAI else "sfx"
            if loai == "nhac":
                so_do.update(_do_nhac(p))
            else:
                so_do.update(_do_sfx(p))
        elif loai == "font":
            so_do.update(_doc_font(p))
        elif loai == "anh":
            so_do.update(_doc_anh(p))
            w, h = so_do["w"], so_do["h"]
            rel_dir = uv["rel_dir"]
            if _co(rel_dir, "icon", "character", "sticker", "emoji", "logo", "nhan vat"):
                loai = "icon"
            elif so_do["alpha"] and max(w, h) <= 1200:
                loai = "icon"
            elif _co(rel_dir, "background", "nen", "texture", "paper", "grid", "gradient", "overlay", "bokeh") or max(w, h) >= 1280:
                loai = "nen" if not so_do["alpha"] or max(w, h) >= 1280 else "icon"
            else:
                loai = "anh"
        elif loai == "video":
            info = _ffprobe_video(p)
            if info:
                so_do.update(info)
            loai = "nen" if uv["phu"].get("nen") else "video"
        elif loai == "lut":
            so_do["kich"] = _kich_lut(p)
        elif loai == "preset_capcut":
            so_do["kb"] = round(uv["size"] / 1024)
    except Exception as ex:
        so_do["loi"] = str(ex)[:120]
    return loai, so_do


def _kich_lut(p):
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            for _ in range(40):
                d = f.readline()
                m = re.match(r"\s*LUT_3D_SIZE\s+(\d+)", d)
                if m:
                    return int(m.group(1))
    except Exception:
        pass
    return None


# ----------------------------------------------------------------------------- lập
def lap(kho_goc=None, chi_muc_dir=None, tien_do=None, xem_truoc_nhanh=True):
    """quét kho gốc → bảng muc (upsert mục đổi, xoá mục mất) + chi-muc.json. tien_do(i, n, ten) được gọi từ nhiều luồng (đã khoá).
    Trả về thống kê: {"tong","theo_loai","giay","moi","giu","font_du_dau","luc"}"""
    t0 = time.time()
    if isinstance(kho_goc, str) and kho_goc:
        goc_ds = [("bo_mua", os.path.abspath(kho_goc))]
    elif isinstance(kho_goc, (list, tuple)) and kho_goc:
        goc_ds = list(kho_goc)
    else:
        goc_ds = cac_goc()
    chi_muc_dir = chi_muc_dir or chung.duong("kho_chi_muc")
    os.makedirs(chi_muc_dir, exist_ok=True)
    cu_ds = csdl.tat_ca(thu_muc=chi_muc_dir)
    cu = {(m.get("goc") or "bo_mua", m.get("rel")): m for m in cu_ds}
    cu_json = {m["id"]: json.dumps(m, ensure_ascii=False, sort_keys=True) for m in cu_ds if m.get("id")}

    if tien_do:
        tien_do(0, 0, "đang quét thư mục…")
    uvs, da_thay = [], set()
    for goc, duong_goc in goc_ds:
        moi = []
        for uv in _quet(duong_goc, goc):
            k = (os.path.basename(uv["duong"]).lower(), uv["size"])
            if k in da_thay and uv["loai"] != "preset_capcut":
                continue                                   # trùng file ở gốc đứng trước → bỏ
            moi.append(uv)
        uvs.extend(moi)
        da_thay.update((os.path.basename(uv["duong"]).lower(), uv["size"]) for uv in moi)
    n = len(uvs)
    ket_qua = [None] * n
    da_co_id = set()
    giu = 0
    viec = []
    for i, uv in enumerate(uvs):
        c = cu.get((uv["goc"], uv["rel"].replace("\\", "/")))
        if c and c.get("mtime") == uv["mtime"] and c.get("size") == uv["size"] and c.get("id"):
            if c.get("pb") != PHIEN_BAN:      # chỉ dựng lại từ khoá/nhóm, giữ số đo + xem trước
                m = _tao_muc(uv, c["loai"], c.get("so_do", {}), kho_goc)
                m["id"], m["xem_truoc"] = c["id"], c.get("xem_truoc", "")
                if c.get("ai"):
                    m["ai"] = c["ai"]
                c = m
            c["duong"] = uv["duong"]          # kho có thể đổi chỗ
            ket_qua[i] = c
            da_co_id.add(c["id"])
            giu += 1
        else:
            viec.append(i)
    dem = [0]

    def lam(i):
        uv = uvs[i]
        loai, so_do = _do(uv)
        m = _tao_muc(uv, loai, so_do, kho_goc)
        with _khoa:
            m["id"] = _tao_id(loai, m["ten"], uv["rel"].replace("\\", "/"), da_co_id, uv["goc"])
            dem[0] += 1
            k = dem[0]
        if xem_truoc_nhanh and loai in ("font", "lut", "icon", "nen", "preset_capcut", "anh"):
            try:
                from kho import xem_truoc
                xt = xem_truoc.tao(m, ep=False, chi_muc_dir=chi_muc_dir)
                if xt:
                    m["xem_truoc"] = os.path.relpath(xt, chi_muc_dir).replace("\\", "/")
            except Exception as ex:
                m["so_do"]["loi_xt"] = str(ex)[:100]
        ket_qua[i] = m
        if tien_do:
            try:
                tien_do(k, len(viec), m["ten"])
            except Exception:
                pass

    if viec:
        with ThreadPoolExecutor(max_workers=SO_LUONG) as ex:
            list(ex.map(lam, viec))

    muc = [m for m in ket_qua if m]
    _gan_ai_cache(muc, chi_muc_dir)
    try:                                       # 1.2.19: tai của kho — đo ngân/chuỗi/độ phẳng/vân tay mel cho sfx+nhạc còn thiếu (rẻ, ~0,1 s/tệp)
        from kho import tai as _tai
        _tai.do_thieu(muc, (lambda i, n, ten: tien_do(i, n, "đo tiếng: " + ten)) if tien_do else None, ghi=False)
    except Exception as ex:
        chung.log(None, f"(đo tiếng thêm lỗi: {ex})") if hasattr(chung, "log") else None
    muc.sort(key=lambda m: (m["loai"], chung.khong_dau(m["ten"])))
    doi = [m for m in muc if cu_json.get(m["id"]) != json.dumps(m, ensure_ascii=False, sort_keys=True)]     # 1.2.21: chỉ upsert mục đổi
    con = {m["id"] for m in muc}
    mat = [i for i in cu_json if i not in con]
    _ghi_csdl(doi, mat, chi_muc_dir)
    theo_loai = {}
    for m in muc:
        theo_loai[m["loai"]] = theo_loai.get(m["loai"], 0) + 1
    tk = {"tong": len(muc), "theo_loai": dict(sorted(theo_loai.items())), "giay": round(time.time() - t0, 1), "moi": len(viec), "giu": giu,
          "upsert": len(doi), "xoa": len(mat),
          "font_du_dau": sum(1 for m in muc if m["loai"] == "font" and m["so_do"].get("du_dau")),
          "luc": time.strftime("%Y-%m-%d %H:%M:%S"), "kho_goc": "; ".join(p for _, p in goc_ds),
          "goc": [{"khoa": k, "duong": p, "so": sum(1 for m in muc if m.get("goc", "bo_mua") == k)} for k, p in goc_ds],
          "co_ai": sum(1 for m in muc if m.get("ai"))}
    chung.ghi_json(os.path.join(chi_muc_dir, "chi-muc.json"), tk)
    if tien_do:
        tien_do(len(viec), len(viec), "xong")
    return tk


def _ghi_csdl(doi, mat, chi_muc_dir):
    """upsert mục đổi + xoá mục mất trong 1 giao dịch"""
    from contextlib import closing
    with closing(csdl.mo(chi_muc_dir)) as c:
        with c:
            if doi:
                csdl.upsert_muc(doi, c=c)
            if mat:
                csdl.xoa_muc(mat, c=c)


def lap_tep(duong_ds, goc_khoa, goc_duong, chi_muc_dir=None, xem_truoc_nhanh=False):
    """1.2.21: lập chỉ mục CHỈ các tệp cho trước (đã nằm trong gốc `goc_duong`, khoá `goc_khoa` — vd font Google vừa tải)
    → đo, tạo mục, gắn nghĩa cache, upsert. Tệp đã có trong csdl (cùng mtime+size) → giữ. Trả [mục]."""
    chi_muc_dir = chi_muc_dir or chung.duong("kho_chi_muc")
    goc_duong = os.path.abspath(goc_duong)
    da_co = {(m.get("goc") or "bo_mua", m.get("rel")): m for m in csdl.tat_ca(thu_muc=chi_muc_dir)}
    da_co_id = {m["id"] for m in da_co.values()}
    ra, moi = [], []
    for p in duong_ds:
        p = os.path.abspath(p)
        try:
            st = os.stat(p)
        except OSError:
            continue
        rel = os.path.relpath(p, goc_duong)
        rel_dir = os.path.dirname(rel)
        ten_goc, duoi = os.path.splitext(os.path.basename(p))
        loai, phu = _phan_loai_so_bo(duoi.lower(), rel_dir, st.st_size)
        if not loai:
            continue
        c = da_co.get((goc_khoa, rel.replace("\\", "/")))
        if c and c.get("mtime") == int(st.st_mtime) and c.get("size") == st.st_size:
            ra.append(c)
            continue
        uv = {"duong": p, "rel": rel, "rel_dir": rel_dir, "ten": NFC(ten_goc), "duoi": duoi.lower(), "size": st.st_size,
              "mtime": int(st.st_mtime), "loai": loai, "phu": phu, "goc": goc_khoa}
        loai2, so_do = _do(uv)
        m = _tao_muc(uv, loai2, so_do, None)
        m["id"] = c["id"] if c else _tao_id(loai2, m["ten"], rel.replace("\\", "/"), da_co_id, goc_khoa)
        if c and c.get("ai"):
            m["ai"] = c["ai"]
        if xem_truoc_nhanh and loai2 in ("font", "lut", "icon", "nen", "preset_capcut", "anh"):
            try:
                from kho import xem_truoc
                xt = xem_truoc.tao(m, ep=False, chi_muc_dir=chi_muc_dir)
                if xt:
                    m["xem_truoc"] = os.path.relpath(xt, chi_muc_dir).replace("\\", "/")
            except Exception as ex:
                m["so_do"]["loi_xt"] = str(ex)[:100]
        moi.append(m); ra.append(m)
    if moi:
        _gan_ai_cache(moi, chi_muc_dir)
        try:
            from kho import tai as _tai
            _tai.do_thieu(moi, ghi=False)
        except Exception:
            pass
        csdl.upsert_muc(moi, thu_muc=chi_muc_dir)
    return ra


def _tao_muc(uv, loai, so_do, kho_goc):
    nhom = uv["phu"].get("nhom") or _nhom(uv["rel_dir"])
    phan_tm = [p for p in re.split(r"[\\/]+", uv["rel_dir"]) if p][-3:]
    tu_khoa = _tokens(uv["ten"], *phan_tm)
    if loai == "font":
        tu_khoa = _tokens(uv["ten"], so_do.get("ho", ""), so_do.get("kieu", ""))
        if so_do.get("du_dau"):
            tu_khoa.append("viet")
        tu_khoa.append("font")
    tu_khoa = dong_nghia.mo_rong(tu_khoa)
    nhom_kd = [chung.khong_dau(x) for x in nhom]
    for t in nhom_kd:
        for tk in dong_nghia.tach(t):
            if tk not in tu_khoa and tk not in TU_BO:
                tu_khoa.append(tk)
    m = {"id": "", "loai": loai, "ten": uv["ten"], "duong": uv["duong"], "rel": uv["rel"].replace("\\", "/"), "goc": uv.get("goc", "bo_mua"),
         "nhom": nhom, "tu_khoa": tu_khoa[:60], "so_do": so_do, "xem_truoc": "", "mtime": uv["mtime"], "size": uv["size"], "pb": PHIEN_BAN}
    if loai == "font":
        m["du_dau"] = bool(so_do.get("du_dau"))
    if uv["phu"].get("bia"):
        m["bia"] = uv["phu"]["bia"]
    return m


def dau_muc(m):
    """dấu vân tay nội dung (file đổi → gắn nghĩa lại)"""
    return f"{m.get('size')}-{m.get('mtime')}"


def dau_goi(m):
    """dấu vân tay cho bộ đi kèm gói (tai-nguyen/): cỡ + tên — mtime đổi khi giải nén ở máy khách nên không dùng được"""
    return f"{m.get('size')}-{chung.khong_dau(m.get('ten') or '')}"


def _gan_ai_cache(muc, chi_muc_dir):
    """gắn lại trường ai + số đo âm thêm từ cache gan_nghia (bảng ai_nghia) cho mục còn đúng dấu vân tay.
    1.2.19: thêm nguồn tai-nguyen/ai-nghia.json đi kèm gói (nghĩa đã gắn ở máy người bán cho bộ miễn phí) — khớp theo cỡ+tên."""
    cache = csdl.ai_nghia_tat_ca(thu_muc=chi_muc_dir)
    goi = chung.doc_json(os.path.join(chung.SKILL, "tai-nguyen", "ai-nghia.json"), {}) or {}
    goi_theo_dau = {v.get("dau2"): v for v in goi.values() if isinstance(v, dict) and v.get("dau2")} if goi else {}
    for m in muc:
        c = cache.get(m.get("id"))
        if not c or c.get("dau") != dau_muc(m):
            c = goi_theo_dau.get(dau_goi(m)) if (goi_theo_dau and m.get("goc") == "goi_kem") else None
        if not c:
            continue
        if c.get("ai"):
            m["ai"] = c["ai"]
        if c.get("do"):
            m.setdefault("so_do", {}).update(c["do"])


if __name__ == "__main__":
    def _td(i, n, ten):
        if n and (i % 50 == 0 or i == n):
            print(f"  {i}/{n} {ten}", flush=True)
    print(json.dumps(lap(tien_do=_td), ensure_ascii=False, indent=1))
