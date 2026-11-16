# Phase 7 — Payment, Review & Profile

Bắt đầu **sau gate Phase 6** (437 pass/4 skip/0 fail/0 xfail), không dùng số đó làm kết quả cuối Phase 7.

| Chức năng | Audit trước sửa | Khoảng trống |
|---|---|---|
| Pending payment/query ownership/cancel/refund_due | IMPLEMENTED & TESTED | Giữ Booking Engine/unique booking/payment; thiếu event history và luồng dev paid/refund có guard |
| Payment events/dev simulation | MISSING | Cần audit trail, state machine, amount authoritative, admin + env guard, không public giả paid |
| Review completed/unique/rating | IMPLEMENTED & TESTED | Thiếu bounded pagination/batch author và Unicode test |
| Profile GET/PUT/password/logout/Argon2/JWT/media | IMPLEMENTED & TESTED | Giữ PUT hiện tại; bổ sung PATCH partial đúng nghĩa và kiểm Unicode/mass assignment |
| Gateway/frontend | BLOCKED ngoài scope | Không provider, không browser integration, giữ USE_MOCK=true |

Issue ghi trước sửa: P7-001 High payment consistency/history/simulation restrictions; P7-002 Medium review/profile validation và pagination. Gate **NOT READY** cho tới full test cuối.

## Chức năng giữ lại và bổ sung

Giữ Argon2id/legacy password/JWT/logout/revocation, ownership Booking, giá Decimal/snapshots, unique Payment.booking_id, cancellation/refund policy và media decode/re-encode hiện có. Bổ sung payment_service, immutable PaymentEvent, GET payment history; admin-only dev/test simulation trên route mới không trùng; PATCH profile đúng nghĩa partial (khác PUT đầy đủ); review SQL pagination/batch author và UTF-8 recursive validation.

## Payment state machine và giới hạn simulation

| Luồng | Điều kiện | Kết quả |
|---|---|---|
| Booking create | User/booking hợp lệ | pending + event, không paid |
| Admin dev/test action paid | Payment pending, booking không cancelled/rejected, amount khớp snapshot | paid, reference SIM-*, event simulation |
| Cancel/reject | Theo state machine Booking, Payment pending | cancelled + event |
| Cancel/reject đã paid | Theo refund policy hiện tại, refund_due<=amount | refund_pending + event nếu đủ điều kiện, chưa refunded |
| Admin dev/test action refunded | Payment refund_pending, terminal booking, 0<refund_due<=amount | refunded mô phỏng + event simulation |
| Retry cùng action paid/refunded | Đã ở trạng thái đó và điều kiện nhất quán | Trả state cũ, không thêm event/thu hoặc hoàn lần nữa |
| Production/anonymous/customer/host simulation | Guard environment/role | 403 (anonymous 401), không ghi DB |

Không có public giả lập thành công hoặc arbitrary payment status endpoint, không nhận amount/PAN/CVV, không dùng giá client. failed dành cho provider tương lai, chưa có transition API. Simulation không sửa Booking.status hoặc RoomNight; cancel/reject mới giải phóng inventory theo quy tắc cũ. Booking→Payment lock order và row refresh dùng chung thứ tự cancel/reject. Event failure rollback cả payment/reference; mismatch amount khi cancel rollback cả booking/history/ledger.

Mô phỏng chỉ ghi sổ **development/test**, không thu/hoàn tiền thật. KPI cash loại reference SIM-* khỏi grossCaptured/paidRevenue/refundPending/refunded và tách simulatedCaptured/simulatedRefundPending/simulatedRefunded/simulatedNet; DTO simulated=true. Production trả 403 kể cả admin hợp lệ; test dùng Settings production với engine test dependency injection, không kết nối production DB. Không gắn gateway/provider hoặc tự chạy simulation trên DB thật.

## Review/profile/media và bảo mật

- Customer own completed booking, đúng homestay public, một review/booking. Rating 1–5 strict, comment 5–3000 ký tự, unique DB và Booking row lock chặn race. GET page/page_size<=100, array mặc định; author batch tránh N+1; average từ review thật. Comment là untrusted plain text, không sanitize rồi tuyên bố HTML-safe; frontend phải textContent/escape (FE-002). verified chỉ có nghĩa completed stay.
- PATCH profile chỉ merge field có mặt, reuse PUT validation/duplicate email/avatar/phone; null explicit bị 422. Không cho role/is_active/id/hash/token_version, không có URL user_id tùy chọn. Avatar bỏ qua nếu PATCH không gửi; không phá ảnh cũ. Profile/password/logout/JWT đều kiểm user hiện tại, hashing/session policy cũ giữ nguyên.
- Recursive UTF-8 cho Input gồm secret, string, list/dict; không truncate/normalize mật khẩu. Wrong old password, revoked/forged token, email trùng, avatar malformed/MIME/size/path/SVG và media upload regression đã được giữ trong full suite. Không fetch remote image URL, filename client không quyết định file path, raster được encode lại.
- Payment/review/profile có test anonymous/role/IDOR/mass assignment/Unicode, duplicate/refund replay và transaction rollback. Error handler không echo input password/token/SQL; không log thẻ/credential. Không có browser E2E hoặc pentest production trong lượt này.

