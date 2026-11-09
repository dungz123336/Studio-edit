# -*- coding: utf-8 -*-
"""Proxy 540p + âm thanh 16k/48k từ nguồn; cache theo băm nguồn trong du_an/cache; ghi doc/nguon.json."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung


def _ok(p):
    return p and os.path.isfile(p) and os.path.getsize(p) > 1024


def _proxy_scale(info, cao):
    """nguồn dọc → chiều cao `cao`; nguồn ngang (hoặc vuông) → chiều rộng `cao`"""
    if info["h"] > info["w"]:
        return f"scale=-2:{cao}"
    return f"scale={cao}:-2"


def _ffmpeg_proxy(src, dst, info, cao, fps_max, hwaccel, co_tieng, log, du_an=None):
    """1.2.21: lọc màu vào (HDR→SDR, 10-bit→8-bit) trước scale; chạy qua chung.chay_ffmpeg (-progress, treo = không tiến); ghi .tmp rồi replace.
    → (ok, err) — err bắt đầu bằng "TREO" khi ffmpeg bị giết vì không tiến (mã 124). hoc/hoc.py (học mẫu) cũng gọi hàm này."""
    ff = chung.duong("ffmpeg")
    vf = []
    if info["fps"] > fps_max + 0.5:
        vf.append(f"fps={fps_max}")
    lm = chung.loc_mau_vao(info)
    if lm:
        vf.append(lm)
    vf += [_proxy_scale(info, cao) + ":out_color_matrix=bt709", "format=yuv420p"]
    cmd = [ff, "-v", "error", "-y", "-nostdin"]
    if hwaccel and hwaccel != "none":
        cmd += ["-hwaccel", hwaccel]
    cmd += ["-i", src, "-vf", ",".join(vf), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-g", "30"] + chung.MAU_RA_BT709 + [
            "-movflags", "+faststart"]
    if co_tieng:
        cmd += ["-c:a", "aac", "-b:a", "128k", "-ac", "2"]
    else:
        cmd += ["-an"]
    tam = dst + ".tmp.mp4"
    cmd += [tam]
    ma, err = chung.chay_ffmpeg(cmd, du_an, "proxy" + (f" ({hwaccel})" if hwaccel and hwaccel != "none" else ""), dur=info.get("dur"))
    if ma == 0 and _ok(tam) and (info.get("dur") or 0) > 1:        # 1.2.21 (R5): card chết giữa chừng → ffmpeg thoát 0 nhưng proxy CỤT → coi là lỗi (hwaccel)
        d_ra = (chung.ffprobe(tam) or {}).get("dur") or 0
        if d_ra < 0.97 * info["dur"]:
            ma, err = 1, f"proxy cụt {d_ra:.1f}/{info['dur']:.1f} s (giải mã dừng giữa chừng)"
    if ma != 0 or not _ok(tam):
        try:
            os.remove(tam)
        except OSError:
            pass
        return False, (err or f"mã {ma}")
    os.replace(tam, dst)
    return True, ""


def _khoa_hw(info):
    return f"{info.get('codec') or '?'}|{'4k' if max(info.get('w') or 0, info.get('h') or 0) > 2200 else 'hd'}"


def _tao_proxy(du_an, src, info, vai, cache, cao, fps_max):
    dst = os.path.join(cache, f"proxy-{chung.bam(src)}.mp4")
    if _ok(dst):
        chung.log(du_an, f"proxy: dùng cache {os.path.basename(dst)}")
        return dst
    pc = chung.phan_cung()
    hw = pc.get("hwaccel", "none") or "none"
    k_hw = _khoa_hw(info)
    if hw != "none" and chung.loi_con_hieu_luc(pc, "hwaccel_loi", k_hw):     # nguồn loại này từng lỗi hwaccel, lỗi CÒN HIỆU LỰC (R4a: có thời hạn) → CPU thẳng
        chung.log(du_an, f"proxy: {k_hw} từng lỗi hwaccel {hw} (phan-cung.json, còn hiệu lực) → giải mã CPU")
        hw = "none"
    co_tieng = bool(info["co_am"]) and vai == "chinh"
    ok, err = _ffmpeg_proxy(src, dst, info, cao, fps_max, hw, co_tieng, None, du_an=du_an)
    if not ok and hw != "none":
        chung.log(du_an, f"proxy: hwaccel {hw} lỗi" + (" (TREO)" if str(err).startswith("TREO") else "") + " → thử CPU, nhớ vào phan-cung.json")
        chung.nho_loi_phan_cung("hwaccel_loi", k_hw)               # 1.2.21: nhớ bền (kể cả mã 124 TREO)
        ok, err = _ffmpeg_proxy(src, dst, info, cao, fps_max, "none", co_tieng, None, du_an=du_an)
    if not ok:
        raise RuntimeError(f"ffmpeg proxy lỗi: {err[-400:]}")
    return dst


def _tao_am(du_an, src, cache, ten, ar, ac):
    dst = os.path.join(cache, f"{ten}-{chung.bam(src)}.wav")
    if _ok(dst):
        return dst
    # 1.2.20: aresample=async → WAV bám đúng mốc thời gian của nguồn (nguồn có khoảng hở tiếng thì không trôi sớm so với hình) —
    # mốc từ trong loi.json và tiếng trộn ra cùng một dòng thời gian với hình
    tam = dst + ".tmp.wav"
    cmd = [chung.duong("ffmpeg"), "-v", "error", "-y", "-nostdin", "-i", src, "-vn", "-af", "aresample=async=1000:first_pts=0", "-ac", str(ac), "-ar", str(ar),
           "-c:a", "pcm_s16le", tam]
    ma, err = chung.chay_ffmpeg(cmd, du_an, f"tách tiếng {ten}", dur=(chung.ffprobe(src) or {}).get("dur"))
    if ma != 0 or not _ok(tam):
        raise RuntimeError(f"ffmpeg âm {ten} lỗi: {err[-300:]}")
    os.replace(tam, dst)
    return dst


def tao(du_an, nguon):
    """nguon: [{"duong", "vai":"chinh|phu"}] → {"proxy","am16","am48","fps","danh_sach":[...]}; ghi doc/nguon.json.
    Nguồn chính đầu tiên quyết định proxy/am16/am48 trả về; chỉ nguồn chính có proxy (phụ = B-roll đọc thẳng gốc)."""
    du_an = os.path.normpath(du_an)
    cfg = chung.cau_hinh()
    may = chung.may_chon(du_an)                              # 1.2.21 (1b): "Máy: … vì …" vào nhật ký + nguon.json["may"] cho AI thấy
    cao = int(cfg.get("proxy_cao") or 0) or int(may["proxy_cao"])
    if cfg.get("proxy_cao"):
        chung.log(du_an, f"Máy: proxy {cao}p vì cau-hinh.json v3.proxy_cao đè")
    fps_max = float(cfg.get("fps_mac_dinh", 30))
    cache = os.path.join(du_an, "cache")
    os.makedirs(cache, exist_ok=True)
    os.makedirs(os.path.join(du_an, "doc"), exist_ok=True)
    chung.don_tep_tam(cache)                                 # 1j: proxy/âm ghi dở lần trước (bị giết) → bỏ
    ds = []
    ra = {"proxy": None, "am16": None, "am48": None, "fps": fps_max, "danh_sach": ds}
    for i, n in enumerate(nguon):
        src = chung.NFC(n["duong"])
        vai = n.get("vai", "chinh" if i == 0 else "phu")
        info = chung.ffprobe(src)
        if not info:
            raise RuntimeError(f"không đọc được nguồn: {src}")
        chung.log(du_an, f"proxy: nguồn {i} ({vai}) {info['w']}x{info['h']} {info['fps']:.2f}fps {info['dur']:.1f}s {info['codec']} "
                         f"{info.get('pix_fmt')} {info.get('bit_depth')}-bit xoay={info['xoay']}" + (" HDR→SDR" if info.get("hdr") else ""))
        muc = {"src": i, "duong": src, "vai": vai, "ffprobe": info, "proxy": None, "am16": None, "am48": None,
               "hdr": bool(info.get("hdr")), "bit_depth": info.get("bit_depth"), "loc_mau": chung.loc_mau_vao(info) or None}
        # nguồn PHỤ (B-roll) không cần proxy: engine đọc thẳng tệp gốc khi dựng, mắt B-roll (doc/broll.py) quét khung chính — tiết kiệm nhiều phút với HEVC 3K/4K
        muc["proxy"] = _tao_proxy(du_an, src, info, vai, cache, cao, fps_max) if vai == "chinh" else None
        pinfo = (chung.ffprobe(muc["proxy"]) or {}) if muc["proxy"] else {}
        muc["proxy_w"], muc["proxy_h"], muc["proxy_fps"] = pinfo.get("w"), pinfo.get("h"), pinfo.get("fps")
        if vai == "chinh" and info["co_am"]:
            muc["am16"] = _tao_am(du_an, src, cache, "am", 16000, 1)
            muc["am48"] = _tao_am(du_an, src, cache, "am48", 48000, 2)
        ds.append(muc)
        if ra["proxy"] is None and vai == "chinh":
            ra.update(proxy=muc["proxy"], am16=muc["am16"], am48=muc["am48"], fps=muc["proxy_fps"] or fps_max,
                      w=info["w"], h=info["h"], dur=info["dur"])
    if ra["proxy"] is None and ds:   # không có nguồn chính → lấy nguồn đầu
        m = ds[0]
        ra.update(proxy=m["proxy"], am16=m["am16"], am48=m["am48"], fps=m["proxy_fps"] or fps_max,
                  w=m["ffprobe"]["w"], h=m["ffprobe"]["h"], dur=m["ffprobe"]["dur"])
    chung.ghi_json(os.path.join(du_an, "doc", "nguon.json"), {"nguon": ds, "chinh": {k: ra[k] for k in ("proxy", "am16", "am48", "fps")},
                                                             "hdr": any(m.get("hdr") for m in ds),
                                                             "may": may.get("mo_ta") or "", "may_chi_tiet": may})   # A2: "may" là CHUỖI cho tổng quan việc
    return ra


if __name__ == "__main__":
    import json
    da, vid = sys.argv[1], sys.argv[2]
    print(json.dumps(tao(da, [{"duong": vid, "vai": "chinh"}]), ensure_ascii=False, indent=1))
