# -*- coding: utf-8 -*-
"""Điều phối dựng (cache theo ĐOẠN):
ctx (khổ ra: 1080 | 1440p | 4K, fps 30|60) → lớp (nhân px theo khổ, xếp nhóm) + phụ đề
→ [base (cache) ∥ âm cả bài (cache) ∥ alpha-tl (lớp sau người, tách một lần) ∥ sprite thường song song (cache theo spec)] → sprite cần nền (mẫu lam_nen, đọc base) sau base
→ lớp sau_nguoi: sprite thường, ghep.dung_khuc chồng người (base × alpha-tl) lên nhóm đó rồi mới tới lớp khác (1.2.21 B1, 0 PNG/khung)
→ chia đoạn ~8 s theo điểm cắt → mỗi đoạn băm (base + lớp giao đoạn + engine) → chỉ dựng đoạn chưa có → concat -c copy + mux âm.
dung(du_an, ke_hoach, che_do="that") → {"video","giay":{...},"sprite_cache_hit","khuc":{...},"may_sua","loi",...}
xem_lai(video, n=8) → xem-lai.jpg (n khung 2 hàng, nhãn giây, rộng ~1600 px)"""
import os, sys, time, json, threading, traceback
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor

try:
    import chung
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import chung
from dung import lop as _lop
from dung import chu as _chu
from dung import ghep as _ghep
_ThieuTruongLop = getattr(_lop, "ThieuTruong", None) or getattr(_chu, "ThieuTruong", None) or chung.ThieuTruong   # lỗi thiếu trường của engine (A3)

try:
    from kho import tim as _kho_tim          # kho.tim.lay(id) — có thể chưa có
except Exception:
    _kho_tim = None


class _KhoStub:
    def lay(self, id_):
        if _kho_tim is not None and hasattr(_kho_tim, "lay"):
            try:
                return _kho_tim.lay(id_)
            except Exception:
                return None
        return None


def giai_font_bang(ke_hoach):
    """ke_hoach["phong_cach"]["font"] {vai: đường dẫn|id|tên} → {vai: file}"""
    bang = {}
    f = ((ke_hoach.get("phong_cach") or {}).get("font") or {})
    kf = ke_hoach.get("font") or {}                      # cong_thuc đã giải (vai → file đủ dấu)
    kho = _KhoStub()
    for vai, gia in f.items():
        p = None
        if isinstance(kf.get(vai), str) and os.path.isfile(kf[vai]):
            p = kf[vai]
        elif isinstance(gia, str) and os.path.isfile(gia):
            p = gia
        elif isinstance(gia, str):
            m = kho.lay(gia)
            if m and m.get("duong") and os.path.isfile(m["duong"]):
                p = m["duong"]
        bang[vai] = p or _chu.font_mac_dinh(vai)
    for vai in ("tieu_de", "phu_de", "nhan", "than", "script"):
        if vai not in bang:
            bang[vai] = kf.get(vai) if isinstance(kf.get(vai), str) and os.path.isfile(kf[vai]) else _chu.font_mac_dinh(vai)
    return bang


def kho_ra(ke_hoach, viec=None):
    """(W0,H0 thiết kế), (W,H ra), fps ra, s = tỉ lệ px. xuat{"cao": 1080|1440|2160 (cạnh NGẮN), "fps": 30|60}"""
    viec = viec or {}
    W0, H0 = [int(v) for v in (ke_hoach.get("khung_tk") or ke_hoach.get("khung") or viec.get("khung") or
                               chung.cau_hinh().get("khung_mac_dinh", [1080, 1920]))]
    fps = float(ke_hoach.get("fps") or viec.get("fps") or chung.cau_hinh().get("fps_mac_dinh", 30))
    xu = ke_hoach.get("xuat") or {}
    s = 1.0
    if xu.get("cao"):
        s = float(xu["cao"]) / float(min(W0, H0))
    if xu.get("fps"):
        fps = float(xu["fps"])
    W, H = int(round(W0 * s / 2)) * 2, int(round(H0 * s / 2)) * 2
    return (W0, H0), (W, H), fps, s


def tao_ctx(du_an, ke_hoach, xuat=False):
    """xuat=False: khổ THIẾT KẾ (đo hộp, bìa, kiểm) · True: khổ RA (dựng thật — có thể 1440p/4K)"""
    viec = chung.doc_json(os.path.join(du_an, "viec.json"), {}) or {}
    (W0, H0), (W, H), fps, s = kho_ra(ke_hoach, viec)
    if not xuat:
        W, H, s = W0, H0, 1.0
    ke_hoach["khung_tk"] = [W0, H0]
    ke_hoach["khung"] = [int(W), int(H)]; ke_hoach["fps"] = float(fps)
    nguon = _ghep.nguon_cua(ke_hoach, du_an)
    ke_hoach["nguon"] = nguon
    cat = _ghep.cat_cua(ke_hoach, du_an, nguon)
    ke_hoach["cat"] = cat
    kich_thuoc = _ghep._kich_thuoc_nguon(nguon)
    mat = chung.doc_json(os.path.join(du_an, "doc", "mat.json"))
    font = giai_font_bang(ke_hoach)
    ctx = _lop.Ctx(W, H, fps, font=font, mat=mat, kho=_KhoStub(), du_an=du_an, cat=cat, camera=ke_hoach.get("camera") or [],
                   nguon=nguon, kich_thuoc=kich_thuoc, quyet_dinh=ke_hoach.get("quyet_dinh") or {})
    ctx.ti_le_px = s
    _chu.GIAI_FONT = lambda ten: font.get(ten)
    ctx.pc = ke_hoach.get("phong_cach") or {}          # màu/font theo vai của video — cho thư viện mẫu (dung/mau)
    ctx.quyet_dinh = ke_hoach.get("quyet_dinh") or {}  # 1.2.21 (1c): QUYẾT ĐỊNH CỦA KÊNH (AI viết) — lop/anim/chu/bia đọc thay mọi MAC_DINH thẩm mỹ
    return ctx


