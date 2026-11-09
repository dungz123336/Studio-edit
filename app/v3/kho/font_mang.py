# -*- coding: utf-8 -*-
"""Tải font theo TÊN HỌ từ Google Fonts (giấy phép mở OFL/Apache) vào kho-them/google-fonts của dữ liệu Studio rồi lập chỉ mục
CHỈ các tệp vừa tải (lap.lap_tep → upsert csdl; 1.2.21 — trước: lập lại cả kho giữa lúc dựng).
Máy chỉ là chân tay: AI/người dùng gọi tên họ (vd "Montserrat", "Playfair Display"), máy mang về đủ độ đậm/nghiêng và trả id kho.

  tai(ho, dam=None, nghieng=None, log=print) → [đường dẫn .ttf]   (dam: [300, 800] hoặc None = cả dải; nghieng: None=cả hai)
  co_mang() → bool
  python v3/kho/font_mang.py "Montserrat" [--dam 300,800] [--nghieng]
"""
import os, re, sys, json, time, socket, urllib.request, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung

UA = "curl/8.0"          # UA cũ → Google trả TTF TRỌN (không woff2, không cắt subset unicode-range) — cần để đủ dấu Việt
GOC = os.path.join(chung.duong("du_lieu"), "kho-them", "google-fonts")
_DAM_MAC = [100, 200, 300, 400, 500, 600, 700, 800, 900]


def co_mang(timeout=2.0):
    try:
        socket.create_connection(("fonts.googleapis.com", 443), timeout=timeout).close()
        return True
    except OSError:
        return False


def _css(ho, dam, nghieng):
    """CSS @font-face từ API css2; thử dải biến thiên trước, rồi danh sách tĩnh (API trả 400 nếu họ không có độ đậm đó)."""
    ten = urllib.parse.quote(ho.strip())
    ital = [0, 1] if nghieng is None else ([1] if nghieng else [0])
    thu = []
    if dam is not None:
        thu.append("ital,wght@" + ";".join(f"{i},{w}" for i in ital for w in dam))
    for bo in (_DAM_MAC, [300, 400, 500, 600, 700, 800, 900], [400, 500, 600, 700, 800, 900], [400, 700, 900], [400, 700], [700], [400]):
        thu.append("ital,wght@" + ";".join(f"{i},{w}" for i in ital for w in bo))
    thu.append("ital@" + ";".join(str(i) for i in ital))
    thu.append("")
    for axis in thu:
        url = f"https://fonts.googleapis.com/css2?family={ten}" + (":" + axis if axis else "")
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=15)
            return r.read().decode("utf-8", "replace")
        except Exception:
            continue
    return ""


def _khoi(css):
    """→ [{style, weight, url}] từ các khối @font-face (chỉ lấy latin / latin-ext hoặc khối không ghi subset)"""
    ra = []
    for khoi in re.findall(r"(/\*\s*([\w-]+)\s*\*/\s*)?@font-face\s*\{(.*?)\}", css, re.S):
        subset, than = khoi[1], khoi[2]
        if subset and subset not in ("latin", "latin-ext", "vietnamese"):
            continue
        st = re.search(r"font-style:\s*(\w+)", than); wt = re.search(r"font-weight:\s*([\d ]+)", than); u = re.search(r"url\(([^)]+)\)", than)
        if not u:
            continue
        ra.append({"style": st.group(1) if st else "normal", "weight": (wt.group(1).strip() if wt else "400").replace(" ", "-"), "url": u.group(1).strip("'\""), "subset": subset or ""})
    # cùng style+weight: ưu tiên vietnamese > latin-ext > latin (đủ dấu)
    uu = {"vietnamese": 0, "latin-ext": 1, "latin": 2, "": 3}
    tot = {}
    for k in ra:
        kk = (k["style"], k["weight"])
        if kk not in tot or uu.get(k["subset"], 9) < uu.get(tot[kk]["subset"], 9):
            tot[kk] = k
    return list(tot.values())


def tai(ho, dam=None, nghieng=None, log=print, lap_chi_muc=True):
    ho = re.sub(r"\s+", " ", str(ho or "")).strip()
    if not ho or not co_mang():
        return []
    css = _css(ho, dam, nghieng)
    ds = _khoi(css)
    if not ds:
        log(f"  Google Fonts: không có họ `{ho}`")
        return []
    thu = os.path.join(GOC, re.sub(r"[^A-Za-z0-9]+", "", ho) or "font")
    os.makedirs(thu, exist_ok=True)
    ra = []
    for k in ds:
        ten = f"{re.sub(r'[^A-Za-z0-9]+', '', ho)}-{k['weight']}{'-Italic' if k['style'] == 'italic' else ''}.ttf"
        p = os.path.join(thu, ten)
        if not (os.path.isfile(p) and os.path.getsize(p) > 1000):
            try:
                d = urllib.request.urlopen(urllib.request.Request(k["url"], headers={"User-Agent": UA}), timeout=30).read()
                if len(d) < 1000:
                    continue
                open(p, "wb").write(d)
            except Exception as ex:
                log(f"  Google Fonts: lỗi tải {ten}: {ex}")
                continue
        ra.append(p)
    if ra:
        bien_thien = any("-" in k["weight"] for k in ds)
        log(f"  Google Fonts: {ho} → {len(ra)} tệp ({'biến thiên' if bien_thien else 'tĩnh'}) vào {thu}")
        if lap_chi_muc:
            try:
                from kho import lap as _lap
                ds_muc = _lap.lap_tep(ra, "google", GOC, xem_truoc_nhanh=False)
                log(f"  Kho: thêm {len(ds_muc)} mục font vào csdl (không lập lại cả kho)")
            except Exception as ex:
                log(f"  (lập chỉ mục font vừa tải lỗi: {ex})")
    return ra


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("ho"); ap.add_argument("--dam"); ap.add_argument("--nghieng", action="store_true")
    a = ap.parse_args()
    dam = [int(x) for x in a.dam.split(",")] if a.dam else None
    for p in tai(a.ho, dam, True if a.nghieng else None):
        print(p)
