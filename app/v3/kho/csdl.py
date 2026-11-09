# -*- coding: utf-8 -*-
"""CSDL kho (1.2.21, kế hoạch 1g): SQLite `kho-chi-muc/kho.sqlite` thay cho danh-muc.jsonl / lich-su-dung.jsonl / ai-nghia.json.
Mọi ghi là UPSERT từng mục trong 1 giao dịch — không còn ghi lại cả tệp; 2 tiến trình ghi song song an toàn (WAL + busy_timeout 5 s).

Bảng:
    muc(id PK, loai, ten, duong, goc, mtime, json)       json = cả mục (như 1 dòng danh-muc.jsonl cũ)
    lich_su(du_an, ho_so, id, luc)                       1 dòng = 1 tài nguyên dùng trong 1 dự án
    ai_nghia(id PK, json)                                 cache gắn nghĩa AI {"dau","dau2","ai","do","luc"} (gan_nghia.py)
    meta(k PK, v)                                         v của k="doi" tăng mỗi lần bảng đổi (trigger) → tim._nap biết khi nào nạp lại

Hàm:
    mo(thu_muc=None) → sqlite3.Connection (đã bật WAL, busy_timeout, tạo bảng; đóng bằng `with closing(mo()) as c`)
    phien(thu_muc=None) → int  (dấu đổi; so sánh để nạp lại bộ nhớ)
    upsert_muc(muc | [muc], thu_muc=None) · xoa_muc(id | [id]) · tat_ca(loai=None) · lay(id) · dem_muc()
    ghi_lich_su(du_an, ho_so, ids, luc=None) — thay toàn bộ dòng của (du_an, ho_so) bằng ids
    lich_su_gan_day(ho_so, n_video=30, bo=None) → {id: số video}   (n video gần nhất theo max(luc), LIMIT trong SQL)
    dem_toan_may(thang=12) → {id: số dự án đã dùng trong `thang` tháng gần đây}
    du_an_da_ghi(ho_so) → set tên dự án đã có lịch sử
    ai_nghia_tat_ca() → {id: rec} · ai_nghia_lay(id) · upsert_ai_nghia({id: rec} | id, rec) · xoa_ai_nghia(ids)
    nhap_tu_jsonl(thu_muc=None) → {"muc","lich_su","ai_nghia"} — nhập 3 tệp cũ một lần khi SQLite trống, giữ nguyên tệp cũ
"""
import os, sys, json, time, sqlite3, threading
from contextlib import closing
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung

TEN = "kho.sqlite"
BUSY_MS = 5000
_khoa = threading.Lock()
_da_tao = set()          # thư mục đã tạo bảng + đã kiểm nhập jsonl (mỗi tiến trình 1 lần)
_DM = {}                 # nhớ chung.duong("kho_chi_muc") (mỗi lần gọi dò ffmpeg qua shutil.which ~27 ms — mo() được gọi rất nhiều)


def thu_muc_mac_dinh():
    if "p" not in _DM:
        _DM["p"] = chung.duong("kho_chi_muc")
    return _DM["p"]
BO_KHOA_KET_QUA = ("diem", "diem_td", "khop", "chu_ky", "da_dung", "dur")     # khoá do tim() thêm vào kết quả — không lưu

_SCHEMA = """
CREATE TABLE IF NOT EXISTS muc(id TEXT PRIMARY KEY, loai TEXT, ten TEXT, duong TEXT, goc TEXT, mtime INTEGER, json TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS muc_loai ON muc(loai);
CREATE TABLE IF NOT EXISTS lich_su(du_an TEXT, ho_so TEXT, id TEXT, luc TEXT);
CREATE INDEX IF NOT EXISTS lich_su_ho_so ON lich_su(ho_so, du_an);
CREATE INDEX IF NOT EXISTS lich_su_id ON lich_su(id);
CREATE INDEX IF NOT EXISTS lich_su_luc ON lich_su(luc);
CREATE TABLE IF NOT EXISTS ai_nghia(id TEXT PRIMARY KEY, json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v INTEGER);
INSERT OR IGNORE INTO meta(k, v) VALUES('doi', 0);
"""
_TRIGGER = "CREATE TRIGGER IF NOT EXISTS {b}_{ev}_doi AFTER {ev} ON {b} BEGIN UPDATE meta SET v = v + 1 WHERE k = 'doi'; END;"


