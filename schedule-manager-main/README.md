# Lịch Làm Việc — phiên bản 3.0

Ứng dụng quản lý lịch **cá nhân**, nâng cấp từ project FastAPI gốc. Frontend HTML/CSS/JavaScript thuần, không cần npm để chạy. Cơ sở dữ liệu SQLite ở local hoặc PostgreSQL khi triển khai. Giao diện hoàn toàn tiếng Việt, dùng được trên máy tính và điện thoại.

### Cập nhật giao diện 04/10/2026

- Sửa hiển thị dấu tiếng Việt ở hai tiêu đề “điều” và “tiếp” bằng phông chữ hệ thống, không phụ thuộc phông serif tải thêm.
- Vào **Tài khoản → Tùy chỉnh giao diện** để chọn một trong 5 bảng màu: xanh lá, xanh đại dương, tím lavender, hồng ấm áp và nâu cát.
- Màu áp dụng ngay, được lưu trên trình duyệt hiện tại và có thể khôi phục mặc định. Không đồng bộ lựa chọn màu giữa các thiết bị.
- Khi cập nhật GitHub, cần thay cả `app/static/index.html`, `app/static/style.css` và `app/static/app.js`. Chờ Vercel triển khai thành công trước khi tải lại website.

## 1. Chạy nhanh trên Windows

Khuyến nghị **Python 3.12**, hỗ trợ Python 3.11 trở lên. Cần Internet lần đầu để tải thư viện.

1. Giải nén ZIP, mở thư mục `schedule-manager-main` trong VS Code.
2. Mở Terminal tại thư mục có `requirements.txt`, chạy:

```powershell
py -3.12 setup_project.py
```

Nếu máy chỉ có lệnh `python` và đó là Python 3.11 trở lên:

```powershell
python setup_project.py
```

Script tự tạo `.venv`, tạo `.env` với khóa ngẫu nhiên, cài thư viện và nâng cấp cơ sở dữ liệu. Không ghi đè `.env` đã có.

3. Nhấp đôi `start.bat`, hoặc chạy:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

4. Mở **http://127.0.0.1:8000**, đăng ký tài khoản của bạn.
5. Để xử lý nhắc việc độc lập với trình duyệt, mở thêm `reminders.bat`:

```powershell
.\.venv\Scripts\python.exe -m app.reminders --loop
```

Giữ hai cửa sổ chạy. Nhắc email chỉ hoạt động khi đã cấu hình SMTP (mục 5). Không có tài khoản hay mật khẩu mẫu được cài sẵn trong bản ZIP.

**Linux/macOS:** `python3 setup_project.py`, sau đó `.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000`; worker: `.venv/bin/python -m app.reminders --loop`.

## 2. Chức năng đã triển khai

