import { getHostHomestays, getHostRooms, getHostBookings } from '../api.js';
import { formatVND } from '../render.js';
import '../components/site-header.js';
import '../components/site-footer.js';

// TODO Mốc 4: bật lại khi có role host thật
// if (!isLoggedIn()) requireLogin();

const STATUS_LABEL = { pending:"Chờ xác nhận", confirmed:"Đã xác nhận", checked_in:"Đã nhận phòng", completed:"Hoàn tất", cancelled:"Đã hủy", rejected:"Bị từ chối" };
const STATUS_BADGE = { pending:"badge--warning", confirmed:"badge--success", checked_in:"badge--success", completed:"", cancelled:"badge--danger", rejected:"badge--danger" };
const STATUS_COLOR = { pending:"#b26a00", confirmed:"#008234", checked_in:"#006ce4", completed:"#6b6b6b", cancelled:"#d32f2f", rejected:"#8e24aa" };
const REVENUE_STATUSES = ['confirmed', 'checked_in', 'completed'];

const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
const millions = n => (n / 1e6).toLocaleString('vi-VN', { maximumFractionDigits: 1 });

// ---------- Biểu đồ cột: doanh thu theo tháng (6 tháng gần nhất có dữ liệu) ----------
function renderRevenueChart(bookings) {
  const byMonth = {};
  bookings.filter(b => REVENUE_STATUSES.includes(b.status)).forEach(b => {
    const key = String(b.checkIn).slice(0, 7);                 // yyyy-mm
    byMonth[key] = (byMonth[key] ?? 0) + (b.totalPrice || 0);
  });
  const keys = Object.keys(byMonth).sort().slice(-6);
  if (!keys.length) { $('chartRevenue').innerHTML = '<div class="chart-empty">Chưa có doanh thu để hiển thị.</div>'; return; }

  const max = Math.max(...keys.map(k => byMonth[k]));
  const PLOT = 180;                                             // px chiều cao vùng cột
  const label = k => `T${Number(k.slice(5))}/${k.slice(2, 4)}`;
  $('chartRevenue').innerHTML = `
    <div class="bar-chart" role="img" aria-label="Biểu đồ cột doanh thu theo tháng">
      ${keys.map(k => `
        <div class="bar-chart__col" title="${label(k)}: ${esc(formatVND(byMonth[k]))}">
          <span class="bar-chart__val">${millions(byMonth[k])}</span>
          <div class="bar-chart__bar" style="height:${Math.max(3, Math.round(byMonth[k] / max * PLOT))}px"></div>
        </div>`).join('')}
    </div>
    <div class="bar-chart__labels">${keys.map(k => `<span>${label(k)}</span>`).join('')}</div>`;
}

// ---------- Biểu đồ tròn: trạng thái đặt phòng ----------
function renderStatusChart(bookings) {
  const counts = Object.keys(STATUS_LABEL).map(s => [s, bookings.filter(b => b.status === s).length]).filter(([, n]) => n > 0);
  const total = counts.reduce((sum, [, n]) => sum + n, 0);
  if (!total) { $('chartStatus').innerHTML = '<div class="chart-empty">Chưa có đặt phòng nào.</div>'; return; }

  let acc = 0;
  const stops = counts.map(([s, n]) => {
    const from = acc / total * 100; acc += n;
    return `${STATUS_COLOR[s]} ${from}% ${acc / total * 100}%`;
  }).join(', ');

  $('chartStatus').innerHTML = `
    <div class="donut-wrap">
      <div class="donut" style="background:conic-gradient(${stops})" role="img" aria-label="Biểu đồ tròn trạng thái đặt phòng">
        <div class="donut__center"><strong>${total}</strong><span>đơn</span></div>
      </div>
      <ul class="legend">
        ${counts.map(([s, n]) => `<li><span class="legend__dot" style="background:${STATUS_COLOR[s]}"></span>${STATUS_LABEL[s]}<span class="legend__num">${n}</span></li>`).join('')}
      </ul>
    </div>`;
}

// ---------- Thanh ngang: doanh thu theo homestay ----------
function renderHomestayChart(bookings, rooms, homestays) {
  const roomToHomestay = Object.fromEntries(rooms.map(r => [r.id, r.homestayId]));
  const revenue = Object.fromEntries(homestays.map(h => [h.id, 0]));
  bookings.filter(b => REVENUE_STATUSES.includes(b.status)).forEach(b => {
    const hid = roomToHomestay[b.roomId];
    if (hid in revenue) revenue[hid] += b.totalPrice || 0;
  });
  const rows = homestays.map(h => ({ name: h.name, value: revenue[h.id] })).sort((a, b) => b.value - a.value).slice(0, 6);
  const max = Math.max(...rows.map(r => r.value), 0);
  if (!rows.length || !max) { $('chartHomestay').innerHTML = '<div class="chart-empty">Chưa có doanh thu để so sánh.</div>'; return; }

  $('chartHomestay').innerHTML = `<div class="hbar">${rows.map(r => `
    <div class="hbar__row">
      <span class="hbar__name" title="${esc(r.name)}">${esc(r.name)}</span>
      <div class="hbar__track"><div class="hbar__fill" style="width:${Math.max(2, Math.round(r.value / max * 100))}%"></div></div>
      <span class="hbar__val">${esc(formatVND(r.value))}</span>
    </div>`).join('')}</div>`;
}

async function load() {
  try {
    const [homestays, allRooms, bookings] = await Promise.all([
      getHostHomestays(), getHostRooms(), getHostBookings(),
    ]);
    const today = new Date().toISOString().slice(0, 10);
    const upcoming = bookings.filter(b => ['confirmed', 'checked_in'].includes(b.status) && b.checkOut >= today);

    $('stats').innerHTML = [
      [homestays.length, 'Homestay đang hoạt động'],
      [allRooms.length, 'Phòng'],
      [upcoming.length, 'Đặt phòng sắp tới'],
      [bookings.filter(b => b.status === 'pending').length, 'Đơn chờ duyệt'],
    ].map(([num, label], i) => `<div class="stat-card"><div class="stat-card__num${i === 3 ? ' is-warning' : ''}">${num}</div><div class="stat-card__label">${label}</div></div>`).join('');

    renderRevenueChart(bookings);
    renderStatusChart(bookings);
    renderHomestayChart(bookings, allRooms, homestays);

    const roomsById = Object.fromEntries(allRooms.map(r => [r.id, r]));
    const recent = [...bookings].sort((a, b) => b.createdAt.localeCompare(a.createdAt)).slice(0, 5);
    $('recent').innerHTML = recent.length ? `<div class="stack">` + recent.map(b => {
      const room = roomsById[b.roomId];
      return `<div class="row row--compact">
        <div><a class="row__title" href="host-bookings.html">${esc(b.customerName)}</a>
          <p class="row__meta">${esc(room ? room.name : '')} · ${esc(b.checkIn)} → ${esc(b.checkOut)}</p></div>
        <div class="row__side"><span class="badge ${STATUS_BADGE[b.status]}">${STATUS_LABEL[b.status]}</span>
          <p class="row__price mt-2">${formatVND(b.totalPrice)}</p></div>
      </div>`;
    }).join('') + `</div>` : `<p class="text-muted">Chưa có đặt phòng nào.</p>`;
  } catch (e) {
    $('recent').innerHTML = `<p class="text-danger">Không tải được dữ liệu. ${esc(e.detail ?? '')}</p>`;
    ['chartRevenue', 'chartStatus', 'chartHomestay'].forEach(id => { $(id).innerHTML = '<div class="chart-empty">Không tải được dữ liệu.</div>'; });
    console.error(e);
  }
}
load();
