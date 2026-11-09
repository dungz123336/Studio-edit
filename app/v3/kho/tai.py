# -*- coding: utf-8 -*-
"""TAI của kho (1.2.19, sửa 1.2.21): đo vật lý tiếng → CHỮ KÝ đọc được + từ tượng thanh Việt / từ khoá Anh + ràng buộc khi tra cứu.
Máy chỉ ĐO, không chọn gu.

so_do thêm cho sfx/nhạc (ngoài pho_hz, tan_cong_ms, dot_ngot của gan_nghia.do_am_them):
    ngan_ms   thời gian từ đỉnh tới khi bao giảm 20 dB (tiếng ngân dài hay tắt khô)
    so_tieng  số lần đập/bật trong cửa sổ đo (1 = một tiếng, nhiều = chuỗi tích tắc/gõ)
    phang     độ phẳng phổ 0..1 (cao = nhiễu/ồn/whoosh, thấp = âm sắc rõ như chuông/nốt) — 1.2.21: đo QUANH ĐỈNH RMS, không phải 3 s đầu
    mel       16 dải mel (dB chuẩn hoá) — vân tay để gom họ / tìm tiếng giống
    peak, rms dBFS (lap._do_sfx đo bằng ffmpeg astats; thiếu thì đo ở đây) — ĐỘ TO đo được, dùng cho từ "nhẹ/mạnh"

do_vat_ly(m) → dict số đo (rỗng nếu không đọc được)            chu_ky(so_do, nguong_to=None) → {"cao","bat","dai","ngan","tieng","chat"[,"to"]}
mo_ta(so_do) → "cao · bật ngay · 0,4 s · ngân · âm sắc rõ · −21 dB"   mo_ta_muc(m) → chuỗi vật lý cho MỌI loại (font/nền/icon/lut…)
rang_buoc(nghia) → (ràng buộc | None, [từ khoá Anh]) — từ tượng thanh Việt + từ khoá Anh (whoosh, pop, ding…) + từ ĐỘ TO (nhẹ/mạnh);
                   rb["_tu"] = các từ đã khớp (tim.py bỏ từ độ to khỏi câu tra nghĩa)
he_so(m, rb, nguong_to=None) → hệ số nhân điểm 0.55..1.25 (đo khớp ràng buộc; thiếu số đo → 1.0); nguong_to = (rms thấp, rms cao) tính từ ứng viên
do_thieu(muc, tien_do=None, luong=6, ghi=True) → số mục đo thêm (ghi vào m["so_do"]; ghi=True → upsert csdl từng mục)
giong(m, muc, n) → n mục cùng loại có vân tay mel gần nhất (tìm tiếng giống)"""
import os, sys, math, re, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung

_NO = getattr(chung, "_NO_WINDOW", 0)
SR = 22050
KHOA_DO = ("pho_hz", "tan_cong_ms", "dot_ngot", "ngan_ms", "so_tieng", "phang", "mel", "peak", "rms")
DO_PB = 2                 # phiên bản cách đo (2 = 1.2.21: cửa sổ quanh đỉnh RMS + phẳng phổ dải con); mục đo bằng bản cũ được đo lại 1 lần khi lập

