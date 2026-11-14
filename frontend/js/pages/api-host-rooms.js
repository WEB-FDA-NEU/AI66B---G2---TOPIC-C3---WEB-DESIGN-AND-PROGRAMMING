import { getHostHomestays, getHostRooms, getHostRoom, saveHostRoom, deleteHostRoom,
  uploadImage, getRoomBlocks, saveRoomBlock, deleteRoomBlock } from '../api.js';
import { safeImageURL } from '../config.js';
import { formatVND } from '../render.js';
import { confirmAction, toast } from '../ui.js';

const $ = id => document.getElementById(id);
const node = (tag, className, text) => {
  const el = document.createElement(tag); if (className) el.className = className;
  if (text !== undefined) el.textContent = text; return el;
};
const field = (label, input) => { const el = node('label', 'field'); el.append(node('span', 'field__label', label), input); return el; };
const input = (id, type, value = '') => { const el = node('input', 'input'); Object.assign(el, { id, type, value }); return el; };
const button = (text, className = 'btn') => { const el = node('button', className, text); el.type = 'button'; return el; };
const image = src => { const el = node('img', 'row__img host-room-card__img'); el.src = safeImageURL(src || 'img/placeholder.svg'); el.alt = ''; el.onerror = () => { el.onerror = null; el.src = 'img/placeholder.svg'; }; return el; };

