# -*- coding: utf-8 -*-
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
"""CẦU NỐI Studio (giao diện, phiếu, trò chuyện Claude của 1.2.x) ↔ LÕI 1.3 (v3/).

v2/st.py chuyển các lệnh `nhanh …` sang đây (tiến trình riêng — v2 và v3 trùng tên mô-đun nên không import chung).
    python v3/cau_noi.py doc            đọc video (proxy 540p, lời, mặt, cắt lặng) → in BẢN TÓM TẮT + từ điển công cụ cho AI
    python v3/cau_noi.py tron           chuẩn hoá công thức + máy kiểm → dựng → 8 khung xem lại + 3 bìa → in đường ảnh cho AI nhìn
    python v3/cau_noi.py khung --tu A --den B [--fps N] [--o-lon]   AI nhìn kỹ một đoạn (giây gốc) → doc/soi-A-B.jpg
    python v3/cau_noi.py giao [--bia N] kiểm kỹ thuật → chép video + bìa ra thư mục giao → đóng phiếu → báo Studio
Lệnh dài chạy NỀN (sống qua giới hạn 10 phút của một lệnh Bash): quá ~9 phút thì in "VẪN ĐANG CHẠY" (mã 75) — chạy lại đúng lệnh để chờ tiếp.
Phiếu (phieu.json) ghi đúng định dạng cũ (mốc 0.1…7.3) để thanh tiến độ của Studio chạy như trước.
"""
import contextlib
import argparse, glob, json, os, re, shutil, subprocess, sys, time, traceback

V3 = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, V3)
import chung

SKILL = chung.SKILL
CHO_TOI_DA = float(os.environ.get("STUDIO_CHO_TOI_DA", "540"))
PHAN_DOC = ["0.1", "0.2", "1.1", "1.2", "1.3", "1.4", "2.1"]
PHAN_TU_DUY = ["2.2", "2.3", "3.1", "3.2", "3.3", "3.4", "3.5", "3.6"]
PHAN_DUNG_TRON = ["4.1", "4.2", "5.1", "5.2", "6.1", "6.2", "6.3", "6.4", "6.5", "6.6"]
PHAN_DUNG_GIAO = ["5.3", "6.7", "7.1", "7.2", "7.3"]


# ───────────────────────────────────────────── phiếu (định dạng 1.2.x)
def _con_tro():
    return os.environ.get("QUY_TRINH_PHIEU2", "").strip() or os.path.join(SKILL, ".phieu2-hien-tai")


def doc_phieu():
    try:
        d = open(_con_tro(), encoding="utf-8").read().strip()
    except OSError:
        d = ""
    ph = chung.doc_json(os.path.join(d, "phieu.json")) if d else None
    if not ph:
        print("CHẶN: chưa có phiếu. Chạy trước: python v2/st.py bat-dau <ten> --video <file> --ho-so <hồ sơ>")
        sys.exit(2)
    return ph


def luu_phieu(ph):
    chung.ghi_json(os.path.join(ph["du_an"], "phieu.json"), ph)


def danh_dau(ph, ds, cong_cu, ghi_chu=None):
    bay = time.strftime("%Y-%m-%d %H:%M:%S")
    for b in ds:
        ph.setdefault("buoc", {})[b] = {"luc": bay, "t": time.time(), "dau_ra": "", "sha": "", "cong_cu": cong_cu, "giay_chay": None,
                                       "ghi_chu": ghi_chu, "loi": "1.3"}
    luu_phieu(ph)


def ghi_cong(ph, so, dat, loi=None):
    ph.setdefault("cong", {})[str(so)] = {"luc": time.strftime("%Y-%m-%d %H:%M:%S"), "dat": bool(dat), "loi": loi or []}
    luu_phieu(ph)


def _log(du_an):
    return lambda d, m=None: chung.log(du_an if m is not None else du_an, m if m is not None else d)


# ───────────────────────────────────────────── hồ sơ 1.2.x → hồ sơ lõi 1.3
def chuan_bi_ho_so(ho_so):
    """đọc cau-hinh.json / phong-cach.md / gop-y / token.json của hồ sơ Studio → nao/ca-nhan/<hs>/ho-so.json (lõi đọc)"""
    tm = os.path.join(chung.duong("ho_so"), ho_so or "")
    if not ho_so or not os.path.isdir(tm):
        return None
    ch = chung.doc_json(os.path.join(tm, "cau-hinh.json"), {}) or {}
    khoa = ch.get("khoa") or []
    khoa = khoa if isinstance(khoa, list) else [k for k, v in (khoa.items() if isinstance(khoa, dict) else []) if v]
    mau, chu = ch.get("mau") or {}, ch.get("chu") or {}
    gu = ""
    try:
        gu = open(os.path.join(tm, "phong-cach.md"), encoding="utf-8").read().strip()[:1800]
    except OSError:
        pass
    tk = chung.doc_json(os.path.join(tm, "token.json"), {}) or {}
    gy = chung.doc_json(os.path.join(tm, "gop-y-v2.json"))
    gy = (gy if isinstance(gy, list) else (gy or {}).get("ds") or []) if gy else []
    hs = {"ten": (ch.get("kenh") or {}).get("ten") or ho_so,
          "mau": {"nhan": mau.get("nhan") or "", "nhan2": mau.get("nhan2") or "", "khoa": "mau_nhan" in khoa},
          "font": {"tieu_de": chu.get("title_to") or "", "phu_de": chu.get("phu_de") or "", "khoa": bool({"font_phu_de", "font_tieu_de"} & set(khoa))},
          "mau_khoa": mau.get("nhan") if "mau_nhan" in khoa else None,
          "font_khoa": {k: chu.get(v) for k, v in (("phu_de", "phu_de"), ("tieu_de", "title_to")) if f"font_{k}" in khoa and chu.get(v)} or None,
          "gu": gu, "ghi_chu": tk.get("luat_cung_ghi") or [], "cam": tk.get("cam") or [],
          "luat_gu": ch.get("luat_gu") or {}, "gop_y": [g if isinstance(g, str) else (g.get("noi_dung") or g.get("cau") or "") for g in gy][-5:],
          "ban_giao": ch.get("ban_giao") or {}}
    chung.ghi_json(os.path.join(tm, "ho-so.json"), hs)
    return hs


# ───────────────────────────────────────────── chạy nền (sống qua giới hạn 10 phút / lệnh)
def _chay_nen(ph, buoc, them=()):
    """chạy `cau_noi.py _lam <buoc>` tách rời; chờ tối đa CHO_TOI_DA giây. → mã (0 xong, 1 lỗi, 75 còn chạy)"""
    d = ph["du_an"]
    tt = os.path.join(d, f".v3-{buoc}.json")
    st = chung.doc_json(tt) or {}
    pid = st.get("pid")
    dang = st.get("trang_thai") == "chay" and pid and _con_song(pid)
    if not dang:
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", V3_DU_AN=d)
        log = open(os.path.join(d, f"v3-{buoc}.log"), "a", encoding="utf-8")
        flags = (0x00000008 | 0x00000200 | 0x08000000) if os.name == "nt" else 0          # DETACHED | NEW_GROUP | NO_WINDOW
        p = subprocess.Popen([chung.python_nen(), os.path.abspath(__file__), "_lam", buoc, *them], stdout=log, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, cwd=SKILL, env=env, creationflags=flags, start_new_session=(os.name != "nt"))
        chung.ghi_json(tt, {"trang_thai": "chay", "pid": p.pid, "bat_dau": time.time()})
        print(f"▶ {buoc}: máy đang làm (theo dõi: {os.path.join(d, 'nhat-ky.txt')})", flush=True)
    t0 = time.time()
    nk = os.path.join(d, "nhat-ky.txt")
    try:                                              # chỉ in nhật ký MỚI của lần chạy này
        da_in = len(open(nk, encoding="utf-8").read().splitlines())
    except OSError:
        da_in = 0
    while time.time() - t0 < CHO_TOI_DA:
        st = chung.doc_json(tt) or {}
        if st.get("trang_thai") == "chay" and st.get("pid") and _con_song(st["pid"]) and _im_lang(d, tt, st) > TREO_GIAY:
            # 1.2.19 (B3): WATCHDOG — tiến trình còn sống nhưng không có tiến độ TREO_GIAY → giết, ghi lỗi để AI chạy lại (không chờ mồ côi)
            if _la_con_cau_noi(st["pid"]) is False:   # PID đã thuộc tiến trình khác (con chết, hệ tái dùng số) → không giết nhầm, coi là lỗi
                chung.ghi_json(tt, dict(st, trang_thai="loi", loi=f"{buoc}: tiến trình máy đã mất (không ghi kết quả) — chạy lại lệnh này", luc=time.time()))
                return 1
            _giet(st["pid"])
            chung.ghi_json(tt, dict(st, trang_thai="loi", loi=f"treo ở bước {buoc}: không có tiến độ {TREO_GIAY // 60} phút — đã tắt, chạy lại lệnh này", luc=time.time()))
            chung.log(d, f"⛔ {buoc}: treo (im {TREO_GIAY // 60} phút) → đã tắt tiến trình {st['pid']}")
            return 1
        try:
            dong = open(nk, encoding="utf-8").read().splitlines()
            for x in dong[da_in:]:
                if x.strip() and not re.search(r"Task finished|Terminating", x):   # 1.2.21: KHÔNG lọc CUDA|hevc @ — AI phải thấy dấu hiệu card lỗi
                    print("  " + x, flush=True)
            da_in = len(dong)
        except OSError:
            pass
        if st.get("trang_thai") in ("xong", "loi"):
            return 0 if st["trang_thai"] == "xong" else 1
        if st.get("pid") and not _con_song(st["pid"]):
            time.sleep(1.0)
            st = chung.doc_json(tt) or {}
            if st.get("trang_thai") not in ("xong", "loi"):
                chung.ghi_json(tt, dict(st, trang_thai="loi", loi="tiến trình dừng giữa chừng"))
                return 1
            return 0 if st["trang_thai"] == "xong" else 1
        time.sleep(2.0)
    print(f"VẪN ĐANG CHẠY ({buoc}) — chạy lại ĐÚNG lệnh vừa rồi để chờ tiếp (máy không làm lại từ đầu).")
    return 75