| Màn hình / nhóm | Chức năng |
| --- | --- |
| Hôm nay | Lịch hôm nay, công việc sắp đến hạn trong 7 ngày, việc quá hạn, đánh dấu hoàn thành nhanh |
| Lịch của tôi | Lịch tháng, tuần, ngày; khung giờ 24 giờ; hiện các việc trùng nhau theo cột; bấm ô giờ/ngày để tạo việc; **kéo thả để dời lịch**; kéo mép dưới trong lịch ngày/tuần để đổi thời lượng |
| Công việc | Thêm/sửa; mô tả; **địa điểm và liên kết họp**; thời gian; hạn chót riêng; ưu tiên; trạng thái; danh mục; checklist; lọc và phân trang |
| Thao tác nhanh | Nhân bản công việc sang ngày kế tiếp; dời việc quá hạn sang ngày mai; các thao tác vẫn kiểm tra trùng lịch |
| Mẫu công việc | Lưu nội dung biểu mẫu thành mẫu, áp dụng lại và xóa mẫu; giữ mô tả, danh mục, ưu tiên, thời lượng, nhắc việc, checklist, địa điểm và liên kết |
| Bộ lọc đã lưu | Lưu và áp dụng lại tổ hợp từ khóa, trạng thái, ưu tiên, danh mục, khoảng ngày, quá hạn và cách sắp xếp |
| Lịch lặp | Hằng ngày/tuần/tháng đến ngày được chọn; sửa/xóa một lần hoặc cả chuỗi; từng lần có trạng thái và checklist riêng |
| Cảnh báo trùng lịch | Kiểm tra trước khi tạo, thay giờ, mở lại công việc, nhập lịch hoặc khôi phục; người dùng xác nhận nếu vẫn muốn lưu |
| Nhắc việc | Nhắc trước giờ bắt đầu; thông báo trong ứng dụng; đã đọc/chưa đọc; **hoãn nhắc lại 10 phút**; thông báo hệ thống khi trang mở và được cấp quyền; gửi email bằng worker/cron |
| Danh mục | Tạo, sửa tên và màu, xóa; đổi tên tự cập nhật công việc; xóa danh mục vẫn giữ công việc |
| Thống kê | Tổng số theo trạng thái; quá hạn; báo cáo theo khoảng ngày; biểu đồ lịch/hoàn thành; tỷ lệ hoàn thành; phân bố danh mục; số hoàn thành đúng hạn; **xuất báo cáo PDF tiếng Việt** |
| Tập trung | Phiên Pomodoro 25 phút; bộ đếm nổi vẫn tiếp tục khi chuyển màn hình/tải lại trang; lưu tổng số phút thực tế theo công việc |
| Hoạt động | Dòng thời gian tạo, sửa, xóa, khôi phục, nhân bản, dời lịch và phiên tập trung; liên kết mở lại công việc còn tồn tại |
| Thùng rác | Xóa mềm; khôi phục; xóa vĩnh viễn sau xác nhận |
| Tài khoản | Hồ sơ, email, múi giờ, chọn nhận email, đổi mật khẩu, quên/đặt lại mật khẩu; vô hiệu hóa phiên khi đổi mật khẩu hoặc đăng xuất |
| Nhập/xuất | CSV và ICS; kiểm tra dữ liệu trước khi nhập; cảnh báo trùng lịch; bỏ qua UID ICS đã nhập; không nhập nửa chừng khi tệp lỗi |

Phạm vi bản này là **quản lý cá nhân**. Phần nhóm/dự án, giao việc cho người khác, bình luận và phân quyền nhóm là một hướng mở rộng riêng, chưa nằm trong phiên bản này.

## 3. Quy tắc lịch và thời gian

- API nhận ISO 8601 có độ lệch múi giờ (`2026-10-05T09:00:00+07:00`) hoặc `Z`; giá trị không có múi giờ được hiểu là UTC để tương thích dữ liệu cũ. Giao diện luôn gửi UTC có `Z`.
- Lưu trong DB dưới dạng **UTC không kèm timezone**, trả ra API có `Z`. Người dùng xem theo múi giờ hồ sơ, mặc định `Asia/Ho_Chi_Minh`.
- Khi chỉnh sửa, biểu mẫu dùng múi giờ của công việc, có ghi rõ dưới trường thời gian. Đổi múi giờ tài khoản không thay thời điểm thực tế của việc đã tạo.
- Kết thúc phải sau bắt đầu. Hạn chót riêng phải từ lúc bắt đầu trở đi. Quá hạn dùng `deadline` nếu có, nếu không dùng `end_time`; việc hoàn thành không bị tính quá hạn.
- Hai việc nối nhau đúng giờ không bị xem là trùng. Việc không có giờ kết thúc chiếm 1 phút cho phép kiểm tra xung đột; trên lịch giờ được hiển thị tối thiểu 30 phút để dễ bấm. Công việc hoàn thành không chặn lịch mới.
- Mỗi chuỗi lặp tối đa **366 lần**, ngày kết thúc không quá **2 năm** kể từ bắt đầu. Các lần được tạo sẵn trong DB, không tự kéo dài sau ngày kết thúc.
- Lặp theo tháng giữ ngày trong tháng: ngày 31 bỏ qua tháng không có ngày 31. Lặp theo múi giờ địa phương, giữ giờ tường qua đổi giờ mùa hè đối với các giờ hợp lệ.
- Với chuỗi có sẵn, sửa **một lần** hoặc **mọi lần chưa ở thùng rác**. Sửa cả chuỗi dời thời gian tương đối từ lần đang chọn, cập nhật cả nội dung, trạng thái và checklist theo biểu mẫu. Cấu hình tần suất/ngày kết thúc chỉ đặt lúc tạo; muốn đổi quy luật, xóa chuỗi cũ và tạo chuỗi mới. Không có thao tác “chỉ từ lần này trở đi”.
- Thùng rác không tự dọn. Khôi phục từng việc; xóa vĩnh viễn không thể hoàn tác.
- Tìm kiếm không phân biệt hoa/thường theo khả năng collation của cơ sở dữ liệu; chưa hỗ trợ tìm không dấu.

