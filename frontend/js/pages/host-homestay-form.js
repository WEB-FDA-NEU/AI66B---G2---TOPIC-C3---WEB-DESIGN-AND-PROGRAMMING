import { ACCOUNT_API_MODE, accountHref, safeImageURL } from '../config.js';
import { uploadImage } from '../api.js';

import {
  getHostHomestay,
  saveHostHomestay,
  deleteHostHomestay
} from '../api.js';

import {
  setFieldError,
  clearFieldErrors,
  confirmAction,
  toast
} from '../ui.js';

import '../components/site-header.js';
import '../components/site-footer.js';
import '../guard.js';

const $ = id => document.getElementById(id);

const id = new URLSearchParams(location.search).get('id');
if (ACCOUNT_API_MODE) {
  $('images').accept = 'image/jpeg,image/png,image/webp';
  $('images').closest('.uploader').querySelector('.field__hint').textContent = 'Tối đa 12 ảnh JPEG, PNG hoặc WebP, mỗi ảnh không quá 5 MB. Ảnh được tải lên máy chủ; lưu homestay để gắn ảnh vào hồ sơ.';
}

let uploading = false;
let saving = false;
let loaded = !id;
let original = null;
const submitButton = $('form').querySelector('[type=submit]');
submitButton.disabled = !loaded;
let images = []; // Data URLs dùng để xem trước ảnh

// ============================================================
// RENDER ẢNH XEM TRƯỚC
// ============================================================

function renderPreview() {
  const fragment = document.createDocumentFragment();
  images.forEach((src, i) => {
    const wrapper = document.createElement('div'); wrapper.className = 'thumb';
    const image = document.createElement('img'); image.className = 'thumb__img'; image.src = safeImageURL(src); image.alt = `\u1ea2nh ${i + 1}`;
    image.onerror = () => { image.onerror = null; image.src = 'img/placeholder.svg'; };
    const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'thumb__remove'; remove.textContent = '\u00d7'; remove.dataset.i = i;
    remove.setAttribute('aria-label', `X\u00f3a \u1ea3nh ${i + 1}`);
    remove.addEventListener('click', () => { if (uploading || saving) return; images.splice(i, 1); $('imagesErr').textContent = ''; renderPreview(); });
    wrapper.append(image, remove); fragment.append(wrapper);
  });
  $('preview').replaceChildren(fragment);
}

// ============================================================
// CHỌN VÀ XỬ LÝ HÌNH ẢNH
// ============================================================

