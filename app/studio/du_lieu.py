# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Lớp dữ liệu của Studio — chỉ ĐỌC não/kho của skill, và ghi những thứ của riêng Studio.

Studio là bàn làm việc, không phải bộ não: nó không sửa luật, không đánh dấu bước của phiếu,
không tự chọn hiệu ứng. Mọi quyết định dựng vẫn do Claude làm theo skill (nao/ + quy trình 12 bước).

Ghi được:
  - hồ sơ mới (gọi đúng `nao.py ho-so tao`, rồi điền màu/tên kênh người dùng chọn)
  - cau-hinh.json / phong-cach.md / anh-bia.md / nguon-hoc.json của hồ sơ khi người dùng sửa trên Studio
  - dữ liệu riêng của Studio (các việc + lời trò chuyện) ở STUDIO_DATA, ngoài thư mục skill
"""
import contextlib, glob, json, os, re, subprocess, sys, time, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
SCRIPTS = os.path.join(SKILL, "scripts")
NAO = os.path.join(SKILL, "nao")
CN = os.path.join(NAO, "ca-nhan")
KT = os.path.join(NAO, "kien-thuc")
PCM = os.path.join(NAO, "phong-cach-mau")
DATA = os.path.expanduser(os.environ.get("STUDIO_DATA") or "~/.studio-edit-video")
VIEC = os.path.join(DATA, "viec")
TAI_LEN = os.path.join(DATA, "tai-len")
KHOA = os.path.join(DATA, ".khoa")
WIN = os.name == "nt"
KHONG_CUA_SO = 0x08000000 if WIN else 0
for d in (VIEC, TAI_LEN):
    os.makedirs(d, exist_ok=True)


def py_skill():
    """Python của skill (.venv) nếu đã cài, không thì Python đang chạy Studio."""
    p = os.path.join(SKILL, ".venv", "Scripts", "python.exe") if WIN else os.path.join(SKILL, ".venv", "bin", "python")
    return p if os.path.isfile(p) else sys.executable


def env_con(**them):
    """1.2.21 (1a): môi trường cho MỌI tiến trình con của Studio — UTF-8, STUDIO_DATA, STUDIO_CPU_ONLY=1 khi cai_dat.tang_toc=cpu,
    STUDIO_FFMPEG_IM_TOI_DA (giây ffmpeg không tiến = treo, lõi đọc)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", STUDIO_DATA=DATA)
    cd = cai_dat()
    if cd.get("tang_toc") == "cpu":
        env["STUDIO_CPU_ONLY"] = "1"
    else:
        env.pop("STUDIO_CPU_ONLY", None)
    try:                                                        # R1: cai-dat.json sửa tay hỏng không được làm MỌI tiến trình con nổ
        im = int(float(cd.get("ffmpeg_im_toi_da_giay") or 300))
    except (TypeError, ValueError):
        im = 300
    env["STUDIO_FFMPEG_IM_TOI_DA"] = str(im if im > 0 else 300)
    dr = cd.get("don_rac") if isinstance(cd.get("don_rac"), dict) else {}
    try:
        giu = float(dr.get("giu_cache_ngay", 3))
    except (TypeError, ValueError):
        giu = 3
    env["STUDIO_GIU_CACHE_NGAY"] = str(int(giu) if giu == int(giu) else giu)   # lõi dọn cache dự án theo cùng ngưỡng
    env.update({k: str(v) for k, v in them.items() if v is not None})
    return env


def chay_script(ten, *args, toi_da=120, nhap=None):
    """Chạy một script của skill, trả (mã thoát, chữ in ra). nhap = chuỗi gửi vào stdin."""
    env = env_con()
    r = subprocess.run([py_skill(), os.path.join(SCRIPTS, ten), *args], capture_output=True, cwd=SKILL,
                       env=env, timeout=toi_da, creationflags=KHONG_CUA_SO,
                       input=(nhap.encode("utf-8") if nhap is not None else None))
    return r.returncode, (r.stdout + r.stderr).decode("utf-8", "replace").strip()


