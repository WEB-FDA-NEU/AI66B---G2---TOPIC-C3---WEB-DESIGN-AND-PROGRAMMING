// ============================================================
//  Trang chi tiết homestay.
// ============================================================
import { getItem, getReviews, addReview, ApiError } from '../api.js';
import { toast, setFieldError, clearFieldErrors } from '../ui.js';
import { formatVND } from '../render.js';
import { stayFromParams, stayToParams, nightsBetween, todayISO, toISO, addDays, parseISO,
         MAX_ADULTS, MAX_CHILDREN, ratingLabel } from '../pricing.js';
import { isLoggedIn, requireLogin, getUser } from '../auth.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const id = new URLSearchParams(location.search).get('id');

const loading   = document.getElementById('detail-loading');
const content   = document.getElementById('detail-content');
const notFound  = document.getElementById('detail-not-found');

let currentRating = null;

async function load() {
  if (!id) { location.href = '404.html'; return; }
  try {
    const item = await getItem(id);
    fillItem(item);
    loading.hidden = true;
    content.hidden = false;
    await loadReviews();
    // Link "Viết đánh giá" từ lịch sử/chi tiết đặt phòng: ?review=1 → mở sẵn form
    if (new URLSearchParams(location.search).get('review') === '1') openReviewForm();
    else if (location.hash) document.querySelector(location.hash)?.scrollIntoView();
  } catch (err) {
    loading.hidden = true;
    if (err instanceof ApiError && err.status === 404) notFound.hidden = false;
    else toast(err.detail ?? 'Không tải được dữ liệu.', 'error');
  }
}

function fillItem(item) {
  document.title = `${item.title} — Homestay Booking`;

  document.getElementById('detail-location').textContent = item.location ?? '';
  document.getElementById('detail-title').textContent    = item.title;
  currentRating = item.rating;
  document.getElementById('detail-rating').textContent   = item.rating != null ? item.rating.toFixed(1) : '—';
  document.getElementById('detail-room-type').textContent = item.room_type ?? '';
  document.getElementById('detail-description').textContent = item.description ?? '';
  document.getElementById('detail-amenities').textContent = (item.amenities ?? []).join(' · ');
  document.getElementById('detail-price').textContent = formatVND(item.price);

  // Gallery: ảnh đầu tiên làm ảnh chính, các ảnh còn lại làm thumbnail bấm để đổi ảnh chính.
  const images = item.images?.length ? item.images : [item.cover_url];
  const mainImg = document.getElementById('detail-image');
  mainImg.src = images[0];
  mainImg.alt = item.title;

  const thumbs = document.getElementById('detail-gallery-thumbs');
  thumbs.replaceChildren(...images.map((src, i) => {
    const img = document.createElement('img');
    img.src = src;
    img.alt = `${item.title} - ảnh ${i + 1}`;
    img.addEventListener('click', () => { mainImg.src = src; });
    return img;
  }));

  setupStayForm(item);
}

// ---------------- CHỌN NGÀY & KHÁCH → sang bước chọn phòng ----------------
function setupStayForm(item) {
  const f = document.getElementById('stay-form');
  const $in = document.getElementById('stay-checkin');
  const $out = document.getElementById('stay-checkout');
  const $ad = document.getElementById('stay-adults');
  const $ch = document.getElementById('stay-children');
  const err = document.getElementById('stay-error');
  const est = document.getElementById('stay-estimate');

  const fill = (sel, from, to, label) => sel.replaceChildren(...Array.from({ length: to - from + 1 }, (_, i) => {
    const o = document.createElement('option'); o.value = from + i; o.textContent = `${from + i} ${label}`; return o;
  }));
  fill($ad, 1, MAX_ADULTS, 'người lớn');
  fill($ch, 0, MAX_CHILDREN, 'trẻ em');

  const stay = stayFromParams(new URLSearchParams(location.search));
  $in.value = stay.checkin; $out.value = stay.checkout;
  $ad.value = stay.adults;  $ch.value = stay.children;
  $in.min = todayISO();

  const current = () => ({ checkin: $in.value, checkout: $out.value, adults: +$ad.value, children: +$ch.value });

  function refresh() {
    const s = current();
    $out.min = $in.value ? toISO(addDays(parseISO($in.value), 1)) : todayISO();
    const n = nightsBetween(s.checkin, s.checkout);
    err.textContent = '';
    est.textContent = n ? `${n} đêm · từ ${formatVND(item.price * n)} (chưa gồm phí dịch vụ)` : '';
    // Giữ ngày trong URL: đăng nhập xong quay lại vẫn còn nguyên lựa chọn, F5 không mất.
    const keep = { id };
    if (new URLSearchParams(location.search).get('review') === '1') keep.review = '1';   // đừng làm mất ?review=1
    history.replaceState(null, '', `?${stayToParams(s, keep)}${location.hash}`);
  }
  $in.addEventListener('change', () => {
    if ($in.value && $out.value && nightsBetween($in.value, $out.value) === 0)
      $out.value = toISO(addDays(parseISO($in.value), 1));
    refresh();
  });
  [$out, $ad, $ch].forEach(el => el.addEventListener('change', refresh));
  refresh();

  f.addEventListener('submit', e => {
    e.preventDefault();
    const s = current();
    if (!s.checkin || !s.checkout)            { err.textContent = 'Vui lòng chọn ngày nhận và trả phòng.'; return; }
    if (s.checkin < todayISO())               { err.textContent = 'Ngày nhận phòng không được ở quá khứ.'; return; }
    if (nightsBetween(s.checkin, s.checkout) === 0) { err.textContent = 'Ngày trả phòng phải sau ngày nhận phòng.'; return; }
    // Đặt phòng bắt buộc đăng nhập (login branch — Mốc 1).
    if (!isLoggedIn()) return requireLogin();
    location.href = `booking-select.html?${stayToParams(s, { id: item.id })}`;
  });
}

