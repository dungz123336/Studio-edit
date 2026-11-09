# -*- coding: utf-8 -*-
"""API kho — hàm thuần, không phụ thuộc framework. Server (http.server) gọi:

    status, mime, body, hdr = api.xu_ly_day_du(duong, query, headers)   # đủ: Range 206, Content-Length…
    status, mime, body      = api.xu_ly(duong, query, headers)          # gọn theo §10 (bỏ qua Range → 200 cả file)

body: bytes | generator (SSE / file stream). mime: Content-Type. hdr: dict header thêm (có thể rỗng).
query: dict {tên: giá trị} (đã urldecode) hoặc chuỗi query. headers: dict header request (chỉ dùng Range).

Đường:
  /api/kho/ds?loai=&q=&trang=&n=&sap=&cd=  danh sách (JSON) — loai có thể nhiều, cách nhau dấu phẩy; cd = lọc công dụng AI
  /api/kho/tim?loai=&q=&n=&cd=&khung=&nl=   tra THEO NGHĨA (đa dạng, gom biến thể) — như kho.tim.tim
  /api/kho/cong-dung?loai=                  nhãn công dụng AI phổ biến [[nhãn, số]] (bộ lọc UI)
  /api/kho/goi-video?du_an=[&lam=1]         gói kho của 1 dự án (doc/kho-video.json; lam=1 chọn lại)
  /api/kho/lay?id=                          1 mục (JSON)
  /api/kho/file?id=&kieu=goc|nghe|thu       file gốc (Range) · nghe thử (mp3) · xem thử (mp4 480p 4 s)
  /api/kho/nghe?id= · /api/kho/thu?id=      tắt của file?kieu=
  /api/kho/xem-truoc?id=                    ảnh xem trước (tạo lười), 404 nếu loại không có
  /api/kho/lap[?ep=1]                       SSE text/event-stream tiến độ (chạy thread, 1 lần một lúc)
  /api/kho/thong-ke                         thống kê (JSON)
  /api/kho/hieu-ung[?sinh=1&ep=1]           danh sách hiệu ứng engine (JSON); sinh=1 dựng nếu thiếu
  /api/kho/hieu-ung/file?id=&kieu=mp4|json|jpg|png
"""
import os, sys, re, json, time, threading, queue, mimetypes
from urllib.parse import parse_qs
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung
from kho import tim, xem_truoc, hieu_ung

MIME = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".aac": "audio/aac", ".m4a": "audio/mp4", ".ogg": "audio/ogg", ".flac": "audio/flac",
        ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm", ".mkv": "video/x-matroska",
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif",
        ".ttf": "font/ttf", ".otf": "font/otf", ".woff": "font/woff", ".woff2": "font/woff2", ".ttc": "font/collection",
        ".json": "application/json; charset=utf-8", ".cube": "text/plain; charset=utf-8", ".3dl": "text/plain; charset=utf-8",
        ".txt": "text/plain; charset=utf-8", ".pdf": "application/pdf", ".xmp": "application/xml", ".lrtemplate": "text/plain; charset=utf-8", ".dng": "image/x-adobe-dng"}
KHUC = 256 * 1024
_lap_khoa = threading.Lock()
_lap_dang = {"chay": False, "nghe": []}       # nghe: list[queue] các client SSE đang theo dõi
_xt_khoa = {}                                  # id → Lock (tránh 2 request cùng tạo 1 xem trước)
_xt_khoa_chinh = threading.Lock()


# ----------------------------------------------------------------------------- tiện ích
def _json(obj, status=200):
    return status, "application/json; charset=utf-8", json.dumps(obj, ensure_ascii=False).encode("utf-8"), {"Cache-Control": "no-store"}


def _loi(msg, status=400):
    return _json({"loi": msg}, status)


def _q(query):
    if isinstance(query, dict):
        return {k: (v[0] if isinstance(v, (list, tuple)) else v) for k, v in query.items()}
    return {k: v[0] for k, v in parse_qs(query or "", keep_blank_values=True).items()}


