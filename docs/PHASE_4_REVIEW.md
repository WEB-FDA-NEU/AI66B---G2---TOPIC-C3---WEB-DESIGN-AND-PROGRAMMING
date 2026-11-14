# Phase 4 — Homestay & Room Management

Ngày: 14/11/2026. Audit source mới trước sửa; trạng thái ban đầu: **NOT READY**. Kết quả sau triển khai/test được ghi cuối tài liệu.

## Audit trước sửa

| Chức năng | Phân loại ban đầu | Bằng chứng và khoảng trống |
|---|---|---|
| Host CRUD homestay/room, ownership, soft delete | IMPLEMENTED & TESTED | host.py, deps.py, test_host_admin_catalog.py; PUT đang là contract frontend, giữ PUT, không thêm PATCH alias |
| Public detail và availability | IMPLEMENTED & TESTED | /api/items/{id}, /availability; trả roomTypes thật, không tạo Deluxe giả |
| Search/filter/pagination | IMPLEMENTED BUT INCOMPLETE | lọc amenity/date và pagination trong Python; N+1; guests bị bỏ qua nếu thiếu ngày, children bị bỏ qua, giá không dựa phòng khả dụng |
| Room status và giá dương | IMPLEMENTED BUT INCOMPLETE | model có status nhưng input không có; API đang cho giá 0 |
| Block toàn inventory/create/list/delete | IMPLEMENTED & TESTED | ledger [start,end), ownership/conflict có test |
| Block một unit, cập nhật range | MISSING | cần field nullable unit và migration additive; không thay thuật toán booking |
| Public rooms riêng | Không cần endpoint mới | detail.roomTypes và availability.rooms đã đáp ứng frontend; không thêm /homestays hoặc /rooms alias trùng |
| Admin moderation | IMPLEMENTED & TESTED | admin.py có route riêng; không cấp admin quyền giả host |
| Upload/media/ảnh/amenities | IMPLEMENTED & TESTED | media.py decode/re-encode, images là mảng có thứ tự, cover là phần tử đầu |
| Frontend API thật | BLOCKED ngoài Phase 4 | FE-001/002/003, pricing.roomTypesFor vẫn tạo mock; giữ USE_MOCK=true |

## Issue trước triển khai

- P4-001, High, IN PROGRESS: search N+1/filter trong bộ nhớ và khả dụng/giá/số khách không nhất quán. Sửa query SQL + batch serializer, kiểm thử cả hai engine và query-count.
- P4-002, Medium, IN PROGRESS: room giá 0/status không điều khiển được; bổ sung validation/status, bảo vệ moderation của homestay.
- P4-003, Medium, IN PROGRESS: chưa có unit block/update; bổ sung unit nullable + migration mới, giữ block cũ là all-unit, test rollback/concurrency/availability.

Không sửa frontend, không đổi mock flag, không reset DB thật, không commit/push. Không viết lại Booking Engine Phase 5.

## Kết quả cuối: READY cho công việc Phase 5

**Phase 4 backend: READY trong phạm vi API và kiểm thử dưới đây.** P4-001/002/003 đạt nghiệm thu, DONE; không còn Critical/High được xác nhận chưa xử lý trong phạm vi Phase 4. Không đồng nghĩa frontend integration hoặc production READY. Bảng audit và issue phía trên lưu trạng thái trước sửa, không phải trạng thái cuối.

## 1. Đã có trước và phần tái sử dụng

- Host GET/list/create/PUT/DELETE homestay và room; ownership từ JWT/DB, soft delete, chặn xóa khi booking pending/confirmed/checked_in. API dùng `/items` và PUT, phù hợp api.js hiện tại; không tạo alias đề xuất `/homestays` hoặc PATCH CRUD trùng chức năng.
- Public detail có roomTypes thật; availability dùng RoomNight, unique unit-night; quote/booking có snapshot giá và giới hạn sức chứa. Không dùng phòng Deluxe hoặc điểm đánh giá giả từ pricing.js frontend.
- Admin moderation dùng route admin riêng. Admin không giả quyền host; customer và anonymous không được gọi protected CRUD.
- Images/amenities là JSON array; thứ tự ảnh giữ trong array và ảnh đầu làm cover. Media đã kiểm MIME bằng decode raster, re-encode, giới hạn 5MB/16MP, tên random, không dùng client filename, không nhận SVG, không fetch URL từ server. Các test hiện có đã được chạy lại.

