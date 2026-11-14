# Backend issues — audit source hiện tại, 14/11/2026

## Trạng thái mới nhất Phase 8–10

FE-001..005 và QA-001 đã đạt nghiệm thu development/API: 505 backend pass/4 skip trên SQLite/PostgreSQL, 103 browser API assertion và mock regression. Giữ nguyên severity High; DONE dựa bằng chứng, không hạ mức. Các mô tả "frontend chưa tích hợp" ở issue là tình trạng khi phát hiện/lịch sử, đã được thay bởi `PHASE_8_REVIEW.md` và `PHASE_9_REVIEW.md`. EXT-001 còn mở: không có gateway/email thật và chưa production ready. Global USE_MOCK=true giữ theo yêu cầu, API hoạt động bằng route opt-in.

### P8-001 — Link neo bị đổi thành URL selector
- Ưu tiên: Medium.
- Vấn đề/tái hiện: detail API mode, mở review=1; khởi tạo tab ném lỗi selector và form review không mở.
- File: frontend/js/auth.js, pages/detail.js, tests/api-accounts-browser.py.
- Nguyên nhân: giữ cờ API đã rewrite href fragment; setupTabs dùng toàn href làm CSS selector.
- Giải pháp: bỏ rewrite fragment-only, resolve hash bằng getElementById, giữ bookingId qua history.
- Nghiệm thu: review completed gửi/lưu/reload/rating và payload HTML an toàn trong browser.
- Trạng thái: DONE — 103 browser assertions PASS.
- Phụ thuộc: FE-001/002.

### P8-002 — Danh sách host mock tham chiếu file thiếu
- Ưu tiên: Medium.
- Vấn đề/tái hiện: mở admin mock ở bốn viewport gây 404/runtime console vì admin-hosts.json không tồn tại.
- File: frontend/js/api.js, tests/ui-browser.py.
- Nguyên nhân: mock source giả định một fixture không có trong repository.
- Giải pháp: ghép user/host-homestays/rooms/bookings bằng owner/room ID thật, không tạo file giả hoặc suy đoán ownership public item.
- Nghiệm thu: 72 tổ hợp mock UI, 0 runtime error.
- Trạng thái: DONE.
- Phụ thuộc: FE-001.

### P9-001 — Nhóm homestay trang chủ mock bỏ sót dữ liệu
- Ưu tiên: Medium.
- Vấn đề/tái hiện: chạy home-checks; 22 records chỉ render tối đa 16 card.
- File: frontend/js/pages/home.js, tests/home-checks.js (assertion giữ nguyên).
- Nguyên nhân: cap explore 8 sau featured/top-rated 4+4.
- Giải pháp: mock render toàn bộ phần còn lại trong rail hiện có; API vẫn lấy trang bounded.
- Nghiệm thu: assertion disjoint/complete và toàn suite home/motion 684 assertion đạt.
- Trạng thái: DONE.
- Phụ thuộc: FE-001.

### P9-002 — Sửa địa chỉ giữ location/city cũ
- Ưu tiên: Medium.
- Vấn đề/tái hiện: sửa address host form API, catalog vẫn location cũ do frontend gửi bản đã load.
- File: frontend/js/pages/host-homestay-form.js, tests/api-accounts-browser.py.
- Nguyên nhân: bảo toàn metadata cũ vô điều kiện.
- Giải pháp: giữ city/location nếu address không đổi; đổi address để backend chuẩn hóa lại, vẫn giữ amenities không có control và không gửi status tự bật moderation.
- Nghiệm thu: browser sửa address và DB location/city đúng, metadata/name reload đúng.
- Trạng thái: DONE — browser PASS.
- Phụ thuộc: FE-001.

### P9-003 — Sink HTML legacy và thông báo upload sai
- Ưu tiên: Medium.
- Vấn đề/nguyên nhân: nhánh mock rooms/error còn nội suy HTML, hint upload nói chưa tải server trong API mode.
- File: frontend/js/pages/host-rooms.js, booking-detail.js, admin-hosts.js, api-host-rooms.js, host-homestay-form.js.
- Giải pháp: textContent/createElement và safeImageURL cho renderer/preview/error; hint API đúng, không sửa CSS.
- Nghiệm thu: API XSS assertions PASS; mock source cuối 72 tổ hợp/244 assertion/0 runtime/overflow.
- Trạng thái: DONE.
- Phụ thuộc: FE-002.

## Phase 7

