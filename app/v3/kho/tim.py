# -*- coding: utf-8 -*-
"""Tra cứu kho THEO NGHĨA: BM25 (bỏ dấu + cụm 2 âm tiết) trên tên + thư mục + từ khoá máy + NGHĨA AI (mo_ta, tu_khoa,
cong_dung, cam_xuc, phong_cach — kho/gan_nghia.py), mở rộng đồng nghĩa Anh↔Việt, điểm cộng khi khớp ĐÚNG DẤU.
Kết quả ĐA DẠNG: gom họ biến thể (tên bỏ số/_mp3/_wav/copy), giới hạn số mục cùng thư mục.

tim(loai=None, nghia="", n=5, tranh=[], cong_dung=None, hop_khung=None, nang_luong=None, dur=None,
    tranh_ho_so=None, da_dang=True, chi_ai=False) → [muc + "diem" (BM25 thô) + "diem_td" (0..1, theo đỉnh TỪNG LOẠI) + "khop"
                                                    + "chu_ky" (chuỗi vật lý, mọi loại) + "da_dung" (số dự án trên máy, 12 tháng) + "dur"]
    - loai "sfx" | "nen,video" … · cong_dung "chuyển cảnh" (khớp chuỗi con, bỏ dấu, với ai.cong_dung) hoặc list (khớp 1)
    - hop_khung "doc"|"ngang" (giữ cả "ca_hai"; mục chưa gắn AI xét theo w/h) · nang_luong 3 (±1) | (2,4) · dur (min,max) giây
    - tranh = id không lấy · tranh_ho_so = tên hồ sơ → bỏ id đã dùng ở N video gần nhất (kho/lich_su.py); lọc hết → bỏ lọc
    - SFX: từ tượng thanh Việt / từ khoá Anh (whoosh, pop, ding…) → nhân điểm theo số đo vật lý (kho/tai.py); từ ĐỘ TO (nhẹ/mạnh)
      ràng theo rms so với phân bố ứng viên và KHÔNG tính vào nghĩa. 1.2.21: bỏ phạt ×0,5 cho mục không chứa cụm 2 âm.
    - Máy KHÔNG chọn: trả n ứng viên kèm số đo; AI/công thức chọn. Ngưỡng tuyệt đối không có ở đây.
lay(id) → muc | None ;  tat_ca() ;  ho(muc) → khoá họ biến thể
ds(loai, q, trang, moi_trang, sap_xep, cong_dung=None) → {"tong","trang","moi_trang","muc","theo_loai"}  (UI)
cong_dung_ds(loai=None, n=40) → [(nhãn, số)]  (lọc theo công dụng trên UI)
thong_ke() → dict
Danh mục nạp từ SQLite (kho/csdl.py) 1 lần vào bộ nhớ (chỉ mục BM25 trong RAM), tự nạp lại khi phiên csdl đổi."""
import os, sys, math, threading, re, bisect
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung
from kho import dong_nghia, csdl
from kho import tai as _TAI            # 1.2.19: chữ ký vật lý + từ tượng thanh
from kho import lich_su as _LS         # 1.2.19: ít dùng nhất thắng khi điểm ngang

K1, B = 1.4, 0.7
CUNG_THU_MUC = 2          # tối đa mục cùng thư mục trong top-k khi da_dang (thiếu thì bù sau)
DIEM_TUONG_DOI = 0.18     # khi tra theo nghĩa: bỏ mục điểm < 18 % đỉnh loại (đuôi nhiễu)
BAC_IT_DUNG = 0.08        # mặc định; cấu hình v3.kho.bac_it_dung
_khoa = threading.Lock()
_bo = {"dau": None, "muc": [], "theo_id": {}, "df": {}, "post": {}, "dai": [], "tb": 1.0, "nhom_tk": [], "ten_kd": [],
       "co_dau": [], "theo_loai": {}, "tu_vung": [], "ho": [], "tm": []}


def bac_it_dung():
    try:
        v = float(_LS.cau_hinh_kho().get("bac_it_dung", BAC_IT_DUNG))
        return v if v > 0 else BAC_IT_DUNG
    except (TypeError, ValueError):
        return BAC_IT_DUNG


def _cap(tk):
    """cụm 2 âm tiết liền nhau ("dien thoai" → "dien_thoai") — tiếng Việt đa âm tiết"""
    return [a + "_" + b for a, b in zip(tk, tk[1:])]


