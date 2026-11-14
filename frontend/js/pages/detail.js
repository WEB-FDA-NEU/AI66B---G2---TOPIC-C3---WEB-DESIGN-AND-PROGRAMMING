import { ACCOUNT_API_MODE, accountHref, safeImageURL } from '../config.js';
// ============================================================
//  Trang chi tiết homestay — ĐÃ GỘP với bước chọn phòng (trước đây là booking-select).
//  Bố cục: ảnh → thanh thông tin → tab neo → [Tổng quan | Thông tin & giá | Tiện nghi | Đánh giá].
//  Mọi lựa chọn (id, ngày, khách, phòng) nằm trên URL → F5 / đăng nhập xong quay lại vẫn giữ nguyên.
// ============================================================
import { getItem, getReviews, addReview, getAvailability, getQuote, ApiError } from '../api.js';
import { toast, setFieldError, clearFieldErrors } from '../ui.js';
import { formatVND } from '../render.js';
import { stayFromParams, stayToParams, nightsBetween, todayISO, toISO, addDays, parseISO,
         roomTypesFor, parseRooms, stringifyRooms, quote, guestText, fmtDate,
         MAX_ADULTS, MAX_CHILDREN, ratingLabel } from '../pricing.js';
import { isLoggedIn, requireLogin, getUser } from '../auth.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const id = params.get('id');

let currentRating = null, totalReviews = 0, reviewPage = 1;

async function load() {
  if (!id) { location.href = '404.html'; return; }
  try {
    const item = await getItem(id);
    fillItem(item);
    $('detail-status').hidden = true;     // bỏ khoảng đệm của khung "đang tải"
    ['detail-top', 'detail-tabs', 'detail-main'].forEach(k => { $(k).hidden = false; });
    setupDescription();
    setupTabs();
    await loadReviews();
    // Link "Viết đánh giá" từ lịch sử/chi tiết đặt phòng: ?review=1 → mở sẵn form
    if (params.get('review') === '1') openReviewForm();
    else if (location.hash) requestAnimationFrame(() => $(decodeURIComponent(location.hash.slice(1)))?.scrollIntoView());
  } catch (err) {
    $('detail-loading').hidden = true;
    if (err instanceof ApiError && err.status === 404) $('detail-not-found').hidden = false;
    else toast(err.detail ?? 'Không tải được dữ liệu.', 'error');
  }
}

// ---------------- ĐIỀN DỮ LIỆU ----------------
function fillItem(item) {
  document.title = `${item.title} — Homestay Booking`;
  currentRating = item.rating; totalReviews = item.review_count || 0;

  const types = roomTypesFor(item);
  $('detail-title').textContent = item.title;
  $('detail-location').textContent = item.location ?? '';
  $('detail-rating').textContent = item.rating != null ? item.rating.toFixed(1) : '—';
  $('detail-room-type').textContent = item.room_type ?? 'Homestay';
  $('detail-capacity').textContent = `Tối đa ${Math.max(...types.map(t => t.capacity))} khách / phòng`;
  $('detail-description').textContent = item.description ?? '';
  $('detail-price').textContent = types.length ? formatVND(Math.min(...types.map(t => t.price))) : '—';
  if (!types.length) $('detail-capacity').textContent = '—';

  renderPhotos(item);
  renderAmenities(item);
  setupBooking(item, types);
}

// ---------------- THƯ VIỆN ẢNH: 1 lớn + 4 nhỏ ----------------
let photos = [], photoTitle = '';

function renderPhotos(item) {
  photos = (item.images?.length ? item.images : [item.cover_url]).filter(Boolean);
  photoTitle = item.title;
  const shown = photos.slice(0, 5);
  const grid = $('photo-grid');
  grid.dataset.n = shown.length;
  grid.style.setProperty('--small', Math.max(shown.length - 1, 1));
  grid.replaceChildren(...shown.map((src, i) => {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'photo-grid__cell';
    b.setAttribute('aria-label', `Xem ảnh ${i + 1} / ${photos.length}`);
    const img = document.createElement('img');
    img.src = safeImageURL(src); img.alt = `${item.title} - ảnh ${i + 1}`;
    b.append(img);
    if (i === 4 && photos.length > 5) {
      const more = document.createElement('span');
      more.className = 'photo-grid__more'; more.textContent = `+${photos.length - 5} ảnh`;
      b.append(more);
    }
    b.addEventListener('click', () => openLightbox(i));
    return b;
  }));
}

