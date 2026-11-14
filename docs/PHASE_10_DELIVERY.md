# Phase 10 — Bàn giao LuxStay

Ngày 14/11/2026. Bàn giao development, không deploy/commit/push, không tác động DB thật. Phase 8 đạt gate trước Phase 9; Phase 9 đạt gate trước tài liệu Phase 10. Source mới nhất và bằng chứng trong `PHASE_8_REVIEW.md`, `PHASE_9_REVIEW.md` là cơ sở, không lấy 493 test lịch sử thay kết quả mới.

| Phạm vi | Kết luận |
|---|---|
| Backend Phase 1–7 + adapter báo cáo | BACKEND READY cho development/API đã kiểm thử |
| Frontend/API customer/host/admin | FRONTEND INTEGRATION READY qua route opt-in |
| Fullstack local development | READY, browser dùng HTTP/Uvicorn và DB thật riêng |
| Staging thật | Chưa deploy/xác minh; cần chạy QA và cấu hình riêng trên môi trường đích |
| Production | NOT READY |

## Khởi chạy

Từ root, Python 3.12+, cài `backend/requirements-dev.txt` trong venv. Copy `.env.example` nếu chưa có `.env`, xác định DATABASE_URL trỏ đúng DB development; không dùng script test/reset cho DB có dữ liệu. Development mặc định `backend/luxstay.db`, tách `dev.db` cũ. Đọc kế hoạch backup/upgrade trong runbook trước nâng DB cũ.

