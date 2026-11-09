# -*- coding: utf-8 -*-
"""GÓI KHO CHO TỪNG VIDEO (1.2.21) — máy chỉ trả BẢNG DỮ LIỆU đo được, KHÔNG tra theo câu cố định, không đoán cảm xúc, không chấm gu.

goi(du_an, ghi=True, anh=True) → dict  (ghi <du_an>/doc/kho-video.json + ảnh bảng <du_an>/doc/kho-video.jpg)
  kho        kho có loại gì / bao nhiêu · đã gắn nghĩa AI bao nhiêu · nhãn công dụng AI phổ biến theo loại (để AI tự viết câu tra)
  bang[loai] = [{"theo", "mo_ta", "muc": [...]}]  top-N mỗi bảng theo SỐ ĐO TRUNG TÍNH:
      nhac   ít dùng · đủ dài (≥ 90 % video) · năng lượng AI 1–2 / 3 / 4–5
      sfx    ít dùng · bật+khô · bật+ngân · dâng dần · cao · trầm · chuỗi · nhiễu/gió · ngắn ≤ 0,8 s · dài ≥ 2,5 s   (chữ ký kho/tai.py)
      icon   ít dùng · có alpha
      nen    hợp khung (ít dùng trước) · động (video) · tĩnh (ảnh) · có alpha
      font   đủ dấu ít dùng · đủ dấu đậm ≥ 700 · nghiêng · biến thiên
      lut    ít dùng
    mỗi mục kèm `chu_ky` (chuỗi vật lý), `da_dung` (số dự án trên máy, 12 tháng), `ho_so_da_dung` (số video trong N video gần
    nhất của hồ sơ), `dur`, `cong_dung`/`nang_luong`/`de_doc` (nhãn AI đã gắn — dữ liệu, không phải gợi ý).
  nhac/icon/nen/lut = danh sách gộp (không trùng) của các bảng loại đó; sfx = {theo: [mục]} (nhóm theo chữ ký) — giữ hình dạng
  cũ cho cong_thuc._NhomSfx / nao.kiem / doc.tom_tat; font = {"so", "du_dau", "bang", "font_khoa_ho_so"}.
  cum_loi    cụm lời kèm giây thành phẩm (dữ liệu để AI gắn icon/sfx theo lời; AI tự tra: `python v3/kho/tim.py <loại> "<nghĩa>"`).
Số mục mỗi bảng = cau_hinh v3.kho.so_ung_vien (8). Lịch sử chống lặp = v3.kho.n_lich_su (30) — chỉ ĐẾM, không loại bỏ.

    python v3/kho/goi_video.py <du_an>
"""
import os, sys, re, json, time, glob
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung
from kho import tim as T, lich_su, tai as _TAI

SO_UNG_VIEN = 8


def so_ung_vien():
    try:
        return max(1, int(lich_su.cau_hinh_kho().get("so_ung_vien", SO_UNG_VIEN)))
    except (TypeError, ValueError):
        return SO_UNG_VIEN


# ----------------------------------------------------------------------------- đọc dự án
def _doc(du_an):
    d = os.path.join(du_an, "doc")
    viec = chung.doc_json(os.path.join(du_an, "viec.json"), {}) or {}
    loi = chung.doc_json(os.path.join(d, "loi.json"), {}) or {}
    catj = chung.doc_json(os.path.join(d, "cat-de-xuat.json"), {}) or {}
    return viec, loi, catj


def _ho_so(ten):
    """→ dict gọn: font_khoa, mau, profile_mau (dữ liệu hồ sơ — không đọc gu)"""
    if not ten:
        return {}
    tm = os.path.join(chung.duong("ho_so"), ten)
    hs = chung.doc_json(os.path.join(tm, "ho-so.json"), {}) or {}
    ch = chung.doc_json(os.path.join(tm, "cau-hinh.json"), {}) or {}
    ra = {"ten": ten}
    fk = hs.get("font_khoa") or {k: v for k, v in (ch.get("chu") or {}).items() if not k.startswith("_") and v}
    if fk:
        ra["font_khoa"] = fk
    mau = hs.get("mau_khoa") or {k: v for k, v in (ch.get("mau") or {}).items() if not k.startswith("_") and v}
    if mau:
        ra["mau"] = mau
    ra["profile_mau"] = ((ch.get("quay") or {}).get("profile_mau")) or "thuong"
    return ra


