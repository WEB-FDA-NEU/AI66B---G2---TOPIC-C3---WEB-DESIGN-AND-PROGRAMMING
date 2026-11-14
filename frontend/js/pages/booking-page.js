// ============================================================
//  Bước 3 — thông tin khách + thanh toán giả lập.
//  Đọc phòng/ngày/khách từ URL (do trang detail.html tạo, đã gộp bước chọn phòng), tính giá bằng pricing.quote(),
//  rồi tạo booking, lưu vào sessionStorage('lastBooking') và chuyển sang booking-confirmed.html
// ============================================================
import { getItem, createBooking, ApiError } from '../api.js';
import { ACCOUNT_API_MODE } from '../config.js';
import { startApiCheckout } from './api-checkout.js';
import { setFieldError, clearFieldErrors, toast } from '../ui.js';
import { formatVND } from '../render.js';
import { isLoggedIn, requireLogin, getUser } from '../auth.js';
import { stayFromParams, parseRooms, quote, fmtDate, guestText, todayISO } from '../pricing.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const itemId = params.get('id');

if (ACCOUNT_API_MODE) startApiCheckout(params);
else if (!itemId) location.replace('search.html');
else if (!isLoggedIn()) requireLogin();
else init();

async function init() {
  let item;
  try { item = await getItem(itemId); }
  catch { location.replace('404.html'); return; }

  const stay  = stayFromParams(params);
  const rooms = parseRooms(params.get('rooms'));
  const q = quote({ item, rooms, checkin: stay.checkin, checkout: stay.checkout });
  const back = `detail.html?${params}#pricing`;

  // Chưa chọn phòng (vào thẳng URL) → quay lại bước chọn phòng
  if (q.roomCount === 0 || q.nights === 0) { location.replace(`detail.html?id=${encodeURIComponent(itemId)}#pricing`); return; }
  $('backToSelect').href = back;
  $('editSelection').href = back;

  // ---------- Tóm tắt bên phải ----------
  $('sumImg').src = item.cover_url ?? item.images?.[0] ?? 'img/placeholder.svg';
  $('sumImg').alt = item.title;
  $('sumTitle').textContent = item.title;
  $('sumLocation').textContent = item.location ?? '';
  if (item.rating != null) {
    $('sumRatingWrap').hidden = false;
    $('sumRating').textContent = item.rating.toFixed(1);
    $('sumRatingLabel').textContent = item.rating >= 4.4 ? 'Rất tốt' : 'Tốt';
    $('sumRatingCount').textContent = 'điểm đánh giá của khách';
  }
  $('checkinDisplay').textContent  = fmtDate(stay.checkin);
  $('checkoutDisplay').textContent = fmtDate(stay.checkout);
  $('nightsVal').textContent  = `${q.nights} đêm`;
  $('guestsVal').textContent  = guestText(stay);
  $('roomLines').replaceChildren(...q.lines.map(l => {
    const d = document.createElement('div'); d.className = 'flex-between';
    const a = document.createElement('span'); a.className = 'text-muted';
    a.textContent = `${l.qty} × ${l.name} × ${q.nights} đêm`;
    const b = document.createElement('span'); b.textContent = formatVND(l.subtotal);
    d.append(a, b); return d;
  }));
  $('roomSubtotalVal').textContent = formatVND(q.roomSubtotal);
  $('serviceFeeVal').textContent   = formatVND(q.serviceFee);
  $('grandTotalVal').textContent   = formatVND(q.total);
  $('btnPayAmount').textContent    = formatVND(q.total);

  // ---------- Điền sẵn từ tài khoản ----------
  const me = getUser();
  if (me) {
    $('accName').textContent = `Đã đăng nhập: ${me.display_name ?? ''}`;
    $('accEmail').textContent = me.email ?? '';
    if (me.email) $('email').value = me.email;
    const parts = (me.display_name ?? '').trim().split(/\s+/);
    if (parts.length > 1) { $('lastname').value = parts[0]; $('firstname').value = parts.slice(1).join(' '); }
  }

  // ---------- Form ----------
  const form = $('checkoutForm'), errorAlert = $('errorAlert'), formMsg = $('formMsg');

  $('cardNum')?.addEventListener('input', e => {
    const v = e.target.value.replace(/\D/g, '').slice(0, 16);
    e.target.value = v.replace(/(.{4})/g, '$1 ').trim();
  });
  $('cardExp')?.addEventListener('input', e => {
    const v = e.target.value.replace(/\D/g, '').slice(0, 4);
    e.target.value = v.length >= 3 ? v.slice(0, 2) + '/' + v.slice(2) : v;
  });
  $('cardCvv')?.addEventListener('input', e => { e.target.value = e.target.value.replace(/\D/g, '').slice(0, 3); });

  const RULES = {
    lastname:  v => v.trim() ? '' : 'Vui lòng nhập họ của bạn.',
    firstname: v => v.trim() ? '' : 'Vui lòng nhập tên của bạn.',
    email:     v => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v.trim()) ? '' : 'Vui lòng nhập email hợp lệ.',
    cardNum:   v => v.replace(/\s/g, '').length === 16 ? '' : 'Số thẻ gồm 16 chữ số.',
    cardExp:   v => {
      const m = /^(\d{2})\/(\d{2})$/.exec(v);
      if (!m || +m[1] < 1 || +m[1] > 12) return 'Hạn thẻ theo dạng MM/YY.';
      const now = new Date();
      return (2000 + +m[2]) * 12 + +m[1] >= now.getFullYear() * 12 + now.getMonth() + 1 ? '' : 'Thẻ đã hết hạn.';
    },
    cardCvv:   v => /^\d{3}$/.test(v) ? '' : 'CVV gồm 3 chữ số.',
  };

  form.addEventListener('submit', async e => {
    e.preventDefault();
    clearFieldErrors(form);
    errorAlert.hidden = true; formMsg.hidden = true;

    let ok = true;
    for (const [id, check] of Object.entries(RULES)) {
      if (!$(id)) continue;
      const msg = check($(id).value);
      if (msg) { setFieldError($(id), msg); ok = false; }
    }
    if (!ok) { errorAlert.hidden = false; errorAlert.scrollIntoView({ behavior: 'smooth', block: 'center' }); return; }

    // Đặt phòng đã quá hạn trong lúc người dùng mở trang
    if (stay.checkin < todayISO()) { formMsg.textContent = 'Ngày nhận phòng đã qua. Vui lòng chọn lại ngày.'; formMsg.hidden = false; return; }

    const btn = $('btnSubmit');
    btn.disabled = true;
    btn.textContent = 'Đang xử lý giao dịch...';

    try {
      await new Promise(r => setTimeout(r, 1200));   // giả lập cổng thanh toán
      const booking = await createBooking({
        homestayId: item.id,
        homestayName: item.title,
        homestayImage: item.cover_url ?? item.images?.[0] ?? 'img/placeholder.svg',
        homestayAddress: item.location ?? '',
        roomName: q.lines.map(l => `${l.qty} × ${l.name}`).join(', '),
        rooms: q.lines.map(l => ({ key: l.key, name: l.name, qty: l.qty, pricePerNight: l.pricePerNight })),
        checkIn: stay.checkin, checkOut: stay.checkout, nights: q.nights,
        adults: stay.adults, children: stay.children, guests: stay.adults + stay.children,
        guestName: `${$('firstname').value.trim()} ${$('lastname').value.trim()}`,
        guestEmail: $('email').value.trim(),
        pricePerNight: Math.round(q.roomSubtotal / q.nights),   // tổng giá các phòng / đêm (booking-detail dùng để hiển thị)
        roomSubtotal: q.roomSubtotal, serviceFee: q.serviceFee, totalPrice: q.total,
        hostPhone: item.hostPhone ?? '0909123456',
        hostAddress: item.location ?? '',
      });
      toast('Thanh toán thành công!');
      sessionStorage.setItem('lastBooking', JSON.stringify(booking));   // booking-confirmed.js đọc từ đây
      location.href = 'booking-confirmed.html';
    } catch (err) {
      formMsg.textContent = err instanceof ApiError ? err.detail : 'Thanh toán thất bại. Vui lòng thử lại.';
      formMsg.hidden = false;
      btn.disabled = false;
      btn.innerHTML = `Xác nhận &amp; Thanh toán (<span id="btnPayAmount">${formatVND(q.total)}</span>)`;
    }
  });
  $('btnSubmit').disabled = false;
}