```powershell
backend/.venv/Scripts/Activate.ps1
python -m alembic -c backend/alembic.ini upgrade head
python -m backend.seed
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Seed hỏi password ẩn do người chạy chọn, chỉ development; không overwrite DB có dữ liệu. Email customer/host/admin lần lượt `huy@test.com`, `host@test.com`, `admin@test.com`. Không có password backend mặc định. Mở **http://127.0.0.1:8000/index.html?mode=api**. Bỏ cờ để dùng mock; `?accounts=api` chỉ sandbox tài khoản. `USE_MOCK=true` cố ý giữ, không cần đổi false để chạy API. Swagger `/docs`, OpenAPI `/openapi.json`, health `/api/health`, readiness `/api/ready`.

Live Server/http.server cổng 5500/5501 dùng cùng hostname backend:8000; CORS phải đúng origin và restart backend sau đổi env. Reverse proxy/API khác inject cấu hình API_BASE không bí mật trước ES modules. Không hardcode production URL/secret vào source; xem README/runbook.

## Chức năng và API thật

| Nhóm | API / hành vi |
|---|---|
| Tài khoản | auth/register, auth/login, me/profile GET/PATCH/PUT, me/password, auth/logout, uploads; JWT/session revoke và server role |
| Đăng ký host | host/apply, me/host-application; admin/host-applications + approve/reject; customer pending, login lại sau duyệt |
| Catalog | items list/detail/availability/reviews; filter/page/sort và RoomTypes DB, không tự sinh phòng/rating |
| Booking | bookings/quote, me/bookings list/create/detail/cancel, Idempotency-Key, server price/snapshot/ledger |
| Host | homestays/rooms CRUD, structured blocks CRUD unit/null/range, bookings/status, dashboard SQL |
| Admin | overview SQL/period, hosts, users filter/page/sort + lock/unlock, homestays moderation |
| Review/payment | review completed một lần và rating DB; customer payment status chỉ đọc; admin simulation API dev/test riêng, không ngân hàng |

Contract đầy đủ có method/body/permissions/errors/pagination ở `API_CONTRACT.md` và OpenAPI từ router thật. Integration chỉ bổ sung `admin.overview.period` và `host.dashboard.occupancySummary` trên endpoint hiện hữu; không thêm bảng/migration. **Head 0005_pay_events**.

## Xác minh

- Backend suite kép: **505 PASS / 0 FAIL / 4 SKIP / 0 XFAIL** = 258 SQLite + 247 PostgreSQL. SQLite riêng lặp lại 258 pass/4 skip, không cộng thành 763 test độc lập.
- Browser API: **103 assertion PASS**, Chrome/Edge + CDP, 375/768/1024/1440; cùng SQLite migrated, DB fixture độc lập. Có cross-role, lost response/reload/idempotency, price snapshot, blocks, review, revoke/lock/moderation/payment labels.
- Mock source cuối: **244 assertion**, 72 tổ hợp trang/viewport, 0 overflow/runtime. Chuyên sâu home/motion: **684 assertion**, cùng 72 tổ hợp; mock account: **34 assertion**. Không cộng các bộ lặp thành số test backend.
- HTTP Uvicorn smoke, Ruff check/format, pip consistency PASS. Exact frontend hash baseline + USE_MOCK assertion PASS; baseline Phase 7 lưu riêng, không làm yếu test.
- Migration/legacy upgrades/backfill/seed/metadata/concurrency kiểm trong test SQLite/PostgreSQL tạm; không migrate/backup/restore DB thật. Bốn skip thuộc SQLite tests dành riêng PostgreSQL.

Các lệnh tái chạy ở README và runbook. Browser script cần Chrome/Edge và venv dependencies; không cần Playwright/Node. PostgreSQL runner cần binaries 17/POSTGRES_BIN hoặc database `_test` riêng; không có môi trường thì ghi chưa chạy. Artifact không credential: `PHASE_9_BROWSER_RESULTS.json`; screenshot/report máy test trong thư mục gitignored `.test-tmp`/Temp.

## Bảo mật và giới hạn

Backend quyết định quyền/ownership, input validation, password hash/JWT/session; UI role cache không cấp quyền. Bearer sessionStorage riêng giúp không lẫn mock, nhưng JavaScript cùng origin vẫn có thể đọc token nếu có XSS mới. DOM/URL sinks trong phạm vi đã harden; chưa pentest độc lập hoặc cookie/CSRF architecture. Không lưu/log password thô, không PAN/CVV, không tạo production credential.

KPI giá trị booking/cash/SIM tách biệt. Cash là trạng thái hiện tại của cohort booking, không phải settlement/cashflow/lợi nhuận; occupancy dùng tồn kho hiện tại, thiếu lịch sử. Biểu đồ occupancy tối đa 100 homestay, KPI tổng không bị projection cắt. Host selector đọc các trang sở hữu; quy mô rất lớn cần UX paging/search riêng. CDN Chart.js cần mạng, có fallback; chưa benchmark FPS/memory/load production.

Checkout intent giữ key/payload trong sessionStorage để retry, không phải nguồn booking canonical. Server replay 24 giờ; key còn lưu hết hạn trả 409, cleanup cutoff 30 ngày. Không xóa intent/tạo key mới khi chưa rõ kết quả; đối soát lịch sử. Chưa có chính sách auto-expiry pending inventory hold.

## Blocker production / ngoài phạm vi

EXT-001 giữ High và mở: gateway/provider, webhook có chữ ký, settlement/refund thật, email/khôi phục tài khoản theo chính sách chưa có. Chưa deploy staging/production, TLS/proxy/CORS/secret manager/hardening edge, backup/restore rehearsal, monitoring/alerting/CI và load/security review thực tế. Không coi payment simulation là thanh toán thật. Không flip global mock hoặc seed production để thay thế các bước này.

Danh sách file mới/sửa và lý do: `PHASE_8_10_CHANGES.json`; nhóm thay đổi giải thích trong `PHASE_8_REVIEW.md`. CSS, motion.js, charts.js, ảnh/mock JSON và host-homestay-form.html không đổi so với snapshot đầu integration. HTML chỉ sửa booking-page loại PAN/CVV và admin tách mock handler; các control nghiệp vụ thêm dùng class hiện có.