### P7-001 — Payment history/state/simulation
- Ưu tiên: High.
- Mô tả/nguyên nhân: payment chỉ current state, thiếu audit trail và cơ chế dev paid/refund có bảo vệ; simulation không được trộn vào KPI cash.
- File: payment_service.py, booking_service.py, models.py, migration 0005, admin/bookings routers, reporting.py, tests Phase 7.
- Giải pháp: append PaymentEvent trong transaction; admin+development/test guard; authoritative amount/refund bound; khóa Booking→Payment, idempotent state replay; SIM-* tách khỏi tiền thật.
- Nghiệm thu: production/customer/host reject simulation, không mass assign amount/status/card; paid/refund/retry/concurrency/rollback, ownership, migration giữ ledger/payment, KPI cash không nhận SIM, SQLite/PostgreSQL.
- Trạng thái: IN PROGRESS — chờ full test cuối Phase 6–7.
- Phụ thuộc: gate Phase 6 đã đạt, Phase 5.

### P7-002 — Review/profile validation và paging
- Ưu tiên: Medium.
- Mô tả/nguyên nhân: review list N+1/unbounded; chưa PATCH profile partial; Unicode JSON có thể lọt tới DB.
- File: schemas.py, auth/items routers, serializers.py, tests Phase 7.
- Giải pháp: partial PATCH reuse validation PUT; recursive UTF-8 check; bounded reviews+batch authors, completed/owner/customer/unique rules giữ server-side.
- Nghiệm thu: duplicate/cross-user/pending/cancelled/rating/Unicode/role bị từ chối, average thật/paging đúng, profile protected fields/email/avatar đúng, password/session/media regression pass cả hai engine.
- Trạng thái: IN PROGRESS — chờ full test cuối.
- Phụ thuộc: BE-001/003/007, Phase 6.

## Phase 6

### P6-001 — KPI/performance
- Ưu tiên: High.
- Vấn đề/nguyên nhân: Python load-all và N+1, booking value dễ bị hiểu là cash, thiếu tổng KPI/SQL page.
- File: reporting.py, host/admin/bookings routers, serializers.py, tests/test_phase6_reporting.py.
- Giải pháp: SQL aggregation/UTC cohort/local day, payment cash riêng, current-inventory occupancy, bounded projections/lists/batch DTO.
- Nghiệm thu: số booking không nhân bởi lines; pending không cash; refund đúng; owner isolation, timezone, query-count, filter/page, SQLite/PostgreSQL/regression.
- Trạng thái: IN PROGRESS — chờ gate Phase 6.
- Phụ thuộc: Phase 5; FE-005 cho charts thật sau.

### P6-002 — Application history và quản trị
- Ưu tiên: Medium.
- Vấn đề/nguyên nhân: resubmit ghi đè review/data cũ, list thiếu filter/sort/page.
- File: models.py, migration 0004, admin router, serializers.py và tests.
- Giải pháp: append immutable history, backfill current reviewed snapshot, giữ lock order/token policy; SQL filter/page/sort.
- Nghiệm thu: reject/resubmit/approve không mất history; migration sạch/v3 upgrade, metadata; duplicate/concurrent review và user lock/moderation vẫn đúng.
- Trạng thái: IN PROGRESS — chờ gate Phase 6.
- Phụ thuộc: BE-002/003, P6-001.

### FE-005 — Chart legacy không biểu diễn cash và projection pagination
- Ưu tiên: High.
- Vấn đề: frontend còn tự cộng toàn giá trị booking và arrays, không dùng SQL KPI mới và chưa tải đủ pages.
- File: frontend host/admin dashboards (chỉ đọc), API_CONTRACT.md.
- Giải pháp/nghiệm thu: integration dùng kpis/payments/series và phân trang, label booking value/cash đúng, occupancy có giới hạn lịch sử; browser E2E trước mock=false.
- Trạng thái: DONE - Phase 8-9 development/API acceptance PASS; PHASE_8_REVIEW.md, PHASE_9_REVIEW.md. Production/provider requirements remain separate.
- Phụ thuộc: FE-001/003, P6-001; ngoài gate API độc lập.

## Phase 5 — Booking Engine

