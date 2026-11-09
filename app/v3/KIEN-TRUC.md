# Studio AI — kiến trúc và hợp đồng mô-đun (nguồn sự thật)

Mục tiêu: 1 phút thành phẩm ≤ 10–15 phút trên máy 8 luồng/16 GB (có hoặc không có card). Studio chỉ mang **engine + luật chất lượng + hồ sơ khách dạng dữ liệu**. AI (Claude Code chạy ngầm) quyết toàn bộ hình ảnh trong **tối đa 2 lượt**.

## 0. Quy ước chung
- Python 3.12, venv `app/.venv` (uv). Gói: numpy, opencv-python 4.11, pillow, skia-python, onnxruntime-directml, faster-whisper, fonttools. Không thêm gói nếu không thật cần; nếu thêm ghi vào `cai_dat/yeu_cau.txt`.
- Mọi đường dẫn qua `chung.py` (`DUONG`), không ghi cứng. Unicode NFC. In tiếng Việt: `PYTHONUTF8=1`.
- Khổ hình là tham số `(W, H)`; mặc định 1080×1920, 30 fps. Tọa độ chuẩn hoá 0..1 trong mọi file JSON; giây = giây **thành phẩm** (timeline) trừ nơi ghi rõ `a/b` = giây gốc.
- Mỗi bước ghi thời gian vào `du_an/nhat-ky-thoi-gian.json` qua `chung.DoThoiGian`.
- Không bao giờ sửa lặng lẽ: máy sửa số (dời khỏi mặt, thu vừa khung) thì ghi vào `kiem.json["may_sua"]` để AI và người dùng thấy.
- Không có bộ lọc màu/LUT/đen trắng khi AI không ghi rõ trong công thức.

## 1. Thư mục
```
<thư mục app>\
  app\
    studio_ai.py        CLI duy nhất: python studio_ai.py <lệnh> …
    chung.py            đường dẫn, cấu hình, json, sh(), băm, DoThoiGian, hwaccel
    cau_hinh.json       cấu hình app (kho_goc, du_lieu, cổng, model, mức sáng tạo)
    doc\                PHẦN ĐỌC: proxy.py · loi.py (Whisper) · mat.py (mặt + cảnh) · alpha.py (tách người) · tom_tat.py
    dung\               ENGINE: anim.py · chu.py (Skia) · lop.py (sprite) · camera.py · am.py · ghep.py (ffmpeg) · dung.py
    ai\                 dong_co.py (Claude) · cong_thuc.py (chuẩn hoá công thức → ke_hoach) · cheat_sheet.md · prompt_*.md
    nao\                luat_chat_luong.json · luat_gu.json · kiem.py · style_spec.schema.json
    kho\                lap.py (lập chỉ mục) · tim.py (tra) · xem_truoc.py (ảnh/âm xem trước) · api.py
    bia\                bia.py (ảnh bìa từ thiết kế của AI, Skia)
    viec\               quy_trinh.py (điều phối 1 việc, cache, song song)
    studio\             server.py (http.server + SSE) · web\ (index.html app.js style.css) · web\kho\ (giao diện kho, iframe)
    cai_dat\            bac_si.py (cài/kiểm) · mo_hinh.py (tải model) · yeu_cau.txt
    kiem_thu\           thu_*.py (chạy thử từng mô-đun bằng clip mẫu)
  du-lieu\
    ho-so\<id>\ho-so.json  (+ style-spec.json, gop-y.json, hoc\)
    du-an\<ten>\           (xem §3)
    kho-chi-muc\           kho.sqlite (bảng muc · lich_su · ai_nghia — 1.2.21, thay danh-muc.jsonl/lich-su-dung.jsonl/ai-nghia.json) · chi-muc.json · do-am.json · xem-truoc\
    mo-hinh\               yunet.onnx · modnet.onnx · (whisper dùng cache HF)
    phan-cung.json · nhat-ky\
```