def duong_db(thu_muc=None):
    return os.path.join(thu_muc or thu_muc_mac_dinh(), TEN)


def _ket_noi(p):
    c = sqlite3.connect(p, timeout=BUSY_MS / 1000.0, check_same_thread=False)
    c.execute(f"PRAGMA busy_timeout={BUSY_MS}")
    try:
        c.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass
    c.execute("PRAGMA synchronous=NORMAL")
    return c


def mo(thu_muc=None):
    """kết nối mới (mỗi lần gọi 1 kết nối — rẻ; người gọi đóng). Lần đầu trong tiến trình: tạo bảng + nhập jsonl cũ."""
    thu_muc = thu_muc or thu_muc_mac_dinh()
    if not os.path.isdir(thu_muc):
        os.makedirs(thu_muc, exist_ok=True)
    p = duong_db(thu_muc)
    c = _ket_noi(p)
    k = os.path.normcase(thu_muc)
    if k not in _da_tao:
        with _khoa:
            if k not in _da_tao:
                c.executescript(_SCHEMA + "".join(_TRIGGER.format(b=b, ev=ev) for b in ("muc", "lich_su", "ai_nghia") for ev in ("INSERT", "UPDATE", "DELETE")))
                c.commit()
                _da_tao.add(k)
                try:
                    _nhap(c, thu_muc)
                except Exception as ex:               # nhập lỗi không được làm chết kho: báo ra stderr, tệp cũ giữ nguyên để thử lại
                    sys.stderr.write(f"(csdl: nhập jsonl cũ lỗi: {ex})\n")
    return c


def phien(thu_muc=None):
    with closing(mo(thu_muc)) as c:
        r = c.execute("SELECT v FROM meta WHERE k='doi'").fetchone()
        return int(r[0]) if r else 0


# ----------------------------------------------------------------------------- muc
def _dong_muc(m):
    j = {k: v for k, v in m.items() if k not in BO_KHOA_KET_QUA}
    return (m.get("id"), m.get("loai"), m.get("ten"), m.get("duong"), m.get("goc") or "bo_mua", int(m.get("mtime") or 0),
            json.dumps(j, ensure_ascii=False, separators=(",", ":")))


def upsert_muc(muc, thu_muc=None, c=None):
    """1 mục hoặc danh sách; 1 giao dịch. Trả số dòng."""
    ds = [muc] if isinstance(muc, dict) else list(muc)
    ds = [m for m in ds if m.get("id")]
    if not ds:
        return 0
    sql = "INSERT INTO muc(id, loai, ten, duong, goc, mtime, json) VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET " \
          "loai=excluded.loai, ten=excluded.ten, duong=excluded.duong, goc=excluded.goc, mtime=excluded.mtime, json=excluded.json"
    if c is not None:
        c.executemany(sql, [_dong_muc(m) for m in ds])
        return len(ds)
    with closing(mo(thu_muc)) as c:
        with c:
            c.executemany(sql, [_dong_muc(m) for m in ds])
    return len(ds)


def xoa_muc(ids, thu_muc=None, c=None):
    ds = [ids] if isinstance(ids, str) else list(ids)
    if not ds:
        return 0
    if c is not None:
        c.executemany("DELETE FROM muc WHERE id=?", [(i,) for i in ds])
        return len(ds)
    with closing(mo(thu_muc)) as c:
        with c:
            c.executemany("DELETE FROM muc WHERE id=?", [(i,) for i in ds])
    return len(ds)


def tat_ca(loai=None, thu_muc=None):
    """[muc dict] (thứ tự loại, tên bỏ dấu — như danh-muc.jsonl cũ)"""
    with closing(mo(thu_muc)) as c:
        if loai:
            ds = set(loai.split(",")) if isinstance(loai, str) else set(loai)
            rows = c.execute(f"SELECT json FROM muc WHERE loai IN ({','.join('?' * len(ds))})", sorted(ds)).fetchall()
        else:
            rows = c.execute("SELECT json FROM muc").fetchall()
    ra = [json.loads(r[0]) for r in rows]
    ra.sort(key=lambda m: (m.get("loai") or "", chung.khong_dau(m.get("ten") or "")))
    return ra