TREO_GIAY = 45 * 60          # 45 phút không có dòng nhật ký mới (một lệnh ffmpeg 4K trên máy yếu có thể im 20-30 phút)


def _im_lang(d, tt, st):
    """giây từ tiến độ mới nhất (nhật ký / tệp trạng thái / lúc bắt đầu)"""
    moc = float(st.get("bat_dau") or 0)
    for p in (os.path.join(d, "nhat-ky.txt"), tt):
        try:
            moc = max(moc, os.path.getmtime(p))
        except OSError:
            pass
    return time.time() - moc if moc else 0.0


def _giet(pid):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(int(pid))], capture_output=True, creationflags=0x08000000)
        else:
            import signal
            try:
                os.killpg(int(pid), signal.SIGKILL)
            except Exception:
                os.kill(int(pid), signal.SIGKILL)
    except Exception:
        pass


@contextlib.contextmanager
def _giu_may(viec, d):
    """1.2.19 (B3): CHỖ NẶNG của máy (v2/may_nang, có từ 1.2.12 nhưng lõi 1.3 chưa gọi) — phần máy nặng của các video chạy TUẦN TỰ
    theo sức máy (1 chỗ với ≤8 luồng/<16 GB), hết giẫm nhau gây CUDA kẹt. Chờ tối đa 2 giờ (tiến trình nền, AI thấy "VẪN ĐANG CHẠY")."""
    try:
        v2, them = os.path.join(SKILL, "v2"), False
        if v2 not in sys.path:
            sys.path.append(v2); them = True    # APPEND, không chèn đầu: v2 cũng có gói `doc` → chèn đầu làm import doc.proxy lệch sang v2
        try:
            import may_nang as MN
        finally:
            if them:                            # gỡ ngay sau import: import sau này thiếu trong v3 phải báo lỗi, không lặng lẽ lấy từ v2
                try:
                    sys.path.remove(v2)
                except ValueError:
                    pass
    except Exception:
        yield None
        return
    with MN.giu(viec, d, cho_toi_da=7200, log=lambda s, **k: chung.log(d, s)) as so:
        yield so


def _con_song(pid):
    try:
        if os.name == "nt":
            r = subprocess.run(["tasklist", "/FI", f"PID eq {int(pid)}", "/NH"], capture_output=True, text=True, creationflags=0x08000000)
            return re.search(rf"^\S+(\.exe)?\s+{int(pid)}\s", r.stdout, re.M) is not None
        os.kill(int(pid), 0)
        return True
    except Exception:
        return False


def _la_con_cau_noi(pid):
    """1.2.19: PID có thể bị hệ tái dùng cho tiến trình khác → trước khi giết, xem dòng lệnh có phải cau_noi.py _lam không.
    Không hỏi được (hệ thiếu công cụ) → None (coi như đúng — giữ hành vi cũ)."""
    try:
        if os.name == "nt":
            r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine"],
                               capture_output=True, text=True, timeout=20, creationflags=0x08000000)
        else:
            r = subprocess.run(["ps", "-o", "args=", "-p", str(int(pid))], capture_output=True, text=True, timeout=20)
        s = (r.stdout or "").strip()
        if not s:
            return None
        return "cau_noi" in s
    except Exception:
        return None


# ───────────────────────────────────────────── viec.json của lõi (từ phiếu)
def _ghep_nguon_chinh(du_an, ds, xuat_4k=False, giu_fps=False):
    """nhiều clip người nói = một video: nối thành một file (cache theo băm danh sách + cờ).
    Mặc định 1080 cạnh ngắn, 30 fps; 1.2.21: xuat_4k → theo cỡ clip đầu (không thu), giu_fps → theo fps clip đầu (khách yêu cầu 4K/60 fps
    không còn bị ép 1080/30 ngay từ bước nối). Lọc màu vào từng clip (HDR→SDR, 10-bit→8-bit) — chung.loc_mau_vao."""
    cache = os.path.join(du_an, "cache"); os.makedirs(cache, exist_ok=True)
    chung.don_tep_tam(cache)
    ra = os.path.join(cache, f"nguon-ghep-{chung.bam([chung.bam(p) for p in ds] + [bool(xuat_4k), bool(giu_fps), 'v2'])}.mp4")
    if os.path.isfile(ra) and os.path.getsize(ra) > 10000:
        return ra
    i0 = chung.ffprobe(ds[0]) or {"w": 1080, "h": 1920, "fps": 30.0}
    doc_ = i0["h"] >= i0["w"]
    W, H = (1080, 1920) if doc_ else (1920, 1080)
    if xuat_4k and i0.get("w") and i0.get("h"):
        W, H = int(i0["w"]) // 2 * 2, int(i0["h"]) // 2 * 2
    fps = 30
    if giu_fps and i0.get("fps"):
        fps = round(float(i0["fps"]), 3)
        fps = int(fps) if abs(fps - round(fps)) < 0.01 else fps
    args, fl, tong = [], [], 0.0
    for k, p in enumerate(ds):
        args += ["-i", p]
        inf = chung.ffprobe(p) or {}
        tong += float(inf.get("dur") or 0)
        lm = chung.loc_mau_vao(inf)
        fl.append(f"[{k}:v]" + (lm + "," if lm else "") + f"scale={W}:{H}:force_original_aspect_ratio=increase:out_color_matrix=bt709,crop={W}:{H},fps={fps},setsar=1,format=yuv420p[v{k}]")
        fl.append(f"[{k}:a]aformat=sample_rates=48000:channel_layouts=stereo[a{k}]" if inf.get("co_am")
                  else f"anullsrc=r=48000:cl=stereo,atrim=0:{inf.get('dur') or 1:.3f}[a{k}]")
    # 1.2.20: tiếng mỗi clip (AAC điện thoại) ngắn hơn hình vài chục ms → concat để HỞ mốc thời gian ở mỗi mối nối; tách WAV tuần tự
    # thì khoảng hở biến mất → tiếng chạy sớm dần (đo 02/11: +21/+61/+76 ms sau clip 2/3/4, khẩu hình lệch). Chèn im lặng đúng mốc.
    fl.append("".join(f"[v{k}][a{k}]" for k in range(len(ds))) + f"concat=n={len(ds)}:v=1:a=1[v][a0]")
    fl.append("[a0]aresample=async=1000:first_pts=0[a]")
    tam = ra + ".tmp.mp4"
    ma, err = chung.chay_ffmpeg([chung.duong("ffmpeg"), "-v", "error", "-y", "-nostdin", *args, "-filter_complex", ";".join(fl), "-map", "[v]", "-map", "[a]",
                                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "16"] + chung.MAU_RA_BT709 + ["-c:a", "aac", "-b:a", "192k", tam],
                                du_an, f"nối {len(ds)} clip người nói ({W}x{H} @{fps})", dur=tong or None)
    if ma != 0 or not os.path.isfile(tam):
        raise RuntimeError("không nối được các clip người nói: " + err[-400:])
    os.replace(tam, ra)
    return ra


def chuan_bi_viec(ph):
    d = ph["du_an"]; tt = ph.get("thong_tin") or {}
    chinh = [chung.NFC(v) for v in tt.get("video") or []]
    phu = [chung.NFC(v) for v in tt.get("phu") or []]
    if not chinh:
        raise RuntimeError("phiếu không có video")
    xuat_4k, giu_fps = bool(tt.get("xuat_4k")), bool(tt.get("giu_fps"))          # 1.2.21: st.py đã tính từ lời khách / --4k → chép sang viec.json
    nguon_chinh = chinh[0] if len(chinh) == 1 else _ghep_nguon_chinh(d, chinh, xuat_4k, giu_fps)
    i0 = chung.ffprobe(nguon_chinh) or {"w": 1080, "h": 1920}
    yc = tt.get("yeu_cau") or ""
    doc_ = i0["h"] >= i0["w"] or re.search(r"\b(dọc|9:16|tiktok|reels|shorts)\b", yc, re.I)
    if re.search(r"\b(ngang|16:9|youtube)\b", yc, re.I):
        doc_ = False
    v = chung.doc_json(os.path.join(d, "viec.json")) or {}
    v.update({"ten": ph.get("ten"), "ho_so": ph.get("ho_so"), "yeu_cau": yc, "che_do": "ky",
              "nguon": [{"duong": nguon_chinh, "vai": "chinh"}] + [{"duong": p, "vai": "phu"} for p in phu],
              "nguon_goc_chinh": chinh, "khung": [1080, 1920] if doc_ else [1920, 1080], "fps": 30,
              "mau_video": tt.get("mau_video"), "cho_chinh_mau": bool(tt.get("cho_chinh_mau")), "goi": tt.get("goi"),
              "xuat_4k": xuat_4k, "giu_fps": giu_fps})
    v.setdefault("buoc_xong", [])
    if tt.get("nhin"):                                    # mức nhìn khung (bat-dau --nhin thua|vua|day) → doc/khung.py
        v["nhin"] = tt["nhin"]
    chung.ghi_json(os.path.join(d, "viec.json"), v)
    return v


