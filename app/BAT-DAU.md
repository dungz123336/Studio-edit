<!--
  © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
  Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
  Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
-->
# Bắt đầu trong 5 phút

## Cài (Windows 10/11 hoặc Mac chip Apple)
Cách nhanh nhất: bấm đúp bộ cài ở thư mục ngoài (`CAI DAT - Windows.cmd` · Mac: chuột phải `CAI DAT - Mac.command` → Mở).
Bộ cài chép skill vào `~/.claude/skills/tro-ly-edit-video`, cài uv + Python 3.12, rồi gọi **bác sĩ máy** cài phần còn lại.
Cài tay (khi bộ cài không chạy được):
1. Chép thư mục `tro-ly-edit-video` vào thư mục skills của Claude Code
   (Mac `~/.claude/skills/` · Windows `%USERPROFILE%\.claude\skills\`).
2. Cài uv (Mac `brew install uv` · Windows `winget install astral-sh.uv`) rồi chạy bác sĩ máy — đúng lệnh bộ cài và Studio dùng:
```bash
uv run --python 3.12 --no-project ~/.claude/skills/tro-ly-edit-video/studio/bac_si.py --sua
```
   Bác sĩ máy tự cài ffmpeg, môi trường Python `.venv`, thư viện (skia-python, onnxruntime…), model nhận giọng, kho tài nguyên sạch
   (`tai-nguyen/` trong gói — không phải chuyển đi đâu). Chạy lại nhiều lần cũng an toàn; trong Studio là nút "Tự sửa tất cả".
3. Bộ quà tặng ~10 GB (link trong thư giao hàng): tải về, giải nén vào thư mục Tải xuống — bác sĩ máy tự tìm (`kit.py tim-bo-mua`).
4. Kích hoạt bằng mã nhận khi mua (mỗi mã dùng cho số máy giới hạn; đổi máy thì `ban_quyen.py huy` ở máy cũ):
```bash
~/.claude/skills/tro-ly-edit-video/.venv/bin/python ~/.claude/skills/tro-ly-edit-video/scripts/ban_quyen.py kich-hoat <MÃ>
```
   (Windows: `.venv\Scripts\python.exe scripts\ban_quyen.py kich-hoat <MÃ>` trong thư mục skill — hoặc nhập mã ở góc dưới trái Studio)
5. Mở Studio: `.venv/bin/python studio/mo.py` (bộ cài đã tạo lối tắt "Studio dựng video" ngoài Desktop) → chọn kênh → Việc mới →
   thả video vào ô chat → gõ yêu cầu. Hoặc mở Claude Code, kéo file quay vào, gõ: **"dựng video này"**.

Xong. Chi tiết ở `CAI-DAT.md`. Linux: chưa có bộ cài và chưa hỗ trợ xuất CapCut (CapCut không có bản Linux).

## Nói thế nào cho ra việc

Cứ nói tiếng Việt bình thường, không cần cú pháp gì.

| Muốn gì | Nói |
|---|---|
| Dựng một video | "dựng video này" |
| Dựng nhiều video | "làm 4 video này, chia ra thư mục, thumb làm luôn" |
| Cắt kỹ hơn | "cắt kỹ nhất, bỏ hết ừm à với chỗ nói lại" |
| Chỉ cắt, không hiệu ứng | "chỉ cắt khoảng lặng thôi, đừng thêm gì" |
| Đổi phong cách | "làm nhanh gọn, ít chữ" · "nhiều hiệu ứng vào" |
| Chỉ làm ảnh bìa | "làm ảnh bìa cho video này" |
| Sửa chỗ cụ thể | "đoạn 1p17–1p20 còn lặng, cắt đi" |
| Xem trước ý tưởng | "biên kịch trước cho anh xem rồi hẵng dựng" |
| Máy yếu, cần nhanh | "làm chế độ nhanh" |
| Kiểm lại | "kiểm tra lỗi lại 3 lần trước khi giao" |

Không vừa ý thì nói thẳng — "chữ xấu", "nhạc to hơn lời", "cảnh trám không có" —
rồi bảo làm lại. Nói rõ chỗ sai luôn nhanh hơn tả chung chung.

## Nó sẽ làm gì
1. **Đọc** — nhận dạng giọng nói, xem hình, tìm chỗ nói lại và khoảng lặng
2. **Quyết định kênh** — lần đầu với một kênh, AI viết `quyet-dinh.json` (font, màu, cỡ chữ, phụ đề, hoạt ảnh…) cho kênh đó; góp ý của bạn sửa vào đây
3. **Biên kịch + dựng** — AI viết công thức, máy dựng: cắt, phụ đề, chữ, cảnh trám, nhạc và SFX cân theo số đo
4. **Kiểm** — đồng bộ hình/tiếng · hình · âm lượng (máy chỉ đo và chặn lỗi vật lý, không tự chọn gu)
5. **Giao** — thư mục riêng, video + ảnh bìa; xuất project CapCut nếu máy có CapCut

Toàn bộ chạy **trên máy bạn**. Video không được gửi đi đâu.

## Tự chỉnh theo kênh mình
Nói với AI trong Studio ("chữ to hơn", "đổi màu nhấn sang xanh") — AI sửa `quyet-dinh.json` của kênh. Cấu hình máy (kho, thư mục
dự án, số luồng, chỉ CPU, dọn rác) ở hộp Máy trong Studio hoặc `cau-hinh.json`. Xem cấu hình đang chạy:
```bash
~/.claude/skills/tro-ly-edit-video/.venv/bin/python ~/.claude/skills/tro-ly-edit-video/scripts/config.py
```

## Hỏng thì xem đâu
| Triệu chứng | Chỗ xem |
|---|---|
| Góc trái dưới Studio có mục đỏ | bấm "Tự sửa tất cả" (bác sĩ máy) |
| Báo thiếu font / thiếu kho | `scripts/kit.py` hoặc bác sĩ máy mục "Kho tài nguyên" |
| Nhận dạng giọng lỗi | `CAI-DAT.md` mục 2 — phải Python 3.12 (bác sĩ máy tự cài) |
| Máy chậm, nóng | hộp Máy → "Chỉ CPU" / giảm số luồng |
| Ổ đầy | hộp Máy → khối Dung lượng → dọn rác |
| CapCut không mở project | mở CapCut, tạo một dự án trống, thoát, xuất lại; hoặc dùng gói tách lớp `7-capcut/HUONG-DAN.txt` |
| Nhạc át lời | `nao/goc/5-am-thanh.md` |
