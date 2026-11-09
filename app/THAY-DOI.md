<!--
  © 2026 Studio dựng video. STUDIO-DUNG-VIDEO · BAN QUYEN.
  Phần mềm có bản quyền. CẤM sao chép, sửa đổi, dịch ngược, phân phối lại dưới mọi hình thức.
  Mọi hành vi dùng/chia sẻ trái phép đều bị truy vết theo mã bản quyền gắn trong bản giao.
-->
# Nhật ký thay đổi

Mỗi bản phát hành ghi ở đây (mới nhất trên cùng). `cap_nhat.py` in mục này cho người dùng khi có bản mới.

## 1.2.21 — 07/11/2026 — MÁY ĐO, AI QUYẾT · DỌN RÁC · CHỈ CPU · HDR · CẬP NHẬT AN TOÀN · GÓI SẠCH
**Nguyên tắc: máy đo → báo số → AI/khách quyết → máy thực thi + chặn vật lý. Máy không còn gu riêng.**
- QUYẾT ĐỊNH KÊNH `quyet-dinh.json`: AI viết một lần cho mỗi kênh (tóm tắt báo "KÊNH CHƯA CÓ QUYẾT ĐỊNH" ở việc đầu), góp ý của bạn sửa vào đây.
  Thay mọi mặc định thẩm mỹ từng hàn trong máy (cỡ chữ, viền, bóng, thẻ, phụ đề, hoạt ảnh, mức nhạc, bìa, màu nhấn tự chế, chấm gu font).
  Hợp đồng dữ liệu `hop_dong` kiểm công thức + quyết định; thiếu trường → báo đúng đường trường cho AI (`thieu_truong`), không tự điền.
- Bìa: số bìa = số phương án AI viết, thiếu thiết kế → trả lỗi (hết bìa mặc định, hết tự xoay màu); `bia-kiem.json` ghi chồng chữ, số dòng, hộp thật.
- Chữ 3D và mọi mẫu chữ giữ đúng cỡ AI ghi (chỉ thu khi tràn, có `may_sua`); lớp w,h ≥ 0,9 là toàn khung (không bị vùng an toàn thu còn 70 %); font thiếu dấu báo `may_sua`; luật nghề chỉ in số đo, mặc định tắt.
**Máy khách — hết "nổ", hết treo, hết mất card**
- Máy không có `nvidia-smi` (AMD/Intel/Mac) không còn dừng ở bước đọc; Mac dùng VideoToolbox; RAM Mac đọc thật.
- ffmpeg chạy theo tiến độ thật: không tiến trong N giây (`ffmpeg_im_toi_da_giay`, mặc định 300) = treo → tắt, nhớ lỗi — hết chờ 1–2 giờ.
- Lỗi phần cứng nhớ ĐÚNG LOẠI (giải mã ≠ mã hoá) và CÓ THỜI HẠN tăng dần (1 giờ → 24 giờ) thay vì vĩnh viễn; "Đo lại máy" thử lại ngay. "Chỉ CPU" trong hộp Máy.
- Tách người: GPU hỏng/treo → tự chuyển CPU trong vài chục giây (trước treo tới 45 phút); bìa không tách được vẫn vẽ.
- HDR (iPhone HLG/PQ) và nguồn 10-bit tonemap về BT.709 trước khi dựng — hết nhạt màu / bạc màu. Yêu cầu 4K/60 fps được tôn trọng.
- Bản kê NĂNG LỰC MÁY đo bằng việc thật (mã hoá 1080×1920, giải mã HEVC 10-bit, tách người, nghe) thay "hạng máy"; đo lúc máy bận không hạ hạng oan; hộp Máy hiện bảng số.
- `phan-cung.json` đọc-sửa-ghi có khoá (hết hai bộ ghi giẫm nhau, hết mất cập nhật khi 2 việc song song).
**Dọn rác (khách báo máy đầy)**
- Khối DUNG LƯỢNG trong hộp Máy: thanh ổ trống, 3 nhóm (tái tạo được / cache dự án đã đóng / đầu ra trùng), dọn từng nhóm; tự dọn khi ổ thấp trước khi dựng và mỗi 6 giờ; xoá việc có ô xoá cả dự án + bản tải lên.
- Chặn từ gốc: sprite PNG xoá ngay sau khi khúc dựng xong; lớp SAU NGƯỜI không nướng ảnh từng khung (210 → 12 ảnh/lớp, người cắt từ base ngay trong ffmpeg, dựng nhanh gấp đôi);
  thành phẩm không còn chép 3 lần (`giao/` chỉ trỏ sang Downloads); base/khúc cũ dọn theo ngày; `server.log` xoay; cache cửa sổ giới hạn; `.ban-cu` giữ 1 bản.
**Soạn việc Đơn giản / Đầy đủ**
- Việc mới có công tắc Đơn giản / Đầy đủ. Đơn giản là các khối thẻ lớn: video chính, tư liệu phụ, video mẫu, yêu cầu chung; mỗi tệp một ghi chú đi nguyên văn cho AI, thứ tự clip chính đổi được. Đầy đủ là ô chat như cũ; đổi qua lại không mất tệp và ghi chú.
- Video mẫu thêm được bằng link TikTok, Facebook, YouTube (máy tải về, vẫn ghi chú như tệp). Video và ảnh đưa vào hiện ảnh thu nhỏ, ở cả form lẫn ô chat.
- Chỉ là giao diện: cơ chế dựng không đổi. Máy đã dùng Studio giữ Đầy đủ, khách mới vào Đơn giản. Đoạn chat đang làm cũng bật được Đơn giản để sửa tiếp video; gửi xong form đóng, ô chat quay lại.
**Studio**
- Cập nhật an toàn: lỗi tải/giải nén không khoá khách vĩnh viễn (đếm hỏng lưu đĩa, hoãn 24 giờ), chờ cổng rảnh thật khi khởi động lại, tắt mọi tiến trình con (kho, daemon nghe, trình duyệt lớp web); tắt Studio là tắt sạch việc.
- Số việc dựng cùng lúc không còn trần 4 (tự động theo luồng/RAM, hoặc bạn đặt); bỏ đo token/trần tiền (Claude Code chạy nền); model nhập tự do.
- Tiếp tục từ điểm dừng: chạy lại không giải mã lại thứ đã có (proxy, lời, mặt, khung, alpha, base, khúc).
**Học mẫu**: một lần giải mã cho mọi khung, cache OCR/cửa sổ/mặt nạ dùng chung, MODNet một lần — mẫu 72 s từ 14 phút xuống ~4 phút (máy có card chạy được nhanh hơn);
  kiểu vào đọc từ hình học hộp chữ (pop/slide đúng 0,2 → 0,7); chữ web/giao diện không bị bỏ mà đánh dấu `nguon_nghi_ngo` để AI quyết; bản ghi mang SỐ ĐO, không mang gu.
**Kho**: SQLite `kho.sqlite` thay jsonl (lần mở đầu tự nhập 3 tệp cũ, giữ nguyên tệp cũ để lùi bản được; lần lập đầu đo lại ~2.500 tệp âm một lần, 1–2 phút); tìm trả top-5 kèm số đo cho AI chọn;
  "whoosh rất nhẹ" ra whoosh (trước ra tiếng máy ảnh); từ độ to ràng theo peak/rms; gói kho video chỉ còn bảng số đo, không câu tra cố định.
**CapCut**: mẫu gieo chỉ chép cấu hình (không vật liệu của bạn); `draft_root_path` posix; rỗng hoá keyframes/relationships/draft_materials (hết id treo); lớp sau người có track "Người (cắt từ base)";
  hoạt ảnh phụ đề AI chọn được áp; viền phụ đề theo quyết định kênh; dự án dựng bằng bản cũ → báo rõ, chạy `nhanh tron` lại trước khi xuất. Linux: chỉ gói tách lớp.
**Đóng gói / bộ cài / tài liệu**: gói không tệp ẩn, không đường dẫn máy người bán/máy khác (soát mọi tệp văn bản), gỡ 11 script 1.x không dùng; bộ cài Windows kiểm lỗi winget/robocopy, ổ trống ≥ 6 GB, mở Studio sau khi đăng nhập; Mac yêu cầu Homebrew rõ; `encoding="utf-8"` mọi `open()`; tài liệu khớp bác sĩ máy.
**Sau cập nhật**: bác sĩ máy đo lại tốc độ một lần (≤ 60 s, chỉ khi máy rảnh); lần dựng đầu mỗi dự án cũ vẽ lại sprite/base một lần (khoá cache đổi).
**Bộ thử**: `thu_nhanh.py` (biên dịch + nạp 97 mô-đun + 18 kiểm hàm), `nen_that.py` (sự thật nền 10 công thức + ảnh chuẩn), hồi quy đặt mẫu theo mặt + quyết định mẫu + mốc 3,32 phút máy/phút (bản này đo 2,61).

## 1.2.20 — 03/11/2026 — HỌC VIDEO HAI TẦNG · CHUYỂN ĐỘNG CÓ CHIỀU SÂU · TIẾNG KHỚP HÌNH KHI NỐI NHIỀU CLIP
**Học video mẫu — học được cả chuyển động, bố cục và trình tự (không còn chỉ thống kê)**
- Tầng 1 BẢN GHI THI CÔNG: máy đo MỌI vệt chữ của mẫu (không giới hạn 24 sự kiện), gom thành cụm (nhãn → từ khoá → cảm xúc), mỗi dòng ghi cỡ/màu/đậm/HOA,
  góc xoay, trễ so với dòng đầu, vào/ra ở mức đường cong (hướng, quãng px, thời lượng, ease, vượt đích, nhoè theo hướng), nằm trước/sau người, neo so với mặt,
  cụm bám từ nào của lời; thêm cắt/punch-in/flash/light-leak của nền và tiếng động bật đúng lúc lớp vào. Viết thẳng bằng ngôn ngữ lớp của máy dựng → dựng lại được.
- Tầng 2 NGỮ PHÁP: từ bản ghi rút ra CÔNG THỨC CỤM có tên và tham số (gộp các cụm cùng chữ ký, số là trung vị) + luật đặt so với mặt, nhịp theo lời, vai màu/chữ,
  nền, tiếng động — kèm khung JSON `khoi` chép được. Chữ của mẫu KHÔNG mang theo. Bài học đang bật đưa ngữ pháp vào tóm tắt; AI tự chọn công thức nào cho câu nào.
