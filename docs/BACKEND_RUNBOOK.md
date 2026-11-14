# Chạy và kiểm thử backend LuxStay

## Head và payment simulation

Head hiện tại `0006_host_cancellations`: backup trước, `alembic upgrade head`, kiểm `/api/ready`; startup không tự migrate. 0004 thêm application decision history, 0005 thêm payment audit events/backfill current state, 0006 thêm lịch sử Host tự hủy/quản trị hủy quyền Host. Không reset hoặc seed đè DB cũ. Snapshot legacy không thay được lịch sử giao dịch đã mất.

Dev/test-only: admin active có thể POST `/api/admin/bookings/{id}/payment-simulation` với `{action:"paid"|"refunded",reason:"..."}` và JWT admin. Không gửi amount/status/PAN/CVV. Production từ chối 403 trước khi xử lý payment. Customer/host/anonymous không có quyền; không có public simulate-paid. Retry cùng action trả state cũ, không phát sinh thu/hoàn lần hai. Reference SIM-* và DTO simulated=true phải được hiển thị đúng khi integration; KPI simulated* tách riêng, không trộn vào grossCaptured/paidRevenue/refunded thật.

Đây chỉ là mô phỏng ghi sổ ở database development/test, không thu hoặc hoàn tiền ngân hàng. Không bật ở production, không dùng toast frontend "thanh toán thành công" để chứng minh paid. Chưa có provider/webhook/settlement; các khoản production mới vẫn pending/manual cho tới khi tích hợp được kiểm chứng.

## Phase 5 — idempotency và retention

Replay cùng customer/key/payload được hỗ trợ 24 giờ; key đã quá cửa sổ nhưng còn lưu trả 409. Key không được tự tái sử dụng khi retry timeout. Mốc retention maintenance là 30 ngày, chạy **hằng ngày** bằng Task Scheduler/cron sau khi xác minh database/môi trường và backup. Cutoff 30 ngày nghĩa là key được dọn ở lần maintenance kế tiếp; không có background scheduler tự cài trong ứng dụng.

```powershell
# Mặc định dry-run: chỉ in số lượng, không in key/credentials/body và không ghi DB.
backend/.venv/Scripts/python -m backend.idempotency_cleanup
# Chỉ người vận hành chạy sau khi kiểm tra dry-run trên đúng môi trường.
backend/.venv/Scripts/python -m backend.idempotency_cleanup --apply
```

Cleanup chỉ đặt idempotency_key=null trên booking cũ hơn cutoff, giữ snapshots/status/updated_at/lines/history/payment/ledger. Không reset database, hủy booking hoặc refund. Sau purge, key cũ không còn chống tạo checkout mới; phải đối soát booking gốc khi mạng gián đoạn quá lâu. Chưa cài lịch maintenance vào máy người dùng hoặc chạy cleanup trên DB thật trong đợt này; chức năng đã test với DB tạm. Pending chưa có auto-expiry/hold timeout vì chưa có chính sách được duyệt; không nhầm key TTL với inventory hold TTL.

## Cài đặt (Python 3.12+, từ thư mục gốc repository)

PowerShell:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/Activate.ps1
python -m pip install -r backend/requirements-dev.txt
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
python -m alembic -c backend/alembic.ini upgrade head
python -m backend.seed
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

Linux/macOS: activate bằng `source backend/.venv/bin/activate`, các lệnh Python còn lại giống nhau.

`backend/requirements-lock.txt` ghi closure phiên bản runtime đã kiểm tra trên Python 3.12/Windows. Có thể cài file này trước requirements-dev để tái lập đúng dependency; môi trường triển khai khác cần kiểm tra wheels/marker tương ứng.

`seed` hỏi password bằng getpass, không echo và không ghi password vào log. Password do người vận hành chọn áp dụng cho các tài khoản seed theo email trong `frontend/mock/users.json`; không dùng lại verifier PBKDF2 từ mock. Không seed production. Sau lần đầu, seed không ghi đè account/catalog đã có.

