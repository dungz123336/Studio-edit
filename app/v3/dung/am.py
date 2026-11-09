# -*- coding: utf-8 -*-
"""Âm: giọng = concat các đoạn cat (atrim/asetpts/concat) đưa về ĐÚNG mức giong_lufs (đo ebur128, cache) · nhạc: aloop, afade,
đặt THẤP HƠN GIỌNG `db` LU (đo LUFS tệp nhạc, cache theo tệp) rồi né giọng (sidechaincompress) · sfx: đo LUFS/đỉnh từng tệp,
đặt tương đối so với giọng · amix normalize=0 · alimiter TP −1.5 dB (KHÔNG loudnorm một lượt — loudnorm 1 lượt chạy kiểu
động, đẩy nhạc trồi lên trong khoảng nghỉ của lời).
bo_loc_am(ke_hoach, cat, nguon, kho, bat_dau_input=0, du_an=None, tong_dai=None) → (inputs, filter, map)
Mức nhạc theo nghĩa: `am.nhac.muc` nhe|vua|noi = −24|−18|−12 LU dưới giọng; `db` (âm) = LU dưới giọng (ghi đè muc)."""
import os, re, json, subprocess, hashlib

try:
    import chung
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import chung

PHIEN = 6                       # 1.2.21: mọi mặc định thẩm mỹ đọc từ quyet-dinh.json của kênh — đổi số này khi đổi cách trộn (cache am-tp theo đó)
# 1.2.21 (1c): KHÔNG còn số thẩm mỹ của máy. Mọi mức (nhạc dưới giọng, sfx, fade, LUFS, TP, sidechain) đọc từ
# ke_hoach["quyet_dinh"]["am"] (AI viết cho kênh); công thức (ke_hoach["am"]) ghi đè từng trường; thiếu cả hai → ThieuTruong trả AI.
# Giữ: phần ĐO (ebur128/astats) và CHẶN VẬT LÝ (tiếng không vượt giọng, kẹp biên số).
MUC_NHAC = {"nhe": -24.0, "vua": -18.0, "noi": -12.0, "khong": None}
SIDECHAIN_KY_THUAT = {"threshold": 0.05, "ratio": 4, "attack": 25, "release": 400}   # tham số bộ nén (kỹ thuật) khi AI/kênh không ghi am.sidechain
_DO_CACHE = {}
TRUONG_AM = {   # đường trong quyet_dinh.am → gợi ý cho AI (hợp đồng hop_dong.py: {"duong","ma":"thieu_truong","goi_y"})
    "giong_lufs": "mức giọng đích LUFS tích phân (−30…−8), ví dụ -16",
    "dinh_dbtp": "đỉnh thật tối đa dBTP (−6…−0.5), ví dụ -2.0",
    "nhac.db": "nhạc thấp hơn giọng bao nhiêu LU (−40…−4), ví dụ -22",
    "nhac.vao": "giây nhạc mờ vào (0 = không), ví dụ 1.0",
    "nhac.ra": "giây nhạc mờ ra ở cuối (0 = không), ví dụ 2.0",
    "nhac.ne_giong": "true/false — nhạc tự lùi khi có giọng (sidechain)",
    "sidechain": "{threshold, ratio, attack, release} của sidechaincompress, ví dụ {\"threshold\":0.05,\"ratio\":4,\"attack\":25,\"release\":400}",
    "sfx.db": "tiếng động so với giọng (LU, −40…−3), ví dụ -8",
}


def _lay(am, qd, duong):
    """giá trị theo thứ tự: công thức (ke_hoach.am) → quyet_dinh.am; không có → None. duong dạng "nhac.db" / "giong_lufs"."""
    for goc in (am, qd):
        d = goc
        for k in duong.split("."):
            d = d.get(k) if isinstance(d, dict) else None
            if d is None:
                break
        if d is not None:
            return d
    return None


def _can(am, qd, duong, thieu, kieu=float):
    v = _lay(am, qd, duong)
    if v is None:
        thieu.append({"duong": "quyet_dinh.am." + duong, "ma": "thieu_truong", "goi_y": TRUONG_AM.get(duong, "")})
        return None
    try:
        return kieu(v) if kieu is not None else v
    except (TypeError, ValueError):
        thieu.append({"duong": "quyet_dinh.am." + duong, "ma": "sai_kieu", "goi_y": TRUONG_AM.get(duong, "")})
        return None


