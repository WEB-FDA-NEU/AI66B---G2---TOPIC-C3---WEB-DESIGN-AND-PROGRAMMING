# LuxStay — Review Phase 1–3

Ngày review: **14/11/2026**. Phần 1–9 bên dưới lưu kết quả review ban đầu **NOT READY**; xem mục 10 để biết kết quả khắc phục và gate hiện tại. Không dùng số test ban đầu làm số test sau sửa.

Đây là kết quả đọc lại source và chạy test trong lượt review này, không sử dụng số pass/coverage ở báo cáo trước làm bằng chứng thay thế. Không triển khai thêm Phase 4, không sửa logic ứng dụng, migration, API, frontend, CSS, animation hoặc USE_MOCK. Không commit/push.

## 1. Tổng quan từng phase

| Phase | Kết quả xác minh | Đánh giá |
|---|---|---|
| 1 — Audit/issue/contract | Có đủ issue, roadmap, bảng endpoint và phụ thuộc; các khoảng trống frontend đã được ghi nhận. Tuy nhiên DONE của BE-007 quá rộng so với lỗi validation/config còn tái hiện; BE-006 còn lỗi đồng thời. Tài liệu kế hoạch cũ và roadmap mới dùng hệ đánh số/phạm vi khác nhau. | PARTIAL; cần làm rõ DONE theo phạm vi và mở lại các phần chưa đạt |
| 2 — Database/models/migrations | SQLite và PostgreSQL: DB sạch, DB template chưa có Alembic version, schema sai bị từ chối, rollback khi role cũ không hợp lệ, metadata không drift, seed và sequence có test. Không chạy migration trên DB thật. | PASS trong các trường hợp test đã thực hiện; không phải chứng nhận mọi dữ liệu production |
| 3 — Auth/authz | Các luồng chính và kiểm tra phân quyền đạt. Tìm thấy bốn lỗi Medium về cấu hình, validation và concurrency. Luồng frontend thật vẫn chưa nối profile/logout/host application. | PARTIAL; chưa thể xác nhận end-to-end |

Không phát hiện lỗ hổng **Critical mới**, bỏ qua chữ ký JWT, tự cấp role hoặc IDOR thành công trong các ca đã chạy. Không được diễn giải điều này thành “không còn lỗ hổng”. Theo yêu cầu không đánh dấu READY khi còn High, các issue High đang mở ở ranh giới frontend/auth integration vẫn là gate chưa được đóng; đồng thời bộ test đầy đủ hiện chưa xanh.

## 2. Phạm vi và phương pháp

- Đọc các module backend: config, database, models, schemas, security, deps, rate limit, media, serializers, booking service, tất cả routers, migrations, seed, requirements và tests; đọc tài liệu docs và đối chiếu với source frontend hiện tại.
- Đối chiếu trực tiếp `frontend/js/api.js`, `auth.js`, `config.js`, profile/register/host-register, guard, admin inline script và các customer/host/admin pages. Không thay đổi frontend để làm khớp báo cáo.
- Lưu hash source đầu lượt review trong bộ nhớ để phân biệt thay đổi mới với working tree đã có từ trước. Repository đã có nhiều file backend modified/untracked trước khi review; các thay đổi cũ đó không phải do lượt này.
- Database test SQLite ở `backend/.test-tmp/run-*`; PostgreSQL 17 là cluster mới, thư mục riêng và cổng loopback ngẫu nhiên do runner hiện có tạo. Mỗi ca có schema `luxstay_test_*` riêng. Không kết nối hay reset database PostgreSQL service hiện có.
- Không phát hiện file SQLite development ở cấp `backend/*.db*` hoặc `backend/.env` trong kiểm tra đầu lượt. Không suy luận rằng không có database ở nơi khác; **không có thao tác ghi lên database thật**.

## 3. Chức năng đã xác minh

