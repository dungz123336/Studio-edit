# -*- coding: utf-8 -*-
"""Nhận dạng lời bằng faster-whisper large-v3-turbo (int8, CPU) → doc/loi.json.
Lặng đo bằng năng lượng wav (RMS 20 ms), không tin Whisper."""
import os, sys, re, wave, time, itertools
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung

# từ đệm (so khớp sau khi bỏ dấu câu, thường hoá); cụm 2 từ xét trước
TU_DEM = {"ừm", "ừ", "ờ", "ờm", "à", "ậm", "ư", "ơ", "hmm", "um", "uh", "ừa", "ừ-hứ", "ờ-ờ",
          "ầm", "ảm", "ơm", "hừm", "ờờ", "ừừ", "ààà", "àà"}   # biến thể Whisper hay viết cho "ầm ừ"
CUM_DEM = [("kiểu", "như"), ("ờ", "thì"), ("à", "thì"), ("ừm", "thì")]
_MODEL = None
PHIEN = 3                       # đổi cách hậu xử lý mốc từ → loi.json cũ tính lại
TU_NGAN = {"la", "thi", "cai", "no", "ma", "kieu", "roi", "ay", "day", "nay", "nhe", "a", "o", "u", "um"}


def _cat_duoi_theo_lang(tu, lang, pad=0.06, toi_thieu=0.08):
    """Whisper hay kéo mốc KẾT THÚC (và đôi khi BẮT ĐẦU) của từ phủ lên khoảng lặng năng lượng kề bên → kéo mốc về mép
    khoảng lặng (giữ ≥ toi_thieu s). Nhờ vậy khoảng lặng thật mới được cắt, phụ đề karaoke không sáng lâu quá."""
    if not lang or not tu:
        return tu
    ra = []
    for t in tu:
        a, b = float(t["a"]), float(t["b"])
        for la, lb in lang:
            if la >= b:
                break
            if lb <= a:
                continue
            if la > a + toi_thieu and (lb >= b - pad or (b - a > 0.5 and lb - la >= 0.25)):
                b = round(la + pad, 3)                           # lặng chiếm đuôi từ, hoặc lặng ≥0.3 s NẰM TRONG từ dài >0.9 s (Whisper gộp "từ + ờ…")
            elif la <= a + 0.02 and lb < b - toi_thieu:         # từ "bắt đầu" trong lặng → dời đầu
                a = round(lb - pad, 3)
        ra.append(dict(t, a=round(a, 3), b=round(max(b, a + 0.05), 3)))
    return ra


def _manh_khong_chu(tu, lang, dur, toi_thieu):
    """→ [[a,b]] mảnh có TIẾNG (ngoài khoảng lặng năng lượng) nhưng KHÔNG có chữ, dài ≥ toi_thieu s"""
    co, t = [], 0.0
    for la, lb in sorted(lang):
        if la > t:
            co.append([t, la])
        t = max(t, lb)
    if dur > t:
        co.append([t, dur])
    moc = sorted((float(x["a"]), float(x["b"])) for x in tu)
    ra = []
    for a, b in co:
        manh = [[a, b]]
        for ta, tb in moc:
            if tb <= a:
                continue
            if ta >= b:
                break
            moi = []
            for ma, mb in manh:
                if tb <= ma or ta >= mb:
                    moi.append([ma, mb]); continue
                if ta > ma:
                    moi.append([ma, ta])
                if tb < mb:
                    moi.append([tb, mb])
            manh = moi
        ra.extend([round(ma, 3), round(mb, 3)] for ma, mb in manh if mb - ma >= toi_thieu)
    return ra


def _mo_c_theo_dem(tu, dem, toi_thieu=0.08):
    """đoạn đệm (lượt hai) rơi VÀO TRONG mốc một từ (Whisper gộp "từ + ờm…") → kéo mốc kết thúc từ về đầu đoạn đệm"""
    if not dem:
        return tu
    ra = []
    for t in tu:
        a, b = float(t["a"]), float(t["b"])
        for d in dem:
            da, db = float(d[0]), float(d[1])
            if a + toi_thieu < da < b - 0.02 and db >= b - 0.1:
                b = round(da, 3)
        ra.append(dict(t, b=max(b, a + 0.05)))
    return ra


def _dem_khong_chu(tu, lang, dur, toi_thieu=0.5, pad=0.05):
    """có tiếng mà không chữ ≥ toi_thieu s → "ờ…/à…/hơi dài" Whisper bỏ qua → từ đệm (lượt hai xác nhận/bác lại)."""
    return [[round(a + pad, 3), round(b - pad, 3), "ờ (có tiếng, không chữ)"] for a, b in _manh_khong_chu(tu, lang, dur, toi_thieu)]


