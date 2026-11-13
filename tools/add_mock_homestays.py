"""
Thêm 12 homestay mới (id 11–22) vào mock. Chạy từ thư mục gốc dự án:
    python tools/add_mock_homestays.py frontend

Ghi vào 3 file, GIỮ NGUYÊN dữ liệu cũ (id 1–10, hs001–hs010, rm001–rm024):
  - mock/items.json          → danh sách công khai (trang chủ, search, detail)
  - mock/host-homestays.json → hs011–hs022, liên kết qua itemId
  - mock/host-rooms.json     → rm025–rm048, mỗi homestay 2 phòng (khớp roomTypesFor() trong js/pricing.js)

Chạy lại nhiều lần vẫn an toàn (xóa phần id ≥ 11 rồi sinh lại). Sau khi chạy: tăng MOCK_DATA_VERSION trong js/api.js.

ẢNH: chưa có ảnh riêng cho homestay mới nên tạm lấy lại ảnh của homestay cũ (IMAGE_FROM).
Khi có ảnh thật, thay mảng "images" của từng homestay trong IMAGES_OVERRIDE bên dưới.
"""
import json, sys
from pathlib import Path

mock = Path(sys.argv[1] if len(sys.argv) > 1 else 'frontend') / 'mock'
load = lambda n: json.loads((mock / n).read_text(encoding='utf-8'))
def save(n, d): (mock / n).write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# ── Ảnh: {id mới: (id homestay cũ để mượn ảnh, vị trí bắt đầu)} ──
IMAGE_FROM = {11: (3, 1), 12: (1, 1), 13: (2, 2), 14: (4, 2), 15: (7, 0), 16: (5, 2), 17: (9, 1),
              18: (10, 1), 19: (8, 0), 20: (5, 1), 21: (6, 0), 22: (9, 2)}
IMAGES_OVERRIDE = {}   # ví dụ: {11: ['https://.../a.jpg', 'https://.../b.jpg']}