## 2. Bổ sung/sửa ở Phase 4

- Search chuyển hoàn toàn việc amenity membership, availability, capacity, giá, count và pagination sang SQL. COUNT/LIMIT/OFFSET chạy trước serialization; chỉ batch-load room/rating/host của trang đang trả. Test query-count xác nhận **5 SELECT**, bằng nhau với 1 và 12 kết quả, trên cả hai engine. Availability gom truy vấn ledger cho toàn bộ room, không query theo từng room.
- Guests áp dụng cả khi không có ngày, cộng children; có ngày chỉ tính unit tự do suốt khoảng lưu trú. Không ghép unit khác nhau giữa các đêm. Price filter áp dụng room còn phù hợp; price card/roomTypes của kết quả lấy từ đúng tập đó. Sort rating_desc dùng review thật và nulls last.
- Ghi status active/inactive cho room/homestay, không cho body deleted; bỏ status trong PUT giữ trạng thái cũ. Host không thể tự mở lại homestay bị admin moderation. Không đổi role/ownership policies.
- API room yêu cầu giá dương nguyên VND, capacity/inventory có bound. Không cho giảm inventory/capacity phá reservation, không chuyển room sang homestay khác. Snapshot booking vẫn độc lập với giá room hiện tại.
- Block thêm `unit`: null/all-unit hoặc integer/một unit, cùng ledger cũ; PUT sửa range/scope giữ ID, xung đột rollback cả thay đổi và ledger. Chặn cùng unit/ngày với booking/block khác trả 409; partial unit còn tự do vẫn sử dụng được.
- Room host response thêm `blocks` đầy đủ. Legacy blockedDates chỉ biểu diễn và thay all-unit blocks, không xóa partial blocks. Tăng inventory mở rộng all-unit, giữ nguyên unit của partial block.

## 3. API hiện tại / frontend đối chiếu

| Luồng frontend | Endpoint chính | Ghi chú tích hợp sau |
|---|---|---|
| home/list/shop getItems | GET /api/items | q/location, dates, guests/children, min/max_price, room_type, amenity, rating, sort, page/page_size; không filter/paginate toàn bộ ở frontend |
| detail getItem | GET /api/items/{id} | roomTypes là dữ liệu thật, không gọi mock roomTypesFor để tạo phòng mới |
| chọn ngày/phòng | GET /api/items/{id}/availability | checkin/checkout/adults/children; available toàn khoảng; room available=0 để disable |
| host list/detail homestay | GET /api/host/homestays, GET .../{id} | ID chuỗi trong view host như frontend đang so sánh |
| host save/delete homestay | POST /api/host/homestays, PUT/DELETE .../{id} | Identity lấy JWT; optional status; xóa mềm, giữ lịch sử |
| host list/detail room | GET /api/host/rooms?homestay_id=..., GET .../{id} | Không tạo nested alias trùng; lọc ownership |
| host save/delete room | POST /api/host/rooms, PUT/DELETE .../{id} | homestayId, capacity, inventory, pricePerNight, images, status, blockedDates |
| quản lý lịch block | GET/POST /api/host/rooms/{id}/blocks, PUT/DELETE .../{block_id} | start_date/end_date/reason/unit; null=all, unit=1..inventory |
| moderation | PATCH /api/admin/homestays/{id}/status | Admin theo chính sách có sẵn |
| upload | POST /api/uploads | Không thêm cloud/provider |

Không thêm public room endpoint riêng vì detail và availability đã đáp ứng frontend. Giá card là mỗi room-night thấp nhất trong tập room phù hợp, không phải tổng cho đủ số khách; báo giá vẫn do endpoint quote có sẵn xác minh lại. Category là query template cũ, chưa có field nghiệp vụ nên giữ tương thích nhận/no-op; không quảng bá như bộ lọc địa điểm. Xem API_CONTRACT.md cho giới hạn và shape chi tiết.

## 4. Database / migration