- Vòng kiểm: máy dựng lại bản ghi lên chính video mẫu, đặt cạnh gốc từng cụm, đo lệch vị trí (IoU), đúng giờ, chữ đọc được → `doi-chieu.json` + ảnh.
- Dải chữ cùng vị trí nhưng nhiều cỡ (nhãn nhỏ + từ khoá lớn) không còn bị coi là phụ đề; chữ in trên áo lặp lại bị loại; chữ OCR rác bị loại.
**Sửa lỗi bộ học cũ**
- Góp ý ("chữ to hơn") giờ sửa cả vào bài học đang bật — trước chỉ sửa style-spec của hồ sơ trong khi máy dựng ưu tiên bài học → video không đổi.
- Số chữ phụ đề tối đa đo bằng từ nhưng máy dựng hiểu là ký tự → phụ đề bị băm cụm 8 ký tự; viền thẻ đo tỉ lệ 0..1 nhưng áp thành px; neo theo mặt lệch nửa
  chiều cao chữ (đo mép, áp tâm). Lưu bài: không ghi đè bài trùng tên; bản sắc kênh lấy đúng spec cuối; thứ tự ảnh soi/cận chữ in đúng (2 trước 10).
**Chuyển động**
- `anim.nhoe_dong` (0..4): nhoè THEO HƯỚNG chuyển động, vệt dài theo tốc độ thật từng khung (rơi → vệt dọc, trượt → vệt ngang, chậm lại thì ngắn).
- Khối chữ: từng dòng `xoay`/`dx`/`dy`/`tre`/`anim` riêng (nhãn fade, từ khoá rơi có nhoè, cảm xúc trượt ngang nghiêng). Chữ nổi `noi_3d.mau2` cạnh chuyển sắc.
- Khối chữ dòng đầu chữ HOA có dấu (Ấ/Ộ/Ừ) không còn bị cắt mất dấu.
**Tiếng động không còn giật mình (khách phản ánh ở 1.2.19)**
- Trước: mức tiếng động đặt theo LUFS tích phân của tệp; tiếng click/gõ phím 0,1 s đo −70 LUFS (đuôi lặng) → máy tăng +30 dB, nổ to hơn giọng rồi
  limiter bóp — nghe "xẹt", giật. Nay: đặt theo RMS đỉnh 50 ms của tệp so với RMS đỉnh của GIỌNG (cùng thước), tối đa −3 LU dưới giọng,
  đỉnh thật không vượt đỉnh giọng −1 dB, mờ đầu 8 ms; mặc định −10 LU. Máy chỉ đo và chặn vật lý — chọn tiếng gì vẫn là việc của AI.
- Mỗi mốc tiếng ghi số đo (mức tệp, gain, mức sau) vào kế hoạch để kiểm lại.
- Số lượng và kiểu tiếng động do AI QUYẾT theo từng video (ý đồ ghi ở `y_do.tieng_dong`: có/không, bao nhiêu, họ nào, vì sao). Máy không có
  số đúng chung và không áp ngưỡng — sau chuẩn hoá chỉ BÁO lại phân bố thật (số mốc, mốc/10 s, họ theo chữ ký vật lý của kho, chuỗi cùng họ dài nhất,
  mốc chồng nhau, khoảng không tiếng dài nhất, tệp lặp) để AI tự soi với ý đồ. Hết kiểu "video nào cũng vụt vụt".
- Bản trộn âm cache theo cả phiên bản mã trộn (trước chỉ theo kế hoạch → cập nhật app xong, dựng lại vẫn dùng bản trộn cũ). Trần đỉnh thật −2 dBTP (trước −1,5; AAC vượt > 0 dBFS).
**Máy khác nhau**
- Tách người ảnh đơn chờ lượt card tối đa 60 s (card treo DML) rồi chạy CPU, không treo 15 phút.
- Học từ link dùng công cụ tải đi kèm gói (taivideo.py) — trước trỏ vào skill cá nhân của máy phát triển.
- Lưu bài học: spec AI viết sai khuôn thì không lưu (báo rõ) — trước lưu bừa rồi lúc dựng bỏ cả bản sắc. Bật/tắt bài không đổi thứ tự "bài mới nhất".
**Tiếng khớp hình**
- Nối nhiều clip / nguồn có khoảng hở tiếng: tiếng không còn trôi sớm ~100 ms về cuối (concat chèn im lặng đúng mốc; tách WAV bám mốc thời gian).

## 1.2.19 — 01/11/2026 — KHO NGHE ĐƯỢC · KHÔNG DỪNG GIỮA CHỪNG · CAPCUT 9.7 · GIỌNG AI ỔN · CHẠY ĐƯỢC NHIỀU LOẠI MÁY
Chỉ THÊM và SỬA LỖI — mọi cơ chế dựng của 1.2.18 giữ nguyên (tư duy, tốc độ, lớp sau người, học phong cách).
**Nhạc & SFX hết "một màu" (kho có tai)**
- Mỗi tiếng trong kho được máy đo chữ ký vật lý (cao/trầm · bật ngay/dâng dần · dài · ngân/khô · chuỗi · nhiễu/âm sắc) + vân tay âm; AI thấy chữ ký và số video đã dùng để tự chọn.
- Hiểu từ tượng thanh Việt: "tinh", "bùm", "vút", "tách", "bíp", "rè"… → tra theo số đo (trước: "tinh tinh" ra tiếng con vượn).
- Điểm tra cứu ngang nhau → tệp ÍT DÙNG trên máy thắng; lịch sử tránh lặp 30 video (trước 5). Gói SFX mỗi nhóm 8 ứng viên khác họ từ nhiều câu tra (trước 1 câu cố định, 5 tệp). Nhạc 8 bài (thêm 3 bài ít dùng cùng năng lượng).
- Đo khô 30 dự án: 187 → 462 tệp SFX khác nhau, 5 tệp hay dùng nhất 20 % → 4 %, nhạc 1 → 22 bài.
- Tiếng của mẫu đồ hoạ (`am.vao:"tu_dong"`) xoay vòng, không dài hơn hoạt ảnh. AI tra cả kho bằng `python v3/kho/tim.py sfx "<tính chất>"`.
- Tab Kho: kéo thẻ thả thẳng vào ô chat (không mở cửa sổ mới), chữ ký tiếng, lọc "chưa dùng", nút ≈ "tiếng giống", nút "Gắn nghĩa AI" cho kho riêng (ước tiền trước). Bộ đi kèm gói có sẵn nghĩa AI (ai-nghia.json) — máy khách không còn tra theo tên tệp.
**Không dừng giữa chừng, không đơ, chạy lại không làm lại**
- Hàng chờ ghi đĩa: Studio tắt/mở lại vẫn chạy tiếp; lời gốc (kèm đường dẫn video) lưu vào việc → "tiếp tục" sau khi mất phiên vẫn biết việc.
- Dừng / tắt Studio giết cả tiến trình dựng tách rời (trước đây sống mồ côi giữ máy). Lúc mở lại tự dọn tiến trình mồ côi.
- Watchdog 3 tầng: bước máy nặng im 45 phút → tắt, ghi lỗi, AI chạy lại; tách người im 5 phút (GPU kẹt) → tắt, thử cách khác; Claude im 45 phút → ngắt lượt, tự nhắc. Cảnh báo ĐỨNG IM không còn báo giả khi đang chờ mạng/chờ lượt.
- Chờ mạng tới 4 giờ và nhả chỗ máy; hết lượt Claude nhả chỗ cho việc khác. Phần máy nặng của nhiều video chạy tuần tự theo chỗ máy (hết giẫm nhau gây CUDA kẹt).
- ffmpeg nhớ nguồn nào lỗi tăng tốc phần cứng (theo codec + cỡ) — hết 70 lần thử CUDA hỏng mỗi việc. Whisper không gọi HuggingFace khi mất mạng.
- Trần mỗi lượt: tiền (mặc định 25 USD) và số bước (khi Claude Code có cờ); ⚡Làm nhanh mặc định Sonnet. stderr Claude lưu `claude-<việc>.log`; lỗi CLI dịch sang tiếng Việt.
**Giọng nói AI (aizening)**
- Dán khoá: kiểm với máy chủ trước khi lưu (dán nhầm mã bản quyền → báo ngay). Chờ theo độ dài văn bản (tới 15 phút), không còn "Failed to fetch". Mẫu giọng wav/m4a/tên có dấu đều được (máy chuẩn hoá mp3 ≤ 60 s). Tệp trả về là WAV đội lốt mp3 → chuyển mp3 thật. Lỗi mạng tách khỏi "chưa có khoá".
**CapCut 9.x**
- Mẫu gieo project lấy đúng BẢN CapCut đang cài (9.7 bố cục phẳng, không Timelines/); lệch bản → tự gieo lại. Mọi lần xuất kèm GÓI TÁCH LỚP (phu-de.srt + từng lớp .mov trong suốt + âm thanh + HUONG-DAN.txt) dùng được với CapCut 10.x, Premiere, DaVinci.
**Bắt buộc cập nhật**
- Có bản mới → hộp thoại hiện giữa màn hình, Studio khoá gửi việc tới khi cập nhật (đặt `cap_nhat_tuy_chon: true` trong cai-dat.json nếu người bán muốn tắt).
**Ô chat**
- Thả video: ô chat gợi "Bạn đã đưa vào: … Bạn muốn một video như thế nào, để làm gì?" — không ghi vẫn dựng (AI tự quyết theo hồ sơ kênh).
**Bớt "một màu"**
- Font AI bỏ trống → lấy từ gói kho của chính video (ít dùng trước), không còn một font "nhà". Bản sắc nháp của kênh chỉ rút từ trường AI đã ghi (không rút số máy điền). 20 phong cách nhanh: 3 biến thể bố cục theo hồ sơ. Tóm tắt kho in chữ ký tiếng + số lần đã dùng + mẫu đồ hoạ hồ sơ đã dùng. Hồ sơ mới hỏi 4 câu ngay lúc tạo. Cấu hình mẫu không còn màu/font của người bán.
**Loại máy**
- Mac M1/M2/M3: cài faster-whisper (lõi 1.3 cần) — trước đây không dựng được. Mac Intel / Linux: bộ yêu cầu riêng (không DirectML). Windows ARM: báo rõ chưa hỗ trợ.
- Tên người dùng Windows có dấu (thư mục người dùng có dấu): OpenCV đọc/ghi và nạp model qua đường an toàn — hết mất phát hiện mặt, bảng khung, bìa.
- Kiểm ổ trống trước khi đọc/dựng (≥ 3 × video nguồn). Bác sĩ máy thêm: hệ máy, thư mục kho mua thêm còn không, dự án trong OneDrive, trình duyệt cho lớp web, ổ dự án.
- Mở Studio thiếu thư viện bắt buộc (sau cập nhật) → tự sửa, chặn gửi việc với lời rõ tới khi xong. Bìa gửi AI xem bản 540 px (rẻ hơn ~12×). Gói chẩn đoán một nút (bảng Máy). Dọn dữ liệu theo tuổi; danh sách việc nhớ theo mtime (UI nhẹ hơn).
**Tab Kho**
- Nút ⤢ "Đẩy rộng kho": kho chiếm ~60 % màn hình ngay tại chỗ, thanh hồ sơ tự thu, kéo thẻ thả vào ô chat vẫn được; Esc / đổi tab / bấm lại → thu về. Không còn mở cửa sổ mới. Hàng nút lọc (loại, công dụng) lướt ngang: lăn chuột, kéo tay, thanh cuộn mảnh.
**Rà soát toàn bộ mã 1.2.19 (4 nhóm kiểm độc lập, sửa trước khi phát hành)**
- Watchdog không giết nhầm bước đang chờ hợp lệ: chờ lượt card, chờ lượt máy nặng, ffmpeg 4K dài, Whisper video dài đều ghi nhịp tim vào nhật ký; tách người trên CPU trần 12 giờ (GPU 4 giờ). PID trong tệp trạng thái bị hệ tái dùng sau khởi động lại → không giết tiến trình lạ.
- Nhớ lỗi tăng tốc phần cứng chỉ khi CPU dựng được VÀ lỗi đúng là hwaccel (ổ đầy/filter hỏng không làm tắt hwaccel vĩnh viễn); bác sĩ máy đo lại tốc độ → xoá nhớ, thử lại. Kiểm ổ trống đọc đúng video nguồn của phiếu.
- Dừng: việc đang xếp hàng bị huỷ không tự sống lại khi mở Studio; việc đang chờ lượt/chờ mạng/chờ chỗ dừng được; tách người sớm cũng bị tắt. Ép cập nhật không chặn trả lời Claude đang hỏi / việc đang dở; cài bản mới hỏng 2 lần → tạm cho dùng 24 giờ (không khoá chết), ghi lý do.
- Giọng nói: máy chủ bận (5xx/429) không bị coi là "khoá sai" (vẫn lưu khoá, báo chờ); lưu khoá đủ thời gian kiểm online. Bác sĩ máy không lặp vô hạn khi ổ dự án ngoài bị rút. YuNet (mặt) nạp qua đường ASCII ở cả bìa/khung/động học.
- Kho: từ tượng thanh khớp CÓ DẤU ("ngân" ≠ "ngắn", "đúng" ≠ "đùng", "chuỗi" ≠ "chuối"); từ thường (trong/ngắn/dài/khô…) chỉ là tính chất tiếng khi câu có từ chỉ tiếng; ràng buộc vật lý chỉ áp cho SFX; "ngắn/dài/xoẹt" lọc cứng theo độ dài đo được. Lọc loại/công dụng/độ dài TRƯỚC rồi mới xét bậc ít dùng (bậc không lấy đỉnh của loại khác, ngưỡng không cắt sớm). Kho chưa đo xong → không nhân hệ số (tệp chưa đo không nổi lên). Liệt kê kho 759 → 18 ms (60 mục).
- Gói kho cho video: 8 ứng viên SFX xếp theo điểm khớp (da_dung chỉ là dữ liệu); 3 bài nhạc ít dùng gộp bản sao mp3/wav và chọn ngẫu nhiên ổn định trong tầng ít dùng (10.000 máy không cùng 3 bài đầu bảng chữ); câu tả nhạc của người dùng bỏ phủ định ("không dùng nhạc nền", "nhạc nền nhỏ thôi"). Lịch sử 30 video phủ hết bộ kèm nhỏ → bỏ lọc tránh thay vì trả rỗng.
- Bớt gu của người làm: lời dặn AI về SFX chỉ mô tả dữ liệu (chữ ký, số lần dùng), không còn bảng "chữ nhỏ → tiếng nhỏ, số liệu → ding, hook → dâng"; font dự phòng chọn theo đủ dấu + ít dùng nhất (số đo) thay vì thứ tự chấm; biến thể bố cục của gói phong cách ghi rõ vào may_sua (AI ghi vị trí thì thắng); cấu hình mẫu không còn máy quay của người bán; mô tả hiệu ứng không còn màu cố định.
- CapCut: so bản theo số (10.0 > 9.7); project thiếu app_version → chấp nhận như 1.2.18 (không còn "CHƯA CÓ PROJECT MẪU" oan); phụ đề SRT theo thời gian; tệp đánh dấu ghi UTF-8.
- Đóng gói: biên bản/điều tra nội bộ, CAI-CACH.md không giao; capcut_preset.json bỏ thư mục kho và đường cache máy người bán; quét vết cá nhân trên MỌI tệp văn bản trước khi ký; gói hosting gốc chọn theo số bản và kiểm trước khi đóng.

