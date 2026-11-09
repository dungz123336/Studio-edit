# -*- coding: utf-8 -*-
"""NGỮ PHÁP (tầng 2 của bộ học 1.2.20) — bản ghi thi công → các CÔNG THỨC có tên, có tham số, dùng lại được với chữ KHÁC:
  • cụm: trình tự vai trong cụm (nhãn → từ khoá → cảm xúc), tỉ lệ cỡ, so le/dx, trễ từng dòng, cách vào/ra từng dòng (kiểu, quãng,
    thời lượng, ease, nhoè), xoay, trước/sau người — gộp các cụm cùng chữ ký thành một công thức, tham số = trung vị
  • đặt: dải vị trí so với mặt (trên đầu / dưới cằm / ngang ngực, ×cao mặt), căn lề, tỉ lệ sau người
  • nhịp: cụm/10 s lời, thời lượng cụm, khoảng trống, cụm bám từ nào (lệch so với từ đầu), tối đa cụm cùng lúc
  • vai màu + chữ: màu/cỡ/đậm/HOA theo vai; nền: cắt, punch-in, flash, light-leak; tiếng động gắn lúc vào
  • KHÔNG mang chữ của video mẫu (chỉ số từ / số ký tự mỗi vai)
Máy chỉ gom và đếm. Chọn công thức nào cho câu nào là việc của AI lúc dựng.

  rut(ban_ghi: dict) → ngu_phap: dict ;  doc_duoc(ngu_phap) → [str]  (bản cho AI đọc)
"""
import os, sys, json, math, copy
from collections import Counter
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung as C

PHIEN_BAN = 2
TEN_VAI = {"nhan": "nhãn", "tu_khoa": "từ khoá", "cam_xuc": "cảm xúc", "phu": "phụ"}
# 1.2.21: trần số công thức / gộp lỏng / bản gọn đọc từ cau_hinh().get("hoc_ngu_phap", {}) — không còn số cứng trong mã
MAC_DINH_CFG = {"toi_da_cong_thuc": 14, "gop_long": True, "gon_toi_da": 6, "gon_dai_dong": 300, "it_nhat_lap": 2, "cum_it_thi_giu_het": 6}


def _cfg():
    c = dict(MAC_DINH_CFG)
    try:
        c.update((C.cau_hinh() or {}).get("hoc_ngu_phap") or {})
    except Exception:
        pass
    return c


def _loc_nghi_ngo(bg):
    """bỏ dòng mang `nguon_nghi_ngo` (web/canh/ao — dấu hiệu vật lý ban_ghi ghi) khỏi phần GOM; cụm không còn dòng thì bỏ.
    → (cụm đã lọc, thống kê nghi ngờ để AI vẫn thấy và tự quyết)"""
    cum, nn = [], {"so_dong": 0, "theo_nguon": {}, "cum_bo": [], "vi_du": []}
    for c in bg.get("cum") or []:
        ds = (c.get("noi_dung") or {}).get("dong") or []
        giu = [d for d in ds if not d.get("nguon_nghi_ngo")]
        for d in ds:
            if d.get("nguon_nghi_ngo"):
                nn["so_dong"] += 1
                nn["theo_nguon"][d["nguon_nghi_ngo"]] = nn["theo_nguon"].get(d["nguon_nghi_ngo"], 0) + 1
                if len(nn["vi_du"]) < 12:
                    nn["vi_du"].append(f"{c.get('id')}: «{(d.get('text') or '')[:30]}» ({d['nguon_nghi_ngo']})")
        if not giu:
            if ds:
                nn["cum_bo"].append(c.get("id"))
            continue
        if len(giu) != len(ds):
            c = copy.deepcopy(c); c["noi_dung"]["dong"] = giu
        cum.append(c)
    return cum, nn


def _tv(xs, n=2):
    xs = [float(x) for x in xs if x is not None]
    return round(float(np.median(xs)), n) if xs else None


def _mode(xs):
    xs = [x for x in xs if x is not None]
    return Counter(xs).most_common(1)[0][0] if xs else None


