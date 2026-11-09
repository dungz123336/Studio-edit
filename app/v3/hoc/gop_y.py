# -*- coding: utf-8 -*-
"""GÓP Ý SAU KHI GIAO: câu tiếng Việt tự do của người dùng ("chữ to hơn", "đừng dùng chữ viết tay", "phụ đề để giữa")
→ AI đọc câu góp ý + QUYẾT ĐỊNH KÊNH hiện tại (nao/ca-nhan/<hs>/quyet-dinh.json) + Style Spec, rồi viết BẢN QUYẾT ĐỊNH MỚI đủ trường
(máy kiểm khuôn ai/hop_dong, lưu, giữ 20 bản lịch sử) và (tuỳ) một DIFF nhỏ trên Style Spec. 1.2.21: KHÔNG còn luật nhanh với hệ số
cứng (×1.25/1.12/0.7/1.35, vị trí 0.55/0.74/0.2) — không có AI thì báo "cần AI", không tự nhân số.

Bộ chuyển: Claude CLI KHÔNG tương tác (`claude -p`, chỉ dùng cờ có trong `claude --help`, không công cụ, không lưu phiên).

    python v3/hoc/gop_y.py ap <hs> "chữ to hơn chút" [--thu]     # --thu: chỉ in, không ghi
    python v3/hoc/gop_y.py hoan-tac <hs>
    python v3/hoc/gop_y.py lich-su <hs>

API: gop_y(ho_so, cau, dung_ai=True, ghi=True) -> {"quyet_dinh": dict|None, "diff", "tom_tat", "nguon", "loi_schema", "loi_quyet_dinh", "lich_su"}
     ap_diff(spec, diff) -> spec mới · hoan_tac(ho_so) -> {...} · lich_su(ho_so) -> [...]
Dạng diff: [{"op": "dat"|"xoa"|"them_vao"|"bo_khoi"|"nhan", "duong": "type_scale.phu_de.co" | "layout.anchors[vai=phu_de].y" | "motion_vocab.vao[0].dai",
            "gia_tri": ..., "ly_do": "..."}]   (nhan = nhân số hiện có với gia_tri)
"""
import os, sys, json, re, time, copy, unicodedata, glob

V3 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if V3 not in sys.path:
    sys.path.insert(0, V3)
import chung as C


