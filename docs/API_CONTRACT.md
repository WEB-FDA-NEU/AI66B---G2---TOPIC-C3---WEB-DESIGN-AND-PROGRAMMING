# LuxStay REST API — contract từ frontend hiện tại

## Phase 8–10 — tích hợp đã kiểm chứng

`?mode=api` nối customer/host/admin; không cờ giữ mock. `?accounts=api` chỉ sandbox tài khoản. Cờ không cấp quyền, endpoint vẫn xác minh JWT/session/role/ownership. Báo cáo source mới: `PHASE_8_REVIEW.md`, `PHASE_9_REVIEW.md`. Những mục Phase 1–7 bên dưới là lịch sử API, không còn nghĩa frontend chưa tích hợp.

Hai bổ sung tương thích cho báo cáo, không đổi schema/migration:

- `GET /api/admin/overview?from=YYYY-MM-DD&to=YYYY-MM-DD`: khoảng tối đa 366 ngày, inclusive, ngày nghiệp vụ Asia/Ho_Chi_Minh; mặc định 30 ngày. Giữ `kpis` toàn hệ thống và projection tối đa 100; thêm `period: {from,to,newUsers,newBookings,series:[{date,users,bookings}],provinces:[{name,bookings}]}` tính SQL trên toàn bộ cohort. Không lấy projection làm tổng. 422 nếu range/ngày sai; chỉ admin.
- `GET /api/host/dashboard?from=...&to=...`: giữ trường hiện hữu; thêm `occupancySummary:{nights,actualNights,capacity,occupancy}` cho toàn bộ tài sản thuộc host, độc lập danh sách chart `occupancy` tối đa 100. `capacity` dựa inventory hiện tại, không phải lịch sử; chỉ host. Giá trị booking không phải cash/lợi nhuận.

Frontend list customer/host/admin gửi page/page_size, filter/status/sort theo các tham số endpoint đã công bố; không suy diễn total từ một array trang. Structured block `unit=null` là tất cả units; metadata room không gửi `blockedDates`. POST booking bắt buộc stable Idempotency-Key ở client; reload/retry payload gốc, không tự đổi key khi chưa rõ kết quả. SessionStorage intent chỉ để đối soát thao tác, không chứa dữ liệu booking/payment làm nguồn chính.

Payment UI dùng `GET /api/me/bookings/{id}/payments`; `simulated=true` luôn ghi mô phỏng. Không customer/host endpoint đánh dấu paid, không PAN/CVV, không gateway thật. Admin simulation chỉ dev/test theo API bên dưới. JWT là bearer trong sessionStorage; logout POST revoke server, password change thu hồi phiên; chưa có HttpOnly cookie flow.

Prefix `/api`, JSON, `Authorization: Bearer <access_token>`. Role frontend: `user` (customer), `host`, `admin`. ID public là integer; view host và room trả ID chuỗi vì các pages so sánh với URL/data-* bằng `===`. Giá JSON là số VND; DB lưu Numeric nguyên đồng. Mọi endpoint ghi đều kiểm tra quyền server.

## Đối chiếu chức năng frontend / API

