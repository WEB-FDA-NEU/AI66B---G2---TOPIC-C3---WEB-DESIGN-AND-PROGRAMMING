# Giai đoạn A — Thay đổi dữ liệu & ảnh (cho cả nhóm đọc trước khi làm B–F)

## Cấu trúc dữ liệu mới (frontend/mock/items.json = NGUỒN CHÍNH)
Mỗi homestay có thêm: `rooms[]`, `host_name`, `check_in_time`, `check_out_time`, `house_rules[]`, `cancellation_policy`.
Mỗi phòng: `id` (vd `r3-1`), `name`, `description`, `bed`, `area_m2`, `capacity`, `price` (VND/đêm),
`breakfast_included`, `free_cancellation`, `images[]` (2 ảnh khác nhau, lấy từ bộ ảnh của chính homestay đó).
`item.price` luôn = giá phòng rẻ nhất.

## Liên kết giữa các file mock
- `host-homestays.json`: hs001–hs009 ↔ items 1–9 qua `itemId`. hs010 chỉ có phía host, chưa có phòng (test empty state).
- `host-rooms.json`: khớp `items[].rooms[]` qua `itemRoomId`.
- `host-bookings.json`: `roomId` đều hợp lệ; `totalPrice` = số đêm × giá phòng.
- `bookings.json` (khách): `homestayId/Name/Image/roomName/pricePerNight` khớp items.json (có thêm `roomId`).

## Ảnh
- Xóa `img/da lat.png` (2 MB, bị dùng lại ở nhiều trang). booking-select/booking-page nay dùng ảnh của homestay Đà Lạt trong items.json.
- Thêm `img/placeholder.svg` (trước đó nhiều nơi tham chiếu nhưng file không tồn tại).
- Sửa đường dẫn avatar trong users.json; xóa `mock/item-1.json` (không dùng, trỏ tới ảnh không tồn tại).

## Quan trọng: cache localStorage
Mock được lưu vào localStorage nên máy các bạn sẽ thấy dữ liệu cũ. `js/api.js` có `MOCK_DATA_VERSION`:
**mỗi khi sửa mock/*.json, tăng số này** → mọi máy tự xóa cache mock cũ (không mất phiên đăng nhập).

## Còn tồn đọng
- Toàn bộ mock chỉ dùng 7 ảnh Unsplash, nên một số homestay vẫn trùng ảnh bìa (2&7, 4&10, 6&9). Cần ảnh thật riêng cho mỗi homestay.
- booking-select.html và booking-page.html vẫn hard-code Đà Lạt và giá cũ (1.200.000đ…) → sẽ được thay bằng dữ liệu động ở Giai đoạn B.
