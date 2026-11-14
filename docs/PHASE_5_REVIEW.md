# Phase 5 — Booking Engine

Audit source ngày 14/11/2026. Trạng thái trước sửa: **NOT READY**; kết quả nghiệm thu mới được ghi ở cuối báo cáo.

| Chức năng | Phân loại trước sửa | Bằng chứng/khoảng trống |
|---|---|---|
| Quote Decimal, snapshot, create lines/ledger/payment atomic | IMPLEMENTED & TESTED | booking_service.py, test_bookings.py, RoomNight unique; giữ nguyên engine |
| Continuous unit, partial/all-unit block | IMPLEMENTED & TESTED | Phase 4 tests và add_block/free_units |
| Đồng bộ search/quote/create | IMPLEMENTED BUT INCOMPLETE | quote chưa kiểm host active/role; quote có thể chọn giá legacy 0 mà search loại; max qty 4 khác search tính toàn inventory |
| Concurrency allocation/idempotency | IMPLEMENTED & TESTED | khóa customer → homestay → room, unique ledger; cần mở rộng cạnh tranh/rollback |
| Idempotency retention | IMPLEMENTED BUT INCOMPLETE | key theo customer và fingerprint có sẵn nhưng chưa có cửa sổ replay rõ ràng |
| Status/history/cancel/reject | IMPLEMENTED BUT INCOMPLETE | host same-status trả thành công im lặng; cần phân biệt retry cancel với quyết định host lặp và refresh sau khóa |
| Customer list/detail và host list/status | IMPLEMENTED & TESTED | giữ DTO array mặc định cho frontend; cần pagination tùy chọn/status filter |
| Host detail | MISSING | chỉ có list và PATCH status, bổ sung GET theo booking ID dưới ownership |
| Frontend checkout API thật | BLOCKED ngoài phạm vi | pricing mock, chưa gửi Idempotency-Key, toast thanh toán thành công dù backend payment pending; không sửa UI/frontend |

Issue trước sửa: P5-001 High — quy tắc eligibility và capacity giữa các bề mặt chưa đồng bộ; P5-002 Medium — replay window/refresh/status repeat; P5-003 Medium — list/filter/detail và test còn thiếu. Ghi nhận trước khi sửa, acceptance và kết quả cuối được cập nhật sau test. Không thêm dashboard Phase 6, payment gateway, frontend integration hoặc reset DB thật.

## 1. Chức năng có sẵn được giữ lại

Đã đọc lại service/router/model/schema/serializer/deps/database/tests/migrations và tài liệu hiện tại, đối chiếu api.js/pricing cùng các trang detail, checkout, booking list/detail/confirmed và host bookings. Tái sử dụng quote Decimal, BookingLine snapshot, reservation ledger unique(room_id,unit,night), giao dịch tạo booking/payment/history, guard ownership, cancellation/refund policy, locks và idempotency hiện có. Không đổi state names, viết engine mới, tạo bảng/endpoint trùng hoặc làm dashboard Phase 6.

## 2. Vấn đề phát hiện

- **P5-001 High:** quote chưa kiểm host active/host role như catalog, nhận room legacy giá 0 và quantity giới hạn 4 trong khi search cộng toàn inventory; có thể báo khả dụng nhưng không đặt được theo cùng giới hạn.
- **P5-002 Medium:** chưa định nghĩa replay window/retention, host repeated state thành công im lặng; cần refresh sau khóa để không dùng account/status ORM cũ lúc tranh khóa.
- **P5-003 Medium:** host chưa có GET detail, list chưa có status/page, Unicode surrogate có thể đi đến fingerprint/SQL gây 500.
- **FE-004 High ngoài Phase 5:** frontend chưa gửi stable key, vẫn quote/phòng mock và báo thanh toán thành công trong khi Payment chỉ pending. Đã ghi dependency, không sửa frontend.

## 3. Thay đổi và quy tắc sau sửa