// ---------------- ĐÁNH GIÁ ----------------
const reviewSummary   = document.getElementById('review-summary');
const reviewsList     = document.getElementById('reviews-list');
const writeBtn        = document.getElementById('write-review-btn');
const formWrapper     = document.getElementById('review-form-wrapper');
const form            = document.getElementById('review-form');
const cancelBtn       = document.getElementById('cancel-review-btn');

async function loadReviews() {
  const reviews = await getReviews(id);
  reviewSummary.textContent = reviews.length ? `${reviews.length} đánh giá` : 'Chưa có đánh giá nào';
  document.getElementById('detail-review-count').textContent =
    reviews.length ? `${[ratingLabel(currentRating), `${reviews.length} đánh giá`].filter(Boolean).join(' · ')}` : 'Chưa có đánh giá';
  reviewsList.replaceChildren(...reviews.map(renderReview));
}

function renderReview(review) {
  const node = document.getElementById('tpl-review').content.cloneNode(true);
  node.querySelector('.review-card__name').textContent = review.name;
  node.querySelector('.review-card__rating').textContent = `⭐ ${review.rating}`;
  node.querySelector('.review-card__verified').hidden = !review.verified;
  node.querySelector('.review-card__date').textContent = new Date(review.created_at).toLocaleDateString('vi-VN');
  node.querySelector('.review-card__comment').textContent = review.comment;
  return node;
}

function openReviewForm() {
  if (!isLoggedIn()) return requireLogin();
  const user = getUser();
  if (user?.display_name) form.name.value = user.display_name;
  formWrapper.hidden = false;
  formWrapper.scrollIntoView({ behavior: 'smooth', block: 'center' });
  form.rating.focus({ preventScroll: true });
}
writeBtn.addEventListener('click', openReviewForm);

cancelBtn.addEventListener('click', () => { formWrapper.hidden = true; form.reset(); });

form.addEventListener('submit', async e => {
  e.preventDefault();
  clearFieldErrors(form);

  let ok = true;
  if (form.name.value.trim().length < 2) { setFieldError(form.name, 'Tên tối thiểu 2 ký tự.'); ok = false; }
  if (!form.rating.value)                { setFieldError(form.rating, 'Vui lòng chọn số sao.'); ok = false; }
  if (form.comment.value.trim().length < 5) { setFieldError(form.comment, 'Nhận xét tối thiểu 5 ký tự.'); ok = false; }
  if (!ok) return;

  const btn = form.querySelector('button[type=submit]');
  btn.disabled = true;
  try {
    await addReview(id, {
      name: form.name.value.trim(),
      rating: Number(form.rating.value),
      comment: form.comment.value.trim(),
    });
    form.reset();
    formWrapper.hidden = true;
    toast('Đã gửi đánh giá. Cảm ơn bạn!');
    // Điểm trung bình đã được cập nhật ở tầng api → tải lại để hiện số mới
    const fresh = await getItem(id);
    currentRating = fresh.rating;
    document.getElementById('detail-rating').textContent = fresh.rating != null ? fresh.rating.toFixed(1) : '—';
    loadReviews();
  } catch (err) {
    toast(err.detail ?? 'Gửi đánh giá thất bại.', 'error');
  } finally {
    btn.disabled = false;
  }
});

load();