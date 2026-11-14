# Phase 8 — Frontend integration review

Ngày 14/11/2026. **READY cho Phase 9**, chưa chứng nhận production. Bằng chứng gate: `tests/api-accounts-browser.py` chạy Chrome/Edge thật, FastAPI/Uvicorn qua HTTP khác origin, SQLite đã migrate trong thư mục test riêng: **97 assertion PASS**, không runtime/console error. Các test backend hồi quy đầy đủ thuộc gate Phase 9, không lấy kết quả 493 lịch sử thay kết quả mới.

## Phạm vi đã nối

Mapping chi tiết: `PHASE_8_INTEGRATION_MAP.md`. `?mode=api` nối customer/host/admin trên cùng DB; `?accounts=api` giữ sandbox tài khoản; mặc định mock và `USE_MOCK=true` không đổi. API_BASE mặc định same-origin; Live Server 5500/5501 nối cùng hostname:8000. Override không bí mật bằng `globalThis.LUXSTAY_CONFIG.apiBase` trước khi nạp ES module. Backend CORS phải allowlist origin thật.

- Auth/profile/password/avatar, logout revoke, pending host/relogin sau approve; server role ghi đè cache bị giả.
- Home/banner 2 giây/search/detail/RoomTypes thật, availability liên tục và quote server; không tự sinh Deluxe/rating.
- Checkout stable request intent + Idempotency-Key, chặn double submit, mất phản hồi sau commit rồi reload/retry giữ nguyên key/payload. Intent sessionStorage không thay thế booking DB. Không thu PAN/CVV; confirmation pending và trạng thái payment đọc API.
- Booking history/detail/cancel; host CRUD homestay/phòng/upload/inventory/status/structured blocks; confirm/reject/check-in/complete; dashboard SQL.
- Admin applications approve/reject, khóa/mở khóa user, moderation homestay, pagination/filter/sort, KPI/chart SQL. Không thêm quyền tự gán host hoặc payment paid cho customer/host.
- Review completed lưu DB, chống submit lặp, author xác thực, rating tổng hợp; payment pending/paid/refund_pending/refunded hiển thị đúng, SIM luôn ghi mô phỏng.

## Bảo mật và lỗi đã sửa

Bearer chỉ gửi đúng origin/path API, timeout 15 giây và lỗi có status, không tự retry POST bằng key mới. Private 401 xóa phiên, logout mất mạng giữ phiên để retry revoke. Cached role chỉ UX; guard xác minh server và endpoint kiểm tra ownership.

Các API renderer điền `textContent`, `createElement`, template hằng, ảnh qua URL protocol validation. Payload HTML độc hại ở tên khách/homestay/review/reason/application không chạy. Mật khẩu không lưu/log thô hoặc nằm trong URL. Token sessionStorage vẫn đọc được bởi JavaScript cùng origin; đây là giới hạn XSS, không phải HttpOnly cookie/CSRF design.

Lỗi phát hiện khi chạy: link giữ API flag làm biến fragment thành CSS selector URL không hợp lệ ở detail, khiến review không khởi tạo; đã giữ nguyên fragment, resolve tab bằng getElementById và thêm browser regression. Test navigation còn được sửa để chờ login module khởi tạo trước submit; assertion kiểm tra mật khẩu cũ vẫn giữ nguyên.

Mock admin trước đây fetch `admin-hosts.json` không tồn tại. Đã dùng users + host-homestays/rooms/bookings thật của mock, nối đúng owner/room ID; không tạo file giả hoặc suy đoán sở hữu từ public catalog.

## Giao diện/baseline

So với snapshot bắt đầu Phase 8: CSS, `motion.js`, `charts.js`, mock JSON, ảnh và `host-homestay-form.html` giữ nguyên hash. HTML chỉ đổi `booking-page.html` để bỏ PAN/CVV và `admin.html` để cô lập handler mock. Các trường inventory/status/structured blocks và user/moderation thêm bằng DOM với class hiện có để kết nối API; không redesign CSS/animation. Carousel chỉ sửa link giữ mode, vẫn timer 2 giây.

Baseline Phase 7 được lưu riêng `FRONTEND_BASELINE_PHASE7.json`; baseline mới chụp chính xác frontend sau thay đổi được yêu cầu và kiểm tra browser. Test so toàn bộ SHA256 và assert USE_MOCK=true không bị làm yếu.

## Test thực tế và giới hạn

Sau QA Phase 9, source cuối đạt **103 browser assertion**, mock source cuối 72 tổ hợp/244 assertion, home/motion chuyên sâu 684 assertion; kết quả 97 ở gate ban đầu được giữ làm lịch sử. Chi tiết và artifact: `PHASE_9_REVIEW.md`, `PHASE_9_BROWSER_RESULTS.json`. Hardening nhánh mock rooms/error, sửa home mock bỏ sót card và cập nhật địa chỉ là các regression fix trong QA, không thay CSS/animation.

- 97 browser assertion: accounts/customer/host/admin, DB persistence/reload, server state, snapshot giá, partial blocks, payment simulation labels, XSS và role cache. Cấu hình 1440/1024/768/375 trên profile/host booking/property/room form/admin không overflow.
- Mock UI: 72 trang/viewport, 244 assertion, 0 overflow, 0 runtime error trong lần chạy trước khi nối dashboard/admin; Phase 9 cần chạy lại source cuối.
- Browser dùng CDP Chrome/Edge có sẵn; Playwright và Node không có trong môi trường. Không tuyên bố đã chạy chúng.
- Check-in fixture dùng ngày nghiệp vụ hiện tại; complete dùng booking lịch sử seed riêng trong DB test, không đổi clock/database thật. Một số fixture và payment simulation tạo qua HTTP test harness, thao tác UI được phân biệt trong tên assertion.
- Chưa gateway/email thật; admin simulation chỉ dev/test qua API, không mở nút customer/host. Dashboard cash là cohort current-state, không phải sổ dòng tiền hoặc lợi nhuận.
- Chart.js CDN có fallback thông báo khi không tải được; chưa đo độ mượt bằng profiler, chưa pentest/deploy/backup restore production.

## File thay đổi của Phase 8

Frontend: `admin.html`, `booking-page.html`; `js/api.js`, `auth.js`, `config.js`, `guard.js`, `pricing.js`, `render.js`, `components/home-carousels.js`; pages `login`, `profile`, `host-register`, `home`, `list`, `shop`, `detail`, `booking-page`, `booking-confirmed`, `booking-detail`, `booking-list`, `host-bookings`, `host-homestays`, `host-homestay-form`, `host-rooms`, `host-dashboard`, `admin-dashboard`, `admin-hosts`; thêm pages `api-checkout.js`, `api-host-rooms.js`, `api-admin.js`.

Backend tối thiểu: `reporting.py`, `routers/admin.py`, `routers/host.py` để SQL series/occupancy summary không phụ thuộc projection; thêm `tests/test_phase8_reporting.py`. Thêm `tests/api-accounts-browser.py`; tài liệu map/review/baseline. Các backend file khác xuất hiện trong git status đã có từ Phase 1–7, không được nhận là sửa mới ở đây.

QA còn định dạng lại assertion xuống dòng trong `backend/tests/test_ops_media_migrations.py` và thêm dòng trống import `backend/migrations/env.py` để lint theo config tường minh đạt; không thay logic test/migration. Manifest đầy đủ: `PHASE_8_10_CHANGES.json`.
