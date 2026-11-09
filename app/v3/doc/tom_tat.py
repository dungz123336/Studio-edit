# -*- coding: utf-8 -*-
"""Tóm tắt dự án cho AI (≤ GIOI_HAN ký tự, lời ≥ LOI_TOI_THIEU) → doc/tom-tat.md: lời theo cụm với giây thành phẩm, thống kê, mặt + vùng trống,
cảnh, màu, nguồn phụ, từ khoá, hồ sơ, QUYẾT ĐỊNH KÊNH (quyet-dinh.json rút gọn đủ trường — hoặc dòng "KÊNH CHƯA CÓ QUYẾT ĐỊNH" + khuôn),
"Máy: …" (doc/nguon.json["may"], cờ hdr), KHO CHO VIDEO NÀY (bảng tài nguyên máy đo từ kho/goi_video.py + ảnh doc/kho-video.jpg).
Không áp phong cách, không gợi ý thủ pháp, không đoán cảm xúc nhạc; ngữ pháp bài học rút gọn ≤ 6 công thức × ≤ 300 ký tự (cache
HS/hoc/<ma>.json["ngu_phap_gon"])."""
import json, glob, os, sys, re, json
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung
from doc import cat as _cat

GIOI_HAN = 13000             # 1.2.21: + quyết định kênh (≤ ~2.600) + bảng kho; lời cắt cụm để vừa
LOI_TOI_THIEU = 3500         # R2: phần LỜI luôn được ít nhất chừng này (khuôn quyết định ~6.400 ký tự từng đẩy lời về 0 cụm)
GIOI_HAN_KHO = 3400          # 1.2.19: thêm chữ ký tiếng + số lần đã dùng
GIOI_HAN_HO_SO = 1600
NGU_PHAP_SO_CONG_THUC = 6    # 1.2.21: ngữ pháp bài học rút gọn
NGU_PHAP_DAI_DONG = 300
STOP = set("""và là của có không được một những các cho với này đó thì mà để từ ở trong ra vào lên xuống về khi nếu
cũng đã sẽ đang rất nhiều ít hơn nhất như vậy thế nào gì ai đâu bao nhiêu mình tôi bạn chúng ta anh chị em họ nó
cái con người việc điều lúc nơi tại bởi vì nên do nhưng hoặc hay còn lại đi đến làm nói biết thấy xem muốn cần
phải đây kia ấy đấy đó rồi nữa thôi à ờ ừm ừ ạ nhé nhỉ nha hả vâng dạ ok okay thật sự rằng là bị bằng theo sau
trước trên dưới giữa ngoài ngay luôn chỉ mỗi hết cả toàn đều hãy đừng chớ tất cả mọi vài một số vừa mới lần thể đưa nào này nọ
hôm nay mai qua năm tháng ngày giờ phút giây lắm quá cực kỳ thực ra kiểu như thế là thì sẽ bạn ơi các bạn""".split())

def _cum_loi(tu, giu, f_tp, toi_da=12, toi_thieu=6):
    """từ → cụm 6–12 từ (ngắt theo dấu câu/khoảng nghỉ), bỏ từ trong vùng cắt, giây thành phẩm"""
    def duoc_giu(t):
        return any(g["a"] - 0.02 <= t["a"] and t["b"] <= g["b"] + 0.02 for g in giu) if giu else True
    ws = [t for t in tu if duoc_giu(t)]
    cum, hien = [], []
    for i, t in enumerate(ws):
        hien.append(t)
        ket = bool(re.search(r"[.!?…]$", t["w"]))
        nghi = i + 1 < len(ws) and ws[i + 1]["a"] - t["b"] > 0.5
        if len(hien) >= toi_da or ((ket or nghi) and len(hien) >= toi_thieu) or i == len(ws) - 1:
            cum.append(hien)
            hien = []
    ra = []
    for c in cum:
        a, b = f_tp(c[0]["a"]), f_tp(c[-1]["b"])
        ra.append(f"[{a:.1f}–{b:.1f}] " + " ".join(t["w"] for t in c))
    return ra


_SO = re.compile(r"\d|\b(một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|trăm|nghìn|ngàn|triệu|tỷ|phần trăm|%|nửa|đôi|vài|chục)\b", re.I)
_LIET_KE = re.compile(r"\b(thứ (nhất|hai|ba|tư|năm)|(một|hai|ba|bốn) là|đầu tiên|tiếp theo|tiếp đến|sau đó|cuối cùng|bước \d|cách \d|điều \d|gồm|bao gồm|như là|chẳng hạn|ví dụ)\b", re.I)
_SO_SANH = re.compile(r"\b(hơn|kém|so với|thay vì|khác với|giống như|ngang|trước đây|bây giờ|ngày xưa|hồi trước|thật ra|thực ra)\b", re.I)
_HOI = re.compile(r"\?|\b(có phải|đúng không|phải không|tại sao|vì sao|làm sao|làm thế nào|như thế nào|bao nhiêu|có biết|bạn có)\b", re.I)
_NHAN = re.compile(r"\b(rất|cực|cực kỳ|hoàn toàn|chỉ cần|duy nhất|quan trọng|nhớ|lưu ý|chú ý|tuyệt đối|không bao giờ|luôn luôn|bí quyết|sự thật|bất ngờ|miễn phí|ngay|lập tức)\b", re.I)
_KEU_GOI = re.compile(r"\b(bình luận|comment|theo dõi|follow|lưu lại|save|chia sẻ|share|nhắn|inbox|đăng ký|link|bấm|nhấn|tải|mua|đặt|liên hệ|gọi)\b", re.I)
_CHUYEN_Y = re.compile(r"^\s*(vậy|vậy thì|tóm lại|còn|nhưng|tuy nhiên|thế nên|cho nên|do đó|ngoài ra|bên cạnh đó|và cuối cùng|ok|okay|rồi)\b", re.I)


