# Hướng dẫn AI viết Style Spec từ SỐ ĐO MÁY (tab Học)

Tệp này dùng hai cách:
1. Luồng tab Học (`cau_noi.py hoc-chuan-bi`): AI (Claude chính) mở tệp này khi thấy dòng "AI: đọc …HUONG-DAN-AI.md" trên đầu ảnh
   `bang-su-kien-dong-hoc-N.jpg`, rồi làm đúng các bước dưới cho từng thư mục video (mọi ảnh `bang-su-kien-*.jpg` được in ra,
   gồm bảng khung dày, dải soi và cận chữ).
2. `hoc/hoc.py hoc()` (gọi `claude -p`): phần sau dấu `---8<---` là khuôn prompt, các `{...}` được máy điền.

Nguyên tắc: Studio KHÔNG mang gu. Spec là CÁCH LÀM của video mẫu, do MÁY ĐO; AI chỉ xác nhận bằng mắt, sửa chỗ máy đo sai
(có lý do), và điền phần máy không đo được (nhóm font, sfx, bìa). Không chép chữ/logo/mặt/giọng. Khi dựng, spec được ÁNH XẠ
thẳng vào trường công thức (hoc/ap_spec.py, không hệ số của máy); trường spec chỉ nói "có/không" (viền, bóng) thì số lấy ở
quyết định kênh (quyet-dinh.json). Mọi số trong hướng dẫn này là mô tả cách đo/đơn vị, không phải ngưỡng khuyên.

---8<---
Bạn đang HỌC CÁCH LÀM của một video mẫu để kênh dùng lại cho nội dung của riêng mình. Máy đã ĐO sẵn; nhiệm vụ của bạn là
viết `style-spec.json` TỪ SỐ ĐO, mắt chỉ để XÁC NHẬN. Không đoán số khi máy đã có số.

## Đầu vào
- Số đo đầy đủ: `{dong_hoc}` (dong_hoc.json) — mỗi `su_kien` có `vai` (tieu_de/nhan/phu_de/do_hoa), `vao`/`ra`
  (`kieu`, `huong`, `dai` giây, `ease`, `ease_rmse`, `chuoi` từng khung: t, x, y, w, h, alpha, phan_hien, ky_tu, tu), `vao_nen`
  (thẻ/pill chứa chữ vào thế nào), `tinh` (hop, tam, anchor, can_le, so_voi_mat{{vi_tri, khoang_theo_cao_mat}}, cao_muc_px_1920,
  co_uoc_1920, hoa, dam_uoc, mau_chu, vien_chu, bong_chu, nen{{hinh, bo_px_1080, mau, nen_mo, bong, co_vien}}); `tong_hop` (phân bố kiểu
  vào/ra, nhịp lớp chữ, phụ đề, cắt cảnh); `bo_qua`/`khong_do_duoc` = máy không chắc → bỏ qua sự kiện đó.
- Spec MÁY (điểm xuất phát, đúng schema): {spec_may}
- Số liệu khác: {so_lieu}
- Spec cũ của hồ sơ (hợp nhất: giữ cái đúng, thêm cái mới; màu/font KHOÁ của khách không bị video mẫu ghi đè): {cu}
- Ảnh (mở TẤT CẢ bằng Read):
  - `bang-deu.jpg`, `bang-su-kien-N.jpg`: bảng khung đều, dải quanh cắt cảnh.
  - `bang-su-kien-khung-N.jpg`: khung DÀY toàn video (proxy 540p, mắt ba tầng mức "day": dày ở chỗ đổi nhiều, viền vàng = cắt cảnh)
    — nhìn nhịp, bố cục, đồ hoạ xuất hiện lúc nào.
  - `bang-su-kien-dong-hoc-N.jpg`: mỗi hàng một sự kiện: khung vắng → các khung chuyển → khung đủ; hộp xanh = máy đo, hộp cam =
    hộp lúc đủ; ô phải = đường tiến trình đo được (chấm) và easing máy khớp (đường cam); nhãn ghi kiểu vào/ra, thời lượng, neo so
    với mặt, cỡ mực chữ, HOA, nền thẻ. Ô nhỏ — chỉ để định vị.
  - `bang-su-kien-soi-<id>.jpg` (+ `-2`): DẢI SOI của sự kiện `<id>` — 12 khung/giây, vùng quanh chữ cắt từ VIDEO GỐC, ô cạnh ngắn
    260 px; phần "— VÀO —" từ ~0,3 s trước lúc vào tới ~0,8 s sau, phần "— RA —" quanh lúc biến mất; viền vàng = khung máy đo
    bắt đầu, xanh = máy đo đủ, đỏ = máy đo hết (lúc ra). Đây là bằng chứng chính cho KIỂU VÀO/RA.
  - `bang-su-kien-chi-tiet-chu-<id>.jpg`: CẬN CHỮ — hộp chữ (+ thẻ nền) lúc đủ cắt từ video gốc độ phân giải đầy đủ, phóng
    ≥ 600 px rộng, kèm khung toàn cảnh (ô cam = vùng cận) và 2 khung lúc 30% / 70% quá trình vào. Đây là bằng chứng chính cho
    FONT, VIỀN, BÓNG, NỀN THẺ, BO GÓC, MÀU.
  Chỉ ~12 sự kiện tiêu biểu (đa dạng vai/kiểu vào/ra) có dải soi + cận chữ; sự kiện khác chỉ có trong dải động học.
{anh}

