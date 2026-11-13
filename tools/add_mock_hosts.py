"""
Tạo dữ liệu host cho trang Admin. Chạy từ thư mục gốc dự án (sau add_mock_homestays.py):
    python tools/add_mock_hosts.py frontend

Ghi:
  - mock/admin-hosts.json    : hồ sơ 9 host + danh sách itemIds (homestay) mỗi người sở hữu
  - mock/admin-overview.json : thêm booking ab901+ cho homestay 11–22 (để host sở hữu các homestay này có số liệu)
Host u012…u083 chính là 8 user role "host" đã có sẵn trong admin-overview.json; host001 khớp mock/users.json.
Chạy lại nhiều lần vẫn an toàn (booking ab901+ được sinh lại theo seed cố định).
"""
import json, random, sys
from datetime import date, timedelta
from pathlib import Path

mock = Path(sys.argv[1] if len(sys.argv) > 1 else 'frontend') / 'mock'
load = lambda n: json.loads((mock / n).read_text(encoding='utf-8'))
def save(n, d): (mock / n).write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

ov = load('admin-overview.json')
items = {i['id']: i for i in load('items.json')['items']}
host_created = {u['id']: u['createdAt'] for u in ov['users'] if u['role'] == 'host'}

# id, tên, email, số điện thoại, homestay sở hữu (itemIds). Dữ liệu giả, dùng cho demo.
HOSTS = [
    ('host001', 'Trần Văn Host',   'host@test.com',            '0912345678', [1, 2, 3, 4, 5, 6, 7, 8, 9], '2026-07-20T03:00:00Z'),
    ('u012', 'Lê Văn Hùng',        'hung.le@example.com',      '0903456721', [10, 11]),
    ('u028', 'Phạm Thị Lan',       'lan.pham@example.com',     '0918234567', [12, 17]),
    ('u035', 'Võ Minh Tuấn',       'tuan.vo@example.com',      '0987123456', [13, 21]),
    ('u037', 'Đặng Thu Hà',        'ha.dang@example.com',      '0934567812', [14, 16]),
    ('u042', 'Hoàng Quốc Bảo',     'bao.hoang@example.com',    '0976543210', [15, 18]),
    ('u055', 'Bùi Ngọc Anh',       'anh.bui@example.com',      '0965432178', [19]),
    ('u056', 'Ngô Thanh Sơn',      'son.ngo@example.com',      '0945678123', [20, 22]),
    ('u083', 'Đỗ Khánh Linh',      'linh.do@example.com',      '0356781234', []),   # host mới, chưa đăng homestay
]
hosts = []
for h in HOSTS:
    hid, name, email, phone, item_ids = h[:5]
    created = h[5] if len(h) > 5 else host_created[hid]
    assert all(i in items for i in item_ids), f'itemId không tồn tại: {item_ids}'
    hosts.append({'id': hid, 'display_name': name, 'email': email, 'phone': phone,
                  'avatar': 'img/anh_dai_dien.jpg' if hid == 'host001' else 'img/placeholder.svg',
                  'createdAt': created, 'itemIds': item_ids})
owned = [i for h in hosts for i in h['itemIds']]
assert len(owned) == len(set(owned)), 'một homestay thuộc 2 host'
save('admin-hosts.json', {
    '_ghi_chu': 'Hồ sơ host cho Admin. Backend thật thay bằng GET /admin/hosts (cùng dạng sau khi ghép). '
                'itemIds ↔ mock/items.json; host001 ↔ mock/users.json.', 'hosts': hosts})

# ───── Booking cho homestay 11–22 ─────
rnd = random.Random(2027)
LAST = date(2026, 11, 12)
bookings = [b for b in ov['bookings'] if not (b['id'].startswith('ab') and int(b['id'][2:]) >= 901)]
n = 901
for iid in range(11, 23):
    it = items[iid]
    first = date.fromisoformat(it['created_at'][:10]) + timedelta(days=1)
    span = (LAST - first).days
    for _ in range(rnd.randint(8, 22)):
        created = first + timedelta(days=rnd.randint(0, span))
        r = rnd.random()
        status = ('cancelled' if r < .07 else 'rejected' if r < .10 else
                  'completed' if r < .70 else 'confirmed' if r < .90 else 'pending')
        nights = rnd.randint(1, 4)
        bookings.append({'id': f'ab{n}', 'itemId': iid,
                         'createdAt': f'{created.isoformat()}T{rnd.randint(1, 20):02d}:{rnd.randint(0, 59):02d}:00Z',
                         'status': status, 'totalPrice': round(it['price'] * nights * 1.05 / 1000) * 1000})
        n += 1
ov['bookings'] = bookings
save('admin-overview.json', ov)
print(f'OK: {len(hosts)} host, {len(bookings)} booking toàn hệ thống.')