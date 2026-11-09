# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""1.2.21 (1h): DỌN RÁC — chỉ xoá thứ máy tạo lại được, không bao giờ đụng việc, hồ sơ, công thức, video đã giao ra Downloads.

    quet()                     → [{"nhom": "a|b|c", "duong", "mb", "so_tep", "tuoi_ngay", "dang_dung", "mo_ta", "can_xac_nhan"}]
    don(nhom_ds, ngay=None, duong_ds=None, xac_nhan=False) → {"xoa_mb", "so_tep", "so_muc", "loi": [...]}
    o_dia()                    → {"duong", "trong_gb", "tong_gb"}
    tom_tat(ds)                → {"a": {"mb", "so_tep", "so_muc", "dang_dung_mb"}, "b": …, "c": …}
    tu_dong_khi_thap()         → kết quả don() khi ổ chứa dự án trống < don_rac.o_trong_toi_thieu_gb (không thì None)

Nhóm:
  a — tái tạo được vô điều kiện: tai-len/ của việc đã đóng, cache trình duyệt cua-so/, .ban-cu/ trừ bản mới nhất, claude-*.log của
      việc đã xoá, hoc/<hs>/<ts>/ đã thành bài học (giữ spec/bài/ngữ pháp/ảnh), xem-trước kho của id không còn, %TEMP%/tro-ly-edit-video,
      %TEMP%/studio-ascii, %TEMP%/studio-web-trinh-duyet, %TEMP%/bg-am-*.wav, giong-thu/, doi-chieu-*, .phieu-cu > 30 ngày, chan-doan cũ.
  b — cache dự án (sprite, khuc, base-*, alpha*, proxy*, am*, web*, 7-capcut/do-hoa sau khi khách xác nhận) của dự án đã đóng,
      không bước nào đang `chay`, không thuộc việc đang chạy trong DONG_CO.
  c — đầu ra trùng: giao/<tên>.mp4 khi thư mục giao (Downloads) còn bản; base-* cũ hơn bản mới nhất.