# Tên điểm đến lấy theo js/pages/home.js: địa chỉ ≥3 phần → phần áp chót; 2 phần → phần cuối.
# (id, tên, địa chỉ, loại, tiện ích, rating, giá, giá cũ, ngày tạo, mô tả, 2 tên phòng phụ, bình luận)
H = [
 (11, 'Đà Lạt Hillside Villa', 'Phường 10, Đà Lạt, Lâm Đồng', 'Toàn bộ homestay', ['Wi-fi', 'Bãi đỗ xe', 'Bếp'], 4.7, 520000, 600000, '2026-11-05T08:00:00Z',
  'Biệt thự nhỏ trên đồi thông với sân vườn và lò sưởi, thích hợp cho gia đình hoặc nhóm bạn muốn tránh xa phố.',
  [('Minh Thư', 5, 'Sáng dậy mở cửa là thấy sương, chủ nhà nhiệt tình.'), ('Đức Anh', 4, 'Sân vườn đẹp, hơi xa trung tâm nhưng đáng.')]),
 (12, 'Sapa Cloud Bamboo House', 'Bản Tả Van, Sa Pa, Lào Cai', 'Phòng riêng', ['Wi-fi', 'Bếp'], 4.6, 340000, None, '2026-11-02T09:30:00Z',
  'Nhà tre giữa ruộng bậc thang Tả Van, có ban công nhìn xuống thung lũng, bữa sáng do gia đình chủ nhà nấu.',
  [('Thanh Hà', 5, 'Ruộng bậc thang ngay trước cửa, bữa sáng rất ngon.'), ('Quang Vinh', 4, 'Đêm hơi lạnh nhưng chăn ấm, yên tĩnh.')]),
 (13, 'Hội An Lantern Courtyard', 'Cẩm Phô, Hội An, Quảng Nam', 'Phòng riêng', ['Wi-fi', 'Hồ bơi', 'Bãi đỗ xe'], 4.8, 480000, 560000, '2026-10-30T10:00:00Z',
  'Nhà sân vườn cách phố cổ 5 phút đi bộ, hồ bơi nhỏ giữa sân và đèn lồng thắp sáng mỗi tối.',
  [('Phương Linh', 5, 'Gần phố cổ, hồ bơi sạch, nhân viên chu đáo.'), ('Hoàng Nam', 5, 'Buổi tối đèn lồng lên rất đẹp.')]),
 (14, 'Đà Nẵng Skyline Studio', 'Sơn Trà, Đà Nẵng', 'Toàn bộ homestay', ['Wi-fi', 'Bếp', 'Bãi đỗ xe'], 4.4, 430000, None, '2026-10-27T07:15:00Z',
  'Căn studio tầng cao nhìn ra sông Hàn và cầu Rồng, đầy đủ bếp và máy giặt cho kỳ nghỉ dài ngày.',
  [('Bảo Ngọc', 4, 'View sông Hàn đẹp, căn hộ sạch.'), ('Tuấn Kiệt', 4, 'Tiện đi biển Mỹ Khê, thang máy hơi chờ lâu.')]),
 (15, 'Phú Quốc Coconut Villa', 'Dương Đông, Phú Quốc, Kiên Giang', 'Toàn bộ homestay', ['Wi-fi', 'Hồ bơi', 'Bếp', 'Bãi đỗ xe'], 4.9, 890000, 1050000, '2026-10-24T11:00:00Z',
  'Villa riêng có hồ bơi dưới tán dừa, cách biển 300m, phù hợp nhóm đông hoặc gia đình có trẻ nhỏ.',
  [('Gia Hân', 5, 'Villa rộng, hồ bơi riêng, đúng như hình.'), ('Văn Long', 5, 'Chủ nhà hỗ trợ thuê xe và hải sản tươi.')]),
 (16, 'Nha Trang Ocean Pearl', 'Trần Phú, Nha Trang, Khánh Hòa', 'Phòng riêng', ['Wi-fi', 'Hồ bơi'], 4.3, 410000, None, '2026-10-21T06:45:00Z',
  'Phòng nhìn biển trên đường Trần Phú, đi bộ ra bãi tắm trong 2 phút, có hồ bơi trên tầng thượng.',
  [('Khánh Vy', 4, 'Gần biển, sáng dậy nghe sóng.'), ('Minh Quân', 4, 'Giá hợp lý, phòng hơi nhỏ.')]),
 (17, 'Hà Giang Loop Stilt House', 'Đồng Văn, Hà Giang', 'Phòng chung', ['Wi-fi', 'Bếp'], 4.5, 220000, None, '2026-10-18T12:30:00Z',
  'Nhà sàn của người Mông ở thị trấn Đồng Văn, phù hợp phượt thủ, có bữa tối cùng gia đình chủ nhà.',
  [('Hải Đăng', 5, 'Trải nghiệm rất thật, bữa tối cả nhà ăn chung.'), ('Mai Anh', 4, 'Phòng chung đông vui, đêm khá lạnh.')]),
 (18, 'Mũi Né Sandy Cabin', 'Hàm Tiến, Phan Thiết, Bình Thuận', 'Toàn bộ homestay', ['Wi-fi', 'Bãi đỗ xe', 'Hồ bơi'], 4.2, 460000, 520000, '2026-10-15T08:20:00Z',
  'Cabin gỗ sát biển Mũi Né, gần đồi cát và làng chài, tiện lướt ván diều vào mùa gió.',
  [('Thành Đạt', 4, 'Sát biển, ngắm bình minh từ ban công.'), ('Lan Chi', 4, 'Chỗ ở đẹp, đường vào hơi khó tìm.')]),
 (19, 'Hà Nội West Lake Loft', 'Tây Hồ, Hà Nội', 'Toàn bộ homestay', ['Wi-fi', 'Bếp'], 4.6, 520000, None, '2026-10-12T09:10:00Z',
  'Căn gác xép gần Hồ Tây với cửa sổ lớn, nhiều cây xanh, có quán cà phê và đường đi dạo quanh hồ ngay dưới nhà.',
  [('Ngọc Mai', 5, 'Yên tĩnh giữa thủ đô, cà phê bên dưới rất ngon.'), ('Việt Hùng', 4, 'Căn gác đẹp, cầu thang hơi dốc.')]),
 (20, 'Sài Gòn Thảo Điền Garden', 'Thảo Điền, TP. Hồ Chí Minh', 'Phòng riêng', ['Wi-fi', 'Hồ bơi', 'Bãi đỗ xe'], 4.5, 600000, 680000, '2026-10-09T10:40:00Z',
  'Nhà vườn trong khu Thảo Điền yên tĩnh, có hồ bơi chung và quán cà phê quanh khu, gần ga metro.',
  [('Thu Trang', 5, 'Khu yên tĩnh, hồ bơi sạch, gần metro.'), ('Đình Phúc', 4, 'Vị trí tốt, giá hơi cao.')]),
 (21, 'Ninh Bình Tràng An Riverside', 'Tràng An, Ninh Bình', 'Phòng riêng', ['Wi-fi', 'Bãi đỗ xe', 'Bếp'], 4.4, 330000, None, '2026-10-06T07:50:00Z',
  'Homestay bên bờ sông Tràng An, có thể chèo thuyền sáng sớm ngắm núi đá vôi trước khi du khách đông.',
  [('Phương Thảo', 4, 'Sáng chèo thuyền rất đã, chủ nhà dễ mến.'), ('Anh Tuấn', 5, 'Cảnh đẹp, bữa cơm quê ngon.')]),
 (22, 'Mộc Châu Pine Hill Cabin', 'Mộc Châu, Sơn La', 'Toàn bộ homestay', ['Wi-fi', 'Bếp', 'Bãi đỗ xe'], 4.1, 380000, None, '2026-10-03T08:00:00Z',
  'Cabin gỗ trên đồi thông gần đồi chè trái tim, có bếp nướng ngoài trời, phù hợp nhóm bạn đi cuối tuần.',
  [('Diệu Linh', 4, 'Đồi chè đẹp, tiệc nướng tối rất vui.'), ('Trung Kiên', 4, 'Phòng sạch, mùa lạnh nên mang thêm áo.')]),
]
BASE_ID, HS_ID_START, ROOM_ID_START = 11, 11, 25

