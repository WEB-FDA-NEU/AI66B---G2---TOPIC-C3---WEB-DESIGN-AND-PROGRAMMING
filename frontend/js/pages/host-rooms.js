
import { getHostHomestays, getHostRooms, saveHostRoom, deleteHostRoom } from '../api.js';
import { formatVND } from '../render.js';
import { setFieldError, clearFieldErrors, confirmAction, toast } from '../ui.js';
import '../components/site-header.js';
import '../components/site-footer.js';
import '../guard.js';

import { ACCOUNT_API_MODE, safeImageURL } from '../config.js';

if (ACCOUNT_API_MODE) {
  const { initHostRooms } = await import('./api-host-rooms.js');
  await initHostRooms();
} else {
const $ = id => document.getElementById(id);

const q = new URLSearchParams(location.search);

let homestayId = q.get('homestayId');
let blockedDates = [];
let roomImages = []; // data URL xem trước, tối đa 6 ảnh/phòng

// ==================== ẢNH PHÒNG ====================

function renderRoomPreview() {
  $('rPreview').replaceChildren(...roomImages.map((src, i) => {
    const wrapper = document.createElement('div'); wrapper.className = 'thumb';
    const image = document.createElement('img'); image.className = 'thumb__img'; image.src = safeImageURL(src); image.alt = `\u1ea2nh ph\u00f2ng ${i + 1}`;
    const remove = document.createElement('button'); remove.className = 'thumb__remove'; remove.type = 'button'; remove.dataset.ri = i; remove.textContent = '\u00d7'; remove.setAttribute('aria-label', 'X\u00f3a \u1ea3nh');
    remove.onclick = () => { roomImages.splice(i, 1); renderRoomPreview(); };
    wrapper.append(image, remove); return wrapper;
  }));
}

$('rImages').addEventListener('change', async e => {
  const files = [...e.target.files].slice(0, 6 - roomImages.length);

  for (const f of files) {
    roomImages.push(await new Promise(res => {
      const r = new FileReader();
      r.onload = () => res(r.result);
      r.readAsDataURL(f);
    }));
  }

  e.target.value = '';

  $('rImagesErr').textContent =
    roomImages.length >= 6 ? 'Đã đạt tối đa 6 ảnh.' : '';

  renderRoomPreview();
});

// ==================== NGÀY BỊ CHẶN ====================

function renderBlockList() {
  $('blockList').replaceChildren(...blockedDates.map(date => {
    const tag = document.createElement('span'); tag.className = 'tag'; tag.textContent = date;
    const remove = document.createElement('button'); remove.type = 'button'; remove.dataset.d = date; remove.textContent = '\u00d7'; remove.setAttribute('aria-label', `X\u00f3a ng\u00e0y ${date}`);
    remove.onclick = () => { blockedDates = blockedDates.filter(value => value !== date); renderBlockList(); };
    tag.append(remove); return tag;
  }));
}

$('addBlockDate').addEventListener('click', () => {
  const v = $('rBlockDate').value;

  if (v && !blockedDates.includes(v)) {
    blockedDates.push(v);
    blockedDates.sort();
    renderBlockList();
  }

  $('rBlockDate').value = '';
});

// ==================== FORM THÊM / SỬA PHÒNG ====================

function openForm(room = null) {
  $('roomForm').classList.add('is-open');

  $('roomFormTitle').textContent = room ? 'Sửa phòng' : 'Thêm phòng';

  $('roomId').value = room?.id || '';
  $('rName').value = room?.name || '';
  $('rDesc').value = room?.description || '';
  $('rCap').value = room?.capacity || 2;
  $('rPrice').value = room?.pricePerNight || '';

  blockedDates = [...(room?.blockedDates || [])];
  renderBlockList();

  roomImages = room?.images && room.images[0] !== 'img/placeholder.svg'
    ? [...room.images]
    : [];

  $('rImagesErr').textContent = '';

  renderRoomPreview();

  $('roomForm').scrollIntoView({
    behavior: 'smooth',
    block: 'center'
  });
}

$('addBtn').addEventListener('click', () => openForm());

$('cancelRoomForm').addEventListener('click', () => {
  $('roomForm').classList.remove('is-open');
});

// ==================== LƯU PHÒNG ====================

$('roomForm').addEventListener('submit', async e => {
  e.preventDefault();

  clearFieldErrors($('roomForm'));

  let ok = true;

  if (!$('rName').value.trim()) {
    setFieldError($('rName'), 'Vui lòng nhập tên phòng.');
    ok = false;
  }

  if (!$('rDesc').value.trim()) {
    setFieldError($('rDesc'), 'Vui lòng nhập mô tả.');
    ok = false;
  }

  if (!$('rCap').value || +$('rCap').value < 1) {
    setFieldError($('rCap'), 'Sức chứa phải ≥ 1.');
    ok = false;
  }

  if (!$('rPrice').value || +$('rPrice').value < 0) {
    setFieldError($('rPrice'), 'Vui lòng nhập giá hợp lệ.');
    ok = false;
  }

  if (!ok) return;

  try {
    await saveHostRoom({
      id: $('roomId').value || undefined,
      homestayId,
      name: $('rName').value.trim(),
      description: $('rDesc').value.trim(),
      capacity: +$('rCap').value,
      pricePerNight: +$('rPrice').value,
      images: roomImages.length
        ? roomImages
        : ['img/placeholder.svg'],
      blockedDates,
    });

    toast('Đã lưu phòng.');

    $('roomForm').classList.remove('is-open');

    render();

  } catch (e2) {
    toast(e2.detail ?? 'Không lưu được phòng.', 'error');
  }
});

// ==================== HIỂN THỊ DANH SÁCH PHÒNG ====================

async function render() {
  try {
    const homestays = await getHostHomestays();

    if (!homestayId) {
      homestayId = homestays[0]?.id;
    }

    const homestay = homestays.find(h => h.id === homestayId);

    if (!homestay) {
      $('homestayName').textContent = 'Bạn chưa có homestay nào.';
      $('list').innerHTML = '';
      $('addBtn').disabled = true;
      return;
    }

    $('homestayName').replaceChildren();
    if (homestays.length > 1) {
      const label = document.createElement('span'); label.textContent = 'Homestay:';
      const select = document.createElement('select'); select.id = 'hsSwitch'; select.className = 'input host-room-homestay-select';
      for (const h of homestays) select.add(new Option(h.name, h.id)); select.value = homestayId;
      $('homestayName').append(label, select);
    } else $('homestayName').textContent = homestay.name;

    document.getElementById('hsSwitch')?.addEventListener('change', e => {
      homestayId = e.target.value;
      render();
    });

    const rooms = await getHostRooms(homestayId);

    const make = (tag, cls, text) => { const el = document.createElement(tag); el.className = cls; if (text !== undefined) el.textContent = text; return el; };
    $('list').replaceChildren(...rooms.map(room => {
      const card = make('article', 'host-room-card');
      const image = make('img', 'row__img host-room-card__img'); image.src = safeImageURL(room.images?.[0] || 'img/placeholder.svg'); image.alt = room.name;
      image.onerror = () => { image.onerror = null; image.src = 'img/placeholder.svg'; };
      const info = make('div', 'host-room-card__info');
      info.append(make('p','row__title',room.name),make('p','row__meta host-room-card__description',room.description),
        make('p','row__meta',`T\u1ed1i \u0111a ${room.capacity} kh\u00e1ch${room.blockedDates?.length ? ` \u00b7 ${room.blockedDates.length} ng\u00e0y b\u1ecb ch\u1eb7n` : ''}`),
        make('p','row__price',`${formatVND(room.pricePerNight)} / \u0111\u00eam`));
      const actions = make('div','row__actions host-room-card__actions');
      const edit = make('button','btn','S\u1eeda'); edit.type = 'button'; edit.dataset.edit = room.id;
      const remove = make('button','btn btn--danger','X\u00f3a'); remove.type = 'button'; remove.dataset.del = room.id; remove.dataset.name = room.name;
      actions.append(edit,remove); card.append(image,info,actions); return card;
    }));
    if (!rooms.length) {
      const empty = make('div', 'empty host-rooms-empty');
      empty.append(make('p','empty__title','Homestay n\u00e0y ch\u01b0a c\u00f3 ph\u00f2ng n\u00e0o'), make('p','empty__hint','Th\u00eam ph\u00f2ng \u0111\u1ec3 kh\u00e1ch c\u00f3 th\u1ec3 \u0111\u1eb7t.'));
      $('list').append(empty);
    }

    // Xử lý nút sửa
    $('list').querySelectorAll('[data-edit]').forEach(b =>
      b.addEventListener('click', () => {
        openForm(rooms.find(r => r.id === b.dataset.edit));
      })
    );

    // Xử lý nút xóa
    $('list').querySelectorAll('[data-del]').forEach(b =>
      b.addEventListener('click', async () => {

        const ok = await confirmAction({
          title: 'Xóa phòng?',
          message: `Xóa "${b.dataset.name}"? Không thể hoàn tác.`,
          confirmText: 'Xóa'
        });

        if (!ok) return;

        try {
          await deleteHostRoom(b.dataset.del);

          toast('Đã xóa phòng.');

          render();

        } catch (e3) {
          toast(e3.detail ?? 'Không xóa được.', 'error');
        }
      })
    );

  } catch (e) {
    $('list').innerHTML = `
      <p class="text-danger">
        Không tải được dữ liệu.
      </p>
    `;

    console.error(e);
  }
}

render();

}