## 1.2.18 — 24/10/2026 — LỚP SAU NGƯỜI · HỌC ĐƯỢC "CHỮ NẰM SAU ĐẦU"
**Lớp nằm sau người (mới)**
- Mọi lớp (chữ, khối, thẻ, ảnh, video, mẫu, web) thêm `sau_nguoi:true`: máy tách người đúng đoạn lớp cần, phần lớp chồng lên người bị che —
  chữ hook chạy sau đầu, thẻ review nằm sau vai, chữ to sau lưng… như các kênh làm. Lớp sau người được phép chồng mặt (không bị dời).
- Tách người chỉ chạy cho đoạn có lớp sau người (nhiều lớp cùng đoạn tách một lần), chạy trên card khi có (Windows mọi card qua DirectML).
**Học phong cách**
- Bộ học đo thêm: chữ / đồ hoạ trong video mẫu nằm TRƯỚC hay SAU người (và người che bao nhiêu phần khối) → dòng thời gian mẫu ghi
  "nằm SAU người (người che 40% khối)" / "đè TRƯỚC người" cho từng lớp, AI tự quyết áp vào video mới.
- Từ điển công cụ + lời dặn cập nhật tương ứng.
**Kiểm**
- Hồi quy 9:16 trên máy rảnh: ĐẠT, 3,32 phút máy / phút thành phẩm (ngân sách 8).