| Chức năng/source hiện tại | API backend | Quyền / khác biệt phải nối ở integration |
|---|---|---|
| home/list/shop getItems | GET /items | Public; q, sort=newest/price_asc/price_desc/rating_desc, min_price, max_price, room_type lặp, amenity lặp (AND), rating, page, page_size<=1000, checkin/checkout/guests/children |
| detail getItem | GET /items/{id} | Public active; images, amenities, roomTypes thật, price min phòng |
| detail chọn ngày/phòng | GET /items/{id}/availability | checkin/checkout, adults/children; inventory còn thật |
| pricing quote / checkout | POST /bookings/quote | Public; không tin giá client, cùng cấu trúc quote hiện tại |
| getReviews/addReview | GET/POST /items/{id}/reviews | POST user có booking completed; bookingId tùy chọn, nếu thiếu chọn completed chưa review; name client không có quyền giả tác giả |
| register | POST /auth/register | Chỉ tạo tài khoản customer; `role` chỉ nhận `user`; đăng ký Host phải gửi đơn bằng tài khoản đang đăng nhập |
| login/saveSession | POST /auth/login | {access_token,token_type,user}; user không có hash |
| getUser/getProfile | GET /me, GET /me/profile | JWT/session active; profile gồm id,display_name,email,phone,role,avatar,createdAt |
| updateProfile | PUT/PATCH /me/profile | PUT đầy đủ, PATCH các field được gửi; display_name,email,phone,avatar; không nhận role/is_active |
| changePassword | POST /me/password | current_password,new_password; thu hồi mọi phiên sau thành công |
| deleteAccount | DELETE /me/account | Customer/host; chặn nếu booking của khách hoặc homestay đang pending/confirmed/checked_in; vô hiệu hóa và ẩn thông tin hồ sơ, dừng homestay, thu hồi mọi phiên; giữ lịch sử giao dịch |
| logout | POST /auth/logout | Thu hồi phiên hiện tại; frontend chưa gọi, FE-001 |
| profile become-host | POST /host/apply; GET /me/host-application | Đơn gồm homestay_name,address,province,room_count,description,experience,phone,accept_terms; chỉ nộp lại sau khi bị từ chối; approve nâng cấp cùng tài khoản thành host, reject kèm lý do |
| createBooking | POST /me/bookings | User; homestayId,checkIn,checkOut,adults,children,guestName,guestEmail,rooms:[{key,qty}]; optional Idempotency-Key; bỏ qua giá/snapshot client |
| booking-list/detail | GET /me/bookings; GET /me/bookings/{id} | Chỉ booking của mình; array mặc định, optional page/page_size/status; view camelCase tương thích |
| cancelBooking | POST /me/bookings/{id}/cancel | pending/confirmed, idempotent cancel; ledger/history/refund |
| getHostHomestays/getHostHomestay | GET /host/homestays[/{id}] | Host sở hữu, loại deleted |
| saveHostHomestay | POST /host/homestays; PUT /host/homestays/{id} | name,address,description,amenities,images; city/location/status tùy chọn; id client không quyết định ownership; không cho host tự bật lại homestay bị admin moderation |
| deleteHostHomestay | DELETE /host/homestays/{id} | Soft delete, chặn nếu còn booking pending/confirmed/checked_in |
| getHostRooms/getHostRoom | GET /host/rooms[/{id}] | homestay_id query (đúng api.js hiện tại), chỉ host sở hữu |
| saveHostRoom | POST /host/rooms; PUT /host/rooms/{id} | homestayId,name,description,capacity,pricePerNight>0,inventory,images,blockedDates,status; kiểm tra xung đột tồn |
| deleteHostRoom | DELETE /host/rooms/{id} | Soft delete, giữ lịch sử, chặn booking đang hoạt động |
| lịch chặn phòng | GET/POST /host/rooms/{id}/blocks; PUT/DELETE /host/rooms/{id}/blocks/{block_id} | Range [start_date,end_date), unit nullable: null/toàn bộ inventory, integer/chỉ một unit; blockedDates cũ chỉ biểu diễn all-unit |
| host-bookings | GET /host/bookings; GET /host/bookings/{id}; PATCH /host/bookings/{id}/status | {status,reason}; ownership; optional page/page_size/status; state machine và lịch sử |
| host-dashboard hiện tự tính | GET /host/dashboard?from=YYYY-MM-DD&to=YYYY-MM-DD | Kỳ inclusive tối đa 366 ngày; mặc định 30 ngày đến hôm nay; series revenue/bookings theo ngày tạo, occupancy theo quantity/inventory; raw lists vẫn tương thích |
| admin-dashboard | GET /admin/overview | Admin; users/bookings/homestays projections tương thích biểu đồ |
| admin-hosts | GET /admin/hosts | Host + homestays + bookingCount/revenue |
| hàng đợi admin HTML viết cứng | GET /admin/host-applications | Cần adapter FE-001 |
| duyệt/từ chối host trên DOM | POST /admin/host-applications/{id}/approve; POST .../reject | reject {reason} bắt buộc; reviewed_by/reviewed_at; không duyệt lặp |
| quản trị user | GET /admin/users; PATCH /admin/users/{id} | active/role theo chính sách, không khóa/hạ quyền admin cuối cùng hoặc chính mình |
| quản trị homestay | GET /admin/homestays; PATCH /admin/homestays/{id}/status | active/inactive; lưu lý do moderation |
| ảnh avatar/homestay/room | POST /uploads | Auth; multipart file JPEG/PNG/WebP, <=5MB; decode/encode lại; trả {url}; data URI raster được kiểm tra khi dùng form hiện tại |
| theo dõi thanh toán | GET /me/bookings/{id}/payments | Chỉ chủ booking; API không nhận PAN/CVV; trạng thái pending/manual, không tự báo paid |
| payment simulation phục vụ test | POST /admin/bookings/{id}/payment-simulation | Admin active + APP_ENV development/test; production 403. Body {action:paid/refunded,reason}; không nhận amount/status/PAN/CVV, không có public/customer/host simulation |
| kiểm tra dịch vụ | GET /health; GET /ready | /ready kiểm tra DB/schema, không tự migrate |

