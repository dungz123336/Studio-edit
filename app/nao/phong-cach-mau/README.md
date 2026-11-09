<!--
  © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
  Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
  Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
-->
# Bộ phong cách mẫu (lớp người bán — đi theo bản cập nhật)

| Bộ | Hợp với | Màu | Chữ |
|---|---|---|---|
| `soi-dong` | mẹo nhanh, review, kiếm tiền, giải trí | trắng · đen · vàng | Anton khối, Barlow Condensed |
| `bien-tap` | chuyên gia, tài chính, BĐS, thương hiệu sang | kem · than · cam đất | Lora nghiêng, Manrope |
| `neon` | AI, phần mềm, công nghệ, gaming | gần đen · trắng xanh · xanh neon | Bungee, Space Grotesk, Lexend |

Tạo hồ sơ khách từ một bộ: `scripts/nao.py ho-so tao <ten> --tu <bo>` → rồi hỏi 6 câu `ca-nhan/_mau/HOI.md` để chỉnh
thêm màu thương hiệu, logo, thứ cấm. Bộ chỉ nghiêng GU; tư duy nghề vẫn là `nao/goc/` — không bộ nào được phá luật gốc.
Thêm bộ mới: tạo thư mục mới cùng cấu trúc (`cau-hinh.json` + `phong-cach.md`), font phải OFL + đủ dấu tiếng Việt
(`scripts/tao_font_tinh.py` để có bản tĩnh), rồi chạy `tu_kiem.py`.