## 2. `chung.py` (có sẵn, mọi mô-đun dùng)
```python
DUONG = {"app", "du_lieu", "ho_so", "du_an", "kho_chi_muc", "mo_hinh", "kho_goc", "ffmpeg", "ffprobe", "python"}
cau_hinh() -> dict                      # cau_hinh.json + mặc định
doc_json(p, mac_dinh=None) / ghi_json(p, obj)
sh(cmd: list, timeout=None, log=None) -> (ma, stdout, stderr)   # chạy lệnh, UTF-8, không mở cửa sổ
ffprobe(p) -> {"w","h","fps","dur","co_am","codec","xoay"}
bam(obj_or_path) -> sha256[:16]
class DoThoiGian: with DoThoiGian(du_an, "proxy"): ...   # ghi {"buoc","giay","luc"} vào nhat-ky-thoi-gian.json
phan_cung() -> {"luong","ram_gb","gpu","hwaccel":"cuda|qsv|d3d11va|none","encoder":"h264_nvenc|h264_qsv|libx264","ort":"DmlExecutionProvider|CPUExecutionProvider"}
log(viec, msg)                           # in + ghi du_an/nhat-ky.txt; Studio đọc file này để hiện tiến độ
```

## 3. Dự án `du-lieu/du-an/<ten>/`
```
viec.json              {"ten","ho_so","nguon":[{"duong","vai":"chinh|phu"}],"yeu_cau","khung":[W,H],"fps","che_do":"nhanh|ky","trang_thai"}
cache/                 proxy-<hash>.mp4 (540p, -g 30) · am-<hash>.wav (16k mono) · am48-<hash>.wav · alpha-<hash>.mp4 (xám) · base-<hash>.mp4 · sprite/<hash>/
doc/                   loi.json · mat.json · canh.json · tom-tat.md · bang-khung.jpg · cat-de-xuat.json
cong-thuc.json         AI viết (lượt 1); cong-thuc.v2.json (lượt 2 nếu sửa)
ke-hoach.json          máy chuẩn hoá từ công thức (đủ trường, đã giải hộp)
kiem.json              kết quả luật chất lượng + may_sua
dung/                  thanh-pham.mp4 · xem-lai.jpg (8 khung) · bia-1..3.png
giao/                  <ten>.mp4 · <ten>-bia.png · bao-cao.md
nhat-ky-thoi-gian.json · nhat-ky.txt
```

### 3.1 `doc/loi.json`
`{"tu":[{"w":"xin","a":0.42,"b":0.61,"p":0.93}], "cau":[{"a":..,"b":..,"txt":..}], "lang":[[a,b]], "dem":[[a,b,"ừm"]], "model":"large-v3-turbo"}` (a/b = giây **gốc** của nguồn chính; nhiều nguồn chính nối tiếp thì `src` thêm vào mỗi từ).

### 3.2 `doc/mat.json`
`{"fps_mau":5, "khung":[{"t":0.0,"mat":[{"x":0.41,"y":0.22,"w":0.2,"h":0.14,"diem":0.9}],"net":0.62}], "mat_tb":{"x","y","w","h","ti_le_co"}, "nguoi_ti_le":0.97}` (toạ độ 0..1 của khung gốc; t = giây gốc).

### 3.3 `doc/canh.json`
`{"cat":[t...], "canh":[{"a","b","kieu":"mat|man_hinh|khac","sang","dong"}], "mau_chu_dao":["#..","#.."]}`

### 3.4 `doc/cat-de-xuat.json` (máy đề xuất cắt lặng/ừm/lặp)
`{"giu":[{"src":0,"a":0.0,"b":8.7}, ...], "bo":[{"a","b","ly_do":"lang|dem|lap"}], "dur_sau":58.2}`

### 3.5 `doc/tom-tat.md` (≤6.000 ký tự) — xem `doc/tom_tat.py`: lời theo cụm với giây thành phẩm (sau cắt đề xuất), vị trí mặt trung bình + vùng trống, cảnh, nguồn phụ, gợi ý kho top-5 nhạc/sfx theo từ khoá, hồ sơ.