$('images').addEventListener('change', async e => {
  if (uploading || saving) return;
  const selectedFiles = [...e.target.files];

  const remaining = 12 - images.length;

  if (remaining <= 0) {
    $('imagesErr').textContent = 'Bạn chỉ được chọn tối đa 12 ảnh.';
    e.target.value = '';
    return;
  }

  const files = selectedFiles.slice(0, remaining);

  if (selectedFiles.length > remaining) {
    $('imagesErr').textContent =
      `Chỉ có thể thêm ${remaining} ảnh nữa.`;
  } else {
    $('imagesErr').textContent = '';
  }

  uploading = true; submitButton.disabled = true;
  for (const file of files) {
    if (ACCOUNT_API_MODE) {
      try { const result = await uploadImage(file); images.push(result.url); }
      catch (error) { $('imagesErr').textContent = error.detail || error.message; }
      continue;
    }
    if (!['image/jpeg','image/png','image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) { $('imagesErr').textContent = 'JPEG, PNG, WebP; maximum 5 MB.'; continue; }

    const dataUrl = await new Promise(resolve => {
      const reader = new FileReader();

      reader.onload = () => resolve(reader.result);
      reader.onerror = () => resolve(null);

      reader.readAsDataURL(file);
    });

    if (dataUrl) {
      images.push(dataUrl);
    }
  }

  uploading = false; submitButton.disabled = !loaded;
  e.target.value = '';

  if (images.length >= 12) {
    $('imagesErr').textContent = 'Đã đạt tối đa 12 ảnh.';
  }

  renderPreview();
});

// ============================================================
// TẢI DỮ LIỆU KHI CHỈNH SỬA HOMESTAY
// ============================================================

async function loadForEdit() {
  if (!id) return;

  $('formTitle').textContent = 'Sửa homestay';
  $('crumb').textContent = 'Sửa homestay';

  // Hiện nút xóa khi đang chỉnh sửa
  $('deleteBtn').hidden = false;

  try {
    const h = await getHostHomestay(id); original = h;

    $('name').value = h.name ?? '';
    $('address').value = h.address ?? '';
    $('description').value = h.description ?? '';

    images = [...(h.images || [])];

    renderPreview();

    for (const checkbox of $('amenities').querySelectorAll('input')) checkbox.checked = (h.amenities || []).includes(checkbox.value);
    loaded = true; submitButton.disabled = false;

  } catch (e) {
    toast(
      e.detail ?? 'Không tải được homestay.',
      'error'
    );
  }
}

// ============================================================
// LƯU HOMESTAY
// ============================================================

$('form').addEventListener('submit', async e => {
  e.preventDefault();
  if (uploading || saving || !loaded) return;

  clearFieldErrors($('form'));

  $('formMsg').hidden = true;
  $('formMsg').textContent = '';

  let ok = true;

  if (!$('name').value.trim()) {
    setFieldError(
      $('name'),
      'Vui lòng nhập tên homestay.'
    );

    ok = false;
  }

  if (!$('address').value.trim()) {
    setFieldError(
      $('address'),
      'Vui lòng nhập địa chỉ.'
    );

    ok = false;
  }

  if (!$('description').value.trim()) {
    setFieldError(
      $('description'),
      'Vui lòng nhập mô tả.'
    );

    ok = false;
  }

  if (!ok) return;

  // Lấy danh sách tiện ích đã chọn
  const amenities = [
    ...$('amenities').querySelectorAll('input:checked')
  ].map(input => input.value);

  const payload = {
    ...(ACCOUNT_API_MODE && original && $('address').value.trim() === original.address ? { city: original.city, location: original.location } : {}),
    id: id || undefined,
    name: $('name').value.trim(),
    address: $('address').value.trim(),
    description: $('description').value.trim(),
    amenities: [...new Set([...amenities, ...(ACCOUNT_API_MODE && original ? original.amenities.filter(value => ![...$('amenities').querySelectorAll('input')].some(input => input.value === value)) : [])])],
    images: images.length
      ? images
      : ['img/placeholder.svg']
  };

  saving = true; submitButton.disabled = true;
  try {
    await saveHostHomestay(payload);

    toast(
      id
        ? 'Đã cập nhật homestay.'
        : 'Đã thêm homestay mới.'
    );

    location.href = accountHref('host-homestays.html');

  } catch (e2) {
    $('formMsg').hidden = false;

    $('formMsg').className =
      'msg msg--error host-homestay-form-message';

    $('formMsg').textContent =
      e2.detail ?? 'Không lưu được, thử lại.';
  } finally { saving = false; submitButton.disabled = false; }
});

// ============================================================
// XÓA HOMESTAY
// ============================================================

$('deleteBtn').addEventListener('click', async () => {
  if (saving || uploading || !loaded) return;
  const ok = await confirmAction({
    title: 'Xóa homestay?',
    message: 'Homestay sẽ bị ẩn khỏi kết quả tìm kiếm.',
    confirmText: 'Xóa'
  });

  if (!ok || saving) return;
  saving = true; $('deleteBtn').disabled = true;
  try {
    await deleteHostHomestay(id);

    toast('Đã xóa homestay.');

    location.href = accountHref('host-homestays.html');

  } catch (e3) {
    toast(
      e3.detail ?? 'Không xóa được.',
      'error'
    );
  } finally { saving = false; $('deleteBtn').disabled = false; }
});

// ============================================================
// KHỞI TẠO
// ============================================================

loadForEdit();
