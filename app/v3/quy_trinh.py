# -*- coding: utf-8 -*-
"""Điều phối một việc (dự án) từ đầu tới giao, hoặc chạy lại từng bước.

chay(ten, buoc=None, log=chung.log) -> dict kết quả
sua(ten, loi_nguoi_dung)            -> AI lượt 2 với lời sửa → dựng lại → giao
Các bước: doc → cat → tom_tat → ai1 → chuan_hoa → dung → xem_lai → ai2 → kiem_ky_thuat → giao   (che_do "hoc": doc → bang_khung_day → tom_tat → hoc)
Mô-đun của người khác (doc/, dung/, bia/, kho/) import trong try/except — thiếu thì báo "mô-đun X chưa sẵn sàng".
"""
import importlib, json, os, shutil, sys, threading, time, traceback
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung
from ai import dong_co, cong_thuc
from nao import kiem as nao_kiem

BUOC = ["doc", "cat", "tom_tat", "ai1", "chuan_hoa", "dung", "xem_lai", "ai2", "kiem_ky_thuat", "giao"]
BUOC_HOC = ["doc", "bang_khung_day", "tom_tat", "hoc"]


def _mo_dun(ten):
    """import 'doc.proxy' … → module | None"""
    try:
        return importlib.import_module(ten)
    except Exception as ex:
        return None


def _can(ten):
    m = _mo_dun(ten)
    if m is None:
        raise RuntimeError(f"mô-đun {ten} chưa sẵn sàng")
    return m


class _Ctx:
    """ngữ cảnh đơn giản cho bia.ve / lớp py: W,H,fps, font(vai), mau, ke_hoach, mat(t)"""

    def __init__(self, du_an, kh):
        self.du_an, self.ke_hoach = du_an, kh
        self.W, self.H = kh.get("khung") or [1080, 1920]
        self.khung = (self.W, self.H)
        self.fps = kh.get("fps", 30)
        self.mau = kh.get("phong_cach") or {}
        self.phong_cach = self.mau
        self._font = kh.get("font") or {}
        self.nguon = kh.get("nguon") or []
        self.cat = kh.get("cat") or []
        self.mat_json = chung.doc_json(os.path.join(du_an, "doc", "mat.json")) or {}
        self.nguon_json = chung.doc_json(os.path.join(du_an, "doc", "nguon.json")) or {}
        self.quyet_dinh = kh.get("quyet_dinh") or {}          # 1.2.21: lớp/bìa đọc quyết định kênh

    def font(self, vai):
        if vai in self._font and self._font[vai]:
            return self._font[vai]
        gt = cong_thuc.GiaiTaiNguyen(self.du_an, self.mau, {}, [], [], [])
        return gt.font(vai, "ctx", vai if vai in cong_thuc.VAI_FONT else "nhan")

    def mat(self, t):
        m = nao_kiem.mat_trong_khoang(self.mat_json, self.cat, t, t + 0.2, self.W, self.H)
        return {k: m[k] for k in ("x", "y", "w", "h")} if m else None


# ---------------------------------------------------------------- trạng thái việc
def _viec(du_an):
    return chung.doc_json(os.path.join(du_an, "viec.json")) or {}


def _ghi_viec(du_an, **k):
    v = _viec(du_an)
    v.update(k)
    v["cap_nhat"] = time.strftime("%Y-%m-%d %H:%M:%S")
    chung.ghi_json(os.path.join(du_an, "viec.json"), v)
    return v


def _trang_thai(du_an, s, buoc=None):
    k = {"trang_thai": s}
    if buoc is not None:
        k["buoc_hien_tai"] = buoc
    _ghi_viec(du_an, **k)