- Swagger: http://127.0.0.1:8000/docs
- Liveness: GET /api/health; readiness/migration: GET /api/ready.
- Development DB mặc định: backend/luxstay.db, tách biệt dev.db cũ.
- Frontend development **vẫn USE_MOCK=true**. Mở `/index.html?mode=api` để nối customer/host/admin; không cờ dùng mock, `/profile.html?accounts=api` là sandbox chỉ tài khoản. Không cần sửa công tắc global. Phiên mock và API tách biệt; user/role thật lấy server.
- Gọi POST /api/auth/login qua Swagger để lấy access_token, chọn Authorize, thử các API theo role. Không gửi mật khẩu/thông tin thẻ vào URL.

## Migration dữ liệu đang có
1. Dừng tác vụ ghi và backup database trước khi thay DATABASE_URL; kiểm tra restore trên bản copy.
2. Dùng đường dẫn SQLite tuyệt đối cho DB cũ để không phụ thuộc cwd. PostgreSQL cấu hình URI `postgresql+psycopg://...`.
3. Revision 0001 nhận diện đúng users/items template (PK, email unique, FK ownership); dữ liệu/schema khác sẽ bị từ chối, không stamp bừa.
4. Revision 0002 chỉ thêm dữ liệu/schema cần thiết; giữ Item cũ và hash cũ. Bcrypt cũ chỉ xác minh mật khẩu <=72 byte, sau login thành công chuyển Argon2id. Không thể khôi phục phần password đã bị template cũ cắt; cần quy trình reset riêng cho các tài khoản đó.
5. Không tự chuyển Item cũ thành Homestay vì thiếu địa chỉ, chủ host đã duyệt và inventory. Chuẩn bị data migration được xác minh cho tập dữ liệu thật đó; không seed đè.
6. `alembic upgrade head`, kiểm tra /api/ready và dữ liệu. Downgrade phá dữ liệu bị chặn; rollback bằng backup đã kiểm chứng.

Phase 4 thêm revision `0003_block_unit`: nullable unit trên room_blocks, CHECK 1–100, null biểu diễn block toàn inventory cũ. Không chỉnh revision 0001/0002. SQLite dùng ALTER ADD COLUMN trực tiếp để tránh rebuild bảng đang được FK tham chiếu; PostgreSQL ADD COLUMN/CHECK trong migration transaction. `/api/ready` và seed CLI yêu cầu head mới; phải backup rồi chạy upgrade trước khi khởi động code mới. Không có thao tác tự migrate/reset ở startup, không tự nâng DB thật trong đợt phát triển này.

## Backup/restore rehearsal trước deployment

Chưa chạy backup/restore trên DB thật trong đợt này. Hướng dẫn dưới đây dành cho người vận hành sau khi xác định đúng môi trường và giữ bản sao nguyên trạng; không thay thế rehearsal đã được kiểm chứng. Không reset/stamp/drop DB thật để giải quyết migration fail.

- SQLite: dừng tác vụ ghi nếu cần snapshot nghiệp vụ ổn định; dùng SQLite Backup API hoặc lệnh `.backup`, không copy riêng file `.db` trong khi bỏ qua WAL đang hoạt động. Mở nguồn bằng URI `mode=ro`, tạo file đích mới không ghi đè; kiểm tra `PRAGMA integrity_check`, revision Alembic và số lượng/quan hệ trên bản sao. Thử restore vào một đường dẫn development/test mới và chạy readiness/API smoke với DATABASE_URL của bản sao; chỉ thay đường dẫn dịch vụ thật theo kế hoạch vận hành sau khi đã kiểm tra.
- PostgreSQL: dùng `pg_dump --format=custom --file=<backup.dump> <database>` với credential từ service/secret manager, không ghi password vào command/source. Tạo database restore test rỗng, ví dụ `luxstay_restore_test`, rồi `pg_restore --exit-on-error --no-owner --dbname=luxstay_restore_test <backup.dump>`. Không dùng `--clean` trên database thật. Xác minh extension/roles, FK/index, revision, counts, readiness, booking/payment history và một giao dịch rollback trên bản restore trước cutover. Lưu checksum, mã hóa/kiểm soát truy cập backup và retention ngoài repository.
- Upgrade: ghi nhận head trước nâng, backup và test restore trước; chạy Alembic một lần trong maintenance/deployment job, kiểm `alembic current`/readiness head `0006_host_cancellations`. Nếu lỗi, ngừng ghi và điều tra trên bản sao; không tự downgrade destructive hoặc seed đè dữ liệu.