const lb = $('lightbox');
let lbIndex = 0;
function showLightbox(i) {
  lbIndex = (i + photos.length) % photos.length;
  $('lb-img').src = safeImageURL(photos[lbIndex]);
  $('lb-img').alt = `${photoTitle} - ảnh ${lbIndex + 1}`;
  $('lb-count').textContent = `${lbIndex + 1} / ${photos.length}`;
  const single = photos.length < 2;
  $('lb-prev').hidden = single; $('lb-next').hidden = single;
}
function openLightbox(i) { showLightbox(i); lb.showModal(); }
$('lb-close').addEventListener('click', () => lb.close());
$('lb-prev').addEventListener('click', () => showLightbox(lbIndex - 1));
$('lb-next').addEventListener('click', () => showLightbox(lbIndex + 1));
lb.addEventListener('click', e => { if (e.target === lb) lb.close(); });          // bấm nền tối để đóng
lb.addEventListener('keydown', e => {
  if (e.key === 'ArrowLeft') showLightbox(lbIndex - 1);
  if (e.key === 'ArrowRight') showLightbox(lbIndex + 1);
});

// ---------------- MÔ TẢ "XEM THÊM" ----------------
function setupDescription() {
  const p = $('detail-description'), btn = $('desc-toggle');
  const check = () => {
    if (p.classList.contains('is-open')) return;        // đang mở rộng thì giữ nút "Thu gọn"
    btn.hidden = p.scrollHeight <= p.clientHeight + 1;  // chỉ hiện nút khi văn bản thực sự bị cắt
  };
  btn.addEventListener('click', () => {
    const open = p.classList.toggle('is-open');
    btn.textContent = open ? 'Thu gọn' : 'Xem thêm';
    btn.setAttribute('aria-expanded', String(open));
  });
  check();
  window.addEventListener('resize', check);
}

// ---------------- TIỆN NGHI: lưới icon chip ----------------
const AMENITY_ICONS = [
  [/wi-?fi|internet/, '📶'], [/do xe|parking|gara/, '🅿️'], [/bep/, '🍳'], [/ho boi|pool/, '🏊'],
  [/dieu hoa|may lanh/, '❄️'], [/bua sang|an sang|breakfast/, '🥐'], [/suoi|may suoi|lo suoi/, '🔥'],
  [/thu cung|pet/, '🐾'], [/tv|tivi|tele/, '📺'], [/may giat/, '🧺'], [/ban cong|san vuon|vuon/, '🌿'],
  [/bbq|nuong/, '🍖'], [/nuoc nong|bon tam/, '🛁'],
];
const plain = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/đ/gi, 'd').toLowerCase();
const amenityIcon = name => AMENITY_ICONS.find(([re]) => re.test(plain(name)))?.[1] ?? '✓';

function renderAmenities(item) {
  const list = item.amenities?.length ? item.amenities : ACCOUNT_API_MODE ? [] : ['Wi-fi'];
  $('detail-amenities').replaceChildren(...list.map(name => {
    const li = document.createElement('li');
    const ic = document.createElement('span'); ic.className = 'amenity-grid__icon'; ic.setAttribute('aria-hidden', 'true'); ic.textContent = amenityIcon(name);
    const tx = document.createElement('span'); tx.textContent = name;
    li.append(ic, tx);
    return li;
  }));
}

