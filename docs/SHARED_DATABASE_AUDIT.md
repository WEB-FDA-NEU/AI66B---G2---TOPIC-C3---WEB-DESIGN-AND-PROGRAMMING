# Cập nhật sau audit

Đã chuyển frontend sang API mặc định và bỏ nhánh localStorage khỏi CRUD booking customer. Các nhận định mock mặc định bên dưới mô tả nguyên nhân ở phiên bản trước. Xem [BOOKING_SYNC_FIX.md](BOOKING_SYNC_FIX.md) cho trạng thái hiện tại và giới hạn triển khai.

# Audit dữ liệu dùng chung

Audit ngày 2026-11-15 trên source hiện tại, trước khi sửa cấu hình shared. Các kết luận dưới đây dựa vào code. Chưa có thông tin server của nhóm hoặc bằng chứng từ hai máy vật lý.

## Nguyên nhân

- `frontend/js/config.js` đặt `USE_MOCK=true`. URL thông thường chọn scope `mock`, `?mode=api` bật toàn bộ adapter, `?accounts=api` chỉ bật tài khoản. Mở cùng file HTML trên hai origin khác nhau tạo hai kho localStorage độc lập.
- `frontend/js/api.js` trong mock đọc JSON và ghi tài khoản, homestay, phòng, booking, đánh giá, đơn Host vào localStorage. `auth.js` dùng localStorage cho phiên mock. Đây là dữ liệu trên từng trình duyệt.
- Trong API Mode, `api.js` gọi FastAPI cho toàn bộ nghiệp vụ đã tích hợp. `auth.js` giữ bearer token và cache UX trong sessionStorage. Checkout giữ intent/idempotency trong sessionStorage để retry. Giá, tồn phòng và quyền lấy từ backend.
- Backend `Settings.from_env()` mặc định kết nối `backend/luxstay.db`. Hai máy tự chạy Uvicorn với cấu hình mặc định sẽ dùng hai SQLite riêng, kể cả khi cả hai URL có `mode=api`.
- Kiểm tra cấu hình cục bộ đã xác nhận workspace này chưa có `backend/.env` và process kiểm tra không có DATABASE_URL được cấp. Khởi chạy bằng cấu hình mặc định tại đây sẽ chọn SQLite cục bộ. Không kết nối hoặc sửa database cá nhân để thu thập bằng chứng này. Environment của server hoặc máy thành viên khác vẫn cần người vận hành đối chiếu.
- PostgreSQL cũng bị tách nếu các backend dùng DATABASE_URL trỏ tới các database/server khác nhau. Code chưa thể chứng minh cấu hình đang chạy trên máy của từng thành viên. Không đọc hoặc công bố credential cá nhân trong audit này.
- API_BASE mặc định `/api`. Riêng localhost/127.0.0.1 cổng 5500/5501 dùng cùng hostname cổng 8000. Localhost luôn là máy đang truy cập. Frontend trên cổng ngẫu nhiên hoặc LAN static server cần cấu hình API origin thích hợp.
- `accountHref` và click handler giữ cờ API trên điều hướng HTML. Link được sao chép thiếu query hoặc mở trực tiếp URL mới sẽ quay về mock mặc định. Cần cấu hình mode ở server cho shared deployment, thay vì yêu cầu mọi người giữ query.

## Mapping nguồn dữ liệu

| Nghiệp vụ frontend | API thật | Nguồn canonical API Mode |
|---|---|---|
| Đăng ký, đăng nhập, đăng xuất | POST `/api/auth/register`, `/login`, `/logout` | users, auth_sessions |
| Hồ sơ, mật khẩu, xóa tài khoản | `/api/me/profile`, `/password`, `/account` | users, thu hồi phiên |
| Xin Host và theo dõi | POST `/api/host/apply`, GET `/api/me/host-application` | host_applications |
| Admin duyệt/từ chối | `/api/admin/host-applications/{id}/approve`, `/reject` | application history và users |
| Catalog, tìm kiếm, đánh giá | `/api/items`, `/{id}`, `/{id}/reviews` | homestays, rooms, reviews |
| Lịch trống, quote, giữ phòng | `/api/items/{id}/availability`, `/calendar`, `/api/bookings/quote`, `/api/me/booking-hold` | inventory, room_nights, booking_hold_nights |
| Booking và hủy | `/api/me/bookings`, `/{id}`, `/{id}/cancel` | bookings, booking_lines, history |
| Payment status | `/api/me/bookings/{id}/payments` | payments, payment events |
| Homestay/phòng/chặn ngày Host | `/api/host/homestays`, `/rooms`, `/rooms/{id}/blocks` | owner-filtered database records |
| Host booking và dashboard | `/api/host/bookings`, `/{id}/status`, `/dashboard` | cùng booking, ledger, reporting |
| Admin users/catalog/dashboard | `/api/admin/users`, `/homestays`, `/overview` | database, backend authorization |
| Ảnh upload | POST `/api/uploads` | filesystem của server, URL công khai có kiểm tra |

## Database và bảo mật hiện tại

SQLAlchemy hỗ trợ SQLite và PostgreSQL qua psycopg. Alembic head đọc từ source là `0007_booking_holds`. Startup không migrate/create_all. RoomNight có unique `(room_id, unit, night)`, booking có unique customer/idempotency key. Booking service có row locks, server pricing và rollback theo request. Host/Admin authorization được kiểm tra trong dependencies/routers, ownership trên truy vấn tài nguyên. JWT có chữ ký, expiry và phiên có thể thu hồi. CORS dùng allowlist.

Một process backend có một engine theo DATABASE_URL. Mock không có SQL database. Nhiều process có thể cùng truy cập một PostgreSQL khi dùng cùng cấu hình, JWT secret và media directory. Số database thực tế ngoài máy này chưa được xác minh.

## Hướng sửa

Thêm cấu hình shared do FastAPI phục vụ cho frontend ở cùng origin, tự bật toàn bộ API kể cả URL thiếu query. Giữ static Mock Mode riêng cho demo. Bổ sung bootstrap admin đầu tiên có kiểm tra migration, hướng dẫn PostgreSQL/LAN/TLS/backup và test hai browser context độc lập với một PostgreSQL test. Không import hoặc xóa localStorage cũ. Không thay booking engine hoặc schema khi chưa có lỗi kiểm chứng.

## Các sai lệch đã kiểm chứng trong quá trình review

- Booking engine mới nhất lưu đơn ở trạng thái confirmed và giữ payment pending/manual. Không thêm bước pending giả để khớp mô tả cũ. Test cross-role kiểm tra Host nhận phòng, hoàn tất, Customer đọc trạng thái và đánh giá sau hoàn tất.
- Snapshot FRONTEND_BASELINE cũ đã lệch với nhiều file được commit trước lượt này. Đã đọc source hiện tại, giữ nguyên HTML/CSS/animation và lưu snapshot cũ trong `FRONTEND_BASELINE_PRE_SHARED.json` trước khi cập nhật checksum. Test SHA-256 toàn bộ frontend được giữ nguyên. Thay đổi frontend của lượt này giới hạn ở cấu hình runtime và error state lịch sử booking.
- UI smoke cũ kiểm tra chọn phòng ngay trong cùng tick dù lịch/phòng đang tải bất đồng bộ. Đã bổ sung chờ điều kiện thật rồi giữ nguyên assertion chọn phòng. Test host-register cũ dùng form đã được thay bằng redirect profile trong source hiện tại. Đã đối chiếu và kiểm tra workflow hiện tại, giữ assertion chống tự cấp role admin.