Giữ: viec/, hồ sơ, cong-thuc/ke-hoach/phieu/doc/*.json, Downloads, giong/, dung/thanh-pham.mp4.
`dang_dung` = True thì chỉ liệt kê, không xoá (việc đang chạy / bước đang chạy / vừa ghi < 10 phút).
Server gán DANG_CHAY (ids việc đang chạy) và DU_AN_CUA (vid → thư mục dự án) trước khi dùng.
"""
import glob, json, os, re, shutil, sqlite3, sys, tempfile, threading, time

import du_lieu as D

DANG_CHAY = lambda: set()           # noqa: E731 — server gán: lambda: set(DONG_CO.chay)
DU_AN_CUA = lambda vid: []          # noqa: E731 — server gán: dong_co._du_an_cua
MOI_GHI_GIAY = 600                  # thứ vừa được ghi trong 10 phút → coi là đang dùng
DUOI_MEDIA_HOC = (".mp4", ".mov", ".mkv", ".webm", ".m4v", ".wav", ".m4a", ".aac", ".flac")
_CACHE = {"luc": 0, "ds": None}
_KHOA_QUET = threading.Lock()       # R1: hai request cùng lúc (GET /api/don-rac + luồng 6 giờ) không quét ổ hai lần song song


def _khoa_ban_cu(ten):
    """thứ tự bản sao .ban-cu/<phiên bản>-<YYYYmmdd-HHMMSS>: theo SỐ phiên bản rồi mốc giờ (R1: sắp theo chuỗi thì 1.2.10 < 1.2.9)"""
    ten = os.path.basename(ten.rstrip("\\/"))
    v, _, moc = ten.partition("-")
    try:
        return (0, tuple(int(x) for x in v.split(".")), moc)
    except ValueError:
        return (-1, (), ten)


# ---------------------------------------------------------------- cấu hình + đường dẫn
def cau_hinh():
    dr = (D.cai_dat() or {}).get("don_rac") or {}
    mac = D.MAC_DINH_CAI_DAT["don_rac"]
    try:
        o = float(dr.get("o_trong_toi_thieu_gb", mac["o_trong_toi_thieu_gb"]))
    except (TypeError, ValueError):
        o = mac["o_trong_toi_thieu_gb"]
    try:
        g = float(dr.get("giu_cache_ngay", mac["giu_cache_ngay"]))
    except (TypeError, ValueError):
        g = mac["giu_cache_ngay"]
    return {"tu_dong": bool(dr.get("tu_dong", mac["tu_dong"])), "o_trong_toi_thieu_gb": o, "giu_cache_ngay": g}


def _chung():
    try:
        v3 = os.path.join(D.SKILL, "v3")
        if v3 not in sys.path:
            sys.path.insert(0, v3)
        import chung
        return chung
    except Exception:
        return None


def thu_muc_du_an():
    """thư mục chứa mọi dự án lõi 1.3 (STUDIO_DU_AN đè được — dùng khi chạy thử)"""
    p = os.environ.get("STUDIO_DU_AN")
    if p:
        return os.path.expanduser(p)
    c = _chung()
    if c:
        try:
            return c.duong("du_an")
        except Exception:
            pass
    return os.path.expanduser("~/Videos/studio-du-an")


def du_lieu_v3():
    """thư mục dữ liệu lõi 1.3 (chỉ mục kho, xem trước, phan-cung.json, loi-daemon.json) — STUDIO_V3_DU_LIEU đè được"""
    p = os.environ.get("STUDIO_V3_DU_LIEU")
    if p:
        return os.path.expanduser(p)
    c = _chung()
    if c:
        try:
            return c.duong("du_lieu")
        except Exception:
            pass
    return os.path.join(D.DATA, "v3")


def thu_muc_giao():
    """mọi thư mục giao video (Downloads mặc định + ban_giao.thu_muc của từng hồ sơ)"""
    ds = [os.path.expanduser("~/Downloads")]
    for f in glob.glob(os.path.join(D.CN, "*", "cau-hinh.json")):
        t = ((D.doc_json(f) or {}).get("ban_giao") or {}).get("thu_muc")
        if t:
            ds.append(os.path.expanduser(t))
    return [d for d in dict.fromkeys(os.path.normpath(x) for x in ds) if os.path.isdir(d)]


# ---------------------------------------------------------------- đo
def _co(duong):
    """(bytes, số tệp) — tệp hoặc cả cây thư mục"""
    try:
        if os.path.isfile(duong):
            return os.path.getsize(duong), 1
    except OSError:
        return 0, 0
    tong, n = 0, 0
    for goc, _, fs in os.walk(duong, onerror=lambda e: None):
        for f in fs:
            try:
                tong += os.path.getsize(os.path.join(goc, f)); n += 1
            except OSError:
                pass
    return tong, n


def _mtime(duong):
    try:
        return os.path.getmtime(duong)
    except OSError:
        return 0


def _tuoi_ngay(duong):
    m = _mtime(duong)
    return round((time.time() - m) / 86400, 1) if m else 0


def _moi_ghi(duong):
    return (time.time() - _mtime(duong)) < MOI_GHI_GIAY


def _muc(nhom, duong, mo_ta, dang_dung=False, can_xac_nhan=False, tuoi=None):
    b, n = _co(duong)
    return {"nhom": nhom, "duong": duong, "mb": round(b / 1e6, 1), "so_tep": n, "tuoi_ngay": _tuoi_ngay(duong) if tuoi is None else tuoi,
            "dang_dung": bool(dang_dung), "mo_ta": mo_ta, "can_xac_nhan": bool(can_xac_nhan)}


def o_dia(duong=None):
    duong = duong or thu_muc_du_an()
    try:
        os.makedirs(duong, exist_ok=True)
        u = shutil.disk_usage(duong)
        return {"duong": duong, "trong_gb": round(u.free / 1e9, 1), "tong_gb": round(u.total / 1e9, 1)}
    except OSError:
        return {"duong": duong, "trong_gb": None, "tong_gb": None}


# ---------------------------------------------------------------- việc đang mở → tệp tải lên còn cần
def _viec_mo():
    """{vid: việc} còn MỞ: đang chạy / xếp hàng / Claude đang hỏi / phiếu cuối chưa đóng / việc mới < 1 ngày chưa có phiếu"""
    chay = DANG_CHAY()
    ra = {}
    for tom in D.ds_viec():
        vid = tom["id"]
        try:
            v = D.doc_viec(vid)
        except KeyError:
            continue
        if vid in chay or v.get("cho_chu") or v.get("dang_lam") or v.get("cho_tra_loi"):
            ra[vid] = v; continue
        try:
            ds2 = D.ds_phieu2(vid)
        except Exception:
            ds2 = []
        if ds2:
            if not ds2[-1].get("dong"):
                ra[vid] = v
        elif time.time() - float(v.get("tao_luc") or 0) < 86400:
            ra[vid] = v
    return ra


def _ten_tep_cua_viec(v):
    """tên tệp (basename) mọi tư liệu việc nhắc tới — lời gốc, lời chờ, các tin"""
    ten = set()
    chu = str(v.get("loi_goc") or "") + "\n" + str((v.get("cho_chu") or {}).get("chu") or "")
    for m in re.finditer(r"^- (.+)$", chu, re.M):
        ten.add(os.path.basename(m.group(1).strip()))
    for t in v.get("tin") or []:
        for k in ("tep", "anh", "am", "tai_lieu", "mau", "lut", "font", "giong"):
            for x in t.get(k) or []:
                ten.add(os.path.basename(str(x)))
        if t.get("tep") and isinstance(t["tep"], str):
            ten.add(os.path.basename(t["tep"]))
    return ten


def tep_tai_len_cua_viec(vid):
    """mọi tệp trong tai-len/ mà việc này nhắc tới (xoá việc kèm bản tải lên)"""
    try:
        v = D.doc_viec(vid)
    except KeyError:
        return []
    ten = _ten_tep_cua_viec(v)
    ra = []
    for goc, _, fs in os.walk(D.TAI_LEN):
        for f in fs:
            if f in ten or os.path.splitext(f)[0] + ".txt" == f and os.path.splitext(f)[0] in {os.path.splitext(t)[0] for t in ten}:
                ra.append(os.path.join(goc, f))
    return ra


# ---------------------------------------------------------------- nhóm a
def _quet_a():
    ds = []
    # tai-len/ của việc đã đóng (tệp còn được việc mở nhắc tới → đang dùng)
    can = set()
    for v in _viec_mo().values():
        can |= _ten_tep_cua_viec(v)
    goc_txt = {os.path.splitext(t)[0] for t in can}
    giu = cau_hinh()["giu_cache_ngay"]           # R1: tai-len của việc đã đóng chỉ kê/xoá khi tuổi ≥ giu_cache_ngay (dự án trỏ thẳng đường
    for goc, _, fs in os.walk(D.TAI_LEN):        #     tai-len → "sửa sau khi giao" còn nguồn trong khoảng này); việc đang mở vẫn dang_dung
        for f in fs:
            p = os.path.join(goc, f)
            if f.endswith(".dang-tai"):
                ds.append(_muc("a", p, "tải lên dở dang", dang_dung=_moi_ghi(p))); continue
            dung = f in can or (os.path.basename(goc) == "doc-duoc" and os.path.splitext(f)[0] in goc_txt) or _moi_ghi(p)
            if not dung and _tuoi_ngay(p) < giu:
                continue
            ds.append(_muc("a", p, f"bản chép tư liệu kéo thả vào Studio (việc đã đóng, > {giu:g} ngày)", dang_dung=dung))
    # cache trình duyệt của cửa sổ app
    cs = os.path.join(D.DATA, "cua-so")
    for mau in ("*/Cache", "*/Code Cache", "*/GPUCache", "*/DawnCache", "*/DawnGraphiteCache", "*/DawnWebGPUCache", "GrShaderCache", "ShaderCache",
                "*/Service Worker/CacheStorage", "*/Service Worker/ScriptCache", "GraphiteDawnCache", "*/blob_storage"):
        for p in glob.glob(os.path.join(cs, mau)):
            if os.path.isdir(p):
                ds.append(_muc("a", p, "cache trình duyệt cửa sổ Studio", dang_dung=_moi_ghi(p)))
    # .ban-cu/ trừ bản mới nhất
    bc = sorted(glob.glob(os.path.join(D.SKILL, ".ban-cu", "*")), key=_khoa_ban_cu)
    for p in bc[:-1]:
        ds.append(_muc("a", p, "bản sao Studio cũ (đã có bản mới hơn)"))
    # claude-*.log của việc đã xoá
    for p in glob.glob(os.path.join(D.DATA, "claude-*.log")):
        vid = os.path.basename(p)[7:-4]
        if not os.path.isfile(os.path.join(D.VIEC, vid + ".json")):
            ds.append(_muc("a", p, "nhật ký Claude của việc đã xoá"))
    # hoc/<hs>/<ts>/: đã thành bài học → bỏ media, giữ spec/bài/ngữ pháp/ảnh
    chay = DANG_CHAY()
    thu_hoc_dang = set()
    for vid in chay:
        try:
            v = D.doc_viec(vid)
        except KeyError:
            continue
        if v.get("loai") == "hoc":
            thu_hoc_dang.add(v.get("ho_so"))
    for ts in glob.glob(os.path.join(D.DATA, "hoc", "*", "*")):
        if not os.path.isdir(ts):
            continue
        hs = os.path.basename(os.path.dirname(ts))
        dung = hs in thu_hoc_dang or _moi_ghi(ts) or _tuoi_ngay(ts) < 1
        for goc, dirs, fs in os.walk(ts):
            for d_ in list(dirs):
                if re.match(r"^(doi-chieu-.*|DA|khung.*|soi.*|cache|proxy.*)$", d_):
                    ds.append(_muc("a", os.path.join(goc, d_), "ảnh/khung trung gian của bộ học (bài học đã lưu)", dang_dung=dung)); dirs.remove(d_)
            for f in fs:
                if f.lower().endswith(DUOI_MEDIA_HOC) or f.startswith("doi-chieu-"):
                    ds.append(_muc("a", os.path.join(goc, f), "video/âm thanh mẫu đã học xong (bài học đã lưu)", dang_dung=dung))
    # xem trước kho của id không còn trong chỉ mục
    xt = os.path.join(du_lieu_v3(), "kho-chi-muc", "xem-truoc")
    ids = _id_kho()
    if ids is not None and os.path.isdir(xt):
        for f in os.listdir(xt):
            if f.startswith("_"):
                continue
            mid = f.split(".nghe.")[0] if ".nghe." in f else os.path.splitext(f)[0]
            if mid not in ids:
                ds.append(_muc("a", os.path.join(xt, f), "ảnh xem trước của tài nguyên không còn trong kho"))
    # A6: bảng AI cũ trong kho-chi-muc/bang-ai/*.jpg (bảng tạm để AI gắn nghĩa — tạo lại được)
    for p in glob.glob(os.path.join(du_lieu_v3(), "kho-chi-muc", "bang-ai", "*.jpg")):
        ds.append(_muc("a", p, "bảng ảnh tạm để AI gắn nghĩa kho", dang_dung=_moi_ghi(p)))
    # A3: tệp tạm bìa <dự án>/dung/_bia_khung-<pid>-*.png mồ côi (bình thường tự xoá; còn lại = tiến trình chết giữa chừng)
    for p in glob.glob(os.path.join(thu_muc_du_an(), "*", "dung", "_bia_khung-*.png")):
        m = re.match(r"_bia_khung-(\d+)-", os.path.basename(p))
        song = bool(m) and _pid_song(int(m.group(1)))
        ds.append(_muc("a", p, "tệp tạm vẽ bìa (tiến trình đã dừng)", dang_dung=song or _moi_ghi(p)))
    # %TEMP%
    tmp = tempfile.gettempdir()
    for ten in ("tro-ly-edit-video", "studio-ascii", "studio-web-trinh-duyet"):
        p = os.path.join(tmp, ten)
        if os.path.isdir(p):
            ds.append(_muc("a", p, "tệp tạm của máy dựng", dang_dung=_moi_ghi(p) or bool(chay)))
    for p in glob.glob(os.path.join(tmp, "bg-am-*.wav")):
        ds.append(_muc("a", p, "âm tạm của bộ học", dang_dung=_moi_ghi(p)))
    # giọng nghe thử
    gt = os.path.join(D.DATA, "giong-thu")
    if os.path.isdir(gt) and os.listdir(gt):
        ds.append(_muc("a", gt, "mẫu nghe thử giọng (tạo lại khi bấm nghe)"))
    # .phieu-cu > 30 ngày (đường thật: <skill>/.phieu-cu — bản cũ trỏ sai đường)
    for p in glob.glob(os.path.join(D.SKILL, ".phieu-cu", "*")):
        if _tuoi_ngay(p) > 30:
            ds.append(_muc("a", p, "phiếu cũ > 30 ngày"))
    # gói chẩn đoán: giữ 4
    for p in sorted(glob.glob(os.path.join(D.DATA, "chan-doan", "chan-doan-*.zip")))[:-4]:
        ds.append(_muc("a", p, "gói chẩn đoán cũ"))
    for p in glob.glob(os.path.join(D.DATA, "server.log.*")):
        ds.append(_muc("a", p, "nhật ký server đã xoay"))
    return ds