def _chu_ky_dong(d):
    an = d.get("anim") or {}
    v = an.get("vao") or {}
    tu = v.get("tu") or {}
    huong = ""
    if v.get("kieu") == "slide":
        x, y = tu.get("x", 0) or 0, tu.get("y", 0) or 0
        huong = ("xuong" if y < 0 else "len") if abs(y) >= abs(x) else ("phai" if x < 0 else "trai")
    elif v.get("kieu") == "pop":
        huong = "to" if (tu.get("scale") or 1) > 1 else "nho"
    return f"{v.get('kieu', 'fade')}{('-' + huong) if huong else ''}" + ("~" if an.get("nhoe_dong") else "")


def _chu_ky_cum(c):
    return " > ".join(f"{(d.get('_do') or {}).get('vai_cum', '?')}:{_chu_ky_dong(d)}" for d in c["noi_dung"]["dong"])


def _gop_anim(ds):
    """nhiều dòng cùng vai cùng chữ ký → anim trung vị (kiểu, dai, ease mode, tu x/y/scale trung vị, nhoè)"""
    vao = [((d.get("anim") or {}).get("vao") or {}) for d in ds]
    ra = [((d.get("anim") or {}).get("ra") or {}) for d in ds]
    kq = {}
    if any(vao):
        k = _mode([v.get("kieu") for v in vao if v])
        vs = [v for v in vao if v.get("kieu") == k]
        a = {"kieu": k, "dai": _tv([v.get("dai") for v in vs]), "ease": _mode([v.get("ease") for v in vs])}
        tu = {}
        for kk in ("x", "y", "scale", "opacity", "blur"):
            xs = [((v.get("tu") or {}).get(kk)) for v in vs]
            xs = [x for x in xs if x is not None]
            if xs:
                tu[kk] = _tv(xs, 2 if kk in ("scale", "opacity") else 0)
        if tu:
            a["tu"] = tu
        if k == "wipe":
            a["huong"] = _mode([v.get("huong") for v in vs])
        kq["vao"] = a
        tach = _mode([(d.get("anim") or {}).get("tach") for d in ds])
        if tach:
            kq["tach"] = tach; kq["so_le"] = _tv([(d.get("anim") or {}).get("so_le") for d in ds])
    if any(ra):
        k = _mode([r.get("kieu") for r in ra if r])
        rs = [r for r in ra if r.get("kieu") == k]
        a = {"kieu": k, "dai": _tv([r.get("dai") for r in rs]), "ease": _mode([r.get("ease") for r in rs])}
        toi = {}
        for kk in ("x", "y", "scale", "opacity", "blur"):
            xs = [((r.get("toi") or {}).get(kk)) for r in rs]
            xs = [x for x in xs if x is not None]
            if xs:
                toi[kk] = _tv(xs, 2 if kk in ("scale", "opacity") else 0)
        if toi:
            a["toi"] = toi
        kq["ra"] = a
    nh = [(d.get("anim") or {}).get("nhoe_dong") for d in ds]
    nh = [x for x in nh if x]
    if nh:
        kq["nhoe_dong"] = _tv(nh, 1)
    return kq


