
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

let images = []; // Data URLs dùng để xem trước ảnh

// ============================================================
// RENDER ẢNH XEM TRƯỚC
// ============================================================

function renderPreview() {
  $('preview').innerHTML = images.map((src, i) => `
    <div class="thumb">
      <img
        class="thumb__img"
        src="${src}"
        alt="Ảnh ${i + 1}"
      >

      <button
        class="thumb__remove"
        type="button"
        data-i="${i}"
        aria-label="Xóa ảnh ${i + 1}"
      >×</button>
    </div>
  `).join('');

  $('preview').querySelectorAll('[data-i]').forEach(button => {
    button.addEventListener('click', () => {
      images.splice(Number(button.dataset.i), 1);

      $('imagesErr').textContent = '';
      renderPreview();
    });
  });
}

// ============================================================
// CHỌN VÀ XỬ LÝ HÌNH ẢNH
// ============================================================

$('images').addEventListener('change', async e => {
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

  for (const file of files) {
    if (!file.type.startsWith('image/')) continue;

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
    const h = await getHostHomestay(id);

    $('name').value = h.name ?? '';
    $('address').value = h.address ?? '';
    $('description').value = h.description ?? '';

    images = [...(h.images || [])];

    renderPreview();

    // Đánh dấu các tiện ích đã lưu
    (h.amenities || []).forEach(amenity => {
      const checkbox = $('amenities').querySelector(
        `input[value="${amenity}"]`
      );

      if (checkbox) {
        checkbox.checked = true;
      }
    });

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
    id: id || undefined,
    name: $('name').value.trim(),
    address: $('address').value.trim(),
    description: $('description').value.trim(),
    amenities,
    images: images.length
      ? images
      : ['img/placeholder.svg']
  };

  try {
    await saveHostHomestay(payload);

    toast(
      id
        ? 'Đã cập nhật homestay.'
        : 'Đã thêm homestay mới.'
    );

    location.href = 'host-homestays.html';

  } catch (e2) {
    $('formMsg').hidden = false;

    $('formMsg').className =
      'msg msg--error host-homestay-form-message';

    $('formMsg').textContent =
      e2.detail ?? 'Không lưu được, thử lại.';
  }
});

// ============================================================
// XÓA HOMESTAY
// ============================================================

$('deleteBtn').addEventListener('click', async () => {
  const ok = await confirmAction({
    title: 'Xóa homestay?',
    message: 'Homestay sẽ bị ẩn khỏi kết quả tìm kiếm.',
    confirmText: 'Xóa'
  });

  if (!ok) return;

  try {
    await deleteHostHomestay(id);

    toast('Đã xóa homestay.');

    location.href = 'host-homestays.html';

  } catch (e3) {
    toast(
      e3.detail ?? 'Không xóa được.',
      'error'
    );
  }
});

// ============================================================
// KHỞI TẠO
// ============================================================

loadForEdit();
