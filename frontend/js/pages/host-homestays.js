import { ACCOUNT_API_MODE, accountHref, safeImageURL } from '../config.js';
import { initHostDashboardReturn } from '../host-navigation.js';

import { getHostHomestays, getHostRooms, deleteHostHomestay } from '../api.js';
import { confirmAction, toast } from '../ui.js';
import '../components/site-header.js';
import '../components/site-footer.js';
import '../guard.js';

const $ = id => document.getElementById(id);
initHostDashboardReturn();
let page = 1;
let loading = false;
const pager = document.createElement('div'); pager.className = 'row__actions'; $('list').after(pager);

async function load() {
  if (loading) return;
  loading = true;
  try {
    const [homestays, rooms] = await Promise.all([
      getHostHomestays({ page, page_size: 20 }),
      ACCOUNT_API_MODE ? Promise.resolve([]) : getHostRooms()
    ]);

    $('count').textContent = `${homestays.length} homestay`;

    pager.replaceChildren();
    if (ACCOUNT_API_MODE) {
      $('count').textContent = `Trang ${page} \u00b7 ${homestays.length} homestay`;
      for (const [label, delta, disabled] of [['Tr\u01b0\u1edbc', -1, page === 1], ['Sau', 1, homestays.length < 20]]) {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'btn'; button.textContent = label; button.disabled = disabled;
        button.addEventListener('click', () => { if (!loading) { page += delta; load(); } }); pager.append(button);
      }
    }
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
    const fragment = document.createDocumentFragment();
    for (const h of homestays) {
      const template = document.createElement('template');
      template.innerHTML = `
        <article class="host-homestay-card">

          <img
            class="row__img host-homestay-card__img"
            src=""
            alt=""
          >

          <div class="host-homestay-card__info">

            <a
              class="row__title"
              href="host-homestay-form.html?id="
            >

            </a>

            <p class="row__meta host-homestay-card__address">
              📍
            </p>

            <p class="row__meta">
               phòng ·
              <span class="badge ">

              </span>
            </p>

          </div>

          <div class="row__actions host-homestay-card__actions">

            <a
              class="btn btn--outline"
              href="host-rooms.html?homestayId="
            >
              Xem phòng
            </a>

            <a
              class="btn"
              href="host-homestay-form.html?id="
            >
              Sửa
            </a>

            <button
              class="btn btn--danger"
              data-del=""
              data-name=""
              type="button"
            >
              Xóa
            </button>

          </div>

        </article>
`;
      const card = template.content.firstElementChild;
      const image = card.querySelector('img'); image.src = safeImageURL(h.images?.[0] || 'img/placeholder.svg'); image.alt = h.name;
      image.onerror = () => { image.onerror = null; image.src = 'img/placeholder.svg'; };
      const edit = accountHref(`host-homestay-form.html?id=${encodeURIComponent(h.id)}`);
      const title = card.querySelector('.row__title'); title.textContent = h.name; title.href = edit;
      card.querySelector('.host-homestay-card__address').textContent = h.address;
      const badge = card.querySelector('.badge'); badge.className = `badge ${h.status === 'active' ? 'badge--success' : ''}`;
      badge.textContent = h.status === 'active' ? '\u0110ang ho\u1ea1t \u0111\u1ed9ng' : h.status;
      badge.parentNode.firstChild.textContent = ACCOUNT_API_MODE ? '' : `${rooms.filter(r => r.homestayId === h.id).length} ph\u00f2ng \u00b7 `;
      const links = card.querySelectorAll('.host-homestay-card__actions a');
      links[0].href = accountHref(`host-rooms.html?homestayId=${encodeURIComponent(h.id)}`); links[1].href = edit;
      const button = card.querySelector('[data-del]'); button.dataset.del = h.id; button.dataset.name = h.name;
      fragment.append(card);
    }
    $('list').replaceChildren(fragment);

    // Xử lý sự kiện xóa homestay
    $('list').querySelectorAll('[data-del]').forEach(btn => {
      btn.addEventListener('click', async () => {

        const ok = await confirmAction({
          title: 'Xóa homestay?',
          message: `"${btn.dataset.name}" sẽ bị ẩn khỏi kết quả tìm kiếm. Các đặt phòng cũ vẫn được giữ lại.`,
          confirmText: 'Xóa'
        });

        if (!ok || btn.disabled) return;
        btn.disabled = true;
        try {
          await deleteHostHomestay(btn.dataset.del);

          toast('Đã xóa homestay.');

          await load();

        } catch (e) {
          btn.disabled = false;
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

    toast(e.detail || e.message, 'error');
  } finally { loading = false; }
}

load();
