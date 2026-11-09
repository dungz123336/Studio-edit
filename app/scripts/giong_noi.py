#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""GIỌNG NÓI AI — gọi dịch vụ TTS/nhân bản giọng của aizening.com.

Mỗi người dùng nhập KHOÁ riêng (lưu ở STUDIO_DATA/giong-noi.json). Không nhúng khoá của ai vào gói.

    python giong_noi.py trang-thai             # còn khoá chưa + còn bao nhiêu lượt
    python giong_noi.py voices                 # danh sách giọng mẫu (JSON)
    python giong_noi.py tao "lời đọc" --voice 0 --ra out.mp3
    python giong_noi.py clone "lời đọc" --mau mau.mp3 --ra out.mp3
    python giong_noi.py luu-khoa               # đọc khoá từ bàn phím (stdin) rồi lưu

Khoá lấy theo thứ tự: --khoa > biến môi trường GIONG_KHOA > tệp giong-noi.json.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ.get("GIONG_BASE", "https://aizening.com/api/v1/voice").rstrip("/")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"


def _data():
    return os.environ.get("STUDIO_DATA") or os.path.join(os.path.expanduser("~"), ".studio-edit-video")


def _tep_khoa():
    return os.path.join(_data(), "giong-noi.json")


def doc_khoa():
    try:
        return (json.load(open(_tep_khoa(), encoding="utf-8")).get("khoa") or "").strip()
    except Exception:
        return ""


def luu_khoa(khoa):
    os.makedirs(_data(), exist_ok=True)
    p = _tep_khoa()
    tam = p + f".{os.getpid()}.tmp"
    with open(tam, "w", encoding="utf-8") as f:
        json.dump({"khoa": khoa.strip()}, f)
    os.replace(tam, p)
    if os.name != "nt":                                   # 1.2.21: khoá API chỉ chủ tệp đọc được (Mac/Linux; Windows bỏ qua — ACL riêng)
        try:
            os.chmod(p, 0o600)
        except OSError:
            pass


def khoa_hien(cli=None):
    return (cli or os.environ.get("GIONG_KHOA") or doc_khoa() or "").strip()


class LoiGiong(Exception):
    def __init__(self, tin, ma=None):
        super().__init__(tin)
        self.ma = ma            # mã HTTP (nếu có) — 401/403 = khoá sai; 5xx/429 = máy chủ bận


def _goi(duong, khoa, method="GET", body=None, raw=False, toi_da=60):
    if not khoa:
        raise LoiGiong("chưa có khoá giọng nói — nhập khoá trong Studio (mục Giọng nói AI)")
    url = BASE + duong
    headers = {"Authorization": "Bearer " + khoa, "user-agent": UA, "accept": "application/json"}
    data = None
    if body is not None:
        headers["content-type"] = "application/json"
        data = json.dumps(body).encode()
    rq = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(rq, timeout=toi_da) as r:
            b = r.read()
            return (b if raw else json.loads(b.decode("utf-8", "replace") or "{}"))
    except urllib.error.HTTPError as e:
        try:
            j = json.loads(e.read().decode("utf-8", "replace"))
            tin = (j.get("error") or {}).get("message") or j.get("message") or f"máy chủ trả {e.code}"
        except Exception:
            tin = f"máy chủ trả {e.code}"
        raise LoiGiong(tin, ma=e.code)
    except LoiGiong:
        raise
    except Exception as e:
        raise LoiGiong(f"không gọi được máy chủ giọng nói ({type(e).__name__})")


def voices(khoa):
    j = _goi("/voices", khoa, toi_da=20)
    ds = j.get("voices") or j.get("data") or (j if isinstance(j, list) else [])
    ra = []
    for v in ds:
        if isinstance(v, dict):
            ra.append({"index": v.get("index", v.get("voice_index", len(ra))),
                       "ten": v.get("name") or v.get("ten") or f"Giọng {len(ra)}",
                       "nghe": v.get("preview") or v.get("sample_url") or v.get("audio_url") or ""})
        else:
            ra.append({"index": len(ra), "ten": str(v), "nghe": ""})
    return ra