// ---------------- THÔNG TIN & GIÁ: ngày/khách → bảng phòng → tóm tắt ----------------
function setupBooking(item, types) {
  const $in = $('stay-checkin'), $out = $('stay-checkout'), $ad = $('stay-adults'), $ch = $('stay-children');
  const rooms = parseRooms(params.get('rooms'));
  let availability = {}, availabilityKey = '', generation = 0;
  for (const k of Object.keys(rooms)) if (!types.some(t => t.key === k)) delete rooms[k];   // bỏ phòng không có trong homestay này

  const fill = (sel, from, to, label) => sel.replaceChildren(...Array.from({ length: to - from + 1 }, (_, i) => {
    const o = document.createElement('option'); o.value = from + i; o.textContent = `${from + i} ${label}`; return o;
  }));
  fill($ad, 1, MAX_ADULTS, 'người lớn');
  fill($ch, 0, MAX_CHILDREN, 'trẻ em');

  const stay0 = stayFromParams(params);
  $in.value = stay0.checkin; $out.value = stay0.checkout; $ad.value = stay0.adults; $ch.value = stay0.children;
  $in.min = todayISO();

  const current = () => ({ checkin: $in.value, checkout: $out.value, adults: +$ad.value, children: +$ch.value });

  // ----- danh sách phòng (dựng 1 lần, refresh chỉ cập nhật số) -----
  const cards = types.map(t => {
    const node = $('tpl-room').content.cloneNode(true);
    const el = node.querySelector('.room-card');
    el.dataset.key = t.key;
    const img = el.querySelector('.room-card__img'); img.src = t.image; img.alt = `${t.name} — ${item.title}`;
    el.querySelector('.room-card__name').textContent = t.name;
    if (ACCOUNT_API_MODE) { el.querySelector('.room-bed').hidden = !t.bed; el.querySelector('.room-area').hidden = !t.area; }
    el.querySelector('.room-bed').textContent = `🛏 ${t.bed}`;
    el.querySelector('.room-area').textContent = `📐 ${t.area}`;
    el.querySelector('.room-cap').textContent = `👥 Tối đa ${t.capacity} khách`;
    el.querySelector('.room-card__policy').textContent = `✓ ${t.policy}`;
    const badge = el.querySelector('.room-badge'); if (t.badge) badge.textContent = t.badge; else badge.remove();
    el.querySelector('.room-price').textContent = formatVND(t.price);
    if (ACCOUNT_API_MODE) { el.querySelector('.room-pick').disabled=true; el.querySelector('.room-plus').disabled=true; }
    const set = n => { rooms[t.key] = Math.max(0, Math.min(ACCOUNT_API_MODE ? (availability[t.key]?.available || 0) : 4, n)); refresh(); };
    el.querySelector('.room-pick').addEventListener('click', () => set(1));
    el.querySelector('.room-minus').addEventListener('click', () => set((rooms[t.key] ?? 0) - 1));
    el.querySelector('.room-plus').addEventListener('click', () => set((rooms[t.key] ?? 0) + 1));
    return el;
  });
  $('room-list').replaceChildren(...cards);

  // ----- kiểm tra ngày -----
  function stayProblem(s) {
    if (!s.checkin || !s.checkout) return 'Vui lòng chọn ngày nhận và trả phòng.';
    if (s.checkin < todayISO()) return 'Ngày nhận phòng không được ở quá khứ.';
    if (nightsBetween(s.checkin, s.checkout) === 0) return 'Ngày trả phòng phải sau ngày nhận phòng.';
    return '';
  }

  async function refresh() {
    const version = ++generation;
    const s = current();
    const sp = stayProblem(s);
    let quoteError = '';
    let q;
    $('book-btn').disabled = true;
    if (ACCOUNT_API_MODE) {
      q = {nights:nightsBetween(s.checkin,s.checkout),lines:[],roomCount:Object.values(rooms).reduce((a,n)=>a+n,0),capacity:0,roomSubtotal:null,serviceFee:null,total:null};
      try {
        if (sp) throw new Error(sp);
        const key = JSON.stringify(s);
        if (key !== availabilityKey) {
          const data = await getAvailability(id,s);
          if (version !== generation) return;
          availability = Object.fromEntries(data.rooms.map(r=>[r.key,r])); availabilityKey = key;
          for (const k of Object.keys(rooms)) rooms[k]=Math.min(rooms[k],availability[k]?.available || 0);
        }
        const selections=Object.entries(rooms).filter(([,n])=>n>0).map(([key,qty])=>({key,qty}));
        q.roomCount=selections.reduce((sum,r)=>sum+r.qty,0);
        if (selections.length) q = await getQuote({homestayId:Number(id),checkIn:s.checkin,checkOut:s.checkout,adults:s.adults,children:s.children,rooms:selections});
      } catch (error) {
        quoteError = error.detail || error.message;
        if (error.status === 409) {
          availabilityKey = '';
          try {
            const fresh = await getAvailability(id, s);
            if (version !== generation) return;
            availability = Object.fromEntries(fresh.rooms.map(room => [room.key, room]));
            for (const key of Object.keys(rooms)) rooms[key] = Math.min(rooms[key], availability[key]?.available || 0);
          } catch { /* Keep the server conflict visible; no mock fallback. */ }
        }
      }
      if (version !== generation) return;
    } else q = quote({ item, rooms, checkin: s.checkin, checkout: s.checkout });
    $out.min = $in.value ? toISO(addDays(parseISO($in.value), 1)) : todayISO();

    $('stay-error').textContent = sp;
    $('stay-nights').textContent = q.nights ? `${q.nights} đêm · ${guestText(s)}` : '';

    // thẻ phòng
    cards.forEach((el, i) => {
      const t = types[i], n = rooms[t.key] ?? 0;
      if (ACCOUNT_API_MODE && availability[t.key]) {
        t.price = Number(availability[t.key].pricePerNight);
        el.querySelector('.room-price').textContent = formatVND(t.price);
      }
      el.classList.toggle('is-selected', n > 0);
      el.querySelector('.room-pick').hidden = n > 0;
      el.querySelector('.stepper').hidden = n === 0;
      el.querySelector('.room-qty').textContent = n;
      const available = ACCOUNT_API_MODE ? (availability[t.key]?.available || 0) : 4;
      el.querySelector('.room-plus').disabled = n >= available;
      el.querySelector('.room-pick').disabled = available === 0;
      el.querySelector('.room-card__total').textContent = q.nights ? `${q.nights} đêm: ${formatVND(t.price * q.nights)}` : '';
    });

    // tóm tắt giá (cột phải)
    $('summary-lines').replaceChildren(...q.lines.map(l => {
      const d = document.createElement('div'); d.className = 'flex-between';
      const a = document.createElement('span'); a.className = 'text-muted'; a.textContent = `${l.qty} × ${l.name}`;
      const b = document.createElement('span'); b.textContent = formatVND(l.subtotal);
      d.append(a, b); return d;
    }));
    $('summary-empty').hidden = q.roomCount > 0;
    $('summary-nights').textContent = q.nights ? `${q.nights} đêm (${fmtDate(s.checkin)} → ${fmtDate(s.checkout)})` : '—';
    $('summary-rooms').textContent = `${q.roomCount} phòng`;
    $('summary-subtotal').textContent = q.roomSubtotal == null ? '—' : formatVND(q.roomSubtotal);
    $('summary-fee').textContent = q.serviceFee == null ? '—' : formatVND(q.serviceFee);
    $('summary-total').textContent = q.total == null ? '—' : formatVND(q.total);

    // điều kiện đi tiếp
    const guests = s.adults + s.children;
    const capProblem = quoteError || (q.roomCount > 0 && q.capacity < guests
      ? `Các phòng đã chọn chứa tối đa ${q.capacity} khách, nhưng bạn có ${guests} khách. Hãy thêm phòng.` : '');
    $('summary-msg').hidden = !capProblem;
    $('summary-msg').textContent = capProblem;
    $('book-btn').disabled = !!sp || q.roomCount === 0 || !!capProblem;

    // Giữ lựa chọn trong URL (kèm ?review=1 nếu có; không để lại "rooms=" rỗng)
    const keep = { id }; // stayToParams preserves API route mode
    if (params.get('review') === '1') keep.review = '1';
    if (params.get('bookingId')) keep.bookingId = params.get('bookingId');
    const r = stringifyRooms(rooms); if (r) keep.rooms = r;
    history.replaceState(null, '', `?${stayToParams(s, keep)}${location.hash}`);
  }

  $in.addEventListener('change', () => {
    if ($in.value && $out.value && nightsBetween($in.value, $out.value) === 0)
      $out.value = toISO(addDays(parseISO($in.value), 1));
    refresh();
  });
  [$out, $ad, $ch].forEach(el => el.addEventListener('change', refresh));
  $('stay-form').addEventListener('submit', e => e.preventDefault());

  $('book-btn').addEventListener('click', () => {
    if ($('book-btn').disabled) return;
    if (!isLoggedIn()) return requireLogin();     // đăng nhập xong quay lại đúng URL này, phòng đã chọn vẫn còn
    location.href = accountHref(`booking-page.html?${stayToParams(current(), { id: item.id, rooms: stringifyRooms(rooms), ...(ACCOUNT_API_MODE ? {intent:crypto.randomUUID()} : {}) })}`);
  });

  refresh();
}

