// ============================================================
//  Trang hồ sơ: điền thông tin, lưu hồ sơ, đổi mật khẩu, đổi ảnh đại diện.
//  Mock: lưu vào localStorage qua api.js (updateProfile / changePassword).
// ============================================================
import { updateProfile, changePassword, ApiError } from '../api.js';
import { getUser, getToken, saveSession, isLoggedIn, requireLogin } from '../auth.js';
import { toast, setFieldError, clearFieldErrors } from '../ui.js';
import '../components/site-header.js';
import '../components/site-footer.js';

if (!isLoggedIn()) requireLogin();

const DEFAULT_AVATAR = 'img/avatar_default.jpg';
const MAX_AVATAR_BYTES = 5 * 1024 * 1024;
const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/webp'];

const profileForm  = document.getElementById('profile-form');
const passwordForm = document.getElementById('password-form');
const avatarImg    = document.querySelector('.profile-avatar__img');
const avatarInput  = document.getElementById('avatar');

let user = getUser();

// Host/admin không cần thấy lời mời "Trở thành Host"
if (user?.role === 'host' || user?.role === 'admin') {
  document.getElementById('become-host-section')?.remove();
}

// ---------- Điền dữ liệu hiện tại ----------
function fillForm() {
  if (!user) return;
  profileForm.display_name.value = user.display_name ?? '';
  profileForm.email.value        = user.email ?? '';
  profileForm.phone.value        = user.phone ?? '';
  setAvatar(user.avatar);
}

function setAvatar(src) {
  avatarImg.onerror = () => { avatarImg.onerror = null; avatarImg.src = DEFAULT_AVATAR; };
  avatarImg.src = src || DEFAULT_AVATAR;
}

/** Ghi user mới vào phiên đăng nhập và cập nhật tên trên header ngay. */
function applyUser(updated) {
  user = { ...user, ...updated };
  saveSession({ access_token: getToken(), user });
  const nameEl = document.querySelector('[data-user-name]');
  if (nameEl) nameEl.textContent = user.display_name ?? '';
}

function withBusy(btn, fn) {
  btn.disabled = true;
  return fn().finally(() => { btn.disabled = false; });
}

// ---------- Lưu thông tin cá nhân ----------
profileForm.addEventListener('submit', async e => {
  e.preventDefault();
  clearFieldErrors(profileForm);

  const name  = profileForm.display_name.value.trim();
  const email = profileForm.email.value.trim();
  const phone = profileForm.phone.value.trim();

  let ok = true;
  if (name.length < 2)                 { setFieldError(profileForm.display_name, 'Họ tên tối thiểu 2 ký tự.'); ok = false; }
  if (!profileForm.email.validity.valid || !email) { setFieldError(profileForm.email, 'Email không hợp lệ.'); ok = false; }
  if (phone && !/^(0|\+84)\d{9,10}$/.test(phone.replace(/\s/g, ''))) {
    setFieldError(profileForm.phone, 'Số điện thoại không hợp lệ (VD: 0912345678).'); ok = false;
  }
  if (!ok) return;

  await withBusy(profileForm.querySelector('button[type=submit]'), async () => {
    try {
      const updated = await updateProfile({ display_name: name, email, phone });
      applyUser(updated);
      toast('Đã lưu thông tin cá nhân.');
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) setFieldError(profileForm.email, err.detail);
      else toast(err.detail ?? 'Lưu thất bại, thử lại sau.', 'error');
    }
  });
});

// ---------- Đổi mật khẩu ----------
passwordForm.addEventListener('submit', async e => {
  e.preventDefault();
  clearFieldErrors(passwordForm);

  const current = passwordForm.current_password;
  const next    = passwordForm.new_password;
  const confirm = passwordForm.confirm_password;

  let ok = true;
  if (!current.value)                { setFieldError(current, 'Vui lòng nhập mật khẩu hiện tại.'); ok = false; }
  if (next.value.length < 8)         { setFieldError(next, 'Mật khẩu mới tối thiểu 8 ký tự.'); ok = false; }
  else if (next.value === current.value) { setFieldError(next, 'Mật khẩu mới phải khác mật khẩu hiện tại.'); ok = false; }
  if (confirm.value !== next.value)  { setFieldError(confirm, 'Mật khẩu nhập lại không khớp.'); ok = false; }
  if (!ok) return;

  await withBusy(passwordForm.querySelector('button[type=submit]'), async () => {
    try {
      await changePassword(current.value, next.value);
      passwordForm.reset();
      toast('Đã đổi mật khẩu.');
    } catch (err) {
      if (err instanceof ApiError && err.status === 400) setFieldError(current, err.detail);
      else toast(err.detail ?? 'Đổi mật khẩu thất bại.', 'error');
    }
  });
});

// ---------- Đổi ảnh đại diện (thu nhỏ còn 256px rồi lưu) ----------
function shrinkAvatar(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = reject;
    reader.onload = () => {
      const img = new Image();
      img.onerror = reject;
      img.onload = () => {
        const side = Math.min(img.width, img.height);           // cắt vuông ở giữa
        const canvas = document.createElement('canvas');
        canvas.width = canvas.height = 256;
        canvas.getContext('2d').drawImage(img, (img.width - side) / 2, (img.height - side) / 2, side, side, 0, 0, 256, 256);
        resolve(canvas.toDataURL('image/jpeg', 0.85));
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

avatarInput.addEventListener('change', async () => {
  const file = avatarInput.files[0];
  if (!file) return;
  if (!ALLOWED_TYPES.includes(file.type)) { toast('Chỉ nhận ảnh JPEG, PNG hoặc WebP.', 'error'); avatarInput.value = ''; return; }
  if (file.size > MAX_AVATAR_BYTES)       { toast('Ảnh quá lớn, tối đa 5MB.', 'error'); avatarInput.value = ''; return; }

  try {
    const dataUrl = await shrinkAvatar(file);
    const updated = await updateProfile({ avatar: dataUrl });
    applyUser(updated);
    setAvatar(dataUrl);
    toast('Đã cập nhật ảnh đại diện.');
  } catch (err) {
    toast(err.detail ?? 'Không đổi được ảnh đại diện.', 'error');
  } finally {
    avatarInput.value = '';
  }
});

fillForm();
