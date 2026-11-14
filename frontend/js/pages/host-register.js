
import { register, getProfile, applyHost, getHostApplication } from '../api.js';
import { saveSession, isLoggedIn, requireLogin } from '../auth.js';
import { ACCOUNT_API_MODE, accountHref } from '../config.js';
import {
  setFieldError,
  clearFieldErrors,
  toast
} from '../ui.js';

import '../components/site-header.js';
import '../components/site-footer.js';

const form = document.getElementById('host-register-form');

if (!form) {
  throw new Error('Không tìm thấy #host-register-form');
}
form.querySelector('[type="submit"]').disabled = false;
const existingAccount = ACCOUNT_API_MODE && isLoggedIn();
if (existingAccount) {
  form.querySelector('[type="submit"]').disabled = true;
  try {
    const current = await getProfile();
    if (current.role !== 'user') {
      form.hidden = true;
      const message = document.createElement('p'); message.textContent = 'Tài khoản hiện tại không cần đăng ký host mới.';
      form.after(message);
    } else {
      for (const key of ['display_name','email','phone']) form.elements.namedItem(key).value = current[key] || '';
      form.elements.namedItem('email').readOnly = true;
      for (const key of ['password','confirm']) {
        const field = form.elements.namedItem(key); field.required = false; field.closest('.field').hidden = true;
      }
      const currentApplication = await getHostApplication().catch(error => { if (error.status !== 404) throw error; return null; });
      const pending = currentApplication?.status === 'pending';
      form.querySelector('[type="submit"]').textContent = pending ? 'Đang chờ xét duyệt' : 'Gửi đơn đăng ký host';
      form.querySelector('[type="submit"]').disabled = pending;
    }
  } catch (error) { if (error.status === 401) requireLogin(); else toast(error.detail || 'Không tải được tài khoản.', 'error'); }
}

// ============================================================
// VALIDATE SỐ ĐIỆN THOẠI VIỆT NAM
// Chấp nhận:
// 0912345678
// +84912345678
// ============================================================

function isValidVietnamesePhone(phone) {
  return /^(0|\+84)(3|5|7|8|9)[0-9]{8}$/.test(phone);
}

// ============================================================
// HIỆN / ẨN MẬT KHẨU
// ============================================================

// Password visibility is handled once by ui.js.

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (form.querySelector('[type="submit"]').disabled) return;

  clearFieldErrors(form);

  let valid = true;

  // LẤY DỮ LIỆU
  const displayName = form.elements.namedItem('display_name').value.trim();
  const email = form.elements.namedItem('email').value.trim();
  const phone = form.elements.namedItem('phone').value.trim();
  const password = form.elements.namedItem('password').value;
  const confirmPassword = form.elements.namedItem('confirm').value;

  const nameInput = form.elements.namedItem('display_name');
  const emailInput = form.elements.namedItem('email');
  const phoneInput = form.elements.namedItem('phone');
  const passwordInput = form.elements.namedItem('password');
  const confirmInput = form.elements.namedItem('confirm');

  // VALIDATE HỌ VÀ TÊN
  if (displayName.length < 2) {
    setFieldError(
      nameInput,
      'Họ và tên phải có ít nhất 2 ký tự.'
    );

    valid = false;
  }

  // VALIDATE EMAIL
  if (!emailInput.validity.valid) {
    setFieldError(
      emailInput,
      'Email không hợp lệ.'
    );

    valid = false;
  }

  // VALIDATE SỐ ĐIỆN THOẠI
  if (!phone) {
    setFieldError(
      phoneInput,
      'Vui lòng nhập số điện thoại.'
    );

    valid = false;
  } else if (!isValidVietnamesePhone(phone)) {
    setFieldError(
      phoneInput,
      'Số điện thoại không hợp lệ. Ví dụ: 0912345678 hoặc +84912345678.'
    );

    valid = false;
  }

  // VALIDATE MẬT KHẨU
  if (!existingAccount && password.length < 8) {
    setFieldError(
      passwordInput,
      'Mật khẩu phải có ít nhất 8 ký tự.'
    );

    valid = false;
  }

  // XÁC NHẬN MẬT KHẨU
  if (!existingAccount && password !== confirmPassword) {
    setFieldError(
      confirmInput,
      'Hai mật khẩu không khớp.'
    );

    valid = false;
  }

  // CÓ LỖI → DỪNG
  if (!valid) return;

  // DISABLE BUTTON KHI ĐANG SUBMIT
  const submitButton = form.querySelector('button[type="submit"]');

  submitButton.disabled = true;
  submitButton.textContent = 'Đang đăng ký...';

  // GỌI AUTH API
  try {
    if (existingAccount) {
      await applyHost({ display_name: displayName, phone });
      location.href = accountHref('profile.html'); return;
    }
    const session = await register({
      display_name: displayName,
      email: email,
      password: password,
      phone: phone,
      role: 'host'
    });

    // LƯU SESSION
    saveSession(session);

    // THÔNG BÁO THÀNH CÔNG
    toast(ACCOUNT_API_MODE ? 'Đã tạo tài khoản khách hàng và gửi đơn chờ duyệt host.' : 'Tạo tài khoản Host thành công!');

    // CHUYỂN SANG HOST DASHBOARD
    location.href = accountHref(ACCOUNT_API_MODE ? 'profile.html' : 'host-dashboard.html');

  } catch (err) {
    if (err.status === 409) {
      setFieldError(
        emailInput,
        err.detail ?? 'Email đã được đăng ký.'
      );
    } else {
      toast(
        err.detail ?? 'Đăng ký Host thất bại.',
        'error'
      );
    }

    // CHO PHÉP SUBMIT LẠI
    submitButton.disabled = false;
    submitButton.textContent = 'Đăng ký Host';
  }
});
