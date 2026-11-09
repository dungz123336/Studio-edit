# -*- coding: utf-8 -*-
"""Ghép bằng ffmpeg — CACHE THEO ĐOẠN.
dung_base(du_an, ke_hoach, ctx=None) → base-<hash>.mp4: nguồn (hwaccel nếu có) → -ss/-t từng đoạn cat → concat → camera
    → chỉnh màu/LUT (mau_video, chỉ khi viec.json cho phép) → nen_moi → mã hoá; KEYFRAME ép đúng ranh giới đoạn (cắt đoạn nhanh, chính xác).
chia_doan(cat, fps) → [(f0, f1)] khung — ranh giới theo điểm cắt cat / mỗi ~8 s (6–10 s); chỉ phụ thuộc cat + fps ⇒ ổn định khi sửa lớp.
chuan_bi_khuc + dung_khuc → cache/khuc/_khuc-<băm>.mp4: base[đoạn] + mọi lớp giao đoạn (sprite PNG cắt theo đoạn · video/ảnh trực tiếp
    có hoà trộn) + flash. Băm = base + đoạn + nội dung lớp giao đoạn + phiên bản engine ⇒ sửa 1 lớp chỉ dựng lại đoạn chứa nó.
    1.2.21 (B1) lớp sau người: base → overlay(lớp sau_nguoi) → overlay(người = [base][alpha-tl]alphamerge) → overlay(lớp khác); alpha-tl
    (dung_alpha_tl) tách MỘT lần cho hợp mọi khoảng, cắt theo đoạn như base; băm khúc gồm tên alpha-tl + khoảng người.
dung_am(du_an, ke_hoach, ctx) → cache/am-tp-<băm>.m4a: trộn âm cả bài MỘT lần (giọng theo cat + nhạc + sfx + loudnorm).
noi(du_an, khuc, am, ra, tong) → concat demuxer `-c copy` + mux âm → thanh-pham.mp4."""
import os, re, shutil

try:
    import chung
except ImportError:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import chung
from dung import camera as _camera
from dung import am as _am

TOI_DA_INPUT = 56          # mỗi lượt overlay
DOAN_MUC, DOAN_MIN, DOAN_MAX = 8.0, 6.0, 10.0
HOA_TRON = {"normal": "normal", "screen": "screen", "add": "addition", "multiply": "multiply", "overlay": "overlay",
            "soft_light": "softlight", "lighten": "lighten", "darken": "darken"}
MAU_TRUNG_TINH = {"screen": "black", "addition": "black", "lighten": "black", "multiply": "white", "darken": "white",
                  "overlay": "0x808080", "softlight": "0x808080", "normal": "black"}       # màu "không đổi gì" của từng chế độ (để mờ vào/ra)
_PHAN_CUNG = None
_PHIEN = None


def phien_ghep():
    global _PHIEN
    if _PHIEN is None:
        g = os.path.dirname(os.path.abspath(__file__))
        _PHIEN = chung.bam([chung.bam(os.path.join(g, f)) for f in ("ghep.py", "camera.py")])
    return _PHIEN


def phan_cung():
    global _PHAN_CUNG
    if _PHAN_CUNG is None:
        try:
            _PHAN_CUNG = dict(chung.phan_cung())
        except Exception:
            _PHAN_CUNG = {"hwaccel": "none", "encoder": "libx264", "luong": os.cpu_count() or 4}
    return _PHAN_CUNG


def ma_hoa_args(encoder=None, chat_luong="that"):
    enc = encoder or phan_cung().get("encoder", "libx264")
    if enc == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-cq", "19", "-b:v", "0", "-pix_fmt", "yuv420p"]
    if enc == "h264_qsv":
        return ["-c:v", "h264_qsv", "-global_quality", "20", "-pix_fmt", "nv12"]
    if enc == "h264_amf":
        return ["-c:v", "h264_amf", "-quality", "balanced", "-rc", "cqp", "-qp_i", "20", "-qp_p", "22", "-pix_fmt", "yuv420p"]
    if enc == "h264_videotoolbox":                         # 1.2.21: Mac
        return ["-c:v", "h264_videotoolbox", "-b:v", "12M" if chat_luong == "that" else "6M", "-pix_fmt", "yuv420p"]
    crf = "18" if chat_luong == "that" else "23"
    return ["-c:v", "libx264", "-preset", chung.hang_may()["x264_preset"], "-crf", crf, "-pix_fmt", "yuv420p"]


_INFO = {}


def _info(duong):
    """ffprobe có cache theo đường dẫn (một tiến trình dựng hỏi cùng nguồn nhiều lần)"""
    if duong not in _INFO:
        try:
            _INFO[duong] = chung.ffprobe(duong) or {}
        except Exception:
            _INFO[duong] = {}
    return _INFO[duong]


_HW_KHOA_DUNG = set()        # khoá (codec|cỡ) của các nguồn đã bật hwaccel trong LỆNH đang dựng (1.2.19)


def _khoa_hw(duong):
    """khoá nhớ lỗi hwaccel theo nguồn: codec + cỡ (hevc 10-bit 4K lỗi CUDA trên card cũ nhưng h264 1080p vẫn chạy)"""
    try:
        inf = chung.ffprobe(duong) or {}
        return f"{inf.get('codec') or '?'}|{'4k' if max(inf.get('w') or 0, inf.get('h') or 0) > 2200 else 'hd'}"
    except Exception:
        return None


def _loi_con_hieu_luc(pc, loai, khoa):
    """R4b 1.2.21: lỗi GPU nhớ bền có THỜI HẠN — có chung.loi_con_hieu_luc(pc, loai, khoa) (R4a) thì hỏi nó; chưa có → mọi giá trị
    (True cũ hoặc {"lan","luc","loi"}) đều coi là còn hiệu lực như trước."""
    v = (pc.get(loai) or {}).get(khoa)
    if not v:
        return False
    f = getattr(chung, "loi_con_hieu_luc", None)
    if f is None:
        return True
    try:
        return bool(f(pc, loai, khoa))
    except Exception:
        return True


def _hwaccel_args(duong=None):
    pc = phan_cung()
    hw = pc.get("hwaccel", "none")
    if not hw or hw == "none":
        return []
    if duong:                                         # 1.2.19 (B3): nguồn từng lỗi hwaccel (nhớ trong phan-cung.json) → CPU thẳng, không thử lại mỗi bước
        k = _khoa_hw(duong)
        if k and _loi_con_hieu_luc(pc, "hwaccel_loi", k):
            return []
        if k:
            _HW_KHOA_DUNG.add(k)
    return ["-hwaccel", hw]


# 1.2.21 (B1): phân loại theo DÒNG LỖI, không theo chuỗi "h264_nvenc" xuất hiện trong mọi stderr dùng nvenc ("Stream mapping … -> h264 (h264_nvenc)")
# — trước đây lỗi GIẢI MÃ CUDA ("Decoding error … [CUDA @ …]") bị coi là lỗi encoder → khách mất NVENC vĩnh viễn tới khi bấm Đo lại.
_DONG_ENC = re.compile(r"^\s*\[(h264|hevc|av1)_(nvenc|amf|qsv|videotoolbox) @ |EncodePicture|Error while opening encoder|Cannot load nvEncodeAPI"
                       r"|No capable devices|OpenEncodeSessionEx|nvenc API|NvEncOpenEncodeSessionEx", re.I | re.M)
_DONG_HW = re.compile(r"Decoding error|Error while decoding|hwaccel|cuvid|nvdec|\[AVHWDeviceContext|d3d11va|dxva2|vaapi|hw device|hardware"
                      r"|(qsv|mfx).*(decod|session)|(decod).*(qsv|mfx)|\[CUDA @|cuda", re.I)
