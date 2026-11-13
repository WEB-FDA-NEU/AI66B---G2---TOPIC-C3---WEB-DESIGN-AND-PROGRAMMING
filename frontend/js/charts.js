// ============================================================
//  Tiện ích DÙNG CHUNG cho Host Dashboard và Admin Dashboard:
//  - bộ lọc kỳ (7 ngày / 30 ngày / Năm) + chia "bucket" theo ngày hoặc tháng
//  - hiệu ứng count-up cho số liệu
//  - vẽ biểu đồ bằng Chart.js (nạp qua CDN bằng thẻ <script> trong HTML → window.Chart)
//
//  Mốc thời gian ("neo"): ngày MỚI NHẤT có trong dữ liệu, để bộ lọc 7/30 ngày luôn có số liệu
//  dù dữ liệu mock là tĩnh. Khi nối backend thật thì neo = ngày hôm nay (xem getWindow()).
//  Mọi phép tính ngày dùng số ngày UTC (dayNum) → không bị lệch múi giờ.
// ============================================================

// ---------- Ngày & kỳ ----------
const DAY = 864e5;
export const dayNum = s => { const [y, m, d] = String(s).slice(0, 10).split('-').map(Number); return Math.floor(Date.UTC(y, m - 1, d) / DAY); };
const toDate = n => new Date(n * DAY);
const pad = n => String(n).padStart(2, '0');
export const fmtDayLabel = n => { const d = toDate(n); return `${pad(d.getUTCDate())}/${pad(d.getUTCMonth() + 1)}`; };
export const fmtFullDate = n => { const d = toDate(n); return `${pad(d.getUTCDate())}/${pad(d.getUTCMonth() + 1)}/${d.getUTCFullYear()}`; };

export const PERIODS = [
  { key: '7d', label: '7 ngày' },
  { key: '30d', label: '30 ngày' },
  { key: 'year', label: 'Năm' },
];

/** Cửa sổ thời gian + các "bucket" để vẽ trục X. start/end là SỐ NGÀY, đã bao gồm cả hai đầu. */
export function getWindow(key, anchor) {
  if (key === 'year') {
    const a = toDate(anchor), y = a.getUTCFullYear(), m = a.getUTCMonth();
    const start = Math.floor(Date.UTC(y, 0, 1) / DAY);
    const buckets = Array.from({ length: m + 1 }, (_, i) => ({
      label: `T${i + 1}`,
      start: Math.floor(Date.UTC(y, i, 1) / DAY),
      end: Math.min(Math.floor(Date.UTC(y, i + 1, 1) / DAY) - 1, anchor),
    }));
    return { key, start, end: anchor, days: anchor - start + 1, unit: 'month', buckets, label: `Năm ${y}` };
  }
  const days = key === '7d' ? 7 : 30;
  const start = anchor - days + 1;
  const buckets = Array.from({ length: days }, (_, i) => ({ label: fmtDayLabel(start + i), start: start + i, end: start + i }));
  return { key, start, end: anchor, days, unit: 'day', buckets, label: `${days} ngày gần nhất` };
}
export const inWindow = (w, dateStr) => { const d = dayNum(dateStr); return d >= w.start && d <= w.end; };
export const bucketIndex = (w, dateStr) => { const d = dayNum(dateStr); return w.buckets.findIndex(b => d >= b.start && d <= b.end); };

// ---------- Định dạng số ----------
export const fmtInt = n => Math.round(n).toLocaleString('vi-VN');
export const fmtPct = n => `${(Math.round(n * 10) / 10).toLocaleString('vi-VN')}%`;
export const fmtVND = n => `${Math.round(n).toLocaleString('vi-VN')} ₫`;
/** Rút gọn cho nhãn trục: 1.250.000 → "1,3 tr", 2.400.000.000 → "2,4 tỷ" */
export function fmtShortVND(n) {
  const a = Math.abs(n), f = x => (Math.round(x * 10) / 10).toLocaleString('vi-VN');
  if (a >= 1e9) return `${f(n / 1e9)} tỷ`;
  if (a >= 1e6) return `${f(n / 1e6)} tr`;
  if (a >= 1e3) return `${f(n / 1e3)}k`;
  return String(n);
}

// ---------- Count-up ----------
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
/** Đếm từ giá trị đang hiện tới `to`. Người dùng bật "giảm chuyển động" thì hiện luôn, không chạy hiệu ứng. */
export function countUp(el, to, format = fmtInt, duration = 900) {
  if (!el) return;
  const from = el._cuValue ?? 0;
  cancelAnimationFrame(el._cuRaf);
  el._cuValue = to;
  if (reduceMotion || from === to) { el.textContent = format(to); return; }
  const t0 = performance.now();
  const step = now => {
    const p = Math.min(1, (now - t0) / duration);
    const eased = 1 - Math.pow(1 - p, 3);           // chậm dần về cuối
    el.textContent = format(from + (to - from) * eased);
    if (p < 1) el._cuRaf = requestAnimationFrame(step);
  };
  el._cuRaf = requestAnimationFrame(step);
}