| Chức năng/rủi ro | Bằng chứng test và đọc code | Kết quả |
|---|---|---|
| Đăng ký customer | HTTP 201; email chuẩn hóa, Argon2id, user DTO không chứa credential/hash | PASS |
| Email trùng | Email khác hoa/thường trả 409; unique index DB | PASS |
| Đăng nhập đúng/sai | Đúng cấp token; sai và email không tồn tại cùng thông điệp 401 | PASS |
| Mật khẩu dài hợp lệ | Unicode >72 byte phân biệt được phần cuối, không truncate; giới hạn 8–128 ký tự | PASS |
| Bcrypt legacy | Không cắt đầu vào >72 byte; login hash cũ hợp lệ nâng lên Argon2id | PASS; reset tài khoản legacy không đăng nhập được vẫn là việc riêng |
| JWT | HS256 allowlist, chữ ký sai/hết hạn/sai issuer/audience, HS384/none, thiếu từng claim, nbf tương lai đều bị từ chối | PASS |
| Token/session | TTL khớp cấu hình; session hết hạn riêng vẫn 401; jti digest, user/session binding, token_version | PASS |
| Logout/password change | Logout một session; đổi password cần mật khẩu cũ và thu hồi mọi session; token cũ không sống lại sau reactivation | PASS |
| Profile/IDOR | `/me/profile` chỉ sửa chính mình; body id/user_id/role/is_active/token_version/password_hash bị chặn; query/path không chọn tài khoản khác | PASS |
| Role | Customer không vào host/admin; host không vào admin; role claim trong JWT không ghi đè role DB | PASS |
| Host application | role=host ở registration chỉ tạo pending; không tự gán applicant/status/reviewer; customer/host không tự duyệt; inactive applicant không được approve | PASS |
| Admin review | Approve/reject, lý do, reviewer/time, token cũ bị thu hồi, đăng nhập lại nhận role mới | PASS tuần tự; FAIL đồng thời ở R13-M04 |
| Quyền tài nguyên đã có | Chạy lại các test ownership host/homestay/room/booking hiện có | PASS; không xây API mới |
| CORS/response | Origin allowlist, bearer auth, không wildcard/credentials rộng; validation không echo input value; 500 trả message tổng quát | PASS các ca hiện có; còn hai nhánh validation 500 |

### Đối chiếu frontend quan trọng

- `frontend/js/api.js:238–262`: profile và đổi mật khẩu vẫn ném lỗi khi USE_MOCK=false, mặc dù backend đã có endpoint. Đây là thiếu adapter, không phải thiếu route backend.
- `frontend/js/auth.js:24–27`: logout mới xóa localStorage, chưa gọi `/api/auth/logout` để revoke server session.
- `frontend/js/pages/host-register.js:131–141`: vẫn báo tạo host thành công rồi sang host-dashboard, khác backend trả customer + application pending. Phải nối và thể hiện trạng thái chờ duyệt trong integration.
- `frontend/admin.html:211–259`: approve/reject vẫn đổi DOM, chưa lấy danh sách/gọi API review thật.
- `frontend/js/config.js`: API_BASE chỉ chọn cổng 8000 cho hostname localhost; Live Server ở 127.0.0.1 cần adapter/config rõ ràng khi chuyển sang API thật.
- `HOST_ID='host001'` chỉ nằm ở nhánh mock frontend. Backend thực tế lấy owner từ user được xác thực; không coi hằng mock đó là bằng chứng backend bị IDOR.

## 4. Automated testing thực hiện trong lượt này

| Lệnh/nhóm | Pass | Fail | Skip | Xfail | Ghi chú |
|---|---:|---:|---:|---:|---|
| `python -m pytest backend/tests -q --tb=short` trước khi thêm test review | 96 | 0 | 0 | 0 | SQLite, source tại đầu lượt |
| Test review bổ sung, SQLite | 29 | 0 | 0 | 4 | Sau thêm test config/validation/schema; trước thêm ca deadlock PostgreSQL |
| Runner PostgreSQL, chọn `-k phase_1_3_review -rxX` | 57 | 0 | 1 | 7 | 187 deselected; cả SQLite/PostgreSQL |
| **Full suite hiện tại qua runner PostgreSQL + JUnit** | **243** | **1** | **1** | **7** | **252 ca**, 166,68 giây; fail baseline ở mục R13-L01 |
| Probe `--runxfail`, chọn config/Unicode/avatar trên SQLite | 0 | 4 | 0 | 0 | Cố ý bỏ marker để xác nhận lỗi thật: 2 cấu hình không raise, 2 response 500 |
| Probe deadlock `--runxfail` qua runner PostgreSQL | 0 | 1 | 1 | 0 | PostgreSQL trả `[503,200]` thay vì `[409,200]`; SQLite skip vì không có row lock tương đương |
| `tools/smoke_backend_http.py` | PASS | — | — | — | HTTP thật qua Uvicorn, DB/port tạm; runner kết thúc thành công |
| `pip check`, Ruff test bổ sung | PASS | — | — | — | Không cài/thay dependency ứng dụng |