- Search/detail/availability/quote/create cùng loại bỏ host không active/không phải host, homestay/room inactive và giá legacy 0. Quote/create kiểm host bằng JOIN; khi tạo vẫn xác minh contact host. Query khóa homestay chỉ FOR UPDATE OF Homestay, sau đó room theo ID; không vô tình khóa cả host User theo thứ tự mới.
- Quantity 1–100, không tin qty vượt inventory hoặc free_units; unit phải tự do toàn bộ [check_in,check_out), không nối unit khác giữa các đêm. Adults 1–10/children 0–6 theo schema hiện tại, tối đa 365 đêm, ngày không ở quá khứ.
- Khóa/refresh customer, kiểm lại active/role/token_version trước tạo; khóa/refresh homestay/room trước tính giá. Token đã bị đổi version trong lúc chờ không tiếp tục tạo booking bằng identity map cũ.
- Giữ Decimal/Numeric; phí 5% ROUND_HALF_UP đến VND, không thêm thuế/discount. Giá/tổng/name/contact từ client không quyết định dữ liệu lưu. Snapshot BookingLine/Booking giữ nguyên khi room đổi giá hoặc soft delete.
- Host lặp cùng trạng thái trả 409; retry customer cancel đã cancelled vẫn 200, không thêm history/refund. Booking mutation dùng refresh sau row lock. Giữ ngày check-in/check-out guards và chính sách cancel pending/confirmed hiện tại; không tự thêm pending hold timeout.
- Thêm GET host booking detail và status/page filter cho list hai phía. Mặc định vẫn array đầy đủ để không phá frontend; page bật SQL LIMIT/OFFSET, page_size<=100. Chưa đổi list legacy sang envelope có total hoặc áp đặt mặc định cắt danh sách.
- Validate UTF-8 của guestName/room key/status reason và quantity overflow, không echo dữ liệu đầu vào trong lỗi.

### State machine và ledger

| Trạng thái hiện tại | Chuyển hợp lệ | Quyền/điều kiện |
|---|---|---|
| pending | confirmed, rejected | Host sở hữu; reject cần reason>=3; confirm trước checkout |
| pending | cancelled | Customer sở hữu |
| confirmed | checked_in | Host sở hữu; check_in<=hôm nay<check_out |
| confirmed | cancelled | Customer sở hữu |
| checked_in | completed | Host sở hữu; hôm nay>=check_out |
| cancelled | cancelled | Chỉ retry customer, không mutation |
| completed/rejected/cancelled | Các chuyển khác | 409; body pending/cancelled ở host status cũng không được schema nhận |

Pending/confirmed/checked_in chiếm ledger. Cancel/reject giải phóng **chỉ** RoomNight thuộc booking đó; payment pending→cancelled, paid→refund_pending nếu được hoàn, lưu refund_due, không tự báo refunded. Completed giữ ledger lịch sử của các đêm đã qua; không purge lịch sử hoặc tự giải phóng một pending vì thời gian trôi. Lịch sử chỉ thêm khi thực sự chuyển trạng thái.

## 4. API endpoints

| Endpoint | Quyền/kết quả |
|---|---|
| POST /api/bookings/quote | Public, eligibility/date/capacity/ledger/Decimal, không giữ chỗ |
| POST /api/me/bookings | User, 201 mới hoặc 200 replay, optional Idempotency-Key |
| GET /api/me/bookings | JWT, chỉ của mình; optional status/page/page_size, array |
| GET /api/me/bookings/{id} | Chỉ của mình, snapshot/statusHistory |
| POST /api/me/bookings/{id}/cancel | Chỉ chủ booking, theo state machine |
| GET /api/me/bookings/{id}/payments | Chủ booking, không có thông tin thẻ |
| GET /api/host/bookings | Host hiện tại, optional status/page/page_size |
| GET /api/host/bookings/{id} | **Bổ sung**, ownership từ Homestay.host_id |
| PATCH /api/host/bookings/{id}/status | Host sở hữu, {status,reason}, không nhận arbitrary status |

401 thiếu/sai/revoked token, 403 sai role, 404 booking ngoài ownership hoặc không tồn tại, 409 hết tồn/state conflict/key conflict, 422 invalid input. Không trả SQL/traceback, password_hash hoặc token qua DTO booking.

## 5. Database/migrations

**Không cần migration mới**, head vẫn `0003_block_unit`. Reuse created_at/request_hash/idempotency_key và unique(customer_id,idempotency_key). Không sửa migrations cũ/schema lớn hoặc reset DB. Full suite tiếp tục kiểm sạch/legacy/upgrade v2→v3, metadata, FK/unique/check, rollback và seed idempotency trên cả hai engine.

Key cleanup chỉ set idempotency_key=null cho cutoff retention, không thay status/updated_at/snapshot hoặc xóa booking, lines, history, payment, ledger. Unique key null vẫn cho client cũ không gửi key. Backup/restore production thực tế chưa được kiểm chứng; mọi DB chạy trong lượt này là test riêng.