def _pid_song(pid):
    try:
        import dong_co
        return dong_co._pid_song(pid)
    except Exception:
        return False


def _id_kho():
    """tập id trong chỉ mục kho (SQLite 1g hoặc danh-muc.jsonl); None = không có chỉ mục → không phán"""
    kcm = os.path.join(du_lieu_v3(), "kho-chi-muc")
    sq = os.path.join(kcm, "kho.sqlite")
    if os.path.isfile(sq):
        try:
            con = sqlite3.connect(f"file:{sq}?mode=ro", uri=True)
            try:
                return {r[0] for r in con.execute("SELECT id FROM muc")}
            finally:
                con.close()
        except Exception:
            pass
    jl = os.path.join(kcm, "danh-muc.jsonl")
    if os.path.isfile(jl):
        ids = set()
        try:
            with open(jl, encoding="utf-8") as f:
                for ln in f:
                    try:
                        ids.add(json.loads(ln).get("id"))
                    except Exception:
                        pass
            return ids
        except OSError:
            pass
    return None


# ---------------------------------------------------------------- nhóm b + c (dự án)
def _trang_thai_du_an(d, du_an_chay):
    """→ (dong, dang_dung)"""
    ph = D.doc_json(os.path.join(d, "phieu.json")) or {}
    dong = bool(ph.get("dong"))
    chay = False
    for f in glob.glob(os.path.join(d, ".v3-*.json")):       # 1.2.21: .v3-chan.json là DANH SÁCH lỗi chặn (không phải trạng thái bước) → chỉ xét dict
        st = D.doc_json(f)
        if isinstance(st, dict) and st.get("trang_thai") == "chay":
            chay = True; break
    dung = chay or os.path.normpath(d) in du_an_chay or _moi_ghi(os.path.join(d, "nhat-ky.txt"))
    return dong, dung


