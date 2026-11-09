# -*- coding: utf-8 -*-
# © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
# Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
# Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
"""Bảng 30 bước + 6 cổng của Studio 2.0 và bộ kiểm NỘI DUNG từng bước (không kiểm bằng từ khoá).
Mỗi bộ kiểm: f(du_an, duong_file) -> list lỗi (rỗng = đạt)."""
import os, re

# ai: may = công cụ tự đánh khi chạy xong · ai = AI nộp bằng `st.py nop` · nguoi = cần lời người dùng
BUOC = [
    # id,   giai đoạn, tên,                                         ai,     đầu ra (trong dự án)
    ("0.1", 0, "Mở phiếu — video của ai → hồ sơ",                   "may", "phieu.json"),
    ("0.2", 0, "Nạp hồ sơ: luật cứng, token, cấm, góp ý, nhật ký",   "may", "01-ho-so.json"),
    ("1.1", 1, "Đọc lời từng từ (sửa từ riêng của hồ sơ)",           "may", "11-loi.json"),
    ("1.2", 1, "Đọc hình: khung, cảnh, mặt, chữ màn hình, rung",     "may", "12-hinh.json"),
    ("1.3", 1, "Đọc âm: LUFS, ồn, khoảng lặng",                      "may", "13-am.json"),
    ("1.4", 1, "Hồ sơ nguyên liệu + bảng khung cho AI nhìn",         "may", "14-nguyen-lieu.json"),
    ("2.1", 2, "Chẩn đoán 6 chiều + tra ma trận",                    "may", "21-chan-doan.json"),
    ("2.2", 2, "AI xác nhận 6 quyết định (có trích thẻ, đã nhìn khung)", "ai", "22-quyet-dinh.json"),
    ("2.3", 2, "Kịch bản nghĩa: cắt theo ý, tách nhịp, mốc",         "ai",  "23-kich-ban.json"),
    ("3.1", 3, "Kế hoạch INTRO",                                     "ai",  "ke-hoach.json"),
    ("3.2", 3, "Kế hoạch THÂN từng giây",                            "ai",  "ke-hoach.json"),
    ("3.3", 3, "Kế hoạch OUTRO",                                     "ai",  "ke-hoach.json"),
    ("3.4", 3, "Kế hoạch ÂM THANH",                                  "ai",  "ke-hoach.json"),
    ("3.5", 3, "Đi chợ kho: mọi thủ pháp → ID tài nguyên",           "ai",  "ke-hoach.json"),
    ("3.6", 3, "Duyệt kế hoạch với người dùng",                      "nguoi", "36-duyet.json"),
    ("4.1", 4, "Dựng bản nháp (proxy)",                              "may", "4-dung/ban-nhap.mp4"),
    ("4.2", 4, "Dựng bản thật — máy dựng chính thức",                "may", "4-dung/ban-that.mp4"),
    ("5.1", 5, "Máy chấm",                                           "may", "5-kiem.json"),
    ("5.2", 5, "Đối chiếu kế hoạch ↔ thành phẩm",                    "may", "5-kiem.json"),
    ("5.3", 5, "AI nhìn bảng khung: sửa hoặc ghi lý do",             "ai",  "53-nhin.json"),
    ("6.1", 6, "Bìa · lời hứa",                                      "may", "6-bia/61-loi-hua.json"),
    ("6.2", 6, "Bìa · chọn kiểu",                                    "may", "6-bia/62-kieu.json"),
    ("6.3", 6, "Bìa · chọn khung",                                   "may", "6-bia/63-khung.json"),
    ("6.4", 6, "Bìa · bố cục theo đích",                             "may", "6-bia/bao-cao.json"),
    ("6.5", 6, "Bìa · áp token hồ sơ",                               "may", "6-bia/bao-cao.json"),
    ("6.6", 6, "Bìa · kiểm chặn",                                    "may", "6-bia/66-kiem.json"),
    ("6.7", 6, "Bìa · AI nhìn + chọn trong 2–3 biến thể",            "ai",  "6-bia/chon.json"),
    ("7.1", 7, "Đóng gói & giao",                                    "may", "giao/bao-cao.md"),
    ("7.2", 7, "Nhật ký sáng tạo → kho (chống lặp)",                 "may", "72-nhat-ky.json"),
    ("7.3", 7, "Góp ý → hồ sơ (hoặc ghi 'chưa có góp ý')",           "nguoi", "73-gop-y.json"),
]
GIAI_DOAN = ["NHẬN VIỆC", "ĐỌC HIỂU", "CHẨN ĐOÁN", "KẾ HOẠCH", "DỰNG", "KIỂM", "ẢNH BÌA", "GIAO & HỌC"]
# cổng: số → (đứng sau bước, mô tả)
CONG = {1: ("2.3", "Lời đã cắt đọc trôi · mọi quyết định có ID thẻ tri thức"),
        2: ("3.5", "Kiểm kế hoạch: trần khoảng trống, ngân sách đếm thật, ≤2 kiểu chữ/khung, chống lặp, luật cứng, tài nguyên tồn tại"),
        3: ("5.3", "Không còn lỗi máy chấm/mắt nhìn chưa sửa hoặc chưa giải thích"),
        4: ("6.6", "≥2 biến thể bìa qua kiểm chặn"),
        5: ("6.7", "Đủ file đầu ra của mọi bước (kiểm khi giao)"),
        6: ("6.7", "Video giao đúng là video máy dựng chính thức ghi (kiểm khi giao)")}
