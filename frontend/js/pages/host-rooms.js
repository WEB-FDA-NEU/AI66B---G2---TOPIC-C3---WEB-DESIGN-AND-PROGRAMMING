import { getHostHomestays, getHostRooms, saveHostRoom, deleteHostRoom } from '../api.js';
import { formatVND } from '../render.js';
import { setFieldError, clearFieldErrors, confirmAction, toast } from '../ui.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const $ = id => document.getElementById(id);
const q = new URLSearchParams(location.search);
let homestayId = q.get('homestayId');
let blockedDates = [];
let roomImages = []; // data URL xem trước, tối đa 6 ảnh/phòng

function renderRoomPreview() {
  $('rPreview').innerHTML = roomImages.map((src, i) => `
    <div class="thumb"><img class="thumb__img" src="${src}" alt="Ảnh phòng ${i + 1}">
      <button class="thumb__remove" type="button" data-ri="${i}" aria-label="Xóa ảnh">×</button></div>`).join('');
  $('rPreview').querySelectorAll('[data-ri]').forEach(b =>
    b.addEventListener('click', () => { roomImages.splice(+b.dataset.ri, 1); renderRoomPreview(); }));
}
$('rImages').addEventListener('change', async e => {
  const files = [...e.target.files].slice(0, 6 - roomImages.length);
  for (const f of files) {
    roomImages.push(await new Promise(res => { const r = new FileReader(); r.onload = () => res(r.result); r.readAsDataURL(f); }));
  }
  e.target.value = '';
  $('rImagesErr').textContent = roomImages.length >= 6 ? 'Đã đạt tối đa 6 ảnh.' : '';
  renderRoomPreview();
});

function renderBlockList() {
  $('blockList').innerHTML = blockedDates.map(d => `<span class="tag">${d}<button type="button" data-d="${d}">×</button></span>`).join('');
  $('blockList').querySelectorAll('[data-d]').forEach(b =>
    b.addEventListener('click', () => { blockedDates = blockedDates.filter(x => x !== b.dataset.d); renderBlockList(); }));
}
$('addBlockDate').addEventListener('click', () => {
  const v = $('rBlockDate').value;
  if (v && !blockedDates.includes(v)) { blockedDates.push(v); blockedDates.sort(); renderBlockList(); }
  $('rBlockDate').value = '';
});

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
  roomImages = room?.images && room.images[0] !== 'img/placeholder.svg' ? [...room.images] : [];
  $('rImagesErr').textContent = '';
  renderRoomPreview();
  $('roomForm').scrollIntoView({ behavior: 'smooth', block: 'center' });
}
$('addBtn').addEventListener('click', () => openForm());
$('cancelRoomForm').addEventListener('click', () => $('roomForm').classList.remove('is-open'));

$('roomForm').addEventListener('submit', async e => {
  e.preventDefault();
  clearFieldErrors($('roomForm'));
  let ok = true;
  if (!$('rName').value.trim()) { setFieldError($('rName'), 'Vui lòng nhập tên phòng.'); ok = false; }
  if (!$('rDesc').value.trim()) { setFieldError($('rDesc'), 'Vui lòng nhập mô tả.'); ok = false; }
  if (!$('rCap').value || +$('rCap').value < 1) { setFieldError($('rCap'), 'Sức chứa phải ≥ 1.'); ok = false; }
  if (!$('rPrice').value || +$('rPrice').value < 0) { setFieldError($('rPrice'), 'Vui lòng nhập giá hợp lệ.'); ok = false; }
  if (!ok) return;

  try {
    await saveHostRoom({
      id: $('roomId').value || undefined, homestayId,
      name: $('rName').value.trim(), description: $('rDesc').value.trim(),
      capacity: +$('rCap').value, pricePerNight: +$('rPrice').value,
      images: roomImages.length ? roomImages : ['img/placeholder.svg'], blockedDates,
    });
    toast('Đã lưu phòng.');
    $('roomForm').classList.remove('is-open');
    render();
  } catch (e2) { toast(e2.detail ?? 'Không lưu được phòng.', 'error'); }
});

async function render() {
  try {
    const homestays = await getHostHomestays();
    if (!homestayId) homestayId = homestays[0]?.id;
    const homestay = homestays.find(h => h.id === homestayId);
    if (!homestay) { $('homestayName').textContent = 'Bạn chưa có homestay nào.'; $('list').innerHTML = ''; $('addBtn').disabled = true; return; }

    $('homestayName').innerHTML = homestays.length > 1
      ? `Homestay: <select id="hsSwitch">${homestays.map(h => `<option value="${h.id}" ${h.id === homestayId ? 'selected' : ''}>${h.name}</option>`).join('')}</select>`
      : homestay.name;
    document.getElementById('hsSwitch')?.addEventListener('change', e => { homestayId = e.target.value; render(); });

    const rooms = await getHostRooms(homestayId);
    $('list').innerHTML = rooms.length ? rooms.map(r => `
      <div class="row" style="grid-template-columns:96px 1fr auto">
        <img class="row__img" src="${r.images?.[0] || 'img/placeholder.svg'}" alt="${r.name}">
        <div><p class="row__title">${r.name}</p>
          <p class="row__meta">${r.description}</p>
          <p class="row__meta">Tối đa ${r.capacity} khách${r.blockedDates?.length ? ` · ${r.blockedDates.length} ngày bị chặn` : ''}</p>
          <p class="row__price">${formatVND(r.pricePerNight)} / đêm</p></div>
        <div class="row__actions" style="flex-direction:column;align-items:flex-end">
          <button class="btn" data-edit="${r.id}" type="button">Sửa</button>
          <button class="btn btn--danger" data-del="${r.id}" data-name="${r.name}" type="button">Xóa</button>
        </div>
      </div>`).join('') : `<div class="empty"><p class="empty__title">Homestay này chưa có phòng nào</p>
        <p class="empty__hint">Thêm phòng để khách có thể đặt.</p></div>`;

    $('list').querySelectorAll('[data-edit]').forEach(b => b.addEventListener('click', () => openForm(rooms.find(r => r.id === b.dataset.edit))));
    $('list').querySelectorAll('[data-del]').forEach(b => b.addEventListener('click', async () => {
      const ok = await confirmAction({ title: 'Xóa phòng?', message: `Xóa "${b.dataset.name}"? Không thể hoàn tác.`, confirmText: 'Xóa' });
      if (!ok) return;
      try { await deleteHostRoom(b.dataset.del); toast('Đã xóa phòng.'); render(); }
      catch (e3) { toast(e3.detail ?? 'Không xóa được.', 'error'); }
    }));
  } catch (e) { $('list').innerHTML = `<p class="text-danger">Không tải được dữ liệu.</p>`; console.error(e); }
}
render();
