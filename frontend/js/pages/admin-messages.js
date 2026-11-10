// ============================================================
//  Admin: xem, đánh dấu đã đọc và xóa tin nhắn liên hệ.
//  Tin nhắn do trang contact.html gửi (qua sendContactMessage trong api.js).
// ============================================================
import { getContactMessages, setContactMessageRead, deleteContactMessage } from '../api.js';
import { toast, confirmAction } from '../ui.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
const formatTime = iso => new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' });

let messages = [];
let filter = 'all';

function render() {
  const unread = messages.filter(m => !m.read).length;
  $('summary').textContent = messages.length
    ? `${messages.length} tin nhắn · ${unread} chưa đọc`
    : 'Chưa có tin nhắn nào.';

  const shown = filter === 'unread' ? messages.filter(m => !m.read) : messages;
  if (!shown.length) {
    $('list').innerHTML = `<p class="text-muted">${filter === 'unread' ? 'Không có tin nhắn chưa đọc.' : 'Khi khách gửi tin ở trang Liên hệ, tin sẽ hiện ở đây.'}</p>`;
    return;
  }

  $('list').innerHTML = shown.map(m => `
    <article class="msg-card${m.read ? '' : ' is-unread'}" data-id="${esc(m.id)}">
      <div class="msg-card__head">
        <span class="msg-card__name">${esc(m.name)}</span>
        <a class="text-muted" href="mailto:${esc(m.email)}">${esc(m.email)}</a>
        <span class="badge">${esc(m.subject)}</span>
        ${m.read ? '' : '<span class="badge badge--info">Mới</span>'}
        <span class="msg-card__time">${esc(formatTime(m.createdAt))}</span>
      </div>
      <p class="msg-card__body">${esc(m.message)}</p>
      <div class="actions-bar mt-3">
        <button class="btn btn--outline btn--sm" type="button" data-action="toggle">${m.read ? 'Đánh dấu chưa đọc' : 'Đánh dấu đã đọc'}</button>
        <a class="btn btn--outline btn--sm" href="mailto:${esc(m.email)}?subject=${encodeURIComponent('Re: ' + m.subject)}">Trả lời qua email</a>
        <button class="btn btn--danger btn--sm push-right" type="button" data-action="delete">Xóa</button>
      </div>
    </article>`).join('');
}

async function load() {
  try {
    messages = await getContactMessages();
    render();
  } catch (e) {
    $('summary').textContent = '';
    $('list').innerHTML = `<p class="text-danger">Không tải được tin nhắn. ${esc(e.detail ?? '')}</p>`;
  }
}

$('tabs').addEventListener('click', e => {
  const btn = e.target.closest('[data-filter]');
  if (!btn) return;
  filter = btn.dataset.filter;
  $('tabs').querySelectorAll('.btn').forEach(b => b.classList.toggle('is-active', b === btn));
  render();
});

$('list').addEventListener('click', async e => {
  const btn = e.target.closest('[data-action]');
  if (!btn) return;
  const id = btn.closest('[data-id]').dataset.id;
  const msg = messages.find(m => m.id === id);
  if (!msg) return;

  try {
    if (btn.dataset.action === 'toggle') {
      await setContactMessageRead(id, !msg.read);
      msg.read = !msg.read;
      render();
    }
    if (btn.dataset.action === 'delete') {
      const ok = await confirmAction({ title: 'Xóa tin nhắn?', message: `Tin nhắn của ${msg.name} sẽ bị xóa vĩnh viễn.`, confirmText: 'Xóa' });
      if (!ok) return;
      await deleteContactMessage(id);
      messages = messages.filter(m => m.id !== id);
      render();
      toast('Đã xóa tin nhắn.');
    }
  } catch (err) {
    toast(err.detail ?? 'Thao tác thất bại, thử lại.', 'error');
  }
});

// TODO Mốc 4: bật lại khi có role admin thật (giống admin.html, các trang host).
// if (!isLoggedIn()) requireLogin();
// else if (getUser()?.role !== 'admin') { ...chặn... }
load();
