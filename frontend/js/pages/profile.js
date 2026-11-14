import { getProfile, updateProfile, changePassword, getHostApplication, applyHost, deleteAccount } from '../api.js';
import { ACCOUNT_API_MODE, accountHref, safeImageURL } from '../config.js';
import { isLoggedIn, requireLogin } from '../auth.js';
import { toast, clearFieldErrors, setFieldError } from '../ui.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const profileForm = document.getElementById('profile-form');
const passwordForm = document.getElementById('password-form');
const avatarInput = document.getElementById('avatar');
const preview = document.getElementById('avatar-preview');
const avatarError = document.getElementById('avatar-error');
const hostApplicationSection = document.getElementById('become-host-section');
const hostApplicationStatus = document.getElementById('host-application-status');
const hostApplicationForm = document.getElementById('host-application-form');
const hostApplyButton = document.getElementById('host-apply-open');
const hostApplicationSubmitError = document.getElementById('host-application-submit-error');
let user, avatar, imageVersion = 0, imageBusy = false, saving = false;
const input = (form, name) => form.elements.namedItem(name);
const profileButton = profileForm.querySelector('[type="submit"]');
const passwordButton = passwordForm.querySelector('[type="submit"]');

function syncButton() { profileButton.disabled = !user || imageBusy || saving; }
function fillProfile() {
  for (const key of ['display_name', 'email', 'phone']) input(profileForm, key).value = user[key] ?? '';
  preview.src = safeImageURL(user.avatar || 'img/avatar_default.jpg');
  document.getElementById('profile-summary-name').textContent = user.display_name ?? '';
  document.getElementById('profile-summary-email').textContent = user.email ?? '';
  document.getElementById('profile-summary-role').textContent = { user: 'Khách hàng', host: 'Chủ nhà', admin: 'Quản trị viên' }[user.role] ?? '';
  if (user.role === 'admin') hostApplicationSection.remove();
  if (user.role === 'host') {
    document.getElementById('host-apply-heading').textContent = 'Tài khoản Host';
    document.getElementById('host-apply-description').textContent = 'Bạn có thể theo dõi trạng thái đơn đăng ký Host tại đây.';
  }
  document.getElementById('delete-account-section').hidden = !['user', 'host'].includes(user.role);
}
preview.addEventListener('error', () => {
  if (!preview.src.endsWith('/img/placeholder.svg')) preview.src = 'img/placeholder.svg';
});
async function fillHostApplication() {
  if (!hostApplicationSection || !['user', 'host'].includes(user.role)) return;
  try {
    renderHostApplication(await getHostApplication());
  } catch (error) {
    if (error.status === 401) requireLogin();
    else if (error.status === 404) renderHostApplication(null);
    else {
      hostApplicationStatus.textContent = error.detail || 'Chưa tải được trạng thái đăng ký host.';
      hostApplicationStatus.hidden = false;
    }
  }
}

function renderHostApplication(application) {
  const statusMessages = {
    pending: 'Đơn đăng ký đang chờ quản trị viên xét duyệt.',
    approved: user.role === 'host'
      ? 'Đơn đã được duyệt. Tài khoản hiện đã có quyền Host.'
      : 'Đơn đã được duyệt. Đăng xuất rồi đăng nhập lại để cập nhật quyền Host.',
    rejected: `Đơn đăng ký bị từ chối.${application?.rejectReason ? ` Lý do: ${application.rejectReason}` : ''}`,
  };
  if (application) {
    hostApplicationStatus.textContent = statusMessages[application.status] || 'Không xác định được trạng thái đơn.';
    hostApplicationStatus.hidden = false;
    const data = application.application_data || {};
    for (const key of ['homestay_name', 'address', 'province', 'room_count', 'description', 'experience', 'phone']) {
      input(hostApplicationForm, key).value = data[key] ?? '';
    }
    input(hostApplicationForm, 'accept_terms').checked = data.accept_terms === true;
  } else {
    hostApplicationStatus.textContent = user.role === 'host' ? 'Tài khoản của bạn đã có quyền Host.' : '';
    hostApplicationStatus.hidden = user.role !== 'host';
  }
  hostApplyButton.hidden = !['user'].includes(user.role) || application?.status === 'pending' || application?.status === 'approved';
  hostApplyButton.textContent = application?.status === 'rejected' ? 'Nộp lại đơn' : 'Trở thành host';
  hostApplicationForm.hidden = true;
}

