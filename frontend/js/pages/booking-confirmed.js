
// ============================================================
// BOOKING CONFIRMED
// - Đọc booking vừa tạo từ sessionStorage
// - Hiển thị thông tin xác nhận đặt phòng
// - Vào trực tiếp URL khi không có booking → booking-list.html
// ============================================================

import { formatVND } from '../render.js';
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
    booking.homestayImage || 'img/placeholder.svg';

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

if (!raw) {

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
