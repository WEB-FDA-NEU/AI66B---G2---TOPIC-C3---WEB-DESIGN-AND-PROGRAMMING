import { getProfile, updateProfile, changePassword } from '../api.js';
import { isLoggedIn, requireLogin } from '../auth.js';
import { toast, clearFieldErrors, setFieldError } from '../ui.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const profileForm = document.getElementById('profile-form');
const passwordForm = document.getElementById('password-form');
const avatarInput = document.getElementById('avatar');
const preview = document.getElementById('avatar-preview');
const avatarError = document.getElementById('avatar-error');
let user, avatar, imageVersion = 0, imageBusy = false, saving = false;
const input = (form, name) => form.elements.namedItem(name);
const profileButton = profileForm.querySelector('[type="submit"]');
const passwordButton = passwordForm.querySelector('[type="submit"]');

function syncButton() { profileButton.disabled = !user || imageBusy || saving; }
function fillProfile() {
  for (const key of ['display_name', 'email', 'phone']) input(profileForm, key).value = user[key] ?? '';
  preview.src = user.avatar || 'img/avatar_default.jpg';
  if (['host', 'admin'].includes(user.role)) document.getElementById('become-host-section')?.remove();
}

// Decode ảnh thật, thu nhỏ và mã hóa lại để không lưu file gốc lớn vào localStorage.
async function readAvatar(file) {
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) throw new Error('Chỉ chấp nhận JPEG, PNG hoặc WebP.');
  if (!file.size || file.size > 5 * 1024 * 1024) throw new Error('Ảnh phải có dung lượng từ 1 byte đến 5MB.');
  const bytes = new Uint8Array(await file.slice(0, 12).arrayBuffer());
  const jpeg = bytes[0] === 255 && bytes[1] === 216 && bytes[2] === 255;
  const png = [137,80,78,71,13,10,26,10].every((v, i) => bytes[i] === v);
  const webp = String.fromCharCode(...bytes.slice(0, 4)) === 'RIFF' && String.fromCharCode(...bytes.slice(8, 12)) === 'WEBP';
  if (!(file.type === 'image/jpeg' ? jpeg : file.type === 'image/png' ? png : webp))
    throw new Error('Nội dung file không khớp loại ảnh.');
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    await new Promise((resolve, reject) => {
      image.onload = resolve;
      image.onerror = () => reject(new Error('File ảnh bị hỏng hoặc không đọc được.'));
      image.src = url;
    });
    if (!image.naturalWidth || image.naturalWidth * image.naturalHeight > 40000000) throw new Error('Kích thước ảnh quá lớn.');
    const scale = Math.min(1, 256 / Math.max(image.naturalWidth, image.naturalHeight));
    const canvas = document.createElement('canvas');
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/png');
  } finally { URL.revokeObjectURL(url); }
}

avatarInput.disabled = true;
avatarInput.addEventListener('change', async () => {
  const version = ++imageVersion;
  const file = avatarInput.files[0];
  avatarError.textContent = '';
  avatarInput.removeAttribute('aria-invalid');
  if (!file) { imageBusy = false; syncButton(); return; }
  imageBusy = true; syncButton();
  try {
    const result = await readAvatar(file);
    if (version !== imageVersion) return;
    avatar = result; preview.src = result;
  } catch (err) {
    if (version !== imageVersion) return;
    avatarError.textContent = err.message;
    avatarInput.setAttribute('aria-invalid', 'true');
    avatar = undefined; preview.src = user.avatar || 'img/avatar_default.jpg';
  } finally {
    if (version === imageVersion) { imageBusy = false; avatarInput.value = ''; syncButton(); }
  }
});

profileForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (!user || imageBusy || saving) return;
  clearFieldErrors(profileForm);
  let valid = true;
  const name = input(profileForm, 'display_name'), email = input(profileForm, 'email'), phone = input(profileForm, 'phone');
  if (name.value.trim().length < 2 || name.value.trim().length > 80) { setFieldError(name, 'Họ tên phải có từ 2 đến 80 ký tự.'); valid = false; }
  if (!email.value.trim() || !email.validity.valid) { setFieldError(email, 'Email không hợp lệ.'); valid = false; }
  if (phone.value.trim() && !/^(0|\+84)[35789][0-9]{8}$/.test(phone.value.trim())) { setFieldError(phone, 'Số điện thoại không hợp lệ.'); valid = false; }
  if (!valid) return;
  saving = true; avatarInput.disabled = true; syncButton();
  try {
    user = await updateProfile({ display_name: name.value, email: email.value, phone: phone.value, avatar });
    avatar = undefined; fillProfile(); toast('Đã lưu hồ sơ mock trên trình duyệt này.');
  } catch (err) {
    if (err.status === 409) setFieldError(email, err.detail);
    else toast(err.detail ?? 'Không lưu được hồ sơ.', 'error');
  } finally { saving = false; avatarInput.disabled = false; syncButton(); }
});

passwordForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (!user || passwordButton.disabled) return;
  clearFieldErrors(passwordForm);
  const current = input(passwordForm, 'current_password'), next = input(passwordForm, 'new_password'), confirm = input(passwordForm, 'confirm_password');
  let valid = true;
  if (!current.value) { setFieldError(current, 'Nhập mật khẩu hiện tại.'); valid = false; }
  if (next.value.length < 8 || next.value.length > 128) { setFieldError(next, 'Mật khẩu phải có từ 8 đến 128 ký tự.'); valid = false; }
  else if (next.value === current.value) { setFieldError(next, 'Mật khẩu mới phải khác mật khẩu hiện tại.'); valid = false; }
  if (next.value !== confirm.value) { setFieldError(confirm, 'Hai mật khẩu không khớp.'); valid = false; }
  if (!valid) return;
  passwordButton.disabled = true;
  try {
    await changePassword(current.value, next.value);
    toast('Đã đổi mật khẩu mock trên trình duyệt này.');
  } catch (err) { toast(err.detail ?? 'Không đổi được mật khẩu.', 'error'); }
  finally { passwordForm.reset(); passwordButton.disabled = false; }
});

if (!isLoggedIn()) requireLogin();
else {
  getProfile().then(profile => {
    user = profile; fillProfile(); syncButton();
    avatarInput.disabled = false; passwordButton.disabled = false;
  }).catch(err => { toast(err.detail ?? 'Không tải được hồ sơ.', 'error'); });
}
