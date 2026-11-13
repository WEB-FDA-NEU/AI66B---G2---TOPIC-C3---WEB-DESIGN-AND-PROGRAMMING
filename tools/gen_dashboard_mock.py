"""
Sinh dữ liệu mock cho Dashboard (Giai đoạn E). Chạy từ thư mục gốc dự án:
    python tools/gen_dashboard_mock.py frontend
- Thêm booking vào mock/host-bookings.json (GIỮ NGUYÊN bk001–bk030 cũ), trải đều T1 → giữa T11/2026.
- Tạo mock/admin-overview.json: user + booking toàn hệ thống (để vẽ đường tăng trưởng, cơ cấu theo tỉnh).
Dữ liệu sinh theo seed cố định nên chạy lại cho ra cùng kết quả. Không tạo trùng lịch cho một phòng.
"""
import json, random, sys
from datetime import date, datetime, timedelta
from pathlib import Path

root = Path(sys.argv[1] if len(sys.argv) > 1 else 'frontend')
mock = root / 'mock'
rnd = random.Random(2026)
TODAY = date(2026, 11, 13)           # "hôm nay" của dữ liệu mock
LAST_CREATED = date(2026, 11, 12)    # booking mới nhất

HO = ['Nguyễn', 'Trần', 'Lê', 'Phạm', 'Hoàng', 'Vũ', 'Đặng', 'Bùi', 'Đỗ', 'Ngô', 'Dương', 'Lý']
DEM = ['Văn', 'Thị', 'Minh', 'Quốc', 'Ngọc', 'Hữu', 'Thu', 'Gia', 'Thanh', 'Anh']
TEN = ['An', 'Bình', 'Châu', 'Dũng', 'Giang', 'Hà', 'Hiếu', 'Khoa', 'Lan', 'Linh', 'Mai', 'Nam', 'Phúc', 'Quân', 'Trang', 'Tú', 'Vy', 'Yến']
name = lambda: f"{rnd.choice(HO)} {rnd.choice(DEM)} {rnd.choice(TEN)}"
phone = lambda: '09' + ''.join(str(rnd.randint(0, 9)) for _ in range(8))
iso = lambda d, h=None: f"{d.isoformat()}T{(h if h is not None else rnd.randint(1, 20)):02d}:{rnd.randint(0,59):02d}:00Z"
D = lambda s: date.fromisoformat(s[:10])

# mùa vụ: tháng cao điểm đặt nhiều hơn (hệ số theo tháng của ngày ĐẶT)
SEASON = {1: .7, 2: .8, 3: .9, 4: 1.1, 5: 1.2, 6: 1.5, 7: 1.6, 8: 1.4, 9: 1.1, 10: 1.2, 11: 1.4}
def rand_created(first, last):
    days = (last - first).days
    while True:
        d = first + timedelta(days=rnd.randint(0, days))
        if rnd.random() < SEASON[d.month] / 1.6:
            return d

def pick_created(first):
    if rnd.random() < .07:   # 7% booking mới trong 30 ngày gần đây (nghiêng về những ngày cuối) — đủ để lọc 7 ngày vẫn có số liệu
        return LAST_CREATED - timedelta(days=int((rnd.random() ** 1.6) * 30))
    return rand_created(first, LAST_CREATED)

def status_for(created, cin, cout):
    r = rnd.random()
    if r < .07: return 'cancelled'
    if r < .10: return 'rejected'
    if cout <= TODAY: return 'completed'
    if cin <= TODAY: return 'checked_in'
    return 'pending' if (cin - TODAY).days > 3 and r < .35 else 'confirmed'

# ───────── 1) host-bookings.json ─────────
hb_path = mock / 'host-bookings.json'
hb = json.loads(hb_path.read_text(encoding='utf-8'))
hb['bookings'] = [b for b in hb['bookings'] if int(b['id'][2:]) <= 30]   # chỉ giữ 30 booking gốc → chạy lại không bị nhân đôi
rooms = json.loads((mock / 'host-rooms.json').read_text(encoding='utf-8'))['rooms']
price = {r['id']: r['pricePerNight'] for r in rooms}
busy = {r['id']: [] for r in rooms}      # các khoảng [in, out) đang chiếm phòng
for b in hb['bookings']:
    if b['status'] in ('confirmed', 'checked_in', 'completed'):
        busy[b['roomId']].append((D(b['checkIn']), D(b['checkOut'])))
