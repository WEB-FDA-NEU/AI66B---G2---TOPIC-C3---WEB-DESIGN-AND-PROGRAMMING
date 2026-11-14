# Phase 9 — Fullstack QA

Ngày 14/11/2026. **READY cho Phase 10 trong phạm vi development đã kiểm thử**. Không còn Critical/High chưa xử lý trong gate tích hợp/API hiện tại. EXT-001 và các yêu cầu vận hành vẫn là blocker production, không hạ mức nghiêm trọng để vượt gate.

## Kết quả thực thi mới

| Kiểm tra | Kết quả |
|---|---|
| Full backend SQLite riêng | 258 PASS / 0 FAIL / 4 SKIP / 0 XFAIL, 76.94 giây |
| Full backend SQLite + PostgreSQL cluster tạm | 505 PASS / 0 FAIL / 4 SKIP / 0 XFAIL, 339.27 giây |
| Phân bổ suite kép | 258 SQLite + 247 PostgreSQL; không cộng thêm lần SQLite riêng vào tổng |
| API browser E2E | 103 assertion PASS, Chrome/Edge thật qua HTTP, SQLite tạm migrated |
| Mock UI source cuối | 72 tổ hợp trang/viewport, 244 assertion, 0 overflow / runtime error |
| Mock carousel + motion chuyên sâu | 72 tổ hợp trang/viewport, 684 assertion, 0 overflow / runtime error |
| Mock accounts | 34 assertion PASS |
| HTTP smoke Uvicorn | PASS: catalog/quote/create/confirm/cancel/logout/ownership |
| Ruff check + format | PASS: backend và browser script mới, 42 file formatted |
| pip check | PASS, không dependency hỏng |
| Baseline source cuối | PASS: 69 SHA256 chính xác + USE_MOCK=true, không giảm assertion |
| Swagger/OpenAPI/readiness kiểm riêng | PASS trên DB test migrated: 40 paths, các method tích hợp có thật, head 0005_pay_events |

4 SKIP là biến thể SQLite của các test khóa hàng/deadlock chỉ áp dụng PostgreSQL. Các biến thể PostgreSQL tương ứng chạy PASS; không dùng xfail. Head **0005_pay_events**. Migrations mới/sạch, upgrade legacy/backfill/metadata, seed và concurrency chạy trong suite backend với DB/schema test riêng. Không reset/upgrade DB thật. Suite PostgreSQL dùng cluster tạm loopback, không kết nối service cá nhân.

## Browser và đồng bộ dữ liệu

`tests/api-accounts-browser.py` tạo credential ngẫu nhiên, profile browser tạm, SQLite riêng và Uvicorn/cổng HTTP riêng, CORS chính xác localhost/127.0.0.1. Không in token/mật khẩu/body credential. Fixture ban đầu qua API; complete dùng một fixture lịch sử chỉnh trong DB test, không đổi clock hệ thống. Payment simulation được gọi rõ ràng bởi admin test harness, không phải thanh toán ngân hàng/UI customer.

- Customer đăng ký/login/profile/avatar/password/logout/relogin; search/RoomTypes/quote; checkout; history/detail/cancel và reload DB.
- Mất phản hồi sau server commit rồi reload/retry: một booking, cùng digest key/payload; double click không gửi trùng.
- Host nhận cùng booking, confirm/reject/check-in/complete; customer đọc trạng thái host và host đọc cancellation customer.
- CRUD homestay/phòng thật; sửa địa chỉ cập nhật location/city, upload HTTP ảnh; inventory và partial/all-unit blocks; sửa metadata không xóa partial block, PUT/DELETE đúng lịch.
- Host đổi giá; booking cũ giữ price/total snapshot. Review completed gửi một lần, author server, reload rating đúng.
- Admin dashboard SQL, approve/reject thật; khóa/mở khóa user; host có homestay bị khóa thì public catalog 404 và JWT cũ 401; mở lại catalog nhưng không phục hồi session cũ. Moderation lưu qua reload.
- Pending/payment states đọc DB; paid/refund_pending/refunded simulation luôn có thông điệp không xác nhận ngân hàng. Không PAN/CVV hoặc quyền paid cho customer/host.

