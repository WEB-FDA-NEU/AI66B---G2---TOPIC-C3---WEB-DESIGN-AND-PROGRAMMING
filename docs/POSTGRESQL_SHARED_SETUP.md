# Chạy LuxStay với PostgreSQL dùng chung

## Mô hình triển khai

Các thiết bị truy cập một origin LuxStay. Reverse proxy HTTPS chuyển frontend, `/js/runtime-config.js`, `/uploads` và `/api` đến một FastAPI. FastAPI dùng một DATABASE_URL PostgreSQL. SQLite tiếp tục phục vụ development/test riêng.

Chọn một máy server có Python và PostgreSQL. Các thành viên truy cập URL của máy này, không chạy thêm database riêng để thay thế nguồn chung. Dùng một instance trước, vì ảnh upload nằm trên filesystem và rate limiter hiện nằm trong process.

## PostgreSQL và bí mật

Người quản trị PostgreSQL tạo role LOGIN không SUPERUSER và database thuộc role đó bằng công cụ quản trị hiện có. Tạo password qua cơ chế nhập ẩn của công cụ, không đưa vào Git hoặc lịch sử command. Ví dụ tên role `luxstay_app`, database `luxstay`. Chỉ cho backend kết nối port 5432. PostgreSQL trên cùng server có thể chỉ listen loopback. PostgreSQL managed cần firewall allowlist backend và TLS `sslmode=verify-full` cùng CA phù hợp.

Với PostgreSQL tự quản, quản trị viên có thể mở psql và chạy các lệnh sau sau khi xác nhận role/database chưa tồn tại. Với database hiện có, giữ nguyên dữ liệu và cấp quyền theo chính sách môi trường.

```sql
CREATE ROLE luxstay_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
\password luxstay_app
CREATE DATABASE luxstay OWNER luxstay_app;
```

`\password` là lệnh psql yêu cầu nhập password ẩn, cần chạy riêng trong psql. Trên PostgreSQL managed, dùng cơ chế cấp database/user của nhà cung cấp với quyền tương đương.

Cấu hình `DATABASE_URL` qua environment hoặc file `backend/.env` được bảo vệ và gitignore. Ví dụ cấu trúc URI khi password được cấp qua pgpass của tài khoản dịch vụ

```dotenv
DATABASE_URL=postgresql+psycopg://luxstay_app@127.0.0.1:5432/luxstay
APP_ENV=production
FRONTEND_MODE=shared
SERVE_FRONTEND=true
CORS_ORIGINS=https://luxstay.example.org
JWT_EXPIRE_MINUTES=60
AUTH_RATE_LIMIT=20
UPLOAD_DIR=/var/lib/luxstay/uploads
```

`luxstay.example.org` cần được thay bằng domain thực. Cấp `JWT_SECRET` ngẫu nhiên ít nhất 32 byte qua secret manager hoặc file environment chỉ tài khoản dịch vụ đọc được. Có thể sinh bằng `secrets.token_urlsafe(48)` rồi lưu trực tiếp vào kho bí mật. Giữ nguyên secret khi restart để phiên còn hạn tiếp tục hoạt động. Không đưa DATABASE_URL/JWT_SECRET vào JavaScript. Không dùng database test cho dữ liệu nhóm.

Psycopg hỗ trợ pgpass mặc định của tài khoản chạy dịch vụ. Linux dùng `~/.pgpass` quyền 0600, Windows dùng `%APPDATA%/postgresql/pgpass.conf`. File này chứa secret, phải bảo vệ ngoài repository. Environment có password trong URL cũng được hỗ trợ, cần URL-encode ký tự đặc biệt và bảo vệ file tương tự.

SQLAlchemy hiện dùng pool_pre_ping và QueuePool mặc định của PostgreSQL, pool_size 5, max_overflow 10, timeout 30 giây. Với một worker, dự trù tối đa 15 kết nối cho process, cộng migration/ops. Chỉ tăng worker khi đã đối chiếu giới hạn kết nối, rate limiting và storage upload chung.

## Cài đặt, migration và admin

Chạy từ repository root, dùng virtualenv và dependency lock hiện có. Sao lưu database đang có trước khi nâng phiên bản. Các lệnh dưới đây do người vận hành chủ động chạy sau khi xác nhận DATABASE_URL trỏ đúng môi trường.

```powershell
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini heads
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini current
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/Scripts/python -m backend.bootstrap_admin
```

Head đã kiểm tra trong source là `0007_booking_holds`. Đối chiếu lại `heads` khi nâng code. Startup không tự migrate. Bootstrap hỏi email/tên và password hai lần bằng getpass, tạo admin đầu tiên bằng Argon2id, không thêm catalog demo. Lệnh từ chối khi đã có admin hoặc email trùng. Không dùng bootstrap để nâng quyền một tài khoản đang có. Có PostgreSQL advisory lock để hai lệnh bootstrap đồng thời không tạo hai admin.

Database rỗng có catalog rỗng. Đăng ký customer, nộp hồ sơ Host, admin duyệt rồi Host đăng nhập lại để tạo homestay/phòng. Không chạy `backend.seed` trên nguồn dữ liệu chung theo quy trình này. Lệnh seed development hiện có vẫn là thao tác riêng có chủ đích.

## LAN development