def _cap_s(s):
    """cụm 2 âm tiết từ chuỗi, giữ âm tiết 1 chữ ("ý tưởng" → y_tuong)"""
    return _cap(dong_nghia.tach(s, giu_1=True))


def _mo_rong(q_tokens, q_txt):
    """đồng nghĩa Anh↔Việt: cụm Việt nhiều âm tiết đưa vào dưới dạng CỤM (bóng_đèn), không rã thành 'bong' + 'den'
    (rã ra sẽ khớp nhầm 'bóng đen'). → {token: trọng số}"""
    ng = dong_nghia._xay_nguoc()
    tk1 = dong_nghia.tach(q_txt, giu_1=True)
    en = set(t for t in q_tokens if t in dong_nghia.BANG)
    for i in range(len(tk1)):
        for k in (3, 2, 1):
            cum = tuple(tk1[i:i + k])
            if len(cum) == k and cum in ng:
                en |= ng[cum]
    ra = {}
    for e in en:
        ra.setdefault(e, 0.6)
        for v in dong_nghia.BANG.get(e, ()):
            tk = dong_nghia.tach(v, giu_1=True)
            if len(tk) == 1 and len(tk[0]) >= 2:
                ra.setdefault(tk[0], 0.6)
            for c in _cap(tk):
                ra.setdefault(c, 0.7)
    return ra


def _tu_co_dau(s):
    s = chung.NFC(s or "").lower()
    return [t for t in re.split(r"[^\wÀ-ỹđĐ]+", s) if t and not t.isascii()]


def _thu_muc(m):
    return "/".join(x for x in (m.get("rel") or "").split("/")[:-1] if chung.khong_dau(x) not in ("mp3", "wav"))


def _ban_sao(m):
    """khoá bản sao khác thư mục: cùng loại + tên chuẩn + kích thước/thời lượng (vd 'neon lights.mp4' ở 2 gói)"""
    sd = m.get("so_do") or {}
    return (m.get("loai"), chung.khong_dau(m.get("ten", "")).strip(), sd.get("w"), sd.get("h"), round(float(sd.get("dur") or 0)))


def ho(m):
    """khoá họ biến thể: loại + thư mục (bỏ mp3/wav) + tên bỏ số đuôi/định dạng/copy"""
    t = chung.khong_dau(m.get("ten", ""))
    t = re.sub(r"[\(\[]?\b(mp3|wav|copy|ban sao|final)\b[\)\]]?", " ", t)
    t = re.sub(r"[\s_\-.#]*\(?\d+\)?\s*$", "", t)
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return (m.get("loai"), _thu_muc(m), t)


def _tokens_muc(m):
    """→ (bag token có trọng số qua lặp, token nhóm, từ có dấu)"""
    ten_tk = dong_nghia.tach(m.get("ten", ""))
    nh = []
    for x in m.get("nhom", []):
        nh.extend(dong_nghia.tach(x))
    toks = list(m.get("tu_khoa", [])) + ten_tk * 2 + _cap_s(m.get("ten", "")) + nh
    co_dau = set(_tu_co_dau(m.get("ten", "")) + _tu_co_dau(" ".join(m.get("nhom", []))))
    ai = m.get("ai") or {}
    if ai:
        for k, w in (("tu_khoa", 2), ("mo_ta", 1), ("cong_dung", 2), ("cam_xuc", 1), ("phong_cach", 1), ("hop_vai", 1)):
            v = ai.get(k)
            if not v:
                continue
            txt = v if isinstance(v, str) else " ; ".join(v)
            for doan in re.split(r"[;,]", txt):
                tk = dong_nghia.tach(doan)
                toks.extend((tk + _cap_s(doan)) * w)
            co_dau.update(_tu_co_dau(txt))
        if ai.get("mau_chu_dao"):
            toks.extend(dong_nghia.tach(ai["mau_chu_dao"]))
    return toks, set(nh), co_dau