## Các bước
0. NHÌN TRƯỚC, ĐIỀN SỐ SAU. Mở bảng khung dày, rồi với MỖI sự kiện có ảnh `soi`/`chi-tiet-chu`: mở cả hai, và viết ra (trong
   suy nghĩ của bạn, trước khi đụng tới JSON) một mô tả bằng lời, đúng những gì THẤY, không suy diễn:
   - FONT: có chân / không chân / display / viết tay / mono; đậm cỡ nào (mảnh–thường–đậm–rất đậm); HOA hết / thường / trộn;
     nén hẹp hay rộng; nghiêng; khoảng cách chữ.
   - VIỀN / BÓNG: có viền không, màu, dày tương đối (mỏng ≈ 1–2 px@1080 / dày); bóng đổ hay quầng, hướng, độ nhoè.
   - NỀN: không nền / thẻ (pill, chữ nhật, bo góc bao nhiêu so với cao thẻ) / dải mờ; màu, độ đục, có viền thẻ không; chữ nhiều
     màu (từ khoá đổi màu?) hay gradient.
   - CÁCH HIỆN (từ dải soi, từng khung): bật ngay / mờ dần / phóng từ to-nhỏ (có vượt rồi về không) / trượt từ hướng nào /
     từng ký tự / từng từ / mặt nạ mở theo chiều nào / thẻ vào trước rồi chữ; mất bao nhiêu khung (12 khung = 1 s). Lúc ra tương tự.
   - Đồ hoạ (`vai: do_hoa`): là gì (sticker, icon, mũi tên, khung, hiệu ứng hạt…), có phải đồ hoạ phủ thật không.
   Mô tả này là bằng chứng của bạn; số máy chỉ đúng khi khớp với nó.
1. Đối chiếu mô tả với số máy, dùng DẢI SOI (rõ hơn dải động học). Với mỗi sự kiện: nhìn khung chuyển có đúng kiểu máy ghi không (pop = to/nhỏ dần về cỡ thật;
   slide = trượt từ hướng `huong`; fade = mờ đều; blur = nhoè → nét; typewriter = từng ký tự; word_by_word = từng từ theo lời;
   mask_reveal = mặt nạ mở một chiều, chữ đã đủ nét; doi_ky_tu = ký tự nhảy rồi chốt (giải mã); none = bật ngay).
   ĐÚNG → dùng nguyên số máy (`dai`, `ease`, `huong`). SAI rõ ràng → sửa kiểu nhưng GIỮ thời lượng đo được, ghi lý do ngắn
   vào `ghi_chu`. Hàng có hộp xanh bám vào tay/mặt/màn hình nền = máy đo nhầm → loại sự kiện đó khỏi thống kê.
   Dải soi cho thấy chữ đổi tức thì (khung trước chữ cũ, khung sau chữ mới) mà máy ghi slide/fade dài = máy bị vật thể đi qua
   đánh lừa → kiểu thật là none (thay chữ), ghi lý do.