## API endpoints

- GET /api/me/bookings/{id}/payments: owner-only, amount/method/status/reference/simulated/history; không tạo payment thứ hai.
- POST /api/admin/bookings/{id}/payment-simulation: active admin + development/test, body action paid/refunded và reason; không dùng như API thanh toán thật.
- GET/POST /api/items/{id}/reviews: GET public paged, POST customer completed booking.
- GET /api/me và /me/profile, PUT/PATCH /me/profile, POST /me/password, POST /auth/logout, POST /uploads: current user và policy hiện có; PATCH mới là partial update, không alias PUT.

## Database migrations

Head **0005_pay_events**. Giữ 0001–0003 nguyên vẹn; 0004 Phase 6 history và 0005 Phase 7 events đều additive. 0005 tạo FK payment/user/index/check 0<=refund_amount<=amount, bootstrap current payment state bằng source legacy_snapshot, không tự đổi paid/refund/status, không tạo lịch sử transition giả. Timestamp bootstrap giữ thời điểm record cũ nhưng note rõ thời gian transition gốc không biết, không dùng làm cashflow đã xác minh. Migrations env.py chỉ sửa import-order lint cũ.

Test migration v4→v5 giữ Payment paid/reference/amount và BookingLine/RoomNight; sạch/legacy/v3→v4, metadata/Alembic/FK/check/unique/seed trên cả engine nằm trong full suite. Không reset/migrate DB thật, không chứng nhận backup restore production chưa chạy.

## Test và gate

Phase 7 riêng SQLite **28 pass**, gồm payment/refund concurrency, production guard, amount forgery/mismatch, event rollback, profile PATCH/security/Unicode, review eligibility/duplicate/concurrency/average/page và migration giữ lịch sử. Full SQLite cuối: **252 pass, 0 fail, 4 skip, 0 xfail**, 83,59 giây. Full cuối SQLite/PostgreSQL sau thêm assertion SIM không vào cash KPI: **493 pass, 0 fail, 4 skip, 0 xfail**, 347,20 giây, **497 ca**, JUnit `backend/.test-tmp/phase6-7-verified.xml`. Trong đó PostgreSQL 241 pass/0 skip; 56 bản test Phase 7 đều PASS. Bốn skip chỉ bản SQLite của các case row-lock Phase 1–3; PostgreSQL tương ứng đã chạy. Lượt 493 pass trước tinh chỉnh KPI giữ như artifact trung gian, không thay bằng chứng final.

Ruff toàn backend PASS, dependency pip check PASS; HTTP smoke thật Uvicorn/migration head 0005/catalog/quote/booking/host/cancel/logout/ownership PASS. Tất cả 66 file frontend khớp baseline, không sửa USE_MOCK. Không test browser E2E, coverage mới, pentest/load/backup restore production. Mọi test dùng DB/schema tạm; không downgrade/reset DB thật. Migration env.py import-order Low cũ đã sửa và toàn Ruff backend nay xanh.

## File thay đổi Phase 7

models.py; payment_service.py (mới); booking_service.py (chỉ thêm audit event/amount guard, không viết lại engine); schemas.py; reporting.py (loại simulation khỏi cash); routers/admin.py/auth.py/bookings.py/items.py; serializers.py; migration 0005_payment_events.py; main.py/seed.py/test_ops_media_migrations.py (head); tests/test_phase7_accounts_payments.py; tài liệu contract/schema/runbook/issues/roadmap/review/summary. Không sửa frontend hoặc dependencies.

## Issues còn mở

FE-001/002/003/004/005, browser E2E, API_BASE/CORS ở môi trường thực, stable checkout key, payment messaging, chart nguồn KPI thật còn mở High cho integration. EXT-001 còn provider/webhook/settlement/email verification/reset/storage/load test; không hạ severity hoặc coi simulation là đã hoàn thành gateway. Không có inventory history, payment legacy transition time hoặc đối soát ngân hàng thật. Cần backup/migrate head trước chạy code mới, không tự thực hiện lên DB thật.

**Phase 7 backend READY; Backend READY FOR FRONTEND INTEGRATION** trong phạm vi API/contract/test nêu trên. P7-001/002 đạt acceptance và DONE, không còn Critical/High đã xác nhận chưa xử lý thuộc backend Phase 6–7. Simulation được bảo vệ và không thay gateway thật. **Frontend Integration/fullstack/production vẫn NOT READY**; các FE/EXT High vẫn mở, không hạ severity hoặc dùng API tests để tuyên bố browser E2E đã đạt.
