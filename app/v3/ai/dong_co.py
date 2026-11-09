# -*- coding: utf-8 -*-
"""Động cơ AI — gọi Claude Code (`claude -p`) chạy ngầm trong thư mục dự án.

goi(prompt, du_an, anh=[], tiep=None, model=None, timeout=900) -> {"ma","text","session","giay","usd","loi","mo_lai"}
luot_1(du_an, loi=None)  -> đường dẫn cong-thuc.json       (từ điển theo khung: tu_dien.tu_dien(khung))
luot_2(du_an, sua_them=None) -> {"duyet", "cong_thuc", "bia", "nhan_xet"}   (tiếp phiên lượt 1, chỉ gửi từ điển rút gọn ≤ tu_dien.TOI_DA_GON ký tự; bìa 1..N)
hoc(du_an, ho_so)        -> đường dẫn style-spec.json
1.2.21: ảnh chỉ kèm khi os.path.isfile; style-spec/kiem.json đưa vào prompt dạng dòng đọc được (không cắt JSON giữa chừng); không đo/giới hạn USD
(`usd` trong kết quả chỉ để đọc); số lần nhắc lại đọc cau_hinh ai.toi_da_luot.
"""
import json, os, re, shutil, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import chung

AI_DIR = os.path.dirname(os.path.abspath(__file__))
_CO = None          # tập cờ CLI tồn tại (đọc `claude --help` một lần)
MA = {0: "ok", 1: "json_sai", 2: "het_luot", 3: "mang", 4: "qua_gio", 5: "khong_co_claude", 6: "dang_nhap", 7: "loi_khac", 8: "thieu_file"}


# ---------------------------------------------------------------- tiện ích
class _AnToan(dict):
    def __missing__(self, k):
        return ""


def _doc(p, mac_dinh=""):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return mac_dinh


def _mau(ten):
    return _doc(os.path.join(AI_DIR, ten))


def cheat_sheet():
    return _mau("cheat_sheet.md")


def _tu_dien(khung, gon=False):
    """từ điển công cụ theo khung của việc (tu_dien.py); gon=True → bản rút gọn cho lượt 2"""
    try:
        from ai import tu_dien as _TD
        return _TD.tu_dien_gon(khung) if gon else _TD.tu_dien(khung)
    except Exception:
        return cheat_sheet()


def _khung(v):
    k = v.get("khung") if isinstance(v, dict) else None
    try:
        return (int(k[0]), int(k[1]))
    except Exception:
        return (1080, 1920)


def _toi_da_luot():
    try:
        return max(1, int((chung.cau_hinh().get("ai") or {}).get("toi_da_luot") or 2))
    except Exception:
        return 2


def _claude():
    c = (chung.cau_hinh().get("ai") or {}).get("claude") or ""
    if c and os.path.exists(c):
        return c
    w = shutil.which("claude")
    if w:
        return w
    # npm toàn cục trên Windows
    for ung in (os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd"),
                os.path.join(os.environ.get("APPDATA", ""), "npm", "claude")):
        if ung and os.path.exists(ung):
            return ung
    return None


def co_cli():
    """tập cờ `claude --help` hỗ trợ (đọc một lần, lưu cache theo phiên bản)."""
    global _CO
    if _CO is not None:
        return _CO
    exe = _claude()
    if not exe:
        _CO = set()
        return _CO
    cache = os.path.join(chung.duong("nhat_ky"), "claude-co.json")
    _, ver, _ = chung.sh([exe, "--version"], timeout=60)
    ver = ver.strip()
    d = chung.doc_json(cache) or {}
    if d.get("ver") == ver and d.get("co"):
        _CO = set(d["co"])
        return _CO
    _, out, err = chung.sh([exe, "--help"], timeout=60)
    co = set(re.findall(r"(--[a-zA-Z][a-zA-Z0-9-]*)", out + err))
    _CO = co
    chung.ghi_json(cache, {"ver": ver, "co": sorted(co)})
    return _CO


