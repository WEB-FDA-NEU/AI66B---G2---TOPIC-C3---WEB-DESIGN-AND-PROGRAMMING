"""
Thay ảnh homestay trong mock bằng ảnh local, KHÔNG phải viết lại dữ liệu.

Cách dùng (chạy từ thư mục gốc dự án):
    python tools/apply_mock_images.py            # áp dụng
    python tools/apply_mock_images.py --check    # chỉ báo cáo, không ghi file

Quy ước thư mục ảnh: frontend/img/homestays/<id homestay>/ chứa 3-5 ảnh (jpg/jpeg/png/webp).
Ví dụ: frontend/img/homestays/1/a.jpg, b.jpg, c.jpg  ->  homestay id 1 (Sapa Misty Hills).
Ảnh được xếp theo tên file; ảnh đầu tiên là ảnh bìa. Đặt tên 1.jpg, 2.jpg, 3.jpg cho dễ kiểm soát.

Homestay nào chưa có thư mục thì GIỮ NGUYÊN ảnh cũ (làm dần được).

Script cập nhật cùng lúc 4 file để các nơi luôn khớp nhau:
  - mock/items.json          cover_url + images
  - mock/host-homestays.json images (nối qua itemId, hoặc theo tên nếu thiếu itemId)
  - mock/host-rooms.json     images của từng phòng (xoay vòng ảnh của homestay)
  - mock/bookings.json       homestayImage
và tự tăng MOCK_DATA_VERSION trong js/api.js để trình duyệt nạp lại dữ liệu.

LƯU Ý: không chạy lại tools/add_mock_homestays.py sau script này, vì nó sinh lại id 11-22
với ảnh mượn. Nếu lỡ chạy, chạy lại apply_mock_images.py là xong.
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONT = ROOT / 'frontend'
MOCK = FRONT / 'mock'
EXT = {'.jpg', '.jpeg', '.png', '.webp'}
CHECK = '--check' in sys.argv


def load(name):
    return json.loads((MOCK / name).read_text(encoding='utf-8'))


def save(name, data):
    if not CHECK:
        (MOCK / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def folder_images():
    """{id homestay: ['img/homestays/1/1.jpg', ...]} - đường dẫn tương đối so với frontend/."""
    found = {}
    base = FRONT / 'img' / 'homestays'
    if not base.is_dir():
        return found
    for d in sorted(base.iterdir()):
        if not (d.is_dir() and d.name.isdigit()):
            continue
        files = sorted(f for f in d.iterdir() if f.suffix.lower() in EXT)
        if files:
            found[int(d.name)] = [f.relative_to(FRONT).as_posix() for f in files]
    return found


def room_images(imgs, k):
    """Phòng thứ k lấy 2 ảnh xoay vòng, giống cách tools/add_mock_homestays.py làm."""
    if len(imgs) < 3:
        return list(imgs)
    return [imgs[(k + 1) % len(imgs)], imgs[(k + 2) % len(imgs)]]


def main():
    imgs_by_id = folder_images()
    items_doc = load('items.json')
    items = items_doc['items']
    all_ids = {i['id']: i['title'] for i in items}

    missing = [f'{i} {t}' for i, t in all_ids.items() if i not in imgs_by_id]
    unknown = [i for i in imgs_by_id if i not in all_ids]
    thin = [f'{i} ({len(v)} ảnh)' for i, v in imgs_by_id.items() if len(v) < 3]

    # 1) items.json
    for it in items:
        imgs = imgs_by_id.get(it['id'])
        if imgs:
            it['cover_url'], it['images'] = imgs[0], list(imgs)
    save('items.json', items_doc)

    # 2) host-homestays.json  (hs -> item id)
    hs_doc = load('host-homestays.json')
    title_to_id = {t: i for i, t in all_ids.items()}
    hs_item = {}
    for h in hs_doc['homestays']:
        item_id = h.get('itemId') or title_to_id.get(h['name'])
        hs_item[h['id']] = item_id
        if item_id in imgs_by_id:
            h['images'] = list(imgs_by_id[item_id])
    save('host-homestays.json', hs_doc)

    # 3) host-rooms.json
    rooms_doc = load('host-rooms.json')
    counter = {}
    for r in rooms_doc['rooms']:
        item_id = hs_item.get(r['homestayId'])
        k = counter.get(r['homestayId'], 0)
        counter[r['homestayId']] = k + 1
        if item_id in imgs_by_id:
            r['images'] = room_images(imgs_by_id[item_id], k)
    save('host-rooms.json', rooms_doc)

    # 4) bookings.json
    bk_doc = load('bookings.json')
    for b in bk_doc['customerBookings']:
        if b.get('homestayId') in imgs_by_id:
            b['homestayImage'] = imgs_by_id[b['homestayId']][0]
    save('bookings.json', bk_doc)

    # 5) tăng MOCK_DATA_VERSION
    api = FRONT / 'js' / 'api.js'
    text = api.read_text(encoding='utf-8')
    version = f"{date.today().isoformat()}-img"
    new_text, n = re.subn(r"(const MOCK_DATA_VERSION = ')[^']*(')", rf"\g<1>{version}\g<2>", text, count=1)
    if n and not CHECK:
        api.write_text(new_text, encoding='utf-8')

    # Báo cáo
    left = sum(p.read_text(encoding='utf-8').count('bstatic.com') for p in MOCK.glob('*.json'))
    print(('[CHECK - chưa ghi file] ' if CHECK else '') + f'Đã áp ảnh cho {len(imgs_by_id)}/{len(all_ids)} homestay.')
    if missing:
        print('Chưa có thư mục ảnh (giữ ảnh cũ):', '; '.join(missing))
    if unknown:
        print('Thư mục không khớp homestay nào:', unknown)
    if thin:
        print('Ít hơn 3 ảnh (nên bổ sung):', '; '.join(thin))
    print(f'Còn {left} link bstatic.com (ảnh Booking.com) trong mock.')
    if n:
        print(f'MOCK_DATA_VERSION -> {version}' if not CHECK else f'(sẽ đặt MOCK_DATA_VERSION -> {version})')
    else:
        print('Không tìm thấy MOCK_DATA_VERSION trong js/api.js, hãy tự tăng thủ công.')


if __name__ == '__main__':
    main()