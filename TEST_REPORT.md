# Kết quả kiểm thử bản 2.0

## Môi trường

- Python 3.12, FastAPI TestClient, SQLAlchemy, SQLite.
- Node.js + Playwright 1.62.1, Chromium 153 (headless).
- Giao diện desktop 1440 × 1100 và mobile 390 × 844; múi giờ Asia/Ho_Chi_Minh.
- Dữ liệu kiểm thử riêng; SMTP được giả lập, không gửi email thật.

## Backend: 24 bài kiểm thử đạt

Lệnh: `python -m pytest -q --disable-warnings`.

- CRUD, checklist, thời điểm hoàn thành, xóa mềm, khôi phục, xóa vĩnh viễn.
- Phân tách công việc giữa hai tài khoản và chặn truy cập bằng ID của người khác.
- Dữ liệu sai: tiêu đề rỗng/quá dài, khoảng thời gian ngược, hạn chót không hợp lệ, mốc nhắc âm, checklist rỗng, múi giờ sai.
- Trùng lịch, xác nhận ghi đè cảnh báo, việc nối tiếp không bị báo trùng, giao với việc không có giờ kết thúc.
- Lịch lặp tuần, giới hạn lặp, ngày 31 khi lặp tháng, đổi giờ mùa hè ở America/New_York.
- Sửa một lần hoặc cả chuỗi; xóa cả chuỗi.
- Danh mục: đổi tên đồng bộ, tên trùng bị chặn, xóa vẫn giữ công việc.
- Phân trang, tìm kiếm, lọc theo ngày/ưu tiên, lọc hạn chót sắp tới; khoảng ngày nửa mở loại việc kết thúc đúng 00:00.
- Thống kê theo ngày hoàn thành thực tế, tỷ lệ và số hoàn thành đúng hạn.
- Tạo thông báo chống trùng, đã đọc, gửi email giả lập một lần, ngừng nhắc việc hoàn thành.
- Cron endpoint cần khóa riêng.
- Hồ sơ, đổi mật khẩu vô hiệu hóa token, khôi phục mật khẩu một lần.
- CSV/ICS xuất-nhập, bỏ qua UID trùng, lịch lặp ICS hữu hạn, tệp lỗi không ghi một phần dữ liệu.
- Nâng cấp schema từ cơ sở dữ liệu v1, giữ tài khoản/công việc/giờ gốc; chạy migration lại không tạo dữ liệu trùng.

Các cảnh báo DeprecationWarning còn xuất phát từ thư viện phụ thuộc; không phải bài kiểm thử thất bại.

## Trình duyệt: luồng thao tác đạt

- Đăng ký, đăng nhập, tạo công việc có mô tả/danh mục/mốc nhắc/checklist.
- Truy cập cả 9 màn hình; lịch tháng, tuần, ngày hiển thị sự kiện.
- Lọc công việc, chỉnh checklist, xóa và khôi phục qua giao diện.
- Tạo danh mục, tạo chuỗi 3 lần, sửa nội dung cả chuỗi.
- Cập nhật tên hiển thị; đăng xuất từ trang Tài khoản trên mobile.
- Không ghi nhận lỗi JavaScript chưa được xử lý trong luồng kiểm thử.
- Trang Hôm nay tại 390 px không bị tràn ngang.
- Đã xem trực quan ảnh desktop, lịch tuần và mobile; ảnh mẫu ở `docs/screenshots/`.

Mã kiểm thử được kèm tại `tests/browser_smoke.cjs`. Chạy trên database thử riêng vì bài kiểm thử sẽ tạo tài khoản và công việc mẫu.

## Giới hạn xác minh

- Chưa gửi thư qua máy chủ SMTP thật, chưa kiểm tra giao nhận qua nhà cung cấp email.
- Chưa triển khai lên hosting hoặc chạy trên PostgreSQL thực.
- Chưa chạy trực tiếp trên Windows, Safari, Firefox hoặc điện thoại vật lý.
- Chưa kiểm thử tải lớn hay nhiều worker đồng thời. Migration production cần chạy một tiến trình riêng.
- Kết quả này xác nhận các luồng đã nêu, không thay thế đánh giá vận hành/bảo mật toàn diện cho sản phẩm thương mại.