def _cong_thuc_cum(nhom, ten):
    """các cụm cùng chữ ký → một công thức: dòng theo thứ tự vai, tham số trung vị"""
    n_dong = len(nhom[0]["noi_dung"]["dong"])
    dong = []
    for i in range(n_dong):
        ds = [c["noi_dung"]["dong"][i] for c in nhom if len(c["noi_dung"]["dong"]) > i]
        co_max = [max(x["co"] for x in c["noi_dung"]["dong"]) for c in nhom]
        e = {"vai": _mode([(d.get("_do") or {}).get("vai_cum") for d in ds]),
             "co_so_voi_tu_khoa": round(float(np.median([d["co"] / max(m, 1) for d, m in zip(ds, co_max)])), 2),
             "co_px_tv": _tv([d["co"] for d in ds], 0), "dam": _mode([d.get("dam") for d in ds]), "hoa": _mode([bool(d.get("hoa")) for d in ds]),
             "mau": _mode([d.get("mau") for d in ds]), "tre": _tv([d.get("tre") for d in ds]),
             "so_tu_tv": _tv([len((d.get("text") or "").split()) for d in ds], 0), "so_ky_tu_tv": _tv([len(d.get("text") or "") for d in ds], 0),
             "font_goi_y": _mode([d.get("font_goi_y") for d in ds])}
        xo = [d.get("xoay") for d in ds if d.get("xoay")]
        if xo:
            e["xoay"] = _tv(xo, 1)
        dx = [d.get("dx") for d in ds if d.get("dx")]
        if dx:
            e["dx"] = _tv(dx, 0)
        if any(d.get("nen") for d in ds):
            e["nen"] = _mode([json.dumps(d.get("nen"), sort_keys=True) for d in ds if d.get("nen")])
            e["nen"] = json.loads(e["nen"])
        if any(d.get("vien") for d in ds):
            e["vien"] = True
        if any(d.get("bong") for d in ds):
            e["bong"] = True
        e["anim"] = _gop_anim(ds)
        dong.append(e)
    vt = [c.get("vi_tri") or {} for c in nhom]
    return {"ten": ten, "so_lan": len(nhom), "chu_ky": _chu_ky_cum(nhom[0]), "dong": dong,
            "dai_tv": _tv([c["t1"] - c["t0"] for c in nhom]), "can": _mode([(c.get("kieu_dang") or {}).get("can") for c in nhom]),
            "sau_nguoi": round(sum(1 for c in nhom if c.get("sau_nguoi")) / len(nhom), 2),
            "tieng_dong_luc_vao": round(sum(1 for c in nhom if c.get("am")) / len(nhom), 2),
            "dat": {"so_voi": _mode([v.get("so_voi") or "khung" for v in vt]), "anchor": _mode([v.get("anchor") for v in vt]),
                    "y": _tv([v.get("y") for v in vt]), "x": _tv([v.get("x") for v in vt])},
            "nhoe_dong": _tv([(c.get("anim") or {}).get("nhoe_dong") for c in nhom if (c.get("anim") or {}).get("nhoe_dong")], 1),
            "vi_du_id": [c["id"] for c in nhom[:4]]}


