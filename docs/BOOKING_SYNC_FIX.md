# Đồng bộ đặt phòng qua database chung

## Nguyên nhân và phạm vi sửa

Source đã có FastAPI, SQLAlchemy, JWT, PostgreSQL và migration `0007_booking_holds`. Tuy nhiên frontend tĩnh và development mặc định chọn mock nếu thiếu cờ URL, nên URL Live Server thông thường đọc lịch sử riêng của mỗi trình duyệt.

Frontend hiện dùng API mặc định (`USE_MOCK=false`, runtime shared). Backend cũng mặc định shared trong development. Bốn hàm customer getBookings/getBooking/createBooking/cancelBooking chỉ gọi API, đã bỏ nhánh localStorage và helper gộp lịch sử mock. Checkout, confirmation, chi tiết, lịch sử, hủy, host và admin sử dụng adapter API sẵn có; giữ nguyên HTML/CSS/animation. Lỗi API không có fallback mock, không báo thành công trước khi POST đã lưu thành công. Idempotency key của lần đặt có thể lưu sessionStorage để retry an toàn; đây không phải nguồn lịch sử.

Backend không cần thêm schema hay migration cho bản sửa này. Đã đọc lại config, models, migrations, routers auth/bookings/host/admin, booking_service, serializers, schemas, frontend config/auth/api/checkout/history/detail và tài liệu vận hành. GET `/api/me/bookings` lọc bằng customer_id của JWT đã xác minh. GET detail/POST cancel kiểm tra owner phía server; customer khác nhận 404. Giá, trạng thái, inventory được server quyết định. User/room locks, ledger RoomNight unique theo phòng/đơn vị/đêm và idempotency constraint hiện có tiếp tục chống đặt trùng. Không bổ sung chức năng sửa booking vốn chưa có.

## Chạy local và dùng chung

Từ repository root, cài dependencies bằng venv hiện có. Chỉ tạo `backend/.env` từ `.env.example` nếu chưa có file; không ghi đè cấu hình đang dùng. Database URL là cấu hình server, không đưa vào frontend.

```powershell
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.txt
backend/.venv/Scripts/python.exe -m alembic -c backend/alembic.ini current
backend/.venv/Scripts/python.exe -m alembic -c backend/alembic.ini heads
backend/.venv/Scripts/python.exe -m alembic -c backend/alembic.ini upgrade head
backend/.venv/Scripts/python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Chạy migration sau khi xác nhận đúng database và có backup khi database đã có dữ liệu. Không có migration production nào được tự áp dụng trong phiên sửa này. SQLite mặc định chỉ dành cho development riêng; nguồn chung cần DATABASE_URL PostgreSQL. Tất cả thành viên mở cùng server, ví dụ `https://<domain-thật>/index.html` và `/booking-list.html`. Mỗi máy mở localhost của chính mình không phải cùng server. Live Server trên 5500/5501 gọi backend cùng hostname cổng 8000; cách đơn giản và ít sai cấu hình nhất là dùng frontend do FastAPI phục vụ.

Các biến server cần cấu hình: `DATABASE_URL=postgresql+psycopg://...`, `APP_ENV=production`, `JWT_SECRET` ngẫu nhiên bền vững, `FRONTEND_MODE=shared`, `SERVE_FRONTEND=true`, `UPLOAD_DIR` trên disk bền vững. CORS phải đúng origin nếu tách frontend; cùng origin dùng `/api` không cần mở CORS rộng. TLS, domain, backup, disk upload và dịch vụ PostgreSQL là việc vận hành còn cần thiết. Không đưa secrets vào Git.

