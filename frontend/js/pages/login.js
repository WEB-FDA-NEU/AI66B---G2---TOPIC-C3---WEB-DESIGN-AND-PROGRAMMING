import { login, ApiError } from '../api.js';
import { saveSession, returnAfterLogin } from '../auth.js';
import { setFieldError, clearFieldErrors, toast } from '../ui.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const form = document.getElementById('login-form');

// Tài khoản demo: bấm một dòng → tự điền email + mật khẩu chung (xem mock/users.json)
document.querySelectorAll('[data-demo-email]').forEach(b => b.addEventListener('click', () => {
  form.email.value = b.dataset.demoEmail;
  form.password.value = '12345678';
  clearFieldErrors(form);
}));

form.addEventListener('submit', async e => {
  e.preventDefault();
  clearFieldErrors(form);

  // 1. Validate phía trình duyệt — để phản hồi nhanh
  let ok = true;
  if (!form.email.validity.valid)      { setFieldError(form.email, 'Email không hợp lệ.'); ok = false; }
  if (form.password.value.length < 8)  { setFieldError(form.password, 'Mật khẩu tối thiểu 8 ký tự.'); ok = false; }
  if (!ok) return;

  // 2. Server mới là thẩm quyền — validate lần hai ở backend
  const btn = form.querySelector('button[type=submit]');
  btn.disabled = true;
  try {
    const session = await login(form.email.value, form.password.value);
    saveSession(session);
    returnAfterLogin();                       // quay lại trang trước khi bị chặn
  } catch (err) {
    if (err instanceof ApiError && err.status === 401)
      setFieldError(form.password, err.detail);
    else
      toast(err.detail ?? 'Đăng nhập thất bại.', 'error');
    btn.disabled = false;
  }
});