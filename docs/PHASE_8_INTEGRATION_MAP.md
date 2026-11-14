# Phase 8 — Integration map (source audit 14/11/2026)

Global USE_MOCK=true được giữ. Chuyển theo route/module, không đổi nguồn toàn website trước gate. Trạng thái dưới đây là audit trước sửa, cập nhật bằng bằng chứng test sau mỗi nhóm.

| Page | Function | Nguồn mock cũ | Backend endpoint / mapping | Trạng thái audit |
|---|---|---|---|---|
| login/register | login/register/saveSession | users.json + local verifier | POST auth/login, auth/register → token/user | NEEDS ADAPTER: API branch có, session/local role chưa xác minh |
| profile | get/updateProfile, changePassword | local users/verifier | GET/PATCH me/profile; POST me/password; POST uploads | NEEDS ADAPTER |
| header/guard | logout/current user/role | app_token/app_user localStorage | POST auth/logout, GET me/profile; server role | SECURITY BLOCKED: cached role/token |
| host-register/profile | register/apply/status | cấp host ngay | POST host/apply; GET me/host-application, pending | NEEDS ADAPTER |
| home/carousel/list/shop | getItems | items.json, local filter | GET items → items/total/page; cards giữ shape | NEEDS ADAPTER: list branch có, home aggregates cần mapping |
| detail/gallery | getItem/reviews | items/mock review | GET items/id, reviews | NEEDS ADAPTER |
| detail/checkout | roomTypesFor/quote | Superior/Deluxe tự sinh | GET items/id/availability, POST bookings/quote | NEEDS ADAPTER |
| checkout | createBooking | local customerBookings | POST me/bookings + stable Idempotency-Key; pending | SECURITY BLOCKED: card form/false paid/key thiếu |
| booking list/detail/confirmed | getBookings/getBooking/cancel | local bookings/session lastBooking | GET/POST me/bookings/id/cancel + payment status | NEEDS ADAPTER |
| host homestays/form/rooms | get/save/delete, blocks | local homestays/rooms + HOST_ID | host CRUD, structured blocks, uploads; string IDs | SECURITY BLOCKED: innerHTML/attrs + missing inventory/partial-block UI |
| host bookings | get/status | local bookings | host/bookings + PATCH status; customer đồng bộ DB | SECURITY BLOCKED: untrusted interpolation |
| host/admin dashboard | aggregates/chart | local arrays/projections | host/dashboard/admin/overview kpis/payments/series | NEEDS ADAPTER: không cộng page đầu làm tổng |
| admin applications/users/moderation | approve/reject/list | DOM-only/current mock | admin APIs, SQL filters/page | NEEDS ADAPTER |
| payment | frontend confirmation | toast success giả | GET me/bookings/id/payments, simulated flag | SECURITY BLOCKED: chưa gateway, không thu PAN/CVV |

Backend hỗ trợ các endpoint cần thiết; chưa thấy MISSING BACKEND SUPPORT trong nhóm tài khoản. Các group chưa tích hợp không được âm thầm ghi mock khi route đang opt-in API. Không đánh dấu TESTED hoặc Phase 8 READY khi chưa có browser evidence.

## Kết quả sau tích hợp

Bảng trên lưu kết quả audit ban đầu, không phải trạng thái bàn giao. Các hàng login/register/profile/header/guard, host application, catalog/detail/availability/quote, checkout/idempotency, booking list/detail/confirmed, host property/room/structured blocks/bookings/dashboard, admin application/users/moderation/dashboard, review/payment display đã **TESTED** bằng trình duyệt API mode. Xem `PHASE_8_REVIEW.md`.

- `?mode=api`: các route customer/host/admin dùng cùng backend; link nội bộ giữ cờ. Route không được hỗ trợ bị chặn, không fallback mock.
- `?accounts=api`: sandbox hẹp chỉ tài khoản, vẫn cố ý chặn booking/host/admin.
- Không cờ: mock cũ. `USE_MOCK=true` giữ nguyên.
- API token nằm trong sessionStorage riêng, không dùng mock token/user. Guard đọc lại `GET me/profile`; backend là quyền quyết định.
- Host metadata không gửi `blockedDates`; lịch chặn dùng GET/POST/PUT/DELETE structured blocks với unit/null và khoảng ngày.
- Host dashboard dùng SQL KPI/series; `occupancySummary` tổng toàn bộ, chart từng homestay giới hạn 100 và ghi rõ giới hạn.
- Admin overview dùng KPI và `period` SQL hoàn chỉnh, không cộng mảng projection 100 dòng. User/applications/homestays dùng pagination/filter/sort theo khả năng endpoint. Tìm host chỉ trong trang và được ghi rõ.
- Bổ sung trường báo cáo vào endpoint hiện hữu là hỗ trợ còn thiếu cho tích hợp chart; không tạo backend nghiệp vụ song song.