# ---------------------------------------------------------------- file
def doc_json(p, mac_dinh=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return mac_dinh


def ghi_json(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tam = f"{p}.{os.getpid()}.tmp"
    with open(tam, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=2)
    for _ in range(40):
        try:
            os.replace(tam, p)
            return
        except PermissionError:
            time.sleep(0.05)
    os.replace(tam, p)


def doc_chu(p, mac_dinh=""):
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return mac_dinh


@contextlib.contextmanager
def khoa(toi_da=60):
    """khoá tệp dùng chung cho viec/*.json (server + bao.py). 1.2.21: KHÔNG bỏ khoá sau 5 s nữa — chờ tới 60 s rồi lỗi rõ
    (bản cũ hai bên cùng ghi viec.json). Khoá bỏ quên > 10 s (tiến trình chết) thì tự gỡ."""
    han = time.time() + toi_da
    fd = None
    while True:
        try:
            fd = os.open(KHOA, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            with contextlib.suppress(OSError):
                if time.time() - os.path.getmtime(KHOA) > 10:
                    os.remove(KHOA)
                    continue
            if time.time() > han:
                raise RuntimeError(f"không lấy được khoá dữ liệu Studio sau {toi_da} s ({KHOA}) — tiến trình khác đang giữ")
            time.sleep(0.02)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
            with contextlib.suppress(OSError):
                os.remove(KHOA)


def khong_dau(s):
    s = unicodedata.normalize("NFD", (s or "").replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def slug(s, toi_da=40):
    return re.sub(r"[^a-z0-9]+", "-", khong_dau(s).lower()).strip("-")[:toi_da] or "ho-so"


# ---------------------------------------------------------------- hồ sơ (tầng cá nhân của não)
def ho_so_dang_dung():
    return doc_chu(os.path.join(CN, "HIEN-TAI")).strip()


def ds_ho_so():
    kq = []
    if not os.path.isdir(CN):
        return kq
    for ten in sorted(os.listdir(CN)):
        d = os.path.join(CN, ten)
        if ten.startswith(("_", ".")) or not os.path.isdir(d):
            continue
        c = doc_json(os.path.join(d, "cau-hinh.json"), {})
        pc = c.get("phong_cach") or {}
        bo3 = pc.get("bo_3_mau") or []
        kq.append({"ten": ten, "kenh": (c.get("kenh") or {}).get("ten") or ten,
                   "mau": (c.get("mau") or {}).get("nhan") or (bo3[2] if len(bo3) > 2 else "#FFD200"),
                   "bo": c.get("_tu_bo") or "", "tao_luc": os.path.getctime(d)})
    return kq


def bo_phong_cach():
    kq = []
    if os.path.isdir(PCM):
        for b in sorted(os.listdir(PCM)):
            d = os.path.join(PCM, b)
            if not os.path.isdir(d):
                continue
            c = doc_json(os.path.join(d, "cau-hinh.json"), {})
            md = doc_chu(os.path.join(d, "phong-cach.md"))
            hop = re.search(r"\*\*Hợp với\*\*:\s*([^.]+)", md)
            kq.append({"ma": b, "ten": c.get("_bo", b), "mau": (c.get("phong_cach") or {}).get("bo_3_mau") or [],
                       "hop": hop.group(1).strip() if hop else ""})
    return kq


def tao_ho_so(ten_kenh, mau, bo=None, ma=None, gu=None):
    ma = slug(ma or ten_kenh)
    if os.path.exists(os.path.join(CN, ma)):
        raise ValueError(f"đã có hồ sơ “{ma}”")
    args = ["ho-so", "tao", ma] + (["--tu", bo] if bo else [])
    rc, out = chay_script("nao.py", *args)
    if rc or not os.path.isdir(os.path.join(CN, ma)):
        raise RuntimeError(out or "không tạo được hồ sơ")
    p = os.path.join(CN, ma, "cau-hinh.json")
    c = doc_json(p, {})
    c.setdefault("kenh", {})["ten"] = ten_kenh
    if re.fullmatch(r"#[0-9A-Fa-f]{6}", mau or ""):
        c.setdefault("mau", {})["nhan"] = mau.upper()
        pc = c.setdefault("phong_cach", {})
        bo3 = list(pc.get("bo_3_mau") or ["#FFFFFF", "#101012", mau])
        while len(bo3) < 3:
            bo3.append(mau)
        bo3[2] = mau.upper()
        pc["bo_3_mau"] = bo3
    gu = {k: str(v or "").strip()[:300] for k, v in (gu or {}).items()}
    if gu.get("cam_giac"):
        c.setdefault("phong_cach", {})["cam_giac"] = gu["cam_giac"]
    ghi_json(p, c)
    if any(gu.values()):                                   # 1.2.19 (D4): gu người dùng ghi lúc tạo → phong-cach.md (AI đọc ở "Gu người dùng ghi")
        try:
            pm = os.path.join(CN, ma, "phong-cach.md")
            s = doc_chu(pm) or "# Phong cách riêng\n\n## Thích\n-\n## Cấm\n-\n"
            them = []
            if gu.get("ve"):
                them.append(f"- Kênh nói về: {gu['ve']}")
            if gu.get("cam_giac"):
                them.append(f"- Muốn người xem cảm thấy: {gu['cam_giac']}")
            if them:
                s = s.replace("## Thích\n-\n", "## Thích\n" + "\n".join(them) + "\n", 1) if "## Thích\n-\n" in s else s + "\n## Thích\n" + "\n".join(them) + "\n"
            if gu.get("cam"):
                s = s.replace("## Cấm\n-\n", f"## Cấm\n- {gu['cam']}\n", 1) if "## Cấm\n-\n" in s else s + f"\n## Cấm\n- {gu['cam']}\n"
            if gu.get("link"):
                s += f"\n## Kênh / video tham khảo (học ở thẻ Học từ video)\n- {gu['link']}\n"
            with open(pm, "w", encoding="utf-8") as f:
                f.write(s)
        except Exception:
            pass
    return ma


def chi_tiet_ho_so(ten):
    d = os.path.join(CN, ten)
    if not os.path.isdir(d) or ten.startswith("_"):
        raise KeyError(ten)
    c = doc_json(os.path.join(d, "cau-hinh.json"), {})
    gop_y = []
    for ln in doc_chu(os.path.join(d, "gop-y.md")).splitlines():
        if ln.startswith("| ") and not ln.startswith(("| Ngày", "|---")):
            o = [x.strip() for x in ln.strip().strip("|").split("|")]
            if any(o):
                gop_y.append((o + ["", "", "", ""])[:4])
    return {"ten": ten, "cau_hinh": c, "phong_cach": doc_chu(os.path.join(d, "phong-cach.md")),
            "anh_bia": doc_chu(os.path.join(d, "anh-bia.md")), "gop_y": gop_y,
            "nguon_hoc": doc_json(os.path.join(d, "nguon-hoc.json"), []),
            "lich_su": lich_su(ten), "bai_hoc": bai_hoc(ten), "dang_dung": ho_so_dang_dung() == ten,
            "thu_vien_hoc": thu_vien_hoc(ten)}


def thu_vien_hoc(ten):
    """1.2.15: THƯ VIỆN HỌC của hồ sơ (nao/ca-nhan/<hs>/hoc/*.json — bộ học tách khung → AI phân tích → hành động máy dựng lại được)"""
    d = os.path.join(CN, ten, "hoc")
    ra = []
    for f in sorted(glob.glob(os.path.join(d, "*.json")), key=os.path.getmtime, reverse=True):
        c = doc_json(f, {}) or {}
        if not c:
            continue
        ma = os.path.splitext(os.path.basename(f))[0]
        ra.append({"id": ma, "ten": c.get("ten") or ma, "nguon": c.get("nguon") or c.get("kenh_mau", ""), "luc": c.get("luc", ""),
                   "da_hoc": c.get("da_hoc") or [], "hanh_dong": c.get("hanh_dong_tom_tat") or [], "cau_truc": c.get("cau_truc") or [],
                   "hop": c.get("hop_noi_dung") or [], "can": c.get("can_tu_lieu") or [], "thieu": c.get("thieu") or [],
                   "bat": c.get("bat", True), "anh": bool(c.get("anh")) and os.path.exists(os.path.join(d, ma + ".jpg"))})
    return ra


def sua_bai_hoc(ten, ma, bat=None, xoa=False):
    """bật/tắt (AI có thấy bài này khi dựng video của hồ sơ không) hoặc xoá một bài trong thư viện học"""
    if not re.fullmatch(r"[\w.-]+", ma):
        raise ValueError("mã bài không hợp lệ")
    d = os.path.join(CN, ten, "hoc")
    p = os.path.join(d, ma + ".json")
    if not os.path.exists(p):
        raise KeyError(ma)
    if xoa:
        for f in (p, os.path.join(d, ma + ".jpg")):
            if os.path.exists(f):
                os.remove(f)
        return
    c = doc_json(p, {})
    c["bat"] = bool(bat)
    mt = os.path.getmtime(p)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=1)
    try:
        os.utime(p, (mt, mt))                     # 1.2.20: bật/tắt không làm bài cũ thành "mới nhất" (máy dựng chọn bài theo mtime)
    except OSError:
        pass


def _tron(cu, moi):
    if not isinstance(cu, dict) or not isinstance(moi, dict):
        return moi
    kq = dict(cu)
    for k, v in moi.items():
        if k.startswith("_"):
            continue
        kq[k] = _tron(cu.get(k), v)
    return kq


def sua_ho_so(ten, cau_hinh=None, phong_cach=None, anh_bia=None, nguon_hoc=None):
    d = os.path.join(CN, ten)
    if not os.path.isdir(d) or ten.startswith("_"):
        raise KeyError(ten)
    if cau_hinh is not None:
        p = os.path.join(d, "cau-hinh.json")
        ghi_json(p, _tron(doc_json(p, {}), cau_hinh))
    for ten_file, nd in (("phong-cach.md", phong_cach), ("anh-bia.md", anh_bia)):
        if nd is not None:
            with open(os.path.join(d, ten_file), "w", encoding="utf-8") as f:
                f.write(nd)
    if nguon_hoc is not None:
        ghi_json(os.path.join(d, "nguon-hoc.json"), nguon_hoc)


def lich_su(ten):
    """Các phiếu đã giao của hồ sơ này (skill lưu ở .phieu-cu/)."""
    d = os.path.join(SKILL, ".phieu-cu")
    kq = []
    if os.path.isdir(d):
        for f in sorted(os.listdir(d), reverse=True):
            p = doc_json(os.path.join(d, f), {})
            if p.get("ho_so") == ten:
                kq.append({"ten": p.get("ten"), "loai": p.get("loai"), "mo_luc": p.get("mo_luc"),
                           "giao": (p.get("buoc", {}).get("11") or {}).get("dau_ra", ""),
                           "gop_y": (p.get("buoc", {}).get("12") or {}).get("dau_ra", ""),
                           "so_buoc": len(p.get("buoc", {}))})
    return kq[:60]


def _dau(p):
    s = doc_chu(p)
    m = re.match(r"---\r?\n(.*?)\r?\n---", s, re.S)
    d = {}
    if m:
        for ln in m.group(1).splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                d[k.strip()] = v.strip()
    tieu = re.search(r"^# (.+)$", s, re.M)
    d["_tieu"] = tieu.group(1).strip() if tieu else ""
    return d


def bai_hoc(ho_so=None):
    """Bài học trong tầng kiến thức. ho_so → chỉ bài học được học cho hồ sơ đó (khoá `ho_so:` ở phần đầu)."""
    kq = []
    for lop in ("cua-toi", "nguoi-ban"):
        d = os.path.join(KT, lop)
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d), reverse=True):
            if not f.endswith(".md") or not f[:1].isdigit():
                continue
            m = _dau(os.path.join(d, f))
            if ho_so and m.get("ho_so") != ho_so:
                continue
            kq.append({"file": f"{lop}/{f}", "lop": lop, "tieu": m["_tieu"], "nguon": m.get("nguon", ""),
                       "ngay": m.get("ngay", ""), "the": m.get("the", ""), "tin_cay": m.get("do_tin_cay", "")})
    return kq


# ---------------------------------------------------------------- phiếu quy trình (chỉ đọc)
PHIEU_VIEC = os.path.join(DATA, "phieu")      # mỗi việc trên Studio một phiếu riêng (QUY_TRINH_PHIEU)


def p_phieu(vid):
    return os.path.join(PHIEU_VIEC, f"{vid}.json")


def phieu(vid=None):
    """Phiếu của việc đang xem; việc chưa mở phiếu → phiếu chung (khi người dùng làm qua chat)."""
    if vid and re.fullmatch(r"[a-z0-9-]{4,60}", vid):
        p = doc_json(p_phieu(vid))
        if p:
            return p
        # việc tạo trước khi có phiếu riêng: dùng phiếu chung nếu cùng hồ sơ và mở sau khi việc bắt đầu
        v = doc_json(_p_viec(vid))
        g = doc_json(os.path.join(SKILL, ".phieu-hien-tai.json"))
        if v and g and g.get("ho_so") == v.get("ho_so"):
            try:
                mo = time.mktime(time.strptime(g.get("mo_luc", ""), "%Y-%m-%d %H:%M"))
            except ValueError:
                mo = 0
            if mo >= v.get("tao_luc", 0) - 60:
                return g
        return None
    return doc_json(os.path.join(SKILL, ".phieu-hien-tai.json"))


def ds_phieu(vid):
    """Mọi phiếu của một việc (một việc có thể dựng nhiều video — mỗi video một phiếu): phiếu đã giao trong
    .phieu-cu có `viec` = vid, cộng phiếu đang mở của việc. Cũ trước, mới sau."""
    if not vid or not re.fullmatch(r"[a-z0-9-]{4,60}", vid):
        return []
    kq = {}
    d = os.path.join(SKILL, ".phieu-cu")
    if os.path.isdir(d):
        for f in os.listdir(d):
            p = doc_json(os.path.join(d, f))
            if p and p.get("viec") == vid:
                kq[(p.get("ten"), p.get("mo_luc"))] = p
    hien = phieu(vid)
    if hien:
        kq[(hien.get("ten"), hien.get("mo_luc"))] = hien      # bản đang mở mới hơn bản lưu (có thể đã thêm bước 12)
    return sorted(kq.values(), key=lambda p: p.get("mo_luc", ""))


def luu_tru_ho_so(ten):
    """Cất hồ sơ khỏi danh sách (không xoá): chuyển vào nao/ca-nhan/.luu-tru/ — lấy lại được bằng tay."""
    d = os.path.join(CN, ten)
    if not os.path.isdir(d) or ten.startswith(("_", ".")):
        raise KeyError(ten)
    dich = os.path.join(CN, ".luu-tru", f"{ten}-{time.strftime('%Y%m%d-%H%M%S')}")
    os.makedirs(os.path.dirname(dich), exist_ok=True)
    os.replace(d, dich)
    if ho_so_dang_dung() == ten:
        with contextlib.suppress(OSError):
            os.remove(os.path.join(CN, "HIEN-TAI"))
    for v in ds_viec(ten):
        with contextlib.suppress(OSError):
            os.replace(_p_viec(v["id"]), _p_viec(v["id"]) + ".luu-tru")
    return dich


def xoa_ho_so(ten):
    """1.2.15: XOÁ HẲN hồ sơ (gu, thương hiệu, thư viện học, góp ý) + các đoạn chat của nó. Video đã giao và thư mục dự án GIỮ NGUYÊN."""
    d = os.path.join(CN, ten)
    if not os.path.isdir(d) or ten.startswith(("_", ".")) or not re.fullmatch(r"[\w-]+", ten):
        raise KeyError(ten)
    import shutil as _sh
    for v in ds_viec(ten):
        with contextlib.suppress(OSError):
            os.remove(_p_viec(v["id"]))
    _sh.rmtree(d)
    if ho_so_dang_dung() == ten:
        with contextlib.suppress(OSError):
            os.remove(os.path.join(CN, "HIEN-TAI"))
    return True


def ten_buoc():
    try:
        sys.path.insert(0, SCRIPTS)
        import quy_trinh
        return {str(k): v for k, v in quy_trinh.BUOC.items()}
    except Exception:
        return {}


# ---------------------------------------------------------------- Studio 2.0: phiếu 30 bước + phong cách nhanh
V2 = os.path.join(SKILL, "v2")
PHIEU2 = os.path.join(DATA, "phieu2")


def p_phieu2(vid):
    """con trỏ phiếu 2.0 của một việc (file chứa thư mục dự án đang mở) — truyền cho Claude qua QUY_TRINH_PHIEU2"""
    os.makedirs(PHIEU2, exist_ok=True)
    return os.path.join(PHIEU2, f"{vid}.txt")


def buoc2():
    try:
        if V2 not in sys.path:
            sys.path.insert(0, V2)
        import buoc
        return {"buoc": [{"id": b[0], "gd": b[1], "ten": b[2], "ai": b[3], "ra": b[4]} for b in buoc.BUOC],
                "giai_doan": buoc.GIAI_DOAN, "cong": {str(k): {"sau": v[0], "ten": v[1], "ngan": getattr(buoc, "CONG_NGAN", {}).get(k, "")} for k, v in buoc.CONG.items()},
                "phan": [{"ten": t, "mo_ta": m, "buoc": ds} for t, m, ds in getattr(buoc, "PHAN", [])]}
    except Exception as e:
        return {"loi": str(e)}


def ds_phieu2(vid):
    """mọi phiếu 2.0 của việc (mỗi video một dự án), cũ trước mới sau"""
    if not vid or not re.fullmatch(r"[a-z0-9-]{4,60}", vid):
        return []
    p = os.path.join(PHIEU2, f"{vid}.txt.ds")
    try:
        ds = [l.strip() for l in open(p, encoding="utf-8") if l.strip()]
    except OSError:
        return []
    kq, da = [], set()
    for d in ds:
        if d in da:
            continue
        da.add(d)
        ph = doc_json(os.path.join(d, "phieu.json"))
        if ph:
            kh = os.path.join(d, "ke-hoach.png")
            ph["_ke_hoach_png"] = kh if os.path.exists(kh) else None
            ph["_may"] = (doc_json(os.path.join(d, "doc", "nguon.json")) or {}).get("may") or None   # 1.2.21: lựa chọn máy (A1 ghi) → tổng quan việc
            try:
                ph["_eta"] = uoc_thoi_gian(d, ph)
            except Exception:
                ph["_eta"] = None
            kq.append(ph)
    return kq


# ---------------------------------------------------------------- 1.3: thời gian 3 phần + ước lượng còn lại (học từ máy này)
P_THOI_GIAN = os.path.join(DATA, "thoi-gian.json")
_MAC_DINH = {"doc": 1.6, "tu_duy": 420.0, "dung": 3.2}     # đọc, dựng: giây máy / giây video · tư duy: giây (AI nghĩ)
_MOC = {"doc": ("0.1", "2.1"), "tu_duy": ("2.1", "3.6"), "dung": ("3.6", "7.2")}


def _luc(ph, b):
    x = (ph.get("buoc") or {}).get(b) or {}
    try:
        return time.mktime(time.strptime(x.get("luc", "")[:19], "%Y-%m-%d %H:%M:%S"))
    except (ValueError, TypeError):
        return None


def _dai_video(d):
    for f, k in (("23-kich-ban.json", "dur"), ("23-kich-ban.nhap.json", "dur")):
        v = (doc_json(os.path.join(d, f)) or {}).get(k)
        if v:
            return float(v)
    t = ((doc_json(os.path.join(d, "14-nguyen-lieu.json")) or {}).get("tom_tat") or {}).get("tong_giay")
    if t:
        return float(t)
    return 60.0


def _dai_nguon(d):
    """tổng giây video THÔ khách thả vào — bước Đọc tốn thời gian theo con số này (24 clip ≠ 1 clip)"""
    t = ((doc_json(os.path.join(d, "14-nguyen-lieu.json")) or {}).get("tom_tat") or {}).get("tong_giay")
    return float(t) if t else _dai_video(d)


def _dai_ra(d):
    """giây video THÀNH PHẨM — bước Dựng tốn thời gian theo con số này (đầu ra 30 s thì dựng 30 s, dù thô dài 40 phút)"""
    for f in ("23-kich-ban.json", "23-kich-ban.nhap.json"):
        v = (doc_json(os.path.join(d, f)) or {}).get("dur")
        if v:
            return float(v)
    return min(_dai_nguon(d), 60.0)


def _hoc(d, ph, tg):
    """phiếu đã đóng → cập nhật tốc độ thật của máy này (trung bình trượt), mỗi dự án học một lần"""
    if d in tg.setdefault("da_hoc", []):
        return False
    # 1.2.13: Đọc chia theo giây THÔ, Dựng chia theo giây THÀNH PHẨM (bản cũ chia cả hai theo thành phẩm rồi nhân với
    # giây thô → 24 clip ra "còn 963 phút"). Tốc độ Đọc học theo khoá mới "doc_n"; khoá "doc" cũ bị bỏ vì đo sai đơn vị.
    dai = {"doc": _dai_nguon(d), "dung": _dai_ra(d)}
    for k, (a, b) in _MOC.items():
        ta, tb = _luc(ph, a), _luc(ph, b)
        if ta and tb and tb > ta:
            v = (tb - ta) if k == "tu_duy" else (tb - ta) / max(10.0, dai[k])
            # 1.2.13: phiếu mở lâu (chờ khách góp ý, sửa nhiều vòng, máy tắt qua đêm) KHÔNG phải tốc độ máy/AI → bỏ, không học
            if (k == "tu_duy" and v > 3600) or (k != "tu_duy" and v > 40):
                continue
            kk = "doc_n" if k == "doc" else k
            cu = tg.get(kk, _MAC_DINH[k])
            tg[kk] = round(cu * 0.6 + v * 0.4, 3)
    tg["da_hoc"] = (tg["da_hoc"] + [d])[-40:]
    return True


def uoc_thoi_gian(d, ph):
    """→ {phan: 0|1|2|3, con_lai: giây ước tính còn lại cả việc, con_phan: giây còn của phần hiện tại, da: giây đã chạy}"""
    if V2 not in sys.path:
        sys.path.insert(0, V2)
    import buoc as _B
    tg = doc_json(P_THOI_GIAN) or {}
    if ph.get("dong"):
        if _hoc(d, ph, tg):
            try:
                with open(P_THOI_GIAN, "w", encoding="utf-8") as f:
                    json.dump(tg, f, ensure_ascii=False)
            except OSError:
                pass
        return {"phan": 3, "con_lai": 0, "con_phan": 0}
    du = {"doc": min(tg.get("doc_n", _MAC_DINH["doc"]), 6.0) * _dai_nguon(d), "tu_duy": min(tg.get("tu_duy", _MAC_DINH["tu_duy"]), 1800.0),   # 1.2.13: trần 30 phút
          "dung": min(tg.get("dung", _MAC_DINH["dung"]), 30.0) * _dai_ra(d)}
    xong = ph.get("buoc") or {}
    phan = next((i for i, (_, _, ds) in enumerate(_B.PHAN) if not all(b in xong for b in ds)), 3)
    khoa = ["doc", "tu_duy", "dung"]
    if phan >= 3:
        return {"phan": 3, "con_lai": 0, "con_phan": 0}
    bat = _luc(ph, _MOC[khoa[phan]][0]) or _luc(ph, "0.1") or time.time()
    da = max(0.0, time.time() - bat)
    con_phan = max(30.0, du[khoa[phan]] - da)
    con = con_phan + sum(du[k] for k in khoa[phan + 1:])
    return {"phan": phan, "con_lai": round(con), "con_phan": round(con_phan), "da": round(da)}


def phong_cach_nhanh():
    """1.3: 20 phong cách nhanh của lõi mới (v3/phong_cach — mỗi gói là một Style Spec)"""
    out = []
    thu = os.path.join(SKILL, "v3", "phong_cach")
    for f in sorted(glob.glob(os.path.join(thu, "*.json"))):
        g = doc_json(f)
        if not g or not g.get("spec"):
            continue
        anh = os.path.join(thu, g.get("minh_hoa") or f"minh-hoa/{g.get('id')}.jpg")
        pal = (g.get("spec") or {}).get("palette") or {}
        out.append({"id": g.get("id"), "ten": g.get("ten"), "lenh": g.get("lenh", []), "mo_ta": g.get("mo_ta", ""),
                    "hop_voi": g.get("hop_voi", []), "grade": g.get("grade"), "anh": anh if os.path.exists(anh) else None,
                    "mau": {k: pal.get(k) for k in ("nhan", "sang", "toi") if pal.get(k)}})
    return out


# ---------------------------------------------------------------- việc + trò chuyện (dữ liệu riêng của Studio)
def _p_viec(vid):
    if not re.fullmatch(r"[a-z0-9-]{4,60}", vid or ""):
        raise KeyError(vid)
    return os.path.join(VIEC, vid + ".json")


def tao_viec(ho_so, ten="Việc mới", loai="dung"):
    vid = time.strftime("%Y%m%d-%H%M%S-") + os.urandom(2).hex()
    v = {"id": vid, "ho_so": ho_so, "ten": ten, "loai": loai, "tao_luc": time.time(),
         "cap_nhat": time.time(), "phien": None, "tin": []}
    with khoa():
        ghi_json(_p_viec(vid), v)
    return v


def doc_viec(vid):
    v = doc_json(_p_viec(vid))
    if not v:
        raise KeyError(vid)
    return v


def sua_viec(vid, fn):
    with khoa():
        v = doc_viec(vid)
        kq = fn(v)
        v["cap_nhat"] = time.time()
        ghi_json(_p_viec(vid), v)
        return kq


def them_tin(vid, vai, noi_dung="", **kv):
    """vai: nguoi_dung | claude | cong_cu | hoi | video | loi | he_thong"""
    def f(v):
        tin = dict(kv, vai=vai, noi_dung=noi_dung, luc=time.time())
        v["tin"].append(tin)
        if vai == "hoi":
            v["cho_tra_loi"] = True             # Claude đang hỏi → Studio nhắc người dùng trả lời
        elif vai == "nguoi_dung":
            v["cho_tra_loi"] = False
        v["tin"] = v["tin"][-1500:]
        if vai == "nguoi_dung" and v["ten"] in ("Việc mới", "") and noi_dung:
            v["ten"] = re.sub(r"\s+", " ", noi_dung).strip()[:60]
    try:
        sua_viec(vid, f)
    except KeyError:
        pass


_DS_VIEC_CACHE = {}


def ds_viec(ho_so=None):
    """1.2.19 (F7): tóm tắt từng việc được nhớ theo (mtime, cỡ) tệp — UI hỏi mỗi 1,2 s không còn đọc + parse mọi tệp việc"""
    kq = []
    for f in os.listdir(VIEC):
        if not f.endswith(".json"):
            continue
        p = os.path.join(VIEC, f)
        try:
            st = os.stat(p); dau = (st.st_mtime, st.st_size)
        except OSError:
            continue
        c = _DS_VIEC_CACHE.get(p)
        if c and c[0] == dau:
            tom = c[1]
        else:
            v = doc_json(p)
            if not v:
                continue
            cuoi = next((t for t in reversed(v["tin"]) if t["vai"] in ("claude", "nguoi_dung")), None)
            tom = {"id": v["id"], "ho_so": v["ho_so"], "ten": v["ten"], "loai": v.get("loai", "dung"),
                   "cap_nhat": v["cap_nhat"], "tao_luc": v["tao_luc"], "so_tin": len(v["tin"]), "cho": bool(v.get("cho_tra_loi")),
                   "cuoi": (cuoi or {}).get("noi_dung", "")[:120]}
            _DS_VIEC_CACHE[p] = (dau, tom)
        if ho_so and tom.get("ho_so") != ho_so:
            continue
        kq.append(dict(tom))
    return sorted(kq, key=lambda x: -x["cap_nhat"])


def xoa_viec(vid):
    with khoa():
        try:
            os.remove(_p_viec(vid))
        except FileNotFoundError:
            raise KeyError(vid)                 # R1: việc không có → route trả 404, không nổ 500 (bản cũ cũng vậy)


def dau_moc_viec():
    """{id: cap_nhat} — để giao diện biết việc nào vừa đổi mà không phải tải lại tất cả."""
    kq = {}
    for f in os.listdir(VIEC):
        if f.endswith(".json"):
            with contextlib.suppress(OSError):
                kq[f[:-5]] = os.path.getmtime(os.path.join(VIEC, f))
    return kq


# ---------------------------------------------------------------- hệ thống: phiên bản, bản quyền, cập nhật
_CACHE = {}


def _nho(khoa_, giay, fn):
    o = _CACHE.get(khoa_)
    if o and time.time() - o[0] < giay:
        return o[1]
    kq = fn()
    _CACHE[khoa_] = (time.time(), kq)
    return kq


def phien_ban():
    return doc_chu(os.path.join(SKILL, "VERSION")).strip() or "?"


def ban_quyen(lam_moi=False):
    def f():
        if os.path.exists(os.path.join(SKILL, "NGUOI-BAN")):
            return {"hop_le": True, "loai": "ok", "chu": "máy người bán"}
        try:
            rc, out = chay_script("ban_quyen.py", "gac", toi_da=30)
            j = json.loads(out.strip().splitlines()[-1])
            return {"hop_le": bool(j.get("ok")), "loai": j.get("loai", ""), "chu": j.get("tb", "")}
        except Exception as e:
            return {"hop_le": False, "loai": "loi", "chu": f"không kiểm được: {e}"}
    if lam_moi:
        _CACHE.pop("bq", None)
    return _nho("bq", 300, f)


def gac():
    """Cổng cho server gọi trước khi cho chat/chạy Claude. Máy người bán luôn mở."""
    bq = ban_quyen()
    return {"ok": bq["hop_le"], "loai": bq.get("loai", ""), "chu": bq.get("chu", "")}


_TEP_NHIP = os.path.join(DATA, ".nhip-cuoi")
_NHIP_DANG = {"chay": False}


def nhip_dinh_ky(ep=False):
    """Gói tháng gọi về máy chủ ~mỗi giờ để gia hạn thẻ ngắn (ep=True: gọi ngay và CHỜ, cho nút 'đã gia hạn').
    1.2.21: không ép → chạy ở LUỒNG NỀN, không bao giờ chặn request /api/tong-quan (bản cũ khựng giao diện tới 12 s)."""
    if os.path.exists(os.path.join(SKILL, "NGUOI-BAN")):
        return
    try:
        t = float(open(_TEP_NHIP).read()) if os.path.exists(_TEP_NHIP) else 0
    except Exception:
        t = 0
    if not ep and time.time() - t < 3600:
        return

    def lam():
        try:
            open(_TEP_NHIP, "w").write(str(time.time()))
            chay_script("ban_quyen.py", "nhip", toi_da=12)
        except Exception:
            pass
        finally:
            _CACHE.pop("bq", None)      # trạng thái bản quyền đọc lại sau khi nhịp
            _NHIP_DANG["chay"] = False
    if ep:
        _NHIP_DANG["chay"] = True
        lam()
        return
    if _NHIP_DANG["chay"]:
        return
    _NHIP_DANG["chay"] = True
    import threading
    threading.Thread(target=lam, daemon=True).start()


def da_cai():
    # Studio thường chạy bằng chính Python của skill (.venv) — chỉ cần .venv có thật là đã cài
    p = os.path.join(SKILL, ".venv", "Scripts", "python.exe") if WIN else os.path.join(SKILL, ".venv", "bin", "python")
    return os.path.isfile(p)


def he_thong():
    nhip_dinh_ky()      # gói tháng: tự gia hạn thẻ theo giờ (có throttle, không chặn UI quá lâu)
    return {"phien_ban": phien_ban(), "ban_quyen": ban_quyen(), "da_cai": da_cai(),
            "cap_nhat": _CACHE.get("cn", (0, None))[1]}


# ---------------------------------------------------------------- cài đặt của khách (cai-dat.json — kế hoạch 1.2.21 mục 1a)
CAI_DAT = os.path.join(DATA, "cai-dat.json")
MAC_DINH_CAI_DAT = {
    "model": "claude-opus-5-5", "model_nhanh": "", "effort": "",
    "song_song": "",                    # "" = tự động theo máy · "N" bất kỳ ≥ 1 (không còn trần 4)
    "tang_toc": "auto",                 # auto | cpu → mọi tiến trình con nhận STUDIO_CPU_ONLY=1
    "don_rac": {"tu_dong": True, "o_trong_toi_thieu_gb": 10, "giu_cache_ngay": 3},
    "ffmpeg_im_toi_da_giay": 300,       # ffmpeg không tiến trong N giây = treo (lõi đọc qua env STUDIO_FFMPEG_IM_TOI_DA)
    "toi_da_buoc": 0,                   # 0 = không giới hạn (chỉ cấu hình, không UI)
    "cong_kho": 4789,                   # máy chủ kho v3 (server_thu.py) — server + app.js cùng đọc
    "cap_nhat_tuy_chon": False,         # True = bản mới không bắt buộc
    "cn_hong": 0, "cn_hoan": 0,         # cập nhật tự động hỏng mấy lần · hoãn ép tới (epoch) — lưu đĩa, mở lại không quên
}
# tên hiển thị của vài model quen; model KHÁC vẫn nhập được dạng chuỗi tự do (^[a-z0-9.\-]+$)
TEN_MODEL = {"claude-opus-5-5": "Opus 5.5", "claude-sonnet-5-5": "Sonnet 5.5", "claude-fable-5-1": "Fable 5.1",
             "claude-haiku-4-5-20251001": "Haiku 4.5"}
MODEL_HOP_LE = re.compile(r"^[a-z0-9.\-]{1,80}$")


def cai_dat():
    d = json.loads(json.dumps(MAC_DINH_CAI_DAT))
    cu = doc_json(CAI_DAT) or {}
    for k, v in cu.items():
        if k == "don_rac":
            if isinstance(v, dict):                 # R1: tệp cũ ghi don_rac không phải dict → giữ mặc định, không làm don_rac.cau_hinh() nổ
                d["don_rac"].update(v)
        else:
            d[k] = v
    return d


def kiem_cai_dat(b):
    """giá trị người dùng gửi lên /api/cai-dat → dict đã kiểm; sai → ValueError (route trả 400). Chỉ nhận khoá có trong MAC_DINH."""
    moi = {}
    if "model" in b:
        m = str(b.get("model") or "").strip()
        if m and not MODEL_HOP_LE.match(m):
            raise ValueError("model không hợp lệ (chỉ a-z, 0-9, dấu chấm, gạch ngang)")
        moi["model"] = m
    if "model_nhanh" in b:
        m = str(b.get("model_nhanh") or "").strip()
        if m and not MODEL_HOP_LE.match(m):
            raise ValueError("model_nhanh không hợp lệ")
        moi["model_nhanh"] = m
    if "effort" in b:
        e = str(b.get("effort") or "").strip()
        if e and e not in ("low", "medium", "high", "max"):
            raise ValueError("effort phải là low/medium/high/max hoặc để trống")
        moi["effort"] = e
    if "song_song" in b:
        ss = str(b.get("song_song") or "").strip()
        if ss and not (ss.isdigit() and int(ss) >= 1):
            raise ValueError("số việc dựng cùng lúc phải là số nguyên ≥ 1 hoặc để trống (tự động)")
        moi["song_song"] = str(int(ss)) if ss else ""
    if "tang_toc" in b:
        t = str(b.get("tang_toc") or "auto").strip()
        if t not in ("auto", "cpu"):
            raise ValueError("tang_toc phải là auto hoặc cpu")
        moi["tang_toc"] = t
    if "don_rac" in b:
        dr = b.get("don_rac")
        if not isinstance(dr, dict):
            raise ValueError("don_rac phải là một đối tượng")
        ra = dict(cai_dat()["don_rac"])
        if "tu_dong" in dr:
            ra["tu_dong"] = bool(dr["tu_dong"])
        for k, lo, cao in (("o_trong_toi_thieu_gb", 0, 10000), ("giu_cache_ngay", 0, 3650)):
            if k in dr:
                try:
                    v = float(dr[k])
                except (TypeError, ValueError):
                    raise ValueError(f"don_rac.{k} phải là số")
                if not (lo <= v <= cao):
                    raise ValueError(f"don_rac.{k} phải trong {lo}–{cao}")
                ra[k] = int(v) if v == int(v) else v
        moi["don_rac"] = ra
    for k, lo, cao in (("ffmpeg_im_toi_da_giay", 10, 86400), ("toi_da_buoc", 0, 100000), ("cong_kho", 1024, 65535)):
        if k in b:
            try:
                v = int(b[k])
            except (TypeError, ValueError):
                raise ValueError(f"{k} phải là số nguyên")
            if not (lo <= v <= cao):
                raise ValueError(f"{k} phải trong {lo}–{cao}")
            moi[k] = v
    if "cap_nhat_tuy_chon" in b:
        moi["cap_nhat_tuy_chon"] = bool(b["cap_nhat_tuy_chon"])
    return moi


def luu_cai_dat(moi):
    """ghi cai-dat.json (đọc-sửa-ghi, .tmp rồi os.replace). Khoá lạ bị bỏ. R1: đọc-sửa-ghi trong khoá dữ liệu (hai request UI gần nhau không mất khoá)."""
    with khoa():
        d = cai_dat()
        d.update({k: v for k, v in moi.items() if k in MAC_DINH_CAI_DAT})
        ghi_json(CAI_DAT, d)
    return d


def ghi_luot(vid, m):
    """1.2.21: bản ghi `result` của Claude Code → 1 lượt chỉ còn thời gian / số bước / lỗi (bỏ đo token + USD theo mục 1a)"""
    luot = {"luc": time.time(), "giay": round((m.get("duration_ms") or 0) / 1000, 1), "so_buoc": m.get("num_turns"), "loi": bool(m.get("is_error"))}

    def f(x):
        x.setdefault("luot", []).append(luot)
        x["luot"] = x["luot"][-200:]
        t = x.setdefault("tong", {"so_luot": 0, "giay": 0.0})
        for k in [k for k in list(t) if k not in ("so_luot", "giay")]:
            t.pop(k, None)                              # dọn số token/USD của bản cũ
        t["so_luot"] = t.get("so_luot", 0) + 1
        t["giay"] = round(t.get("giay", 0) + luot["giay"], 1)
    try:
        sua_viec(vid, f)
    except Exception:
        pass
