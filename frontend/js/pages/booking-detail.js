// ============================================================
//  Chi tiết một đặt phòng: đọc ?id=, đổ dữ liệu, timeline trạng thái,
//  huỷ đặt phòng (có hộp xác nhận), và nút viết đánh giá khi đã hoàn thành.
// ============================================================
import { getBooking, cancelBooking, getReviews, ApiError } from '../api.js';
import { toast, confirmAction } from '../ui.js';
import { formatVND } from '../render.js';
import { isLoggedIn, requireLogin, getUser } from '../auth.js';
import { fmtDate, daysUntil, FREE_CANCEL_DAYS } from '../pricing.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const $ = id => document.getElementById(id);
const id = new URLSearchParams(location.search).get('id');

const STATUS_LABEL = { pending: 'Chờ xác nhận', confirmed: 'Đã xác nhận', checked_in: 'Đã nhận phòng',
  completed: 'Hoàn thành', cancelled: 'Đã huỷ', rejected: 'Bị từ chối' };
const STATUS_BADGE = { pending: 'badge--warning', confirmed: 'badge--success', checked_in: 'badge--success',
  cancelled: 'badge--danger', rejected: 'badge--danger' };
const STEPS = ['pending', 'confirmed', 'checked_in', 'completed'];

if (!isLoggedIn()) requireLogin();
else if (!id) location.replace('booking-list.html');
else load();

async function load() {
  let b;
  try { b = await getBooking(id); }
  catch (e) {
    $('detail-loading').textContent = e instanceof ApiError && e.status === 404
      ? 'Không tìm thấy đặt phòng này.' : (e.detail ?? 'Không tải được dữ liệu.');
    return;
  }
  await render(b);
  $('detail-loading').hidden = true;
  $('detail-content').hidden = false;
  if (location.hash) document.querySelector(location.hash)?.scrollIntoView();
}

async function render(b) {
  document.title = `Đặt phòng ${b.homestayName} — Homestay Booking`;
  $('dTitle').textContent = b.homestayName;
  $('dCode').textContent = b.code ?? `#BK${String(b.id).padStart(6, '0')}`;
  const badge = $('dBadge');
  badge.textContent = STATUS_LABEL[b.status] ?? b.status;
  badge.className = `badge ${STATUS_BADGE[b.status] ?? ''}`.trim();

  // Timeline
  const idx = STEPS.indexOf(b.status);
  document.querySelectorAll('#dSteps [data-step]').forEach(el => el.classList.toggle('is-active', idx >= 0 && STEPS.indexOf(el.dataset.step) <= idx));
  $('dSteps').hidden = idx < 0;
  const ended = $('dEnded');
  ended.hidden = idx >= 0;
  if (idx < 0) ended.textContent = b.status === 'rejected' ? 'Chủ nhà đã từ chối đặt phòng này.' : 'Đặt phòng này đã được huỷ.';

  $('dImg').src = b.homestayImage; $('dImg').alt = b.homestayName;
  $('dLink').textContent = b.homestayName;
  $('dLink').href = `detail.html?id=${encodeURIComponent(b.homestayId)}`;
  $('dAddress').textContent = b.homestayAddress ?? b.hostAddress ?? '';
  $('dRoom').textContent = b.roomName;
  $('dGuests').textContent = `${b.guests} khách`;
  $('dIn').textContent = fmtDate(b.checkIn);
  $('dOut').textContent = fmtDate(b.checkOut);
  $('dNights').textContent = `${b.nights} đêm`;

  // Liên hệ: chỉ sau khi đã xác nhận
  const showContact = ['confirmed', 'checked_in', 'completed'].includes(b.status);
  $('dContact').hidden = !showContact;
  $('dHostAddress').textContent = b.hostAddress ?? '';
  $('dPhone').textContent = b.hostPhone ?? ''; $('dPhone').href = `tel:${b.hostPhone}`;

  // Thanh toán: có danh sách phòng thì chia dòng; đơn cũ (seed) chỉ có giá/đêm
  const lines = b.rooms?.length
    ? b.rooms.map(r => [`${r.qty} × ${r.name} × ${b.nights} đêm`, r.pricePerNight * r.qty * b.nights])
    : [[`${formatVND(b.pricePerNight)} × ${b.nights} đêm`, b.pricePerNight * b.nights]];
  $('dLines').replaceChildren(...lines.map(([label, amount]) => {
    const d = document.createElement('div'); d.className = 'flex-between';
    const x = document.createElement('span'); x.textContent = label;
    const y = document.createElement('span'); y.textContent = formatVND(amount);
    d.append(x, y); return d;
  }));
  $('dFee').textContent = formatVND(b.serviceFee);
  $('dTotal').textContent = formatVND(b.totalPrice);

  // Huỷ
  const cancellable = b.status === 'pending' || b.status === 'confirmed';
  $('dCancel').hidden = !cancellable;
  const left = daysUntil(b.checkIn);
  const refundable = left >= FREE_CANCEL_DAYS;
  $('dPolicy').textContent = !cancellable ? ''
    : refundable ? `Huỷ trước ${FREE_CANCEL_DAYS} ngày nhận phòng để được hoàn tiền toàn bộ — bạn vẫn còn hạn.`
                 : `Còn ${Math.max(left, 0)} ngày tới ngày nhận phòng, huỷ lúc này sẽ không được hoàn tiền.`;
  $('dCancel').onclick = async () => {
    const ok = await confirmAction({
      title: 'Huỷ đặt phòng?',
      message: refundable ? 'Bạn sẽ được hoàn tiền toàn bộ theo chính sách hủy phòng.'
                          : `Đã quá hạn hủy miễn phí (trước ${FREE_CANCEL_DAYS} ngày nhận phòng) nên bạn sẽ không được hoàn tiền.`,
      confirmText: 'Huỷ đặt phòng',
    });
    if (!ok) return;
    try {
      const next = await cancelBooking(b.id);
      toast('Đã huỷ đặt phòng.');
      await render({ ...b, ...next });
    } catch (e) { toast(e.detail ?? 'Không thể huỷ đặt phòng.', 'error'); }
  };

  // Đánh giá — chỉ khi đã hoàn thành
  $('review').hidden = b.status !== 'completed';
  if (b.status === 'completed') {
    const me = getUser();
    let mine = null;
    try { mine = (await getReviews(b.homestayId)).find(r => me && String(r.userId) === String(me.id)); } catch { /* bỏ qua */ }
    const base = `detail.html?id=${encodeURIComponent(b.homestayId)}`;
    if (mine) {
      $('dReviewText').textContent = `Bạn đã đánh giá ⭐ ${mine.rating}: “${mine.comment}”`;
      $('dReviewBtn').textContent = 'Xem đánh giá';
      $('dReviewBtn').href = `${base}#reviews-section`;
    } else {
      $('dReviewText').textContent = 'Bạn chưa đánh giá lượt lưu trú này. Chia sẻ trải nghiệm để giúp khách khác chọn homestay.';
      $('dReviewBtn').textContent = 'Viết đánh giá';
      $('dReviewBtn').href = `${base}&review=1#reviews-section`;
    }
  }
}
