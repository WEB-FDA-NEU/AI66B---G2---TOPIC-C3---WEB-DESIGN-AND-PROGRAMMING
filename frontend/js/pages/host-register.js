// ============================================================
// HOST REGISTRATION
// - Validate thông tin đăng ký
// - Validate số điện thoại
// - Dùng chung api.js + auth.js + ui.js của nhóm
// - Không viết fetch() trực tiếp
// ============================================================

import { register } from '../api.js';
import { saveSession } from '../auth.js';
import {
  setFieldError,
  clearFieldErrors,
  toast
} from '../ui.js';

import '../components/site-header.js';
import '../components/site-footer.js';


const form = document.getElementById('host-register-form');

if (!form) {
  throw new Error(
    'Không tìm thấy #host-register-form'
  );
}


// ============================================================
// VALIDATE SỐ ĐIỆN THOẠI VIỆT NAM
//
// Chấp nhận:
// 0912345678
// 0987654321
// 0321234567
// 0351234567
// 0771234567
// 0811234567
// 0911234567
//
// Có thể nhập:
// 0912345678
// +84912345678
// ============================================================

function isValidVietnamesePhone(phone) {
  return /^(0|\+84)(3|5|7|8|9)[0-9]{8}$/.test(phone);
}


// ============================================================
// SUBMIT FORM
// ============================================================

form.addEventListener('submit', async event => {

  event.preventDefault();

  // Xóa lỗi cũ
  clearFieldErrors(form);

  let valid = true;


  // ==========================================================
  // LẤY DỮ LIỆU
  // ==========================================================

  const displayName =
    form.display_name.value.trim();

  const email =
    form.email.value.trim();

  const phone =
    form.phone.value.trim();

  const password =
    form.password.value;

  const confirmPassword =
    form.confirm.value;


  // ==========================================================
  // VALIDATE HỌ VÀ TÊN
  // ==========================================================

  if (displayName.length < 2) {

    setFieldError(
      form.display_name,
      'Họ và tên phải có ít nhất 2 ký tự.'
    );

    valid = false;
  }


  // ==========================================================
  // VALIDATE EMAIL
  // ==========================================================

  if (!form.email.validity.valid) {

    setFieldError(
      form.email,
      'Email không hợp lệ.'
    );

    valid = false;
  }


  // ==========================================================
  // VALIDATE SỐ ĐIỆN THOẠI
  // ==========================================================

  if (!phone) {

    setFieldError(
      form.phone,
      'Vui lòng nhập số điện thoại.'
    );

    valid = false;

  } else if (!isValidVietnamesePhone(phone)) {

    setFieldError(
      form.phone,
      'Số điện thoại không hợp lệ. Ví dụ: 0912345678.'
    );

    valid = false;
  }


  // ==========================================================
// VALIDATE MẬT KHẨU
  // ==========================================================

  if (password.length < 8) {

    setFieldError(
      form.password,
      'Mật khẩu phải có ít nhất 8 ký tự.'
    );

    valid = false;
  }


  // ==========================================================
  // XÁC NHẬN MẬT KHẨU
  // ==========================================================

  if (password !== confirmPassword) {

    setFieldError(
      form.confirm,
      'Hai mật khẩu không khớp.'
    );

    valid = false;
  }


  // Có lỗi → dừng
  if (!valid) {
    return;
  }


  // ==========================================================
  // DISABLE BUTTON KHI ĐANG SUBMIT
  // ==========================================================

  const submitButton =
    form.querySelector('button[type="submit"]');

  submitButton.disabled = true;
  submitButton.textContent = 'Đang đăng ký...';


  // ==========================================================
  // GỌI AUTH API
  // ==========================================================

  try {

    const session = await register({

      display_name: displayName,

      email: email,

      password: password,

      phone: phone,

      role: 'host',

    });


    // ========================================================
    // LƯU SESSION
    // ========================================================

    saveSession(session);


    // ========================================================
    // THÔNG BÁO THÀNH CÔNG
    // ========================================================

    toast(
      'Tạo tài khoản Host thành công!'
    );


    // ========================================================
    // CHUYỂN SANG HOST DASHBOARD
    // ========================================================

    location.href =
      'host-dashboard.html';


  } catch (err) {

    // ========================================================
    // EMAIL ĐÃ TỒN TẠI
    // ========================================================

    if (err.status === 409) {

      setFieldError(
        form.email,
        err.detail ?? 'Email đã được đăng ký.'
      );


    } else {

      // ======================================================
      // LỖI KHÁC
      // ======================================================

      toast(
        err.detail ?? 'Đăng ký Host thất bại.',
        'error'
      );

    }


    // Cho phép submit lại
    submitButton.disabled = false;
    submitButton.textContent = 'Đăng ký Host';

  }

});