def _tru_vung(dem, bo, toi_thieu=0.08):
    """trừ các vùng `bo` [[a,b]] khỏi từ đệm (lượt hai bác phần đó) → mảnh còn lại ≥ toi_thieu s"""
    ra = []
    for a, b, nh in dem:
        manh = [[a, b]]
        for ba, bb in bo:
            moi = []
            for ma, mb in manh:
                if bb <= ma or ba >= mb:
                    moi.append([ma, mb]); continue
                if ba > ma:
                    moi.append([ma, ba])
                if bb < mb:
                    moi.append([bb, mb])
            manh = moi
        ra.extend([round(ma, 3), round(mb, 3), nh] for ma, mb in manh if mb - ma >= toi_thieu)
    return ra


def _gop_dem(dem):
    """gộp các từ đệm chồng nhau (lượt một + lượt hai) → [[a,b,nhãn]] (nhãn của mục đến trước theo thời gian)"""
    ra = []
    for d in sorted(dem, key=lambda d: (d[0], d[1])):
        if ra and d[0] <= ra[-1][1]:
            ra[-1][1] = max(ra[-1][1], d[1])
            if "lượt 2" in d[2] and "lượt 2" not in ra[-1][2]:
                ra[-1][2] = d[2]
        else:
            ra.append([d[0], d[1], d[2]])
    return ra


def _sach(w):
    return re.sub(r"^[\W_]+|[\W_]+$", "", chung.NFC(w or "").strip().lower())


def _wav(am16):
    with wave.open(am16, "rb") as f:
        n, sr, ch, sw = f.getnframes(), f.getframerate(), f.getnchannels(), f.getsampwidth()
        raw = f.readframes(n)
    if sw != 2:
        raise RuntimeError("wav không phải 16-bit")
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    return x, sr


