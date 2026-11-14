// ============================================================
//  Admin: danh sách host + hộp thoại chi tiết.
//  Dữ liệu từ getAdminHosts() (mock: tài khoản Host và booking đang lưu).
//  Chỉ dùng textContent / createElement, không innerHTML (dữ liệu có thể do người dùng nhập khi đăng ký).
// ============================================================
import { getAdminHosts, cancelAdminHost } from '../api.js';
import { fmtVND, fmtInt } from '../charts.js';
import { showSkeleton, showError, confirmAction, toast } from '../ui.js';
import '../guard.js';

import { ACCOUNT_API_MODE, safeImageURL } from '../config.js';
if (!ACCOUNT_API_MODE) {
const $ = id => document.getElementById(id);
const list = $('host-list'), empty = $('host-empty'), dialog = $('host-dialog');

let hosts = [];

const fmtDate = s => { const d = new Date(s); return Number.isNaN(+d) ? '—' : d.toLocaleDateString('vi-VN'); };
const norm = s => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd').toLowerCase();

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function hostRow(h) {
  const row = el('article', 'row');
  const img = el('img', 'row__img'); img.src = safeImageURL(h.avatar || 'img/placeholder.svg'); img.alt = '';
  img.onerror = () => { img.onerror = null; img.src = 'img/placeholder.svg'; };

  const info = el('div');
  info.append(
    el('p', 'row__title', h.display_name),
    el('p', 'row__meta', [h.email, h.phone].filter(Boolean).join(' · ')),
    el('p', 'row__meta', `Host từ ${fmtDate(h.createdAt)} · ${h.homestays.length} homestay · ${fmtInt(h.bookingCount)} đơn đặt`),
  );

  const actions = el('div', 'row__actions');
  const badge = h.homestays.length ? el('span', 'badge badge--success', 'Đang hoạt động') : el('span', 'badge badge--warning', 'Chưa có homestay');
  const btn = el('button', 'btn', 'Xem chi tiết'); btn.type = 'button';
  btn.addEventListener('click', () => openDetail(h));
  const cancel = el('button', 'btn btn--danger', 'Hủy làm Host'); cancel.type = 'button';
  cancel.addEventListener('click', async () => {
    if (cancel.disabled || !await confirmAction({
      title: 'Hủy quyền Host?',
      message: `Hủy quyền của ${h.display_name}? Thao tác bị chặn nếu còn booking đang chờ, đã xác nhận hoặc khách đang lưu trú.`,
      confirmText: 'Hủy làm Host',
    })) return;
    cancel.disabled = true;
    try {
      await cancelAdminHost(h.id);
      toast(`Đã hủy quyền Host của ${h.display_name}.`);
      await load();
    } catch (error) {
      toast(error.detail || 'Không thể hủy quyền Host.', 'error');
    } finally { cancel.disabled = false; }
  });
  actions.append(badge, btn, cancel);

  row.append(img, info, actions);
  return row;
}

function render() {
  const q = norm($('host-search').value.trim());
  const shown = hosts.filter(h => !q || norm(`${h.display_name} ${h.email} ${h.phone}`).includes(q));
  list.replaceChildren(...shown.map(hostRow));
  list.hidden = !shown.length;
  empty.hidden = !!shown.length;
  $('host-count').textContent = q ? `(${shown.length}/${hosts.length})` : `(${hosts.length})`;
}

function openDetail(h) {
  $('hd-name').textContent = h.display_name;
  const rows = [
    ['Email', h.email || '—'],
    ['Số điện thoại', h.phone || '—'],
    ['Tham gia', fmtDate(h.createdAt)],
    ['Tổng đơn đặt', fmtInt(h.bookingCount)],
    ['Doanh thu (đơn hoàn thành)', fmtVND(h.revenue)],
  ];
  $('hd-info').replaceChildren(...rows.flatMap(([k, v]) => [el('dt', '', k), el('dd', '', v)]));
  $('hd-count').textContent = h.homestays.length;
  $('hd-homestays').replaceChildren(...(h.homestays.length
    ? h.homestays.map(i => {
        const li = el('li');
        const a = el('a', '', i.title); a.href = `detail.html?id=${encodeURIComponent(i.id)}`;
        li.append(a, el('span', 'row__meta', ` · ${i.location} · ${fmtVND(i.price)}/đêm`));
        return li;
      })
    : [el('li', 'row__meta', 'Chưa đăng homestay nào.')]));
  dialog.showModal();
}

for (const id of ['hd-close', 'hd-close-top']) {
  $(id).addEventListener('click', () => dialog.close());
}
dialog.addEventListener('click', e => { if (e.target === dialog) dialog.close(); });   // bấm ra ngoài để đóng
$('host-search').addEventListener('input', render);

async function load() {
  showSkeleton(list, 3);
  try {
    hosts = (await getAdminHosts()).sort((a, b) => String(b.createdAt).localeCompare(String(a.createdAt)));
    render();
  } catch (e) {
    console.error(e);
    showError(list, e, load);
  }
}
load();
}
