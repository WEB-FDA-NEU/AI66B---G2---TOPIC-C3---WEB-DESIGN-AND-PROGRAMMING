# Kế hoạch triển khai Backend — LuxStay

Nhóm 2 · AI66B · Topic C3 (Homestay Booking)

## 1. Mục tiêu và hiện trạng

**Mục tiêu:** thay toàn bộ dữ liệu mock bằng API FastAPI + database thật, đặt `USE_MOCK = false` mà giao diện vẫn chạy đúng như hiện tại, không phải sửa lại từng trang.

**Hiện trạng**

- Frontend xong 19 màn hình, chạy bằng `frontend/mock/*.json` và `localStorage`.
- Backend mới là khung template: có `User` (role `user | admin`), đăng ký/đăng nhập (JWT + bcrypt), router mẫu `items`, `get_current_user`, `get_admin`. Model `Item` và tiêu đề API "TÊN-SẢN-PHẨM" vẫn chưa đổi.
- `frontend/js/api.js` đã định nghĩa sẵn URL cho từng chức năng. Đây chính là **hợp đồng API** mà backend phải đáp ứng (mục 4).

**Nguyên tắc chung**

1. Backend phải trả JSON **khớp từng chữ** với mock (tên trường, kiểu dữ liệu). Sai một tên trường là giao diện vỡ.
2. Mọi luật nghiệp vụ và phân quyền kiểm tra ở backend. `guard.js` chỉ là lớp giao diện.
3. Tiền tính ở server (số đêm × giá phòng + phí dịch vụ 5%). Không tin con số client gửi lên.
4. Chống đặt trùng phòng bằng ràng buộc ở database, không chỉ bằng câu `if` trong Python.

## 2. Phân công

| Người | Phụ trách backend | Lý do (khớp phần frontend đã làm) |
|-------|-------------------|-----------------------------------|
| **Dương Đức Anh** (A) | Danh mục công khai: tìm kiếm/lọc/sắp xếp homestay, chi tiết, phòng trống theo ngày, đánh giá | Home, Search, Detail |
| **Hoàng Thị Phương Linh** (B) | Tài khoản và role: đăng ký, đăng nhập, role `host`, đơn đăng ký host; **luồng tạo booking + thanh toán mô phỏng** | Login, Register, Host Register, Booking Page, Confirmation |
| **Nguyễn Quang Huy** (C) | Booking của khách (xem, hủy), hồ sơ, đổi mật khẩu; toàn bộ API Admin | Booking History/Detail, Profile, Admin |
| **Lê Sỹ Huy** (D) | API Host: homestay, phòng, lịch trống, quản lý đặt phòng, số liệu dashboard; upload ảnh | Host Dashboard, Homestays, Rooms, Host Bookings |

Cả nhóm cùng làm Giai đoạn 0. Sau đó mỗi người làm trong router riêng của mình để tránh conflict Git.

## 3. Mô hình dữ liệu (chốt ở Giai đoạn 0)

Id dùng số nguyên (`int`). Mock hiện có id dạng chuỗi (`hs001`, `rm001`, `bk001`, `host001`), `seed.py` sẽ chuyển sang số và frontend không được giả định tiền tố.

| Bảng | Cột chính | Ghi chú |
|------|-----------|---------|
| `users` | id, email (unique), password_hash, display_name, phone, role, avatar, created_at | Thêm role `host` |
| `host_applications` | id, user_id, thông tin đăng ký, status (`pending/approved/rejected`), reject_reason, created_at, reviewed_at | Duyệt xong thì đổi `users.role` thành `host` |
| `homestays` | id, host_id, name, location, province, description, amenities (JSON), room_type, status (`active/pending/inactive/deleted`), check_in_time, check_out_time, house_rules (JSON), cancellation_policy, created_at | Xóa mềm = `deleted` |
| `homestay_images` | id, homestay_id, url, position | Ảnh đầu tiên là `cover_url` |
| `rooms` | id, homestay_id, name, description, bed, area_m2, capacity, price_per_night, breakfast_included, free_cancellation | `homestay.price` (giá từ) = giá phòng rẻ nhất, tính khi trả về |
| `room_images` | id, room_id, url, position | |
| `room_nights` | id, room_id, night (date), booking_id (null nếu host khóa ngày) | **UniqueConstraint(room_id, night)**, xem mục 5 |
| `bookings` | id, code, user_id, room_id, check_in, check_out, nights, adults, children, price_per_night, service_fee, total_price, status, reject_reason, customer_name, customer_phone, created_at | Lưu giá tại thời điểm đặt, đổi giá sau không ảnh hưởng đơn cũ |
| `reviews` | id, homestay_id, user_id, rating (1–5), comment, created_at | Rating của homestay là trung bình, tính khi trả về |