**Xfail không phải pass.** Bảy expected failures là các lỗi chưa sửa, được đánh dấu `strict=True`; khi sửa xong phải gỡ marker và đạt assertion mong muốn. Một skip là ca deadlock trên SQLite; ca tương ứng **đã chạy** trên PostgreSQL, không phải bỏ qua toàn bộ concurrency.

JUnit của full run: `backend/.test-tmp/phase13-review.xml` (gitignored). Không cộng các lượt chạy lặp lại thành tổng số test khác nhau. Không đo lại coverage trong lượt review; số 93% của báo cáo trước không được dùng làm kết quả mới. Không chạy browser E2E hoặc pentest/load test production.

## 5. Database và migration đã kiểm tra

| Trường hợp | SQLite | PostgreSQL |
|---|---|---|
| DB trống → 0001 → 0002 | PASS | PASS |
| users/items có dữ liệu, không có alembic_version → head, giữ id/email/hash/item | PASS | PASS |
| DB lạ bị từ chối, dữ liệu gốc vẫn còn | PASS | PASS |
| Thiếu email unique, thiếu owner FK, sai kiểu PK | PASS: từ chối | PASS: từ chối |
| Legacy role không hỗ trợ: v2 thất bại, cột thêm được rollback, record và revision 0001 giữ nguyên | PASS | PASS |
| Alembic check so với models | PASS | PASS |
| Seed chạy lại, sequence sau seed, không seed production/ghi đè dữ liệu hiện có | PASS | PASS |
| Destructive downgrade bị chặn | PASS | PASS |
| User role check, AuthSession FK, application unique | PASS (trigger + FK) | PASS (CHECK + FK) |

Đọc models/migrations xác nhận Numeric(14,0) cho tiền, Date cho ngày lưu trú, UTCDateTime cho timestamp, check status/range/date, FK và indexes. Booking–Room dùng BookingLine N-N; application/review/payment có unique theo quan hệ tương ứng. Models không khai báo ORM `relationship()`, nhưng quan hệ vật lý tồn tại qua FK và các query explicit; điều này tự thân không phải lỗi toàn vẹn dữ liệu.

Metadata check không thay thế kiểm tra constraint thực thi; vì vậy có thêm ca ghi role sai, FK sai, application trùng và negative migration. Không chạy downgrade/reset trên database thật, không kiểm tra restore backup production và không khẳng định có thể chuyển mọi database tùy biến sang schema mới.

## 6. Phát hiện và mức độ

### Critical
Không có Critical mới được xác nhận trong phạm vi kiểm thử. Không có bằng chứng thành công về JWT forgery, self-admin/self-host hoặc IDOR ở API.

### High — các gate hiện vẫn mở, được xác minh lại từ source

**R13-H01 — DOM sinks + token localStorage trước tích hợp (FE-002, TODO).** `frontend/js/pages/host-rooms.js:232–276` chèn name/ảnh/description vào innerHTML và attribute; các host pages khác có mẫu tương tự. Token ở `frontend/js/auth.js:6–20` được lưu localStorage. Cần xử lý sink DOM trước khi đưa dữ liệu server do người dùng khác nhập vào giao diện. Đây là rủi ro ở ranh giới tích hợp đã có trong tracker, **không phải bằng chứng API backend hiện bị vượt quyền hoặc đã có XSS được thực thi trong browser**. Không sửa frontend ở review này.

**R13-H02 — Luồng account/host/admin chưa khớp frontend thật (FE-001, TODO).** Profile/password không có nhánh API thật, logout chưa revoke, host-register và admin approval vẫn mock như mục 3. Không thể dùng kết quả API độc lập để đánh dấu hoàn tất luồng Phase 3 end-to-end. API backend tương ứng có thật; không cần tạo route Homestay/Room mới để giải quyết. FE-003/EXT-001 cũng còn High trong tracker, nhưng nghiệp vụ Phase 4/provider không được mở rộng ở lượt này.