def _cum_loi(tu, giu, toi_da=12, toi_thieu=5):
    """từ → cụm (a_tp, b_tp, chữ) theo dấu câu / nghỉ > 0,5 s, bỏ từ trong vùng cắt"""
    from doc import cat as _cat
    f_tp = _cat.tao_anh_xa(giu)[0] if giu else (lambda a: round(a, 3))

    def giu_tu(t):
        return any(g["a"] - 0.02 <= t["a"] and t["b"] <= g["b"] + 0.02 for g in giu) if giu else True
    ws = [t for t in tu if giu_tu(t)]
    ra, hien = [], []
    for i, t in enumerate(ws):
        hien.append(t)
        ket = bool(re.search(r"[.!?…,]$", t["w"]))
        nghi = i + 1 < len(ws) and ws[i + 1]["a"] - t["b"] > 0.5
        if len(hien) >= toi_da or ((ket or nghi) and len(hien) >= toi_thieu) or i == len(ws) - 1:
            ra.append((f_tp(hien[0]["a"]), f_tp(hien[-1]["b"]), " ".join(x["w"] for x in hien)))
            hien = []
    return ra


# ----------------------------------------------------------------------------- lịch sử
def _dong_bo_lich_su(ho_so, du_an_nay):
    """ghi lịch sử cho các dự án cùng hồ sơ đã có cong-thuc.json (tối đa N dự án mới nhất) — để số đếm đúng ngay cả khi điều phối
    chưa gọi lich_su.ghi_tu_du_an sau giao"""
    if not ho_so:
        return 0
    da = lich_su.du_an_da_ghi(ho_so)
    goc = chung.duong("du_an")
    ds = []
    for p in glob.glob(os.path.join(goc, "*", "cong-thuc.json")):
        tm = os.path.dirname(p)
        if os.path.normcase(tm) == os.path.normcase(os.path.abspath(du_an_nay)):
            continue
        ds.append((os.path.getmtime(p), tm))
    ds.sort(reverse=True)
    n = 0
    for _, tm in ds[:lich_su.n_lich_su()]:
        if os.path.basename(tm) in da:
            continue
        v = chung.doc_json(os.path.join(tm, "viec.json"), {}) or {}
        if v.get("ho_so") == ho_so:
            try:
                if lich_su.ghi_tu_du_an(tm, ho_so):
                    n += 1
            except Exception:
                pass
    return n


# ----------------------------------------------------------------------------- mục gọn
def _gon(m, dem, tranh):
    ai = m.get("ai") or {}
    sd = m.get("so_do") or {}
    r = {"id": m["id"], "ten": m.get("ten"), "mo_ta": ai.get("mo_ta") or m.get("ten"), "chu_ky": _TAI.mo_ta_muc(m),
         "da_dung": dem.get(m["id"], 0)}
    if m["id"] in tranh:
        r["ho_so_da_dung"] = tranh[m["id"]]
    if sd.get("dur") is not None:
        r["dur"] = round(float(sd["dur"]), 2)
    if m["loai"] == "nhac":
        for k in ("bpm", "lufs"):
            if sd.get(k) is not None:
                r[k] = sd[k]
    if m["loai"] in ("nen", "video", "icon", "anh") and sd.get("w"):
        r["kich"] = f"{sd['w']}x{sd['h']}" + (" alpha" if sd.get("alpha") else "")
    if m["loai"] == "font":
        r["dam"] = sd.get("dam"); r["nghieng"] = bool(sd.get("nghieng")); r["du_dau"] = bool(m.get("du_dau"))
        if ai.get("de_doc") is not None:
            r["de_doc"] = ai["de_doc"]
    for k in ("cong_dung", "cam_xuc", "phong_cach"):
        if ai.get(k):
            r[k] = list(ai[k])[:3]
    if ai.get("nang_luong") is not None:
        r["nang_luong"] = ai["nang_luong"]
    if ai.get("hop_khung"):
        r["hop_khung"] = ai["hop_khung"]
    return r


