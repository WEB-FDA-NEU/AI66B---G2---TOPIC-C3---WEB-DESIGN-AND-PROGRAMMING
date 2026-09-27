// ============================================================
//  Booking History — đọc mock/bookings.json qua getBookings(),
//  render bằng <template id="tpl-booking-row">, lọc theo tab,
//  huỷ booking qua confirmAction() + cancelBooking().
// ============================================================
import { getBookings, cancelBooking, ApiError } from '../api.js';
import { toast, confirmAction } from '../ui.js';
import { formatVND } from '../render.js';
import { isLoggedIn, requireLogin } from '../auth.js';
import '../components/site-header.js';
import '../components/site-footer.js';

if (!isLoggedIn()) requireLogin(); // Booking History chỉ dành cho user đã đăng nhập

const STATUS_LABEL = {
  pending: 'Chờ xác nhận', confirmed: 'Đã xác nhận', checked_in: 'Đã nhận phòng',
  completed: 'Hoàn thành', cancelled: 'Đã huỷ', rejected: 'Bị từ chối',
};
const STATUS_BADGE = {
  pending: 'badge--warning', confirmed: 'badge--success', checked_in: 'badge--success',
  cancelled: 'badge--danger', rejected: 'badge--danger',
}; // completed cố tình không có class riêng — dùng badge mặc định (xám)

const listEl  = document.getElementById('booking-list');
const emptyEl = document.getElementById('booking-empty');
const tplRow  = document.getElementById('tpl-booking-row');

let bookings = [];
let currentFilter = 'all';

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('vi-VN');
}

function renderRow(b) {
  const node = tplRow.content.cloneNode(true);

  node.querySelector('.row').dataset.status = b.status;
  node.querySelector('.row__img').src = b.homestayImage;
  node.querySelector('.row__img').alt = b.homestayName;

  const titleEl = node.querySelector('.row__title');
  titleEl.textContent = b.homestayName;
  titleEl.href = `booking-detail.html?id=${b.id}`;

  node.querySelector('.row__meta').textContent =
    `${b.roomName} · ${fmtDate(b.checkIn)} → ${fmtDate(b.checkOut)} (${b.nights} đêm)`;
  node.querySelector('.row__price').textContent = formatVND(b.totalPrice);

  const badge = node.querySelector('.badge');
  badge.textContent = STATUS_LABEL[b.status] ?? b.status;
  if (STATUS_BADGE[b.status]) badge.classList.add(STATUS_BADGE[b.status]);

  node.querySelector('.btn--outline').href = `booking-detail.html?id=${b.id}`;

  const cancelBtn = node.querySelector('[data-action="cancel"]');
  if (b.status === 'pending' || b.status === 'confirmed') {
    cancelBtn.hidden = false;
    cancelBtn.dataset.bookingId = b.id;
  }

  const reviewLink = node.querySelector('[data-review]');
  if (b.status === 'completed') {
    reviewLink.hidden = false;
    reviewLink.textContent = 'Viết đánh giá';
    reviewLink.href = `booking-detail.html?id=${b.id}#review`;
  }

  return node;
}

function renderList() {
  listEl.innerHTML = '';
  const filtered = currentFilter === 'all'
    ? bookings
    : bookings.filter(b => b.status === currentFilter);

  if (filtered.length === 0) {
    listEl.hidden = true;
    emptyEl.hidden = false;
  } else {
    listEl.hidden = false;
    emptyEl.hidden = true;
    filtered.forEach(b => listEl.appendChild(renderRow(b)));
  }
}

document.querySelectorAll('.tabs .btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelector('.tabs .btn.is-active')?.classList.remove('is-active');
    btn.classList.add('is-active');
    currentFilter = btn.dataset.filter;
    renderList();
  });
});

listEl.addEventListener('click', async e => {
  const btn = e.target.closest('[data-action="cancel"]');
  if (!btn) return;

  const ok = await confirmAction({
    title: 'Huỷ đặt phòng?',
    message: 'Bạn có chắc muốn huỷ đặt phòng này không?',
    confirmText: 'Huỷ đặt phòng',
  });
  if (!ok) return;

  try {
    await cancelBooking(btn.dataset.bookingId);
    toast('Đã huỷ đặt phòng.');
    await load();
  } catch (err) {
    toast(err instanceof ApiError ? err.detail : 'Không thể huỷ đặt phòng.', 'error');
  }
});

async function load() {
  try {
    bookings = await getBookings();
    renderList();
  } catch (err) {
    toast(err instanceof ApiError ? err.detail : 'Không tải được danh sách đặt phòng.', 'error');
  }
}

load();