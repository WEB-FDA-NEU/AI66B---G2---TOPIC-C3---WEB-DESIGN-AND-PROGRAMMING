import { animateList, animateStatus } from '../motion.js';

import { getHostBookings, getHostRooms, getHostHomestays, updateBookingStatus } from '../api.js';
import { ACCOUNT_API_MODE } from '../config.js';
import { initHostDashboardReturn } from '../host-navigation.js';
import { formatVND } from '../render.js';
import { toast } from '../ui.js';
import '../components/site-header.js';
import '../components/site-footer.js';
import '../guard.js';

initHostDashboardReturn();
const $ = id => document.getElementById(id);

const STATUS_LABEL = {
  pending: 'Chờ xác nhận',
  confirmed: 'Đã xác nhận',
  checked_in: 'Đã nhận phòng',
  completed: 'Hoàn tất',
  cancelled: 'Đã hủy',
  rejected: 'Bị từ chối'
};

const STATUS_BADGE = {
  pending: 'badge--warning',
  confirmed: 'badge--success',
  checked_in: 'badge--success',
  completed: '',
  cancelled: 'badge--danger',
  rejected: 'badge--danger'
};

// Bước tiếp theo hợp lệ cho từng trạng thái — theo docs/api-contract.md
const NEXT_STEP = {
  pending: 'confirmed',
  confirmed: 'checked_in',
  checked_in: 'completed'
};

const NEXT_LABEL = {
  confirmed: 'Xác nhận',
  checked_in: 'Nhận phòng',
  completed: 'Hoàn tất'
};

let bookings = [];
let rooms = [];
let homestays = [];
let filter = '';
let page = 1;
let loading = false;
let generation = 0;
const pager = document.createElement('div'); pager.className = 'row__actions';
$('list').after(pager);
let hasRendered = false;

async function loadData() {
  const current = ++generation;
  loading = true;
  try {
    const result = ACCOUNT_API_MODE
      ? [await getHostBookings({ page, page_size: 20, ...(filter ? { status: filter } : {}) }), [], []]
      : await Promise.all([getHostBookings(), getHostRooms(), getHostHomestays()]);
    if (current !== generation) return;
    [bookings, rooms, homestays] = result;
  } finally { if (current === generation) loading = false; }
}

function renderPager() {
  pager.replaceChildren();
  if (!ACCOUNT_API_MODE) return;
  for (const [label, delta, disabled] of [['\u0054r\u01b0\u1edbc', -1, page === 1], ['Sau', 1, bookings.length < 20]]) {
    const button = document.createElement('button'); button.type = 'button';
    button.className = 'btn'; button.textContent = label; button.disabled = disabled;
    button.addEventListener('click', async () => {
      if (loading) return;
      const previous = page; page += delta;
      try { await loadData(); render(); } catch (error) { page = previous; toast(error.detail, 'error'); }
    });
    pager.append(button);
  }
}