# ───────────────────────────────────────────── các bước thật (chạy trong tiến trình nền `_lam`)
def tu_dien(khung=None):
    """từ điển công cụ cho AI: ai/tu_dien.py (động: phần cố định + danh mục mẫu + lớp web) — chưa có thì cheat_sheet.md"""
    _dat_mau_rieng(None)
    try:
        from ai import tu_dien as TD
        return TD.tu_dien(tuple(khung) if khung else (1080, 1920))
    except Exception:
        return open(os.path.join(V3, "ai", "cheat_sheet.md"), encoding="utf-8").read()


def _dat_mau_rieng(ph):
    """thư mục mẫu riêng của hồ sơ + dự án → V3_MAU_RIENG (registry dung/mau nạp thêm)"""
    ds = []
    if ph:
        hs = os.path.join(chung.duong("ho_so"), ph.get("ho_so") or "", "mau-rieng")
        ds += [hs, os.path.join(ph["du_an"], "mau-rieng")]
    os.environ["V3_MAU_RIENG"] = os.pathsep.join(x for x in ds if os.path.isdir(x))


TACH_NEN_TU = re.compile(r"t[aá]ch\s*n[eề]n|x[oó]a\s*n[eề]n|xo[aá]\s*ph[oô]ng|đ[oổ]i\s*n[eề]n|n[eề]n\s*m[oớ]i|green\s*screen|ph[oô]ng\s*xanh", re.I)


def _tach_nguoi_som(d, v):
    """yêu cầu có nhắc tách/xoá/đổi nền → tách người CẢ VIDEO ngay sau khi đọc, chạy nền ưu tiên thấp trong lúc AI nghĩ"""
    if not TACH_NEN_TU.search(v.get("yeu_cau") or ""):
        return
    px = _nguon_proxy(d)
    if not px or not os.path.isfile(px):
        return
    flags = (0x00000008 | 0x00000200 | 0x08000000 | 0x00004000) if os.name == "nt" else 0
    log = open(os.path.join(d, "v3-alpha-som.log"), "a", encoding="utf-8")
    p_som = subprocess.Popen([chung.python_nen(), os.path.abspath(__file__), "_alpha_som", d, px], stdout=log, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, cwd=SKILL, env=dict(os.environ, PYTHONUTF8="1"), creationflags=flags,
                             start_new_session=(os.name != "nt"))
    chung.ghi_json(os.path.join(d, ".v3-alpha-som.json"), {"trang_thai": "chay", "luc": time.time(), "proxy": px, "pid": p_som.pid})   # pid: Dừng giết được
    chung.log(d, "tách người cả video: chạy nền trong lúc AI nghĩ (yêu cầu có nhắc tách nền)")


def _alpha_som_lam(d, px):
    from doc import alpha as A
    tt = os.path.join(d, ".v3-alpha-som.json")
    try:
        with chung.DoThoiGian(d, "alpha (sớm, cả video)"):
            p = A.tao_ranh(d, px, None, None, uu_tien_thap=True)
        chung.ghi_json(tt, {"trang_thai": "xong", "duong": p, "luc": time.time()})
    except Exception as ex:
        chung.ghi_json(tt, {"trang_thai": "loi", "loi": str(ex)})


def _kiem_o_dia(ph, buoc):
    """1.2.19 (E3): ổ chứa dự án phải còn ≥ max(2 GB, 3 × cỡ video nguồn) trước khi đọc/dựng — hết ổ giữa chừng là lỗi khó hiểu nhất"""
    d = ph["du_an"]
    trong = chung.o_dia_trong_gb(d)
    if trong is None:
        return
    co = 0.0
    ti = ph.get("thong_tin") or {}
    ds = list(ph.get("nguon") or []) + list(ti.get("video") or []) + list(ti.get("phu") or [])
    if not ds:
        ds = list((chung.doc_json(os.path.join(d, "viec.json"), {}) or {}).get("nguon") or [])
    da = set()
    for n in ds:
        p = n.get("duong") if isinstance(n, dict) else n
        if not isinstance(p, str) or p in da:
            continue
        da.add(p)
        try:
            co += os.path.getsize(p) / 1e9
        except (OSError, TypeError):
            pass
    can = max(2.0, 3.0 * co)
    if trong < can:
        raise RuntimeError(f"Ổ chứa dự án ({os.path.splitdrive(d)[0] or d[:2]}) chỉ còn {trong:.1f} GB, bước {buoc} cần khoảng {can:.1f} GB "
                           f"(3 × video nguồn {co:.1f} GB). Dọn ổ hoặc đổi thư mục dự án trong cau-hinh.json (du_an) rồi chạy lại.")


def _ghi_buoc_xong(d, buoc):
    """1j: viec.json["buoc_xong"] — bước đã xong (doc/tron/giao/hoc); chạy lại sau khi bị giết biết nối từ đâu (st.py tiep)"""
    v = chung.doc_json(os.path.join(d, "viec.json")) or {}
    bx = [b for b in (v.get("buoc_xong") or []) if b != buoc] + [buoc]
    v["buoc_xong"] = bx
    v["buoc_xong_luc"] = dict(v.get("buoc_xong_luc") or {}, **{buoc: time.strftime("%Y-%m-%d %H:%M:%S")})
    if buoc == "doc":                                        # tron/giao làm lại thì vẫn tính; doc làm lại → bỏ dấu tron/giao cũ
        v["buoc_xong"] = ["doc"]
    chung.ghi_json(os.path.join(d, "viec.json"), v)


def _don_tep_do(d):
    """1j: mở lại việc — bỏ mọi tệp .tmp ghi dở (bị giết giữa chừng) trong cache/, cache/khuc, dung/, doc/"""
    n = 0
    som = chung.doc_json(os.path.join(d, ".v3-alpha-som.json")) or {}
    giu_alpha = som.get("trang_thai") == "chay" and bool(som.get("pid")) and _con_song(som["pid"])   # R4a: tách người sớm còn chạy → không đụng alpha-*.tmp.mp4 của nó
    bo_qua = (lambda ten: ten.startswith("alpha-") and ten.endswith(".tmp.mp4")) if giu_alpha else None
    for tm in ("cache", os.path.join("cache", "khuc"), "dung", "doc", ""):
        n += chung.don_tep_tam(os.path.join(d, tm), bo_qua=bo_qua if tm == "cache" else None)
    if n:
        chung.log(d, f"dọn {n} tệp tạm dở của lần chạy trước")


def lam_doc(ph):
    import quy_trinh as Q
    d = ph["du_an"]; lg = _log(d)
    _kiem_o_dia(ph, "đọc")
    _don_tep_do(d)
    v = chuan_bi_viec(ph)
    chuan_bi_ho_so(ph.get("ho_so"))
    bg = {}
    with _giu_may("doc", d):
        Q.b_doc(d, v, lg, bg)
    Q.b_cat(d, v, lg)
    Q.b_tom_tat(d, v, lg)
    _tach_nguoi_som(d, v)
    if v.get("mau_video") and os.path.isfile(v["mau_video"]):
        try:
            from hoc import hoc as H
            with chung.DoThoiGian(d, "mau"):
                nl = H.chuan_bi(v["mau_video"], os.path.join(d, "mau"), log=lambda m: chung.log(d, m))
            chung.ghi_json(os.path.join(d, "mau", "anh.json"), nl)
        except Exception as ex:
            chung.log(d, f"không bóc được video mẫu: {ex}")


def _nguon_proxy(d):
    n = chung.doc_json(os.path.join(d, "doc", "nguon.json")) or {}
    if isinstance(n.get("chinh"), dict):
        return n["chinh"].get("proxy")
    for x in n.get("danh_sach") or []:
        if x.get("vai") == "chinh":
            return x.get("proxy")
    return n.get("proxy")


def _ranh_alpha(d, kh):
    """nền mới → tách người CHỈ đoạn giây gốc cần dùng (rãnh xám, cache) → kh["alpha"]"""
    nm = kh.get("nen_moi") or []
    if not nm:
        return None
    from doc import alpha as A
    from dung import ghep as G
    cat = kh.get("cat") or []
    a_min, b_max, t = None, None, 0.0
    for s in cat:
        dai = s["b"] - s["a"]
        for x in nm:
            x0, x1 = float(x.get("t0", 0)), float(x.get("t1", 1e9))
            o0, o1 = max(t, x0), min(t + dai, x1)
            if o1 > o0 and int(s.get("src", 0)) == 0:
                a = s["a"] + (o0 - t); b = s["a"] + (o1 - t)
                a_min = a if a_min is None else min(a_min, a); b_max = b if b_max is None else max(b_max, b)
        t += dai
    if a_min is None:
        return None
    a_min = max(0.0, a_min - 0.2); b_max = b_max + 0.2
    som = os.path.join(d, ".v3-alpha-som.json")
    for _ in range(900):                                   # tách sớm đang chạy → chờ (tối đa ~15 phút), xong thì dùng luôn
        st = chung.doc_json(som) or {}
        if st.get("trang_thai") != "chay":
            break
        time.sleep(1.0)
    st = chung.doc_json(som) or {}
    if st.get("trang_thai") == "xong" and st.get("duong") and os.path.isfile(st["duong"]):
        inf = chung.ffprobe(st.get("duong")) or {}
        return {"duong": st["duong"], "a": 0.0, "dur_nguon": (chung.ffprobe(_nguon_proxy(d)) or {}).get("dur") or inf.get("dur")}
    px = _nguon_proxy(d)
    if not px or not os.path.isfile(px):
        raise RuntimeError("không thấy proxy để tách người")
    with chung.DoThoiGian(d, "alpha"):
        p = A.tao_ranh_tai_su_dung(d, px, a_min, b_max, uu_tien_thap=False)     # 1.2.19: dùng lại rãnh đã có
    if not p:
        return None
    inf = chung.ffprobe(px) or {}
    return {"duong": p, "a": round(a_min, 3), "dur_nguon": inf.get("dur")}