### P5-001 — Eligibility giữa search/availability/quote/create
- Ưu tiên: High.
- Mô tả/nguyên nhân: quote chưa kiểm host active/role và nhận room giá legacy 0; quantity<=4 làm lệch inventory thực của search.
- File: booking_service.py, schemas.py, routers/items.py, serializers.py, test_phase5_booking_engine.py.
- Giải pháp: cùng eligibility host/homestay/room/giá; quantity<=100 với kiểm free_units thực; refresh sau khóa.
- Nghiệm thu: inactive/zero-price/partial block không lọt; unit liên tục cùng quy tắc; inventory>4 quote/create được; concurrency không oversell trên PostgreSQL; Decimal/snapshot/rollback đạt.
- Trạng thái: DONE - acceptance PASS; PHASE_5_REVIEW.md: SQLite 212 pass / 4 skip; full SQLite + PostgreSQL 413 pass / 4 skip / 0 fail / 0 xfail.
- Phụ thuộc: P4-001, P4-003, BE-002/003.

### P5-002 — Replay/status/concurrency và retention
- Ưu tiên: Medium.
- Mô tả/nguyên nhân: chưa có replay window/maintenance retention; host same-status trả thành công; một số truy vấn khóa chưa refresh identity map.
- File: booking_service.py, idempotency_cleanup.py, routers/bookings.py, routers/host.py, tests và runbook.
- Giải pháp: 24h replay, key quá window còn lưu trả 409; maintenance dry-run/apply dọn key>30 ngày, giữ lịch sử; host duplicate status 409, customer cancel retry idempotent; refresh customer/Booking sau khóa.
- Nghiệm thu: same/different key/payload/customer và concurrency; TTL/cancelled replay, cleanup giữ dữ liệu; confirm-vs-cancel/duplicate-confirm không sai history hoặc ledger; expired key không tự tạo đơn trước purge.
- Trạng thái: DONE - acceptance PASS; PHASE_5_REVIEW.md: SQLite 212 pass / 4 skip; full SQLite + PostgreSQL 413 pass / 4 skip / 0 fail / 0 xfail.
- Phụ thuộc: BE-002/003, P5-001.

### P5-003 — Customer/host list/detail và validation
- Ưu tiên: Medium.
- Mô tả/nguyên nhân: host thiếu GET detail, list chưa filter/page; surrogate trong input booking có thể lỗi UTF-8 server.
- File: routers/bookings.py, routers/host.py, schemas.py, test_phase5_booking_engine.py.
- Giải pháp: host GET detail cùng ownership guard, optional status/page giữ array cũ, UTF-8 validation và quantity bound.
- Nghiệm thu: customer/host khác không xem/hủy/sửa được; query sai/Unicode sai/quantity overflow 422; pagination/filter đúng; full regression không lỗi.
- Trạng thái: DONE - acceptance PASS; PHASE_5_REVIEW.md: SQLite 212 pass / 4 skip; full SQLite + PostgreSQL 413 pass / 4 skip / 0 fail / 0 xfail.
- Phụ thuộc: BE-003, P5-001.

### FE-004 — Checkout chưa gửi key và mô tả payment sai khi nối API thật
- Ưu tiên: High.
- Mô tả/nguyên nhân: api.js createBooking chưa gửi stable Idempotency-Key, booking-page dùng quote mock/roomTypesFor và toast thanh toán thành công, trong khi payment server chỉ pending/manual.
- File: frontend/js/api.js, pricing.js, pages/booking-page.js, booking-confirmed.js; chỉ đọc trong Phase 5.
- Giải pháp: integration sau dùng quote/availability thật, stable key giữ qua retry, xử lý replay/expired key, thông điệp payment đúng, không thu PAN/CVV nếu chưa có provider.
- Nghiệm thu: browser E2E retry/timeout không trùng, không false paid, không đưa card data vào API/log; giữ giao diện theo scope integration được duyệt.
- Trạng thái: DONE - Phase 8-9 development/API acceptance PASS; PHASE_8_REVIEW.md, PHASE_9_REVIEW.md. Production/provider requirements remain separate.
- Phụ thuộc: FE-001/002, P5-001/002, EXT-001. Không chặn nghiệm thu API độc lập Phase 5 nhưng chặn fullstack/production.

## Phase 4 — audit và nghiệm thu riêng

Các trạng thái Phase 4 mới nhất nằm tại `PHASE_4_REVIEW.md`; không lấy DONE nghiệp vụ cũ làm bằng chứng thay thế test mới. Không đóng FE-001/FE-002/FE-003, QA-001 frontend E2E hoặc EXT-001 trong Phase 4.