## 1.2.17 — 24/10/2026 — LÕI MỚI 1.3: NHANH HƠN NHIỀU LẦN · CHỮ SẠCH · 3D · B-ROLL · HỌC PHONG CÁCH · TÁCH NỀN KHÔNG MẤT NGƯỜI · AI TỰ THIẾT KẾ
Giao diện giữ nguyên. Toàn bộ phần dựng bên dưới được viết lại.
**Nhanh hơn**
- Video ~1 phút: khoảng 8–12 phút từ lúc thả video tới lúc giao (trước 30–60 phút). AI chỉ còn ~7 lượt (trước 25–40).
- Bản xem trước nhẹ hơn nhiều lần; không còn dựng nháp; sửa sau khi giao chỉ dựng lại phần đổi (vài chục giây).
- Phụ đề hàng trăm cụm được gộp khi ghép, dựng nhanh gấp 3.
**Chữ đẹp, hết chồng lên nhau**
- Bộ vẽ chữ mới: khoảng cách chữ chuẩn của font, viền và bóng nhiều lớp sạch, chữ gradient, nền pill.
- Chữ nhiều dòng tự giãn dòng theo dấu tiếng Việt (Ể, Ẫ, Ữ…) — dấu dòng dưới không còn đâm vào dòng trên.
- Chữ không che mắt–miệng: máy dời về phía chữ được đặt (trên thì lên, dưới thì xuống) rồi thu nhỏ vừa đủ; phụ đề tự nhường chỗ cho thẻ.
**Tách nền (xoá nền giữ người)**
- Mô hình tách người mới chạy trên card đồ hoạ (mọi card, kể cả đời cũ): giữ tóc, tay, ngón tay; không nhoè, không mất mảng người.
- Chỉ tách đúng đoạn cần dùng (vài giây video mất vài chục giây máy). Ngoài đoạn đó video giữ nguyên.
**AI tự thiết kế, không theo khuôn**
- Mỗi lớp chữ/thẻ/hình: AI tự chọn kiểu dáng, vị trí so với mặt, kiểu hiện ra (bật, trượt, gõ chữ, hiện từng từ…), nhịp, màu.
- Máy chỉ chặn lỗi đo được (che mặt, ra ngoài vùng an toàn, đọc không kịp, chữ chồng chữ, thiếu dấu, âm quá to).
- Tab Học: học cách bố trí, cách chữ hiện ra, đồ hoạ, nhịp theo lời của video mẫu → bài học áp cho mọi video của hồ sơ.
- Khối chữ trộn font (`khoi`): một khối nhiều dòng, mỗi dòng font/cỡ/màu/đậm/nghiêng riêng, dòng chồng sát, lệch so le, từng dòng hiện lần lượt — kiểu tiêu đề 'dòng dẫn mảnh + từ khoá đậm + từ cảm xúc script' của video mẫu tái hiện được.
- Lớp chữ có `nghieng` (độ) khi font không có bản italic.
- Font AI chọn cho chữ tiếng Anh/không dấu được giữ nguyên (chỉ đổi khi font thiếu đúng ký tự của chữ đó); phụ đề và font mặc định kênh vẫn phải đủ dấu Việt.
- Tra font theo mô tả học được: mảnh → font nhẹ thật (light/thin/biến thiên), 'không nghiêng' không ra font italic.
- Font theo TÊN HỌ Google Fonts (1.800 họ, giấy phép mở): AI/người dùng ghi "Montserrat", "Playfair Display"… → máy tự tải bản TTF trọn (đủ dấu Việt), lập chỉ mục, chọn đúng tệp theo độ đậm/nghiêng; `kho tai-font <họ>`.
- 3D phối cảnh cho mọi lớp: xoay quanh trục ngang/dọc (`rot_x`, `rot_y`) trong vào/ra/keyframes; kiểu vào `flip` (lật) và `tilt` (ngả); lớp web dùng được CSS 3D cho chồng giấy, parallax.
- Bài học (tab Học) đưa cho AI TRỌN khi dựng: mọi ý đã học, trình tự của video mẫu, và dòng thời gian mẫu máy đo (cái gì hiện lúc nào, ở đâu so với mặt, vào/ra kiểu gì) — AI tự quyết áp vào lời của video mới.
- Phụ đề có thêm lựa chọn: ẩn cụm khi chồng lớp chữ (`khi_chong: an`) hoặc không phụ đề khi đang có khối chữ/thẻ (`an_khi_lop_chu`) — kiểu khối nhấn thay phụ đề của nhiều kênh.
**3D**
- Chữ nổi khối (`noi_3d`): chữ/khối có độ dày, góc và màu cạnh; kết hợp xoay phối cảnh thành chữ 3D thật.
- Chuyển cảnh 3D dùng khung hình thật: lật tấm thẻ (`mau.lat-3d`, trục dọc/ngang) và khối lập phương xoay (`mau.lap-phuong`, 4 hướng).
- Lớp web có sẵn three.js ngoại tuyến (viết `THREE`): vật thể 3D, thẻ/ảnh bay trong không gian, camera chuyển động, ánh sáng; video nguồn hoặc B-roll làm texture (máy tự chuyển mã cho trình duyệt ẩn, tua đúng từng khung).
- Sửa: hiệu ứng âm thanh (SFX) bị mất ở bản trộn âm mới — mixer tra nhầm nhãn thay vì đường dẫn.
**B-roll**
- Máy nhìn mọi video phụ / thư mục tư liệu: bảng khung có mốc giây, cắt cảnh, độ động, mặt người, tiếng → AI chọn đúng đoạn; ghép toàn khung, hộp nhỏ, nghiêng 3D, montage nhiều B-roll; tiếng của B-roll trộn đúng đoạn (`am_db`).
- Nhìn kỹ một đoạn B-roll: `nhanh khung --nguon <n> --tu --den`.
**Tốc độ**
- Whisper ở lại bộ nhớ giữa các việc (daemon), bỏ 11–45 giây nạp model mỗi video.
- Video phụ (B-roll) không tạo proxy nữa; mắt B-roll chỉ giải mã khung chính (3K HEVC 88 s: 2,5 phút → 13 giây).
**Ảnh bìa**
- Máy đưa ~30 khung ứng viên rải đều cả video, mỗi khung có số đo nét, miệng há/khép, mắt mở, đang nói/lặng, cười, cỡ mặt (`doc/bia-ung-vien.jpg`); AI tự chọn khung cho từng bìa, máy không chọn hộ.
**Kho**
- Khung Kho mới: nghe thử nhạc/SFX, xem font hiện bằng chính font đó (đánh dấu đủ dấu Việt), nền, LUT trước/sau, video mẫu hiệu ứng. Bấm "Dùng" để chèn vào ô chat.
**Xuất CapCut**
- Project CapCut cho video lõi mới: video nền đã cắt, mỗi lớp đồ hoạ một clip trong suốt đúng vị trí, phụ đề là chữ CapCut thật, âm thanh đã trộn.
**Kho được dùng thật sự (không còn 2–3 món quen)**
- Hơn 3.100 tài nguyên được AI gắn nghĩa tiếng Việt (nhạc, SFX, icon, nền, font, LUT, video). Mỗi video máy soạn sẵn một "gói kho" ~60 món hợp nội dung (ảnh xem nhanh + danh sách), AI dùng rộng gói này.
- SFX gắn theo từng lớp chữ/thẻ (vào/ra), máy xoay vòng trong nhóm để không lặp; dùng một tiếng quá 3 lần thì máy nhắc.
- Máy nhớ tài nguyên đã dùng ở các video trước của kênh → video sau tránh lặp.
**Thư viện 81 mẫu đồ hoạ**
- Cảnh trám, thẻ, chữ hiệu ứng (sau người, gõ máy, đếm số…), sơ đồ, biểu đồ, giao diện giả, chuyển cảnh, lớp phủ. AI gọi theo tên, đổi mọi tham số; màu/font theo phong cách video.
- Lớp HTML/CSS (vẽ bằng trình duyệt có sẵn trên máy) cho đồ hoạ tự thiết kế; kênh có thể có mẫu riêng.
**Dựng nhanh hơn khi sửa**
- Video chia đoạn: sửa một chữ chỉ dựng lại đoạn đó (~1/10 thời gian). Bìa không vẽ lại nếu thiết kế không đổi.
- Lớp phủ video/ảnh hoà trộn (screen, multiply, soft light…), chỉnh màu/LUT khi người dùng cho phép, xuất 1440p/4K, 60 fps.
**Học và phong cách**
- 20 phong cách nhanh (/review, /vlog…) là Style Spec — AI làm theo bố cục, cách chữ hiện, đồ hoạ của gói.
- Góp ý cho cả kênh ("lần sau phụ đề để giữa") sửa thẳng Style Spec của hồ sơ, hoàn tác được.
- Xem trước mặt nạ tách người trước khi dùng nền mới.
- Sửa được chữ phụ đề khi máy nghe nhầm (giữ nhịp chữ chạy theo lời). Bìa dùng được nền động từ kho.
**Âm thanh đúng nghề (23/10 chiều)**
- Nhạc đặt theo độ to THẬT của giọng (máy đo giọng và tệp nhạc): nhẹ/vừa/nổi = 24/18/12 LU dưới giọng; tệp nào cũng ra cùng cảm giác. Bỏ chuẩn hoá động từng làm nhạc trồi lên trong khoảng nghỉ.
- Cắt sạch hơn: mốc từ kéo về đúng khoảng lặng; tiếng "ờ…" không ra chữ cũng bị cắt; nhịp cắt nhanh/vừa/chậm chọn theo thể loại.
**Não AI nghĩ trước khi làm**
- Công thức bắt buộc có "ý đồ" (video về gì, người xem nhớ gì, ngôn ngữ hình ảnh một câu, nhịp, nhạc). Mỗi lớp phải trả lời "bỏ đi thì mất gì".
- Luật nghề đo được (chỉ báo): lớp mới/10 s, khoảng thở, số kiểu đồ hoạ, hiệu ứng trình diễn; máy in phiếu tự soi sau mỗi lần dựng.
- 5 bìa là 5 thiết kế khác hẳn nhau do AI đưa (không còn 3 biến thể của một thiết kế).
**Không còn màu "nhà"**: màu nhấn khi AI không chọn suy từ bối cảnh video; phụ đề/đường kẻ/mẫu dùng màu của video.
**Bản sắc kênh tự có**: kênh mới → máy rút bản sắc nháp từ video đầu đã giao; các video sau nhất quán; sửa bằng góp ý ("bỏ nhạc", "cắt gọn hơn", "ít hiệu ứng").
**AI nhìn video thật sự — ba tầng khung hình, không giả định thể loại**
- Tầng 1: máy đo mọi khung hình (chuyển động, cắt cảnh, mặt, độ sáng, dấu hiệu chữ) — vlog hành động hay người ngồi nói đều đo như nhau.
- Tầng 2: bảng ảnh cho AI lấy dày ở chỗ đổi nhiều, thưa ở chỗ yên; mức nhìn thưa/vừa/dày do kênh hoặc yêu cầu đặt; mỗi cắt cảnh đều có khung.
- Tầng 3: AI tự xin nhìn thêm đoạn nào, bao nhiêu khung mỗi giây, độ phân giải đầy đủ.
- Bản tóm tắt có thêm đường cong chuyển động theo giây và "dấu hiệu trong lời" (số liệu, liệt kê, nhấn, kêu gọi, chuyển ý, tên riêng, nói nhanh/chậm) — chỉ là dữ liệu, AI tự quyết.
**Không còn ngưỡng của nhà phát hành**: các luật mật độ chỉ bật khi kênh đặt; phiếu tự soi chỉ in số đo; lời dặn không gợi kiểu bìa hay thể loại→nhạc.
**Hạng máy A/B/C/D theo tốc độ đo thật** (bác sĩ máy đo một lần: mã hoá, tách người, nhận giọng, ổ đĩa; ước "1 phút video mất bao lâu"): Studio tự chọn mô hình nhận giọng, độ phân giải proxy, số luồng vẽ, preset mã hoá theo máy khách (bác sĩ máy hiện hạng).
**Đã gỡ lõi 1.2**: quy trình 30 bước, bộ lớp hiệu ứng cũ, kho bản đồ cũ, bộ học hành động cũ — Studio chỉ còn một lõi.

## 1.2.16 — 20/10/2026 — GHÉP PHỦ VIDEO: QUAY MÀN HÌNH + NGƯỜI NÓI · A-ROLL + B-ROLL · VIDEO DÀI KHÔNG CÒN DỪNG GIỮA CHỪNG
**Ghép nhiều video chồng lên nhau (mới)**
- Gửi kèm clip quay màn hình / B-roll cùng clip người nói: AI tự phân vai — clip có người nói là video chính, clip màn hình /
  B-roll là "video phủ". Giọng video chính chạy liền, video phủ hiện đè lên đúng lúc:
  · Video hướng dẫn: màn hình làm NỀN toàn khung + người nói trong ô bo góc (vị trí, cỡ, viền, ô vuông/giữ tỉ lệ đều chỉnh được).
  · B-roll phủ kín khung đúng câu đang nói tới (nói "căn hộ view sông" → hiện clip view sông), hoặc trong ô nổi.
- Hai máy quay CÙNG LÚC (màn hình + camera): máy tự khớp thời gian theo tiếng hoặc giờ quay ghi trong file, giữ khớp qua mọi chỗ
  cắt lặng / nói lặp — thao tác trên màn hình luôn khớp lời đang nói. AI kiểm độ khớp bằng ảnh so sánh trước khi dựng.
- B-roll đọc nhanh (không nhận giọng): 20 clip B-roll không làm bước đọc chậm như trước. Clip không lời bị đưa nhầm vào video chính
  thì Studio báo để AI chuyển sang video phủ (trước đây bị bỏ lặng lẽ).
- Máy có card NVIDIA: video phủ 4K giải mã trên card.
**Ảnh bìa do AI thiết kế (làm lại hoàn toàn)**
- Bỏ hẳn bìa lắp theo khuôn (nền bốc thăm, bố cục cố định). AI xem TOÀN BỘ chất liệu rồi tự nghĩ và tự vẽ bìa:
  · khung hình trải đều cả video (ghi rõ khung nào mặt đạt: ngậm miệng, mắt mở), khung của bản đã dựng (đồ hoạ, phụ đề),
    lời nói và ý tưởng video, gu kênh, các bìa gần đây của kênh (để giữ nhận diện nhưng không lặp khuôn cũ);
  · AI tự xin bất kỳ khung nào ở độ phân giải gốc, tách người khỏi nền khi cần (máy báo phía người bị cắt ở mép khung);
  · AI vẽ tự do: khung cảnh thật, trước/sau, giao diện, danh sách, bong bóng thoại, chữ khổng lồ… mỗi bìa một câu chữ riêng.
- Video không có người (quay màn hình, sản phẩm, cảnh) vẫn có bìa đúng nội dung — dựng từ màn hình/cảnh/đồ hoạ thật.
- Mặc định 5 BÌA phong cách khác hẳn nhau, AI tự sáng tạo (không theo mẫu nào; khách yêu cầu phong cách cố định thì AI theo).
  AI tự soi lỗi và sửa rồi mới chốt. Thư mục giao: video + 5 bìa (bia-<tên>.png là bìa chính, bia-<tên>-2…5.png).
- Máy chỉ chặn lỗi kỹ thuật: mặt còn thấy rõ, mặt trên bìa phải ngậm miệng + mở mắt, chữ chính của từng bìa đọc được ở cỡ ô
  lưới hồ sơ, đúng khổ.