def _nap():
    """nạp lại từ SQLite nếu phiên csdl đổi (bảng muc/ai_nghia/lich_su có ghi) — chỉ mục BM25 giữ trong RAM"""
    try:
        dau = csdl.phien()
    except Exception:
        dau = None
    if dau == _bo["dau"] and _bo["dau"] is not None:
        return
    with _khoa:
        if dau == _bo["dau"] and _bo["dau"] is not None:
            return
        muc = csdl.tat_ca()
        post, dai, df, nhom_tk, ten_kd, co_dau_ds, theo_loai, ho_ds, tm_ds = {}, [], {}, [], [], [], {}, [], []
        for i, m in enumerate(muc):
            toks, nh, cd = _tokens_muc(m)
            d = {}
            for t in toks:
                d[t] = d.get(t, 0) + 1
            for t, f in d.items():
                df[t] = df.get(t, 0) + 1
                post.setdefault(t, []).append((i, f))
            dai.append(len(toks)); nhom_tk.append(nh); ten_kd.append(chung.khong_dau(m.get("ten", "")))
            co_dau_ds.append(cd); ho_ds.append(ho(m)); tm_ds.append(_thu_muc(m))
            theo_loai[m.get("loai")] = theo_loai.get(m.get("loai"), 0) + 1
        _bo.update({"dau": dau, "muc": muc, "theo_id": {m["id"]: m for m in muc}, "df": df, "post": post, "dai": dai,
                    "tb": (sum(dai) / len(dai)) if dai else 1.0, "nhom_tk": nhom_tk, "ten_kd": ten_kd, "co_dau": co_dau_ds,
                    "theo_loai": theo_loai, "tu_vung": sorted(post), "ho": ho_ds, "tm": tm_ds})


def nap_lai():
    _bo["dau"] = None
    _nap()


def lay(mid):
    _nap()
    return _bo["theo_id"].get(mid)


def tat_ca():
    _nap()
    return _bo["muc"]


def _tien_to(t):
    """token trong từ vựng bắt đầu bằng t (≥ 3 ký tự) — "whoo" → "whoosh" """
    tv = _bo["tu_vung"]
    i = bisect.bisect_left(tv, t)
    ra = []
    while i < len(tv) and tv[i].startswith(t) and len(ra) < 30:
        if tv[i] != t and "_" not in tv[i]:
            ra.append(tv[i])
        i += 1
    return ra


def _diem(nghia, them=None):
    """→ (list[(diem, i)] giảm dần, {i: set token gốc khớp}). them = [từ khoá Anh thêm từ từ tượng thanh] (trọng số 0.8).
    1.2.21: KHÔNG còn hạ nửa điểm mục không chứa cụm 2 âm tiết (cụm hiếm như 'rất nhẹ' từng át từ chính)."""
    q_tokens = dong_nghia.tach(nghia)
    q_cap = _cap_s(nghia)
    them = [t for t in (them or []) if t not in q_tokens]
    if not q_tokens and not q_cap and not them:
        return [], {}
    goc = set(q_tokens) | set(q_cap)
    trong_so = {t: w for t, w in _mo_rong(q_tokens, nghia).items() if t not in goc}   # đồng nghĩa nhẹ hơn từ gốc
    for t in them:
        trong_so.setdefault(t, 0.8)
    for t in q_tokens:
        trong_so[t] = 1.0
    for t in q_cap:
        trong_so[t] = 1.6                                     # khớp cả cụm 2 âm tiết: mạnh
    for t in q_tokens:
        if len(t) >= 3 and t not in _bo["post"]:
            for t2 in _tien_to(t):
                trong_so.setdefault(t2, 0.5)
    N = len(_bo["muc"]) or 1
    df, post, dai, tb = _bo["df"], _bo["post"], _bo["dai"], _bo["tb"]
    s, khop = {}, {}
    for t, w in trong_so.items():
        ds_ = post.get(t)
        if not ds_:
            continue
        n = df.get(t, 0)
        idf = math.log(1 + (N - n + 0.5) / (n + 0.5))
        for i, f in ds_:
            s[i] = s.get(i, 0.0) + w * idf * (f * (K1 + 1)) / (f + K1 * (1 - B + B * dai[i] / tb))
            if w >= 0.8:
                khop.setdefault(i, set()).add(t.replace("_", " "))
    q_kd = chung.khong_dau(nghia).strip()
    q_dau = set(_tu_co_dau(nghia))
    for i in list(s):
        if q_kd and len(q_kd) >= 3 and q_kd in _bo["ten_kd"][i]:
            s[i] += 2.0                                      # cả cụm nằm trong tên
        for t in q_tokens:
            if t in _bo["nhom_tk"][i]:
                s[i] += 0.6                                  # khớp nhóm (thư mục)
        if q_dau:
            s[i] += 0.5 * len(q_dau & _bo["co_dau"][i])      # khớp ĐÚNG DẤU ("bàn" ≠ "bản")
    ra = sorted(((v, i) for i, v in s.items() if v > 0), key=lambda x: -x[0])
    return ra, khop