## 6. SQLite sau sửa

Test Phase 5 riêng ban đầu: 22 pass; sau quantity overflow/duplicate-confirm/cleanup: **27 pass**. **Full SQLite cuối: 212 pass, 0 fail, 4 skip, 0 xfail**, 66,41 giây, JUnit `backend/.test-tmp/phase5-sqlite.xml`. Không cộng các lượt chạy lặp thành số ca mới. Một lượt trung gian thêm cleanup lỗi thiếu import utcnow trong file test (211 pass/1 fail/4 skip); đã sửa import, thêm assertion updated_at không bị đổi, giữ nguyên các assertion khác và chạy lại đầy đủ.

## 7. PostgreSQL/regression

**Full suite cuối SQLite + PostgreSQL: 413 pass, 0 fail, 4 skip, 0 xfail**, 251,55 giây, **417 ca**, lệnh `backend/.venv/Scripts/python tools/test_backend_postgres.py -rxX --junitxml=backend/.test-tmp/phase5-verified.xml`. Trong đó SQLite 212 pass/4 skip, PostgreSQL 201 pass/0 skip; 4 skip là bản SQLite của các ca row-lock Phase 1–3, các ca PostgreSQL tương ứng đều chạy. Toàn bộ **27 ca Phase 5 mới × 2 engine = 54 PASS**. Runner tạo cluster PostgreSQL 17/cổng ngẫu nhiên/DB luxstay_test và private schemas; không dùng DB service thật. Lượt trước cleanup (phase5-final.xml) có 411 pass/4 skip; lượt thiếu import test cleanup (phase5-final-retention.xml) có 411 pass/2 fail/4 skip, lỗi NameError trên cả hai engine. Không dùng các lượt trung gian thay bằng chứng final.

HTTP smoke thật Uvicorn + migrate database tạm + catalog/quote/booking/host confirm/cancel/logout/ownership: **PASS**. Ruff check và format --check cả 8 file Python sửa/thêm: **PASS**; pip check PASS. Toàn bộ 66 file frontend khớp baseline không sửa. Không đo coverage mới, không browser E2E hoặc pentest/load test production.

## 8. Double booking và atomicity

- Test cũ: hai customer tranh unit cuối chỉ một 201/một 409; cùng key cùng payload concurrent trả 201/200 cùng ID; multi-room thất bại rollback toàn đơn; duplicate ledger qua unique constraint rollback Booking/line/Payment; block-vs-booking chỉ một thắng.
- Test mới: hai customer cùng room inventory=2 đều 201, request thứ ba 409; ledger đúng 4 unit-nights, hai Booking/lines/history/payments. Partial block khác unit giữa hai đêm không tạo unit liên tục giả; search/availability/quote/create đều từ chối room đó.
- Confirm-vs-cancel có hai thứ tự hợp lệ: pending→cancelled, hoặc pending→confirmed→cancelled. Test chỉ chấp nhận đúng hai lịch sử đó, cuối luôn cancelled và ledger rỗng. Duplicate confirm đồng thời chỉ một 200/một 409, một entry confirmed, ledger còn nguyên.
- RoomNight unique, ownership, transaction và lock order vẫn là lớp bảo vệ; không diễn giải việc pass vài interleaving thành không còn mọi race/deadlock trong toàn hệ thống.

## 9. Idempotency/retention

- Scope theo customer; fingerprint SHA256 của payload đã validate (bỏ field giá/display thừa). Cùng key/payload trong **24h** trả booking gốc, kể cả đã cancelled, không chiếm ledger lại; khác payload 409. Key còn lưu quá replay window trả 409 yêu cầu đối soát, không tự tạo mới.
- Retention maintenance cutoff **30 ngày**: `python -m backend.idempotency_cleanup` mặc định chỉ count/dry-run; `--apply` mới xóa key cũ (không xóa booking). Phải được operator lên lịch hằng ngày; không tự cài scheduler hoặc chạy trên DB thật trong lượt này.
- Sau khi key được maintenance purge, không còn guarantee dedupe bằng key đó. Client phải tìm/đối soát booking gốc trước checkout mới sau timeout dài; đây là guarantee hữu hạn, không phải exactly-once vô thời hạn. Nếu operator không chạy maintenance, key tiếp tục được giữ và request cũ tiếp tục 409 sau window, không tự tái sử dụng.
- Tests: cùng key khác user, concurrent cùng key cùng/khác payload, cancelled replay, expiry không thêm booking, dry-run không ghi, cleanup giữ snapshot/updated_at/history/lines/payment, cleanup idempotent và sử dụng key sau retention là request mới.