# từ tượng thanh / tính chất tiếng Việt → từ khoá Anh (tên tệp hay dùng) + ràng buộc vật lý (đo được, không phải gu)
#   cao: pho_hz ≥ 2200 · trung: 700..2200 · tram: ≤ 700 · bat: tan_cong ≤ 25 ms · dang: ≥ 120 ms
#   ngan: ngan_ms ≥ 350 · kho: ≤ 150 · chuoi: so_tieng ≥ 3 · nhieu: phang ≥ 0.35 · am_sac: phang ≤ 0.2 · dai_s: dur (min, max)
#   to: "nhe" | "manh" — rms so với phân bố ứng viên (1/3 thấp · 1/3 cao), không có ngưỡng dB cố định
TUONG_THANH = {
    "tinh": (["ding", "bell", "chime", "ting"], {"cao": "cao", "bat": "bat", "ngan": "ngan"}),
    "ting": (["ding", "bell", "chime"], {"cao": "cao", "bat": "bat", "ngan": "ngan"}),
    "tinh tinh": (["ding", "bell", "chime", "sparkle"], {"cao": "cao", "bat": "bat"}),
    "ting ting": (["ding", "bell", "chime", "sparkle"], {"cao": "cao", "bat": "bat"}),
    "keng": (["bell", "ding", "metal"], {"cao": "cao", "bat": "bat", "ngan": "ngan"}),
    "đinh": (["ding", "bell"], {"cao": "cao", "bat": "bat"}),
    "leng keng": (["bell", "jingle", "chime"], {"cao": "cao", "tieng": "chuoi"}),
    "lấp lánh": (["sparkle", "shimmer", "magic", "glitter"], {"cao": "cao", "tieng": "chuoi"}),
    "bùm": (["boom", "impact", "hit", "explosion"], {"cao": "tram", "bat": "bat", "chat": "nhieu"}),
    "bùm bùm": (["boom", "impact", "drum"], {"cao": "tram", "bat": "bat"}),
    "đùng": (["boom", "impact", "explosion"], {"cao": "tram", "bat": "bat"}),
    "rầm": (["impact", "slam", "crash"], {"cao": "tram", "bat": "bat", "chat": "nhieu"}),
    "vút": (["whoosh", "swoosh", "swish"], {"bat": "dang", "chat": "nhieu"}),
    "vèo": (["whoosh", "swoosh", "swish", "zip"], {"chat": "nhieu"}),
    "xoẹt": (["swoosh", "swish", "whoosh"], {"chat": "nhieu", "dai_s": (0.05, 1.5)}),
    "vù": (["whoosh", "wind"], {"cao": "tram", "chat": "nhieu"}),
    "tách": (["click", "tap", "snap"], {"bat": "bat", "ngan": "kho", "dai_s": (0.03, 0.6)}),
    "cạch": (["click", "clack", "knock"], {"bat": "bat", "ngan": "kho", "dai_s": (0.03, 0.6)}),
    "tích": (["tick", "click", "ticker"], {"bat": "bat", "ngan": "kho", "dai_s": (0.03, 0.6)}),
    "tích tắc": (["tick", "ticker", "clock"], {"tieng": "chuoi"}),
    "tích tích": (["tick", "ticker", "typing"], {"tieng": "chuoi"}),
    "cốc": (["knock", "wood", "block"], {"bat": "bat", "ngan": "kho"}),
    "cộc": (["knock", "wood"], {"bat": "bat", "ngan": "kho"}),
    "lạch cạch": (["typing", "keyboard", "clack"], {"tieng": "chuoi"}),
    "bụp": (["pop", "bubble", "thud"], {"bat": "bat", "ngan": "kho"}),
    "bốp": (["pop", "slap", "punch"], {"bat": "bat", "ngan": "kho"}),
    "bíp": (["beep", "blip", "bleep"], {"cao": "cao", "chat": "am_sac", "dai_s": (0.03, 1.0)}),
    "bíp bíp": (["beep", "alarm", "blip"], {"cao": "cao", "tieng": "chuoi"}),
    "tít tít": (["alarm", "beep", "alert"], {"cao": "cao", "tieng": "chuoi"}),
    "rè": (["glitch", "static", "noise", "distortion"], {"chat": "nhieu"}),
    "giật": (["glitch", "stutter", "digital"], {"chat": "nhieu", "tieng": "chuoi"}),
    "xì": (["hiss", "steam", "air", "static"], {"chat": "nhieu", "cao": "cao"}),
    "ù": (["drone", "hum", "rumble", "sub"], {"cao": "tram", "bat": "dang"}),
    "ùng": (["rumble", "sub", "drone"], {"cao": "tram"}),
    "dâng": (["riser", "rise", "uplifter", "build"], {"bat": "dang", "dai_s": (1.0, 12.0)}),
    "ngân": (["chime", "bell", "pad", "shimmer"], {"ngan": "ngan"}),
    "trong": (["bell", "chime", "glass", "crystal"], {"chat": "am_sac"}),
    "chói": (["high", "bright", "sharp"], {"cao": "cao"}),
    "trầm": (["bass", "sub", "low", "deep"], {"cao": "tram"}),
    "khô": (["dry", "click", "tap"], {"ngan": "kho"}),
    "ngắn": ([], {"dai_s": (0.03, 1.5)}),       # tiếng ngắn: cả tệp ≤ 1,5 s (chuông "ngắn ngân" 1,1 s vẫn là ngắn; chime 12 s thì không)
    "dài": ([], {"dai_s": (1.5, None)}),
    "chuỗi": (["sequence", "ticker", "multiple"], {"tieng": "chuoi"}),
    "một tiếng": ([], {"tieng": "mot"}),
    # 1.2.21: ĐỘ TO — ràng theo rms đã đo (so với phân bố ứng viên), không phải gu
    "rất nhẹ": ([], {"to": "nhe"}), "nhẹ": ([], {"to": "nhe"}), "khẽ": ([], {"to": "nhe"}), "nhỏ": ([], {"to": "nhe"}), "êm": ([], {"to": "nhe"}),
    "rất mạnh": ([], {"to": "manh"}), "mạnh": ([], {"to": "manh"}), "to": ([], {"to": "manh"}), "lớn": ([], {"to": "manh"}), "rõ": ([], {"to": "manh"}),
}
TU_DO_TO = {"rất nhẹ", "nhẹ", "khẽ", "nhỏ", "êm", "rất mạnh", "mạnh", "to", "lớn", "rõ", "soft", "quiet", "loud", "subtle", "gentle", "hard"}