Trạng thái booking (đã có trong `api.js`): `pending → confirmed → checked_in → completed`, nhánh phụ `cancelled` (khách hủy) và `rejected` (host từ chối).

## 4. Hợp đồng API

Tiền tố `/api`. Cột "Frontend" là hàm trong `frontend/js/api.js` đang gọi endpoint đó.

### Công khai (Người A)

| Method | Endpoint | Frontend | Ghi chú |
|--------|----------|----------|---------|
| GET | `/items` | `getItems` | Tham số: `q, sort, category, min_price, max_price, room_type[], amenity[], rating, page, page_size`. `q` khớp tên **hoặc** địa điểm. `amenity` phải có **đủ tất cả**. Trả `{items,total,page,page_size}` |
| GET | `/items/{id}` | `getItem` | Gồm `images`, `description`, `amenities`, thông tin phòng |
| GET | `/items/{id}/availability` | (mới) | `checkin, checkout, adults, children` → danh sách phòng còn trống kèm giá |
| GET/POST | `/items/{id}/reviews` | `getReviews`, `addReview` | POST cần đăng nhập, chỉ khách đã hoàn thành đặt phòng mới được đánh giá, mỗi booking một đánh giá |

### Tài khoản (Người B)

| Method | Endpoint | Frontend | Ghi chú |
|--------|----------|----------|---------|
| POST | `/auth/register` | `register` | Đã có, bổ sung `role` hợp lệ |
| POST | `/auth/login` | `login` | Đã có |
| GET | `/me` | | Đã có |
| POST | `/host/apply` | `host-register.js` | Tạo `host_applications` ở trạng thái `pending` |
| POST | `/me/bookings` | `createBooking` | Xem mục 5 (phần quan trọng nhất) |

### Khách (Người C)

| Method | Endpoint | Frontend |
|--------|----------|----------|
| GET | `/me/bookings`, `/me/bookings/{id}` | `getBookings`, `getBooking` |
| POST | `/me/bookings/{id}/cancel` | `cancelBooking` |
| GET, PUT | `/me/profile` | `getProfile`, `updateProfile` (hiện chỉ có chế độ mock) |
| POST | `/me/password` | `changePassword` |

### Admin (Người C, dùng `get_admin`)

| Method | Endpoint | Frontend |
|--------|----------|----------|
| GET | `/admin/overview` | `getAdminOverview`: user và booking toàn hệ thống để vẽ biểu đồ |
| GET | `/admin/hosts` | `getAdminHosts` |
| GET | `/admin/host-applications` | (mới) hàng đợi đơn chờ duyệt |
| POST | `/admin/host-applications/{id}/approve`, `/reject` | (mới) reject bắt buộc có lý do |

### Host (Người D, dùng `get_host` mới, chỉ truy cập dữ liệu của chính mình)

| Method | Endpoint | Frontend |
|--------|----------|----------|
| GET, POST | `/host/homestays` | `getHostHomestays`, `saveHostHomestay` |
| GET, PUT, DELETE | `/host/homestays/{id}` | `getHostHomestay`, `saveHostHomestay`, `deleteHostHomestay` (xóa mềm) |
| GET, POST | `/host/rooms?homestayId=` | `getHostRooms`, `saveHostRoom` |
| GET, PUT, DELETE | `/host/rooms/{id}` | `getHostRoom`, `saveHostRoom`, `deleteHostRoom` |
| GET | `/host/bookings` | `getHostBookings` |
| PATCH | `/host/bookings/{id}/status` | `updateBookingStatus` (body `{status, reason}`) |
| GET | `/host/dashboard?from&to` | (mới) gom số liệu để dashboard không phải tải 500+ booking |
| POST | `/uploads` | (mới) ảnh homestay/phòng/avatar, lưu vào `backend/uploads/` (đã mount `/uploads`) |

**Quy ước tên trường:** mock đang trộn `snake_case` (items) và `camelCase` (host, bookings). Giữ nguyên theo từng endpoint để không phải sửa giao diện. Dùng `alias_generator=to_camel` của Pydantic cho nhóm endpoint camelCase.