def _chong_that(d, kh):
    """hộp THẬT (engine đo chữ, dời mặt, vùng an toàn) của các lớp chữ/thẻ/hình → cặp chồng nhau > 30% trong > 0.15 s"""
    import copy
    from dung import dung as DG, lop as LP
    ctx = DG.tao_ctx(d, copy.deepcopy(kh))
    hop = []

    def _bo_qua(sp):                                       # lớp phủ / toàn khung / cố ý đè → không xét chồng
        kd = sp.get("kieu_dang") or {}; vt = sp.get("vi_tri") or {}
        if sp.get("ne_mat") is False or (kd.get("hoa_tron") or "normal") != "normal":
            return True
        if float(vt.get("w") or 0) >= 0.95 and float(vt.get("h") or 0) >= 0.95:
            return True
        if sp.get("kieu") == "mau":
            try:
                from dung import mau as M
                r = M.lay(((sp.get("noi_dung") or {}).get("mau")) or "")
                return bool(r and (r["the"].get("toan_khung") or r["the"].get("lam_nen") is True))
            except Exception:
                return False
        return False

    for sp in kh.get("lop") or []:
        if sp.get("kieu") not in ("chu", "khoi", "the", "hinh", "mau", "web") or _bo_qua(sp):
            continue
        try:
            x, y, w, h = LP.tao_lop(sp, ctx).khoi()
            hop.append((sp, (x, y, x + w, y + h)))
        except Exception as ex:
            if type(ex).__name__ == "ThieuTruong":          # 1.2.21: thiếu trường quyết định → trả AI (lam() in danh sách), không nuốt
                raise
            pass
    loi = []
    for i in range(len(hop)):
        for j in range(i + 1, len(hop)):
            (a, ha), (b, hb) = hop[i], hop[j]
            na, nb = (a.get("vi_tri") or {}).get("nhom"), (b.get("vi_tri") or {}).get("nhom")
            if na and na == nb:                            # cùng nhóm xếp chồng → engine đã xếp, không chồng thật
                continue
            t = min(float(a["t1"]), float(b["t1"])) - max(float(a["t0"]), float(b["t0"]))
            if t <= 0.15:
                continue
            gx = max(0.0, min(ha[2], hb[2]) - max(ha[0], hb[0])); gy = max(0.0, min(ha[3], hb[3]) - max(ha[1], hb[1]))
            nho = min((ha[2] - ha[0]) * (ha[3] - ha[1]), (hb[2] - hb[0]) * (hb[3] - hb[1])) or 1
            if gx * gy / nho > 0.3:
                loi.append({"id": "chong_lop", "lop": f"{a.get('id')}+{b.get('id')}", "t": round(max(float(a["t0"]), float(b["t0"])), 2),
                            "mo_ta": f"hai lớp chồng {gx * gy / nho * 100:.0f}% trong {t:.1f}s (hộp thật sau khi đo chữ) — lệch giờ (t1 lớp trước ≤ t0 lớp sau) hoặc đổi vi_tri/anchor"})
    return loi


def lam_tron(ph):
    import quy_trinh as Q
    d = ph["du_an"]; lg = _log(d)
    v = chung.doc_json(os.path.join(d, "viec.json")) or chuan_bi_viec(ph)
    ct = os.path.join(d, "cong-thuc.json")
    if not os.path.isfile(ct):
        raise RuntimeError("chưa có cong-thuc.json")
    _kiem_o_dia(ph, "dựng")
    _don_tep_do(d)
    with chung.DoThoiGian(d, "chuan_hoa"):
        kh, kq, chan = Q._chuan_hoa_kiem(d, ct, lg)
    if not chan:
        chan = _chong_that(d, kh)                # chữ/thẻ chồng nhau theo hộp THẬT → chặn trước khi dựng (AI lệch giờ / đổi chỗ)
    if chan:
        chung.ghi_json(os.path.join(d, ".v3-chan.json"), chan)
        raise _Chan(chan)
    with _giu_may("dung", d):
        if kh.get("nen_moi"):
            al = _ranh_alpha(d, kh)
            if al:
                kh["alpha"] = al
                chung.ghi_json(os.path.join(d, "ke-hoach.json"), kh)
        Q.b_dung(d, v, lg)
    Q.b_xem_lai(d, v, lg)                         # (gồm cả vẽ 3 bìa)


class _Chan(Exception):
    def __init__(self, ds):
        super().__init__("máy chặn")
        self.ds = ds


def _thieu_truong_cua(ex):
    """lỗi thiếu trường của mọi mô-đun → [{"duong","ma","goi_y","lop"}]: chung.ThieuTruong (.loi là list) hoặc dung.chu.ThieuTruong (.loi() là dict)"""
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
    return [x for x in l if isinstance(x, dict)]


def lam(buoc, them):
    if buoc == "_alpha_som":
        return _alpha_som_lam(them[0], them[1])
    d = os.environ.get("V3_DU_AN")
    ph = chung.doc_json(os.path.join(d, "phieu.json"))
    _dat_mau_rieng(ph)
    tt = os.path.join(d, f".v3-{buoc}.json")
    try:
        if buoc == "doc":
            lam_doc(ph)
        elif buoc == "tron":
            lam_tron(ph)
        _ghi_buoc_xong(d, buoc)
        chung.ghi_json(tt, {"trang_thai": "xong", "luc": time.time()})
    except _Chan as ex:
        chung.ghi_json(tt, {"trang_thai": "loi", "chan": ex.ds, "luc": time.time()})
    except Exception as ex:
        ds_tt = _thieu_truong_cua(ex)
        if ds_tt:                                            # 1.2.21: máy không tự điền (chung.ThieuTruong của am/bìa, dung.chu.ThieuTruong của lớp) → trả AI danh sách trường
            chung.log(d, "THIẾU TRƯỜNG: " + ", ".join(l.get("duong", "?") for l in ds_tt))
            chung.ghi_json(tt, {"trang_thai": "loi", "thieu_truong": ds_tt, "loi": str(ex), "luc": time.time()})
            return
        chung.log(d, "LỖI: " + "".join(traceback.format_exception_only(type(ex), ex)).strip())
        chung.ghi_json(tt, {"trang_thai": "loi", "loi": str(ex), "vet": traceback.format_exc()[-3000:], "luc": time.time()})


# ───────────────────────────────────────────── lệnh người dùng (Claude) gọi
def _in_loi(ph, buoc):
    st = chung.doc_json(os.path.join(ph["du_an"], f".v3-{buoc}.json")) or {}
    if st.get("chan"):
        print("TRỌN: DỪNG — máy chặn (luật chất lượng). Sửa cong-thuc.json đúng các lỗi dưới rồi chạy lại `nhanh tron`:")
        for l in st["chan"]:
            print(f"  ⛔ [{l.get('id')}] {l.get('lop', '')}{' @' + str(l.get('t')) + 's' if l.get('t') is not None else ''}: {l.get('mo_ta', '')}")
    elif st.get("thieu_truong"):
        print(f"{buoc.upper()}: DỪNG — THIẾU TRƯỜNG (máy không tự điền số thẩm mỹ). Ghi các trường dưới vào cong-thuc.json "
              "(hoặc quyet-dinh-kenh.json của kênh) rồi chạy lại:")
        for l in st["thieu_truong"]:
            print(f"  ⛔ {l.get('duong')} [{l.get('ma', 'thieu_truong')}]" + (f": {l['goi_y']}" if l.get("goi_y") else ""))
    else:
        print(f"LỖI ({buoc}): {st.get('loi', '?')}")
        if st.get("vet"):
            print(st["vet"][-1200:])


def lenh_doc(a):
    ph = doc_phieu()
    ma = _chay_nen(ph, "doc")
    if ma == 75:
        sys.exit(75)
    ph = doc_phieu()
    if ma != 0:
        _in_loi(ph, "doc"); sys.exit(1)
    danh_dau(ph, PHAN_DOC, "v3 doc")
    d = ph["du_an"]
    print("\n" + "═" * 70)
    print(open(os.path.join(d, "doc", "tom-tat.md"), encoding="utf-8").read())
    mau = chung.doc_json(os.path.join(d, "mau", "anh.json"))
    if mau:
        print("\n## VIDEO MẪU khách đưa — học CÁCH LÀM (bố cục, chữ hiện ra, đồ hoạ, nhịp theo lời), không chép chữ/logo/mặt")
        for p in [mau.get("bang_deu")] + list(mau.get("bang_su_kien") or []):
            if p:
                print(f"- mở: {p}")
        sm = os.path.join(d, "mau", "spec-may.json")
        if os.path.isfile(sm):
            print(f"- số đo máy (Style Spec đo sẵn: kiểu chữ vào/ra, thời lượng, màu, neo so với mặt): {sm}")
    print("\n" + "═" * 70)
    print(tu_dien(v.get("khung") if (v := chung.doc_json(os.path.join(d, "viec.json"), {}) or {}) else None))
    print("═" * 70)
    print(f"DỰ ÁN: {d}")
    _in_bang_khung(d)
    print(f"VIẾT: {os.path.join(d, 'cong-thuc.json')}  →  rồi chạy `nhanh tron`")


