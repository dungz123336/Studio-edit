# -*- coding: utf-8 -*-
"""Camera: keyframes [{"t","z","x","y","ease","dai"}] → chuỗi filter ffmpeg.
Đã thử trên ffmpeg 8.1: `crop` KHÔNG nhận w/h động (lỗi "Error when evaluating the expression"), `scale eval=frame + crop`
chạy đúng nhưng chậm (~0.5× thời gian thực ở 1080×1920), `zoompan` đúng và nhanh (~10× thời gian thực) → dùng zoompan.
Chuỗi trả về: [cắt tỉ lệ khung (cover)] , fps , zoompan=z:x:y:d=1:s=WxH:fps   hoặc   crop tĩnh + scale khi không có zoom."""
import math


def _ease_expr(ten, u):
    """biểu thức ffmpeg của ease(u) với u đã clip 0..1 (chuỗi)"""
    if ten in (None, "", "linear"):
        return u
    if ten == "in":
        return f"pow({u},3)"
    if ten == "out":
        return f"(1-pow(1-{u},3))"
    if ten == "in_out":
        return f"if(lt({u},0.5),4*pow({u},3),1-pow(-2*{u}+2,3)/2)"
    if ten == "back":
        c1 = 1.70158; c3 = c1 + 1
        return f"(1+{c3}*pow({u}-1,3)+{c1}*pow({u}-1,2))"
    if ten == "expo":
        return f"if(gte({u},1),1,1-pow(2,-10*{u}))"
    return u


def _thieu_ease(i):
    try:
        from dung.chu import ThieuTruong
    except Exception:
        return RuntimeError("thieu_truong: camera[%d].ease" % i)
    return ThieuTruong("camera[%d].ease" % i, "keyframe camera có dai > 0 phải ghi ease (hoặc quyet_dinh camera.ease, cong_thuc điền)", "camera")


def _chuan(keyframes, ease_mac_dinh=None):
    """1.2.21: ease KHÔNG còn mặc định "out" — keyframe trượt (dai > 0) thiếu ease → ease_mac_dinh (quyet_dinh camera.ease, nơi gọi truyền)
    → thiếu nữa → ThieuTruong(camera[i].ease). Keyframe cắt (dai = 0) không cần ease."""
    kfs = []
    for i, k in enumerate(sorted(keyframes or [], key=lambda k: float(k.get("t", 0)))):
        dai = max(0.0, float(k.get("dai", 0) or 0))
        e = k.get("ease") or ease_mac_dinh
        if dai > 0 and not e:
            raise _thieu_ease(i)
        kfs.append({"t": float(k.get("t", 0)), "z": max(1.0, float(k.get("z", 1.0))), "x": float(k.get("x", 0.5)), "y": float(k.get("y", 0.5)),
                    "ease": e or "linear", "dai": dai})
    if not kfs or kfs[0]["t"] > 0:
        kfs.insert(0, {"t": 0.0, "z": 1.0, "x": 0.5, "y": 0.5, "ease": "linear", "dai": 0.0})
    return kfs


def _piecewise(kfs, truong, bien="time"):
    """giá trị trường theo thời gian: giữ giá trị trước, tại t_i trượt tới giá trị mới trong dai_i"""
    gia = kfs[0][truong]
    expr = f"{gia:.6f}"
    for k in kfs[1:]:
        moi = k[truong]; t = k["t"]; dai = k["dai"]
        if dai <= 0:
            seg = f"{moi:.6f}"
        else:
            u = f"clip(({bien}-{t:.4f})/{dai:.4f},0,1)"
            seg = f"({gia:.6f}+({moi:.6f}-{gia:.6f})*{_ease_expr(k['ease'], u)})"
        expr = f"if(lt({bien},{t:.4f}),{expr},{seg})"
        gia = moi
    return expr


def can_zoom(keyframes, ease_mac_dinh=None):
    kfs = _chuan(keyframes, ease_mac_dinh)
    return any(abs(k["z"] - 1.0) > 1e-4 or abs(k["x"] - 0.5) > 1e-4 or abs(k["y"] - 0.5) > 1e-4 for k in kfs)


def bieu_thuc_crop(keyframes, W, H, fps=30, ease_mac_dinh=None):
    """→ chuỗi filter video (không có nhãn) áp lên nguồn đã concat. Luôn kết thúc ở kích thước W×H.
    ease_mac_dinh: quyet_dinh["camera"]["ease"] của kênh (ghep.py truyền) cho keyframe thiếu ease."""
    W, H = int(W), int(H)
    cover = f"crop=w='min(iw,ih*{W}/{H})':h='min(ih,iw*{H}/{W})'"      # cắt về tỉ lệ khung (tâm)
    kfs = _chuan(keyframes, ease_mac_dinh)
    if not can_zoom(kfs, ease_mac_dinh):
        return f"{cover},scale={W}:{H}:flags=bicubic,fps={fps}"
    dong = len(kfs) > 1 and any(abs(k["z"] - kfs[0]["z"]) > 1e-4 or abs(k["x"] - kfs[0]["x"]) > 1e-4 or abs(k["y"] - kfs[0]["y"]) > 1e-4 for k in kfs)
    if not dong:   # zoom tĩnh: crop + scale (nhanh, nét)
        k = kfs[0]; z = k["z"]
        return (f"{cover},crop=w='iw/{z:.5f}':h='ih/{z:.5f}':x='iw*{k['x']:.5f}-iw/{z:.5f}/2':y='ih*{k['y']:.5f}-ih/{z:.5f}/2',"
                f"scale={W}:{H}:flags=bicubic,fps={fps}")
    z = _piecewise(kfs, "z"); cx = _piecewise(kfs, "x"); cy = _piecewise(kfs, "y")
    # zoompan: vùng iw/zoom × ih/zoom tại x,y (góc trên trái) → s=WxH. x,y kẹp trong [0, iw-iw/zoom].
    zp = (f"zoompan=z='{z}':x='clip(iw*({cx})-iw/zoom/2,0,iw-iw/zoom)':y='clip(ih*({cy})-ih/zoom/2,0,ih-ih/zoom)'"
          f":d=1:s={W}x{H}:fps={fps}")
    return f"{cover},fps={fps},{zp}"


def gia_tri_tai(keyframes, t, ease_mac_dinh=None):
    """(z, cx, cy) tại t — bản Python, cùng công thức (dùng cho giải vị trí lớp/mặt)"""
    from dung import anim
    kfs = _chuan(keyframes, ease_mac_dinh)
    z, cx, cy = kfs[0]["z"], kfs[0]["x"], kfs[0]["y"]
    for k in kfs[1:]:
        if t < k["t"]:
            break
        u = anim.ease(k["ease"], (t - k["t"]) / k["dai"]) if k["dai"] > 0 else 1.0
        z += (k["z"] - z) * u; cx += (k["x"] - cx) * u; cy += (k["y"] - cy) * u
    return z, cx, cy
