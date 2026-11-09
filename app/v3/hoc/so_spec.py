# -*- coding: utf-8 -*-
"""SO HAI STYLE SPEC (D5) → điểm giống 0..1 theo từng phần + chi tiết lệch. Dùng để kiểm video dựng có giống mẫu không:
chạy dong_hoc trên THÀNH PHẨM → spec_may → so với spec_may của VIDEO MẪU (cùng thước đo máy, công bằng).

    python v3/hoc/so_spec.py a.json b.json                       # 2 spec (hoặc 2 dong_hoc.json — tự lấy spec_may)
    python v3/hoc/so_spec.py --video-mau mau.mp4 --video-dung ra.mp4 --thu-muc <thư mục>/so   # đo cả hai rồi so

Phần & trọng số: palette (ΔE CIE76 theo vai) · type_scale (tỉ lệ cỡ log2, đậm, HOA) · layout (khoảng cách neo theo vai + so_voi)
· motion (phân phối kiểu vào/ra — 1 − khoảng cách biến phân, + thời lượng, ease) · graphics (thẻ/chữ bool, hình) · rhythm (tương đối).
"""
import os, sys, json, math

V3 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if V3 not in sys.path:
    sys.path.insert(0, V3)
import chung as C

TRONG_SO = {"palette": 0.15, "type_scale": 0.15, "layout": 0.2, "motion": 0.25, "graphics": 0.1, "rhythm": 0.15}


def _de(a, b):
    try:
        from hoc.dong_hoc import delta_e
        return delta_e(a, b)
    except Exception:
        def lab(h):
            h = h.lstrip("#")[:6]
            r, g, b_ = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
            return r * 100, g * 100, b_ * 100
        return math.dist(lab(a), lab(b))


