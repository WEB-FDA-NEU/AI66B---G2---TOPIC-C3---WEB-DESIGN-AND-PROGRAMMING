// ============================================================
//  Admin Dashboard: số liệu + biểu đồ tính từ getAdminOverview() (mock: dữ liệu đang lưu).
//  Không còn con số viết cứng trong HTML.
//   • "User mới" / đường tăng trưởng / cơ cấu theo tỉnh: theo NGÀY TẠO (createdAt) trong kỳ.
//   • Tỉnh/thành: phần cuối của location (sau dấu phẩy cuối) của homestay mà đơn đặt.
//   • "Đơn chờ duyệt" đếm trực tiếp từ danh sách đơn xin làm host trên trang → duyệt/từ chối là số tự giảm.
// ============================================================
import { getAdminOverview, getAdminApplications, decideHostApplication, getAdminHostCancellations } from '../api.js';
import '../guard.js';
import { periodTabs, getWindow, inWindow, bucketIndex, dayNum, fmtFullDate, fmtInt, fmtPct,
         countUp, drawChart, axisOptions, theme, palette } from '../charts.js';
import { safeImageURL } from '../config.js';
import { confirmAction, toast } from '../ui.js';

import { ACCOUNT_API_MODE } from '../config.js';
if (ACCOUNT_API_MODE) {
  const { initAdmin } = await import('./api-admin.js');
  await initAdmin();
} else {
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
    await Promise.all([loadApplications(), loadHostCancellations()]);

    tabs = periodTabs($('period-tabs'), { initial: 'year', onChange: render });
    render(tabs.value);
  } catch (e) {
    console.error(e);
    $('period-note').textContent = `Không tải được số liệu. ${e.detail ?? ''}`;
    $('period-note').classList.add('text-danger');
  }
}

async function loadHostCancellations() {
  const list = $('host-cancellation-list');
  const empty = $('host-cancellation-empty');
  try {
    const records = await getAdminHostCancellations({ page: 1, page_size: 100 });
    list.replaceChildren(...records.map(record => {
      const card = document.createElement('article');
      card.className = 'host-cancellation-card';
      const host = document.createElement('div');
      host.className = 'host-cancellation-card__host';
      const avatar = document.createElement('span');
      avatar.className = 'host-cancellation-card__avatar';
      avatar.setAttribute('aria-hidden', 'true');
      avatar.textContent = (record.host.display_name || record.host.email || '').trim().slice(0, 1).toLocaleUpperCase('vi-VN') || '?';
      const identity = document.createElement('div');
      identity.className = 'host-cancellation-card__identity';
      const name = document.createElement('h3');
      name.className = 'host-cancellation-card__name';
      name.textContent = record.host.display_name || 'Host';
      const email = document.createElement('p');
      email.className = 'host-cancellation-card__email';
      email.textContent = record.host.email || '';
      identity.append(name, email);
      host.append(avatar, identity);

      const reasonGroup = document.createElement('div');
      reasonGroup.className = 'host-cancellation-card__reason';
      const reasonLabel = document.createElement('span');
      reasonLabel.className = 'host-cancellation-card__label';
      reasonLabel.textContent = 'Lý do tự hủy';
      const reason = document.createElement('p');
      reason.className = 'host-cancellation-card__reason-text';
      reason.textContent = record.reason || 'Không có lý do được cung cấp.';
      reasonGroup.append(reasonLabel, reason);

      const timeGroup = document.createElement('div');
      timeGroup.className = 'host-cancellation-card__time';
      const timeLabel = document.createElement('span');
      timeLabel.className = 'host-cancellation-card__label';
      timeLabel.textContent = 'Thời gian';
      const at = new Date(record.createdAt);
      const created = document.createElement('time');
      created.className = 'host-cancellation-card__timestamp';
      created.textContent = Number.isNaN(at.getTime()) ? String(record.createdAt || 'Không rõ') : at.toLocaleString('vi-VN');
      if (!Number.isNaN(at.getTime())) created.dateTime = at.toISOString();
      timeGroup.append(timeLabel, created);
      card.append(host, reasonGroup, timeGroup);
      return card;
    }));
    empty.hidden = records.length > 0;
  } catch (error) {
    console.error(error);
    list.replaceChildren();
    empty.hidden = true;
    const notice = document.createElement('p');
    notice.className = 'text-danger';
    notice.textContent = error.detail || 'Không tải được thông báo hủy Host.';
    list.append(notice);
  }
}

// ---------- Đơn chờ duyệt: đếm từ danh sách đơn trên trang, tự cập nhật khi Duyệt/Từ chối ----------
function watchPending() {
  const list = $('application-list');
  const count = () => list.querySelectorAll('[data-status="pending"]').length;
  countUp($('kpi-pending'), count());
  new MutationObserver(() => countUp($('kpi-pending'), count()))
    .observe(list, { subtree: true, childList: true, attributes: true, attributeFilter: ['data-status'] });
}