# 1.2.21: từ khoá ANH trong câu tra (AI hay viết "whoosh", "pop", "ding") → ràng buộc vật lý tương ứng (trước: không ràng buộc gì)
TIENG_ANH = {
    "whoosh": {"chat": "nhieu", "bat": "dang"}, "swoosh": {"chat": "nhieu", "bat": "dang"}, "swish": {"chat": "nhieu", "bat": "dang"}, "woosh": {"chat": "nhieu", "bat": "dang"},
    "wind": {"chat": "nhieu", "cao": "tram"}, "air": {"chat": "nhieu"}, "hiss": {"chat": "nhieu", "cao": "cao"},
    "pop": {"bat": "bat", "ngan": "kho"}, "click": {"bat": "bat", "ngan": "kho"}, "tap": {"bat": "bat", "ngan": "kho"}, "snap": {"bat": "bat", "ngan": "kho"},
    "knock": {"bat": "bat", "ngan": "kho"}, "clack": {"bat": "bat", "ngan": "kho"}, "bubble": {"bat": "bat", "ngan": "kho"}, "thud": {"bat": "bat", "cao": "tram"},
    "ding": {"cao": "cao", "bat": "bat", "ngan": "ngan"}, "bell": {"cao": "cao", "bat": "bat", "ngan": "ngan"}, "chime": {"cao": "cao", "ngan": "ngan"},
    "ting": {"cao": "cao", "bat": "bat", "ngan": "ngan"}, "jingle": {"cao": "cao", "tieng": "chuoi"}, "sparkle": {"cao": "cao", "tieng": "chuoi"},
    "shimmer": {"cao": "cao", "ngan": "ngan"}, "glitter": {"cao": "cao", "tieng": "chuoi"}, "magic": {"cao": "cao"},
    "riser": {"bat": "dang", "dai_s": (1.0, 12.0)}, "rise": {"bat": "dang"}, "uplifter": {"bat": "dang", "dai_s": (1.0, 12.0)}, "build": {"bat": "dang"},
    "boom": {"cao": "tram", "bat": "bat"}, "impact": {"cao": "tram", "bat": "bat"}, "hit": {"bat": "bat"}, "explosion": {"cao": "tram", "bat": "bat", "chat": "nhieu"},
    "slam": {"cao": "tram", "bat": "bat"}, "crash": {"bat": "bat", "chat": "nhieu"}, "punch": {"bat": "bat", "ngan": "kho"}, "slap": {"bat": "bat", "ngan": "kho"},
    "bass": {"cao": "tram"}, "sub": {"cao": "tram"}, "low": {"cao": "tram"}, "deep": {"cao": "tram"}, "rumble": {"cao": "tram"}, "drone": {"cao": "tram", "bat": "dang"},
    "hum": {"cao": "tram", "bat": "dang"}, "high": {"cao": "cao"}, "bright": {"cao": "cao"}, "sharp": {"cao": "cao"},
    "glitch": {"chat": "nhieu"}, "static": {"chat": "nhieu"}, "noise": {"chat": "nhieu"}, "distortion": {"chat": "nhieu"}, "stutter": {"chat": "nhieu", "tieng": "chuoi"},
    "beep": {"cao": "cao", "chat": "am_sac"}, "blip": {"cao": "cao", "chat": "am_sac", "ngan": "kho"}, "bleep": {"cao": "cao", "chat": "am_sac"}, "alarm": {"cao": "cao", "tieng": "chuoi"},
    "tick": {"bat": "bat", "ngan": "kho"}, "ticker": {"tieng": "chuoi"}, "clock": {"tieng": "chuoi"}, "typing": {"tieng": "chuoi"}, "keyboard": {"tieng": "chuoi"},
    "sequence": {"tieng": "chuoi"}, "multiple": {"tieng": "chuoi"}, "dry": {"ngan": "kho"}, "glass": {"chat": "am_sac"}, "crystal": {"chat": "am_sac"},
    "short": {"dai_s": (0.03, 1.5)}, "long": {"dai_s": (1.5, None)},
    "soft": {"to": "nhe"}, "quiet": {"to": "nhe"}, "subtle": {"to": "nhe"}, "gentle": {"to": "nhe"}, "loud": {"to": "manh"}, "hard": {"to": "manh"},
}