def rut(bg):
    cfg = _cfg()
    cum, nghi_ngo = _loc_nghi_ngo(bg)
    cum = [c for c in cum if c.get("noi_dung", {}).get("dong")]
    dur = float(bg.get("dur") or 1)
    np_ = {"phien_ban": PHIEN_BAN, "nguon": os.path.basename(str(bg.get("nguon"))), "dur": dur, "so_cum": len(cum),
           "so_dong": sum(len(c["noi_dung"]["dong"]) for c in cum), "nghi_ngo": nghi_ngo, "cau_hinh": cfg}
    # số đo TRUNG VỊ của mọi dòng còn lại — làm mặc định cho khung JSON mẫu (thay 60/600/#FFFFFF/0.95 cố định)
    tat_ca = [d for c in cum for d in c["noi_dung"]["dong"]]
    cd = [(c.get("_do") or {}).get("cach_dong") for c in cum if (c.get("_do") or {}).get("cach_dong")]
    np_["mac_dinh_do"] = {"co": _tv([d.get("co") for d in tat_ca], 0), "dam": _mode([d.get("dam") for d in tat_ca]),
                          "mau": _mode([d.get("mau") for d in tat_ca]), "cach_dong": _tv(cd, 2)}
    # ── 1) công thức cụm (gộp theo chữ ký vai+kiểu vào; rồi gộp lỏng theo trình tự vai nếu chữ ký quá lẻ)
    nhom = {}
    for c in cum:
        nhom.setdefault(_chu_ky_cum(c), []).append(c)
    ct = []
    le = []
    for ck, ds in sorted(nhom.items(), key=lambda kv: -len(kv[1])):
        if len(ds) >= int(cfg["it_nhat_lap"]) or len(cum) <= int(cfg["cum_it_thi_giu_het"]):
            ct.append(_cong_thuc_cum(ds, f"cum-{len(ct) + 1}"))
        else:
            le.append(ds[0])
    # gộp lỏng: cùng trình tự vai (bỏ kiểu vào)
    if cfg.get("gop_long", True):
        nhom2 = {}
        for c in le:
            k = " > ".join((d.get("_do") or {}).get("vai_cum", "?") for d in c["noi_dung"]["dong"])
            nhom2.setdefault(k, []).append(c)
        for k, ds in sorted(nhom2.items(), key=lambda kv: -len(kv[1])):
            ct.append(_cong_thuc_cum(ds, f"cum-{len(ct) + 1}"))
    ct.sort(key=lambda c: (-c["so_lan"], -len(c["dong"])))          # cụm nhiều dòng & lặp nhiều lên đầu (đó là chữ ký của phong cách)
    np_["so_cong_thuc_truoc_tran"] = len(ct)
    np_["cong_thuc_cum"] = ct[:int(cfg["toi_da_cong_thuc"])]
    for c in np_["cong_thuc_cum"]:
        c["cach_dong_do"] = _tv([(x.get("_do") or {}).get("cach_dong") for x in cum if x["id"] in c["vi_du_id"] and (x.get("_do") or {}).get("cach_dong")], 2)
    # ── 2) đặt so với mặt
    dat = Counter(((c.get("vi_tri") or {}).get("so_voi") or "khung") for c in cum)
    np_["dat"] = {"phan_bo": {k: round(v / max(len(cum), 1), 2) for k, v in dat.items()},
                  "tren_dau_y": _tv([(c["vi_tri"].get("y")) for c in cum if (c.get("vi_tri") or {}).get("so_voi") == "tren_dau"]),
                  "duoi_cam_y": _tv([(c["vi_tri"].get("y")) for c in cum if (c.get("vi_tri") or {}).get("so_voi") == "duoi_cam"]),
                  "can": {k: round(v / max(len(cum), 1), 2) for k, v in Counter((c.get("kieu_dang") or {}).get("can") for c in cum).items()},
                  "sau_nguoi": round(sum(1 for c in cum if c.get("sau_nguoi")) / max(len(cum), 1), 2),
                  "rong_cum_tv": _tv([(c.get("vi_tri") or {}).get("w") for c in cum])}
    # ── 3) nhịp
    cs = sorted(cum, key=lambda c: c["t0"])
    khe = [b["t0"] - a["t1"] for a, b in zip(cs, cs[1:])]
    cung_luc = 0
    for c in cs:
        cung_luc = max(cung_luc, sum(1 for x in cs if x["t0"] < c["t1"] and x["t1"] > c["t0"]))
    loi = [c.get("_loi") for c in cs if c.get("_loi")]
    np_["nhip"] = {"cum_moi_10s": round(len(cs) / dur * 10, 2), "dai_cum_tv": _tv([c["t1"] - c["t0"] for c in cs]),
                   "khe_tv": _tv([max(0, k) for k in khe]), "khe_max": round(max(khe), 2) if khe else None, "cung_luc_max": cung_luc,
                   "cum_dau_tien_giay": round(cs[0]["t0"], 2) if cs else None,
                   "lech_so_voi_tu_dau_tv": _tv([l.get("lech_tu_dau") for l in loi if l.get("lech_tu_dau") is not None]),
                   "so_tu_loi_moi_cum_tv": _tv([l.get("so_tu") for l in loi if l.get("so_tu")], 0),
                   "ti_le_cum_co_loi": round(sum(1 for l in loi if l.get("tu")) / max(len(cs), 1), 2) if loi else None}
    # ── 4) vai màu / chữ
    vai = {}
    for c in cum:
        for d in c["noi_dung"]["dong"]:
            v = (d.get("_do") or {}).get("vai_cum") or "?"
            vai.setdefault(v, []).append(d)
    np_["chu_theo_vai"] = {v: {"so": len(ds), "co_px_tv": _tv([d["co"] for d in ds], 0), "dam": _mode([d.get("dam") for d in ds]),
                               "hoa_ti_le": round(sum(1 for d in ds if d.get("hoa")) / len(ds), 2),
                               "mau": [m for m, _ in Counter(d.get("mau") for d in ds).most_common(3)],
                               "xoay_ti_le": round(sum(1 for d in ds if d.get("xoay")) / len(ds), 2),
                               "vao": [k for k, _ in Counter(_chu_ky_dong(d) for d in ds).most_common(3)],
                               "ra": [k for k, _ in Counter(((d.get("anim") or {}).get("ra") or {}).get("kieu") or "giu" for d in ds).most_common(3)],
                               "font_goi_y": _mode([d.get("font_goi_y") for d in ds])} for v, ds in vai.items()}
    mau = Counter()
    for c in cum:
        for d in c["noi_dung"]["dong"]:
            mau[d.get("mau")] += 1
    np_["bang_mau"] = [{"mau": m, "ti_le": round(n / max(sum(mau.values()), 1), 2)} for m, n in mau.most_common(5)]
    # ── 5) nền + tiếng
    np_["nen"] = {"so_cat": len(bg.get("cat") or []), "cat_moi_10s": round(len(bg.get("cat") or []) / dur * 10, 2),
                  "punch_in": len(bg.get("punch") or []), "flash": len(bg.get("flash") or []), "light_leak": len(bg.get("am_mau") or []),
                  "punch_gan_cum": round(sum(1 for z in (bg.get("punch") or []) if any(abs(z - c["t0"]) < 0.3 for c in cum)) / max(len(bg.get("punch") or []), 1), 2) if bg.get("punch") else None}
    np_["tieng_dong"] = {"ti_le_cum_co_tieng": round(sum(1 for c in cum if c.get("am")) / max(len(cum), 1), 2),
                         "so_onset": len(bg.get("onset_am") or [])}
    if bg.get("phu_de"):
        np_["phu_de"] = bg["phu_de"]
    np_["khong_chep"] = sorted({(d.get("text") or "")[:60] for c in cum for d in c["noi_dung"]["dong"] if d.get("text")})[:60]
    np_["ngu_phap_gon"] = gon(np_, int(cfg["gon_toi_da"]), int(cfg["gon_dai_dong"]))
    return np_


