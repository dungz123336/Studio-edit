# -*- coding: utf-8 -*-
"""Đề xuất cắt: lặng > 0.4 s (giữ 0.25 s), từ đệm, cụm lặp liền kề → doc/cat-de-xuat.json + ánh xạ giây gốc → thành phẩm."""
import os, sys, re, wave, difflib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung

LANG_TOI_DA = 0.4      # lặng dài hơn → cắt
LANG_GIU = 0.25        # phần lặng giữ lại
DOAN_TOI_THIEU = 0.6   # đoạn giữ ngắn hơn → bỏ
GOP_DUOI = 0.15        # 2 đoạn giữ cách nhau ít hơn → gộp (bỏ vết cắt)
LAP_CUA_SO = 6.0       # cụm lặp trong 6 s
LAP_GIONG = 0.8
# nhịp cắt (AI chọn theo nội dung: TikTok/hướng dẫn nhanh → "nhanh"; tâm sự/podcast → "cham"): lặng tối đa, lặng giữ, cắt từ đệm
NHIP = {"nhanh": (0.3, 0.18, True), "vua": (0.4, 0.25, True), "cham": (0.7, 0.4, False)}

_ANH_XA = []           # [(a_goc, b_goc, tp_bat_dau)] của lần de_xuat gần nhất


def _sach(w):
    return chung.khong_dau(re.sub(r"[\W_]+", " ", w or "")).strip()


def _dur_wav(am16):
    try:
        with wave.open(am16, "rb") as f:
            return f.getnframes() / float(f.getframerate())
    except Exception:
        return 0.0


def _gop(ds):
    """gộp các khoảng [a,b,ly_do] chồng/chạm nhau"""
    ds = sorted([d for d in ds if d[1] > d[0]], key=lambda d: d[0])
    ra = []
    for d in ds:
        if ra and d[0] <= ra[-1][1] + 1e-6:
            if d[1] > ra[-1][1]:
                ra[-1][1] = d[1]
            if ra[-1][2] != d[2]:   # ưu tiên lý do: lap > dem > lang > ngan
                uu = {"lap": 3, "dem": 2, "lang": 1, "ngan": 0}
                ra[-1][2] = max(ra[-1][2], d[2], key=lambda k: uu.get(k, 0))
        else:
            ra.append(list(d))
    return ra


def _lang_an_toan(lang, tu, dur, dem=0.03):
    """khoảng lặng (năng lượng) trừ đi mọi từ (đệm 30 ms) → chỉ còn phần không dính lời; → [[a,b]]"""
    if not tu:
        return [[a, b] for a, b in lang]
    moc = sorted([(t["a"] - dem, t["b"] + dem) for t in tu])
    ra = []
    for a, b in lang:
        manh = [[a, b]]
        for ta, tb in moc:
            if tb <= a or ta >= b:
                continue
            moi = []
            for ma_, mb in manh:
                if tb <= ma_ or ta >= mb:
                    moi.append([ma_, mb])
                else:
                    if ta > ma_:
                        moi.append([ma_, ta])
                    if tb < mb:
                        moi.append([tb, mb])
            manh = moi
        ra.extend([m for m in manh if m[1] - m[0] > 0])
    return ra


def _tim_lap(tu, cau):
    """cụm lặp liền kề: câu giống ≥ 80 % trong 6 s (giữ lần sau) + n-gram từ 3..8 lặp y hệt → [[a,b,"lap"]]"""
    bo = []
    s_cau = [_sach(c["txt"]) for c in cau]
    for i in range(len(cau)):
        for j in range(i + 1, len(cau)):
            if cau[j]["a"] - cau[i]["a"] > LAP_CUA_SO:
                break
            if len(s_cau[i].split()) < 2:
                continue
            r = difflib.SequenceMatcher(None, s_cau[i].split(), s_cau[j].split()).ratio()
            if r >= LAP_GIONG:
                bo.append([cau[i]["a"], cau[i]["b"], "lap"])
                break
    s_tu = [_sach(t["w"]) for t in tu]
    n = len(tu)
    i = 0
    while i < n:
        tim = False
        for k in range(8, 2, -1):
            if i + 2 * k <= n and s_tu[i:i + k] == s_tu[i + k:i + 2 * k] and all(s_tu[i:i + k]) \
                    and tu[i + k]["a"] - tu[i]["a"] <= LAP_CUA_SO:
                bo.append([tu[i]["a"], tu[i + k]["a"], "lap"])
                i += k
                tim = True
                break
        if not tim:
            i += 1
    return bo


def tao_anh_xa(giu):
    """→ hàm giay_tp(a_goc) theo danh sách giữ [{a,b}]"""
    bang, c = [], 0.0
    for g in giu:
        bang.append((g["a"], g["b"], c))
        c += g["b"] - g["a"]

    def f(a):
        for ga, gb, c0 in bang:
            if a < ga:
                return round(c0, 3)
            if a <= gb:
                return round(c0 + (a - ga), 3)
        return round(c, 3)
    return f, bang


def giay_tp(a):
    """giây gốc → giây thành phẩm theo đề xuất cắt gần nhất (de_xuat đã chạy trong tiến trình này)"""
    if not _ANH_XA:
        return round(float(a), 3)
    c = 0.0
    for ga, gb, c0 in _ANH_XA:
        c = c0 + (gb - ga)
        if a < ga:
            return round(c0, 3)
        if a <= gb:
            return round(c0 + (a - ga), 3)
    return round(c, 3)


