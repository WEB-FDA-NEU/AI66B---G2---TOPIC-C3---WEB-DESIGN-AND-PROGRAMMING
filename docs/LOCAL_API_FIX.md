# Chạy LuxStay local với API thật (15/11/2026)

Mở **http://127.0.0.1:8000/index.html?mode=api**. FastAPI phục vụ frontend và API chung origin. **Không cần bật Live Server 5500**. Không thêm `/frontend/` vào URL cổng 8000.

## Bắt đầu nhanh: kết nối database

SQLite là một file database trên máy, không cần cài MySQL hay PostgreSQL để chạy local.

1. Trong VS Code, mở terminal PowerShell tại thư mục gốc repo (nơi có `README.md`). Môi trường `.venv` đã được cài trong lần sửa này.
2. Nếu chưa có database, chạy lệnh sau **một lần**, rồi tự chọn mật khẩu khi được hỏi:

   ```powershell
   .\backend\.venv\Scripts\python.exe tools/run_local.py --init-demo
   ```

3. Khởi động web và kết nối file `backend/luxstay-demo.db`:

   ```powershell
   .\backend\.venv\Scripts\python.exe tools/run_local.py --demo
   ```

4. Giữ terminal mở, truy cập **http://127.0.0.1:8000/index.html?mode=api**. Đăng nhập `huy@test.com` bằng mật khẩu vừa chọn. Không bật Live Server.
5. Lần sau chỉ chạy lại lệnh ở bước 3; dữ liệu vẫn ở cùng file database.

**Nếu đã có database cũ:** bỏ bước tạo demo. Trong `backend/.env`, đặt `DATABASE_URL=sqlite:///C:/duong-dan-thuc/luxstay.db` (thay bằng đường dẫn thật), rồi chạy `tools/run_local.py --check` và `tools/run_local.py` bằng Python trong `.venv`. Không seed lại database cũ.

Commit/push lên GitHub chỉ chia sẻ code. File database, `.env` và mật khẩu không được commit; mỗi người clone repo sẽ không tự có dữ liệu của bạn. Muốn cả nhóm thấy cùng đơn đặt phòng, cần dùng một backend/database chung như phần “Cả nhóm cùng truy cập” bên dưới.

## Bằng chứng và nguyên nhân

- Với URL trong ảnh `http://127.0.0.1:5500/frontend/index.html?mode=api`, `frontend/js/config.js` chọn API base `http://127.0.0.1:8000/api`; trang chủ gọi `/api/items` với query phân trang/sắp xếp. `mode=api` không khởi động backend.
- Tái hiện bằng `curl.exe --max-time 5 -i http://127.0.0.1:8000/api/items`: `curl (7) Failed to connect ... Could not connect to server`. Không có mã HTTP/body; không có listener 8000 trong môi trường kiểm tra. Đây là lỗi backend chưa chạy, chưa phải phản hồi CORS, HTML hay database.
- Checkout ban đầu không có `backend/.env`, `.venv`, hoặc file `*.db`/`*.sqlite*`. Không có log backend đang chạy để đọc, không có dữ liệu server cũ để xác minh. Không kết luận rằng database của một máy khác bị mất. Không reset/seed database hiện có.
- `python` và `py` mặc định trỏ tới Python WindowsApps bị từ chối truy cập. Python dùng được: `C:\Users\ADMIN\AppData\Local\Programs\Python\Python311\python.exe` (3.11.9). Đã tạo `.venv` và cài requirements trong đó.
- Route thật: `backend/routers/items.py`, prefix `/api/items`; lệnh Uvicorn phục vụ cổng 8000. SQLite mặc định là đường dẫn tuyệt đối tới `backend/luxstay.db` trong `Settings.from_env()`, không phụ thuộc thư mục gọi Uvicorn. Nếu `.env` có `DATABASE_URL` thì giá trị đó được ưu tiên; launcher in đường dẫn SQLite để kiểm tra.

Các trường hợp cần phân biệt khi tự kiểm tra:

| Kết quả | Ý nghĩa |
| --- | --- |
| Connection refused, không có HTTP | Backend/cổng chưa nghe; Live Server chỉ phục vụ file |
| HTTP 404 JSON `http_404` từ cổng 8000 | Nhầm route API |
| HTML thay JSON | Gọi nhầm static server/path; frontend giờ báo rõ URL và mã HTTP |
| HTTP 200 bằng curl nhưng browser chặn | Kiểm tra Origin/CORS; curl không thực thi CORS |
| `/api/health` 200 nhưng `/api/ready` 503 | Process chạy nhưng DB/schema chưa sẵn sàng |
| `/api/items` 503 `database_unavailable` | Backend không truy vấn được DB; không chữa bằng seed/mock |