Theo gate “không READY khi còn Critical/High chưa xử lý”, hai nhóm High chưa đóng phải được xử lý hoặc được chủ dự án phân tách phạm vi/gate một cách rõ ràng; reviewer không tự hạ severity hay đóng issue để cho qua Phase 4.

### Medium — lỗi mới được tái hiện, chưa sửa

**R13-M01 — APP_ENV lạ bị chấp nhận thay vì fail closed.**
- Source: `backend/config.py:26–36,43–69` chỉ áp dụng guard production với chuỗi chính xác `production`, không có allowlist environment.
- Probe: APP_ENV=`prod` hoặc `Production`, DATABASE_URL SQLite và secret đủ dài vẫn tạo Settings thành công; không raise ValueError. Việc thử dùng ROOT/env tạm, không sửa env thật.
- Tác động: lỗi cấu hình vận hành có thể bỏ qua yêu cầu PostgreSQL/mặc định không serve frontend ở production. Không phải bỏ qua chữ ký JWT và không làm secret thành giá trị mặc định đoán được.
- Đề xuất: enum/allowlist hoặc mapping alias có chủ đích, reject giá trị không hỗ trợ; bổ sung range validation cho tham số nhạy cảm. Test hiện strict xfail.

**R13-M02 — Mật khẩu có surrogate Unicode không hợp lệ gây 500.**
- Source: `backend/schemas.py:RegisterIn`, `backend/security.py:18–21`, register router.
- Probe: JSON ASCII-escaped chứa password `"\ud800"` lặp 8 lần đi tới Argon2 và trả HTTP 500, thay vì lỗi đầu vào 400/422. Request được gửi bằng content JSON đã escape để bảo đảm lỗi xảy ra ở server, không phải ở HTTPX encoder.
- Tác động: validation thiếu và server error có thể lặp từ request ngoài. Mật khẩu Unicode hợp lệ dài vẫn hoạt động; không được sửa bằng cắt mật khẩu.
- Đề xuất: xác minh chuỗi encode được UTF-8 trước hashing, trả validation error đã redacted; giữ toàn bộ ký tự hợp lệ. Test strict xfail.

**R13-M03 — URL avatar sai cú pháp gây 500.**
- Source: `backend/media.py:61` gọi urlsplit ngoài nhánh bắt ValueError; `routers/auth.py:update_profile` sử dụng trực tiếp.
- Probe: avatar=`https://[` trả 500 thay vì 422 trên cả hai engine.
- Tác động: parser exception lọt thành lỗi máy chủ. Đã kiểm tra profile không bị commit dở dang; response 500 không lộ traceback/hash/token.
- Đề xuất: bắt lỗi parse URL và map sang validation 422; không bỏ kiểm tra scheme/host. Test strict xfail.

**R13-M04 — Đảo thứ tự khóa trong quy trình host application.**
- Source: `backend/routers/auth.py:125–127` khóa User rồi HostApplication; `backend/routers/admin.py:67–75` khóa HostApplication rồi User.
- Probe PostgreSQL: giữ hai khóa đầu bằng hook quan sát SQL để ép interleaving, sau đó để code thật tiếp tục. Hai request gửi lại application đang pending và admin approve trả `[503,200]`; PostgreSQL hủy một transaction vì deadlock. Hook chỉ đồng bộ thời điểm, không thay đổi SQL hay nghiệp vụ.
- Tác động: lỗi khả dụng/đồng thời ở Phase 3; chưa thấy nâng quyền sai hoặc dữ liệu commit một nửa. SQLite serialize transaction nên không chứng minh được trường hợp này.
- Đề xuất: thống nhất thứ tự khóa, đọc lại trạng thái sau khóa, test approve/reject/resubmit cạnh tranh và chính sách retry phù hợp. Chưa sửa logic ứng dụng; test strict xfail.

