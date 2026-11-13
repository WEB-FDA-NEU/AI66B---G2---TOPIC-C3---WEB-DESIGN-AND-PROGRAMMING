# LuxStay — Homestay Booking Website

**Topic:** C3 – Homestay Booking
**Group:** 2 — AI66B
**Repository:** https://github.com/WEB-FDA-NEU/AI66B---G2---TOPIC-C3---WEB-DESIGN-AND-PROGRAMMING

---

## Trạng thái hiện tại

| Hạng mục | Tình trạng |
|----------|------------|
| Giao diện (frontend) | Hoàn thành 19 màn hình, chạy ổn định bằng dữ liệu mock |
| Phân quyền theo role (user / host / admin) trên giao diện | Hoàn thành (`js/guard.js`) |
| Dashboard có biểu đồ cho Host và Admin | Hoàn thành (Chart.js) |
| Kiểm thử giao diện tự động | Có (`tests/`) |
| Backend FastAPI | **Mới ở mức khung** từ template: có đăng ký/đăng nhập và router mẫu `items`, chưa đổi sang thực thể Homestay |
| Nối frontend với backend thật | **Chưa làm** (`USE_MOCK = true` trong `frontend/js/config.js`) |

---

## 3.1. Project Overview

LuxStay là nền tảng đặt homestay trực tuyến, kết nối du khách với chủ nhà (host) trên khắp Việt Nam.

- **Khách (user):** tìm kiếm và lọc homestay, xem chi tiết, chọn ngày và phòng ngay trên trang chi tiết, đặt phòng và thanh toán (mô phỏng), theo dõi lịch sử đặt và hủy đặt phòng, quản lý hồ sơ.
- **Host:** gửi đơn đăng ký làm host, quản lý homestay, phòng, giá và lịch trống, xử lý các đơn đặt phòng, xem dashboard doanh thu và công suất phòng.
- **Admin:** xem dashboard tăng trưởng người dùng và đơn đặt theo tỉnh, duyệt hoặc từ chối đơn xin làm host, xem danh sách host.

Hiện tại toàn bộ dữ liệu lấy từ `frontend/mock/*.json` và lưu tạm trong `localStorage` của trình duyệt. Chưa có lời gọi API thật nào được dùng trên giao diện.

---

## 3.2. Implemented Screens and Features

Tất cả file giao diện nằm trong `frontend/`.

| # | Screen | File | Key features | Status |
|---|--------|------|--------------|--------|
| 1 | Home | `index.html` | Thanh tìm kiếm, homestay nổi bật và điểm đến phổ biến dạng carousel | Completed |
| 2 | Search Results | `search.html` | Bộ lọc (giá, loại phòng, tiện nghi, đánh giá, ngày), sắp xếp, phân trang, empty state; giữ ngày và số khách khi chuyển sang trang chi tiết | Completed |
| 3 | Homestay Detail (gộp chọn phòng) | `detail.html` | Thư viện ảnh, mô tả, tiện nghi, vị trí, đánh giá, chọn ngày và hiển thị phòng trống ngay trong trang, tính giá | Completed |
| 4 | Room / Date Selection | `booking-select.html` | Đã gộp vào `detail.html#pricing`. File này chỉ chuyển hướng để link và bookmark cũ vẫn hoạt động | Merged |
| 5 | Login | `login.html` | Đăng nhập, báo lỗi ngay tại trường nhập, quay lại đúng trang đang xem sau khi đăng nhập | Completed |
| 6 | Register | `register.html` | Họ tên, email, số điện thoại, mật khẩu và xác nhận, điều khoản, kiểm tra dữ liệu | Completed |
| 7 | Host Registration | `host-register.html` | Đơn xin làm host, dùng chung logic kiểm tra với Register | Completed |
| 8 | Booking Page (gồm thanh toán) | `booking-page.html` | Bước 1: ngày, số khách, bảng chi phí (số đêm × giá + phí dịch vụ 5%). Bước 2: thanh toán mô phỏng | Completed |
| 9 | Booking Confirmation | `booking-confirmed.html` | Mã đặt phòng, thông tin homestay, ngày, tổng tiền, liên hệ host | Completed |
| 10 | Booking History | `booking-list.html` | Danh sách đặt phòng theo trạng thái, empty state | Completed |
| 11 | Booking Detail | `booking-detail.html` | Chi tiết, tiến trình trạng thái, hủy đặt có hộp xác nhận và chính sách hủy (hoàn tiền toàn bộ nếu hủy trước 3 ngày nhận phòng) | Completed |
| 12 | Profile | `profile.html` | Tên, email, số điện thoại, ảnh đại diện, đổi mật khẩu | Completed |
| 13 | Admin Dashboard | `admin.html` | Số liệu tổng quan, biểu đồ tăng trưởng người dùng và đơn đặt, cơ cấu đơn theo tỉnh, hàng đợi đơn xin làm host (duyệt hoặc từ chối kèm lý do), danh sách host và hộp thoại chi tiết | Completed |
| 14 | Host Dashboard | `host-dashboard.html` | Bộ lọc kỳ (7 ngày / 30 ngày / năm), doanh thu theo tháng, trạng thái đặt phòng, công suất phòng theo homestay, đặt phòng gần đây, thao tác nhanh | Completed |
| 15 | Homestay Management | `host-homestays.html` | Danh sách homestay, đếm theo trạng thái, sửa, xóa mềm, xem phòng, empty state | Completed |
| 16 | Homestay Form (Add/Edit) | `host-homestay-form.html` | Tên, mô tả, vị trí, tiện nghi, tải ảnh (1–10), xóa ở chế độ sửa | Completed |
| 17 | Room Management | `host-rooms.html` | Danh sách phòng theo homestay, form thêm/sửa ngay trong trang, giá, ảnh, lịch trống | Completed |
| 18 | Host Booking Management | `host-bookings.html` | Đơn đặt trên mọi homestay của host, cập nhật trạng thái | Completed |
| 19 | 404 — Not Found | `404.html` | Thông báo thân thiện, link về Home và Search | Completed |

