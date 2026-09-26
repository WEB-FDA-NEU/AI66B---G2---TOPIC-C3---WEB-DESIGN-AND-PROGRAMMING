import { getHostBookings, getHostRooms, getHostHomestays, updateBookingStatus } from '../api.js';
import { formatVND } from '../render.js';
import { toast } from '../ui.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const $ = id => document.getElementById(id);
const STATUS_LABEL = { pending: 'Chờ xác nhận', confirmed: 'Đã xác nhận', checked_in: 'Đã nhận phòng',
  completed: 'Hoàn tất', cancelled: 'Đã hủy', rejected: 'Bị từ chối' };
const STATUS_BADGE = { pending: 'badge--warning', confirmed: 'badge--success', checked_in: 'badge--success',
  completed: '', cancelled: 'badge--danger', rejected: 'badge--danger' };
// Bước tiếp theo hợp lệ cho từng trạng thái — theo docs/api-contract.md
const NEXT_STEP = { pending: 'confirmed', confirmed: 'checked_in', checked_in: 'completed' };
const NEXT_LABEL = { confirmed: 'Xác nhận', checked_in: 'Nhận phòng', completed: 'Hoàn tất' };

let bookings = [], rooms = [], homestays = [], filter = '';

async function loadData() {
  [bookings, rooms, homestays] = await Promise.all([getHostBookings(), getHostRooms(), getHostHomestays()]);
}

function render() {
  const roomsById = Object.fromEntries(rooms.map(r => [r.id, r]));
  const hsById = Object.fromEntries(homestays.map(h => [h.id, h]));
  const list = filter ? bookings.filter(b => b.status === filter) : bookings;
  const sorted = [...list].sort((a, b) => b.createdAt.localeCompare(a.createdAt));

  if (!sorted.length) {
    $('list').innerHTML = `<div class="empty"><p class="empty__title">Không có đặt phòng nào</p>
      <p class="empty__hint">${filter ? 'Không có đặt phòng ở trạng thái này.' : 'Chưa có khách đặt phòng nào của bạn.'}</p></div>`;
    return;
  }

  $('list').innerHTML = sorted.map(b => {
    const room = roomsById[b.roomId];
    const hs = room ? hsById[room.homestayId] : null;
    const next = NEXT_STEP[b.status];
    return `<div class="row" style="grid-template-columns:1fr auto">
      <div>
        <p class="row__title">${b.customerName} <span class="text-muted">— ${b.customerPhone || ''}</span></p>
        <p class="row__meta">${hs ? hs.name : ''} · ${room ? room.name : ''}</p>
        <p class="row__meta">📅 ${b.checkIn} → ${b.checkOut} · ${b.guests} khách</p>
        ${b.status === 'rejected' && b.rejectReason ? `<p class="row__meta text-danger">Lý do từ chối: ${b.rejectReason}</p>` : ''}
      </div>
      <div style="text-align:right">
        <span class="badge ${STATUS_BADGE[b.status]}">${STATUS_LABEL[b.status]}</span>
        <p class="row__price mt-3">${formatVND(b.totalPrice)}</p>
        <div class="row__actions mt-3" style="justify-content:flex-end">
          ${next ? `<button class="btn btn--primary" data-act="${b.id}:${next}">${NEXT_LABEL[next]}</button>` : ''}
          ${b.status === 'pending' ? `<button class="btn btn--danger" data-reject="${b.id}">Từ chối</button>` : ''}
        </div>
      </div>
    </div>`;
  }).join('');

  $('list').querySelectorAll('[data-act]').forEach(btn => btn.addEventListener('click', async () => {
    const [id, status] = btn.dataset.act.split(':');
    try { await updateBookingStatus(id, status); toast('Đã cập nhật trạng thái.'); await loadData(); render(); }
    catch (e) { toast(e.detail ?? 'Không cập nhật được.', 'error'); }
  }));
  $('list').querySelectorAll('[data-reject]').forEach(btn => btn.addEventListener('click', () => openReject(btn.dataset.reject)));
}

let rejectingId = null;
function openReject(id) {
  rejectingId = id;
  $('rejectReason').value = '';
  $('rejectErr').textContent = '';
  $('reject-dialog').showModal();
}
$('rejectCancel').addEventListener('click', () => $('reject-dialog').close());
$('rejectConfirm').addEventListener('click', async () => {
  const reason = $('rejectReason').value.trim();
  if (!reason) { $('rejectErr').textContent = 'Vui lòng nhập lý do từ chối.'; return; }
  try {
    await updateBookingStatus(rejectingId, 'rejected', reason);
    $('reject-dialog').close();
    toast('Đã từ chối đặt phòng.');
    await loadData(); render();
  } catch (e) { $('rejectErr').textContent = e.detail ?? 'Không thực hiện được.'; }
});

$('tabs').addEventListener('click', e => {
  const btn = e.target.closest('button[data-status]');
  if (!btn) return;
  $('tabs').querySelectorAll('button').forEach(b => b.classList.remove('is-active'));
  btn.classList.add('is-active');
  filter = btn.dataset.status;
  render();
});

loadData().then(render).catch(e => { $('list').innerHTML = `<p class="text-danger">Không tải được dữ liệu.</p>`; console.error(e); });