## 4. Nâng cấp từ phiên bản cũ

**Sao lưu database và `.env` trước khi nâng cấp.** Dừng ứng dụng cũ và worker trước khi thay mã nguồn. Giữ file `schedule.db` ở thư mục project hoặc giữ `DATABASE_URL` trỏ tới PostgreSQL cũ.

```powershell
.\.venv\Scripts\python.exe -m app.migrations
```

Migration chỉ thêm cột/bảng/index (bao gồm mẫu, bộ lọc, hoạt động, vị trí/liên kết và dữ liệu tính giờ) và chuyển các tên loại việc cũ thành danh mục, không xóa công việc/tài khoản. Có thể chạy lại. `AUTO_MIGRATE=true` chạy bước này khi ứng dụng khởi động; trên hệ thống nhiều worker nên chạy migration **một lần riêng**, sau đó đặt `AUTO_MIGRATE=false`.

Phiên đăng nhập cũ cần đăng nhập lại; mật khẩu cũ giữ nguyên. `SECRET_KEY` cần ít nhất 32 ký tự; không dùng khóa mẫu từ project cũ.

Dữ liệu thời gian của project gốc được giả định là UTC theo cách frontend gốc đã gửi. Nếu từng tự nhập giờ địa phương trực tiếp vào database, cần chuyển những bản ghi đó sang UTC trước. Công việc hoàn thành cũ không có thời điểm thực sự hoàn thành nên giữ `completed_at=NULL`, không bịa ngày và không đưa vào biểu đồ hoàn thành theo ngày.

API danh sách `/tasks` đã đổi từ mảng thuần thành `{items,total,page,page_size}` để hỗ trợ phân trang. Frontend trong ZIP đã cập nhật tương ứng. Client bên ngoài cần cập nhật nếu dùng API này.

## 5. Email và nhắc việc khi đóng website

Chỉnh `.env` theo máy chủ SMTP của bạn:

```dotenv
APP_BASE_URL=http://127.0.0.1:8000
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USER=your-account
SMTP_PASSWORD=your-smtp-or-app-password
SMTP_FROM=your-account@example.com
SMTP_SSL=false
SMTP_STARTTLS=true
```

Với SMTP SSL trực tiếp thường dùng cổng 465: `SMTP_SSL=true`. Dùng thông số do nhà cung cấp email cấp. Không đưa mật khẩu SMTP vào JavaScript hoặc Git. `APP_BASE_URL` phải là địa chỉ thật của ứng dụng để liên kết khôi phục mở đúng nơi.

1. Cấu hình SMTP.
2. Vào **Tài khoản**, bật **Nhận nhắc việc qua email**.
3. Chọn thời gian nhắc trong từng công việc.
4. Chạy `python -m app.reminders --loop` trên máy chủ luôn bật.

Worker kiểm tra mỗi 30 giây. Khi chỉ mở website mà chưa chạy worker, thông báo trong ứng dụng vẫn được tạo khi trang kiểm tra mỗi 30 giây; email không tự gửi. Thông báo hệ thống của trình duyệt cần người dùng bấm nút cấp quyền và trang đang mở; đây không phải Web Push khi đóng trình duyệt.

Một lựa chọn khác là cron chạy `python -m app.reminders` mỗi phút, hoặc gọi `GET/POST /internal/reminders` với header `Authorization: Bearer <CRON_SECRET>`. Khóa này chỉ cấu hình ở cron/máy chủ. Không chạy worker vòng lặp bên trong request serverless. Tần suất thực tế phụ thuộc cấu hình cron của nơi triển khai.

Thông báo có khóa chống trùng theo công việc + giờ bắt đầu + thời gian nhắc. Email được claim trước khi gửi, thử lại tối đa 5 lần, cách nhau ít nhất 5 phút khi lỗi. SMTP không đảm bảo “exactly once”: sự cố đúng lúc đã gửi nhưng chưa ghi DB vẫn có thể tạo thư lặp khi retry. Nhắc trễ tối đa 24 giờ sau giờ bắt đầu để tránh gửi hàng loạt lịch quá cũ khi máy chủ vừa bật lại.