_LOI_HW = re.compile(r"hwaccel|cuda|nvdec|cuvid|qsv|d3d11|dxva|vaapi|videotoolbox|hardware|hw device", re.I)     # (giữ cho mã cũ tham chiếu)
_LOI_ENC = _DONG_ENC                                                                                              # (giữ tên cũ: dung.py cũ tham chiếu)


def phan_loai_loi(err, ma=1, co_hwaccel=False, enc="libx264"):
    """stderr ffmpeg + mã thoát → {"encoder": bool (lỗi BỘ MÃ HOÁ phần cứng — nhớ bền encoder_loi), "hwaccel": bool (lỗi GIẢI MÃ phần cứng —
    nhớ bền hwaccel_loi theo nguồn), "treo": bool (mã 124), "dong": dòng lỗi quyết định}.
    - encoder: có DÒNG lỗi bắt đầu `[h264_nvenc @`/`[hevc_nvenc @`/`[h264_amf @`/`[h264_qsv @`/`[h264_videotoolbox @` hoặc chứa EncodePicture /
      Error while opening encoder / Cannot load nvEncodeAPI / No capable devices / OpenEncodeSessionEx; "Stream mapping … (h264_nvenc)" KHÔNG tính.
    - hwaccel: dòng lỗi chứa Decoding error / Error while decoding / hwaccel / cuvid / nvdec / [AVHWDeviceContext / d3d11va / dxva2 / qsv phía giải mã /
      [CUDA @ …]; hoặc TREO (124) khi lệnh có -hwaccel.
    - TREO với encoder phần cứng mà KHÔNG có dòng lỗi encoder → encoder=False (chỉ tắt encoder trong PHIÊN, không ghi encoder_loi bền)."""
    err = err or ""
    dong = [d for d in err.splitlines() if d.strip()]
    treo = ma == 124
    d_enc = next((d for d in dong if _DONG_ENC.search(d)), None)
    d_hw = next((d for d in dong if _DONG_HW.search(d) and not _DONG_ENC.search(d)), None)
    encoder = bool(enc and enc != "libx264" and d_enc)
    hwaccel = bool(co_hwaccel and (d_hw or treo))
    return {"encoder": encoder, "hwaccel": hwaccel, "treo": treo, "dong": (d_enc or d_hw or (dong[-1] if dong else ""))[:200]}


def _nho_hwaccel_loi(ks):
    """nhớ VĨNH VIỄN (phan-cung.json, đọc-sửa-ghi có khoá — 1.2.21) các nguồn codec|cỡ mà hwaccel lỗi (kể cả TREO/mã 124).
    Bác sĩ "Đo lại" → xoá hết (thử lại từ đầu)."""
    ks = set(k for k in ks if k)
    if not ks:
        return
    for k in ks:
        chung.nho_loi_phan_cung("hwaccel_loi", k)
    luc = __import__("time").strftime("%Y-%m-%d %H:%M")        # R4b: cùng dạng {"lan","luc"} như tệp (chung.loi_con_hieu_luc coi True cũ là hết hạn)
    phan_cung().setdefault("hwaccel_loi", {}).update({k: {"lan": 1, "luc": luc, "loi": ""} for k in ks})


def _nho_encoder_loi(enc, err):
    """1.2.21: encoder phần cứng lỗi (kể cả mã 124 TREO) → phan-cung.json encoder_loi[enc] {lan, luc, loi}; phiên này và mọi tiến trình
    sau dùng libx264 tới khi khách bấm "Đo lại" (phan_cung(lam_moi=True) xoá encoder_loi)."""
    if not enc or enc == "libx264":
        return
    chung.nho_loi_phan_cung("encoder_loi", enc, err)
    pc = phan_cung()
    pc.setdefault("encoder_loi", {})[enc] = {"lan": 1, "luc": __import__("time").strftime("%Y-%m-%d %H:%M"), "loi": str(err)[-200:]}   # R4b: cùng dạng tệp (luc → thời hạn)
    pc["encoder"] = "libx264"


def _chay(cmd, du_an, buoc, timeout=None, cwd=None, dur=None):
    """1.2.21: qua chung.chay_ffmpeg (-progress; treo = không tiến ffmpeg_im_toi_da_giay; không trần 3600 s). `timeout` giữ cho mã cũ, không dùng."""
    return chung.chay_ffmpeg(cmd, du_an, buoc, dur=dur, cwd=cwd)


def _chay_co_du_phong(cmd_fn, du_an, buoc, cwd=None, dur=None):
    """thử (hwaccel, encoder phần cứng) → nếu lỗi thử lại CPU thuần.
    1.2.21: lỗi do hwaccel (regex hoặc TREO/mã 124 khi lệnh có -hwaccel) → nhớ hwaccel_loi theo codec|cỡ NGAY; lỗi do encoder phần cứng
    (regex hoặc TREO khi encoder ≠ libx264) → nhớ encoder_loi; lỗi khác (filter sai, ổ đầy…) → vẫn thử CPU nhưng KHÔNG tắt hwaccel cả phiên."""
    _HW_KHOA_DUNG.clear()
    pc = phan_cung()
    hw0, enc0 = pc.get("hwaccel", "none") or "none", pc.get("encoder", "libx264") or "libx264"
    ma, err = _chay(cmd_fn(True, None), du_an, buoc, cwd=cwd, dur=dur)
    if ma == 0:
        return True
    ks = set(_HW_KHOA_DUNG)
    err = err or ""
    pl = phan_loai_loi(err, ma, co_hwaccel=bool(ks) and hw0 != "none", enc=enc0)
    treo = pl["treo"]
    loi_hw, loi_enc = pl["hwaccel"], pl["encoder"]
    if loi_hw:
        chung.log(du_an, f"{buoc}: hwaccel {hw0} lỗi với {', '.join(sorted(ks))}" + (" (TREO)" if treo else "") + f" → nhớ, lần sau giải mã CPU ({pl['dong'][:120]})")
        _nho_hwaccel_loi(ks)
        pc["hwaccel"] = "none"
    if loi_enc:
        chung.log(du_an, f"{buoc}: bộ mã hoá {enc0} lỗi → nhớ, dùng libx264 tới khi Đo lại ({pl['dong'][:120]})")
        _nho_encoder_loi(enc0, pl["dong"] or err)
    elif treo and enc0 != "libx264":          # treo mà không có dòng lỗi encoder → chỉ tắt encoder trong PHIÊN này, không ghi bền
        chung.log(du_an, f"{buoc}: TREO với {enc0} nhưng không có dòng lỗi encoder → phiên này dùng libx264 (không ghi encoder_loi)")
        pc["encoder"] = "libx264"
    if not loi_hw and not loi_enc:
        chung.log(du_an, f"{buoc}: lỗi không do phần cứng ({err.strip().splitlines()[-1][:160] if err.strip() else 'mã %s' % ma}) → thử lại CPU thuần một lần")
    chung.log(du_an, "thử lại không hwaccel / libx264 (%s)" % buoc)
    ma, err = _chay(cmd_fn(False, "libx264"), du_an, buoc + " (dự phòng)", cwd=cwd, dur=dur)
    if ma != 0:
        raise RuntimeError("ffmpeg thất bại (%s): %s" % (buoc, err[-800:]))
    return True


def nguon_cua(ke_hoach, du_an):
    """[đường dẫn nguồn] từ ke_hoach["nguon"] hoặc viec.json"""
    ng = ke_hoach.get("nguon")
    if not ng and du_an:
        v = chung.doc_json(os.path.join(du_an, "viec.json"), {}) or {}
        ng = v.get("nguon") or []
    return [n["duong"] if isinstance(n, dict) else n for n in ng or []]


