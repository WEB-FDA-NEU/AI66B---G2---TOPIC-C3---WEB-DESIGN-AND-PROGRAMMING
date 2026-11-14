// ============================================================
//  Booking History — đọc mock/bookings.json qua getBookings(),
//  render bằng <template id="tpl-booking-row">, lọc theo tab,
//  huỷ booking qua confirmAction() + cancelBooking().
// ============================================================
import { getBookings, cancelBooking, ApiError } from '../api.js';
import { ACCOUNT_API_MODE, accountHref, safeImageURL } from '../config.js';
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
let page = 1;
const pager = document.createElement('div'); pager.className='row__actions'; pager.id='booking-pages';
if(ACCOUNT_API_MODE) listEl.after(pager);
function renderPages() {
  if(!ACCOUNT_API_MODE)return;
  pager.replaceChildren();
  for(const [label,delta,disabled] of [['Trước',-1,page===1],['Sau',1,bookings.length<20]]) {
    const button=document.createElement('button');button.type='button';button.className='btn';button.textContent=label;button.disabled=disabled;
    button.addEventListener('click',()=>{page+=delta;load();});pager.append(button);
  }
}

function fmtDate(iso) {
  return new Date(iso).toLocaleDateString('vi-VN');
}

function renderRow(b) {
  const node = tplRow.content.cloneNode(true);

  node.querySelector('.row').dataset.status = b.status;
  node.querySelector('.row__img').src = safeImageURL(b.homestayImage);
  node.querySelector('.row__img').alt = b.homestayName;

  const titleEl = node.querySelector('.row__title');
  titleEl.textContent = b.homestayName;
  titleEl.href = accountHref(`booking-detail.html?id=${b.id}`);

  node.querySelector('.row__meta').textContent =
    `${b.roomName} · ${fmtDate(b.checkIn)} → ${fmtDate(b.checkOut)} (${b.nights} đêm)`;
  node.querySelector('.row__price').textContent = formatVND(b.totalPrice);

  const badge = node.querySelector('.badge');
  badge.textContent = STATUS_LABEL[b.status] ?? b.status;
  if (STATUS_BADGE[b.status]) badge.classList.add(STATUS_BADGE[b.status]);

  node.querySelector('.btn--outline').href = accountHref(`booking-detail.html?id=${b.id}`);

  const cancelBtn = node.querySelector('[data-action="cancel"]');
  if (b.status === 'pending' || b.status === 'confirmed') {
    cancelBtn.hidden = false;
    cancelBtn.dataset.bookingId = b.id;
  }

  const reviewLink = node.querySelector('[data-review]');
  if (b.status === 'completed') {
    reviewLink.hidden = false;
    reviewLink.textContent = 'Viết đánh giá';
    reviewLink.href = accountHref(`booking-detail.html?id=${b.id}#review-section`);
  }

  return node;
}

function updateTabCounts() {
  document.querySelectorAll('.tabs .btn').forEach(btn => {
    const filter = btn.dataset.filter;
    const count = filter === 'all' ? bookings.length : bookings.filter(b => b.status === filter).length;
    const countEl = btn.querySelector('.tab-count');
    if (countEl) countEl.textContent = !ACCOUNT_API_MODE && count > 0 ? count : '';
  });
}

function renderList() {
  listEl.innerHTML = '';
  const filtered = ACCOUNT_API_MODE || currentFilter === 'all'
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
  updateTabCounts();
}

function showLoadingSkeleton() {
  emptyEl.hidden = true;
  listEl.hidden = false;
  listEl.innerHTML = '';
  for (let i = 0; i < 3; i++) {
    const d = document.createElement('div');
    d.className = 'skeleton-card row-skeleton';
    listEl.appendChild(d);
  }
}

document.querySelectorAll('.tabs .btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelector('.tabs .btn.is-active')?.classList.remove('is-active');
    btn.classList.add('is-active');
    currentFilter = btn.dataset.filter;
    if(ACCOUNT_API_MODE){page=1;load();}else renderList();
  });
});

listEl.addEventListener('click', async e => {
  const btn = e.target.closest('[data-action="cancel"]');
  if (!btn) return;
  if(btn.disabled)return;

  const ok = await confirmAction({
    title: 'Huỷ đặt phòng?',
    message: 'Bạn có chắc muốn huỷ đặt phòng này không?',
    confirmText: 'Huỷ đặt phòng',
  });
  if (!ok || btn.disabled) return;
  btn.disabled = true;

  try {
    await cancelBooking(btn.dataset.bookingId);
    toast('Đã huỷ đặt phòng.');
    await load();
  } catch (err) {
    btn.disabled = false;
    toast(err instanceof ApiError ? err.detail : 'Không thể huỷ đặt phòng.', 'error');
  }
});

async function load() {
  showLoadingSkeleton();
  try {
    bookings = await getBookings(ACCOUNT_API_MODE ? {page,page_size:20,...(currentFilter==='all'?{}:{status:currentFilter})} : {});
    renderList();
    renderPages();
  } catch (err) {
    if(ACCOUNT_API_MODE && err.status===401){requireLogin();return;}
    toast(err instanceof ApiError ? err.detail : 'Không tải được danh sách đặt phòng.', 'error');
  }
}

load();