def _ban_giao_con(d, giao_ds):
    """thư mục giao (Downloads) còn bản của dự án d (dấu .du-an trỏ về d)? → {tên tệp mp4}"""
    co = set()
    for g in giao_ds:
        for dau in glob.glob(os.path.join(g, "*", ".du-an")):
            try:
                if os.path.normpath(open(dau, encoding="utf-8").read().strip()) == os.path.normpath(d):
                    for f in os.listdir(os.path.dirname(dau)):
                        if f.lower().endswith(".mp4"):
                            co.add((f, os.path.getsize(os.path.join(os.path.dirname(dau), f))))
            except OSError:
                pass
    return co


def _quet_du_an():
    ds = []
    goc = thu_muc_du_an()
    du_an_chay = set()
    for vid in DANG_CHAY():
        try:
            du_an_chay |= {os.path.normpath(x) for x in DU_AN_CUA(vid)}
        except Exception:
            pass
    giao_ds = thu_muc_giao()
    for d in sorted(glob.glob(os.path.join(goc, "*"))):
        if not os.path.isdir(d):
            continue
        try:
            ds += _quet_mot_du_an(d, du_an_chay, giao_ds)
        except Exception as e:                        # 1.2.21: một dự án hỏng tệp không được làm hỏng cả lượt quét
            ds.append(_muc("b", d, f"không quét được dự án này: {e}", dang_dung=True))
    return ds