def _khac_ho(ds, n, dem):
    """n mục ÍT DÙNG trước, khác họ biến thể / khác bản sao (tên+cỡ) — thứ tự ổn định theo tên"""
    ds = sorted(ds, key=lambda m: (dem.get(m["id"], 0), chung.khong_dau(m.get("ten", ""))))
    ra, ho_da, sao_da = [], set(), set()
    for m in ds:
        h = T.ho(m)
        bs = T._ban_sao(m)
        if h in ho_da or bs in sao_da:
            continue
        ho_da.add(h); sao_da.add(bs); ra.append(m)
        if len(ra) >= n:
            break
    return ra


def _bang(ten, mo_ta, ds, n, dem, tranh):
    return {"theo": ten, "mo_ta": mo_ta, "so_hop": len(ds), "muc": [_gon(m, dem, tranh) for m in _khac_ho(ds, n, dem)]}


def _bang_loai(muc, loai_ds, dur_video, khung_doc, n, dem, tranh):
    """các bảng số đo cho 1 loại → [bảng]"""
    ds = [m for m in muc if m.get("loai") in loai_ds]
    if not ds:
        return []
    ck = {m["id"]: _TAI.chu_ky(m.get("so_do")) for m in ds} if "sfx" in loai_ds else {}
    sd = lambda m: m.get("so_do") or {}
    ai = lambda m: m.get("ai") or {}
    B = []
    if "nhac" in loai_ds:
        can = max(15.0, min(dur_video * 0.9, 150.0))
        B.append(_bang("it_dung", "ít dùng nhất trên máy", ds, n, dem, tranh))
        B.append(_bang("du_dai", f"dài ≥ {can:.0f} s (≈ 90 % video), ít dùng trước", [m for m in ds if float(sd(m).get("dur") or 0) >= can], n, dem, tranh))
        for ten, mo, lo, hi in (("nang_luong_1_2", "năng lượng AI 1–2", 1, 2), ("nang_luong_3", "năng lượng AI 3", 3, 3), ("nang_luong_4_5", "năng lượng AI 4–5", 4, 5)):
            B.append(_bang(ten, mo, [m for m in ds if ai(m).get("nang_luong") is not None and lo <= ai(m)["nang_luong"] <= hi], n, dem, tranh))
    elif "sfx" in loai_ds:
        B.append(_bang("it_dung", "ít dùng nhất trên máy", ds, n, dem, tranh))
        for ten, mo, dk in (("bat_kho", "bật ngay (tấn công ≤ 25 ms) + khô (tắt ≤ 150 ms)", lambda c: c.get("bat") == "bat" and c.get("ngan") == "kho"),
                            ("bat_ngan", "bật ngay + ngân (≥ 350 ms)", lambda c: c.get("bat") == "bat" and c.get("ngan") == "ngan"),
                            ("dang", "dâng dần (tấn công ≥ 120 ms)", lambda c: c.get("bat") == "dang"),
                            ("cao", "phổ cao (≥ 2200 Hz)", lambda c: c.get("cao") == "cao"),
                            ("tram", "phổ trầm (≤ 700 Hz)", lambda c: c.get("cao") == "tram"),
                            ("chuoi", "chuỗi nhiều tiếng (≥ 3)", lambda c: c.get("tieng") == "chuoi"),
                            ("nhieu", "nhiễu/gió (phẳng phổ ≥ 0,35)", lambda c: c.get("chat") == "nhieu"),
                            ("ngan", "ngắn ≤ 0,8 s", lambda c: c.get("dai") == "ngan"),
                            ("dai", "dài ≥ 2,5 s", lambda c: c.get("dai") == "dai")):
            B.append(_bang(ten, mo + " · ít dùng trước", [m for m in ds if dk(ck[m["id"]])], n, dem, tranh))
    elif "icon" in loai_ds:
        B.append(_bang("it_dung", "ít dùng nhất trên máy", ds, n, dem, tranh))
        B.append(_bang("alpha", "có kênh trong suốt (alpha)", [m for m in ds if sd(m).get("alpha")], n, dem, tranh))
    elif "nen" in loai_ds:
        hk = "doc" if khung_doc else "ngang"
        B.append(_bang("hop_khung", f"hợp khung {hk} (đo w/h hoặc AI hop_khung), ít dùng trước", [m for m in ds if T._khop_khung(m, hk)], n, dem, tranh))
        B.append(_bang("dong", "động (video có thời lượng)", [m for m in ds if sd(m).get("dur")], n, dem, tranh))
        B.append(_bang("tinh", "tĩnh (ảnh)", [m for m in ds if not sd(m).get("dur")], n, dem, tranh))
        B.append(_bang("alpha", "có alpha", [m for m in ds if sd(m).get("alpha")], n, dem, tranh))
    elif "font" in loai_ds:
        du = [m for m in ds if m.get("du_dau")]
        B.append(_bang("du_dau_it_dung", "đủ dấu tiếng Việt, ít dùng trước", du, n, dem, tranh))
        B.append(_bang("du_dau_dam", "đủ dấu, đậm ≥ 700", [m for m in du if (sd(m).get("dam") or 0) >= 700], n, dem, tranh))
        B.append(_bang("du_dau_nghieng", "đủ dấu, nghiêng", [m for m in du if sd(m).get("nghieng")], n, dem, tranh))
        B.append(_bang("du_dau_bien_thien", "đủ dấu, font biến thiên (trục đậm)", [m for m in du if sd(m).get("var")], n, dem, tranh))
    elif "lut" in loai_ds:
        B.append(_bang("it_dung", "ít dùng nhất trên máy", ds, n, dem, tranh))
    return B


