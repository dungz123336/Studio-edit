# -*- coding: utf-8 -*-
"""DỰNG LẠI SO VỚI GỐC (vòng kiểm của bộ học 1.2.20) — bản ghi thi công → dựng bằng chính engine lên video mẫu (không cắt, không phụ đề)
→ đặt cạnh gốc tại các mốc từng cụm → đo: lệch vị trí (IoU hộp chữ), đúng giờ, chữ đọc được.
Kết quả: <thu_muc>/doi-chieu.json + doi-chieu-N.jpg. AI đọc ảnh/điểm, sửa bản ghi (font, cỡ, neo) rồi chạy lại nếu cần.

1.2.21: · bản chép dùng HỌ font ghi trong bản ghi (`font_xac_nhan` do AI ghi sau khi xem cận chữ → `font` máy ghi theo độ đậm đo), không cố định
        · cỡ chữ KẸP theo chiều cao mực đo (`_do.cao_muc_px_1920`) bằng cách vẽ thử glyph rồi scale `co`; giữ `dx`/`xoay`
        · lớp đánh dấu `ne_mat:false, toan_khung:true, co_y:true` → không né mặt / vùng an toàn (đường tắt); nếu máy kiểm vẫn dời
          (may_sua vung_an_toan/doi/thu) → vá ke-hoach.json rồi dựng lại bằng dung.dung trực tiếp
        · "đúng giờ" + IoU đo bằng ALPHA SPRITE của lớp (engine vẽ lớp tại mốc, có mặt nạ) thay vì hiệu ảnh sau re-encode; hiệu ảnh giữ làm số phụ
        · t0 lớp đồng bộ `t_du − dai` của dòng (mốc máy đo)
        · KHÔNG ghi đè app/.phieu2-hien-tai: con trỏ việc riêng trong <thu_muc>, truyền qua QUY_TRINH_PHIEU2

  chay(thu_muc, ho_so, log, du_an=None) → {"json", "anh", "diem"}     (cần ban-ghi-lop.json của ban_ghi.tao)
Dùng luồng chuẩn của máy dựng (st.py bat-dau → nhanh doc → cong-thuc.json → nhanh tron) để kết quả đúng như khi dựng thật.
"""
import os, sys, json, time, subprocess, re
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung as C

APP = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V3 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ST = os.path.join(APP, "v2", "st.py")
PHIEU = os.path.join(APP, ".phieu2-hien-tai")          # chỉ ĐỌC (tìm việc đang mở khi không truyền --du-an); không bao giờ ghi


def _py():
    return sys.executable


def _chay(args, log, timeout=1800, env=None):
    e = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    if env:
        e.update(env)
    p = subprocess.run([_py(), "-X", "utf8", ST, *args], cwd=APP, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                       env=e, creationflags=(0x08000000 if os.name == "nt" else 0))
    out = (p.stdout or "") + (p.stderr or "")
    for dong in out.strip().splitlines()[-6:]:
        log("    | " + dong[:160])
    return p.returncode, out


def _dh():
    import importlib.util
    if "hoc_dong_hoc" in sys.modules:
        return sys.modules["hoc_dong_hoc"]
    sp = importlib.util.spec_from_file_location("hoc_dong_hoc", os.path.join(os.path.dirname(os.path.abspath(__file__)), "dong_hoc.py"))
    m = importlib.util.module_from_spec(sp); sys.modules["hoc_dong_hoc"] = m; sp.loader.exec_module(m)
    return m


def _ocr():
    return _dh().ocr