def lay(mid, thu_muc=None):
    with closing(mo(thu_muc)) as c:
        r = c.execute("SELECT json FROM muc WHERE id=?", (mid,)).fetchone()
    return json.loads(r[0]) if r else None


def dem_muc(thu_muc=None):
    """{loai: số}"""
    with closing(mo(thu_muc)) as c:
        return {k: n for k, n in c.execute("SELECT loai, COUNT(*) FROM muc GROUP BY loai")}


def ids_muc(thu_muc=None):
    with closing(mo(thu_muc)) as c:
        return {r[0] for r in c.execute("SELECT id FROM muc")}


# ----------------------------------------------------------------------------- lịch sử
def ghi_lich_su(du_an, ho_so, ids, luc=None, thu_muc=None):
    """thay toàn bộ dòng của (du_an, ho_so) bằng ids (gọi lại vô hại). Trả số dòng ghi."""
    luc = luc or time.strftime("%Y-%m-%d %H:%M:%S")
    ids = [i for i in dict.fromkeys(ids or []) if i]
    with closing(mo(thu_muc)) as c:
        with c:
            c.execute("DELETE FROM lich_su WHERE du_an=? AND ho_so=?", (du_an, ho_so or ""))
            c.executemany("INSERT INTO lich_su(du_an, ho_so, id, luc) VALUES(?,?,?,?)", [(du_an, ho_so or "", i, luc) for i in ids])
    return len(ids)


def lich_su_gan_day(ho_so, n_video=30, bo=None, thu_muc=None):
    """{id: số video} trong n_video dự án gần nhất (theo max(luc)) của hồ sơ, bỏ dự án `bo`"""
    if not ho_so:
        return {}
    with closing(mo(thu_muc)) as c:
        gan = [r[0] for r in c.execute(
            "SELECT du_an FROM lich_su WHERE ho_so=? AND du_an<>? GROUP BY du_an ORDER BY MAX(luc) DESC LIMIT ?",
            (ho_so, bo or "", int(n_video)))]
        if not gan:
            return {}
        rows = c.execute(f"SELECT id, COUNT(DISTINCT du_an) FROM lich_su WHERE ho_so=? AND du_an IN ({','.join('?' * len(gan))}) GROUP BY id",
                         [ho_so] + gan).fetchall()
    return {i: n for i, n in rows}


def dem_toan_may(thang=12, thu_muc=None):
    """{id: số dự án đã dùng} trên cả máy, chỉ `thang` tháng gần đây (0/None = tất cả)"""
    with closing(mo(thu_muc)) as c:
        if thang:
            moc = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - float(thang) * 30.44 * 86400))
            rows = c.execute("SELECT id, COUNT(DISTINCT du_an) FROM lich_su WHERE luc>=? GROUP BY id", (moc,)).fetchall()
        else:
            rows = c.execute("SELECT id, COUNT(DISTINCT du_an) FROM lich_su GROUP BY id").fetchall()
    return {i: n for i, n in rows if i}


def du_an_da_ghi(ho_so, thu_muc=None):
    with closing(mo(thu_muc)) as c:
        return {r[0] for r in c.execute("SELECT DISTINCT du_an FROM lich_su WHERE ho_so=?", (ho_so or "",))}


# ----------------------------------------------------------------------------- ai_nghia
def ai_nghia_tat_ca(thu_muc=None):
    with closing(mo(thu_muc)) as c:
        return {i: json.loads(j) for i, j in c.execute("SELECT id, json FROM ai_nghia")}


def ai_nghia_lay(mid, thu_muc=None):
    with closing(mo(thu_muc)) as c:
        r = c.execute("SELECT json FROM ai_nghia WHERE id=?", (mid,)).fetchone()
    return json.loads(r[0]) if r else None


def upsert_ai_nghia(ids_rec, rec=None, thu_muc=None):
    """upsert_ai_nghia({id: rec, ...}) hoặc upsert_ai_nghia(id, rec)"""
    d = {ids_rec: rec} if isinstance(ids_rec, str) else dict(ids_rec or {})
    d = {k: v for k, v in d.items() if k and isinstance(v, dict)}
    if not d:
        return 0
    with closing(mo(thu_muc)) as c:
        with c:
            c.executemany("INSERT INTO ai_nghia(id, json) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET json=excluded.json",
                          [(k, json.dumps(v, ensure_ascii=False, separators=(",", ":"))) for k, v in d.items()])
    return len(d)