## 4. CÔNG THỨC AI viết — `cong-thuc.json` (hợp đồng quan trọng nhất)
AI viết gọn; `ai/cong_thuc.py` chuẩn hoá thành `ke-hoach.json` (điền mặc định, giải hộp, kiểm luật, tra kho). Mọi giây là giây thành phẩm sau khi áp `cat`.

```jsonc
{
  "khung": [1080, 1920],                 // tuỳ, mặc định theo viec.json
  "cat": [{"src":0,"a":0.0,"b":8.7}, {"src":0,"a":9.4,"b":30.1}],   // bỏ → dùng cat-de-xuat; AI có thể đảo/cắt thêm
  "phong_cach": {"mau_nhan":"#FFD200","mau_nhan2":"#22D3EE","mau_sang":"#FFFFFF","mau_toi":"#0E0E12",
                 "font":{"tieu_de":"<id kho|tên họ>","phu_de":"...","nhan":"..."}, "cam_giac":"1 câu"},
  "camera": [{"t":0,"z":1.0,"x":0.5,"y":0.5},{"t":3.2,"z":1.12,"x":0.5,"y":0.42,"ease":"out","dai":0.25}],
             // keyframe: tại t nhảy/trượt tới z (1..2), tâm x,y; "dai" = giây chuyển (0 = cắt), "ease"
  "lop": [
    {"id":"hook","kieu":"chu","t0":0.2,"t1":2.6,
     "noi_dung":{"text":"3 LỖI\nKHI QUAY","theo_loi":false},
     "kieu_dang":{"font":"tieu_de","co":120,"dam":800,"mau":"#fff","hoa":true,"gian":-0.02,"dong":1.1,"can":"giua",
                  "vien":[{"w":10,"mau":"#000"}],"bong":[{"x":0,"y":8,"mo":0,"mau":"#000c"},{"x":0,"y":20,"mo":30,"mau":"#0008"}],
                  "nen":{"mau":"#FFD200","dem":[28,16],"bo":18},"gradient":{"mau":["#fff","#FFD200"],"goc":90},"rong_max":0.86},
     "vi_tri":{"anchor":"mc","x":0.5,"y":0.3,"so_voi":"khung"},
     "anim":{"vao":{"kieu":"pop","dai":0.32,"ease":"back","tu":{"scale":0.6,"opacity":0,"y":24}},
             "ra":{"kieu":"fade","dai":0.18,"ease":"in","toi":{"opacity":0,"y":-16,"blur":6}},
             "tach":"tu","so_le":0.06,
             "keyframes":[{"t":1.2,"scale":1.06,"ease":"in_out","dai":0.2}]}},
    {"id":"the1","kieu":"the","t0":5,"t1":9,"noi_dung":{"text":"97% người mới mắc","icon":"<id kho|null>"},
     "kieu_dang":{"hinh":"pill|rect|circle","mau":"#111c","vien":{"w":2,"mau":"#FFD200"},"bo":24,"bong":[...],"dem":[32,20],"chu":{"co":52,"mau":"#fff","font":"nhan"}},
     "vi_tri":{"anchor":"bc","x":0.5,"y":0.12,"so_voi":"duoi_cam"},"anim":{"vao":{"kieu":"slide","tu":{"x":-60,"opacity":0},"dai":0.3,"ease":"out"}}},
    {"id":"anh1","kieu":"hinh","t0":12,"t1":15,"noi_dung":{"duong":"<id kho|đường dẫn>"},
     "kieu_dang":{"fit":"cover","bo":24,"bong":[...],"vien":{"w":4,"mau":"#fff"}},"vi_tri":{"anchor":"mc","x":0.5,"y":0.5,"w":0.8,"h":0.4},"anim":{"vao":{"kieu":"fade","dai":0.3}, "ken_burns":{"z":[1.0,1.08]}}},
    {"id":"clip1","kieu":"video","t0":20,"t1":26,"noi_dung":{"src":1,"a":3.0},"kieu_dang":{"fit":"cover","bo":0},"vi_tri":{"anchor":"mc","x":0.5,"y":0.5,"w":1,"h":1},"anim":{"vao":{"kieu":"fade","dai":0.2}}},
    {"id":"gach","kieu":"duong","t0":7,"t1":9,"noi_dung":{"loai":"gach_chan|mui_ten|khung|khoanh","tu":[0.2,0.5],"den":[0.8,0.5]},"kieu_dang":{"w":8,"mau":"#FFD200","ve":0.4}},
    {"id":"rieng1","kieu":"py","t0":30,"t1":34,"noi_dung":{"file":"lop-rieng/bieu_do.py"},"vi_tri":{"anchor":"mc","x":0.5,"y":0.5,"w":0.9,"h":0.5}}
  ],
  "phu_de": {"che_do":"cum|tu|tat","toi_da_chu":22,"karaoke":true,
             "kieu_dang":{"font":"phu_de","co":60,"dam":700,"mau":"#fff","mau_noi":"#FFD200","vien":[{"w":8,"mau":"#000"}],"nen":null,"hoa":false},
             "vi_tri":{"anchor":"bc","x":0.5,"y":0.3,"so_voi":"khung"},"anim":{"vao":{"kieu":"pop","dai":0.12,"ease":"out","tu":{"scale":0.9}}}},
  "nen_moi": [{"t0":0,"t1":58,"nen":{"kieu":"mau|gradient|anh|video|kho|mo","gia_tri":"#0E0E12|<id kho>|<đường>","mo":0.3},"vien_sang":{"w":3,"mau":"#FFD200"}}],
  "chuyen_canh": [{"t":9.4,"kieu":"flash|zoom|cut","dai":0.2}],
  "am": {"nhac":{"id":"<id kho|nghĩa>","db":-20,"ne_giong":true,"vao":1.0,"ra":2.0}, "sfx":[{"t":0.2,"id":"<id kho|nghĩa>","db":-6}], "giong_db":-16},
  "bia": {"khung_t":12.3,"thiet_ke":{...xem §6...}},
  "ghi_chu": "ý đồ 2–3 câu (không ảnh hưởng dựng)"
}
```
Quy tắc chuẩn hoá (`cong_thuc.py`):
- `font` nhận id kho (`font.<ten>`), tên họ (tra kho) hoặc vai (`tieu_de|phu_de|nhan`) → đường dẫn file; font phải đủ dấu tiếng Việt (kho đã đánh dấu), nếu không → thay font cùng nhóm, ghi `may_sua`.
- `vi_tri.so_voi`: `khung` | `mat` (x,y lệch so với tâm mặt) | `duoi_cam` (y tính từ cằm xuống) | `tren_dau`. Máy giải ra hộp pixel theo `mat.json` tại t0..t1 (mặt trung vị trong khoảng), áp vùng an toàn (9:16: trên 0.08, dưới 0.22, phải 0.10, trái 0.04), **không đè mặt** (luật chất lượng): đè → dời theo hướng gần nhất, không dời được → thu tới 0.8, vẫn không được → báo lỗi `de_mat` cho AI.
- `anim.vao/ra.kieu` ∈ fade · slide · pop · blur · wipe (trái→phải mask) · typewriter (chữ) · none; `ease` ∈ linear · in · out · in_out · back · spring · expo; `tach` ∈ none · tu · ky_tu (stagger `so_le` giây); `keyframes` tuỳ ý trường scale/x/y/rot/opacity/blur.
- Thiếu trường → mặc định trung tính (fade 0.25 out, anchor mc). Máy **không** thêm lớp, không đổi kiểu hoạt ảnh, không đổi màu.
- Kho: `id` dạng `nhac.<ten>` `sfx.<ten>` `font.<ten>` `nen.<ten>` `icon.<ten>` `lut.<ten>` `video.<ten>`; nếu là nghĩa (chuỗi không có dạng id) → `kho.tim` top-1, ghi `ke_hoach["tra_kho"]`.