### Thành phần và cơ chế dùng chung

- **Header và footer:** `js/components/site-header.js`, `site-footer.js`.
- **Phân quyền giao diện:** `js/guard.js`. Trang có `<body data-require-role="host|admin">` sẽ chuyển người chưa đăng nhập sang `login.html` (đăng nhập xong quay lại trang cũ). Người sai role thấy màn hình "Trang này chỉ dành cho …" kèm nút quay về hoặc đăng ký làm host. Áp dụng cho `admin.html` và các trang `host-*.html` (trừ `host-register.html`).
- **Tính giá:** `js/pricing.js` là nơi duy nhất tính tiền, để trang chi tiết, trang đặt phòng và xác nhận luôn ra cùng một con số.
- **Biểu đồ:** `js/charts.js` dùng chung cho hai dashboard (bộ lọc kỳ, hiệu ứng đếm số, Chart.js).
- **Hiệu ứng chuyển động:** `js/motion.js` và `css/motion.css`, tôn trọng cài đặt `prefers-reduced-motion`.
- **Tầng dữ liệu:** `js/api.js` là nơi duy nhất được gọi mạng. `js/config.js` chứa công tắc `USE_MOCK`.
- **UI dùng chung:** thẻ homestay, huy hiệu trạng thái, toast, hộp thoại xác nhận, skeleton loading (`render.js`, `ui.js`, `css/components.css`).

---

## 3.3. Instructions to Open/Run the Project

> Không mở `index.html` bằng cách nhấp đúp. Trang dùng ES module và đọc file mock bằng `fetch`, mà trình duyệt chặn cả hai khi mở qua `file://`. Cần chạy qua một máy chủ cục bộ.

**Cách 1 — Chỉ chạy giao diện (không cần cài gì thêm, cần Python)**

```bash
cd frontend
python -m http.server 5500
```

Mở http://localhost:5500.