def cat_cua(ke_hoach, du_an, nguon):
    cat = ke_hoach.get("cat")
    if cat:
        return [{"src": int(s.get("src", 0)), "a": float(s["a"]), "b": float(s["b"])} for s in cat]
    if du_an:
        dx = chung.doc_json(os.path.join(du_an, "doc", "cat-de-xuat.json"))
        if dx and dx.get("giu"):
            return [{"src": int(s.get("src", 0)), "a": float(s["a"]), "b": float(s["b"])} for s in dx["giu"]]
    if nguon:
        info = chung.ffprobe(nguon[0]) or {"dur": 10}
        return [{"src": 0, "a": 0.0, "b": float(info["dur"])}]
    return []


# ======================================================================== đoạn ====
def chia_doan(cat, fps, muc=DOAN_MUC, lo=DOAN_MIN, hi=DOAN_MAX):
    """→ [(f0, f1)] chỉ số khung [f0, f1) từng đoạn. Ưu tiên điểm cắt cat gần mốc ~muc giây trong [lo, hi]; chỉ phụ thuộc cat+fps."""
    fps = float(fps)
    tong = sum(float(s["b"]) - float(s["a"]) for s in cat or [])
    N = max(1, int(round(tong * fps)))
    diem, t = [], 0.0
    for s in (cat or [])[:-1]:
        t += float(s["b"]) - float(s["a"]); diem.append(int(round(t * fps)))
    ra, f = [], 0
    while N - f > hi * fps:
        con = (N - f) / fps
        muc_ = muc if con >= muc + lo else con / 2
        ung = [d for d in diem if f + lo * fps * (0.5 if muc_ < lo else 1) <= d <= f + hi * fps and N - d >= 2 * fps]
        nxt = min(ung, key=lambda d: abs(d - (f + muc_ * fps))) if ung else f + int(round(muc_ * fps))
        ra.append((f, nxt)); f = nxt
    ra.append((f, N))
    return ra


# ======================================================================== chỉnh màu ====
def _chuan_lut(du_an, lut_path):
    """chép LUT vào cache với tên ASCII (lut3d trên Windows khó thoát đường dẫn có dấu/khoảng trắng/":") → tên file"""
    if not lut_path or not os.path.isfile(lut_path):
        return None
    cache = os.path.join(du_an, "cache"); os.makedirs(cache, exist_ok=True)
    ten = f"lut-{chung.bam(lut_path)}{os.path.splitext(lut_path)[1].lower()}"
    dich = os.path.join(cache, ten)
    if not os.path.isfile(dich):
        shutil.copyfile(lut_path, dich)
    return ten


def bo_loc_mau(mv, lut_ten, vao, ra):
    """mau_video {duong (LUT đã giải), cuong_do 0..1 (độ mạnh LUT), sang, tuong_phan, bao_hoa, am_lanh: −1..1 (am_lanh +ấm/−lạnh)}
    → danh sách filter (ffmpeg chạy với cwd = cache để lut3d đọc tên ASCII). Không có gì → []."""
    if not mv:
        return []
    fl, cur = [], vao
    cd = max(0.0, min(1.0, float(mv.get("cuong_do", 1.0))))
    if lut_ten and cd > 0.001:
        if cd >= 0.999:
            fl.append(f"{cur}lut3d=file={lut_ten}:interp=tetrahedral[mlut]")
        else:
            fl.append(f"{cur}split=2[mg0][mg1]")
            fl.append(f"[mg1]lut3d=file={lut_ten}:interp=tetrahedral[mg2]")
            fl.append(f"[mg0][mg2]blend=all_mode=normal:all_opacity={cd:.3f}[mlut]")
        cur = "[mlut]"
    sang = float(mv.get("sang", 0) or 0); tp = float(mv.get("tuong_phan", 0) or 0); bh = float(mv.get("bao_hoa", 0) or 0)
    al = float(mv.get("am_lanh", 0) or 0)
    ch = []
    if abs(sang) > 1e-3 or abs(tp) > 1e-3 or abs(bh) > 1e-3:
        ch.append(f"eq=brightness={0.25 * sang:.4f}:contrast={1 + 0.5 * tp:.4f}:saturation={max(0.0, 1 + bh):.4f}")
    if abs(al) > 1e-3:
        ch.append(f"colortemperature=temperature={int(6500 - 3000 * al)}:pl=0.5")
    if ch:
        fl.append(f"{cur}{','.join(ch)}[mchinh]")
        cur = "[mchinh]"
    if not fl:
        return []
    fl.append(f"{cur}null{ra}")
    return fl


# ======================================================================== base ====
def _doan_nguon(nguon, cat, hw):
    args = []; nhan = []
    for k, s in enumerate(cat):
        args += (_hwaccel_args(nguon[int(s.get("src", 0))]) if hw else []) + ["-ss", "%.4f" % s["a"], "-t", "%.4f" % (s["b"] - s["a"]), "-i", nguon[int(s.get("src", 0))]]
        nhan.append(k)
    return args, nhan


def _bieu_thuc_cam(camera, W, H, fps, ke_hoach):
    """camera.bieu_thuc_crop với ease mặc định từ quyet_dinh["camera"]["ease"] (A3, 1.2.21) — camera.py cũ không có tham số thì gọi như cũ"""
    qd = ((ke_hoach or {}).get("quyet_dinh") or {}).get("camera") or {}
    try:
        return _camera.bieu_thuc_crop(camera, W, H, fps, ease_mac_dinh=qd.get("ease") if isinstance(qd, dict) else None)
    except TypeError:
        return _camera.bieu_thuc_crop(camera, W, H, fps)


def _zmax(camera):
    return max([1.0] + [float(k.get("z", 1) or 1) for k in camera or []])


def _chuoi_cat(nhan, W, H, fps, kich_thuoc, cat, hau_to="", zmax=1.0, nguon=None):
    """filter: từng input → cắt tỉ lệ (cover) + [lọc màu vào: HDR→SDR / 10-bit→8-bit (1.2.21, chung.loc_mau_vao)] + scale chung (ma trận BT.709)
    → concat → [cat<hau_to>]. Cỡ chung = cover của nguồn đầu nhưng KHÔNG lớn hơn W×H×zmax (camera zoom lớn nhất): nguồn 4K mà không zoom
    thì thu thẳng về khổ ra (đỡ một lần scale khổ lớn — nguồn HEVC 1728×3072 nhanh hơn rõ)."""
    sw, sh = kich_thuoc.get(int(cat[0].get("src", 0)), (W, H))
    s = max(W / sw, H / sh)
    cw, ch = W / s, H / s
    if cw > W * zmax:
        cw, ch = W * zmax, H * zmax
    cw, ch = int(round(cw)) // 2 * 2, int(round(ch)) // 2 * 2
    fl = []
    for k in nhan:
        lm = ""
        if nguon:
            try:
                lm = chung.loc_mau_vao(_info(nguon[int(cat[k].get("src", 0))]))
            except Exception:
                lm = ""
        fl.append(f"[{k}:v]setpts=PTS-STARTPTS,fps={fps},crop=w='min(iw,ih*{W}/{H})':h='min(ih,iw*{H}/{W})',"
                  + (lm + "," if lm else "") + f"scale={cw}:{ch}:flags=bicubic:out_color_matrix=bt709,setsar=1[c{k}{hau_to}]")
    if len(nhan) == 1:
        fl.append(f"[c{nhan[0]}{hau_to}]null[cat{hau_to}]")
    else:
        fl.append("".join(f"[c{k}{hau_to}]" for k in nhan) + f"concat=n={len(nhan)}:v=1:a=0[cat{hau_to}]")
    return fl, (cw, ch)


