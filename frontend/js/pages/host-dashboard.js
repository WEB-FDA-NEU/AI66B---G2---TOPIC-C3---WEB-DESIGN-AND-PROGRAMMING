import { ACCOUNT_API_MODE, accountHref, safeImageURL } from '../config.js';
import { initHostDashboardNavigation } from '../host-navigation.js';
import { getHostDashboard } from '../api.js';
// ============================================================
//  Host Dashboard: số liệu + biểu đồ tính từ dữ liệu host (getHost*), có bộ lọc kỳ.
//  Quy ước tính (hiện ngay trên giao diện để người xem hiểu số):
//   • Doanh thu / lượt đặt / tỉ lệ trạng thái: theo NGÀY ĐẶT (createdAt) nằm trong kỳ.
//   • Doanh thu chỉ cộng đơn confirmed | checked_in | completed (không cộng pending/cancelled/rejected).
//   • Công suất = số đêm có khách trong kỳ ÷ (số phòng × số ngày trong kỳ).
// ============================================================
import { getHostHomestays, getHostRooms, getHostBookings } from '../api.js';
import { formatVND } from '../render.js';
import { periodTabs, getWindow, inWindow, bucketIndex, dayNum, fmtFullDate, fmtInt, fmtPct, fmtVND,
         countUp, drawChart, axisOptions, theme, centerTextPlugin } from '../charts.js';
import '../components/site-header.js';
import '../components/site-footer.js';
import '../guard.js';


const STATUS_LABEL = {
  pending: 'Chờ xác nhận', confirmed: 'Đã xác nhận', checked_in: 'Đã nhận phòng',
  completed: 'Hoàn tất', cancelled: 'Đã hủy', rejected: 'Bị từ chối',
};
const STATUS_BADGE = {
  pending: 'badge--warning', confirmed: 'badge--success', checked_in: 'badge--success',
  completed: '', cancelled: 'badge--danger', rejected: 'badge--danger',
};
const MONEY_STATUSES = new Set(['confirmed', 'checked_in', 'completed']);   // tính doanh thu và chiếm phòng

const $ = id => document.getElementById(id);
const make = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

let homestays = [], rooms = [], bookings = [], roomsById = {}, roomsByHs = {}, hsById = {};
let anchor = 0;
let requestGeneration = 0;
let tabs;

async function load() {
  try {
    if (ACCOUNT_API_MODE) {
      anchor = dayNum(new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()));
      $('kpi-revenue').nextElementSibling.textContent = 'Gi\u00e1 tr\u1ecb booking';
      $('revenue-title').nextElementSibling.textContent = 'Booking \u0111\u00e3 x\u00e1c nh\u1eadn, \u0111ang \u1edf ho\u1eb7c ho\u00e0n t\u1ea5t; kh\u00f4ng ph\u1ea3i ti\u1ec1n \u0111\u00e3 thu.';
      $('chart-occupancy').closest('article').querySelector('.dash-note').textContent = 'C\u00f4ng su\u1ea5t d\u1ef1 ki\u1ebfn tr\u00ean t\u1ed3n kho hi\u1ec7n t\u1ea1i; bi\u1ec3u \u0111\u1ed3 t\u1ed1i \u0111a 100 homestay. Ch\u01b0a c\u00f3 l\u1ecbch s\u1eed t\u1ed3n kho.';
      tabs = periodTabs($('period-tabs'), { initial: 'year', onChange: renderApi });
      await renderApi(tabs.value); return;
    }
    [homestays, rooms, bookings] = await Promise.all([getHostHomestays(), getHostRooms(), getHostBookings()]);
    roomsById = Object.fromEntries(rooms.map(r => [r.id, r]));
    hsById = Object.fromEntries(homestays.map(h => [h.id, h]));
    // Chỉ tính phòng thuộc homestay còn hoạt động của host này
    rooms = rooms.filter(r => hsById[r.homestayId]);
    roomsByHs = {};
    rooms.forEach(r => (roomsByHs[r.homestayId] ??= []).push(r));
    anchor = bookings.length ? Math.max(...bookings.map(b => dayNum(b.createdAt))) : dayNum(new Date().toISOString());

    renderCurrentStats();
    renderRecent();
    tabs = periodTabs($('period-tabs'), { initial: 'year', onChange: render });
    render(tabs.value);
  } catch (e) {
    $('recent').replaceChildren(make('p', 'text-danger', `Không tải được dữ liệu. ${e.detail ?? ''}`));
    console.error(e);
  } finally {
    window.dispatchEvent(new Event('host-dashboard-ready'));
  }
}

