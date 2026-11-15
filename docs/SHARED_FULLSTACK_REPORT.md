# Bàn giao chế độ shared Fullstack

Source được audit ngày 2026-11-15. Root cause và mapping nghiệp vụ ở SHARED_DATABASE_AUDIT, hướng dẫn vận hành ở POSTGRESQL_SHARED_SETUP, bằng chứng browser ở SHARED_BROWSER_RESULTS.json.

## Thay đổi

FastAPI phục vụ module `/js/runtime-config.js` với mode và API base công khai, Cache-Control no-store. Khi FRONTEND_MODE=shared, toàn bộ trang dùng API cùng origin kể cả mở trực tiếp URL thiếu query hoặc URL mang cờ mock cũ. Static demo vẫn có module mock riêng. USE_MOCK giữ true để cách mở demo hiện có tiếp tục hoạt động. Không xóa hoặc import dữ liệu localStorage của người dùng.

Các adapter catalog, profile, Host application, admin, phòng, availability, booking, payment, review và dashboard hiện có được tái sử dụng. Không thay SQLAlchemy models, migration, booking engine hoặc auth backend. Shared frontend dùng sessionStorage cho phiên và intent retry, backend quyết định quyền, giá và tồn phòng.

Thêm CLI bootstrap admin đầu tiên có nhập password ẩn, kiểm tra revision/email/admin hiện có và khóa PostgreSQL khi chạy đồng thời. Production từ chối phục vụ frontend ở mock mode. Error state lịch sử booking được sửa để thay skeleton bằng thông báo thử lại khi API lỗi. Thông báo nguồn dữ liệu tài khoản khớp chế độ shared.

## File đã thay đổi

| File | Lý do |
|---|---|
| backend/config.py, backend/.env.example | FRONTEND_MODE, validation và cấu hình mẫu |
| backend/main.py | Public runtime config cùng origin |
| backend/bootstrap_admin.py | Tạo admin đầu tiên chủ động, không seed catalog |
| frontend/js/runtime-config.js, frontend/js/config.js | Static mock tách khỏi shared API do server cấu hình |
| frontend/js/auth.js | Thông báo đúng nguồn dữ liệu shared, giữ phiên API hiện có |
| frontend/js/pages/booking-list.js, frontend/js/ui.js | Error state API có retry, hỗ trợ trang thiếu template empty |
| backend/tests/test_shared_deployment.py | Test runtime config, validation, bootstrap không ghi đè |
| backend/tests/test_search.py, backend/tests/test_phase_1_3_review.py | Tách fixture tìm kiếm khỏi số điện thoại trùng từ khóa và kiểm chứng cả trạng thái DB trong race approve/apply |
| tests/shared-postgres-browser.py | Hai browser context dùng một PostgreSQL test và backend thật |
| tools/test_backend_postgres.py | Tùy chọn chạy shared browser với cluster test tạm |
| tests/ui-browser.py, tests/mock-accounts-browser.py | Cập nhật thao tác test theo lịch bất đồng bộ và workflow Host hiện tại |
| docs/FRONTEND_BASELINE.json, docs/FRONTEND_BASELINE_PRE_SHARED.json | Đối chiếu latest frontend và lưu snapshot cũ, giữ assertion SHA-256 |
| README.md, docs/BACKEND_RUNBOOK.md | Cách mở cùng website và các lệnh vận hành mới |
| Bốn tài liệu SHARED_DATABASE_AUDIT, POSTGRESQL_SHARED_SETUP, MULTI_DEVICE_SYNC_TEST, SHARED_FULLSTACK_REPORT và SHARED_BROWSER_RESULTS.json | Nguyên nhân, cấu hình, bằng chứng và giới hạn |

Không thay HTML, CSS, typography, carousel, animation, modal hoặc layout. Không tạo schema migration mới. Không thao tác database thật, deploy, commit hoặc push.

## Kiểm thử và readiness

| Trạng thái | Kết quả |
|---|---|
| CODE READY | ĐẠT trong phạm vi shared configuration và kiểm thử đã nêu |
| LOCAL SHARED BACKEND TESTED | ĐẠT, Uvicorn và PostgreSQL test ở localhost |
| POSTGRESQL MULTI-SESSION TESTED | ĐẠT, 30 assertion trong hai Chrome context riêng |
| LAN MULTI-DEVICE TESTED | CHƯA KIỂM CHỨNG |
| INTERNET STAGING VERIFIED | CHƯA KIỂM CHỨNG |
| PRODUCTION READY | CHƯA ĐẠT |

UI smoke đã chạy 72 tổ hợp và 240 assertion, 0 overflow/runtime error. Mock account browser đạt 44 assertion. PostgreSQL multi-session browser đạt 30 assertion. Pip check và Ruff đã chạy thành công. Backend suite SQLite/PostgreSQL cuối đạt 548 pass, 0 fail, 4 skip, 0 xfail trong 915.33 giây. Bốn skip dành cho row-lock PostgreSQL ở fixture SQLite, các bản PostgreSQL đã chạy. Các fail của lần chạy đầu, nguyên nhân và điều chỉnh fixture/assertion được ghi trong MULTI_DEVICE_SYNC_TEST.