## 5. ENGINE `dung/`
```python
# anim.py
ease(ten, u) -> float            # linear/in/out/in_out/back/spring/expo
trang_thai(anim, lt, dur) -> {"opacity","scale","x","y","rot","blur","wipe"}   # lt = giây từ t0, hợp nhất vào/ra/keyframes
tach_chi_so(anim, n_phan, lt) -> [u_i]   # stagger cho tách từ/ký tự

# chu.py (Skia + HarfBuzz qua skia.textlayout) — chữ chuẩn: kerning, variable font (wght), gradient, nhiều viền, nhiều bóng, pill
ve_chu(text, kieu_dang, W, H, rong_max_px, tach=None, u_phan=None) -> skia.Image RGBA (kích thước vừa khối + lề bóng) + meta {"w","h","dong":[...],"tu":[hộp từng từ]}
do_kich_thuoc(text, kieu_dang, rong_max_px) -> (w, h)

# lop.py — mỗi lớp → sprite theo thời gian, CHỈ trong hộp của nó
class Lop: __init__(ke_hoach_lop, ctx)  # ctx: W,H,fps,font resolver,kho,mat.json,alpha track
    hop() -> (x0,y0,x1,y1)  pixel, đã giải anchor/so_voi/vùng an toàn, có lề cho chuyển động
    ve(lt) -> np.uint8 RGBA (h,w,4) kích thước hộp   # lt từ t0
    tinh() -> bool            # True nếu nội dung tĩnh ngoài vào/ra (để dedup)
tao_lop(spec, ctx) -> Lop     # kiểu: chu, the, hinh, video, duong, py
ket_xuat_sprite(lop, thu_muc) -> {"concat": "lop.ffconcat", "x":x0,"y":y0,"t0","t1"}   # PNG seq dedup theo hash khung + ffconcat có duration
phu_de_sang_lop(loi_json, cat, phu_de_spec, ctx) -> [Lop]   # cụm ≤ toi_da_chu, karaoke theo từ

# camera.py
bieu_thuc_crop(keyframes, W, H) -> "crop=w='…':h='…':x='…':y='…',scale=W:H"   # biểu thức ffmpeg piecewise theo t, có ease

# am.py
bo_loc_am(ke_hoach, cat, nguon, kho) -> (inputs:list, filter:str, map)   # giọng concat theo cat, nhạc loop/fade/sidechain, sfx adelay, loudnorm I=-16

# ghep.py
dung_base(du_an, ke_hoach) -> base.mp4   # cat (trim/concat) + camera + nen_moi(alpha) — cache theo hash(cat, camera, nen_moi, nguon)
dung_thanh_pham(du_an, ke_hoach, sprites) -> thanh-pham.mp4   # base + overlay từng sprite (ffconcat input, enable between) + âm
# dung.py
dung(du_an, ke_hoach, che_do="that") -> {"video", "giay", "sprite_cache_hit": n}   # điều phối: sprite song song (ThreadPool), base cache, composite
xem_lai(video, n=8) -> xem-lai.jpg     # 8 khung + mốc giây để AI nhìn
```
Mã hoá: `chung.phan_cung()["encoder"]` (NVENC/QSV nếu thử được, không thì libx264 `-preset veryfast -crf 18`). Nguồn 4K giải mã bằng hwaccel nếu có.

