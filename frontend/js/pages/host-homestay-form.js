import { getHostHomestay, saveHostHomestay, deleteHostHomestay } from '../api.js';
import { setFieldError, clearFieldErrors, confirmAction, toast } from '../ui.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const $ = id => document.getElementById(id);
const id = new URLSearchParams(location.search).get('id');
let images = []; // data URLs xem trước

function renderPreview() {
  $('preview').innerHTML = images.map((src, i) => `
    <div class="thumb"><img class="thumb__img" src="${src}" alt="Ảnh ${i + 1}">
      <button class="thumb__remove" type="button" data-i="${i}" aria-label="Xóa ảnh">×</button></div>`).join('');
  $('preview').querySelectorAll('[data-i]').forEach(b =>
    b.addEventListener('click', () => { images.splice(+b.dataset.i, 1); renderPreview(); }));
}

$('images').addEventListener('change', async e => {
  const files = [...e.target.files].slice(0, 12 - images.length);
  for (const f of files) {
    images.push(await new Promise(res => { const r = new FileReader(); r.onload = () => res(r.result); r.readAsDataURL(f); }));
  }
  e.target.value = '';
  $('imagesErr').textContent = images.length >= 12 ? 'Đã đạt tối đa 12 ảnh.' : '';
  renderPreview();
});

async function loadForEdit() {
  if (!id) return;
  $('formTitle').textContent = 'Sửa homestay';
  $('crumb').textContent = 'Sửa homestay';
  $('deleteBtn').style.display = 'inline-flex';
  try {
    const h = await getHostHomestay(id);
    $('name').value = h.name;
    $('address').value = h.address;
    $('description').value = h.description;
    images = [...(h.images || [])];
    renderPreview();
    (h.amenities || []).forEach(a => {
      const box = $('amenities').querySelector(`input[value="${a}"]`);
      if (box) box.checked = true;
    });
  } catch (e) { toast(e.detail ?? 'Không tải được homestay.', 'error'); }
}

$('form').addEventListener('submit', async e => {
  e.preventDefault();
  clearFieldErrors($('form'));
  let ok = true;
  if (!$('name').value.trim())        { setFieldError($('name'), 'Vui lòng nhập tên homestay.'); ok = false; }
  if (!$('address').value.trim())     { setFieldError($('address'), 'Vui lòng nhập địa chỉ.'); ok = false; }
  if (!$('description').value.trim()) { setFieldError($('description'), 'Vui lòng nhập mô tả.'); ok = false; }
  if (!ok) return;

  const amenities = [...$('amenities').querySelectorAll('input:checked')].map(i => i.value);
  const payload = {
    id: id || undefined,
    name: $('name').value.trim(),
    address: $('address').value.trim(),
    description: $('description').value.trim(),
    amenities,
    images: images.length ? images : ['img/placeholder.svg'],
  };
  try {
    await saveHostHomestay(payload);
    toast(id ? 'Đã cập nhật homestay.' : 'Đã thêm homestay mới.');
    location.href = 'host-homestays.html';
  } catch (e2) {
    $('formMsg').style.display = 'block'; $('formMsg').className = 'msg msg--error mt-3';
    $('formMsg').textContent = e2.detail ?? 'Không lưu được, thử lại.';
  }
});

$('deleteBtn').addEventListener('click', async () => {
  const ok = await confirmAction({ title: 'Xóa homestay?', message: 'Homestay sẽ bị ẩn khỏi kết quả tìm kiếm.', confirmText: 'Xóa' });
  if (!ok) return;
  try { await deleteHostHomestay(id); toast('Đã xóa homestay.'); location.href = 'host-homestays.html'; }
  catch (e3) { toast(e3.detail ?? 'Không xóa được.', 'error'); }
});

loadForEdit();