def _mime(p):
    return MIME.get(os.path.splitext(p)[1].lower()) or mimetypes.guess_type(p)[0] or "application/octet-stream"


def _doc_khuc(p, a, b):
    with open(p, "rb") as f:
        f.seek(a)
        con = b - a + 1
        while con > 0:
            d = f.read(min(KHUC, con))
            if not d:
                break
            con -= len(d)
            yield d


def _tra_file(p, headers=None, cache=True, tai_ten=None):
    """phục vụ file có Range → (status, mime, generator, hdr)"""
    if not p or not os.path.isfile(p):
        return _loi("không có file", 404)
    size = os.path.getsize(p)
    mime = _mime(p)
    hdr = {"Accept-Ranges": "bytes", "Cache-Control": "public, max-age=86400" if cache else "no-store",
           "Last-Modified": time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(os.path.getmtime(p)))}
    if tai_ten:
        hdr["Content-Disposition"] = "inline; filename*=UTF-8''" + _url(tai_ten)
    rng = (headers or {}).get("Range") or (headers or {}).get("range")
    a, b = 0, size - 1
    status = 200
    if rng:
        m = re.match(r"bytes=(\d*)-(\d*)", rng.strip())
        if m:
            s1, s2 = m.group(1), m.group(2)
            if s1 == "" and s2:
                a = max(0, size - int(s2))
            else:
                a = int(s1 or 0)
                if s2:
                    b = min(size - 1, int(s2))
            if a > b or a >= size:
                return 416, "text/plain", b"", {"Content-Range": f"bytes */{size}"}
            status = 206
            hdr["Content-Range"] = f"bytes {a}-{b}/{size}"
    hdr["Content-Length"] = str(b - a + 1)
    if size == 0:
        return status, mime, b"", hdr
    return status, mime, _doc_khuc(p, a, b), hdr


def _url(s):
    from urllib.parse import quote
    return quote(s, safe="")


def _xem_truoc(muc, ep=False):
    """tạo lười, khoá theo id"""
    with _xt_khoa_chinh:
        k = _xt_khoa.setdefault(muc["id"], threading.Lock())
    with k:
        return xem_truoc.tao(muc, ep=ep)


# ----------------------------------------------------------------------------- làm nóng xem trước âm thanh ở nền
_nong = {"chay": False, "con": 0}


def lam_nong_am(so_luong=1):
    """sinh dần dạng sóng nhạc/sfx còn thiếu ở nền (1 luồng, nhường máy: nghỉ khi RAM trống < 1,5 GB, nghỉ khi đang lập)
    để UI không phải chờ. Gọi nhiều lần vô hại (chỉ 1 vòng chạy một lúc); mục lỗi sẽ được thử lại ở lần gọi sau.
    1.2.21: cấu hình v3.kho.lam_nong = false → không chạy (máy yếu / kho lớn)."""
    try:
        from kho import lich_su as _lsc
        if not _lsc.cau_hinh_kho().get("lam_nong", True):
            return
    except Exception:
        pass
    with _lap_khoa:
        if _nong["chay"]:
            return
        _nong["chay"] = True

    def chay():
        try:
            d = os.path.join(chung.duong("kho_chi_muc"), "xem-truoc")
            thieu = [m for m in tim.tat_ca() if m["loai"] in ("nhac", "sfx") and not os.path.isfile(os.path.join(d, m["id"] + ".png"))]
            _nong["con"] = len(thieu)
            for m in thieu:
                while _lap_dang["chay"] or chung.ram_trong_gb() < 1.5:
                    time.sleep(3)
                try:
                    _xem_truoc(m)
                except Exception:
                    time.sleep(1)
                _nong["con"] -= 1
                time.sleep(0.05)
        finally:
            _nong["chay"] = False
    threading.Thread(target=chay, daemon=True, name="kho-lam-nong").start()