# ----------------------------------------------------------------------------- lọc
def _khop_cong_dung(m, cd):
    if not cd:
        return True
    ai = m.get("ai") or {}
    nhan = [chung.khong_dau(x) for x in (ai.get("cong_dung") or [])]
    if not nhan:
        return False
    ds_ = [cd] if isinstance(cd, str) else list(cd)
    for c in ds_:
        c = chung.khong_dau(c).strip()
        if c and any(c in x or x in c for x in nhan if x):
            return True
    return False


def _khop_khung(m, hk):
    if not hk:
        return True
    hk = chung.khong_dau(hk)[:3]
    ai = (m.get("ai") or {}).get("hop_khung")
    if ai:
        return ai == "ca_hai" or ai.startswith(hk)
    sd = m.get("so_do") or {}
    w, h = sd.get("w"), sd.get("h")
    if not w or not h:
        return True
    return (h >= w) if hk == "doc" else (w >= h)


def _khop_nl(m, nl):
    if nl is None:
        return True
    v = (m.get("ai") or {}).get("nang_luong")
    if v is None:
        return True
    if isinstance(nl, (list, tuple)):
        return nl[0] <= v <= nl[1]
    return abs(v - int(nl)) <= 1


def _khop_dur(m, dur):
    if not dur:
        return True
    d = (m.get("so_do") or {}).get("dur")
    if d is None:
        return True
    a, b = (dur if isinstance(dur, (list, tuple)) else (dur, None))
    return (a is None or d >= a) and (b is None or d <= b)


def _loc(m, loai_ds, tranh, cong_dung, hop_khung, nang_luong, dur, chi_ai):
    if loai_ds and m.get("loai") not in loai_ds:
        return False
    if m["id"] in tranh:
        return False
    if chi_ai and not m.get("ai"):
        return False
    return _khop_cong_dung(m, cong_dung) and _khop_khung(m, hop_khung) and _khop_nl(m, nang_luong) and _khop_dur(m, dur)


BO_TU_LOAI = {"icon": {"icon", "bieu", "tuong"}, "nhac": {"nhac", "music", "bgm"}, "sfx": {"sfx", "tieng", "am", "thanh", "hieu", "ung", "sound"},
              "nen": {"nen", "background", "bg"}, "font": {"font", "phong"}, "lut": {"lut"}, "video": {"video", "clip"}, "anh": {"anh", "hinh"}}