_PHIEN_ENGINE = None


def _phien_engine():
    """băm mã engine (lop, chu, anim, web, web_khung.js, mọi mẫu thư viện) — sửa engine/cập nhật phần mềm thì sprite cũ tự hết hạn"""
    global _PHIEN_ENGINE
    if _PHIEN_ENGINE is None:
        import glob as _glob
        g = os.path.dirname(os.path.abspath(__file__))
        ds = [os.path.join(g, f) for f in ("lop.py", "chu.py", "anim.py", "web.py", "web_khung.js")]
        ds += sorted(_glob.glob(os.path.join(g, "mau", "*.py")))
        _PHIEN_ENGINE = chung.bam([chung.bam(f) if os.path.isfile(f) else None for f in ds])
    return _PHIEN_ENGINE


def _bam_nguon_lop(spec, du_an):
    """lớp web/py: băm tệp nguồn (html/py) — spec không đổi mà sửa tệp lop-rieng/x.html|x.py thì vẽ lại"""
    nd = spec.get("noi_dung") or {}
    if not isinstance(nd, dict):
        return None
    ra = {}
    for k in ("html", "file", "duong"):
        f = nd.get(k)
        if isinstance(f, str) and f and not f.lstrip().startswith("<"):
            pth = f if os.path.isabs(f) else os.path.join(du_an or "", f)
            if os.path.isfile(pth):
                ra[k] = chung.bam(pth)
    return ra or None


def _phien_mau(spec):
    """mẫu thư viện: băm file mã của mẫu — mũi Mẫu sửa mẫu thì sprite tự vẽ lại"""
    try:
        from dung import mau as _M
        r = _M.lay(str((spec.get("noi_dung") or {}).get("mau") or ""))
        f = r["ham"].__code__.co_filename if r else None          # cả mẫu riêng (nạp từ tệp, không có trong sys.modules)
        return chung.bam(f) if f and os.path.isfile(f) else None
    except Exception:
        return None


def _khoa_sprite(spec, ctx, them=None):
    return chung.bam({"spec": spec, "W": ctx.W, "H": ctx.H, "fps": ctx.fps, "font": ctx.font if isinstance(ctx.font, dict) else {},
                      "mat": chung.bam(ctx.mat) if ctx.mat else None, "cat": ctx.cat, "camera": ctx.camera, "them": them, "v": _phien_engine(),
                      "pc": getattr(ctx, "pc", None) or {},           # mẫu/web lấy màu theo vai từ phong cách → đổi màu nhấn phải vẽ lại
                      "qd": getattr(ctx, "quyet_dinh", None) or {}})  # R4b 1.2.21: lớp điền co/dam/anim/thẻ… từ quyet_dinh → đổi quyết định kênh phải vẽ lại


def _ve_sprite(lop, thu_muc):
    t = time.time()
    meta = _lop.ket_xuat_sprite(lop, thu_muc)
    meta["giay"] = round(time.time() - t, 2)
    return meta


# ---- tiến trình con: dựng lại lớp từ spec thuần (không pickle đối tượng skia)
def _ve_sprite_proc(args):
    spec, ctx_d, thu_muc, phu_de = args
    import os as _os
    _os.environ.setdefault("PYTHONUTF8", "1")
    sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from dung import lop as L, chu as C
    ctx = L.Ctx.tu_dict(ctx_d)
    C.GIAI_FONT = lambda ten: (ctx_d.get("font") or {}).get(ten)
    if phu_de is not None:
        loi_json, phu_de_spec, i, hop_lop = phu_de[:4]
        ctx.hop_lop = hop_lop
        ctx.hop_lop_chu = phu_de[4] if len(phu_de) > 4 else []
        lops = L.phu_de_sang_lop(loi_json, ctx.cat, phu_de_spec, ctx)
        lop = lops[i]
    else:
        lop = L.tao_lop(spec, ctx)
    return _ve_sprite(lop, thu_muc)


def _proxy_chinh(du_an):
    n = chung.doc_json(os.path.join(du_an, "doc", "nguon.json")) or {}
    if isinstance(n.get("chinh"), dict) and n["chinh"].get("proxy"):
        return n["chinh"]["proxy"]
    for x in n.get("danh_sach") or []:
        if x.get("vai") == "chinh" and x.get("proxy"):
            return x["proxy"]
    return n.get("proxy")