Không chạy Playwright (không có sẵn) hoặc Node (không có binary). Browser dùng Chrome/Edge + CDP. Browser E2E hiện dùng SQLite; PostgreSQL được kiểm đầy đủ bằng API/concurrency/migration pytest, chưa chạy cùng browser suite trên PostgreSQL và chưa deploy staging thật.

## Security

Backend test hiện tại xác minh JWT signature/expiry/session revocation, role/ownership/IDOR, mass assignment, Unicode/long password, URL/file validation, CORS, không lộ hash/credential, payment forgery và race/rollback. Browser kiểm HTML injection ở user/guest/property/application/review/reason, cached role giả bị server sửa, token sessionStorage riêng, logout revoke và retry mất mạng. API request không gửi bearer sang asset/mock/host khác.

Renderer host rooms/mock preview và lỗi booking-detail cũng chuyển sang DOM text an toàn; không chỉ bảo vệ nhánh API. Không đưa dữ liệu backend/user vào template HTML động. Chưa pentest độc lập, chưa CSP/HttpOnly-cookie architecture; bearer vẫn có rủi ro XSS cùng origin. CSRF cookie không áp dụng vì bearer + credentials omit, không tự đổi session architecture.

## Responsive và performance

Viewport 375/768/1024/1440: profile, host booking/property/room form, admin không overflow; UI mock 72 tổ hợp và interaction sau mở editor/modal/toast cũng đạt. Ảnh chụp API admin/room form được lưu trong `backend/.test-tmp/phase9-*.png`, đã xem trực tiếp ảnh mobile room form và desktop admin. Không tuyên bố pixel-perfect hoặc benchmark FPS.

Carousel browser test kiểm timer 2 giây, pause/resume, resize/touch/reduced-motion và khởi tạo lại không nhân listener/timer. SQL tests kiểm query count không tăng theo số user/booking; thêm 105 user và 101 homestay xác minh KPI/occupancy không bị cắt ở projection 100. List API giới hạn trang; dashboard recent 10, biểu đồ occupancy tối đa 100 có chú thích, tổng dùng occupancySummary SQL đầy đủ.

Chưa load/stress test dài hạn, profiler memory/FPS hoặc đo hiệu năng mạng production. Selector homestay host hiện đọc các trang để có đủ lựa chọn; quy mô tài khoản có rất nhiều tài sản cần UX tìm kiếm/paging riêng trước triển khai lớn. Chart.js CDN đã có fallback, chưa đóng gói offline.

## Bug và regression

- P8-001: fragment URL bị rewrite thành selector không hợp lệ → giữ fragment và resolve ID an toàn; review browser PASS.
- P8-002: mock admin fetch file không tồn tại → dùng ownership tables thật của mock; mock UI 0 runtime error.
- P9-001: 22 mock listings bị cắt còn 16 trên home → render toàn bộ phần còn lại trong rail mock; giữ nguyên assertion đủ/không trùng; 684 checks PASS. API home vẫn bounded server queries.
- P9-002: sửa địa chỉ homestay giữ city/location cũ → cho backend chuẩn hóa địa chỉ mới; browser assertion PASS.
- P9-003: renderer legacy có sink động → DOM text/URL validation, selector/class bảo toàn; UI source cuối PASS.
- Test harness chờ redirect login đủ module readiness; không bỏ validation/password-failure assertion. Fixture báo cáo bổ sung location bắt buộc; không thay model constraint để test pass.

Không còn lỗi chặn Phase 10 trong phạm vi đã kiểm thử. Giới hạn production và chức năng ngoài scope xem `PHASE_10_DELIVERY.md`. Danh sách file chung xem `PHASE_8_REVIEW.md` và `PHASE_8_10_CHANGES.json`.

Markdown link nội bộ của README/các báo cáo bàn giao đã kiểm tra tồn tại. `git diff --check` còn báo whitespace có sẵn ở `frontend/host-homestay-form.html`; file giữ nguyên hash theo yêu cầu bảo toàn source người dùng, không nhận là lỗi do integration và không tự sửa file đó.