def _gop(bang_ds):
    """gộp các bảng → danh sách mục không trùng, mỗi mục ghi `bang` = các bảng nó thuộc về"""
    ra, idx = [], {}
    for b in bang_ds:
        for x in b["muc"]:
            if x["id"] in idx:
                ra[idx[x["id"]]]["bang"].append(b["theo"])
            else:
                idx[x["id"]] = len(ra); ra.append(dict(x, bang=[b["theo"]]))
    return ra


# ----------------------------------------------------------------------------- ảnh bảng
def _anh_bang(goi_d, dich):
    """lưới icon / nền-lớp phủ / font / LUT trong gói, mỗi ô có id → 1 ảnh AI Read là thấy"""
    from PIL import Image, ImageDraw
    from kho import gan_nghia
    f_tieu, f_id = gan_nghia._font_nhan(22), gan_nghia._font_nhan(13)
    W, pad = 1500, 8
    phan = []   # (tiêu đề, [(muc, nhãn phụ)], kiểu)
    if goi_d["icon"]:
        phan.append(("ICON (ít dùng / alpha)", [(T.lay(x["id"]), ",".join(x.get("bang", []))) for x in goi_d["icon"]], "o"))
    if goi_d["nen"]:
        phan.append(("NỀN / LỚP PHỦ", [(T.lay(x["id"]), ",".join(x.get("bang", []))) for x in goi_d["nen"]], "o"))
    fonts = [(T.lay(x["id"]), f"đậm {x.get('dam')}" + (" nghiêng" if x.get("nghieng") else "")) for b in goi_d["font"].get("bang", []) for x in b["muc"]]
    seen = set(); fonts = [f for f in fonts if f[0] and not (f[0]["id"] in seen or seen.add(f[0]["id"]))]
    if fonts:
        phan.append(("FONT (đủ dấu)", fonts, "f"))
    if goi_d["lut"]:
        phan.append(("LUT trái gốc / phải sau", [(T.lay(x["id"]), "") for x in goi_d["lut"]], "l"))
    khoi = []
    for tieu, ds, kieu in phan:
        cot, ow, oh = {"o": (7, 204, 204), "f": (3, 492, 120), "l": (4, 366, 206)}[kieu]
        hang = (len(ds) + cot - 1) // cot
        H = 34 + hang * (oh + 36 + pad)
        im = Image.new("RGB", (W, H), (20, 20, 24))
        dr = ImageDraw.Draw(im)
        dr.text((pad, 4), tieu, font=f_tieu, fill=(255, 210, 0))
        for i, (m, phu) in enumerate(ds):
            if not m:
                continue
            r, c = divmod(i, cot)
            x0, y0 = pad + c * (ow + pad), 34 + r * (oh + 36 + pad)
            try:
                a = gan_nghia._anh_o(m)
            except Exception:
                a = None
            o = Image.new("RGB", (ow, oh), (40, 40, 46))
            if a is not None:
                a = a.copy(); a.thumbnail((ow, oh), Image.LANCZOS)
                xx, yy = (ow - a.width) // 2, (oh - a.height) // 2
                if a.mode == "RGBA":
                    ca = gan_nghia._caro(a.width, a.height).convert("RGBA"); ca.alpha_composite(a); o.paste(ca.convert("RGB"), (xx, yy))
                else:
                    o.paste(a, (xx, yy))
            im.paste(o, (x0, y0))
            dr.rectangle([x0, y0 + oh, x0 + ow, y0 + oh + 34], fill=(10, 10, 12))
            idt = m["id"]
            while dr.textlength(idt, font=f_id) > ow - 6 and len(idt) > 8:
                idt = idt[:-2]
            dr.text((x0 + 3, y0 + oh + 2), idt if idt == m["id"] else idt + "…", font=f_id, fill=(235, 235, 240))
            if phu:
                dr.text((x0 + 3, y0 + oh + 18), str(phu)[:40], font=f_id, fill=(150, 200, 255))
        khoi.append(im)
    if not khoi:
        return None
    H = sum(k.height for k in khoi)
    bang = Image.new("RGB", (W, H), (20, 20, 24))
    y = 0
    for k in khoi:
        bang.paste(k, (0, y)); y += k.height
    bang.save(dich, quality=85)
    return dich


