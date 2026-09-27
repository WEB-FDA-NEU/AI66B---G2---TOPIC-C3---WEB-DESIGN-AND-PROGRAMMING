// ============================================================
//  Trang chi tiết homestay.
// ============================================================
import { getItem, getReviews, addReview, ApiError } from '../api.js';
import { toast, setFieldError, clearFieldErrors } from '../ui.js';
import { formatVND } from '../render.js';
import { isLoggedIn, requireLogin, getUser } from '../auth.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const id = new URLSearchParams(location.search).get('id');

const loading   = document.getElementById('detail-loading');
const content   = document.getElementById('detail-content');
const notFound  = document.getElementById('detail-not-found');

async function load() {
  if (!id) { location.href = '404.html'; return; }
  try {
    const item = await getItem(id);
    fillItem(item);
    loading.hidden = true;
    content.hidden = false;
    loadReviews();
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
  document.getElementById('detail-rating').textContent   = item.rating ?? '—';
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

  // Nút đặt phòng: bắt buộc đăng nhập trước (login branch — Mốc 1).
  document.getElementById('book-btn').addEventListener('click', () => {
    if (!isLoggedIn()) return requireLogin();
    location.href = `booking-select.html?id=${item.id}`;
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
  reviewsList.replaceChildren(...reviews.map(renderReview));
}

function renderReview(review) {
  const node = document.getElementById('tpl-review').content.cloneNode(true);
  node.querySelector('.review-card__name').textContent = review.name;
  node.querySelector('.review-card__rating').textContent = `⭐ ${review.rating}`;
  node.querySelector('.review-card__date').textContent = new Date(review.created_at).toLocaleDateString('vi-VN');
  node.querySelector('.review-card__comment').textContent = review.comment;
  return node;
}

writeBtn.addEventListener('click', () => {
  if (!isLoggedIn()) return requireLogin();
  const user = getUser();
  if (user?.display_name) form.name.value = user.display_name;
  formWrapper.hidden = false;
});

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
    loadReviews();
  } catch (err) {
    toast(err.detail ?? 'Gửi đánh giá thất bại.', 'error');
  } finally {
    btn.disabled = false;
  }
});

load();