# ---------------------------------------------------------------- bước ĐỌC
def b_doc(du_an, viec, log, bg):
    proxy = _can("doc.proxy")
    nguon = viec.get("nguon") or []
    if not nguon:
        raise RuntimeError("việc không có nguồn video")
    with chung.DoThoiGian(du_an, "proxy"):
        px = proxy.tao(du_an, nguon)
    am16, pr = px.get("am16"), px.get("proxy")
    loi_m, mat_m, khung_m = _mo_dun("doc.loi"), _mo_dun("doc.mat"), _mo_dun("doc.khung")
    kq = {"proxy": px}

    def chay_loi():
        if loi_m is None:
            log(du_an, "mô-đun doc.loi chưa sẵn sàng → loi.json rỗng")
            chung.ghi_json(os.path.join(du_an, "doc", "loi.json"), {"tu": [], "cau": [], "lang": [], "dem": [], "model": "khong"})
            return None
        with chung.DoThoiGian(du_an, "loi"):
            return loi_m.nhan(du_an, am16)

    def chay_mat():
        if mat_m is None:
            log(du_an, "mô-đun doc.mat chưa sẵn sàng → không có mat.json / bang-khung.jpg")
            return None
        with chung.DoThoiGian(du_an, "mat"):
            return mat_m.quet(du_an, pr)

    def chay_khung():                                 # MẮT tầng 1: đo 100% khung (song song với lời + mặt)
        if khung_m is None:
            log(du_an, "mô-đun doc.khung chưa sẵn sàng → không có khung-so.json")
            return None
        try:
            with chung.DoThoiGian(du_an, "khung (tầng 1)"):
                return khung_m.do(du_an, pr)
        except Exception as ex:
            log(du_an, f"khung tầng 1 lỗi (bỏ qua): {ex}")
            return None

    def chay_broll():                                 # MẮT B-ROLL: video phụ người dùng đưa → bảng khung có giây, cắt cảnh, tiếng, mặt
        phu = [n.get("duong") for n in nguon if isinstance(n, dict) and n.get("vai") == "phu" and n.get("duong")]
        if not phu:
            return None
        try:
            from doc import broll as _BR
            with chung.DoThoiGian(du_an, "b-roll"):
                return _BR.quet(du_an, phu, log=lambda m: log(du_an, m), ten_goc="nguon_phu")
        except Exception as ex:
            log(du_an, f"b-roll lỗi (bỏ qua): {ex}")
            return None

    with ThreadPoolExecutor(max_workers=4) as ex:
        f1, f2, f3, f4 = ex.submit(chay_loi), ex.submit(chay_mat), ex.submit(chay_khung), ex.submit(chay_broll)
        kq["loi"], kq["mat"], kq["khung"], kq["broll"] = f1.result(), f2.result(), f3.result(), f4.result()
    kq["bang_khung"] = b_bang_khung(du_an, viec, log)
    try:                                              # KHUNG ỨNG VIÊN BÌA: máy đo (nét, miệng, mắt, động, lặng) → AI chọn khung_t
        from doc import bia_ung_vien as _BUV
        with chung.DoThoiGian(du_an, "bia-ung-vien"):
            kq["bia_uv"] = _BUV.quet(du_an, pr, log=lambda m: log(du_an, m))
    except Exception as ex:
        log(du_an, f"bìa ứng viên lỗi (bỏ qua): {ex}")
    # alpha nền ưu tiên thấp (nếu có người, RAM trống > 3 GB) — chạy nền, huỷ được
    mat = chung.doc_json(os.path.join(du_an, "doc", "mat.json")) or {}
    alpha_m = _mo_dun("doc.alpha")
    if alpha_m and mat.get("mat_tb") and (mat.get("nguoi_ti_le") or 0) >= 0.5 and chung.ram_trong_gb() > 3 and viec.get("che_do") != "hoc"             and viec.get("tach_nen_som"):           # 1.3: chỉ khi cần nền mới (cầu nối đã tự tách theo lời) — tách cả video tốn GPU/CPU nhiều phút
        bg["huy_alpha"] = threading.Event()

        def chay_alpha():
            try:
                with chung.DoThoiGian(du_an, "alpha"):
                    bg["alpha"] = alpha_m.tao_ranh(du_an, pr, uu_tien_thap=True, huy=bg["huy_alpha"].is_set)
            except Exception as ex:
                log(du_an, f"alpha lỗi (bỏ qua): {ex}")
        th = threading.Thread(target=chay_alpha, daemon=True, name="alpha")
        bg["alpha_thread"] = th
        th.start()
        log(du_an, "alpha: chạy nền ưu tiên thấp")
    return kq


def b_bang_khung(du_an, viec, log, muc=None, ten="bang-khung"):
    """MẮT tầng 2: bảng ảnh cho AI, mật độ theo lượng thay đổi (doc/khung.py) → doc/bang-khung.jpg, -2, … ; trả meta (anh, so_khung…).
    Chưa có số đo tầng 1 → giữ bảng 12 khung của doc/mat.py (nếu có)."""
    km = _mo_dun("doc.khung")
    if km is None or not os.path.isfile(os.path.join(du_an, "doc", "khung-so.json")):
        return None
    try:
        with chung.DoThoiGian(du_an, "khung (tầng 2)"):
            return km.bang(du_an, muc=muc, ten=ten)
    except Exception as ex:
        log(du_an, f"khung tầng 2 lỗi (giữ bảng cũ): {ex}")
        return None


def b_bang_khung_day(du_an, viec, log):
    """bảng khung DÀY cho việc học: tầng 2 ở mức "day" → bang-khung-day.jpg (+ -2 …); thiếu số đo → 6×8 = 48 khung đều (ffmpeg + PIL)."""
    m = b_bang_khung(du_an, viec, log, muc="day", ten="bang-khung-day")
    if m and m.get("anh"):
        return m["anh"][0]
    with chung.DoThoiGian(du_an, "bang_khung_day"):
        ng = (chung.doc_json(os.path.join(du_an, "doc", "nguon.json")) or {}).get("chinh") or {}
        video = ng.get("proxy") or (viec.get("nguon") or [{}])[0].get("duong")
        info = chung.ffprobe(video) or {}
        dur = float(info.get("dur") or 0) or 1
        return _bang_khung(video, dur, os.path.join(du_an, "doc", "bang-khung-day.jpg"), cot=6, hang=8, rong_o=240)