# ----------------------------------------------------------------------------- đo
def _pcm(duong, ss, t):
    cmd = [chung.duong("ffmpeg"), "-v", "error", "-ss", f"{ss:.2f}", "-t", f"{t:.2f}", "-i", duong, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"]
    e = dict(os.environ); e.setdefault("PYTHONUTF8", "1")
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=60, env=e, creationflags=_NO)
    except Exception:
        return None
    import numpy as np
    x = np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768.0
    return x if len(x) >= SR // 20 else None


def _mel_bank(n_fft, n_mel=16, fmin=60.0, fmax=9000.0):
    import numpy as np
    def hz2mel(f): return 2595.0 * np.log10(1.0 + f / 700.0)
    def mel2hz(m): return 700.0 * (10.0 ** (m / 2595.0) - 1.0)
    pts = mel2hz(np.linspace(hz2mel(fmin), hz2mel(fmax), n_mel + 2))
    f = np.fft.rfftfreq(n_fft, 1 / SR)
    bank = np.zeros((n_mel, len(f)), np.float32)
    for i in range(n_mel):
        lo, mid, hi = pts[i], pts[i + 1], pts[i + 2]
        bank[i] = np.clip(np.minimum((f - lo) / max(mid - lo, 1e-6), (hi - f) / max(hi - mid, 1e-6)), 0, 1)
    return bank