Rehearsal môi trường đích, RPO/RTO, retention, offsite backup và giám sát vẫn là gate production chưa thực hiện.

## Automated QA (lệnh)
```powershell
backend/.venv/Scripts/python -m pytest backend/tests -q
backend/.venv/Scripts/python tools/test_backend_postgres.py
backend/.venv/Scripts/python tools/smoke_backend_http.py
```

- SQLite test tạo DB riêng trong backend/.test-tmp, không dùng DB development.
- Script PostgreSQL dùng binaries PostgreSQL 17 sẵn trên máy Windows, init cluster tạm và cổng loopback ngẫu nhiên, không kết nối PostgreSQL service/database cá nhân. `POSTGRES_BIN` đổi thư mục binaries. Authentication trust/fsync off chỉ cho cluster test bị hủy ngay sau chạy; tuyệt đối không dùng cho deployment.
- Nếu đã có DB test riêng: đặt TEST_POSTGRES_URL tới DB có tên kết thúc `_test`, chạy pytest. Mỗi test tạo schema ngẫu nhiên `luxstay_test_*` và chỉ xóa schema do chính fixture tạo.
- HTTP smoke chạy Uvicorn thật, DB/port tạm, thử quote/booking/host/cancel/logout, rồi dừng process tree test. Windows có thể giữ file log tạm vì antivirus/OneDrive; các file trong .test-tmp bị gitignore.
- Kiểm tra lint: `python -m ruff check backend tools/test_backend_postgres.py tools/smoke_backend_http.py --config backend/ruff.toml` (Ruff là công cụ development tùy chọn).
- Snapshot `docs/FRONTEND_BASELINE.json` kiểm tra SHA-256 mọi file frontend và USE_MOCK; nếu frontend được người dùng cập nhật sau này, audit và cập nhật snapshot trong một thay đổi riêng, không bỏ test bảo toàn giao diện để che sai lệch.

## Deployment gate
- APP_ENV=production, PostgreSQL/TLS, JWT_SECRET ngẫu nhiên >=32 bytes từ secret manager; không dùng development secret, trust auth hay seed password.
- `SERVE_FRONTEND=false` mặc định ở production. Chỉ bật sau khi FE-001/FE-002/FE-003 được xử lý trong integration.
- CORS allowlist chính xác; HTTPS/reverse proxy, cấu hình trusted proxy cho IP thật, giới hạn body/rate/concurrency ở edge. API không tin X-Forwarded-For tùy ý.
- Migrate một lần trước rolling deployment, readiness phải pass, backup định kỳ và kiểm tra restore. Server không tự create_all hay migrate.
- Dọn auth_sessions hết hạn và media chưa tham chiếu bằng job có backup/policy; upload hiện là filesystem local, nhiều replica cần storage chung/object storage và quota.
- Payment gateway thật, email verification/reset password, E2E frontend với API thật và load test là các hạng mục riêng chưa được tuyên bố hoàn tất. Không bật mock checkout thành thanh toán thật chỉ bằng đổi config.

## Integration tối thiểu sau backend

Đã hoàn thành adapter development theo Phase 8–10; danh sách công việc bên dưới là checklist lịch sử, kết quả hiện tại đọc `PHASE_8_REVIEW.md`/`PHASE_9_REVIEW.md`/`PHASE_10_DELIVERY.md`.

Chạy same-origin được ưu tiên: `python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000`, mở `http://127.0.0.1:8000/index.html?mode=api`. Không dùng `file://`.