## 6. BÌA `bia/bia.py` — thiết kế khai báo, cùng text engine
```jsonc
"bia": {"khung_t": 12.3,                                  // giây gốc lấy khung người (máy đưa 12 ứng viên trong bảng; AI chọn)
        "thiet_ke": {"nen":{"kieu":"mau|gradient|khung_mo|anh|kho","gia_tri":...,"mo":0.4,"toi":0.3},
                     "nguoi":{"co":1.15,"x":0.55,"y":0.62,"vien_sang":{"w":6,"mau":"#FFD200"},"bong":true,"lat":false},  // null = không tách người
                     "khoi":[{"hinh":"rect|pill|circle","x","y","w","h","mau","bo","xoay"}],
                     "chu":[{"text":"3 LỖI","kieu_dang":{...như lớp chu...},"vi_tri":{"anchor":"tl","x":0.07,"y":0.12},"xoay":-4}],
                     "hinh":[{"duong":"<id kho|đường>","x","y","w","h","bo","xoay"}]}}
```
`bia.ve(du_an, bia_spec, ctx) -> [bia-1.png, bia-2.png, bia-3.png]` (3 biến thể: như thiết kế, đổi màu nền/nhấn, không người) + kiểm: mặt thấy ≥ 1 (YuNet), chữ trong khung, độ tương phản. Tách người bìa dùng `doc/alpha.tach_anh(rgb, muc="cao")`.