### P4-001 — Search/availability/pagination không nhất quán
- Ưu tiên: High.
- Mô tả/nguyên nhân: tải toàn catalog và lọc/paginate Python; N+1 serializer; guests thiếu ngày và children không lọc; giá card lấy room không còn trống.
- File: routers/items.py, serializers.py, tests/test_phase4_management.py.
- Giải pháp: query eligible rooms, distinct occupied unit toàn khoảng, aggregate capacity/price, JSON membership SQL, COUNT/LIMIT/OFFSET, batch serializer.
- Nghiệm thu: location/guest/children/date/price/amenity/rating/sort/page/invalid query đạt trên SQLite và PostgreSQL; không hiển thị inactive; query-count giữ 5 SELECT với 1 hoặc 12 kết quả.
- Trạng thái: DONE - acceptance PASS; PHASE_4_REVIEW.md, SQLite 185 pass / 4 skip; full SQLite + PostgreSQL 359 pass / 4 skip / 0 fail / 0 xfail.
- Phụ thuộc: BE-002, BE-003; không phụ thuộc viết lại Phase 5.

### P4-002 — Room status/giá và moderation
- Ưu tiên: Medium.
- Mô tả/nguyên nhân: model có inactive nhưng API chưa nhận status; API nhận giá 0.
- File: schemas.py, routers/host.py, deps.py, test_phase4_management.py.
- Giải pháp: pricePerNight > 0, status active/inactive, PUT không có status giữ nguyên; chặn host tự bật lại homestay bị moderation; refresh dữ liệu khi khóa.
- Nghiệm thu: invalid capacity/inventory/price/status bị 422; customer/anonymous/admin không vào host CRUD; host khác 404; inactive không public; admin có thể mở lại theo chính sách riêng; không đổi snapshot booking.
- Trạng thái: DONE - acceptance PASS; PHASE_4_REVIEW.md, SQLite 185 pass / 4 skip; full SQLite + PostgreSQL 359 pass / 4 skip / 0 fail / 0 xfail.
- Phụ thuộc: BE-003, BE-007, P4-001.

### P4-003 — Block một unit và sửa range
- Ưu tiên: Medium.
- Mô tả/nguyên nhân: chỉ block toàn inventory, thiếu update và biểu diễn partial closure.
- File: models.py, migration 0003, booking_service.add_block, routers/host.py, serializers.py, main.py, seed.py, tests.
- Giải pháp: nullable unit có CHECK, null=all; PUT giữ ID, rollback ledger nếu conflict; legacy blockedDates chỉ thay all-unit blocks; partial blocks giữ nguyên khi đổi inventory hoặc gửi form cũ.
- Nghiệm thu: upgrade v2 giữ block/ledger, metadata/FK/check nhất quán; partial/all-unit availability, update/rollback, exclusive checkout và unit liên tục; block-vs-booking không oversell trên PostgreSQL.
- Trạng thái: DONE - acceptance PASS; PHASE_4_REVIEW.md, SQLite 185 pass / 4 skip; full SQLite + PostgreSQL 359 pass / 4 skip / 0 fail / 0 xfail.
- Phụ thuộc: BE-002, P4-001; tái sử dụng ledger Phase 5 có sẵn, không viết engine mới.

Nguồn: toàn bộ `frontend/`, `backend/`, JSON và các script kiểm thử hiện có; không dùng giả định của bản cũ. Frontend hiện có 22 homestay công khai, 22 homestay host, 48 phòng, 550 booking host, 4 booking customer; đây là các tập mock khác nhau, không phải một database đã đồng bộ. Không import mù các tập booking thống kê vào dữ liệu thật.

## BE-001 — Password truncation và JWT không thu hồi
- Ưu tiên: Critical
- Vấn đề: bcrypt cắt mật khẩu UTF-8 sau 72 byte; JWT dùng secret mặc định, không có logout thật, không kiểm tra tài khoản khóa.
- File: `backend/security.py`, `deps.py`, `routers/auth.py`, `.env.example`.
- Nguyên nhân: khung template.
- Giải pháp: Argon2id, kiểm tra 8–128 ký tự không cắt; xác minh hash bcrypt cũ chỉ khi <=72 byte; phiên JWT có jti được lưu dạng digest, thời hạn, token version; secret production bắt buộc; khóa user và đổi mật khẩu vô hiệu hóa phiên.
- Nghiệm thu: Unicode dài phân biệt đúng; token giả/hết hạn/logout/password-change không truy cập được; không trả hash hoặc log credentials; test phân quyền.
- Trạng thái: DONE
- Phụ thuộc: BE-002.

