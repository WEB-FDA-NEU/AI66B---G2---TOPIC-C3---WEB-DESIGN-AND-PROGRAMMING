# Kiểm thử nguồn dữ liệu dùng chung

Ngày chạy 2026-11-15. Dùng Chrome thật qua CDP, hai process/profile riêng, một Uvicorn phục vụ frontend và API, một PostgreSQL test. Hai context có sessionStorage và localStorage độc lập. Chưa dùng hai máy vật lý hoặc mạng LAN/Internet.

## Lệnh tái lập

```powershell
backend/.venv/Scripts/python tools/test_backend_postgres.py --browser-only
backend/.venv/Scripts/python tools/test_backend_postgres.py
backend/.venv/Scripts/python tests/mock-accounts-browser.py
backend/.venv/Scripts/python tests/ui-browser.py
```

Runner PostgreSQL dùng binaries PostgreSQL 17 trên máy Windows, tạo cluster tạm loopback và database `luxstay_test`. Script browser chỉ chấp nhận PostgreSQL test có tên database kết thúc `_test`, tạo schema ngẫu nhiên và chỉ xóa schema đó khi kết thúc. Không sử dụng database development hoặc dữ liệu nhóm. Nếu đã có server test riêng, đặt TEST_POSTGRES_URL bảo mật rồi chạy `tests/shared-postgres-browser.py` trực tiếp.

## Kết quả đã chạy

| Nhóm | Kết quả | Bằng chứng |
|---|---|---|
| Shared PostgreSQL browser | 30 PASS | `SHARED_BROWSER_RESULTS.json` |
| Mock account browser | 44 assertion PASS | Chrome profile riêng, đăng ký/reload/login/profile/password/host cancellation |
| UI smoke | 72 tổ hợp PASS, 240 assertion | 18 trang × 375/768/1024/1440px, 0 overflow, 0 runtime error |
| Backend SQLite và PostgreSQL | 548 PASS, 0 FAIL, 4 SKIP, 0 XFAIL | 915.33 giây, runner cluster riêng, bao gồm migrations/concurrency |
| Alembic source head | `0007_booking_holds` | `alembic heads` đã chạy |
| Dependency consistency | PASS | `pip check`, không có broken requirements |

## Mapping yêu cầu nghiệm thu

| Yêu cầu | Phần đã kiểm chứng |
|---|---|
| Đăng ký trên A, đăng nhập B | Cùng user ID được đối chiếu trực tiếp PostgreSQL, hai JWT session độc lập |
| Booking chung | A tạo, B đăng nhập cùng customer và tải lại lịch sử thấy đơn từ DB |
| Customer–Host | Host sở hữu thấy đơn, Host nhận phòng, Customer đọc checked_in, Host hoàn tất, Customer đánh giá |
| Xác nhận booking | Engine hiện tại tạo confirmed ngay. Không sửa nghiệp vụ để thêm pending. Các transition/legacy pending được kiểm tra trong backend suite |
| Homestay chung | Host tạo homestay/phòng qua API adapter, cùng Host ở context khác thấy bản ghi |
| Host approval | Pending bị chặn Host API, admin ở context khác thấy application thật và approve, phiên cũ bị thu hồi, đăng nhập lại nhận Host, catalog ban đầu rỗng |
| Admin | Danh sách user được so sánh chính xác với bốn account trong PostgreSQL test |
| Persistence | Restart Uvicorn phục vụ cả frontend/API, giữ PostgreSQL và secret, reload vẫn thấy booking và phiên còn hạn |
| API failure | Chặn API booking trong browser, thấy error state. Dừng backend hoàn toàn, adapter trả lỗi kết nối. Kho mock bị cài dữ liệu mồi vẫn nguyên trạng và không được dùng làm fallback |
| Security | Customer bị từ chối Host/Admin, Host bị từ chối Admin, Host B không đọc được homestay Host A, public runtime config không chứa PostgreSQL/JWT secret |
| Giá/tồn phòng/idempotency | Cùng key replay một booking, đối chiếu PostgreSQL có đúng hai RoomNight cho hai đêm. Regression engine kiểm tra tranh chấp đồng thời và rollback |
| Reviews/payment | Đánh giá đủ điều kiện đọc được ở context khác. Payment vẫn pending/manual, không tự ghi paid |

Các thao tác nghiệp vụ shared test dùng API adapter thật trong browser context, cùng bước hiển thị lịch sử qua DOM. Đây là kiểm tra multi-session ở localhost. Không tuyên bố toàn bộ thao tác đã được bấm thủ công trên hai máy.

## Test thủ công trên mạng nhóm

1. Triển khai theo POSTGRESQL_SHARED_SETUP, ghi nhận một URL duy nhất và `/api/ready` trả head đúng. Tạo admin đầu tiên chủ động.
2. Máy A đăng ký một email thử. Máy B mở cùng origin, đăng nhập email đó. Kiểm tra profile giống nhau, bỏ query URL rồi reload vẫn dùng API.
3. Customer gửi đơn Host. Admin dùng profile trình duyệt khác duyệt. Customer đăng nhập lại, thấy dashboard rỗng và tạo homestay/phòng thật.
4. Customer khác đặt khoảng ngày còn phòng. Máy B cùng customer reload lịch sử, Host reload danh sách, đối chiếu cùng code và tiền. Booking mới hiện confirmed theo engine hiện tại, payment vẫn pending/manual.
5. Thử hủy đơn hợp lệ, Host refresh thấy cancelled. Với đơn đến ngày nhận phòng, Host nhận phòng/hoàn tất, Customer refresh và đánh giá.
6. Restart dịch vụ server theo runbook, kiểm tra dữ liệu vẫn tồn tại. Ngắt API ở môi trường test, xác minh thấy lỗi và không có dữ liệu mock chen vào.
7. Ghi lại URL/origin, revision, thời điểm, trình duyệt và kết quả. Không chụp token, mật khẩu hoặc DATABASE_URL chứa secret. Chỉ đánh dấu LAN/Internet đạt sau khi thực hiện trên mạng tương ứng.

## Hồi quy test cũ

Hai test harness cũ cần đồng bộ với source mới nhất. UI phải chờ lịch/phòng tải xong trước khi chọn. `host-register.html` hiện chuyển tới profile, test dùng form cũ đã được cập nhật để kiểm tra redirect và chặn tự cấp quyền admin. Không giảm assertion snapshot, phân quyền hoặc idempotency. Snapshot frontend cũ được lưu nguyên bản trước khi cập nhật theo source hiện tại và các chỉnh sửa được phép.

Lần backend regression đầu ghi nhận 545 pass, 3 fail và 4 skip. Hai fail tìm kiếm phát sinh vì fixture điện thoại `0912345678` cũng khớp từ khóa số `2`/`3`. Đã dùng số điện thoại không trùng từ khóa trong test, giữ nguyên các assertion và logic tìm kiếm. Fail concurrency xuất hiện khi approve lấy khóa trước, request apply đọc lại role Host và trả 403. Test hiện yêu cầu approve 200, apply bị từ chối 403/409, đồng thời đối chiếu chính xác role Host, một application approved và đúng một lịch sử approve trong DB. Chạy lại riêng các trường hợp này đạt 3 pass, 1 skip ở SQLite vì test dành cho row lock PostgreSQL, 548 deselected. Lần chạy đầy đủ cuối đạt 548 pass, 4 skip, không fail/xfail. Bốn skip là các tình huống row-lock PostgreSQL khi fixture chạy trên SQLite. Các tình huống tương ứng đã chạy trên PostgreSQL.
