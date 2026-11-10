# Studio edit — Windows

Bản mã nguồn Studio 1.2.21 được chủ repository chỉnh sửa, có bộ mở dành cho Windows 10/11 x64. Mã nguồn ứng dụng nằm trong `app/`.

## Tải và chạy

Cài Git for Windows nếu máy chưa có Git, rồi chạy:

```powershell
git clone https://github.com/dungz123336/Studio-edit.git
cd Studio-edit
.\start.bat
```

Sau khi clone, những lần sau chỉ cần bấm đúp `start.bat` trong thư mục `Studio-edit`.

Lần đầu cần Internet để chuẩn bị Python 3.12, thư viện và công cụ còn thiếu; quá trình này có thể mất vài phút. Giữ cửa sổ thiết lập mở đến khi hoàn tất. Studio mở tại <http://127.0.0.1:4788>.

Mỗi máy đăng nhập Claude bằng tài khoản riêng. Mô hình nhận dạng giọng nói có thể tải ở lần sử dụng đầu tiên. Repository không chứa tài khoản, mã kích hoạt đã lưu, video hay dữ liệu cá nhân của máy nguồn.

Nếu máy chưa cài Claude Code, `start.bat` sẽ hiện hướng dẫn cài từ nguồn chính thức trước khi tiếp tục.

Các ô thêm clip chính, tư liệu phụ và video mẫu mở hộp chọn tệp của trình duyệt. Nếu đang mở một bản cũ, bấm `Ctrl+F5` sau khi cập nhật.

Nếu Windows báo **Application Control / lỗi 4551**, chính sách trên máy đang chặn file Python. Bộ cài dừng và giữ nguyên môi trường, không tự đổi file để vượt chặn. Nhờ quản trị viên kiểm tra chính sách và cung cấp bộ Python được phép chạy, rồi mở lại `start.bat`; không cần xóa repo hoặc tắt bảo vệ Windows.

### Chọn CPython chính thức đã cài trên máy

Nếu đã có **CPython 3.12 x64 chính thức, được chính sách của máy cho phép chạy**, bấm đúp `setup-system-python.bat` một lần. Tệp này chọn bộ Python tại `%LOCALAPPDATA%\Programs\Python\Python312\python.exe`; có thể truyền đường dẫn khác làm đối số. Bộ mở kiểm tra chữ ký hợp lệ của Python Software Foundation trên interpreter và các trình phóng venv tiêu chuẩn, rồi dùng `python -m venv --without-pip` tạo môi trường riêng trong `.runtime/system-venv`. Môi trường `app/.venv` hiện có được giữ nguyên.

Đây là lựa chọn rõ ràng của người dùng, không phải cách tự đổi interpreter khi Windows từ chối. Nếu tệp hoặc thư viện của bộ Python được chọn vẫn bị chặn, thiết lập dừng để quản trị viên xử lý. Chữ ký hợp lệ không bảo đảm mọi thư viện đều được chính sách cho chạy. Bộ mở không cài Python hoặc thay đổi chính sách Windows trong chế độ này. Sau khi thiết lập thư viện thành công, `start.bat`, `stop.bat` và lối tắt Desktop hiện có sẽ dùng môi trường đã chọn.

Python **3.12.10** là bản cuối có bộ cài Windows trên python.org, cũ hơn các bản vá bảo mật 3.12 hiện hành. Bộ mở hiển thị đúng phiên bản đang dùng; không tự tải bản cũ hay hạ phiên bản Python đã cài. Bản Studio này chưa hỗ trợ Python 3.13/3.14 do các thư viện đang ghim.

## Cập nhật mã

Đóng công việc đang chạy rồi bấm đúp `update.bat`. Bộ cập nhật dừng đúng bản Studio của thư mục này và lấy commit mới bằng `git pull --ff-only`; các tệp dữ liệu được Git bỏ qua vẫn ở trên máy.

Có thể làm thủ công bằng `stop.bat`, sau đó chạy:

```powershell
git pull --ff-only
.\start.bat
```

`git pull` chỉ lấy các commit đã được đẩy lên GitHub. Sửa mã ở máy khác xong cần commit và push thì máy này mới nhận được. Nếu Git báo có thay đổi cục bộ hoặc nhánh đã phân kỳ, giữ nguyên các tệp đó và xử lý trước khi cập nhật; không dùng lệnh xóa thay đổi để ép cập nhật.

Nút cập nhật có sẵn trong giao diện Studio chưa mặc nhiên dùng repository GitHub này. Hướng dẫn ở trên là cách cập nhật qua Git.

## Khi Claude báo lỗi

HTTP 522 nghĩa là máy chủ API không phản hồi qua Cloudflare. Tạo phiên mới vẫn dùng cùng kết nối API nên không khắc phục được sự cố máy chủ. Studio chờ hai phút giữa các lần thử; bấm **Dừng** nếu muốn ngừng chờ. Cần chờ nhà cung cấp khôi phục hoặc dùng một kết nối API hoạt động.

Nếu chuyển thư mục và phiên Claude cũ không còn, Studio tự mở phiên mới rồi gửi lại yêu cầu vừa rồi một lần. Lịch sử công việc trên máy vẫn được giữ. Mục đo tốc độ máy là tùy chọn và không ngăn gửi yêu cầu cho Claude.

## Dữ liệu trên từng máy

- `data/`: công việc, nhật ký và trạng thái Studio.
- `projects/`: dự án xuất video.
- `app/nao/ca-nhan/`: hồ sơ kênh; thư mục `_mau` là mẫu được theo dõi trong Git.
- `app/cau-hinh.json`: cấu hình máy do bộ mở tạo.
- `.runtime/`, `.cache/`, `app/.venv/`, `runtime/`, `tools/`: môi trường và công cụ tải trên máy.

Các dữ liệu và môi trường cục bộ được bỏ qua trong `.gitignore`. Không commit khóa API, tệp `.env`, tệp `.ban-quyen.json`, nội dung đăng nhập Claude hay GitHub.

Đây là bản tùy chỉnh của chủ repository, không phải toàn bộ gói nguyên bản được nhà phát hành ký. `app/TEP-GOI.json` được giữ để đối chiếu nguồn gốc; `app/LOCAL-CHANGES.json` ghi nhận những thay đổi ban đầu. Việc mở được giao diện không thay thế cho thử dựng một video hoàn chỉnh trên cấu hình máy đích.
