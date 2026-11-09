# -*- coding: utf-8 -*-
"""Hoạt ảnh do dữ liệu điều khiển: ease, hợp nhất vào/ra/keyframes thành trạng thái, tách từ/ký tự so le.

1.2.21: anim.py KHÔNG còn số thẩm mỹ riêng. Mọi anim của lớp đi qua day_du(anim, quyet_dinh) (lop.Lop.__init__ gọi) để điền
vao/ra (kieu, dai, ease, tu/toi), so_le, keyframe_dai, keyframe_ease, trạng thái đầu theo kiểu (slide/pop/blur/flip/tilt) từ
quyet_dinh["anim"] của kênh (Kế hoạch 1.2.21 §1c). Thiếu → ThieuTruong(anim.<trường>). Hàm nhận anim chưa điền đủ → cũng ném thieu_truong.
Giữ vì vật lý: nhoe_dong_toi_da (hộp sprite hữu hạn), tham số đường cong ease (định nghĩa chuẩn của tên ease, như CSS)."""
import math

# ---- VẬT LÝ (không phải gu) ----
MAC_DINH = {
    "nhoe_dong": 0.0,                   # 1.2.20: nhoè THEO HƯỚNG chuyển động = hệ số × tốc độ (px/khung); 0 = tắt. 1 = vệt dài đúng quãng đi trong 1 khung
    "nhoe_dong_toi_da": 160.0,          # px vệt dài nhất (giữ hộp sprite hữu hạn)
    # trạng thái đầu/cuối CẤU TRÚC của kiểu (không có số gu): fade = mờ, wipe = chưa lộ, typewriter = ẩn, none = không
    "kieu_cau_truc": {"fade": {"opacity": 0}, "wipe": {"wipe": 0}, "typewriter": {"opacity": 0}, "none": {}},
    "kieu_can_quyet": ("slide", "pop", "blur", "flip", "tilt"),     # trạng thái đầu có SỐ (lệch px, scale, blur, góc) → quyet_dinh anim.kieu.<kieu>
    "ease": {"back_overshoot": 1.70158, "spring_tat_dan": 6.0, "spring_tan_so": 1.5, "expo_muc": 10.0},   # định nghĩa đường cong (chuẩn CSS)
}

TRANG_THAI_GOC = {"opacity": 1.0, "scale": 1.0, "x": 0.0, "y": 0.0, "rot": 0.0, "blur": 0.0, "wipe": 1.0, "rot_x": 0.0, "rot_y": 0.0}
_CONG = ("x", "y", "rot", "blur", "rot_x", "rot_y")       # trường cộng dồn (rot_x/rot_y: độ, phối cảnh 3D)
_NHAN = ("opacity", "scale", "wipe")    # trường nhân
_DA_DAY = "_day_du"                     # dấu anim đã qua day_du


class ThieuTruongAnim(RuntimeError):
    """thiếu trường anim — dùng chung định dạng với lop.ThieuTruong ({"duong","ma":"thieu_truong"})"""

    def __init__(self, duong, goi_y="", lop=None):
        self.duong, self.ma, self.goi_y, self.lop = str(duong), "thieu_truong", goi_y, lop
        super().__init__("thieu_truong: %s%s" % (self.duong, (" — " + goi_y) if goi_y else ""))

    def loi(self):
        return {"id": "thieu_truong", "ma": "thieu_truong", "duong": self.duong, "lop": self.lop, "t": None,
                "mo_ta": "thiếu trường `%s`%s — ghi vào anim của lớp hoặc quyet-dinh.json của kênh (mục anim)" % (self.duong, (" (" + self.goi_y + ")") if self.goi_y else "")}


def _thieu(duong, lop=None, goi_y=""):
    try:
        from dung.lop import ThieuTruong          # cùng một lớp lỗi với engine (isinstance bắt được ở dung.py)
        return ThieuTruong(duong, goi_y, lop)
    except Exception:
        return ThieuTruongAnim(duong, goi_y, lop)


def _qd(qd, duong, lop=None):
    """qd = quyet_dinh["anim"]; duong tính từ đó → lỗi ghi đường đầy đủ "anim.<duong>" """
    cur = qd if isinstance(qd, dict) else None
    for k in duong.split("."):
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            raise _thieu("anim." + duong, lop, "quyet_dinh.anim chưa có" if not isinstance(qd, dict) else "")
    if cur is None:
        raise _thieu("anim." + duong, lop, "giá trị null")
    return cur