## 7. ĐỌC `doc/`
```python
proxy.tao(du_an, nguon) -> {"proxy": path 540p mp4 (-g 30, h264), "am16": wav 16k mono, "am48": wav 48k}   # hwaccel nếu có; cache theo hash
loi.nhan(du_an, am16) -> loi.json       # faster-whisper large-v3-turbo int8, beam 1, vad_filter, word_timestamps; cache HF có sẵn
mat.quet(du_an, proxy) -> mat.json, canh.json   # YuNet 5 fps ở 320px + cắt cảnh (hist) + độ nét + màu chủ đạo; bang-khung.jpg 12 khung
alpha.tao_rãnh(du_an, proxy, a=None, b=None) -> alpha-<hash>.mp4 (xám, 720 cạnh ngắn… giữ tỉ lệ) # MODNet ONNX (DirectML|CPU), letterbox 512, alpha mềm, flow-warp thời gian, guided filter đầy đủ; chạy ưu tiên thấp, huỷ được
alpha.tach_anh(rgb, muc="cao") -> alpha float32 HxW        # 1 khung cho bìa (MODNet @1024 + guided)
cat.de_xuat(loi_json, am16) -> cat-de-xuat.json   # lặng >0.4 s (giữ 0.25), từ đệm (ừm/ờ/à/kiểu), lặp liền
tom_tat.viet(du_an) -> tom-tat.md
```
Điều phối (`viec/quy_trinh.py`): proxy → (Whisper ∥ mắt ∥ alpha-nền-ưu-tiên-thấp) → cắt đề xuất → tóm tắt → AI lượt 1 → chuẩn hoá + kiểm → dựng (sprite ∥, base cache) → xem-lai + bìa 3 bản → AI lượt 2 (duyệt/sửa) → dựng lại phần đổi → kiểm kỹ thuật → giao. Mỗi bước ghi thời gian.

## 8. AI `ai/`
```python
dong_co.goi(prompt_md, du_an, anh=[...], tiep=None, model=None) -> {"text","session","giay","usd"}   # claude -p, --output-format json, --allowedTools Read,Write,Bash(python chỉ trong du_an), --add-dir du_an; tiep = session id để --resume
luot_1(du_an) -> cong-thuc.json     # prompt: cheat_sheet.md + tom-tat.md + hồ sơ + bảng khung; AI phải Write cong-thuc.json
luot_2(du_an) -> {"duyet": bool, "cong_thuc": path}   # prompt: xem-lai.jpg + kiem.json + bia-1..3 → AI Write cong-thuc.v2.json hoặc ghi duyet.json
cong_thuc.chuan_hoa(du_an, cong_thuc) -> ke-hoach.json (+ lỗi chặn → trả AI)
```
`cheat_sheet.md` ≤ 3.500 ký tự: các kiểu lớp, trường, anim, anchor, ví dụ 3 lớp, cách ghi kho theo nghĩa, luật chất lượng (gạch đầu dòng), lớp `py` (hợp đồng `ve(t, W, H, ctx) -> RGBA`).

## 9. LUẬT `nao/`
- `luat_chat_luong.json`: id, mô tả, cách đo, luôn chặn: `de_mat`, `ngoai_vung_an_toan`, `doc_khong_kip` (≥ 0.3 s/từ chữ nhấn, ≥ 0.18 s/từ phụ đề), `chu_tran_khung`, `font_thieu_dau`, `tai_nguyen_khong_co`, `lech_tieng_hinh`, `khung_den`, `am_qua_to` (true peak > −1 dBTP), `chong_lop` (2 lớp chữ chồng nhau > 30%).
- `luat_gu.json`: id, mô tả, giá trị số mặc định **tắt**: `mat_do_toi_da`, `khoang_trong_toi_da`, `so_font_toi_da`, `bia_so_chu`, … Hồ sơ bật và đặt số.
- `kiem.py: kiem(du_an, ke_hoach) -> kiem.json {"loi":[{id,lop,t,mo_ta}], "may_sua":[...], "canh_bao":[...]}` — đo bằng hộp đã giải + `mat.json`, không giải mã video. Kiểm kỹ thuật sau dựng: `kiem_ky_thuat(video) -> {"khung_den","dong_bang","lufs","peak"}` (1 lượt ffmpeg 540p 4 fps + ebur128).