def do_vat_ly(m):
    """đo → dict số đo; rỗng nếu không đọc được. sfx: đọc tới 12 s đầu; nhạc: 6 s từ 25 % bài.
    1.2.21: phổ (pho_hz, phang, mel) đo trên CỬA SỔ 3 S QUANH ĐỈNH RMS (−0,5 s … +2,5 s) — tiếng dâng dần (whoosh/riser) không còn bị
    đo lúc mới nhú; bao/tấn công/ngân/số tiếng đo trên cả đoạn đọc; peak/rms (dBFS) bổ sung khi lap._do_sfx chưa đo."""
    try:
        import numpy as np
    except Exception:
        return {}
    sd = m.get("so_do") or {}
    dur = float(sd.get("dur") or 0)
    nhac = m.get("loai") == "nhac" and dur > 6
    ss = max(0.0, min(dur * 0.25, dur - 6.0)) if nhac else 0.0
    x = _pcm(m.get("duong") or "", ss, 6.0 if nhac else 12.0)
    if x is None:
        return {}
    ra = {"do_pb": DO_PB}
    hop = int(SR * 0.01)
    k = len(x) // hop
    env = None
    if k >= 3:
        env = np.sqrt((x[:k * hop].reshape(k, hop) ** 2).mean(1)) + 1e-7
        db = 20 * np.log10(env)
        dinh = int(np.argmax(db))
        nguong = db[dinh] - 40
        dau = int(np.argmax(db > nguong))
        ra["tan_cong_ms"] = int((dinh - dau) * 10)
        dd = np.diff(db[dau:dinh + 1]) if dinh > dau else np.array([db[dinh] - nguong])
        ra["dot_ngot"] = round(float(dd.max()) if len(dd) else 0.0, 1)
        sau = db[dinh:]
        duoi = np.nonzero(sau < db[dinh] - 20)[0]
        ra["ngan_ms"] = int((duoi[0] if len(duoi) else len(sau)) * 10)
        ng = db[dinh] - 18                   # số tiếng: đỉnh cục bộ của bao vượt ngưỡng (cách nhau ≥ 60 ms)
        so, cuoi = 0, -100
        for i in range(1, k - 1):
            if db[i] > ng and db[i] >= db[i - 1] and db[i] >= db[i + 1] and i - cuoi >= 6:
                so += 1; cuoi = i
        ra["so_tieng"] = max(1, so)
        if "peak" not in sd:
            ra["peak"] = round(float(20 * np.log10(max(float(np.abs(x).max()), 1e-6))), 1)
        if "rms" not in sd:
            ra["rms"] = round(float(20 * np.log10(max(float(np.sqrt((x ** 2).mean())), 1e-6))), 1)
        a = max(0, dinh * hop - int(SR * 0.5)); b = min(len(x), a + int(SR * 3.0))
        cua_so = x[a:b]
    else:
        cua_so = x
    n = 2048
    if len(cua_so) >= n:
        kk = len(cua_so) // n
        fr = cua_so[:kk * n].reshape(kk, n) * np.hanning(n)
        mag = np.abs(np.fft.rfft(fr, axis=1)) + 1e-9
        en = mag.sum(1)
        song = en > (en.max() * 0.05)
        if song.any():
            f = np.fft.rfftfreq(n, 1 / SR)
            c = (mag[song] * f).sum(1) / np.maximum(mag[song].sum(1), 1e-9)
            ra["pho_hz"] = int(np.median(c))
            p = mag[song] ** 2
            # độ phẳng phổ: trung bình (trọng số năng lượng) của phẳng phổ TỪNG DẢI con (12 dải log 100 Hz–8 kHz, sàn −40 dB trong dải)
            # — nhiễu/gió trong dải nó chiếm → ~0,5; nốt/chuông → ~0,05. 1.2.21: trước đây lấy cả 1025 bin tới 11 kHz không sàn →
            # bin gần 0 kéo trung bình nhân về 0, 98 % kho ra phang < 0,05 (nhãn "nhiễu" không bao giờ đúng với whoosh)
            bien = np.geomspace(100.0, 8000.0, 13)
            tu_so, mau_so = np.zeros(len(p)), np.zeros(len(p))
            for j in range(12):
                dai = (f >= bien[j]) & (f < bien[j + 1])
                if dai.sum() < 4:
                    continue
                pb = p[:, dai]
                w = pb.sum(1)
                pb = np.maximum(pb, pb.max(1, keepdims=True) * 1e-4)
                fl = np.exp(np.log(pb).mean(1)) / np.maximum(pb.mean(1), 1e-12)
                tu_so += w * fl; mau_so += w
            phang = tu_so / np.maximum(mau_so, 1e-12)
            ra["phang"] = round(float(np.median(phang)), 3)
            bank = _mel_bank(n)
            melv = np.log10(np.maximum(bank @ p.mean(0), 1e-10))
            melv = melv - melv.max()
            ra["mel"] = [round(float(v), 2) for v in melv]
    return ra


def ghi_danh_muc(muc):
    """1.2.21: upsert các mục cho trước vào csdl (trước: ghi lại cả danh-muc.jsonl). Trả số mục ghi."""
    from kho import csdl
    return csdl.upsert_muc([m for m in muc if m.get("id")])


def do_thieu(muc, tien_do=None, luong=6, ghi=True):
    """đo thêm cho mục sfx/nhạc chưa có 'ngan_ms' / 'rms' hoặc đo bằng phiên bản cũ (do_pb ≠ DO_PB) → số mục đã đo (ghi vào m['so_do']).
    ghi=True: upsert csdl từng mục đã đo (lap.lap gọi ghi=False vì tự upsert phần đổi)."""
    can = [m for m in muc if m.get("loai") in ("sfx", "nhac") and m.get("duong")
           and ("ngan_ms" not in (m.get("so_do") or {}) or "rms" not in (m.get("so_do") or {}) or (m.get("so_do") or {}).get("do_pb") != DO_PB)]
    if not can:
        return 0
    from concurrent.futures import ThreadPoolExecutor
    n, da_do = 0, []
    with ThreadPoolExecutor(max_workers=max(1, luong)) as ex:
        for i, (m, d) in enumerate(zip(can, ex.map(do_vat_ly, can))):
            if d:
                m.setdefault("so_do", {}).update(d); n += 1; da_do.append(m)
            if tien_do and (i % 50 == 0 or i == len(can) - 1):
                try:
                    tien_do(i + 1, len(can), m.get("ten", ""))
                except Exception:
                    pass
    if ghi and da_do:
        ghi_danh_muc(da_do)
    return n