def _ham_tao_alpha(du_an, ke_hoach, ctx, nen_khoang=None):
    """→ callable(khoang) tạo rãnh alpha theo dòng thời gian (tách người LƯỜI — chỉ khi mẫu gọi lay_alpha).
    1.2.21: tách MỘT LẦN cho HỢP mọi khoảng cần nền (nen_khoang) rồi dùng lại cho mọi lớp (trước: mỗi lớp tách lại khoảng riêng);
    tao_ranh_tai_su_dung cắt/nối từ rãnh đã có trong chỉ mục nên chạy lại không tách lại."""
    nho = {}

    def tao(khoang):
        if nho.get("p") and nho["kh"][0] <= khoang[0] + 1e-3 and nho["kh"][1] >= khoang[1] - 1e-3:
            return nho["p"]
        if nen_khoang:
            khoang = (min(nen_khoang[0], khoang[0]), max(nen_khoang[1], khoang[1]))
        ta, tb = khoang
        a_min = b_max = None; off = 0.0
        for s in ctx.cat:
            d = s["b"] - s["a"]
            o0, o1 = max(off, ta), min(off + d, tb)
            if o1 > o0 and int(s.get("src", 0)) == 0:
                a, b = s["a"] + (o0 - off), s["a"] + (o1 - off)
                a_min = a if a_min is None else min(a_min, a); b_max = b if b_max is None else max(b_max, b)
            off += d
        if a_min is None:
            return None
        al = ke_hoach.get("alpha")
        if isinstance(al, dict) and al.get("duong") and os.path.isfile(al["duong"]):
            dur = float((chung.ffprobe(al["duong"]) or {}).get("dur") or 0)
            if float(al.get("a") or 0) <= a_min + 0.05 and float(al.get("a") or 0) + dur >= b_max - 0.05:
                nho.update(p=_ghep.dung_alpha_tl(du_an, ke_hoach, al), kh=khoang)
                return nho["p"]
        px = _proxy_chinh(du_an)
        if not px or not os.path.isfile(px):
            raise RuntimeError("không thấy proxy để tách người")
        from doc import alpha as _A
        a0, b0 = max(0.0, a_min - 0.2), b_max + 0.2
        chung.log(du_an, f"alpha: mẫu cần mặt nạ người → tách {a0:.1f}–{b0:.1f}s (giây gốc)")
        with chung.DoThoiGian(du_an, "alpha_mau"):
            p = _A.tao_ranh_tai_su_dung(du_an, px, a0, b0, uu_tien_thap=False)     # 1.2.19: dùng lại/nối rãnh đã có
        if not p:
            return None
        nho.update(p=_ghep.dung_alpha_tl(du_an, ke_hoach, {"duong": p, "a": round(a0, 3), "dur_nguon": (chung.ffprobe(px) or {}).get("dur")}), kh=khoang)
        return nho["p"]
    return tao


def _la_phu_toan_khung(sp):
    """lớp phủ cả khung / hoà trộn (ánh sáng, nền động) — không tính là “vật cản” cho phụ đề.
    1.2.21: MỌI lớp có vi_tri w,h ≥ 0,9 là toàn khung (web/py/mẫu phủ khung cũng vậy — trước chỉ miễn video/hinh)."""
    vt = sp.get("vi_tri") or {}
    if hasattr(_lop, "la_toan_khung") and _lop.la_toan_khung(sp):       # A3: một luật w,h ≥ 0,9 cho mọi kiểu lớp
        return True
    if sp.get("toan_khung") or _lop.the_mau(sp).get("toan_khung"):
        return True
    if float(vt.get("w", 0) or 0) >= 0.9 and float(vt.get("h", 0) or 0) >= 0.9:
        return True
    if sp.get("kieu") in ("video", "hinh") and (sp.get("kieu_dang") or {}).get("hoa_tron") not in (None, "normal"):
        return True
    return False


def _png_dau(meta):
    """đường PNG đầu tiên của sprite (từ lop.ffconcat) — None nếu không đọc được"""
    try:
        muc = _ghep._doc_ffconcat(meta.get("concat") or "")
        return muc[0][0] if muc else None
    except Exception:
        return None


def _xoa_png_sprite(thu_muc_sprite, dung_ngay, giu_ngay):
    """1.2.21 (1h): sau khi khúc dựng xong — XOÁ PNG của sprite (giữ meta.json + lop.ffconcat vài KB để băm khúc vẫn trúng cache;
    khúc cần dựng lại mà thiếu PNG thì vẽ lại đúng sprite đó — tên tệp tất định). Thư mục sprite không dùng trong lần này và cũ hơn
    giu_ngay ngày cũng xoá PNG. cau-hinh v3 giu_sprite=true / dung(giu_sprite=True) → giữ."""
    n, bay = 0, time.time()
    try:
        ds = os.listdir(thu_muc_sprite)
    except OSError:
        return 0
    for ten in ds:
        d = os.path.join(thu_muc_sprite, ten)
        if not os.path.isdir(d):
            continue
        try:
            if d not in dung_ngay and bay - os.path.getmtime(d) < giu_ngay * 86400:
                continue
            for f in os.listdir(d):
                if f.lower().endswith(".png"):
                    os.remove(os.path.join(d, f)); n += 1
        except OSError:
            pass
    return n