def _in_bang_khung(d):
    """in danh sách bảng khung tầng 2 (doc/khung.py); bảng vẽ trước khi có cat-de-xuat → vẽ lại để ô có giây thành phẩm"""
    bk = chung.doc_json(os.path.join(d, "doc", "bang-khung.json")) or {}
    if bk.get("anh") and not bk.get("co_cat") and os.path.isfile(os.path.join(d, "doc", "cat-de-xuat.json")):
        try:
            from doc import khung as K
            bk = K.bang(d, bk.get("muc"))
        except Exception as ex:
            chung.log(d, f"vẽ lại bảng khung lỗi (giữ bảng cũ): {ex}")
    anh = [p for p in (bk.get("anh") or []) if os.path.isfile(p)]
    if not anh:
        print(f"BẢNG KHUNG: {os.path.join(d, 'doc', 'bang-khung.jpg')}")
        return
    print(f"BẢNG KHUNG — MỞ HẾT {len(anh)} ảnh (mức nhìn {bk.get('muc')}: {bk.get('so_khung')} khung, lấy dày ở chỗ video đổi nhiều; "
          f"ô ghi giây gốc{' + dòng 2 «tp» = giây thành phẩm theo cắt đề xuất («tp: bỏ» = đoạn đề xuất bỏ)' if bk.get('co_cat') else ''}; viền vàng = ngay sau cắt cảnh):")
    for k, b in enumerate(bk.get("bang") or [{"anh": p} for p in anh]):
        if os.path.isfile(b.get("anh") or ""):
            kh = f"   ({b['tu']}–{b['den']}s gốc, {b['so']} khung)" if b.get("so") else ""
            print(f"  {k + 1}) {b['anh']}{kh}")
    print("Muốn nhìn kỹ đoạn nào: `v2/st.py nhanh khung --tu <giây gốc> --den <giây gốc> [--fps N] [--o-lon]` rồi MỞ ảnh nó in.")
    try:                                                   # BẢNG MẪU ĐỒ HOẠ: AI thấy mọi công cụ trông thế nào (dữ liệu, không gợi ý)
        from dung.mau import bang as _bang
        bm = _bang.dam_bao()
        print(f"BẢNG MẪU ĐỒ HOẠ — MỞ HẾT {len(bm['anh'])} ảnh ({bm['so_mau']} mẫu, màu trung tính; mẫu nào cũng đổi màu/font/tham số theo video):")
        for p_ in bm["anh"]:
            print(f"- mở: {p_}")
        print("Xem kỹ chuyển động một mẫu: `v2/st.py nhanh mau --id mau.<id>` → ảnh dải 6 thời điểm. Bộ công cụ ngoài mẫu: lớp chu/the/hinh/video/web/py, nen_moi, camera, chuyen_canh, lớp phủ hoà trộn, mau_video (khi được phép) — xem từ điển.")
    except Exception as ex:
        print(f"(bảng mẫu đồ hoạ chưa sẵn: {ex})")


def lenh_broll(a):
    """MẮT B-ROLL: quét video phụ / thư mục tư liệu → doc/b-roll.json + bảng khung từng tệp; in cho AI mở ảnh và dùng lớp `video`"""
    from doc import broll as BR
    ph = doc_phieu(); d = ph["du_an"]
    ds = list(a.duong or [])
    if not ds:                                              # không đưa gì → video phụ của việc
        ds = [n.get("duong") for n in (ph.get("nguon") or chung.doc_json(os.path.join(d, "viec.json"), {}).get("nguon") or [])
              if isinstance(n, dict) and n.get("vai") == "phu"]
    if not ds:
        print("Cần đường dẫn tệp video hoặc thư mục: `nhanh broll <đường 1> [<đường 2>…]`"); sys.exit(2)
    try:
        BR.quet(d, ds, log=print)
    except Exception as ex:
        print(f"LỖI (b-roll): {ex}"); sys.exit(1)
    print("\n".join(BR.dong_tom_tat(d)))
    try:
        from doc import tom_tat as TT
        TT.viet(d)                                          # cập nhật bản tóm tắt để lượt sau vẫn thấy
    except Exception:
        pass


def lenh_khung(a):
    """MẮT tầng 3: AI xin nhìn kỹ một đoạn → doc/soi-<tu>-<den>.jpg (+ -2 …), in đường ảnh; --nguon <n|đường> = nhìn một B-roll"""
    from doc import khung as K
    ph = doc_phieu(); d = ph["du_an"]
    if a.tu is None or a.den is None:
        print("Cần --tu <giây gốc> --den <giây gốc> (tuỳ chọn --fps N tới 30, --o-lon, --nguon <n|đường B-roll>)"); sys.exit(2)
    if getattr(a, "nguon", None):
        from doc import broll as BR
        try:
            kq = BR.soi(d, a.nguon, a.tu, a.den, a.fps)
        except Exception as ex:
            print(f"LỖI (b-roll): {ex}"); sys.exit(1)
        print(f"SOI B-ROLL {os.path.basename(kq['duong'])} {a.tu}–{a.den}s: {kq['so_khung']} khung ({kq['fps']:.1f} khung/giây) — MỞ:")
        print(f"  {kq['anh']}")
        return
    try:
        kq = K.soi(d, a.tu, a.den, a.fps, a.o_lon)
    except Exception as ex:
        print(f"LỖI (khung): {ex}"); sys.exit(1)
    print(f"SOI {a.tu}–{a.den}s gốc: {kq['so_khung']} khung ({kq['fps']} khung/giây) — MỞ HẾT:")
    for p in kq["anh"]:
        print(f"  {p}")
    for g in kq.get("ghi_chu") or []:
        print(f"  ({g})")


def lenh_tron(a):
    ph = doc_phieu()
    ma = _chay_nen(ph, "tron")
    if ma == 75:
        sys.exit(75)
    ph = doc_phieu()
    if ma != 0:
        _in_loi(ph, "tron"); sys.exit(1)
    d = ph["du_an"]
    danh_dau(ph, PHAN_TU_DUY, "v3 tron"); ghi_cong(ph, 1, True); ghi_cong(ph, 2, True)
    danh_dau(ph, PHAN_DUNG_TRON, "v3 tron")
    kq = chung.doc_json(os.path.join(d, "kiem.json"), {}) or {}
    tg = chung.doc_json(os.path.join(d, "nhat-ky-thoi-gian.json"), []) or []
    che = [x for x in (kq.get("loi_dung") or []) if isinstance(x, dict) and x.get("id") == "de_mat"]
    if che:                                                # đã dựng nhưng còn lớp che mặt → AI phải sửa, không được giao
        print("TRỌN: DỪNG — đã dựng nhưng còn lớp CHE MẶT (máy không dời được). Sửa cong-thuc.json rồi `nhanh tron` lại:")
        for x in che:
            print(f"  - lớp {x.get('lop')} lúc {x.get('t')}s: đổi vi_tri (neo phía trên/dưới mặt, thu w/h) hoặc `ne_mat:false` nếu CỐ Ý đè (vd chữ sau người)")
        print(f"  (ảnh xem lại: {os.path.join(d, 'dung', 'xem-lai.jpg')})")
        sys.exit(1)
    print("TRỌN: XEM — video đã dựng. MỞ (Read) 2 ảnh dưới rồi quyết:")
    print(f"  1) {os.path.join(d, 'dung', 'xem-lai.jpg')}   (8 khung thành phẩm)")
    bias = sorted(glob.glob(os.path.join(d, "dung", "bia-*.png")))
    if bias:
        print(f"  2) {' · '.join(_bia_xem(b) for b in bias)}   ({len(bias)} bìa — bản xem 540 px; bản gốc PNG đủ khổ dùng khi giao)")
    if kq.get("may_sua"):
        print(f"  máy đã tự sửa {len(kq['may_sua'])} chỗ số học: " + "; ".join(str(x.get('mo_ta') or x.get('sua')) for x in kq["may_sua"][:6]))
    if kq.get("loi_dung"):
        print("  LỖI LÚC DỰNG (lớp bị bỏ/khác ý): " + "; ".join(str(x.get("mo_ta") if isinstance(x, dict) else x) for x in kq["loi_dung"][:6]))
    if kq.get("canh_bao"):
        print("  cảnh báo: " + "; ".join(x.get("mo_ta", "") for x in kq["canh_bao"][:6]))
    for dong in _tu_soi(d):
        print("  " + dong)
    print(f"  Đạt → `nhanh giao --bia <1..{max(1, len(bias))}>`. Chưa đạt → sửa cong-thuc.json rồi `nhanh tron` lại (chỉ dựng lại phần đổi).")
    print(f"  (máy: {sum(x.get('giay', 0) for x in tg):.0f}s tổng các bước tới giờ)")


def _bia_xem(p):
    """1.2.19 (F2): bìa gửi AI xem = JPEG 540 px (≈ 1/12 token ảnh so với PNG 1080×1920); lỗi thì trả bản gốc"""
    try:
        from PIL import Image
        q = p[:-4] + "-xem.jpg"
        if not os.path.isfile(q) or os.path.getmtime(q) < os.path.getmtime(p):
            im = Image.open(p).convert("RGB"); im.thumbnail((540, 960)); im.save(q, quality=82)
        return q
    except Exception:
        return p