2. Bắt đầu từ spec máy, chỉnh theo bước 1:
   - `motion_vocab.vao/ra`: giữ phân bố `tan_suat` từ `tong_hop.vao_chu/ra_chu` (đã loại sự kiện sai). Ánh xạ kiểu máy → schema:
     pop→pop, slide→slide (+`huong`), fade→fade, blur→blur, typewriter→typewriter, word_by_word→pop với `"tach":"tu"`
     (và `motion_vocab.tach="tu"` nếu là kiểu chính), mask_reveal→wipe (+`huong`), doi_ky_tu→typewriter (+`"do_may":"doi_ky_tu"`),
     none→none. Giữ trường `do_may` (kiểu máy gốc) trong từng động tác. `dai` = số đo (giây), `ease` = ease máy khớp
     (ghi nguyên ease máy khớp; `vuot`/số lần qua đích là số đo kèm theo). `nhip_dong` theo thời lượng vào trung vị.
   - `layout.anchors`: lấy từ `tinh.tam`/`anchor`/`so_voi_mat` theo vai; `so_voi`: tren_dau | duoi_cam (gồm ngang_nguc) | mat | khung;
     giữ `khoang_theo_cao_mat` (khoảng cách tính theo chiều cao mặt — engine đặt chữ theo mặt của video mới). `rong_max_chu` từ `rong_ti_le`.
   - `type_scale`: `co` = `co_uoc_1920` trung vị theo vai (px trên khung 1080×1920; HOA/không dấu đã nằm trong số đo),
     `hoa` theo đa số, `dam` từ `dam_uoc` (ước theo độ dày nét — xác nhận bằng mắt trên ảnh cận chữ; lệch rõ thì theo mắt và ghi lý do).
     `nhom_font` (sans_dam/sans_thuong/serif/display/viet_tay/mono) và `so_font_khac_nhau` lấy từ mô tả FONT ở bước 0 trên ảnh cận chữ.
   - `palette`: màu đo được (`mau_chu`, `nen.mau`) — nhan = màu bão hoà nổi bật nhất, sang = chữ sáng, toi = nền tối/viền. Không bịa màu.
   - TỪNG VAI trong `type_scale` còn có: `mau` (màu chữ của vai đó — lấy từ cận chữ, vd tiêu đề cam #FA5B4C, phụ đề trắng), `vien` (true/false), `bong` (true/false), `nen_mau` (màu nền thẻ sau chữ nếu có), `font_goi_y` (mô tả font NHÌN THẤY, vd "sans đậm hẹp", "script viết tay nghiêng", "serif italic" — máy tra kho font theo mô tả này). Đây là thứ máy áp lại đúng từng vai khi dựng — ghi đủ.
   - `graphics_vocab`: `the` từ `nen` (pill/rect/circle, `bo` px@1080, `nen_mo`, `co_vien`), `chu` (vien/bong/nen_khoi/gradient/hoa) theo
     đa số số đo; máy hay bỏ sót viền mảnh/bóng mờ/nền thẻ → ảnh cận chữ THẤY rõ thì ghi theo ảnh (nêu lý do trong `ghi_chu`).
     Đồ hoạ (`vai: do_hoa`) chỉ tính khi ảnh xác nhận là đồ hoạ phủ thật; `duong`, `hinh_minh_hoa`, `nen_moi` theo những gì thấy.
   - `rhythm_rules`: `giay_moi_lop_chu` = `tong_hop.chu_giay_tv`, `so_lop_dong_thoi_toi_da`, `khoang_trong_toi_da_giay`, `hook_giay`
     Thêm `karaoke` (phụ đề có tô màu từ đang nói không — nhìn dải soi) và `phu_de_hien`: "dan" = từng từ hiện ra rồi ở lại (word-by-word), "noi" = cả cụm hiện + tô từ đang nói, "cum" = cả cụm hiện, không tô.
     (giây chữ phủ đầu tiên), `phu_de` = "tu" nếu phụ đề vào word_by_word, "cum" nếu cả cụm, "tat" nếu không có; `phu_de_toi_da_chu`.
   - `dau_an_khong_chep`: câu chữ/tên kênh/logo/watermark của video mẫu (máy đã liệt kê chữ OCR) — để máy TRÁNH chép.
3. Write đúng MỘT file `{ra}` (JSON hợp lệ, đúng schema dưới; trường lạ ở cấp trên cùng KHÔNG được thêm). `ghi_chu` (≤ 600 ký tự):
   (a) mô tả ngắn chữ đã thấy theo vai — font, viền/bóng, nền thẻ, cách hiện (vd "nhãn: sans đậm HOA, viền đen dày, không nền,
   pop vượt rồi về; phụ đề: sans thường, bóng mờ, hiện từng từ"); (b) chỗ bạn sửa số máy và vì sao. Không hỏi lại.
4. (Luồng tab Học) Write thêm `bai-hoc.json` cùng thư mục: {{"ten": "tên ngắn cách làm", "da_hoc": ["các chi tiết kỹ thuật CÓ SỐ, vd
   'từ khoá HOA pop từ 125% về 100% trong 0,14 s, ease back, đặt trên đầu 0,4 chiều cao mặt'"], "hop_noi_dung": ["…"], "cau_truc": ["…"]}}.
   `da_hoc` gồm cả mô tả nhìn thấy ở bước 0 cho từng vai (font/viền/bóng/nền/cách hiện), kèm id sự kiện làm bằng chứng.

## Schema style-spec.json
{schema}