function openHostApplicationForm() {
  const phone = input(hostApplicationForm, 'phone');
  if (!phone.value) phone.value = input(profileForm, 'phone').value;
  hostApplicationSubmitError.textContent = '';
  clearFieldErrors(hostApplicationForm);
  hostApplyButton.hidden = true;
  hostApplicationForm.hidden = false;
  hostApplicationForm.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

hostApplyButton.addEventListener('click', openHostApplicationForm);
document.getElementById('host-apply-cancel').addEventListener('click', () => {
  hostApplicationForm.hidden = true;
  hostApplyButton.hidden = false;
});
hostApplicationForm.addEventListener('submit', async event => {
  event.preventDefault();
  if (!user || hostApplicationForm.querySelector('[type="submit"]').disabled) return;
  clearFieldErrors(hostApplicationForm);
  hostApplicationSubmitError.textContent = '';

  const fields = Object.fromEntries(
    ['homestay_name', 'address', 'province', 'room_count', 'description', 'experience', 'phone', 'accept_terms']
      .map(key => [key, input(hostApplicationForm, key)])
  );
  const text = key => fields[key].value.trim();
  let valid = true;
  const errors = {
    homestay_name: text('homestay_name').length >= 2 && text('homestay_name').length <= 160 ? '' : 'Tên homestay phải có từ 2 đến 160 ký tự.',
    address: text('address').length >= 5 && text('address').length <= 300 ? '' : 'Địa chỉ phải có từ 5 đến 300 ký tự.',
    province: text('province').length >= 2 && text('province').length <= 120 ? '' : 'Nhập tỉnh hoặc thành phố.',
    room_count: Number.isInteger(fields.room_count.valueAsNumber) && fields.room_count.valueAsNumber >= 1 && fields.room_count.valueAsNumber <= 100 ? '' : 'Số phòng phải từ 1 đến 100.',
    description: text('description').length >= 10 && text('description').length <= 1000 ? '' : 'Mô tả phải có từ 10 đến 1000 ký tự.',
    experience: text('experience').length <= 1000 ? '' : 'Thông tin kinh nghiệm không được vượt quá 1000 ký tự.',
    phone: /^(0|\+84)[35789][0-9]{8}$/.test(text('phone')) ? '' : 'Số điện thoại không hợp lệ.',
    accept_terms: fields.accept_terms.checked ? '' : 'Bạn cần đồng ý với điều khoản dành cho Host.',
  };
  for (const [key, message] of Object.entries(errors)) {
    if (message) { setFieldError(fields[key], message); valid = false; }
  }
  if (!valid) return;

  const submitButton = hostApplicationForm.querySelector('[type="submit"]');
  submitButton.disabled = true;
  submitButton.textContent = 'Đang gửi đơn...';
  try {
    const application_data = {
      homestay_name: text('homestay_name'),
      address: text('address'),
      province: text('province'),
      room_count: fields.room_count.valueAsNumber,
      description: text('description'),
      experience: text('experience'),
      phone: text('phone'),
      accept_terms: fields.accept_terms.checked,
    };
    renderHostApplication(await applyHost(application_data));
    toast('Đã gửi đơn đăng ký. Bạn có thể theo dõi trạng thái tại hồ sơ.');
  } catch (error) {
    if (error.status === 401) requireLogin();
    else hostApplicationSubmitError.textContent = error.detail || 'Không gửi được đơn đăng ký.';
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = 'Gửi đơn đăng ký';
  }
});

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
    avatar = undefined; preview.src = safeImageURL(user.avatar || 'img/avatar_default.jpg');
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
    avatar = undefined; fillProfile(); toast(ACCOUNT_API_MODE ? 'Đã lưu hồ sơ trên máy chủ.' : 'Đã lưu hồ sơ mock trên trình duyệt này.');
  } catch (err) {
    if (err.status === 401) { requireLogin(); return; }
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
    toast(ACCOUNT_API_MODE ? 'Đã đổi mật khẩu và thu hồi các phiên. Vui lòng đăng nhập lại.' : 'Đã đổi mật khẩu mock trên trình duyệt này.');
    if (ACCOUNT_API_MODE) location.href = accountHref('login.html');
  } catch (err) { toast(err.detail ?? 'Không đổi được mật khẩu.', 'error'); }
  finally { passwordForm.reset(); passwordButton.disabled = false; }
});

const deleteAccountButton = document.getElementById('delete-account');
const deleteAccountDialog = document.getElementById('delete-account-dialog');
const deleteAccountConfirm = deleteAccountDialog.querySelector('[data-confirm]');
const deleteAccountError = document.getElementById('delete-account-error');
deleteAccountButton.addEventListener('click', () => {
  deleteAccountError.textContent = '';
  deleteAccountError.hidden = true;
  deleteAccountDialog.showModal();
});
deleteAccountDialog.querySelector('[data-cancel]').addEventListener('click', () => deleteAccountDialog.close());
deleteAccountDialog.addEventListener('cancel', event => {
  if (deleteAccountButton.disabled) event.preventDefault();
});
deleteAccountDialog.addEventListener('click', event => {
  if (event.target === deleteAccountDialog && !deleteAccountButton.disabled) deleteAccountDialog.close();
});
deleteAccountConfirm.addEventListener('click', async () => {
  if (deleteAccountButton.disabled) return;
  deleteAccountButton.disabled = true;
  deleteAccountConfirm.disabled = true;
  try {
    await deleteAccount();
    deleteAccountDialog.close();
    toast('Tài khoản đã được xóa.');
    location.href = accountHref('login.html');
  } catch (error) {
    if (error.status === 401) { requireLogin(); return; }
    deleteAccountError.textContent = error.detail ?? 'Không thể xóa tài khoản.';
    deleteAccountError.hidden = false;
  } finally {
    deleteAccountButton.disabled = false;
    deleteAccountConfirm.disabled = false;
  }
});

if (!isLoggedIn()) requireLogin();
else {
  getProfile().then(async profile => {
    user = profile; fillProfile(); syncButton();
    await fillHostApplication();
    if (location.hash === '#become-host' && user.role === 'user' && !hostApplyButton.hidden)
      openHostApplicationForm();
    avatarInput.disabled = false; passwordButton.disabled = false;
  }).catch(err => { if (err.status === 401) requireLogin(); else toast(err.detail ?? 'Không tải được hồ sơ.', 'error'); });
}