**Cách 2 — Chạy qua backend FastAPI (backend phục vụ luôn thư mục `frontend/`)**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
python seed.py                  # tùy chọn: nạp dữ liệu mẫu của template
uvicorn main:app --reload --port 8000
```

Mở http://localhost:8000. Tài liệu API tự sinh tại http://localhost:8000/docs. Vì `USE_MOCK = true`, giao diện vẫn đọc dữ liệu mock chứ chưa gọi API.

**Tài khoản demo (mock)**

| Role | Email |
|------|-------|
| Khách (user) | `huy@test.com` |
| Host | `host@test.com` |
| Admin | `admin@test.com` |

<!-- Nhóm bổ sung mật khẩu demo vào đây (không ghi plaintext trong mock/users.json, chỉ có hash PBKDF2). -->

Có thể tự đăng ký tài khoản mới. Tài khoản mock được lưu trong `localStorage` (khóa `luxstay_mock_users_v1`) và không bị mất khi cập nhật dữ liệu mock.

**Luồng thử nhanh**

- Khách: Home → Search → Detail (chọn ngày và phòng) → Booking → Confirmation → Booking History → Booking Detail.
- Host: đăng nhập `host@test.com` → Host Dashboard → Homestays → Rooms → Host Bookings.
- Admin: đăng nhập `admin@test.com` → Admin Dashboard.
- Thử phân quyền: đăng nhập tài khoản khách rồi vào `host-dashboard.html` để thấy màn hình chặn quyền.

**Lưu ý**

- Biểu đồ dùng Chart.js nạp từ CDN. Mất mạng thì trang vẫn chạy nhưng không có biểu đồ.
- Dữ liệu mock được sao chép vào `localStorage` ở lần đọc đầu. Khi sửa `mock/*.json`, hãy **tăng `MOCK_DATA_VERSION` trong `js/api.js`** để mọi máy tự xóa cache cũ (phiên đăng nhập không bị ảnh hưởng).

---

## Dữ liệu mock và công cụ sinh dữ liệu

`frontend/mock/items.json` là nguồn dữ liệu chính. Mỗi homestay có `rooms[]`, `host_name`, giờ nhận/trả phòng, nội quy và chính sách hủy. `item.price` luôn bằng giá phòng rẻ nhất. Các file `host-*.json`, `bookings.json` và `admin-*.json` liên kết với nhau qua `itemId` và `roomId` (chi tiết trong `docs/PHASE-A-DATA-NOTES.md`).

Các script trong `tools/` sinh thêm dữ liệu và chạy lại nhiều lần vẫn an toàn. Chạy từ thư mục gốc dự án, theo thứ tự:

```bash
python tools/add_mock_homestays.py frontend   # thêm homestay 11–22 cùng phòng
python tools/gen_dashboard_mock.py frontend   # booking và user cho dashboard
python tools/add_mock_hosts.py frontend       # hồ sơ host cho trang Admin
```

Sau khi chạy, nhớ tăng `MOCK_DATA_VERSION`.

---

## Kiểm thử

Các bài kiểm thử dùng Chrome hoặc Edge đã cài sẵn, chỉ cần thư viện chuẩn của Python, và chạy trong profile tạm nên không đụng dữ liệu trình duyệt của bạn.

```bash
python tests/ui-browser.py [--screenshots] [--normal-motion] [--motion-checks] [--home-checks]
python tests/mock-accounts-browser.py [đường/dẫn/tới/chrome.exe]
```

- `ui-browser.py`: kiểm tra giao diện responsive. Các cờ thêm kiểm tra chuyển động (`motion-checks.js`) và trang chủ/tìm kiếm (`home-checks.js`).
- `mock-accounts-browser.py`: kiểm tra đăng ký, đăng nhập, đổi hồ sơ và đổi mật khẩu với tài khoản mock.

---

## Cấu trúc thư mục

```
├── README.md
├── frontend/
│   ├── index.html, search.html, detail.html, booking-select.html, booking-page.html,
│   │   booking-confirmed.html, booking-list.html, booking-detail.html, profile.html,
│   │   login.html, register.html, host-register.html, admin.html, 404.html
│   ├── host-dashboard.html, host-homestays.html, host-homestay-form.html,
│   │   host-rooms.html, host-bookings.html
│   ├── css/    reset · tokens · layout · components · home · motion
│   ├── js/
│   │   ├── api.js, auth.js, guard.js, config.js, pricing.js, charts.js,
│   │   │   render.js, ui.js, motion.js
│   │   ├── components/   site-header · site-footer · home-carousels
│   │   └── pages/        mỗi trang một file JS
│   ├── mock/   items · bookings · users · host-* · admin-*  (JSON)
│   └── img/
├── backend/    FastAPI + SQLAlchemy (main, models, schemas, security, deps, database, seed, routers/)
├── tests/      ui-browser.py · mock-accounts-browser.py · home-checks.js · motion-checks.js
├── tools/      add_mock_homestays.py · gen_dashboard_mock.py · add_mock_hosts.py
└── docs/       PHASE-A-DATA-NOTES.md · ảnh chụp giao diện
```

---

## 3.4. Team Members and Individual Contributions

| No. | Student ID | Full Name | Assigned Screens/Pages | Main Contributions | Status |
|-----|-----------|-----------|--------------------------|----------------------|--------|
| 1 | 11247257 | Duong Duc Anh | Home (`index.html`), Search Results (`search.html`), Homestay Detail (`detail.html`), 404 (`404.html`), Room/Date Selection (`booking-select.html`) | Trang chủ, trang tìm kiếm có bộ lọc và phân trang, trang chi tiết với thư viện ảnh và chọn phòng ngay trong trang, trang 404, thẻ homestay dùng chung. Thêm hiệu ứng chuyển động cho toàn giao diện và hỗ trợ hoàn thiện frontend. | Completed |
| 2 | 11247308 | Hoang Thi Phuong Linh | Login (`login.html`), Register (`register.html`), Host Registration (`host-register.html`), Booking Page (`booking-page.html`), Booking Confirmation (`booking-confirmed.html`) | Form đăng nhập, đăng ký có kiểm tra dữ liệu, đơn đăng ký host (dùng chung logic với đăng ký khách), luồng đặt phòng kèm thanh toán mô phỏng và trang xác nhận. | Completed |
| 3 | 11247298 | Nguyen Quang Huy | Booking History (`booking-list.html`), Booking Detail (`booking-detail.html`), Profile (`profile.html`), Admin Dashboard (`admin.html`) | Lịch sử đặt phòng, chi tiết đặt phòng với hộp hủy và chính sách hủy, trang hồ sơ, trang Admin với hàng đợi duyệt host. Đồng bộ phần việc của Đức Anh và Phương Linh cho thống nhất. | Completed |
| 4 | 11247296 | Le Sy Huy | Host Dashboard (`host-dashboard.html`), Homestay Management (`host-homestays.html`), Homestay Form (`host-homestay-form.html`), Room Management (`host-rooms.html`), Host Booking Management (`host-bookings.html`) | Dashboard host, quản lý homestay (xóa mềm), form thêm/sửa homestay, quản lý phòng với lịch trống, quản lý đặt phòng phía host. Hỗ trợ hoàn thiện frontend. | Completed |

<!-- Nhóm bổ sung người phụ trách cho các hạng mục làm thêm: guard.js (phân quyền), charts.js và biểu đồ dashboard, pricing.js, bộ test trong tests/, script sinh mock trong tools/, backend FastAPI. -->

---

## 3.5. Incomplete Features and Screens

**Giao diện:** tất cả màn hình đã hoàn thành trên dữ liệu mock.

**Việc còn lại để chuyển sang chạy thật (giai đoạn backend):**

- **Backend chưa đổi sang đề tài.** `models.py` và `routers/items.py` vẫn là mẫu `Item`, tiêu đề API trong `main.py` còn là "TÊN-SẢN-PHẨM". Cần có model và router cho Homestay, Room, Booking, Review, đơn xin làm host, và các endpoint cho Host và Admin.
- **Chưa nối frontend với API.** Cần đặt `USE_MOCK = false` và bổ sung nhánh gọi API cho các hàm còn thiếu trong `api.js`. Ví dụ `getProfile()` hiện chỉ chạy ở chế độ mock.
- **Phân quyền thật ở backend.** `guard.js` chỉ là lớp giao diện, người dùng vẫn sửa được `localStorage`. Cần thêm `get_host` tương tự `get_admin` trong `deps.py` cho các endpoint của host. Role trong `models.py` hiện mới có `user | admin`, thiếu `host`.
- **Chống đặt trùng phòng ở database.** Cần ràng buộc ở tầng database (ví dụ `UniqueConstraint`) thay vì chỉ kiểm tra bằng `if` trong code.
- **Mốc thời gian của dashboard.** Với dữ liệu mock, biểu đồ lấy ngày mới nhất trong dữ liệu làm mốc. Khi có backend thật phải đổi sang ngày hôm nay (xem `getWindow()` trong `js/charts.js`).
- **Tài liệu tham chiếu chưa có:** `config.js` nhắc `docs/api-contract.md` và `models.py` nhắc `docs/QUY-UOC-CODE.md`, nhưng hai file này chưa có trong `docs/`.
- **Ảnh:** mock mới dùng một số ít ảnh Unsplash nên vài homestay còn trùng ảnh bìa. Cần ảnh riêng cho mỗi homestay.
- **File thừa từ template:** `js/pages/shop.js` và `docs/preview-shop.html` không được trang nào dùng, có thể xóa khi dọn dẹp.