Nếu frontend chạy Live Server/http.server 5500/5501, API_BASE tự dùng cùng hostname:8000. CORS cần chứa chính xác origin frontend (scheme/host/port); .env.example có localhost/127.0.0.1:5500, cổng 5501 phải thêm nếu dùng. Đổi env/CORS cần khởi động lại backend. Deployment URL khác có thể inject `globalThis.LUXSTAY_CONFIG.apiBase` trước ES modules; không đưa token/secret vào cấu hình này hoặc URL.

Kiểm thử browser fullstack:

```powershell
backend/.venv/Scripts/python tests/api-accounts-browser.py
backend/.venv/Scripts/python tests/ui-browser.py --normal-motion --motion-checks --home-checks
backend/.venv/Scripts/python tests/mock-accounts-browser.py
backend/.venv/Scripts/python -m pip check
```

Browser runner dùng Chrome/Edge cài sẵn và CDP, không Playwright/Node. DB/profile/credential ngẫu nhiên riêng; ảnh/report trong `backend/.test-tmp` bị gitignore. Artifact tổng không chứa credential: `docs/PHASE_9_BROWSER_RESULTS.json`. Không chuyển runner tới DB thật. Nếu máy không có browser/PostgreSQL binaries, ghi rõ phần chưa chạy; không giả pass.

API token chỉ sống trong sessionStorage tab, không có refresh cookie. Hết hạn/thu hồi → đăng nhập lại. Đổi password thu hồi mọi phiên; approve host đòi đăng nhập lại. Logout mất mạng giữ token để thử revoke lại; đóng tab chỉ xóa token client, không thay thế server logout/expiry. Không dùng cache role để xử lý authorization.

Thanh toán mặc định pending/manual tại chỗ; simulation admin chỉ test/development, luôn SIM và tách cash KPI. Không có gateway/webhook/email gửi thật. Booking timeout phải đối soát lịch sử hoặc retry intent/key gốc; không xóa intent rồi bấm tạo key mới khi chưa rõ kết quả. Xem retention 24 giờ/30 ngày ở trên.
Đã xử lý FE-001..005 theo bằng chứng browser/API của Phase 8–9. Rollout global USE_MOCK=false là quyết định riêng; hiện route opt-in chạy API đầy đủ và mock mặc định vẫn giữ theo yêu cầu.

## Smoke thủ công sau khởi chạy development

1. Mở `index.html?mode=api`, đăng ký customer; sửa profile/avatar, tải lại rồi logout/login để kiểm tra DB.
2. Customer gửi host application. Dùng phiên admin riêng vào `admin.html?mode=api` duyệt; customer đăng nhập lại để nhận role host từ server.
3. Host tạo homestay/phòng, nhập giá dương/inventory, upload ảnh. Lưu phòng rồi thêm lịch chặn theo unit hoặc tất cả; ngày kết thúc không tính đêm.
4. Customer tìm homestay, chọn ngày/phòng, xem quote và gửi booking; confirmation phải pending/chưa thanh toán, không có ô thẻ. Tải lại history/detail.
5. Host mở bookings để confirm hoặc reject có lý do; customer tải lại thấy cùng trạng thái. Customer hủy pending/confirmed; host tải lại thấy cancelled.
6. Check-in chỉ vào ngày lưu trú hợp lệ; complete chỉ khi đạt ngày checkout. Không sửa clock/DB thật để ép trạng thái. Dùng test runner fixture lịch sử riêng nếu cần kiểm tra ngay. Customer completed mới review và reload rating.
7. Admin khóa host hoặc tạm ngừng homestay; public catalog phản ánh thay đổi, JWT cũ bị revoke theo policy. Mở lại rồi login mới; không coi cache role là quyền.
8. Thử 375/768/1024/1440, modal/toast/errors và carousel 2 giây. Bỏ cờ API để xác nhận mock vẫn độc lập. Payment simulation chỉ qua admin API trong DB dev/test chủ động, không có thanh toán ngân hàng thật.