- Chế độ Làm nhanh: AI thiết kế bìa trong lúc máy đang dựng video — không tốn thêm thời gian chờ.
**Video dài**
- Video dài / quay 4K (hoặc ổ đầy nên máy không làm được bản xem trước) khiến bước ĐỌC quá 10 phút: trước đây Claude dừng giữa
  chừng và Studio phải tự nhắc làm tiếp. Nay bước đọc chạy nền và Claude tự chờ tiếp đúng chỗ, không làm lại từ đầu.
**AI điều khiển thêm nhiều thứ — Studio không tự áp kiểu cài sẵn**
- Phụ đề: AI chọn cỡ, màu, viền, bóng, khối nền, viết hoa, vị trí, số chữ mỗi dòng, kiểu hiện (hiện/mờ/trượt/bật) và tô màu
  chữ đang nói (kiểu karaoke). Không ghi thì giữ giao diện trung tính như cũ. Máy vẫn giữ phụ đề trong vùng an toàn và né mặt.
- Font: chữ nhấn phụ / chữ viết tay theo font AI chọn cho video (trước: rơi về một font nghiêng cài sẵn). Font người dùng khoá
  trong hồ sơ không bị đè. Chữ chạy theo lời dùng font của video (trước: luôn Inter + Playfair).
- Giao diện thẻ cảnh trám (lưới tối / giấy sáng / kính mờ / viền mạnh) do AI chọn — máy không còn bốc thăm.
- Chỉnh màu cảnh quay: AI chọn bộ màu (chỉ khi hồ sơ cho phép chỉnh màu).
- Âm thanh: AI chỉnh to/nhỏ và độ dài từng tiếng động, mức nhạc nền. Nhạc trùng video gần đây chỉ được nhắc, máy không tự đổi bài.
- Mọi lớp chữ/đồ hoạ nhận thêm nhịp hiện/tắt (giây, 0 = cắt thẳng) và bóng đổ do AI chọn.
- Zoom trong chế độ Làm nhanh chuyển mượt theo thời gian AI ghi (trước: nhảy bậc).
- CapCut: hoạt ảnh chữ theo AI chọn; không chọn thì hiện dần trung tính (trước: máy bốc ngẫu nhiên).
- Lệnh bìa cũ và nút "Ảnh bìa" trong chat đều đi theo luồng bìa AI thiết kế.
- Máy phải bỏ một lớp vì lỗi bố cục không sửa được → AI được báo lại để kể cho người dùng.

## 1.2.15 — 20/10/2026 — CHẾ ĐỘ LÀM NHANH · RẺ HƠN ~12 LẦN · TỐI ƯU THEO PHẦN CỨNG · NHIỀU CLIP = MỘT VIDEO
**⚡ Làm nhanh (nút dưới ô chat)**
- Bật nút **Làm nhanh** rồi gửi video: AI chỉ đọc video và nghĩ ý tưởng riêng cho video đó (một công thức gọn), máy tự làm hết phần
  còn lại trong MỘT lượt — dựng, chấm, chọn bìa (mặt ngậm miệng, mắt mở), giao. Video ~1 phút: khoảng 10–12 phút, chi phí AI
  khoảng 0,25 USD (trước ~3 USD). Vẫn đủ: cắt ghép, khoảng lặng, ừm à, chữ, SFX, nhạc, ảnh, b-roll, cảnh trám, bìa.
- Làm nhanh không xoá nền, không tự xuất CapCut (cần thì bấm "Xuất sang CapCut" trên thẻ video), bìa do máy chọn.
**Studio là công cụ — AI chọn phong cách cho từng video**
- Màu nhấn, font (tiêu đề, phụ đề, chữ nhấn), hiệu ứng, nhạc, kiểu bìa: AI phân tích video (nội dung, cảm xúc, màu cảnh, người xem)
  rồi tự chọn riêng cho từng video. Studio không còn gu mặc định: bỏ bốc thăm "gói phong cách", "thẻ kích thích", thực đơn ngẫu
  nhiên, nhạc/font tự bốc; không còn dấu ấn kênh mẫu nào trong bộ cài.
- Muốn giữ màu / font thương hiệu cho MỌI video: tab Thương hiệu của hồ sơ → tick **Khoá** cạnh màu nhấn / font phụ đề / font tiêu đề.
- Gu riêng của kênh vẫn theo: ghi trong tab Gu riêng (phong-cach.md) — AI đọc mỗi lần dựng.
**Tab Học của hồ sơ (mới)**
- Dán link TikTok / Facebook / YouTube hoặc chọn video trên máy → AI TÁCH KHUNG từng khoảnh khắc có chuyện, đọc và phân tích chi
  tiết kỹ thuật (chữ, đồ hoạ, nhịp, camera, âm thanh), viết thành HÀNH ĐỘNG cho máy dựng, rồi máy DỰNG LẠI để so với gốc.
- Mỗi bài học hiện: ảnh gốc | máy dựng lại, **Đã học gì**, **Hành động cho AI**, thứ máy chưa làm được. Bật/tắt từng bài;
  bài đang bật thì AI thấy khi dựng mọi video của hồ sơ và tự quyết dùng khi hợp nội dung. Chỉ học cách làm, không chép nội dung.
**Rẻ hơn ở mọi chế độ**
- Claude chạy ngầm chỉ nạp đúng công cụ Studio dùng — không nạp plugin/MCP khác cài trên máy: mỗi lượt AI đọc ít hơn ~6 lần.
**Tối ưu theo máy**
- Bản xem trước (proxy) giải mã + thu nhỏ NGAY TRÊN CARD ĐỒ HOẠ: NVIDIA (CUDA), Intel (Quick Sync), Mac (VideoToolbox). Máy tự
  đo thử một lần cách nhanh nhất cho từng loại file và nhớ lại; card lỗi/driver cũ thì tự dùng CPU. Video 4K nhanh hơn ~2,5 lần.
- Card NVIDIA đời cũ (GTX 10xx) mã hoá được bằng NVENC. Làm mờ nền ở cảnh trám nhanh ~10 lần.
- Ổ đĩa gần đầy (< 10 GB): Studio báo ngay trong chat (trước đây lặng lẽ bỏ bản xem trước, chạy chậm hơn).
**Sửa lỗi**
- Gửi nhiều clip cùng lúc KHÔNG còn bị tách thành nhiều đoạn chat: mặc định các clip là tư liệu của MỘT video. Muốn mỗi file một
  video riêng thì nói rõ ("mỗi video riêng", "tách thành 3 video"…).
- Nhiều video chạy cùng lúc: xếp lượt công bằng, video chờ lâu không bị chen mãi.
- Thẻ các bước không còn chồng ô / lố khung; chữ gõ máy câu dài không còn tràn mất chữ; lớp hiện dần đo vùng an toàn đúng.
- Lệnh của Studio luôn chạy bằng Python riêng của Studio (không lỗi thiếu thư viện khi máy có Python khác).
**Tiện hơn**
- Xoá đoạn chat (nút thùng rác trên đầu khung chat) và xoá hẳn hồ sơ (trong hồ sơ → Xoá hồ sơ, gõ đúng mã để xác nhận).
  Video đã giao và thư mục dự án luôn được giữ.
- Thư mục giao video chỉ còn **video + ảnh bìa** (kế hoạch, báo cáo vẫn xem được trong Studio).
- Nói "edit riêng từng video" ở BẤT KỲ lúc nào trong đoạn chat (không chỉ tin đầu) là Studio tách mỗi video một việc;
  đang bật Làm nhanh thì các việc tách ra cũng chạy Làm nhanh.

## 1.2.14 — 18/10/2026 — XUẤT SANG CAPCUT · AI TỰ SÁNG TẠO THEO TỪNG VIDEO · XOÁ NỀN MỚI · CẮT SẠCH · CHẠY NHIỀU VIDEO
**Xuất sang CapCut (mới)**
- Thẻ video đã giao có nút **Xuất sang CapCut**: tạo project sửa tiếp được — video đã cắt + zoom, mỗi hiệu ứng một lớp trong suốt
  (khớp từng điểm ảnh với video MP4), phụ đề và chữ là CHỮ CAPCUT THẬT, nhạc và tiếng động tách track, preset CapCut thật.
- Máy có CapCut thì giao xong tự xuất luôn; máy không có CapCut thì không tốn thời gian, cần lúc nào bấm nút lúc đó.
  Mở được trên CapCut quốc tế bản 9.x trở xuống (CapCut 10.x chặn project do công cụ khác tạo).
**Mỗi video một phong cách — máy không áp gu của ai**
- Máy chỉ CHẶN lỗi kỹ thuật (lệch tiếng–hình, chữ ra ngoài vùng an toàn, chữ đè mặt, không đủ thời gian đọc, bịa số, thiếu tài
  nguyên) và luật bạn đặt. Mật độ chữ, nhịp, số hiệu ứng, kiểu chữ, tiêu đề bìa… là PHONG CÁCH — AI và bạn quyết, máy chỉ gợi ý.
  Máy không còn tự chèn zoom, tự thêm hiệu ứng hay tự chọn "điểm nhấn" thay AI. Muốn máy ép luật như cũ: hồ sơ đặt `luat_phong_cach: "chan"`.
- AI viết một CÔNG THỨC gọn cho từng video (ít token hơn nhiều), chọn món trong THỰC ĐƠN riêng của video đó (bốc theo nội dung,
  khác nhau mỗi video, đánh dấu món kênh chưa dùng). Kho tài nguyên vào tay AI: font, nền động, lớp phủ ánh sáng, icon, ảnh.
- Tra nhạc / tiếng động hiểu đúng cụm từ tiếng Việt; tiếng động không tìm được thì báo AI, không bỏ lặng lẽ. Không dùng font cấm kiếm tiền.
- AI edit theo HÀNH VI người nói (đếm ngón, chỉ tay, giơ đồ vật → chữ / thẻ / zoom đúng khoảnh khắc).
**Hiệu ứng mới**
- Xoá nền viết lại: viền tóc, vai, tay gọn, hết bóng ma khi đầu di chuyển. Nền mới có thể là ẢNH (căn nhà, dự án, thành phố…
  khi người nói nhắc tới nơi đó) hoặc nền lưới đúng màu lời nói ("nền xanh", "nền đỏ"…), đổi liên tiếp không chớp.
