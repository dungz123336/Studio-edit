# -*- coding: utf-8 -*-
"""Tiến trình giữ Whisper trong RAM giữa các việc (nạp model large-v3-turbo mất ~45 s mỗi lần — bỏ được cho mọi việc sau).
- Tự khởi động khi doc/loi.nhan() cần; nghe 127.0.0.1:<cổng ngẫu nhiên>, ghi <du_lieu>/loi-daemon.json {port, pid, model}.
- Mỗi lúc một việc; đang bận → trả "ban" ngay để việc kia tự nạp model tại chỗ (không xếp hàng, không chờ nhau).
- Không việc 40 phút → tự thoát, trả RAM. Đổi model (hạng máy / cấu hình) → thoát để nạp lại.
  python v3/doc/loi_daemon.py --chay        (máy tự gọi; chạy tay để thử)
"""
import os, sys, json, time, socket, threading, subprocess
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung

NGHI_TOI_DA = 40 * 60
HAN_CHO_SAN_SANG = 75.0


def _tep():
    return os.path.join(chung.duong("du_lieu"), "loi-daemon.json")


def _ten_model():
    cfg = chung.cau_hinh().get("whisper", {})
    return cfg.get("model") or chung.hang_may(ha_luong=False)["whisper"]


def _goi_socket(port, msg, han):
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    s.settimeout(han)
    s.sendall((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
    buf = b""
    while not buf.endswith(b"\n"):
        d = s.recv(65536)
        if not d:
            break
        buf += d
    s.close()
    return json.loads(buf.decode("utf-8", "replace") or "{}")


def _dang_chay():
    d = chung.doc_json(_tep(), {}) or {}
    if not d.get("port"):
        return None
    try:
        r = _goi_socket(int(d["port"]), {"lenh": "ping"}, 3)
        if r.get("ok") and r.get("model") == _ten_model():
            return int(d["port"])
        if r.get("ok"):                                  # model khác → bảo thoát, nạp lại
            try:
                _goi_socket(int(d["port"]), {"lenh": "thoat"}, 3)
            except Exception:
                pass
    except Exception:
        pass
    return None


LOG_TOI_DA = 2 << 20        # loi-daemon.log xoay khi > 2 MB (1.2.21)


def _mo_log():
    p = os.path.join(chung.duong("du_lieu"), "loi-daemon.log")
    try:
        if os.path.isfile(p) and os.path.getsize(p) > LOG_TOI_DA:
            os.replace(p, p + ".1")
    except OSError:
        pass
    return open(p, "a", encoding="utf-8")


def _khoi_dong():
    """bật daemon — có KHOÁ tệp: nhiều việc cùng lúc chỉ một việc bật, việc kia chờ (loi-daemon.json.lock).
    1.2.21: lock cũ > 90 s (daemon trước bị giết trước khi xoá lock) → tự xoá rồi O_EXCL lại — trước: mỗi việc chờ 75 s rồi mới nạp tại chỗ."""
    khoa = _tep() + ".lock"
    try:
        if os.path.isfile(khoa):
            if time.time() - os.path.getmtime(khoa) < 90:
                return False
            try:
                os.remove(khoa)
            except OSError:
                pass
        fd = os.open(khoa, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode()); os.close(fd)
    except FileExistsError:
        return False
    except OSError:
        pass
    flags = (0x00000008 | 0x00000200 | 0x08000000) if os.name == "nt" else 0
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    if os.environ.get("HF_HOME"):
        env["HF_HOME"] = os.environ["HF_HOME"]
    log = _mo_log()
    try:
        subprocess.Popen([chung.python_nen(), os.path.abspath(__file__), "--chay"], stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                         cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), env=env, creationflags=flags, start_new_session=(os.name != "nt"))
    finally:
        log.close()                                           # R4a: con đã giữ bản sao handle; cha không giữ loi-daemon.log mở suốt việc
    return True


def goi(du_an, am16, ngon_ngu="vi"):
    """→ "ok" (đã ghi loi.json) | "ban" | None (không có daemon / lỗi → tự nạp tại chỗ)"""
    if os.environ.get("V3_LOI_TAI_CHO"):
        return None
    port = _dang_chay()
    if port is None:
        try:
            _khoi_dong()
        except Exception:
            return None
        het = time.time() + HAN_CHO_SAN_SANG
        while time.time() < het and port is None:
            time.sleep(1.0)
            port = _dang_chay()
        if port is None:
            return None
    try:
        r = _goi_socket(port, {"lenh": "nhan", "du_an": du_an, "am16": am16, "ngon_ngu": ngon_ngu}, 3600)   # 1.2.19 (E6): máy chậm/video dài
    except Exception as ex:
        chung.log(du_an, f"lời: daemon lỗi ({ex}) → nạp tại chỗ")
        return None
    if r.get("ban"):
        return "ban"
    if r.get("ok"):
        return "ok"
    chung.log(du_an, f"lời: daemon báo lỗi {str(r.get('loi'))[:200]} → nạp tại chỗ")
    return None


def _chay():
    from doc import loi as L
    model_ten = _ten_model()
    khoa = threading.Lock()
    cuoi = [time.time()]
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", 0)); srv.listen(4)
    port = srv.getsockname()[1]
    chung.ghi_json(_tep(), {"port": port, "pid": os.getpid(), "model": model_ten, "luc": time.strftime("%Y-%m-%d %H:%M:%S")})
    try:
        os.remove(_tep() + ".lock")
    except OSError:
        pass
    print(f"[{time.strftime('%H:%M:%S')}] daemon lời: cổng {port}, model {model_ten}", flush=True)
    san_sang = {"ok": False}

    def nap():
        try:
            t0 = time.time(); L._nap_model(chung.cau_hinh().get("whisper", {}))
            print(f"[{time.strftime('%H:%M:%S')}] nạp model {time.time() - t0:.1f}s", flush=True)
        except Exception as ex:
            print(f"nạp model lỗi: {ex}", flush=True)
        san_sang["ok"] = True
    threading.Thread(target=nap, daemon=True).start()           # nhận kết nối NGAY (ping trả san_sang=false) → việc khác không bật thêm daemon

    def xu_ly(conn):
        try:
            conn.settimeout(3600)
            buf = b""
            while not buf.endswith(b"\n"):
                d = conn.recv(65536)
                if not d:
                    break
                buf += d
            msg = json.loads(buf.decode("utf-8", "replace") or "{}")
            lenh = msg.get("lenh")
            if lenh == "ping":
                ra = {"ok": 1, "model": model_ten, "san_sang": bool(san_sang["ok"])}
            elif lenh == "thoat":
                ra = {"ok": 1}
                conn.sendall((json.dumps(ra) + "\n").encode("utf-8")); conn.close()
                os._exit(0)
            elif lenh == "nhan":
                het_ = time.time() + 120
                while not san_sang["ok"] and time.time() < het_:
                    time.sleep(0.5)
                if not khoa.acquire(blocking=False):
                    ra = {"ban": 1}
                else:
                    try:
                        cuoi[0] = time.time()
                        p = L._nhan_tai_cho(msg["du_an"], msg["am16"], msg.get("ngon_ngu") or "vi")
                        ra = {"ok": 1, "ra": p}
                    except Exception as ex:
                        ra = {"loi": str(ex)}
                    finally:
                        khoa.release(); cuoi[0] = time.time()
            else:
                ra = {"loi": "lệnh lạ"}
            conn.sendall((json.dumps(ra, ensure_ascii=False) + "\n").encode("utf-8"))
        except Exception as ex:
            try:
                conn.sendall((json.dumps({"loi": str(ex)}) + "\n").encode("utf-8"))
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def canh_nghi():
        while True:
            time.sleep(30)
            if time.time() - cuoi[0] > NGHI_TOI_DA and not khoa.locked():
                print(f"[{time.strftime('%H:%M:%S')}] nghỉ quá lâu → thoát", flush=True)
                try:
                    d = chung.doc_json(_tep(), {}) or {}
                    if d.get("pid") == os.getpid():
                        os.remove(_tep())
                except Exception:
                    pass
                os._exit(0)
    threading.Thread(target=canh_nghi, daemon=True).start()
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=xu_ly, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    if "--chay" in sys.argv:
        _chay()
    else:
        print("cổng:", _dang_chay())
