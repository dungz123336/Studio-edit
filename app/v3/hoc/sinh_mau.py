# -*- coding: utf-8 -*-
"""SINH MẪU RIÊNG (D4): hiệu ứng đo được ở video mẫu mà thư viện `dung/mau` (danh_sach()) + engine anim không có tương đương
→ tạo KHUNG tệp mẫu mới trong thư mục mẫu riêng của hồ sơ `app/nao/ca-nhan/<hs>/mau-rieng/<id>.py` (đúng hợp đồng
`@dang_ky` + `ve(t, dur, W, H, c, p)`), đã chạy được ngay theo SỐ ĐO (kiểu vào, thời lượng, easing, cỡ, màu, nền) để AI điền/tinh chỉnh;
`kiem(id)` vẽ thử 6 khung và so với dải khung gốc (SSIM vùng chữ + IoU hộp mực).

    python v3/hoc/sinh_mau.py thieu <dong_hoc.json> [--ho-so hs]
    python v3/hoc/sinh_mau.py tao <hs> <id> --dong-hoc <dong_hoc.json> --su-kien e03 [--ghi-de]
    python v3/hoc/sinh_mau.py kiem <hs> <id>
    python v3/hoc/sinh_mau.py nap <hs>                # nạp mẫu riêng vào REGISTRY (in id)

ĐIỀU PHỐI: registry (`dung/mau/__init__.py`) chưa tự nạp thư mục mẫu riêng của hồ sơ — gọi `sinh_mau.nap_mau_rieng(ho_so)` trước khi
dựng (hoặc chép logic vào nap_tat_ca). Id mẫu riêng dạng `rieng.<hs>.<id>` để không đụng thư viện chung.
"""
import os, sys, json, math, re, time, glob, importlib.util, unicodedata

V3 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if V3 not in sys.path:
    sys.path.insert(0, V3)
import numpy as np
import cv2
import chung as C

# kiểu ĐO → engine anim đã lo (không cần mẫu) | từ khoá tìm mẫu tương đương trong thư viện
ENGINE_CO = {"fade", "slide", "pop", "blur", "none"}
KHOP = {
    "typewriter": ["go-may", "go may", "typewriter", "o-tim-kiem", "tung ky tu"],
    "word_by_word": ["go-theo-loi", "karaoke", "phu-de-chay", "tung tu"],
    "mask_reveal": ["viet-tay", "truot-mask", "mask", "lo dan", "quet"],
    "doi_ky_tu": ["giai-ma", "glitch", "nhay ngau nhien"],
    "nen:pill": ["nhan-dan", "sticker", "pill"],
    "nen:chu_nhat": ["nhan-dan", "the", "khoi"],
    "nen:bo_goc": ["nhan-dan", "the", "bo goc"],
    "do_hoa:icon": ["icon"],
    "do_hoa:khung_rong": ["dong-khung", "vien-om"],
    "do_hoa:duong": ["gach-chan", "mui-ten"],
    "do_hoa:tron": ["khoanh", "icon"],
    "do_hoa:the": ["the", "nhan-dan", "chuong"],
}