def _kich_thuoc_nguon(nguon):
    kt = {}
    for i, p in enumerate(nguon):
        inf = chung.ffprobe(p)
        if inf:
            kt[i] = (inf["w"], inf["h"])
    return kt


def _alpha_cua(ke_hoach):
    alpha = ke_hoach.get("alpha")          # {"duong": alpha-<hash>.mp4 (xám), "a": giây gốc bắt đầu, "dur_nguon"} hoặc đường dẫn (a=0)
    a, dn = 0.0, None
    if isinstance(alpha, dict):
        a, dn = float(alpha.get("a") or 0), alpha.get("dur_nguon")
        alpha = alpha.get("duong")
    return alpha, a, dn


def _chuoi_alpha(args, ia, alpha, alpha_a, alpha_dur, cat, nhan, W, H, fps, kich_thuoc, cam, zmax=1.0):
    """rãnh alpha (giây gốc của proxy) → cắt theo cat + camera như hình → [alp] (gray, W×H, dòng thời gian thành phẩm)"""
    args += ["-i", alpha]
    cw, ch = _chuoi_cat(nhan, W, H, fps, kich_thuoc, cat, zmax=zmax)[1]
    dn = float(alpha_dur or max(s["b"] for s in cat) + 1)
    fl = [f"[{ia}:v]fps={fps},tpad=start_duration={alpha_a:.4f}:start_mode=add:color=black,"
          f"tpad=stop_duration={dn:.3f}:stop_mode=add:color=black,split={len(cat)}" + "".join(f"[as{k}]" for k in range(len(cat)))]
    for k, s in enumerate(cat):
        fl.append(f"[as{k}]trim={s['a']:.4f}:{s['b']:.4f},setpts=PTS-STARTPTS,crop=w='min(iw,ih*{W}/{H})':h='min(ih,iw*{H}/{W})',scale={cw}:{ch}:flags=bicubic,setsar=1[a{k}]")
    fl.append("".join(f"[a{k}]" for k in range(len(cat))) + (f"concat=n={len(cat)}:v=1:a=0" if len(cat) > 1 else "null") + "[acat]")
    fl.append(f"[acat]{cam},format=gray[alp]")
    return fl


def khoa_base(du_an, ke_hoach):
    W, H = [int(v) for v in (ke_hoach.get("khung") or [1080, 1920])]
    fps = float(ke_hoach.get("fps") or 30)
    nguon = nguon_cua(ke_hoach, du_an)
    cat = cat_cua(ke_hoach, du_an, nguon)
    alpha, _, _ = _alpha_cua(ke_hoach)
    mv = ke_hoach.get("mau_video") or None
    return chung.bam({"cat": cat, "camera": ke_hoach.get("camera") or [], "nen_moi": ke_hoach.get("nen_moi") or [],
                      "nguon": [chung.bam(p) for p in nguon], "W": W, "H": H, "fps": fps, "alpha": chung.bam(alpha) if alpha else None,
                      "mau": (dict(mv, duong=chung.bam(mv.get("duong")) if mv.get("duong") else None) if mv else None), "v": 7,
                      "qd_cam": (ke_hoach.get("quyet_dinh") or {}).get("camera")})   # R4b: ease camera mặc định của kênh nằm trong base → đổi là dựng lại


def base_hop_le(ra, tong, fps=30.0):
    """1.2.21: base cache chỉ tin khi ffprobe đọc được và thời lượng ≈ tổng cat (bị giết/ổ đầy để lại tệp cụt → dựng lại)"""
    try:
        if not os.path.isfile(ra) or os.path.getsize(ra) < 1000:
            return False
        inf = chung.ffprobe(ra) or {}
        d = float(inf.get("dur") or 0)
        return d > 0 and abs(d - float(tong)) <= max(0.5, 2.0 / max(1.0, float(fps)))
    except Exception:
        return False


def dung_base(du_an, ke_hoach, ctx=None, lam_moi=False):
    """→ đường dẫn base.mp4 (cache du_an/cache/base-<hash>.mp4)"""
    W, H = ke_hoach.get("khung") or [1080, 1920]; W, H = int(W), int(H)
    fps = float(ke_hoach.get("fps") or 30)
    nguon = nguon_cua(ke_hoach, du_an)
    if not nguon:
        raise ValueError("không có nguồn video")
    cat = cat_cua(ke_hoach, du_an, nguon)
    camera = ke_hoach.get("camera") or []
    nen_moi = ke_hoach.get("nen_moi") or []
    mv = ke_hoach.get("mau_video") or None
    alpha, alpha_a, alpha_dur = _alpha_cua(ke_hoach)
    kich_thuoc = _kich_thuoc_nguon(nguon)
    key = khoa_base(du_an, ke_hoach)
    cache = os.path.join(du_an, "cache"); os.makedirs(cache, exist_ok=True)
    ra = os.path.join(cache, f"base-{key}.mp4")
    tong = sum(s["b"] - s["a"] for s in cat)
    if not lam_moi and base_hop_le(ra, tong, fps):
        return ra
    tam = ra[:-4] + f".{os.getpid()}.tmp.mp4"                # 1.2.21: ghi .tmp rồi os.replace — không bao giờ có base cụt mang tên thật
    lut_ten = _chuan_lut(du_an, (mv or {}).get("duong")) if mv else None
    if mv and mv.get("duong") and not lut_ten:
        chung.log(du_an, f"chỉnh màu: không đọc được LUT {mv.get('duong')} → chỉ chỉnh sáng/tương phản/bão hoà")
    moc_key = [f0 / fps for f0, _ in chia_doan(cat, fps)[1:]]

    def lenh(hw, enc):
        args, nhan = _doan_nguon(nguon, cat, hw)
        fl, _ = _chuoi_cat(nhan, W, H, fps, kich_thuoc, cat, zmax=_zmax(camera), nguon=nguon)
        cam = _bieu_thuc_cam(camera, W, H, fps, ke_hoach)
        fl.append(f"[cat]{cam}[cam0]")
        mau_fl = bo_loc_mau(mv, lut_ten, "[cam0]", "[cam]")
        fl += mau_fl if mau_fl else ["[cam0]null[cam]"]
        cuoi = "[cam]"
        n_in = len(nhan)
        # ---- nen_moi (tách người): rãnh alpha tính trước trên proxy (đoạn giây gốc [a, a+dài]) → đệm đen cho đủ dòng thời gian gốc
        nm = nen_moi[0] if nen_moi else None
        if nm and alpha and os.path.isfile(alpha):
            fl += _chuoi_alpha(args, n_in, alpha, alpha_a, alpha_dur, cat, nhan, W, H, fps, kich_thuoc, cam, zmax=_zmax(camera))
            n_in += 1
            nen = nm.get("nen") or {}
            kieu = nen.get("kieu", "mau"); gt = nen.get("gia_tri", "#0E0E12")
            fl.append("[cam]split=3[fg][fg2][goc]")
            p_nen = nen.get("duong") if nen.get("duong") and os.path.isfile(str(nen.get("duong"))) else (ctx.tai_nguyen(gt) if ctx is not None else None)
            if kieu == "mo":
                mo = float(nen.get("mo", 0.3)); sig = max(2, int(mo * 24))
                fl.append(f"[fg2]scale=iw/8:ih/8,gblur=sigma={sig},scale={W}:{H},eq=brightness=-0.15[bg]")
            elif kieu == "gradient":
                ms = gt if isinstance(gt, list) else [gt, "#000000"]
                c0 = str(ms[0]).lstrip("#")[:6]; c1 = str(ms[-1]).lstrip("#")[:6]
                fl.append(f"[fg2]nullsink;gradients=s={W}x{H}:c0=0x{c0}:c1=0x{c1}:x0=0:y0=0:x1=0:y1={H}:r={fps}:d={tong:.3f}[bg]")
            elif kieu in ("anh", "video", "kho") and p_nen:
                if kieu == "anh" or p_nen.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                    args += ["-loop", "1", "-framerate", str(int(fps)), "-i", p_nen]
                else:
                    args += ["-stream_loop", "-1", "-i", p_nen]
                ib = n_in; n_in += 1
                fl.append(f"[fg2]nullsink;[{ib}:v]crop=w='min(iw,ih*{W}/{H})':h='min(ih,iw*{H}/{W})',scale={W}:{H},fps={fps},setsar=1,trim=0:{tong:.3f}[bg]")
            else:
                c = str(gt).lstrip("#")[:6] if isinstance(gt, str) else "0E0E12"
                fl.append(f"[fg2]nullsink;color=c=0x{c}:s={W}x{H}:r={fps}:d={tong:.3f}[bg]")
            fl.append("[fg][alp]alphamerge[fga]")
            fl.append("[bg][fga]overlay=format=auto[ghep]")
            bat = "+".join(f"between(t,{float(x.get('t0', 0)):.3f},{float(x.get('t1', tong)):.3f})" for x in nen_moi)
            fl.append(f"[goc][ghep]overlay=format=auto:enable='{bat}'[nm]")
            cuoi = "[nm]"
        fl.append(f"{cuoi}scale=flags=bicubic:out_color_matrix=bt709:out_range=tv,format=yuv420p[vout]")
        kf = ["-force_key_frames", ",".join("%.6f" % t for t in moc_key)] if moc_key else []
        return [chung.duong("ffmpeg"), "-v", "error", "-y", "-nostdin"] + args + ["-filter_complex", ";".join(fl), "-map", "[vout]", "-an",
                "-t", "%.4f" % tong] + ma_hoa_args(enc) + chung.MAU_RA_BT709 + kf + ["-movflags", "+faststart", tam]

    try:
        _chay_co_du_phong(lenh, du_an, "base", cwd=cache, dur=tong)
        if not base_hop_le(tam, tong, fps):
            inf = chung.ffprobe(tam) or {}
            raise RuntimeError(f"base dựng ra không đủ thời lượng ({inf.get('dur')}s / {tong:.2f}s) — ổ đầy hoặc ffmpeg bị ngắt")
        os.replace(tam, ra)
    finally:
        try:
            if os.path.exists(tam):
                os.remove(tam)
        except OSError:
            pass
    return ra