def _khung(video, t, canh=540):
    """một khung BGR tại t, cạnh ngắn `canh` (giữ tỉ lệ)"""
    cmd = [C.duong("ffmpeg"), "-v", "error", "-nostdin", "-ss", f"{max(0.0, t):.3f}", "-i", video, "-frames:v", "1",
           "-vf", f"scale='if(gt(iw,ih),-2,{canh})':'if(gt(iw,ih),{canh},-2)'", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.run(cmd, capture_output=True, creationflags=(0x08000000 if os.name == "nt" else 0))
    info = C.ffprobe(video) or {}
    w0, h0 = int(info.get("w") or 1080), int(info.get("h") or 1920)
    if w0 > h0:
        h, w = canh, int(round(w0 * canh / h0 / 2)) * 2
    else:
        w, h = canh, int(round(h0 * canh / w0 / 2)) * 2
    if len(p.stdout) < w * h * 3:
        return None
    return np.frombuffer(p.stdout[:w * h * 3], np.uint8).reshape(h, w, 3)


def _khung_nhieu(video, ts, canh=540):
    """nhiều khung BGR (cạnh ngắn `canh`) trong MỘT lượt đọc tuần tự → {t: BGR} (1.2.21: thay N lần ffmpeg)"""
    info = C.ffprobe(video) or {}
    W0, H0 = int(info.get("w") or 1080), int(info.get("h") or 1920)
    if W0 > H0:
        h, w = canh, int(round(W0 * canh / H0 / 2)) * 2
    else:
        w, h = canh, int(round(H0 * canh / W0 / 2)) * 2
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        return {t: _khung(video, t, canh) for t in ts}
    fps = float(cap.get(cv2.CAP_PROP_FPS) or info.get("fps") or 30.0) or 30.0
    can = {}
    for t in ts:
        can.setdefault(max(0, int(round(t * fps))), []).append(t)
    ra = {}
    j = 0; cuoi = max(can) if can else -1
    while j <= cuoi:
        if not cap.grab():
            break
        if j in can:
            ok, f = cap.retrieve()
            if ok and f is not None:
                f = cv2.resize(f, (w, h), interpolation=cv2.INTER_AREA)
                for t in can[j]:
                    ra[t] = f
        j += 1
    cap.release()
    return ra


def _iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i
    return i / u if u > 0 else 0.0


def _khong_dau(s):
    import unicodedata
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D")
    return re.sub(r"[^A-Za-z0-9]", "", s).upper()


def _giong(a, b):
    """độ giống 2 chuỗi (0..1) — tỉ lệ ký tự chung theo thứ tự (LCS xấp xỉ bằng difflib)"""
    import difflib
    a, b = _khong_dau(a), _khong_dau(b)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# ─────────────────────────────────────────────────────────────── font + cỡ theo mực đo
def _ho_font(d):
    """họ font cho bản chép: AI xác nhận (`font_xac_nhan`, ghi vào dòng bản ghi sau khi xem cận chữ) → `font` máy ghi theo độ đậm (TÊN HỌ)"""
    for k in ("font_xac_nhan", "font"):
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _cao_muc_ve_thu(text, kd, W):
    """vẽ thử glyph với kieu_dang (font/co/dam) → chiều cao mực (px) của chính các ký tự trong câu; None nếu engine chữ không sẵn"""
    try:
        from dung import chu as _chu
        kd2 = _chu._kd(dict(kd), W)
        tren, duoi = _chu._muc_doc(text, kd2)
        return float(duoi - tren) if duoi > tren else None
    except Exception:
        return None


def _kep_co_theo_muc(d, W):
    """kẹp `co` theo chiều cao mực đo (`_do.cao_muc_px_1920`): vẽ thử → scale; lặp 2 lần; ghi `may_sua` số trước/sau"""
    do = d.get("_do") or {}
    muc = do.get("cao_muc_px_1920")
    if not muc or not d.get("text"):
        return None
    co0 = float(d.get("co") or 0)
    if co0 <= 0:
        return None
    co = co0
    kd = {"font": _ho_font(d) or "phu_de", "co": co, "dam": d.get("dam") or 500, "dong": 1.0, "can": "giua", "hoa": bool(d.get("hoa"))}   # dong/can: chu._kd bắt buộc (không ảnh hưởng cao mực)
    txt = d["text"].upper() if d.get("hoa") else d["text"]
    for _ in range(2):
        h = _cao_muc_ve_thu(txt, dict(kd, co=co), W)
        if not h or h <= 0:
            return None
        co = co * float(muc) / h
    co = max(8.0, co)
    if abs(co - co0) >= 1.0:
        d["co"] = int(round(co))
        return {"sua": "co_theo_muc", "tu": int(round(co0)), "den": int(round(co)), "muc_px": muc}
    return None


def cong_thuc_tu_ban_ghi(lop_json, dur, ten="dựng lại bản ghi", bg=None, W=1080):
    """ban-ghi-lop.json (+ ban-ghi.json để lấy hộp/số đo) → cong-thuc.json tối thiểu đúng khuôn. Bản chép để SO: mọi lớp cố ý
    (co_y, ne_mat false, toan_khung — không né mặt, không dời vào vùng an toàn), vị trí TUYỆT ĐỐI theo hộp đo (neo theo mặt chỉ dùng
    khi áp sang video khác), rong_max = rộng hộp đo, giữ dx/xoay, cỡ chữ kẹp theo chiều cao mực đo, t0 = t_du − dai (mốc máy đo)."""
    bl = C.doc_json(lop_json, {}) or {}
    hop_cum, do_cum = {}, {}
    for c in (bg or {}).get("cum") or []:
        ds = [d.get("_do", {}).get("hop") for d in c["noi_dung"]["dong"] if d.get("_do", {}).get("hop")]
        if ds:
            hop_cum[c["id"]] = [min(h[0] for h in ds), min(h[1] for h in ds), max(h[2] for h in ds), max(h[3] for h in ds)]
        do_cum[c["id"]] = {i: (d.get("_do") or {}) for i, d in enumerate(c["noi_dung"]["dong"])}
        for i, d in enumerate(c["noi_dung"]["dong"]):
            if d.get("font_xac_nhan"):
                do_cum[c["id"]][i]["font_xac_nhan"] = d["font_xac_nhan"]
    lop, may_sua, ho_dem = [], [], {}
    for l in bl.get("lop") or []:
        l = json.loads(json.dumps(l))
        l["ne_mat"] = False; l["co_y"] = True; l["toan_khung"] = True
        hb = hop_cum.get(l.get("id"))
        dos = do_cum.get(l.get("id")) or {}
        if hb:
            cx, cy = (hb[0] + hb[2]) / 2, (hb[1] + hb[3]) / 2
            w, h = hb[2] - hb[0], hb[3] - hb[1]
            l["vi_tri"] = {"anchor": "mc", "x": round(cx, 3), "y": round(cy, 3), "w": round(min(0.96, w + 0.04), 3), "h": round(min(0.7, h + 0.04), 3)}
            kd = l.setdefault("kieu_dang", {})
            kd["rong_max"] = round(min(0.96, w + 0.02), 3)
        t0_moi = []
        for i, d in enumerate(l["noi_dung"]["dong"]):
            do = dos.get(i) or {}
            d["_do"] = do
            if do.get("font_xac_nhan"):
                d["font_xac_nhan"] = do["font_xac_nhan"]
            ho = _ho_font(d)
            if ho:
                d["font"] = ho; ho_dem[ho] = ho_dem.get(ho, 0) + 1
            ms = _kep_co_theo_muc(d, W)
            if ms:
                may_sua.append(dict(ms, lop=l.get("id"), dong=i))
            # t0 = t_du − dai (mốc máy): dòng nào có số đo thì dùng, lấy sớm nhất làm t0 lớp
            vao = ((d.get("anim") or {}).get("vao") or {})
            if do.get("t_du") is not None and vao.get("dai") is not None:
                t0_moi.append(float(do["t_du"]) - float(vao["dai"]) - float(d.get("tre") or 0))
            d.pop("_do", None); d.pop("font_xac_nhan", None)
        if t0_moi:
            t0n = round(max(0.0, min(t0_moi)), 2)
            if abs(t0n - float(l.get("t0") or 0)) >= 0.02:
                may_sua.append({"lop": l.get("id"), "sua": "t0_theo_t_du", "tu": l.get("t0"), "den": t0n})
                # dòng: trễ tính lại so với t0 mới
                for i, d in enumerate(l["noi_dung"]["dong"]):
                    do = dos.get(i) or {}
                    vao = ((d.get("anim") or {}).get("vao") or {})
                    if do.get("t_du") is not None and vao.get("dai") is not None:
                        d["tre"] = round(max(0.0, float(do["t_du"]) - float(vao["dai"]) - t0n), 2)
                l["t0"] = t0n
        lop.append(l)
    ho = max(ho_dem, key=ho_dem.get) if ho_dem else "Be Vietnam Pro"
    return {"y_do": {"video_ve": ten, "nguoi_xem": "máy", "nho_1_dieu": "dựng lại bản ghi để so với gốc", "ngon_ngu_hinh_anh": "chép đúng mẫu",
                     "nhip": "theo bản ghi", "nhac_ly_do": "không"},
            "khung": bl.get("khung") or [1080, 1920], "cat": [{"src": 0, "a": 0, "b": round(dur, 2)}],
            "phong_cach": {"mau_nhan": "#FFFFFF", "mau_nhan2": "#AAAAAA", "mau_sang": "#FFFFFF", "mau_toi": "#111111",
                           "font": {"tieu_de": ho, "phu_de": ho, "nhan": ho}},
            "phu_de": {"che_do": "tat", "kieu_dang": {"font": ho, "co": 44, "mau": "#FFFFFF", "vien": []}, "vi_tri": {"anchor": "bc", "x": 0.5, "y": 0.8}},
            "camera": [], "chuyen_canh": [], "am": {"nhac": {"muc": "khong"}},      # bản chép để SO: không punch-in/flash (hiệu khung chỉ còn lớp chữ)
            "lop": lop, "ghi_chu": "bản dựng lại của bộ học — để so với gốc, không giao", "_may_sua_ban_chep": may_sua}


# ─────────────────────────────────────────────────────────────── đo bằng alpha sprite của lớp
def _lop_engine(du_an, kh):
    """ke-hoach.json đã chuẩn hoá → (ctx, {id lớp: đối tượng Lop}) bằng chính engine (dung.tao_ctx + lop.tao_lop); None nếu engine không nạp được"""
    try:
        from dung import dung as D, lop as L
        if not kh.get("quyet_dinh"):
            kh["quyet_dinh"] = quyet_dinh_ban_chep()
        ctx = D.tao_ctx(du_an, kh)
        ra = {}
        for sp in kh.get("lop") or []:
            try:
                ra[sp.get("id")] = L.tao_lop(sp, ctx)
            except Exception:
                pass
        return ctx, ra
    except Exception:
        return None, {}


def _alpha_lop(lop, t, ctx):
    """alpha (uint8 H×W toàn khung, 0..255) của lớp tại giây t thành phẩm; None nếu ngoài [t0, t1]"""
    lt = float(t) - lop.t0
    if lt < 0 or lt > lop.dur + 1e-6:
        return None
    bgra = lop.ve(lt, tra_bgra=True)
    hx0, hy0, hx1, hy1 = lop.hop()
    A = np.zeros((ctx.H, ctx.W), np.uint8)
    a = bgra[:, :, 3]
    x0, y0 = max(0, hx0), max(0, hy0)
    x1, y1 = min(ctx.W, hx0 + a.shape[1]), min(ctx.H, hy0 + a.shape[0])
    if x1 > x0 and y1 > y0:
        A[y0:y1, x0:x1] = a[y0 - hy0:y1 - hy0, x0 - hx0:x1 - hx0]
    return A


def _hop_alpha(A, W, H, nguong=8):
    ys, xs = np.nonzero(A > nguong)
    if len(xs) < 20:
        return None
    return [np.percentile(xs, 1) / W, np.percentile(ys, 1) / H, np.percentile(xs, 99) / W, np.percentile(ys, 99) / H]


def quyet_dinh_ban_chep():
    """quyết định kênh cho BẢN CHÉP (engine 1.2.21 không còn mặc định thẩm mỹ): v3/ai/quyet-dinh.mau.json (A4) → bang.QUYET_DINH_XEM_TRUOC;
    ne_mat.thu_toi = 1.0 (không thu khi đè mặt — bản chép phải nằm đúng chỗ mẫu, chỉ báo)"""
    qd = None
    p = os.path.join(V3, "ai", "quyet-dinh.mau.json")
    if os.path.isfile(p):
        qd = C.doc_json(p)
    if not qd:
        try:
            from dung.mau import bang as _bang
            qd = json.loads(json.dumps(_bang.QUYET_DINH_XEM_TRUOC))
        except Exception:
            qd = {}
    qd = dict(qd); qd["ne_mat"] = dict(qd.get("ne_mat") or {}, thu_toi=1.0)
    qd["ly_do"] = "bản chép của bộ học (dung_lai) — trung tính, không thu khi đè mặt"
    return qd


def _con_tro(thu_muc, du_an):
    """con trỏ việc RIÊNG cho vòng dựng lại (không đụng app/.phieu2-hien-tai) → đường dẫn tệp con trỏ + env"""
    p = os.path.join(thu_muc, "_phieu-dung-lai.txt")
    if du_an:
        with open(p, "w", encoding="utf-8") as f:
            f.write(du_an)
    return p, {"QUY_TRINH_PHIEU2": p}


def _du_an_tu(p):
    try:
        s = open(p, encoding="utf-8").read().strip()
        j = json.loads(s) if s.startswith("{") else None
        if j:
            return j.get("du_an") or j.get("duong")
        return s
    except Exception:
        return None


def _dung_truc_tiep(du_an, kh, log):
    """vá ke-hoach.json (toan_khung/ne_mat) rồi dựng lại bằng dung.dung trong tiến trình con — đường tắt không qua kiem"""
    p = os.path.join(du_an, "ke-hoach.json")
    C.ghi_json(p, kh)
    ma = f"import sys; sys.path.insert(0, {V3!r}); import chung; from dung import dung as D; kh = chung.doc_json({p!r}); r = D.dung({du_an!r}, kh); print('VIDEO', (r or {{}}).get('video') if isinstance(r, dict) else r)"
    r = subprocess.run([_py(), "-X", "utf8", "-c", ma], cwd=APP, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=3600,
                       env=dict(os.environ, PYTHONUTF8="1"), creationflags=(0x08000000 if os.name == "nt" else 0))
    out = (r.stdout or "") + (r.stderr or "")
    for dong in out.strip().splitlines()[-4:]:
        log("    | " + dong[:160])
    m = re.findall(r"VIDEO (.+)", out)
    return r.returncode, (m[-1].strip() if m else None)


def chay(thu_muc, ho_so, log=print, ten=None, chi_so_sanh=False, du_an=None):
    t_bd = time.time()
    bg = C.doc_json(os.path.join(thu_muc, "ban-ghi.json"), {}) or {}
    pl = os.path.join(thu_muc, "ban-ghi-lop.json")
    if not bg or not os.path.isfile(pl):
        raise RuntimeError("chưa có ban-ghi.json / ban-ghi-lop.json")
    video = bg["nguon"]; dur = float(bg["dur"])
    W0 = int((bg.get("khung") or [1080, 1920])[0])
    ten = ten or ("doi-chieu-" + C.slug(os.path.splitext(os.path.basename(video))[0], 24))
    ct = None
    dung_lai_truc_tiep = False
    if not chi_so_sanh:
        if du_an and os.path.isdir(du_an):              # dùng lại việc đã đọc nguồn (chỉ viết công thức + dựng lại)
            _, env = _con_tro(thu_muc, du_an)
            log(f"  dựng lại: dùng lại việc {du_an} (con trỏ riêng, không ghi .phieu2-hien-tai)")
        else:
            p_ct, env = _con_tro(thu_muc, None)
            log(f"  dựng lại: mở việc `{ten}` (hồ sơ {ho_so})")
            ma, out = _chay(["bat-dau", ten, "--video", video, "--ho-so", ho_so, "--yeu-cau", "Dựng lại bản ghi thi công để so với gốc (bộ học). Không cắt, không phụ đề.", "--de"], log, env=env)
            if ma != 0:
                raise RuntimeError("bat-dau lỗi: " + out[-400:])
            du_an = _du_an_tu(p_ct)
            if not du_an:
                raise RuntimeError("bat-dau không ghi con trỏ việc (QUY_TRINH_PHIEU2)")
            log(f"  dựng lại: đọc nguồn (Whisper/mắt) → {du_an}")
            ma, out = _chay(["nhanh", "doc"], log, timeout=2400, env=env)
            lan = 0
            while ma == 75 and lan < 6:
                lan += 1; ma, out = _chay(["nhanh", "doc"], log, timeout=2400, env=env)
            if ma not in (0,):
                raise RuntimeError("nhanh doc lỗi: " + out[-400:])
        ct = cong_thuc_tu_ban_ghi(pl, dur, ten, bg=bg, W=W0)
        C.ghi_json(os.path.join(du_an, "cong-thuc.json"), ct)
        C.ghi_json(os.path.join(du_an, "quyet-dinh-kenh.json"), quyet_dinh_ban_chep())      # 1.2.21: nhanh tron đọc quyết định kênh từ dự án
        log(f"  dựng lại: dựng {len(ct['lop'])} lớp (nhanh tron) · máy sửa bản chép {len(ct.get('_may_sua_ban_chep') or [])} chỗ (cỡ theo mực / t0 theo t_du)")
        ma, out = _chay(["nhanh", "tron"], log, timeout=3600, env=env)
        lan = 0
        while ma == 75 and lan < 10:
            lan += 1; ma, out = _chay(["nhanh", "tron"], log, timeout=3600, env=env)
        if ma != 0 and "CHE MẶT" not in out:
            raise RuntimeError("nhanh tron lỗi: " + out[-600:])
        # đường tắt: máy kiểm vẫn dời/thu lớp (vùng an toàn, né mặt) → vá ke-hoach (toan_khung, ne_mat false) rồi dựng lại trực tiếp
        kiem0 = C.doc_json(os.path.join(du_an, "kiem.json"), {}) or {}
        ids = {l.get("id") for l in ct["lop"]}
        doi = [m for m in (kiem0.get("may_sua") or []) if isinstance(m, dict) and m.get("lop") in ids and m.get("sua") in ("vung_an_toan", "doi", "thu", "doi_khoi_mat")]
        if doi:
            kh = C.doc_json(os.path.join(du_an, "ke-hoach.json"), {}) or {}
            if kh.get("lop"):
                for l in kh["lop"]:
                    if l.get("id") in ids:
                        l["toan_khung"] = True; l["ne_mat"] = False
                log(f"  dựng lại: máy kiểm dời/thu {len(doi)} lớp → vá ke-hoach (toan_khung, ne_mat false) và dựng trực tiếp (không qua kiem)")
                ma2, vid2 = _dung_truc_tiep(du_an, kh, log)
                dung_lai_truc_tiep = ma2 == 0
    elif not du_an:
        du_an = _du_an_tu(os.path.join(thu_muc, "_phieu-dung-lai.txt")) or _du_an_tu(PHIEU)
    vid = os.path.join(du_an, "dung", "thanh-pham.mp4")
    if not os.path.isfile(vid):
        cands = [os.path.join(du_an, "dung", f) for f in os.listdir(os.path.join(du_an, "dung")) if f.endswith(".mp4")] if os.path.isdir(os.path.join(du_an, "dung")) else []
        if not cands:
            raise RuntimeError("không thấy video dựng lại trong dung/")
        vid = max(cands, key=os.path.getmtime)
    kiem = C.doc_json(os.path.join(du_an, "kiem.json"), {}) or {}
    kh = C.doc_json(os.path.join(du_an, "ke-hoach.json"), {}) or {}
    ctx, lops = _lop_engine(du_an, kh) if kh.get("lop") else (None, {})
    # ── so sánh từng cụm
    kq = {"video_goc": video, "video_dung_lai": vid, "du_an": du_an, "cum": [], "may_sua": kiem.get("may_sua"), "loi_dung": kiem.get("loi_dung"),
          "may_sua_ban_chep": (ct or {}).get("_may_sua_ban_chep") if ct else None, "dung_truc_tiep": dung_lai_truc_tiep,
          "phuong_phap": "alpha_lop" if lops else "hieu_anh"}
    cums = bg.get("cum") or []
    moc = []
    for c in cums:
        dong = c["noi_dung"]["dong"]
        dai_vao = max([((d.get("anim") or {}).get("vao") or {}).get("dai") or 0 for d in dong] + [0.0])
        tre_max = max([d.get("tre") or 0 for d in dong] + [0.0])
        t_du = min(c["t1"] - 0.05, c["t0"] + tre_max + dai_vao + 0.08)
        t_truoc = c["t0"] - 0.12
        moc.append((t_du, t_truoc))
    ts_can = sorted({t for t_du, t_truoc in moc for t in (t_du, t_truoc) if t > 0} | {0.0})
    kg = _khung_nhieu(video, ts_can); kr = _khung_nhieu(vid, ts_can)
    o_goc = kg.get(0.0)
    if o_goc is None:
        o_goc = _khung(video, 0.0)
    H, W = o_goc.shape[:2]
    tiles = []
    for c, (t_du, t_truoc) in zip(cums, moc):
        dong = c["noi_dung"]["dong"]
        bb = [min(d["_do"]["hop"][0] for d in dong), min(d["_do"]["hop"][1] for d in dong), max(d["_do"]["hop"][2] for d in dong), max(d["_do"]["hop"][3] for d in dong)]
        fg, fr = kg.get(t_du), kr.get(t_du)
        fr0 = kr.get(t_truoc) if t_truoc > 0 else None
        if fg is None or fr is None:
            continue
        pad = 0.06
        x0, y0 = int(max(0, bb[0] - pad) * W), int(max(0, bb[1] - pad) * H); x1, y1 = int(min(1, bb[2] + pad) * W), int(min(1, bb[3] + pad) * H)
        if y1 - y0 < 40:
            y1 = min(H, y0 + 40)
        if x1 - x0 < 40:
            x1 = min(W, x0 + 40)
        # (phụ) LỚP CỦA MÌNH = hiệu (bản dựng lại − bản gốc) cùng mốc: chữ của mẫu ở nền triệt tiêu, chỉ còn lớp vừa vẽ
        def _mask(fr_, fg_):
            d_ = np.abs(fr_.astype(np.int16) - fg_.astype(np.int16)).max(2) > 40
            return cv2.morphologyEx(d_.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)).astype(bool)
        m_du = _mask(fr, fg)
        fg0 = kg.get(t_truoc) if t_truoc > 0 else None
        m_truoc = _mask(fr0, fg0) if (fr0 is not None and fg0 is not None) else None
        def _trong(m, hb):
            x0_, y0_, x1_, y1_ = int(hb[0] * W), int(hb[1] * H), int(np.ceil(hb[2] * W)), int(np.ceil(hb[3] * H))
            return m[y0_:y1_, x0_:x1_]
        dong_kq = []
        for d in dong:
            hd = d["_do"]["hop"]
            mw, mh = (hd[2] - hd[0]) * 0.25, (hd[3] - hd[1]) * 0.6
            vung = [max(0, hd[0] - mw), max(0, hd[1] - mh), min(1, hd[2] + mw), min(1, hd[3] + mh)]
            sub = _trong(m_du, vung)
            ys, xs = np.nonzero(sub)
            if len(xs) >= 30:
                x0v, y0v = int(vung[0] * W), int(vung[1] * H)
                hb = [(x0v + np.percentile(xs, 1)) / W, (y0v + np.percentile(ys, 1)) / H, (x0v + np.percentile(xs, 99)) / W, (y0v + np.percentile(ys, 99)) / H]
                iou = _iou(hd, hb)
            else:
                iou = 0.0
            dong_kq.append({"text": d["text"][:30], "iou_hieu_anh": round(float(iou), 2), "co_lop": bool(len(xs) >= 30)})
        # (chính) ALPHA SPRITE của lớp tại mốc — không nhiễu re-encode
        lop = lops.get(c["id"]) if lops else None
        iou_alpha = co_truoc_a = co_sau_a = None
        if lop is not None and ctx is not None:
            try:
                A = _alpha_lop(lop, t_du, ctx)
                co_sau_a = bool(A is not None and float(_trong(A, bb).max() if _trong(A, bb).size else 0) > 8)
                hb = _hop_alpha(A, ctx.W, ctx.H) if A is not None else None
                iou_alpha = round(float(_iou(bb, hb)), 2) if hb else 0.0
                A0 = _alpha_lop(lop, t_truoc, ctx) if t_truoc > 0 else None
                co_truoc_a = bool(A0 is not None and float(_trong(A0, bb).max() if _trong(A0, bb).size else 0) > 8)
            except Exception as ex:
                iou_alpha = None; co_sau_a = None
                dong_kq.append({"text": "(alpha lỗi)", "loi": str(ex)[:80]})
        # đúng giờ: trước t0 vùng cụm chưa có lớp mình; tại t_du có
        co_truoc = bool(_trong(m_truoc, bb).mean() > 0.01) if m_truoc is not None else None
        co_sau = bool(_trong(m_du, bb).mean() > 0.01)
        diem_vt_hieu = float(np.mean([x["iou_hieu_anh"] for x in dong_kq if "iou_hieu_anh" in x])) if dong_kq else 0.0
        diem_chu = float(np.mean([1.0 if x.get("co_lop") else 0.0 for x in dong_kq if "co_lop" in x])) if dong_kq else 0.0
        if co_sau_a is not None:
            dung_gio = bool(co_sau_a and not co_truoc_a)
            diem_vt = float(iou_alpha if iou_alpha is not None else diem_vt_hieu)
        else:
            dung_gio = (co_sau and (co_truoc is False or co_truoc is None))
            diem_vt = diem_vt_hieu
        kq["cum"].append({"id": c["id"], "t_du": round(t_du, 2), "vi_tri_iou": round(diem_vt, 2), "vi_tri_iou_alpha": iou_alpha, "vi_tri_iou_hieu_anh": round(diem_vt_hieu, 2),
                          "co_lop_ti_le": round(diem_chu, 2), "dung_gio": dung_gio, "co_truoc_t0": co_truoc_a if co_truoc_a is not None else co_truoc,
                          "co_tai_t_du": co_sau_a if co_sau_a is not None else co_sau, "dong": dong_kq})
        # ô so sánh: gốc | dựng lại (cùng vùng), kèm nhãn
        a = fg[y0:y1, x0:x1]; b = fr[y0:y1, x0:x1]
        hh = 220; sc = hh / max(1, a.shape[0])
        a = cv2.resize(a, (max(1, int(a.shape[1] * sc)), hh)); b = cv2.resize(b, (max(1, int(b.shape[1] * sc)), hh))
        o = np.full((hh + 26, a.shape[1] + b.shape[1] + 12, 3), 18, np.uint8)
        o[26:, :a.shape[1]] = a; o[26:, a.shape[1] + 12:] = b
        cv2.putText(o, f"{c['id']} {t_du:.2f}s goc | dung lai  vi tri {diem_vt:.2f} co lop {diem_chu:.2f} {'dung gio' if dung_gio else 'LECH GIO'}", (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (240, 240, 240), 1, cv2.LINE_AA)
        tiles.append(o)
    # ghép ảnh (7 ô một tấm)
    anh = []
    for j in range(0, len(tiles), 7):
        nhom = tiles[j:j + 7]
        w = max(t.shape[1] for t in nhom); h = sum(t.shape[0] + 6 for t in nhom)
        im = np.full((h, w, 3), 10, np.uint8); y = 0
        for t in nhom:
            im[y:y + t.shape[0], :t.shape[1]] = t; y += t.shape[0] + 6
        p = os.path.join(thu_muc, f"doi-chieu-{j // 7 + 1}.jpg")
        cv2.imwrite(p, im, [cv2.IMWRITE_JPEG_QUALITY, 86]); anh.append(p)
    cs = kq["cum"]
    ia = [c["vi_tri_iou_alpha"] for c in cs if c.get("vi_tri_iou_alpha") is not None]
    kq["diem"] = {"vi_tri_iou_tv": round(float(np.median([c["vi_tri_iou"] for c in cs])), 2) if cs else None,
                  "vi_tri_iou_alpha_tv": round(float(np.median(ia)), 2) if ia else None,
                  "vi_tri_iou_hieu_anh_tv": round(float(np.median([c["vi_tri_iou_hieu_anh"] for c in cs])), 2) if cs else None,
                  "co_lop_tv": round(float(np.median([c["co_lop_ti_le"] for c in cs])), 2) if cs else None,
                  "dung_gio_ti_le": round(sum(1 for c in cs if c["dung_gio"]) / len(cs), 2) if cs else None,
                  "so_cum": len(cs), "cum_lech_vi_tri": [c["id"] for c in cs if c["vi_tri_iou"] < 0.3], "cum_lech_gio": [c["id"] for c in cs if not c["dung_gio"]],
                  "phuong_phap": kq["phuong_phap"]}
    kq["anh"] = anh; kq["giay"] = round(time.time() - t_bd, 1)
    pj = os.path.join(thu_muc, "doi-chieu.json")
    C.ghi_json(pj, kq)
    log(f"  đối chiếu ({kq['phuong_phap']}): {len(cs)} cụm · vị trí IoU tv {kq['diem']['vi_tri_iou_tv']} · có lớp tv {kq['diem']['co_lop_tv']} · đúng giờ {kq['diem']['dung_gio_ti_le']} → {pj}")
    return {"json": pj, "anh": anh, "diem": kq["diem"]}


def _du_an_hien_tai():
    """việc đang mở theo con trỏ chung (chỉ đọc) — giữ cho mã cũ gọi"""
    return _du_an_tu(PHIEU)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("thu_muc"); ap.add_argument("--ho-so", required=True); ap.add_argument("--chi-so-sanh", action="store_true"); ap.add_argument("--du-an")
    a = ap.parse_args()
    kq = chay(a.thu_muc, a.ho_so, chi_so_sanh=a.chi_so_sanh, du_an=a.du_an)
    print(json.dumps(kq["diem"], ensure_ascii=False))