def do_lang(am16, cua_so=0.02, toi_thieu=0.25):
    """→ (lang:[[a,b]], dur, co_tieng) — RMS 20 ms, ngưỡng thích nghi theo sàn ồn (p10 + 10 dB, trần −32 dBFS)."""
    x, sr = _wav(am16)
    dur = len(x) / sr
    if len(x) == 0:
        return [], 0.0, False
    n = int(sr * cua_so)
    m = len(x) // n
    if m == 0:
        return [[0.0, dur]], dur, False
    rms = np.sqrt((x[: m * n].reshape(m, n) ** 2).mean(axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    p10, p95 = np.percentile(db, 10), np.percentile(db, 95)
    co_tieng = (p95 - p10) > 12 and p95 > -45
    nguong = min(-32.0, max(p10 + 10.0, -60.0))
    lang_mask = db < nguong
    # làm mịn: lấp lỗ < 60 ms trong vùng có tiếng
    lang = []
    i = 0
    while i < m:
        if lang_mask[i]:
            j = i
            while j < m and lang_mask[j]:
                j += 1
            a, b = i * cua_so, j * cua_so
            if b - a >= toi_thieu:
                lang.append([round(a, 3), round(min(b, dur), 3)])
            i = j
        else:
            i += 1
    return lang, dur, co_tieng


_KHOA_NAP = __import__("threading").Lock()


def _nap_model(cfg):
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    with _KHOA_NAP:                                  # 1.2.19 (E6): hai luồng cùng nạp → nạp một lần (trước: 2 Whisper song song trên máy yếu)
        if _MODEL is not None:
            return _MODEL
        return _nap_model_that(cfg)


def _nap_model_that(cfg):
    global _MODEL
    from faster_whisper import WhisperModel
    hm = chung.hang_may(ha_luong=False)
    ten = cfg.get("model") or hm["whisper"]
    # V3_WHISPER_LUONG (môi trường) / whisper.luong (cấu hình) ép số luồng — máy đang bận việc khác
    luong = int(os.environ.get("V3_WHISPER_LUONG") or cfg.get("luong") or hm["whisper_luong"])
    ung_vien = [ten]
    if ten == "large-v3-turbo":
        ung_vien = ["mobiuslabsgmbh/faster-whisper-large-v3-turbo", "large-v3-turbo"]
    loi_cuoi = None
    for uv in ung_vien:
        for local in (True, False):
            if not local and not _co_mang_hf():
                continue                                  # 1.2.19: không có mạng → không gọi HuggingFace (trước: treo/lỗi getaddrinfo)
            try:
                _MODEL = WhisperModel(uv, device="cpu", compute_type=cfg.get("compute", "int8"), cpu_threads=luong,
                                      local_files_only=local)
                return _MODEL
            except Exception as ex:
                loi_cuoi = ex
    raise RuntimeError(f"không nạp được Whisper: {loi_cuoi}")


def _co_mang_hf():
    """có phân giải được huggingface.co trong 4 s không (getaddrinfo không nghe setdefaulttimeout → chạy trong luồng riêng)"""
    import socket, threading
    kq = []

    def _thu():
        try:
            socket.getaddrinfo("huggingface.co", 443)
            kq.append(True)
        except OSError:
            kq.append(False)
    t = threading.Thread(target=_thu, daemon=True)
    t.start()
    t.join(4.0)
    return bool(kq and kq[0])


def _tim_dem(tu):
    """→ [[a,b,"ừm"]] từ danh sách từ (đã có w,a,b)"""
    dem, bo = [], set()
    s = [_sach(t["w"]) for t in tu]
    for i in range(len(tu) - 1):
        if (s[i], s[i + 1]) in CUM_DEM and i not in bo and (i + 1) not in bo:
            dem.append([tu[i]["a"], tu[i + 1]["b"], s[i] + " " + s[i + 1]])
            bo.update((i, i + 1))
    for i, t in enumerate(tu):
        if i in bo:
            continue
        if s[i] in TU_DEM:
            dem.append([t["a"], t["b"], s[i]])
    dem.sort()
    return dem


# ── LƯỢT HAI: nghe lại CHỈ các đoạn nghi ngờ (Whisper hay bỏ/gộp "ờ…, à…, ừm") ────────────────────────────────────
# Tham số DÒ (không phải gu) — cắt hay không do cat.NHIP quyết.
LUOT2_PROMPT = "Ờ… thì là, ừm, kiểu như là… à, mình nói ờ, ừ, ờm vậy đó."   # câu tự nhiên (danh sách "ờ, ờ" dễ gây lặp)
LUOT2_KHONG_CHU = 0.25   # có tiếng mà không chữ từ ngần này (s) → nghi
LUOT2_DAI = 2.5          # từ dài hơn n × trung vị độ dài từ → nghi
LUOT2_MEP = 0.15         # mép đầu/cuối của từ dính khoảng lặng (s) → nghi
LUOT2_DEM = 0.1          # đệm hai bên mỗi đoạn cắt tiếng (s)
LUOT2_DEM_NGAN = 0.15    # "ờ" lượt hai ngắn hơn ngần này (s) không tin (thường là âm cuối "m/n" của từ trước nghe thành "ờm")
LUOT2_KE = 0.15          # từ sát vùng "không chữ" trong ngần này (s) = từ bên cạnh (lượt hai nghe lọt mép nó → không tính chữ thật)
LUOT2_CACH = 0.3         # lặng chèn giữa các đoạn khi ghép thành khối (s)
LUOT2_KHOI = 15.0        # khối ghép ≤ ngần này (s) → 1 lần transcribe; hết ngân sách → khối sau (ưu tiên thấp) bỏ qua
LUOT2_NGAN_SACH = 0.15   # lượt hai ≤ 15 % thời gian lượt một (hết ngân sách → khối ưu tiên thấp bỏ qua)
LUOT2_DB_THAP = 10.0     # đuôi từ "thấp năng lượng" khi trung bình dB kém đầu từ ≥ ngần này
TU_KEO = TU_NGAN | {"nhu"}   # từ đệm "có chữ" hay bị kéo dài (khong_dau): thì/là/cái/kiểu (như)/nó/mà/rồi…


def _khong_dau_sach(w):
    return chung.khong_dau(_sach(w))


def _nang_luong(x, sr, cua_so=0.02):
    """→ (dB theo khung 20 ms, cua_so)"""
    n = int(sr * cua_so)
    m = len(x) // n
    if m == 0:
        return np.zeros(0, np.float32), cua_so
    rms = np.sqrt((x[: m * n].reshape(m, n) ** 2).mean(axis=1) + 1e-12)
    return 20 * np.log10(rms + 1e-9), cua_so


def _db_tb(db, cs, a, b):
    i, j = int(a / cs), int(np.ceil(b / cs))
    if j <= i or i >= len(db):
        return -120.0
    return float(np.mean(db[i:min(j, len(db))]))


def _trung_vi(tu):
    d = sorted(float(t["b"]) - float(t["a"]) for t in tu)
    return d[len(d) // 2] if d else 0.2


def _doan_nghi(tu, lang, dur):
    """→ [{a,b (vùng nghi), sa,sb (đoạn cắt tiếng), ly_do, i (chỉ số từ | None), ke (chữ từ bên cạnh), uu}]"""
    tv = _trung_vi(tu)
    ra = []
    for a, b in _manh_khong_chu(tu, lang, dur, LUOT2_KHONG_CHU):
        # chữ của từ sát hai bên: lượt hai hay nghe lọt mép từ bên cạnh (hoặc kéo dài nó) vào vùng → không tính là "chữ thật".
        # KHÔNG ghép cả từ bên cạnh vào đoạn nghe: có ngữ cảnh, Whisper lại "chuẩn hoá" bỏ ờ/à (đã thử: "cái… ờm" → "cái… mình").
        ke = {_sach(t["w"]) for t in tu if a - LUOT2_KE <= float(t["b"]) <= a + 0.02 or b - 0.02 <= float(t["a"]) <= b + LUOT2_KE}
        ra.append({"a": a, "b": b, "sa": a, "sb": b, "ly_do": "khong_chu", "i": None, "ke": ke, "uu": 0})
    dau_lang = [la for la, lb in lang]
    cuoi_lang = [lb for la, lb in lang]
    for i, t in enumerate(tu):
        a, b = float(t["a"]), float(t["b"])
        if _sach(t["w"]) in TU_DEM:
            continue                                          # đã là từ đệm
        g = {"i": i, "sa": a, "sb": b}                        # nghe CẢ từ để Whisper nhận ra chính nó + phần "ờ" dính
        if b - a > LUOT2_DAI * tv:
            ra.append(dict(g, a=a, b=b, ly_do="dai", uu=1))
            continue
        if b - a < 2 * LUOT2_MEP:
            continue                                          # từ ngắn: mép ≈ cả từ, nghe lại chỉ ra chính nó
        if any(abs(la - b) <= 0.08 for la in dau_lang):      # dính lặng phía sau ("là-ờờ…" rồi ngừng)
            ra.append(dict(g, a=b - LUOT2_MEP, b=b, ly_do="mep_cuoi", uu=2))
        if any(abs(lb - a) <= 0.08 for lb in cuoi_lang):     # dính lặng phía trước ("ờờ-thì…" sau khi ngừng)
            ra.append(dict(g, a=a, b=a + LUOT2_MEP, ly_do="mep_dau", uu=3))
    for d in ra:
        d["sa"], d["sb"] = round(max(0.0, d["sa"] - LUOT2_DEM), 3), round(min(dur, d["sb"] + LUOT2_DEM), 3)
    return ra


def _khoi_ghep(doan, toi_da=None):
    """gộp đoạn cắt tiếng chồng nhau → nhóm; xếp nhóm theo ưu tiên vào khối ≤ LUOT2_KHOI s (khối đầu = quan trọng nhất)"""
    nhom = []
    for d in sorted(doan, key=lambda d: d["sa"]):
        if nhom and d["sa"] <= nhom[-1]["sb"]:
            g = nhom[-1]
            g["sb"] = max(g["sb"], d["sb"]); g["ds"].append(d); g["uu"] = min(g["uu"], d["uu"])
        else:
            nhom.append({"sa": d["sa"], "sb": d["sb"], "ds": [d], "uu": d["uu"]})
    toi_da = toi_da or LUOT2_KHOI
    khoi, cur, dai = [], [], LUOT2_CACH
    for g in sorted(nhom, key=lambda g: (g["uu"], g["sa"])):
        l = g["sb"] - g["sa"] + LUOT2_CACH
        if cur and dai + l > toi_da:
            khoi.append(sorted(cur, key=lambda g: g["sa"])); cur, dai = [], LUOT2_CACH
        cur.append(g); dai += l
    if cur:
        khoi.append(sorted(cur, key=lambda g: g["sa"]))
    return khoi


def _transcribe_ngan(model, am, ngon_ngu):
    """transcribe một khối ≤ 30 s; encoder chạy đúng độ dài khối thay vì đệm 3000 khung (khối ~15 s nhanh ≈ 2×).
    Đã thử mỗi đoạn một mẫu batch (encoder 1–2 s): ra rác ("Kat", "Mr", "A..!!!") → cần khối đủ dài."""
    import faster_whisper.transcribe as fwt
    goc = fwt.pad_or_trim
    khung = int(np.ceil(len(am) / 16000 * 100)) + 4
    khung += khung % 2
    if khung < 3000:
        fwt.pad_or_trim = lambda arr, length=3000, **k: goc(arr, min(length, khung), **k)
    try:
        seg_iter, _ = model.transcribe(
            am, language=ngon_ngu, beam_size=1, vad_filter=False, initial_prompt=LUOT2_PROMPT, word_timestamps=True,
            condition_on_previous_text=False, temperature=0.0, no_speech_threshold=None, log_prob_threshold=None,
            compression_ratio_threshold=None, no_repeat_ngram_size=3,
            max_new_tokens=int(len(am) / 16000 * 12) + 8)        # chặn vòng lặp ảo giác tốn thời gian giải mã
        return list(seg_iter)
    finally:
        fwt.pad_or_trim = goc


def _nghe_khoi(model, x, sr, khoi, ngon_ngu):
    """ghép các nhóm của khối (chèn lặng) → 1 lần transcribe → [(nhom, [(w, a_goc, b_goc, p)] | None nếu ảo giác lặp)]"""
    cach = np.zeros(int(sr * LUOT2_CACH), np.float32)
    phan, bang, t = [cach], [], LUOT2_CACH
    for g in khoi:
        s = x[int(g["sa"] * sr):int(g["sb"] * sr)]
        bang.append((t, t + len(s) / sr, g))
        phan += [s, cach]
        t += len(s) / sr + LUOT2_CACH
    segs = _transcribe_ngan(model, np.concatenate(phan).astype(np.float32), ngon_ngu)
    tat_ca = [_sach(w.word) for sg in segs for w in (sg.words or [])]
    lap = max((sum(1 for _ in k) for _, k in itertools.groupby(w for w in tat_ca if w)), default=0)
    if lap >= 4 or len(tat_ca) > t / 0.1:                    # "ờ, ờ, ờ…" — prompt gây vòng lặp → bỏ cả khối
        return [(g, None) for _, _, g in bang]
    ra = {id(g): [] for _, _, g in bang}
    for sg in segs:
        for w in (sg.words or []):
            s = chung.NFC((w.word or "").strip())
            if not s:
                continue
            wa, wb = float(w.start), float(w.end)
            giua = (wa + wb) / 2
            for t0, t1, g in bang:
                if t0 - LUOT2_CACH / 2 <= giua < t1 + LUOT2_CACH / 2:
                    a = g["sa"] + max(0.0, wa - t0)
                    b = g["sa"] + min(t1 - t0, wb - t0)
                    if b > a:
                        ra[id(g)].append((s, round(a, 3), round(b, 3), round(float(w.probability or 0), 3)))
                    break
    return [(g, ra[id(g)]) for _, _, g in bang]


def _tru_chu(lo, hi, chu, le=0.02):
    """thu hẹp [lo,hi] để không đè lên chữ thật lượt hai (chữ nằm bên trái → đẩy lo, bên phải → kéo hi)"""
    giua = (lo + hi) / 2
    for c in chu:
        if c[2] <= lo or c[1] >= hi:
            continue
        if (c[1] + c[2]) / 2 <= giua:
            lo = max(lo, c[2] + le)
        else:
            hi = min(hi, c[1] - le)
    return lo, hi


def _la_dem(chu):
    """[(w,a,b,p)] → [(a,b,nhãn)] các từ/cụm đệm"""
    s = [_sach(c[0]) for c in chu]
    ra, bo = [], set()
    for i in range(len(chu) - 1):
        if (s[i], s[i + 1]) in CUM_DEM:
            ra.append((chu[i][1], chu[i + 1][2], s[i] + " " + s[i + 1])); bo.update((i, i + 1))
    for i, c in enumerate(chu):
        if i not in bo and s[i] in TU_DEM:
            ra.append((c[1], c[2], s[i]))
    return ra


def _keo_dai(t, chu, db, cs, tv):
    """đuôi từ đệm "có chữ" kéo dài → [a,b,"keo_dai <từ>"] | None. Giữ đầu từ 1.5 × trung vị (hoặc tới mốc kết thúc
    lượt hai nếu sớm hơn). Cắt khi đuôi thấp năng lượng, hoặc lượt hai nghe lại mà không ra chữ khác trong đuôi."""
    a, b = float(t["a"]), float(t["b"])
    goc = _sach(t["w"])
    giu = a + 1.5 * tv
    khac = False
    if chu is not None:
        cung = [c for c in chu if _sach(c[0]) == goc and a - 0.1 <= c[1] < b]
        if cung and cung[0][1] > a + tv:
            return None                                       # lượt hai: từ thật bắt đầu muộn (mốc lượt một sớm) → không cắt
        khac = any(_sach(c[0]) not in TU_DEM and _sach(c[0]) != goc and giu < (c[1] + c[2]) / 2 <= b + 0.05 for c in chu)
        if cung and not khac:
            giu = max(a + tv, min(giu, cung[0][2]))
    if b - giu < 0.15:
        return None
    thap = _db_tb(db, cs, giu, b) <= _db_tb(db, cs, a, giu) - LUOT2_DB_THAP
    if thap or (chu is not None and not khac):
        return [round(giu, 3), round(b, 3), "keo_dai " + goc]
    return None


def luot_hai(model, x, sr, tu, lang, dur, ngon_ngu="vi", ngan_sach=None, toc_do=None):
    """nghe lại các đoạn nghi ngờ (ghép thành ít khối có chèn lặng, mỗi khối 1 lần transcribe, encoder ngắn) →
    (dem [[a,b,nhãn]], bo_dem [[a,b]] (vùng "không chữ" mà lượt hai nghe ra chữ thật → KHÔNG phải đệm),
    chi_tiet {"doan": [[a,b,ly_do,"chữ@a-b …",ket_luan]], "giay", "khoi", "da_nghe", "bo_qua"}). Không đổi `tu`.
    ngan_sach: giây tối đa; toc_do: giây máy / giây tiếng của lượt một → cỡ khối vừa ngân sách, khối sau ước vượt thì bỏ."""
    t0 = time.time()
    doan = _doan_nghi(tu, lang, dur)
    toi_da = max(3.0, min(LUOT2_KHOI, ngan_sach / (1.2 * toc_do))) if ngan_sach and toc_do else None
    khoi = _khoi_ghep(doan, toi_da) if doan else []
    db, cs = _nang_luong(x, sr)
    tv = _trung_vi(tu)
    dem, bo_dem, ct, nghe, da_nghe, ao_giac = [], [], [], {}, 0, 0
    da_tieng = 0.0
    for k in khoi:
        tieng = sum(g["sb"] - g["sa"] + LUOT2_CACH for g in k)
        if da_nghe and ngan_sach is not None and time.time() - t0 + (time.time() - t0) / da_tieng * tieng > ngan_sach:
            break                                             # ước khối này làm vượt ngân sách → bỏ (cả các khối ưu tiên thấp hơn)
        da_tieng += tieng
        for g, chu in _nghe_khoi(model, x, sr, k, ngon_ngu):
            if chu is None:
                ao_giac += 1
                continue
            for d in g["ds"]:
                nghe[id(d)] = [c for c in chu if d["sa"] <= (c[1] + c[2]) / 2 <= d["sb"]]
        da_nghe += 1
    for d in doan:
        a, b = d["a"], d["b"]
        chu = nghe.get(id(d))
        ket, that = None, []
        if chu is None:                                       # chưa nghe lại (hết ngân sách/ảo giác): chỉ xét từ kéo dài theo năng lượng
            if d["ly_do"] == "dai" and _khong_dau_sach(tu[d["i"]]["w"]) in TU_KEO:
                ket = _keo_dai(tu[d["i"]], None, db, cs, tv)
        elif d["ly_do"] == "khong_chu":
            trong = [c for c in chu if a + 0.03 <= (c[1] + c[2]) / 2 <= b - 0.03]
            that = [c for c in trong if _sach(c[0]) and _sach(c[0]) not in TU_DEM and _sach(c[0]) not in d["ke"]]
            if that:
                bo_dem.append([a, b])                          # nghe ra chữ thật (lượt một bỏ sót) → không phải đệm
            else:
                lo, hi = _tru_chu(a, b, [c for c in chu if _sach(c[0]) in d["ke"]])   # phần từ bên cạnh "kéo" sang
                if lo > a + 0.02:
                    bo_dem.append([a, lo])
                if hi < b - 0.02:
                    bo_dem.append([hi, b])
                dm = _la_dem(trong)
                rong_ = not any(_sach(c[0]) for c in chu)      # "rỗng" chỉ khi cả đoạn không ra chữ nào (lọt mép từ bên cạnh → mơ hồ, không cắt)
                if hi - lo >= LUOT2_DEM_NGAN and (dm or rong_):
                    ket = [lo, hi, (dm[0][2] + " (lượt 2)") if dm else "ờ (có tiếng, lượt 2 rỗng)"]
        else:
            t = tu[d["i"]]
            ta, tb = float(t["a"]), float(t["b"])
            goc = _sach(t["w"])
            nghe_dung = bool(goc) and any(_sach(c[0]) == goc for c in chu)   # lượt hai nghe lại đúng từ gốc → mốc đáng tin
            that = [c for c in chu if _sach(c[0]) and _sach(c[0]) not in TU_DEM]
            kets = []
            for m in _la_dem(chu):
                if not (a - 0.05 <= (m[0] + m[1]) / 2 <= b + 0.05):
                    continue
                if not nghe_dung and m[1] - m[0] < 0.2:       # không khớp từ gốc → chỉ tin "ờ" đủ dài
                    continue
                lo, hi = _tru_chu(max(m[0], ta), min(m[1], tb), that)
                if hi - lo >= LUOT2_DEM_NGAN:
                    kets.append([lo, hi, m[2] + " (dính, lượt 2)"])
            ket = kets or None
            if ket is None and d["ly_do"] == "dai" and _khong_dau_sach(t["w"]) in TU_KEO:
                ket = _keo_dai(t, chu, db, cs, tv)
        kets = [k for k in ((ket if isinstance(ket[0], list) else [ket]) if ket else []) if k[1] - k[0] >= 0.08]
        dem += [[round(k[0], 3), round(k[1], 3), k[2]] for k in kets]
        ct.append([round(a, 3), round(b, 3), d["ly_do"],
                   " ".join(f"{c[0]}@{c[1]:.2f}-{c[2]:.2f}" for c in chu) if chu is not None else None,
                   "; ".join(f"{k[2]} {k[0]:.2f}-{k[1]:.2f}" for k in kets) if kets
                   else ("chữ thật" if that and d["ly_do"] == "khong_chu" else "-")])
    return dem, bo_dem, {"doan": ct, "giay": round(time.time() - t0, 2), "khoi": len(khoi), "da_nghe": da_nghe,
                         "ao_giac": ao_giac, "bo_qua": sum(1 for d in doan if id(d) not in nghe)}


def nhan(du_an, am16, ngon_ngu="vi"):
    """→ đường doc/loi.json. Ưu tiên daemon giữ model trong RAM (doc/loi_daemon.py — bỏ ~45 s nạp model mỗi việc);
    daemon bận / không có / tắt (V3_LOI_TAI_CHO=1) → nhận dạng tại chỗ."""
    cfg = chung.cau_hinh().get("whisper", {})
    ra_p = os.path.join(du_an, "doc", "loi.json")
    ten_model = cfg.get("model") or chung.hang_may(ha_luong=False)["whisper"]
    if am16 and os.path.isfile(am16):
        h = chung.bam(am16)
        cu = chung.doc_json(ra_p)
        if cu and cu.get("bam") == h and cu.get("model") == ten_model and cu.get("phien") == PHIEN:
            chung.log(du_an, "lời: dùng cache loi.json")
            return ra_p
        r = None
        try:
            from doc import loi_daemon as _LD
            r = _LD.goi(du_an, am16, ngon_ngu)
        except Exception as ex:
            chung.log(du_an, f"lời: daemon không dùng được ({ex}) → tại chỗ")
        if r == "ok" and os.path.isfile(ra_p):
            return ra_p
        if r == "ban":
            chung.log(du_an, "lời: daemon đang bận việc khác → nhận dạng tại chỗ")
    return _nhan_tai_cho(du_an, am16, ngon_ngu)


def _nhan_tai_cho(du_an, am16, ngon_ngu="vi"):
    """→ đường doc/loi.json {"tu","cau","lang","dem","model","dur"}; cache theo băm am16."""
    cfg = chung.cau_hinh().get("whisper", {})
    ra_p = os.path.join(du_an, "doc", "loi.json")
    ten_model = cfg.get("model") or chung.hang_may(ha_luong=False)["whisper"]
    rong = {"tu": [], "cau": [], "lang": [], "dem": [], "model": ten_model, "dur": 0.0, "bam": None}
    if not am16 or not os.path.isfile(am16):
        chung.log(du_an, "lời: nguồn không có tiếng → loi.json rỗng")
        chung.ghi_json(ra_p, rong)
        return ra_p
    h = chung.bam(am16)
    cu = chung.doc_json(ra_p)
    if cu and cu.get("bam") == h and cu.get("model") == ten_model and cu.get("phien") == PHIEN:
        chung.log(du_an, "lời: dùng cache loi.json")
        return ra_p
    lang, dur, co_tieng = do_lang(am16)
    rong.update(lang=lang, dur=round(dur, 3), bam=h)
    if not co_tieng:
        chung.log(du_an, "lời: âm quá yếu/không có tiếng nói → loi.json rỗng")
        chung.ghi_json(ra_p, rong)
        return ra_p
    t0 = time.time()
    model = _nap_model(cfg)
    t_nap = time.time() - t0
    chung.log(du_an, f"lời: nạp Whisper {ten_model} {t_nap:.1f}s, đang nhận dạng {dur:.0f}s…")
    x, sr = _wav(am16)          # đưa mảng float32 16k thẳng vào (tránh PyAV; av 19 không hợp faster-whisper 1.2)
    if sr != 16000:
        raise RuntimeError(f"am16 phải 16 kHz, đang {sr}")
    seg_iter, info = model.transcribe(
        x, language=ngon_ngu, beam_size=int(cfg.get("beam", 1)), vad_filter=bool(cfg.get("vad", True)),
        vad_parameters={"min_silence_duration_ms": 400, "speech_pad_ms": 200},
        word_timestamps=True, condition_on_previous_text=False, temperature=0.0,
        no_speech_threshold=0.6, log_prob_threshold=-1.0, compression_ratio_threshold=2.4)
    tu, cau = [], []
    cuoi = -1.0
    t_bao = time.time()
    for sg in seg_iter:
        if time.time() - t_bao > 60:            # 1.2.19: tiến độ mỗi phút (video dài trên CPU yếu nhận dạng > 45 phút) → watchdog không coi là treo
            chung.log(du_an, f"lời: đã nhận {float(getattr(sg, 'end', 0) or 0):.0f}/{dur:.0f} s…")
            t_bao = time.time()
        txt = chung.NFC((sg.text or "").strip())
        if not txt:
            continue
        ws = []
        for w in (sg.words or []):
            s = chung.NFC((w.word or "").strip())
            if not s:
                continue
            a, b = float(w.start), float(w.end)
            if a < cuoi:          # chống trùng thời gian giữa các đoạn
                a = cuoi
            if b <= a:
                b = a + 0.05
            cuoi = b
            d = {"w": s, "a": round(a, 3), "b": round(b, 3), "p": round(float(w.probability or 0), 3)}
            ws.append(d)
        if not ws:
            continue
        tu.extend(ws)
        cau.append({"a": ws[0]["a"], "b": ws[-1]["b"], "txt": txt})
    # lọc ảo giác: câu lặp y hệt ≥ 3 lần liên tiếp → giữ 1
    loc, lap = [], 0
    for c in cau:
        if loc and loc[-1]["txt"].lower() == c["txt"].lower():
            lap += 1
            if lap >= 2:
                continue
        else:
            lap = 0
        loc.append(c)
    tu = _cat_duoi_theo_lang(tu, lang)
    dem = _tim_dem(tu) + _dem_khong_chu(tu, lang, dur)
    t1 = time.time() - t0
    so_dem1 = len(dem)
    if tu and cfg.get("luot_hai", True):
        try:
            d2, bo2, ct = luot_hai(model, x, sr, tu, lang, dur, ngon_ngu, ngan_sach=LUOT2_NGAN_SACH * t1,
                                  toc_do=max(0.05, (t1 - t_nap) / max(dur, 1.0)))
            dem = _tru_vung(dem, bo2) + d2
            rong["luot_hai"] = ct
            chung.log(du_an, f"lời lượt 2: {len(ct['doan'])} đoạn nghi, {ct['da_nghe']}/{ct['khoi']} khối, +{len(d2)} đệm, "
                             f"bác {len(bo2)} — {ct['giay']:.1f}s")
        except Exception as ex:
            chung.log(du_an, f"lời lượt 2 lỗi (bỏ qua): {ex}")
    dem = _gop_dem(dem)
    tu = _mo_c_theo_dem(tu, dem)
    rong.update(tu=tu, cau=loc, dem=dem, phien=PHIEN)
    chung.log(du_an, f"lời: {len(tu)} từ, {len(loc)} câu, {len(rong['dem'])} từ đệm (lượt một {so_dem1}), {len(lang)} khoảng lặng — {time.time() - t0:.1f}s")
    chung.ghi_json(ra_p, rong)
    return ra_p


if __name__ == "__main__":
    print(nhan(sys.argv[1], sys.argv[2]))