Head Alembic thực tế là 0007_booking_holds. Suite kiểm tra migrate database sạch, nâng legacy giữ dữ liệu, metadata/model consistency, foreign keys, room-night uniqueness và concurrency/idempotency. Shared browser migrate PostgreSQL test, kiểm readiness, đối chiếu ledger và restart backend giữ dữ liệu. Database thật chưa được migrate hoặc chạy backup/restore trong phiên này.

## Việc người vận hành cần hoàn thành

- Cấp một server, PostgreSQL, DATABASE_URL và JWT_SECRET được bảo vệ, storage upload bền vững. Xác minh mọi backend process dùng cùng nguồn PostgreSQL và secret.
- Backup/restore rehearsal nếu có dữ liệu, chủ động chạy migration, bootstrap admin nếu chưa có admin. Không seed hoặc import mock tự động.
- LAN dùng địa chỉ mạng server và firewall phù hợp. Staging dùng domain, TLS và reverse proxy cùng origin. Chạy lại checklist hai máy thật và lưu bằng chứng.
- Chốt giám sát, backup ngoài server, restart/update, kiểm tra tải và giới hạn ở proxy. Payment provider và email verification/reset vẫn là hạng mục riêng.

## Vấn đề còn lại

Website mở từ static server riêng vẫn là demo theo thiết kế. Muốn dữ liệu chung phải truy cập shared server đã cấu hình, hoặc reverse proxy đúng runtime module/API/upload. Không có cơ chế biến tài khoản mock cục bộ thành tài khoản PostgreSQL. Account trùng và booking cũ cần quy trình import có kiểm soát. Không có server/domain/tài khoản dịch vụ đích trong phiên này, vì vậy chưa có URL Internet để bàn giao.

## Sửa lịch sử đặt phòng sau phản hồi người dùng

URL người dùng cung cấp là `http://127.0.0.1:5500/frontend/booking-list.html`, đang dùng static Mock Mode. Đã tái hiện checkout thật trong Chrome profile riêng, cùng tiền tố `/frontend/`, trên HTTP server test với cổng tạm. Live Server cổng 5500 chưa truy cập được từ process kiểm tra, nên không tuyên bố đã đọc dữ liệu trình duyệt cá nhân của người dùng.

Phát hiện chính nằm trong migration đầu module api.js. Khi mock_version thay đổi, code cũ xóa customerBookings có ID 1–4 và userId=1, đồng thời xóa host booking dựa trên roomId. Các ID này cũng được cấp cho đơn khách đặt thật. Regression test đã tái hiện đơn của Huy biến mất sau đổi version dù checkout và reload bình thường vẫn thành công.

Đã sửa các phần sau

- `frontend/js/api.js` tăng MOCK_DATA_VERSION, bỏ việc suy luận dữ liệu mẫu bằng ID để xóa lịch sử, hỗ trợ cache dạng mảng và hai wrapper customerBookings/bookings cũ. Cache sai cú pháp trả lỗi có thể xử lý, giữ nguyên dữ liệu để sao lưu. ID/userId/status của booking lấy từ phiên và hệ thống, giữ quyền đọc/hủy theo chủ sở hữu.
- `frontend/js/pages/booking-list.js` chỉ render response mới nhất khi đổi bộ lọc nhanh, reload khi quay lại bằng browser back-forward cache. Tab trạng thái rỗng có thông báo riêng và nút quay về Tất cả.
- `tests/booking-history-browser.py` bổ sung checkout thật → confirmation → history, kiểm tra visibility, reload, nâng version, hai dạng cache cũ, đổi tài khoản, chống giả owner và retry cache hỏng.
- `tests/shared-postgres-browser.py` bổ sung đo visibility thật và mô phỏng response bộ lọc về sai thứ tự. Test cũ chỉ kiểm tra row tồn tại trong DOM nên chưa bao phủ đầy đủ các tình huống này.
- `docs/FRONTEND_BASELINE.json` cập nhật checksum đúng hai file JavaScript được sửa, giữ nguyên assertion SHA-256 và giao diện hiện tại.

Kết quả chạy trong lượt sửa này gồm 17 assertion lịch sử Mock PASS, 32 assertion shared PostgreSQL PASS, 44 assertion tài khoản Mock PASS và UI smoke 72 tổ hợp/240 assertion PASS với 0 overflow/runtime error. Regression backend liên quan booking/shared configuration và snapshot đạt 37 pass. Bộ backend đầy đủ 548 pass/4 skip phía trên là kết quả của lượt bàn giao shared trước đó. Lượt sửa lịch sử này chỉ chỉnh frontend và chạy thêm regression backend có liên quan.

Các đơn đã bị code cũ xóa khỏi localStorage không thể khôi phục tự động nếu không còn bản sao. Bản sửa bảo toàn bản ghi đang còn và đơn mới. Không xóa/reset localStorage cá nhân để xử lý. Lịch sử ở Mock Mode và PostgreSQL vẫn là hai nguồn tách biệt theo cấu hình, truy cập shared server để đọc lịch sử backend.