def _quet_mot_du_an(d, du_an_chay, giao_ds):
    ds = []
    if True:
        dong, dung = _trang_thai_du_an(d, du_an_chay)
        tuoi = _tuoi_ngay(os.path.join(d, "nhat-ky.txt")) if os.path.isfile(os.path.join(d, "nhat-ky.txt")) else _tuoi_ngay(d)
        cache = os.path.join(d, "cache")
        bases = sorted(glob.glob(os.path.join(cache, "base-*.mp4")), key=_mtime)
        base_cu = {os.path.normpath(p) for p in bases[:-1]}          # base cũ hơn bản mới nhất → nhóm c (không kê trùng ở b)
        # b: cache của dự án đã đóng
        b_dung = dung or not dong
        for ten in ("sprite", "khuc"):
            p = os.path.join(cache, ten)
            if os.path.isdir(p):
                ds.append(_muc("b", p, f"cache {ten} (dựng lại được)", dang_dung=b_dung, tuoi=tuoi))
        if os.path.isdir(cache):
            for f in os.listdir(cache):
                if f in ("sprite", "khuc") or os.path.normpath(os.path.join(cache, f)) in base_cu:
                    continue
                if re.match(r"^(base-|alpha|proxy|am|web)", f):
                    ds.append(_muc("b", os.path.join(cache, f), "cache dựng (proxy/alpha/base/âm/web)", dang_dung=b_dung, tuoi=tuoi))
        dh = os.path.join(d, "7-capcut", "do-hoa")
        if os.path.isdir(dh):
            ds.append(_muc("b", dh, "gói tách lớp CapCut (.mov) — xoá khi đã mở xong trong CapCut", dang_dung=b_dung, can_xac_nhan=True, tuoi=tuoi))
        # c: đầu ra trùng
        gd = os.path.join(d, "giao")
        if os.path.isdir(gd):
            con = _ban_giao_con(d, giao_ds)
            for f in os.listdir(gd):
                p = os.path.join(gd, f)
                if f.lower().endswith(".mp4") and os.path.isfile(p):
                    try:
                        if (f, os.path.getsize(p)) in con:
                            ds.append(_muc("c", p, "bản video đã có trong thư mục giao (Downloads)", dang_dung=dung, tuoi=tuoi))
                    except OSError:
                        pass
        for p in bases[:-1]:
            ds.append(_muc("c", p, "base cũ hơn bản mới nhất", dang_dung=dung, tuoi=tuoi))
    return ds


