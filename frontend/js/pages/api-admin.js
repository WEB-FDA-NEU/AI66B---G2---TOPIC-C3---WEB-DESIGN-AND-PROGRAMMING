import { getAdminOverview, getAdminApplications, decideHostApplication, getAdminUsers, updateAdminUser,
  getAdminHomestays, moderateHomestay, getAdminHosts, getAdminHostCancellations, cancelAdminHost } from '../api.js';
import { safeImageURL } from '../config.js';
import { confirmAction, toast } from '../ui.js';
import { periodTabs, getWindow, dayNum, bucketIndex, countUp, drawChart, axisOptions, theme, palette, fmtVND } from '../charts.js';

const $ = id => document.getElementById(id);
const el = (tag, cls, text) => { const node = document.createElement(tag); if (cls) node.className = cls; if (text !== undefined) node.textContent = text; return node; };
const button = (label, primary = false) => { const node = el('button', primary ? 'btn btn--primary' : 'btn', label); node.type = 'button'; return node; };
const select = (id, options) => { const node = el('select', 'input'); node.id = id; for (const [value, label] of options) node.add(new Option(label, value)); return node; };
const field = (label, node) => { const wrapper = el('label', 'field'); wrapper.append(el('span', 'field__label', label), node); return wrapper; };
const picture = src => { const node = el('img', 'row__img'); node.alt = ''; node.src = safeImageURL(src || 'img/placeholder.svg'); node.onerror = () => { node.onerror = null; node.src = 'img/placeholder.svg'; }; return node; };