async function loadApplications() {
  const list = $('application-list');
  const empty = $('application-empty');
  try {
    const applications = await getAdminApplications({ status: 'pending', page: 1, page_size: 100 });
    list.replaceChildren(...applications.map(renderApplication));
    list.hidden = applications.length === 0;
    empty.hidden = applications.length > 0;
    countUp($('kpi-pending'), applications.length);
  } catch (error) {
    console.error(error);
    list.replaceChildren(Object.assign(document.createElement('p'), {
      className: 'text-danger',
      textContent: error.detail || 'Không tải được danh sách đơn đăng ký Host.',
    }));
    list.hidden = false;
    empty.hidden = true;
  }
}

function renderApplication(application) {
  const row = document.createElement('article');
  row.className = 'row';
  row.dataset.status = application.status;
  const image = document.createElement('img');
  image.className = 'row__img';
  image.src = safeImageURL(application.user.avatar || 'img/placeholder.svg');
  image.alt = '';
  image.onerror = () => { image.onerror = null; image.src = 'img/placeholder.svg'; };

  const info = document.createElement('div');
  const addMeta = (label, value) => {
    const meta = document.createElement('p');
    meta.className = 'row__meta';
    meta.textContent = `${label}: ${value}`;
    info.append(meta);
  };
  const title = document.createElement('p');
  title.className = 'row__title';
  title.textContent = application.user.display_name;
  info.append(title);
  addMeta('Email', application.user.email);
  const createdAt = new Date(application.createdAt);
  addMeta('Nộp đơn', Number.isNaN(createdAt.getTime()) ? application.createdAt : createdAt.toLocaleString('vi-VN'));

  const labels = {
    homestay_name: 'Tên homestay dự kiến',
    address: 'Địa chỉ',
    province: 'Tỉnh/thành phố',
    room_count: 'Số phòng',
    description: 'Mô tả',
    experience: 'Kinh nghiệm / tin đăng',
    phone: 'Số điện thoại',
  };
  for (const [key, value] of Object.entries(application.application_data)) {
    if (key !== 'accept_terms') addMeta(labels[key] || key, value);
  }
  if (application.application_data.accept_terms) addMeta('Điều khoản', 'Đã đồng ý');

  const actions = document.createElement('div');
  actions.className = 'row__actions';
  const badge = document.createElement('span');
  badge.className = 'badge badge--warning';
  badge.textContent = 'Chờ duyệt';
  const approve = document.createElement('button');
  approve.className = 'btn btn--primary';
  approve.type = 'button';
  approve.textContent = 'Duyệt';
  const reject = document.createElement('button');
  reject.className = 'btn btn--danger';
  reject.type = 'button';
  reject.textContent = 'Từ chối';

  let processing = false;
  const decide = async (action, reason = '') => {
    if (processing) return;
    processing = true;
    approve.disabled = reject.disabled = true;
    try {
      await decideHostApplication(application.id, action, reason);
      toast(action === 'approve' ? `Đã duyệt đơn của ${application.user.display_name}.` : `Đã từ chối đơn của ${application.user.display_name}.`);
      await loadApplications();
    } catch (error) {
      toast(error.detail || 'Không thể cập nhật đơn đăng ký Host.', 'error');
    } finally {
      processing = false;
      approve.disabled = reject.disabled = false;
    }
  };

  approve.onclick = async () => {
    if (processing || !await confirmAction({
      title: 'Duyệt đơn xin làm host?',
      message: `Đồng ý cho "${application.user.display_name}" trở thành host?`,
      confirmText: 'Duyệt',
    })) return;
    await decide('approve');
  };
  reject.onclick = () => {
    if (processing) return;
    $('rejectReason').value = '';
    $('rejectErr').textContent = '';
    $('rejectReason').removeAttribute('aria-invalid');
    $('reject-dialog').dataset.applicationId = application.id;
    $('reject-dialog').showModal();
  };
  actions.append(badge, approve, reject);
  row.append(image, info, actions);
  return row;
}

const rejectDialog = $('reject-dialog');
$('rejectCancel').onclick = () => rejectDialog.close();
$('rejectConfirm').onclick = async () => {
  const applicationId = rejectDialog.dataset.applicationId;
  const reason = $('rejectReason').value.trim();
  if (reason.length < 3 || reason.length > 1000) {
    $('rejectErr').textContent = 'Lý do từ chối phải có từ 3 đến 1000 ký tự.';
    $('rejectReason').setAttribute('aria-invalid', 'true');
    return;
  }
  $('rejectConfirm').disabled = true;
  try {
    await decideHostApplication(applicationId, 'reject', reason);
    rejectDialog.close();
    toast('Đã từ chối đơn đăng ký Host.');
    await loadApplications();
  } catch (error) {
    $('rejectErr').textContent = error.detail || 'Không thể cập nhật đơn đăng ký Host.';
  } finally {
    $('rejectConfirm').disabled = false;
  }
};

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
}