Trên một máy server trong mạng tin cậy, dùng PostgreSQL riêng cho nhóm. Đặt APP_ENV=development, FRONTEND_MODE=shared, SERVE_FRONTEND=true và DATABASE_URL của server. Dùng bộ dữ liệu thử, vì HTTP LAN truyền thông tin qua mạng không mã hóa.

```powershell
backend/.venv/Scripts/python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --no-access-log
```

Xác định IPv4 LAN của server bằng `ipconfig`. Ví dụ server `192.168.1.20`, tất cả máy mở `http://192.168.1.20:8000/`. API_BASE tự dùng `http://192.168.1.20:8000/api`, kể cả mở trang không có query. Không dùng localhost trên máy client. Nếu firewall chặn, người quản trị cho phép inbound TCP 8000 từ subnet LAN trên Private profile. Kiểm tra các máy cùng mạng, không bị guest Wi-Fi/AP isolation hoặc VPN tách tuyến. Không mở port PostgreSQL cho trình duyệt. Không port-forward dịch vụ development ra Internet.

Kiểm tra `/api/health` và `/api/ready` từ máy client, sau đó thử đăng ký trên A và đăng nhập trên B. Đây là bước thực hiện tại mạng của nhóm, chưa được xác minh từ môi trường coding này.

## Staging Internet

Triển khai một server có domain và PostgreSQL dùng chung. Chạy Uvicorn loopback 127.0.0.1:8000 phía sau reverse proxy TLS. Ví dụ Caddy cấu hình tối thiểu sau khi domain đã trỏ về server và cổng 80/443 được cho phép

```caddyfile
luxstay.example.org {
    reverse_proxy 127.0.0.1:8000
}
```

Ví dụ này cần được kiểm tra trên server đích. Caddy quản lý chứng chỉ khi đáp ứng điều kiện DNS/ACME. Dùng service manager để tự khởi động lại Uvicorn. Chỉ tin forwarded headers từ reverse proxy loopback, ví dụ `--proxy-headers --forwarded-allow-ips 127.0.0.1`. Không công khai port Uvicorn/5432. Tắt access log có dữ liệu nhạy cảm, không log Authorization/request body hoặc URL kết nối. Thiết lập giới hạn request/rate/concurrency tại proxy theo tải thực tế. CORS dùng origin chính xác. Khi cùng origin, frontend không cần cross-origin CORS.

Giữ `FRONTEND_MODE=shared` và phục vụ tất cả đường dẫn qua FastAPI. Nếu tách static frontend sang dịch vụ khác, reverse proxy vẫn phải chuyển `/js/runtime-config.js`, `/api` và `/uploads` đến backend. Phục vụ module runtime tĩnh của bản demo sẽ làm trang chọn mock. Không đưa file cấu hình bí mật, `.env` hoặc thư mục backend lên static hosting.

## Backup, restart và cập nhật

- Đặt backup PostgreSQL và thư mục UPLOAD_DIR ở vị trí được bảo vệ ngoài repository. Dùng pg_dump custom format với credential từ pgpass/service, ví dụ `pg_dump --format=custom --file=<file-moi.dump> "service=luxstay"`. File service cần được cấu hình trên server. Kiểm tra mã thoát và dung lượng backup.
- Restore rehearsal vào database mới riêng, ví dụ `luxstay_restore_test`, dùng `pg_restore --exit-on-error --no-owner --dbname=<database-restore> <backup.dump>`. Không dùng `--clean` trên nguồn dữ liệu đang hoạt động. Đối chiếu revision, counts, FK và thử API trên bản restore.
- Chốt lịch backup, retention và nơi lưu ngoài server theo nhu cầu nhóm. Theo dõi kết quả job và thử restore định kỳ. Mã hóa và giới hạn quyền đọc bản sao.
- Khi cập nhật, dừng hoặc tạm chặn tác vụ ghi, backup, kiểm tra restore/migration trên bản sao, deploy code, chạy Alembic một lần rồi restart dịch vụ. Kiểm readiness và smoke đăng nhập/booking trước khi mở lại. Nếu upgrade lỗi, giữ nguyên bản nguồn và điều tra trên bản sao. Không reset hoặc downgrade phá dữ liệu để xử lý lỗi.
- Restart giữ nguyên PostgreSQL, JWT_SECRET và UPLOAD_DIR. Không dùng thư mục tạm cho các thành phần này trên staging.

## Dữ liệu cũ

Không có import tự động từ localStorage/SQLite. Giữ bản nguồn nguyên trạng. Trước import cần xuất dữ liệu có đồng ý, chuẩn hóa email, đối chiếu account trùng, xác minh host đã duyệt, ánh xạ homestay/phòng, rà soát trùng booking và tồn phòng theo từng đêm, rồi dry-run có báo cáo. Mock PBKDF2 và phiên `mock-token` không chuyển thành JWT hoặc quyền thật. Tài khoản cần quy trình đặt lại mật khẩu được xác minh. Booking thiếu owner, phòng, ngày hoặc snapshot đáng tin cậy phải đưa vào danh sách xử lý thủ công. Legacy Item không tự trở thành Homestay.

## Giới hạn vận hành

Chưa cấp server/domain/TLS hoặc deploy. Chưa kiểm tra firewall LAN hay đường Internet thực tế. Payment gateway, email verification/reset password, offsite backup rehearsal, giám sát và load test là các hạng mục triển khai cần người vận hành hoàn tất. Các khoản thanh toán hiện là manual/pending hoặc simulation dev/test được phân biệt rõ.
