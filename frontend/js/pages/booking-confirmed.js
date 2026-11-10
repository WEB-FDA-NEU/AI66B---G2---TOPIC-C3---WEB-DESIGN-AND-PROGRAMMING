// ============================================================
//  Trang xác nhận đặt phòng — đọc booking theo ?id= (đã lưu ở bước thanh toán),
//  nên F5 hay mở lại link vẫn thấy đúng đơn. Không có id → về lịch sử đặt phòng.
// ============================================================
import { getBooking, ApiError } from '../api.js';
import { formatVND } from '../render.js';
import { isLoggedIn, requireLogin } from '../auth.js';
import { fmtDate } from '../pricing.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const $ = id => document.getElementById(id);
const id = new URLSearchParams(location.search).get('id');

if (!isLoggedIn()) requireLogin();
else if (!id) location.replace('booking-list.html');
else load();

async function load() {
  let b;
  try { b = await getBooking(id); }
  catch (e) { location.replace(e instanceof ApiError && e.status === 404 ? 'booking-list.html' : '404.html'); return; }

  $('bCode').textContent = b.code ?? `#BK${String(b.id).padStart(6, '0')}`;
  $('bImage').src = b.homestayImage; $('bImage').alt = b.homestayName;
  $('bName').textContent = b.homestayName;
  $('bAddress').textContent = b.homestayAddress ?? b.hostAddress ?? '';
  $('bRoom').textContent = b.roomName;
  $('bCheckIn').textContent = fmtDate(b.checkIn);
  $('bCheckOut').textContent = fmtDate(b.checkOut);
  $('bNights').textContent = `${b.nights} đêm`;
  $('bGuests').textContent = `${b.guests} khách`;
  $('bGuestName').textContent = b.guestName ?? '—';

  const subtotal = b.roomSubtotal ?? b.pricePerNight * b.nights;
  $('bRoomTotal').textContent = formatVND(subtotal);
  $('bFee').textContent = formatVND(b.serviceFee);
  $('bTotal').textContent = formatVND(b.totalPrice);

  $('bPhone').textContent = b.hostPhone;
  $('bPhone').href = `tel:${b.hostPhone}`;
  $('bHostAddress').textContent = b.hostAddress ?? '';
  $('bDetailLink').href = `booking-detail.html?id=${encodeURIComponent(b.id)}`;
}
