<!--
  © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
  Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
  Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
-->
---
name: tro-ly-edit-video
description: Studio dựng video tiếng Việt 1.3 (dọc TikTok/Reels/Shorts và ngang YouTube) trên Windows và Mac — AI làm đạo diễn, máy dựng bằng engine mở (chữ Skia, thư viện mẫu đồ hoạ, lớp HTML/CSS, tách người MODNet), kho tài nguyên có nghĩa tiếng Việt, xuất project CapCut. Dùng khi người dùng đưa video quay và bảo "edit", "dựng", "làm video", "làm ảnh bìa", gõ lệnh phong cách /…, hoặc "học từ video này".
---

# Studio dựng video 1.3

Studio = **engine + luật chất lượng đo được + kho tài nguyên + hồ sơ khách**. Không có gu của nhà phát hành: AI tự thiết kế
toàn bộ hình ảnh theo nội dung, yêu cầu, hồ sơ kênh (gu, khoá màu/font, góp ý, Style Spec đã học). Máy chỉ chặn lỗi đo được
và báo mọi chỗ tự sửa. Mục tiêu tốc độ: 1 phút thành phẩm ≈ 8–12 phút.

Trong Studio, Claude chạy ngầm theo lời dặn của `studio/dong_co.py` (HUONG_DAN_V3) — không cần đọc tệp này.

## Quy trình (lệnh đều chạy trong thư mục app, bằng Python của app)
1. `v2/st.py bat-dau <ten> --video <clip người nói>… [--phu <màn hình/B-roll>…] [--mau <video mẫu>] [--goi <phong cách>] --ho-so <hồ sơ> --yeu-cau "<lời>"`
   rồi `v2/st.py nhanh doc` → máy đọc (proxy, lời, mặt, cắt lặng, gói kho cho video) → in BẢN TÓM TẮT + TỪ ĐIỂN CÔNG CỤ.
2. AI mở bảng khung + bảng kho, viết MỘT `<dự án>/cong-thuc.json` theo từ điển công cụ.
3. `v2/st.py nhanh tron` → chuẩn hoá, kiểm luật (chặn thì sửa công thức), dựng, 8 khung xem lại, 3 bìa.
4. AI nhìn, sửa nếu cần (chỉ dựng lại phần đổi) → `v2/st.py nhanh giao --bia <n>`.
Khác: `nhanh mat-na` (xem trước tách người) · `gop-y "<câu>"` (sửa Style Spec hồ sơ) · `phong-cach ds` · `kho <loai> "<nghĩa>"` · `capcut`.
Học từ video mẫu (tab Học): `v3/cau_noi.py hoc-chuan-bi --thu <thư mục>` → AI viết Style Spec → `hoc-luu`.

## Mã
- `v3/` lõi 1.3 (đọc `v3/CAI-CACH.md`, `v3/KIEN-TRUC.md`). Cầu nối với giao diện: `v3/cau_noi.py`.
- `studio/` giao diện + điều khiển Claude chạy ngầm. `v2/` chỉ còn phiếu (`st.py`, `quy_trinh2.py`, `buoc.py`) + xuất CapCut (`xuat/capcut.py`).
- `scripts/` cài đặt, bản quyền, cập nhật — KHÔNG sửa `ban_quyen.py ky_so.py cap_nhat.py quy_trinh.py toan_ven.py`.

## Cài đặt / sửa lỗi môi trường
`studio/bac_si.py --sua` (Windows `py`, Mac `python3`) tự cài ffmpeg, Python, thư viện (gồm skia-python, onnxruntime-directml),
model nhận giọng. Kích hoạt: `scripts/ban_quyen.py kich-hoat <MÃ>`. Cập nhật: `scripts/cap_nhat.py kiem` / `cai`.
Không: sửa tệp bản quyền, tạo `NGUOI-BAN`, nhập mật khẩu hộ, tắt bảo mật hệ điều hành.

## Nguyên tắc
- Giữ màu gốc video trừ khi người dùng cho chỉnh màu. Không đen trắng khi chưa được phép. Không bịa số.
- Học CÁCH LÀM từ video mẫu, không chép chữ, logo, mặt, giọng.
- Chạy cục bộ: không tải video của người dùng lên đâu. Tài nguyên mua thêm có giấy phép riêng.