def quota(khoa):
    try:
        j = _goi("/quota", khoa, toi_da=15)
        con = j.get("remaining")
        if con is None:
            con = (j.get("quota") or {}).get("remaining")
        return {"con": con, "tong": j.get("limit") or j.get("total") or (j.get("quota") or {}).get("limit")}
    except LoiGiong:
        return {"con": None, "tong": None}


def _job_id(j):
    return (j.get("job") or {}).get("id") or j.get("job_id") or j.get("id")


def _cho_xong(khoa, jid, lan=60, text=""):
    """1.2.19: chờ theo độ dài văn bản (≈ 3 s + 1 s / 40 ký tự, tối thiểu 3 phút, tối đa 15 phút); lỗi mạng tạm thời không bỏ cuộc"""
    gioi_han = max(180.0, min(900.0, 120.0 + len(text or "") / 40.0 * 3.0)) if text else lan * 3.0
    t0, loi_lien = time.time(), 0
    while time.time() - t0 < gioi_han:
        time.sleep(3)
        try:
            j = _goi(f"/jobs/{jid}", khoa, toi_da=20)
            loi_lien = 0
        except LoiGiong as e:
            loi_lien += 1
            if loi_lien >= 5:
                raise
            continue
        job = j.get("job") or j
        st = job.get("status", "")
        if st == "done":
            return job.get("audio_url") or ""
        if st in ("failed", "expired"):
            raise LoiGiong(f"máy chủ báo {st}: {job.get('error') or ''}")
    raise LoiGiong(f"máy chủ giọng nói đang chậm (chưa xong sau {int(gioi_han // 60)} phút, mã việc {jid}) — thử lại sau ít phút; lượt đã trừ sẽ được dùng nếu máy chủ hoàn tất")


def _ffmpeg():
    """1.2.21: tìm ffmpeg theo thứ tự FFMPEG_EXE → PATH → thư mục ffmpeg của Studio (có/không đuôi .exe) → Homebrew (Mac) → /usr/local"""
    import shutil
    dl = _data()
    for c in (os.environ.get("FFMPEG_EXE"), shutil.which("ffmpeg"),
              os.path.join(dl, "ffmpeg", "ffmpeg.exe"), os.path.join(dl, "ffmpeg", "ffmpeg"),
              os.path.join(os.path.expanduser("~"), ".studio-edit-video", "ffmpeg", "ffmpeg.exe"),
              os.path.join(os.path.expanduser("~"), ".studio-edit-video", "ffmpeg", "ffmpeg"),
              "/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"):
        if c and os.path.isfile(c):
            return c
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "v3"))
        import chung
        return chung.duong("ffmpeg")
    except Exception:
        return None


def _chuan_mau(mau):
    """1.2.19: mẫu giọng (mp3/wav/m4a/…, tên có dấu, dài) → mp3 mono 44,1 kHz ≤ 60 s tên ASCII trong thư mục tạm; không có ffmpeg → dùng nguyên"""
    ff = _ffmpeg()
    if not ff:
        return mau
    import subprocess, tempfile
    ra = os.path.join(tempfile.gettempdir(), f"studio-giong-mau-{os.getpid()}-{int(time.time())}.mp3")
    try:
        r = subprocess.run([ff, "-v", "error", "-y", "-i", mau, "-t", "60", "-ac", "1", "-ar", "44100", "-b:a", "128k", "-f", "mp3", ra],
                           capture_output=True, timeout=120, creationflags=0x08000000 if os.name == "nt" else 0)
        if r.returncode == 0 and os.path.isfile(ra) and os.path.getsize(ra) > 2000:
            return ra
    except Exception:
        pass
    return mau