**R13-M05 — DONE/phạm vi và dependency cần chỉnh lại sau review.**
- BE-007 đang DONE nhưng tiêu chí invalid input trả 4xx chưa đạt ở M02/M03, fail-fast config chưa đầy đủ ở M01. Cần mở lại các phần này.
- BE-006 có happy-path và anti-escalation đúng nhưng chưa giải quyết M04; không nên hiểu DONE là đã an toàn trong mọi luồng đồng thời.
- BE-001/002/003 được hỗ trợ bởi test crypto/migration/authz hiện tại. BE-005 có backend route/serializer nhưng không đồng nghĩa FE-001 đã DONE.
- Roadmap đã ghi “nghiệp vụ backend DONE” và dependencies BE-006→BE-004 (review phụ thuộc booking), trong khi gate hiện chỉ Phase 1–3. Cần tách auth/application khỏi review/booking và đánh dấu kế hoạch cũ là tham khảo để không kéo scope hoặc đóng phase nhầm.

### Low / ghi chú chất lượng

**R13-L01 — Baseline frontend lệch đúng một trailing space.** Full run fail ở `test_frontend_baseline_and_mock_switch_are_untouched`. File `frontend/host-homestay-form.html:161` có `</main> ` thay cho `</main>`. Đầu review hash là `1ba539c2c7c83ed85bf8bcef9a339e3a3a8a979693ccbe22e31dc5a845a80c5d`, lúc full run là `0bd97b3bc8fa3ea3c05104b3b04425411d297e5eefdb10645befed88d85d7a48`; 65 file còn lại khớp snapshot cũ. Không có thao tác chỉnh frontend từ reviewer. Diff này không chứng minh lỗi UI/animation; không tự revert file hiện tại hoặc cập nhật hash để che fail. Khi chốt phiên bản frontend mới, audit rồi cập nhật baseline trong thay đổi riêng.

**R13-L02 — Settings repr chưa redacted.** Dataclass Settings chứa jwt_secret kiểu str với repr mặc định. Chưa thấy chỗ code hiện tại log Settings hoặc response lộ secret; đây là defense-in-depth khi debug/logging về sau. Có thể dùng repr=False/secret wrapper trong lần sửa được duyệt.

## 7. Thiếu/chưa có test hoặc chưa thể xác minh

- Chưa browser E2E với API thật; profile/logout/application/admin adapters vẫn mock. Không bật USE_MOCK để làm phép thử.
- Chưa stress test auth nhiều worker, các biến thể retry deadlock, mọi thứ tự approve/reject/resubmit hoặc recovery khi DB mất kết nối giữa transaction.
- Chưa chạy migration/restore trên bản sao database production thực tế do người vận hành cung cấp. Chỉ đã kiểm tra các fixture legacy/sạch/sai schema trên hai engine.
- Chưa chạy CVE advisory scanner, pentest, production TLS/proxy hoặc log collector thực tế. `pip check` chỉ xác minh dependency consistency, không phải quét lỗ hổng.
- Chưa chứng nhận email verification/reset, gateway/webhook hay object storage; đó là các hạng mục đã ghi nhận riêng, không triển khai trong review.
- Coverage không đo lại; không tuyên bố “test toàn diện” chỉ từ số lượng ca.

## 8. File thay đổi trong lượt review

1. **Thêm** `backend/tests/test_phase_1_3_review.py`: test auth/config/identity/host approval/migration còn thiếu; các bug chưa sửa được strict xfail với issue ID.
2. **Thêm** `docs/PHASE_1_3_REVIEW.md`: báo cáo này.

Artifact runtime gitignored: JUnit `backend/.test-tmp/phase13-review.xml` và database/log test tạm. Không sửa file backend ứng dụng, migrations, tests cũ, docs tracker cũ, frontend hay mock flag. Thay đổi trailing space của host-homestay-form phát sinh so với snapshot đầu lượt được ghi nhận riêng, không gán là thay đổi do reviewer thực hiện. Không commit/push.

## 9. Kết luận và điều kiện xem xét lại

**NOT READY** theo tiêu chí được giao: còn High chưa đóng, full suite có fail baseline chưa được chốt và có 7 expected failures biểu diễn bốn lỗi Medium thật chưa sửa. Chữ ký JWT, password hashing, phân quyền/ownership và migrations trong các trường hợp test không có lỗi vượt quyền được tái hiện; không phủ nhận các kết quả PASS đó.

