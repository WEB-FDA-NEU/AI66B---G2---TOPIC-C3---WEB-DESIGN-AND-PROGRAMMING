
import { getHostHomestays, getHostRooms, deleteHostHomestay } from '../api.js';
import { confirmAction, toast } from '../ui.js';
import '../components/site-header.js';
import '../components/site-footer.js';
import '../guard.js';

const $ = id => document.getElementById(id);

async function load() {
  try {
    const [homestays, rooms] = await Promise.all([
      getHostHomestays(),
      getHostRooms()
    ]);

    $('count').textContent = `${homestays.length} homestay`;

    // Trường hợp chưa có homestay
    if (!homestays.length) {
      $('list').innerHTML = `
        <div class="empty host-homestays-empty">
          <p class="empty__title">Bạn chưa có homestay nào</p>

          <p class="empty__hint">
            Thêm homestay đầu tiên để bắt đầu nhận đặt phòng.
          </p>

          <a
            class="btn btn--primary empty__action"
            href="host-homestay-form.html"
          >
            + Thêm homestay
          </a>
        </div>
      `;
      return;
    }

    // Render danh sách homestay
    $('list').innerHTML = homestays.map(h => {
      const roomCount = rooms.filter(
        r => r.homestayId === h.id
      ).length;

      return `
        <article class="host-homestay-card">

          <img
            class="row__img host-homestay-card__img"
            src="${h.images?.[0] || 'img/placeholder.svg'}"
            alt="${h.name}"
          >

          <div class="host-homestay-card__info">

            <a
              class="row__title"
              href="host-homestay-form.html?id=${h.id}"
            >
              ${h.name}
            </a>

            <p class="row__meta host-homestay-card__address">
              📍 ${h.address}
            </p>

            <p class="row__meta">
              ${roomCount} phòng ·
              <span class="badge ${h.status === 'active' ? 'badge--success' : ''}">
                ${h.status === 'active' ? 'Đang hoạt động' : h.status}
              </span>
            </p>

          </div>

          <div class="row__actions host-homestay-card__actions">

            <a
              class="btn btn--outline"
              href="host-rooms.html?homestayId=${h.id}"
            >
              Xem phòng
            </a>

            <a
              class="btn"
              href="host-homestay-form.html?id=${h.id}"
            >
              Sửa
            </a>

            <button
              class="btn btn--danger"
              data-del="${h.id}"
              data-name="${h.name}"
              type="button"
            >
              Xóa
            </button>

          </div>

        </article>
      `;
    }).join('');

    // Xử lý sự kiện xóa homestay
    $('list').querySelectorAll('[data-del]').forEach(btn => {
      btn.addEventListener('click', async () => {

        const ok = await confirmAction({
          title: 'Xóa homestay?',
          message: `"${btn.dataset.name}" sẽ bị ẩn khỏi kết quả tìm kiếm. Các đặt phòng cũ vẫn được giữ lại.`,
          confirmText: 'Xóa'
        });

        if (!ok) return;

        try {
          await deleteHostHomestay(btn.dataset.del);

          toast('Đã xóa homestay.');

          load();

        } catch (e) {
          toast(e.detail ?? 'Không xóa được.', 'error');
        }
      });
    });

  } catch (e) {
    $('list').innerHTML = `
      <p class="text-danger">
        Không tải được dữ liệu.
      </p>
    `;

    console.error(e);
  }
}

load();