# ----------------------------------------------------------------------------- chữ ký
def chu_ky(sd, nguong_to=None):
    """số đo → nhãn (chỉ nhãn có số đo). Ngưỡng là vật lý âm học, không phải gu.
    nguong_to = (rms thấp, rms cao) — phân bố của tập ứng viên (tim.py tính) → nhãn "to": nhe/vua/manh; không có → không gắn nhãn."""
    sd = sd or {}
    ra = {}
    hz = sd.get("pho_hz")
    if hz is not None:
        ra["cao"] = "cao" if hz >= 2200 else "tram" if hz <= 700 else "trung"
    tc = sd.get("tan_cong_ms")
    if tc is not None:
        ra["bat"] = "bat" if tc <= 25 else "dang" if tc >= 120 else "vua"
    d = sd.get("dur")
    if d is not None:
        d = float(d)
        ra["dai"] = "ngan" if d <= 0.8 else "dai" if d >= 2.5 else "vua"
    ng = sd.get("ngan_ms")
    if ng is not None:
        ra["ngan"] = "ngan" if ng >= 350 else "kho" if ng <= 150 else "vua"
    st = sd.get("so_tieng")
    if st is not None:
        ra["tieng"] = "chuoi" if st >= 3 else "mot"
    ph = sd.get("phang")
    if ph is not None:
        ra["chat"] = "nhieu" if ph >= 0.35 else "am_sac" if ph <= 0.2 else "vua"
    rms = sd.get("rms")
    if rms is not None and nguong_to:
        lo, hi = nguong_to
        ra["to"] = "nhe" if rms <= lo else "manh" if rms >= hi else "vua"
    return ra


_TEN = {"cao": {"cao": "cao", "trung": "trung", "tram": "trầm"}, "bat": {"bat": "bật ngay", "dang": "dâng dần", "vua": ""},
        "ngan": {"ngan": "ngân", "kho": "khô", "vua": ""}, "tieng": {"chuoi": "chuỗi", "mot": ""}, "chat": {"nhieu": "nhiễu/gió", "am_sac": "âm sắc rõ", "vua": ""}}


def _db(v):
    return f"{v:.0f} dB".replace("-", "−")


def mo_ta(sd):
    """'cao · bật ngay · 0,4 s · ngân · âm sắc rõ · −21 dB' (bỏ nhãn trung tính; rms là SỐ đo, AI tự so).
    Nhạc (có BPM/LUFS): 'BPM · LUFS · dài · sáng/trầm'."""
    sd = sd or {}
    if sd.get("bpm") or (sd.get("dur") and float(sd["dur"]) >= 25 and sd.get("lufs") is not None):
        phan = []
        if sd.get("bpm"):
            phan.append(f"{sd['bpm']} BPM")
        if sd.get("lufs") is not None:
            phan.append(f"{sd['lufs']} LUFS")
        if sd.get("dur"):
            d = float(sd["dur"]); phan.append(f"{int(d // 60)}:{int(d % 60):02d}")
        hz = sd.get("pho_hz")
        if hz is not None:
            phan.append("sáng" if hz >= 2200 else "trầm" if hz <= 700 else "ấm")
        return " · ".join(phan)
    ck = chu_ky(sd)
    phan = []
    for k in ("cao", "bat"):
        t = _TEN[k].get(ck.get(k, ""), "")
        if t:
            phan.append(t)
    d = (sd or {}).get("dur")
    if d is not None:
        d = float(d)
        phan.append(f"{d:.1f} s".replace(".", ",") if d < 10 else f"{d:.0f} s")
    for k in ("ngan", "tieng", "chat"):
        t = _TEN[k].get(ck.get(k, ""), "")
        if t:
            phan.append(t)
    if sd.get("rms") is not None:
        phan.append(_db(float(sd["rms"])))
    return " · ".join(phan)