def _mcp_rong():
    p = os.path.join(chung.duong("nhat_ky"), "mcp-rong.json")
    if not os.path.exists(p):
        chung.ghi_json(p, {"mcpServers": {}})
    return p


def _phan_loai_loi(van_ban):
    """→ (mã, thông báo tiếng Việt, giờ mở lại|None)"""
    v = (van_ban or "").lower()
    mo_lai = None
    m = re.search(r"reset(?:s)?\s*(?:at|in|lúc)?\s*:?\s*([0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?(?:\s*\([^)]{0,40}\))?)", v)
    if m:
        mo_lai = m.group(1).strip()
    if any(k in v for k in ("usage limit", "rate limit", "limit reached", "hit your limit", "out of extra usage", "overloaded", "529", "too many requests", "429")):
        return 2, "AI hết lượt / quá tải" + (f" — mở lại lúc {mo_lai}" if mo_lai else ""), mo_lai
    if any(k in v for k in ("enotfound", "econnreset", "etimedout", "fetch failed", "network", "offline", "getaddrinfo", "socket hang up", "econnrefused")):
        return 3, "Lỗi mạng khi gọi AI — kiểm tra kết nối rồi chạy lại", None
    if any(k in v for k in ("not logged in", "please log in", "authentication", "unauthorized", "401", "invalid api key", "login")):
        return 6, "Claude Code chưa đăng nhập — chạy `claude` rồi /login", None
    return 7, "Lỗi AI không rõ: " + (van_ban or "").strip()[-400:], None


