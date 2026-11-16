# Backend roadmap — frontend baseline 14/11/2026

## Hiện tại — Phase 8–10

- Phase 8 integration **DONE/READY cho Phase 9**: customer/host/admin dùng DB qua `?mode=api`; mock mặc định vẫn giữ. Không sửa CSS/motion, không đổi USE_MOCK.
- Phase 9 QA **DONE/READY cho Phase 10 trong development**: suite SQLite/PostgreSQL mới 505 pass/4 skip/0 fail/0 xfail, browser API 103 assertion, UI mock/motion 684 assertion và mock accounts 34 assertion. Xem `PHASE_9_REVIEW.md`, không dùng số 493 lịch sử bên dưới.
- Phase 10 tài liệu/bàn giao: `PHASE_10_DELIVERY.md`, `FULLSTACK_FINAL_REPORT.md`, README, API contract/schema/runbook và manifest thay đổi. Backend/frontend integration **READY trong môi trường development đã test**. Staging thật chưa deploy/xác minh.
- Production **NOT READY**: giữ EXT-001 và gate TLS/deployment/secret/backup restore/security/load; không biến simulation thành gateway, không seed production.

Các mục Phase 1–7 bên dưới giữ để truy vết lịch sử; câu "chưa tích hợp" và trạng thái FE/QA tại thời điểm cũ được thay bằng kết quả ở đầu tài liệu và `BACKEND_ISSUES.md`.

## Phase 6–7 — gate mới nhất

Phase 6 **READY** trước Phase 7: 437 pass/4 skip, 0 fail/xfail SQLite/PostgreSQL. Phase 7 **READY** sau payment events/admin dev simulation/partial profile/paged reviews và tách SIM khỏi cash KPI: full cuối **493 pass/4 skip, 0 fail/xfail**, SQLite riêng 252 pass/4 skip. **Backend READY FOR FRONTEND INTEGRATION**, chi tiết `PHASE_6_7_SUMMARY.md`. Head 0005_pay_events, không sửa frontend, USE_MOCK=true. P6-001/002 và P7-001/002 DONE. Frontend/fullstack/production vẫn NOT READY; các High FE-001..005/EXT-001 giữ nguyên và phải được xử lý trong scope tiếp theo.

## Phase 5 — kết quả lượt trước

Audit service/ledger hiện có, không viết lại engine. Đã đồng bộ eligibility search/availability/quote/create, mở quantity theo inventory thực, refresh khi khóa, host duplicate-status 409, list có optional status/page và host GET detail. Replay window 24h, key maintenance cutoff 30 ngày có dry-run/apply, không xóa booking/snapshot. **Phase 5 backend DONE/READY để bắt đầu Phase 6** theo `PHASE_5_REVIEW.md`: full SQLite 212 pass/4 skip; full SQLite + PostgreSQL 413 pass/4 skip, 0 fail/xfail, gồm 54 ca Phase 5 mới. P5-001/002/003 DONE. Phase 6 dashboard mới chưa triển khai; FE-004 checkout/key/payment message là dependency integration High, USE_MOCK=true. Frontend/fullstack/production vẫn NOT READY.

## Phase 4 — kết quả lượt trước

Audit và hoàn thiện API quản lý trên code có sẵn, chi tiết `PHASE_4_REVIEW.md`. Search SQL/batch pagination, status/positive price, block theo unit/update và migration additive 0003 đã kiểm thử: SQLite **185 pass/4 skip**, full SQLite + PostgreSQL **359 pass/4 skip, 0 fail, 0 xfail**. **Phase 4 backend DONE/READY để bắt đầu Phase 5** trong phạm vi nghiệm thu; P4-001/002/003 DONE. Không phát triển Phase 5 mới; code booking có sẵn chỉ dùng kiểm tra xung đột tồn và regression. Frontend integration vẫn TODO và USE_MOCK=true.

## Gate hiện tại sau khắc phục Phase 1–3