function render({ changedId = null } = {}) {
  renderPager();
  const roomsById = Object.fromEntries(rooms.map(r => [r.id, r]));
  const hsById = Object.fromEntries(homestays.map(h => [h.id, h]));

  const list = filter
    ? bookings.filter(b => b.status === filter)
    : bookings;

  const sorted = [...list].sort((a, b) =>
    b.createdAt.localeCompare(a.createdAt)
  );

  if (!sorted.length) {
    $('list').innerHTML = `
      <div class="empty host-bookings-empty">
        <p class="empty__title">Không có đặt phòng nào</p>
        <p class="empty__hint">
          ${filter
            ? 'Không có đặt phòng ở trạng thái này.'
            : 'Chưa có khách đặt phòng nào của bạn.'}
        </p>
      </div>
    `;
    animateList($('list'), { initial: !hasRendered });
    hasRendered = true;
    return;
  }

  const fragment = document.createDocumentFragment();
  for (const b of sorted) {
    const room = roomsById[b.roomId];
    const hs = room ? hsById[room.homestayId] : null;
    const template = document.createElement('template');
    // Constant layout only; API/user values never enter the HTML parser.
    template.innerHTML = `
      <article class="row host-booking-card">

        <div class="host-booking-info">
          <p class="row__title">

            <span class="text-muted">— </span>
          </p>

          <p class="row__meta">
             ·
          </p>

          <p class="row__meta">
            📅  →  ·  khách
          </p>

          <p class="row__meta text-danger host-booking-reject-reason" hidden></p>
        </div>

        <div class="host-booking-summary">
          <span class="badge ">

          </span>

          <p class="row__price host-booking-price">

          </p>

          <div class="row__actions host-booking-actions"></div>
        </div>

      </article>
`;
    const card = template.content.firstElementChild;
    const title = card.querySelector('.row__title');
    title.firstChild.textContent = String(b.customerName || '');
    title.querySelector('span').textContent = ` \u2014 ${b.customerPhone || ''}`;
    const meta = card.querySelectorAll('.host-booking-info > .row__meta');
    meta[0].textContent = `${b.homestayName || hs?.name || ''} \u00b7 ${b.roomName || room?.name || ''}`;
    meta[1].textContent = `\ud83d\udcc5 ${b.checkIn} \u2192 ${b.checkOut} \u00b7 ${b.guests} kh\u00e1ch`;
    const reason = card.querySelector('.host-booking-reject-reason');
    reason.hidden = b.status !== 'rejected' || !b.rejectReason;
    reason.textContent = `L\u00fd do t\u1eeb ch\u1ed1i: ${b.rejectReason || ''}`;
    const badge = card.querySelector('.badge');
    badge.className = `badge ${STATUS_BADGE[b.status] || ''}`;
    badge.textContent = STATUS_LABEL[b.status] || b.status;
    card.querySelector('.host-booking-price').textContent = formatVND(b.totalPrice);
    const actions = card.querySelector('.host-booking-actions');
    const next = NEXT_STEP[b.status];
    if (next) {
      const button = document.createElement('button'); button.type = 'button';
      button.className = 'btn btn--primary'; button.dataset.act = `${b.id}:${next}`;
      button.textContent = NEXT_LABEL[next]; actions.append(button);
    }
    if (b.status === 'pending') {
      const button = document.createElement('button'); button.type = 'button';
      button.className = 'btn btn--danger'; button.dataset.reject = b.id;
      button.textContent = 'T\u1eeb ch\u1ed1i'; actions.append(button);
    }
    fragment.append(card);
  }
  $('list').replaceChildren(fragment);

  $('list').querySelectorAll('[data-act]').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (btn.disabled) return;
      const [id, status] = btn.dataset.act.split(':');
      const actions = [...btn.closest('.host-booking-actions').querySelectorAll('button')];
      actions.forEach(button => button.disabled = true);

      try {
        await updateBookingStatus(id, status);
        toast('Đã cập nhật trạng thái.');
        await loadData();
        render({ changedId: id });
      } catch (e) {
        actions.forEach(button => button.disabled = false);
        toast(e.detail ?? 'Không cập nhật được.', 'error');
      }
    });
  });

  $('list').querySelectorAll('[data-reject]').forEach(btn => {
    btn.addEventListener('click', () => openReject(btn.dataset.reject));
  });

  if (changedId) {
    const index = sorted.findIndex(booking => String(booking.id) === String(changedId));
    if (index >= 0) animateStatus($('list').children[index].querySelector('.badge'));
    else animateList($('list'));
  } else animateList($('list'), { initial: !hasRendered });
  hasRendered = true;
}

let rejectingId = null;

function openReject(id) {
  rejectingId = id;
  $('rejectReason').value = '';
  $('rejectErr').textContent = '';
  $('reject-dialog').showModal();
}

$('rejectCancel').addEventListener('click', () => {
  $('reject-dialog').close();
});

$('rejectConfirm').addEventListener('click', async () => {
  if ($('rejectConfirm').disabled) return;
  const reason = $('rejectReason').value.trim();

  if (!reason) {
    $('rejectErr').textContent = 'Vui lòng nhập lý do từ chối.';
    return;
  }

  const id = rejectingId;
  $('rejectConfirm').disabled = true;
  try {
    await updateBookingStatus(id, 'rejected', reason);

    $('reject-dialog').close();
    toast('Đã từ chối đặt phòng.');

    await loadData();
    render({ changedId: id });
  } catch (e) {
    $('rejectErr').textContent = e.detail ?? 'Không thực hiện được.';
  } finally {
    $('rejectConfirm').disabled = false;
  }
});

$('tabs').addEventListener('click', async e => {
  const btn = e.target.closest('button[data-status]');
  if (!btn || loading) return;

  $('tabs').querySelectorAll('button').forEach(b => {
    b.classList.remove('is-active');
  });

  btn.classList.add('is-active');
  filter = btn.dataset.status; page = 1;
  try { if (ACCOUNT_API_MODE) await loadData(); render(); }
  catch (error) { $('list').replaceChildren(); pager.replaceChildren(); toast(error.detail, 'error'); }
});

loadData()
  .then(render)
  .catch(e => {
    $('list').innerHTML = `
      <p class="text-danger">Không tải được dữ liệu.</p>
    `;
    console.error(e);
  });