def day_du(anim, quyet_dinh, lop=None):
    """→ bản sao anim đã điền đủ: vao/ra {kieu, dai, ease, tu|toi}, so_le, keyframe_dai, keyframe_ease, keyframes[i].dai/ease.
    Trường lớp ghi luôn thắng; thiếu → quyet_dinh["anim"] (§1c); thiếu cả hai → ThieuTruong(anim.<trường>). Idempotent."""
    anim = dict(anim or {})
    if anim.get(_DA_DAY):
        return anim
    qa = (quyet_dinh or {}).get("anim") if isinstance(quyet_dinh, dict) else None
    for khoa, kk in (("vao", "tu"), ("ra", "toi")):
        v = anim.get(khoa)
        if v is None:
            v = dict(_qd(qa, khoa, lop))
        elif isinstance(v, str):
            v = {"kieu": v}
        else:
            v = dict(v)
        kieu = v.get("kieu") or "none"
        v["kieu"] = kieu
        if kieu == "none":
            v.setdefault("dai", 0.0); v.setdefault("ease", "linear")
        else:
            if v.get("dai") is None:
                goc = (qa or {}).get(khoa) if isinstance(qa, dict) else None
                v["dai"] = goc.get("dai") if isinstance(goc, dict) and goc.get("dai") is not None else _qd(qa, khoa + ".dai", lop)
            if v.get("ease") is None:
                if kieu == "typewriter":
                    v["ease"] = "step"
                else:
                    goc = (qa or {}).get(khoa) if isinstance(qa, dict) else None
                    v["ease"] = goc.get("ease") if isinstance(goc, dict) and goc.get("ease") else _qd(qa, khoa + ".ease", lop)
        if not isinstance(v.get(kk), dict):
            if kieu in MAC_DINH["kieu_cau_truc"]:
                v[kk] = dict(MAC_DINH["kieu_cau_truc"][kieu])
            elif kieu in MAC_DINH["kieu_can_quyet"]:
                v[kk] = dict(_qd(qa, "kieu." + kieu, lop))
            else:
                raise _thieu("anim.%s.%s" % (khoa, kk), lop, "kiểu `%s` không biết — ghi rõ tu/toi" % kieu)
        v["dai"] = float(v.get("dai") or 0)
        anim[khoa] = v
    if anim.get("so_le") is None:
        anim["so_le"] = _qd(qa, "so_le", lop)
    if anim.get("keyframe_dai") is None:
        anim["keyframe_dai"] = _qd(qa, "keyframe_dai", lop)
    if anim.get("keyframe_ease") is None:
        anim["keyframe_ease"] = _qd(qa, "keyframe_ease", lop)
    kfs = []
    for kf in anim.get("keyframes") or []:
        kf = dict(kf)
        if kf.get("dai") is None:
            kf["dai"] = anim["keyframe_dai"]
        if kf.get("ease") is None:
            kf["ease"] = anim["keyframe_ease"]
        kfs.append(kf)
    if kfs:
        anim["keyframes"] = kfs
    anim[_DA_DAY] = True
    return anim


def _kep(u):
    return 0.0 if u < 0 else 1.0 if u > 1 else float(u)


def ease(ten, u):
    """u 0..1 → 0..1 (back/spring có thể vượt 1). linear · in · out · in_out · back · spring · expo · step"""
    u = _kep(u)
    e = MAC_DINH["ease"]
    if ten in (None, "", "linear"):
        return u
    if ten == "in":
        return u * u * u
    if ten == "out":
        return 1 - (1 - u) ** 3
    if ten == "in_out":
        return 4 * u * u * u if u < 0.5 else 1 - ((-2 * u + 2) ** 3) / 2
    if ten == "back":                   # ease-out back: vượt đích rồi về
        c1 = e["back_overshoot"]; c3 = c1 + 1
        return 1 + c3 * (u - 1) ** 3 + c1 * (u - 1) ** 2
    if ten == "spring":                 # dao động tắt dần quanh đích
        if u >= 1:
            return 1.0
        d, f = e["spring_tat_dan"], e["spring_tan_so"]
        return 1 - math.exp(-d * u) * math.cos(2 * math.pi * f * u)
    if ten == "expo":
        return 1.0 if u >= 1 else 1 - 2 ** (-e["expo_muc"] * u)
    if ten == "step":
        return 1.0 if u >= 1 else 0.0
    return u


def _tron(a, b, u):
    return a + (b - a) * u


