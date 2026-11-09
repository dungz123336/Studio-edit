# -*- coding: utf-8 -*-
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Máy giữ phiếu Studio 2.0 — 30 bước, 6 cổng, chặn thật.
Luật (THIET-KE.md §2):
 1. Bước k chỉ nộp khi mọi bước trước đã xong và cổng ngay trước đã ĐẠT.
 2. Nộp = file đầu ra qua bộ kiểm nội dung của bước; phiếu ghi sha256 + công cụ + thời gian chạy.
 3. Nộp lại một bước với nội dung khác → huỷ mọi bước và cổng sau nó (phải làm lại).
 4. Bước AI không thể nộp cách bước AI trước < 2 giây (chống đánh dấu hàng loạt).
 5. Hồ sơ của phiếu phải khớp HO_SO mà Studio ghim cho việc.
"""
import os, sys, time, json
import chung as C
import buoc as B

DIEM_TRO = os.path.join(C.SKILL, ".phieu2-hien-tai")


class Chan(SystemExit):
    pass


def chan(thong_bao):
    raise Chan("⛔ DỪNG — " + thong_bao)


def con_tro():
    """file con trỏ chứa đường dẫn thư mục dự án đang mở: Studio ghim mỗi việc một con trỏ (QUY_TRINH_PHIEU2),
    dùng CLI thường thì là <skill>/.phieu2-hien-tai"""
    return os.environ.get("QUY_TRINH_PHIEU2", "").strip() or DIEM_TRO


def duong_phieu():
    try:
        d = open(con_tro(), encoding="utf-8").read().strip()
        return os.path.join(d, "phieu.json") if d else ""
    except OSError:
        return ""


def doc_phieu(bat_buoc=True):
    p = duong_phieu()
    ph = C.doc(p) if p else None
    if ph is None and bat_buoc:
        chan("chưa có phiếu. Chạy trước: python v2/st.py bat-dau <ten> --video <file> --ho-so <hồ sơ>")
    return ph


def luu(ph):
    C.ghi(os.path.join(ph["du_an"], "phieu.json"), ph)


def du_an():
    return doc_phieu()["du_an"]


def _kiem_ho_so(ph):
    hs_ghim = os.environ.get("HO_SO", "").strip()
    if hs_ghim and hs_ghim != ph["ho_so"]:
        chan(f"phiếu thuộc hồ sơ `{ph['ho_so']}` nhưng việc này ghim hồ sơ `{hs_ghim}` — không được dùng gu/thương hiệu của người khác")


def mo(ten, ho_so, thu_muc=None, thong_tin=None, de=False):
    try:
        import ban_quyen
        ok, loai, tb = ban_quyen.gac()
        if not ok:
            chan(f"{loai}: {tb}")
    except Chan:
        raise
    except Exception:
        pass
    if not ho_so or not os.path.isdir(os.path.join(C.CA_NHAN, ho_so)) or ho_so.startswith("_"):
        chan(f"hồ sơ `{ho_so}` không tồn tại. Video của người khác → tạo hồ sơ riêng cho họ (nao.py ho-so tao <ten>)")
    hs_ghim = os.environ.get("HO_SO", "").strip()
    if hs_ghim and hs_ghim != ho_so:
        chan(f"việc này ghim hồ sơ `{hs_ghim}`, không mở phiếu cho `{ho_so}`")
    cu = doc_phieu(bat_buoc=False)
    if cu and not cu.get("dong") and not de:
        chan(f"còn phiếu `{cu['ten']}` chưa giao/đóng ({cu['du_an']}). Giao xong hoặc thêm --de để bỏ.")
    if thu_muc:
        goc = thu_muc
        os.makedirs(goc, exist_ok=True)
    else:                                       # 1.2.9: nhiều việc song song cùng phút + cùng tên → mỗi việc một thư mục riêng
        os.makedirs(C.goc_du_an(), exist_ok=True)
        goc0 = os.path.join(C.goc_du_an(), time.strftime("%Y%m%d-%H%M") + "-" + ten)
        for k in range(1, 100):
            goc = goc0 if k == 1 else f"{goc0}-{k}"
            try:
                os.makedirs(goc)                # tạo NGUYÊN TỬ: việc khác đã giành tên này thì thử tên kế
                break
            except FileExistsError:
                continue
    ph = {"phien": 2, "ten": ten, "ho_so": ho_so, "du_an": os.path.abspath(goc), "mo_luc": C.bay_gio(),
          "thong_tin": thong_tin or {}, "buoc": {}, "cong": {}, "lich_su": []}
    luu(ph)
    ct = con_tro()
    os.makedirs(os.path.dirname(os.path.abspath(ct)), exist_ok=True)
    open(ct, "w", encoding="utf-8").write(ph["du_an"])
    with open(ct + ".ds", "a", encoding="utf-8") as f:          # mọi phiếu của việc này (Studio hiện từng phiếu)
        f.write(ph["du_an"] + "\n")
    danh_dau("0.1", "phieu.json", "st.py bat-dau")
    return ph


def _sau(buoc):
    i = B.THU_TU.index(buoc)
    return B.THU_TU[i + 1:]


def _huy_sau(ph, buoc, ly_do):
    bo = [b for b in _sau(buoc) if b in ph["buoc"]]
    for b in bo:
        ph["buoc"].pop(b, None)
    i = B.THU_TU.index(buoc)
    for n, (sau, _) in B.CONG.items():
        if B.THU_TU.index(sau) >= i and str(n) in ph["cong"]:
            ph["cong"].pop(str(n), None)
    if bo:
        ph["lich_su"].append({"luc": C.bay_gio(), "huy": bo, "vi": ly_do})
    return bo


def kiem_dieu_kien(ph, buoc):
    """bước trước xong hết + cổng ngay trước đạt"""
    if buoc not in B.THU_TU:
        chan(f"không có bước {buoc}")
    i = B.THU_TU.index(buoc)
    thieu = [b for b in B.THU_TU[:i] if b not in ph["buoc"]]
    if thieu:
        chan(f"bước {buoc} chưa được làm: còn thiếu {', '.join(thieu[:6])} ({B.TEN[thieu[0]]}). Làm đúng thứ tự.")
    n = B.CONG_TRUOC.get(buoc)
    if n and not ph["cong"].get(str(n), {}).get("dat"):
        chan(f"CỔNG {n} chưa đạt ({B.CONG[n][1]}). Chạy: python v2/st.py cong {n}")


def danh_dau(buoc, dau_ra, cong_cu, giay_chay=None, ghi_chu=None):
    """bước MÁY tự đánh khi công cụ chạy xong"""
    ph = doc_phieu()
    _kiem_ho_so(ph)
    kiem_dieu_kien(ph, buoc)
    p = os.path.join(ph["du_an"], dau_ra)
    if not os.path.exists(p):
        chan(f"bước {buoc}: công cụ báo xong nhưng không thấy {dau_ra}")
    sha = C.bam(p)
    cu = ph["buoc"].get(buoc)
    if cu and cu.get("sha") != sha:
        _huy_sau(ph, buoc, f"{buoc} làm lại")
    ph["buoc"][buoc] = {"luc": C.bay_gio(), "t": time.time(), "dau_ra": dau_ra, "sha": sha, "cong_cu": cong_cu,
                        "giay_chay": round(giay_chay, 1) if giay_chay else None, "ghi_chu": ghi_chu}
    luu(ph)
    print(f"  ✓ {buoc} {B.TEN[buoc]}  → {dau_ra}")
    return ph


def nop(buoc, duong):
    """bước AI / người dùng: kiểm nội dung rồi mới đánh"""
    ph = doc_phieu()
    _kiem_ho_so(ph)
    kiem_dieu_kien(ph, buoc)
    p = duong if os.path.isabs(duong) else os.path.join(ph["du_an"], duong)
    if not os.path.exists(p):
        chan(f"không thấy file {duong}")
    can = os.path.join(ph["du_an"], B.DAU_RA[buoc])
    truoc = [v.get("t", 0) for k, v in ph["buoc"].items() if B.AI_LAM.get(k) != "may"]
    if truoc and time.time() - max(truoc) < 2.0 and not os.environ.get("_NOP_GOP"):   # nộp gộp (phương pháp nhanh) được phép
        chan("nộp quá nhanh sau bước trước — mỗi bước tư duy phải được làm thật, không đánh dấu hàng loạt")
    kiem = B.KIEM_AI.get(buoc)
    loi = kiem(ph["du_an"], p) if kiem else []          # kiểm bản nộp TRƯỚC khi chép vào chỗ chính thức
    if loi:
        print(f"⛔ Bước {buoc} ({B.TEN[buoc]}) CHƯA ĐẠT:")
        for l in loi[:25]:
            print("   -", l)
        raise Chan(1)
    if os.path.abspath(p) != os.path.abspath(can):
        import shutil
        shutil.copyfile(p, can); p = can
    return danh_dau(buoc, os.path.relpath(p, ph["du_an"]).replace("\\", "/"), "AI nộp (st.py nop)")


def ghi_cong(n, dat, loi, chi_tiet=None):
    ph = doc_phieu()
    sau = B.CONG[n][0]
    if sau not in ph["buoc"]:
        chan(f"cổng {n} đứng sau bước {sau} — làm bước đó trước")
    ph["cong"][str(n)] = {"luc": C.bay_gio(), "dat": bool(dat), "loi": loi[:50], "chi_tiet": chi_tiet}
    luu(ph)
    print(f"  {'✅' if dat else '⛔'} CỔNG {n}: {B.CONG[n][1]} → {'ĐẠT' if dat else 'CHƯA ĐẠT'}")
    for l in loi[:20]:
        print("     -", l)
    return dat


def trang_thai(ph=None, in_ra=True):
    ph = ph or doc_phieu()
    dong = []
    xong = 0
    for gd in range(8):
        dong.append(f"── GĐ{gd} · {B.GIAI_DOAN[gd]}")
        for b in [x for x in B.BUOC if x[1] == gd]:
            ok = b[0] in ph["buoc"]
            xong += ok
            dong.append(f"   {'✓' if ok else '·'} {b[0]} {b[2]}" + (f"  ({ph['buoc'][b[0]]['luc'][11:]})" if ok else ""))
        for n, (sau, mt) in B.CONG.items():
            if B.THU_TU.index(sau) // 1 >= 0 and [x for x in B.BUOC if x[0] == sau][0][1] == gd:
                c = ph["cong"].get(str(n))
                dong.append(f"   {'✅' if c and c['dat'] else ('⛔' if c else '◇')} CỔNG {n}: {mt}")
    tiep = next((b for b in B.THU_TU if b not in ph["buoc"]), None)
    dau = f"Phiếu `{ph['ten']}` · hồ sơ {ph['ho_so']} · {xong}/{len(B.THU_TU)} bước · dự án {ph['du_an']}"
    if tiep:
        dau += f"\nBước kế: {tiep} — {B.TEN[tiep]}"
    if in_ra:
        print(dau + "\n" + "\n".join(dong))
    return {"xong": xong, "tong": len(B.THU_TU), "tiep": tiep}