def _ebur128(args_input, filter_, timeout=120, ngan_han=False):
    """chạy ffmpeg -f null với ebur128 → (lufs tích hợp | None, đỉnh thật dBTP | None[, S_max]) — ngan_han=True trả thêm mức
    NGẮN HẠN lớn nhất (LUFS-S 3 s, đo mỗi 100 ms): tiếng động ngắn có đỉnh cao mà LUFS tích phân thấp (đuôi lặng) → đặt theo tích phân
    sẽ to hơn giọng đúng lúc nổ — chính là tiếng "giật mình"."""
    cmd = [chung.duong("ffmpeg"), "-v", "info", "-nostats", "-nostdin", *args_input,
           "-filter_complex", filter_ + "ebur128=peak=true[o]", "-map", "[o]", "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=(0x08000000 if os.name == "nt" else 0))
    except Exception:
        return (None, None, None) if ngan_han else (None, None)
    txt = r.stderr.decode("utf-8", "replace")
    tom = txt[txt.rfind("Summary:"):] if "Summary:" in txt else txt
    m = re.search(r"I:\s*(-?[\d.]+|-inf)\s*LUFS", tom)
    pk = re.search(r"Peak:\s*(-?[\d.]+|-inf)\s*dBFS", tom)
    lufs = float(m.group(1)) if m and m.group(1) != "-inf" else None
    peak = float(pk.group(1)) if pk and pk.group(1) != "-inf" else None
    if not ngan_han:
        return lufs, peak
    return lufs, peak, _rms_dinh(args_input, filter_, timeout)


def _rms_dinh(args_input, filter_, timeout=120):
    """RMS ĐỈNH cửa sổ 50 ms (dBFS, astats) — mức "nổ" thật của tiếng ngắn (ebur128 M/S cần ≥ 0,4–3 s nên không đo được tiếng < 0,4 s)"""
    cmd = [chung.duong("ffmpeg"), "-v", "info", "-nostats", "-nostdin", *args_input,
           "-filter_complex", filter_ + "astats=metadata=0:measure_perchannel=none:measure_overall=RMS_peak[o]", "-map", "[o]", "-f", "null", "-"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, creationflags=(0x08000000 if os.name == "nt" else 0))
    except Exception:
        return None
    txt = r.stderr.decode("utf-8", "replace")
    m = re.findall(r"RMS peak dB:\s*(-?[\d.]+|-inf)", txt)
    vals = [float(x) for x in m if x != "-inf"]
    return max(vals) if vals else None


def _do_tep(p, giay=40.0):
    """LUFS + đỉnh của một tệp âm (nhạc: 40 s đầu; sfx: cả tệp) — cache kho_chi_muc/do-am.json theo đường dẫn + cỡ + mtime"""
    try:
        st = os.stat(p); khoa = f"{os.path.abspath(p)}|{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        return None, None, None
    pc = os.path.join(chung.duong("kho_chi_muc"), "do-am.json")
    if not _DO_CACHE:
        _DO_CACHE.update(chung.doc_json(pc, {}) or {})
    khoa += "|v4"                                          # 1.2.20: thêm mức ngắn hạn → đo lại
    if khoa in _DO_CACHE:
        v = _DO_CACHE[khoa]; return v.get("lufs"), v.get("peak"), v.get("s_max")
    lufs, peak, s_max = _ebur128(["-t", f"{giay:.1f}", "-i", p], "[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,", ngan_han=True)
    _DO_CACHE[khoa] = {"lufs": lufs, "peak": peak, "s_max": s_max}
    try:
        chung.ghi_json(pc, _DO_CACHE)
    except Exception:
        pass
    return lufs, peak, s_max


def _do_giong(du_an, inputs, fl_giong):
    """LUFS giọng sau cat (đo một lần, cache du_an/cache/am-do.json theo băm cat+nguồn)"""
    return _do_giong_du(du_an, inputs, fl_giong)[0]


def _do_giong_du(du_an, inputs, fl_giong):
    """→ (LUFS tích phân, đỉnh thật dBTP, S_max) của giọng sau cat — cache theo băm cat+nguồn"""
    pc = os.path.join(du_an, "cache", "am-do.json") if du_an else None
    d = (chung.doc_json(pc, {}) or {}) if pc else {}
    khoa = hashlib.md5(("|".join(inputs) + "||" + fl_giong + "|v4").encode("utf-8")).hexdigest()
    if d.get("khoa") == khoa and d.get("lufs") is not None:
        return d["lufs"], d.get("peak"), d.get("s_max")
    lufs, peak, s_max = _ebur128(inputs, fl_giong, ngan_han=True)
    if pc and lufs is not None:
        os.makedirs(os.path.dirname(pc), exist_ok=True)
        chung.ghi_json(pc, {"khoa": khoa, "lufs": lufs, "peak": peak, "s_max": s_max})
    return lufs, peak, s_max


def _duong(kho, id_or_path, du_an=None):
    if not id_or_path:
        return None
    if isinstance(id_or_path, str) and os.path.isfile(id_or_path):
        return id_or_path
    if du_an and isinstance(id_or_path, str) and os.path.isfile(os.path.join(du_an, id_or_path)):
        return os.path.join(du_an, id_or_path)
    if kho is not None:
        try:
            m = kho.lay(id_or_path) if hasattr(kho, "lay") else kho(id_or_path)
            if m and m.get("duong") and os.path.isfile(m["duong"]):
                return m["duong"]
        except Exception:
            pass
    return None


def bo_loc_am(ke_hoach, cat, nguon, kho=None, bat_dau_input=0, du_an=None, tong_dai=None):
    """nguon: [đường dẫn âm (am48 wav) theo src]. bat_dau_input: chỉ số input ffmpeg đầu tiên dành cho âm.
    Trả (inputs, filter_complex, map) — inputs là danh sách tham số như ["-i", a, "-i", b, ...]; map = "[aout]".
    Không có giọng lẫn nhạc → ("", "", None)."""
    am = (ke_hoach or {}).get("am") or {}
    qd = ((ke_hoach or {}).get("quyet_dinh") or {}).get("am") or {}
    thieu = []
    nguon = [n for n in (nguon or []) if n]
    cat = cat or ([{"src": 0, "a": 0, "b": tong_dai}] if nguon and tong_dai else [])
    nh = am.get("nhac") or {}
    p_nhac = (_duong(kho, nh.get("duong"), du_an) or _duong(kho, nh.get("id"), du_an)) if nh else None
    co_nhac = bool(p_nhac) and str(nh.get("muc") or "").lower() != "khong"
    co_sfx = bool(am.get("sfx"))
    if not (nguon and cat) and not co_nhac and not co_sfx:
        return [], "", None
    # --- mọi mức từ quyết định kênh (công thức đè từng trường); thiếu → trả AI, không tự điền ---
    lufs = _can(am, qd, "giong_lufs", thieu)
    tp = _can(am, qd, "dinh_dbtp", thieu)
    if co_nhac:
        lu_qd = _can(am, qd, "nhac.db", thieu) if (nh.get("db") is None and str(nh.get("muc") or "").lower() not in MUC_NHAC) else None
        vao = _can(am, qd, "nhac.vao", thieu); ra = _can(am, qd, "nhac.ra", thieu)
        ne = _can(am, qd, "nhac.ne_giong", thieu, kieu=bool)
        # sidechain (threshold/ratio/attack/release): TUỲ CHỌN trong hợp đồng 1c/hop_dong.py (chưa có trường) → thiếu thì dùng bộ số
        # kỹ thuật của bộ nén và ghi _do.sidechain_nguon="may_mac_dinh" để AI thấy; AI/kênh ghi am.sidechain thì dùng của AI
        sc = _lay(am, qd, "sidechain") if ne else None
        sc_nguon = "ai"
        if ne and not (isinstance(sc, dict) and all(k in sc for k in ("threshold", "ratio", "attack", "release"))):
            sc, sc_nguon = SIDECHAIN_KY_THUAT, "may_mac_dinh"
    if co_sfx and any(s.get("db") is None for s in am.get("sfx") or []):
        sfx_db_qd = _can(am, qd, "sfx.db", thieu)
    else:
        sfx_db_qd = None
    if thieu:
        raise chung.ThieuTruong(thieu)
    lufs = max(-30.0, min(-8.0, float(lufs)))              # kẹp biên vật lý (ngoài dải này nền tảng tự nén/bóp)
    tp = max(-6.0, min(-0.5, float(tp)))
    inputs = []; fl = []; idx = bat_dau_input
    tong = tong_dai or sum(float(s["b"]) - float(s["a"]) for s in cat)
    # --- giọng ---
    giong = None
    if nguon and cat:
        src_idx = {}
        for s in cat:
            si = int(s.get("src", 0))
            if si not in src_idx and si < len(nguon):
                src_idx[si] = idx; inputs += ["-i", nguon[si]]; idx += 1
        doan = []
        for k, s in enumerate(cat):
            si = int(s.get("src", 0))
            if si not in src_idx:
                continue
            fl.append(f"[{src_idx[si]}:a]atrim={float(s['a']):.4f}:{float(s['b']):.4f},asetpts=PTS-STARTPTS,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[g{k}]")
            doan.append(f"[g{k}]")
        if doan:
            gdb = float(am.get("giong_db") or 0.0)       # độ lệch thêm so với mức đích (AI ghi; 0 = đúng giong_lufs)
            if not (-6 <= gdb <= 6):                      # kế hoạch cũ ghi giong_db = mức LUFS đích → không phải độ lệch
                gdb = 0.0
            if len(doan) == 1:
                chuoi = doan[0] + "anull,"
            else:
                chuoi = "".join(doan) + "concat=n=%d:v=0:a=1," % len(doan)
            # đo LUFS giọng thật → đưa về giong_lufs bằng gain tĩnh (không bơm theo khoảng nghỉ)
            lufs_giong, peak_giong, s_giong = _do_giong_du(du_an, inputs, ";".join(fl + [chuoi]))
            if lufs_giong is None:
                lufs_giong = lufs
            g_v = max(-20.0, min(30.0, lufs - lufs_giong)) + gdb
            dinh_giong = (peak_giong + g_v) if peak_giong is not None else None        # đỉnh thật của giọng SAU chuẩn mức
            s_giong_sau = (s_giong + g_v) if s_giong is not None else None
            fl.append(f"{chuoi}volume={g_v:.2f}dB[giong]")
            giong = "[giong]"
    muc_giong = lufs                                   # mức giọng sau chuẩn (video không lời: mức đích)
    if not giong:
        dinh_giong, s_giong_sau = None, None
    # --- nhạc: mức = LU DƯỚI GIỌNG (đo LUFS tệp nhạc để đặt đúng, tệp nào cũng ra cùng cảm giác) ---
    nhac = None
    muc = str(nh.get("muc") or "").lower()
    if co_nhac:
        inputs += ["-stream_loop", "-1", "-i", p_nhac]; i_n = idx; idx += 1
        lu = nh.get("db")
        if lu is None:
            lu = MUC_NHAC.get(muc) if muc in MUC_NHAC else lu_qd
        lu = max(-40.0, min(-4.0, float(lu)))
        lufs_nhac, _, _ = _do_tep(p_nhac)
        dich = (muc_giong if giong else lufs - 4.0) + lu
        g_n = (dich - lufs_nhac) if lufs_nhac is not None else lu
        g_n = max(-60.0, min(20.0, g_n))
        vao = max(0.0, float(vao)); ra = max(0.0, float(ra))
        bd = float(nh.get("bat_dau", 0))
        ch = f"[{i_n}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,atrim=start={bd:.3f},asetpts=PTS-STARTPTS,atrim=0:{tong:.4f}"
        if vao > 0:
            ch += f",afade=t=in:st=0:d={vao:.3f}"
        if ra > 0 and tong > ra:
            ch += f",afade=t=out:st={tong - ra:.3f}:d={ra:.3f}"
        ch += f",volume={g_n:.2f}dB"
        if ne and giong:
            n = sc
            fl.append(ch + "[nhac0]")
            fl.append(f"{giong}asplit=2[giong_a][giong_sc]")
            fl.append(f"[nhac0][giong_sc]sidechaincompress=threshold={n['threshold']}:ratio={n['ratio']}:attack={n['attack']}:release={n['release']}:makeup=1[nhac]")
            giong = "[giong_a]"
        else:
            fl.append(ch + "[nhac]")
        nhac = "[nhac]"
        am.setdefault("_do", {}).update({"giong_lufs": round(muc_giong, 1), "nhac_lufs_tep": lufs_nhac, "nhac_duoi_giong_lu": lu, "nhac_gain_db": round(g_n, 1),
                                         "ne_giong": bool(ne and giong), "sidechain": (sc if (ne and giong) else None), "sidechain_nguon": (sc_nguon if (ne and giong) else None)})
    # --- sfx: mức = dB so với giọng theo LUFS tệp (tệp quá ngắn → theo đỉnh) ---
    am.setdefault("_do", {}).update({"giong_lufs": round(muc_giong, 1), "giong_dinh_dbtp": (round(dinh_giong, 1) if dinh_giong is not None else None),
                                     "giong_s_max": (round(s_giong_sau, 1) if s_giong_sau is not None else None)})
    sfxs = []
    for j, s in enumerate(am.get("sfx") or []):
        # kế hoạch đã giải: ưu tiên ĐƯỜNG DẪN, rồi id kho; "id" của sfx là nhãn nghĩa AI đặt (hook, the_bat…) — không tra được
        p = _duong(kho, s.get("duong"), du_an) or _duong(kho, s.get("id_kho"), du_an) or _duong(kho, s.get("id"), du_an)
        if not p:
            continue
        inputs += ["-i", p]; i_s = idx; idx += 1
        # 1.2.20 — tiếng động KHÔNG được to hơn giọng ở bất kỳ khoảnh khắc nào (vật lý, không phải gu):
        #  · mức đặt theo LUFS-S lớn nhất của tệp (không theo tích phân: tệp ngắn có đuôi lặng bị đặt quá to)
        #  · db tối đa −3 LU dưới giọng; đỉnh thật sau gain ≤ đỉnh giọng − 1 dB (hết "nổ" vượt giọng rồi limiter bóp)
        #  · mờ đầu 8 ms / cuối 40 ms (hết "tách" số)
        t = max(0.0, float(s.get("t", 0))); db = max(-40.0, min(-3.0, float(s.get("db") if s.get("db") is not None else sfx_db_qd)))
        l_s, pk_s, s_s = _do_tep(p, giay=20.0)
        # mức so sánh: RMS đỉnh 50 ms của tệp so với RMS đỉnh 50 ms của GIỌNG (cùng thước) — tiếng không được "nổ" to hơn giọng + db
        muc_tep = s_s if (s_s is not None and s_giong_sau is not None) else l_s
        if s_s is not None and s_giong_sau is not None:
            g_s = (s_giong_sau + db) - s_s
        elif l_s is not None:
            g_s = (muc_giong + db) - l_s
        elif pk_s is not None:
            g_s = (-3.0 + db) - pk_s
        else:
            g_s = db
        if pk_s is not None and dinh_giong is not None:
            g_s = min(g_s, (dinh_giong - 1.0) - pk_s)
        g_s = max(-60.0, min(30.0, g_s))
        am.setdefault("_do", {}).setdefault("sfx", []).append({"t": round(t, 2), "tep": os.path.basename(p), "s_max_tep": s_s, "lufs_tep": l_s, "dinh_tep": pk_s,
                                                              "gain_db": round(g_s, 1), "muc_sau": round((muc_tep or 0) + g_s, 1) if muc_tep is not None else None,
                                                              "dinh_sau": round(pk_s + g_s, 1) if pk_s is not None else None, "db_yeu_cau": db})
        ms = int(round(t * 1000))
        cat_ = ""
        if s.get("dai"):                                   # tiếng B-roll: cắt đúng đoạn [tu, tu+dai] + mờ đầu/cuối
            tu_ = max(0.0, float(s.get("tu") or 0)); dai_ = max(0.05, float(s["dai"])); mo_ = min(float(s.get("mo") or 0), dai_ / 2)
            cat_ = f"atrim=start={tu_:.3f}:duration={dai_:.3f},asetpts=PTS-STARTPTS,"
            if mo_ > 0:
                cat_ += f"afade=t=in:st=0:d={mo_:.3f},afade=t=out:st={max(0.0, dai_ - mo_):.3f}:d={mo_:.3f},"
        mo_dau = "afade=t=in:st=0:d=0.008," if not cat_ else ""
        fl.append(f"[{i_s}:a]{cat_}aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo,{mo_dau}volume={g_s:.2f}dB,adelay={ms}|{ms}[sfx{j}]")
        sfxs.append(f"[sfx{j}]")
    if du_an and am.get("_do"):                              # số đo mức từng mốc tiếng → cache/am-do-sfx.json (kiểm lại được)
        try:
            os.makedirs(os.path.join(du_an, "cache"), exist_ok=True)
            chung.ghi_json(os.path.join(du_an, "cache", "am-do-sfx.json"), am["_do"])
        except Exception:
            pass
    # --- trộn: gain tĩnh đã đúng mức → chỉ chặn đỉnh ---
    kenh = [k for k in [giong, nhac] if k] + sfxs
    if not kenh:
        return [], "", None
    lim = 10 ** (tp / 20.0)
    duoi = f"atrim=0:{tong:.4f},alimiter=limit={lim:.4f}:attack=5:release=60:level=false,aresample=48000[aout]"
    if len(kenh) == 1:
        fl.append(f"{kenh[0]}{duoi}")
    else:
        fl.append(f"{''.join(kenh)}amix=inputs={len(kenh)}:duration=first:normalize=0:dropout_transition=0,{duoi}")
    return inputs, ";".join(fl), "[aout]"