def mo_ta_muc(m):
    """1.2.21: chuỗi vật lý cho MỌI loại mục (tim.tim trả `chu_ky` cho mọi ứng viên):
    sfx/nhạc = mo_ta(so_do) · font = 'đậm 700 · nghiêng · biến thiên · đủ dấu' · nền/video/icon/ảnh = '1920×1080 · alpha · 12 s · 30 fps' · lut = '33³'"""
    sd = m.get("so_do") or {}
    loai = m.get("loai")
    if loai in ("sfx", "nhac"):
        return mo_ta(sd)
    phan = []
    if loai == "font":
        if sd.get("dam") is not None:
            phan.append(f"đậm {sd['dam']}")
        if sd.get("nghieng"):
            phan.append("nghiêng")
        if sd.get("var"):
            phan.append("biến thiên" + (f" ({','.join(sd.get('truc') or [])})" if sd.get("truc") else ""))
        phan.append("đủ dấu" if (m.get("du_dau") or sd.get("du_dau")) else "THIẾU DẤU")
        if sd.get("so_ky_tu"):
            phan.append(f"{sd['so_ky_tu']} ký tự")
        return " · ".join(phan)
    if loai == "lut":
        return f"{sd['kich']}³" if sd.get("kich") else ""
    if loai == "preset_capcut":
        return f"{sd['kb']} KB" if sd.get("kb") else ""
    if sd.get("w") and sd.get("h"):
        phan.append(f"{sd['w']}×{sd['h']}" + (" dọc" if sd["h"] > sd["w"] else " ngang" if sd["w"] > sd["h"] else " vuông"))
    if sd.get("alpha"):
        phan.append("alpha")
    if sd.get("dur"):
        d = float(sd["dur"]); phan.append(f"{d:.1f} s".replace(".", ",") if d < 10 else f"{d:.0f} s")
    if sd.get("fps"):
        phan.append(f"{sd['fps']:.0f} fps")
    if sd.get("co_am"):
        phan.append("có tiếng")
    return " · ".join(phan)


# ----------------------------------------------------------------------------- ràng buộc từ nghĩa
def _co_dau(s):
    return chung.NFC((s or "")).lower()


_TT = sorted(((_co_dau(k), k) for k in TUONG_THANH), key=lambda x: -len(x[0]))
# tính từ thường của tiếng Việt (trong, ngắn, dài, khô, tách…) chỉ là tính chất TIẾNG khi câu có từ chỉ tiếng — "gõ phím trong văn phòng" không phải "âm sắc trong"
_TU_THUONG = {"trong", "ngắn", "dài", "khô", "chói", "trầm", "tách", "cốc", "cộc", "tích", "dâng", "giật", "ngân", "ù", "xì", "to", "lớn", "rõ", "êm", "nhỏ"}
_CO_TIENG = re.compile(r"tiếng|âm thanh|âm sắc|sfx|sound|chuông|bell|ding|chime|pop|click|whoosh|swoosh|swish|hit|impact|riser|beep|bíp|glitch|noise"
                       r"|hiệu ứng|nhấn|chuyển cảnh|đập|bật|vang|vút|bùm|tinh|ting|keng|rè|vèo|xoẹt|bụp|bốp|reo|boom|tick|typing|whoosh|woosh", re.I)


def rang_buoc(nghia):
    """nghĩa → (ràng buộc gộp | None, [từ khoá Anh thêm]). Khớp CÓ DẤU (ngân ≠ ngắn, đùng ≠ đúng, chuỗi ≠ chuối), cụm dài trước;
    từ thường (trong/ngắn/dài/khô/to/nhỏ…) chỉ tính khi câu có từ chỉ tiếng. 1.2.21: từ khoá Anh (TIENG_ANH) cũng ràng buộc;
    từ độ to (nhẹ/mạnh…) → rb["to"]; rb["_tu"] = các từ đã khớp (tim.py bỏ từ độ to khỏi câu tra nghĩa)."""
    s = " " + re.sub(r"[^\w ]+", " ", _co_dau(nghia)) + " "
    s = re.sub(r"\s+", " ", s)
    rb, en, da = {}, [], []
    co_tieng = bool(_CO_TIENG.search(s))
    for kd, goc in _TT:
        if f" {kd} " in s and not any(f" {kd} " in f" {x} " for x in da):
            if kd in _TU_THUONG and not co_tieng:
                continue
            da.append(kd)
            e, r = TUONG_THANH[goc]
            en.extend(x for x in e if x not in en)
            for k, v in r.items():
                rb.setdefault(k, v)
    for t in re.findall(r"[a-z]+", s):                 # từ khoá Anh trong câu (whoosh, pop, ding, riser…)
        r = TIENG_ANH.get(t)
        if r and t not in da:
            da.append(t)
            for k, v in r.items():
                rb.setdefault(k, v)
    if rb:
        rb["_tu"] = da
    return (rb or None), en