# ---------------------------------------------------------------- API
def _quet_het():
    ds = []
    for f in (_quet_a, _quet_du_an):
        try:
            ds += f()
        except Exception as e:
            ds.append({"nhom": "a", "duong": "", "mb": 0, "so_tep": 0, "tuoi_ngay": 0, "dang_dung": True, "mo_ta": f"lỗi quét: {e}", "can_xac_nhan": False})
    return ds


def _loc(ds, nhom):
    return [x for x in ds if x["nhom"] == nhom] if nhom else list(ds)


def quet(nhom=None, moi=False, han_giay=None):
    """mọi mục rác (hoặc một nhóm). Kết quả nhớ 60 s (ổ lớn quét lâu) — moi=True quét lại.
    R1: han_giay=N → không chặn quá N giây: bộ nhớ còn mới thì trả ngay; không thì quét ở luồng phụ, chờ tối đa N giây,
    chưa xong → trả None (luồng phụ vẫn chạy tiếp và ghi vào bộ nhớ cho lần sau)."""
    if han_giay is not None:
        with _KHOA_QUET:
            if not moi and _CACHE["ds"] is not None and time.time() - _CACHE["luc"] <= 60:
                return _loc(_CACHE["ds"], nhom)
        kq = {}

        def lam():
            with _KHOA_QUET:
                kq["ds"] = _quet_het()
                _CACHE.update(luc=time.time(), ds=kq["ds"])
        t = threading.Thread(target=lam, daemon=True); t.start(); t.join(han_giay)
        return _loc(kq["ds"], nhom) if "ds" in kq else None
    with _KHOA_QUET:
        if moi or _CACHE["ds"] is None or time.time() - _CACHE["luc"] > 60:
            _CACHE.update(luc=time.time(), ds=_quet_het())
        ds = _CACHE["ds"]
    return _loc(ds, nhom)