- Chồng thẻ bằng chứng, bút dạ, con trỏ bấm, trang nghiêng 3D cuộn, trang cá nhân giả lập, phụ đề in hoa giãn chữ, icon minh hoạ.
**Cắt & âm thanh**
- Máy tự cắt tiếng đệm (ừm, ờ…), từ lặp liền, tiếng kéo dài; khoảng lặng giữ tối đa 0,32 s (hồ sơ đổi được: `nghi_cat`).
- Tiếng động dừng cùng chữ/đồ hoạ đi kèm — hết kêu kéo dài khi chữ đã tắt.
- Video quay NGANG giữ khổ ngang (trừ khi bạn yêu cầu dọc).
**Học video mẫu — học để làm được**
- Máy tách các lớp đồ hoạ của video mẫu, AI xem từng khoảnh khắc rồi viết thành thao tác của máy dựng; máy dựng lại đặt cạnh bản
  gốc để so và sửa. Kết quả thành công thức dùng lại cho video hợp nội dung. Nhận đúng ngôn ngữ video mẫu.
**Chạy nhiều video**
- Giao một thư mục nhiều video → tự tách mỗi video một việc, chạy song song theo sức máy, phần còn lại tự xếp hàng.
- Việc đứng im lâu hoặc bị ngắt (tắt máy, tắt Studio) → Studio báo ngay trong khung chat, gửi "tiếp tục" để làm nốt.
**Sửa lỗi**
- Thiếu thư viện đọc chữ (OCR) khi cài mới; bộ cài kho đặt sai chỗ; lưới bìa lấy nhầm bìa của kênh khác; chữ tràn khung / ký tự
  font không có (ô vuông); bảng khung cho AI nhẹ hơn.

## 1.2.13 — 17/10/2026 — VIDEO KHÔNG CÒN MỘT KHUÔN · ĐÚNG ĐỘ DÀI KHÁCH YÊU CẦU · CHẠY ỔN TRÊN MỌI LOẠI MÁY
**Sáng tạo — AI TỰ THIẾT KẾ phong cách cho từng video**
- Khách không đưa video mẫu / không chọn gói: máy chỉ dựng khung thời gian (nhịp, đoạn ý), KHÔNG điền sẵn lớp hiệu ứng nào.
  AI tự viết `phong_cach_video` (ý tưởng, khác video trước ở đâu, bộ 4–10 thủ pháp lấy từ cả kho, cách mở bài, mật độ chữ + nhịp
  kèm lý do) rồi đặt lớp theo đúng thiết kế đó. Máy chỉ kiểm KẾT QUẢ: đọc được, không che mặt, đúng độ dài, đúng mật độ AI tự đặt,
  không trùng > 60% thủ pháp với video gần đây, không dùng kiểu quen của bộ mặc định (khung thu nhỏ, chữ 3D, xếp lớp, checklist,
  khoanh tay) trừ khi hồ sơ tự chọn giữ. Thẻ não / bài học là tham khảo kỹ thuật, không phải gu bắt buộc.
- Bỏ các luật cũ ép mọi video phải có "khung thu nhỏ + tiêu đề trên" và "chữ 3D / xếp lớp": giờ chỉ đòi CÓ đổi cảnh lớn và CÓ
  điểm nhấn sáng tạo — chọn từ cả kho (cảnh trám, ảnh chèn, nền mới, thẻ chương, giải mã, phát sáng, trượt lên, hai tầng…).
- Chống lặp có kiểm soát: thủ pháp đã lặp ở các video gần đây (của kênh này và của khách khác trên cùng máy) + các "chữ ký" quen
  của bộ mặc định được hạ ưu tiên, máy bổ sung lựa chọn mới từ toàn bộ kho; mở bài chọn từ mọi hiệu ứng chữ hợp intro.
  Kênh muốn giữ nhận diện riêng: ghi vào `cau-hinh.json → chu_ky_rieng`.
- Font xoay vòng theo video kể cả máy KHÔNG có bộ tài nguyên (dùng font đi kèm), thứ tự nhóm font đổi theo video.
- Hồ sơ mới mặc định trung tính: không còn chung một font, một màu vàng — kênh chưa chọn màu được máy gán một màu nhấn riêng.
**Độ dài**
- Lời yêu cầu có độ dài ("30s", "45 giây", "1 phút", "1p30", "dưới 30s") thành RÀNG BUỘC: cổng kịch bản chặn khi lệch; nhiều clip
  thì AI chọn câu hay nhất cho vừa (bản đọc lại có bảng từng câu theo clip để chọn).
**Đọc nhiều clip không còn làm đứng máy**
- Thả 20–30 clip: máy "mắt" chạy theo hàng đợi (1–3 tiến trình tuỳ số luồng CPU, ưu tiên thấp) thay vì mỗi clip một tiến trình
  cùng lúc — chừa máy cho người dùng làm việc khác.
- Clip chờ tới lượt proxy 1080p thay vì quay sang giải mã bản gốc 4K (clip 4:2:2 10-bit không giải mã bằng GPU được nên rất nặng).
- Thử GPU (giải mã, nhận giọng) mà hỏng vì máy đang bận (quá giờ) → chỉ nhớ 6 giờ rồi tự thử lại, không khoá CPU vĩnh viễn.
- Hàng đợi proxy: một clip lỗi không còn làm chết cả hàng (bản cũ để 20 clip nằm chờ mãi); khoá của hệ điều hành nên tiến trình
  chết giữa chừng không còn làm kẹt; proxy mã hoá bằng GPU (NVENC/QSV/AMF) khi máy có, CPU dành để giải mã nguồn.
- AI không tự áp LUT lên từng clip thô nữa — LUT ghi vào kế hoạch, máy áp một lần lúc dựng, chỉ trên đoạn được dùng.
- Thời gian còn lại: Đọc tính theo tổng giây thô, Dựng theo giây thành phẩm (hết báo "còn 963 phút" khi thả nhiều clip). Thời gian chờ khách góp ý / phiếu mở qua đêm không còn bị học thành "AI suy nghĩ" (trần 30 phút).
- Nhận giọng nạp mô hình một lần cho cả loạt clip (trước: mỗi clip nạp lại).
**Chạy đúng trên nhiều loại máy**
- Clip không có tiếng (quay màn hình, drone, GoPro tắt tiếng) không còn làm dựng dừng.
- Video HDR của iPhone (HLG / Dolby Vision) đổi về màu chuẩn — hết xám nhạt.
- Video điện thoại quay xoay / khung hình thay đổi (VFR) đọc đúng khổ và đúng số khung.
- Mac Intel mã hoá được (trước lỗi -q:v); Mac: bấm Dừng tắt cả tiến trình con; Apple Silicon đọc đúng RAM trống.
- Card GeForce: giới hạn số phiên mã hoá phần cứng cùng lúc (trước: máy nhiều nhân dựng song song bị lỗi đoạn).
- Ổ gần đầy: không làm proxy (đọc thẳng bản gốc) thay vì làm đầy ổ.
- Hai clip trùng tên (C0001.MP4 từ hai thẻ nhớ) không còn dùng nhầm kết quả của nhau.
- Đường dẫn có dấu nháy ' hoặc tiếng Việt có dấu chạy đúng (filter ffmpeg, tiến trình nền, lối tắt Desktop OneDrive).
- Ghi file trên Windows không còn lỗi khi Studio / phần mềm diệt virus đang đọc; kết quả thử phần cứng ghi an toàn khi nhiều
  tiến trình cùng thử; học kênh và lập danh mục kho chạy theo sức máy.

## 1.2.12 — 16/10/2026 — EDIT NHANH GẤP ĐÔI · QUY TRÌNH 3 PHẦN · ẢNH BÌA DỰNG MỚI
- QUY TRÌNH 3 PHẦN thay 30 bước: ĐỌC (máy đọc video một lần) → TƯ DUY (AI nghĩ một lần như editor) → DỰNG (máy dựng một lần,
  AI nhìn lại). Mọi luật (vùng an toàn, chữ không đè mặt, nhịp không bị trống, chống lặp…) máy tự kiểm và TỰ SỬA bên trong —
  AI không phải nộp đi nộp lại. Studio hiện 3 phần + thời gian còn lại (học theo tốc độ thật của máy bạn).
- NHANH HƠN: video 4K chỉ giải mã một lần (mọi bước đọc bản 1080p), dựng bản thật song song nhiều nhân, chỉ trộn chữ ở vùng
  có chữ, ảnh bìa dựng song song lúc dựng video. Máy tự dời chữ né mặt, tự kéo/thu chữ vào vùng an toàn, tự thêm cú đổi khung
  khi nhịp trống — bắt ngay ở bản nháp nên bản thật chỉ dựng MỘT lần.
- ẢNH BÌA DỰNG MỚI: không cắt thẳng khung video nữa — máy tách người, vẽ nền mới (dải màu, tia sáng, vòng tròn, chéo hai màu,
  lưới công nghệ, cảnh mờ, thẻ màn hình, chữ khổng lồ sau lưng), dải mờ từ dưới lên, viền/hào quang quanh người. Mỗi bìa một
  công thức, không lặp các video gần đây. CHỈ lấy khoảnh khắc NGẬM MIỆNG, mắt mở (máy đo khe môi + lòng miệng, dò dày quanh
  từng khoảnh khắc); AI nhìn lại từng mặt và loại mặt chưa đẹp.
- TÁCH NỀN SẠCH HƠN: mô hình tách người đa lớp mới (bản quyền thương mại Apache 2.0) — không còn dính bàn ghế, laptop; tóc gọn.
- GPU: tự dò card đồ hoạ thật; máy thiếu thư viện CUDA không còn báo lỗi — tự chuyển CPU, bác sĩ máy cài thêm khi đủ điều kiện.
- FONT: kèm sẵn bộ font giấy phép mở mà các phong cách dùng (Anton, Bungee, Barlow, Oswald, Playfair, Lora, Manrope, Space
  Grotesk, Baloo, Lexend, Be Vietnam Pro…) — lỡ xoá kho tài nguyên, phong cách vẫn giữ đúng chữ. Tài nguyên đã bị xoá khỏi ổ
  tự được bỏ qua khi chọn nhạc/SFX (không còn vấp lúc dựng).
- BÌA THEO GU TỪNG NGƯỜI: hồ sơ chọn "bìa dựng" hay "bìa khung thật + chữ"; chưa chọn thì AI TỰ ĐỀ XUẤT hình thức hợp nội
  dung video — kể cả hình thức mới chưa từng có (AI tự vẽ bìa: khung phim, tạp chí, tách đôi…), máy vẫn kiểm chặn chất lượng.
- XUẤT 4K / 3K / CHẤT LƯỢNG GỐC khi bạn yêu cầu ("xuất 4K", "trả nguyên 3K bằng video gốc", "60fps"): xuất đúng độ phân giải
  gốc cao nhất (tối đa 4K), giữ fps gốc khi bạn đòi; không yêu cầu thì 1080p cho nhẹ. Nguồn nhỏ hơn thì không phóng giả.
- NHIỀU VIDEO CÙNG LÚC thông minh hơn: phần máy nặng (đọc video, dựng) của các video xếp lượt — video này được đọc trong lúc AI
  của video kia đang nghĩ, không giẫm lên nhau. Máy mạnh dựng tới 12 luồng song song (trước 6).
