# Phase 6 — Host Dashboard & Admin

Audit mới 14/11/2026, chưa dùng số test Phase 5 làm bằng chứng. Gate ban đầu **NOT READY**, chưa chuyển Phase 7.

| Chức năng | Trước sửa | Khoảng trống |
|---|---|---|
| Host dashboard và admin overview | IMPLEMENTED BUT INCOMPLETE | Load toàn bộ booking/Python aggregate, N+1, chưa tách payment cash/value, thiếu KPI rõ |
| User/admin moderation/authz | IMPLEMENTED & TESTED | Giữ policy self/last-admin/token revoke, cần filter/sort/SQL page |
| Host approval concurrency | IMPLEMENTED & TESTED | Lock User→Application đã đúng, nhưng resubmit ghi đè review/data cũ |
| Application history | MISSING | Cần migration additive, chỉ backfill snapshot hiện có, không bịa lịch sử đã mất |
| Reporting timezone/inventory | IMPLEMENTED BUT INCOMPLETE | Cần SQL UTC range/local bucket, projection occupancy/actual tách riêng và cảnh báo inventory history |
| Frontend integration | BLOCKED ngoài scope | Giữ toàn bộ frontend và USE_MOCK=true |

Issue trước sửa: P6-001 High KPI/performance; P6-002 Medium filter/page/history. Chỉ đóng sau test SQLite/PostgreSQL/regression. Không bắt đầu sửa Phase 7 trước gate này.

## API và định nghĩa KPI sau sửa

- Giữ GET /host/dashboard, /admin/overview, /admin/hosts, /admin/users, /admin/homestays, /admin/host-applications và các mutation hiện có. Admin user filter role/is_active, sort id/newest/email; homestay/application filter status; SQL page/page_size<=100, array shape giữ nguyên.
- Host dashboard: SQL COUNT/SUM/GROUP BY theo owner; roomTypeCount đếm loại phòng không deleted, inventoryCount cộng unit, homestayCounts theo status; recentBookings<=10, homestays/rooms projection<=100. Không JOIN BookingLine vào tổng booking/money nên không nhân số booking.
- BookingValue chỉ confirmed/checked_in/completed; allBookingValue gồm mọi trạng thái để đối chiếu. Legacy confirmedRevenue/completedRevenue/series.revenue/admin-host revenue vẫn là **booking value**, có basis/definitions rõ và không được coi là tiền đã thu.
- payments.grossCaptured = tổng amount ở paid/refund_pending/refunded; refundPending/refunded lấy refund_due theo trạng thái; paidRevenue = captured-refunded, chưa trừ refund_pending vì chưa hoàn xong. Payment pending/failed/cancelled không tính captured. platformRevenue=null vì chưa có chính sách phí/đối soát; không gọi booking value là lợi nhuận LuxStay.
- Kỳ from/to inclusive, tối đa 366 ngày. Booking cohort lọc created_at bằng UTC boundaries của ngày Asia/Ho_Chi_Minh, bucket local date trong SQL. Payment KPI hiện là trạng thái hiện tại của cohort booking tạo trong kỳ, **không phải dòng tiền theo ngày thanh toán** vì schema cũ chưa có event timestamp.
- Occupancy projected = ledger unit-night confirmed/checked_in/completed trong kỳ / (inventory hiện tại của room active thuộc homestay không deleted × số ngày). actualNights chỉ checked_in/completed và đêm trước hôm nay. Không cộng block, không dùng số booking chia phòng. Không có inventory history nên không chứng nhận occupancy lịch sử chính xác; occupancy projection giới hạn 100 homestay hiển thị, không giả đầy đủ nếu vượt limit.
- Admin overview kpis là thống kê toàn DB thật, projection users/bookings/homestays<=100 để giữ shape cũ. Integration phải dùng kpis/series, không cộng lại projection giới hạn rồi coi là tổng.
- Batch room blocks, booking lines/history, host catalog và application owners/history; test query-count không tăng khi booking tăng 1→13. Không cài cache hoặc thêm thư viện.

## Host application và migration

Thêm `HostApplicationHistory`, revision `0004_app_history` sau 0003. Snapshot gồm application_data/status/reason/reviewer/time, append trong cùng transaction quyết định approve/reject. Resubmit chỉ thay current application, không xóa snapshots. Migration backfill review hiện còn trong DB; lịch sử đã bị ghi đè trước migration không thể khôi phục và không được bịa.

Giữ lock User→Application, token_version tăng khi approve, duplicate review 409, admin-only và active/role conditions. Lịch sử hiển thị ở current/my/admin application response. Head readiness/seed/test được nâng tương ứng; không sửa migration cũ hoặc chạy DB thật.

## Bảo mật và kiểm thử gate

Giữ self/last-admin policy và token revoke; ownership host SQL scope, admin-only lists/mutations, mass assignment ngoài schema 422. Existing tests approval concurrency/moderation/JWT/IDOR/booking/media/migration được chạy lại. Không thay trạng thái booking/payment thật để tạo KPI; các ca paid/refund Phase 6 chỉ là fixture DB test.

SQLite mới: **224 pass, 0 fail, 4 skip, 0 xfail**, 54,66 giây, gồm 12 ca Phase 6. Full SQLite/PostgreSQL: **437 pass, 0 fail, 4 skip, 0 xfail**, 253,42 giây, JUnit `phase6-gate.xml` (gitignored). 24 bản test Phase 6 đều PASS; skip chỉ bản SQLite của 4 row-lock cases Phase 1–3, PostgreSQL đã chạy. Migration sạch/upgrade/backfill/metadata và regression đạt. **Phase 6 backend READY; gate đã đạt trước khi bắt đầu sửa Phase 7**.

## File sửa trong Phase 6

backend/reporting.py; routers/host.py, admin.py, bookings.py; serializers.py; models.py; migrations/versions/0004_application_history.py; main.py/seed.py (head); tests/test_phase6_reporting.py và test_ops_media_migrations.py (expected head); tài liệu issue/roadmap/contract/review. Không chỉnh frontend, Booking Engine hoặc Auth policy.

## Giới hạn và gate

FE-001/002/003/004/005 còn mở High ngoài gate backend; không coi booking value là cash hoặc tổng hợp projections giới hạn ở frontend. Không browser E2E/load test/backup restore production. Phần application history trước khi bị overwrite chỉ backfill được current review. **Không còn Critical/High đã xác nhận chưa xử lý trong scope Phase 6; P6-001/002 DONE. READY để chuyển Phase 7**, không phải fullstack/production READY.
