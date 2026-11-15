# Đưa LuxStay lên Internet để cả nhóm dùng chung dữ liệu

Cập nhật ngày 2026-11-15 theo source hiện tại và tài liệu nhà cung cấp. Cấu hình đã được chuẩn bị trong repository. Chưa tạo dịch vụ, deploy, chạy migration trên cloud hoặc phát sinh chi phí.

## Chọn phương án

Khuyến nghị cho nhóm là Render với một web service Docker phục vụ cả frontend/FastAPI, một Render Postgres 17 và một persistent disk lưu ảnh. Mọi thành viên mở cùng HTTPS URL. Các đường dẫn `/api`, `/uploads` và `/js/runtime-config.js` ở cùng origin, giảm việc cấu hình CORS và giữ mode khi điều hướng. Đây là lựa chọn triển khai, giao diện hiện có được giữ nguyên.

Render web Starter tương đương `0.5c-512mb` khoảng 7 USD/tháng, Postgres nhỏ nhất trả phí `0.1c-256mb` khoảng 6 USD/tháng. Cần cộng persistent disk và các khoản usage theo dashboard. Chi phí compute cơ bản khoảng 13 USD/tháng, cần kiểm tra tổng tiền trước khi tạo. Free Postgres hết hạn sau 30 ngày và free web không có persistent disk hoặc Shell/pre-deploy cần cho quy trình này. [Giá Render](https://render.com/pricing), [giới hạn free](https://render.com/docs/free), [disk](https://render.com/docs/disks).

Railway là phương án thay thế dùng Dockerfile và railway.toml đã chuẩn bị. Hobby có mức tối thiểu 5 USD/tháng, bao gồm 5 USD usage, tổng thực tế có thể cao hơn khi cộng app/Postgres/volume. Bật cảnh báo ngân sách, đọc giá trong dashboard. Hai service này cần volume riêng cho PostgreSQL và upload. [Giá Railway](https://railway.com/pricing), [volume](https://docs.railway.com/volumes/reference).

Railway đã công bố báo cáo sự cố bảo mật tháng 10/2026 và biện pháp khắc phục. Đọc thông tin chính thức trước khi lựa chọn, đặc biệt nếu đã có account/secret trên nền tảng từ trước sự cố. [Báo cáo Railway](https://blog.railway.com/p/incident-report-october-security-incident).

## 1. Chuẩn bị bản source sẽ triển khai

1. Review thay đổi local, đặc biệt Dockerfile, `.dockerignore`, `render.yaml`, `railway.toml`. Các file này chưa tự được đưa lên GitHub bởi assistant.
2. Khi bạn chủ động quyết định phát hành, bảo đảm branch/commit trên remote đã chứa cấu hình và source đã review. Render/Railway deploy từ GitHub chỉ đọc commit trên remote. Thư mục đang sửa trong VS Code không tự xuất hiện trên cloud.
3. Dùng repository này, giữ root directory ở gốc repo. Đặt root thành `backend` sẽ làm thiếu frontend trong Docker build context.
4. Không đưa backend/.env, `.local-secret`, database local, token hoặc upload cá nhân lên repository. `.dockerignore` loại chúng khỏi build context, đồng thời loại frontend/mock và các test fixtures khỏi image.

Docker image dùng Python 3.12 và runtime dependencies từ backend/requirements.txt. Defaults công khai là APP_ENV=production, FRONTEND_MODE=shared, SERVE_FRONTEND=true. Thiếu secret/PostgreSQL sẽ làm cấu hình production bị từ chối. Container bind cổng PORT do nền tảng cấp. Một instance được dùng để ảnh upload nằm trên một volume.

## 2. Tạo Render PostgreSQL

1. Đăng nhập Render, kiểm tra workspace và billing của người chịu trách nhiệm.
2. Chọn New → PostgreSQL. Tên ví dụ `luxstay-db`, region Singapore, PostgreSQL 17, database `luxstay`, user `luxstay_app`.
3. Chọn plan trả phí nhỏ nhất phù hợp sau khi xem phí. Không chọn database free nếu cần lưu dữ liệu nhóm sau 30 ngày.
4. Đợi database Available. Lưu Internal Database URL trong khu vực bí mật của dashboard, không đưa vào file source hoặc gửi qua chat.
5. App và database phải ở cùng region. Giới hạn external access; backend dùng private/internal connection. Không mở PostgreSQL cho browser hoặc toàn Internet. Với database đang có dữ liệu, tạo backup và kiểm tra khả năng restore trước migration.

Nếu dùng Blueprint ở bước tiếp theo, Render sẽ đề xuất tạo database theo render.yaml. Chọn một cách tạo và đối chiếu tên để tránh tạo hai database ngoài ý muốn. Đối với database đã có, dùng URL bí mật của chính database đó trong web service, không tạo DB thứ hai để thay thế dữ liệu.

## 3. Tạo Render web service

**Cách dùng Blueprint cho môi trường mới**

1. Chọn New → Blueprint, kết nối GitHub repo và chọn branch/commit đã review.
2. Render đọc render.yaml. Kiểm tra đúng một web service, một PostgreSQL và disk upload 1 GB. Blueprint này chứa tài nguyên trả phí, chỉ bấm tạo khi đã đồng ý mức phí.
3. JWT_SECRET được Render sinh qua generateValue, DATABASE_URL lấy từ private connection của database cùng Blueprint. Không chụp hoặc công khai các giá trị này.
4. Auto deploy đặt off để bạn chủ động deploy bản code đã review. Nền tảng chỉ thực thi migration khi bạn chủ động triển khai.

**Cách cấu hình thủ công nếu đã tạo database**

1. Chọn New → Web Service, repo của LuxStay, region trùng DB, runtime Docker.
2. Root directory để trống/gốc repository. Dockerfile Path là `./Dockerfile`, Docker Context là `.`. Chọn web compute phù hợp, một instance.
3. Gắn persistent disk 1 GB tại `/var/data`. App dùng `/var/data/uploads`. Không lưu ảnh ở filesystem tạm mặc định.
4. Đặt health check path `/api/ready`.
5. Pre-deploy command đặt `python -m alembic -c backend/alembic.ini upgrade head`.
6. Start command giữ CMD trong Dockerfile, không thêm migration/seed/bootstrap vào start command.
7. Thêm environment variables ở phần tiếp theo rồi mới deploy. [Blueprint reference](https://render.com/docs/blueprint-spec), [deploy lifecycle](https://render.com/docs/deploys).

## 4. Environment variables của app

| Biến | Giá trị |
|---|---|
| APP_ENV | production |
| FRONTEND_MODE | shared |
| SERVE_FRONTEND | true |
| DATABASE_URL | Internal Database URL của PostgreSQL, nhập bằng dashboard hoặc fromDatabase |
| JWT_SECRET | Secret ngẫu nhiên ít nhất 32 byte, giữ ổn định khi restart |
| UPLOAD_DIR | /var/data/uploads |
| CORS_ORIGINS | Ban đầu có thể để chuỗi rỗng cho same-origin; sau khi có domain đặt đúng origin HTTPS, không thêm path hoặc dấu / cuối |
| JWT_EXPIRE_MINUTES | 60, nếu cần thay thì tuân validation trong backend/config.py |
| AUTH_RATE_LIMIT | 20 mặc định; xem xét theo test thực tế và cấu hình rate limiting tại edge |

Có thể tự sinh JWT_SECRET bằng Python trên máy riêng rồi lưu trực tiếp trong dashboard

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Đây là thao tác người vận hành thực hiện. Không paste kết quả vào source/chat/log chung. Không tạo JWT secret mới ở mỗi lần deploy. Không dùng bí mật mặc định hoặc token của account mock. Với Blueprint, dùng secret đã được generateValue tạo.

PORT do provider cấp, Dockerfile đọc giá trị đó. FORWARDED_ALLOW_IPS chỉ nên được cấp bằng danh sách proxy tin cậy đã xác minh. Mặc định giữ loopback, không tự trust mọi X-Forwarded-For từ Internet. Rate limiter hiện nằm trong process, cần kiểm tra giới hạn IP thực tế phía proxy trước khi gọi đây là production-ready.

## 5. Chạy Alembic migration có kiểm soát

Head trong source đã kiểm tra là `0007_booking_holds`. Đối chiếu lại source khi nâng phiên bản.

```bash
python -m alembic -c backend/alembic.ini heads
python -m alembic -c backend/alembic.ini current
python -m alembic -c backend/alembic.ini upgrade head
```

Pre-deploy command đã chứa lệnh upgrade, chạy trong môi trường có DATABASE_URL của service và chặn deploy nếu thất bại. Bạn phải kiểm tra đúng database, backup và review migration trước khi bấm deploy. Nó không chạy seed. Pre-deploy tách khỏi container runtime và không cần disk upload. Nếu service đã chạy và cần thao tác thủ công, mở service → Shell, chạy các lệnh trên với đúng biến của server. Không đưa password vào đối số shell.

Database trống sẽ được tạo schema, catalog và booking vẫn trống. Database có dữ liệu được upgrade qua migrations hiện có. Không DROP, truncate, reset, stamp giả hoặc đổi sang DB mới để né migration fail. Giữ service cũ/backup và điều tra trên bản sao nếu có lỗi.

## 6. Tạo admin đầu tiên

Sau migration, mở Shell của web service và chạy

```bash
python -m backend.bootstrap_admin
```

Nhập email/tên, nhập password hai lần bằng getpass. Password không hiện trên màn hình. CLI kiểm tra migration head, từ chối nếu đã có admin hoặc email đã tồn tại. Chỉ tạo admin, không tạo account demo/homestay/booking. Bảo vệ account admin và chia sẻ quyền quản trị theo chính sách nhóm.

Sau đó đăng ký customer qua website, gửi đơn Host thật từ profile, admin duyệt, Host đăng nhập lại rồi tạo homestay/phòng thật. Một account Host mới có dashboard rỗng là kết quả đúng. Các tài khoản local mock như huy@test.com không tự trở thành account server.

## 7. Lấy public URL và mở trên các máy

1. Khi deploy thành công, sao chép URL HTTPS hiển thị trong Render service, dạng `https://<ten-service>.onrender.com`.
2. Mở `/api/health`, cần trả status ok. Mở `/api/ready`, cần trả ready và revision `0007_booking_holds`.
3. Mở `/js/runtime-config.js`, chỉ có mode shared và apiBase `/api`. Không được có DATABASE_URL/JWT_SECRET trong response.
4. Mở `/index.html`. Tất cả thành viên dùng cùng URL này. Không mở Live Server 127.0.0.1:5500 để kiểm thử đồng bộ Internet.
5. Đặt CORS_ORIGINS thành origin HTTPS thực tế nếu dùng allowlist đó, ví dụ URL service vừa nhận, rồi triển khai thay đổi cấu hình có chủ đích. Same-origin hiện không cần cross-origin permission.
6. Thử truy cập bằng mạng di động và máy khác. Chỉ sau bước này mới đánh dấu Internet staging verified.

Frontend được FastAPI phục vụ ở root, vì vậy URL cloud là `/booking-list.html`, không có tiền tố `/frontend/`. Không cần `?mode=api` khi FRONTEND_MODE=shared. Không cần sửa USE_MOCK hoặc hardcode URL API vào frontend. [FastAPI trên Render](https://render.com/docs/deploy-fastapi).

## 8. Checklist test chéo máy với dữ liệu thật trên staging

1. Máy A mở URL cloud, đăng ký một email test. Máy B mở cùng URL, đăng nhập email đó, thấy cùng profile.
2. Customer A gửi đơn Host. Admin ở phiên riêng thấy đơn pending trong DB, approve. Customer đăng nhập lại thành Host, ban đầu chưa có homestay.
3. Host tạo homestay và phòng có giá/inventory hợp lệ, upload ảnh thật lên disk staging. Máy B tìm thấy homestay công khai.
4. Customer đặt phòng. Xem confirmation và booking history. Cùng customer trên máy B reload, phải thấy cùng booking code, giá, ngày và trạng thái.
5. Host mở danh sách khách đặt, thấy cùng đơn. Đến ngày nhận phòng hợp lệ, Host nhận phòng/hoàn tất, Customer refresh thấy thay đổi. Engine hiện tại tạo confirmed ngay, payment vẫn pending/manual.
6. Hủy một đơn còn đủ điều kiện, đối chiếu Host refresh. Thử Host khác và customer khác, không được xem/hủy/sửa tài nguyên của nhau.
7. Redeploy/restart có chủ đích. Account/booking vẫn có trong PostgreSQL, ảnh vẫn nằm trên persistent disk. Xác minh thêm lỗi API không hiện dữ liệu mock.
8. Ghi nhận public origin, thời điểm, revision, mã booking thử và kết quả hai máy, tránh ghi password/token/connection string. Đây là checklist chưa được thực hiện trên cloud trong lượt chuẩn bị này.

## 9. Railway thay cho Render

1. Tạo project mới trong Railway, xem billing/usage trước khi xác nhận tạo tài nguyên. Thêm PostgreSQL trong cùng project/environment. Kiểm tra volume PostgreSQL bền vững và cơ chế backup.
2. Thêm service từ GitHub repo đã review, root directory là gốc repo. railway.toml chọn Dockerfile hiện tại. Kiểm tra thiết lập auto-deploy của service và chọn triển khai thủ công nếu muốn review từng lần như cấu hình Render. Không tạo project FastAPI từ template chứa auth/schema khác.
3. App Variables đặt APP_ENV=production, FRONTEND_MODE=shared, SERVE_FRONTEND=true, JWT_SECRET riêng và UPLOAD_DIR=/var/data/uploads. DATABASE_URL dùng reference `${{Postgres.DATABASE_URL}}` nếu tên service DB là Postgres. Chọn biến private/internal của service thật nếu bạn đã đổi tên. Không dùng URL database ở browser.
4. Gắn volume riêng cho app tại `/var/data`, giữ một replica. Đây là volume upload, tách với volume của PostgreSQL.
5. railway.toml chứa preDeployCommand Alembic và healthcheck `/api/ready`. Kiểm tra biến/region/private networking, review migration và backup trước khi deploy. Migrations không ghi vào upload volume.
6. Sau deploy, service Settings → Networking → Generate Domain. Dùng HTTPS domain được cấp và port PORT của ứng dụng. Đặt CORS_ORIGINS theo domain thực nếu cần.
7. Mở Shell/SSH vào đúng app service, chạy `python -m backend.bootstrap_admin`. Có thể dùng Railway CLI đã đăng nhập, link đúng project/environment/service, rồi `railway ssh` để mở shell và nhập password ẩn. `railway run` chạy ở máy local, có thể không truy cập được private DB hostname nên không dùng thay bước SSH này.
8. Thực hiện checklist chéo máy ở trên. Bật cảnh báo chi phí và backup. Không bật public TCP proxy PostgreSQL chỉ để browser truy cập website. [FastAPI](https://railway.com/guides/fastapi), [variables](https://docs.railway.com/variables), [private networking](https://docs.railway.com/platform/best-practices), [pre-deploy](https://docs.railway.com/deployments/pre-deploy-command), [SSH](https://docs.railway.com/cli/ssh).

## 10. Backup, cập nhật và xử lý lỗi

- Trước nâng code/migration, tạo backup PostgreSQL bằng công cụ của provider, xác minh revision và thử restore vào DB riêng. Sao lưu upload disk riêng. Xem BACKEND_RUNBOOK và POSTGRESQL_SHARED_SETUP cho quy trình restore.
- Lưu backup ngoài service, kiểm soát quyền đọc và chọn retention theo nhu cầu nhóm. Không đặt backup trong frontend hoặc Git. Thử restore thực tế trước khi tin rằng dữ liệu có thể khôi phục.
- Cập nhật code đã review, chủ động deploy, theo dõi pre-deploy rồi kiểm ready. Không thay DATABASE_URL sang DB rỗng hoặc seed để làm một màn hình có dữ liệu.
- Nếu lỗi ModuleNotFoundError backend hoặc thiếu frontend, kiểm tra root/build context và Dockerfile. Nếu 503 ready, kiểm tra migration và kết nối đúng PostgreSQL. Nếu thiếu ảnh sau restart, kiểm tra UPLOAD_DIR và volume mount. Nếu app fail ngay do config, kiểm tra production secret, Postgres URL và FRONTEND_MODE.
- Nếu lịch sử trống, đối chiếu public URL, account đang đăng nhập, Network GET `/api/me/bookings` và DB của service. Đừng dùng cache local làm fallback.
- Không gửi DATABASE_URL, JWT_SECRET, password hoặc token cho assistant. Có thể gửi public URL, HTTP status và thông báo lỗi đã loại dữ liệu nhạy cảm để rà soát tiếp.

## Phạm vi xác minh

Local PostgreSQL multi-session đã kiểm tra trong SHARED_BROWSER_RESULTS.json. Docker build, provider Blueprint validation, migration cloud, domain/TLS, dữ liệu hai máy Internet và backup/restore đích cần được xác minh khi người vận hành thực hiện. Không có public URL đã được tạo trong lượt này. Payment gateway, xác minh email/reset password, edge rate limiting và load test vẫn là các gate riêng trước production.
