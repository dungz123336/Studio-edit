# -*- coding: utf-8 -*-
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""1.2.12 · ĐIỀU PHỐI VIỆC NẶNG giữa nhiều video chạy cùng lúc.

Mỗi video là một phiên AI riêng. Phần AI NGHĨ không tốn CPU máy, nhưng các phần MÁY NẶNG (đọc video: nhận giọng + proxy +
mắt máy · dựng nháp · dựng bản thật + chấm · làm lại bìa) mà chạy chồng nhau thì video nào cũng chậm (4K giành CPU).
→ Máy có N "chỗ nặng" (theo nhân + RAM). Phần nặng phải GIỮ một chỗ; hết chỗ thì chờ lượt. Nhờ vậy video B được đọc đúng
lúc AI của video A đang nghĩ, và hai lần dựng không giẫm lên nhau.

Khoá bằng khoá file của hệ điều hành (tiến trình chết là tự nhả — không bao giờ kẹt chỗ).
    with giu("dung", du_an): ...           # chờ tối đa ~8 phút; quá thì báo MÁY BẬN (lệnh chạy lại được)
Đặt STUDIO_CHO_NANG=<số> để ép số chỗ (0 = tắt điều phối)."""
import os, sys, json, time, contextlib

DATA = os.path.expanduser(os.environ.get("STUDIO_DATA") or "~/.studio-edit-video")
THU = os.path.join(DATA, "may-nang")


class MayBan(Exception):
    pass


def _ram_gb():
    try:
        if os.name == "nt":
            import ctypes

            class M(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = M(); m.dwLength = ctypes.sizeof(M)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullTotalPhys / 1024 ** 3
        return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 1024 ** 3
    except Exception:
        return 8.0


def _so_cho_cau_hinh():
    """cau-hinh.json {"v3": {"so_cho": N}} (lõi 1.3) đè số chỗ nặng — đọc thẳng tệp vì v2 không import chung của v3"""
    try:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cau-hinh.json")
        v = ((json.load(open(p, encoding="utf-8")) or {}).get("v3") or {}).get("so_cho")
        return int(v) if v not in (None, "", 0, "0") else None
    except Exception:
        return None


def so_cho():
    """số phần nặng chạy cùng lúc (1.2.21: KHÔNG trần cứng 1–2–3): max(1, min(luồng // 4, RAM GB // 8)) — mỗi phần nặng ~4 luồng + ~8 GB.
    STUDIO_CHO_NANG (0 = tắt điều phối) rồi cau-hinh.json v3.so_cho đè."""
    ep = os.environ.get("STUDIO_CHO_NANG")
    if ep is not None and ep.strip().isdigit():
        return int(ep)
    ch = _so_cho_cau_hinh()
    if ch is not None:
        return max(1, ch)
    luong, ram = os.cpu_count() or 2, _ram_gb()
    return max(1, min(int(luong) // 4, int(ram) // 8))


def _khoa(f):
    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _nha(f):
    try:
        if os.name == "nt":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    f.close()


def ai_dang_giu():
    """[{viec, du_an, luc}] các phần nặng đang chạy (để báo người dùng đang chờ ai)"""
    out = []
    for i in range(so_cho() or 0):
        try:
            out.append(json.load(open(os.path.join(THU, f"cho{i}.json"), encoding="utf-8")))
        except Exception:
            pass
    return out


XEP = os.path.join(THU, "xep")
VE_SONG = 240          # vé không được chạm quá 4 phút (lệnh chờ đã thôi, không chạy lại) → bỏ qua


def _lay_ve(viec, du_an):
    """vé xếp hàng CÔNG BẰNG: ai chờ trước vào trước. Vé giữ nguyên khi lệnh hết giờ chờ rồi chạy lại (cùng việc + dự án)
    → video chờ lâu không bị video khác giành mất lượt mãi."""
    import hashlib
    os.makedirs(XEP, exist_ok=True)
    f = os.path.join(XEP, hashlib.md5(f"{viec}|{du_an}".encode("utf-8")).hexdigest()[:12] + ".json")
    try:
        if time.time() - os.path.getmtime(f) < VE_SONG:
            _cham_ve(f)
            return f
    except OSError:
        pass
    try:
        json.dump({"viec": viec, "du_an": du_an, "tu": time.time()}, open(f, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        return None
    return f


def _cham_ve(f):
    if f:
        try:
            os.utime(f, None)
        except OSError:
            pass


def _bo_ve(f):
    if f:
        try:
            os.remove(f)
        except OSError:
            pass


def _toi_luot(ve, n):
    """được thử giành chỗ khi số vé còn sống xếp TRƯỚC mình < số chỗ"""
    if not ve:
        return True
    try:
        cua = json.load(open(ve, encoding="utf-8"))["tu"]
    except Exception:
        return True
    truoc = 0
    for ten in os.listdir(XEP):
        g = os.path.join(XEP, ten)
        if g == ve:
            continue
        try:
            if time.time() - os.path.getmtime(g) > VE_SONG:
                continue
            if json.load(open(g, encoding="utf-8"))["tu"] < cua:
                truoc += 1
        except Exception:
            continue
    return truoc < n


@contextlib.contextmanager
def giu(viec, du_an="", cho_toi_da=None, log=print):
    n = so_cho()
    if n <= 0:
        yield None
        return
    os.makedirs(THU, exist_ok=True)
    t0, da_bao, giu_f, so = time.time(), False, None, None
    ve = _lay_ve(viec, du_an)
    while giu_f is None:
        for i in range(n if _toi_luot(ve, n) else 0):
            f = open(os.path.join(THU, f"cho{i}.lock"), "a+")
            if _khoa(f):
                giu_f, so = f, i
                break
            f.close()
        if giu_f is not None:
            break
        if not da_bao:
            dang = ", ".join(f"{os.path.basename(str(x.get('du_an', '')))} ({x.get('viec')})" for x in ai_dang_giu()) or "video khác"
            log(f"⏳ Máy đang làm phần nặng của {dang} — chờ lượt (các phần AI nghĩ vẫn chạy song song)…", flush=True) \
                if log is print else log(f"⏳ chờ lượt máy nặng: {dang}")
            da_bao, t_bao = True, time.time()
        elif time.time() - t_bao > 300:                  # 1.2.19: nhịp tim mỗi 5 phút → watchdog (cầu nối/Studio) không coi chờ lượt là treo
            log(f"⏳ vẫn chờ lượt máy nặng ({int((time.time() - t0) // 60)} phút)…", flush=True) \
                if log is print else log(f"⏳ vẫn chờ lượt máy nặng ({int((time.time() - t0) // 60)} phút)")
            t_bao = time.time()
        if cho_toi_da is None:                       # 8 phút (< giới hạn 10 phút một lệnh của Claude Code); đè bằng STUDIO_CHO_TOI_DA
            try:
                cho_toi_da = float(os.environ.get("STUDIO_CHO_TOI_DA") or 540)
            except ValueError:
                cho_toi_da = 540
        _cham_ve(ve)
        if time.time() - t0 > cho_toi_da:
            raise MayBan("máy đang bận dựng video khác")
        time.sleep(3)
    _bo_ve(ve)
    if da_bao:
        log(f"▶ Tới lượt sau {time.time() - t0:.0f}s chờ.", flush=True) if log is print else log("tới lượt")
    try:
        json.dump({"viec": viec, "du_an": du_an, "luc": time.strftime("%H:%M:%S"), "pid": os.getpid()},
                  open(os.path.join(THU, f"cho{so}.json"), "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass
    try:
        yield so
    finally:
        try:
            os.remove(os.path.join(THU, f"cho{so}.json"))
        except OSError:
            pass
        _nha(giu_f)
