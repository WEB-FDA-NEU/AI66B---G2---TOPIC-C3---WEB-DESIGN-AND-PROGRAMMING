import { getHostHomestays, getHostRooms, getHostBookings } from '../api.js';
import { formatVND } from '../render.js';
import { requireLogin } from '../auth.js';
import '../components/site-header.js';
import '../components/site-footer.js';

// TODO Mốc 4: bật lại khi có role host thật
// if (!isLoggedIn()) requireLogin();

const STATUS_LABEL = { pending:"Chờ xác nhận", confirmed:"Đã xác nhận", checked_in:"Đã nhận phòng", completed:"Hoàn tất", cancelled:"Đã hủy", rejected:"Bị từ chối" };
const STATUS_BADGE = { pending:"badge--warning", confirmed:"badge--success", checked_in:"badge--success", completed:"", cancelled:"badge--danger", rejected:"badge--danger" };

const $ = id => document.getElementById(id);

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
    ].map(([num, label]) => `<div class="stat-card"><div class="stat-card__num">${num}</div><div class="stat-card__label">${label}</div></div>`).join('');

    const roomsById = Object.fromEntries(allRooms.map(r => [r.id, r]));
    const recent = [...bookings].sort((a, b) => b.createdAt.localeCompare(a.createdAt)).slice(0, 5);
    $('recent').innerHTML = recent.length ? `<div class="stack">` + recent.map(b => {
      const room = roomsById[b.roomId];
      return `<div class="row">
        <div style="width:96px;height:72px;background:var(--c-surface);border-radius:var(--radius-s)"></div>
        <div><a class="row__title" href="host-bookings.html">${b.customerName}</a>
          <p class="row__meta">${room ? room.name : ''} · ${b.checkIn} → ${b.checkOut}</p></div>
        <div style="text-align:right"><span class="badge ${STATUS_BADGE[b.status]}">${STATUS_LABEL[b.status]}</span>
          <p class="row__price mt-3">${formatVND(b.totalPrice)}</p></div>
      </div>`;
    }).join('') + `</div>` : `<p class="text-muted">Chưa có đặt phòng nào.</p>`;
  } catch (e) {
    $('recent').innerHTML = `<p class="text-danger">Không tải được dữ liệu. ${e.detail ?? ''}</p>`;
    console.error(e);
  }
}
load();