async function renderApi(key) {
  const generation = ++requestGeneration;
  const w = getWindow(key, anchor), date = day => new Date(day * 864e5).toISOString().slice(0, 10);
  $('period-note').textContent = '\u0110ang t\u1ea3i s\u1ed1 li\u1ec7u m\u00e1y ch\u1ee7...';
  try {
    const data = await getHostDashboard({ from: date(w.start), to: date(w.end) });
    if (generation !== requestGeneration) return;
    const stats = [[data.homestayCounts.active || 0, 'Homestay \u0111ang ho\u1ea1t \u0111\u1ed9ng'], [data.inventoryCount, 'T\u1ed5ng s\u1ed1 ph\u00f2ng'], [data.bookingCount, 'T\u1ed5ng booking'], [data.periodBookingCount, 'Booking trong k\u1ef3']];
    $('stats').replaceChildren(...stats.map(([value, label]) => { const card = make('div', 'stat-card'); const number = make('div', 'stat-card__num'); card.append(number, make('div', 'stat-card__label', label)); countUp(number, value); return card; }));
    countUp($('kpi-revenue'), data.bookingValue, fmtVND); countUp($('kpi-bookings'), data.periodBookingCount); countUp($('kpi-occupancy'), data.occupancySummary.occupancy, fmtPct);
    const revenue = w.buckets.map(() => 0);
    for (const row of data.series) { const i = bucketIndex(w, row.date); if (i >= 0) revenue[i] += row.bookingValue; }
    renderRevenueChart({ w, revenue, totalRevenue: data.bookingValue });
    $('revenue-title').textContent = 'Gi\u00e1 tr\u1ecb booking theo k\u1ef3';
    renderStatusChart({ inP: { length: data.periodBookingCount }, byStatus: data.statusCounts });
    renderOccupancyChart({ w, totalNights: data.occupancySummary.nights, perHs: data.occupancy.map(row => ({ ...row, pct: row.occupancy })) });
    bookings = data.recentBookings; rooms = data.rooms; homestays = data.homestays;
    roomsById = Object.fromEntries(rooms.map(row => [row.id, row])); hsById = Object.fromEntries(homestays.map(row => [row.id, row])); renderRecent();
    $('period-note').textContent = `${fmtFullDate(w.start)} \u2013 ${fmtFullDate(w.end)} \u00b7 Thu th\u1ef1c ghi nh\u1eadn ${formatVND(data.payments.grossCaptured)} \u00b7 Ho\u00e0n ch\u1edd ${formatVND(data.payments.refundPending)} \u00b7 M\u00f4 ph\u1ecfng ${formatVND(data.payments.simulatedCaptured)} (kh\u00f4ng ph\u1ea3i giao d\u1ecbch ng\u00e2n h\u00e0ng).`;
  } catch (error) {
    if (generation !== requestGeneration) return;
    $('period-note').textContent = error.detail || 'Kh\u00f4ng t\u1ea3i \u0111\u01b0\u1ee3c s\u1ed1 li\u1ec7u.';
    for (const id of ['kpi-revenue', 'kpi-bookings', 'kpi-occupancy']) $(id).textContent = '\u2014';
  }
}

// ---------- Số liệu "hiện tại" (không phụ thuộc kỳ) ----------
function renderCurrentStats() {
  const today = new Date().toISOString().slice(0, 10);
  const upcoming = bookings.filter(b => ['confirmed', 'checked_in'].includes(b.status) && b.checkOut >= today);
  const items = [
    [homestays.length, 'Homestay đang hoạt động', ''],
    [rooms.length, 'Phòng', ''],
    [upcoming.length, 'Đặt phòng sắp tới', ''],
    [bookings.filter(b => b.status === 'pending').length, 'Đơn chờ duyệt', 'is-warning'],
  ];
  $('stats').replaceChildren(...items.map(([num, label, cls]) => {
    const card = make('div', 'stat-card');
    const n = make('div', `stat-card__num ${cls}`.trim(), '0');
    card.append(n, make('div', 'stat-card__label', label));
    countUp(n, num);
    return card;
  }));
}