def _dong_gon(d, md):
    an = d.get("anim") or {}
    v = an.get("vao") or {}; r = an.get("ra") or {}
    tu = v.get("tu") or {}
    mo = (f"{v.get('kieu')} {v.get('dai')}s" + (f" {v.get('ease')}" if v.get("ease") else "")) if v else "fade"
    if tu.get("x") or tu.get("y"):
        mo += f" từ({int(tu.get('x', 0) or 0)},{int(tu.get('y', 0) or 0)})"
    if tu.get("scale"):
        mo += f" sc{tu['scale']}"
    if an.get("tach"):
        mo += f" tách {an['tach']}"
    return (f"{TEN_VAI.get(d['vai'], d['vai'])} ~{int(d.get('so_tu_tv') or 1)} từ {int(d.get('co_px_tv') or md.get('co') or 0)}px đậm {d.get('dam') or md.get('dam')}"
            + (" HOA" if d.get("hoa") else "") + f" {d.get('mau') or md.get('mau')}" + (f" xoay {d['xoay']}°" if d.get("xoay") else "")
            + (f" trễ {d['tre']}s" if d.get("tre") else "") + f" vào {mo}" + (f" ra {r.get('kieu')} {r.get('dai')}s" if r else "")
            + (" viền" if d.get("vien") else "") + (" bóng" if d.get("bong") else "") + (f" nền {d['nen'].get('mau')}" if d.get("nen") else ""))


