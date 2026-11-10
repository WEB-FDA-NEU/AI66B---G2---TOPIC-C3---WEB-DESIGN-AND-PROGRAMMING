import { getHostHomestay, saveHostHomestay, deleteHostHomestay } from '../api.js';
import { setFieldError, clearFieldErrors, confirmAction, toast } from '../ui.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const $ = id => document.getElementById(id);
const id = new URLSearchParams(location.search).get('id');
let images = []; // ảnh xem trước (data URL đã thu nhỏ)

const MAX_IMAGES = 12;
const MAX_SIDE = 900;   // thu nhỏ ảnh để không đầy localStorage (mock) và tải nhanh hơn

function renderPreview() {
  $('preview').innerHTML = images.map((src, i) => `
    <div class="thumb"><img class="thumb__img" src="${src}" alt="Ảnh ${i + 1}">
      ${i === 0 ? '<span class="thumb__cover">Ảnh bìa</span>' : ''}
      <button class="thumb__remove" type="button" data-i="${i}" aria-label="Xóa ảnh">×</button></div>`).join('');
  $('preview').querySelectorAll('[data-i]').forEach(b =>
    b.addEventListener('click', () => { images.splice(+b.dataset.i, 1); $('imagesErr').textContent = ''; renderPreview(); }));
}

/** Đọc file ảnh → thu nhỏ còn tối đa MAX_SIDE px → data URL JPEG. */
function readAndShrink(file) {
  return new Promise(resolve => {
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        const scale = Math.min(1, MAX_SIDE / Math.max(img.width, img.height));
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(img.width * scale);
        canvas.height = Math.round(img.height * scale);
        canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
        resolve(canvas.toDataURL('image/jpeg', 0.7));
      };
      img.onerror = () => resolve(reader.result);
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

$('images').addEventListener('change', async e => {
  const files = [...e.target.files].slice(0, MAX_IMAGES - images.length);
  for (const f of files) images.push(await readAndShrink(f));
  e.target.value = '';
  $('imagesErr').textContent = images.length >= MAX_IMAGES ? `Đã đạt tối đa ${MAX_IMAGES} ảnh.` : '';
  renderPreview();
});

async function loadForEdit() {
  if (!id) return;
  $('formTitle').textContent = 'Sửa homestay';
  $('crumb').textContent = 'Sửa homestay';
  $('deleteBtn').hidden = false;
  try {
    const h = await getHostHomestay(id);
    $('name').value = h.name;
    $('address').value = h.address;
    $('description').value = h.description;
    $('price').value = h.price ?? '';
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
  if ($('price').value !== '' && Number($('price').value) < 0) { setFieldError($('price'), 'Giá không hợp lệ.'); ok = false; }
  if (!ok) return;

  const amenities = [...$('amenities').querySelectorAll('input:checked')].map(i => i.value);
  const payload = {
    id: id || undefined,
    name: $('name').value.trim(),
    address: $('address').value.trim(),
    description: $('description').value.trim(),
    price: $('price').value === '' ? null : Number($('price').value),
    amenities,
    images: images.length ? images : ['img/placeholder.svg'],
  };
  try {
    await saveHostHomestay(payload);
    toast(id ? 'Đã cập nhật homestay.' : 'Đã thêm homestay mới.');
    location.href = 'host-homestays.html';
  } catch (e2) {
    $('formMsg').hidden = false; $('formMsg').className = 'msg msg--error mt-3';
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