Render/Railway đã có Dockerfile và manifest trong repo. Dùng [hướng dẫn Internet](INTERNET_DEPLOYMENT.md) và [thiết lập PostgreSQL](POSTGRESQL_SHARED_SETUP.md); chưa tạo dịch vụ hay public URL trong phiên này. Tài liệu chính thức: [FastAPI trên Render](https://render.com/docs/deploy-fastapi), [kết nối Render PostgreSQL](https://render.com/docs/postgresql-creating-connecting). Khi dùng Render, chọn backend/database cùng region và dùng internal database URL khi có thể.

Database mới không có tài khoản `huy@test.com` hoặc phòng giả tự động. Tạo admin đầu tiên bằng `python -m backend.bootstrap_admin`, đăng ký tài khoản customer qua website, gửi/duyệt host rồi host tạo phòng thật. Không dùng seed/mock cho dữ liệu nhóm.

## Dữ liệu cũ

Không xóa, sửa hoặc tự nhập đơn/tài khoản trong localStorage lên database. Các đơn đó không xuất hiện trong lịch sử server. Muốn giữ cần xuất bản sao có đồng ý, xác minh owner, ánh xạ tài khoản/phòng, kiểm tra tồn theo đêm và trùng lặp, dry-run rồi nhập có kiểm soát phía server. Không tin email/userId hay quyền tự khai trong dữ liệu trình duyệt. Tài khoản mock cần đăng ký lại hoặc quy trình chuyển tài khoản/đặt lại mật khẩu được xác minh.

## Kiểm thử và nghiệm thu

Runner `python tools/test_backend_postgres.py --browser-only` tạo PostgreSQL test riêng và hai Chrome profile độc lập, đăng ký user/host và tạo phòng bằng API thật; không đọc mock fixtures. A tạo đơn bằng frontend API adapter; B cùng user mở lịch sử không có cờ mode và thấy DOM hiển thị đơn. Kiểm tra khác user không thấy/đọc/hủy đơn, host đúng quyền thấy trạng thái, hủy đồng bộ, restart vẫn còn dữ liệu, localStorage giữ nguyên và lỗi API không fallback. Đây là kiểm thử qua browser adapter và màn hình lịch sử, không khẳng định đã thao tác toàn bộ form checkout bằng tay.

Runner backend: `python tools/test_backend_postgres.py -k "booking or shared_deployment or frontend_baseline or both_database_engines"` đã chạy: **153 PASS, 0 FAIL/SKIP/XFAIL, 399 deselected**, trên SQLite và PostgreSQL tạm. Bao gồm booking engine, ownership, idempotency, cạnh tranh đặt phòng/hủy và Alembic check khớp models trên hai engine. Database test sạch được migrate đến `0007_booking_holds`; không cần migration mới. Chạy bổ sung `pytest backend/tests/test_shared_deployment.py -q --tb=short`: **3 PASS** trên SQLite để xác minh mặc định shared. Không tuyên bố đã chạy toàn bộ 552 test backend.

Hai Chrome profile với một PostgreSQL/FastAPI: **39 kiểm tra PASS**, chi tiết tại [SHARED_BROWSER_RESULTS.json](SHARED_BROWSER_RESULTS.json). Các lượt đầu gặp lỗi trong script kiểm thử: kỳ vọng nhầm list thành object, import module sau khi tắt server, và đợi cố định 650ms chưa đủ khi máy bận. Đã sửa harness để dùng đúng DTO, tải adapter trước khi mô phỏng mất mạng và chờ cả hai request; không thay đổi/giảm assertion nghiệp vụ. Lượt cuối hoàn tất toàn bộ. Ruff PASS; git diff --check PASS. PostgreSQL initdb không chạy được trong sandbox nên runner test tạm được thực thi với quyền đã được cấp; không kết nối database thật.

File thay đổi: `frontend/js/config.js`, `runtime-config.js`, `api.js` (API mặc định và loại bỏ booking local); `backend/config.py`, `.env.example` (shared mặc định); `backend/tests/test_shared_deployment.py`, `test_ops_media_migrations.py`, `tests/shared-postgres-browser.py` (regression/mode/ownership/cancel); `docs/FRONTEND_BASELINE.json` (hash chính xác cho thay đổi JS được yêu cầu, không đổi CSS/HTML); `README.md`, `docs/POSTGRESQL_SHARED_SETUP.md`, `SHARED_DATABASE_AUDIT.md`, `SHARED_FULLSTACK_REPORT.md`, báo cáo này và `SHARED_BROWSER_RESULTS.json` (hướng dẫn và bằng chứng mới). Không commit/push/deploy hay tác động database thật.

Chưa kiểm thử hai máy vật lý hoặc bản deploy Internet. Sau deploy: A/B mở cùng public URL; cùng user đặt ở A rồi tải lại lịch sử B; đăng nhập user khác và thử URL detail/cancel; hủy ở A rồi reload B; thử API gián đoạn. Không sử dụng tài khoản/số phòng đang có giao dịch thật để thử phá vỡ.