// ---------- Bộ lọc kỳ ----------
/** Dựng nhóm nút "7 ngày | 30 ngày | Năm" vào `container`; gọi onChange(key) khi đổi. Trả về { get value }. */
export function periodTabs(container, { initial = 'year', onChange }) {
  let current = initial;
  container.classList.add('period-tabs');
  container.setAttribute('role', 'group');
  container.setAttribute('aria-label', 'Chọn kỳ thống kê');
  const buttons = PERIODS.map(p => {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'period-tabs__btn'; b.textContent = p.label; b.dataset.key = p.key;
    b.addEventListener('click', () => {
      if (current === p.key) return;
      current = p.key; sync(); onChange(current);
    });
    return b;
  });
  const sync = () => buttons.forEach(b => { const on = b.dataset.key === current; b.classList.toggle('is-active', on); b.setAttribute('aria-pressed', String(on)); });
  container.replaceChildren(...buttons);
  sync();
  return { get value() { return current; } };
}

// ---------- Màu theo theme của dự án (đọc từ tokens.css, không viết cứng) ----------
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
export function theme() {
  return {
    primary: css('--c-primary-l') || '#11695f', dark: css('--c-primary') || '#0f3d38',
    accent: css('--c-accent') || '#c28a2c', warning: css('--c-warning') || '#b54708',
    success: css('--c-success') || '#067647', danger: css('--c-danger') || '#b42318',
    muted: css('--c-muted') || '#5a6761', border: css('--c-border') || '#dbe3df',
    text: css('--c-text') || '#1c2421', font: css('--font') || 'system-ui, sans-serif',
  };
}
/** Bảng màu cho các lát cắt (6 màu + màu xám cho mục "Khác") */
export function palette() {
  const t = theme();
  return [t.primary, t.accent, '#2f6690', '#b5532a', '#7aa874', '#7a4e7e', '#8a9a94'];
}

// ---------- Vẽ biểu đồ ----------
let defaultsSet = false;
function setDefaults() {
  if (defaultsSet || !window.Chart) return;
  const t = theme();
  Chart.defaults.font.family = t.font;
  Chart.defaults.font.size = 13;
  Chart.defaults.color = t.muted;
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxWidth = 8;
  Chart.defaults.plugins.legend.labels.boxHeight = 8;     // chấm chú thích nhỏ gọn
  Chart.defaults.plugins.tooltip.padding = 10;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.animation.duration = reduceMotion ? 0 : 700;
  defaultsSet = true;
}

/**
 * Vẽ (hoặc vẽ lại) biểu đồ vào <canvas>. Canvas phải nằm trong `.chart-box` có sẵn <p class="chart-msg" hidden>.
 *  - emptyText: nếu có → không vẽ, hiện thông báo "không có dữ liệu" thay vì biểu đồ trống.
 *  - Chart.js không tải được (mất mạng/CDN lỗi) → hiện thông báo, trang vẫn dùng được (các số liệu vẫn hiện).
 */
export function drawChart(canvas, config, { emptyText = '', label = '' } = {}) {
  const box = canvas.parentElement, msg = box.querySelector('.chart-msg');
  if (window.Chart) Chart.getChart(canvas)?.destroy();
  const showMsg = text => { canvas.hidden = true; msg.hidden = false; msg.textContent = text; return null; };
  if (!window.Chart) return showMsg('Không tải được thư viện biểu đồ (cần kết nối Internet). Các số liệu bên trên vẫn đúng.');
  if (emptyText) return showMsg(emptyText);
  setDefaults();
  canvas.hidden = false; msg.hidden = true;
  if (label) canvas.setAttribute('aria-label', label);
  return new Chart(canvas, config);
}

/** Tùy chọn trục dùng chung cho biểu đồ cột/đường */
export function axisOptions({ money = false, maxTicks = 12 } = {}) {
  const t = theme();
  return {
    x: { grid: { display: false }, ticks: { maxTicksLimit: maxTicks, maxRotation: 0 } },
    y: { beginAtZero: true, grid: { color: t.border }, border: { display: false },
         ticks: { precision: 0, callback: v => money ? fmtShortVND(v) : v } },
  };
}

/** Plugin: hiện số tổng ở giữa biểu đồ donut */
export const centerTextPlugin = {
  id: 'centerText',
  afterDraw(chart, _args, opts) {
    if (!opts || opts.text == null) return;
    const { ctx, chartArea: { left, right, top, bottom } } = chart;
    const x = (left + right) / 2, y = (top + bottom) / 2, t = theme();
    ctx.save();
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = t.dark; ctx.font = `700 26px ${t.font}`;
    ctx.fillText(opts.text, x, y - 8);
    ctx.fillStyle = t.muted; ctx.font = `13px ${t.font}`;
    ctx.fillText(opts.caption ?? '', x, y + 16);
    ctx.restore();
  },
};