Auth dùng bearer JWT trong `sessionStorage`, không dùng cookie. Frontend gửi Authorization, `credentials: 'omit'`; CORS `allow_credentials=False` phù hợp. Allowlist mặc định có riêng cả `http://localhost:5500` và `http://127.0.0.1:5500`. Origin khác cần cấu hình chính xác `CORS_ORIGINS`. Với URL chính cổng 8000, request cùng origin nên không cần CORS.

## Lệnh PowerShell

Tất cả lệnh chạy từ **thư mục gốc repo**:

```powershell
Set-Location 'C:\Users\ADMIN\OneDrive - National Economics University\Documents\GitHub\AI66B---G2---TOPIC-C3---WEB-DESIGN-AND-PROGRAMMING'
# .venv đã được tạo trong lần sửa này. Chỉ cần hai lệnh sau nếu máy mới/chưa có .venv:
& "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe" -m venv backend/.venv
& .\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
```

Nếu có database cũ: giữ nguyên file đó, cấu hình `DATABASE_URL` trong `backend/.env` tới đúng file. Không copy `.env.example` đè `.env`. Ví dụ SQLite trên Windows: `DATABASE_URL=sqlite:///C:/duong-dan-thuc/luxstay.db`. Không để trống nếu file cần dùng không phải `backend/luxstay.db`.

```powershell
& .\backend\.venv\Scripts\python.exe tools/run_local.py --check
& .\backend\.venv\Scripts\python.exe tools/run_local.py
```

Launcher chỉ đọc kiểm tra file, revision và số dòng users/homestays/rooms/bookings. Không tự migrate hoặc seed. Nếu không có DB/schema cũ, nó dừng với lỗi rõ ràng thay vì tạo SQLite rỗng.

**Checkout này chưa có database cũ**. Để chạy thử ngay, tạo **database development riêng** một lần (không phải database dùng chung):

```powershell
& .\backend\.venv\Scripts\python.exe tools/run_local.py --init-demo
# Nhập mật khẩu mới khi được hỏi, ký tự không hiện trên terminal.
& .\backend\.venv\Scripts\python.exe tools/run_local.py --demo
```

`--init-demo` dùng migration/seed hiện có, chỉ ghi file mới `backend/luxstay-demo.db`; từ chối nếu file đã tồn tại. Không chạy nó lại để sửa lỗi. Các lần sau chỉ chạy `--demo`. Tài khoản development: `huy@test.com`, `host@test.com`, `admin@test.com`, mật khẩu là giá trị bạn vừa chọn. Frontend vẫn đọc/ghi API thật, dữ liệu dev nằm trong SQLite phía server; không fallback sang mock/localStorage.

Giữ terminal server mở rồi mở **http://127.0.0.1:8000/index.html?mode=api**. Danh sách: **http://127.0.0.1:8000/search.html?mode=api**. Ctrl+C để dừng. File database vẫn ở cùng đường dẫn qua lần khởi động sau.

```powershell
curl.exe -i http://127.0.0.1:8000/api/ready
curl.exe -i http://127.0.0.1:8000/api/items
& .\backend\.venv\Scripts\python.exe -m pytest backend/tests -q
& .\backend\.venv\Scripts\python.exe tools/smoke_backend_http.py
& .\backend\.venv\Scripts\python.exe tests/shared-postgres-browser.py --sqlite
```

Các runner kiểm thử dùng DB/profile tạm riêng; không yêu cầu mật khẩu tài khoản đang dùng, không nhập/xóa đơn trong localStorage của bạn. Test hai phiên tạo tài khoản `huy@test.com` trong DB test riêng qua API đăng ký; đó không phải xác minh mật khẩu/tài khoản `huy@test.com` trên database cũ không được cung cấp.

## Cả nhóm cùng truy cập

Localhost của từng thành viên là các máy khác nhau. Muốn đồng bộ, cả nhóm cần truy cập **một URL của cùng một backend và database**. Không chạy `--init-demo` riêng trên từng máy rồi kỳ vọng đồng bộ.

- LAN development: máy chủ duy nhất cấu hình `DATABASE_URL` đúng DB hiện có, `SERVE_FRONTEND=true`, `FRONTEND_MODE=shared`; chạy `.\backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`. Các máy mở `http://<IP-LAN-may-chu>:8000/index.html?mode=api`; người vận hành cấu hình firewall phù hợp.
- Internet: dùng một domain HTTPS/reverse proxy phục vụ frontend và `/api` chung origin. Runtime config do FastAPI trả `apiBase: '/api'`; bản deploy không trỏ về localhost của người dùng. Host public chạy static riêng phải khai báo `LUXSTAY_CONFIG.apiBase` tới HTTPS API thật và allowlist đúng origin.
- Không thay đổi database engine trong lần sửa này. Cấu hình production hiện có của repo **yêu cầu PostgreSQL**; hướng dẫn deploy cũ vẫn là phương án riêng cần review, không phải điều kiện để sửa local SQLite. Chưa deploy, chưa migration production.
- Nếu sau này chủ đích deploy SQLite: cần thiết kế lại validation production hiện có và gắn persistent volume, đặt `DATABASE_URL` tuyệt đối tới file trên volume, có backup; kiểm chứng bằng đơn test còn nguyên sau restart/redeploy. Không dùng filesystem tạm của container hay tự tạo/seed mỗi lần deploy. Lần này **chưa có volume/deployment SQLite để xác minh độ bền dữ liệu**, không coi restart local là chứng minh redeploy production.