# ----------------------------------------------------------------------------- lập (SSE)
def _sse(ev, data):
    return f"event: {ev}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


def _chay_lap(ep):
    from kho import lap as lap_mod

    def phat(ev, d):
        for q in list(_lap_dang["nghe"]):
            try:
                q.put_nowait((ev, d))
            except Exception:
                pass
    last = [0.0]

    def td(i, n, ten):
        t = time.time()
        if n and i < n and t - last[0] < 0.15:
            return
        last[0] = t
        phat("tien_do", {"i": i, "n": n, "ten": ten})
    try:
        if ep:                                   # 1.2.21: lập ép = bỏ toàn bộ bảng muc (nghĩa AI trong ai_nghia vẫn giữ, lap gắn lại theo dấu)
            try:
                from kho import csdl
                csdl.xoa_muc(list(csdl.ids_muc()))
            except Exception:
                pass
        tk = lap_mod.lap(tien_do=td)
        tim.nap_lai()
        phat("xong", tk)
        lam_nong_am()
    except Exception as ex:
        phat("loi", {"loi": f"{type(ex).__name__}: {ex}"})
    finally:
        with _lap_khoa:
            _lap_dang["chay"] = False
        phat("het", {})


def _lap_sse(q):
    hang = queue.Queue()
    with _lap_khoa:
        _lap_dang["nghe"].append(hang)
        moi = not _lap_dang["chay"]
        if moi:
            _lap_dang["chay"] = True
    if moi:
        threading.Thread(target=_chay_lap, args=(q.get("ep") in ("1", "true"),), daemon=True).start()

    def gen():
        try:
            yield _sse("bat_dau", {"moi": moi})
            while True:
                try:
                    ev, d = hang.get(timeout=15)
                except queue.Empty:
                    yield b": giu-ket-noi\n\n"
                    continue
                yield _sse(ev, d)
                if ev == "het":
                    break
        finally:
            with _lap_khoa:
                if hang in _lap_dang["nghe"]:
                    _lap_dang["nghe"].remove(hang)
    return 200, "text/event-stream; charset=utf-8", gen(), {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}


# ----------------------------------------------------------------------------- gắn nghĩa AI (1.2.19, SSE)
_gn = {"chay": False, "nghe": []}


def _gan_nghia_sse(q):
    from kho import gan_nghia as GN
    if q.get("uoc") in ("1", "true"):
        try:
            r = GN.chay(chi_uoc=True, in_ra=lambda s: None)
            so_muc = sum(sum(len(x) if isinstance(x, list) else 1 for x in t.get("muc", [])) if isinstance(t, dict) else 0 for t in [])
            theo = r.get("theo") or {}
            return _json({"viec": r.get("viec", 0), "uoc_usd": r.get("uoc_usd", 0), "so_muc": sum(int(t.get("muc", 0)) for t in theo.values()), "theo": theo})
        except Exception as ex:
            return _loi(f"không ước được: {ex}", 500)
    hang = queue.Queue()
    with _lap_khoa:
        _gn["nghe"].append(hang)
        moi = not _gn["chay"]
        if moi:
            _gn["chay"] = True

    def phat(ev, d):
        for x in list(_gn["nghe"]):
            try:
                x.put_nowait((ev, d))
            except Exception:
                pass

    def chay():
        try:
            try:
                ns = float(q.get("ngan_sach") or 3.0)
            except ValueError:
                ns = 3.0
            r = GN.chay(ngan_sach=ns, in_ra=lambda s: phat("dong", {"chu": s}))
            try:
                tim.nap_lai()
            except Exception:
                pass
            phat("xong", {"gan": r.get("gan", 0), "usd": r.get("usd", 0)})
        except Exception as ex:
            phat("loi", {"loi": f"{type(ex).__name__}: {ex}"})
        finally:
            with _lap_khoa:
                _gn["chay"] = False
            phat("het", {})
    if moi:
        threading.Thread(target=chay, daemon=True, name="kho-gan-nghia").start()

    def gen():
        try:
            yield _sse("bat_dau", {"moi": moi})
            while True:
                try:
                    ev, d = hang.get(timeout=15)
                except queue.Empty:
                    yield b": giu-ket-noi\n\n"
                    continue
                yield _sse(ev, d)
                if ev == "het":
                    break
        finally:
            with _lap_khoa:
                if hang in _gn["nghe"]:
                    _gn["nghe"].remove(hang)
    return 200, "text/event-stream; charset=utf-8", gen(), {"Cache-Control": "no-store", "X-Accel-Buffering": "no"}