## 10. Security review

Authorization/ownership thực hiện backend, không dùng HOST_ID. Customer không thể xem/hủy booking người khác; host khác không xem/sửa; anonymous/customer không vào host detail. Client userId/status/tổng tiền không được mass assign; SQLAlchemy bind parameter, query status enum và query range được validate. Unicode không hợp lệ trả 422 thay vì 500; giá overflow và quantity overflow rollback không để orphan. Decimal tests gồm mức làm tròn 0,5 VND và tổng nhiều room-night. Request thua race nhận 409, không raw SQL/secret/token. Full regression chạy lại các test JWT/role/IDOR/migration/media Phase 1–4.

Frontend chưa nối API thật nên không coi pass API là đã pass browser hoặc an toàn XSS. PAN/CVV không được API nhận; không thêm gateway, không tự ghi paid/refunded hoặc gửi/log dữ liệu thẻ. FE-004 theo dõi integration checkout riêng.

## 11. File thay đổi trong lượt Phase 5

- backend/booking_service.py — eligibility/lock refresh, replay window, repeated status.
- backend/schemas.py — BookingState, qty range và UTF-8.
- backend/routers/bookings.py — optional page/status và booking refresh.
- backend/routers/host.py — list page/status, host detail/ownership helper, status refresh; không đổi dashboard.
- backend/routers/items.py, backend/serializers.py — loại room giá legacy 0 ở availability/detail như search/quote.
- backend/idempotency_cleanup.py — retention dry-run/apply riêng.
- backend/tests/test_phase5_booking_engine.py — acceptance/concurrency/security/retention tests mới.
- docs/API_CONTRACT.md, DATABASE_SCHEMA.md, BACKEND_RUNBOOK.md — quy tắc/API/retention và vận hành.
- docs/BACKEND_ISSUES.md, BACKEND_ROADMAP.md, PHASE_5_REVIEW.md — issue/gate/bằng chứng mới.

Working tree có nhiều thay đổi trước lượt này; chỉ liệt kê phần Phase 5. Không sửa frontend/baseline/USE_MOCK, không cài dependency, không commit/push và không thao tác DB thật.

## 12. Các phần còn mở/giới hạn

- FE-001/002/003/004, browser E2E, provider/payment/email/reset/storage vẫn High mở, ngoài gate API Phase 5. Frontend phải dùng roomTypes/availability/quote thật, stable key qua retry, thông báo pending đúng thay vì false paid, xử lý expiry/đối soát trước USE_MOCK=false.
- Legacy list không có page vẫn unbounded/N+1 serializer; đã bổ sung đường paging có giới hạn cho integration, chưa thay shape cũ hoặc chứng nhận performance production. Test load/benchmark và tối ưu batch list/dashboard thuộc công việc QA/Phase 6 tiếp theo.
- Chưa có chính sách pending expiry tự động; không tự phát minh timeout giữ phòng hoặc xóa ledger đang active. Payment hoàn tiền vẫn ledger nghiệp vụ, chưa phải gateway.
- Chưa kiểm backup/restore production, advisory/CVE scanner, stress nhiều worker dài hạn hay tất cả interleaving; Ruff import-order Low ở migrations/env.py từ trước vẫn được ghi nhận.
- Bảo đảm idempotency chỉ trong window/retention đã nêu; cleanup phải được operator lên lịch, không tự chạy trên máy người dùng.

## 13. Kết luận

**Backend Phase 5: READY để bắt đầu audit/phát triển Phase 6**, trong phạm vi contract và kiểm thử đã nêu. P5-001/002/003 đạt acceptance và DONE; không còn Critical/High đã xác nhận chưa xử lý thuộc phạm vi Phase 5. Full regression Phase 1–4 và các test mới SQLite/PostgreSQL đều đạt, không có xfail. Đây không phải chứng nhận mọi interleaving/tải production. **Frontend integration/fullstack/production vẫn NOT READY**; FE-004 và các High integration/provider vẫn mở, giữ nguyên severity. Không triển khai dashboard Phase 6 trong lượt này.