def dung_alpha_tl(du_an, ke_hoach, alpha):
    """rãnh alpha (proxy, giây gốc) → cache/alpha-tl-<hash>.mp4 xám W×H khớp dòng thời gian thành phẩm (cắt + camera) — cho ctx.lay_alpha"""
    W, H = [int(v) for v in (ke_hoach.get("khung") or [1080, 1920])]
    fps = float(ke_hoach.get("fps") or 30)
    nguon = nguon_cua(ke_hoach, du_an)
    cat = cat_cua(ke_hoach, du_an, nguon)
    p, a, dn = _alpha_cua({"alpha": alpha})
    if not p or not os.path.isfile(p):
        return None
    key = chung.bam({"cat": cat, "camera": ke_hoach.get("camera") or [], "W": W, "H": H, "fps": fps, "alpha": chung.bam(p), "a": a, "v": 1,
                     "qd_cam": (ke_hoach.get("quyet_dinh") or {}).get("camera")})   # R4b: cùng khoá ease với base (alpha-tl phải khớp khung base)
    ra = os.path.join(du_an, "cache", f"alpha-tl-{key}.mp4")
    if os.path.isfile(ra) and os.path.getsize(ra) > 1000:
        return ra
    kich_thuoc = _kich_thuoc_nguon(nguon)
    tong = sum(s["b"] - s["a"] for s in cat)
    cam = _bieu_thuc_cam(ke_hoach.get("camera") or [], W, H, fps, ke_hoach)
    args = []
    fl = _chuoi_alpha(args, 0, p, a, dn, cat, list(range(len(cat))), W, H, fps, kich_thuoc, cam, zmax=_zmax(ke_hoach.get("camera")))
    cmd = [chung.duong("ffmpeg"), "-v", "error", "-y", "-nostdin"] + args + ["-filter_complex", ";".join(fl), "-map", "[alp]", "-an",
                                                                            "-t", "%.4f" % tong, "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
                                                                            "-pix_fmt", "gray", "-g", "30", ra + ".tmp.mp4"]
    ma, err = _chay(cmd, du_an, "alpha theo dòng thời gian", dur=tong)
    if ma != 0:
        return None
    os.replace(ra + ".tmp.mp4", ra)
    return ra