// ---------- Tính theo kỳ ----------
function compute(key) {
  const w = getWindow(key, anchor);
  const inP = bookings.filter(b => inWindow(w, b.createdAt));

  const revenue = w.buckets.map(() => 0);
  inP.forEach(b => {
    if (!MONEY_STATUSES.has(b.status)) return;
    const i = bucketIndex(w, b.createdAt);
    if (i >= 0) revenue[i] += Number(b.totalPrice) || 0;
  });

  const byStatus = {};
  inP.forEach(b => { byStatus[b.status] = (byStatus[b.status] ?? 0) + 1; });

  // Công suất: đếm số đêm của từng đơn rơi vào cửa sổ [start, end]
  const perHs = homestays
    .filter(h => roomsByHs[h.id]?.length)
    .map(h => ({ id: h.id, name: h.name, roomCount: roomsByHs[h.id].length, nights: 0, orders: 0, capacity: 0, pct: 0 }));
  const perHsById = Object.fromEntries(perHs.map(p => [p.id, p]));
  const endExclusive = w.end + 1;
  bookings.filter(b => MONEY_STATUSES.has(b.status)).forEach(b => {
    const p = perHsById[roomsById[b.roomId]?.homestayId];
    if (!p) return;
    const nights = Math.min(dayNum(b.checkOut), endExclusive) - Math.max(dayNum(b.checkIn), w.start);
    if (nights > 0) { p.nights += nights; p.orders += 1; }
  });
  perHs.forEach(p => { p.capacity = p.roomCount * w.days; p.pct = Math.min(100, (p.nights / p.capacity) * 100); });
  perHs.sort((a, b) => b.pct - a.pct);
  const totalNights = perHs.reduce((s, p) => s + p.nights, 0);
  const totalCap = perHs.reduce((s, p) => s + p.capacity, 0);

  return {
    w, inP, revenue, byStatus, perHs,
    totalRevenue: revenue.reduce((s, v) => s + v, 0),
    occupancy: totalCap ? Math.min(100, (totalNights / totalCap) * 100) : 0,
    totalNights,
  };
}

function render(key) {
  const d = compute(key);
  const { w } = d;

  $('period-note').textContent =
    `Dữ liệu tính đến ${fmtFullDate(anchor)} · Kỳ: ${w.label} (${fmtFullDate(w.start)} – ${fmtFullDate(w.end)})`;

  countUp($('kpi-revenue'), d.totalRevenue, fmtVND);
  countUp($('kpi-bookings'), d.inP.length);
  countUp($('kpi-occupancy'), d.occupancy, fmtPct);

  renderRevenueChart(d);
  renderStatusChart(d);
  renderOccupancyChart(d);
}

// ---------- Biểu đồ ----------
function renderRevenueChart({ w, revenue, totalRevenue }) {
  const t = theme();
  const unit = w.unit === 'month' ? 'tháng' : 'ngày';
  $('revenue-title').textContent = `Doanh thu theo ${unit}`;
  drawChart($('chart-revenue'), {
    type: 'bar',
    data: { labels: w.buckets.map(b => b.label), datasets: [{ label: ACCOUNT_API_MODE ? 'Gi\u00e1 tr\u1ecb booking' : 'Doanh thu', data: revenue,
      backgroundColor: t.primary, hoverBackgroundColor: t.dark, borderRadius: 5, maxBarThickness: 44 }] },
    options: {
      responsive: true, maintainAspectRatio: false,
      scales: axisOptions({ money: true, maxTicks: w.key === '30d' ? 10 : 12 }),
      plugins: { legend: { display: false },
        tooltip: { callbacks: { label: c => ` ${fmtVND(c.parsed.y)}` } } },
    },
  }, {
    emptyText: totalRevenue ? '' : 'Chưa có doanh thu trong kỳ này.',
    label: `Biểu đồ cột doanh thu theo ${unit}, tổng ${fmtVND(totalRevenue)}`,
  });
}

const STATUS_ORDER = ['completed', 'confirmed', 'checked_in', 'pending', 'cancelled', 'rejected'];
function renderStatusChart({ inP, byStatus }) {
  const t = theme();
  const color = { completed: t.dark, confirmed: t.primary, checked_in: '#2f6690', pending: t.accent, cancelled: '#8a9a94', rejected: t.danger };
  const keys = STATUS_ORDER.filter(k => byStatus[k]);
  drawChart($('chart-status'), {
    type: 'doughnut',
    data: { labels: keys.map(k => STATUS_LABEL[k]), datasets: [{ data: keys.map(k => byStatus[k]),
      backgroundColor: keys.map(k => color[k]), borderColor: '#fff', borderWidth: 2, hoverOffset: 6 }] },
    plugins: [centerTextPlugin],
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '64%',
      plugins: {
        legend: { position: 'bottom' },
        centerText: { text: fmtInt(inP.length), caption: 'đơn đặt' },
        tooltip: { callbacks: { label: c => ` ${c.label}: ${c.parsed} đơn (${fmtPct((c.parsed / inP.length) * 100)})` } },
      },
    },
  }, {
    emptyText: inP.length ? '' : 'Chưa có đơn đặt phòng trong kỳ này.',
    label: `Biểu đồ donut trạng thái: ${keys.map(k => `${STATUS_LABEL[k]} ${byStatus[k]}`).join(', ')}`,
  });
}