- Evidence: automated API/migration tests + HTTP smoke; see BACKEND_TEST_REPORT.md.

## BE-002 — Thiếu schema và migrations
- Ưu tiên: Critical
- Vấn đề: chỉ có users/items; app và seed tự create_all khi chạy.
- File: toàn bộ backend models/database/main/seed.
- Nguyên nhân: chưa triển khai nghiệp vụ homestay.
- Giải pháp: Alembic baseline giữ users/items cũ, migration cộng thêm schema mới; không xóa bản ghi; DB mới dùng tên riêng; nâng cấp DB cũ sau backup, xác nhận cấu trúc; seed idempotent chỉ development.
- Nghiệm thu: upgrade DB trống và DB template có dữ liệu, dữ liệu cũ nguyên vẹn; FK/index/check/unique hoạt động; không create_all lúc startup.
- Trạng thái: DONE
- Phụ thuộc: không.

- Evidence: automated API/migration tests + HTTP smoke; see BACKEND_TEST_REPORT.md.

## BE-003 — Thiếu authorization theo tài nguyên
- Ưu tiên: Critical
- Vấn đề: chưa có quyền host; frontend hardcode HOST_ID; guard/localStorage không bảo mật.
- File: `backend/deps.py`, routers; `frontend/js/api.js`, `guard.js`.
- Nguyên nhân: mock.
- Giải pháp: backend lấy user từ JWT/session DB; lọc chủ sở hữu mọi homestay/phòng/block/booking; admin có quyền được khai báo rõ; không lấy host/customer ID từ client.
- Nghiệm thu: khách không gọi được host/admin; host A không đọc/sửa tài nguyên host B; đăng ký role admin/host không tự cấp quyền.
- Trạng thái: DONE
- Phụ thuộc: BE-001, BE-002.

- Evidence: automated API/migration tests + HTTP smoke; see BACKEND_TEST_REPORT.md.

## BE-004 — Booking, giá, tồn phòng và thanh toán chưa thật
- Ưu tiên: Critical
- Vấn đề: client gửi tổng tiền/snapshot; booking customer và host độc lập; không giữ tồn phòng, frontend giả lập thành công thanh toán.
- File: `frontend/js/pages/booking-page.js`, `pricing.js`, `api.js`; backend booking services mới.
- Nguyên nhân: mock chưa có server authority.
- Giải pháp: một Booking có nhiều BookingLine; giá snapshot Numeric từ DB, phí 5%; [check_in, check_out); RoomNight unique(room, unit, night), transaction + lock; idempotency; Payment chỉ ghi pending/manual, không tự nhận tiền thành công.
- Nghiệm thu: cạnh tranh không oversell; rollback toàn đơn; hủy/từ chối nhả tồn; giá giả bị bỏ qua; state machine/history; không nhận PAN/CVV; retry không nhân đôi.
- Trạng thái: DONE
- Phụ thuộc: BE-002, BE-003.

- Evidence: automated API/migration tests + HTTP smoke; see BACKEND_TEST_REPORT.md.

## BE-005 — API công khai/host/admin/profile thiếu hoặc lệch contract
- Ưu tiên: High
- Vấn đề: API mẫu thiếu location, amenities, rating, room inventory, ảnh, review, CRUD host, dashboard và profile.
- File: `backend/routers/`, `schemas.py`; `frontend/js/api.js`, các pages.
- Nguyên nhân: template chưa khớp source mới.
- Giải pháp: serializer theo từng endpoint snake_case/camelCase; giữ /api/items làm compatibility; bổ sung API còn thiếu trong API_CONTRACT.md.
- Nghiệm thu: đối chiếu toàn bộ chức năng; schema/validation/filter/ownership có tests.
- Trạng thái: DONE
- Phụ thuộc: BE-002, BE-003, BE-004.

- Evidence: automated API/migration tests + HTTP smoke; see BACKEND_TEST_REPORT.md.

