# -*- coding: utf-8 -*-
"""DÒNG THỜI GIAN MẪU — máy sinh từ dong_hoc.json (số đo), không AI: mỗi sự kiện chữ/đồ hoạ của video mẫu thành một dòng đọc được
(lúc nào, vai gì, mấy dòng, cỡ, màu, ở đâu so với mặt, vào/ra kiểu gì), kèm punch-in / cắt nhảy. AI lúc dựng thấy NHỊP và THỨ TỰ
thật của mẫu để tự quyết áp vào lời của video mới. Không có luật, không có ngưỡng.

  tu_dong_hoc(dh: dict) → [str]      tu_thu_muc(thu_muc_video_mau) → [str]
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung

VAI = {"tieu_de": "tiêu đề", "nhan": "nhãn/nhấn", "phu_de": "phụ đề", "do_hoa": "đồ hoạ", "the": "thẻ"}
VI_TRI = {"ngang_mat": "ngang mặt", "tren_dau": "trên đầu", "duoi_cam": "dưới cằm", "tren_mat": "trên mặt", "duoi_mat": "dưới mặt",
          "ben_mat": "bên mặt", "nguc": "ngang ngực", "khong_mat": "không có mặt trong khung"}


def _f(x, n=1):
    try:
        return f"{float(x):.{n}f}"
    except Exception:
        return "?"


def _mo_ta(e):
    t = e.get("tinh") or {}
    svm = t.get("so_voi_mat") or {}
    phan = []
    sd = t.get("so_dong") or e.get("so_dong_tho")
    if sd:
        phan.append(f"{sd} dòng")
    if t.get("co_uoc_1920"):
        phan.append(f"~{int(t['co_uoc_1920'])}px")
    hoa = t.get("hoa")
    if hoa is True or hoa == "hoa":
        phan.append("HOA")
    elif hoa == "hon_hop":
        phan.append("hoa+thường")
    if t.get("dam_uoc"):
        phan.append(f"đậm~{t['dam_uoc']}")
    if t.get("mau_chu"):
        phan.append("màu " + str(t["mau_chu"]) + (f"+{t['mau_chu_2']}" if t.get("mau_chu_2") and t["mau_chu_2"] != t["mau_chu"] else ""))
    if t.get("vien_chu"):
        phan.append("viền")
    if t.get("bong_chu"):
        phan.append("bóng")
    nen = t.get("nen") or {}
    if isinstance(nen, dict) and nen.get("hinh"):
        phan.append(f"nền thẻ {nen.get('hinh')}")
    vt = []
    if svm.get("vi_tri"):
        vt.append(VI_TRI.get(svm["vi_tri"], str(svm["vi_tri"])))
        try:
            lx = float(svm.get("lech_x_theo_rong_mat") or 0)
            if abs(lx) >= 0.3:
                vt.append(f"lệch {'phải' if lx > 0 else 'trái'} {abs(lx):.1f}×rộng mặt")
        except Exception:
            pass
        try:
            kc = float(svm.get("khoang_theo_cao_mat") or 0)
            if abs(kc) >= 0.05:
                vt.append(f"cách {abs(kc):.1f}×cao mặt")
        except Exception:
            pass
        if svm.get("che_mat"):
            vt.append("CHE mặt")
    elif t.get("tam"):
        vt.append(f"tâm ({_f(t['tam'][0], 2)}, {_f(t['tam'][1], 2)})")
    sn = t.get("so_voi_nguoi") or {}
    try:
        ch = int(round(float(sn.get("chong") or 0) * 100))
    except Exception:
        ch = 0
    if sn.get("lop") == "sau":
        vt.append(f"nằm SAU người (người che {ch}% khối)")
    elif sn.get("lop") == "truoc" and ch >= 4:
        vt.append(f"đè TRƯỚC người ({ch}% khối trên người)")
    if t.get("anchor"):
        vt.append(f"neo {t['anchor']}")
    dong = []
    for k, ten in (("vao", "vào"), ("ra", "ra")):
        v = e.get(k) or {}
        if v.get("kieu"):
            d = f"{ten} {v['kieu']}"
            if v.get("dai"):
                d += f" {_f(v['dai'], 2)}s"
            if v.get("ease") and v["ease"] != "linear":
                d += f" {v['ease']}"
            if v.get("huong"):
                d += f" {v['huong']}"
            if (v.get("dac_trung") or {}).get("tu_du"):
                d += f" ({v['dac_trung']['tu_du']} từ lần lượt)" if v.get("kieu") in ("word_by_word", "typewriter") else ""
            dong.append(d)
    return "; ".join(x for x in (", ".join(phan), ", ".join(vt), ", ".join(dong)) if x)


def tu_dong_hoc(dh, toi_da=60):
    if not isinstance(dh, dict):
        return []
    L = []
    dur = dh.get("dur")
    sk = sorted([e for e in (dh.get("su_kien") or []) if isinstance(e, dict)], key=lambda e: float(e.get("t_vao", 0) or 0))
    pd = [e for e in sk if e.get("vai") == "phu_de" and not e.get("bo_qua")]
    khac = [e for e in sk if not (e.get("vai") == "phu_de" and not e.get("bo_qua"))]
    for e in khac:
        t0, t1 = _f(e.get("t_vao")), _f(e.get("t_ra"))
        vai = VAI.get(e.get("vai"), str(e.get("vai")))
        if e.get("bo_qua"):
            hop = e.get("hop_tho") or []
            vt = f" vùng x {_f(hop[0], 2)}–{_f(hop[2], 2)}, y {_f(hop[1], 2)}–{_f(hop[3], 2)}" if len(hop) == 4 else ""
            L.append(f"{t0}–{t1}s {vai}: lớp chữ/ảnh chèn máy không đọc được chữ{vt}")
            continue
        L.append(f"{t0}–{t1}s {vai}: {_mo_ta(e)}")
    if pd:
        if len(pd) <= 4:
            for e in pd:
                L.append(f"{_f(e.get('t_vao'))}–{_f(e.get('t_ra'))}s phụ đề: {_mo_ta(e)}")
        else:
            dai = [float(e.get("t_ra", 0)) - float(e.get("t_vao", 0)) for e in pd]
            L.append(f"phụ đề: {len(pd)} cụm đo được từ {_f(pd[0].get('t_vao'))}s tới {_f(pd[-1].get('t_ra'))}s, mỗi cụm ~{_f(sum(dai) / len(dai), 2)}s; cụm tiêu biểu: {_mo_ta(pd[len(pd) // 2])}")
    for z in (dh.get("zoom_cat") or []):
        try:
            L.append(f"{float(z):.1f}s: punch-in (cắt cận)")
        except Exception:
            pass
    cat = dh.get("cat") or []
    if isinstance(cat, list) and cat:
        moc = []
        for c in cat:
            try:
                moc.append(float(c if not isinstance(c, dict) else (c.get("t") or c.get("a"))))
            except Exception:
                pass
        if moc:
            L.append("cắt nhảy tại: " + ", ".join(f"{m:.1f}s" for m in moc[:20]) + ("…" if len(moc) > 20 else ""))
    dh_ = [g for g in (dh.get("do_hoa_tho") or []) if isinstance(g, dict) and g.get("xuat_hien") and not g.get("co_chu")]
    if dh_:
        L.append("đồ hoạ không chữ xuất hiện tại: " + ", ".join(f"{_f(g.get('t'))}s" for g in dh_[:15]))
    if dur:
        L.insert(0, f"(video mẫu dài {_f(dur)}s, {len(sk)} sự kiện chữ/đồ hoạ máy bắt được)")
    L.sort(key=lambda s: (0 if s.startswith("(") else 1, float(s.split("–")[0].split("s")[0].replace(",", ".")) if s[:1].isdigit() else 9e9))
    return L[:toi_da]


def tu_thu_muc(tm):
    for ten in ("dong_hoc.json", "dong-hoc.json"):
        p = os.path.join(tm, ten)
        if os.path.isfile(p):
            return tu_dong_hoc(chung.doc_json(p) or {})
    return []


if __name__ == "__main__":
    for d in tu_thu_muc(sys.argv[1]):
        print(d)