def _tu_soi(d):
    """PHIẾU TỰ SOI — chỉ SỐ ĐO khách quan của bản dựng (máy không phán nhiều/ít; AI đối chiếu với y_do và bản sắc kênh)"""
    kh = chung.doc_json(os.path.join(d, "ke-hoach.json"), {}) or {}
    lop = [l for l in kh.get("lop") or [] if isinstance(l, dict)]
    dh = [l for l in lop if l.get("kieu") in ("chu", "khoi", "the", "hinh", "mau", "web", "video", "duong", "py") and not str(l.get("id", "")).startswith("pd")]
    dur = float(kh.get("dur") or 0) or max([float(l.get("t1", 0)) for l in lop] + [1.0])
    ra = []
    if dh:
        t0s = sorted(float(l["t0"]) for l in dh)
        dinh = max(sum(1 for b in t0s[i:] if b < a + 10) for i, a in enumerate(t0s))
        ds = sorted((float(l["t0"]), float(l["t1"])) for l in dh)
        phu, cuoi = 0.0, 0.0
        for a_, b_ in ds:
            if b_ > cuoi:
                phu += b_ - max(a_, cuoi); cuoi = b_
        kieu = {((l.get("noi_dung") or {}).get("mau") if l.get("kieu") == "mau" else l.get("kieu")) for l in dh}
        td = [l for l in dh if l.get("kieu") == "mau" and any(k in str((l.get("noi_dung") or {}).get("mau", "")).lower() for k in ("glitch", "leak", "vet-sang", "chop", "3d", "phat-sang"))]
        ra.append(f"PHIẾU TỰ SOI · đồ hoạ {len(dh)} lớp ({len(dh) / max(0.5, dur / 60):.1f}/phút) · đông nhất {dinh} lớp mới/10 s · "
                  f"không đồ hoạ {100 * (1 - phu / dur):.0f}% thời lượng · {len(kieu)} kiểu · trình diễn {len(td)}")
    else:
        ra.append("PHIẾU TỰ SOI · không có lớp đồ hoạ")
    am = kh.get("am") or {}
    nh = am.get("nhac") or {}
    if nh:
        lu = nh.get("db") if nh.get("db") is not None else {"nhe": -24, "vua": -18, "noi": -12}.get(str(nh.get("muc") or "").lower(), -22)
        ra.append(f"  nhạc `{nh.get('id') or nh.get('nghia')}` {lu} LU dưới giọng ({nh.get('muc') or 'mặc định'}) · sfx {len(am.get('sfx') or [])}")
    else:
        ra.append("  không nhạc nền")
    cx = chung.doc_json(os.path.join(d, "doc", "cat-de-xuat.json"), {}) or {}
    tk = cx.get("thong_ke") or {}
    nguon_cat = kh.get("nguon_cat")
    ra.append(f"  cắt: {cx.get('dur_goc', '?')}s → {kh.get('dur', '?')}s (nhịp {cx.get('nhip', 'vua')}, bỏ {tk.get('lang', 0)} lặng + {tk.get('dem', 0)} ờ/đệm + {tk.get('lap', 0)} lặp"
              + (", AI tự cắt" if nguon_cat == "ai" else "") + ")")
    return ra


def lenh_giao(a):
    ph = doc_phieu(); d = ph["du_an"]
    v = chung.doc_json(os.path.join(d, "viec.json")) or {}
    vid = os.path.join(d, "dung", "thanh-pham.mp4")
    if not os.path.isfile(vid):
        print("CHẶN: chưa có video dựng — chạy `nhanh tron` trước"); sys.exit(2)
    sys.path.insert(0, V3)
    from nao import kiem as K
    with chung.DoThoiGian(d, "kiem_ky_thuat"):
        kt = K.kiem_ky_thuat(vid)
    chung.ghi_json(os.path.join(d, "kiem-ky-thuat.json"), kt)
    bias = sorted(glob.glob(os.path.join(d, "dung", "bia-*.png")))
    so = max(1, min(len(bias), int(a.bia or 1))) if bias else 0
    hs = chuan_bi_ho_so(ph.get("ho_so")) or {}
    bg = hs.get("ban_giao") or {}
    goc = os.path.expanduser(bg.get("thu_muc") or "~/Downloads")
    ra = os.path.join(goc, ph["ten"])
    for k in range(2, 100):
        dau = os.path.join(ra, ".du-an")
        if not os.path.exists(ra) or (os.path.exists(dau) and open(dau, encoding="utf-8").read().strip() == os.path.abspath(d)):
            break
        ra = os.path.join(goc, f"{ph['ten']}-{k}")
    os.makedirs(ra, exist_ok=True)
    open(os.path.join(ra, ".du-an"), "w", encoding="utf-8").write(os.path.abspath(d))
    shutil.copyfile(vid, os.path.join(ra, f"{ph['ten']}.mp4"))
    bia_chinh = None
    if bias:
        thu_tu = [bias[so - 1]] + [b for i, b in enumerate(bias) if i != so - 1]
        for i, b in enumerate(thu_tu):
            dst = os.path.join(ra, f"bia-{ph['ten']}.png" if i == 0 else f"bia-{ph['ten']}-{i + 1}.png")
            shutil.copyfile(b, dst)
            bia_chinh = bia_chinh or dst
    # báo cáo
    gd = os.path.join(d, "giao"); os.makedirs(gd, exist_ok=True)
    kq = chung.doc_json(os.path.join(d, "kiem.json"), {}) or {}
    tg = chung.doc_json(os.path.join(d, "nhat-ky-thoi-gian.json"), []) or []
    ct = chung.doc_json(os.path.join(d, "cong-thuc.json"), {}) or {}
    dong = [f"# Báo cáo giao — {ph['ten']}", "", f"Hồ sơ **{ph.get('ho_so')}** · lõi 1.3 · {v.get('khung')}", "",
            f"Ý đồ của AI: {ct.get('ghi_chu', '')}", "", "## Thời gian máy", "", "| bước | giây |", "|---|---:|"]
    gop = {}
    for x in tg:
        gop[x["buoc"]] = gop.get(x["buoc"], 0) + x.get("giay", 0)
    dong += [f"| {k} | {g:.1f} |" for k, g in gop.items()] + [f"| **tổng** | **{sum(gop.values()):.0f}** |", "",
             "## Kiểm", f"- Kỹ thuật: LUFS {kt.get('lufs')} · đỉnh {kt.get('peak')} dBTP · đen {len(kt.get('khung_den') or [])} · đứng {len(kt.get('dong_bang') or [])}"]
    for x in kq.get("may_sua") or []:
        dong.append(f"- máy sửa: {x.get('lop')}: {x.get('mo_ta') or x.get('sua')}")
    for x in kq.get("canh_bao") or []:
        dong.append(f"- cảnh báo: {x.get('mo_ta')}")
    open(os.path.join(gd, "bao-cao.md"), "w", encoding="utf-8").write("\n".join(dong) + "\n")
    # 1.2.21 (1h): KHÔNG chép thêm bản giao/<tên>.mp4 (thành phẩm đã có ở dung/thanh-pham.mp4 + Downloads) — giao/ chỉ giữ bao-cao.md + .du-an
    open(os.path.join(gd, ".du-an"), "w", encoding="utf-8").write(os.path.abspath(ra))
    ph = doc_phieu()
    ghi_cong(ph, 3, True); ghi_cong(ph, 4, bool(bias)); ghi_cong(ph, 5, True); ghi_cong(ph, 6, True)
    danh_dau(ph, PHAN_DUNG_GIAO, "v3 giao")
    ph = doc_phieu(); ph["dong"] = time.strftime("%Y-%m-%d %H:%M:%S"); luu_phieu(ph)
    _ghi_buoc_xong(d, "giao")
    try:                                                   # lịch sử dùng kho → video sau của hồ sơ tránh lặp tài nguyên
        from kho import lich_su as KLS
        KLS.ghi_tu_du_an(d)
    except Exception as ex:
        chung.log(d, f"(chưa ghi được lịch sử dùng kho: {ex})")
    ban_sac = ""
    try:                                                   # kênh CHƯA có bản sắc → rút bản sắc NHÁP từ chính video này (giữ nhất quán về sau)
        p_ss = os.path.join(chung.duong("ho_so"), ph["ho_so"], "style-spec.json")
        if not os.path.isfile(p_ss):
            from hoc import spec_tu_cong_thuc as STC
            kh_ = chung.doc_json(os.path.join(d, "ke-hoach.json"), {}) or {}
            sp_ = STC.tao(kh_, tho=chung.doc_json(os.path.join(d, "cong-thuc.json")))   # 1.2.19 (D3): chỉ rút trường AI đã ghi
            chung.ghi_json(p_ss, sp_)
            ban_sac = STC.tom_tat(sp_)
    except Exception as ex:
        chung.log(d, f"(chưa ghi được bản sắc nháp: {ex})")
    if os.environ.get("STUDIO_VIEC"):
        args = [sys.executable, os.path.join(SKILL, "studio", "bao.py"), "video", os.path.join(ra, f"{ph['ten']}.mp4")]
        if bia_chinh:
            args += ["--bia", bia_chinh]
        subprocess.run(args, capture_output=True, creationflags=(0x08000000 if os.name == "nt" else 0))
    tong = sum(gop.values())
    print(f"GIAO XONG → {ra}\n  video {os.path.basename(vid)} · {len(bias)} bìa · máy {tong:.0f}s · LUFS {kt.get('lufs')}")
    if ban_sac:
        print(f"  BẢN SẮC KÊNH (nháp, từ video đầu tiên): {ban_sac} — nói cho người dùng một dòng; các video sau giữ nhất quán, đổi bằng gop-y.")


# ───────────────────────────────────────────── HỌC (tab Học của hồ sơ): học NGÔN NGỮ THỊ GIÁC → Style Spec
def _tim_tai_video():
    """1.2.20: công cụ tải video đi kèm gói (…/taivideo.py cạnh app, hoặc tai-video-kenh/scripts) rồi mới tới skill cá nhân"""
    goc = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for p in (os.path.join(goc, "taivideo.py"), os.path.join(goc, "tai-video-kenh", "scripts", "taivideo.py"),
              os.path.join(goc, "tai-video-kenh", "taivideo.py"), os.path.expanduser("~/.claude/skills/tai-video-kenh/scripts/taivideo.py")):
        if os.path.isfile(p):
            return p
    return ""


