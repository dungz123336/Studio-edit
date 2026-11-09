<!--
  © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
  Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
  Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
-->
# Cài đặt

## 1. Chép skill vào máy
| Mac | Windows |
|---|---|
| `~/.claude/skills/tro-ly-edit-video/` | `%USERPROFILE%\.claude\skills\tro-ly-edit-video\` |

Bộ cài (`CAI DAT - Windows.cmd` / `CAI DAT - Mac.command` ở thư mục ngoài) làm bước này; cài lại / nâng cấp giữ nguyên
hồ sơ kênh (`nao/ca-nhan/`), bài tự học (`nao/kien-thuc/cua-toi/`), cấu hình máy (`cau-hinh.json`), thẻ bản quyền.
Mở Claude Code, gõ `/tro-ly-edit-video` — nếu hiện tên là đã nhận.

## 2. Bác sĩ máy — một lệnh cài mọi thứ

Cần trước: **uv** (Mac `brew install uv` — Mac phải có Homebrew · Windows `winget install astral-sh.uv`). Rồi:
```bash
uv run --python 3.12 --no-project ~/.claude/skills/tro-ly-edit-video/studio/bac_si.py --sua
```
Windows (PowerShell): `uv run --python 3.12 --no-project $env:USERPROFILE\.claude\skills\tro-ly-edit-video\studio\bac_si.py --sua`

Bác sĩ máy kiểm và tự sửa đúng các mục Studio hiện ở góc dưới trái: ffmpeg (winget `Gyan.FFmpeg` / `brew install ffmpeg`),
uv, môi trường Python `.venv` (Python **3.12**), thư viện đúng phiên bản (`yeu-cau-win.txt` / `yeu-cau-mac.txt` / `yeu-cau-linux.txt`),
nhận dạng giọng nói, kho tài nguyên sạch, bộ quà tặng, Git (Windows), Claude Code, đăng nhập Claude, bản quyền, dung lượng ổ,
thư mục dự án ngoài OneDrive, trình duyệt cho lớp web 3D, đo tốc độ máy, tăng tốc phần cứng. Chạy lại nhiều lần cũng an toàn.

Khác biệt theo máy (gom ở `scripts/nen_tang.py` + `v3/chung.py`):

| Việc | Mac Apple Silicon | Windows | Mac Intel / Linux |
|---|---|---|---|
| Nhận dạng giọng (cục bộ) | faster-whisper (CPU) | faster-whisper — GPU NVIDIA nếu có, không thì CPU | faster-whisper (CPU) |
| Tăng tốc dựng | VideoToolbox (nếu ffmpeg có) → CPU | NVIDIA NVENC → Intel QSV → AMD AMF → CPU | CPU |
| Tách người khỏi nền | MODNet (onnxruntime, CoreML/CPU) | MODNet (onnxruntime-directml — mọi card) | MODNet (onnxruntime CPU) |
| Kho mặc định | `~/Movies/VideoKit-Free` | `~/Videos/VideoKit-Free` | `~/Videos/VideoKit-Free` |

Kiểm lại bất cứ lúc nào: `.venv/bin/python scripts/nen_tang.py` (Windows: `.venv\Scripts\python scripts\nen_tang.py`).
Hộp Máy trong Studio có "Chỉ CPU" (tắt mọi tăng tốc phần cứng khi card lỗi) và số luồng dựng.

## 3. Kho tài nguyên
Gói đã kèm kho sạch bản quyền (`tai-nguyen/`: font OFL, tiếng động, nhạc, nền, LUT tự tổng hợp) — bác sĩ máy tự nhận, không cần
chuyển đi đâu. Bộ quà tặng ~10 GB (link trong thư giao hàng): giải nén vào Tải xuống / Desktop / Documents / Movies / Videos,
bác sĩ máy (hoặc `scripts/kit.py tim-bo-mua --ghi`) tự tìm và ghi `kho.bo_mua` vào `cau-hinh.json`. Cấu trúc kho:

```
VideoKit/
├── fonts/        font có dấu tiếng Việt (.otf .ttf)
├── sfx/          tiếng động ngắn (.mp3 .wav)
├── music/        nhạc nền
├── grids/        ảnh nền lưới
├── overlays/     lớp phủ hạt phim, ánh sáng
├── luts/         .cube — chỉ dùng khi quay D-Log
├── characters/   ảnh nhân vật tách nền
└── titles/       mẫu title
```

Mac: CapCut chạy sandbox, chỉ tự đọc được `~/Movies` — muốn project CapCut xuất ra thấy file kho thì để kho trong `~/Movies`.

Soát kho:
```bash
~/.claude/skills/tro-ly-edit-video/.venv/bin/python ~/.claude/skills/tro-ly-edit-video/scripts/kit.py
```

### Gợi ý nguồn
- Font Việt miễn phí thương mại: Google Fonts (Be Vietnam Pro, Bricolage), Fonts.vn.
  **Đừng dùng font bản dùng thử** — nó nhúng chữ quảng cáo hiện đè lên video.
- SFX/nhạc: Pixabay, Mixkit, YouTube Audio Library (kiểm tra giấy phép trước khi bán video).
- Bộ preset trả phí (Edit không khó và tương tự) dùng được, nhưng chỉ cho chính mình, không phát tán lại.

## 4. Tự chỉnh theo mình
Gu của kênh (font, màu, cỡ chữ, phụ đề, hoạt ảnh, bìa) nằm ở `nao/ca-nhan/<kênh>/quyet-dinh.json` — **AI viết và sửa theo
góp ý của bạn trong Studio**, không sửa tay. Máy không có số thẩm mỹ riêng.
Cấu hình MÁY ở `cau-hinh.json` (hộp Máy trong Studio có giao diện cho phần lớn):

| Khoá | Sửa gì |
|---|---|
| `kho.duong_dan`, `kho.bo_mua` | Kho ở chỗ khác / bộ quà tặng |
| `v3.du_an` | Thư mục dự án (mặc định `~/Videos/studio-du-an`; để ngoài OneDrive) |
| `song_song`, `tang_toc` | Số luồng dựng ("" = tự động) · `auto` / `cpu` (chỉ CPU) |
| `don_rac` | Tự dọn rác: bật/tắt, ổ trống tối thiểu (GB), giữ cache mấy ngày |
| `ffmpeg_im_toi_da_giay` | ffmpeg không tiến trong N giây = treo (mặc định 300) |
| `capcut.tu_dong`, `capcut.thu_muc_du_an` | Tự xuất CapCut khi giao (`neu_co` / `luon` / `tat`) · thư mục project CapCut |
| `ban_giao.thu_muc` | Nơi trả video |

Xem cấu hình đang hiệu lực:
```bash
~/.claude/skills/tro-ly-edit-video/.venv/bin/python ~/.claude/skills/tro-ly-edit-video/scripts/config.py
```

## 5. Dùng
Mở Studio (lối tắt "Studio dựng video", hoặc `.venv/bin/python studio/mo.py`) → chọn kênh → Việc mới → thả video → gõ yêu cầu.
Hoặc kéo file quay vào Claude Code rồi bảo "dựng video này". Luồng: đọc → quyết định kênh (lần đầu) → công thức → dựng → kiểm →
giao video kèm ảnh bìa (+ project CapCut nếu có CapCut).

## Giấy phép và bản quyền
Skill này gồm mã nguồn, quy trình và thông số. Font, nhạc, SFX, LUT, preset trong kho
của bạn giữ giấy phép riêng của chúng — **không được đóng gói bán lại kèm skill**.
Video làm ra phải tự kiểm giấy phép nhạc trước khi kiếm tiền.