def gon(np_, toi_da=6, dai_dong=300):
    """bản GỌN cho tóm tắt dựng (A4 in): ≤ `toi_da` công thức, mỗi dòng ≤ `dai_dong` ký tự — chỉ số đo, không chữ của mẫu"""
    md = np_.get("mac_dinh_do") or {}
    ra = []
    for c in (np_.get("cong_thuc_cum") or [])[:toi_da]:
        dat = c.get("dat") or {}
        neo = f"{dat.get('anchor')}({dat.get('x')},{dat.get('y')}" + (f" {dat['so_voi']}×mặt" if dat.get("so_voi") in ("tren_dau", "duoi_cam") else "") + ")"
        dau = (f"{c['ten']} ×{c['so_lan']} · {len(c['dong'])} dòng · ~{c.get('dai_tv')}s · căn {c.get('can')} · neo {neo}"
               + (f" · sau người {int(c['sau_nguoi'] * 100)}%" if c.get("sau_nguoi") else "") + (f" · cách dòng {c['cach_dong_do']}" if c.get("cach_dong_do") else "")
               + (f" · tiếng {int(c['tieng_dong_luc_vao'] * 100)}%" if c.get("tieng_dong_luc_vao") else ""))
        dong = " > ".join(_dong_gon(d, md) for d in c["dong"])
        s = dau + " · " + dong
        if len(s) > dai_dong:
            s = s[:dai_dong - 1] + "…"
        ra.append(s)
    return ra


# ─────────────────────────────────────────────────────────────── bản cho AI đọc
def _snippet(ctc, md=None):
    """công thức cụm → mẩu JSON lớp khoi mẫu (chữ thay bằng <vai>) để AI chép khung rồi điền chữ của mình.
    Thiếu số thì lấy TRUNG VỊ đo được của mẫu (`mac_dinh_do`), không còn 60/600/#FFFFFF/0.95 cố định."""
    md = md or {}
    dong = []
    for d in ctc["dong"]:
        e = {"text": f"<{d['vai']} ~{int(d.get('so_tu_tv') or 1)} từ>", "co": int(d.get("co_px_tv") or md.get("co") or 0), "dam": d.get("dam") or md.get("dam"), "mau": d.get("mau") or md.get("mau")}
        e = {k: v for k, v in e.items() if v not in (None, 0, "")}
        if d.get("hoa"):
            e["hoa"] = True
        if d.get("xoay"):
            e["xoay"] = d["xoay"]
        if d.get("dx"):
            e["dx"] = int(d["dx"])
        if d.get("tre"):
            e["tre"] = d["tre"]
        an = copy.deepcopy(d.get("anim") or {})
        if an:
            e["anim"] = an
        if d.get("nen"):
            e["nen"] = d["nen"]
        dong.append(e)
    kd = {"can": ctc.get("can") or "giua"}
    cd = ctc.get("cach_dong_do") or md.get("cach_dong")
    if cd:
        kd["cach_dong"] = cd
    l = {"kieu": "khoi", "noi_dung": {"dong": dong}, "kieu_dang": kd,
         "vi_tri": {"anchor": ctc["dat"].get("anchor") or "mc", "x": ctc["dat"].get("x"), "y": ctc["dat"].get("y")},
         "anim": {"tach": "dong", "so_le": 0.0}}
    if ctc["dat"].get("so_voi") in ("tren_dau", "duoi_cam"):
        l["vi_tri"].update({"so_voi": ctc["dat"]["so_voi"], "theo_mat": True})
    if ctc.get("nhoe_dong"):
        l["anim"]["nhoe_dong"] = ctc["nhoe_dong"]
    if ctc.get("sau_nguoi", 0) >= 0.5:
        l["sau_nguoi"] = True; l["ne_mat"] = False
    return json.dumps(l, ensure_ascii=False)