def quet_nhanh_a(han_giay=5.0):
    """R1: chỉ nhóm a (tai-len, cache cửa sổ, tệp tạm…) ở luồng phụ, chờ tối đa han_giay → ds hoặc None (chưa xong)"""
    kq = {}

    def lam():
        try:
            kq["ds"] = _quet_a()
        except Exception:
            kq["ds"] = []
    t = threading.Thread(target=lam, daemon=True); t.start(); t.join(han_giay)
    return kq.get("ds")


def tom_tat(ds=None):
    ds = quet() if ds is None else ds
    ra = {k: {"mb": 0.0, "so_tep": 0, "so_muc": 0, "dang_dung_mb": 0.0, "can_xac_nhan_mb": 0.0} for k in ("a", "b", "c")}
    for x in ds:
        t = ra.setdefault(x["nhom"], {"mb": 0.0, "so_tep": 0, "so_muc": 0, "dang_dung_mb": 0.0, "can_xac_nhan_mb": 0.0})
        t["so_muc"] += 1
        if x["dang_dung"]:
            t["dang_dung_mb"] = round(t["dang_dung_mb"] + x["mb"], 1); continue
        if x.get("can_xac_nhan"):
            t["can_xac_nhan_mb"] = round(t["can_xac_nhan_mb"] + x["mb"], 1)
        t["mb"] = round(t["mb"] + x["mb"], 1); t["so_tep"] += x["so_tep"]
    return ra


def _xoa(p):
    if os.path.isdir(p) and not os.path.islink(p):
        shutil.rmtree(p)
    else:
        os.remove(p)


def don(nhom_ds, ngay=None, duong_ds=None, xac_nhan=False, ds=None):
    """xoá các mục thuộc nhom_ds (vd ["a","b"]) hoặc đúng các đường dẫn duong_ds (phải là mục quét ra). ngay: chỉ xoá mục có tuổi ≥ ngay
    (nhóm b mặc định giu_cache_ngay). Mục dang_dung không bao giờ xoá; mục can_xac_nhan chỉ xoá khi xac_nhan=True.
    R1: ds = danh sách đã quét sẵn (quet_nhanh_a / quet(han_giay=…)) → không quét lại cả ổ."""
    cfg = cau_hinh()
    nhom_ds = set(nhom_ds or [])
    chon = {os.path.normpath(x) for x in (duong_ds or [])}
    kq = {"xoa_mb": 0.0, "so_tep": 0, "so_muc": 0, "loi": []}
    for x in (list(ds) if ds is not None else quet(moi=True)):
        if not x["duong"]:
            continue
        if chon:
            if os.path.normpath(x["duong"]) not in chon:
                continue
        elif x["nhom"] not in nhom_ds:
            continue
        if x["dang_dung"] or (x.get("can_xac_nhan") and not xac_nhan):
            continue
        han = ngay if ngay is not None else (cfg["giu_cache_ngay"] if x["nhom"] == "b" else None)
        if han is not None and x["tuoi_ngay"] < float(han):
            continue
        try:
            _xoa(x["duong"])
            kq["xoa_mb"] = round(kq["xoa_mb"] + x["mb"], 1); kq["so_tep"] += x["so_tep"]; kq["so_muc"] += 1
        except Exception as e:
            kq["loi"].append(f"{x['duong']}: {type(e).__name__}: {e}")
    _CACHE["ds"] = None
    return kq


