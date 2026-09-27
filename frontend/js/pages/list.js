// ============================================================
//  Trang tìm homestay — viết theo đúng MẪU của js/pages/shop.js
//  (đọc bộ lọc từ URL, showSkeleton/showEmpty/showError, phân trang).
// ============================================================
import { getItems, ApiError } from '../api.js';
import { renderCard, renderList } from '../render.js';
import { showSkeleton, showEmpty, showError } from '../ui.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const grid        = document.getElementById('results');
const form        = document.getElementById('filter-form');
const sortSel     = document.getElementById('sort');
const summary     = document.getElementById('result-summary');
const resultsCount = document.getElementById('results-count');
const pager       = document.getElementById('pagination');

if (!grid || !form) {
  console.error('list.js cần #results và #filter-form trong HTML.');
  throw new Error('Thiếu phần tử bắt buộc');
}

const PAGE_SIZE = 6;

// ---------- Bộ lọc đọc từ URL, không từ biến toàn cục ----------
// Nhờ vậy: nút Back chạy đúng, và copy link gửi bạn ra đúng kết quả.
function readFilters() {
  const p = new URLSearchParams(location.search);
  return {
    q:         p.get('q') ?? '',
    min_price: p.get('min_price') ?? '',
    max_price: p.get('max_price') ?? '',
    room_type: p.getAll('room_type'),   // nhiều checkbox cùng tên → nhiều giá trị
    amenity:   p.getAll('amenity'),
    rating:    p.get('rating') ?? '',
    sort:      p.get('sort') ?? 'newest',
    page:      Number(p.get('page') ?? 1),
    page_size: PAGE_SIZE,
  };
}

/** Đổ ngược bộ lọc lên giao diện để người dùng thấy mình đang lọc gì. */
function syncControls(f) {
  form.q.value         = f.q;
  form.min_price.value = f.min_price;
  form.max_price.value = f.max_price;
  sortSel.value         = f.sort;

  form.querySelectorAll('input[name="room_type"]').forEach(cb => { cb.checked = f.room_type.includes(cb.value); });
  form.querySelectorAll('input[name="amenity"]').forEach(cb => { cb.checked = f.amenity.includes(cb.value); });
  form.querySelectorAll('input[name="rating"]').forEach(r => { r.checked = r.value === f.rating; });
}

/** Ghi bộ lọc vào URL rồi tải lại. URL là nguồn sự thật duy nhất. */
function apply(patch = {}) {
  const next = { ...readFilters(), ...patch };
  if (!('page' in patch)) next.page = 1;          // đổi bộ lọc thì về trang 1

  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(next)) {
    if (k === 'page_size') continue;
    if (k === 'page' && v === 1) continue;
    if (Array.isArray(v)) { v.forEach(val => val && qs.append(k, val)); continue; }
    if (v !== '' && v != null) qs.set(k, v);
  }
  history.pushState({}, '', qs.toString() ? `?${qs}` : location.pathname);
  load();
}

// ---------- Phân trang ----------
function renderPagination(total, page) {
  const pages = Math.ceil(total / PAGE_SIZE);
  pager.replaceChildren();
  if (pages <= 1) return;

  const add = (label, targetPage, { active = false, disabled = false } = {}) => {
    const b = document.createElement('button');
    b.className = 'btn' + (active ? ' is-active' : '');
    b.type = 'button';
    b.textContent = label;
    if (disabled) b.disabled = true;
    else b.addEventListener('click', () => apply({ page: targetPage }));
    if (active) b.setAttribute('aria-current', 'page');
    pager.append(b);
  };

  add('‹ Trước', page - 1, { disabled: page === 1 });
  for (let i = 1; i <= pages; i++) add(String(i), i, { active: i === page });
  add('Sau ›', page + 1, { disabled: page === pages });
}

// ---------- Tải dữ liệu: bốn trạng thái ----------
async function load() {
  const f = readFilters();
  syncControls(f);

  showSkeleton(grid, PAGE_SIZE);                        // 1. ĐANG TẢI
  pager.replaceChildren();
  try {
    const { items, total } = await getItems(f);

    if (items.length === 0) {                           // 2. RỖNG
      summary.textContent = '';
      if (resultsCount) resultsCount.textContent = '';
      return showEmpty(grid, {
        title: f.q ? `Không tìm thấy homestay nào cho “${f.q}”` : 'Chưa có homestay nào',
        hint : 'Thử bỏ bớt bộ lọc hoặc đổi địa điểm.',
        actionText: 'Xóa bộ lọc', actionHref: 'search.html',
      });
    }

    summary.textContent = `${total} kết quả`;
    if (resultsCount) resultsCount.textContent = `${total} chỗ nghỉ`;
    renderList(grid, items, renderCard);                 // 3. CÓ DỮ LIỆU
    renderPagination(total, f.page);
  } catch (err) {                                        // 4. LỖI
    summary.textContent = '';
    if (resultsCount) resultsCount.textContent = '';
    showError(grid, err instanceof ApiError ? err : null, load);
  }
}

// ---------- Sự kiện ----------
form.addEventListener('submit', e => {
  e.preventDefault();
  const d = new FormData(form);
  apply({
    q:         d.get('q') ?? '',
    min_price: d.get('min_price') ?? '',
    max_price: d.get('max_price') ?? '',
    room_type: d.getAll('room_type'),
    amenity:   d.getAll('amenity'),
    rating:    d.get('rating') ?? '',
  });
});

sortSel.addEventListener('change', () => apply({ sort: sortSel.value }));

document.getElementById('clear-filters')?.addEventListener('click', () => { location.href = 'search.html'; });

window.addEventListener('popstate', load);

load();