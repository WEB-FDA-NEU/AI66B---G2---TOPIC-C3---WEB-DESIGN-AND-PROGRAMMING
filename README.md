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
| Backend FastAPI | Có migrations, JWT thu hồi được, profile, duyệt host, catalog, booking giao dịch, API host/admin; có thể hủy quyền Host và ghi nhận lý do/thông báo cho Admin. Migration head hiện tại: `0006_host_cancellations`; xem [runbook](docs/BACKEND_RUNBOOK.md) |
| Nối frontend với backend thật | Đã nối customer/host/admin qua `?mode=api`; mock mặc định vẫn được giữ, `USE_MOCK=true` |
| QA | Báo cáo Phase 9/10 là snapshot trước tính năng hủy quyền Host mới nhất; dùng các lệnh kiểm thử bên dưới để xác minh source hiện tại |
| Triển khai production | Chưa sẵn sàng: gateway/email, TLS/deployment, backup/restore và kiểm thử vận hành còn thiếu |

---

## 3.1. Project Overview

LuxStay là nền tảng đặt homestay trực tuyến, kết nối du khách với chủ nhà (host) trên khắp Việt Nam.

- **Khách (user):** tìm kiếm và lọc homestay, xem chi tiết, chọn ngày và phòng ngay trên trang chi tiết, đặt phòng và thanh toán (mô phỏng), theo dõi lịch sử đặt và hủy đặt phòng, quản lý hồ sơ.
- **Host:** gửi đơn đăng ký làm host, quản lý homestay, phòng, giá và lịch trống, xử lý các đơn đặt phòng, xem dashboard doanh thu và công suất phòng.
- **Admin:** xem dashboard tăng trưởng người dùng và đơn đặt theo tỉnh, duyệt hoặc từ chối đơn xin làm host, xem danh sách host.

Không có cờ URL: giao diện dùng mock. Mở `http://127.0.0.1:8000/index.html?mode=api` để dùng FastAPI và database thật trong development. Các luồng customer/host/admin ở API mode dùng cùng DB; localStorage không quyết định booking/phòng/homestay/review/payment. API session riêng trong sessionStorage, backend kiểm tra quyền. Không dùng tài khoản mock đang đăng nhập để thay phiên API.

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
- **Hủy quyền Host:** Host tự hủy trong hồ sơ; Admin có thể hủy Host. Không cho hủy khi còn booking đang chờ, đã xác nhận hoặc đang lưu trú; hủy thành công sẽ vô hiệu hóa homestay và thu hồi phiên đăng nhập Host.
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
python -m venv backend/.venv
backend/.venv/Scripts/Activate.ps1  # macOS/Linux: source backend/.venv/bin/activate
python -m pip install -r backend/requirements-dev.txt
# Chỉ copy .env.example nếu chưa có backend/.env; xem runbook để cấu hình.
python -m alembic -c backend/alembic.ini upgrade head
python -m backend.seed             # development-only, hỏi password bằng getpass
python -m uvicorn backend.main:app --reload --port 8000
```

Mở http://localhost:8000/index.html?mode=api để dùng backend; bỏ `mode=api` để dùng mock. Swagger tại http://localhost:8000/docs. `USE_MOCK=true` vẫn giữ; không cần sửa source để chuyển mode. Hướng dẫn .env, PostgreSQL, backup/migration và QA tại [BACKEND_RUNBOOK.md](docs/BACKEND_RUNBOOK.md).

Seed chỉ dùng development và hỏi mật khẩu ẩn do bạn chọn; không có mật khẩu backend hardcode. Email seed: `huy@test.com` (customer), `host@test.com` (host), `admin@test.com` (admin); mật khẩu chính là giá trị nhập lúc seed, khác verifier demo mock. Seed từ chối ghi đè DB đã có dữ liệu; không reset DB để chạy lại. Khách đăng ký host mới phải chờ admin duyệt và đăng nhập lại.

Chạy frontend riêng: `python -m http.server 5500 --directory frontend`, mở `http://localhost:5500/index.html?mode=api`, backend ở cùng hostname cổng 8000. Dùng nhất quán localhost hoặc 127.0.0.1; CORS allowlist phải đúng origin. Port khác hoặc reverse proxy: cung cấp `globalThis.LUXSTAY_CONFIG = {apiBase: 'https://your-api.example/api'}` trước các module; đây chỉ là cấu hình URL, không chứa secret. Sandbox `?accounts=api` chỉ tài khoản và cố ý chặn nghiệp vụ khác.

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

Kiểm thử API/fullstack cần Python 3.12+, dependency trong `backend/requirements-dev.txt` và Chrome/Edge đã cài. Không cần Node hoặc Playwright:

```powershell
backend/.venv/Scripts/python -m pytest backend/tests -q
backend/.venv/Scripts/python tools/test_backend_postgres.py
backend/.venv/Scripts/python tools/smoke_backend_http.py
backend/.venv/Scripts/python tests/api-accounts-browser.py
backend/.venv/Scripts/python -m ruff check backend tests/api-accounts-browser.py --config backend/ruff.toml
backend/.venv/Scripts/python -m ruff format --check backend tests/api-accounts-browser.py --config backend/ruff.toml
backend/.venv/Scripts/python -m pip check
```

Các runner dùng DB/profile tạm riêng. PostgreSQL runner cần binaries 17 (`POSTGRES_BIN` nếu đường dẫn khác); nếu không có, báo chưa kiểm chứng PostgreSQL, không coi skip là pass. Migration head hiện tại `0006_host_cancellations`. Báo cáo Phase 9/10 và báo cáo tổng là snapshot tại thời điểm lập; [runbook](docs/BACKEND_RUNBOOK.md) mô tả quy trình hiện tại.

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
└── docs/       API_CONTRACT.md · BACKEND_RUNBOOK.md · báo cáo QA · ảnh chụp giao diện
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

**Backend đã có:** schema Alembic giữ dữ liệu cũ, Argon2id/JWT revocation, ownership, catalog/phòng thật, đặt nhiều phòng trong transaction, chống trùng bằng ledger unique, host/admin, review đủ điều kiện, upload, tests SQLite/PostgreSQL và hủy quyền Host có kiểm tra booking đang hoạt động. Migration hiện tại là `0006_host_cancellations`.

**Việc còn lại để chuyển frontend sang chạy thật:**

- **Integration:** customer/host/admin đã nối và kiểm chứng qua `?mode=api`; giữ `USE_MOCK=true` để mock không bị mất. Không dùng mock làm hệ thống xác thực hoặc thanh toán an toàn.
- **DOM safety:** đã xử lý renderer/preview/error bằng DOM và validation URL; bearer vẫn có rủi ro nếu phát sinh XSS mới, chưa pentest độc lập.
- **Dashboard:** đã nối SQL KPI/series/inventory-aware; occupancy dùng tồn kho hiện tại, chưa có inventory history; cash không phải settlement/lợi nhuận.
- **Dịch vụ ngoài:** payment gateway/webhook, email verification/reset và storage/deployment cần cấu hình và QA riêng; không giả lập thành công. Xem EXT-001.
- **Contract:** tài liệu mới là [API_CONTRACT.md](docs/API_CONTRACT.md); một số comment cũ trong frontend vẫn dùng tên tài liệu trước đó và chưa bị sửa trong giai đoạn backend.
- **Ảnh:** mock mới dùng một số ít ảnh Unsplash nên vài homestay còn trùng ảnh bìa. Cần ảnh riêng cho mỗi homestay.
- **File thừa từ template:** `js/pages/shop.js` và `docs/preview-shop.html` không được trang nào dùng, có thể xóa khi dọn dẹp.