## 10. KHO `kho/`
```python
lap.lap(kho_goc, chi_muc_dir, tien_do=None)   # quét: wav/mp3/aac (dur, lufs ước, nhóm theo thư mục/tên), ttf/otf (họ, đậm, nghiêng, đủ dấu Việt qua cmap), cube/3dl, png/jpg (w,h, alpha), mp4/mov (dur, w,h, alpha?), json CapCut preset (chỉ đếm) → upsert bảng `muc` trong kho-chi-muc/kho.sqlite (kho/csdl.py; 1.2.21 — trước là danh-muc.jsonl), mỗi mục:
   {"id":"nhac.ten-khong-dau","loai":"nhac|sfx|font|lut|nen|icon|video|anh|khac","ten","duong","nhom":["…"],"tu_khoa":[…],"so_do":{…},"xem_truoc":"xem-truoc/<id>.jpg|png|mp3", "du_dau": true}
tim.tim(loai=None, nghia="", n=5, tranh=[]) -> [dict]     # BM25 bỏ dấu + đồng nghĩa VN (bảng nhỏ) + điểm nhóm
tim.lay(id) -> dict|None
xem_truoc.tao(muc) -> path   # font: PNG mẫu "Tiếng Việt có dấu – Ăn Ở Ệ 0123"; lut: jpg áp lên ảnh mẫu; nhạc/sfx: PNG dạng sóng; video: jpg khung 1 s; icon/nen: thumbnail
api.xu_ly(duong, query) -> (status, mime, body)   # /api/kho/ds?loai=&q=&n= · /api/kho/file?id= (Range) · /api/kho/xem-truoc?id= · /api/kho/lap (SSE tiến độ)
```
Giao diện `studio/web/kho/` (kho.html/js/css, độc lập, nhúng iframe): lưới theo loại, tìm, nghe nhạc/sfx ngay (audio), xem video hover, mẫu font hiện bằng chính font đó (FontFace), LUT trước/sau, hiệu ứng engine có video xem trước (`kho/hieu-ung/` do engine sinh từ `ai/cheat_sheet` ví dụ), nút "chép id" để dán vào yêu cầu.

## 11. STUDIO `studio/server.py` (http.server, cổng 4800)
API: `/api/ho-so` (CRUD) · `/api/viec` (tạo: nguồn[], yêu cầu, hồ sơ, chế độ) · `/api/viec/<id>/su-kien` (SSE từ nhat-ky.txt + thời gian) · `/api/viec/<id>/sua` (lời sửa → AI lượt 2 lại) · `/api/tep` (upload/drag-drop lưu vào `du-lieu/tai-len`) · `/api/kho/*` (uỷ quyền `kho/api.py`) · `/api/may` (phan-cung, bác sĩ) · `/media/<...>` (video/ảnh kết quả, Range).
Giao diện: trái hồ sơ · giữa việc (thả video, yêu cầu, tiến độ từng bước có giây, video kết quả + bìa + báo cáo, ô sửa) · phải tab Kho (iframe) / Hồ sơ (màu khoá, font khoá, luật gu bật tắt, style spec, góp ý) / Máy.

## 12. CLI `studio_ai.py`
`cai-dat` · `mo` (mở Studio) · `kho lap|tim|xem` · `viec tao --video … --ho-so … --yeu-cau "…" [--nhanh]` · `viec chay <ten>` (toàn bộ) · `doc <ten>` · `ai1 <ten>` · `dung <ten>` · `ai2 <ten>` · `giao <ten>` · `hoc --video mau.mp4 --ho-so X` · `thu <mo-dun>`.
