// ============================================================
//  Trang xác nhận đặt phòng — đọc booking vừa tạo từ sessionStorage
//  (được booking-page.html lưu trước khi chuyển trang), đổ dữ liệu
//  vào các ô hiển thị. Vào thẳng URL này mà chưa đặt phòng → về
//  booking-list.html.
// ============================================================
import { formatVND } from '../render.js';
import { isLoggedIn, requireLogin } from '../auth.js';
import '../components/site-header.js';
import '../components/site-footer.js';

if (!isLoggedIn()) requireLogin();

const STORAGE_KEY = 'lastBooking';

function formatDateVN(iso) {
  return new Date(iso).toLocaleDateString('vi-VN');
}

function render(booking) {
  document.getElementById('bCode').textContent = booking.code;
  document.getElementById('bImage').src = booking.homestayImage;
  document.getElementById('bImage').alt = booking.homestayName;
  document.getElementById('bName').textContent = booking.homestayName;
  document.getElementById('bAddress').textContent = booking.homestayAddress;
  document.getElementById('bRoom').textContent = booking.roomName;

  document.getElementById('bCheckIn').textContent = formatDateVN(booking.checkIn);
  document.getElementById('bCheckOut').textContent = formatDateVN(booking.checkOut);
  document.getElementById('bNights').textContent = `${booking.nights} đêm`;
  document.getElementById('bGuests').textContent = `${booking.guests} khách`;
  document.getElementById('bGuestName').textContent = booking.guestName;

  document.getElementById('bRoomTotal').textContent = formatVND(booking.roomSubtotal);
  document.getElementById('bFee').textContent = formatVND(booking.serviceFee);
  document.getElementById('bTotal').textContent = formatVND(booking.totalPrice);

  const phoneEl = document.getElementById('bPhone');
  phoneEl.textContent = booking.hostPhone;
  phoneEl.href = `tel:${booking.hostPhone}`;
  document.getElementById('bHostAddress').textContent = booking.hostAddress;
}

const raw = sessionStorage.getItem(STORAGE_KEY);

if (!raw) {
  window.location.href = 'booking-list.html';
} else {
  render(JSON.parse(raw));
  sessionStorage.removeItem(STORAGE_KEY); // dùng 1 lần, F5 lại sẽ không còn dữ liệu cũ
}