def _vao_ra(anim, khoa):
    """anim[khoa] ('vao'|'ra') đã qua day_du → {"kieu","dai","ease","tu"/"toi": {...}}; chưa đủ → thieu_truong (không tự điền)"""
    v = anim.get(khoa) if isinstance(anim, dict) else None
    if isinstance(v, str):
        v = {"kieu": v}
    if v is None:
        if isinstance(anim, dict) and anim.get(_DA_DAY):
            v = {"kieu": "none"}
        else:
            raise _thieu("anim." + khoa, goi_y="anim chưa qua day_du(anim, quyet_dinh)")
    v = dict(v)
    kieu = v.get("kieu") or "none"
    v["kieu"] = kieu
    k = "tu" if khoa == "vao" else "toi"
    if kieu == "none":
        v.setdefault("dai", 0.0); v.setdefault("ease", "linear"); v.setdefault(k, {})
    else:
        if v.get("dai") is None:
            raise _thieu("anim.%s.dai" % khoa)
        if v.get("ease") is None:
            v["ease"] = "step" if kieu == "typewriter" else None
            if v["ease"] is None:
                raise _thieu("anim.%s.ease" % khoa)
        if not isinstance(v.get(k), dict):
            if kieu in MAC_DINH["kieu_cau_truc"]:
                v[k] = dict(MAC_DINH["kieu_cau_truc"][kieu])
            else:
                raise _thieu("anim.%s.%s" % (khoa, k), goi_y="kiểu `%s` cần trạng thái đầu/cuối (quyet_dinh anim.kieu.%s)" % (kieu, kieu))
    v["dai"] = float(v["dai"] or 0)
    return v


def _ap(tt, muc, u):
    """tt (trạng thái) ← trộn từ `muc` (dict trường→giá trị) về gốc theo u (u=1 là gốc)"""
    for k, gia in muc.items():
        if k not in TRANG_THAI_GOC:
            continue
        goc = TRANG_THAI_GOC[k]
        g = _tron(float(gia), goc, u)
        if k in _NHAN:
            tt[k] *= g if goc != 0 else g
        else:
            tt[k] += g
    return tt


def _kf_dai(anim, kf):
    d = kf.get("dai")
    if d is None:
        d = anim.get("keyframe_dai")
    if d is None:
        raise _thieu("anim.keyframe_dai")
    return float(d)


def _kf_ease(anim, kf):
    e = kf.get("ease") or anim.get("keyframe_ease")
    if e is None:
        raise _thieu("anim.keyframe_ease")
    return e


def so_le_cua(anim):
    s = (anim or {}).get("so_le")
    if s is None:
        raise _thieu("anim.so_le")
    return float(s)


def trang_thai(anim, lt, dur, tre=0.0):
    """Hợp nhất vào/ra/keyframes → {"opacity","scale","x","y","rot","blur","wipe"}.
    lt: giây từ t0; dur: thời lượng lớp; tre: trễ thêm cho phần vào (dùng cho so le)."""
    anim = anim or {}
    tt = dict(TRANG_THAI_GOC)
    # --- vào ---
    v = _vao_ra(anim, "vao")
    if v["dai"] > 0 and v["tu"]:
        u = ease(v["ease"], (lt - tre) / v["dai"])
        if (lt - tre) < v["dai"]:
            _ap(tt, v["tu"], u)
    elif v["tu"] and lt < tre:          # dai=0 nhưng có trễ: ẩn tới khi đến lượt
        _ap(tt, v["tu"], 0.0)
    # --- ra ---
    r = _vao_ra(anim, "ra")
    if r["dai"] > 0 and r["toi"] and lt > dur - r["dai"]:
        u = ease(r["ease"], (lt - (dur - r["dai"])) / r["dai"])
        _ap(tt, r["toi"], 1.0 - u)
    # --- keyframes: tại t (giây từ t0) trượt từ giá trị trước tới giá trị mới trong "dai" ---
    kfs = anim.get("keyframes") or []
    if kfs:
        hien = {}                       # trường → giá trị hiện tại (đã đạt)
        for kf in sorted(kfs, key=lambda k: float(k.get("t", 0))):
            t = float(kf.get("t", 0)); dai = _kf_dai(anim, kf)
            if lt < t:
                break
            u = ease(_kf_ease(anim, kf), (lt - t) / dai) if dai > 0 else 1.0
            for k, gia in kf.items():
                if k in TRANG_THAI_GOC:
                    truoc = hien.get(k, TRANG_THAI_GOC[k])
                    hien[k] = _tron(truoc, float(gia), u)
        for k, g in hien.items():
            if k in _NHAN:
                tt[k] *= g
            else:
                tt[k] += g
    tt["opacity"] = _kep(tt["opacity"]); tt["wipe"] = _kep(tt["wipe"])
    if tt["blur"] < 0:
        tt["blur"] = 0.0
    if tt["scale"] < 0:
        tt["scale"] = 0.0
    return tt