def _tb(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def so_palette(a, b, ct):
    pa, pb = a.get("palette") or {}, b.get("palette") or {}
    d = []
    for vai in ("nhan", "nhan2", "sang", "toi"):
        if pa.get(vai) and pb.get(vai):
            de = _de(pa[vai], pb[vai])
            d.append(max(0.0, 1 - de / 50))
            ct.append(f"palette.{vai}: {pa[vai]} vs {pb[vai]} ΔE={de:.0f}")
    return _tb(d)


def so_type(a, b, ct):
    ta, tb = a.get("type_scale") or {}, b.get("type_scale") or {}
    d = []
    for vai in ("tieu_de", "nhan", "phu_de"):
        x, y = ta.get(vai) or {}, tb.get(vai) or {}
        if not x or not y:
            if x or y:
                d.append(0.5); ct.append(f"type.{vai}: chỉ một bên có")
            continue
        p = []
        if x.get("co") and y.get("co"):
            r = abs(math.log2(float(x["co"]) / float(y["co"])))
            p.append(max(0.0, 1 - r)); ct.append(f"type.{vai}.co: {x['co']} vs {y['co']}")
        if x.get("dam") and y.get("dam"):
            p.append(max(0.0, 1 - abs(x["dam"] - y["dam"]) / 400))
        if x.get("hoa") is not None and y.get("hoa") is not None:
            p.append(1.0 if bool(x["hoa"]) == bool(y["hoa"]) else 0.0)
            if bool(x["hoa"]) != bool(y["hoa"]):
                ct.append(f"type.{vai}.hoa: {x['hoa']} vs {y['hoa']}")
        if p:
            d.append(sum(p) / len(p))
    return _tb(d)


def so_layout(a, b, ct):
    la = ((a.get("layout") or {}).get("anchors")) or []
    lb = ((b.get("layout") or {}).get("anchors")) or []
    if not la or not lb:
        return None
    d = []
    vai = {x["vai"] for x in la} | {x["vai"] for x in lb}
    for v in vai:
        xa = sorted([x for x in la if x["vai"] == v], key=lambda r: -(r.get("tan_suat") or 0))
        xb = sorted([x for x in lb if x["vai"] == v], key=lambda r: -(r.get("tan_suat") or 0))
        if not xa or not xb:
            d.append(0.3); ct.append(f"layout.{v}: chỉ một bên có"); continue
        p, q = xa[0], xb[0]
        kc = math.hypot(p["x"] - q["x"], p["y"] - q["y"])
        s = max(0.0, 1 - kc / 0.35)
        if (p.get("so_voi") or "khung") != (q.get("so_voi") or "khung"):
            s *= 0.7
        d.append(s)
        ct.append(f"layout.{v}: ({p['x']:.2f},{p['y']:.2f}/{p.get('so_voi')}) vs ({q['x']:.2f},{q['y']:.2f}/{q.get('so_voi')})")
    return _tb(d)


def _pb(ds):
    """[{kieu, tan_suat, do_may?}] → phân phối (dùng kiểu máy đo nếu có để phân biệt word_by_word/mask_reveal)"""
    p = {}
    for x in ds or []:
        k = x.get("do_may") or x.get("kieu")
        p[k] = p.get(k, 0) + float(x.get("tan_suat") or 1.0)
    t = sum(p.values()) or 1
    return {k: v / t for k, v in p.items()}


def so_motion(a, b, ct):
    ma, mb = a.get("motion_vocab") or {}, b.get("motion_vocab") or {}
    d = []
    for k in ("vao", "ra"):
        pa, pb = _pb(ma.get(k)), _pb(mb.get(k))
        if not pa or not pb:
            continue
        tv = 0.5 * sum(abs(pa.get(x, 0) - pb.get(x, 0)) for x in set(pa) | set(pb))
        s = 1 - tv
        # thời lượng của kiểu chính
        ka, kb = max(pa, key=pa.get), max(pb, key=pb.get)
        da = next((x.get("dai") for x in ma.get(k) if (x.get("do_may") or x.get("kieu")) == ka), None)
        db = next((x.get("dai") for x in mb.get(k) if (x.get("do_may") or x.get("kieu")) == kb), None)
        if da and db:
            s = 0.75 * s + 0.25 * max(0.0, 1 - abs(math.log2(max(da, 0.03) / max(db, 0.03))))
        d.append(s)
        ct.append(f"motion.{k}: {json.dumps({x: round(v, 2) for x, v in pa.items()})} vs {json.dumps({x: round(v, 2) for x, v in pb.items()})}")
    if ma.get("tach") and mb.get("tach"):
        d.append(1.0 if ma["tach"] == mb["tach"] else 0.4)
    return _tb(d)


def so_graphics(a, b, ct):
    ga, gb = a.get("graphics_vocab") or {}, b.get("graphics_vocab") or {}
    d = []
    for nhom in ("chu", "the"):
        x, y = ga.get(nhom) or {}, gb.get(nhom) or {}
        for k in set(x) & set(y):
            if isinstance(x[k], bool) and isinstance(y[k], bool):
                d.append(1.0 if x[k] == y[k] else 0.0)
                if x[k] != y[k]:
                    ct.append(f"graphics.{nhom}.{k}: {x[k]} vs {y[k]}")
            elif k == "hinh":
                d.append(1.0 if x[k] == y[k] else 0.3)
            elif isinstance(x[k], (int, float)) and isinstance(y[k], (int, float)):
                m = max(abs(x[k]), abs(y[k]), 1e-6)
                d.append(max(0.0, 1 - abs(x[k] - y[k]) / m))
    if ga.get("hinh_minh_hoa") and gb.get("hinh_minh_hoa"):
        d.append(1.0 if ga["hinh_minh_hoa"] == gb["hinh_minh_hoa"] else 0.5)
    return _tb(d)


def so_rhythm(a, b, ct):
    ra, rb = a.get("rhythm_rules") or {}, b.get("rhythm_rules") or {}
    d = []
    for k in ("giay_moi_lop_chu", "so_lop_dong_thoi_toi_da", "khoang_trong_toi_da_giay", "hook_giay", "phu_de_toi_da_chu"):
        if ra.get(k) is not None and rb.get(k) is not None:
            x, y = float(ra[k]), float(rb[k])
            m = max(abs(x), abs(y), 0.5)
            s = max(0.0, 1 - abs(x - y) / m)
            d.append(s)
            if s < 0.6:
                ct.append(f"rhythm.{k}: {x} vs {y}")
    if ra.get("phu_de") and rb.get("phu_de"):
        d.append(1.0 if ra["phu_de"] == rb["phu_de"] else 0.0)
        if ra["phu_de"] != rb["phu_de"]:
            ct.append(f"rhythm.phu_de: {ra['phu_de']} vs {rb['phu_de']}")
    return _tb(d)


def _spec(x):
    if isinstance(x, str):
        x = C.doc_json(x) or {}
    if "spec_may" in x and "su_kien" in x:        # dong_hoc.json
        return x["spec_may"]
    if "spec" in x and "palette" not in x:         # gói phong cách
        return x["spec"]
    if "style_spec" in x:                          # bài học hồ sơ
        return x["style_spec"]
    return x


def so(a, b):
    """a, b: dict spec | đường dẫn (spec / dong_hoc.json / bài học) → {"tong", "phan": {...}, "chi_tiet": [...]}"""
    a, b = _spec(a), _spec(b)
    ct = []
    phan = {"palette": so_palette(a, b, ct), "type_scale": so_type(a, b, ct), "layout": so_layout(a, b, ct),
            "motion": so_motion(a, b, ct), "graphics": so_graphics(a, b, ct), "rhythm": so_rhythm(a, b, ct)}
    co = {k: v for k, v in phan.items() if v is not None}
    w = sum(TRONG_SO[k] for k in co) or 1
    tong = sum(TRONG_SO[k] * v for k, v in co.items()) / w if co else 0.0
    return {"tong": round(tong, 3), "phan": {k: (None if v is None else round(v, 3)) for k, v in phan.items()}, "chi_tiet": ct}


def so_video(video_mau, video_dung, thu_muc, log=print):
    """đo động học cả hai (dùng lại nếu đã có) → so spec_may. Trả kết quả so + đường dẫn."""
    from hoc import dong_hoc as DH
    kq = {}
    for ten, v in (("mau", video_mau), ("dung", video_dung)):
        tm = os.path.join(thu_muc, ten)
        p = os.path.join(tm, "dong_hoc.json")
        dh = C.doc_json(p)
        if not dh or dh.get("video") != v or dh.get("phien_ban") != DH.PHIEN_BAN:
            dh = DH.phan_tich(v, tm, log=log)
        kq[ten] = dh
    r = so(kq["mau"], kq["dung"])
    r["mau"], r["dung"] = os.path.join(thu_muc, "mau", "dong_hoc.json"), os.path.join(thu_muc, "dung", "dong_hoc.json")
    C.ghi_json(os.path.join(thu_muc, "so-spec.json"), r)
    return r


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("a", nargs="?"); ap.add_argument("b", nargs="?")
    ap.add_argument("--video-mau"); ap.add_argument("--video-dung"); ap.add_argument("--thu-muc")
    x = ap.parse_args()
    if x.video_mau:
        r = so_video(x.video_mau, x.video_dung, x.thu_muc)
    else:
        r = so(x.a, x.b)
    print(json.dumps(r, ensure_ascii=False, indent=1))