def dung(du_an, ke_hoach, che_do="that", song_song=None, luong=None, loi_json=None, giu_sprite=None):
    """che_do: "that" | "nhanh" (crf cao hơn). song_song: "thread" | "process" | None (tự chọn). → dict kết quả.
    giu_sprite=True (xuất CapCut cần PNG từng lớp): vẽ lại PNG sprite đã dọn và KHÔNG dọn sau khi dựng; None = theo cau-hinh v3 giu_sprite.
    Thiếu trường quyết định (lớp/anim/camera/âm) → ghi kiem.json["loi"] dạng {"id","ma":"thieu_truong","duong","lop","mo_ta"} rồi ném lại
    ThieuTruong (cau_noi in cho AI, không trace)."""
    try:
        return _dung(du_an, ke_hoach, che_do, song_song, luong, loi_json, giu_sprite)
    except (_ThieuTruongLop, chung.ThieuTruong) as ex:
        l0 = getattr(ex, "loi", None)
        ds = l0 if isinstance(l0, list) else ([l0()] if callable(l0) else [])
        ds = [dict(l, id="thieu_truong", ma=l.get("ma") or "thieu_truong", lop=l.get("lop") or "*",
                   mo_ta=l.get("mo_ta") or ("thiếu trường " + str(l.get("duong")) + (": " + l["goi_y"] if l.get("goi_y") else "")))
              for l in ds if isinstance(l, dict)]
        try:
            p = os.path.join(du_an, "kiem.json")
            d = chung.doc_json(p) or {"loi": [], "may_sua": [], "canh_bao": []}
            d["loi"] = [l for l in d.get("loi") or [] if l.get("id") != "thieu_truong"] + ds
            d["loi_dung"] = [l for l in d.get("loi_dung") or [] if l.get("id") != "thieu_truong"] + ds
            chung.ghi_json(p, d)
        except Exception:
            pass
        chung.log(du_an, "dựng dừng — thiếu trường quyết định: " + ", ".join(str(l.get("duong")) for l in ds))
        raise