def _bo_tu(q, tu_ds):
    """bỏ các từ/cụm (có dấu) khỏi câu — cụm dài trước"""
    s = " " + re.sub(r"\s+", " ", chung.NFC(q)) + " "
    for t in sorted(tu_ds, key=lambda x: -len(x)):
        s = re.sub(r"(?i)\s" + re.escape(t) + r"(?=\s)", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def tim(loai=None, nghia="", n=5, tranh=None, cong_dung=None, hop_khung=None, nang_luong=None, dur=None,
        tranh_ho_so=None, da_dang=True, chi_ai=False):
    """top-n theo nghĩa, đa dạng, có lọc. Kết quả: dict mục + diem + diem_td + khop + chu_ky + da_dung + dur"""
    _nap()
    tranh = set(tranh or [])
    if tranh_ho_so:
        try:
            tranh |= set(_LS.gan_day(tranh_ho_so))
        except Exception:
            pass
    muc = _bo["muc"]
    loai_ds = set(loai.split(",")) if isinstance(loai, str) and loai else (set(loai) if loai else None)
    q = nghia or ""
    if loai_ds:                                   # "icon điện thoại" → bỏ từ chỉ loại, chỉ còn nghĩa thật
        bo = set().union(*[BO_TU_LOAI.get(l, set()) for l in loai_ds])
        tk = dong_nghia.tach(q)
        loc = [t for t in tk if t not in bo]
        if loc and len(loc) < len(tk):
            q = " ".join(loc)
    # ràng buộc vật lý (chỉ SFX): tra trên câu GỐC ("tiếng ngắn": 'tiếng' là ngữ cảnh); từ ĐỘ TO là ràng buộc, không phải nghĩa → bỏ khỏi câu tra
    rb, en = _TAI.rang_buoc(nghia) if (q.strip() and loai_ds and loai_ds <= {"sfx"}) else (None, [])
    if rb:
        q2 = _bo_tu(q, _TAI.tu_do_to(rb))
        q = q2 if (q2 or en) else q
    ds_diem, khop = _diem(q, them=en)
    dem = _LS.dem_toan_may()                       # R3 1.2.21: nạp 1 lần / lượt (trước: da_dang=False → {} → _ket_qua gọi lại từng mục, mỗi lần mở SQLite ~2 ms)
    if not ds_diem and not q.strip():             # không nghĩa: theo lọc, mục có AI trước, ít dùng trước
        ds_diem = [(0.0, i) for i, m in enumerate(muc)]
        ds_diem.sort(key=lambda x: (0 if muc[x[1]].get("ai") else 1, dem.get(muc[x[1]]["id"], 0), chung.khong_dau(muc[x[1]].get("ten", ""))))
    # 1.2.19: LỌC TRƯỚC (loại/tránh/công dụng/khung/độ dài) rồi mới xét ràng buộc vật lý, ngưỡng tương đối và bậc ít dùng — bậc tính trên
    # đúng tập ứng viên (không lấy đỉnh của loại khác), ngưỡng không cắt sớm mục điểm cao đứng sau
    ds_diem = [(s_, i) for s_, i in ds_diem if _loc(muc[i], loai_ds, tranh, cong_dung, hop_khung, nang_luong, dur, chi_ai)]
    if rb and ds_diem:                             # "tinh", "bùm", "vút", whoosh, pop… → điểm nhân theo số đo vật lý — chỉ SFX
        dau = ds_diem[:300]                        # chỉ ~300 ứng viên đầu (đủ cho n ≤ 60; không nhân cả kho)
        do_duoc = sum(1 for _, i in dau if (muc[i].get("so_do") or {}).get("pho_hz") is not None)
        if do_duoc >= 0.8 * len(dau):              # kho chưa đo xong (máy mới) → không nhân, kẻo tệp chưa đo nổi lên trên tệp đã đo
            ng_to = _TAI.nguong_to([muc[i] for _, i in dau]) if rb.get("to") else None   # 1.2.21: độ to so với phân bố ứng viên
            dau = sorted(((s_ * _TAI.he_so(muc[i], rb, ng_to), i) for s_, i in dau), key=lambda x: -x[0])
            ds_diem = dau + ds_diem[300:]
        if rb.get("dai_s") and not dur:            # "ngắn"/"dài"/"xoẹt"… = ĐỘ DÀI đo được → lọc cứng (tra nghĩa bỏ dấu khớp nhầm "ngân" cho "ngắn");
            lo, hi = rb["dai_s"]                   # không đủ ứng viên trong khoảng → giữ như cũ
            def _vua(i):
                d_ = (muc[i].get("so_do") or {}).get("dur")
                return d_ is not None and (lo is None or float(d_) >= lo) and (hi is None or float(d_) <= hi)
            loc_dai = [x for x in ds_diem if _vua(x[1])]
            if len(loc_dai) >= min(n, 3):
                ds_diem = loc_dai
    # 1.2.21: chuẩn hoá theo ĐỈNH TỪNG LOẠI → diem_td 0..1 (tra "nen,video": loại ít từ khoá không bị loại kia át; ngưỡng/bậc tính trên diem_td)
    dinh = {}
    for s_, i in ds_diem:
        l = muc[i].get("loai")
        if s_ > dinh.get(l, 0.0):
            dinh[l] = s_
    td = {i: (s_ / dinh[muc[i].get("loai")] if dinh.get(muc[i].get("loai")) else 0.0) for s_, i in ds_diem}
    if q.strip() and not cong_dung and ds_diem and ds_diem[0][0] > 0:   # ngưỡng tương đối theo đỉnh loại (có lọc công dụng thì bộ lọc đã bảo đảm nghĩa)
        ds_diem = [x for x in ds_diem if td[x[1]] >= DIEM_TUONG_DOI]
    if da_dang and ds_diem and ds_diem[0][0] > 0:  # điểm xấp xỉ nhau (cùng bậc của đỉnh loại) → tệp ÍT DÙNG trên máy này đứng trước
        buoc = bac_it_dung()
        ds_diem.sort(key=lambda x: (-int(td[x[1]] // buoc), dem.get(muc[x[1]]["id"], 0), -x[0]))
    else:
        ds_diem.sort(key=lambda x: -td[x[1]])
    ra, ho_da, tm_dem, de_sau, sao_da = [], set(), {}, [], set()
    for s, i in ds_diem:
        m = muc[i]
        if da_dang:
            h = _bo["ho"][i]
            bs = _ban_sao(m)
            if h in ho_da or bs in sao_da:
                continue
            sao_da.add(bs)
            tm = _bo["tm"][i]
            if tm_dem.get(tm, 0) >= CUNG_THU_MUC:
                de_sau.append((s, i))
                continue
            ho_da.add(h); tm_dem[tm] = tm_dem.get(tm, 0) + 1
        ra.append(_ket_qua(m, s, td[i], khop.get(i, ()), dem))
        if len(ra) >= n:
            break
    if len(ra) < n and de_sau:                    # thiếu → bù mục cùng thư mục (vẫn khác họ)
        for s, i in de_sau:
            h = _bo["ho"][i]
            if h in ho_da:
                continue
            ho_da.add(h)
            ra.append(_ket_qua(muc[i], s, td[i], khop.get(i, ()), dem))
            if len(ra) >= n:
                break
        ra.sort(key=lambda m: -m["diem_td"])
    if not ra and tranh_ho_so and tranh:          # 1.2.19: lịch sử N video phủ hết loại này (bộ kèm nhỏ) → bỏ lọc tránh thay vì trả rỗng
        return tim(loai, nghia, n, None, cong_dung, hop_khung, nang_luong, dur, None, da_dang, chi_ai)
    return ra


def _ket_qua(m, s, s_td, khop, dem):
    """mục + diem (thô) + diem_td (0..1 theo đỉnh loại) + khop + chu_ky (chuỗi vật lý, MỌI loại) + da_dung (số dự án trên máy, 12 tháng) + dur"""
    r = dict(m, diem=round(s, 2), diem_td=round(s_td, 3), khop=sorted(khop))
    r["chu_ky"] = _TAI.mo_ta_muc(m)
    r["da_dung"] = (dem if dem is not None else _LS.dem_toan_may()).get(m["id"], 0)
    d = (m.get("so_do") or {}).get("dur")
    r["dur"] = round(float(d), 2) if d is not None else None
    return r


# ----------------------------------------------------------------------------- UI
UU_TIEN = {"nhac": 0, "sfx": 1, "font": 2, "nen": 3, "icon": 4, "video": 5, "lut": 6, "preset_capcut": 7, "anh": 8, "khac": 9}


def _khoa_sap(sap_xep):
    if sap_xep == "moi":
        return lambda m: -m.get("mtime", 0), False
    if sap_xep == "dai":
        return lambda m: -(m.get("so_do", {}).get("dur") or 0), False
    if sap_xep == "ngan":
        return lambda m: (m.get("so_do", {}).get("dur") if m.get("so_do", {}).get("dur") is not None else 1e9), False
    if sap_xep == "nhom":
        return lambda m: (chung.khong_dau(" ".join(m.get("nhom", []))), chung.khong_dau(m["ten"])), False
    if sap_xep == "dam":
        return lambda m: -(m.get("so_do", {}).get("dam") or 0), False
    if sap_xep == "nang_luong":
        return lambda m: -((m.get("ai") or {}).get("nang_luong") or 0), False
    return lambda m: (UU_TIEN.get(m["loai"], 9), chung.khong_dau(m["ten"])), False


def ds(loai=None, q="", trang=1, moi_trang=60, sap_xep="ten", cong_dung=None, chua_dung=False):
    """danh sách cho UI: lọc loại (+ công dụng), tìm q (xếp theo điểm nếu có q, không thì theo sap_xep), phân trang.
    1.2.19: chua_dung=True → chỉ mục chưa video nào trên máy dùng; sap_xep "it_dung" → ít dùng trước."""
    _nap()
    muc = _bo["muc"]
    loai_ds = set(loai.split(",")) if loai else None
    q = (q or "").strip()
    if q:                                        # 1.2.21: cùng xếp hạng với tim() (ràng buộc vật lý SFX, điểm theo đỉnh loại) — UI thấy đúng thứ AI thấy
        ket = tim(loai_ds, q, n=len(muc), da_dang=False)
        if sap_xep and sap_xep not in ("ten", "", "diem"):
            k, _ = _khoa_sap(sap_xep); ket.sort(key=k)
    else:
        ket = [m for m in muc if not loai_ds or m["loai"] in loai_ds]
        k, _ = _khoa_sap(sap_xep); ket = sorted(ket, key=k)
    if cong_dung:
        ket = [m for m in ket if _khop_cong_dung(m, cong_dung)]
    if chua_dung or sap_xep == "it_dung":
        dem = _LS.dem_toan_may()
        if chua_dung:
            ket = [m for m in ket if not dem.get(m["id"])]
        if sap_xep == "it_dung":
            ket = sorted(ket, key=lambda m: (dem.get(m["id"], 0), chung.khong_dau(m.get("ten", ""))))
    tong = len(ket)
    trang = max(1, int(trang or 1)); moi_trang = max(1, min(500, int(moi_trang or 60)))
    a = (trang - 1) * moi_trang
    return {"tong": tong, "trang": trang, "moi_trang": moi_trang, "muc": ket[a:a + moi_trang], "theo_loai": dict(_bo["theo_loai"])}


def _gon_cd(c):
    """'icon minh hoạ từ 'tiền'' → 'icon minh hoạ'"""
    return re.sub(r"\s*(từ|tu)\s*['\"‘“].*$", "", c).strip()


def cong_dung_ds(loai=None, n=40):
    """nhãn công dụng AI phổ biến (gộp bỏ dấu; 'icon minh hoạ từ ...' gộp về 'icon minh hoạ') → [(nhãn, số)]"""
    _nap()
    loai_ds = set(loai.split(",")) if loai else None
    dem, ten = {}, {}
    for m in _bo["muc"]:
        if loai_ds and m["loai"] not in loai_ds:
            continue
        thay = set()
        for c in (m.get("ai") or {}).get("cong_dung") or []:
            c2 = _gon_cd(c)
            k = chung.khong_dau(c2)
            if not k or k in thay:
                continue
            thay.add(k)
            dem[k] = dem.get(k, 0) + 1
            ten.setdefault(k, c2)
    return [(ten[k], v) for k, v in sorted(dem.items(), key=lambda kv: -kv[1])[:n] if v >= 2]


def thong_ke():
    _nap()
    cm = chung.doc_json(os.path.join(chung.duong("kho_chi_muc"), "chi-muc.json"), {}) or {}
    ra = dict(cm)
    ra["tong"] = len(_bo["muc"])
    ra["theo_loai"] = dict(sorted(_bo["theo_loai"].items()))
    ra["font_du_dau"] = sum(1 for m in _bo["muc"] if m.get("loai") == "font" and m.get("du_dau"))
    ra["co_ai"] = sum(1 for m in _bo["muc"] if m.get("ai"))
    try:
        ra["csdl"] = csdl.thong_ke()
    except Exception:
        pass
    return ra


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "tai-font":          # kho tai-font "Montserrat" [300,800]
        from kho import font_mang as _FM
        dam = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else None
        ds_ = _FM.tai(sys.argv[2], dam)
        for m in tim("font", sys.argv[2], 12):
            print(f"  {m['id']}  đậm {(m.get('so_do') or {}).get('dam')}  nghiêng {(m.get('so_do') or {}).get('nghieng')}  đủ dấu {m.get('du_dau')}")
        print(f"XONG: {len(ds_)} tệp — dùng `font: \"{sys.argv[2]}\"` hoặc id ở trên")
        sys.exit(0)
    loai = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "-" else None
    nghia = " ".join(sys.argv[2:])
    for m in tim(loai, nghia, 8):
        ai = m.get("ai") or {}
        ck = (" · chữ ký: " + m["chu_ky"]) if m.get("chu_ky") else ""
        print(f"{m['diem_td']:5.2f} ({m['diem']:5.2f})  {m['id'][:44]:44s} {m['ten'][:28]:28s} | {ai.get('mo_ta', '')[:58]}  {ai.get('cong_dung', '')}")
        print(f"        đã dùng {m.get('da_dung', 0)} dự án{ck}")