function renderOccupancyChart({ perHs, totalNights, w }) {
  const t = theme();
  // Trục X tự co theo số lớn nhất (tối đa 100%) để các cột không bị dẹt khi công suất thấp
  const maxPct = Math.max(0, ...perHs.map(p => p.pct));
  const xMax = Math.min(100, Math.max(20, Math.ceil(maxPct / 10) * 10 + 10));
  drawChart($('chart-occupancy'), {
    type: 'bar',
    data: { labels: perHs.map(p => p.name), datasets: [{ label: 'Công suất', data: perHs.map(p => Math.round(p.pct * 10) / 10),
      backgroundColor: t.primary, hoverBackgroundColor: t.dark,
      borderRadius: 5, maxBarThickness: 26 }] },
    options: {
      indexAxis: 'y', responsive: true, maintainAspectRatio: false,
      scales: {
        x: { min: 0, max: xMax, grid: { color: t.border }, border: { display: false }, ticks: { callback: v => `${v}%` } },
        // Tên homestay dài thì cắt bớt, tên đầy đủ vẫn xem được ở tooltip
        y: { grid: { display: false }, ticks: { callback(v) { const n = this.getLabelForValue(v); return n.length > 24 ? `${n.slice(0, 23)}…` : n; } } },
      },
      plugins: { legend: { display: false },
        tooltip: { callbacks: { title: items => perHs[items[0].dataIndex].name, label: c => {
          const p = perHs[c.dataIndex];
          return [` Công suất: ${fmtPct(p.pct)}`, ` ${p.nights} đêm có khách / ${p.capacity} đêm-phòng (${p.roomCount} phòng × ${w.days} ngày)`];
        } } } },
    },
  }, {
    emptyText: totalNights ? '' : 'Chưa có đêm nào có khách trong kỳ này.',
    label: `Biểu đồ cột ngang công suất phòng của ${perHs.length} homestay`,
  });
}

// ---------- Đặt phòng gần đây (có ảnh thật) ----------
function renderRecent() {
  const recent = [...bookings].sort((a, b) => b.createdAt.localeCompare(a.createdAt)).slice(0, 5);
  if (!recent.length) { $('recent').replaceChildren(make('p', 'text-muted', 'Chưa có đặt phòng nào.')); return; }

  const wrap = make('div', 'stack host-dashboard-recent-list');
  recent.forEach(b => {
    const room = roomsById[b.roomId];
    const hs = hsById[room?.homestayId];
    const row = make('div', 'row host-dashboard-booking-row');

    const img = make('img', 'row__img');
    img.src = safeImageURL(ACCOUNT_API_MODE ? b.homestayImage || 'img/placeholder.svg' : room?.images?.[0] ?? hs?.images?.[0] ?? 'img/placeholder.svg');
    img.alt = room ? `${room.name} — ${hs?.name ?? ''}` : '';
    img.loading = 'lazy';
    img.onerror = () => { img.onerror = null; img.src = 'img/placeholder.svg'; };   // ảnh hỏng → ảnh mặc định

    const info = make('div', 'host-dashboard-booking-info');
    const title = make('a', 'row__title', b.customerName); title.href = accountHref('host-bookings.html');
    info.append(title,
      make('p', 'row__meta', (ACCOUNT_API_MODE ? [b.homestayName, b.roomName] : [hs?.name, room?.name]).filter(Boolean).join(' · ')),
      make('p', 'row__meta', `${b.checkIn} → ${b.checkOut} · ${b.guests} khách`));

    const side = make('div', 'host-dashboard-booking-status');
    side.append(make('span', `badge ${STATUS_BADGE[b.status] ?? ''}`.trim(), STATUS_LABEL[b.status] ?? b.status),
                make('p', 'row__price mt-3', formatVND(b.totalPrice)));

    row.append(img, info, side);
    wrap.append(row);
  });
  $('recent').replaceChildren(wrap);
}

initHostDashboardNavigation();
load();