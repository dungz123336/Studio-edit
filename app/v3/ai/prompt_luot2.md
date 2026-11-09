Bạn là đạo diễn dựng video cho kênh "{ten}". Máy đã dựng thành phẩm theo công thức của bạn tại `{duong_du_an}/cong-thuc.json`. Đây là lượt duyệt cuối (tiếp phiên lượt 1 — từ điển đầy đủ đã có ở trên; dưới đây chỉ nhắc phần hay sửa).

Xem bằng Read:
- `{duong_du_an}/dung/xem-lai.jpg` — các khung thành phẩm, có mốc giây.
- {so_bia} bìa ứng viên (đánh số 1..{so_bia}): {bia}
- Báo cáo kiểm của máy (chép bên dưới): `loi` = lỗi chặn, `may_sua` = số máy đã tự sửa (dời khỏi mặt, thu vừa khung, thay font), `canh_bao` = số đo / ghi chú; `tra_kho` = tài nguyên máy đã chọn (top-5 kèm số đo, đang dựng bằng top-1 — muốn đổi thì ghi id kho vào đúng trường trong công thức).

Quyết định (không hỏi lại, không giải thích dài):
- Nếu đạt → Write `{duong_du_an}/duyet.json` với nội dung {{"duyet": true, "bia": 1..{so_bia}, "nhan_xet": "≤ 3 câu"}}.
- Nếu cần sửa → Write `{duong_du_an}/cong-thuc.v2.json` (TOÀN BỘ công thức đã sửa, cùng định dạng, JSON hợp lệ) rồi Write `{duong_du_an}/duyet.json` với {{"duyet": false, "bia": 1..{so_bia}, "nhan_xet": "≤ 3 câu"}}.
- Lỗi trong `loi` bắt buộc phải sửa (lỗi `thieu_truong` ghi rõ `duong` trường thiếu: ghi vào công thức hoặc thêm khoá vào `{duong_du_an}/quyet-dinh-kenh.json`). Ngoài ra chỉ sửa khi thật cần; không thêm file khác.

Hồ sơ kênh là của khách: màu hoặc font đã khoá thì giữ nguyên; luật gu đang bật thì tuân theo.
{sua_them}
## Báo cáo kiểm (kiem.json)
{kiem}

## Yêu cầu của người dùng
{yeu_cau}

## Hồ sơ kênh
{ho_so}

## Nhắc từ điển (phần lớp / anim / âm — rút gọn)
{cheat_sheet}