# 1.3 — người dùng và AI chỉ thấy 3 PHẦN. Các bước con ở trên là mốc + phép kiểm TỰ ĐỘNG bên trong từng phần (luật cứng, cổng),
# không còn là việc AI phải làm từng bước.
PHAN = [
    ("ĐỌC", "Máy đọc lời, hình, âm một lần (4K chỉ giải mã 1 lần), chẩn đoán, viết nháp kịch bản + khung kế hoạch",
     ["0.1", "0.2", "1.1", "1.2", "1.3", "1.4", "2.1"]),
    ("TƯ DUY", "AI nghĩ một lần: quyết định, kịch bản, kế hoạch từng giây, tài nguyên — máy tự kiểm luật cứng và tự sửa",
     ["2.2", "2.3", "3.1", "3.2", "3.3", "3.4", "3.5", "3.6"]),
    ("DỰNG", "Máy dựng một lần, tự chấm, AI nhìn lại; dựng ảnh bìa; giao",
     ["4.1", "4.2", "5.1", "5.2", "5.3", "6.1", "6.2", "6.3", "6.4", "6.5", "6.6", "6.7", "7.1", "7.2", "7.3"]),
]
CONG_NGAN = {1: "lời cắt đọc trôi", 2: "luật kế hoạch", 3: "máy chấm sạch", 4: "bìa đạt kiểm", 5: "đủ đầu ra", 6: "đúng video máy dựng"}
PHAN_CUA = {b: i for i, (_, _, ds) in enumerate(PHAN) for b in ds}
THU_TU = [b[0] for b in BUOC]
TEN = {b[0]: b[2] for b in BUOC}
AI_LAM = {b[0]: b[3] for b in BUOC}
DAU_RA = {b[0]: b[4] for b in BUOC}
CONG_TRUOC = {}          # bước → cổng phải đạt trước khi nộp bước đó
for _n, (_sau, _) in CONG.items():
    _i = THU_TU.index(_sau)
    if _i + 1 < len(THU_TU) and _n <= 4:
        CONG_TRUOC[THU_TU[_i + 1]] = _n


# 1.3: bộ kiểm nội dung từng bước của lõi cũ đã gỡ — lõi mới kiểm bằng v3/nao (luật đo được); bảng trên chỉ còn làm MỐC phiếu.
KIEM_AI = {}