# ───────── items.json ─────────
items_doc = load('items.json')
items = [i for i in items_doc['items'] if i['id'] < BASE_ID]
by_id = {i['id']: i for i in items}
def pick_images(nid):
    if nid in IMAGES_OVERRIDE: return IMAGES_OVERRIDE[nid]
    src, start = IMAGE_FROM[nid]
    large = [u for u in by_id[src]['images'] if 'max1024' in u]    # ảnh lớn, không lấy ảnh thumb 300px
    n = len(large)
    return [large[(start + k) % n] for k in range(n)]

new_items = []
for (nid, title, addr, rtype, amen, rating, price, old, created, desc, revs) in H:
    imgs = pick_images(nid)
    new_items.append({
        'id': nid, 'title': title, 'location': addr, 'meta': addr, 'room_type': rtype, 'amenities': amen,
        'rating': rating, 'price': price, **({'price_old': old} if old else {}),
        'cover_url': imgs[0], 'images': imgs, 'status': 'active', 'created_at': created, 'description': desc,
        'reviews': [{'id': f'rv{nid}{k+1}', 'name': n, 'rating': s, 'comment': c,
                     'created_at': f'2026-10-{10 + k * 5:02d}T09:00:00Z'} for k, (n, s, c) in enumerate(revs)],
    })
items_doc['items'] = items + new_items
items_doc['total'] = len(items_doc['items'])
save('items.json', items_doc)

# ───────── host-homestays.json ─────────
hh_doc = load('host-homestays.json')
hh = [h for h in hh_doc['homestays'] if not (h['id'][2:].isdigit() and int(h['id'][2:]) >= HS_ID_START)]
hs_of = {}
for n, (nid, title, addr, rtype, amen, rating, price, old, created, desc, revs) in zip(range(len(H)), H):
    hid = f'hs{HS_ID_START + n:03d}'; hs_of[nid] = hid
    hh.append({'id': hid, 'hostId': 'host001', 'itemId': nid, 'name': title, 'address': addr, 'description': desc,
               'amenities': amen, 'images': next(i for i in new_items if i['id'] == nid)['images'],
               'status': 'active', 'createdAt': f'2026-{int(created[5:7]) - 1:02d}-{created[8:10]}T03:00:00Z'})
hh_doc['homestays'] = hh
save('host-homestays.json', hh_doc)

# ───────── host-rooms.json ─────────
hr_doc = load('host-rooms.json')
rooms = [r for r in hr_doc['rooms'] if int(r['id'][2:]) < ROOM_ID_START]
rid = ROOM_ID_START
for (nid, title, addr, rtype, amen, rating, price, old, created, desc, revs) in H:
    imgs = next(i for i in new_items if i['id'] == nid)['images']
    for k, (name, cap, p, d) in enumerate([
        ('Phòng Superior Giường Đôi', 2, price, 'Phòng thoáng, giường đôi lớn, nhà tắm riêng.'),
        ('Deluxe Studio Hướng Núi' if 'Sa Pa' in addr or 'Đà Lạt' in addr or 'Mộc Châu' in addr or 'Hà Giang' in addr else 'Deluxe Studio Hướng Đẹp',
         3, round(price * 1.33 / 1000) * 1000, 'Rộng hơn, có sofa và góc làm việc, bao gồm ăn sáng.')]):
        rooms.append({'id': f'rm{rid:03d}', 'homestayId': hs_of[nid], 'itemRoomId': f'r{nid}-{k+1}', 'name': name,
                      'description': d, 'capacity': cap, 'pricePerNight': p,
                      'images': [imgs[(k + 1) % len(imgs)], imgs[(k + 2) % len(imgs)]], 'blockedDates': []})
        rid += 1
hr_doc['rooms'] = rooms
save('host-rooms.json', hr_doc)

# ───────── kiểm tra liên kết ─────────
items_ids = {i['id'] for i in load('items.json')['items']}
hs_list = load('host-homestays.json')['homestays']; rm_list = load('host-rooms.json')['rooms']
hs_ids = {h['id'] for h in hs_list}
assert all(h['itemId'] in items_ids for h in hs_list if h.get('itemId')), 'itemId không khớp items.json'
assert all(r['homestayId'] in hs_ids for r in rm_list), 'homestayId của phòng không khớp'
assert len({r['id'] for r in rm_list}) == len(rm_list) and len(hs_ids) == len(hs_list), 'trùng id'
print(f'OK: {len(items_ids)} homestay công khai, {len(hs_list)} homestay của host, {len(rm_list)} phòng.')