# ======================================================================== âm ====
def nguon_am_cua(ke_hoach, du_an, nguon):
    """[wav 48k theo src] — dùng cache/am48-<hash>.wav nếu có, không thì tách từ nguồn (nhanh)"""
    ra = []
    cache = os.path.join(du_an, "cache") if du_an else None
    for p in nguon:
        inf = chung.ffprobe(p)
        if not inf or not inf.get("co_am"):
            ra.append(None); continue
        if cache:
            os.makedirs(cache, exist_ok=True)
            w = os.path.join(cache, f"am48-{chung.bam(p)}.wav")
            if not os.path.isfile(w):
                # 1.2.20: aresample=async → WAV bám ĐÚNG mốc thời gian của nguồn (chèn im lặng vào chỗ hở, cắt chỗ chồng) — nguồn có
                # khoảng hở tiếng (clip nối, máy quay điện thoại) không làm tiếng trôi sớm so với hình
                tam = w + ".tmp.wav"
                ma, _ = chung.chay_ffmpeg([chung.duong("ffmpeg"), "-v", "error", "-y", "-nostdin", "-i", p, "-vn", "-af", "aresample=async=1000:first_pts=0", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", tam],
                                          du_an, "tách tiếng 48k", dur=(inf.get("dur") or None))
                if ma == 0 and os.path.isfile(tam):
                    os.replace(tam, w)
            ra.append(w if os.path.isfile(w) else p)
        else:
            ra.append(p)
    return ra


def dung_am(du_an, ke_hoach, ctx=None):
    """trộn âm cả bài MỘT lần → cache/am-tp-<hash>.m4a (None nếu không có âm). Sửa lớp không đổi âm ⇒ dùng lại."""
    nguon = nguon_cua(ke_hoach, du_an)
    cat = cat_cua(ke_hoach, du_an, nguon)
    tong = sum(s["b"] - s["a"] for s in cat)
    nam = nguon_am_cua(ke_hoach, du_an, nguon)
    am = ke_hoach.get("am") or {}
    key = chung.bam({"am": am, "cat": cat, "nguon": [chung.bam(p) if p else None for p in nam], "tong": round(tong, 4),
                     "qd": (ke_hoach.get("quyet_dinh") or {}).get("am") or {}, "v": 4, "am_phien": getattr(_am, "PHIEN", 1)})   # 1.2.21: mức âm theo quyết định kênh → đổi là trộn lại
    ra = os.path.join(du_an, "cache", f"am-tp-{key}.m4a")
    if os.path.isfile(ra) and os.path.getsize(ra) > 500:
        return ra
    inputs, fl, mp = _am.bo_loc_am(ke_hoach, cat, nam, getattr(ctx, "kho", None), bat_dau_input=0, du_an=du_an, tong_dai=tong)
    if not mp:
        return None
    cmd = [chung.duong("ffmpeg"), "-v", "error", "-y", "-nostdin"] + inputs + ["-filter_complex", fl, "-map", mp, "-c:a", "aac", "-b:a", "192k",
                                                                              "-t", "%.4f" % tong, ra + ".tmp.m4a"]
    ma, err = _chay(cmd, du_an, "trộn âm", dur=tong)
    if ma != 0:
        raise RuntimeError("trộn âm thất bại: " + err[-600:])
    os.replace(ra + ".tmp.m4a", ra)
    return ra


# ======================================================================== đoạn: dựng ====
def _doc_ffconcat(p):
    """→ [(png tuyệt đối, giay)] (bỏ dòng lặp cuối không có duration)"""
    goc = os.path.dirname(os.path.abspath(p))
    muc, cur = [], None
    with open(p, encoding="utf-8") as f:
        for d in f:
            d = d.strip()
            if d.startswith("file "):
                cur = d[5:].strip().strip("'\"")
            elif d.startswith("duration ") and cur is not None:
                f_ = cur if os.path.isabs(cur) else os.path.join(goc, cur)
                muc.append((f_, float(d[9:]))); cur = None
    return muc


def _cat_ffconcat(sp, w0, w1, thu_muc):
    """sprite (t0, ffconcat) → ffconcat chỉ phần [w0, w1) (giây tuyệt đối), ghi vào thu_muc theo băm nội dung (dùng lại giữa các lần)"""
    muc = _doc_ffconcat(sp["concat"])
    t0 = float(sp["t0"])
    r0, r1 = w0 - t0, w1 - t0
    ra, c = [], 0.0
    for f, d in muc:
        a, b = max(c, r0), min(c + d, r1)
        if b - a > 1e-6:
            ra.append((f, b - a))
        c += d
        if c >= r1:
            break
    if not ra:
        return None
    noi_dung = "ffconcat version 1.0\n" + "".join("file '%s'\nduration %.6f\n" % (f.replace("\\", "/"), d) for f, d in ra) + \
        "file '%s'\n" % ra[-1][0].replace("\\", "/")
    p = os.path.join(thu_muc, "c-%s.ffconcat" % chung.bam(noi_dung))
    if not os.path.isfile(p):
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(noi_dung)
    return p


def _flash_filters(ke_hoach, tong, s0=0.0, s1=None):
    """flash = eq với biểu thức theo t (giờ ĐỊA PHƯƠNG của đoạn: t + s0 = giờ thành phẩm), eval=frame. → (filters, terms)"""
    s1 = tong if s1 is None else s1
    terms = []
    for c in ke_hoach.get("chuyen_canh") or []:
        if c.get("kieu") != "flash":
            continue
        t = float(c.get("t", 0)); dai = max(0.05, float(c.get("dai", 0.2)))
        d1 = dai * 0.3; d2 = dai * 0.7; st = max(0.0, t - d1)
        if t + d2 > tong or t <= 0 or t + d2 < s0 or st > s1:
            continue
        st -= s0; tl = t - s0
        terms.append(f"if(between(t,{st:.4f},{tl:.4f}),(t-{st:.4f})/{d1:.4f},if(between(t,{tl:.4f},{tl + d2:.4f}),1-(t-{tl:.4f})/{d2:.4f},0))")
    if not terms:
        return [], []
    f = "clip(" + "+".join(terms) + ",0,1)"
    return [f"eq=brightness='{f}':contrast='1-{f}':saturation='1-{f}':eval=frame"], terms


def _thong_tin_truc_tiep(it, s0, s1, fps):
    """lớp video/ảnh trực tiếp giao đoạn → dict thời gian (giây) hoặc None"""
    t0, t1 = float(it["t0"]), float(it["t1"])
    w0, w1 = max(t0, s0), min(t1, s1)
    if w1 - w0 < 0.5 / fps:
        return None
    skip = w0 - t0                       # giây vào lớp lúc đoạn bắt đầu
    dv, dr = float(it.get("dv") or 0), float(it.get("dr") or 0)
    dai = t1 - t0
    bd = skip if skip >= dv else 0.0      # luồng lớp bắt đầu từ đâu (đang mờ vào thì đọc từ đầu lớp để fade đúng)
    if dr > 0 and bd > dai - dr:
        bd = max(0.0, dai - dr)
    return {"w0": w0, "w1": w1, "skip": skip, "bd": bd, "dv": dv, "dr": dr, "dai": dai, "off": w0 - s0, "L": w1 - w0}


def _truc_tiep_filter(it, idx, tt, W, H, fps, args):
    """thêm input + filter cho lớp video/ảnh trực tiếp → (filter list, nhãn ra, (x,y,w,h,mode)) hoặc (None,None,None) nếu ngoài khung"""
    x, y, w, h = [int(round(float(v))) for v in (it["x"], it["y"], it["w"], it["h"])]
    w, h = max(2, w // 2 * 2), max(2, h // 2 * 2)
    toc = max(0.1, float(it.get("toc_do") or 1.0))
    mode = HOA_TRON.get(it.get("hoa_tron") or "normal", "normal")
    neutral = MAU_TRUNG_TINH.get(mode, "black")
    vx0, vy0 = max(0, x), max(0, y); vx1, vy1 = min(W, x + w), min(H, y + h)
    if vx1 - vx0 < 2 or vy1 - vy0 < 2:
        return None, None, None
    if it["loai_nguon"] == "anh":
        args += ["-loop", "1", "-framerate", "%g" % fps, "-t", "%.4f" % (tt["dai"] + 1), "-i", it["file"]]
    else:
        dfile = float(it.get("dur_file") or 0)
        src_pos = float(it.get("a") or 0) + tt["bd"] * toc
        if it.get("lap") and dfile > 0:
            src_pos = src_pos % dfile
            args += ["-stream_loop", "-1"]
        args += ["-ss", "%.4f" % src_pos, "-i", it["file"]]
    cover = it.get("fit", "cover") != "contain"
    ch = [f"setpts=(PTS-STARTPTS)/{toc:.5f}", f"fps={fps}",
          f"scale={w}:{h}:force_original_aspect_ratio={'increase' if cover else 'decrease'}:flags=bicubic"]
    if cover:
        ch.append(f"crop={w}:{h}")
    het_vao = tt["bd"] < tt["dv"]
    co_ra = tt["dr"] > 0 and tt["skip"] + tt["L"] > tt["dai"] - tt["dr"] - 1e-6
    st_ra = max(0.0, tt["dai"] - tt["dr"] - tt["bd"])
    if mode == "normal":
        ch.append("format=rgba")
        if not cover:
            ch.append(f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black@0")
        if het_vao:
            ch.append(f"fade=t=in:st=0:d={tt['dv'] - tt['bd']:.4f}:alpha=1")
        if co_ra:
            ch.append(f"fade=t=out:st={st_ra:.4f}:d={tt['dr']:.4f}:alpha=1")
        do = float(it.get("do_trong", 1.0) if it.get("do_trong") is not None else 1.0)
        if do < 0.999:
            ch.append(f"colorchannelmixer=aa={max(0.0, do):.3f}")
    else:
        if not cover:
            ch.append(f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color={neutral}")
        ch.append("format=gbrp")
        if het_vao:       # mờ vào/ra = trộn về màu trung tính của chế độ (đen cho screen/add, trắng cho multiply, xám cho overlay)
            ch.append(f"fade=t=in:st=0:d={tt['dv'] - tt['bd']:.4f}:color={neutral}")
        if co_ra:
            ch.append(f"fade=t=out:st={st_ra:.4f}:d={tt['dr']:.4f}:color={neutral}")
    ch.append(f"trim=start={tt['skip'] - tt['bd']:.4f}:duration={tt['L']:.4f}")
    ch.append("setpts=PTS-STARTPTS")
    if mode != "normal":
        if (vx0, vy0, vx1, vy1) != (x, y, x + w, y + h):          # blend cần cùng cỡ: bỏ phần ngoài khung
            cw_, ch_ = (vx1 - vx0) // 2 * 2, (vy1 - vy0) // 2 * 2
            ch.append(f"crop={cw_}:{ch_}:{vx0 - x}:{vy0 - y}")
            x, y, w, h = vx0, vy0, cw_, ch_
        ch.append(f"tpad=start_duration={tt['off']:.4f}:color={neutral}")
    else:
        ch.append(f"setpts=PTS+{tt['off']:.5f}/TB")
    return [f"[{idx}:v]" + ",".join(ch) + f"[tt{idx}]"], f"[tt{idx}]", (x, y, w, h, mode)


def chuan_bi_khuc(du_an, ke_hoach, base, f0, f1, lop_ds, enc, chat_luong="that", alpha_tl=None):
    """→ (khoa, mô tả) — lop_ds theo thứ tự chồng: sprite meta ({"concat",...}) hoặc trực tiếp ({"loai":"truc_tiep",...}).
    1.2.21 (B1): lớp có "sau_nguoi" + alpha_tl (mặt nạ xám toàn dòng thời gian, dung_alpha_tl) → item mang cờ "sn"; mô tả có "nguoi"
    {alpha, off, het} = người cắt từ base chồng lên NHÓM lớp sau người (dung_khuc). Không có alpha_tl → lớp sau người dựng như lớp thường."""
    W, H = [int(v) for v in (ke_hoach.get("khung") or [1080, 1920])]
    fps = float(ke_hoach.get("fps") or 30)
    s0, s1 = f0 / fps, f1 / fps
    tong = float(ke_hoach.get("_tong") or ke_hoach.get("dur") or 0) or s1
    thu_muc = os.path.join(du_an, "cache", "khuc"); os.makedirs(thu_muc, exist_ok=True)
    co_alpha = bool(alpha_tl) and os.path.isfile(alpha_tl)
    items = []
    for s in lop_ds:
        if not s:
            continue
        t0, t1 = float(s["t0"]), float(s["t1"])
        if t1 <= s0 or t0 >= s1:
            continue
        sn = bool(co_alpha and s.get("sau_nguoi"))
        if s.get("loai") == "truc_tiep":
            tt = _thong_tin_truc_tiep(s, s0, s1, fps)
            if tt:
                it = {"loai": "truc_tiep", "s": {k: s.get(k) for k in ("id", "file", "loai_nguon", "a", "lap", "toc_do", "dur_file", "x", "y", "w", "h",
                                                                        "fit", "t0", "t1", "hoa_tron", "do_trong", "dv", "dr")},
                      "file_bam": chung.bam(s["file"]), "tt": {k: round(v, 5) for k, v in tt.items()}}
                if sn:
                    it["sn"] = True
                items.append(it)
        else:
            w0, w1 = max(t0, s0), min(t1 + 0.5 / fps, s1)
            p = _cat_ffconcat(s, w0, w1, thu_muc)
            if p:
                it = {"loai": "sprite", "concat": p, "x": int(s["x"]), "y": int(s["y"]), "off": round(w0 - s0, 5), "het": round(w1 - s0, 5)}
                if sn:
                    it["sn"] = True; it["w"] = int(s.get("w") or W); it["h"] = int(s.get("h") or H)
                items.append(it)
    nguoi = None
    sn_items = [it for it in items if it.get("sn")]
    if sn_items:
        offs = [it["off"] if it["loai"] == "sprite" else it["tt"]["off"] for it in sn_items]
        hets = [it["het"] if it["loai"] == "sprite" else it["tt"]["off"] + it["tt"]["L"] for it in sn_items]
        # hộp hợp của các lớp sau người (người chỉ cần chồng lại trong vùng này — ngoài vùng khung đã là base)
        hx0 = hy0 = 10 ** 9; hx1 = hy1 = -10 ** 9
        for it in sn_items:
            b = it if it["loai"] == "sprite" else it["s"]
            x, y, w, h = int(round(float(b["x"]))), int(round(float(b["y"]))), int(round(float(b["w"]))), int(round(float(b["h"])))
            hx0, hy0, hx1, hy1 = min(hx0, x), min(hy0, y), max(hx1, x + w), max(hy1, y + h)
        hx0, hy0 = max(0, hx0) // 2 * 2, max(0, hy0) // 2 * 2
        hx1, hy1 = min(W, hx1 + 1) // 2 * 2, min(H, hy1 + 1) // 2 * 2
        if hx1 - hx0 < 2 or hy1 - hy0 < 2:
            hx0, hy0, hx1, hy1 = 0, 0, W, H
        nguoi = {"alpha": alpha_tl, "off": round(max(0.0, min(offs)), 5), "het": round(max(hets), 5), "hop": [hx0, hy0, hx1, hy1]}
    fx, terms = _flash_filters(ke_hoach, tong, s0, s1)
    k = chung.bam({"base": os.path.basename(base), "f": [f0, f1], "fps": fps, "W": W, "H": H, "items": items, "flash": terms,
                   "enc": enc, "cl": chat_luong, "v": phien_ghep(),
                   "nguoi": ({"alpha": os.path.basename(alpha_tl), "off": nguoi["off"], "het": nguoi["het"], "hop": nguoi["hop"]} if nguoi else None)})
    return k, {"items": items, "fx": fx, "W": W, "H": H, "fps": fps, "s0": s0, "s1": s1, "n": f1 - f0, "nguoi": nguoi}


def duong_khuc(du_an, khoa):
    return os.path.join(du_an, "cache", "khuc", f"_khuc-{khoa}.mp4")


def _chia_luot(items):
    """chia items thành các lượt ffmpeg, mỗi lượt ≤ TOI_DA_INPUT input (lớp = 1 input; "nguoi" = 2 input: base gốc + alpha)"""
    luot, nhom, so = [], [], 0
    for it in items:
        c = 2 if it["loai"] == "nguoi" else 1
        if nhom and so + c > TOI_DA_INPUT:
            luot.append(nhom); nhom, so = [], 0
        nhom.append(it); so += c
    luot.append(nhom)
    return luot


def dung_khuc(du_an, base, khoa, mo_ta, enc=None, chat_luong="that"):
    """→ (cache/khuc/_khuc-<khoa>.mp4, có_sẵn).
    1.2.21 (B1): có mo_ta["nguoi"] → đồ thị: base → overlay(các lớp "sn" theo thứ tự) → overlay(NGƯỜI cắt từ base gốc:
    [base -ss/-t][alpha-tl -ss/-t] alphamerge, enable trong khoảng lớp sau người) → overlay(các lớp còn lại). Người luôn cắt từ base GỐC
    (thêm input riêng) kể cả khi rơi vào lượt trung gian; mặt nạ không nướng vào PNG nên sprite sau người dedup như lớp thường."""
    ra = duong_khuc(du_an, khoa)
    if os.path.isfile(ra) and os.path.getsize(ra) > 500:
        return ra, True
    W, H, fps, s0, s1, n = mo_ta["W"], mo_ta["H"], mo_ta["fps"], mo_ta["s0"], mo_ta["s1"], mo_ta["n"]
    items = list(mo_ta["items"])
    nguoi = mo_ta.get("nguoi")
    if nguoi:
        items = [it for it in items if it.get("sn")] + [{"loai": "nguoi"}] + [it for it in items if not it.get("sn")]
    luot = _chia_luot(items)
    cat_doan = ["-ss", "%.6f" % s0, "-t", "%.6f" % (s1 - s0 + 1.0 / fps)]
    hien, tam = base, []
    for li, nhom in enumerate(luot):
        cuoi = li == len(luot) - 1
        args = (cat_doan if li == 0 else []) + ["-i", hien]
        fl = ["[0:v]setpts=PTS-STARTPTS,format=rgba[v0]"]
        v = "[v0]"
        idx = 1
        for it in nhom:
            if it["loai"] == "sprite":
                args += ["-f", "concat", "-safe", "0", "-i", it["concat"]]
                fl.append(f"[{idx}:v]setpts=PTS-STARTPTS+{it['off']:.5f}/TB,format=rgba[s{idx}]")
                fl.append(f"{v}[s{idx}]overlay=x={it['x']}:y={it['y']}:format=rgb:eof_action=pass:repeatlast=0:"
                          f"enable='between(t,{it['off']:.5f},{it['het']:.5f})'[v{idx}]")
            elif it["loai"] == "nguoi":
                # người cắt từ base GỐC theo đúng đoạn (cùng -ss/-t, cùng fps, setpts về 0 → khớp khung với [0:v]); CHỈ trong hộp hợp
                # của các lớp sau người (ngoài hộp khung đã là base) → rẻ hơn chồng cả khung
                x0, y0, x1, y1 = nguoi.get("hop") or [0, 0, W, H]
                cw, ch = x1 - x0, y1 - y0
                args += cat_doan + ["-i", base] + cat_doan + ["-i", nguoi["alpha"]]
                fl.append(f"[{idx}:v]setpts=PTS-STARTPTS,fps={fps},crop={cw}:{ch}:{x0}:{y0},format=rgba[nb{idx}]")
                fl.append(f"[{idx + 1}:v]setpts=PTS-STARTPTS,fps={fps},format=gray,scale={W}:{H}:flags=neighbor,crop={cw}:{ch}:{x0}:{y0}[na{idx}]")
                fl.append(f"[nb{idx}][na{idx}]alphamerge[ng{idx}]")
                fl.append(f"{v}[ng{idx}]overlay=x={x0}:y={y0}:format=rgb:eof_action=pass:repeatlast=0:"
                          f"enable='between(t,{nguoi['off']:.5f},{nguoi['het']:.5f})'[v{idx}]")
                v = f"[v{idx}]"; idx += 2
                continue
            else:
                s, tt = it["s"], it["tt"]
                f_, nhan, hop = _truc_tiep_filter(s, idx, tt, W, H, fps, args)
                if not f_:
                    args += ["-f", "lavfi", "-i", "nullsrc=s=16x16:d=0.1"]       # giữ đúng chỉ số input
                    fl.append(f"[{idx}:v]nullsink")
                    idx += 1
                    continue
                fl += f_
                x, y, w, h, mode = hop
                en = f"enable='between(t,{tt['off']:.5f},{tt['off'] + tt['L']:.5f})'"
                if mode == "normal":
                    fl.append(f"{v}{nhan}overlay=x={x}:y={y}:format=rgb:eof_action=pass:repeatlast=0:{en}[v{idx}]")
                else:
                    do = max(0.0, min(1.0, float(s.get("do_trong") if s.get("do_trong") is not None else 1.0)))
                    fl.append(f"{v}split=2[va{idx}][vb{idx}]")
                    fl.append(f"[vb{idx}]crop={w}:{h}:{x}:{y},format=gbrp[vc{idx}]")
                    fl.append(f"[vc{idx}]{nhan}blend=all_mode={mode}:all_opacity={do:.3f}:shortest=0:repeatlast=1,format=rgba[vd{idx}]")
                    fl.append(f"[va{idx}][vd{idx}]overlay=x={x}:y={y}:format=rgb:eof_action=pass:{en}[v{idx}]")
            v = f"[v{idx}]"; idx += 1
        if cuoi:
            # 1.2.21: RGB → YUV theo ma trận BT.709 (trước: swscale mặc định BT.601 → màu đoạn lệch nhẹ so với base) + gắn thẻ màu
            fl.append(f"{v}" + ",".join(["scale=flags=bicubic:out_color_matrix=bt709:out_range=tv,format=yuv420p"] + mo_ta["fx"]) + "[vout]")
            dau_ra = ra + ".tmp.mp4"
            cmd = [chung.duong("ffmpeg"), "-v", "error", "-y", "-nostdin"] + args + ["-filter_complex", ";".join(fl), "-map", "[vout]", "-an",
                                                                                    "-frames:v", str(n), "-r", "%g" % fps, "-fps_mode", "cfr"] + \
                ma_hoa_args(enc, chat_luong) + chung.MAU_RA_BT709 + ["-video_track_timescale", "15360", dau_ra]
            ma, err = _chay(cmd, du_an, "đoạn %.1f–%.1fs" % (s0, s1), dur=s1 - s0)
            if ma != 0:
                raise RuntimeError("dựng đoạn %.1f–%.1fs thất bại: %s" % (s0, s1, err[-800:]))
            os.replace(dau_ra, ra)
        else:                              # quá nhiều input: lượt trung gian gần như không mất (crf 8, yuv444) — giờ đã là giờ địa phương
            fl.append(f"{v}format=yuv444p[vout]")
            dau_ra = ra + f".luot{li}.mkv"
            cmd = [chung.duong("ffmpeg"), "-v", "error", "-y", "-nostdin"] + args + ["-filter_complex", ";".join(fl), "-map", "[vout]", "-an",
                                                                                    "-frames:v", str(n), "-c:v", "libx264", "-preset", "ultrafast",
                                                                                    "-crf", "8", "-pix_fmt", "yuv444p", dau_ra]
            ma, err = _chay(cmd, du_an, "đoạn %.1f–%.1fs lượt %d" % (s0, s1, li), dur=s1 - s0)
            if ma != 0:
                raise RuntimeError("đoạn trung gian thất bại: " + err[-800:])
            tam.append(dau_ra); hien = dau_ra
    for t in tam:
        try:
            os.remove(t)
        except Exception:
            pass
    return ra, False


def noi(du_an, khuc, am, ra, tong):
    """concat các đoạn (-c copy) + mux âm → ra"""
    ds = os.path.join(du_an, "cache", "khuc", "_noi-%s.txt" % chung.bam(khuc))
    with open(ds, "w", encoding="utf-8") as fh:
        fh.write("ffconcat version 1.0\n" + "".join("file '%s'\n" % p.replace("\\", "/") for p in khuc))
    tam = ra + ".tmp.mp4"
    cmd = [chung.duong("ffmpeg"), "-v", "error", "-y", "-nostdin", "-f", "concat", "-safe", "0", "-i", ds]
    if am:
        cmd += ["-i", am, "-map", "0:v", "-map", "1:a", "-c", "copy"]
    else:
        cmd += ["-map", "0:v", "-c", "copy", "-an"]
    cmd += ["-t", "%.4f" % tong, "-movflags", "+faststart", tam]
    ma, err = _chay(cmd, du_an, "nối %d đoạn + âm" % len(khuc), dur=tong)
    if ma != 0:
        raise RuntimeError("nối đoạn thất bại: " + err[-800:])
    os.replace(tam, ra)
    return ra
