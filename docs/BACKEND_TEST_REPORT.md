# Kết quả kiểm thử backend — 14/11/2026

## Kết quả mới nhất Phase 8–10

Full suite hiện tại: SQLite riêng **258 pass/4 skip**, SQLite + PostgreSQL cluster tạm **505 pass/4 skip/0 fail/0 xfail**; HTTP smoke/lint/format/pip check PASS. Browser API hiện **103 assertion**, mock UI 72 tổ hợp/244 assertion và home/motion 684 assertion, mock accounts 34 assertion. Xem `PHASE_9_REVIEW.md` để phân biệt backend tests và browser assertions, fixture, skip và giới hạn chưa kiểm chứng.

Baseline hiện có 69 file frontend; Phase 7 66 file đã lưu `FRONTEND_BASELINE_PHASE7.json`. CSS/motion/ảnh/mock JSON/host-homestay-form.html giữ hash, adapter/renderer đổi có chủ đích theo Phase 8. Các mục "không sửa frontend/chưa E2E" ở bên dưới là báo cáo lịch sử trước integration, không phải kết luận source hiện tại.

## Source và phạm vi
- Audit source đang có trong repository; `docs/FRONTEND_BASELINE.json` ghi SHA-256 66 file frontend. Không sửa bất kỳ HTML/CSS/JavaScript/mock frontend nào; `USE_MOCK = true` vẫn nguyên vẹn.
- Backend đã có catalog/availability/quote, auth/profile/password/logout, host applications/admin review, booking nhiều phòng, inventory/block, review đủ điều kiện, dashboard và upload.
- Đây là QA backend độc lập, **không phải** xác nhận frontend đã tích hợp Fullstack hoặc cổng thanh toán đã hoạt động.

## Kết quả thực tế
| Kiểm tra | Kết quả |
|---|---|
| Full API/migration suite trên SQLite và PostgreSQL 17 cô lập | **185 passed**, 172,03 giây |
| Coverage backend runtime, bỏ test/venv khỏi mẫu số | **93%**, 1.543 statements, 104 chưa chạy |
| Bổ sung database cũ không có Alembic version + homestay không có room active, cả hai engine | **4 passed**, 183 deselected, 3,30 giây; 2 ca migration chạy lại, 2 ca giá nullable mới |
| HTTP thật: Uvicorn + SQLite riêng | PASS: register/login, catalog, quote, tạo booking, host xác nhận, khách hủy, logout/token revoked, host không truy cập admin |
| Frontend baseline | PASS: 66/66 file giữ nguyên byte/hash và mock flag |
| Alembic metadata | PASS cả SQLite/PostgreSQL; không drift models/migrations |
| Python syntax / Ruff | PASS |
| pip check trong virtualenv kiểm thử | PASS |

Full suite gồm các ca: mật khẩu Unicode >72 byte không bị cắt; xác minh bcrypt cũ không truncate và nâng cấp Argon2id; JWT forged/expired/issuer/audience/jti/version; logout từng session; password change/khóa user thu hồi phiên; trùng email và mass assignment; rate limit giữa app instances; ownership mọi nhóm tài nguyên; pending host không tự được cấp quyền; reviewer/reason; booking nhiều loại phòng/snapshot giá/capacity; cạnh tranh không oversell; same idempotency key không nhân đôi; unique ledger ép rollback cả booking/payment; hủy/từ chối nhả phòng; state machine và thời điểm check-in/out; policy refund_due không giả đã hoàn tiền; review completed + unique; block/inventory/capacity; catalog/filter; upload decode/encode; body/CORS/errors; seed và legacy migrations.

## Các lỗi phát hiện và đã sửa trong quá trình QA
- ID user mock là hỗn hợp số/chuỗi; không được chép vào PK integer. Seed map ID database, không copy credential mock.
- `hs010.itemId` null: SQLite và PostgreSQL auto-increment khác nhau. Seed cấp/map ID rõ ràng và đồng bộ PostgreSQL sequence, test thêm bản ghi sau seed.
- Tăng inventory phải mở rộng toàn bộ maintenance block; giảm capacity không được phá booking đang hoạt động.
- Nâng cấp DB template thực tế phải thử khi chưa có `alembic_version`, không chỉ nâng DB đã stamp.
- Homestay chưa có phòng không được tạo giá 0 giả: detail trả price null, roomTypes rỗng; search chỉ trả nơi có room active.
- Test fixture có payload byte lớn cần ID ngắn; thư mục test riêng tránh permission/caching Windows. HTTP runner dừng process tree riêng và chịu được file log tạm bị OneDrive/antivirus giữ.

## Lặp lại
```powershell
backend/.venv/Scripts/python -m pytest backend/tests -q
backend/.venv/Scripts/python tools/test_backend_postgres.py
backend/.venv/Scripts/python tools/smoke_backend_http.py
```

Coverage: thêm `--cov=backend --cov-config=backend/.coveragerc --cov-report=term:skip-covered` vào runner PostgreSQL. Báo cáo máy nằm trong backend/.test-tmp/coverage.json (gitignored); không coi số coverage là chứng nhận an toàn production.

## Chưa xác minh / còn việc
- Chưa E2E frontend với API thật; chưa thay giao diện, auth storage hoặc switch mock. FE-001/FE-002/FE-003 còn TODO.
- Chưa tích hợp payment provider/webhook hoặc gửi email/reset; Payment pending/manual và refund_due là dữ liệu nghiệp vụ, không phải giao dịch thành công.
- Chưa deploy, load test, penetration test, restore production backup hay multi-replica shared storage. SQLite chạy serialize transaction là môi trường development.
- JSON amenities/availability có bước lọc portable trong Python; cần tối ưu và đo khi dữ liệu lớn. Occupancy dùng inventory hiện tại, chưa có lịch sử inventory thay đổi theo ngày.
- Legacy bcrypt đã truncate không thể phục hồi phần mật khẩu mất; tài khoản đó cần luồng reset riêng trước production.
- Không có GitHub Issue, push hoặc deployment nào được thực hiện.