def _kd(s):
    s = unicodedata.normalize("NFD", (s or "").lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")


def thu_muc_rieng(ho_so):
    return os.path.join(C.duong("ho_so"), ho_so, "mau-rieng")


def _thu_vien(ho_so=None):
    ds = []
    try:
        from dung import mau as M
        ds = M.danh_sach()
    except Exception:
        pass
    if ho_so:
        for p in glob.glob(os.path.join(thu_muc_rieng(ho_so), "*.py")):
            ds.append({"id": f"rieng.{ho_so}.{os.path.splitext(os.path.basename(p))[0]}", "ten": os.path.basename(p), "mo_ta": "", "hop_nghia": []})
    return ds


def _dong_hoc(x):
    return C.doc_json(x) if isinstance(x, str) else x


def hieu_ung_do(dh):
    """dong_hoc → [{"khoa", "kieu", "huong", "su_kien": [ids], "vai"}] hiệu ứng đo được (bỏ sự kiện máy không chắc)"""
    gom = {}
    for s in dh.get("su_kien") or []:
        if s.get("bo_qua") or s.get("loi"):
            continue
        v = s.get("vao") or {}
        if v.get("kieu") in (None, "khong_do_duoc"):
            continue
        if s["vai"] == "do_hoa":
            h = ((s.get("tinh") or {}).get("hinh") or {})
            k = "do_hoa:" + (h.get("loai") if h.get("loai") in ("icon", "the") else h.get("hinh") or "tu_do")
        else:
            k = v["kieu"]
        r = gom.setdefault(k, {"khoa": k, "kieu": v.get("kieu"), "huong": v.get("huong"), "su_kien": [], "vai": s["vai"]})
        r["su_kien"].append(s["id"])
        nen = (s.get("tinh") or {}).get("nen")
        if nen and s["vai"] != "do_hoa":
            k2 = "nen:" + (nen.get("hinh") or "chu_nhat")
            r2 = gom.setdefault(k2, {"khoa": k2, "kieu": "nen", "huong": None, "su_kien": [], "vai": s["vai"]})
            r2["su_kien"].append(s["id"])
    return list(gom.values())


def thieu(nguon, ho_so=None):
    """nguon: dong_hoc.json (đường dẫn/dict) → {"co": [{khoa, mau: [ids]}], "thieu": [{khoa, su_kien, goi_y_id}]}"""
    dh = _dong_hoc(nguon) or {}
    tv = _thu_vien(ho_so)
    van = [(d["id"], _kd(" ".join([d.get("id") or "", d.get("ten") or "", d.get("mo_ta") or ""] + list(d.get("hop_nghia") or [])))) for d in tv]
    co, th = [], []
    for h in hieu_ung_do(dh):
        k = h["khoa"]
        if k in ENGINE_CO:
            co.append({"khoa": k, "mau": ["engine.anim:" + k], "su_kien": h["su_kien"]}); continue
        tk = [_kd(x) for x in KHOP.get(k, [k.split(":")[-1]])]
        trung = [mid for mid, txt in van if any(t in txt for t in tk)]
        if trung:
            co.append({"khoa": k, "mau": trung[:5], "su_kien": h["su_kien"]})
        else:
            th.append({"khoa": k, "su_kien": h["su_kien"], "goi_y_id": re.sub(r"[^a-z0-9]+", "-", _kd(k)).strip("-")})
    return {"co": co, "thieu": th}


# ───────────────────────────────────────────── khung tệp mẫu
KHUNG = '''# -*- coding: utf-8 -*-
"""MẪU RIÊNG của hồ sơ {hs}: `{mid}` — sinh từ SỐ ĐO video mẫu ({video}, sự kiện {sk}).
Đã chạy được theo số đo (kiểu vào `{kieu}`{huong_txt}, {dai}s, ease {ease}; ra `{kieu_ra}` {dai_ra}s). AI: tinh chỉnh các chỗ `# TODO`
cho giống dải khung gốc, rồi chạy  python v3/hoc/sinh_mau.py kiem {hs} {ten}  (SSIM/IoU càng cao càng giống).
Hợp đồng: ve(t, dur, W, H, c, p) → numpy uint8 RGBA (H, W, 4) KHÔNG nhân trước alpha; W,H = px hộp lớp; mọi kích thước theo W/H/p."""
import math, random
import numpy as np
import cv2
from dung.mau import dang_ky

SO_DO = {so_do}


def _ease(ten, u):
    try:
        from dung import anim
        return anim.ease(ten or "linear", u)
    except Exception:
        u = min(1.0, max(0.0, u))
        return 1 - (1 - u) ** 3


def _dan(nen, a, x, y):
    """dán RGBA a lên RGBA nen tại (x, y) góc trên-trái (alpha over, không nhân trước)"""
    H, W = nen.shape[:2]; h, w = a.shape[:2]
    x0, y0 = max(0, int(x)), max(0, int(y)); x1, y1 = min(W, int(x) + w), min(H, int(y) + h)
    if x1 <= x0 or y1 <= y0:
        return nen
    s = a[y0 - int(y):y1 - int(y), x0 - int(x):x1 - int(x)].astype(np.float32) / 255
    d = nen[y0:y1, x0:x1].astype(np.float32) / 255
    al = s[..., 3:4] + d[..., 3:4] * (1 - s[..., 3:4])
    rgb = (s[..., :3] * s[..., 3:4] + d[..., :3] * d[..., 3:4] * (1 - s[..., 3:4])) / np.maximum(al, 1e-6)
    nen[y0:y1, x0:x1] = np.concatenate([rgb, al], -1).clip(0, 1) * 255
    return nen


@dang_ky(id="{mid}", nhom="{nhom}", ten="{ten_hien}", mo_ta="{mo_ta}",
         hop_nghia={hop_nghia}, tham_so={{"chu": "chữ hiển thị", "co": "px cỡ chữ (khung 1920)", "mau": "vai màu|#hex",
         "dai": "giây vào", "ease": "easing vào", "dai_ra": "giây ra"}},
         mac_dinh={mac_dinh}, hop={hop}, dong=True, sfx_goi_y=[], vi_du={vi_du})
def ve(t, dur, W, H, c, p):
    kd = {{"co": float(p["co"]), "mau": c.mau(p["mau"]), "dam": int(p.get("dam", 800))}}
    if p.get("nen"):
        kd["nen"] = {{"mau": c.mau(p["nen"]), "hinh": p.get("hinh_nen", "pill")}}    # TODO: lề/bo góc nền theo SO_DO["nen"]
    chu = str(p.get("chu") or "")
    kieu, dai, ease = p.get("kieu", "{kieu}"), max(1e-3, float(p["dai"])), p.get("ease", "{ease}")
    u = min(1.0, max(0.0, t / dai))
    e = _ease(ease, u)
    # ---- nội dung theo kiểu vào đo được (TODO: tinh chỉnh cho khớp dải gốc)
    if kieu == "typewriter":
        n = int(math.ceil(len(chu) * u))
        anh, meta = c.ve_chu(chu[:n] or " ", kd, rong_max_px=W)
        du, _ = c.ve_chu(chu, kd, rong_max_px=W)
        ox = (W - du.shape[1]) / 2                     # neo trái của cả câu (gõ không làm câu dời)
    elif kieu == "word_by_word":
        tu = chu.split()
        n = int(math.ceil(len(tu) * u))
        anh, meta = c.ve_chu(" ".join(tu[:n]) or " ", kd, rong_max_px=W)
        ox = None
    elif kieu == "doi_ky_tu":
        rnd = random.Random(int(t * 24))
        chot = int(len(chu) * u)
        hien = "".join(ch if (i < chot or ch == " ") else rnd.choice("ABCDEFGHKLMNOPQRSTUVXY0123456789#$%&@") for i, ch in enumerate(chu))
        anh, meta = c.ve_chu(hien, kd, rong_max_px=W)
        ox = None
    else:
        anh, meta = c.ve_chu(chu, kd, rong_max_px=W)
        ox = None
    anh = np.ascontiguousarray(anh)
    a = anh.astype(np.float32)
    if kieu == "mask_reveal":
        huong = p.get("huong", "{huong}")
        h_, w_ = a.shape[:2]
        m = np.zeros((h_, w_), np.float32)
        if huong == "phai_sang_trai":
            m[:, int(w_ * (1 - e)):] = 1
        elif huong == "tren_xuong":
            m[:int(h_ * e), :] = 1
        elif huong == "duoi_len":
            m[int(h_ * (1 - e)):, :] = 1
        else:
            m[:, :int(w_ * e)] = 1
        a[..., 3] *= cv2.GaussianBlur(m, (0, 0), 2)    # TODO: mép mềm theo SO_DO
    elif kieu == "blur" and u < 1:
        a = cv2.GaussianBlur(a, (0, 0), max(0.1, (1 - e) * 0.05 * max(a.shape[:2])))
    elif kieu == "fade":
        a[..., 3] *= e
    s = 1.0
    if kieu == "pop":
        s0 = float(SO_DO.get("ti_le_dau") or 0.6)
        s = s0 + (1 - s0) * e
        if s0 < 1:
            a[..., 3] *= min(1.0, u * 3)
    dx = dy = 0.0
    if kieu == "slide":
        d = (1 - e) * 0.15 * max(W, H)
        hg = p.get("huong", "{huong}")
        dx, dy = {{"tu_trai": (-d, 0), "tu_phai": (d, 0), "tu_tren": (0, -d), "tu_duoi": (0, d)}}.get(hg, (0, d))
        a[..., 3] *= min(1.0, u * 2)
    # ---- ra
    dra = float(p.get("dai_ra") or 0)
    if dra > 0 and t > dur - dra:
        a[..., 3] *= max(0.0, (dur - t) / dra)                 # TODO: kiểu ra khác fade theo SO_DO["ra"]
    a = a.clip(0, 255).astype(np.uint8)
    if abs(s - 1) > 1e-3:
        a = cv2.resize(a, (max(1, int(a.shape[1] * s)), max(1, int(a.shape[0] * s))), interpolation=cv2.INTER_LINEAR)
    nen = np.zeros((H, W, 4), np.uint8)
    x = (W - a.shape[1]) / 2 if ox is None else ox
    y = (H - a.shape[0]) / 2
    return _dan(nen, a, x + dx, y + dy)
'''


def tao_khung(ho_so, ten, dong_hoc=None, su_kien=None, mo_ta="", ghi_de=False):
    """→ đường dẫn tệp mẫu mới (app/nao/ca-nhan/<hs>/mau-rieng/<ten>.py) + <ten>.json (số đo gốc để kiem)"""
    ten = re.sub(r"[^a-z0-9_]+", "_", _kd(ten)).strip("_") or "mau_moi"
    tm = thu_muc_rieng(ho_so)
    os.makedirs(tm, exist_ok=True)
    p = os.path.join(tm, ten + ".py")
    if os.path.exists(p) and not ghi_de:
        raise FileExistsError(p)
    dh = _dong_hoc(dong_hoc) or {}
    sk = next((s for s in dh.get("su_kien") or [] if s["id"] == su_kien), None) if su_kien else None
    if sk is None and dh.get("su_kien"):
        sk = next((s for s in dh["su_kien"] if (s.get("vao") or {}).get("kieu") not in (None, "khong_do_duoc") and s.get("tinh")), None)
    sk = sk or {}
    v, r, tc = sk.get("vao") or {}, sk.get("ra") or {}, sk.get("tinh") or {}
    hop = tc.get("hop") or [0.1, 0.4, 0.9, 0.6]
    cx, cy = (hop[0] + hop[2]) / 2, (hop[1] + hop[3]) / 2
    w, h = min(1.0, (hop[2] - hop[0]) * 1.3), min(1.0, (hop[3] - hop[1]) * 1.8)
    mid = f"rieng.{ho_so}.{ten}"
    kieu = v.get("kieu") or "fade"
    so_do = {"video": dh.get("video"), "dong_hoc": dh.get("duong"), "su_kien": sk.get("id"), "vao": {k: v.get(k) for k in ("kieu", "huong", "dai", "ease", "dac_trung", "t_bat_dau", "t_du")},
             "ra": {k: r.get(k) for k in ("kieu", "dai", "ease")}, "hop": hop, "nen": tc.get("nen"), "mau_chu": tc.get("mau_chu"),
             "co_uoc_1920": tc.get("co_uoc_1920"), "hoa": tc.get("hoa"), "ti_le_dau": (v.get("dac_trung") or {}).get("ti_le_dau")}
    md = {"chu": "MẪU CHỮ" if tc.get("hoa") == "hoa" else "Mẫu chữ", "co": float(tc.get("co_uoc_1920") or 96), "mau": tc.get("mau_chu") or "nhan",
          "dam": int(tc.get("dam_uoc") or 800), "kieu": kieu, "dai": float(v.get("dai") or 0.3), "ease": v.get("ease") or "out",
          "dai_ra": float(r.get("dai") or 0.2) if r.get("kieu") not in (None, "none", "khong_do_duoc") else 0.0}
    if v.get("huong"):
        md["huong"] = v["huong"]
    if tc.get("nen"):
        md["nen"] = tc["nen"].get("mau"); md["hinh_nen"] = "pill" if tc["nen"].get("hinh") == "pill" else "rect"
    vd = {"chu": (tc.get("chu_ocr") or md["chu"])[:40]}
    ma = KHUNG.format(hs=ho_so, mid=mid, ten=ten, video=os.path.basename(str(dh.get("video") or "?")), sk=sk.get("id") or "?",
                      kieu=kieu, huong_txt=(" / " + v["huong"]) if v.get("huong") else "", huong=v.get("huong") or "trai_sang_phai",
                      dai=md["dai"], ease=md["ease"], kieu_ra=r.get("kieu") or "?", dai_ra=md["dai_ra"],
                      so_do=repr(so_do), nhom="chu" if sk.get("vai") != "do_hoa" else "do_hoa",
                      ten_hien=(mo_ta or f"Mẫu riêng {ten}").replace('"', "'"), mo_ta=(mo_ta or f"học từ video mẫu: vào {kieu}").replace('"', "'"),
                      hop_nghia=repr(["học từ video mẫu"]), mac_dinh=repr(md),
                      hop=repr({"anchor": "mc", "x": round(cx, 3), "y": round(cy, 3), "w": round(w, 3), "h": round(h, 3)}),
                      vi_du=repr(vd))
    with open(p, "w", encoding="utf-8") as f:
        f.write(ma)
    C.ghi_json(os.path.join(tm, ten + ".json"), {"id": mid, "so_do": so_do, "tao_luc": time.strftime("%Y-%m-%d %H:%M")})
    return p


def nap_mau_rieng(ho_so):
    """import mọi <hs>/mau-rieng/*.py → đăng ký vào dung.mau.REGISTRY (id rieng.<hs>.<ten>). Trả [id] nạp được."""
    from dung import mau as M
    M.nap_tat_ca()
    ra = []
    for p in sorted(glob.glob(os.path.join(thu_muc_rieng(ho_so), "*.py"))):
        ten = os.path.splitext(os.path.basename(p))[0]
        mod = f"mau_rieng_{re.sub(r'[^a-z0-9_]', '_', _kd(ho_so))}_{ten}"
        try:
            sp = importlib.util.spec_from_file_location(mod, p)
            m = importlib.util.module_from_spec(sp)
            sys.modules[mod] = m
            sp.loader.exec_module(m)
            ra += [k for k, v in M.REGISTRY.items() if v["the"].get("module") == mod]
        except Exception as ex:
            print(f"(mẫu riêng {ten} lỗi: {str(ex)[:200]})")
    return ra


# ───────────────────────────────────────────── kiểm: vẽ thử 6 khung, so với dải gốc
def _ssim(a, b):
    a = a.astype(np.float32); b = b.astype(np.float32)
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    g = lambda x: cv2.GaussianBlur(x, (7, 7), 1.5)
    ma, mb = g(a), g(b)
    va, vb, cab = g(a * a) - ma * ma, g(b * b) - mb * mb, g(a * b) - ma * mb
    s = ((2 * ma * mb + C1) * (2 * cab + C2)) / ((ma * ma + mb * mb + C1) * (va + vb + C2))
    return float(s.mean())


def _khung_tai(video, t, W, H):
    import subprocess
    r = subprocess.run([C.duong("ffmpeg"), "-v", "error", "-ss", f"{max(0, t):.3f}", "-i", video, "-frames:v", "1",
                        "-vf", f"scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True,
                       creationflags=0x08000000 if os.name == "nt" else 0)
    return np.frombuffer(r.stdout, np.uint8).reshape(H, W, 3).copy() if len(r.stdout) == W * H * 3 else None


def kiem(ho_so, ten, n=6, ra=None):
    """vẽ thử mẫu riêng 6 thời điểm của lúc vào (theo số đo gốc) trên khung VẮNG của video mẫu, so với khung gốc cùng thời điểm:
    SSIM vùng hộp chữ + IoU hộp mực (vẽ vs gốc). → {"ssim": [...], "iou": [...], "ssim_tb", "iou_tb", "anh"}"""
    from dung import mau as M, lop as L
    ten = re.sub(r"[^a-z0-9_]+", "_", _kd(ten)).strip("_")
    meta = C.doc_json(os.path.join(thu_muc_rieng(ho_so), ten + ".json")) or {}
    so = meta.get("so_do") or {}
    nap_mau_rieng(ho_so)
    mid = meta.get("id") or f"rieng.{ho_so}.{ten}"
    r = M.lay(mid)
    if not r:
        raise RuntimeError(f"không nạp được mẫu {mid}")
    the = r["the"]
    video = so.get("video")
    v = so.get("vao") or {}
    W, H = 540, 960
    from dung.mau import bang as _bang                   # 1.2.21: engine không còn mặc định thẩm mỹ → quyết định TRUNG TÍNH cho bộ học
    ctx = L.Ctx(1080, 1920, 30, font={}, mat=None, kho=None, du_an=thu_muc_rieng(ho_so), quyet_dinh=json.loads(json.dumps(_bang.QUYET_DINH_XEM_TRUOC)))
    ctx.pc = {"mau_nhan": so.get("mau_chu") or "#FFD200", "mau_sang": "#FFFFFF", "mau_toi": "#111111"}
    cc = M.CongCu(ctx, None)
    p = dict(the.get("mac_dinh") or {}); p.update(the.get("vi_du") or {})
    hop = the.get("hop") or {}
    bw, bh = int(hop.get("w", 0.8) * 1080), int(hop.get("h", 0.3) * 1920)
    bx, by = int(hop.get("x", 0.5) * 1080 - bw / 2), int(hop.get("y", 0.5) * 1920 - bh / 2)
    t0 = float(v.get("t_bat_dau") or 0); t1 = float(v.get("t_du") or t0 + 0.4)
    dai_vao = max(0.1, t1 - t0)
    ts = [t0 + dai_vao * i / (n - 2) for i in range(n - 1)] + [t1 + 0.3]
    dur = max(1.0, dai_vao + 1.0)
    nen = _khung_tai(video, t0 - 0.05, W, H) if video and os.path.isfile(video) else np.full((H, W, 3), 40, np.uint8)
    goc_hop = so.get("hop") or [0.1, 0.4, 0.9, 0.6]
    mx_, my_ = 0.2 * (goc_hop[2] - goc_hop[0]) * W + 10, 0.35 * (goc_hop[3] - goc_hop[1]) * H + 10
    X0, Y0, X1, Y1 = int(goc_hop[0] * W - mx_), int(goc_hop[1] * H - my_), int(goc_hop[2] * W + mx_), int(goc_hop[3] * H + my_)
    X0, Y0 = max(0, X0), max(0, Y0); X1, Y1 = min(W, X1), min(H, Y1)
    ss, ious, hang_goc, hang_ve = [], [], [], []
    for t in ts:
        goc = _khung_tai(video, t, W, H) if video and os.path.isfile(video) else nen.copy()
        lt = t - t0
        rgba = r["ham"](lt, dur, bw, bh, cc, p)
        lay = np.zeros((1920, 1080, 4), np.uint8)
        x0, y0 = max(0, bx), max(0, by)
        sub = rgba[y0 - by:y0 - by + min(bh, 1920 - y0), x0 - bx:x0 - bx + min(bw, 1080 - x0)]
        lay[y0:y0 + sub.shape[0], x0:x0 + sub.shape[1]] = sub
        lay = cv2.resize(lay, (W, H), interpolation=cv2.INTER_AREA)
        al = lay[..., 3:4].astype(np.float32) / 255
        ve = (lay[..., :3].astype(np.float32) * al + nen.astype(np.float32) * (1 - al)).astype(np.uint8)
        g1 = cv2.cvtColor(goc[Y0:Y1, X0:X1], cv2.COLOR_RGB2GRAY); g2 = cv2.cvtColor(ve[Y0:Y1, X0:X1], cv2.COLOR_RGB2GRAY)
        ss.append(round(_ssim(g1, g2), 3))
        m1 = np.abs(goc.astype(np.int16) - nen.astype(np.int16)).max(2) > 40
        m2 = lay[..., 3] > 100
        def hb(m):
            ys, xs = np.nonzero(m[Y0:Y1, X0:X1])
            return None if len(xs) < 10 else [xs.min(), ys.min(), xs.max() + 1, ys.max() + 1]
        a_, b_ = hb(m1), hb(m2)
        if a_ is None and b_ is None:
            ious.append(1.0)
        elif a_ is None or b_ is None:
            ious.append(0.0)
        else:
            ix = max(0, min(a_[2], b_[2]) - max(a_[0], b_[0])); iy = max(0, min(a_[3], b_[3]) - max(a_[1], b_[1]))
            u = (a_[2] - a_[0]) * (a_[3] - a_[1]) + (b_[2] - b_[0]) * (b_[3] - b_[1]) - ix * iy
            ious.append(round(ix * iy / u if u else 0.0, 3))
        hang_goc.append(goc[Y0:Y1, X0:X1]); hang_ve.append(ve[Y0:Y1, X0:X1])
    # ảnh so
    from PIL import Image, ImageDraw
    hh = 120
    def nho(a):
        s = hh / a.shape[0]
        return Image.fromarray(cv2.resize(a, (max(1, int(a.shape[1] * s)), hh)))
    cot = [nho(a) for a in hang_goc]; cot2 = [nho(a) for a in hang_ve]
    wcol = max(c.width for c in cot) + 6
    im = Image.new("RGB", (wcol * n + 10, 2 * (hh + 22) + 30), (16, 16, 20))
    d = ImageDraw.Draw(im)
    try:
        from hoc.dong_hoc import _font_ve
        ft = _font_ve(14)
    except Exception:
        ft = None
    d.text((6, 4), f"{mid}: hàng trên = GỐC, dưới = MẪU vẽ thử · SSIM tb {np.mean(ss):.2f} · IoU tb {np.mean(ious):.2f}", fill=(255, 210, 0), font=ft)
    for i in range(n):
        im.paste(cot[i], (6 + i * wcol, 26)); im.paste(cot2[i], (6 + i * wcol, 26 + hh + 22))
        d.text((6 + i * wcol, 26 + hh + 2), f"{ts[i]:.2f}s", fill=(120, 255, 160))
        d.text((6 + i * wcol, 26 + 2 * hh + 24), f"S{ss[i]:.2f} I{ious[i]:.2f}", fill=(120, 220, 255))
    ra = ra or os.path.join(thu_muc_rieng(ho_so), ten + "-kiem.jpg")
    im.save(ra, quality=88)
    kq = {"id": mid, "t": [round(x, 3) for x in ts], "ssim": ss, "iou": ious, "ssim_tb": round(float(np.mean(ss)), 3), "iou_tb": round(float(np.mean(ious)), 3), "anh": ra}
    m = C.doc_json(os.path.join(thu_muc_rieng(ho_so), ten + ".json")) or {}
    m.setdefault("kiem", []).append(dict(kq, luc=time.strftime("%Y-%m-%d %H:%M")))
    C.ghi_json(os.path.join(thu_muc_rieng(ho_so), ten + ".json"), m)
    return kq


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("lenh", choices=["thieu", "tao", "kiem", "nap"])
    ap.add_argument("a", nargs="?"); ap.add_argument("b", nargs="?")
    ap.add_argument("--ho-so"); ap.add_argument("--dong-hoc"); ap.add_argument("--su-kien"); ap.add_argument("--mo-ta", default="")
    ap.add_argument("--ghi-de", action="store_true")
    x = ap.parse_args()
    if x.lenh == "thieu":
        print(json.dumps(thieu(x.a, x.ho_so), ensure_ascii=False, indent=1))
    elif x.lenh == "tao":
        print(tao_khung(x.a, x.b, x.dong_hoc, x.su_kien, x.mo_ta, x.ghi_de))
    elif x.lenh == "kiem":
        print(json.dumps(kiem(x.a, x.b), ensure_ascii=False, indent=1))
    else:
        print(nap_mau_rieng(x.a))
