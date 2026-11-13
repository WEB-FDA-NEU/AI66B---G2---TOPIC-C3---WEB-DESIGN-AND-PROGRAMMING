// ============================================================
//  Admin Dashboard: số liệu + biểu đồ tính từ getAdminOverview() (mock: admin-overview.json + items.json).
//  Không còn con số viết cứng trong HTML.
//   • "User mới" / đường tăng trưởng / cơ cấu theo tỉnh: theo NGÀY TẠO (createdAt) trong kỳ.
//   • Tỉnh/thành: phần cuối của location (sau dấu phẩy cuối) của homestay mà đơn đặt.
//   • "Đơn chờ duyệt" đếm trực tiếp từ danh sách đơn xin làm host trên trang → duyệt/từ chối là số tự giảm.
// ============================================================
import { getAdminOverview } from '../api.js';
import { periodTabs, getWindow, inWindow, bucketIndex, dayNum, fmtFullDate, fmtInt, fmtPct,
         countUp, drawChart, axisOptions, theme, palette } from '../charts.js';

const $ = id => document.getElementById(id);

let users = [], bookings = [], homestays = [], provinceOf = {};
let anchor = 0, tabs;

const province = loc => (loc ?? '').split(',').pop().trim() || 'Khác';

async function load() {
  try {
    ({ users, bookings, homestays } = await getAdminOverview());
    provinceOf = Object.fromEntries(homestays.map(h => [h.id, province(h.location)]));
    anchor = Math.max(...[...users, ...bookings].map(x => dayNum(x.createdAt)));

    countUp($('kpi-homestays'), homestays.length);
    countUp($('kpi-bookings-total'), bookings.length);
    watchPending();

    tabs = periodTabs($('period-tabs'), { initial: 'year', onChange: render });
    render(tabs.value);
  } catch (e) {
    console.error(e);
    $('period-note').textContent = `Không tải được số liệu. ${e.detail ?? ''}`;
    $('period-note').classList.add('text-danger');
  }
}

// ---------- Đơn chờ duyệt: đếm từ danh sách đơn trên trang, tự cập nhật khi Duyệt/Từ chối ----------
function watchPending() {
  const list = $('application-list');
  const count = () => list.querySelectorAll('[data-status="pending"]').length;
  countUp($('kpi-pending'), count());
  new MutationObserver(() => countUp($('kpi-pending'), count()))
    .observe(list, { subtree: true, attributes: true, attributeFilter: ['data-status'] });
}

// ---------- Theo kỳ ----------
function render(key) {
  const w = getWindow(key, anchor);
  $('period-note').textContent =
    `Dữ liệu tính đến ${fmtFullDate(anchor)} · Kỳ: ${w.label} (${fmtFullDate(w.start)} – ${fmtFullDate(w.end)})`;
  $('kpi-period-label').textContent = key === 'year' ? 'trong năm' : `${w.days} ngày qua`;
  $('growth-note').textContent = `Số lượng mới theo từng ${w.unit === 'month' ? 'tháng' : 'ngày'} trong kỳ`;

  const newUsers = users.filter(u => inWindow(w, u.createdAt));
  const newBookings = bookings.filter(b => inWindow(w, b.createdAt));
  countUp($('kpi-users-new'), newUsers.length);

  renderGrowth(w, newUsers, newBookings);
  renderProvince(newBookings);
}

function renderGrowth(w, newUsers, newBookings) {
  const t = theme();
  const series = list => { const a = w.buckets.map(() => 0); list.forEach(x => { const i = bucketIndex(w, x.createdAt); if (i >= 0) a[i]++; }); return a; };
  const u = series(newUsers), b = series(newBookings);
  const line = (label, data, color) => ({ label, data, borderColor: color, backgroundColor: color + '22', fill: true,
    tension: .35, borderWidth: 2.5, pointRadius: w.unit === 'month' ? 4 : 2, pointHoverRadius: 6, pointBackgroundColor: color });
  drawChart($('chart-growth'), {
    type: 'line',
    data: { labels: w.buckets.map(x => x.label), datasets: [line('Booking mới', b, t.primary), line('User mới', u, t.accent)] },
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false },
      scales: axisOptions({ maxTicks: w.key === '30d' ? 10 : 12 }),
      plugins: { legend: { position: 'top', align: 'end' } },
    },
  }, {
    emptyText: (newUsers.length || newBookings.length) ? '' : 'Chưa có dữ liệu trong kỳ này.',
    label: `Biểu đồ đường: ${newUsers.length} user mới và ${newBookings.length} booking mới trong kỳ`,
  });
}

function renderProvince(newBookings) {
  const counts = {};
  newBookings.forEach(x => { const p = provinceOf[x.itemId] ?? 'Khác'; counts[p] = (counts[p] ?? 0) + 1; });
  const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  const top = sorted.slice(0, 5), rest = sorted.slice(5).reduce((s, [, n]) => s + n, 0);
  if (rest) top.push(['Khác', rest]);
  const total = newBookings.length, pal = palette();
  drawChart($('chart-province'), {
    type: 'doughnut',
    data: { labels: top.map(([p]) => p), datasets: [{ data: top.map(([, n]) => n),
      backgroundColor: top.map(([p], i) => (p === 'Khác' ? pal[6] : pal[i])), borderColor: '#fff', borderWidth: 2, hoverOffset: 6 }] },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '58%',
      plugins: {
        legend: { position: 'bottom' },
        tooltip: { callbacks: { label: c => ` ${c.label}: ${fmtInt(c.parsed)} đơn (${fmtPct((c.parsed / total) * 100)})` } },
      },
    },
  }, {
    emptyText: total ? '' : 'Chưa có đơn đặt phòng trong kỳ này.',
    label: `Biểu đồ donut cơ cấu đơn theo tỉnh: ${top.map(([p, n]) => `${p} ${n}`).join(', ')}`,
  });
}

load();