TAI_VIDEO = _tim_tai_video()
DUOI_VIDEO = (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".avi")


def lenh_hoc_chuan_bi(a):
    """thu/nguon.txt (link hoặc đường dẫn video) → tải/gắn video → mỗi video: bảng khung đều + dải khung quanh sự kiện → in ảnh cho AI"""
    thu = os.path.abspath(a.thu)
    p_ng = os.path.join(thu, "nguon.txt")
    dong = [x.strip() for x in open(p_ng, encoding="utf-8").read().splitlines() if x.strip() and not x.startswith("#")] if os.path.isfile(p_ng) else []
    links = [x for x in dong if re.match(r"https?://", x)]
    if links:
        if os.path.isfile(TAI_VIDEO):
            p_l = os.path.join(thu, "_links.txt")
            open(p_l, "w", encoding="utf-8").write("\n".join(links) + "\n")
            print(f"▶ tải {len(links)} link…", flush=True)
            r_ = subprocess.run([sys.executable, TAI_VIDEO, "--file", p_l, "--out", thu], capture_output=True, creationflags=(0x08000000 if os.name == "nt" else 0), timeout=1800)
            if r_.returncode != 0:
                print(f"! tải link lỗi (mã {r_.returncode}): {(r_.stderr or r_.stdout).decode('utf-8', 'replace')[-300:]}")
        else:
            print("! chưa có công cụ tải video (skill tai-video-kenh) — chỉ học video trên máy")
    for x in dong:
        if re.match(r"https?://", x) or not os.path.isfile(x):
            continue
        dich = os.path.join(thu, os.path.basename(x))
        if not os.path.exists(dich):
            try:
                os.link(x, dich)
            except OSError:
                shutil.copyfile(x, dich)
    vs = sorted(p for p in glob.glob(os.path.join(glob.escape(thu), "*")) if p.lower().endswith(DUOI_VIDEO))
    if not vs:
        print("CHẶN: không có video nào để học"); sys.exit(2)
    from hoc import hoc as H
    print(f"ĐỌC TRƯỚC: {os.path.join(V3, 'hoc', 'HUONG-DAN-AI.md')} (cách viết spec từ số đo máy; máy đo đồ hoạ còn yếu — tin MẮT hơn số với đồ hoạ)")
    print(f"HỌC {len(vs)} video — học CÁCH LÀM (bố cục so với mặt, chữ hiện ra thế nào, đồ hoạ, nhịp theo lời), KHÔNG chép chữ/logo/mặt/giọng.")
    for v in vs:
        ma = chung.slug(os.path.splitext(os.path.basename(v))[0], 40)
        tm = os.path.join(thu, ma)
        if not os.path.isfile(os.path.join(tm, "so-lieu.json")):
            H.chuan_bi(v, tm, log=lambda m: print("  " + str(m), flush=True))
        # 1.2.20 — TẦNG 2: bản ghi thi công (mọi vệt chữ, cụm, đường cong chuyển động, sau người) + ngữ pháp (công thức có tham số)
        if not os.path.isfile(os.path.join(tm, "ngu-phap.json")) and os.environ.get("V3_HOC_TANG2", "1") != "0":
            try:
                from hoc import ban_ghi as BG, ngu_phap as NP
                loi_mau = None
                try:                                       # mốc từng từ của lời mẫu (Whisper, cache theo băm) → cụm bám từ nào
                    from doc import loi as LOI
                    d_loi = os.path.join(tm, "_loi"); os.makedirs(os.path.join(d_loi, "doc"), exist_ok=True)
                    am16 = os.path.join(d_loi, "am16.wav")
                    if not os.path.isfile(am16):
                        subprocess.run([chung.duong("ffmpeg"), "-v", "error", "-y", "-i", v, "-vn", "-ac", "1", "-ar", "16000", am16],
                                       creationflags=(0x08000000 if os.name == "nt" else 0), timeout=600)
                    lj = chung.doc_json(LOI.nhan(d_loi, am16))
                    loi_mau = lj.get("tu") if isinstance(lj, dict) else None
                except Exception as ex:
                    print(f"  (lời mẫu chưa đọc được: {str(ex)[:120]})")
                    loi_mau = None
                BG.tao(v, tm, loi=loi_mau, log=lambda m: print("  " + str(m), flush=True))
                NP.tu_thu_muc(tm, log=lambda m: print("  " + str(m), flush=True))
            except Exception as ex:
                import traceback
                print(f"  (tầng 2 bản ghi/ngữ pháp chưa chạy được: {traceback.format_exc(limit=2)[-300:]})")
        sl = chung.doc_json(os.path.join(tm, "so-lieu.json"), {}) or {}
        print(f"\n## {ma}  ({os.path.basename(v)} · {sl.get('dur', 0):.0f}s · {sl.get('so_cat')} cắt · cảnh TB {sl.get('canh_tb_s')}s · mặt TB {sl.get('mat_tb')})")
        def _thu_tu(p):                                    # 1.2.20: đúng thứ tự xem (khung → động học → soi/cận chữ), số 2 trước 10
            b = os.path.basename(p)
            nhom = 0 if "khung" in b else 1 if "dong-hoc" in b else 2 if "soi" in b else 3 if "chi-tiet" in b else 4
            so = re.findall(r"(\d+)", b)
            return (nhom, b.split("-")[-2] if nhom in (2, 3) else "", int(so[-1]) if so else 0, b)
        for p in [os.path.join(tm, "bang-deu.jpg")] + sorted(glob.glob(os.path.join(tm, "bang-su-kien-*.jpg")), key=_thu_tu):
            if os.path.isfile(p):
                print(f"- mở: {p}")
        for ten_, mt_ in (("ban-ghi.md", "BẢN GHI THI CÔNG — mọi cụm chữ của mẫu, từng dòng: cỡ/màu/xoay/trễ, vào-ra ở mức đường cong, sau người, bám lời"),
                          ("ngu-phap.md", "NGỮ PHÁP — công thức cụm có tham số + luật đặt/nhịp/màu (máy gom từ bản ghi; đây là thứ AI dùng lại khi dựng)"),
                          ("ban-ghi-lop.json", "bản lớp engine dựng lại được (dung_lai.py so với gốc)")):
            if os.path.isfile(os.path.join(tm, ten_)):
                print(f"- đọc: {os.path.join(tm, ten_)}  ({mt_})")
        for ten_, mt_ in (("dong_hoc.json", "số đo chuyển động chữ/phụ đề"), ("spec-may.json", "Style Spec máy đo sẵn — sửa/bổ sung")):
            if os.path.isfile(os.path.join(tm, ten_)):
                print(f"- số đo: {os.path.join(tm, ten_)}  ({mt_})")
        print(f"- viết: {os.path.join(tm, 'style-spec.json')}  (theo khuôn {os.path.join(V3, 'nao', 'style_spec.schema.json')})")
        print(f"- viết: {os.path.join(tm, 'bai-hoc.json')}  {{\"ten\": \"tên ngắn cách làm\", \"da_hoc\": [\"≥3 chi tiết kỹ thuật cụ thể\"], \"hop_noi_dung\": [\"…\"], \"cau_truc\": [\"…\"]}}")
    print(f"\nXONG thì: \"{sys.executable}\" v3/cau_noi.py hoc-luu --thu \"{thu}\" --ho-so <hồ sơ>")