def _sua_dinh_dang(ra):
    """1.2.19: máy chủ trả WAV đội lốt .mp3 → chuyển thành mp3 thật (có ffmpeg); không có thì giữ nguyên (trình duyệt/ffmpeg vẫn phát được)"""
    try:
        with open(ra, "rb") as f:
            dau = f.read(4)
    except OSError:
        return ra
    if dau != b"RIFF" or not ra.lower().endswith(".mp3"):
        return ra
    ff = _ffmpeg()
    if not ff:
        return ra
    import subprocess
    tam = ra + ".tmp.mp3"
    try:
        r = subprocess.run([ff, "-v", "error", "-y", "-i", ra, "-b:a", "160k", "-f", "mp3", tam], capture_output=True, timeout=120,
                           creationflags=0x08000000 if os.name == "nt" else 0)
        if r.returncode == 0 and os.path.getsize(tam) > 1000:
            os.replace(tam, ra)
    except Exception:
        try:
            os.remove(tam)
        except OSError:
            pass
    return ra


def _tai_mp3(khoa, jid, audio_url, ra):
    b = None
    try:
        b = _goi(f"/jobs/{jid}/audio", khoa, raw=True, toi_da=120)
    except LoiGiong:
        b = None
    if (not b or len(b) < 1000) and audio_url:
        rq = urllib.request.Request(audio_url, headers={"user-agent": UA})
        b = urllib.request.urlopen(rq, timeout=120).read()
    if not b or len(b) < 1000:
        raise LoiGiong("tải mp3 không thành công")
    os.makedirs(os.path.dirname(os.path.abspath(ra)), exist_ok=True)
    open(ra, "wb").write(b)
    return _sua_dinh_dang(ra)


def tao(khoa, text, voice_index, ra):
    j = _goi("/tts", khoa, "POST", {"text": text, "voice_index": int(voice_index)}, toi_da=30)
    jid = _job_id(j)
    if not jid:
        raise LoiGiong("máy chủ không trả job id")
    return _tai_mp3(khoa, jid, _cho_xong(khoa, jid, text=text), ra)