# ----------------------------------------------------------------------------- chính
def goi(du_an, ghi=True, anh=True):
    t0 = time.time()
    du_an = os.path.abspath(du_an)
    viec, loi, catj = _doc(du_an)
    ten = os.path.basename(du_an)
    ho_so_ten = viec.get("ho_so") or ""
    hs = _ho_so(ho_so_ten)
    try:   # lịch sử: ghi dự án này nếu đã dựng (gọi lại sau giao) + đồng bộ các dự án cùng hồ sơ → số đếm đúng
        if os.path.isfile(os.path.join(du_an, "cong-thuc.json")):
            lich_su.ghi_tu_du_an(du_an, ho_so_ten)
        _dong_bo_lich_su(ho_so_ten, du_an)
    except Exception:
        pass
    n_ls = lich_su.n_lich_su()
    tranh = lich_su.gan_day(ho_so_ten, n_ls, bo=ten)
    dem = lich_su.dem_toan_may()
    n = so_ung_vien()

    tu, giu = loi.get("tu", []), catj.get("giu", [])
    dur = float(catj.get("dur_sau") or loi.get("dur") or 60)
    try:
        cum = _cum_loi(tu, giu) if tu else []
    except Exception:
        cum = []
    noi = sum(c["b"] - c["a"] for c in loi.get("cau", [])) or dur
    toc = len(tu) / noi * 60 if noi else 0
    khung = viec.get("khung") or [1080, 1920]
    khung_doc = khung[1] >= khung[0]

    muc = T.tat_ca()
    theo_loai = {}
    chua = {}
    for m in muc:
        theo_loai[m["loai"]] = theo_loai.get(m["loai"], 0) + 1
        if m["loai"] in ("nhac", "sfx", "icon", "nen", "video", "font", "lut") and not m.get("ai"):
            chua[m["loai"]] = chua.get(m["loai"], 0) + 1
    g = {"du_an": ten, "luc": time.strftime("%Y-%m-%d %H:%M:%S"), "ho_so": ho_so_ten, "khung": khung, "dur": round(dur, 1),
         "toc_do_noi": round(toc), "so_ung_vien": n, "n_lich_su": n_ls, "tranh_lich_su": len(tranh),
         "kho": {"tong": len(muc), "theo_loai": dict(sorted(theo_loai.items())), "co_ai": sum(1 for m in muc if m.get("ai")),
                 "chua_gan_nghia": chua, "font_du_dau": sum(1 for m in muc if m["loai"] == "font" and m.get("du_dau")),
                 "cong_dung": {l: T.cong_dung_ds(l, 12) for l in ("sfx", "nhac", "icon", "nen", "font", "lut") if theo_loai.get(l)}}}
    bang = {}
    for khoa, loai_ds in (("nhac", {"nhac"}), ("sfx", {"sfx"}), ("icon", {"icon"}), ("nen", {"nen", "video"}), ("font", {"font"}), ("lut", {"lut"})):
        bang[khoa] = _bang_loai(muc, loai_ds, dur, khung_doc, n, dem, tranh)
    g["bang"] = bang
    g["nhac"] = _gop(bang["nhac"])
    g["sfx"] = {b["theo"]: b["muc"] for b in bang["sfx"] if b["muc"]}
    g["icon"] = _gop(bang["icon"])
    g["nen"] = [dict(x, nhom=x["bang"][0], nhom_ten=x["bang"][0]) for x in _gop(bang["nen"])]
    g["font"] = {"so": theo_loai.get("font", 0), "du_dau": g["kho"]["font_du_dau"], "bang": bang["font"]}
    if hs.get("font_khoa"):
        g["font"]["font_khoa_ho_so"] = hs["font_khoa"]
    if hs.get("mau"):
        g["mau_ho_so"] = hs["mau"]
    g["profile_mau"] = hs.get("profile_mau", "thuong")
    g["cho_chinh_mau"] = bool(viec.get("cho_chinh_mau"))
    g["lut"] = _gop(bang["lut"])
    g["cum_loi"] = [{"a": round(a, 2), "b": round(b, 2), "chu": c[:120]} for a, b, c in cum][:80]
    g["tong"] = len(g["nhac"]) + sum(len(v) for v in g["sfx"].values()) + len(g["icon"]) + len(g["nen"]) + len(g["lut"]) \
        + sum(len(b["muc"]) for b in bang["font"])
    g["chua_gan_nghia"] = sum(chua.values())
    g["huong_dan"] = ("BẢNG SỐ ĐO của kho, máy không chọn hộ. `kho` = kho có gì/bao nhiêu + nhãn công dụng AI phổ biến; `bang[loai]` = top "
                      f"{n} mỗi bảng theo số đo (ít dùng, dài, năng lượng, chữ ký tiếng, đủ dấu, khung) — mỗi mục có `chu_ky` (đo), `da_dung` "
                      f"(số dự án trên máy, 12 tháng), `ho_so_da_dung` (số video trong {n_ls} video gần nhất của hồ sơ: để bạn tự thấy lặp). "
                      "Cần đúng NGHĨA (icon 'điện thoại', sfx 'tinh chuông cao ngân', nhạc 'piano chậm') → tự tra: "
                      "`python v3/kho/tim.py <loai> \"<nghĩa>\"` (trả top-8 kèm diem_td, chữ ký, đã dùng) rồi ghi id vào công thức "
                      "(am.nhac.id, am.sfx[].id, hinh.noi_dung.duong, the.noi_dung.icon, nen_moi kho, font). `cum_loi` = cụm lời + giây "
                      "thành phẩm để gắn icon/sfx theo lời. LUT: `cho_chinh_mau` false = người dùng chưa cho chỉnh màu.")
    d = os.path.join(du_an, "doc")
    os.makedirs(d, exist_ok=True)
    if anh:
        try:
            p = _anh_bang(g, os.path.join(d, "kho-video.jpg"))
            g["anh"] = os.path.relpath(p, du_an).replace("\\", "/") if p else None
        except Exception as ex:
            g["anh"] = None; g["loi_anh"] = str(ex)[:160]
    g["giay_chon"] = round(time.time() - t0, 2)
    if ghi:
        chung.ghi_json(os.path.join(d, "kho-video.json"), g)
    return g


if __name__ == "__main__":
    g = goi(sys.argv[1])
    print(json.dumps({k: (v if k not in ("sfx", "font", "bang") else {kk: (len(vv) if isinstance(vv, list) else vv) for kk, vv in v.items()})
                      if not isinstance(v, list) else len(v) for k, v in g.items()}, ensure_ascii=False, indent=1))