**Quy ước lỗi:** 401 chưa đăng nhập, 403 sai role hoặc không phải chủ sở hữu, 404 không tìm thấy, 409 xung đột (trùng email, trùng lịch phòng), 422 dữ liệu sai. Thông điệp tiếng Việt, ngắn gọn.

## 5. Phần khó nhất: đặt phòng và chống trùng lịch

Áp dụng cho `POST /me/bookings` (Người B) và các thao tác đổi trạng thái (Người C, D).

1. Kiểm tra đầu vào: `check_in < check_out`, `check_in` không ở quá khứ, số khách ≤ `capacity`, homestay và phòng đang `active`.
2. Tính tiền ở server: `nights × price_per_night`, phí dịch vụ `5%` (`SERVICE_FEE_RATE` trong `pricing.js`), tổng = hai khoản cộng lại.
3. Trong **một transaction**, chèn mỗi đêm vào `room_nights(room_id, night, booking_id)`. Vì có `UniqueConstraint(room_id, night)`, hai người đặt cùng lúc thì một người nhận lỗi `IntegrityError`, backend bắt và trả **409** "Phòng đã được đặt trong khoảng ngày này".
4. Host khóa ngày trong lịch trống = chèn các dòng `room_nights` có `booking_id = NULL` (cùng ràng buộc).
5. Hủy hoặc từ chối: xóa các dòng `room_nights` của booking đó để phòng trống lại.
6. Luật hủy: khách hủy trước ngày nhận phòng ít nhất 3 ngày (`FREE_CANCEL_DAYS`) thì hoàn tiền toàn bộ. Quá hạn vẫn cho hủy nhưng trả lời rõ không hoàn tiền (cần cả nhóm thống nhất mức hoàn).
7. Chuyển trạng thái chỉ theo đúng thứ tự cho phép. Host chỉ đổi trạng thái booking thuộc homestay của mình.
8. Thanh toán là mô phỏng: không lưu số thẻ và CVV ở bất kỳ đâu.

## 6. Các giai đoạn

| GĐ | Nội dung | Ai làm | Phụ thuộc | Ước lượng |
|----|----------|--------|-----------|-----------|
| 0 | **Chốt nền:** viết models, `docs/api-contract.md`, role `host` + `get_host`, đổi tên `Item`→`Homestay`, quy ước Git, chốt id số nguyên và camelCase/snake_case | Cả nhóm | — | 1–2 ngày |
| 1 | `seed.py` đọc `frontend/mock/*.json` để nạp DB có dữ liệu giống mock; thiết lập pytest | D + A | GĐ 0 | 1–2 ngày |
| 2 | Auth + role + đơn đăng ký host | B | GĐ 0 | 1–2 ngày |
| 3 | API danh mục công khai (tìm kiếm, chi tiết, phòng trống, đánh giá) | A | GĐ 1 | 2–3 ngày |
| 4 | API Host (homestay, phòng, lịch trống, upload) | D | GĐ 1, 2 | 3 ngày |
| 5 | Booking: tạo, chống trùng, hủy, host đổi trạng thái | B + C + D | GĐ 3, 4 | 3 ngày |
| 6 | API Admin + hồ sơ + đổi mật khẩu | C | GĐ 2 | 2–3 ngày |
| 7 | Dashboard host và admin (tổng hợp số liệu bằng SQL) | D, C | GĐ 5 | 2 ngày |
| 8 | **Nối frontend:** `USE_MOCK=false`, bỏ `HOST_ID` cứng, xử lý token hết hạn (401 → về đăng nhập), sửa lệch dữ liệu | Mỗi người nối phần của mình | GĐ 3–7 | 2–3 ngày |
| 9 | Kiểm thử tổng, sửa lỗi, deploy (Neon/Supabase + Render/Railway), chuẩn bị demo | Cả nhóm | GĐ 8 | 2–3 ngày |

GĐ 3, 4, 6 chạy song song được sau GĐ 1. **Ngày hoàn thành từng giai đoạn: nhóm điền sau khi thống nhất.**

## 7. Việc phải xử lý ngay ở Giai đoạn 0

Khi đọc code tôi thấy các điểm lệch cần chốt trước khi viết API:

- `items.json` hiện **không có mảng `rooms`** (ghi chú `PHASE-A-DATA-NOTES.md` nói có). Phòng đang đến từ `host-rooms.json` và hàm `roomTypesFor()` trong `pricing.js`. Cần quyết định: backend là nguồn duy nhất của phòng, và `detail.js` đọc phòng từ API.
- `mock/admin-hosts.json` được nhắc trong `api.js` và `tools/add_mock_hosts.py` nhưng **không có trong zip**. Cần kiểm tra trang danh sách host của Admin có đang hoạt động trên mock không.
- Id kiểu chuỗi trong mock (`hs001`, `rm001`, `host001`) và `HOST_ID = 'host001'` trong `api.js` phải bỏ khi dùng id số.
- `models.py` mới có role `user | admin`, `deps.py` chưa có `get_host`.
- `docs/api-contract.md` và `docs/QUY-UOC-CODE.md` được nhắc trong code nhưng chưa tồn tại. Tài liệu hợp đồng API là sản phẩm của Giai đoạn 0.
- Mật khẩu mock dùng PBKDF2 ở client, backend dùng bcrypt. `seed.py` phải tạo tài khoản demo bằng bcrypt với mật khẩu mà nhóm thống nhất.
- `shop.js` và `docs/preview-shop.html` là file thừa của template, nên xóa.

## 8. Quy trình làm việc chung

- Mỗi việc một nhánh: `feature/<tên>-<chức-năng>`, tạo Pull Request vào `main`, **một người khác review** rồi mới merge. Không push thẳng `main`.
- `models.py`, `schemas.py` dùng chung: sửa phải báo cả nhóm trong PR và ưu tiên merge sớm.
- Mỗi người chỉ thêm router của mình (`routers/homestays.py`, `bookings.py`, `host.py`, `admin.py`…) và đăng ký trong `main.py`. Trong `api.js`, chỉ sửa vùng của mình.
- Đổi cấu trúc DB: dùng Alembic migration (template ghi `create_all` chỉ dùng tạm).
- Thông tin bí mật (`JWT_SECRET`, `DATABASE_URL`) để trong `.env`, không commit. Đổi `JWT_SECRET` trước khi deploy.
- Mỗi endpoint có test pytest tối thiểu: thành công, thiếu đăng nhập (401), sai quyền (403), dữ liệu sai (422).

## 9. Tiêu chí hoàn thành (Definition of Done)

Một endpoint chỉ được tính là xong khi:

1. JSON trả về khớp mock mà trang tương ứng đang dùng.
2. Có kiểm tra quyền đúng role và đúng chủ sở hữu.
3. Có test pytest và đã được một thành viên khác review.
4. Trang frontend tương ứng chạy được với `USE_MOCK = false` trên dữ liệu seed.
5. Có mô tả trong `docs/api-contract.md` và hiện đúng trong `/docs` (Swagger).

**Bộ kiểm thử bắt buộc trước khi demo**

- Hai request cùng đặt một phòng, cùng khoảng ngày: đúng một request thành công, request còn lại nhận 409.
- Hủy hoặc từ chối booking thì phòng đặt lại được.
- Khách gọi `/host/*` hoặc `/admin/*` nhận 403. Host A không sửa được homestay của host B.
- Email trùng khi đăng ký nhận 409. Mật khẩu có dấu tiếng Việt dài hơn 72 byte vẫn đăng nhập được.
- Chạy lại bộ kiểm thử giao diện trong `tests/` với `USE_MOCK = false`.

## 10. Rủi ro

| Rủi ro | Cách giảm |
|--------|-----------|
| Mỗi người hiểu hợp đồng API một kiểu, giao diện vỡ | Viết `api-contract.md` ở GĐ 0, đối chiếu với mock trước khi code |
| Conflict ở `models.py`, `main.py`, `api.js` | Chốt model ở GĐ 0, mỗi người một router và một vùng `api.js` |
| Đặt trùng phòng khi demo đông người | Ràng buộc unique ở DB + test đồng thời (mục 5, 9) |
| Dashboard chậm vì tải hàng trăm booking về trình duyệt | Endpoint tổng hợp bằng SQL (GĐ 7) |
| Lệch dữ liệu giữa mock và DB khiến demo thiếu nội dung | `seed.py` đọc trực tiếp từ `frontend/mock/*.json` |
| Trễ tiến độ ở các giai đoạn phụ thuộc nhau | Làm GĐ 0 và 1 thật nhanh để các nhánh song song bắt đầu sớm |