def _kd(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


def _p_spec(ho_so):
    return os.path.join(C.duong("ho_so"), ho_so, "style-spec.json")


def _p_ls(ho_so):
    return os.path.join(C.duong("ho_so"), ho_so, "style-spec-lich-su")


# ───────────────────────────────────────────── áp diff
def _tach(duong):
    """'a.b[2].c[vai=phu_de]' → ['a','b',2,'c',('vai','phu_de')]"""
    ra = []
    for phan in re.findall(r"[^.\[\]]+|\[[^\]]*\]", duong or ""):
        if phan.startswith("["):
            x = phan[1:-1]
            if "=" in x:
                k, v = x.split("=", 1)
                ra.append((k.strip(), v.strip().strip("'\"")))
            elif x.strip().lstrip("-").isdigit():
                ra.append(int(x))
            else:
                ra.append(x)
        else:
            ra.append(phan)
    return ra


def _buoc(cha, k, tao_kieu=dict):
    if isinstance(k, tuple):
        if not isinstance(cha, list):
            raise KeyError(f"[{k[0]}={k[1]}] cần mảng")
        for x in cha:
            if isinstance(x, dict) and str(x.get(k[0])) == k[1]:
                return x
        x = {k[0]: k[1]}
        cha.append(x)
        return x
    if isinstance(k, int):
        if not isinstance(cha, list) or not (-len(cha) <= k < len(cha)):
            raise KeyError(f"chỉ số {k} ngoài mảng")
        return cha[k]
    if k not in cha or cha[k] is None:
        cha[k] = tao_kieu()
    return cha[k]


def _dat(goc, duong, op, gia_tri):
    ks = _tach(duong)
    if not ks:
        raise KeyError("đường dẫn rỗng")
    cha = goc
    for i, k in enumerate(ks[:-1]):
        sau = ks[i + 1]
        cha = _buoc(cha, k, list if isinstance(sau, (int, tuple)) else dict)
    k = ks[-1]
    if op == "xoa":
        if isinstance(k, tuple):
            cha[:] = [x for x in cha if not (isinstance(x, dict) and str(x.get(k[0])) == k[1])]
        elif isinstance(k, int):
            cha.pop(k)
        else:
            cha.pop(k, None)
        return
    if op in ("them_vao", "bo_khoi"):
        ds = _buoc(cha, k, list)
        if not isinstance(ds, list):
            raise KeyError(f"{duong} không phải mảng")
        if op == "them_vao":
            if gia_tri not in ds:
                ds.append(gia_tri)
        else:
            ds[:] = [x for x in ds if x != gia_tri]
        return
    if op == "nhan":
        cu = cha[k] if not isinstance(k, tuple) else None
        if not isinstance(cu, (int, float)):
            raise KeyError(f"{duong} chưa có số để nhân")
        gia_tri = round(cu * float(gia_tri), 3)
    if isinstance(k, tuple):
        x = _buoc(cha, k)
        x.clear(); x.update(gia_tri if isinstance(gia_tri, dict) else {k[0]: k[1]})
    elif isinstance(k, int):
        cha[k] = gia_tri
    else:
        cha[k] = gia_tri


def ap_diff(spec, diff):
    """→ (spec mới, [lỗi từng thao tác])"""
    s = copy.deepcopy(spec or {})
    loi = []
    for d in diff or []:
        try:
            _dat(s, d.get("duong", ""), d.get("op", "dat"), d.get("gia_tri"))
        except Exception as ex:
            loi.append(f"{d.get('duong')}: {ex}")
    return s, loi


# ───────────────────────────────────────────── không có AI
def luat_nhanh(cau, spec):
    """1.2.21: máy không còn hệ số cứng → không có AI thì không chuyển được góp ý thành số"""
    return {"diff": [], "tom_tat": "", "can_ai": True}


# ───────────────────────────────────────────── AI (claude -p)
PROMPT = """Bạn là đạo diễn của kênh, chỉnh QUYẾT ĐỊNH KÊNH (quyet-dinh.json — mặc định thẩm mỹ cho mọi video của kênh, máy không có số riêng)
theo GÓP Ý của người dùng sau khi xem video đã giao. Trả về DUY NHẤT một JSON (không markdown, không giải thích):
{{"quyet_dinh": {{...TOÀN BỘ quyết định kênh mới, đủ mọi trường của khuôn...}},
  "diff": [{{"op": "dat|xoa|them_vao|bo_khoi|nhan", "duong": "...", "gia_tri": ..., "ly_do": "..."}}],
  "tom_tat": "một câu tiếng Việt nói đã đổi gì (số cũ → số mới)"}}
Quy tắc:
- `quyet_dinh`: chép bản hiện tại, CHỈ đổi những trường góp ý nhắc tới; số do bạn chọn (không có hệ số sẵn); tăng `phien` lên 1; ghi `ly_do` 1–2 câu.
  Khuôn (kiểu, miền) bên dưới; cỡ là px trên khung 1080×1920, giây, tỉ lệ 0..1, màu #RRGGBB[AA].
- `diff` (tuỳ, có thể []): thay đổi nhỏ tương ứng trên Style Spec của hồ sơ (bản sắc đã học) nếu góp ý đụng tới nó; "duong" khoá cách nhau bởi
  dấu chấm, phần tử mảng [0] hoặc [vai=phu_de]; op dat/xoa/them_vao/bo_khoi/nhan.
- Không làm được bằng khuôn → làm phần gần nhất + nói rõ trong tom_tat. Câu mơ hồ → chọn cách hiểu phổ biến nhất, ghi trong tom_tat.

Góp ý của người dùng: «{cau}»

Quyết định kênh hiện tại (JSON):
{quyet_dinh}

Khuôn quyet-dinh.json:
{khuon}

Style Spec hiện tại (bản sắc đã học, chỉ để đối chiếu):
{spec}
"""


def _goi_claude(prompt, timeout=240):
    try:
        from ai import dong_co as DC
        exe = DC._claude()
        co = DC.co_cli()
    except Exception as ex:
        return None, f"không nạp được ai.dong_co: {ex}"
    if not exe:
        return None, "không có lệnh claude"
    cmd = [exe, "-p", "--output-format", "json"]
    if "--tools" in co:
        cmd += ["--tools", ""]
    if "--no-session-persistence" in co:
        cmd += ["--no-session-persistence"]
    if "--disable-slash-commands" in co:
        cmd += ["--disable-slash-commands"]
    if "--strict-mcp-config" in co and "--mcp-config" in co:
        try:
            cmd += ["--strict-mcp-config", "--mcp-config", DC._mcp_rong()]
        except Exception:
            pass
    if "--no-chrome" in co:
        cmd += ["--no-chrome"]
    md = ((C.cau_hinh().get("ai") or {}).get("model_nhanh") or "")
    if md and "--model" in co:
        cmd += ["--model", md]
    tm = os.path.join(C.duong("nhat_ky"), "gop-y")
    os.makedirs(tm, exist_ok=True)
    env = {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "DISABLE_AUTOUPDATER": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
    ma, out, err = C.sh(cmd, timeout=timeout, cwd=tm, env=env, nhap=prompt.encode("utf-8"))
    if ma != 0 and not out.strip():
        return None, (err or out)[-300:]
    txt = out.strip()
    try:
        j = json.loads(txt)
        if isinstance(j, list):
            j = next((x for x in reversed(j) if isinstance(x, dict) and x.get("type") == "result"), {})
        if j.get("is_error"):
            return None, str(j.get("result"))[:300]
        txt = j.get("result") or ""
        usd = j.get("total_cost_usd")
    except Exception:
        usd = None
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return None, "AI không trả JSON: " + txt[:200]
    try:
        r = json.loads(m.group(0))
        r["_usd"] = usd
        return r, None
    except Exception as ex:
        return None, f"JSON hỏng: {ex}"


# ───────────────────────────────────────────── chính
def doc_spec(ho_so):
    return C.doc_json(_p_spec(ho_so)) or {}


def gop_y(ho_so, cau, dung_ai=True, ghi=True, log=print):
    from hoc import kiem_spec as K
    from ai import hop_dong as H
    if not os.path.isdir(os.path.join(C.duong("ho_so"), ho_so)):
        raise SystemExit(f"không có hồ sơ {ho_so}")
    spec = doc_spec(ho_so)
    qd_cu, _, loi_qd_cu = H.doc_quyet_dinh(None, ho_so, luu=False)
    if qd_cu is None:
        try:
            from phong_cach import ap as _ap
            hs = C.doc_json(os.path.join(C.duong("ho_so"), ho_so, "ho-so.json")) or {}
            qd_cu = _ap.quyet_dinh_cho(hs.get("goi") or "") if hs.get("goi") else None
        except Exception:
            qd_cu = None
    if qd_cu is None:
        qd_cu = H.mau_quyet_dinh()
        qd_nguon_cu = "mau"
    else:
        qd_nguon_cu = qd_cu.get("_nguon") or "ho_so"
    kq, nguon, loi_ai = None, None, None
    if dung_ai:
        kq, loi_ai = _goi_claude(PROMPT.format(cau=cau, quyet_dinh=json.dumps({k: v for k, v in qd_cu.items() if not k.startswith("_")}, ensure_ascii=False, indent=1),
                                               khuon=H.khuon_toi_thieu_md(),
                                               spec=json.dumps({k: v for k, v in (spec or {}).items() if not k.startswith("_")}, ensure_ascii=False, separators=(",", ":"))[:6000]))
        nguon = "ai" if kq else None
        if loi_ai:
            log(f"(AI không chuyển được: {loi_ai})")
    if not kq or (not isinstance(kq.get("quyet_dinh"), dict) and not kq.get("diff")):
        return {"quyet_dinh": None, "diff": [], "nguon": nguon or "khong", "loi_ai": loi_ai,
                "tom_tat": "Cần AI để chuyển góp ý thành quyết định kênh (máy không có luật số riêng)" + (f" — {loi_ai}" if loi_ai else "")
                           + ". Hoặc sửa tay nao/ca-nhan/" + ho_so + "/quyet-dinh.json."}
    ra = {"quyet_dinh": None, "diff": kq.get("diff") or [], "tom_tat": kq.get("tom_tat") or "", "nguon": nguon, "loi_ap": [], "loi_schema": [],
          "loi_quyet_dinh": [], "usd": kq.get("_usd"), "loi_ai": loi_ai}
    qd_moi = kq.get("quyet_dinh") if isinstance(kq.get("quyet_dinh"), dict) else None
    if qd_moi is not None:
        loi_qd = H.kiem_quyet_dinh(qd_moi)
        if loi_qd:
            ra["loi_quyet_dinh"] = [f"{l['duong']}: {l['goi_y']}" for l in loi_qd[:20]]
            ra["tom_tat"] += " (CHƯA LƯU quyết định: sai khuôn — " + "; ".join(ra["loi_quyet_dinh"][:4]) + ")"
            qd_moi = None
        else:
            ra["quyet_dinh"] = qd_moi
            if ghi:
                ra["tep_quyet_dinh"] = H.luu_quyet_dinh(ho_so, qd_moi, nguon="gop_y", ly_do_luu=f"góp ý: {str(cau)[:120]}")
    if not ra["diff"]:
        return ra
    moi, loi_ap = ap_diff(spec, ra["diff"])
    truoc_loi = set(K.kiem(spec)) if spec else set()
    loi_moi = [l for l in K.kiem(moi) if l not in truoc_loi and not (not spec and "thiếu" in l)]
    ra["loi_ap"], ra["loi_schema"] = loi_ap, loi_moi
    if loi_moi:
        ra["tom_tat"] += " (diff Style Spec CHƯA LƯU: sai schema)"
        return ra
    if ghi:
        os.makedirs(_p_ls(ho_so), exist_ok=True)
        ten = time.strftime("%Y%m%d-%H%M%S") + f"-{int(time.time() * 1000) % 1000:03d}"
        p_ls = os.path.join(_p_ls(ho_so), ten + ".json")
        i = 1
        while os.path.exists(p_ls):
            p_ls = os.path.join(_p_ls(ho_so), f"{ten}{chr(96 + i)}.json"); i += 1
        C.ghi_json(p_ls, {"luc": time.strftime("%Y-%m-%d %H:%M:%S"), "cau": cau, "tom_tat": ra["tom_tat"], "diff": ra["diff"], "nguon": nguon,
                          "truoc": spec, "sau": moi, "da_hoan_tac": False})
        C.ghi_json(_p_spec(ho_so), moi)
        ra["lich_su"] = p_ls
        # 1.2.20: bài học đang BẬT là spec máy dựng ưu tiên (cong_thuc.py) → góp ý phải sửa cả vào đó, không thì "đã chỉnh" mà video không đổi
        sua_bai = []
        for pb in sorted(glob.glob(os.path.join(C.duong("ho_so"), ho_so, "hoc", "*.json"))):
            b = C.doc_json(pb, {}) or {}
            if b.get("bat", True) and isinstance(b.get("style_spec"), dict):
                sb, _ = ap_diff(b["style_spec"], ra["diff"])
                if not [l for l in K.kiem(sb) if l not in set(K.kiem(b["style_spec"]))]:
                    b["style_spec"] = sb; b.setdefault("gop_y_da_ap", []).append({"luc": time.strftime("%Y-%m-%d %H:%M"), "cau": cau})
                    mt = os.path.getmtime(pb); C.ghi_json(pb, b)
                    try:
                        os.utime(pb, (mt, mt))            # không đổi mtime: thứ tự "bài mới nhất" giữ nguyên
                    except OSError:
                        pass
                    sua_bai.append(os.path.basename(pb))
        if sua_bai:
            ra["bai_hoc_da_sua"] = sua_bai
    return ra


def lich_su(ho_so):
    ra = []
    for p in sorted(glob.glob(os.path.join(_p_ls(ho_so), "*.json"))):
        j = C.doc_json(p) or {}
        ra.append({"tep": p, "luc": j.get("luc"), "cau": j.get("cau"), "tom_tat": j.get("tom_tat"), "nguon": j.get("nguon"), "da_hoan_tac": j.get("da_hoan_tac")})
    return ra


def hoan_tac(ho_so, ep=False):
    """khôi phục spec TRƯỚC lần góp ý gần nhất chưa hoàn tác. Nếu spec đã bị sửa nơi khác sau đó → từ chối (ep=True để vẫn làm)."""
    ds = [x for x in lich_su(ho_so) if not x["da_hoan_tac"]]
    if not ds:
        return {"ok": False, "tom_tat": "Không còn góp ý nào để hoàn tác."}
    p = ds[-1]["tep"]
    j = C.doc_json(p)
    hien = doc_spec(ho_so)
    if C.bam(hien) != C.bam(j.get("sau") or {}) and not ep:
        return {"ok": False, "tom_tat": "Spec đã đổi sau lần góp ý này (học lại/sửa tay) — không hoàn tác tự động (dùng ep=True)."}
    C.ghi_json(_p_spec(ho_so), j.get("truoc") or {})
    j["da_hoan_tac"] = True; j["hoan_tac_luc"] = time.strftime("%Y-%m-%d %H:%M:%S")
    C.ghi_json(p, j)
    return {"ok": True, "tom_tat": f"Đã hoàn tác: {j.get('tom_tat') or j.get('cau')}", "tep": p}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", choices=["ap", "hoan-tac", "lich-su"])
    ap.add_argument("ho_so"); ap.add_argument("cau", nargs="?")
    ap.add_argument("--thu", action="store_true")
    x = ap.parse_args()
    if x.lenh == "ap":
        print(json.dumps(gop_y(x.ho_so, x.cau, dung_ai=True, ghi=not x.thu), ensure_ascii=False, indent=1))
    elif x.lenh == "hoan-tac":
        print(json.dumps(hoan_tac(x.ho_so), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(lich_su(x.ho_so), ensure_ascii=False, indent=1))