## Quy ước
- Phase 7 head `0005_pay_events` (sau `0004_app_history`): Payment response thêm history và simulated, transactionReference mô phỏng bắt đầu SIM-. State thật do Booking Engine tạo pending/cancelled/refund_pending; paid/refunded chỉ qua explicit admin development/test simulation ở lượt này. Production không có gateway/provider nên không có API đánh dấu paid/refunded. GET payment chỉ chủ booking, amount từ snapshot booking; mismatch hoặc refund_due ngoài 0..amount trả 409 và rollback.
- Payment simulation: pending→paid khi booking không cancelled/rejected; paid→refund_pending chỉ do cancel/reject và refund policy; refund_pending→refunded khi terminal booking, refund_due>0 và không vượt amount. Retry cùng paid/refunded trả state cũ, không thêm event/thu hoặc hoàn lần hai. Simulation không thay Booking.status/RoomNight. failed dành cho provider tương lai, không có endpoint arbitrary transition. History append cùng transaction; migration chỉ tạo legacy_snapshot current state, không bịa thời điểm giao dịch đã mất.
- KPI tiền từ Phase 7 loại SIM-* khỏi grossCaptured/paidRevenue/refundPending/refunded; tiền thử nằm riêng simulatedCaptured/simulatedRefundPending/simulatedRefunded/simulatedNet, containsSimulation. Legacy doanh thu booking vẫn là booking value. Các số tiền dựa trạng thái ghi trong DB, không thay chứng từ đối soát ngân hàng.
- PATCH /me/profile chỉ merge các field được gửi, reject explicit null (dùng phone="" hoặc avatar="img/placeholder.svg" để xóa hiển thị), validate như PUT. Không cho role/is_active/hash/token_version/id; chỉ current user. Không cần gửi lại avatar để sửa tên. Password/logout/JWT/Argon2 giữ policy cũ. Unicode không encode UTF-8 hợp lệ trong Input (kể cả JSON nested) trả 422 không echo input.
- Public reviews GET /items/{id}/reviews giữ array, page>=1/page_size<=100 mặc định 100, batch authors; POST chỉ customer sở hữu completed booking, một review/booking, đúng homestay. Comment là **plain text không đáng tin**, không phải HTML safe; verified nghĩa là completed stay, không xác nhận payment hay HTML. Integration phải render bằng textContent/escape. Điểm lấy review thật; duplicate race bị unique booking constraint chặn 409.
- Phase 6: lists host homestays/rooms và admin users/homestays/hosts/applications mặc định page=1/page_size=100, max=100; customer/host booking lists mặc định page=1/page_size=20, max=100. Giữ array shape, dùng LIMIT/OFFSET SQL và batch DTO. Điều này thay mặc định unbounded Phase 5; integration phải tải page cần thiết, không coi page đầu là toàn dữ liệu.
- Admin users hỗ trợ role=user/host/admin, is_active, sort=id/newest/email; admin homestays/application hỗ trợ status hợp lệ. Overview có kpis toàn DB, các mảng legacy projection giới hạn 100. Host dashboard có SQL KPIs, payments, recentBookings<=10, roomTypeCount/inventoryCount/homestayCounts; arrays homestays/rooms<=100. Admin hosts có projection homestay giới hạn 1000 trên trang, không dùng projection để suy KPI toàn bộ.
- Tiền dashboard: bookingValue/legacy revenue fields là giá trị booking, payments.paidRevenue mới là captured-refunded; refundPending không phải đã hoàn. Không coi serviceFee hay booking value là platform profit (platformRevenue=null). Payment kỳ hiện theo cohort booking created_at, không phải cashflow event-date. Occupancy dựa ledger/current inventory, không có inventory history; xem PHASE_6_REVIEW.md.
- Host application response thêm history immutable của các quyết định từ migration 0004; backfill chỉ current reviewed snapshot có thật, không tái tạo các bản cũ đã mất.
- Phase 4 giữ tên `/items`, PUT và `/host/rooms?homestay_id=...` đang được api.js sử dụng. Không tạo alias `/homestays`, PATCH CRUD hay public `/rooms` trùng chức năng: public rooms đã nằm trong detail.roomTypes và availability.rooms.
- Search: q tìm name/location/city; room_type là loại homestay, amenity là exact membership JSON với AND, rating dựa review thật (không có review trả null, không tạo điểm giả). category là tham số template cũ được nhận để tương thích nhưng chưa có dữ liệu tương ứng và không lọc; integration không được quảng bá category như một bộ lọc thực. Sort rating_desc để null cuối, id làm tie-breaker. Pagination COUNT/LIMIT/OFFSET tại SQL, không tải toàn catalog rồi cắt trong Python.
- Search guests là số người lớn mà list.js lấy từ guests/adults; children được cộng riêng. Không có ngày vẫn lọc capacity×inventory. Có ngày chỉ tính unit còn trống **suốt khoảng lưu trú**; không cho chuyển unit giữa chừng. Bộ lọc min/max_price áp dụng giá từng room còn phù hợp trước khi cộng capacity; giá card và roomTypes trong search chỉ từ các room đó. Đây là giá mỗi room-night, không phải tổng chi phí đủ chỗ cho toàn nhóm. Detail vẫn trả mọi room active, availability trả cả room available=0 để frontend vô hiệu hóa lựa chọn; quote/booking luôn xác minh lại tồn, không giữ chỗ bởi search.
- Host có thể ghi status active/inactive, không nhận deleted qua body; DELETE là soft delete và từ chối khi còn booking active. Nếu PUT không có status thì giữ status cũ. Admin có route moderation riêng; host không thể tự bỏ khóa moderation. Giá API room phải dương, nguyên VND; DB constraint lịch sử vẫn cho 0 để không phá dữ liệu cũ, các room giá 0 không được đưa vào search. Capacity 1–50, inventory 1–100, không chuyển room sang homestay khác.
- Block POST/PUT body `{start_date,end_date,reason,unit?}`: unit null/missing chặn toàn bộ inventory, unit 1..inventory chặn đúng unit. PUT là thay khoảng đầy đủ, giữ block ID; lỗi trả 409/422 và rollback cả ledger cũ. Response có unit và scope=all/unit; room host có blocks đầy đủ. blockedDates chỉ gồm ngày chặn all-unit; khi client cũ gửi blockedDates chỉ thay các all-unit blocks, không xóa partial blocks. Tăng inventory mở rộng all-unit blocks, partial blocks giữ unit. Không giảm inventory làm mất unit đang giữ/chặn. Khoảng chặn tối đa 365 đêm, không bao gồm end_date.
- Ảnh là mảng có thứ tự; cover là phần tử đầu, không tạo bảng hoặc dịch vụ cloud mới. Public hostPhone là số liên hệ được contract hiện tại công khai, không trả email/credential/token của host. Head hiện tại của `/ready` và seed CLI là `0005_pay_events`.
- Ngày ISO `YYYY-MM-DD`; nhận phòng không ở quá khứ, trả sau nhận, tối đa 365 đêm; tính theo Asia/Ho_Chi_Minh. Timestamp ISO UTC có timezone.
- Giá được tính từ giá phòng trong DB và snapshot lúc booking; phí 5% làm tròn HALF_UP đến VND. Báo giá không giữ phòng.
- Homestay chưa có room active không có trong kết quả đặt phòng; trang chi tiết/lịch sử vẫn có thể xem và trả `price:null`, `roomTypes:[]` để không tạo giá 0 giả. Adapter tích hợp phải hiện chưa có phòng thay vì định dạng null thành tiền.
- `rooms[].key` là key loại phòng thật trong `roomTypes` (không tiếp tục suy ra superior/deluxe trong production). Có thêm `roomId` cho API client trực tiếp. Item/room availability/quote sử dụng cùng data source.
- Pending/confirmed/checked_in chiếm tồn, completed giữ lịch sử; canceled/rejected nhả reservation. `pending -> confirmed/rejected`, `confirmed -> checked_in`, `checked_in -> completed`; customer có thể cancel pending/confirmed. Check-in/check-out thực tế kiểm tra ngày.
- Host view booking trả một dòng theo Booking (không nhân đôi doanh thu), `id` là booking ID dạng chuỗi và `bookingId` là integer canonical. `roomId` đầu tiên chỉ để tương thích hiển thị hiện tại; `roomIds`/`rooms` và dashboard server là nguồn đúng khi có nhiều loại phòng/inventory. Xem FE-003 trước tích hợp biểu đồ công suất.
- `Idempotency-Key` tối đa 128 ký tự, optional để tương thích client cũ, phạm vi customer. Trong cửa sổ replay 24 giờ từ created_at: cùng key và payload đã validate trả 200 đơn cũ (kể cả đã cancelled), khác payload 409. Key còn lưu nhưng đã quá 24 giờ trả 409, không tự tạo đơn mới. Maintenance chỉ xóa key quá 30 ngày, giữ nguyên Booking/lines/history/payment/snapshot; sau purge không còn bảo đảm dedupe key đó. Client phải đối soát booking gốc trước một checkout/key mới sau timeout dài. Không được quảng bá exactly-once vô thời hạn; xem runbook về lịch cleanup. Body extra display/price bị bỏ qua nên không quyết định fingerprint; thứ tự rooms trong payload có ý nghĩa đối với fingerprint hiện tại.
- List customer/host giữ array để không phá frontend; từ Phase 6 page mặc định 1 (1..100000), page_size 1..100 (mặc định 20), status đúng sáu trạng thái. Không gửi page cũng giới hạn trang đầu; integration phải phân trang. Host GET detail dưới ownership; không cấp customer/admin quyền giả host.
- Phase 5: quote/create cùng yêu cầu host active/role host, homestay active, room active và giá dương. Room quantity 1..100, không vượt inventory thực còn liên tục. Giá legacy 0 không được chọn qua detail/availability/quote/create. Booking giữ snapshot giá/tên/contact dù phòng/homestay đổi hoặc soft delete.
- State transition: pending→confirmed/rejected/cancelled; confirmed→checked_in/cancelled; checked_in→completed. Host gửi lại cùng trạng thái trả 409 và không thêm history. Customer retry cancel đã cancelled trả booking cũ, không thêm history/refund. Cancel/reject xóa đúng ledger của booking, payment pending→cancelled hoặc paid→refund_pending theo policy; không tự hoàn tiền gateway. Completed giữ ledger lịch sử của đêm đã qua; không tự release một booking đang pending/confirmed chỉ vì thời gian trôi qua.
- Lỗi JSON: `{detail: "...", code: "..."}`; validation có `errors` chỉ loc/type/msg, không echo input password/body. 401 thiếu/sai/hết hạn token; 403 sai role; 404 không tồn tại hoặc ngoài ownership; 409 xung đột trạng thái/tồn/email; 413 quá lớn; 415 file sai; 422 validation; 429 rate limit kèm Retry-After.
- AuthSession lưu SHA256(jti), không lưu raw JWT. Logout hiện tại thu hồi một phiên; đổi password/khóa user tăng token_version thu hồi mọi phiên.
- `USE_MOCK=true` được giữ nguyên. API có thật không đồng nghĩa frontend đã tích hợp. Các thay đổi frontend cần thiết được ghi ở FE-001/FE-002 trước khi thực hiện.

## Nguồn kỹ thuật được kiểm tra
- [FastAPI JWT/security](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [SQLAlchemy SQLite transactions](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)
- [Alembic cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html)