def tach_chi_so(anim, n, lt):
    """stagger: → [u_i] 0..1 tiến độ phần vào của từng phần i (trễ i*so_le)."""
    anim = anim or {}
    v = _vao_ra(anim, "vao")
    so_le = so_le_cua(anim)
    dai = max(v["dai"], 1e-6)
    return [_kep((lt - i * so_le) / dai) for i in range(n)]


def trang_thai_phan(anim, n, lt, dur):
    """trạng thái đầy đủ cho từng phần (vào so le, ra & keyframes chung)."""
    anim = anim or {}
    so_le = so_le_cua(anim)
    return [trang_thai(anim, lt, dur, tre=i * so_le) for i in range(n)]


def dai_vao_ra(anim):
    """(dai_vao, dai_ra) giây — để biết khung nào tĩnh"""
    return _vao_ra(anim or {}, "vao")["dai"], _vao_ra(anim or {}, "ra")["dai"]


def dang_chuyen_dong(anim, lt, dur, n_phan=1):
    """True nếu tại lt lớp đang trong vào/ra/keyframe (khung thay đổi theo thời gian)"""
    anim = anim or {}
    dv, dr = dai_vao_ra(anim)
    so_le = so_le_cua(anim) if n_phan > 1 else 0.0
    if lt < dv + so_le * (n_phan - 1) + 1e-6:
        return True
    if lt > dur - dr - 1e-6:
        return True
    for kf in anim.get("keyframes") or []:
        t = float(kf.get("t", 0)); dai = _kf_dai(anim, kf)
        if t - 1e-6 <= lt <= t + dai + 1e-6:
            return True
    return False


def he_so_nhoe_dong(anim):
    """anim.nhoe_dong (hệ số nhoè theo hướng chuyển động) → float ≥ 0"""
    try:
        return max(0.0, float((anim or {}).get("nhoe_dong", MAC_DINH["nhoe_dong"]) or 0))
    except Exception:
        return 0.0


def van_toc(anim, lt, dur, fps, tre=0.0):
    """(vx, vy) px/khung của trạng thái dịch chuyển tại lt (sai phân giữa, nửa khung mỗi bên) — cho nhoè theo hướng"""
    dt = 0.5 / max(float(fps), 1.0)
    a = trang_thai(anim, lt - dt, dur, tre); b = trang_thai(anim, lt + dt, dur, tre)
    return (b["x"] - a["x"]), (b["y"] - a["y"])


def vet_nhoe_toi_da(anim, fps):
    """ước lượng vệt nhoè dài nhất (px) của vào/ra theo nhoe_dong — để nới hộp sprite. ease out/back/spring: đỉnh ≈ 3× tốc độ trung bình"""
    k = he_so_nhoe_dong(anim)
    if k <= 0:
        return 0.0
    L = 0.0
    for kh, kk in (("vao", "tu"), ("ra", "toi")):
        v = _vao_ra(anim or {}, kh)
        d = max(float(v.get("dai") or 0), 1e-6)
        m = v.get(kk) or {}
        q = math.hypot(float(m.get("x", 0) or 0), float(m.get("y", 0) or 0))
        if q > 0:
            L = max(L, 3.0 * q / (d * float(fps)) * k)
    for kf in (anim or {}).get("keyframes") or []:
        d = max(_kf_dai(anim, kf), 1e-6)
        q = math.hypot(float(kf.get("x", 0) or 0), float(kf.get("y", 0) or 0))
        if q > 0:
            L = max(L, 3.0 * q / (d * float(fps)) * k)
    return min(L, MAC_DINH["nhoe_dong_toi_da"])


def bien_do(anim, n_phan=1):
    """biên độ dịch chuyển/scale tối đa của anim → {"x","y","scale","blur"} (để tính lề hộp sprite)"""
    anim = anim or {}
    mx = my = 0.0; ms = 1.0; mb = 0.0; r3 = 0.0
    for v in (_vao_ra(anim, "vao").get("tu", {}), _vao_ra(anim, "ra").get("toi", {}), *(anim.get("keyframes") or [])):
        mx = max(mx, abs(float(v.get("x", 0)))); my = max(my, abs(float(v.get("y", 0))))
        r3 = max(r3, abs(float(v.get("rot_x", 0))), abs(float(v.get("rot_y", 0))))
        s = float(v.get("scale", 1))
        ms = max(ms, s if s > 1 else 1.0)
        mb = max(mb, float(v.get("blur", 0)))
    e_back = MAC_DINH["ease"]["back_overshoot"] * 0.1 + 1.0     # back vượt ~10%
    if any((_vao_ra(anim, k).get("ease") in ("back", "spring")) for k in ("vao", "ra")):
        ms = max(ms, e_back)
    return {"x": mx, "y": my, "scale": ms, "blur": mb, "rot3d": r3}