def doc_duoc(np_):
    L = [f"NGỮ PHÁP học từ {np_.get('nguon')} ({np_.get('dur')}s, {np_.get('so_cum')} cụm / {np_.get('so_dong')} dòng chữ). Số là trung vị đo được; "
         "chữ của mẫu KHÔNG chép — mỗi công thức là một khung có tham số, điền chữ của video này vào. Dùng công thức nào cho câu nào là việc của bạn."]
    L.append("CÔNG THỨC CỤM (theo số lần xuất hiện):")
    for c in np_.get("cong_thuc_cum") or []:
        dat = c["dat"]
        neo = f"{dat.get('anchor')} tại ({dat.get('x')}, {dat.get('y')})" + (f" so với {dat['so_voi']} (×cao mặt)" if dat.get("so_voi") in ("tren_dau", "duoi_cam") else "")
        L.append(f"- {c['ten']} ×{c['so_lan']} · {len(c['dong'])} dòng · dài ~{c['dai_tv']}s · căn {c.get('can')} · neo {neo}"
                 + (f" · SAU người {int(c['sau_nguoi'] * 100)}%" if c.get("sau_nguoi") else "") + (f" · nhoè {c['nhoe_dong']}" if c.get("nhoe_dong") else "")
                 + (f" · tiếng động lúc vào {int(c['tieng_dong_luc_vao'] * 100)}%" if c.get("tieng_dong_luc_vao") else ""))
        for d in c["dong"]:
            an = d.get("anim") or {}
            v = an.get("vao") or {}; r = an.get("ra") or {}
            tu = v.get("tu") or {}
            mo = f"{v.get('kieu')} {v.get('dai')}s {v.get('ease') or ''}".strip() if v else "fade"
            if tu.get("x") or tu.get("y"):
                mo += f" từ ({int(tu.get('x', 0) or 0)}, {int(tu.get('y', 0) or 0)})px"
            if tu.get("scale"):
                mo += f" scale {tu['scale']}"
            if an.get("nhoe_dong"):
                mo += f" nhoè {an['nhoe_dong']}"
            if an.get("tach"):
                mo += f" tách {an['tach']} so le {an.get('so_le')}"
            L.append(f"    · {TEN_VAI.get(d['vai'], d['vai'])}: ~{int(d.get('so_tu_tv') or 1)} từ, cỡ {d.get('co_px_tv')}px ({d['co_so_voi_tu_khoa']}× từ khoá), đậm {d.get('dam')}"
                     + (", HOA" if d.get("hoa") else "") + f", {d.get('mau')}" + (f", xoay {d['xoay']}°" if d.get("xoay") else "") + (f", dx {int(d['dx'])}" if d.get("dx") else "")
                     + f", trễ {d.get('tre')}s · vào {mo}" + (f" · ra {r.get('kieu')} {r.get('dai')}s" + (f" tới ({int((r.get('toi') or {}).get('x', 0) or 0)}, {int((r.get('toi') or {}).get('y', 0) or 0)})" if (r.get("toi") or {}).get("x") or (r.get("toi") or {}).get("y") else "") if r else " · ra: giữ tới hết")
                     + (f" · nền thẻ {d['nen'].get('mau')}" if d.get("nen") else "") + (f" · font: {d['font_goi_y']}" if d.get("font_goi_y") else ""))
        L.append(f"    khung JSON: {_snippet(c, np_.get('mac_dinh_do'))}")
    dat = np_.get("dat") or {}
    L.append("ĐẶT SO VỚI MẶT: " + ", ".join(f"{k} {int(v * 100)}%" for k, v in (dat.get("phan_bo") or {}).items())
             + (f"; trên đầu cách ~{dat['tren_dau_y']}×cao mặt" if dat.get("tren_dau_y") is not None else "")
             + (f"; dưới cằm cách ~{dat['duoi_cam_y']}×cao mặt" if dat.get("duoi_cam_y") is not None else "")
             + f"; căn lề {', '.join(f'{k} {int(v * 100)}%' for k, v in (dat.get('can') or {}).items())}; sau người {int((dat.get('sau_nguoi') or 0) * 100)}% cụm; rộng cụm ~{dat.get('rong_cum_tv')} khung")
    nh = np_.get("nhip") or {}
    L.append(f"NHỊP: {nh.get('cum_moi_10s')} cụm mỗi 10 s · mỗi cụm ~{nh.get('dai_cum_tv')}s · khe giữa cụm ~{nh.get('khe_tv')}s (lớn nhất {nh.get('khe_max')}s) · tối đa {nh.get('cung_luc_max')} cụm cùng lúc"
             + f" · cụm đầu tại {nh.get('cum_dau_tien_giay')}s" + (f" · cụm vào lệch ~{nh.get('lech_so_voi_tu_dau_tv')}s so với từ đầu nó bám, mỗi cụm phủ ~{nh.get('so_tu_loi_moi_cum_tv')} từ lời" if nh.get("lech_so_voi_tu_dau_tv") is not None else ""))
    L.append("CHỮ THEO VAI: " + " | ".join(f"{TEN_VAI.get(v, v)}: {x['so']} dòng, ~{x['co_px_tv']}px, đậm {x['dam']}, HOA {int(x['hoa_ti_le'] * 100)}%, màu {'/'.join(m for m in x['mau'] if m)}"
                                       + (f", xoay {int(x['xoay_ti_le'] * 100)}%" if x.get("xoay_ti_le") else "") + f", vào {'/'.join(x['vao'])}, ra {'/'.join(x['ra'])}" for v, x in (np_.get("chu_theo_vai") or {}).items()))
    L.append("BẢNG MÀU CHỮ: " + ", ".join(f"{m['mau']} {int(m['ti_le'] * 100)}%" for m in np_.get("bang_mau") or []))
    n = np_.get("nen") or {}
    L.append(f"NỀN: {n.get('so_cat')} cắt ({n.get('cat_moi_10s')}/10 s), {n.get('punch_in')} punch-in" + (f" ({int(n['punch_gan_cum'] * 100)}% trùng lúc cụm vào)" if n.get("punch_gan_cum") is not None else "")
             + f", {n.get('flash')} flash, {n.get('light_leak')} đoạn ám màu/light-leak")
    td = np_.get("tieng_dong") or {}
    L.append(f"TIẾNG ĐỘNG: {int((td.get('ti_le_cum_co_tieng') or 0) * 100)}% cụm có tiếng bật đúng lúc vào ({td.get('so_onset')} onset đo được)")
    if np_.get("phu_de"):
        p = np_["phu_de"]
        L.append(f"PHỤ ĐỀ: {p.get('so_cum')} cụm, cao dòng {p.get('cao_dong_ti_le')} khung, y {p.get('y')}, mỗi cụm ~{p.get('dai_tv')}s")
    nn = np_.get("nghi_ngo") or {}
    if nn.get("so_dong"):
        L.append(f"NGHI NGỜ (máy KHÔNG gom vào công thức, bạn quyết): {nn['so_dong']} dòng {nn.get('theo_nguon')} — web = màn hình/trang web quay lại, "
                 f"canh = chữ trong cảnh trôi cùng nền, ao = chữ in trên người; cụm bỏ hẳn: {', '.join(nn.get('cum_bo') or []) or 'không'}; ví dụ: " + "; ".join(nn.get("vi_du") or [])[:400])
    if np_.get("khong_chep"):
        L.append("KHÔNG CHÉP (chữ của mẫu): " + "; ".join(np_["khong_chep"][:25]))
    return L


def tu_thu_muc(tm, log=print):
    bg = C.doc_json(os.path.join(tm, "ban-ghi.json"), {}) or {}
    if not bg:
        return None
    np_ = rut(bg)
    p = os.path.join(tm, "ngu-phap.json")
    C.ghi_json(p, np_)
    pm = os.path.join(tm, "ngu-phap.md")
    with open(pm, "w", encoding="utf-8") as f:
        f.write("\n".join(doc_duoc(np_)))
    nn = np_.get("nghi_ngo") or {}
    log(f"  ngữ pháp: {len(np_['cong_thuc_cum'])} công thức cụm (gọn {len(np_.get('ngu_phap_gon') or [])}), bỏ qua {nn.get('so_dong', 0)} dòng nghi ngờ → {p}")
    return {"json": p, "md": pm, "ngu_phap": np_}


if __name__ == "__main__":
    kq = tu_thu_muc(sys.argv[1])
    if kq:
        print("\n".join(doc_duoc(kq["ngu_phap"])))
