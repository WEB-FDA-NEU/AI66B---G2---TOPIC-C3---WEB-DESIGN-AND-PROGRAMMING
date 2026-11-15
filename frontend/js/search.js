// ============================================================
//  Tìm kiếm dùng chung cho các danh sách host / admin.
//  • foldText / matchesQuery: không phân biệt hoa-thường và dấu tiếng Việt ("da lat" khớp "Đà Lạt").
//    Mỗi từ trong ô tìm kiếm phải xuất hiện ở đâu đó trong các trường ("ha dalat" ≠ "ha da lat").
//    Backend (backend/search.py) dùng cùng quy tắc nên mock và API cho kết quả giống nhau.
//  • bindSearchbar: gắn hành vi cho khối <label class="searchbar"> (debounce, nút xóa, phím Esc).
//  • createSearchbar: tạo cùng khối đó bằng JS cho các mục admin dựng động.
// ============================================================
export const foldText = value => String(value ?? '')
  .normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').replace(/Đ/g, 'd').toLowerCase();

export const queryTokens = query => foldText(query).split(/\s+/).filter(Boolean);

export function matchesQuery(query, ...fields) {
  const needles = queryTokens(query);
  if (!needles.length) return true;
  const haystack = foldText(fields.join(' '));
  return needles.every(token => haystack.includes(token));
}

const SVG_NS = 'http://www.w3.org/2000/svg';

export function createSearchbar({ placeholder, label }) {
  const root = document.createElement('label');
  root.className = 'searchbar';
  const icon = document.createElementNS(SVG_NS, 'svg');
  icon.setAttribute('class', 'searchbar__icon');
  icon.setAttribute('viewBox', '0 0 24 24');
  icon.setAttribute('fill', 'none');
  icon.setAttribute('stroke', 'currentColor');
  icon.setAttribute('stroke-width', '2');
  icon.setAttribute('stroke-linecap', 'round');
  icon.setAttribute('aria-hidden', 'true');
  const circle = document.createElementNS(SVG_NS, 'circle');
  circle.setAttribute('cx', '11'); circle.setAttribute('cy', '11'); circle.setAttribute('r', '7');
  const handle = document.createElementNS(SVG_NS, 'path');
  handle.setAttribute('d', 'm20 20-3.5-3.5');
  icon.append(circle, handle);
  const text = document.createElement('span');
  text.className = 'sr-only'; text.textContent = label;
  const input = document.createElement('input');
  input.className = 'input'; input.type = 'search'; input.placeholder = placeholder; input.autocomplete = 'off';
  const clear = document.createElement('button');
  clear.type = 'button'; clear.className = 'searchbar__clear'; clear.setAttribute('aria-label', 'Xóa tìm kiếm'); clear.textContent = '×';
  root.append(icon, text, input, clear);
  return root;
}

/** onChange(query) được gọi sau `delay` ms kể từ lần gõ cuối (xóa bằng nút × hoặc Esc thì gọi ngay). */
export function bindSearchbar(root, onChange, { delay = 300 } = {}) {
  const input = root.querySelector('input');
  const clear = root.querySelector('.searchbar__clear');
  let timer = 0, last = input.value.trim();
  const fire = immediate => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const value = input.value.trim();
      if (value === last) return;     // chỉ khác khoảng trắng → không tải lại
      last = value; onChange(value);
    }, immediate ? 0 : delay);
  };
  const sync = () => root.classList.toggle('has-value', input.value !== '');
  input.addEventListener('input', () => { sync(); fire(false); });
  input.addEventListener('keydown', event => {
    if (event.key === 'Enter') { event.preventDefault(); fire(true); }
    if (event.key === 'Escape' && input.value) { input.value = ''; sync(); fire(true); }
  });
  clear?.addEventListener('click', () => { input.value = ''; sync(); fire(true); input.focus(); });
  sync();
  return {
    input,
    get value() { return input.value.trim(); },
    set(value) { input.value = value; sync(); last = input.value.trim(); },
  };
}