# ----------------------------------------------------------------------------- xử lý
def xu_ly_day_du(duong, query=None, headers=None):
    q = _q(query)
    d = duong.split("?", 1)[0].rstrip("/")
    try:
        if d == "/api/kho/ds":
            try:
                trang, n = int(q.get("trang") or 1), int(q.get("n") or 60)
            except ValueError:
                return _loi("trang/n phải là số")
            r = tim.ds(q.get("loai") or None, q.get("q") or "", trang, n, q.get("sap") or "ten", cong_dung=q.get("cd") or None,
                       chua_dung=q.get("chua_dung") in ("1", "true"))
            r["muc"] = [_gon(m) for m in r["muc"]]
            if not _nong["chay"] and r["tong"]:
                lam_nong_am()
            return _json(r)
        if d == "/api/kho/tim":
            try:
                n = max(1, min(60, int(q.get("n") or 12)))
                nl = int(q["nl"]) if q.get("nl") else None
            except ValueError:
                return _loi("n/nl phải là số")
            ds = tim.tim(q.get("loai") or None, q.get("q") or "", n=n, cong_dung=q.get("cd") or None,
                         hop_khung=q.get("khung") or None, nang_luong=nl)
            return _json({"tong": len(ds), "muc": [dict(_gon(m), diem=m.get("diem"), khop=m.get("khop")) for m in ds]})
        if d == "/api/kho/giong":
            try:
                int(q.get("n") or 8)
            except ValueError:
                return _loi("n phải là số")                       # 1.2.19: tiếng/nhạc GIỐNG mục này (vân tay mel) — "cho tôi tiếng như tiếng này nhưng khác"
            m = tim.lay(q.get("id") or "")
            if not m:
                return _loi("không có id", 404)
            from kho import tai as _tai
            ds = _tai.giong(m, tim.tat_ca(), n=max(1, min(30, int(q.get("n") or 10))))
            return _json({"tong": len(ds), "muc": [dict(_gon(x), giong=x.get("giong")) for x in ds]})
        if d == "/api/kho/cong-dung":
            return _json({"muc": tim.cong_dung_ds(q.get("loai") or None)})
        if d == "/api/kho/goi-video":
            da = os.path.abspath(q.get("du_an") or "")
            if not da or not os.path.isfile(os.path.join(da, "viec.json")):
                return _loi("du_an không phải thư mục dự án (thiếu viec.json)", 404)
            p = os.path.join(da, "doc", "kho-video.json")
            if q.get("lam") in ("1", "true") or not os.path.isfile(p):
                from kho import goi_video
                return _json(goi_video.goi(da))
            return _json(chung.doc_json(p, {}))
        if d == "/api/kho/lay":
            m = tim.lay(q.get("id") or "")
            return _json(_gon(m, du=True)) if m else _loi("không có id", 404)
        if d in ("/api/kho/file", "/api/kho/nghe", "/api/kho/thu"):
            m = tim.lay(q.get("id") or "")
            if not m:
                return _loi("không có id", 404)
            kieu = q.get("kieu") or ("nghe" if d.endswith("nghe") else "thu" if d.endswith("thu") else "goc")
            if kieu == "nghe" and m["loai"] in ("nhac", "sfx"):
                return _tra_file(xem_truoc.nghe(m), headers)
            if kieu == "thu" and m["loai"] in ("nen", "video"):
                return _tra_file(xem_truoc.thu(m), headers)
            return _tra_file(m["duong"], headers, tai_ten=os.path.basename(m["duong"]))
        if d == "/api/kho/xem-truoc":
            m = tim.lay(q.get("id") or "")
            if not m:
                return _loi("không có id", 404)
            try:
                p = _xem_truoc(m, ep=q.get("ep") in ("1", "true"))
            except Exception as ex:
                return _loi(f"không tạo được xem trước: {ex}", 500)
            if not p:
                return _loi("loại này không có ảnh xem trước", 404)
            return _tra_file(p, headers)
        if d == "/api/kho/lap":
            return _lap_sse(q)
        if d == "/api/kho/gan-nghia":
            return _gan_nghia_sse(q)
        if d == "/api/kho/thong-ke":
            tk = tim.thong_ke()
            try:
                from kho import lich_su as _lsc
                tk["cau_hinh_kho"] = _lsc.cau_hinh_kho()
            except Exception:
                pass
            tk["dang_lap"] = _lap_dang["chay"]
            tk["dang_lam_nong"] = _nong["chay"]; tk["xem_truoc_am_con"] = _nong.get("con", 0)
            tk["hieu_ung"] = len(hieu_ung.danh_sach())
            return _json(tk)
        if d == "/api/kho/hieu-ung":
            ds = hieu_ung.danh_sach()
            if q.get("sinh") in ("1", "true") or (not ds and q.get("sinh") != "0"):
                ds = hieu_ung.sinh(ep=q.get("ep") in ("1", "true"))
            return _json({"tong": len(ds), "muc": ds})
        if d == "/api/kho/hieu-ung/file":
            kieu = q.get("kieu") or "mp4"
            if kieu not in ("mp4", "json", "jpg", "png"):
                return _loi("kieu sai")
            return _tra_file(hieu_ung.duong_file(q.get("id") or "", kieu), headers)
        return _loi("không có đường " + d, 404)
    except Exception as ex:
        return _loi(f"lỗi: {type(ex).__name__}: {ex}", 500)