def tu_dong_khi_thap(ds_a=None):
    """trước khi gửi việc dựng / theo luồng: ổ chứa dự án trống < ngưỡng → dọn a rồi b. → kết quả hoặc None
    R1: ds_a = kết quả quet_nhanh_a() đã có → bước a không quét lại."""
    cfg = cau_hinh()
    if not cfg["tu_dong"]:
        return None
    o = o_dia()
    if o["trong_gb"] is None or o["trong_gb"] >= cfg["o_trong_toi_thieu_gb"]:
        return None
    kq = don(["a"], ds=ds_a)
    if o_dia()["trong_gb"] < cfg["o_trong_toi_thieu_gb"]:
        kb = don(["b"], ngay=0)
        kq = {"xoa_mb": round(kq["xoa_mb"] + kb["xoa_mb"], 1), "so_tep": kq["so_tep"] + kb["so_tep"], "so_muc": kq["so_muc"] + kb["so_muc"], "loi": kq["loi"] + kb["loi"]}
    kq["o_truoc_gb"], kq["o_sau_gb"] = o["trong_gb"], o_dia()["trong_gb"]
    return kq


def tu_dong_dinh_ky():
    """lúc mở Studio + mỗi 6 giờ: dọn nhóm a và cache dự án đóng quá giu_cache_ngay (khi don_rac.tu_dong bật)"""
    cfg = cau_hinh()
    if not cfg["tu_dong"]:
        return None
    return don(["a", "b"])


def _la_thu_muc_du_an(p):
    """R1 chốt an toàn: chỉ rmtree thư mục CÓ DẤU dự án (phieu.json / viec.json / cong-thuc.json) và KHÔNG phải gốc dự án, nhà, ổ, thư mục dữ liệu"""
    try:
        p = os.path.normpath(os.path.abspath(p))
    except Exception:
        return False
    if not os.path.isdir(p):
        return False
    cam = {os.path.normpath(os.path.abspath(x)) for x in (thu_muc_du_an(), os.path.expanduser("~"), D.DATA, D.SKILL, D.VIEC, D.TAI_LEN, os.path.expanduser("~/Downloads"))}
    if p in cam or os.path.dirname(p) == p or any(c.startswith(p + os.sep) for c in cam):
        return False
    return any(os.path.isfile(os.path.join(p, f)) for f in ("phieu.json", "viec.json", "cong-thuc.json"))


def xoa_cua_viec(vid, du_an_ds):
    """xoá việc KÈM thư mục dự án + bản tải lên + nhật ký + phiếu (nút xoá có ô «xoá cả thư mục dự án và bản tải lên»)"""
    kq = {"xoa_mb": 0.0, "so_tep": 0, "so_muc": 0, "loi": []}
    ds = []
    for d in du_an_ds or []:
        if _la_thu_muc_du_an(d):
            ds.append(d)
        elif d:
            kq["loi"].append(f"{d}: không giống thư mục dự án (không có phieu.json/viec.json) hoặc là thư mục gốc — không xoá")
    ds += tep_tai_len_cua_viec(vid) + [os.path.join(D.DATA, f"claude-{vid}.log")]
    ds += glob.glob(os.path.join(D.PHIEU_VIEC, vid + "*")) + glob.glob(os.path.join(D.PHIEU2, vid + "*"))
    for p in ds:
        if not os.path.exists(p):
            continue
        b, n = _co(p)
        try:
            _xoa(p)
            kq["xoa_mb"] = round(kq["xoa_mb"] + b / 1e6, 1); kq["so_tep"] += n; kq["so_muc"] += 1
        except Exception as e:
            kq["loi"].append(f"{p}: {type(e).__name__}: {e}")
    _CACHE["ds"] = None
    return kq


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="dọn rác Studio")
    ap.add_argument("lenh", choices=["quet", "don"], nargs="?", default="quet")
    ap.add_argument("--nhom", default="a")
    ap.add_argument("--ngay", type=float, default=None)
    a = ap.parse_args()
    if a.lenh == "quet":
        print(json.dumps({"o": o_dia(), "tom_tat": tom_tat(), "muc": quet(moi=True)}, ensure_ascii=False, indent=1))
    else:
        print(json.dumps(don(list(a.nhom), a.ngay), ensure_ascii=False, indent=1))
