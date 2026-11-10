// ============================================================
//  Bước 2 — chọn loại phòng & số lượng.
//  Ngày/khách đến từ trang chi tiết qua URL; ở đây chỉ hiện thanh tóm tắt
//  (đổi được nếu cần) rồi chuyển phòng đã chọn sang booking-page qua URL.
// ============================================================
import { getItem, getReviews, ApiError } from '../api.js';
import { formatVND } from '../render.js';
import { isLoggedIn, requireLogin } from '../auth.js';
import { stayFromParams, stayToParams, roomTypesFor, parseRooms, stringifyRooms, quote,
         fmtDate, guestText, todayISO, toISO, addDays, parseISO, nightsBetween,
         MAX_ADULTS, MAX_CHILDREN, ratingLabel } from '../pricing.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const $ = id => document.getElementById(id);
const params = new URLSearchParams(location.search);
const itemId = params.get('id');

if (!itemId) location.replace('search.html');
else if (!isLoggedIn()) requireLogin();
else init();

async function init() {
  let item;
  try { item = await getItem(itemId); }
  catch (e) {
    if (e instanceof ApiError && e.status === 404) { location.replace('404.html'); return; }
    $('itemTitle').textContent = 'Không tải được dữ liệu';
    return;
  }

  const types = roomTypesFor(item);
  let stay = stayFromParams(params);
  // Số lượng từng loại phòng; mặc định chọn sẵn 1 phòng đầu tiên
  let rooms = parseRooms(params.get('rooms'));
  if (!Object.keys(rooms).length) rooms = { [types[0].key]: 1 };

  fillOverview(item);
  fillReviews(item);
  renderRoomRows();
  setupStayForm();
  setupSubNav();
  refresh();

  // ---------- Tổng quan ----------
  function fillOverview(item) {
    document.title = `Chọn phòng — ${item.title}`;
    $('crumbTitle').textContent = item.title;
    $('crumbDetail').href = `detail.html?id=${encodeURIComponent(item.id)}`;
    $('itemTitle').textContent = item.title;
    $('itemLocation').textContent = item.location ?? '';
    $('itemRating').textContent = item.rating != null ? item.rating.toFixed(1) : '—';
    $('ratingLabel').textContent = ratingLabel(item.rating);
    $('itemDesc').textContent = item.description ?? '';

    const imgs = item.images?.length ? item.images : [item.cover_url];
    const main = document.createElement('img'); main.src = imgs[0]; main.alt = item.title;
    const thumbs = document.createElement('div'); thumbs.className = 'detail-gallery__thumbs';
    imgs.slice(0, 4).forEach((src, i) => {
      const t = document.createElement('img'); t.src = src; t.alt = `${item.title} - ảnh ${i + 1}`;
      t.addEventListener('click', () => { main.src = src; });
      thumbs.appendChild(t);
    });
    $('gallery').replaceChildren(main, thumbs);

    const am = item.amenities?.length ? item.amenities : ['Wi-fi'];
    $('amenityList').replaceChildren(...am.map(a => { const li = document.createElement('li'); li.textContent = a; return li; }));
  }

  // ---------- Đánh giá (dữ liệu thật, cùng nguồn với trang chi tiết) ----------
  async function fillReviews(item) {
    const enc = encodeURIComponent(item.id);
    $('allReviewsLink').href = `detail.html?id=${enc}#reviews-section`;
    $('writeReviewLink').href = `detail.html?id=${enc}&review=1#reviews-section`;
    try {
      const list = await getReviews(item.id);
      $('ratingCount').textContent = list.length ? `${list.length} đánh giá` : 'Chưa có đánh giá';
      $('reviewSummary').textContent = list.length
        ? `Điểm trung bình ${item.rating?.toFixed(1) ?? '—'} / 5 · ${list.length} đánh giá`
        : 'Chưa có đánh giá nào — hãy là người đầu tiên!';
      $('reviewPreview').replaceChildren(...list.slice(0, 2).map(r => {
        const n = $('tpl-review').content.cloneNode(true);
        n.querySelector('.review-card__name').textContent = r.name;
        n.querySelector('.review-card__verified').hidden = !r.verified;
        n.querySelector('.review-card__rating').textContent = `⭐ ${r.rating}`;
        n.querySelector('.review-card__date').textContent = new Date(r.created_at).toLocaleDateString('vi-VN');
        n.querySelector('.review-card__comment').textContent = r.comment;
        return n;
      }));
    } catch { $('reviewSummary').textContent = 'Không tải được đánh giá.'; }
  }

  // ---------- Bảng phòng ----------
  function renderRoomRows() {
    $('roomRows').replaceChildren(...types.map(t => {
      const tr = $('tpl-room-row').content.cloneNode(true);
      const row = tr.querySelector('tr');
      row.dataset.key = t.key;
      tr.querySelector('.room-name').textContent = t.name;
      tr.querySelector('.room-detail').textContent = t.detail;
      const note = tr.querySelector('.room-note'); if (t.note) note.textContent = t.note; else note.remove();
      const badge = tr.querySelector('.room-badge'); if (t.badge) badge.textContent = t.badge; else badge.remove();
      tr.querySelector('.room-capacity').textContent = `👥 ${t.capacity} khách`;
      const sel = tr.querySelector('.room-select');
      sel.value = String(rooms[t.key] ?? 0);
      sel.setAttribute('aria-label', `Số lượng ${t.name}`);
      sel.addEventListener('change', () => { rooms[t.key] = +sel.value; refresh(); });
      return tr;
    }));
  }

  // ---------- Tính lại giá + cập nhật URL ----------
  function refresh() {
    const q = quote({ item, rooms, checkin: stay.checkin, checkout: stay.checkout });

    $('sbIn').textContent = fmtDate(stay.checkin);
    $('sbOut').textContent = fmtDate(stay.checkout);
    $('sbNights').textContent = `${q.nights} đêm`;
    $('sbGuests').textContent = guestText(stay);
    $('priceHeader').textContent = `Giá (${q.nights} đêm)`;

    document.querySelectorAll('#roomRows tr').forEach(row => {
      const t = types.find(x => x.key === row.dataset.key);
      row.querySelector('.room-price').textContent = formatVND(t.price * q.nights);
      row.querySelector('.room-unit').textContent = `${formatVND(t.price)} / đêm`;
    });

    $('summaryLines').replaceChildren(...q.lines.map(l => {
      const d = document.createElement('div'); d.className = 'flex-between';
      const a = document.createElement('span'); a.className = 'text-muted'; a.textContent = `${l.qty} × ${l.name}`;
      const b = document.createElement('span'); b.textContent = formatVND(l.subtotal);
      d.append(a, b); return d;
    }));
    $('selectedCount').textContent = `${q.roomCount} phòng`;
    $('nightsDisplay').textContent = `${q.nights} đêm`;
    $('totalVal').textContent = formatVND(q.roomSubtotal);

    // Điều kiện để đi tiếp
    const guests = stay.adults + stay.children;
    let problem = '';
    if (q.roomCount === 0) problem = 'Hãy chọn ít nhất 1 phòng.';
    else if (q.capacity < guests) problem = `Các phòng đã chọn chứa tối đa ${q.capacity} khách, nhưng bạn có ${guests} khách. Hãy thêm phòng.`;
    $('selectMsg').hidden = !problem || q.roomCount === 0;   // chưa chọn phòng thì chỉ cần nút xám, không báo lỗi đỏ
    $('selectMsg').textContent = problem;

    const btn = $('btnGoToCheckout');
    const ok = !problem;
    btn.classList.toggle('btn--disabled', !ok);
    btn.setAttribute('aria-disabled', String(!ok));
    const next = stayToParams(stay, { id: item.id, rooms: stringifyRooms(rooms) });
    btn.href = ok ? `booking-page.html?${next}` : '#';

    history.replaceState(null, '', `?${next}${location.hash}`);   // F5 / quay lại vẫn giữ lựa chọn
  }

  // ---------- Form đổi ngày / khách ----------
  function setupStayForm() {
    const form = $('stayForm'), bar = $('stayBar');
    const fill = (sel, from, to, label) => sel.replaceChildren(...Array.from({ length: to - from + 1 }, (_, i) => {
      const o = document.createElement('option'); o.value = from + i; o.textContent = `${from + i} ${label}`; return o;
    }));
    fill($('adults'), 1, MAX_ADULTS, 'người lớn');
    fill($('children'), 0, MAX_CHILDREN, 'trẻ em');
    $('checkin').min = todayISO();

    const load = () => {
      $('checkin').value = stay.checkin; $('checkout').value = stay.checkout;
      $('adults').value = stay.adults;   $('children').value = stay.children;
      $('checkout').min = toISO(addDays(parseISO(stay.checkin), 1));
      $('stayError').textContent = '';
    };
    const toggle = open => {
      form.hidden = !open;
      $('stayEditBtn').setAttribute('aria-expanded', String(open));
      bar.classList.toggle('is-editing', open);
      if (open) load();
    };

    $('stayEditBtn').addEventListener('click', () => toggle(form.hidden));
    $('stayCancelBtn').addEventListener('click', () => toggle(false));
    $('checkin').addEventListener('change', () => {
      const v = $('checkin').value; if (!v) return;
      $('checkout').min = toISO(addDays(parseISO(v), 1));
      if (nightsBetween(v, $('checkout').value) === 0) $('checkout').value = toISO(addDays(parseISO(v), 1));
    });
    form.addEventListener('submit', e => {
      e.preventDefault();
      const next = { checkin: $('checkin').value, checkout: $('checkout').value,
                     adults: +$('adults').value, children: +$('children').value };
      if (!next.checkin || next.checkin < todayISO()) { $('stayError').textContent = 'Ngày nhận phòng không hợp lệ.'; return; }
      if (nightsBetween(next.checkin, next.checkout) === 0) { $('stayError').textContent = 'Ngày trả phòng phải sau ngày nhận phòng.'; return; }
      stay = next;
      toggle(false);
      refresh();
    });
  }

  // ---------- Menu phụ: đổi mục đang sáng theo vị trí cuộn ----------
  function setupSubNav() {
    const links = [...document.querySelectorAll('.sub-nav__link')];
    const sections = links.map(a => document.querySelector(a.getAttribute('href')));
    const sync = () => {
      const offset = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--header-h'), 10) + 90;
      let cur = 0;
      sections.forEach((s, i) => { if (s && s.getBoundingClientRect().top <= offset) cur = i; });
      links.forEach((a, i) => a.classList.toggle('is-active', i === cur));
    };
    window.addEventListener('scroll', sync, { passive: true });
    sync();
  }
}