def tu_do_to(rb):
    """các từ ĐỘ TO đã khớp trong rb (để bỏ khỏi câu tra nghĩa — là ràng buộc vật lý, không phải nghĩa)"""
    return [t for t in (rb or {}).get("_tu", []) if t in TU_DO_TO]


def he_so(m, rb, nguong_to=None):
    """điểm × hệ số: mỗi ràng buộc khớp +0.08 (tối đa 1.25), lệch ×0.75 (tối thiểu 0.55); thiếu số đo → bỏ qua.
    "to" (nhẹ/mạnh) so rms với nguong_to = (thấp, cao) của tập ứng viên; không có ngưỡng → bỏ qua."""
    if not rb:
        return 1.0
    sd = m.get("so_do") or {}
    ck = chu_ky(sd, nguong_to)
    hs = 1.0
    for k, v in rb.items():
        if k.startswith("_"):
            continue
        if k == "dai_s":
            d = sd.get("dur")
            if d is None:
                continue
            a, b = v
            ok = (a is None or float(d) >= a) and (b is None or float(d) <= b)
        else:
            if k not in ck:
                continue
            ok = ck[k] == v or ck[k] == "vua"
        hs *= 1.08 if ok else 0.75
    return max(0.55, min(1.25, hs))


def nguong_to(muc_ds):
    """(rms 1/3 thấp, rms 1/3 cao) của các mục có rms — phân bố thật của tập ứng viên, không phải ngưỡng dB cố định"""
    v = sorted(float((m.get("so_do") or {}).get("rms")) for m in muc_ds if (m.get("so_do") or {}).get("rms") is not None)
    if len(v) < 6:
        return None
    return (v[len(v) // 3], v[(2 * len(v)) // 3])


def giong(m, muc, n=8):
    """n mục cùng loại GIỐNG tiếng này: cosine vân tay mel − lệch độ dài (log) − lệch chữ ký (cao/bật/chất/chuỗi) — 'tiếng như tiếng này nhưng khác tệp'"""
    sd0 = m.get("so_do") or {}
    v = sd0.get("mel")
    if not v:
        return []
    import numpy as np
    a = np.array(v, np.float32); a = a - a.mean(); na = np.linalg.norm(a) + 1e-6
    ck0 = chu_ky(sd0); d0 = float(sd0.get("dur") or 1.0)
    ra = []
    for x in muc:
        if x is m or x.get("loai") != m.get("loai") or x.get("id") == m.get("id"):
            continue
        sd = x.get("so_do") or {}
        w = sd.get("mel")
        if not w or len(w) != len(v):
            continue
        b = np.array(w, np.float32); b = b - b.mean()
        s = float(a @ b) / (na * (np.linalg.norm(b) + 1e-6))
        s -= 0.12 * abs(math.log((float(sd.get("dur") or 1.0) + 0.05) / (d0 + 0.05)))
        ck = chu_ky(sd)
        for k in ("cao", "bat", "chat", "tieng", "ngan"):
            if k in ck0 and k in ck and ck0[k] != ck[k] and "vua" not in (ck0[k], ck[k]):
                s -= 0.1
        ra.append((s, x))
    ra.sort(key=lambda t: -t[0])
    return [dict(x, giong=round(float(s), 3)) for s, x in ra[:n]]


if __name__ == "__main__":
    from kho import tim as T
    if len(sys.argv) > 1 and sys.argv[1] == "do":
        muc = T.tat_ca()
        if len(sys.argv) > 2 and sys.argv[2] == "lai":            # đo lại cả kho theo cách 1.2.21 (quanh đỉnh RMS)
            for m in muc:
                if m.get("loai") in ("sfx", "nhac"):
                    for k in ("ngan_ms", "phang"):
                        (m.get("so_do") or {}).pop(k, None)
        n_ = do_thieu(muc, lambda i, n, t: print(f"  {i}/{n} {t}", flush=True))
        print("đo thêm:", n_)
    else:
        for mid in sys.argv[1:]:
            m = T.lay(mid)
            print(mid, chu_ky((m or {}).get("so_do")), mo_ta((m or {}).get("so_do")))