- HẾT LƯỢT CLAUDE GIỮA CHỪNG: Studio tự chờ tới giờ mở lại lượt rồi làm tiếp (mất mạng thì tự chờ có mạng như trước).
- GỬI THÊM LUT MÀU (.cube) VÀ FONT (.ttf/.otf): kéo thả vào Studio — LUT áp đúng (chỉnh được độ đậm), font dùng cho chữ video.
- Sửa: sơ đồ tư duy chữ dài tràn khung/nhánh đè nhau; cắt nói lặp xoá nhầm cả từ; phụ đề né mặt; máy chấm nhận nhầm bàn tay là mặt;
  chữ to quá khổ tự thu nhỏ; LUT trong kho trước đây không được áp.
- APP KHÔNG CÒN LỖI "No Python at…" khi tắt máy mở lại: app mở qua bộ mở tự chữa — Python bên dưới bị thay/gỡ thì Studio tự
  nhận bản Python 3.12 khác (thiếu thì tự cài), không phải cài lại. Lối tắt cũ tự đổi sang bộ mở mới. Bác sĩ máy kiểm mục này.

## 1.2.11 — 14/10/2026 — COPY PHONG CÁCH TỪ VIDEO MẪU
- COPY PHONG CÁCH: thả một VIDEO MẪU (nút "Video mẫu", hoặc bấm nhãn "video" trên file đã thả để đổi thành "video mẫu") —
  AI băm nhỏ video đó: nhịp cắt, kiểu chuyển cảnh, zoom, chữ (font khớp từ kho, màu, cỡ, vị trí, viết hoa, viền, nền),
  phụ đề, nhạc/SFX, bố cục — rồi dựng video của bạn theo đúng phong cách đó (màu video của bạn giữ nguyên). Bản dựng được đo lại và so với mẫu
  (điểm giống từng mặt + ảnh so sánh mẫu/bản dựng). Không chép nội dung chữ, logo, watermark của video mẫu.
- GIỮ 100% MÀU GỐC: mặc định AI không chỉnh màu video (kể cả khi copy video mẫu). Chỉ chỉnh khi bạn yêu cầu
  ("chỉnh màu", "tone ấm", "màu điện ảnh"…) hoặc chọn phong cách nhanh.
- KHÔNG CẦN DUYỆT KỊCH BẢN: mặc định AI tự duyệt và dựng luôn. Muốn xem trước, chỉ cần nói "cho mình duyệt kịch bản trước".
- NHẬN ĐỦ LOẠI FILE: kéo thả hoặc chọn ảnh (làm B-roll/ảnh trám), âm thanh (nhạc/SFX của bạn), file kịch bản Excel, Word,
  PowerPoint, CSV, TXT, PDF — AI đọc và bám theo.
- KẾT NỐI THƯ MỤC: nút "Thư mục" cho AI đọc cả một thư mục tư liệu của bạn.
- HẾT CỬA SỔ CMD: Studio chạy hoàn toàn ẩn, không còn cửa sổ đen dễ tắt nhầm.
- Thêm 3 hiệu ứng: chèn ảnh của bạn, chuyển cảnh qua đen, chuyển cảnh nhoè mềm.
- CẢNH TRÁM VẼ ĐÚNG THỨ ĐANG NÓI (lấy lại điểm mạnh của bản đầu): sơ đồ tư duy toả nhánh, checklist tích từng ý, biểu đồ cột
  mọc dần, so sánh đúng/sai, khung chat với AI gõ chữ, ô tìm kiếm, các bước nối nhau — và AI tự vẽ cảnh riêng khi cần.
- TÁCH NỀN thông minh: chỉ dùng ở câu then chốt có người rõ, nền rối — tối đa 2 lần, mỗi lần ≤ 6 giây.
- MỖI VIDEO MỘT VẺ — BỘ NÃO SÁNG TẠO (khi không đưa video mẫu): AI đọc Ý ĐỊNH video (hướng dẫn, review, bán hàng, tâm sự,
  kiến thức, kể chuyện…) rồi chọn 1 trong 11 gói biến tấu (chuyên gia nhịp nhanh, editorial chữ chạy, tối giản, giải thích
  bằng đồ hoạ, tutorial màn hình, một máy chân thật, phóng sự ngắn…) — không lặp gói của video trước hay video đang làm cùng
  lúc. Giữ chất kênh (màu nhấn, phụ đề, màu gốc video), chỉ đổi bề mặt: nhịp, zoom, chuyển cảnh, kiểu chữ, cảnh trám, nhạc, bìa.
  Mỗi video thêm 1 "thẻ kích thích" sáng tạo, 3 ý tưởng để chọn, và danh sách cấm lặp từ 3 video gần nhất (mở bài, nhạc,
  cảnh trám, bìa, font). Chủ đề nhạy cảm tự dùng gói điềm tĩnh. Nhạc chọn theo đúng loại video (không lót nhạc buồn cho
  video hướng dẫn) và không trùng bài 3 video gần nhất.
- XÉ NHỎ PHẦN THÂN như editor người: thân video được chia thành các ĐOẠN Ý (yếu tố 1, 2, 3… / ví dụ / lật vấn đề), mỗi đoạn
  có vai trò, cường độ dồn về cao trào và một cách xử lý hình riêng (người nói + chữ, cắt zoom, cảnh trám, màn hình lồng, tách
  nền, phóng màn hình, khoảng lặng) — đoạn kề không trùng; các ý song song mở chương cùng một kiểu để người xem nhận ra cấu
  trúc. Bảng xé nhỏ hiện trong bản kế hoạch.
- MỨC SÁNG TẠO trong hồ sơ: Giữ đúng chất kênh / Làm mới vừa phải / Thử nghiệm táo bạo (hoặc nói "làm táo bạo hơn").
- MÀU NHẤN PHỤ (tuỳ chọn) trong hồ sơ: chữ nhấn và cảnh trám xen kẽ 2 màu. Cảnh trám có 4 giao diện đổi theo video
  (lưới tối, giấy sáng, kính mờ nổi trên hình, viền đậm).
- CHỌN PHONG CÁCH NHANH thì được đổi màu theo phong cách đó, đồng thời dùng đúng bộ hiệu ứng, chuyển cảnh, nhạc, bìa của phong cách.
- Ảnh minh hoạ 8 phong cách nhanh (review, bán hàng, tâm sự, công nghệ, hài, podcast, ẩm thực, bài giảng) làm mới bằng footage của chính Studio; gỡ toàn bộ tư liệu tham chiếu của một kênh bên thứ ba theo yêu cầu của chủ kênh.
- NGHE THỬ GIỌNG AI: nút "▶ Nghe thử" cạnh danh sách giọng — 51 giọng có mẫu sẵn, nghe không tốn lượt.
- NHANH HƠN, CHẤT LƯỢNG GIỮ NGUYÊN: đọc khung hình nhanh hơn, bỏ bước mã hoá lại khi giữ màu gốc, chữ chạy và cảnh trám vẽ
  nhanh 3–4 lần, đọc hình chạy song song với nhận giọng, tách nền dùng lại mặt nạ, AI kiểm bản nháp trước khi dựng bản chính
  (bớt dựng lại), chờ việc nền bằng lệnh chờ thay vì ngủ cố định. Hợp máy cấu hình trung bình không GPU.
- CHỮ CHẠY THEO LỜI (kiểu editor 2026): cụm 2 tầng hiện từng chữ theo giọng nói, mờ → nét, chuyển màu, tự né mặt,
  tự đổi chữ tối khi nền sáng. Font mới: Inter (giống SF Pro) đủ dấu tiếng Việt.

## 1.2.10 — 14/10/2026
- Sửa lỗi chạy song song: hai video trùng tên giao cùng lúc không còn ghi đè nhau trong thư mục Tải xuống — mỗi video
  một thư mục riêng (trùng tên thì thêm -2, -3…). Cổng kế hoạch đo "chữ to" và "đổi cảnh" sát với mắt người xem hơn:
  thẻ danh sách chữ nhỏ không tính là chữ to; talking head một góc máy phải có đổi cảnh thật (màn hình lồng…), zoom không tính.

## 1.2.9 — 14/10/2026 — DỰNG SÁNG TẠO HƠN, BỚT DẬP KHUÔN
- CHỮ ĐẸP KIỂU KÊNH LỚN: thêm chữ xếp lớp (sans đậm + viết tay đè chéo), chữ khối 3D xoay, chữ to nằm SAU người,
  khung bo góc ôm vùng kèm nhãn viết tay, khung hình lồng trên nền tối để "đổi cảnh" khi chỉ có một góc máy.
- FONT MỚI MỖI VIDEO: máy tự chọn tổ hợp font theo vai (tiêu đề / nhấn / phụ / viết tay) từ cả kho ~400 font, tránh font
  đã dùng ở 5 video gần nhất; sửa lỗi không đọc được font bộ quà tặng có tên thư mục tiếng Việt.
- HẾT DẬP KHUÔN: so "khung xương" (mở bài, kết, thủ pháp chính, font, kiểu bìa) với 5 video gần nhất; một thủ pháp không
  quá 35%; khung/khoanh/làm tối tối đa 3 lần/video. Mẫu kế hoạch không còn mặc định một kiểu mở bài.
- NHIỀU CHỮ & NHỊP HƠN: tối đa 3 kiểu chữ/khung, chữ nhấn dày hơn ở hook/payoff; máy chấm đo mật độ hình ảnh (chữ to,
  vị trí, cỡ, đổi cảnh) so với dải của 162 video kênh mẫu.
- ẢNH BÌA: chữ trên bìa là tiêu đề viết lại đủ nghĩa (hết chữ cụt kiểu "VÌ SAO TRẢ"); 3 biến thể khác ý tưởng, khác màu;
  tương phản chữ ≥ 4,5:1.
- MÀU DA: sau grade máy tự đo và bù — hết đè đen, bớt lạnh xanh, nền bớt chói (đo theo kênh mẫu).
- GỢI Ý QUAY: báo cáo giao kèm gợi ý quay lần sau khi video chỉ có một góc máy quá lâu.
- Sửa chip model/token hiện "chưa đo nullnull".
- Chạy song song an toàn hơn: hai việc bắt đầu cùng phút, cùng tên không còn dùng chung một thư mục dự án; Claude không được
  tắt tiến trình của việc khác.

## 1.2.8 — 13/10/2026
- GÓI THÁNG: thêm lựa chọn thuê bao 30 ngày (dùng đủ tính năng + cập nhật khi còn hạn). Hết hạn, Studio hiện màn
  gia hạn ngay trong app — bấm gia hạn, chuyển khoản xong bấm "Tôi đã gia hạn — kiểm lại" là dùng tiếp, giữ nguyên mã.