Đổi giờ/đổi mốc nhắc, hoàn thành hoặc xóa công việc sẽ xóa thông báo nhắc cũ của việc đó. Danh sách thông báo vì vậy không phải nhật ký bất biến.

Khôi phục mật khẩu: token ngẫu nhiên, DB chỉ lưu hash, hết hạn 30 phút, dùng một lần; yêu cầu mới thay thế token cũ. Nếu chưa cấu hình SMTP, giao diện báo rõ chưa thể gửi khôi phục. Email thật chưa được gửi thử trong môi trường phát triển bản ZIP.

## 6. Nhập / xuất

**CSV:** UTF-8 (xuất có BOM để Excel đọc tiếng Việt). Các cột:

```csv
title,description,category,start_time,end_time,deadline,status,priority,location,meeting_url
Họp nhóm,Chuẩn bị nội dung,Công việc,2026-10-05T09:00:00+07:00,2026-10-05T10:00:00+07:00,,todo,high,Phòng A1,https://meet.example.com/team
```

`title`, `start_time` bắt buộc. Status: `todo`, `in_progress`, `done`; priority: `low`, `medium`, `high`. Ngày giờ không có offset trong CSV được hiểu theo múi giờ tài khoản. Nhập CSV lại sẽ tạo bản ghi mới, không tự gộp theo tên. Khi xuất, giá trị có thể bị Excel hiểu thành công thức được thêm dấu `'` để vô hiệu hóa.

**ICS:** hỗ trợ VEVENT, sự kiện cả ngày, DTSTART/DTEND/DURATION, SUMMARY, DESCRIPTION, LOCATION, URL, danh mục đầu tiên; lịch lặp DAILY/WEEKLY/MONTHLY có COUNT hoặc UNTIL, cùng EXDATE. Giới hạn 366 lần / 2 năm mỗi chuỗi. Tệp có RECURRENCE-ID hoặc RDATE bị từ chối rõ ràng; hãy xuất từng sự kiện riêng trước. URL chỉ được lưu làm liên kết công việc, máy chủ không truy cập URL hay tải tệp đính kèm trong ICS.

ICS xuất từng lần lặp thành sự kiện độc lập với UID ổn định. Nhập lại ICS của chính tài khoản hoặc UID đã nhập sẽ bỏ qua bản ghi đã có, kể cả ở thùng rác; không tự đồng bộ nội dung thay đổi. CSV/ICS dùng để trao đổi lịch, **không phải bản sao lưu đầy đủ**: checklist, lịch sử thông báo, mật khẩu và cấu hình tài khoản không nằm trong tệp xuất. Để sao lưu đầy đủ, sao lưu DB.

Công việc nhập có trạng thái hoàn thành nhưng thiếu thời điểm hoàn thành thực tế sẽ giữ `completed_at=NULL`, không tính vào biểu đồ hoàn thành theo ngày. Tổng số và tỷ lệ trạng thái vẫn tính bình thường.

Mỗi tệp tối đa **2 MB**, tối đa **1.000 công việc**. Tất cả được kiểm tra trước khi ghi; danh mục mới được tạo tự động. Khi gặp trùng lịch, giao diện cho xác nhận lưu tiếp.

## 7. Triển khai lên Vercel (GitHub -> Vercel)

Project đã được cấu hình sẵn để **push lên GitHub, Import vào Vercel là chạy được ngay**,
không cần thêm biến môi trường nào.

**Các bước**

1. Đẩy toàn bộ thư mục này lên một repository GitHub (nhớ giữ `vercel.json`, `api/index.py`,
   `requirements.txt`, `.python-version`).
2. Vào <https://vercel.com/new>, chọn **Import Git Repository** và chọn repo vừa tạo.
3. Framework Preset để **Other**, không cần Build Command hay Output Directory. Bấm **Deploy**.
4. Mở domain `*.vercel.app` là thấy giao diện. Kiểm tra `/health` để xem trạng thái database.

**Rất quan trọng — dữ liệu sẽ mất nếu không gắn database**

Mặc định app dùng SQLite trong `/tmp` của serverless function, nên dữ liệu chỉ tồn tại tạm
thời và biến mất khi function khởi động lại. Chế độ này chỉ để xem thử giao diện. Muốn dùng
thật, hãy gắn PostgreSQL:

1. Trong project trên Vercel: **Storage → Create Database → Postgres** (hoặc Neon / Supabase).
2. Vercel tự tạo biến `POSTGRES_URL`; app nhận biến này tự động. Nếu dùng nhà cung cấp khác,
   tự thêm `DATABASE_URL=postgresql://...` trong **Settings → Environment Variables**.
3. Redeploy. Bảng được tạo tự động ở request đầu tiên (`AUTO_MIGRATE=true`).

**Biến môi trường nên đặt cho bản chạy thật** (Settings → Environment Variables)

| Biến | Vì sao cần |
| --- | --- |
| `DATABASE_URL` | PostgreSQL để dữ liệu không mất. |
| `SECRET_KEY` | Khóa ký token riêng, tối thiểu 32 ký tự. Nếu bỏ trống, app tự sinh khóa tất định từ domain để vẫn đăng nhập được — tiện nhưng không an toàn. Tạo bằng `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `APP_ENV=production` | Bật quy ước production. |
| `APP_BASE_URL` | Chỉ cần khi dùng domain riêng; mặc định lấy domain Vercel. |
| `SMTP_*` | Chỉ khi muốn gửi email nhắc việc / quên mật khẩu. |
| `CRON_SECRET` | Chỉ khi muốn chạy cron gọi `/internal/reminders` (gửi kèm header `Authorization: Bearer <CRON_SECRET>`). |

**Ghi chú kỹ thuật**

- `vercel.json` chuyển mọi đường dẫn về `api/index.py`; FastAPI phục vụ luôn cả file tĩnh trong `app/static`.
- Migration chạy lazy ở request đầu tiên của mỗi tiến trình, vì sự kiện lifespan không đảm bảo chạy trên serverless.
- Nếu `postgres://` hoặc URL có `pgbouncer=true`, app tự chuẩn hóa lại cho SQLAlchemy/psycopg2.
- Không tạo tiến trình gửi mail dài hạn trong function; dùng cron HTTP có khóa.
- CORS mặc định cùng domain. Nếu tách frontend, đặt `CORS_ORIGINS`.

## 8. Kiểm thử và cấu trúc

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Tests dùng SQLite in-memory hoặc DB tạm, không đụng dữ liệu thật. Email được giả lập; không gửi thư cho người dùng. Xem `TEST_REPORT.md` để biết kết quả kiểm thử bản giao.

```text
app/
  main.py             # FastAPI, middleware, frontend
  models.py           # Công việc, mẫu, bộ lọc, hoạt động, người dùng, thông báo
  schemas.py          # Kiểm tra dữ liệu vào/ra
  migrations.py       # Migration bổ sung v1 -> v2
  services.py         # Lặp lịch, quyền sở hữu, kiểm tra trùng
  timeutils.py        # Chuẩn hóa UTC/múi giờ
  reminders.py        # Worker nhắc việc
  mailer.py           # SMTP
  activity.py         # Ghi nhật ký thay đổi công việc
  reports.py          # Tạo báo cáo PDF
  assets/             # Font Unicode kèm giấy phép để PDF chạy ổn định trên Vercel
  routers/            # API theo nhóm chức năng
  static/             # HTML, CSS, JS
api/index.py          # Entry point serverless gốc
setup_project.py      # Khởi tạo local
start.bat             # Chạy web trên Windows
reminders.bat         # Chạy worker trên Windows
tests/                # Kiểm thử tự động
```

Lưu ý: trình xử lý lỗi và API có thể trả mã 409 kèm danh sách `conflicts`; gửi lại `allow_overlap=true` chỉ sau khi người dùng đã xác nhận. Không có thao tác gửi mail thật, công bố website hoặc đăng nhập dịch vụ bên ngoài được thực hiện khi tạo bản ZIP này.

### Kiểm thử giao diện (tùy chọn)

Phần này cần Node.js, chỉ dành cho kiểm thử; chạy ứng dụng bình thường không cần npm. Khởi động web với **database thử riêng**, sau đó mở terminal thứ hai tại project:

```powershell
npm install
npx playwright install chromium
npm run test:browser
```

Mặc định test mở `http://127.0.0.1:8000`. Đổi địa chỉ qua biến `TEST_BASE_URL` nếu cần. Script tạo tài khoản mẫu mới, thao tác trên tài khoản đó và lưu ảnh vào `test-results/` (không đưa vào Git). Hình tham khảo đã chụp trong lần kiểm thử bản giao nằm tại `docs/screenshots/`.