- **Backend Phase 1–3 độc lập: READY** theo `PHASE_1_3_REVIEW.md` mục 10: SQLite 139 pass/4 skip; full SQLite + PostgreSQL 267 pass/4 skip, 0 fail, 0 xfail. Migrations và bốn ca concurrency PostgreSQL đạt; không sửa schema/migration ở lượt khắc phục.
- **Frontend integration/fullstack: NOT READY**. FE-001/FE-002/FE-003 và phần E2E của QA-001 còn mở, giữ nguyên High; USE_MOCK=true. Không lấy backend READY để bật API thật hoặc đóng các issue này.
- **Lịch sử gate Phase 1–3:** khi chốt lượt trước chưa phát triển/nghiệm thu thêm Phase 4. Đợt Phase 4 hiện tại đã được nghiệm thu riêng ở đầu tài liệu và PHASE_4_REVIEW.md; EXT-001/deployment vẫn TODO.
- Bằng chứng mới thay thế các kết luận DONE quá rộng của báo cáo trước; kết quả đầy đủ, lỗi trung gian và giới hạn nằm ở mục 10 báo cáo review.

## Lộ trình và code hiện có

1. **Audit (đã đọc source mới):** giữ SHA-256 toàn bộ frontend trong FRONTEND_BASELINE.json; ghi issue trước sửa; đối chiếu từng API trong API_CONTRACT.md. Các kế hoạch cũ chỉ là tài liệu tham khảo, không quyết định schema.
2. **Database (DONE):** baseline Alembic giữ users/items template; revision mở rộng additive; User → Homestay → Room; Booking → BookingLine → RoomNight; HostApplication, Review, Payment, BookingStatusHistory, AuthSession, RateLimitBucket. Không dùng create_all cho startup/production. Không import booking thống kê mock vào tồn phòng.
3. **Auth (backend, kiểm chứng lại tại PHASE_1_3_REVIEW.md mục 10):** Argon2id, JWT session/revocation, profile/password, role và ownership, customer đăng ký trước rồi admin duyệt host, validation/rate limit. Frontend integration chưa DONE.
4. **Nghiệp vụ backend (code có sẵn từ trước, ngoài gate Phase 1–3 hiện tại):** tìm kiếm/availability/quote; booking nhiều loại phòng, giá từ DB, idempotency, ledger unique theo unit-night, cancellation/refund ledger; host CRUD/block/status; review đủ điều kiện; admin moderation và dashboard. Không phát triển hoặc chứng nhận hoàn tất Phase 4 trong đợt khắc phục này.
5. **API QA độc lập (DONE):** test migrations DB mới/cũ, seed idempotent, auth/logout/password/Unicode, IDOR, upload, lỗi/CORS, booking cạnh tranh/rollback/state transitions. Đã chạy SQLite và PostgreSQL 17 cluster tạm; có runner để lặp lại bằng TEST_POSTGRES_URL hoặc tools/test_backend_postgres.py.
6. **Integration có cổng kiểm soát (TODO):** chỉ sau API QA; giải quyết FE-001/FE-002/FE-003 bằng adapter tối thiểu, không đổi CSS/animation. Giữ USE_MOCK=true trong đợt backend; không tuyên bố frontend đã dùng backend thật.
7. **Deployment (TODO):** env/secret riêng, PostgreSQL/TLS/reverse proxy, backup rồi alembic upgrade head, không seed production, payment gateway qua adapter + webhook đã xác minh (không giả lập giao dịch thật).

## Quyết định dữ liệu
- Public homestay id số; host serializers dùng chuỗi ID để không phá so sánh nghiêm ngặt hiện tại. Chỉ có một homestay/booking thật, các serializer là view, không phải bảng mock song song.
- `user` là customer theo frontend; host/admin là role backend đã xác minh.
- Nhiều loại phòng trong một booking phải có BookingLine, không nhét tất cả vào một room_id.
- Room.inventory là số unit vật lý tương đương; RoomNight khóa từng unit từng đêm. FK và unique constraint là lớp bảo vệ cuối cùng, transaction/row lock bảo vệ mọi phép ghi tồn.
- VND nguyên đồng, Numeric(14,0); timestamp UTC; ngày lưu trú theo lịch Asia/Ho_Chi_Minh; checkout không chiếm đêm.
- Hủy pending/confirmed; hoàn toàn bộ nếu trước nhận phòng >=3 ngày, còn lại 0 theo chính sách hiện tại; không tự hoàn tiền qua cổng chưa kết nối. Lưu số tiền phải hoàn và trạng thái yêu cầu.
- Thu hồi token trên server; frontend logout hiện vẫn mock nên được ghi nhận ở FE-001.