def nap_anh_xa(cat_json):
    """nạp ánh xạ từ cat-de-xuat.json (đường hoặc dict) để giay_tp dùng ở tiến trình khác"""
    global _ANH_XA
    d = chung.doc_json(cat_json, {}) if isinstance(cat_json, str) else (cat_json or {})
    _ANH_XA = [tuple(x) for x in d.get("anh_xa", [])]
    return giay_tp


def de_xuat(loi_json, am16, du_an=None, src=0, nhip=None):
    """loi_json: đường doc/loi.json (hoặc dict + du_an) → đường doc/cat-de-xuat.json
    {"giu":[{src,a,b}], "bo":[{a,b,ly_do}], "dur_goc", "dur_sau", "anh_xa":[[a,b,tp]], "nhip", "nhip_nguon"}
    nhip: AI/kênh truyền (nhanh|vua|cham); None → máy đề xuất theo bảng "vua" và ghi nhip_nguon="may_mac_dinh" (1.2.21: không ép "vua" lặng lẽ)"""
    nhip_nguon = "ai" if nhip in NHIP else "may_mac_dinh"
    global _ANH_XA
    if isinstance(loi_json, str):
        loi = chung.doc_json(loi_json, {}) or {}
        du_an = du_an or os.path.dirname(os.path.dirname(os.path.abspath(loi_json)))
    else:
        loi = loi_json or {}
    if not du_an:
        raise ValueError("cần du_an")
    dur = _dur_wav(am16) if am16 and os.path.isfile(am16) else 0.0
    dur = dur or float(loi.get("dur") or 0) or (loi["tu"][-1]["b"] if loi.get("tu") else 0.0)
    tu, cau = loi.get("tu", []), loi.get("cau", [])
    lang_toi_da, lang_giu, cat_dem = NHIP.get(nhip or "vua", NHIP["vua"])
    bo = []
    if tu:
        for a, b in _lang_an_toan(loi.get("lang", []), tu, dur):
            if b - a > lang_toi_da:
                bo.append([a + lang_giu / 2, b - lang_giu / 2, "lang"])
        if cat_dem:                 # "dem": ờ/à/ừm (lượt một + lượt hai nghe lại đoạn nghi) và đuôi từ đệm kéo dài ("keo_dai …")
            for d in loi.get("dem", []):
                bo.append([float(d[0]), float(d[1]), "dem"])
        bo.extend(_tim_lap(tu, cau))
    bo = _gop(bo)
    # đoạn giữ = phần bù
    giu, truoc = [], 0.0
    for a, b, _ in bo:
        if a > truoc:
            giu.append([truoc, a])
        truoc = max(truoc, b)
    if dur > truoc:
        giu.append([truoc, dur])
    # gộp đoạn giữ cách nhau < 0.15 s (xoá vết cắt tí hon)
    g2 = []
    for g in giu:
        if g2 and g[0] - g2[-1][1] < GOP_DUOI:
            g2[-1][1] = g[1]
        else:
            g2.append(list(g))
    # bỏ đoạn giữ < 0.6 s (đánh dấu "ngan") — trừ khi đoạn chứa chữ thật (cắt ờ dày đặc dễ để lại mảnh ngắn có lời)
    dem_ds = [(float(d[0]), float(d[1])) for d in loi.get("dem", [])] if cat_dem else []
    giua_chu = [(float(t["a"]) + float(t["b"])) / 2 for t in tu]
    giua_chu = [m for m in giua_chu if not any(a <= m <= b for a, b in dem_ds)]
    giu = []
    for g in g2:
        if g[1] - g[0] >= DOAN_TOI_THIEU or (len(g2) == 1) or any(g[0] <= m <= g[1] for m in giua_chu):
            giu.append(g)
        else:
            bo.append([g[0], g[1], "ngan"])
    bo = [d for d in _gop(bo) if not any(d[0] < g[1] and d[1] > g[0] for g in giu)]
    giu_ds = [{"src": src, "a": round(a, 3), "b": round(b, 3)} for a, b in giu]
    bo_ds = [{"a": round(a, 3), "b": round(b, 3), "ly_do": l} for a, b, l in bo]
    _, bang = tao_anh_xa(giu_ds)
    _ANH_XA = bang
    dur_sau = sum(g["b"] - g["a"] for g in giu_ds)
    ra = {"giu": giu_ds, "bo": bo_ds, "nhip": nhip or "vua", "nhip_nguon": nhip_nguon, "dur_goc": round(dur, 3), "dur_sau": round(dur_sau, 3),
          "anh_xa": [[round(a, 3), round(b, 3), round(c, 3)] for a, b, c in bang],
          "thong_ke": {"lang": sum(1 for d in bo_ds if d["ly_do"] == "lang"), "dem": sum(1 for d in bo_ds if d["ly_do"] == "dem"),
                       "lap": sum(1 for d in bo_ds if d["ly_do"] == "lap"), "ngan": sum(1 for d in bo_ds if d["ly_do"] == "ngan"),
                       "keo_dai": sum(1 for d in loi.get("dem", []) if cat_dem and str(d[2]).startswith("keo_dai"))}}
    p = os.path.join(du_an, "doc", "cat-de-xuat.json")
    chung.ghi_json(p, ra)
    chung.log(du_an, f"cắt đề xuất (nhịp {nhip or 'vua'}, {'AI/kênh chọn' if nhip_nguon == 'ai' else 'máy đề xuất — AI đổi bằng cong-thuc.nhip'}): "
                     f"{dur:.1f}s → {dur_sau:.1f}s, {len(giu_ds)} đoạn giữ, bỏ {ra['thong_ke']}")
    return p


if __name__ == "__main__":
    print(de_xuat(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