def _ghi_nhat_ky(du_an, muc):
    try:
        with open(os.path.join(du_an, "ai-nhat-ky.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(muc, ensure_ascii=False) + "\n")
    except Exception:
        pass


def chi_phi(du_an):
    """tổng hợp từ ai-nhat-ky.jsonl → {"usd","giay","so_lan","muc":[...]}"""
    ds = []
    try:
        with open(os.path.join(du_an, "ai-nhat-ky.jsonl"), "r", encoding="utf-8") as f:
            for d in f:
                d = d.strip()
                if d:
                    ds.append(json.loads(d))
    except Exception:
        pass
    return {"usd": round(sum(x.get("usd") or 0 for x in ds), 4), "giay": round(sum(x.get("giay") or 0 for x in ds), 1), "so_lan": len(ds), "muc": ds}


# ---------------------------------------------------------------- gọi claude
def goi(prompt, du_an, anh=None, tiep=None, model=None, timeout=900, buoc="ai"):
    """chạy `claude -p` trong cwd=du_an. Prompt đưa qua stdin (tránh giới hạn dòng lệnh Windows).
    anh: đường dẫn ảnh AI cần mở bằng Read (ghi thêm vào cuối prompt nếu chưa có trong prompt)."""
    exe = _claude()
    if not exe:
        return {"ma": 5, "text": "", "session": tiep, "giay": 0, "usd": 0, "loi": "Không tìm thấy lệnh `claude` (cài Claude Code: npm i -g @anthropic-ai/claude-code)", "mo_lai": None}
    co = co_cli()
    du_an = os.path.abspath(du_an)
    os.makedirs(du_an, exist_ok=True)
    anh = [a for a in (anh or []) if a and os.path.isfile(a)]
    them = [a for a in anh if a not in prompt]
    if them:
        prompt = prompt.rstrip() + "\n\n## Ảnh kèm (mở bằng Read)\n" + "\n".join("- " + a for a in them) + "\n"
    cfg = chung.cau_hinh().get("ai") or {}
    cmd = [exe, "-p", "--output-format", "json", "--permission-mode", "acceptEdits",
           "--add-dir", du_an, "--allowedTools", "Read,Write,Edit,Bash"]
    if "--tools" in co:
        cmd += ["--tools", "Read,Write,Edit,Bash,Glob,Grep"]
    if "--strict-mcp-config" in co and "--mcp-config" in co:
        cmd += ["--strict-mcp-config", "--mcp-config", _mcp_rong()]
    if "--disable-slash-commands" in co:
        cmd += ["--disable-slash-commands"]
    if "--permission-prompts" in co:
        cmd += ["--permission-prompts", "none"]
    if "--no-chrome" in co:
        cmd += ["--no-chrome"]
    model = model or cfg.get("model") or None
    if model:
        cmd += ["--model", model]
    if tiep:
        cmd += ["--resume", tiep]
    t0 = time.time()
    chung.log(du_an, f"gọi AI ({buoc}, {len(prompt)} ký tự{', tiếp phiên' if tiep else ''}{', model ' + model if model else ''})")
    env = {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "DISABLE_AUTOUPDATER": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
    ma, out, err = chung.sh(cmd, timeout=timeout, cwd=du_an, env=env, nhap=prompt.encode("utf-8"))
    giay = round(time.time() - t0, 1)
    kq = {"ma": 0, "text": "", "session": tiep, "giay": giay, "usd": 0.0, "loi": None, "mo_lai": None, "tho": None}
    if ma == 124:
        kq.update(ma=4, loi=f"AI chạy quá {timeout}s, đã dừng")
    j = None
    s = out.strip()
    if s:
        try:
            j = json.loads(s)
        except Exception:
            # có thể lẫn dòng khác trước JSON
            m = re.search(r"\{.*\}\s*$", s, re.S)
            if m:
                try:
                    j = json.loads(m.group(0))
                except Exception:
                    j = None
    if isinstance(j, list):
        j = next((x for x in reversed(j) if isinstance(x, dict) and x.get("type") == "result"), None)
    if isinstance(j, dict):
        kq["tho"] = {k: j.get(k) for k in ("subtype", "is_error", "num_turns", "duration_ms", "duration_api_ms", "stop_reason", "usage")}
        kq["text"] = j.get("result") or ""
        kq["session"] = j.get("session_id") or tiep
        kq["usd"] = float(j.get("total_cost_usd") or 0)
        if j.get("duration_ms"):
            kq["giay"] = round(j["duration_ms"] / 1000, 1)
        if j.get("is_error") or (j.get("subtype") and j.get("subtype") != "success"):
            m2, tb, mo = _phan_loai_loi((kq["text"] or "") + " " + err + " " + str(j.get("subtype")))
            if kq["ma"] == 0:
                kq.update(ma=m2, loi=tb, mo_lai=mo)
    elif kq["ma"] == 0:
        if ma != 0 or not s:
            m2, tb, mo = _phan_loai_loi(err + " " + s)
            kq.update(ma=m2, loi=tb, mo_lai=mo)
        else:
            kq["text"] = s
    if kq["ma"] == 0 and ma != 0 and not kq["text"]:
        m2, tb, mo = _phan_loai_loi(err + " " + s)
        kq.update(ma=m2, loi=tb, mo_lai=mo)
    _ghi_nhat_ky(du_an, {"buoc": buoc, "ma": kq["ma"], "session": kq["session"], "usd": kq["usd"], "giay": kq["giay"],
                         "luc": time.strftime("%Y-%m-%d %H:%M:%S"), "loi": kq["loi"], "ky_tu_prompt": len(prompt), "tho": kq["tho"]})
    chung.log(du_an, f"AI xong ({buoc}): mã {kq['ma']} {MA.get(kq['ma'])}, {kq['giay']}s" + (f" — {kq['loi']}" if kq["loi"] else ""))
    return kq


# ---------------------------------------------------------------- dữ liệu prompt
def ho_so_van_ban(ho_so_id):
    """hồ sơ kênh → văn bản ngắn cho AI (màu/font khoá, luật gu bật, góp ý, mô tả, style-spec)."""
    if not ho_so_id:
        return "(không có hồ sơ — bạn tự quyết màu, font, gu)"
    tm = os.path.join(chung.duong("ho_so"), ho_so_id)
    hs = chung.doc_json(os.path.join(tm, "ho-so.json")) or {}
    if not hs:
        return f"(hồ sơ {ho_so_id} chưa có dữ liệu — bạn tự quyết)"
    d = [f"- Tên kênh: {hs.get('ten') or ho_so_id}"]
    if hs.get("mo_ta_kenh"):
        d.append(f"- Mô tả kênh: {hs['mo_ta_kenh']}")
    mau = hs.get("mau") or {}
    if mau.get("nhan"):
        d.append(f"- Màu nhấn: {mau['nhan']}" + (" (KHOÁ — bắt buộc dùng làm mau_nhan)" if mau.get("khoa") else " (gợi ý, được đổi)"))
    font = hs.get("font") or {}
    if font.get("tieu_de") or font.get("phu_de"):
        d.append(f"- Font tiêu đề: {font.get('tieu_de') or '-'}; phụ đề: {font.get('phu_de') or '-'}" + (" (KHOÁ — bắt buộc)" if font.get("khoa") else " (gợi ý)"))
    luat = chung.doc_json(os.path.join(chung.duong("app"), "nao", "luat_gu.json")) or {}
    mo_ta = {l["id"]: l for l in luat.get("luat", [])}
    bat = [(k, v) for k, v in (hs.get("luat_gu") or {}).items() if isinstance(v, dict) and v.get("bat")]
    if bat:
        d.append("- Luật gu đang bật (phải theo):")
        for k, v in bat:
            l = mo_ta.get(k, {})
            d.append(f"  • {k} = {v.get('gia_tri', l.get('gia_tri'))} {l.get('don_vi', '')} — {l.get('mo_ta', '')}")
    gy = [g for g in (hs.get("gop_y") or []) if g]
    if gy:
        d.append("- Góp ý trước đây của khách (ràng buộc):")
        d += [f"  • {g if isinstance(g, str) else g.get('noi_dung', '')}" for g in gy[-8:]]
    ss = chung.doc_json(os.path.join(tm, "style-spec.json"))
    if ss:
        d.append("- Style spec đã học từ video mẫu (cách làm, không chép chữ/logo):")
        try:
            from doc import tom_tat as _TT
            d += ["  " + x for x in _TT._ban_sac_doc_duoc(ss)]
        except Exception:
            d.append("  " + json.dumps({k: ss.get(k) for k in ("palette", "type_scale", "motion_vocab") if ss.get(k)}, ensure_ascii=False, separators=(",", ":"))[:1500])
    try:
        from ai import hop_dong as _HD
        qd, nguon, loi_qd = _HD.doc_quyet_dinh(None, ho_so_id, luu=False)
        if qd:
            d.append(f"- Quyết định kênh (nao/ca-nhan/{ho_so_id}/quyet-dinh.json, phiên {qd.get('phien')}): đã có — mọi trường công thức bỏ trống lấy từ đây; chi tiết trong tóm tắt")
        elif loi_qd:
            d.append("- Quyết định kênh: tệp hiện có SAI KHUÔN — " + "; ".join(f"{l['duong']}: {l['goi_y']}" for l in loi_qd[:6]))
        else:
            d.append("- Quyết định kênh: CHƯA CÓ — Write <dự án>/quyet-dinh-kenh.json theo khuôn trong tóm tắt trước khi viết công thức")
    except Exception:
        pass
    return "\n".join(d)


def _viec(du_an):
    return chung.doc_json(os.path.join(du_an, "viec.json")) or {}


def _ten_kenh(du_an, v=None):
    v = v or _viec(du_an)
    hs = chung.doc_json(os.path.join(chung.duong("ho_so"), v.get("ho_so") or "", "ho-so.json")) or {}
    return hs.get("ten") or v.get("ho_so") or "kênh"


def _model_cho(v):
    cfg = chung.cau_hinh().get("ai") or {}
    if v.get("che_do") == "nhanh" and cfg.get("model_nhanh"):
        return cfg["model_nhanh"]
    return cfg.get("model") or None


def _phien(du_an):
    return chung.doc_json(os.path.join(du_an, "ai-phien.json")) or {}


def _luu_phien(du_an, khoa, sid):
    p = _phien(du_an)
    if sid:
        p[khoa] = sid
        chung.ghi_json(os.path.join(du_an, "ai-phien.json"), p)


def _json_hop_le(p, bat_buoc=()):
    """→ (obj|None, thông báo lỗi|None)"""
    if not os.path.isfile(p):
        return None, f"không thấy file {os.path.basename(p)}"
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            s = f.read()
        o = json.loads(s)
    except Exception as ex:
        return None, f"{os.path.basename(p)} không phải JSON hợp lệ: {ex}"
    if not isinstance(o, dict):
        return None, f"{os.path.basename(p)} phải là object JSON"
    thieu = [k for k in bat_buoc if k not in o]
    if thieu:
        return None, f"{os.path.basename(p)} thiếu trường bắt buộc: {', '.join(thieu)}"
    return o, None


def _dong_loi(l):
    d = l.get("duong")
    return f"- [{l.get('id')}] " + (f"`{d}`" if d else f"lớp {l.get('lop', '-')}") + (f" t={l.get('t')}" if l.get("t") is not None else "") + f": {str(l.get('mo_ta', ''))[:400]}"


def _tom_tat_loi_kiem(kiem):
    if not kiem:
        return ""
    loi = kiem.get("loi") or []
    if not loi:
        return ""
    d = ["## Lỗi máy CHẶN ở công thức trước — bắt buộc sửa rồi Write lại toàn bộ cong-thuc.json (thieu_truong: ghi trường theo `duong` hoặc thêm khoá vào quyet-dinh-kenh.json):"]
    d += [_dong_loi(l) for l in loi[:40]]
    if len(loi) > 40:
        d.append(f"… (+{len(loi) - 40} lỗi, đủ trong kiem.json)")
    ms = kiem.get("may_sua") or []
    if ms:
        d.append("Máy đã tự sửa số (tham khảo): " + "; ".join(f"{m.get('lop')}: {str(m.get('mo_ta', m.get('sua', '')))[:160]}" for m in ms[:20]))
    return "\n".join(d) + "\n"


def _kiem_doc_duoc(kiem, toi_da_dong=60):
    """kiem.json → dòng đọc được cho lượt 2 (không cắt JSON giữa chừng): lỗi, máy sửa, cảnh báo, kỹ thuật, tra kho top-5"""
    if not kiem:
        return "(không có lỗi, không có sửa)"
    D = []
    loi = kiem.get("loi") or []
    D.append(f"LỖI CHẶN ({len(loi)}):" if loi else "LỖI CHẶN: không")
    D += [_dong_loi(l) for l in loi[:toi_da_dong]]
    ms = kiem.get("may_sua") or []
    if ms:
        D.append(f"MÁY ĐÃ TỰ SỬA ({len(ms)}):")
        D += [f"- {m.get('lop')} [{m.get('sua')}]: {str(m.get('mo_ta', ''))[:220]}" for m in ms[:toi_da_dong]]
    cb = kiem.get("canh_bao") or []
    if cb:
        D.append(f"CẢNH BÁO / SỐ ĐO ({len(cb)}):")
        D += [f"- [{c.get('id')}] {c.get('lop', '')}: {str(c.get('mo_ta', ''))[:300]}" for c in cb[:toi_da_dong]]
    kt = kiem.get("ky_thuat") or {}
    if kt:
        D.append("KỸ THUẬT: " + ", ".join(f"{k} {v}" for k, v in kt.items() if v not in (None, [], {})))
    tk = kiem.get("tra_kho") or []
    if tk:
        D.append(f"TRA KHO ({len(tk)} chỗ; đang dựng bằng top-1, muốn đổi ghi id kho vào trường đó):")
        for t in tk[:30]:
            uv = t.get("ung_vien") or []
            D.append(f"- {t.get('lop')} «{str(t.get('nghia', ''))[:40]}» → {t.get('id')}" + (" | ứng viên: " + "; ".join(
                f"{u.get('id')} ({u.get('diem')}{', ' + str(u.get('chu_ky')) if u.get('chu_ky') else ''}{', dùng ' + str(u.get('da_dung')) if u.get('da_dung') else ''}{', ' + str(round(float(u['dur']), 1)) + 's' if u.get('dur') else ''})"
                for u in uv[:5]) if uv else ""))
    return "\n".join(D)


# ---------------------------------------------------------------- lượt 1
def luot_1(du_an, loi=None, model=None):
    """AI thiết kế video → cong-thuc.json. loi = kiem.json (dict) nếu gọi lại sau khi máy chặn.
    Trả đường dẫn cong-thuc.json; ném RuntimeError kèm mã nếu thất bại."""
    du_an = os.path.abspath(du_an)
    v = _viec(du_an)
    model = model or _model_cho(v)
    ten = _ten_kenh(du_an, v)
    cong_thuc = os.path.join(du_an, "cong-thuc.json")
    tom_tat = _doc(os.path.join(du_an, "doc", "tom-tat.md"), "(chưa có tóm tắt)")
    phien = _phien(du_an).get("luot1")
    kiem_vb = _tom_tat_loi_kiem(loi)
    anh = [a for a in (os.path.join(du_an, "doc", "bang-khung.jpg"), os.path.join(du_an, "doc", "bia-ung-vien.jpg")) if os.path.isfile(a)]
    if loi and phien:
        # gọi lại trong cùng phiên: ngắn gọn
        prompt = (kiem_vb + f"\nHãy Write lại TOÀN BỘ `{cong_thuc}` (JSON hợp lệ, cùng định dạng). Không hỏi lại, không giải thích dài; lý do ghi trong ghi_chu ≤ 3 câu.\n")
        kq = goi(prompt, du_an, tiep=phien, model=model, buoc="ai1-sua")
        if kq["ma"] != 0 and kq["ma"] not in (4,):
            # phiên cũ hỏng → gọi mới đầy đủ
            phien = None
    if not (loi and phien):
        try:
            os.remove(cong_thuc)
        except FileNotFoundError:
            pass
        du_lieu = _AnToan(ten=ten, yeu_cau=v.get("yeu_cau") or "(không có yêu cầu riêng)", ho_so=ho_so_van_ban(v.get("ho_so")),
                          tom_tat=tom_tat, cheat_sheet=_tu_dien(_khung(v)), duong_du_an=du_an, kiem=kiem_vb, bia="")
        prompt = _mau("prompt_luot1.md").format_map(du_lieu)
        kq = goi(prompt, du_an, anh=anh, model=model, buoc="ai1")
    if kq["ma"] in (2, 3, 5, 6):
        raise RuntimeError(f"[{MA[kq['ma']]}] {kq['loi']}")
    _luu_phien(du_an, "luot1", kq["session"])
    o, l = _json_hop_le(cong_thuc, bat_buoc=("lop",))
    lan = 0
    while o is None and lan < _toi_da_luot() - 1:
        lan += 1
        chung.log(du_an, f"AI lượt 1: {l} → nhắc lại ({lan}/{_toi_da_luot() - 1})")
        prompt2 = (f"Kết quả chưa dùng được: {l}. Hãy Write lại TOÀN BỘ `{cong_thuc}` là JSON hợp lệ đúng từ điển công cụ "
                   f"(object gốc có `lop` là mảng, không chú thích, không dấu phẩy thừa). Không hỏi lại.")
        kq2 = goi(prompt2, du_an, tiep=kq["session"], model=model, buoc="ai1-json")
        if kq2["ma"] in (2, 3, 5, 6):
            raise RuntimeError(f"[{MA[kq2['ma']]}] {kq2['loi']}")
        _luu_phien(du_an, "luot1", kq2["session"] or kq["session"])
        o, l = _json_hop_le(cong_thuc, bat_buoc=("lop",))
    if o is None:
        raise RuntimeError(f"[json_sai] AI lượt 1 không viết được cong-thuc.json hợp lệ: {l}")
    return cong_thuc


# ---------------------------------------------------------------- lượt 2
def luot_2(du_an, sua_them=None, model=None):
    """AI xem xem-lai.jpg + kiem.json + N bìa (bia-1..N.png, N = số phương án AI ghi) → duyet.json (+ cong-thuc.v2.json nếu sửa).
    Tiếp phiên lượt 1 (tiep=) nếu còn; chỉ gửi từ điển rút gọn. → {"duyet": bool|None, "cong_thuc": path|None, "bia": 1..N, "nhan_xet": str, "loi": str|None}"""
    du_an = os.path.abspath(du_an)
    v = _viec(du_an)
    model = model or _model_cho(v)
    ten = _ten_kenh(du_an, v)
    duyet_p = os.path.join(du_an, "duyet.json")
    v2 = os.path.join(du_an, "cong-thuc.v2.json")
    for p in (duyet_p, v2):
        try:
            os.remove(p)
        except FileNotFoundError:
            pass
    bia_co = []
    for i in range(1, 9):
        b = os.path.join(du_an, "dung", f"bia-{i}.png")
        if os.path.isfile(b):
            bia_co.append(b)
        else:
            break
    so_bia = max(1, len(bia_co))
    kiem = chung.doc_json(os.path.join(du_an, "kiem.json")) or {}
    kiem_vb = _kiem_doc_duoc(kiem)
    sua_vb = ""
    if sua_them:
        sua_vb = f"\n## Lời sửa của người dùng (ưu tiên cao nhất — phải thực hiện, viết cong-thuc.v2.json)\n{sua_them}\n"
    tiep = _phien(du_an).get("luot1")
    du_lieu = _AnToan(ten=ten, yeu_cau=v.get("yeu_cau") or "(không có yêu cầu riêng)", ho_so=ho_so_van_ban(v.get("ho_so")),
                      cheat_sheet=_tu_dien(_khung(v), gon=bool(tiep)), duong_du_an=du_an, kiem=kiem_vb, so_bia=so_bia,
                      bia=", ".join(f"`{b}`" for b in bia_co) or "(chưa có bìa)", sua_them=sua_vb, tom_tat="")
    prompt = _mau("prompt_luot2.md").format_map(du_lieu)
    anh = [os.path.join(du_an, "dung", "xem-lai.jpg")] + bia_co
    kq = goi(prompt, du_an, anh=anh, tiep=tiep, model=model, buoc="ai2" + ("-sua" if sua_them else ""))
    if kq["ma"] != 0 and tiep and kq["ma"] not in (2, 3, 5, 6):
        chung.log(du_an, f"lượt 2 tiếp phiên lỗi ({kq.get('loi')}) → gọi phiên mới với từ điển đầy đủ")
        du_lieu["cheat_sheet"] = _tu_dien(_khung(v))
        prompt = _mau("prompt_luot2.md").format_map(du_lieu)
        kq = goi(prompt, du_an, anh=anh, model=model, buoc="ai2-moi")
    if kq["ma"] in (2, 3, 5, 6):
        raise RuntimeError(f"[{MA[kq['ma']]}] {kq['loi']}")
    _luu_phien(du_an, "luot2", kq["session"])

    def doc_kq():
        d, l = _json_hop_le(duyet_p)
        if d is None and os.path.isfile(v2):
            d = {"duyet": False, "bia": 1, "nhan_xet": "(AI chỉ viết cong-thuc.v2.json)"}
            l = None
        if d is None:
            return None, l
        if not d.get("duyet", False):
            o, l2 = _json_hop_le(v2, bat_buoc=("lop",))
            if o is None:
                return None, l2
        return d, None

    d, l = doc_kq()
    if d is None:
        chung.log(du_an, f"AI lượt 2: {l} → nhắc lại một lần")
        prompt2 = (f"Kết quả chưa dùng được: {l}. Hãy Write `{duyet_p}` dạng {{\"duyet\": true|false, \"bia\": 1..{so_bia}, \"nhan_xet\": \"...\"}}; "
                   f"nếu duyet=false thì Write thêm `{v2}` là TOÀN BỘ công thức đã sửa (JSON hợp lệ, có `lop`). Không hỏi lại.")
        kq2 = goi(prompt2, du_an, tiep=kq["session"], model=model, buoc="ai2-json")
        if kq2["ma"] in (2, 3, 5, 6):
            raise RuntimeError(f"[{MA[kq2['ma']]}] {kq2['loi']}")
        d, l = doc_kq()
    if d is None:
        return {"duyet": None, "cong_thuc": None, "bia": 1, "nhan_xet": "", "loi": f"AI lượt 2 không trả lời hợp lệ: {l}"}
    try:
        b = int(d.get("bia") or 1)
    except Exception:
        b = 1
    b = min(max(b, 1), so_bia)
    return {"duyet": bool(d.get("duyet")), "cong_thuc": None if d.get("duyet") else v2, "bia": b,
            "nhan_xet": str(d.get("nhan_xet") or ""), "loi": None}


# ---------------------------------------------------------------- học style
def _kiem_style_spec(o):
    schema = chung.doc_json(os.path.join(chung.duong("app"), "nao", "style_spec.schema.json")) or {}
    loi = []
    for k in schema.get("required", []):
        if k not in o:
            loi.append(f"thiếu `{k}`")
    cho_phep = set((schema.get("properties") or {}).keys())
    for k in o:
        if cho_phep and k not in cho_phep:
            loi.append(f"trường lạ `{k}`")
    if not isinstance(o.get("dau_an_khong_chep", []), list):
        loi.append("`dau_an_khong_chep` phải là mảng")
    return loi


def hoc(du_an, ho_so=None, model=None):
    """AI nhìn bảng khung dày của video mẫu → style-spec.json (chỉ cách làm). Trả đường dẫn file."""
    du_an = os.path.abspath(du_an)
    v = _viec(du_an)
    ho_so = ho_so or v.get("ho_so")
    model = model or _model_cho(v)
    ra = os.path.join(du_an, "style-spec.json")
    try:
        os.remove(ra)
    except FileNotFoundError:
        pass
    schema = _doc(os.path.join(chung.duong("app"), "nao", "style_spec.schema.json"), "{}")
    tom = _doc(os.path.join(du_an, "doc", "tom-tat.md"), "")
    tom_vb = ("\nTóm tắt máy đọc (lời/cảnh của video mẫu — chỉ để hiểu nhịp, KHÔNG chép câu chữ):\n" + tom[:3000]) if tom else ""
    du_lieu = _AnToan(ten=_ten_kenh(du_an, {"ho_so": ho_so}), duong_du_an=du_an, ho_so=ho_so_van_ban(ho_so), cheat_sheet=schema, tom_tat=tom_vb)
    prompt = _mau("prompt_hoc.md").format_map(du_lieu)
    anh = [os.path.join(du_an, "doc", "bang-khung-day.jpg"), os.path.join(du_an, "doc", "bang-khung.jpg")]
    kq = goi(prompt, du_an, anh=[a for a in anh if os.path.isfile(a)], model=model, buoc="hoc")
    if kq["ma"] in (2, 3, 5, 6):
        raise RuntimeError(f"[{MA[kq['ma']]}] {kq['loi']}")
    o, l = _json_hop_le(ra)
    loi = _kiem_style_spec(o) if o else [l]
    if loi:
        prompt2 = f"style-spec.json chưa đạt: {'; '.join(loi)}. Hãy Write lại TOÀN BỘ `{ra}` đúng schema (JSON hợp lệ). Không hỏi lại."
        kq2 = goi(prompt2, du_an, tiep=kq["session"], model=model, buoc="hoc-json")
        if kq2["ma"] in (2, 3, 5, 6):
            raise RuntimeError(f"[{MA[kq2['ma']]}] {kq2['loi']}")
        o, l = _json_hop_le(ra)
        loi = _kiem_style_spec(o) if o else [l]
        if loi:
            raise RuntimeError("[json_sai] AI không viết được style-spec.json hợp lệ: " + "; ".join(loi))
    return ra


if __name__ == "__main__":
    print("claude:", _claude())
    print("cờ:", sorted(co_cli()))