- Thêm **0003_block_unit**, down_revision=0002_luxstay. Thêm nullable Integer unit trên room_blocks và CHECK null hoặc 1–100. Không sửa revision cũ, không reset/copy lại bảng hoặc xóa ledger/booking.
- SQLite dùng native ADD COLUMN có CHECK để tránh rebuild parent đang được RoomNight tham chiếu; PostgreSQL ADD COLUMN + CHECK trong migration transaction. Null trên mọi block cũ giữ nguyên ý nghĩa all-unit. Unit không vượt inventory được kiểm tra khi ghi API dưới khóa room.
- Models giữ FK, unique room+key, ledger unique(room_id,unit,night), XOR booking/block, date-order, status/range, indexes room/night, Numeric(14,0), UTC timestamps. Không có schema lớn mới hoặc ORM relationship bắt buộc.
- DB price constraint lịch sử vẫn cho phép 0 để không tự thay dữ liệu cũ; API mới không nhận 0 và search loại room giá 0. Nếu có dữ liệu miễn phí legacy, người vận hành phải audit/chọn giá hợp lệ trước quảng bá, không tự bịa giá/migrate giá.
- `/api/ready` và seed CLI được cập nhật yêu cầu `0003_block_unit`. Test readiness đổi expected revision tương ứng, không bỏ assertion. Runbook bổ sung yêu cầu backup → upgrade head trước khi chạy code mới. Không chạy upgrade trên DB thật trong lượt này.
- Tests sạch đến head, legacy users/items lên head, v2 có block/ledger lên v3 giữ ID/reason/unit null, CHECK unit=0 bị từ chối/rollback, FK, unique, seed idempotent, Alembic metadata check đều PASS trên SQLite/PostgreSQL. Không chứng nhận restore bản sao production chưa được cung cấp.

## 5. Security/authorization review

- Test anonymous=401, customer/admin gọi host CRUD=403, host khác=404; owner identity không nhận từ body và host_id/hostId bị 422. Public chỉ trả homestay active của host active; host account bị khóa được auth guard từ chối theo test Phase 1–3 chạy lại.
- Status moderation không bị PUT không có status vô tình mở lại; host tự mở homestay bị moderation trả 409, admin có route mở lại. Soft delete không xóa booking/Room/BookingLine bằng SQL DELETE.
- Invalid name/address/description/length/status, capacity/inventory/price, JSON/query, date/partial range và unit được validate; giá NaN/rating NaN bị 422. SQLAlchemy bind parameters được dùng cho query; probe q/amenity kiểu SQL injection không mở rộng kết quả.
- DTO public không xuất password_hash/email/token của host; hostPhone là contact public có trong contract cũ, không thêm hồ sơ account vào catalog. Không log password/token. Upload tests giữ kiểm nội dung raster và path traversal.
- Block/create/update và booking cùng khóa homestay → room; rollback khi conflict. Test đồng thời block-vs-booking chỉ một request thành công, request còn lại 409, ledger không trùng và không trộn reservation thất bại.
- Không phát hiện bypass mới trong các ca đã chạy. Đây không phải pentest toàn diện hoặc kiểm chứng mọi race condition.

## 6. Kiểm thử đã chạy

| Lệnh/nhóm | Pass | Fail | Skip | Xfail |
|---|---:|---:|---:|---:|
| Test Phase 4 mới riêng, SQLite | 46 | 0 | 0 | 0 |
| Full SQLite, phase4-sqlite.xml | 185 | 0 | 4 | 0 |
| Full SQLite + PostgreSQL 17 tạm, phase4-final.xml | **359** | **0** | **4** | **0** |

Full SQLite 44,57 giây; full cả hai engine 208,18 giây, **363 ca**. 4 skip là ca row-lock Phase 1–3 chỉ hỗ trợ PostgreSQL trên bản SQLite; các ca PostgreSQL tương ứng đều chạy. Test block-vs-booking Phase 4 chạy cả hai engine. Không cộng các lượt chạy lặp thành số test khác nhau.

Lệnh tái lập từ repo root:

```powershell
backend/.venv/Scripts/python -m pytest backend/tests -q --tb=short
backend/.venv/Scripts/python tools/test_backend_postgres.py -rxX
backend/.venv/Scripts/python tools/smoke_backend_http.py
```