export async function initHostRooms() {
  let homestayId = new URLSearchParams(location.search).get('homestayId');
  let selected = null, images = [], blocks = [], page = 1, busy = false, loading = false, editingBlock = null;
  const save = $('roomForm').querySelector('[type=submit]');
  const inventory = input('rInventory', 'number', '1'); inventory.min = '1'; inventory.max = '100'; inventory.step = '1';
  const status = node('select', 'input'); status.id = 'rStatus';
  for (const [value, label] of [['active', 'Đang hoạt động'], ['inactive', 'Tạm ngừng']]) status.add(new Option(label, value));
  $('rPrice').closest('label').after(field('Số lượng phòng', inventory), field('Trạng thái', status));
  const endDate = input('rBlockEnd', 'date'), unit = node('select', 'input'), reason = input('rBlockReason', 'text');
  unit.id = 'rBlockUnit'; reason.maxLength = 500;
  const blockControls = $('addBlockDate').parentElement;
  blockControls.before(node('p', 'field__hint', 'Lịch chặn lưu riêng trên máy chủ. Ngày kết thúc không bao gồm đêm bị chặn. Lưu phòng trước khi thêm lịch.'));
  const cancelBlock = button('Hủy sửa lịch'); cancelBlock.hidden = true;
  blockControls.after(field('Ngày kết thúc', endDate), field('Phạm vi', unit), field('Lý do', reason), cancelBlock);
  const pager = node('div', 'row__actions'); $('list').after(pager);
  $('rImages').accept = 'image/jpeg,image/png,image/webp';
  $('rImages').closest('.uploader').querySelector('.field__hint').textContent = 'Tối đa 6 ảnh JPEG, PNG hoặc WebP, mỗi ảnh không quá 5 MB. Ảnh được tải lên máy chủ; lưu phòng để gắn ảnh vào phòng.';

  function setBusy(value) {
    busy = value; save.disabled = value; $('rImages').disabled = value;
    $('addBlockDate').disabled = value || !selected;
    for (const el of $('blockList').querySelectorAll('button')) el.disabled = value;
  }
  function resetBlock() {
    editingBlock = null; $('rBlockDate').value = ''; endDate.value = ''; reason.value = ''; unit.value = '';
    $('addBlockDate').textContent = 'Thêm'; cancelBlock.hidden = true;
  }
  cancelBlock.onclick = resetBlock;
  function renderImages() {
    $('rPreview').replaceChildren(...images.map((src, index) => {
      const wrapper = node('div', 'thumb'), img = image(src); img.className = 'thumb__img';
      const remove = button('×', 'thumb__remove'); remove.dataset.ri = index; remove.setAttribute('aria-label', 'Xóa ảnh');
      remove.onclick = () => { if (!busy) { images.splice(index, 1); renderImages(); } };
      wrapper.append(img, remove); return wrapper;
    }));
  }
  function renderBlocks() {
    $('blockList').replaceChildren(...blocks.map(block => {
      const row = node('div', 'tag'); row.dataset.blockId = block.id;
      row.append(node('span', '', `${block.start_date} → ${block.end_date} · ${block.unit == null ? 'Tất cả phòng' : 'Phòng số ' + block.unit} · ${block.reason}`));
      const edit = button('Sửa'), remove = button('Xóa');
      edit.onclick = () => {
        if (busy) return;
        editingBlock = block.id; $('rBlockDate').value = block.start_date; endDate.value = block.end_date;
        unit.value = block.unit == null ? '' : String(block.unit); reason.value = block.reason;
        $('addBlockDate').textContent = 'Lưu lịch'; cancelBlock.hidden = false;
      };
      remove.onclick = async () => {
        if (busy || !selected) return;
        if (!await confirmAction({ title: 'Xóa lịch chặn?', message: 'Chỉ xóa lịch đã chọn.', confirmText: 'Xóa' }) || busy) return;
        setBusy(true);
        try { await deleteRoomBlock(selected.id, block.id); blocks = await getRoomBlocks(selected.id); resetBlock(); renderBlocks(); }
        catch (error) { toast(error.detail, 'error'); } finally { setBusy(false); }
      };
      row.append(edit, remove); return row;
    }));
  }
  $('rImages').onchange = async event => {
    if (busy) return;
    const files = [...event.target.files]; setBusy(true); $('rImagesErr').textContent = '';
    try {
      if (files.length + images.length > 6) throw Error('Chỉ được chọn tối đa 6 ảnh.');
      for (const file of files) { const uploaded = await uploadImage(file); images.push(uploaded.url); renderImages(); }
    } catch (error) { $('rImagesErr').textContent = error.detail || error.message; }
    finally { event.target.value = ''; setBusy(false); }
  };
  $('addBlockDate').onclick = async () => {
    if (busy || !selected) return;
    const start = $('rBlockDate').value, end = endDate.value;
    if (!start || !end || end <= start) { toast('Ngày kết thúc phải sau ngày bắt đầu.', 'error'); return; }
    setBusy(true);
    try {
      await saveRoomBlock(selected.id, { ...(editingBlock ? { id: editingBlock } : {}), start_date: start, end_date: end,
        unit: unit.value ? Number(unit.value) : null, reason: reason.value.trim() });
      blocks = await getRoomBlocks(selected.id); resetBlock(); renderBlocks(); toast('Đã lưu lịch chặn.');
    } catch (error) { toast(error.detail, 'error'); } finally { setBusy(false); }
  };
  async function open(roomId = null) {
    if (busy || loading) return;
    setBusy(true); selected = null; blocks = []; resetBlock();
    try {
      const room = roomId ? await getHostRoom(roomId) : null;
      const loadedBlocks = room ? await getRoomBlocks(room.id) : [];
      selected = room; blocks = loadedBlocks;
      $('roomId').value = room?.id || ''; $('rName').value = room?.name || ''; $('rDesc').value = room?.description || '';
      $('rCap').value = room?.capacity || 2; $('rPrice').value = room?.pricePerNight || '';
      inventory.value = room?.inventory || 1; status.value = room?.status || 'active';
      unit.replaceChildren(new Option('Tất cả phòng', ''));
      for (let n = 1; n <= Number(inventory.value); n++) unit.add(new Option('Phòng số ' + n, String(n)));
      images = [...(room?.images || [])]; $('rImagesErr').textContent = '';
      renderImages(); renderBlocks(); $('roomFormTitle').textContent = room ? 'Sửa phòng' : 'Thêm phòng';
      $('roomForm').classList.add('is-open'); $('roomForm').scrollIntoView({ behavior: 'smooth', block: 'center' });
    } catch (error) { $('roomForm').classList.remove('is-open'); toast(error.detail, 'error'); }
    finally { setBusy(false); }
  }
  $('addBtn').onclick = () => open();
  $('cancelRoomForm').onclick = () => { if (!busy) $('roomForm').classList.remove('is-open'); };
  $('roomForm').onsubmit = async event => {
    event.preventDefault(); if (busy || loading) return;
    if (!$('rName').value.trim() || $('rDesc').value.trim().length < 5 || !Number.isInteger(Number(inventory.value)) || Number(inventory.value) < 1 || Number(inventory.value) > 100 || Number($('rPrice').value) <= 0) {
      toast('Kiểm tra tên, mô tả tối thiểu 5 ký tự, giá dương và số lượng phòng 1–100.', 'error'); return;
    }
    setBusy(true);
    try {
      await saveHostRoom({ ...(selected ? { id: selected.id } : {}), homestayId, name: $('rName').value.trim(), description: $('rDesc').value.trim(),
        capacity: Number($('rCap').value), pricePerNight: Number($('rPrice').value), inventory: Number(inventory.value), status: status.value,
        images: images.length ? images : ['img/placeholder.svg'] });
      // Metadata saves never replace structured/partial blocks with legacy blockedDates.
      $('roomForm').classList.remove('is-open'); toast('Đã lưu phòng.'); await load();
    } catch (error) { toast(error.detail, 'error'); } finally { setBusy(false); }
  };
  async function load() {
    if (loading) return; loading = true;
    try {
      const rooms = homestayId ? await getHostRooms(homestayId, { page, page_size: 20 }) : [];
      $('list').replaceChildren(...rooms.map(room => {
        const card = node('article', 'host-room-card'), info = node('div', 'host-room-card__info'), actions = node('div', 'row__actions host-room-card__actions');
        info.append(node('p', 'row__title', room.name), node('p', 'row__meta host-room-card__description', room.description),
          node('p', 'row__meta', `Tối đa ${room.capacity} khách · ${room.inventory} phòng · ${room.status === 'active' ? 'Đang hoạt động' : 'Tạm ngừng'}`),
          node('p', 'row__price', `${formatVND(room.pricePerNight)} / đêm`));
        const edit = button('Sửa'), remove = button('Xóa', 'btn btn--danger'); edit.dataset.edit = room.id; remove.dataset.del = room.id;
        edit.onclick = () => open(room.id);
        remove.onclick = async () => {
          if (busy || loading || !await confirmAction({ title: 'Xóa phòng?', message: `Ẩn ${room.name}? Lịch sử đặt phòng vẫn được giữ.`, confirmText: 'Xóa' }) || busy) return;
          setBusy(true);
          try { await deleteHostRoom(room.id); $('roomForm').classList.remove('is-open'); await load(); }
          catch (error) { toast(error.detail, 'error'); } finally { setBusy(false); }
        };
        actions.append(edit, remove); card.append(image(room.images?.[0]), info, actions); return card;
      }));
      if (!rooms.length) $('list').append(node('p', 'empty', 'Chưa có phòng ở trang này.'));
      pager.replaceChildren();
      for (const [label, delta, disabled] of [['Trước', -1, page === 1], ['Sau', 1, rooms.length < 20]]) {
        const el = button(label); el.disabled = disabled; el.onclick = () => { if (!loading && !busy) { page += delta; load(); } }; pager.append(el);
      }
    } catch (error) { $('list').replaceChildren(node('p', 'text-danger', error.detail || 'Không tải được phòng.')); pager.replaceChildren(); }
    finally { loading = false; }
  }
  try {
    const homestays = [];
    for (let n = 1; ; n++) { const batch = await getHostHomestays({ page: n, page_size: 100 }); homestays.push(...batch); if (batch.length < 100) break; }
    if (!homestays.some(h => h.id === homestayId)) homestayId = homestays[0]?.id;
    $('homestayName').replaceChildren();
    const select = node('select', 'input host-room-homestay-select'); select.id = 'hsSwitch';
    for (const h of homestays) select.add(new Option(h.name, h.id)); select.value = homestayId || '';
    $('homestayName').append(select); $('addBtn').disabled = !homestayId;
    select.onchange = () => { if (busy || loading) { select.value = homestayId || ''; return; } homestayId = select.value; page = 1; $('roomForm').classList.remove('is-open'); load(); };
    await load();
  } catch (error) { $('addBtn').disabled = true; $('homestayName').textContent = error.detail || 'Không tải được homestay.'; }
}
