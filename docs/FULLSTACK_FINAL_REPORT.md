# LuxStay — Fullstack final report

14/11/2026. Đã hoàn thành triển khai/kiểm chứng Phase 8, QA Phase 9 và tài liệu bàn giao Phase 10 trong development. Backend Phase 1–7 được tái sử dụng, không viết lại; UI/CSS/animation và carousel 2 giây được giữ. `USE_MOCK=true`; opt-in `?mode=api` đưa customer/host/admin vào cùng DB qua FastAPI.

**BACKEND READY** và **FRONTEND INTEGRATION READY** trong phạm vi local đã kiểm thử. **FULLSTACK DEVELOPMENT READY**. Staging thật chưa được triển khai/xác minh; **PRODUCTION NOT READY**, EXT-001 và các yêu cầu vận hành vẫn mở.

Nguồn dữ liệu API mode: SQLAlchemy/database cho user/homestay/room/blocks/booking/review/payment; frontend không dùng localStorage làm nghiệp vụ song song. Auth JWT có server revocation; guard đọc profile server. Stable idempotency key giữ qua timeout/reload; không thu PAN/CVV hoặc xác nhận paid giả. Admin/host thay đổi DB, customer đọc cùng trạng thái. Schema/migration head **0005_pay_events** không đổi trong integration.

| Bằng chứng mới | Kết quả |
|---|---|
| Backend SQLite + PostgreSQL | 505 pass / 0 fail / 4 skip / 0 xfail |
| Browser API/customer-host-admin | 103 assertion PASS, HTTP/Uvicorn/SQLite tạm |
| Mock UI source cuối | 72 trang/viewport, 244 assertion, 0 overflow/runtime |
| Home/carousel/motion | 684 assertion, 0 overflow/runtime |
| Mock account | 34 assertion PASS |
| HTTP smoke / lint / format / pip check / baseline | PASS |

Không cộng lặp các suite vào tổng backend; không dùng số 493 lịch sử. SQLite skip chỉ dành biến thể row-lock PostgreSQL; biến thể PG chạy pass. Browser E2E chưa chạy trên PostgreSQL hoặc staging đích; backend PG đã chạy concurrency/migrations/API. Không có Playwright/Node trên máy; dùng Chrome/Edge CDP, có screenshot kiểm tra layout. Chưa load test/profiler/pentest độc lập.

Các bug integration/QA đã đóng với regression: fragment selector làm ngắt review, thiếu admin-hosts.json, mock home bỏ sót 6 card, city/location stale sau sửa địa chỉ, legacy DOM sinks và hint upload sai. FE-001..005/QA-001 DONE theo gate development, giữ nguyên mức High; EXT-001 không hạ mức hoặc đóng giả.

Giới hạn: token sessionStorage vẫn có rủi ro XSS; payment/email provider chưa tích hợp; simulation không ngân hàng; occupancy không có inventory history; không settlement/cashflow; pending hold chưa auto-expire; chart CDN và selector quy mô lớn cần xem xét trước deployment. TLS/secret/backup restore/monitoring/deployment/security review là blocker production.

Khởi chạy: migrate DB development theo runbook, seed password ẩn do bạn chọn, chạy Uvicorn, mở **http://127.0.0.1:8000/index.html?mode=api**. Không đổi `USE_MOCK=false`. Xem [README](../README.md), [bàn giao](PHASE_10_DELIVERY.md), [QA](PHASE_9_REVIEW.md), [API contract](API_CONTRACT.md), [database](DATABASE_SCHEMA.md), [runbook](BACKEND_RUNBOOK.md). Manifest file/lý do/hash: [PHASE_8_10_CHANGES.json](PHASE_8_10_CHANGES.json).

Không commit, push, deploy, reset/upgrade hoặc backup/restore database thật trong công việc này.