Trước khi xem xét READY: chốt phạm vi/gate của FE-001/FE-002/FE-003 và các High còn mở; xử lý M01–M04 trong thay đổi riêng được duyệt, gỡ xfail và chạy lại cả SQLite/PostgreSQL; đồng bộ trạng thái issue/DONE; audit/chốt baseline frontend hiện tại thay vì bỏ assertion. Review này không tự thực hiện các sửa nghiệp vụ đó và không bắt đầu Phase 4.

## 10. Khắc phục theo yêu cầu tiếp theo — 14/11/2026

Mục này thay thế kết luận hiện tại của mục 1–9; các mục trước được giữ làm lịch sử review, không phải trạng thái code sau sửa. Phạm vi được chủ dự án xác định lại rõ: nghiệm thu **backend Phase 1–3 độc lập**, không yêu cầu đóng frontend integration/Phase 4 trong lượt này. Không hạ severity các issue High hoặc tuyên bố hệ thống fullstack đã READY.

### Các thay đổi thực hiện

| Issue | Thay đổi | Acceptance được kiểm tra |
|---|---|---|
| R13-M01 | Chỉ nhận development/test/production; reject env lạ trước khi tạo secret; parse dialect DB; kiểm tra TTL, rate limit/window, body size, CORS URL/port và SERVE_FRONTEND | prod/Production bị từ chối; production thiếu secret/SQLite bị từ chối; config sai bị từ chối; development SQLite tiếp tục chạy |
| R13-M02 | Validator chung cho SecretStr kiểm tra UTF-8; hash_password có guard phòng vệ | Register/login/current/new password có surrogate trả 422; không echo input; Unicode hợp lệ không bị truncate/normalize; Argon2id và bcrypt legacy không đổi chính sách |
| R13-M03 | Bắt ValueError từ urlsplit và truy cập port, trả 422 | Profile không commit một phần; URL xấu không lưu; tests raster upload/data URI vẫn đạt; không fetch URL trên server |
| R13-M04 | Admin đọc user_id bất biến rồi khóa User trước Application; cả hai flow dùng populate_existing và kiểm tra trạng thái/điều kiện sau khóa | Apply/approve trả 409/200 thay vì 503; hai admin approve/approve, approve/reject, reject/reject chỉ một quyết định 200 và một 409, role DB khớp quyết định thắng |
| R13-L01 | Audit diff chỉ một space ngoài text content sau thẻ đóng main; giữ nguyên HTML, chỉ cập nhật một hash | Assertion toàn bộ frontend và USE_MOCK được giữ nguyên; không sửa UI/CSS/animation |
| R13-L02 | jwt_secret đặt repr=False | Assertion trực tiếp xác nhận repr(Settings) không chứa secret |

Test concurrency bỏ hook buộc hai luồng lấy **hai loại khóa đảo nhau**, vì thứ tự đó không còn tồn tại sau sửa; thay bằng Barrier trước truy vấn khóa User để hai request thực sự tranh khóa. Vẫn giữ assertion chính xác 200/409 và bổ sung kiểm tra kết quả lưu DB. Không thay expected status bằng tập giá trị rộng hơn để che lỗi. SQLite skip bốn ca row-lock PostgreSQL; các ca tương ứng được chạy trên PostgreSQL.

`get_db` tiếp tục rollback mọi exception; không thêm commit trung gian. Admin chỉ xét pending, applicant active và role user; thay role chỉ khi approve, đồng thời tăng token_version. Apply kiểm tra lại trạng thái application sau khóa trước khi tạo/reset đơn, tránh sử dụng identity map cũ sau lúc chờ.

### Kết quả kiểm tra sau sửa

