// ============================================================
//  Booking Detail — đọc ?id= trên URL, lấy đúng booking qua
//  getBooking(id) rồi đổ dữ liệu vào các phần tử #bd-*.
// ============================================================
import { getBooking, cancelBooking, ApiError } from '../api.js';
import { toast, confirmAction } from '../ui.js';
import { formatVND } from '../render.js';
import { isLoggedIn, requireLogin } from '../auth.js';
import '../components/site-header.js';
import '../components/site-footer.js';

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
  $('bd-code').textContent  = '#BK' + String(b.id).padStart(6, '0');

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
  img.src = b.homestayImage || 'img/placeholder.svg';
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
  $('bd-rate-total').textContent = formatVND(b.pricePerNight * b.nights);
  $('bd-fee').textContent        = formatVND(b.serviceFee);
  $('bd-total').textContent      = formatVND(b.totalPrice);

  // Nút huỷ chỉ khi còn huỷ được
  const canCancel = b.status === 'pending' || b.status === 'confirmed';
  $('bd-cancel').hidden = !canCancel;
  $('bd-cancel-hint').hidden = !canCancel;

  // Đánh giá chỉ khi đã hoàn thành
  $('review-section').hidden = b.status !== 'completed';
  $('review-section').querySelector('a').href = `detail.html?id=${encodeURIComponent(b.homestayId)}&review=1#reviews-section`;
}

function showNotFound(err) {
  document.querySelector('main').innerHTML = `
    <section class="not-found">
      <h1 class="not-found__title">Không tìm thấy đặt phòng</h1>
      <p class="not-found__text">${err instanceof ApiError ? err.detail : 'Không tải được dữ liệu đặt phòng.'}</p>
      <div class="not-found__actions">
        <a class="btn btn--primary" href="booking-list.html">Về lịch sử đặt phòng</a>
      </div>
    </section>`;
}

async function load() {
  if (!bookingId) return showNotFound(new ApiError(404, 'Thiếu mã đặt phòng trên đường dẫn.'));
  try {
    render(await getBooking(bookingId));
  } catch (err) {
    showNotFound(err);
  }
}

$('bd-cancel').addEventListener('click', async () => {
  const ok = await confirmAction({
    title: 'Huỷ đặt phòng?',
    message: 'Bạn có chắc muốn huỷ đặt phòng này không?',
    confirmText: 'Huỷ đặt phòng',
  });
  if (!ok) return;
  try {
    await cancelBooking(bookingId);
    toast('Đã huỷ đặt phòng.');
    await load();
  } catch (err) {
    toast(err instanceof ApiError ? err.detail : 'Không thể huỷ đặt phòng.', 'error');
  }
});

load();