## FE-001 — Cần adapter tích hợp, chưa được sửa giao diện
- Ưu tiên: High
- Vấn đề: getProfile/updateProfile/changePassword chỉ hỗ trợ mock; logout chỉ xóa localStorage; host-register tự gán host; đơn admin viết cứng và đổi DOM; pricing suy ra hai loại phòng; checkout giả lập thanh toán; getAdminHosts đọc admin-hosts.json không tồn tại. Host pages so sánh ID chuỗi nghiêm ngặt.
- File: `frontend/js/api.js`, `auth.js`, `pricing.js`, `pages/host-register.js`, `pages/booking-page.js`, `admin.html`, `pages/admin-hosts.js`.
- Nguyên nhân: các luồng mock không tương đương production.
- Giải pháp: trước tích hợp giữ nguyên frontend và USE_MOCK=true; sau API QA, nối profile/logout/applications, đọc roomTypes và báo giá server, bỏ thông báo thanh toán thành công giả. Serializer host trả ID chuỗi để giữ các so sánh hiện tại.
- Nghiệm thu: integration riêng, không đổi CSS/animation/markup thiết kế, E2E đầy đủ trước khi đổi công tắc.
- Trạng thái: DONE - Phase 8-9 development/API acceptance PASS; PHASE_8_REVIEW.md, PHASE_9_REVIEW.md. Production/provider requirements remain separate.
- Phụ thuộc: BE-001 đến BE-007.

## FE-002 — InnerHTML với dữ liệu có thể do người dùng nhập
- Ưu tiên: High
- Vấn đề: host rooms/homestays/bookings, preview ảnh và lỗi booking-detail có nội suy HTML; token localStorage có rủi ro XSS.
- File: `frontend/js/pages/host-rooms.js`, `host-homestays.js`, `host-bookings.js`, `host-homestay-form.js`, `booking-detail.js`, `auth.js`.
- Nguyên nhân: render mock bằng template string.
- Giải pháp: ghi nhận trước khi đổi; integration chuyển textContent/DOM và nguồn ảnh được kiểm tra, đánh giá lưu token/cookie. Backend luôn phân quyền; không coi việc lọc văn bản là thay thế cho sửa sink DOM.
- Nghiệm thu: payload XSS không chạy; giao diện và selector giữ nguyên; không bật API thật trước xử lý.
- Trạng thái: DONE - Phase 8-9 development/API acceptance PASS; PHASE_8_REVIEW.md, PHASE_9_REVIEW.md. Production/provider requirements remain separate.
- Phụ thuộc: FE-001.

## BE-006 — Review và xét duyệt host thiếu điều kiện
- Ưu tiên: High
- Vấn đề: mock cho gửi review không cần lưu trú hoàn tất, host được cấp ngay; admin chưa lưu duyệt/từ chối.
- File: auth/admin/review routers mới; frontend detail/host-register/admin.
- Nguyên nhân: mô phỏng.
- Giải pháp: customer mặc định, application pending; admin approve/reject có reviewer/time/reason; mỗi completed booking một review, tên lấy từ tài khoản.
- Nghiệm thu: không tự nâng role; không review thay người khác, trước completed hay hai lần.
- Trạng thái: DONE
- Phụ thuộc: BE-001, BE-003, BE-004.

- Evidence: automated API/migration tests + HTTP smoke; see BACKEND_TEST_REPORT.md.

## BE-007 — Config, upload, validation, QA và vận hành
- Ưu tiên: High
- Vấn đề: CORS cấu hình rộng, chưa rate limit, upload validation, body-size limit, lỗi chuẩn, tests/migrations/deployment instructions.
- File: backend main/config/upload/tests/requirements.
- Nguyên nhân: template.
- Giải pháp: settings fail-fast production, origin allowlist, giới hạn body/ảnh, decode và encode lại JPEG/PNG/WebP, rate limit lưu DB, exception không lộ dữ liệu, pytest SQLite và PostgreSQL tùy môi trường; runbook.
- Nghiệm thu: invalid body/file trả 4xx không lộ secret/password; CORS/rate limit có test; fixture DB tách biệt; frontend baseline nguyên vẹn.
- Trạng thái: DONE
- Phụ thuộc: BE-002.

- Evidence: automated API/migration tests + HTTP smoke; see BACKEND_TEST_REPORT.md.