- SQLite, source cuối: `python -m pytest backend/tests -q --tb=short --junitxml=backend/.test-tmp/phase13-fix-sqlite.xml`: **139 pass, 0 fail, 4 skip, 0 xfail**, 32,88 giây.
- PostgreSQL + SQLite, source cuối: **267 pass, 0 fail, 4 skip, 0 xfail**, 171,01 giây; `python tools/test_backend_postgres.py -rxX --junitxml=backend/.test-tmp/phase13-fix-final.xml`. Cả bốn ca concurrency PostgreSQL đều PASS; bốn skip chỉ là bản SQLite của các ca này. Các test trước đây xfail nay PASS thật, không còn marker xfail trong module review.
- Lượt PostgreSQL trung gian trước tinh chỉnh thứ tự kiểm tra conflict: **266 pass, 1 fail, 4 skip, 0 xfail**; lỗi là 403 thay cho 409 khi admin thắng trước, không còn deadlock 503. Đã sửa code, giữ assertion và chạy lại toàn bộ; không dùng lượt này để tuyên bố pass.
- HTTP smoke thật Uvicorn + database tạm: **PASS**; không kiểm thử browser E2E và không bật mock=false.
- Ruff tất cả file Python sửa: **PASS**. Chạy Ruff toàn backend còn một lỗi import-order có sẵn ở `backend/migrations/env.py`; không sửa migration ngoài phạm vi. Đây là ghi chú Low chưa xử lý, không phải lỗi chạy migration.
- `pip check`: **PASS**; không thay dependencies. Settings repr redaction assertion: **PASS**.

Migrations không bị sửa. Full suite bao gồm DB sạch đến head, nâng legacy users/items giữ dữ liệu, schema sai từ chối, rollback role legacy không hợp lệ, metadata/Alembic check, FK/unique enforcement và seed idempotent trên cả hai engine. Tất cả chỉ chạy trên DB/schema tạm. Không upgrade/reset DB thật; không chứng nhận restore backup production.

### File thay đổi trong lượt khắc phục

1. `backend/config.py`: environment và cấu hình nhạy cảm, repr secret.
2. `backend/schemas.py`: validation UTF-8 cho tất cả đầu vào SecretStr.
3. `backend/security.py`: guard UTF-8 khi hash, giữ chính sách hash/legacy.
4. `backend/media.py`: lỗi parser URL thành 422.
5. `backend/routers/auth.py`: lock order, refresh và điều kiện sau khóa.
6. `backend/routers/admin.py`: cùng lock order và refresh sau khóa.
7. `backend/tests/test_phase_1_3_review.py`: gỡ toàn bộ strict xfail R13-M01–M04; bổ sung config/Unicode/concurrent decisions và điều chỉnh hook đồng bộ theo thứ tự khóa mới.
8. `docs/FRONTEND_BASELINE.json`: cập nhật đúng hash host-homestay-form đã audit; không ghi vào frontend.
9. `docs/BACKEND_ISSUES.md`: acceptance và trạng thái remediation, giữ các High integration mở.
10. `docs/BACKEND_ROADMAP.md`: tách nghiệm thu backend Phase 1–3 khỏi integration và code Phase 4 có sẵn.
11. `docs/PHASE_1_3_REVIEW.md`: lịch sử và kết quả mới.

Working tree đã có nhiều thay đổi từ trước; danh sách trên chỉ là lượt khắc phục này. Artifact test trong `.test-tmp` được gitignore. Không commit/push.

### Gate và việc còn lại

**Backend Phase 1–3 độc lập: READY trong phạm vi kiểm thử nêu trên.** R13-M01–M04, L01/L02 đạt acceptance và DONE; không còn Critical/High backend Phase 1–3 được xác nhận chưa xử lý trong review này. R13-M05 được xử lý bằng việc tách rõ phạm vi/gate và cập nhật issue/roadmap. Kết luận này không đóng các High integration, không phải chứng nhận production, không phải READY fullstack hoặc nghiệm thu Phase 4.

**Frontend integration/fullstack: NOT READY.** FE-001/FE-002/FE-003, phần E2E của QA-001 và EXT-001 vẫn mở, giữ nguyên mức High. Trước USE_MOCK=false phải nối profile/password/logout revoke, host application pending và admin approve/reject; loại bỏ DOM sinks không an toàn khi render dữ liệu server; kiểm tra cách lưu token; thay HOST_ID mock bằng identity thật; dùng dữ liệu quantity/inventory và dashboard chuẩn; chạy browser E2E customer/host/admin và xác minh CORS/API_BASE ở hostname thực tế. Không coi pass API là đã pass trình duyệt.

Phase 4 không được phát triển hoặc nghiệm thu thêm ở lượt này. Các giới hạn về provider/email/reset/storage, migration trên bản sao DB production, load/pentest/CVE scan vẫn giữ như mục 7. Không thể suy rộng các ca concurrency đã pass thành không có mọi race condition ở toàn hệ thống.
