// ============================================================
//  Booking Detail — đọc ?id= trên URL, lấy đúng booking qua
//  getBooking(id) rồi đổ dữ liệu vào các phần tử #bd-*.
// ============================================================
import { getBooking, getPayment, cancelBooking, ApiError } from '../api.js';
import { ACCOUNT_API_MODE, accountHref, safeImageURL } from '../config.js';
import { paymentText } from '../pricing.js';
import { toast, confirmAction } from '../ui.js';
import { formatVND } from '../render.js';
import { isLoggedIn, requireLogin } from '../auth.js';
import '../components/site-header.js';
import '../components/site-footer.js';
import '../guard.js';

if (!isLoggedIn()) requireLogin();

const STATUS_LABEL = {
  pending: 'Chờ xác nhận', confirmed: 'Đã xác nhận', checked_in: 'Đã nhận phòng',
  completed: 'Hoàn thành', cancelled: 'Đã huỷ', rejected: 'Bị từ chối',
};
const STATUS_BADGE = {
  pending: 'badge--warning', confirmed: 'badge--success', checked_in: 'badge--success',
  cancelled: 'badge--danger', rejected: 'badge--danger',
};
const STEPS = ['pending', 'confirmed', 'checked_in', 'completed'];

const $ = id => document.getElementById(id);
const bookingId = new URLSearchParams(location.search).get('id');

const fmtDate = iso => new Date(iso).toLocaleDateString('vi-VN');

function render(b) {
  document.title = `${b.homestayName} — Chi tiết đặt phòng`;
  $('bd-title').textContent = b.homestayName;
  $('bd-code').textContent  = b.code || '#BK' + String(b.id).padStart(6, '0');

  // Badge trạng thái
  const badge = $('bd-status');
  badge.className = 'badge ' + (STATUS_BADGE[b.status] ?? '');
  badge.textContent = STATUS_LABEL[b.status] ?? b.status;

  // Timeline: bật các bước đã đi qua; huỷ/từ chối thì tắt hết
  const cur = STEPS.indexOf(b.status);
  document.querySelectorAll('#bd-timeline [data-step]').forEach(el => {
    el.classList.toggle('is-active', cur >= 0 && STEPS.indexOf(el.dataset.step) <= cur);
  });

  // Homestay
  const img = $('bd-img');
  img.src = safeImageURL(b.homestayImage || 'img/placeholder.svg');
  img.alt = b.homestayName;
  img.onerror = () => { img.onerror = null; img.src = 'img/placeholder.svg'; };
  $('bd-name').textContent = b.homestayName;
  $('bd-name').href = `detail.html?id=${b.homestayId}`;
  $('bd-location').textContent = '📍 ' + (b.hostAddress ?? '');
  $('bd-room').textContent = `${b.roomName} · ${b.guests} khách`;

  // Thời gian lưu trú
  $('bd-checkin').textContent  = fmtDate(b.checkIn);
  $('bd-checkout').textContent = fmtDate(b.checkOut);
  $('bd-nights').textContent   = `${b.nights} đêm`;

  // Liên hệ
  $('bd-address').textContent = '📍 Địa chỉ đầy đủ: ' + (b.hostAddress ?? '—');
  $('bd-phone').textContent   = '📞 Điện thoại: ' + (b.hostPhone ?? '—');

  // Thanh toán
  $('bd-rate-label').textContent = `${formatVND(b.pricePerNight)} × ${b.nights} đêm`;
  $('bd-rate-total').textContent = formatVND(b.roomSubtotal ?? b.pricePerNight * b.nights);
  $('bd-fee').textContent        = formatVND(b.serviceFee);
  $('bd-total').textContent      = formatVND(b.totalPrice);

  // Nút huỷ chỉ khi còn huỷ được
  const canCancel = b.status === 'pending' || b.status === 'confirmed';
  $('bd-cancel').hidden = !canCancel;
  $('bd-cancel-hint').hidden = !canCancel;

  // Đánh giá chỉ khi đã hoàn thành
  $('review-section').hidden = b.status !== 'completed';
  $('review-section').querySelector('a').href = accountHref(`detail.html?id=${encodeURIComponent(b.homestayId)}&review=1&bookingId=${b.id}#reviews-section`);
}

function showNotFound(err) {
  if (ACCOUNT_API_MODE && err.status === 401) { requireLogin(); return; }
  const section = document.createElement('section'); section.className = 'not-found';
  const title = document.createElement('h1'); title.className = 'not-found__title'; title.textContent = 'Kh\u00f4ng t\u00ecm th\u1ea5y \u0111\u1eb7t ph\u00f2ng';
  const text = document.createElement('p'); text.className = 'not-found__text'; text.textContent = err.detail || 'Kh\u00f4ng t\u1ea3i \u0111\u01b0\u1ee3c d\u1eef li\u1ec7u \u0111\u1eb7t ph\u00f2ng.';
  const actions = document.createElement('div'); actions.className = 'not-found__actions';
  const link = document.createElement('a'); link.href = accountHref('booking-list.html'); link.className = 'btn btn--primary'; link.textContent = 'V\u1ec1 l\u1ecbch s\u1eed \u0111\u1eb7t ph\u00f2ng';
  actions.append(link); section.append(title,text,actions); document.querySelector('main').replaceChildren(section);
}

async function load() {
  if (!bookingId) return showNotFound(new ApiError(404, 'Thiếu mã đặt phòng trên đường dẫn.'));
  try {
    render(await getBooking(bookingId));
    if (ACCOUNT_API_MODE) {
      const payment=await getPayment(bookingId);
      let state=document.getElementById('booking-payment-state');if(!state){state=document.createElement('p');state.id='booking-payment-state';state.className='field__hint';$('bd-total').parentElement.after(state);}
      state.textContent=paymentText(payment);
    }
  } catch (err) {
    showNotFound(err);
  }
}

$('bd-cancel').addEventListener('click', async () => {
  const button = $('bd-cancel');
  if (button.disabled) return;
  const ok = await confirmAction({
    title: 'Huỷ đặt phòng?',
    message: 'Bạn có chắc muốn huỷ đặt phòng này không?',
    confirmText: 'Huỷ đặt phòng',
  });
  if (!ok || button.disabled) return;
  button.disabled = true;
  try {
    await cancelBooking(bookingId);
    toast('Đã huỷ đặt phòng.');
    await load();
  } catch (err) {
    toast(err instanceof ApiError ? err.detail : 'Không thể huỷ đặt phòng.', 'error');
  } finally { button.disabled = false; }
});

load();