def lenh_hoc_luu(a):
    """mỗi video đã có style-spec.json (+ bai-hoc.json) → nao/ca-nhan/<hs>/hoc/<ma>.json (+ ảnh) — hiện trong tab Học, bật/tắt được"""
    thu = os.path.abspath(a.thu)
    hs = a.ho_so
    d = os.path.join(chung.duong("ho_so"), hs, "hoc")
    os.makedirs(d, exist_ok=True)
    so = 0
    spec_cuoi, ma_cuoi = None, None
    da_dung = set()
    for tm in sorted(glob.glob(os.path.join(glob.escape(thu), "*", ""))):
        spec = chung.doc_json(os.path.join(tm, "style-spec.json"))
        if not spec:
            continue
        try:                                               # 1.2.20: spec AI viết phải đúng schema — sai thì không lưu (trước: lưu bừa, lúc dựng bỏ cả bản sắc)
            from hoc import kiem_spec as _KS
            loi_ss = _KS.kiem(spec)
        except Exception:
            loi_ss = []
        if loi_ss:
            print(f"✗ {os.path.basename(tm.rstrip('/\\'))}: style-spec.json sai schema, KHÔNG lưu — " + "; ".join(str(x) for x in loi_ss[:4]))
            continue
        bh = chung.doc_json(os.path.join(tm, "bai-hoc.json"), {}) or {}
        ma = "ss-" + chung.slug(bh.get("ten") or os.path.basename(tm.rstrip("/\\")), 40)
        if ma in da_dung or os.path.isfile(os.path.join(d, ma + ".json")):     # 1.2.20: không ghi đè bài trùng tên
            k = 2
            while ma + f"-{k}" in da_dung or os.path.isfile(os.path.join(d, ma + f"-{k}.json")):
                k += 1
            ma = ma + f"-{k}"
        da_dung.add(ma)
        spec_cuoi, ma_cuoi = spec, ma
        sl = chung.doc_json(os.path.join(tm, "so-lieu.json"), {}) or {}
        bai = {"ten": bh.get("ten") or ma, "nguon": os.path.basename(tm.rstrip("/\\")), "luc": time.strftime("%Y-%m-%d %H:%M"), "loai": "style_spec",
               "da_hoc": bh.get("da_hoc") or [], "hop_noi_dung": bh.get("hop_noi_dung") or [], "cau_truc": bh.get("cau_truc") or [],
               "hanh_dong_tom_tat": [f"{k}: {json.dumps(spec.get(k), ensure_ascii=False)[:160]}" for k in ("layout", "motion_vocab", "type_scale") if spec.get(k)],
               "style_spec": spec, "dai_mau": sl.get("dur"), "bat": True, "anh": True}
        try:                                               # dòng thời gian mẫu (máy sinh từ số đo) — AI lúc dựng thấy nhịp & thứ tự thật
            from hoc import dong_thoi_gian as _DTG
            bai["dong_thoi_gian"] = _DTG.tu_thu_muc(tm)
        except Exception:
            bai["dong_thoi_gian"] = []
        # 1.2.20: NGỮ PHÁP (công thức có tham số) + điểm đối chiếu → AI lúc dựng dùng ngữ pháp, không dùng chữ mẫu
        np_ = chung.doc_json(os.path.join(tm, "ngu-phap.json"))
        if np_:
            try:
                from hoc import ngu_phap as _NP
                bai["ngu_phap"] = np_; bai["ngu_phap_doc"] = _NP.doc_duoc(np_); bai["loai"] = "ngu_phap"
            except Exception:
                pass
        dc = chung.doc_json(os.path.join(tm, "doi-chieu.json"))
        if dc and dc.get("diem"):
            bai["doi_chieu"] = dc["diem"]
        chung.ghi_json(os.path.join(d, ma + ".json"), bai)
        anh = os.path.join(tm, "doi-chieu-1.jpg") if os.path.isfile(os.path.join(tm, "doi-chieu-1.jpg")) else os.path.join(tm, "bang-deu.jpg")
        if os.path.isfile(anh):
            shutil.copyfile(anh, os.path.join(d, ma + ".jpg"))
        so += 1
        print(f"✓ lưu bài {ma}: {bai['ten']} ({len(bai['da_hoc'])} ý đã học)")
    if not so:
        print("CHẶN: chưa có style-spec.json nào trong các thư mục video"); sys.exit(2)
    try:                                                   # spec HỌC được thay bản nháp (rút từ video đầu) làm bản sắc kênh
        p_ss = os.path.join(chung.duong("ho_so"), hs, "style-spec.json")
        cu = chung.doc_json(p_ss) or {}
        if spec_cuoi and (not cu or (cu.get("_nguon") or {}).get("loai") == "video_dau_tien"):
            moi = dict(spec_cuoi); ma = ma_cuoi; moi["_nguon"] = {"loai": "hoc_video_mau", "bai": ma, "luc": time.strftime("%Y-%m-%d %H:%M")}
            chung.ghi_json(p_ss, moi)
            print(f"  bản sắc kênh = spec học từ video mẫu ({ma}); máy áp vào mọi trường AI bỏ trống khi dựng.")
    except Exception as ex:
        print(f"  (chưa ghi được bản sắc từ bài học: {ex})")
    print(f"XONG: {so} bài vào thư viện học của hồ sơ {hs} — AI thấy khi dựng mọi video của hồ sơ (tắt trong tab Học nếu không muốn).")


def lenh_mau_xem(a):
    """`mau --id mau.<id>`: ảnh dải 6 thời điểm của một mẫu + tham số (xem kỹ trước khi dùng)"""
    from dung.mau import bang as _bang, lay as _lay
    mid = (a.id or "").strip()
    if not mid.startswith("mau."):
        mid = "mau." + mid
    r = _lay(mid)
    if not r:
        print(f"Không có mẫu `{mid}` — xem danh mục trong từ điển."); sys.exit(2)
    p = _bang.dai(mid)
    the = r["the"]
    print(f"MẪU {mid} — {the.get('ten')}: {the.get('mo_ta')}")
    print(f"- tham số: {json.dumps(the.get('tham_so') or {}, ensure_ascii=False)[:600]}")
    print(f"- mặc định: {json.dumps(the.get('mac_dinh') or {}, ensure_ascii=False)[:300]} · hộp: {the.get('hop')} · toàn khung: {the.get('toan_khung')} · cần nền: {the.get('lam_nen')}")
    print(f"- MỞ: {p}")


def lenh_mat_na(a):
    """XEM TRƯỚC MẶT NẠ tách người: 6 khung đều thân video (hoặc --luc "3,7.5"), mỗi khung = gốc | người trên nền
    caro hồng | viền mặt nạ đỏ → <dự án>/doc/mat-na.jpg. AI nhìn trước khi dùng nen_moi: mất tay/tóc/áo thì tránh đoạn đó."""
    import cv2, numpy as np
    from doc import alpha as A
    ph = doc_phieu(); d = ph["du_an"]
    px = _nguon_proxy(d)
    if not px or not os.path.isfile(px):
        print("Chưa có proxy — chạy `nhanh doc` trước."); sys.exit(2)
    dur = (chung.ffprobe(px) or {}).get("dur") or 0
    luc = [float(x) for x in (a.luc or "").split(",") if x.strip()] or [round(dur * (i + 0.5) / 6, 2) for i in range(6)]
    st = chung.doc_json(os.path.join(d, ".v3-alpha-som.json")) or {}
    ranh_som = st.get("duong") if st.get("trang_thai") == "xong" and os.path.isfile(st.get("duong") or "") else None

    def khung(video, t, xam=False):
        r = subprocess.run([chung.duong("ffmpeg"), "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1",
                            "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, creationflags=(0x08000000 if os.name == "nt" else 0))
        im = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_GRAYSCALE if xam else cv2.IMREAD_COLOR)
        return im

    o = []
    for t in luc:
        g = khung(px, t)
        if g is None:
            continue
        if ranh_som:
            m = khung(ranh_som, t, True)
        else:                                              # chưa có rãnh: tách ngay ảnh này trong tiến trình (cùng mạng 512 như video)
            m = (A.tach_anh(cv2.cvtColor(g, cv2.COLOR_BGR2RGB), muc="thuong") * 255).clip(0, 255).astype(np.uint8)
        if m is None:
            continue
        h = 480; w = int(g.shape[1] * h / g.shape[0])
        g = cv2.resize(g, (w, h)); m = cv2.resize(m, (w, h)).astype(np.float32) / 255.0
        yy, xx = np.mgrid[0:h, 0:w]
        caro = np.where(((yy // 16 + xx // 16) % 2)[..., None] == 0, (180, 105, 255), (120, 40, 200)).astype(np.float32)
        nguoi = (g.astype(np.float32) * m[..., None] + caro * (1 - m[..., None])).astype(np.uint8)
        vien = g.copy()
        cnt, _ = cv2.findContours((m > 0.5).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        cv2.drawContours(vien, cnt, -1, (0, 0, 255), 2)
        o_ = np.hstack([vien, nguoi])
        cv2.putText(o_, f"{t:.1f}s", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        o.append(o_)
    if not o:
        print("Không lấy được khung nào để xem mặt nạ."); sys.exit(1)
    rong = max(x.shape[1] for x in o)
    o = [cv2.copyMakeBorder(x, 0, 0, 0, rong - x.shape[1], cv2.BORDER_CONSTANT) for x in o]
    hang = [np.hstack(o[i:i + 2]) if i + 1 < len(o) else np.hstack([o[i], np.zeros_like(o[i])]) for i in range(0, len(o), 2)]
    ra = os.path.join(d, "doc", "mat-na.jpg"); os.makedirs(os.path.dirname(ra), exist_ok=True)
    cv2.imencode(".jpg", np.vstack(hang), [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tofile(ra)
    print(f"MẶT NẠ: {ra}  (mỗi ô: viền mặt nạ đỏ trên gốc | người trên caro hồng; hồng lọt vào người = mất người)")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "_lam":
        return lam(sys.argv[2], sys.argv[3:])
    if len(sys.argv) > 1 and sys.argv[1] == "_alpha_som":
        return lam("_alpha_som", sys.argv[2:])
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", choices=["doc", "tron", "giao", "ho-so", "hoc-chuan-bi", "hoc-luu", "mat-na", "mau", "khung", "broll"])
    ap.add_argument("duong", nargs="*", help="broll: tệp video / thư mục")
    ap.add_argument("--nguon", help="khung: chỉ số hoặc đường dẫn B-roll")
    ap.add_argument("--bia", default="1")
    ap.add_argument("--ho-so")
    ap.add_argument("--thu")
    ap.add_argument("--luc", help="mat-na: các giây cần xem, cách nhau dấu phẩy")
    ap.add_argument("--id", help="mau: id mẫu cần xem kỹ")
    ap.add_argument("--tu", type=float, help="khung: từ giây gốc")
    ap.add_argument("--den", type=float, help="khung: đến giây gốc")
    ap.add_argument("--fps", type=float, help="khung: số khung mỗi giây (tới 30); bỏ = vừa một bảng")
    ap.add_argument("--o-lon", action="store_true", help="khung: ô lớn hơn")
    a = ap.parse_args()
    if a.lenh == "ho-so":
        print(json.dumps(chuan_bi_ho_so(a.ho_so), ensure_ascii=False, indent=1)); return
    {"doc": lenh_doc, "tron": lenh_tron, "giao": lenh_giao, "hoc-chuan-bi": lenh_hoc_chuan_bi, "hoc-luu": lenh_hoc_luu, "mat-na": lenh_mat_na, "mau": lenh_mau_xem,
     "khung": lenh_khung, "broll": lenh_broll}[a.lenh](a)


if __name__ == "__main__":
    main()