Kết quả chi tiết test hai phiên local được lưu tại [LOCAL_SQLITE_BROWSER_RESULTS.json](LOCAL_SQLITE_BROWSER_RESULTS.json). Chưa kiểm chứng trên link deploy, LAN hay hai máy vật lý.

## Kết quả kiểm thử

- Request ban đầu: `http://127.0.0.1:8000/api/items`, lỗi kết nối curl (7), không HTTP/body.
- Request sau khi chạy backend test: `http://127.0.0.1:56833/api/items`, HTTP **200**, `Content-Type: application/json`, JSON thực có `total: 1`, homestay đầu tiên `id: 1`. Cổng 56833 là cổng tạm do runner chọn, đã dừng sau test; URL dùng hàng ngày vẫn là cổng 8000.
- HTTP smoke trên SQLite tạm: **PASS** catalog, quote, tạo đơn confirmed, host đọc đơn, hủy, logout và phân quyền. Đã sửa kỳ vọng runner cũ (mock frontend, tạo đơn pending) cho đúng hành vi hiện có.
- Hai Chrome profile độc lập / cùng FastAPI / cùng SQLite: **48 kiểm tra PASS**, bao gồm trang chủ, search, hai lần đăng nhập cùng customer, đơn lưu trong DB, idempotency, lịch sử phiên B, tài khoản khác GET/hủy nhận 404, host/admin sai quyền nhận 403, hủy thấy ở cả hai phiên và dữ liệu còn sau backend restart. Luồng checkout/chọn phòng/hủy qua giao diện thật cũng qua; khi giữ phản hồi backend, frontend vẫn chờ, chưa báo thành công. Cả hai CORS preflight dùng Authorization/Content-Type/Idempotency-Key đều 200 với đúng origin.
- Backend pytest: **284 passed, 4 skipped** trong lần chạy toàn bộ trước khi thêm test khởi tạo demo; các skip là kiểm thử khóa hàng dành riêng PostgreSQL. Có một cảnh báo deprecation từ Starlette/httpx.
- `pip check`: **No broken requirements found**.
- Runner cũ `tests/api-accounts-browser.py`: **FAIL** tại assertion `unintegrated business is blocked without mock write`, vì runner vẫn kỳ vọng createBooking trả 503 như giai đoạn chưa tích hợp; adapter hiện có booking API và yêu cầu Idempotency-Key (400 khi thiếu). Không báo runner này là pass và không thay đổi nghiệp vụ để khớp kỳ vọng cũ. Runner hai phiên phía trên kiểm tra luồng shared hiện tại.
- Launcher: kiểm tra thiếu file không tạo SQLite mới, DB/schema cũ không bị sửa, byte dữ liệu giữ nguyên khi kiểm tra và DB chưa migrate không bị tự migrate. Test demo riêng xác nhận chỉ tạo file dev mới, không ghi DB đang cấu hình, và từ chối chạy seed lại khi file demo đã tồn tại.
- Lệnh riêng `pytest backend/tests/test_local_launcher.py -q` sau khi thêm test demo: **4 passed**. `git diff --check` và biên dịch cú pháp các script mới/sửa đều qua.

## File thay đổi

- `tools/run_local.py`: launcher local cùng origin, kiểm tra DB trước khi chạy, tùy chọn khởi tạo dev riêng có bảo vệ file cũ.
- `frontend/js/api.js`: lỗi kết nối nêu origin API/CORS; phản hồi không phải JSON nêu URL/mã HTTP. Không dùng no-cors hoặc fallback mock.
- `backend/.env.example`, `README.md`, `docs/LOCAL_API_FIX.md`: cấu hình/lệnh chạy thực tế, giữ SQLite local và tách hướng dẫn chia sẻ/deploy.
- `tests/shared-postgres-browser.py`: giữ runner PostgreSQL, thêm `--sqlite` tạm, kiểm tra trang chủ/catalog/CORS/hai phiên và dừng đúng cây process test Windows.
- `tools/smoke_backend_http.py`: cập nhật kỳ vọng frontend API và đơn confirmed ngay theo backend hiện có.
- `backend/tests/test_local_launcher.py`, `backend/tests/test_ops_media_migrations.py`: kiểm tra bảo vệ database và cả hai origin CORS.
- `docs/FRONTEND_BASELINE.json`: cập nhật đúng hash file `api.js` đã sửa; `docs/LOCAL_SQLITE_BROWSER_RESULTS.json`: lưu 48 kết quả kiểm tra hai phiên.