export async function initAdmin() {
  const anchor = dayNum(new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()));
  let generation = 0, currentPeriod = 'year';
  const tabs = periodTabs($('period-tabs'), { initial: 'year', onChange: renderOverview });
  async function renderOverview(key = currentPeriod) {
    currentPeriod = key; const current = ++generation, w = getWindow(key, anchor);
    const date = day => new Date(day * 864e5).toISOString().slice(0, 10);
    $('period-note').textContent = 'Đang tải số liệu máy chủ...';
    try {
      const data = await getAdminOverview({ from: date(w.start), to: date(w.end) }); if (current !== generation) return;
      const k = data.kpis, p = data.period;
      countUp($('kpi-homestays'), Object.values(k.homestays).reduce((sum, n) => sum + n, 0));
      countUp($('kpi-bookings-total'), k.bookingCount); countUp($('kpi-users-new'), p.newUsers); countUp($('kpi-pending'), k.applications.pending || 0);
      $('kpi-period-label').textContent = 'trong kỳ';
      $('period-note').textContent = `Biểu đồ: ${p.from} – ${p.to} · Toàn hệ thống: giá trị booking ${fmtVND(k.bookingValue)}, thu thực ghi nhận ${fmtVND(k.payments.grossCaptured)}, mô phỏng ${fmtVND(k.payments.simulatedCaptured)} (không phải giao dịch ngân hàng).`;
      $('growth-note').textContent = 'Người dùng và booking mới theo kỳ, tính theo ngày Việt Nam.';
      const users = w.buckets.map(() => 0), bookings = w.buckets.map(() => 0), t = theme();
      for (const row of p.series) { const i = bucketIndex(w, row.date); if (i >= 0) { users[i] += row.users; bookings[i] += row.bookings; } }
      drawChart($('chart-growth'), { type: 'line', data: { labels: w.buckets.map(b => b.label), datasets: [
        { label: 'User mới', data: users, borderColor: t.accent, tension: .35 },
        { label: 'Booking mới', data: bookings, borderColor: t.primary, tension: .35 } ] },
      options: { responsive: true, maintainAspectRatio: false, scales: axisOptions(), plugins: { legend: { position: 'top' } } } },
      { emptyText: p.newUsers || p.newBookings ? '' : 'Chưa có dữ liệu trong kỳ.', label: `${p.newUsers} user mới, ${p.newBookings} booking mới` });
      const top = p.provinces.slice(0, 5), rest = p.provinces.slice(5).reduce((sum, row) => sum + row.bookings, 0);
      if (rest) top.push({ name: 'Khác', bookings: rest });
      drawChart($('chart-province'), { type: 'doughnut', data: { labels: top.map(r => r.name), datasets: [{ data: top.map(r => r.bookings), backgroundColor: palette() }] },
        options: { responsive: true, maintainAspectRatio: false, cutout: '58%', plugins: { legend: { position: 'bottom' } } } },
      { emptyText: p.newBookings ? '' : 'Chưa có booking trong kỳ.', label: 'Cơ cấu booking theo tỉnh, dữ liệu máy chủ' });
    } catch (error) {
      if (current !== generation) return;
      $('period-note').textContent = error.detail || 'Không tải được số liệu.';
      for (const id of ['kpi-homestays','kpi-bookings-total','kpi-users-new','kpi-pending']) $(id).textContent = '—';
    }
  }

  // Each list has independent, server-backed filters and paging. Counts are page counts only.
  function pagedList({ root, list, filters, fetchRows, renderRow, afterLoad }) {
    let page = 1, busy = false;
    const controls = el('div', 'row__actions'), pager = el('div', 'row__actions'), note = el('p', 'field__hint');
    for (const [label, node] of filters) { controls.append(field(label, node)); node.onchange = () => { if (!busy) { page = 1; load(); } }; }
    list.before(controls); list.after(note, pager);
    async function load() {
      if (busy) return; busy = true;
      for (const [, node] of filters) node.disabled = true;
      try {
        const params = { page, page_size: 20 };
        for (const [, node] of filters) if (node.value !== '') params[node.dataset.param] = node.value;
        const rows = await fetchRows(params);
        list.replaceChildren(...rows.map(row => renderRow(row, load)));
        list.hidden = false; if (!rows.length) list.append(el('p', 'empty', 'Không có dữ liệu ở trang này.'));
        note.textContent = `Trang ${page} · ${rows.length} mục`; pager.replaceChildren();
        for (const [label, delta, disabled] of [['Trước', -1, page === 1], ['Sau', 1, rows.length < 20]]) {
          const node = button(label); node.disabled = disabled;
          node.onclick = () => { if (!busy) { page += delta; load(); } }; pager.append(node);
        }
        afterLoad?.(rows);
      } catch (error) { list.replaceChildren(el('p', 'text-danger', error.detail || 'Không tải được dữ liệu.')); pager.replaceChildren(); }
      finally { busy = false; for (const [, node] of filters) node.disabled = false; }
    }
    load(); return load;
  }
  const filter = (id, param, options) => { const node = select(id, options); node.dataset.param = param; return node; };
  const applicationStatus = filter('application-status', 'status', [['pending','Chờ duyệt'],['approved','Đã duyệt'],['rejected','Bị từ chối'],['','Tất cả']]);
  const rejectDialog = $('reject-dialog'); let rejectAction = null;
  $('rejectCancel').onclick = () => rejectDialog.close();
  $('rejectConfirm').onclick = async () => {
    if ($('rejectConfirm').disabled || !rejectAction) return;
    const reason = $('rejectReason').value.trim(); if (!reason) { $('rejectErr').textContent = 'Vui lòng nhập lý do.'; return; }
    $('rejectConfirm').disabled = true;
    try { await rejectAction(reason); rejectDialog.close(); }
    catch (error) { $('rejectErr').textContent = error.detail || 'Không thực hiện được.'; }
    finally { $('rejectConfirm').disabled = false; }
  };
  $('application-empty').hidden = true;
  pagedList({ root: $('application-list').parentElement, list: $('application-list'), filters: [['Trạng thái', applicationStatus]], fetchRows: getAdminApplications,
    renderRow(application, reload) {
      const row = el('article', 'row'); row.dataset.status = application.status; row.dataset.applicationId = application.id;
      const info = el('div'), actions = el('div', 'row__actions');
      info.append(el('p', 'row__title', application.user.display_name), el('p', 'row__meta', application.user.email),
        el('p', 'row__meta', `Nộp đơn: ${application.createdAt}`));
      const applicationFieldLabels = {
        homestay_name: 'Tên homestay dự kiến', address: 'Địa chỉ', province: 'Tỉnh/thành phố',
        room_count: 'Số phòng', description: 'Mô tả', experience: 'Kinh nghiệm / tin đăng',
        phone: 'Số điện thoại', accept_terms: 'Đồng ý điều khoản',
      };
      for (const [key, value] of Object.entries(application.application_data)) {
        if (key !== 'accept_terms') info.append(el('p', 'row__meta', `${applicationFieldLabels[key] ?? key}: ${value}`));
      }
      if (application.application_data.accept_terms) info.append(el('p', 'row__meta', 'Đã đồng ý điều khoản dành cho Host.'));
      if (application.rejectReason) info.append(el('p', 'row__meta text-danger', application.rejectReason));
      actions.append(el('span', `badge ${application.status === 'pending' ? 'badge--warning' : application.status === 'approved' ? 'badge--success' : 'badge--danger'}`,
        { pending: 'Chờ duyệt', approved: 'Đã duyệt', rejected: 'Bị từ chối' }[application.status]));
      if (application.status === 'pending') {
        let processing = false;
        const approve = button('Duyệt', true), reject = button('Từ chối'); approve.dataset.action = 'approve'; reject.dataset.action = 'reject';
        async function decide(action, reason = '') {
          if (processing) return; processing = true; approve.disabled = reject.disabled = true;
          try { await decideHostApplication(application.id, action, reason); await reload(); await renderOverview(); }
          finally { processing = false; approve.disabled = reject.disabled = false; }
        }
        approve.onclick = async () => {
          if (processing || !await confirmAction({ title: 'Duyệt đơn xin làm host?', message: application.user.display_name, confirmText: 'Duyệt' })) return;
          try { await decide('approve'); } catch (error) { toast(error.detail, 'error'); }
        };
        reject.onclick = () => { if (processing) return; $('rejectReason').value = ''; $('rejectErr').textContent = ''; rejectAction = reason => decide('reject', reason); rejectDialog.showModal(); };
        actions.append(approve, reject);
      }
      row.append(picture(application.user.avatar), info, actions); return row;
    } });

  function section(id, title) { const root = el('section', 'mt-6'); root.id = id; root.append(el('h2', '', title)); const list = el('div', 'stack'); root.append(list); document.querySelector('main').append(root); return { root, list }; }
  const userSection = section('admin-users', 'Quản lý người dùng');
  const role = filter('admin-user-role', 'role', [['','Tất cả vai trò'],['user','Customer'],['host','Host'],['admin','Admin']]);
  const active = filter('admin-user-active', 'is_active', [['','Tất cả tài khoản'],['true','Đang hoạt động'],['false','Đã khóa']]);
  const sort = filter('admin-user-sort', 'sort', [['id','ID'],['newest','Mới nhất'],['email','Email']]);
  pagedList({ ...userSection, filters: [['Vai trò',role],['Tình trạng',active],['Sắp xếp',sort]], fetchRows: getAdminUsers,
    renderRow(user, reload) {
      const row = el('article', 'row'); row.dataset.userId = user.id;
      const info = el('div'), actions = el('div', 'row__actions');
      info.append(el('p', 'row__title', user.display_name), el('p', 'row__meta', `${user.email} · ${user.role} · ${user.is_active ? 'Hoạt động' : 'Đã khóa'}`));
      const toggle = button(user.is_active ? 'Khóa' : 'Mở khóa'); toggle.dataset.action = 'toggle-active';
      toggle.onclick = async () => {
        if (toggle.disabled || !await confirmAction({ title: user.is_active ? 'Khóa tài khoản?' : 'Mở khóa tài khoản?', message: user.email, confirmText: 'Xác nhận' })) return;
        toggle.disabled = true;
        try { await updateAdminUser(user.id, { is_active: !user.is_active }); await reload(); await renderOverview(); }
        catch (error) { toast(error.detail, 'error'); } finally { toggle.disabled = false; }
      };
      actions.append(toggle); row.append(picture(user.avatar), info, actions); return row;
    } });

  pagedList({ root: $('host-cancellations'), list: $('host-cancellation-list'), filters: [],
    fetchRows: getAdminHostCancellations,
    renderRow(record) {
      const row = el('article', 'row'), info = el('div');
      const created = new Date(record.createdAt);
      info.append(
        el('p', 'row__title', `${record.host.display_name} · ${record.host.email}`),
        el('p', 'row__meta', `Lý do: ${record.reason}`),
        el('p', 'row__meta', `Thời gian: ${Number.isNaN(created.getTime()) ? record.createdAt : created.toLocaleString('vi-VN')}`),
      );
      row.append(info);
      return row;
    } });

  const staySection = section('admin-homestays', 'Kiểm duyệt homestay');
  const stayStatus = filter('admin-stay-status', 'status', [['','Tất cả trạng thái'],['active','Đang hoạt động'],['inactive','Tạm ngừng'],['deleted','Đã xóa']]);
  pagedList({ ...staySection, filters: [['Trạng thái',stayStatus]], fetchRows: getAdminHomestays,
    renderRow(stay, reload) {
      const row = el('article', 'row'); row.dataset.homestayId = stay.id;
      const info = el('div'), actions = el('div', 'row__actions');
      info.append(el('p','row__title',stay.name), el('p','row__meta',`${stay.address} · ${stay.status}`));
      if (stay.status !== 'deleted') {
        const reason = el('input','input'); reason.placeholder = 'Lý do kiểm duyệt'; reason.maxLength = 500; reason.setAttribute('aria-label','Lý do kiểm duyệt');
        const toggle = button(stay.status === 'active' ? 'Tạm ngừng' : 'Kích hoạt'); toggle.dataset.action = 'moderate';
        toggle.onclick = async () => {
          if (toggle.disabled) return;
          if (!reason.value.trim()) { toast('Vui lòng nhập lý do kiểm duyệt.', 'error'); return; }
          if (!await confirmAction({ title: 'Cập nhật trạng thái homestay?', message: stay.name, confirmText: 'Xác nhận' })) return;
          toggle.disabled = true;
          try { await moderateHomestay(stay.id, { status: stay.status === 'active' ? 'inactive' : 'active', reason: reason.value.trim() }); await reload(); await renderOverview(); }
          catch (error) { toast(error.detail,'error'); } finally { toggle.disabled = false; }
        }; actions.append(reason,toggle);
      }
      row.append(picture(stay.images?.[0]),info,actions); return row;
    } });

  // Backend has no host name search parameter: disclose that this search covers the current page.
  $('host-search').placeholder = 'Tìm trong trang host hiện tại'; $('host-empty').hidden = true;
  let hostRows = [], reloadHostRows = async () => {};
  const renderHosts = () => {
    const query = $('host-search').value.trim().toLocaleLowerCase('vi');
    $('host-list').replaceChildren(...hostRows.filter(h => `${h.display_name} ${h.email} ${h.phone}`.toLocaleLowerCase('vi').includes(query)).map(host => {
      const row = el('article','row'), info = el('div'), actions = el('div', 'row__actions');
      info.append(el('p','row__title',host.display_name),el('p','row__meta',`${host.email} · ${host.phone || ''}`),
        el('p','row__meta',`${host.bookingCount} booking · Giá trị đơn hoàn tất ${fmtVND(host.revenue)} (không phải tiền đã thu)`),
        el('p','row__meta',`Danh sách homestay tối đa ${host.homestayProjectionLimit}: ${host.homestays.map(h=>h.title).join(', ') || 'Chưa có'}`));
      const cancel = button('Hủy làm Host'); cancel.classList.add('btn--danger');
      cancel.onclick = async () => {
        if (cancel.disabled || !await confirmAction({
          title: 'Hủy quyền Host?',
          message: `Hủy quyền của ${host.display_name}? Thao tác bị chặn nếu còn booking đang chờ, đã xác nhận hoặc khách đang lưu trú.`,
          confirmText: 'Hủy làm Host',
        })) return;
        cancel.disabled = true;
        try {
          await cancelAdminHost(host.id);
          toast(`Đã hủy quyền Host của ${host.display_name}.`);
          await reloadHostRows();
          await renderOverview();
        } catch (error) { toast(error.detail || 'Không thể hủy quyền Host.', 'error'); }
        finally { cancel.disabled = false; }
      };
      actions.append(cancel); row.append(picture(host.avatar),info,actions); return row;
    }));
  };
  $('host-search').oninput = renderHosts;
  reloadHostRows = pagedList({ root: $('host-section'), list: $('host-list'), filters: [], fetchRows: getAdminHosts,
    renderRow: () => el('div'), afterLoad(rows) { hostRows = rows; renderHosts(); $('host-count').textContent = `(${rows.length} trong trang)`; } });
  await renderOverview(tabs.value);
}