def xu_ly(duong, query=None, headers=None):
    """bản gọn 3 giá trị theo KIEN-TRUC §10 (không Range: luôn 200 cả file)"""
    status, mime, body, hdr = xu_ly_day_du(duong, query, None)
    return status, mime, body


AI_UI = ("mo_ta", "tu_khoa", "cong_dung", "cam_xuc", "phong_cach", "mau_chu_dao", "nang_luong", "hop_khung", "hop_vai", "de_doc")


def _gon(m, du=False):
    """mục gửi cho UI (bỏ tu_khoa máy dài khi liệt kê; nghĩa AI giữ gọn)"""
    r = {k: v for k, v in m.items() if k not in ("tu_khoa", "pb", "bia", "ai", "diem", "khop") or du}
    ai = m.get("ai") or {}
    if ai:
        r["ai"] = {k: (ai[k][:8] if k == "tu_khoa" and not du else ai[k]) for k in AI_UI if ai.get(k)}
    r["co_xt"] = m["loai"] in ("font", "lut", "nhac", "sfx", "nen", "video", "icon", "anh") or bool(m.get("xem_truoc"))
    try:                                                   # 1.2.19: số video trên máy đã dùng + chữ ký tiếng (UI lọc "chưa dùng", hiện chữ ký)
        from kho import lich_su as _ls, tai as _tai
        r["da_dung"] = _ls.dem_toan_may().get(m["id"], 0)
        if m["loai"] in ("nhac", "sfx"):
            r["chu_ky"] = _tai.mo_ta(m.get("so_do"))
    except Exception:
        pass
    return r


if __name__ == "__main__":
    st, mi, body, h = xu_ly_day_du("/api/kho/thong-ke", {})
    print(st, mi, body.decode("utf-8")[:300])