def _bang_khung(video, dur, ra, cot=4, hang=2, rong_o=400, t_list=None):
    """ghép n khung (có mốc giây) thành 1 ảnh. Trả đường dẫn hoặc None."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except Exception:
        return None
    n = cot * hang
    ts = t_list or [dur * (i + 0.5) / n for i in range(n)]
    tam = os.path.join(os.path.dirname(ra), "_khung")
    os.makedirs(tam, exist_ok=True)
    anh = []
    for i, t in enumerate(ts):
        p = os.path.join(tam, f"k{i:02d}.jpg")
        chung.sh([chung.duong("ffmpeg"), "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-vf", f"scale={rong_o}:-2", "-q:v", "4", p], timeout=60)
        anh.append((t, p if os.path.isfile(p) else None))
    co = [Image.open(p) for _, p in anh if p]
    if not co:
        return None
    w, h = co[0].size
    tam_anh = Image.new("RGB", (cot * w, hang * (h + 22)), (20, 20, 24))
    dr = ImageDraw.Draw(tam_anh)
    try:
        f = ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf"), 16)
    except Exception:
        f = ImageFont.load_default()
    for i, (t, p) in enumerate(anh):
        x, y = (i % cot) * w, (i // cot) * (h + 22)
        if p:
            tam_anh.paste(Image.open(p).resize((w, h)), (x, y))
        dr.text((x + 6, y + h + 3), f"{t:.1f}s", font=f, fill=(255, 230, 0))
    tam_anh.save(ra, quality=82)
    shutil.rmtree(tam, ignore_errors=True)
    return ra


# ---------------------------------------------------------------- CẮT, TÓM TẮT
def _nhip_cat(du_an, viec):
    """1.2.21 (4a): nhịp cắt do AI truyền — cong-thuc.json["nhip"] (hoặc cat_tu_dong.nhip) → quyet-dinh của kênh (ke-hoach / viec
    quyet_dinh["cat"]["nhip"]) → None (máy đề xuất theo bảng "vua" nhưng ghi nhip_nguon="may_mac_dinh" để AI thấy và đổi)."""
    ct = chung.doc_json(os.path.join(du_an, "cong-thuc.json")) or {}
    n = ct.get("nhip") or ((ct.get("cat_tu_dong") or {}).get("nhip") if isinstance(ct.get("cat_tu_dong"), dict) else None)
    if not n:
        for src in (chung.doc_json(os.path.join(du_an, "ke-hoach.json")) or {}, viec or {}):
            qd = src.get("quyet_dinh") or {}
            n = (qd.get("cat") or {}).get("nhip") if isinstance(qd.get("cat"), dict) else None
            if n:
                break
    n = str(n or "").lower()
    return n if n in ("nhanh", "vua", "cham") else None


def b_cat(du_an, viec, log, nhip=None):
    with chung.DoThoiGian(du_an, "cat"):
        m = _mo_dun("doc.cat")
        ra = os.path.join(du_an, "doc", "cat-de-xuat.json")
        ng = (chung.doc_json(os.path.join(du_an, "doc", "nguon.json")) or {}).get("chinh") or {}
        nhip = nhip or _nhip_cat(du_an, viec)
        if m is not None:
            try:
                return m.de_xuat(chung.doc_json(os.path.join(du_an, "doc", "loi.json")) or {}, ng.get("am16"), du_an=du_an, nhip=nhip)
            except Exception as ex:
                log(du_an, f"doc.cat lỗi ({ex}) → giữ toàn bộ")
        else:
            log(du_an, "mô-đun doc.cat chưa sẵn sàng → giữ toàn bộ")
        # dự phòng: giữ toàn bộ nguồn chính, bỏ lặng dài > 0.8 s theo loi.json nếu có
        src0 = (viec.get("nguon") or [{}])[0].get("duong")
        info = chung.ffprobe(src0) or {}
        dur = float(info.get("dur") or 0)
        giu, bo = [], []
        loi = chung.doc_json(os.path.join(du_an, "doc", "loi.json")) or {}
        cuoi = 0.0
        for a, b in loi.get("lang") or []:
            if b - a > 0.8 and a > cuoi:
                giu.append({"src": 0, "a": round(cuoi, 3), "b": round(a + 0.25, 3)})
                bo.append({"a": round(a + 0.25, 3), "b": round(b - 0.25, 3), "ly_do": "lang"})
                cuoi = b - 0.25
        if dur > cuoi:
            giu.append({"src": 0, "a": round(cuoi, 3), "b": round(dur, 3)})
        if not giu:
            giu = [{"src": 0, "a": 0.0, "b": round(dur, 3)}]
        chung.ghi_json(ra, {"giu": giu, "bo": bo, "dur_sau": round(cong_thuc.dur_cat(giu), 3)})
        return ra


def b_tom_tat(du_an, viec, log):
    with chung.DoThoiGian(du_an, "tom_tat"):
        m = _mo_dun("doc.tom_tat")
        if m is not None:
            try:
                return m.viet(du_an)
            except Exception as ex:
                log(du_an, f"doc.tom_tat lỗi ({ex}) → tóm tắt dự phòng")
        else:
            log(du_an, "mô-đun doc.tom_tat chưa sẵn sàng → tóm tắt dự phòng")
        return _tom_tat_du_phong(du_an, viec)


def _tom_tat_du_phong(du_an, viec):
    loi = chung.doc_json(os.path.join(du_an, "doc", "loi.json")) or {}
    mat = chung.doc_json(os.path.join(du_an, "doc", "mat.json")) or {}
    cat = chung.doc_json(os.path.join(du_an, "doc", "cat-de-xuat.json")) or {}
    giu = cat.get("giu") or [{"src": 0, "a": 0, "b": 0}]
    d = [f"# Tóm tắt (dự phòng) — {viec.get('ten')}", ""]
    d.append("## Nguồn")
    for i, n in enumerate(viec.get("nguon") or []):
        info = chung.ffprobe(n.get("duong")) or {}
        d.append(f"- src {i} ({n.get('vai', 'chinh')}): {os.path.basename(n.get('duong', ''))}, {info.get('dur', 0):.1f} s, {info.get('w')}×{info.get('h')}, {'có' if info.get('co_am') else 'không'} tiếng")
    d += ["", f"## Lời theo giây thành phẩm (đề xuất cắt giữ {len(giu)} đoạn, {cat.get('dur_sau', 0)} s)"]
    cau = loi.get("cau") or []
    if cau:
        for c in cau[:120]:
            a = cong_thuc.goc_sang_tp(giu, c["a"]); b = cong_thuc.goc_sang_tp(giu, c["b"])
            if a is None and b is None:
                continue
            d.append(f"- [{(a if a is not None else 0):05.1f}–{(b if b is not None else a):05.1f}] {c.get('txt', '')}")
    else:
        d.append("- (không nhận được lời — video không tiếng hoặc Whisper chưa chạy)")
    tb = mat.get("mat_tb") or {}
    d += ["", "## Mặt"]
    if tb.get("w"):
        d.append(f"- Mặt trung bình: x={tb['x']:.2f} y={tb['y']:.2f} w={tb['w']:.2f} h={tb['h']:.2f} (tâm {tb['x'] + tb['w'] / 2:.2f}, {tb['y'] + tb['h'] / 2:.2f}); có mặt {100 * (mat.get('nguoi_ti_le') or 0):.0f}% thời gian; cằm y≈{tb['y'] + tb['h']:.2f}; đỉnh đầu y≈{tb['y']:.2f}")
        d.append(f"- Vùng trống: trên mặt y<{max(0, tb['y'] - 0.03):.2f}; dưới cằm y {tb['y'] + tb['h'] + 0.03:.2f}–0.78")
    else:
        d.append("- không phát hiện mặt (hoặc mô-đun mat chưa chạy)")
    canh = chung.doc_json(os.path.join(du_an, "doc", "canh.json")) or {}
    if canh.get("canh"):
        d += ["", "## Cảnh"] + [f"- [{c['a']:.1f}–{c['b']:.1f}] {c.get('kieu')} sáng {c.get('sang', 0):.2f}" for c in canh["canh"][:30]]
        if canh.get("mau_chu_dao"):
            d.append("- màu chủ đạo: " + ", ".join(canh["mau_chu_dao"]))
    d += ["", "## Gợi ý kho"]
    try:
        from kho import tim
        for loai, q in (("nhac", viec.get("yeu_cau") or "nhạc nền nhẹ"), ("sfx", "whoosh pop ding")):
            ds = tim.tim(loai=loai, nghia=q, n=5)
            d.append(f"- {loai}: " + (", ".join(m["id"] for m in ds) if ds else "(kho trống)"))
    except Exception:
        d.append("- (mô-đun kho chưa sẵn sàng — ghi nhạc/sfx theo nghĩa)")
    p = os.path.join(du_an, "doc", "tom-tat.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(d)[:6000])
    return p


# ---------------------------------------------------------------- AI, CHUẨN HOÁ
def b_ai1(du_an, viec, log):
    with chung.DoThoiGian(du_an, "ai1"):
        return dong_co.luot_1(du_an)


def _chuan_hoa_kiem(du_an, ct_path, log):
    kh, loi = cong_thuc.chuan_hoa(du_an, ct_path)
    kq = nao_kiem.kiem(du_an, kh)
    kh = chung.doc_json(os.path.join(du_an, "ke-hoach.json")) or kh
    chan = [l for l in kq["loi"] if not l.get("khong_sua_duoc")]
    log(du_an, f"chuẩn hoá: {len(kh['lop'])} lớp, {kh['dur']}s; kiểm: {len(kq['loi'])} lỗi, {len(kq['may_sua'])} máy sửa, {len(kq['canh_bao'])} cảnh báo")
    return kh, kq, chan


def b_chuan_hoa(du_an, viec, log, bg=None, ct_path=None, goi_lai=True):
    with chung.DoThoiGian(du_an, "chuan_hoa"):
        ct_path = ct_path or os.path.join(du_an, "cong-thuc.json")
        if not os.path.isfile(ct_path):
            raise RuntimeError("chưa có cong-thuc.json — chạy bước ai1 trước")
        kh, kq, chan = _chuan_hoa_kiem(du_an, ct_path, log)
        if chan and goi_lai and viec.get("che_do") != "thu":
            log(du_an, f"máy chặn {len(chan)} lỗi → gọi lại AI một lần")
            try:
                with chung.DoThoiGian(du_an, "ai1-sua"):
                    dong_co.luot_1(du_an, loi=kq)
                kh, kq, chan = _chuan_hoa_kiem(du_an, ct_path, log)
            except RuntimeError as ex:
                log(du_an, f"gọi lại AI thất bại: {ex} — dựng với công thức hiện có")
        if chan:
            log(du_an, "vẫn còn lỗi chặn: " + "; ".join(f"{l['id']}@{l.get('lop')}" for l in chan[:8]) + " — ghi vào báo cáo, vẫn dựng")
        # huỷ alpha nền nếu công thức không cần
        if bg and bg.get("huy_alpha") and not kh.get("can_alpha"):
            bg["huy_alpha"].set()
            log(du_an, "alpha: công thức không dùng nen_moi/bìa người → huỷ")
        return kh


# ---------------------------------------------------------------- DỰNG, XEM LẠI, BÌA
def b_dung(du_an, viec, log, bg=None):
    kh = chung.doc_json(os.path.join(du_an, "ke-hoach.json"))
    if not kh:
        raise RuntimeError("chưa có ke-hoach.json — chạy bước chuan_hoa trước")
    if bg and kh.get("can_alpha") and bg.get("alpha_thread") and bg["alpha_thread"].is_alive():
        log(du_an, "đợi alpha nền xong…")
        bg["alpha_thread"].join()
    d = _can("dung.dung")
    with chung.DoThoiGian(du_an, "dung"):
        kq = d.dung(du_an, kh)
    video = kq.get("video") if isinstance(kq, dict) else kq
    if not video or not os.path.isfile(video):
        raise RuntimeError("dung.dung không trả video")
    log(du_an, f"dựng xong: {os.path.basename(video)} ({kq.get('giay', '?')}s, cache sprite {kq.get('sprite_cache_hit', 0)})" if isinstance(kq, dict) else f"dựng xong: {video}")
    return video


def _video(du_an):
    for p in (os.path.join(du_an, "dung", "thanh-pham.mp4"),):
        if os.path.isfile(p):
            return p
    return None


def b_xem_lai(du_an, viec, log):
    video = _video(du_an)
    if not video:
        raise RuntimeError("chưa có dung/thanh-pham.mp4 — chạy bước dung trước")
    kh = chung.doc_json(os.path.join(du_an, "ke-hoach.json")) or {}
    with chung.DoThoiGian(du_an, "xem_lai"):
        d = _mo_dun("dung.dung")
        ra = os.path.join(du_an, "dung", "xem-lai.jpg")
        ok = None
        if d is not None and hasattr(d, "xem_lai"):
            try:
                ok = d.xem_lai(video, 8)
            except Exception as ex:
                log(du_an, f"dung.xem_lai lỗi ({ex}) → ghép khung dự phòng")
        if not ok:
            info = chung.ffprobe(video) or {}
            _bang_khung(video, float(info.get("dur") or 1), ra, cot=4, hang=2, rong_o=405)
    with chung.DoThoiGian(du_an, "bia"):
        bia = _ve_bia(du_an, kh, log)
    return {"xem_lai": ra, "bia": bia}


def _ghi_loi_bia(du_an, loi, log):
    """lỗi bìa (thiếu trường / engine lỗi) → kiem.json["loi"] + ["loi_dung"] dạng hợp đồng {"duong","ma","goi_y"} để AI sửa công thức"""
    try:
        p = os.path.join(du_an, "kiem.json")
        d = chung.doc_json(p) or {"loi": [], "may_sua": [], "canh_bao": []}
        d["loi"] = [l for l in d.get("loi") or [] if not (isinstance(l, dict) and l.get("lop") == "bia")] + loi
        d["loi_dung"] = [l for l in d.get("loi_dung") or [] if not (isinstance(l, dict) and l.get("lop") == "bia")] + loi
        chung.ghi_json(p, d)
    except Exception as ex:
        log(du_an, f"ghi lỗi bìa vào kiem.json lỗi: {ex}")
    for l in loi:
        log(du_an, f"bìa: ⛔ {l.get('duong')} [{l.get('ma')}] {l.get('mo_ta') or l.get('goi_y') or ''}")


def _ve_bia(du_an, kh, log):
    """1.2.21: KHÔNG còn bìa mặc định / bìa dự phòng của máy (gu nhà phát hành). AI phải ghi bia.thiet_ke (hoặc bia.phuong_an[]);
    thiếu → lỗi thieu_truong trả AI (kiem.json), trả []. Số bìa = số phương án AI ghi (bia.bia của A3)."""
    bia = kh.get("bia") or {}
    spec = dict(bia)
    pa = [p_ for p_ in (spec.get("phuong_an") or []) if isinstance(p_, dict) and p_.get("thiet_ke")]
    if not spec.get("thiet_ke") and not pa:
        _ghi_loi_bia(du_an, [{"id": "thieu_truong", "lop": "bia", "duong": "bia.phuong_an", "ma": "thieu_truong",
                              "goi_y": "ghi bia.phuong_an: [{khung_t, ten, thiet_ke:{nen, nguoi, chu[], khoi[], hinh[]}}] (≥ 1 phương án) hoặc bia.thiet_ke",
                              "mo_ta": "AI chưa ghi thiết kế bìa — máy không tự bịa bìa mặc định"}], log)
        return []
    m = _mo_dun("bia.bia")
    if m is None:
        _ghi_loi_bia(du_an, [{"id": "bia_loi", "lop": "bia", "duong": "bia", "ma": "khong_biet", "mo_ta": "mô-đun bia.bia chưa sẵn sàng"}], log)
        return []
    try:
        try:                                       # ngữ cảnh của engine (font_file, kho, nguồn đã giải) — giống lúc dựng
            from dung import dung as _dung_mod
            import copy as _copy
            ctx_b = _dung_mod.tao_ctx(du_an, _copy.deepcopy(kh))
        except Exception:
            ctx_b = _Ctx(du_an, kh)
        ds = m.ve(du_an, spec, ctx_b)
        ds = [p for p in (ds or []) if p and os.path.isfile(p)]
        if ds:
            return ds
        _ghi_loi_bia(du_an, [{"id": "bia_loi", "lop": "bia", "duong": "bia.phuong_an", "ma": "khong_biet", "mo_ta": "bia.ve không trả ảnh nào — xem bia-kiem.json"}], log)
    except Exception as ex:
        # R4a (1.2.21): bia.bia ném dung.chu.ThieuTruong (= lop.ThieuTruong, .loi() → dict) chứ KHÔNG phải chung.ThieuTruong (.loi là list)
        # → bắt theo tên lớp + gom cả hai dạng; trước đây rơi xuống "khong_biet", AI không thấy đường trường để sửa
        ds_tt = _thieu_truong_cua(ex)
        if ds_tt:
            _ghi_loi_bia(du_an, [dict(l, id="thieu_truong", lop="bia", ma=l.get("ma") or "thieu_truong") for l in ds_tt], log)
        else:
            _ghi_loi_bia(du_an, [{"id": "bia_loi", "lop": "bia", "duong": "bia", "ma": "khong_biet", "mo_ta": f"bia.ve lỗi: {ex}"}], log)
    return []


def _thieu_truong_cua(ex):
    """ThieuTruong của mọi mô-đun → [{"duong","ma","goi_y"|"mo_ta"}] : chung.ThieuTruong (.loi list) | dung.chu.ThieuTruong (.loi() dict); khác → None"""
    if type(ex).__name__ != "ThieuTruong":
        return None
    l = getattr(ex, "loi", None)
    try:
        l = l() if callable(l) else l
    except Exception:
        l = None
    if isinstance(l, dict):
        l = [l]
    if not isinstance(l, list):
        l = [{"duong": getattr(ex, "duong", str(ex)), "ma": "thieu_truong", "goi_y": getattr(ex, "goi_y", "")}]
    return [x for x in l if isinstance(x, dict)] or None


# ---------------------------------------------------------------- AI LƯỢT 2
def b_ai2(du_an, viec, log, bg=None, sua_them=None):
    """lượt 2: duyệt hoặc sửa (tối đa 1 lần dựng lại). Chế độ nhanh → tự duyệt bìa 1."""
    if viec.get("che_do") == "nhanh" and not sua_them:
        chung.ghi_json(os.path.join(du_an, "duyet.json"), {"duyet": True, "bia": 1, "nhan_xet": "chế độ Nhanh: tự duyệt", "tu_dong": True})
        log(du_an, "chế độ Nhanh → bỏ lượt 2, tự duyệt bìa 1")
        return {"duyet": True, "bia": 1}
    with chung.DoThoiGian(du_an, "ai2" + ("-sua" if sua_them else "")):
        kq = dong_co.luot_2(du_an, sua_them=sua_them)
    if kq.get("duyet") is None:
        log(du_an, f"lượt 2 không có kết quả ({kq.get('loi')}) → giữ bản hiện tại, bìa 1")
        chung.ghi_json(os.path.join(du_an, "duyet.json"), {"duyet": True, "bia": 1, "nhan_xet": kq.get("loi") or "", "tu_dong": True})
        return {"duyet": True, "bia": 1}
    if kq["duyet"]:
        log(du_an, f"AI duyệt, chọn bìa {kq['bia']}: {kq.get('nhan_xet', '')}")
        return kq
    log(du_an, f"AI sửa (cong-thuc.v2.json), bìa {kq['bia']}: {kq.get('nhan_xet', '')}")
    b_chuan_hoa(du_an, viec, log, bg, ct_path=kq["cong_thuc"], goi_lai=False)
    b_dung(du_an, viec, log, bg)
    b_xem_lai(du_an, viec, log)
    return kq


def b_kiem_ky_thuat(du_an, viec, log):
    video = _video(du_an)
    if not video:
        raise RuntimeError("chưa có video để kiểm kỹ thuật")
    with chung.DoThoiGian(du_an, "kiem_ky_thuat"):
        kt = nao_kiem.kiem_ky_thuat(video)
        nao_kiem.ghi_ky_thuat(du_an, kt)
    log(du_an, f"kỹ thuật: LUFS {kt.get('lufs')}, peak {kt.get('peak')}, đen {len(kt['khung_den'])}, đứng {len(kt['dong_bang'])}")
    return kt


# ---------------------------------------------------------------- GIAO
def _bao_cao(du_an, viec):
    ten = viec.get("ten") or os.path.basename(du_an)
    tg = chung.doc_json(os.path.join(du_an, "nhat-ky-thoi-gian.json"), []) or []
    kiem = chung.doc_json(os.path.join(du_an, "kiem.json")) or {}
    kh = chung.doc_json(os.path.join(du_an, "ke-hoach.json")) or {}
    duyet = chung.doc_json(os.path.join(du_an, "duyet.json")) or {}
    cp = dong_co.chi_phi(du_an)
    d = [f"# Báo cáo — {ten}", "", f"- Hồ sơ: {viec.get('ho_so') or '(không)'} · chế độ: {viec.get('che_do')} · khung {kh.get('khung')} · {kh.get('dur', 0)} s · {len(kh.get('lop') or [])} lớp", ""]
    d += ["## Thời gian từng bước", "", "| bước | giây | lần |", "|---|---:|---:|"]
    gop = {}
    for m in tg:
        g = gop.setdefault(m["buoc"], [0.0, 0])
        g[0] += m["giay"]; g[1] += 1
    tong = sum(v[0] for v in gop.values())
    for b, (g, n) in gop.items():
        d.append(f"| {b} | {g:.1f} | {n} |")
    d.append(f"| **tổng** | **{tong:.1f}** | |")
    d += ["", "## Chi phí AI", "", f"- {cp['so_lan']} lần gọi · {cp['giay']} s · ${cp['usd']:.3f}"]
    for m in cp["muc"]:
        d.append(f"  - {m.get('buoc')}: ${m.get('usd') or 0:.3f}, {m.get('giay')} s" + (f" — {m.get('loi')}" if m.get("loi") else ""))
    d += ["", "## Lỗi / máy sửa", ""]
    loi = kiem.get("loi") or []
    d.append(f"- Lỗi chặn còn lại: {len(loi)}")
    d += [f"  - [{l.get('id')}] {l.get('lop')}: {l.get('mo_ta')}" for l in loi[:30]]
    ms = kiem.get("may_sua") or []
    d.append(f"- Máy tự sửa số: {len(ms)}")
    d += [f"  - {m.get('lop')}: {m.get('mo_ta')}" for m in ms[:30]]
    cb = kiem.get("canh_bao") or []
    if cb:
        d.append(f"- Cảnh báo (gu/kỹ thuật): {len(cb)}")
        d += [f"  - [{c.get('id')}] {c.get('lop', '')}: {c.get('mo_ta')}" for c in cb[:30]]
    kt = kiem.get("ky_thuat") or {}
    if kt:
        d += ["", "## Kỹ thuật", "", f"- LUFS {kt.get('lufs')} · true peak {kt.get('peak')} dBTP · LRA {kt.get('lra')} · đoạn đen {kt.get('khung_den')} · đứng hình {kt.get('dong_bang')}"]
    tk = kh.get("tra_kho") or []
    if tk:
        d += ["", "## Kho đã tra theo nghĩa", ""] + [f"- {t.get('lop')}: “{t.get('nghia')}” → {t.get('id')}" for t in tk]
    d += ["", "## Ghi chú của AI", "", f"- Lượt 1: {kh.get('ghi_chu') or '(không)'}", f"- Lượt 2: {'duyệt' if duyet.get('duyet') else 'sửa'} · bìa {duyet.get('bia', 1)} · {duyet.get('nhan_xet') or ''}"]
    sua = viec.get("sua") or []
    if sua:
        d += ["", "## Lời sửa của người dùng", ""] + [f"- {s.get('luc', '')}: {s.get('loi')}" for s in sua]
    os.makedirs(os.path.join(du_an, "giao"), exist_ok=True)
    p = os.path.join(du_an, "giao", "bao-cao.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("\n".join(d))
    return p


def b_giao(du_an, viec, log):
    with chung.DoThoiGian(du_an, "giao"):
        video = _video(du_an)
        if not video:
            raise RuntimeError("chưa có video để giao")
        ten = viec.get("ten") or os.path.basename(du_an)
        giao = os.path.join(du_an, "giao")
        os.makedirs(giao, exist_ok=True)
        ra_v = video                                       # 1.2.21 (1h): không chép thêm giao/<tên>.mp4 — trỏ thẳng dung/thanh-pham.mp4
        open(os.path.join(giao, ".du-an"), "w", encoding="utf-8").write(os.path.abspath(du_an))
        duyet = chung.doc_json(os.path.join(du_an, "duyet.json")) or {}
        b = int(duyet.get("bia") or 1)
        bia = os.path.join(du_an, "dung", f"bia-{b}.png")
        ra_b = None
        if os.path.isfile(bia):
            ra_b = os.path.join(giao, f"{ten}-bia.png")
            shutil.copy2(bia, ra_b)
        bc = _bao_cao(du_an, viec)
        _ghi_viec(du_an, giao={"video": ra_v, "bia": ra_b, "bao_cao": bc, "luc": time.strftime("%Y-%m-%d %H:%M:%S")})
        log(du_an, f"giao: {ra_v}")
        return {"video": ra_v, "bia": ra_b, "bao_cao": bc}


# ---------------------------------------------------------------- HỌC
def b_hoc(du_an, viec, log):
    with chung.DoThoiGian(du_an, "hoc"):
        p = dong_co.hoc(du_an, viec.get("ho_so"))
    hs = viec.get("ho_so")
    if hs:
        tm = os.path.join(chung.duong("ho_so"), hs)
        os.makedirs(os.path.join(tm, "hoc"), exist_ok=True)
        shutil.copy2(p, os.path.join(tm, "style-spec.json"))
        shutil.copy2(p, os.path.join(tm, "hoc", f"{viec.get('ten')}-style-spec.json"))
        for f in ("bang-khung-day.jpg", "bang-khung.jpg"):
            src = os.path.join(du_an, "doc", f)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(tm, "hoc", f"{viec.get('ten')}-{f}"))
        log(du_an, f"đã lưu style-spec.json vào hồ sơ {hs}")
    return p


# ---------------------------------------------------------------- điều phối
def chay(ten, buoc=None, log=chung.log):
    """chạy toàn bộ (buoc=None) hoặc một bước. Trả {"ok", "buoc", "ket_qua"|"loi"}."""
    du_an = chung.du_an_duong(ten)
    viec = _viec(du_an)
    if not viec:
        return {"ok": False, "loi": f"không có việc {ten}"}
    hoc = viec.get("che_do") == "hoc"
    ds = BUOC_HOC if hoc else BUOC
    if buoc:
        if buoc not in ds and buoc not in ("bia", "sua"):
            return {"ok": False, "loi": f"bước `{buoc}` không có (có: {', '.join(ds)})"}
        ds = [buoc]
    bg = {}
    kq = {}
    t_bat_dau = time.time()
    _trang_thai(du_an, "dang_chay", ds[0])
    log(du_an, f"═══ bắt đầu {ten} ({'học' if hoc else viec.get('che_do', 'ky')}): {' → '.join(ds)}")
    try:
        for b in ds:
            _trang_thai(du_an, "dang_chay", b)
            if b == "doc":
                kq[b] = b_doc(du_an, viec, log, bg)
            elif b == "bang_khung_day":
                kq[b] = b_bang_khung_day(du_an, viec, log)
            elif b == "cat":
                kq[b] = b_cat(du_an, viec, log)
            elif b == "tom_tat":
                kq[b] = b_tom_tat(du_an, viec, log)
            elif b == "ai1":
                kq[b] = b_ai1(du_an, viec, log)
            elif b == "chuan_hoa":
                kq[b] = b_chuan_hoa(du_an, viec, log, bg)
            elif b == "dung":
                kq[b] = b_dung(du_an, viec, log, bg)
            elif b in ("xem_lai", "bia"):
                kq[b] = b_xem_lai(du_an, viec, log)
            elif b == "ai2":
                kq[b] = b_ai2(du_an, viec, log, bg)
            elif b == "kiem_ky_thuat":
                kq[b] = b_kiem_ky_thuat(du_an, viec, log)
            elif b == "giao":
                kq[b] = b_giao(du_an, viec, log)
            elif b == "hoc":
                kq[b] = b_hoc(du_an, viec, log)
        if bg.get("huy_alpha"):
            bg["huy_alpha"].set()
        tong = time.time() - t_bat_dau
        _trang_thai(du_an, "xong", None)
        log(du_an, f"═══ xong {ten} sau {tong:.0f}s")
        return {"ok": True, "buoc": ds, "ket_qua": {k: (v if isinstance(v, (str, dict, list, int, float)) or v is None else str(v)) for k, v in kq.items()}, "giay": round(tong, 1)}
    except Exception as ex:
        if bg.get("huy_alpha"):
            bg["huy_alpha"].set()
        tb = traceback.format_exc(limit=4)
        msg = f"{type(ex).__name__}: {ex}"
        log(du_an, f"✖ lỗi ở bước {viec.get('buoc_hien_tai') or '?'}: {msg}")
        log(du_an, tb.strip().splitlines()[-1] if tb else "")
        _ghi_viec(du_an, trang_thai="loi", loi=msg, loi_chi_tiet=tb[-2000:])
        return {"ok": False, "buoc": ds, "loi": msg}


def sua(ten, loi_nguoi_dung, log=chung.log):
    """lời sửa của người dùng → AI lượt 2 (sửa) → dựng lại → kiểm kỹ thuật → giao."""
    du_an = chung.du_an_duong(ten)
    viec = _viec(du_an)
    if not viec:
        return {"ok": False, "loi": f"không có việc {ten}"}
    ds = list(viec.get("sua") or [])
    ds.append({"loi": loi_nguoi_dung, "luc": time.strftime("%Y-%m-%d %H:%M:%S")})
    viec = _ghi_viec(du_an, sua=ds, trang_thai="dang_chay", buoc_hien_tai="ai2-sua")
    log(du_an, f"═══ sửa thêm: {loi_nguoi_dung}")
    try:
        if not os.path.isfile(os.path.join(du_an, "ke-hoach.json")):
            raise RuntimeError("việc chưa dựng xong lần nào — chạy toàn bộ trước")
        kq = b_ai2(du_an, viec, log, None, sua_them=loi_nguoi_dung)
        _trang_thai(du_an, "dang_chay", "kiem_ky_thuat")
        b_kiem_ky_thuat(du_an, viec, log)
        _trang_thai(du_an, "dang_chay", "giao")
        g = b_giao(du_an, viec, log)
        _trang_thai(du_an, "xong", None)
        log(du_an, "═══ sửa xong")
        return {"ok": True, "duyet": kq, "giao": g}
    except Exception as ex:
        msg = f"{type(ex).__name__}: {ex}"
        log(du_an, f"✖ sửa lỗi: {msg}")
        _ghi_viec(du_an, trang_thai="loi", loi=msg)
        return {"ok": False, "loi": msg}


def tao(nguon, yeu_cau="", ho_so="", che_do="ky", khung=None, fps=None, ten=None):
    """tạo thư mục việc + viec.json. nguon: [đường dẫn] hoặc [{"duong","vai"}]. Trả tên việc."""
    cfg = chung.cau_hinh()
    ds = []
    for i, n in enumerate(nguon or []):
        if isinstance(n, dict):
            ds.append({"duong": os.path.abspath(n["duong"]), "vai": n.get("vai") or ("chinh" if i == 0 else "phu")})
        else:
            ds.append({"duong": os.path.abspath(str(n)), "vai": "chinh" if i == 0 else "phu"})
    goc = chung.slug(os.path.splitext(os.path.basename(ds[0]["duong"]))[0] if ds else (yeu_cau or "viec"), 28)
    ten = ten or f"{time.strftime('%Y%m%d-%H%M%S')}-{goc}"
    du_an = chung.du_an_duong(ten)
    os.makedirs(os.path.join(du_an, "doc"), exist_ok=True)
    v = {"ten": ten, "ho_so": ho_so or "", "nguon": ds, "yeu_cau": yeu_cau or "", "khung": khung or cfg.get("khung_mac_dinh") or [1080, 1920],
         "fps": fps or cfg.get("fps_mac_dinh") or 30, "che_do": che_do if che_do in ("nhanh", "ky", "hoc") else "ky", "trang_thai": "moi",
         "tao_luc": time.strftime("%Y-%m-%d %H:%M:%S")}
    chung.ghi_json(os.path.join(du_an, "viec.json"), v)
    return ten


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(chay(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None), ensure_ascii=False, indent=1))