// ---------------- TAB NEO: sáng đúng mục đang xem ----------------
function setupTabs() {
  const links = [...document.querySelectorAll('.sub-nav__link')];
  const sections = links.map(a => {
    const hash = new URL(a.href, location.href).hash;
    try { return hash ? document.getElementById(decodeURIComponent(hash.slice(1))) : null; }
    catch { return null; }
  });
  const sync = () => {
    const offset = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--header-h'), 10) + 90;
    let cur = 0;
    sections.forEach((s, i) => { if (s && s.getBoundingClientRect().top <= offset) cur = i; });
    // cuộn tới cuối trang thì mục cuối cùng phải sáng
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) cur = links.length - 1;
    links.forEach((a, i) => a.classList.toggle('is-active', i === cur));
  };
  window.addEventListener('scroll', sync, { passive: true });
  sync();
}

// ---------------- ĐÁNH GIÁ ----------------
const reviewSummary = $('review-summary');
const reviewsList   = $('reviews-list');
const writeBtn      = $('write-review-btn');
const formWrapper   = $('review-form-wrapper');
const form          = $('review-form');
const cancelBtn     = $('cancel-review-btn');

async function loadReviews() {
  const reviews = await getReviews(id, {page:reviewPage,page_size:20});
  const count = ACCOUNT_API_MODE ? totalReviews : reviews.length;
  reviewSummary.textContent = count ? `${count} đánh giá` : 'Chưa có đánh giá nào';
  $('detail-review-count').textContent =
    count ? [ratingLabel(currentRating), `${count} đánh giá`].filter(Boolean).join(' · ') : 'Chưa có đánh giá';
  reviewsList.replaceChildren(...reviews.map(renderReview));
  document.getElementById('review-pages')?.remove();
  if (ACCOUNT_API_MODE && count > 20) {
    const controls = document.createElement('div'); controls.id = 'review-pages'; controls.className = 'row__actions';
    for (const [label, delta, disabled] of [['Trước',-1,reviewPage===1],['Sau',1,reviewPage*20>=count]]) {
      const button = document.createElement('button'); button.type='button'; button.className='btn'; button.textContent=label; button.disabled=disabled;
      button.addEventListener('click',()=>{reviewPage+=delta;loadReviews().catch(error=>toast(error.detail,'error'));}); controls.append(button);
    }
    reviewsList.after(controls);
  }
}

function renderReview(review) {
  const node = $('tpl-review').content.cloneNode(true);
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
  if (form.querySelector('[type=submit]').disabled) return;
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
      ...(ACCOUNT_API_MODE && params.get('bookingId') ? {bookingId:Number(params.get('bookingId'))} : {}),
      name: form.name.value.trim(),
      rating: Number(form.rating.value),
      comment: form.comment.value.trim(),
    });
    form.reset();
    formWrapper.hidden = true;
    toast('Đã gửi đánh giá. Cảm ơn bạn!');
    // Điểm trung bình đã được cập nhật ở tầng api → tải lại để hiện số mới
    const fresh = await getItem(id);
    currentRating = fresh.rating; totalReviews = fresh.review_count || 0;
    $('detail-rating').textContent = fresh.rating != null ? fresh.rating.toFixed(1) : '—';
    loadReviews();
  } catch (err) {
    toast(err.detail ?? 'Gửi đánh giá thất bại.', 'error');
  } finally {
    btn.disabled = false;
  }
});

load();