## QA-001 — PostgreSQL và tích hợp frontend thực tế
- Ưu tiên: High
- Vấn đề: PostgreSQL/API đã được kiểm thử bằng cluster riêng; E2E frontend với API thật chưa thực hiện vì frontend vẫn giữ mock theo gate tích hợp.
- File: backend tests/deployment; frontend integration sau.
- Nguyên nhân: môi trường phát triển và phạm vi giữ frontend mock.
- Giải pháp: suite dùng TEST_POSTGRES_URL cho database test riêng; CI/service PostgreSQL; integration có báo cáo riêng. Không ghi DONE khi chưa chạy.
- Nghiệm thu: migrations, cạnh tranh, API ownership/state machine trên PostgreSQL; E2E trước bật USE_MOCK=false.
- Trạng thái: DONE - Phase 8-9 development/API acceptance PASS; PHASE_8_REVIEW.md, PHASE_9_REVIEW.md. Production/provider requirements remain separate.
- Phụ thuộc: BE-001 đến BE-007, FE-001, FE-002.

## BE-008 — ID mock hỗn hợp và itemId null gây lỗi seed PostgreSQL
- Ưu tiên: High
- Vấn đề: user mock có ID số/chuỗi, hs010 có itemId null; insert hỗn hợp ID tường minh/tự tăng làm PostgreSQL sequence trùng khóa trong khi SQLite không báo lỗi.
- File: `backend/seed.py`, mock chỉ đọc.
- Nguyên nhân: các nguồn mock độc lập không có ràng buộc FK/sequence thật.
- Giải pháp: tạo ID user DB và map ownership; property thiếu itemId được đối chiếu title chính xác duy nhất hoặc cấp ID mới sau vùng đã dành; không ghi đè source; đồng bộ sequence PostgreSQL sau seed.
- Nghiệm thu: seed cả SQLite/PostgreSQL, chạy lại không đổi dữ liệu, thêm homestay tiếp theo không trùng ID; không tạo inventory/review/booking giả.
- Trạng thái: DONE
- Phụ thuộc: BE-002.

## FE-003 — Công suất dashboard hiện chỉ tính một roomId và bỏ qua quantity
- Ưu tiên: High
- Vấn đề: frontend dùng booking.roomId và số record room làm mẫu số; đơn nhiều loại phòng hoặc inventory>1 sẽ sai occupancy nếu chỉ đổi API URL.
- File: `frontend/js/pages/host-dashboard.js`, `pricing.js`; backend host dashboard.
- Nguyên nhân: mock giả định mỗi booking một phòng, mỗi record là một unit.
- Giải pháp: backend trả một Booking canonical với rooms/roomIds, dashboard /host/dashboard có from/to, series và occupancy theo BookingLine.quantity/inventory. Integration chỉ thay nguồn số liệu, không thay chart/CSS/layout.
- Nghiệm thu: booking 2 phòng ×2 đêm tạo 4 room-nights, denominator tính inventory; không nhân đôi tổng tiền; E2E chart giữ giao diện.
- Trạng thái: DONE - Phase 8-9 development/API acceptance PASS; PHASE_8_REVIEW.md, PHASE_9_REVIEW.md. Production/provider requirements remain separate.
- Phụ thuộc: FE-001, BE-004, BE-005.

## EXT-001 — Cổng thanh toán và dịch vụ tài khoản ngoài phạm vi kết nối hiện tại
- Ưu tiên: High
- Vấn đề: chưa có payment provider/webhook credentials, email verification/reset password, production storage và load test.
- File: backend Payment/media/config; frontend checkout trong giai đoạn tích hợp.
- Nguyên nhân: chưa có provider và cấu hình triển khai được chọn.
- Giải pháp: hiện theo dõi pending/pay_at_property/refund_due thật, không nhận PAN/CVV hoặc giả paid/refunded; bổ sung adapter/provider, xác minh webhook/idempotency và email service trong thay đổi riêng.
- Nghiệm thu: thanh toán chỉ paid khi được xác minh, retry/webhook không nhân đôi; email/reset và storage có test độc lập.
- Trạng thái: TODO
- Phụ thuộc: BE-004, BE-007, FE-001.

## Khắc phục review Phase 1–3 — 14/11/2026

Trạng thái các issue dưới đây phải đọc cùng kết quả chạy mới ở `PHASE_1_3_REVIEW.md` mục 10. BE-006/BE-007 chỉ được xác nhận trong phạm vi backend đã kiểm thử; không đóng FE-001/FE-002/FE-003, QA-001 hoặc EXT-001. Các mức High hiện có được giữ nguyên. Phần host application của BE-006 thuộc Phase 3; phần review booking phụ thuộc BE-004 và nằm ngoài nghiệm thu lần này.