def _dung(du_an, ke_hoach, che_do, song_song, luong, loi_json, giu_sprite):
    T = {}; t_all = time.time()
    ke_hoach = json.loads(json.dumps(ke_hoach))
    ctx = tao_ctx(du_an, ke_hoach, xuat=True)
    W, H, fps, s_px = ctx.W, ctx.H, ctx.fps, ctx.ti_le_px
    tong = ctx.tong_dai() or float(ke_hoach.get("dur") or 0)
    ke_hoach["_tong"] = tong
    chat_luong = "nhanh" if che_do == "nhanh" else "that"
    thu_muc_sprite = os.path.join(du_an, "cache", "sprite"); os.makedirs(thu_muc_sprite, exist_ok=True)
    may_sua, loi = [], []
    if s_px != 1:
        chung.log(du_an, f"xuất {W}×{H} @{fps:g} fps (px công thức ×{s_px:.3f})")

    # ---- base + âm chạy nền (ffmpeg, tiến trình riêng)
    base_kq, am_kq = {}, {}

    def _base():
        t = time.time()
        try:
            base_kq["path"] = _ghep.dung_base(du_an, ke_hoach, ctx)
        except (_ThieuTruongLop, chung.ThieuTruong) as ex:   # R4b 1.2.21: camera.ease thiếu (quyet_dinh) → ThieuTruong, không thành "base lỗi" có trace
            base_kq["thieu"] = ex
        except Exception:
            base_kq["loi"] = traceback.format_exc()
        base_kq["giay"] = round(time.time() - t, 2)

    def _am():
        t = time.time()
        try:
            am_kq["path"] = _ghep.dung_am(du_an, ke_hoach, ctx)
        except chung.ThieuTruong as ex:                      # 1.2.21: am.py không tự điền → trả AI danh sách trường
            am_kq["thieu"] = ex.loi
        except Exception:
            am_kq["loi"] = traceback.format_exc()
        am_kq["giay"] = round(time.time() - t, 2)
    th_base = threading.Thread(target=_base, daemon=True); th_base.start()
    th_am = threading.Thread(target=_am, daemon=True); th_am.start()

    # ---- lớp: nhân px (khổ ra), xếp nhóm, thứ tự chồng (z rồi thứ tự trong công thức)
    t = time.time()
    specs = [_lop.nhan_px(sp, s_px) for sp in (ke_hoach.get("lop") or [])]
    specs, ms = _lop.xep_nhom(specs, ctx)
    may_sua += ms
    thu_tu = sorted(range(len(specs)), key=lambda i: (float(specs[i].get("z", 0) or 0), i))
    viec = []        # (vị trí chồng, khoa, thu_muc, spec, phu_de_info, lam_nen)
    truc_tiep = {}   # vị trí chồng → mô tả lớp trực tiếp
    nen_khoang = None
    sau_nguoi_vt, sau_nguoi_khoang = {}, None     # 1.2.21 (B1): vị trí chồng → id lớp sau người; hợp khoảng của chúng (alpha-tl tách một lần)
    for vt_i, i in enumerate(thu_tu):
        sp = specs[i]
        if sp.get("sau_nguoi") and not _lop.la_truc_tiep(sp):
            sau_nguoi_vt[vt_i] = sp.get("id")
            t0_, t1_ = float(sp["t0"]), float(sp["t1"])
            sau_nguoi_khoang = (min(sau_nguoi_khoang[0], t0_), max(sau_nguoi_khoang[1], t1_)) if sau_nguoi_khoang else (t0_, t1_)
        if _lop.la_truc_tiep(sp):
            try:
                L = _lop.tao_lop(sp, ctx)
                truc_tiep[vt_i] = _lop.muc_truc_tiep(L)
                may_sua += L.may_sua; loi += L.loi
                if not truc_tiep[vt_i].get("file"):
                    truc_tiep.pop(vt_i)
            except _ThieuTruongLop:                          # 1.2.21: thiếu trường quyết định → không nuốt thành tai_nguyen_khong_co
                raise
            except Exception as ex:
                loi.append({"id": "tai_nguyen_khong_co", "lop": sp.get("id"), "t": sp.get("t0"), "mo_ta": f"lớp video/ảnh lỗi: {ex}"})
            continue
        nen = _lop.can_nen(sp)
        them = {"mau": _phien_mau(sp)} if sp.get("kieu") == "mau" else None
        if sp.get("kieu") in ("web", "py"):
            them = {"nguon": _bam_nguon_lop(sp, du_an)}
        if nen:
            them = dict(them or {}, base=_ghep.khoa_base(du_an, ke_hoach))
            nen_khoang = (min(nen_khoang[0], float(sp["t0"])), max(nen_khoang[1], float(sp["t1"]))) if nen_khoang else (float(sp["t0"]), float(sp["t1"]))
        k = _khoa_sprite(sp, ctx, them)
        viec.append((vt_i, k, os.path.join(thu_muc_sprite, k), sp, None, nen))
    alpha_khoang = None                            # hợp khoảng cần mặt nạ người: mẫu lam_nen (nen_khoang) + lớp sau người
    for kh_ in (nen_khoang, sau_nguoi_khoang):
        if kh_:
            alpha_khoang = (min(alpha_khoang[0], kh_[0]), max(alpha_khoang[1], kh_[1])) if alpha_khoang else kh_
    if alpha_khoang:
        ctx.tao_alpha = _ham_tao_alpha(du_an, ke_hoach, ctx, alpha_khoang)
    alpha_kq = {}
    th_alpha = None
    if sau_nguoi_khoang:                           # 1.2.21 (B1): alpha-tl dựng MỘT lần, chạy nền song song base/sprite (không chờ mẫu gọi)
        def _alpha():
            t = time.time()
            try:
                with ctx._khoa_alpha:
                    p = ctx.tao_alpha(alpha_khoang)
                    if p:
                        ctx.alpha_tl, ctx._alpha_khoang = p, alpha_khoang
                    alpha_kq["path"] = p
            except Exception:
                alpha_kq["loi"] = traceback.format_exc()
            alpha_kq["giay"] = round(time.time() - t, 2)
        th_alpha = threading.Thread(target=_alpha, daemon=True); th_alpha.start()
    pd = dict(ke_hoach.get("phu_de") or {})
    if s_px != 1 and pd:
        tmp = _lop.nhan_px({"kieu_dang": pd.get("kieu_dang"), "anim": pd.get("anim")}, s_px)
        pd["kieu_dang"], pd["anim"] = tmp.get("kieu_dang"), tmp.get("anim")
    if loi_json is None and pd.get("che_do", "cum") != "tat":
        loi_json = chung.doc_json(os.path.join(du_an, "doc", "loi.json"))
    pd_lops = []
    hop_lop = []
    hop_lop_chu = []
    if loi_json and pd.get("che_do", "cum") != "tat":
        for sp in specs:
            if sp.get("kieu") in ("chu", "khoi", "the", "hinh", "video", "py", "mau", "web") and not _la_phu_toan_khung(sp):
                try:
                    lx, ly, lw, lh = _lop.tao_lop(sp, ctx).khoi()
                    hop_lop.append((float(sp["t0"]), float(sp["t1"]), (lx, ly, lx + lw, ly + lh), sp.get("id")))
                    if sp.get("kieu") in ("chu", "khoi", "the"):
                        hop_lop_chu.append((float(sp["t0"]), float(sp["t1"])))
                except _ThieuTruongLop:
                    raise
                except Exception:
                    pass
        ctx.hop_lop = hop_lop
        ctx.hop_lop_chu = hop_lop_chu
        pd_lops = _lop.phu_de_sang_lop(loi_json, ctx.cat, pd, ctx)
        for i, l in enumerate(pd_lops):
            k = _khoa_sprite(l.spec, ctx, them={"pd": i, "tween": l.tween, "loi": chung.bam(loi_json)})
            viec.append((len(thu_tu) + i, k, os.path.join(thu_muc_sprite, k), l.spec, (loi_json, pd, i, hop_lop, hop_lop_chu), False))
    chung.log(du_an, f"lớp: {len(specs)} ({len(truc_tiep)} video/ảnh trực tiếp) + phụ đề {len(pd_lops)} cụm")
    # ---- cache hit? (1.2.21: meta + ffconcat còn = trúng cache dù PNG đã dọn; PNG vẽ lại chỉ khi khúc chứa nó phải dựng)
    sprites = {}; can_ve = []; png_thieu = set()
    for j, (vt_i, k, tm, spec, pdi, nen) in enumerate(viec):
        m = chung.doc_json(os.path.join(tm, "meta.json"))
        if m and os.path.isfile(m.get("concat", "")):
            m["cache"] = True; sprites[j] = m
            p0 = _png_dau(m)
            if p0 and not os.path.isfile(p0):
                png_thieu.add(j)
        else:
            can_ve.append(j)
    hit = len(viec) - len(can_ve)
    luong = luong or int(chung.hang_may(ha_luong=False)["sprite_luong"])
    ve_truoc = [j for j in can_ve if not viec[j][5]]          # không cần nền → vẽ ngay (song song base)
    ve_sau = [j for j in can_ve if viec[j][5]]               # mẫu lam_nen → sau base
    if song_song is None:
        song_song = "process" if len(ve_truoc) >= 4 else "thread"

    def _lam(j):
        vt_i, k, tm, spec, pdi, nen = viec[j]
        lop = pd_lops[pdi[2]] if pdi else _lop.tao_lop(spec, ctx)
        return _ve_sprite(lop, tm)

    def _ve_nhieu(js, ss):
        """vẽ các sprite js (song song theo ss) → sprites[j]; trả chế độ đã dùng"""
        if not js:
            return ss
        if ss == "process":
            ctx_d = ctx.xuat()
            args = [(viec[j][3], ctx_d, viec[j][2], viec[j][4]) for j in js]
            try:
                with ProcessPoolExecutor(max_workers=luong) as ex:
                    for j, m in zip(js, ex.map(_ve_sprite_proc, args)):
                        sprites[j] = m
                return ss
            except (_ThieuTruongLop, chung.ThieuTruong):     # R4b 1.2.21: thiếu trường trong tiến trình con → ném thẳng (không in trace, không vẽ lại bằng thread)
                raise
            except Exception:
                chung.log(du_an, "process pool lỗi → thread:\n" + traceback.format_exc()[-600:])
                ss = "thread"
        with ThreadPoolExecutor(max_workers=luong) as ex:
            for j, m in zip(js, ex.map(_lam, js)):
                sprites[j] = m
        return ss
    song_song = _ve_nhieu(ve_truoc, song_song)
    T["sprite"] = round(time.time() - t, 2)
    # ---- base xong?
    th_base.join()
    if "thieu" in base_kq:
        raise base_kq["thieu"]
    if "loi" in base_kq:
        raise RuntimeError("base lỗi: " + base_kq["loi"][-800:])
    T["base"] = base_kq["giay"]
    ctx.base = base_kq["path"]
    alpha_tl = None
    if th_alpha is not None:                       # mẫu lam_nen (ve_sau) và khúc đều cần alpha-tl đã xong
        th_alpha.join()
        T["alpha"] = alpha_kq.get("giay")
        alpha_tl = alpha_kq.get("path")
        if not alpha_tl or not os.path.isfile(alpha_tl):
            ly_do = (alpha_kq.get("loi") or "").strip().splitlines()[-1:] if alpha_kq.get("loi") else ["không tách được người"]
            chung.log(du_an, f"sau_nguoi: không có mặt nạ người ({ly_do[0][:160] if ly_do else ''}) → {len(sau_nguoi_vt)} lớp dựng như lớp thường")
            may_sua.append({"id": "sau_nguoi_khong_alpha", "lop": sorted(v for v in sau_nguoi_vt.values() if v), "sua": "sau_nguoi",
                            "tu": "sau người", "den": "lớp thường",
                            "mo_ta": "không có mặt nạ người (không tách được/không có proxy) → lớp sau_nguoi dựng như lớp thường (chữ đè lên người)"})
            alpha_tl = None
    if ve_sau:                                     # mẫu cần nền: đọc base đã dựng (luồng — dùng chung ctx, bộ đọc khung riêng mỗi lớp)
        t = time.time()
        with ThreadPoolExecutor(max_workers=max(1, min(luong, 4))) as ex:
            for j, m in zip(ve_sau, ex.map(_lam, ve_sau)):
                sprites[j] = m
        T["sprite_nen"] = round(time.time() - t, 2)
        loi += ctx.loi
    T["sprite_ve"] = round(sum(m.get("giay", 0) for m in sprites.values() if not m.get("cache")), 2)
    for j, m in sprites.items():
        may_sua += m.get("may_sua") or []; loi += m.get("loi") or []
    # ---- danh sách chồng theo thứ tự: lớp (z, thứ tự) rồi phụ đề
    chong = {}
    for j, m in sprites.items():
        chong[viec[j][0]] = dict(m, thu_tu=viec[j][0], sau_nguoi=bool(alpha_tl and viec[j][0] in sau_nguoi_vt))
    for vt_i, it in truc_tiep.items():
        chong[vt_i] = dict(it, thu_tu=vt_i)
    lop_ds = [chong[k] for k in sorted(chong)]
    # ---- đoạn
    t = time.time()
    doan = _ghep.chia_doan(ctx.cat, fps)
    enc = _ghep.phan_cung().get("encoder", "libx264")
    # 1.2.21: số khúc dựng song song không trần cứng 3 — theo luồng còn rảnh (mỗi ffmpeg khúc ~4 luồng); cau-hinh v3 khuc_song_song đè
    # B1: đo TƯƠI (không dùng mẫu cache 10 s đo lúc ffmpeg alpha-tl/base còn chạy — mẫu cũ cho 1 luồng → khúc dựng tuần tự)
    n_song = int(chung.cau_hinh().get("khuc_song_song") or 0) or max(1, int(chung.luong_ranh(cache_giay=0)["luong_ranh"]) // 4)
    def _dung_tat_ca(enc):
        ds = []
        for f0, f1 in doan:
            k, mt = _ghep.chuan_bi_khuc(du_an, ke_hoach, base_kq["path"], f0, f1, lop_ds, enc, chat_luong, alpha_tl=alpha_tl)
            ds.append((k, mt))
        ket = [None] * len(ds)
        moi = [i for i, (k, mt) in enumerate(ds) if not os.path.isfile(_ghep.duong_khuc(du_an, k))]
        # sprite đã dọn PNG mà khúc chứa nó phải dựng → vẽ lại đúng sprite đó (tên tệp tất định → băm khúc không đổi)
        can_png = set()
        for i in moi:                                  # ffconcat con (c-*.ffconcat trong cache/khuc) → PNG đầu → thư mục sprite
            for it in ds[i][1]["items"]:
                if it.get("loai") != "sprite":
                    continue
                try:
                    p0 = _ghep._doc_ffconcat(it["concat"])[0][0]
                except Exception:
                    continue
                if not os.path.isfile(p0):
                    tm_ = os.path.normcase(os.path.abspath(os.path.dirname(p0)))
                    for j, m in sprites.items():
                        if os.path.normcase(os.path.abspath(os.path.dirname(m.get("concat") or ""))) == tm_:
                            can_png.add(j)
        if can_png:
            chung.log(du_an, f"sprite: vẽ lại {len(can_png)} lớp đã dọn PNG (khúc chứa chúng phải dựng lại)")
            _ve_nhieu(sorted(j for j in can_png if not viec[j][5]), song_song)
            for j in sorted(j for j in can_png if viec[j][5]):
                sprites[j] = _lam(j)

        def _mot(i):
            return _ghep.dung_khuc(du_an, base_kq["path"], ds[i][0], ds[i][1], enc, chat_luong)
        for i, (k, mt) in enumerate(ds):
            if i not in moi:
                ket[i] = (_ghep.duong_khuc(du_an, k), True)
        with ThreadPoolExecutor(max_workers=max(1, n_song)) as ex:
            for i, r in zip(moi, ex.map(_mot, moi)):
                ket[i] = r
        return ket
    try:
        ket = _dung_tat_ca(enc)
    except RuntimeError as ex:
        if enc == "libx264":
            raise
        chung.log(du_an, f"đoạn lỗi với {enc} ({str(ex)[:160]}) → dựng lại mọi đoạn bằng libx264 (concat cần cùng bộ mã hoá)")
        # 1.2.21 (B1): chỉ ghi encoder_loi BỀN khi có DÒNG lỗi encoder thật (ghep.phan_loai_loi); TREO / lỗi khác → libx264 trong phiên
        pl = _ghep.phan_loai_loi(str(ex), ma=124 if "TREO" in str(ex) else 1, co_hwaccel=False, enc=enc) if hasattr(_ghep, "phan_loai_loi") else {"encoder": True}
        if pl.get("encoder"):
            _ghep._nho_encoder_loi(enc, pl.get("dong") or str(ex))
        else:
            _ghep.phan_cung()["encoder"] = "libx264"
        enc = "libx264"
        ket = _dung_tat_ca(enc)
    T["khuc"] = round(time.time() - t, 2)
    try:   # env STUDIO_GIU_CACHE_NGAY (Studio đặt từ cai-dat.json don_rac.giu_cache_ngay) → cau-hinh v3 → 3
        giu_ngay = float(os.environ.get("STUDIO_GIU_CACHE_NGAY") or chung.cau_hinh().get("giu_cache_ngay") or 3)
    except (TypeError, ValueError):
        giu_ngay = 3.0
    giu = bool(chung.cau_hinh().get("giu_sprite")) if giu_sprite is None else bool(giu_sprite)
    if giu:                                        # xuất CapCut: cần PNG mọi lớp → vẽ lại những sprite đã dọn
        thieu = [j for j in sorted(png_thieu) if not os.path.isfile(_png_dau(sprites[j]) or "")]
        if thieu:
            chung.log(du_an, f"sprite: vẽ lại {len(thieu)} lớp đã dọn PNG (giữ sprite cho xuất CapCut)")
            _ve_nhieu([j for j in thieu if not viec[j][5]], song_song)
            for j in [j for j in thieu if viec[j][5]]:
                sprites[j] = _lam(j)
    else:
        try:                                       # 1.2.21 (1h): khúc xong → dọn PNG sprite ngay (meta/ffconcat giữ), trước khi nối
            n_png = _xoa_png_sprite(thu_muc_sprite, {os.path.dirname(m.get("concat") or "") for m in sprites.values()}, giu_ngay)
            if n_png:
                chung.log(du_an, f"dọn {n_png} PNG sprite sau khi khúc dựng xong (cache/sprite chỉ giữ meta + ffconcat)")
        except Exception:
            pass
    khuc_info = {"tong": len(ket), "cache": sum(1 for _, c in ket if c), "dung": sum(1 for _, c in ket if not c),
                 "ranh": [[round(f0 / fps, 3), round(f1 / fps, 3)] for f0, f1 in doan]}
    # ---- âm + nối
    th_am.join()
    if "thieu" in am_kq:
        try:
            from nao import kiem as _kiem
            _kiem.ghi_loi_dung(du_an, [dict(l, id="thieu_truong", lop="am", mo_ta=f"thiếu {l.get('duong')}: {l.get('goi_y', '')}") for l in am_kq["thieu"]])
        except Exception:
            pass
        raise chung.ThieuTruong(am_kq["thieu"])
    if "loi" in am_kq:
        raise RuntimeError("âm lỗi: " + am_kq["loi"][-800:])
    T["am"] = am_kq["giay"]
    t = time.time()
    out_dir = os.path.join(du_an, "dung"); os.makedirs(out_dir, exist_ok=True)
    video = _ghep.noi(du_an, [p for p, _ in ket], am_kq.get("path"), os.path.join(out_dir, "thanh-pham.mp4"), tong)
    T["noi"] = round(time.time() - t, 2)
    try:                                           # dọn đoạn/ffconcat cũ không còn dùng (giữ giu_cache_ngay ngày — cau-hinh v3 giu_cache_ngay, mặc định 3)
        import glob as _glob
        dang = {os.path.normcase(os.path.abspath(p)) for p, _ in ket}
        for f in _glob.glob(os.path.join(du_an, "cache", "khuc", "*")):
            if os.path.normcase(os.path.abspath(f)) not in dang and time.time() - os.path.getmtime(f) > giu_ngay * 86400:
                os.remove(f)
        # 1.2.21: base-* cũ hơn bản vừa dùng → xoá (mỗi lần đổi cắt/camera là 100–200 MB)
        bhc = os.path.normcase(os.path.abspath(base_kq["path"]))
        for f in _glob.glob(os.path.join(du_an, "cache", "base-*.mp4")):
            if os.path.normcase(os.path.abspath(f)) != bhc and os.path.getmtime(f) <= os.path.getmtime(base_kq["path"]):
                os.remove(f)
    except Exception:
        pass
    T["tong"] = round(time.time() - t_all, 2)
    # danh sách lớp đã dùng (xuất CapCut: mỗi lớp sprite một clip trong suốt; phụ đề → chữ CapCut thật; video trực tiếp → ghi đường dẫn)
    ds_lop = []
    for j, m in sorted(sprites.items(), key=lambda x: viec[x[0]][0]):
        sp = viec[j][3] or {}
        ds_lop.append({"meta": {k: m.get(k) for k in ("id", "kieu", "concat", "x", "y", "w", "h", "t0", "t1")},
                       "text": (sp.get("noi_dung") or {}).get("text"), "kieu_dang": sp.get("kieu_dang"), "phu_de": viec[j][4] is not None,
                       "sau_nguoi": bool(sp.get("sau_nguoi"))})       # 1.2.21 (B1): PNG KHÔNG che người — xuất CapCut cần tự chồng người (alpha_tl)
    for vt_i, it in sorted(truc_tiep.items()):
        ds_lop.append({"meta": {"id": it["id"], "kieu": it["kieu"], "concat": None, "duong": it["file"], "x": it["x"], "y": it["y"], "w": it["w"],
                                "h": it["h"], "t0": it["t0"], "t1": it["t1"], "hoa_tron": it["hoa_tron"], "do_trong": it["do_trong"],
                                "a": it.get("a", 0.0), "lap": it.get("lap", False), "toc_do": it.get("toc_do", 1.0), "fit": it.get("fit", "cover"),
                                "loai_nguon": it.get("loai_nguon")},
                       "truc_tiep": True, "phu_de": False})
    da, ms2 = set(), []
    for m in may_sua:
        kk = json.dumps(m, sort_keys=True, ensure_ascii=False, default=str)
        if kk not in da:
            da.add(kk); ms2.append(m)
    kq = {"video": video, "giay": T, "sprite_cache_hit": hit, "sprite": len(viec), "song_song": song_song, "khuc": khuc_info,
          "may_sua": ms2, "loi": loi, "base": base_kq["path"], "am": am_kq.get("path"), "lop": ds_lop, "W": W, "H": H, "fps": fps,
          "dur": float(tong), "ti_le_px": s_px, "alpha_tl": alpha_tl}
    chung.ghi_json(os.path.join(du_an, "dung", "ket-qua-dung.json"), kq)
    try:                                           # lỗi phát hiện lúc dựng (lớp web/py/mẫu, đè mặt không cứu được…) → kiem.json cho AI thấy
        from nao import kiem as _kiem
        _kiem.ghi_loi_dung(du_an, loi)
    except Exception as ex:
        chung.log(du_an, f"ghi lỗi dựng vào kiem.json lỗi: {ex}")
    chung.log(du_an, f"dựng: {T} · đoạn {khuc_info['dung']}/{khuc_info['tong']} dựng mới · sprite cache {hit}/{len(viec)}")
    return kq


def xem_lai(video, n=8, ra=None, rong=1600):
    """n khung đều nhau (2 hàng) có nhãn giây → xem-lai.jpg"""
    from PIL import Image, ImageDraw, ImageFont
    inf = chung.ffprobe(video) or {"dur": 1, "w": 1080, "h": 1920}
    dur = max(inf["dur"], 0.1)
    ra = ra or os.path.join(os.path.dirname(video), "xem-lai.jpg")
    cot = (n + 1) // 2
    tw = rong // cot; th = int(tw * inf["h"] / max(inf["w"], 1))
    ban = Image.new("RGB", (tw * cot, th * 2 + 0), (16, 16, 20))
    try:
        fnt = ImageFont.truetype(_chu.font_mac_dinh("phu_de"), 28)
    except Exception:
        fnt = ImageFont.load_default()
    d = ImageDraw.Draw(ban)
    moc = [dur * (i + 0.5) / n for i in range(n)]
    tmp = ra + ".k%d.png"
    sel = "+".join(f"eq(n,{int(round(t * inf['fps']))})" for t in moc)
    chung.sh([chung.duong("ffmpeg"), "-v", "error", "-y", "-i", video, "-vf", f"select='{sel}',scale={tw}:{th}", "-vsync", "0", "-start_number", "0", tmp], timeout=300)
    for i, t in enumerate(moc):
        try:
            im = Image.open(tmp % i).convert("RGB")
            ban.paste(im, ((i % cot) * tw, (i // cot) * th))
            os.remove(tmp % i)
        except Exception:
            pass
        x, y = (i % cot) * tw + 8, (i // cot) * th + 6
        d.rectangle([x - 4, y - 2, x + 70, y + 32], fill=(0, 0, 0))
        d.text((x, y), "%.1fs" % t, fill=(255, 220, 0), font=fnt)
    ban.save(ra, quality=88)
    return ra


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(); ap.add_argument("du_an"); ap.add_argument("--ke-hoach", default=None); ap.add_argument("--song-song", default=None)
    a = ap.parse_args()
    kh = chung.doc_json(a.ke_hoach or os.path.join(a.du_an, "ke-hoach.json"))
    kq = dung(a.du_an, kh, song_song=a.song_song)
    print(json.dumps(kq["giay"], ensure_ascii=False))
    print(xem_lai(kq["video"]))