def xoa_ai_nghia(ids, thu_muc=None):
    ds = [ids] if isinstance(ids, str) else list(ids)
    if not ds:
        return 0
    with closing(mo(thu_muc)) as c:
        with c:
            c.executemany("DELETE FROM ai_nghia WHERE id=?", [(i,) for i in ds])
    return len(ds)


# ----------------------------------------------------------------------------- nhập jsonl cũ
def _nhap(c, thu_muc):
    """nhập danh-muc.jsonl / lich-su-dung.jsonl / ai-nghia.json MỘT LẦN khi SQLite còn trống. Không đổi tên hay xoá tệp cũ: trong lúc cập nhật
    bản 1.2.20 (server, máy chủ kho) có thể còn chạy và đọc các tệp này; lùi bản cũng cần chúng."""
    ra = {"muc": 0, "lich_su": 0, "ai_nghia": 0}
    if c.execute("SELECT COUNT(*) FROM muc").fetchone()[0]:
        return ra
    p = os.path.join(thu_muc, "ai-nghia.json")
    ds_ai = []
    if os.path.isfile(p):
        d = chung.doc_json(p, {}) or {}
        ds_ai = [(k, json.dumps(v, ensure_ascii=False, separators=(",", ":"))) for k, v in d.items() if k and isinstance(v, dict)]
    p = os.path.join(thu_muc, "lich-su-dung.jsonl")
    ds_ls = []
    if os.path.isfile(p):
        da = set(c.execute("SELECT du_an, ho_so, id FROM lich_su"))
        for d in chung.doc_jsonl(p):
            k = (d.get("du_an") or "", d.get("ho_so") or "", d.get("id") or "")
            if not k[2] or k in da:
                continue
            da.add(k)
            ds_ls.append((k[0], k[1], k[2], d.get("luc") or ""))
    p = os.path.join(thu_muc, "danh-muc.jsonl")
    ds = [m for m in chung.doc_jsonl(p) if m.get("id")] if os.path.isfile(p) else []
    with c:                                # một giao dịch: nhập dở thì lần sau nhập lại từ đầu
        c.executemany("INSERT INTO ai_nghia(id, json) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET json=excluded.json", ds_ai)
        c.executemany("INSERT INTO lich_su(du_an, ho_so, id, luc) VALUES(?,?,?,?)", ds_ls)
        c.executemany("INSERT INTO muc(id, loai, ten, duong, goc, mtime, json) VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                      "loai=excluded.loai, ten=excluded.ten, duong=excluded.duong, goc=excluded.goc, mtime=excluded.mtime, json=excluded.json",
                      [_dong_muc(m) for m in ds])
    ra.update(muc=len(ds), lich_su=len(ds_ls), ai_nghia=len(ds_ai))
    return ra


def nhap_tu_jsonl(thu_muc=None):
    """gọi tay: nhập 3 tệp cũ khi SQLite còn trống → {"muc","lich_su","ai_nghia"}"""
    thu_muc = thu_muc or thu_muc_mac_dinh()
    with closing(mo(thu_muc)) as c:      # mo() đã nhập ở lần đầu
        return _nhap(c, thu_muc)


def thong_ke(thu_muc=None):
    with closing(mo(thu_muc)) as c:
        n_muc = c.execute("SELECT COUNT(*) FROM muc").fetchone()[0]
        n_ls = c.execute("SELECT COUNT(*) FROM lich_su").fetchone()[0]
        n_ai = c.execute("SELECT COUNT(*) FROM ai_nghia").fetchone()[0]
        doi = c.execute("SELECT v FROM meta WHERE k='doi'").fetchone()[0]
    p = duong_db(thu_muc)
    return {"muc": n_muc, "lich_su": n_ls, "ai_nghia": n_ai, "doi": doi, "duong": p,
            "mb": round(os.path.getsize(p) / 1e6, 2) if os.path.isfile(p) else 0}


if __name__ == "__main__":
    print(json.dumps({"nhap": nhap_tu_jsonl(), "thong_ke": thong_ke()}, ensure_ascii=False, indent=1))