JUnit gitignored: backend/.test-tmp/phase4-sqlite.xml và phase4-final.xml. PostgreSQL là cluster/initdb mới, cổng loopback ngẫu nhiên, DB luxstay_test và private schemas từ fixtures; không dùng service/database thật. SQLite cũng là file test riêng. HTTP smoke thật Uvicorn/migrate/catalog/quote/booking/host/cancel/logout PASS, frontend vẫn mock.

Ruff các file Python sửa PASS. Không đo lại coverage, không browser E2E, không load/EXPLAIN benchmark production hoặc quét CVE trong lượt này.

## 7. Lỗi/giới hạn còn lại

- Không còn Critical/High Phase 4 đã được xác nhận chưa sửa. Query-count test không chứng minh hiệu năng catalog lớn; JSON/aggregate cần load test/EXPLAIN trước production.
- Category template chưa có entity/filter nghiệp vụ, giữ no-op đã công khai trong contract. Không nằm trong danh sách filter nghiệm thu Phase 4.
- Ruff toàn backend còn import-order Low đã ghi nhận ở migrations/env.py từ trước; không sửa migration env ngoài phạm vi.
- FE-001/002/003, E2E frontend, EXT-001/provider/email/reset/storage còn mở, giữ nguyên High. Không hạ severity để tuyên bố fullstack READY.
- Không có lịch sử thay đổi inventory theo thời gian; dashboard dùng inventory hiện tại, không chứng nhận doanh thu/công suất lịch sử tuyệt đối. Không mở rộng Phase 5 hoặc provider trong lượt này.

## 8. File thay đổi trong lượt Phase 4

| File | Lý do |
|---|---|
| backend/routers/items.py | SQL search/filter/page, rating sort, availability batch |
| backend/serializers.py | batch catalog, structured blocks và legacy dates |
| backend/routers/host.py | status/moderation, partial block preservation, update block |
| backend/booking_service.py | mở rộng riêng add_block theo unit/update; không viết lại booking engine |
| backend/schemas.py | status, giá dương, block unit |
| backend/models.py | RoomBlock.unit/check |
| backend/deps.py | populate_existing khi khóa homestay |
| backend/migrations/versions/0003_room_block_unit.py | additive migration |
| backend/main.py, backend/seed.py | head revision mới |
| backend/tests/test_phase4_management.py | 46 ca test mới, chạy trên cả hai engine |
| backend/tests/test_ops_media_migrations.py | expected head trong readiness test |
| docs/API_CONTRACT.md | query/status/unit semantics và frontend mapping |
| docs/DATABASE_SCHEMA.md, docs/BACKEND_RUNBOOK.md | schema mới, SQL search và upgrade |
| docs/BACKEND_ISSUES.md, docs/BACKEND_ROADMAP.md | trạng thái/gate và dependencies |
| docs/PHASE_4_REVIEW.md | audit trước sửa và báo cáo sau test |

Working tree có các sửa đổi cũ từ trước, kể cả trailing space frontend đã audit ở Phase 1–3. Lượt này không chỉnh bất kỳ frontend file/baseline, USE_MOCK hoặc dependencies. Không commit/push.

## 9. API frontend cần tích hợp sau

Giữ giao diện hiện tại; nối getItems với query/pagination thật và roomTypes/availability với dữ liệu DB, thay logic roomTypesFor/quote mock ở integration có kiểm soát. Host dùng nguyên PUT/POST endpoints; partial block phải dùng blocks/structured API, không suy partial closure từ blockedDates. Thể hiện status/conflict 409 và moderation đúng; không coi search là giữ chỗ. Nối upload theo URL server và giữ thứ tự ảnh. Chạy E2E customer/host/admin, xử lý DOM sinks/token/API_BASE/CORS trước khi bật USE_MOCK=false.

## 10. Kết luận

**READY để bắt đầu audit/phát triển Phase 5 trong phạm vi backend**, sau khi người triển khai đọc contract mới và áp dụng migration trên môi trường phù hợp. Không đánh dấu Phase 5 DONE chỉ vì code booking đã tồn tại. **Frontend integration/fullstack/production vẫn NOT READY** theo các gate riêng đã nêu.