for r in rooms:                           # ngày chặn do host (blockedDates) cũng tính là bận
    for s in r.get('blockedDates', []): busy[r['id']].append((D(s), D(s) + timedelta(days=1)))

existing = {b['id'] for b in hb['bookings'] if b['id'].startswith('bk')}
n = max(int(i[2:]) for i in existing)
new = []
target = 520
tries = 0
while len(new) < target and tries < 80000:
    tries += 1
    created = pick_created(date(2026, 1, 4))
    cin = created + timedelta(days=rnd.randint(2, 40))
    cout = cin + timedelta(days=rnd.choice([2, 2, 3, 3, 4, 5]))
    room = rnd.choice(rooms)['id']
    st = status_for(created, cin, cout)
    holds = st in ('confirmed', 'checked_in', 'completed')
    if holds and any(cin < o and i < cout for i, o in busy[room]): continue
    if holds: busy[room].append((cin, cout))
    n += 1
    new.append({
        'id': f'bk{n:03d}', 'roomId': room, 'customerName': name(), 'customerPhone': phone(),
        'checkIn': cin.isoformat(), 'checkOut': cout.isoformat(), 'guests': rnd.randint(1, 3),
        'totalPrice': price[room] * (cout - cin).days, 'status': st,
        'rejectReason': 'Phòng đang bảo trì' if st == 'rejected' else '',
        'createdAt': iso(created),
    })
hb['bookings'] = hb['bookings'] + sorted(new, key=lambda b: b['createdAt'])
hb_path.write_text(json.dumps(hb, ensure_ascii=False, indent=2), encoding='utf-8')

# ───────── 2) admin-overview.json (toàn hệ thống) ─────────
items = json.loads((mock / 'items.json').read_text(encoding='utf-8'))['items']
users = []
for k in range(1, 101):
    # số user đăng ký tăng dần theo thời gian: lấy mẫu lệch về cuối năm
    d = date(2026, 1, 2) + timedelta(days=int(((LAST_CREATED - date(2026, 1, 2)).days) * (rnd.random() ** .62)))
    users.append({'id': f'u{k:03d}', 'createdAt': iso(d), 'role': 'host' if k % 12 == 0 else 'user'})
users.sort(key=lambda u: u['createdAt'])
for k, u in enumerate(users, 1): u['id'] = f'u{k:03d}'

weight = {1: 1.0, 2: .9, 3: .85, 4: .8, 5: .6, 6: .6, 7: .7, 8: .5, 9: .55, 10: .45}   # Sa Pa, Hội An... đặt nhiều hơn
bookings = []
for k in range(1, 901):
    it = rnd.choices(items, weights=[weight.get(i['id'], .5) for i in items])[0]
    created = pick_created(date(2026, 1, 3))
    nights = rnd.choice([2, 2, 3, 3, 4, 5])
    cin = created + timedelta(days=rnd.randint(2, 40))
    cout = cin + timedelta(days=nights)
    bookings.append({'id': f'ab{k:03d}', 'itemId': it['id'], 'createdAt': iso(created),
                     'status': status_for(created, cin, cout), 'totalPrice': it['price'] * nights})
bookings.sort(key=lambda b: b['createdAt'])
for k, b in enumerate(bookings, 1): b['id'] = f'ab{k:03d}'

(mock / 'admin-overview.json').write_text(json.dumps({
    '_ghi_chu': 'Số liệu toàn hệ thống cho Admin Dashboard (user + booking, có ngày tạo) — sinh bằng tools/gen_dashboard_mock.py. '
                'Backend thật thay bằng GET /admin/overview. Tỉnh/thành lấy từ location của mock/items.json theo itemId.',
    'users': users, 'bookings': bookings}, ensure_ascii=False, indent=2), encoding='utf-8')

print('host-bookings:', len(hb['bookings']), '(thêm', len(new), ')  admin users:', len(users), ' admin bookings:', len(bookings))