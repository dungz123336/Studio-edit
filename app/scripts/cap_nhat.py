#!/usr/bin/env python3
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""CẬP NHẬT SKILL — thay lớp của người bán, KHÔNG BAO GIỜ đụng dữ liệu của người dùng.

    python3 cap_nhat.py kiem              # có bản mới không? (nhanh, mất mạng thì im lặng)
    python3 cap_nhat.py cai               # tải bản mới nhất từ máy chủ (cần đã kích hoạt bản quyền) rồi cài
    python3 cap_nhat.py cai <file.zip>    # cài từ zip người bán gửi (kèm <file.zip>.chuky.json)
Mọi bản cập nhật phải mang chữ ký số của người bán (ky_so.KHOA_CAP_NHAT) — sai chữ ký là không cài.
    python3 cap_nhat.py lui               # quay về bản trước (bản sao ở .ban-cu/)

Không bao giờ ghi đè / xoá: hồ sơ người dùng (nao/ca-nhan/* trừ _mau), bài tự học (nao/kien-thuc/cua-toi/),
cau-hinh.json, .venv, tai-nguyen/, dự án và video. Chỉ thay các file có trong TEP-GOI.json của gói.
"""
import hashlib, json, os, shutil, sys, tempfile, time, urllib.error, urllib.request, zipfile

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CU = os.path.join(SKILL, ".ban-cu")
DATA = os.path.expanduser(os.environ.get("STUDIO_DATA") or "~/.studio-edit-video")   # 1.2.21: tệp tạm tải về nằm ở thư mục dữ liệu, không vào RAM
BAO_VE = ("nao/ca-nhan/", "nao/kien-thuc/cua-toi/", "cau-hinh.json", ".venv/", "tai-nguyen/", ".ban-cu/", "NGUOI-BAN",
          ".ban-quyen.json", ".phieu-hien-tai.json", ".phieu-cu/")
GIU_MAU = "nao/ca-nhan/_mau/"          # mẫu hồ sơ là của người bán → được cập nhật


def duoc_thay(rel):
    rel = rel.replace(os.sep, "/")
    if rel.startswith(GIU_MAU):
        return True
    return not any(rel == b or rel.startswith(b) for b in BAO_VE)


def ver(s):
    return tuple(int(x) for x in s.strip().split("."))


def hien_tai():
    try:
        return open(os.path.join(SKILL, "VERSION")).read().strip()
    except OSError:
        return "0.0.0"


def _cfg():
    """→ (địa chỉ gốc máy chủ, mã bản quyền, dấu máy)"""
    sys.path.insert(0, os.path.join(SKILL, "scripts"))
    import ban_quyen
    ma = ban_quyen._doc().get("ma", "")
    return ban_quyen.goc(), ma, ban_quyen.ma_may()


def _rq(url, ma, may):
    if not url.startswith("https://") and not url.startswith(("http://127.0.0.1", "http://localhost")):
        raise RuntimeError("từ chối tải qua kết nối không mã hoá (chỉ https)")
    return urllib.request.Request(url, headers={"X-Ma-Ban-Quyen": ma, "X-Ma-May": may,
                                               "User-Agent": "tro-ly-edit-video/" + hien_tai()})


def _tai(url, ma, may, toi_da=30):
    return urllib.request.urlopen(_rq(url, ma, may), timeout=toi_da).read()


def _tai_ve_tep(url, ma, may, dich, toi_da=120):
    """1.2.21: tải THEO LUỒNG vào tệp (không giữ cả gói 50 MB trong RAM), in tiến độ `TẢI x/y MB` mỗi ~5 %, toi_da = giây chờ mỗi gói dữ liệu.
    → sha256 của tệp"""
    h = hashlib.sha256()
    da, moc = 0, -1
    with urllib.request.urlopen(_rq(url, ma, may), timeout=toi_da) as r, open(dich, "wb") as f:
        tong = int(r.headers.get("Content-Length") or 0)
        while True:
            k = r.read(1 << 18)
            if not k:
                break
            f.write(k); h.update(k); da += len(k)
            pham = int(20 * da / tong) if tong else -1
            if pham != moc:
                moc = pham
                print(f"TẢI {da / 1e6:.1f}/{tong / 1e6:.1f} MB" if tong else f"TẢI {da / 1e6:.1f} MB", flush=True)
    return h.hexdigest()


def _sha_tep(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for k in iter(lambda: f.read(1 << 20), b""):
            h.update(k)
    return h.hexdigest()


def _khoa_ban_cu(ten):
    """thứ tự bản sao .ban-cu/<phiên bản>-<YYYYmmdd-HHMMSS>: theo SỐ phiên bản rồi mốc giờ (R1: sắp theo chuỗi thì 1.2.10 < 1.2.9 → xoá nhầm bản mới)"""
    v, _, moc = ten.partition("-")
    try:
        return (0, ver(v), moc)
    except ValueError:
        return (-1, (), ten)


def don_ban_cu(giu=1):
    """1.2.21 (1h): .ban-cu/ chỉ giữ bản mới nhất (mỗi bản ~51 MB) — gọi sau khi cài thành công"""
    try:
        ds = sorted((d for d in os.listdir(CU) if os.path.isdir(os.path.join(CU, d))), key=_khoa_ban_cu)
    except OSError:
        return 0
    n = 0
    for d in ds[:-giu] if giu else ds:
        shutil.rmtree(os.path.join(CU, d), ignore_errors=True); n += 1
    return n


def kiem_ky(moi):
    """bản cập nhật phải có chữ ký của người bán — máy chủ bị chiếm cũng không giả được"""
    import ky_so
    if not isinstance(moi, dict) or any(k not in moi for k in ("phien_ban", "tep", "sha256")):
        return False                            # R1: latest/chuky thiếu trường → coi như không có chữ ký (bản cũ nổ KeyError)
    nd = {k: moi[k] for k in ("phien_ban", "tep", "sha256")}
    try:
        return bool(ky_so.kiem(ky_so.KHOA_CAP_NHAT, ky_so.chuan(nd), moi.get("chu_ky", "")))
    except Exception:
        return False


def kiem(im_lang=False):
    goc, ma, may = _cfg()
    try:
        moi = json.loads(_tai(goc + "/?duong=latest", ma, may, 4))
    except urllib.error.HTTPError as e:
        try:
            ly_do = json.loads(e.read()).get("loi", "")
        except Exception:
            ly_do = f"máy chủ trả {e.code}"
        print(f"Không nhận được bản mới: {ly_do} — dùng tiếp bản {hien_tai()}.")
        return None
    except Exception as e:
        if not im_lang:
            print(f"Không kiểm được bản mới ({type(e).__name__}) — dùng tiếp bản {hien_tai()}.")
        return None
    if not kiem_ky(moi):
        print("CẢNH BÁO: thông tin bản mới trên máy chủ KHÔNG có chữ ký hợp lệ của người bán — bỏ qua, báo người bán.")
        return None
    if ver(moi["phien_ban"]) > ver(hien_tai()):
        print(f"CÓ BẢN MỚI {moi['phien_ban']} (đang dùng {hien_tai()}). Cài: python3 scripts/cap_nhat.py cai")
        # 1.2.21: người bán ghi `bat_buoc: false` trong phat-hanh.json/latest → bản này không ép khách (Studio đọc dòng này)
        bb = moi.get("bat_buoc", True)
        print("BẮT BUỘC: " + ("0" if bb in (False, 0, "0", "false", "no") else "1"))
        print(moi.get("ghi_chu", "")[:800])
        return moi
    if not im_lang:
        print(f"Đang dùng bản mới nhất ({hien_tai()}).")
    return None


def cai(nguon_zip=None):
    goc_tam = os.path.join(DATA, "cap-nhat-tam")       # 1.2.21: tệp tạm ở thư mục dữ liệu Studio (cùng ổ, không phình %TEMP%)
    os.makedirs(goc_tam, exist_ok=True)
    for d in os.listdir(goc_tam):                        # dọn lần tải dở trước
        shutil.rmtree(os.path.join(goc_tam, d), ignore_errors=True)
    with tempfile.TemporaryDirectory(dir=goc_tam) as td:
        z = os.path.join(td, "goi.zip")
        if nguon_zip:
            if not os.path.exists(nguon_zip):
                sys.exit(f"Không thấy file {nguon_zip}")
            ck = nguon_zip + ".chuky.json"          # người bán gửi kèm file chữ ký
            if not os.path.exists(ck):
                sys.exit(f"DỪNG: thiếu file chữ ký {os.path.basename(ck)} đi kèm — không cài gói không rõ nguồn.")
            moi = json.load(open(ck))
            shutil.copy(nguon_zip, z)
            sha = _sha_tep(z)
        else:
            moi = kiem()
            if not moi:
                return 0
            goc, ma, may = _cfg()
            sha = _tai_ve_tep(goc + "/?duong=tai&phien_ban=" + moi["phien_ban"], ma, may, z, 120)
        if not kiem_ky(moi):
            sys.exit("DỪNG: chữ ký bản cập nhật không hợp lệ — không cài.")
        if sha != moi["sha256"]:
            sys.exit("DỪNG: file gói không khớp mã kiểm tra trong chữ ký — không cài.")
        print("ĐANG CÀI…", flush=True)
        zipfile.ZipFile(z).extractall(td)
        goi = os.path.join(td, "tro-ly-edit-video")
        ds = json.load(open(os.path.join(goi, "TEP-GOI.json")))
        moi_v = ds["phien_ban"]
        if ver(moi_v) <= ver(hien_tai()) and "--ep" not in sys.argv:
            print(f"Gói {moi_v} không mới hơn bản đang dùng {hien_tai()} — bỏ qua (thêm --ep để cài đè).")
            return 0
        # 1) sao lưu toàn bộ lớp người bán hiện tại
        cu_ds = {}
        p_cu = os.path.join(SKILL, "TEP-GOI.json")
        if os.path.exists(p_cu):
            cu_ds = json.load(open(p_cu))["tep"]
        sl = os.path.join(CU, f"{hien_tai()}-{time.strftime('%Y%m%d-%H%M%S')}")
        for r, dirs, fs in os.walk(SKILL):
            dirs[:] = [d for d in dirs if d not in (".venv", ".ban-cu", "__pycache__", "tai-nguyen")]
            for f in fs:
                rel = os.path.relpath(os.path.join(r, f), SKILL)
                if duoc_thay(rel):
                    os.makedirs(os.path.dirname(os.path.join(sl, rel)), exist_ok=True)
                    shutil.copy2(os.path.join(r, f), os.path.join(sl, rel))
        # 2) chép file mới (chỉ lớp người bán)
        thay = 0
        for rel in list(ds["tep"]) + ["TEP-GOI.json"]:
            if not duoc_thay(rel):
                continue
            d = os.path.join(SKILL, rel)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(os.path.join(goi, rel), d); thay += 1
        # 3) bỏ file người bán đã gỡ khỏi bản mới (chỉ file từng thuộc gói cũ)
        bo = [rel for rel in cu_ds if rel not in ds["tep"] and duoc_thay(rel) and os.path.exists(os.path.join(SKILL, rel))]
        for rel in bo:
            os.remove(os.path.join(SKILL, rel))
        # 4) skill tải video đi kèm (nếu có)
        tv = os.path.join(td, "tai-video-kenh")
        if os.path.isdir(tv):
            dich = os.path.join(os.path.dirname(SKILL), "tai-video-kenh")
            shutil.copytree(tv, dich, dirs_exist_ok=True)
    n_cu = don_ban_cu(giu=1)                             # 1.2.21: chỉ giữ bản sao mới nhất trong .ban-cu/
    print(f"ĐÃ CẬP NHẬT lên {moi_v}: thay {thay} file, gỡ {len(bo)} file cũ. Bản trước lưu ở {sl}" + (f" (đã xoá {n_cu} bản sao cũ hơn)" if n_cu else ""))
    print("Hồ sơ, bài tự học, cấu hình máy: giữ nguyên. Nếu bản mới cần gói Python mới: chạy lại scripts/cai_dat.py")
    return 0


def lui():
    if not os.path.isdir(CU) or not os.listdir(CU):
        sys.exit("Chưa có bản sao nào để quay lại.")
    sl = os.path.join(CU, sorted(os.listdir(CU), key=_khoa_ban_cu)[-1])      # R1: cùng thứ tự với don_ban_cu (số phiên bản, không phải chuỗi)
    p_moi = os.path.join(SKILL, "TEP-GOI.json")
    moi = json.load(open(p_moi))["tep"] if os.path.exists(p_moi) else {}     # đọc TRƯỚC khi chép đè bằng bản cũ
    for r, _, fs in os.walk(sl):
        for f in fs:
            rel = os.path.relpath(os.path.join(r, f), sl)
            d = os.path.join(SKILL, rel)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(os.path.join(r, f), d)
    # file chỉ có ở bản mới (không có trong bản sao) thì gỡ
    for rel in moi:
        if duoc_thay(rel) and not os.path.exists(os.path.join(sl, rel)) and os.path.exists(os.path.join(SKILL, rel)):
            os.remove(os.path.join(SKILL, rel))
    shutil.rmtree(sl)
    print(f"Đã quay về bản {hien_tai()}.")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] == "kiem":
        kiem("--im-lang" in a)
    elif a[0] == "cai":
        sys.exit(cai(a[1] if len(a) > 1 and not a[1].startswith("--") else None))
    elif a[0] == "lui":
        lui()
