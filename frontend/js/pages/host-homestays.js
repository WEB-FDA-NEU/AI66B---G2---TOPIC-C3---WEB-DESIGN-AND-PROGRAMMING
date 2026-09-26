import { getHostHomestays, getHostRooms, deleteHostHomestay } from '../api.js';
import { confirmAction, toast } from '../ui.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const $ = id => document.getElementById(id);

async function load() {
  try {
    const [homestays, rooms] = await Promise.all([getHostHomestays(), getHostRooms()]);
    $('count').textContent = `${homestays.length} homestay`;

    if (!homestays.length) {
      $('list').innerHTML = `<div class="empty">
        <p class="empty__title">Bạn chưa có homestay nào</p>
        <p class="empty__hint">Thêm homestay đầu tiên để bắt đầu nhận đặt phòng.</p>
        <a class="btn btn--primary empty__action" href="host-homestay-form.html">+ Thêm homestay</a></div>`;
      return;
    }

    $('list').innerHTML = homestays.map(h => {
      const roomCount = rooms.filter(r => r.homestayId === h.id).length;
      return `<div class="row" style="grid-template-columns:96px 1fr auto">
        <img class="row__img" src="${h.images?.[0] || 'img/placeholder.svg'}" alt="${h.name}">
        <div>
          <a class="row__title" href="host-homestay-form.html?id=${h.id}">${h.name}</a>
          <p class="row__meta">📍 ${h.address}</p>
          <p class="row__meta">${roomCount} phòng · <span class="badge ${h.status === 'active' ? 'badge--success' : ''}">${h.status === 'active' ? 'Đang hoạt động' : h.status}</span></p>
        </div>
        <div class="row__actions" style="flex-direction:column;align-items:flex-end">
          <a class="btn btn--outline" href="host-rooms.html?homestayId=${h.id}">Xem phòng</a>
          <a class="btn" href="host-homestay-form.html?id=${h.id}">Sửa</a>
          <button class="btn btn--danger" data-del="${h.id}" data-name="${h.name}" type="button">Xóa</button>
        </div>
      </div>`;
    }).join('');

    $('list').querySelectorAll('[data-del]').forEach(btn => btn.addEventListener('click', async () => {
      const ok = await confirmAction({ title: 'Xóa homestay?',
        message: `"${btn.dataset.name}" sẽ bị ẩn khỏi kết quả tìm kiếm. Các đặt phòng cũ vẫn được giữ lại.`,
        confirmText: 'Xóa' });
      if (!ok) return;
      try { await deleteHostHomestay(btn.dataset.del); toast('Đã xóa homestay.'); load(); }
      catch (e) { toast(e.detail ?? 'Không xóa được.', 'error'); }
    }));
  } catch (e) {
    $('list').innerHTML = `<p class="text-danger">Không tải được dữ liệu.</p>`;
    console.error(e);
  }
}
load();