def _dau_hieu_cau(loi, f_tp, gioi_han=1300):
    """DẤU HIỆU TRONG LỜI — máy đánh dấu từng câu (số, liệt kê, so sánh, hỏi, nhấn, kêu gọi, chuyển ý, tên riêng, nhanh/chậm, nghỉ sau).
    Chỉ là dữ liệu để AI tự quyết chỗ nào cần gì; không kèm lời khuyên."""
    cau = loi.get("cau") or []
    tu = loi.get("tu") or []
    if not cau:
        return []
    tocs = []
    for c in cau:
        n = len(c["txt"].split()); d = max(0.2, c["b"] - c["a"])
        tocs.append(n / d)
    tb = sorted(tocs)[len(tocs) // 2] if tocs else 0
    dong = ["## Dấu hiệu trong lời (máy đánh dấu từng câu — dữ liệu, AI tự quyết dùng gì)"]
    n_tag = 0
    for i, c in enumerate(cau):
        t = c["txt"]
        tags = []
        if _SO.search(t):
            tags.append("số")
        if _LIET_KE.search(t):
            tags.append("liệt kê")
        if _SO_SANH.search(t):
            tags.append("so sánh")
        if _HOI.search(t):
            tags.append("hỏi")
        if _NHAN.search(t):
            tags.append("nhấn")
        if _KEU_GOI.search(t):
            tags.append("kêu gọi")
        if _CHUYEN_Y.search(t):
            tags.append("chuyển ý")
        rieng = [w for w in re.findall(r"\b\w[\w\-]{1,}\b", t[1:]) if w[0].isupper() and w.lower() not in ("tôi", "mình", "bạn", "anh", "em", "chị")]
        rieng = [w for w in rieng if not w.isupper() or len(w) <= 6]
        if rieng:
            tags.append("tên: " + ", ".join(dict.fromkeys(rieng))[:40])
        if tb and tocs[i] > 1.3 * tb:
            tags.append("nói nhanh")
        elif tb and tocs[i] < 0.7 * tb:
            tags.append("nói chậm")
        if i + 1 < len(cau):
            nghi = cau[i + 1]["a"] - c["b"]
            if nghi >= 0.6:
                tags.append(f"nghỉ {nghi:.1f}s sau")
        if not tags:
            continue
        n_tag += 1
        a, b = f_tp(c["a"]), f_tp(c["b"])
        dong.append(f"- [{a:.1f}–{b:.1f}] {' · '.join(tags)} — “{t[:70]}{'…' if len(t) > 70 else ''}”")
        if sum(len(x) + 1 for x in dong) > gioi_han:
            dong.append(f"… (còn {len(cau) - i - 1} câu; đủ trong doc/loi.json)")
            break
    return dong if n_tag else []


def _tu_khoa(tu, n=8):
    dem = Counter()
    ws = [chung.NFC(re.sub(r"[\W_]+", "", t["w"]).lower()) for t in tu]
    ws = [w for w in ws if w and w not in STOP and len(w) > 1 and not w.isdigit()]
    for w in ws:
        dem[w] += 1
    cum = Counter()
    for a, b in zip(ws, ws[1:]):   # cụm 2 từ hay gặp (tiếng Việt đa âm tiết)
        cum[a + " " + b] += 1
    chon = [c for c, k in cum.most_common(n) if k >= 2]
    da = set(w for c in chon for w in c.split())
    for w, _ in dem.most_common(n * 2):
        if len(chon) >= n:
            break
        if w not in da:
            chon.append(w)
    return chon[:n]


def _vung_trong(mt, W, H):
    """mặt trung bình (0..1) → vùng trống trên/dưới/trái/phải mặt trong vùng an toàn"""
    v = chung.vung_an_toan(W, H)
    tren_mat, duoi_cam = mt["y"] - mt["h"] / 2, mt["y"] + mt["h"] / 2
    trai_mat, phai_mat = mt["x"] - mt["w"] / 2, mt["x"] + mt["w"] / 2
    vung = {
        "trên mặt": (v["tren"], tren_mat - 0.02),
        "dưới cằm": (duoi_cam + 0.02, 1 - v["duoi"]),
        "trái mặt": (v["trai"], trai_mat - 0.02),
        "phải mặt": (phai_mat + 0.02, 1 - v["phai"]),
    }
    dong = []
    for ten, (a, b) in vung.items():
        if b - a > 0.04:
            dong.append(f"{ten}: {a:.2f}–{b:.2f} ({(b - a) * 100:.0f}% {'cao' if ten.startswith(('trên', 'dưới')) else 'rộng'})")
    tot = max(vung.items(), key=lambda kv: kv[1][1] - kv[1][0])
    return dong, tot[0]


def _ho_so(ten):
    if not ten:
        return None
    tm = os.path.join(chung.duong("ho_so"), ten)
    hs = chung.doc_json(os.path.join(tm, "ho-so.json"))
    if not hs:
        return None
    gon = {k: hs[k] for k in ("ten", "mau_khoa", "font_khoa", "luat_gu", "gu", "ghi_chu") if k in hs}
    gy = chung.doc_json(os.path.join(tm, "gop-y.json"), []) or hs.get("gop_y") or []
    if gy:
        gon["gop_y_gan_nhat"] = gy[-5:]
    ss = chung.doc_json(os.path.join(tm, "style-spec.json"))
    if ss:
        ss = {k: v for k, v in ss.items() if not k.startswith("_") or k == "_nguon"}
        gon["style_spec"] = ss
        if (ss.get("_nguon") or {}).get("loai") == "video_dau_tien":
            gon["ban_sac"] = "NHÁP từ video đầu tiên của kênh — giữ nhất quán (màu, font, cách chữ hiện, nhịp) trừ khi yêu cầu/góp ý đổi"
    bai = []                                        # tab Học: bài Style Spec đang BẬT (bài kiểu cũ — id lớp lõi cũ — bỏ qua)
    for f in sorted(glob.glob(os.path.join(tm, "hoc", "*.json")), key=os.path.getmtime, reverse=True):
        c = chung.doc_json(f, {}) or {}
        if c.get("bat", True) and c.get("style_spec"):
            bai.append({"ten": c.get("ten"), "da_hoc": c.get("da_hoc"), "cau_truc": c.get("cau_truc"), "hop_noi_dung": c.get("hop_noi_dung"),
                        "dong_thoi_gian": c.get("dong_thoi_gian"), "style_spec": c["style_spec"], "ngu_phap_doc": c.get("ngu_phap_doc"),
                        "ngu_phap_gon": c.get("ngu_phap_gon"), "doi_chieu": c.get("doi_chieu"), "_tep": f})
    if bai:
        gon["bai_hoc_dang_bat"] = bai[:3]
    return gon


def _ban_sac_doc_duoc(ss):
    """Style Spec → các dòng ngắn đọc được (AI không phải đoán JSON bị cắt)"""
    if not isinstance(ss, dict):
        return []
    D = []
    pal = ss.get("palette") or {}
    if pal:
        D.append("- Màu: nhấn " + str(pal.get("nhan")) + (f" · nhấn 2 {pal.get('nhan2')}" if pal.get("nhan2") else "") + f" · sáng {pal.get('sang')} · tối {pal.get('toi')}")
    ts = ss.get("type_scale") or {}
    if ts:
        co = "; ".join(f"{k} {v.get('co')}px đậm {v.get('dam')}{' HOA' if v.get('hoa') else ''}" for k, v in ts.items() if isinstance(v, dict) and v.get("co"))
        D.append("- Chữ: " + (co or "") + (f" · nhóm font {', '.join(ts['nhom_font'])}" if ts.get("nhom_font") else "") + (f" · {ts['so_font_khac_nhau']} font" if ts.get("so_font_khac_nhau") else ""))
    mv = ss.get("motion_vocab") or {}
    if mv:
        vao = ", ".join(f"{x.get('kieu')} {x.get('dai', '')}s" for x in (mv.get("vao") or [])[:3])
        D.append(f"- Chữ hiện: vào {vao or '?'} · tách {mv.get('tach', '?')} · nhịp động {mv.get('nhip_dong', '?')}")
    la = (ss.get("layout") or {}).get("anchors") or []
    if la:
        D.append("- Vị trí quen: " + "; ".join(f"{a.get('vai')} {a.get('anchor')} ({a.get('x')},{a.get('y')})" for a in la[:5]))
    rr = ss.get("rhythm_rules") or {}
    if rr:
        D.append("- Phụ đề/nhịp: " + ", ".join(f"{k} {v}" for k, v in rr.items()))
    am = ss.get("am_nhac") or {}
    if am:
        D.append(f"- Nhạc: {'có' if am.get('co') else 'không'} · mức {am.get('muc', '?')}" + (f" · {am.get('nghia')}" if am.get("nghia") else ""))
    ct = ss.get("cat") or {}
    if ct:
        D.append(f"- Cắt: nhịp {ct.get('nhip', 'vua')}")
    dh = ss.get("do_hoa") or {}
    gv = ss.get("graphics_vocab") or {}
    if dh or gv:
        D.append("- ĐỒ HOẠ (sở thích kênh): mức " + str(dh.get("muc") or "chưa đặt")
                 + (f" · thích: {', '.join(dh['thich'])}" if dh.get("thich") else "")
                 + (f" · tránh: {', '.join(dh['tranh'])}" if dh.get("tranh") else "")
                 + (f" · minh hoạ {gv.get('hinh_minh_hoa')}" if gv.get("hinh_minh_hoa") else "")
                 + (f" · nền mới {gv.get('nen_moi')}" if gv.get("nen_moi") else "")
                 + (f" · thẻ {(gv.get('the') or {}).get('hinh')}{' có icon' if (gv.get('the') or {}).get('co_icon') else ''}" if gv.get("the") else ""))
    bia = ss.get("bia") or {}
    if bia:
        D.append("- Bìa quen: " + ", ".join(f"{k} {v}" for k, v in bia.items()))
    if ss.get("ghi_chu"):
        D.append("- Ghi chú: " + str(ss["ghi_chu"])[:400])
    return D


def _kho_so_do():
    """kho có gì (số đo, không câu tra cố định): số mục theo loại; AI tự viết nghĩa/tính chất khi tra"""
    try:
        from kho import tim as kt
    except Exception:
        return ["(kho chưa lập chỉ mục / chưa có kho.tim)"]
    dem = {}
    try:
        kt._nap()
        for m in (kt._bo or {}).get("muc") or []:
            dem[m.get("loai") or "khac"] = dem.get(m.get("loai") or "khac", 0) + 1
    except Exception:
        try:
            for loai in ("nhac", "sfx", "font", "icon", "nen", "video", "anh", "lut"):
                dem[loai] = len(kt.tim(loai, "", n=500) or [])
        except Exception as ex:
            return [f"(kho lỗi: {str(ex)[:80]})"]
    if not dem:
        return ["(kho rỗng — mọi tra kho sẽ bị bỏ qua, cảnh báo kho_khong_co_<loai>)"]
    return ["- Kho trên máy: " + ", ".join(f"{k} {v}" for k, v in sorted(dem.items(), key=lambda kv: -kv[1]))
            + " — tra theo nghĩa/tính chất tiếng → máy trả top-5 kèm số đo; loại nào = 0 thì đừng dùng loại đó"]


def _ngu_phap_gon(bai, p_bai, so=NGU_PHAP_SO_CONG_THUC, dai=NGU_PHAP_DAI_DONG):
    """ngữ pháp bài học rút gọn: ≤ so công thức (theo số lần xuất hiện), mỗi dòng ≤ dai ký tự, kèm khung JSON của công thức đầu;
    cache vào HS/hoc/<ma>.json["ngu_phap_gon"] (khoá theo băm ngu_phap_doc), không đổi mtime tệp bài"""
    npd = bai.get("ngu_phap_doc") or []
    if not npd:
        return []
    khoa = chung.bam(npd)
    c = bai.get("ngu_phap_gon")
    if isinstance(c, dict) and c.get("khoa") == khoa and isinstance(c.get("dong"), list):
        return c["dong"]
    dong, n_ct = [], 0
    for x in npd:
        x = str(x)
        if x.startswith("- "):
            if n_ct >= so:
                break
            n_ct += 1
            dong.append(_cat_ngan(x, dai))
        elif x.strip().startswith("khung JSON:") and n_ct == 1 and not any(d.startswith("    khung JSON") for d in dong):
            dong.append("    " + _cat_ngan(x.strip(), dai))
        elif x.startswith("    ·") and n_ct and n_ct <= so:
            dong.append(_cat_ngan(x, dai))
        elif x.startswith("ĐẶT SO VỚI MẶT"):
            dong.append(_cat_ngan(x, dai))
    tong = sum(1 for x in npd if str(x).startswith("- "))
    if tong > n_ct:
        dong.append(f"    (+{tong - n_ct} công thức khác, đủ trong {os.path.basename(p_bai) if p_bai else 'bài học'})")
    if p_bai and os.path.isfile(p_bai):
        try:
            mt = os.path.getmtime(p_bai)
            b2 = chung.doc_json(p_bai, {}) or {}
            b2["ngu_phap_gon"] = {"khoa": khoa, "dong": dong}
            chung.ghi_json(p_bai, b2)
            os.utime(p_bai, (mt, mt))
        except Exception:
            pass
    return dong


def _quyet_dinh_kenh(du_an, ho_so_id):
    """QUYẾT ĐỊNH KÊNH: bản rút gọn đủ mọi trường, hoặc dòng KÊNH CHƯA CÓ QUYẾT ĐỊNH + khuôn tối thiểu"""
    try:
        from ai import hop_dong as H
    except Exception as ex:
        return [f"(không nạp được ai.hop_dong: {ex})"]
    qd, nguon, loi = H.doc_quyet_dinh(du_an, ho_so_id, luu=False)
    if qd is None and not loi:
        try:
            viec = chung.doc_json(os.path.join(du_an, "viec.json"), {}) or {}
            if viec.get("goi"):
                from phong_cach import ap as _ap
                qd = _ap.quyet_dinh_cho(viec["goi"]); nguon = "goi:" + str(viec["goi"]) if qd else None
        except Exception:
            pass
    D = []
    if qd:
        D.append(f"## QUYẾT ĐỊNH KÊNH (nguồn: {nguon}; phiên {qd.get('phien')}) — mặc định cho MỌI trường công thức bỏ trống; trường ghi trong công thức thắng"
                 + (f"; lý do: {_cat_ngan(qd.get('ly_do'), 200)}" if qd.get("ly_do") else ""))
        D += H.quyet_dinh_gon(qd)
        D.append("Muốn đổi quyết định kênh (người dùng yêu cầu): Write `" + os.path.join(du_an, "quyet-dinh-kenh.json") + "` bản mới đủ trường (máy kiểm khuôn, lưu lịch sử).")
    elif loi:
        D.append("## QUYẾT ĐỊNH KÊNH SAI KHUÔN — sửa rồi Write lại `" + os.path.join(du_an, "quyet-dinh-kenh.json") + "`:")
        D += [f"- {l.get('duong')}: {l.get('goi_y')}" for l in loi[:20]]
        D.append(H.khuon_gon_md())                    # R2: khuôn gọn ≤ ~3k (đầy đủ: từ điển / hop_dong.py khuon)
    else:
        D.append("## KÊNH CHƯA CÓ QUYẾT ĐỊNH — Write `" + os.path.join(du_an, "quyet-dinh-kenh.json") + "` theo khuôn dưới đây TRƯỚC khi viết công thức "
                 "(máy không có số thẩm mỹ riêng: trường công thức bỏ trống mà không có quyết định → lỗi thieu_truong). Số là lựa chọn của bạn cho kênh này.")
        D.append(H.khuon_gon_md())                    # R2: khuôn gọn ≤ ~3k (đầy đủ: từ điển / hop_dong.py khuon)
    return D


def _may(nguon):
    """dòng "Máy: …" từ doc/nguon.json["may"] (A1 ghi: proxy, model nghe, mã hoá…) + cờ hdr"""
    may = nguon.get("may") if isinstance(nguon, dict) else None
    hdr = bool(nguon.get("hdr")) if isinstance(nguon, dict) else False
    hdr = hdr or (any(((n.get("ffprobe") or {}).get("hdr") or n.get("hdr")) for n in (nguon.get("nguon") or []) if isinstance(n, dict)) if isinstance(nguon, dict) else False)
    hdr = hdr or (bool((nguon.get("chinh") or {}).get("hdr")) if isinstance(nguon, dict) else False)
    D = []
    if isinstance(may, dict) and may.get("mo_ta"):
        D.append(str(may["mo_ta"]) if str(may["mo_ta"]).startswith("Máy") else "Máy: " + str(may["mo_ta"]))
    elif may:
        D.append("Máy: " + (may if isinstance(may, str) else "; ".join(f"{k} {v}" for k, v in may.items() if k != "mo_ta")))
    if hdr:
        D.append("Nguồn HDR (HLG/PQ/bt2020) → máy đã chuyển SDR bt709 khi đọc; màu đo trong canh.json là sau chuyển.")
    return D


def _cat_ngan(s, n):
    """cắt ở ranh giới từ"""
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    if len(s) <= n:
        return s
    c = s[:n].rsplit(" ", 1)[0] if " " in s[:n] else s[:n]
    return c.rstrip(" ,.;:-–") + "…"


TEN_NHOM_SFX = {"it_dung": "ít dùng", "bat_kho": "bật ngay · khô", "bat_ngan": "bật ngay · ngân", "dang": "dâng dần", "cao": "cao", "tram": "trầm",
                "chuoi": "chuỗi", "nhieu": "nhiễu/gió", "ngan": "ngắn", "dai": "dài"}


def _kho_video(du_an, gioi_han=GIOI_HAN_KHO):
    """mục KHO CHO VIDEO NÀY (≤ gioi_han ký tự) từ doc/kho-video.json (kho/goi_video.goi — BẢNG SỐ ĐO, máy không chọn hộ):
    `kho` = có gì/bao nhiêu; `sfx` = dict theo CHỮ KÝ vật lý; nhac/icon/nen/lut = list; font = {so, du_dau, bang[], font_khoa_ho_so}.
    Chỉ in số đo; đủ bảng ở doc/kho-video.json."""
    try:
        from kho import goi_video
        g = goi_video.goi(du_an)
    except Exception as ex:
        return None, f"(bảng kho lỗi: {type(ex).__name__}: {str(ex)[:80]})"
    anh = os.path.join(du_an, g["anh"]).replace("\\", "/") if g.get("anh") else None
    kho = g.get("kho") or {}

    def them(ds, k):
        return f" (+{len(ds) - k} trong json)" if len(ds) > k else ""

    def muc(x, mo, co_dur=True):
        ck = (" · " + x["chu_ky"]) if x.get("chu_ky") else ""
        dd = f" · dùng {x['da_dung']}" if x.get("da_dung") else ""
        return f"{x['id']} ({_cat_ngan(x.get('mo_ta'), mo)}{ck}{dd})"

    def dung(k_nhac, k_sfx, k_icon, k_nen, mo, mo_sfx):
        D = [f"## KHO CHO VIDEO NÀY — bảng số đo, máy không chọn hộ (đủ: doc/kho-video.json; {g.get('tong')} mục trong bảng)"]
        if anh:
            D.append(f"Ảnh xem nhanh icon/nền/font (Read 1 ảnh): {anh}")
        if kho.get("theo_loai"):
            D.append("Kho có: " + ", ".join(f"{k} {v}" for k, v in sorted(kho["theo_loai"].items(), key=lambda kv: -kv[1]) if k != "khac")
                     + (f" · font đủ dấu {kho.get('font_du_dau')}" if kho.get("font_du_dau") is not None else "")
                     + (f" · chưa gán nghĩa {kho.get('chua_gan_nghia')}" if kho.get("chua_gan_nghia") else "") + " — loại = 0 thì đừng dùng loại đó")
        if isinstance(kho.get("cong_dung"), dict) and kho["cong_dung"].get("sfx"):
            D.append("Nhãn công dụng sfx phổ biến (số mục): " + ", ".join(f"{a} {n}" for a, n in kho["cong_dung"]["sfx"][:8]))
        if g.get("nhac"):
            D.append(f"Nhạc (video {g.get('dur')}s; id · mô tả · BPM/LUFS/dài){them(g['nhac'], k_nhac)}:")
            D += [f"- {muc(x, mo)}" for x in g["nhac"][:k_nhac]]
        sx = g.get("sfx") if isinstance(g.get("sfx"), dict) else {}
        if sx:
            D.append("SFX theo CHỮ KÝ vật lý (ghi id, hoặc TÊN NHÓM = khoá dưới đây, hoặc tính chất tiếng):")
            for k, ds in sx.items():
                if not ds:
                    continue
                D.append(f"- {k} ({TEN_NHOM_SFX.get(k, k)}): " + " · ".join(muc(x, mo_sfx) for x in ds[:k_sfx]) + them(ds, k_sfx))
        if g.get("icon"):
            D.append(f"Icon{them(g['icon'], k_icon)}: " + " · ".join(muc(x, mo) for x in g["icon"][:k_icon]))
        if g.get("nen"):
            D.append(f"Nền / lớp phủ{them(g['nen'], k_nen)}: " + " · ".join(muc(x, mo) for x in g["nen"][:k_nen]))
        f = g.get("font") or {}
        if f:
            D.append(f"Font: {f.get('so')} tệp, đủ dấu {f.get('du_dau')}" + (" · hồ sơ khoá: " + _cat_ngan(json.dumps(f["font_khoa_ho_so"], ensure_ascii=False), 100) if f.get("font_khoa_ho_so") else ""))
            for bg in (f.get("bang") or [])[:3]:
                ms = bg.get("muc") or []
                D.append(f"- {bg.get('mo_ta') or bg.get('theo')} ({bg.get('so_hop')}): " + " · ".join(f"{m['id']} ({m.get('chu_ky', '')})" for m in ms[:4]) + them(ms, 4))
        if g.get("lut"):
            D.append("LUT (CHỈ khi người dùng cho chỉnh màu): " + " · ".join(x["id"] for x in g["lut"][:6]))
        if g.get("huong_dan"):
            D.append(_cat_ngan(g["huong_dan"], 300))
        try:                                                     # hồ sơ này đã dùng mẫu/tài nguyên nào bao nhiêu lần (30 video gần nhất) — số đếm
            from kho import lich_su as _ls
            viec_ = chung.doc_json(os.path.join(du_an, "viec.json"), {}) or {}
            gd = _ls.gan_day(viec_.get("ho_so") or "", 30, bo=os.path.basename(du_an))
            mau_ = sorted(((v, k) for k, v in gd.items() if k.startswith("mau.")), reverse=True)[:8]
            tn_ = sorted(((v, k) for k, v in gd.items() if k.split(".")[0] in ("sfx", "nhac", "font", "nen")), reverse=True)[:8]
            if mau_ or tn_:
                D.append("Hồ sơ này đã dùng (số video trong 30 video gần nhất — số đếm): " + ", ".join(f"{k} {v}" for v, k in mau_ + tn_))
        except Exception:
            pass
        return "\n".join(D)
    txt = ""
    for cau_hinh in ((5, 4, 8, 6, 40, 22), (4, 3, 8, 5, 34, 20), (3, 3, 6, 4, 30, 18), (3, 2, 6, 4, 26, 18),
                     (2, 2, 5, 3, 24, 16), (2, 2, 4, 3, 22, 14), (2, 1, 4, 3, 20, 14), (1, 1, 3, 2, 18, 12)):
        txt = dung(*cau_hinh)
        if len(txt) <= gioi_han:
            return g, txt
    dong = txt.split("\n")                 # vẫn dài: cắt dòng cuối, ghi chú
    while len("\n".join(dong)) > gioi_han - 60 and len(dong) > 5:
        dong.pop()
    return g, "\n".join(dong) + "\n… (còn mục trong doc/kho-video.json)"


def viet(du_an):
    """→ đường doc/tom-tat.md"""
    d = os.path.join(du_an, "doc")
    viec = chung.doc_json(os.path.join(du_an, "viec.json"), {}) or {}
    nguon = chung.doc_json(os.path.join(d, "nguon.json"), {}) or {}
    loi = chung.doc_json(os.path.join(d, "loi.json"), {}) or {}
    mat = chung.doc_json(os.path.join(d, "mat.json"), {}) or {}
    canh = chung.doc_json(os.path.join(d, "canh.json"), {}) or {}
    catj = chung.doc_json(os.path.join(d, "cat-de-xuat.json"), {}) or {}
    tu, giu = loi.get("tu", []), catj.get("giu", [])
    f_tp, _ = _cat.tao_anh_xa(giu) if giu else (lambda a: round(a, 3), None)
    chinh = next((n for n in nguon.get("nguon", []) if n.get("vai") == "chinh"), (nguon.get("nguon") or [{}])[0])
    fp = chinh.get("ffprobe", {}) or {}
    W, H = fp.get("w") or 1080, fp.get("h") or 1920
    dur_goc = catj.get("dur_goc") or fp.get("dur") or loi.get("dur") or 0
    dur_sau = catj.get("dur_sau") or dur_goc
    so_tu = len(tu)
    noi = sum(c["b"] - c["a"] for c in loi.get("cau", [])) or dur_sau or 1
    toc_do = so_tu / noi * 60 if noi else 0
    tk = _tu_khoa(tu)
    L = []
    L.append(f"# Tóm tắt dự án `{viec.get('ten') or os.path.basename(du_an)}`")
    if viec.get("yeu_cau"):
        L.append(f"Yêu cầu người dùng: {viec['yeu_cau']}")
    L.append(f"Khung {viec.get('khung', [1080, 1920])} · fps {viec.get('fps', 30)} · chế độ {viec.get('che_do', 'ky')} · nguồn chính {W}x{H} {fp.get('fps', 0):.0f}fps")
    L.extend(_may(nguon))
    L.append("")
    L.append("## Thống kê")
    L.append(f"- Thời lượng gốc {dur_goc:.1f}s → sau cắt đề xuất {dur_sau:.1f}s (bỏ {catj.get('thong_ke', {})})")
    L.append(f"- {so_tu} từ, {len(loi.get('cau', []))} câu, tốc độ nói ≈ {toc_do:.0f} từ/phút, {len(loi.get('dem', []))} từ đệm, {len(loi.get('lang', []))} khoảng lặng")
    if not tu:
        L.append("- Không có lời nói (nguồn không tiếng hoặc chỉ nhạc)")
    L.append("")
    L.append("## Mặt và vùng trống (toạ độ 0..1 khung gốc)")
    mt = mat.get("mat_tb")
    if mt:
        L.append(f"- Mặt trung bình: tâm ({mt['x']:.2f}, {mt['y']:.2f}), cỡ {mt['w']:.2f}×{mt['h']:.2f}; có người ở {mat.get('nguoi_ti_le', 0) * 100:.0f}% khung; độ nét TB {mat.get('net_tb', 0):.2f}")
        dong, tot = _vung_trong(mt, W, H)
        for x in dong:
            L.append(f"- Trống {x}")
        L.append(f"- Vùng đặt chữ rộng nhất: {tot}")
    else:
        L.append("- Không thấy mặt")
    L.append("")
    L.append("## Cảnh")
    cs = canh.get("canh", [])
    L.append(f"- {len(cs)} cảnh, {len(canh.get('cat', []))} cắt cảnh tại {canh.get('cat', [])[:12]}")
    for c in cs[:12]:
        L.append(f"  - [{c['a']:.1f}–{c['b']:.1f}] {c['kieu']} · sáng {c['sang']:.2f} · động {c['dong']:.3f}")
    L.append(f"- Màu chủ đạo: {', '.join(canh.get('mau_chu_dao', []))}")
    phu = [n for n in nguon.get("nguon", []) if n.get("vai") == "phu"]
    if phu:
        L.append("")
        L.append("## Nguồn phụ")
        for n in phu:
            f2 = n.get("ffprobe", {})
            L.append(f"- src {n['src']}: {f2.get('dur', 0):.1f}s {f2.get('w')}x{f2.get('h')} {'có tiếng' if f2.get('co_am') else 'không tiếng'} ({os.path.basename(n['duong'])})")
    try:                                                   # khung ứng viên bìa (doc/bia_ung_vien.py)
        from doc import bia_ung_vien as _BUV
        buv = _BUV.dong_tom_tat(d)
        if buv:
            L.append("")
            L.extend(buv)
    except Exception:
        pass
    try:                                                   # mắt B-roll (doc/broll.py): video phụ + thư mục đã quét bằng `nhanh broll`
        from doc import broll as _BR
        br = _BR.dong_tom_tat(d)
        if br:
            L.append("")
            L.extend(br)
    except Exception:
        pass
    L.append("")
    L.append(f"## Từ khoá nội dung: {', '.join(tk) if tk else '(không)'}")
    hs = _ho_so(viec.get("ho_so"))
    L.append("")
    L.append("## Hồ sơ kênh" + (f" — {hs.get('ten')}" if hs and hs.get("ten") else ""))
    if not hs:
        L.append("(không có hồ sơ)")
    else:
        if hs.get("mau_khoa") or hs.get("font_khoa"):
            L.append(f"- KHOÁ: màu {hs.get('mau_khoa')} · font {hs.get('font_khoa')}")
        gu = str(hs.get("gu") or "").strip()
        if gu and "Ghi gu, luật riêng của kênh ở đây" not in gu:
            L.append("- Gu người dùng ghi: " + gu.replace("\n", " ")[:500])
        for g in (hs.get("gop_y_gan_nhat") or [])[-3:]:
            L.append("- Góp ý gần: " + _cat_ngan(g if isinstance(g, str) else (g.get("noi_dung") or g.get("cau") or json.dumps(g, ensure_ascii=False)), 160))
        lg = {k: v for k, v in (hs.get("luat_gu") or {}).items() if isinstance(v, dict) and v.get("bat")}
        if lg:
            L.append("- Luật gu kênh bật: " + ", ".join(f"{k}={v.get('gia_tri')}" for k, v in lg.items()))
        ss = hs.get("style_spec")
        if ss:
            L.append("### Bản sắc kênh" + (" (NHÁP từ video đầu — giữ nhất quán trừ khi yêu cầu/góp ý đổi)" if hs.get("ban_sac") else " (đã học/đã duyệt)"))
            L.extend(_ban_sac_doc_duoc(ss))
        for b in (hs.get("bai_hoc_dang_bat") or [])[:3]:
            L.append(f"### Bài học đang bật: {b.get('ten')}")
            for y in (b.get("da_hoc") or [])[:10]:
                L.append(f"- {str(y)[:420]}")
            if b.get("cau_truc"):
                L.append("- Trình tự của video mẫu: " + " → ".join(str(x)[:160] for x in b["cau_truc"][:8]))
            if b.get("hop_noi_dung"):
                L.append("- Hợp nội dung: " + "; ".join(str(x)[:120] for x in b["hop_noi_dung"][:4]))
            npd = b.get("ngu_phap_doc") or []
            if npd:                                     # NGỮ PHÁP — rút gọn ≤ 6 công thức × ≤ 300 ký tự (đủ trong tệp bài học)
                L.append(f"- NGỮ PHÁP ĐÃ HỌC (rút gọn; đủ ở {b.get('_tep') or 'HS/hoc/<ma>.json'} → ngu_phap_doc; chữ của mẫu KHÔNG dùng; chọn công thức nào cho câu nào là việc của bạn):")
                L.extend("    " + x for x in _ngu_phap_gon(b, b.get("_tep")))
                if b.get("doi_chieu"):
                    L.append(f"    (máy đã dựng lại bản ghi so với gốc: vị trí IoU {b['doi_chieu'].get('vi_tri_iou_tv')}, đúng giờ {b['doi_chieu'].get('dung_gio_ti_le')})")
            dtg = b.get("dong_thoi_gian") or []
            if dtg and not npd:
                L.append("- DÒNG THỜI GIAN MẪU (máy đo từ video mẫu — để thấy nhịp, thứ tự, cái gì hiện lúc nào & ở đâu; áp vào LỜI của video này thế nào là việc của bạn):")
                L.extend("    " + str(x)[:220] for x in dtg[:40])
            ss_b = b.get("style_spec") or {}
            if json.dumps(ss_b.get("type_scale"), sort_keys=True) != json.dumps((ss or {}).get("type_scale"), sort_keys=True):
                L.extend(_ban_sac_doc_duoc(ss_b)[:8])
    L.append("")
    L.extend(_quyet_dinh_kenh(du_an, viec.get("ho_so")))
    L.append("")
    if viec.get("goi"):                                 # PHONG CÁCH NHANH người dùng chọn (/review…) → Style Spec của gói
        try:
            from phong_cach import ap as _ap
            sp = _ap.spec_cho(viec["goi"])
            p_sp = os.path.join(d, "phong-cach-goi.json"); chung.ghi_json(p_sp, sp)
            g_ = sp.get("_goi") or {}
            L.append(f"## Phong cách người dùng chọn: {g_.get('ten') or viec['goi']} — làm THEO Style Spec này (khoá màu/font của hồ sơ vẫn thắng)")
            L.extend(_ban_sac_doc_duoc(sp))                 # R2: dòng đọc được thay JSON cắt ở 1.100 ký tự
            L.append(f"Đủ spec (layout, sfx, bìa, điều không chép): {p_sp}")
            L.append("")
        except Exception as ex:
            L.append(f"(không nạp được phong cách `{viec.get('goi')}`: {ex})"); L.append("")
    g_kho, kho_txt = _kho_video(du_an)
    if g_kho:
        L.append(kho_txt)
    else:
        L.append("## Kho " + kho_txt)
        L.extend(_kho_so_do())
    L.append("")
    try:                                                   # tầng 1/2 khung hình (doc/khung.py — mũi Mắt): chuyển động, cắt cảnh, bảng ảnh
        from doc import khung as _khung
        kt = _khung.tom_tat(du_an)
        if kt:
            L.append(kt.strip()); L.append("")
    except Exception:
        pass
    dh = _dau_hieu_cau(loi, f_tp)
    if dh:
        L.extend(dh); L.append("")
    L.append("## Lời (giây THÀNH PHẨM sau cắt đề xuất)")
    cum = _cum_loi(tu, giu, f_tp)
    dau = "\n".join(L) + "\n"
    con = max(GIOI_HAN - len(dau) - 40, LOI_TOI_THIEU)     # R2: không để lời = 0 cụm khi đầu tóm tắt dài (khuôn quyết định, bài học)
    than = ""
    for i, c in enumerate(cum):
        if len(than) + len(c) + 1 > con:
            than += f"… (còn {len(cum) - i} cụm, xem doc/loi.json)\n"
            break
        than += c + "\n"
    md = dau + than
    p = os.path.join(d, "tom-tat.md")
    os.makedirs(d, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(md)
    chung.log(du_an, f"tóm tắt: {len(md)} ký tự, {len(cum)} cụm lời")
    return p


if __name__ == "__main__":
    print(open(viet(sys.argv[1]), encoding="utf-8").read())