def clone(khoa, text, mau_mp3, ra):
    # /clone là multipart (text + sample). Tự gói multipart, không cần thư viện ngoài.
    if not os.path.isfile(mau_mp3):
        raise LoiGiong("không thấy tệp giọng mẫu")
    mau_goc = mau_mp3
    mau_mp3 = _chuan_mau(mau_mp3)                   # 1.2.19: mp3 mono ≤ 60 s, tên ASCII (wav/m4a/tên có dấu đều được)
    ranh = "----studio" + os.urandom(8).hex()
    with open(mau_mp3, "rb") as f:
        noi = f.read()
    if mau_mp3 != mau_goc and os.path.basename(mau_mp3).startswith("studio-giong-mau-"):   # 1.2.21: tệp tạm xoá ngay sau khi đọc để gửi
        try:
            os.remove(mau_mp3)
        except OSError:
            pass
    if len(noi) > 25 * 1024 * 1024:
        raise LoiGiong("tệp giọng mẫu quá lớn (> 25 MB) — chọn đoạn 10–60 giây")
    phan = []
    phan.append(f'--{ranh}\r\nContent-Disposition: form-data; name="text"\r\n\r\n{text}\r\n'.encode("utf-8"))
    phan.append(f'--{ranh}\r\nContent-Disposition: form-data; name="sample"; filename="sample.mp3"\r\n'
                f'Content-Type: audio/mpeg\r\n\r\n'.encode("utf-8") + noi + b"\r\n")
    phan.append(f'--{ranh}--\r\n'.encode())
    body = b"".join(phan)
    rq = urllib.request.Request(BASE + "/clone", data=body, method="POST", headers={
        "Authorization": "Bearer " + khoa, "user-agent": UA,
        "content-type": f"multipart/form-data; boundary={ranh}"})
    try:
        j = json.loads(urllib.request.urlopen(rq, timeout=60 + len(noi) // 100000).read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        try:
            tin = (json.loads(e.read()).get("error") or {}).get("message") or f"máy chủ trả {e.code}"
        except Exception:
            tin = f"máy chủ trả {e.code}"
        raise LoiGiong(tin)
    except Exception as e:
        raise LoiGiong(f"gửi giọng mẫu lỗi ({type(e).__name__})")
    jid = _job_id(j)
    if not jid:
        raise LoiGiong("máy chủ không trả job id")
    return _tai_mp3(khoa, jid, _cho_xong(khoa, jid, text=text), ra)


def kiem_khoa(khoa):
    """1.2.19: xác thực khoá ONLINE trước khi lưu → {"ok", "loi", "quota"}: khoá sai (401) / mạng hỏng phân biệt rõ"""
    try:
        q = _goi("/quota", khoa, toi_da=15)
        con = q.get("remaining")
        if con is None:
            con = (q.get("quota") or {}).get("remaining")
        return {"ok": True, "quota": {"con": con, "tong": q.get("limit") or q.get("total") or (q.get("quota") or {}).get("limit")}}
    except LoiGiong as e:
        s = str(e)
        if getattr(e, "ma", None) in (401, 403):
            return {"ok": False, "loi": "khoá không được máy chủ chấp nhận: " + s}
        if "không gọi được" in s or getattr(e, "ma", None) is None or int(e.ma) >= 500 or int(e.ma) == 429:
            return {"ok": False, "loi": "không nối được / máy chủ giọng nói đang bận (mạng, tường lửa, proxy hoặc máy chủ) — khoá chưa kiểm được: " + s, "mang": True}
        return {"ok": False, "loi": "khoá không được máy chủ chấp nhận: " + s}


# ─────────────────────── CLI ───────────────────────
def _arg(ten, mac=None):
    return sys.argv[sys.argv.index(ten) + 1] if ten in sys.argv and sys.argv.index(ten) + 1 < len(sys.argv) else mac


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    a = sys.argv[1:]
    K = khoa_hien(_arg("--khoa"))
    try:
        if not a or a[0] == "trang-thai":
            print(json.dumps({"co_khoa": bool(K), "quota": quota(K) if K else {"con": None}}, ensure_ascii=False))
        elif a[0] == "luu-khoa":
            k = (_arg("--khoa") or sys.stdin.readline()).strip()
            if not k:
                sys.exit("chưa nhập khoá")
            kk = kiem_khoa(k)                       # 1.2.19: dán nhầm mã bản quyền / khoá sai → báo ngay, không lưu
            if not kk.get("ok") and not kk.get("mang"):
                print(json.dumps({"ok": False, "co_khoa": False, "loi": kk["loi"]}, ensure_ascii=False)); sys.exit(1)
            luu_khoa(k)
            print(json.dumps({"ok": True, "co_khoa": True, "quota": kk.get("quota"), "canh_bao": kk.get("loi")}, ensure_ascii=False))
        elif a[0] == "kiem-khoa":
            print(json.dumps(kiem_khoa(K), ensure_ascii=False))
        elif a[0] == "voices":
            print(json.dumps(voices(K), ensure_ascii=False))
        elif a[0] == "tao":
            p = tao(K, a[1], _arg("--voice", "0"), _arg("--ra", "giong.mp3"))
            print(json.dumps({"ok": True, "tep": p}, ensure_ascii=False))
        elif a[0] == "clone":
            p = clone(K, a[1], _arg("--mau"), _arg("--ra", "giong.mp3"))
            print(json.dumps({"ok": True, "tep": p}, ensure_ascii=False))
        elif a[0] == "quota":
            print(json.dumps(quota(K), ensure_ascii=False))
        else:
            sys.exit(__doc__)
    except LoiGiong as e:
        print(json.dumps({"ok": False, "loi": str(e)}, ensure_ascii=False))
        sys.exit(1)
