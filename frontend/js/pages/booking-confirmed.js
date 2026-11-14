
// ============================================================
// BOOKING CONFIRMED
// - Đọc booking vừa tạo từ sessionStorage
// - Hiển thị thông tin xác nhận đặt phòng
// - Vào trực tiếp URL khi không có booking → booking-list.html
// ============================================================

import { formatVND } from '../render.js';
import { getBooking, getPayment } from '../api.js';
import { ACCOUNT_API_MODE, accountHref, safeImageURL } from '../config.js';
import { paymentText } from '../pricing.js';
import { isLoggedIn, requireLogin } from '../auth.js';

import '../components/site-header.js';
import '../components/site-footer.js';

// ============================================================
// KIỂM TRA ĐĂNG NHẬP
// ============================================================

if (!isLoggedIn()) {
  requireLogin();
}

const STORAGE_KEY = 'lastBooking';

const $ = id => document.getElementById(id);

// ============================================================
// FORMAT NGÀY
// ============================================================

function formatDateVN(iso) {
  if (!iso) return '—';

  const date = new Date(iso);

  if (Number.isNaN(date.getTime())) {
    return '—';
  }

  return date.toLocaleDateString('vi-VN');
}

// ============================================================
// HIỂN THỊ DỮ LIỆU BOOKING
// ============================================================

function render(booking) {

  // Mã đặt phòng
  $('bCode').textContent = booking.code ?? '—';

  // Thông tin homestay
  $('bImage').src =
    safeImageURL(booking.homestayImage || 'img/placeholder.svg');

  $('bImage').alt =
    booking.homestayName || 'Hình ảnh homestay';

  $('bName').textContent =
    booking.homestayName ?? '—';

  $('bAddress').textContent =
    booking.homestayAddress ?? '—';

  $('bRoom').textContent =
    booking.roomName ?? '—';

  // Ngày lưu trú
  $('bCheckIn').textContent =
    formatDateVN(booking.checkIn);

  $('bCheckOut').textContent =
    formatDateVN(booking.checkOut);

  $('bNights').textContent =
    booking.nights != null
      ? `${booking.nights} đêm`
      : '—';

  $('bGuests').textContent =
    booking.guests != null
      ? `${booking.guests} khách`
      : '—';

  $('bGuestName').textContent =
    booking.guestName ?? '—';

  // Thanh toán
  $('bRoomTotal').textContent =
    booking.roomSubtotal != null
      ? formatVND(booking.roomSubtotal)
      : '—';

  $('bFee').textContent =
    booking.serviceFee != null
      ? formatVND(booking.serviceFee)
      : '—';

  $('bTotal').textContent =
    booking.totalPrice != null
      ? formatVND(booking.totalPrice)
      : '—';

  // Liên hệ chủ nhà
  const phoneEl = $('bPhone');
  const phone = booking.hostPhone ?? '';

  phoneEl.textContent = phone || 'Chưa có số điện thoại';

  if (phone) {
    phoneEl.href = `tel:${phone}`;
  } else {
    phoneEl.removeAttribute('href');
  }

  $('bHostAddress').textContent =
    booking.hostAddress ?? '—';
}

// ============================================================
// ĐỌC BOOKING TỪ SESSION STORAGE
// ============================================================

const raw = sessionStorage.getItem(STORAGE_KEY);

if (ACCOUNT_API_MODE) {
  const id=new URLSearchParams(location.search).get('id');
  if (!id) location.replace(accountHref('booking-list.html'));
  else Promise.all([getBooking(id),getPayment(id)]).then(([booking,payment])=>{
    render(booking);
    document.querySelector('.booking-confirmed-success__heading strong').textContent='Đã ghi nhận yêu cầu đặt phòng';
    document.querySelector('.booking-confirmed-success > p').textContent='Trạng thái bên dưới lấy từ máy chủ. Chưa có dịch vụ gửi email xác nhận.';
    const badge=document.querySelector('.booking-confirmed-code-card .badge');
    badge.textContent=({pending:'Chờ xác nhận',confirmed:'Đã xác nhận',cancelled:'Đã hủy',rejected:'Bị từ chối',checked_in:'Đã nhận phòng',completed:'Hoàn tất'})[booking.status] || booking.status;
    badge.className='badge '+(booking.status==='pending'?'badge--warning':['cancelled','rejected'].includes(booking.status)?'badge--danger':'badge--success');
    document.querySelector('.booking-confirmed-total > strong').textContent='Tổng giá trị đặt phòng:';
    const state=document.createElement('p');state.id='booking-server-state';state.className='field__hint';
    state.textContent=`Trạng thái đặt phòng: ${({pending:'Chờ xác nhận',confirmed:'Đã xác nhận',cancelled:'Đã hủy',rejected:'Bị từ chối',checked_in:'Đã nhận phòng',completed:'Hoàn tất'})[booking.status] || booking.status}. ${paymentText(payment)}`;
    document.querySelector('main').prepend(state);
  }).catch(error=>{if(error.status===401)requireLogin();else{const p=document.createElement('p');p.textContent=error.detail || 'Không tải được booking.';document.querySelector('main').prepend(p);}});
} else if (!raw) {

  // Không có booking vừa tạo
  window.location.href = 'booking-list.html';

} else {

  try {
    const booking = JSON.parse(raw);

    if (!booking || typeof booking !== 'object') {
      throw new Error('Dữ liệu booking không hợp lệ.');
    }

    render(booking);

    // Chỉ sử dụng dữ liệu một lần
    sessionStorage.removeItem(STORAGE_KEY);

  } catch (error) {
    console.error('Không thể hiển thị booking:', error);

    sessionStorage.removeItem(STORAGE_KEY);

    window.location.href = 'booking-list.html';
  }
}