- BẢN QUYỀN chắc hơn: mỗi mã dùng 1 thiết bị; thẻ kích hoạt tự gia hạn an toàn, không bị qua mặt bằng chỉnh giờ máy.
- Mọi tệp trong bộ cài có dòng bản quyền © và mã truy vết — chống sao chép, phát tán trái phép.

## 1.2.7 — 12/10/2026
- PHONG CÁCH NHANH: 20 ảnh minh hoạ làm lại bằng KHUNG HÌNH QUAY THẬT (người thật, món ăn, sản phẩm, cảnh thật) thay cho
  ảnh vẽ — mỗi thẻ 3 khung Mở đầu · Thân · Kết đã áp đúng màu, font, hiệu ứng của phong cách, kèm bảng màu và font.

## 1.2.6 — 12/10/2026 — STUDIO 2.0 (bộ não mới + quy trình bắt buộc)
- BỘ NÃO MỚI: 195 thẻ lý thuyết dựng video (tri giác, cắt ghép, cấu trúc, giữ chân phần thân, âm thanh, chữ & màu, ảnh bìa),
  ma trận 14 tình huống × 6 quyết định, 6 ngữ pháp dựng. AI chẩn đoán từng video rồi mới quyết hook, thân, chữ, nhạc, bìa.
- QUY TRÌNH 30 BƯỚC · 6 CỔNG CHẶN: đọc video từng khung → chẩn đoán → kịch bản theo ý → KẾ HOẠCH TỪNG GIÂY (intro · thân ·
  outro · âm thanh, có đường cường độ) → bạn duyệt → dựng → máy chấm + AI nhìn lại → ảnh bìa → giao. Bỏ bước là bị chặn.
- MÁY DỰNG MỚI: ghép từng khung, camera ảo đẩy cận, bám đúng nút trên màn hình quay cầm tay, 36 hiệu ứng chữ/thẻ/nét chỉ
  dẫn/chuyển cảnh/grade chọn theo NGHĨA từng câu; tự giữ vùng an toàn, tự làm tối nền sau chữ; không bao giờ đen trắng.
- KHO 2.0: mỗi tài nguyên có mã + nghĩa + số đo; AI tra theo nghĩa ("tiếng lật bất ngờ, mạnh"), tự tránh lặp với 3 video
  gần nhất. Sửa lỗi bộ 405 font quà tặng không nạp được.
- 20 PHONG CÁCH NHANH: nút "Phong cách" (có ảnh minh hoạ) hoặc gõ /review /sanpham /huongdan /kienthuc /tamsu /vlog
  /dienanh /tintuc /congnghe /taichinh /hai /podcast /dulich /amthuc /bds /giaoduc /thethao /thoitrang /sukien /showcase.
- ẢNH BÌA THEO LÝ THUYẾT: 10 kiểu bìa, tự kiểm tương phản, cỡ chữ, đè mặt, đọc được ở cỡ lưới; 2–3 biến thể khác kiểu.
- HỌC KÊNH KIỂU MỚI: tách mọi khung, đọc chữ trên màn, đo nhạc/SFX, đoán font, bóc mở–thân–kết.
- CHẠY SONG SONG: nhiều đoạn chat chạy cùng lúc. Câu hỏi luôn trả lời ngay; việc dựng/học video chạy song song theo sức
  máy (tự tính theo CPU/RAM, chỉnh được 1–4), máy quá tải thì việc dựng mới chờ chỗ trống — không còn xếp hàng lần lượt.
- MODEL & TOKEN: chip trên đầu mỗi việc hiện model (mặc định khoá Opus 5.5) và token vào/ra; bấm xem từng lượt.
- Lần đầu dựng sau khi cập nhật, Studio tự lập danh mục kho (một lần, 5–15 phút). Bác sĩ máy có thêm mục kiểm/sửa.

## 1.2.5 — 08/10/2026
- GIỌNG NÓI AI: nút mic ở thanh trên mở hộp "Giọng nói AI". Nhập khoá riêng (dịch vụ aizening.com), chọn giọng mẫu,
  gõ chữ → tạo mp3, nghe/tải ngay trong app. Nhân bản giọng từ một tệp mp3 mẫu. Bấm "Dùng cho video này" để đính
  giọng vào ô chat — Claude lồng vào video khi dựng. Mỗi người nhập khoá của mình (không nhúng khoá ai vào gói).
- Nhẹ hơn khi việc dài: khung chat chỉ vẽ ~300 dòng gần nhất (việc vẫn đủ ở phiếu/báo cáo).
- Bộ chọn tệp nhận thêm mp3 (cho nhân bản giọng).

## 1.2.4 — 07/10/2026
- Siết bản quyền: chưa kích hoạt thì KHÓA ngay ở ô chat (không chỉ ở bước dựng) — không gửi được tin, không chạy Claude.
  Mỗi phiếu đều kiểm bản quyền trước khi mở.
- Chống sửa file: mỗi lần chạy, Studio đối chiếu mã băm các file quan trọng (bản quyền, quy trình, máy dựng, bộ não gốc)
  với danh sách ĐÃ KÝ SỐ trong TEP-GOI.json. Có file bị sửa → Studio tạm khóa, báo "cài lại từ link chính chủ".
  Hồ sơ kênh, bài đã học của người dùng vẫn giữ nguyên.

## 1.2.3 — 07/10/2026
- Tự báo bản mới: mở Studio là tự kiểm (rồi 6 giờ một lần); có bản mới thì hiện dòng báo với nút "Cập nhật ngay".
  Bấm 1 lần: tải, kiểm chữ ký, cài, Studio tự mở lại bằng bản mới. Không cài khi Claude đang làm việc.
- Mất mạng giữa chừng: Studio tự chờ có mạng lại rồi cho Claude làm tiếp từ chỗ dở (không cần gõ "làm tiếp").

## 1.2.2 — 07/10/2026
- Sửa lỗi Studio đứng ở bước Dựng: Claude cho lệnh dựng (video 4K) chạy nền rồi kết thúc lượt, lệnh dựng bị tắt theo.
  Nay Claude phải chạy lệnh dựng thẳng hoặc tự chờ trong cùng lượt; và nếu vẫn dừng khi phiếu chưa giao,
  Studio tự nhắc "làm tiếp" (tối đa 3 lần) — không cần người dùng gõ gì.

## 1.2.1 — 07/10/2026
- Claude hỏi lại hiện thành THẺ CÂU HỎI nổi bật, có nút bấm chọn nhanh; việc đang chờ có nhãn "chờ bạn" ở cột trái,
  ô chat đổi thành "Trả lời Claude…", tiêu đề cửa sổ báo số câu hỏi đang chờ.
- Cuối khung chat có thanh đang chạy: đồng hồ đếm giờ, bước đang làm, thao tác gần nhất, nút Dừng.
- Nút "Đăng nhập Claude" trong Studio: tự tìm đúng Claude Code trên máy (tự cài nếu thiếu) và mở cửa sổ đăng nhập —
  không còn bắt gõ `claude.cmd` (máy cài bằng bộ cài chính thức không có lệnh này).
- Bác sĩ máy tự cài Git for Windows và Claude Code; kiểm đăng nhập Claude và hiện gói (Pro/Max).
- Sửa Studio báo nhầm "Skill chưa cài xong" khi chạy bằng Python của skill.
- Bản quyền hiện "đang hoạt động" thay vì số ngày của thẻ xác nhận (thẻ tự gia hạn, bản quyền trọn đời).

## 1.2.0 — 06/10/2026
- Bản kê kho công cụ tự in khi nạp não; phiếu đi chợ `scripts/tham_kho.py` (hiệu ứng theo nghĩa từng câu, nhạc theo mood,
  SFX theo loại nhấn, lớp hình); luật `nao/goc/6-di-cho-kho.md`. Bước 5, 7 phải tự ghi lý do; dựng thật cần đủ bước 1–7.
- Nhiều video một lần: mỗi video một phiếu, Studio hiện từng phiếu.
- Bộ cài bấm đúp Windows / Mac (`CAI DAT - …`) + `CLAUDE.md` để Claude Code tự cài.
- Studio: app làm việc (hồ sơ kênh theo màu · trò chuyện · phiếu 12 bước trực tiếp · kho kéo thả · học từ link video ·
  bản quyền và cập nhật ngay trong app). Mở bằng lối tắt "Studio dựng video" ngoài Desktop.
- Bác sĩ máy `studio/bac_si.py`: tự kiểm 12 mục và tự cài / sửa (ffmpeg, uv, thư viện, nhận giọng, kho, bộ quà tặng).
- Sửa nhận giọng hỏng trên Windows: khoá `faster-whisper==1.2.1`, `av==14.2.0` (av 15+ bỏ tham số faster-whisper cần).
- Sửa bộ cài dừng vì bảng mã cp1252; sửa font không vào được thư mục libass khi Windows cấm liên kết (tự lùi về chép).
- Luật mới `nao/goc/3-chu.md`: không tự sửa tên sản phẩm / thương hiệu khi chưa có bằng chứng; hồ sơ có `tu_giu`.
- Mỗi việc một phiếu (`QUY_TRINH_PHIEU`) và ghim hồ sơ (`HO_SO`) — nhiều kênh không còn ghi lẫn bước của nhau.
## 1.1.0 — 06/10/2026 (bản phát hành qua aizening.com)
- Kích hoạt bằng mã bản quyền trong thư giao hàng (dạng EV123456-XXXX-XXXX-XXXX), gói 2–3 tự nhận bản mới.
- Kho tài nguyên sạch đi kèm gói (không phải dựng); tự tìm và dùng bộ tài nguyên quà tặng ~10 GB (tự gộp khi Drive chia nhiều zip).
- Ảnh bìa theo hồ sơ (4 kiểu), loé sáng tự tạo khi không có bộ quà tặng, phiếu quy trình 12 bước bắt buộc.

## 1.0.0 — 06/10/2026
- Bộ não 3 tầng (gốc · kiến thức · cá nhân) + quy trình chuẩn 12 bước, máy dựng chặn khi thiếu nhật ký dựng.
- 3 bộ phong cách mẫu: Sôi động · Biên tập · Neon (`nao.py ho-so tao <ten> --tu <bo>`).
- Học thêm từ kênh/video: bài học của người dùng lưu riêng ở `nao/kien-thuc/cua-toi/`, cập nhật không bao giờ đụng tới.
- Chạy trên Mac (Apple Silicon) và Windows; bộ cài 1 lệnh `scripts/cai_dat.py`.
- Tự chấm sau dựng: 3 lượt đồng bộ/hình/tiếng · bố cục · chữ.
- Bản quyền theo máy (kích hoạt bằng mã) + bản cập nhật có chữ ký số, chỉ tải qua https.