### R13-M01 — Environment validation
- Ưu tiên: Medium.
- Vấn đề/nguyên nhân: chuỗi APP_ENV lạ bỏ qua guard chỉ áp dụng cho `production`.
- File: `backend/config.py`, `backend/tests/test_phase_1_3_review.py`.
- Giải pháp: allowlist development/test/production trước khi đọc/tạo secret; xác minh dialect DB, TTL, rate limit/window, body limit, origin/port và boolean; secret không xuất hiện trong Settings repr.
- Nghiệm thu: prod/Production bị từ chối; production thiếu secret/SQLite bị từ chối; cấu hình không hợp lệ có regression test; development SQLite vẫn chạy.
- Trạng thái: DONE - acceptance PASS; PHASE_1_3_REVIEW.md section 10, final suite 267 passed / 4 skipped / 0 failed / 0 xfail.
- Phụ thuộc: BE-007.

### R13-M02 — Unicode password
- Ưu tiên: Medium.
- Vấn đề/nguyên nhân: surrogate không encode UTF-8 được đi tới Argon2 gây 500.
- File: `backend/schemas.py`, `backend/security.py`, test review.
- Giải pháp: validate SecretStr trước router và kiểm tra UTF-8 phòng vệ khi hash; không truncate/normalize mật khẩu, giữ legacy bcrypt policy.
- Nghiệm thu: register/login/current/new password không hợp lệ trả 422, không echo mật khẩu; Unicode hợp lệ/legacy tests vẫn pass.
- Trạng thái: DONE - acceptance PASS; PHASE_1_3_REVIEW.md section 10, final suite 267 passed / 4 skipped / 0 failed / 0 xfail.
- Phụ thuộc: BE-001, BE-007.

### R13-M03 — Avatar URL validation
- Ưu tiên: Medium.
- Vấn đề/nguyên nhân: urlsplit/port có thể ném ValueError.
- File: `backend/media.py`, test review và upload hiện có.
- Giải pháp: map parser exception thành 422, giữ whitelist và không fetch URL server-side.
- Nghiệm thu: avatar sai trả 422, profile không cập nhật một phần; upload raster/data URI vẫn pass.
- Trạng thái: DONE - acceptance PASS; PHASE_1_3_REVIEW.md section 10, final suite 267 passed / 4 skipped / 0 failed / 0 xfail.
- Phụ thuộc: BE-007.

### R13-M04 — Host application lock order
- Ưu tiên: Medium.
- Vấn đề/nguyên nhân: User/Application bị khóa theo thứ tự đảo nhau; dữ liệu ORM có thể cũ sau khi chờ khóa.
- File: `backend/routers/auth.py`, `backend/routers/admin.py`, test review.
- Giải pháp: luôn khóa User trước Application, populate_existing, kiểm tra lại role/active/status; dependency get_db rollback exception.
- Nghiệm thu: PostgreSQL apply/approve không deadlock; approve/approve, approve/reject, reject/reject chỉ một quyết định 200, quyết định còn lại 409; role khớp kết quả được lưu.
- Trạng thái: DONE - acceptance PASS; PHASE_1_3_REVIEW.md section 10, final suite 267 passed / 4 skipped / 0 failed / 0 xfail.
- Phụ thuộc: BE-006.

### R13-L01 — Frontend baseline
- Ưu tiên: Low.
- Vấn đề/nguyên nhân: source có một trailing space sau `</main>` ở host-homestay-form.html, hash khác snapshot cũ.
- File: `docs/FRONTEND_BASELINE.json`; frontend chỉ đọc.
- Giải pháp: xác minh diff chỉ là whitespace ngoài text content; giữ nguyên source hiện tại và cập nhật đúng một hash. Không nới assertion hoặc thay UI.
- Nghiệm thu: baseline kiểm tra toàn bộ file và USE_MOCK, không còn diff không được giải thích.
- Trạng thái: DONE - acceptance PASS; PHASE_1_3_REVIEW.md section 10, final suite 267 passed / 4 skipped / 0 failed / 0 xfail.
- Phụ thuộc: BE-007.

### R13-L02 — Settings repr
- Ưu tiên: Low.
- Vấn đề/nguyên nhân: dataclass có thể in jwt_secret qua repr khi debug.
- File: `backend/config.py`.
- Giải pháp: field(repr=False).
- Nghiệm thu: secret không nằm trong repr(Settings).
- Trạng thái: DONE - acceptance PASS; PHASE_1_3_REVIEW.md section 10, final suite 267 passed / 4 skipped / 0 failed / 0 xfail.
- Phụ thuộc: R13-M01.
