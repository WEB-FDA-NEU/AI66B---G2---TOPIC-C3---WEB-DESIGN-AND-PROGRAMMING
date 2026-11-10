// ============================================================
//  Trang liên hệ: kiểm tra form và báo kết quả.
//  Tin nhắn được lưu qua sendContactMessage (api.js) và hiện ở trang admin-messages.html.
// ============================================================
import { sendContactMessage } from '../api.js';
import { toast, setFieldError, clearFieldErrors } from '../ui.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const form = document.getElementById('contact-form');

form.addEventListener('submit', async e => {
  e.preventDefault();
  clearFieldErrors(form);

  const { name, email, subject, message } = form.elements;
  let ok = true;
  if (name.value.trim().length < 2)    { setFieldError(name, 'Vui lòng nhập họ tên.'); ok = false; }
  if (!email.value.trim() || !email.validity.valid) { setFieldError(email, 'Email không hợp lệ.'); ok = false; }
  if (message.value.trim().length < 10) { setFieldError(message, 'Nội dung tối thiểu 10 ký tự.'); ok = false; }
  if (!ok) return;

  const btn = form.querySelector('button[type=submit]');
  btn.disabled = true;
  try {
    await sendContactMessage({
      name: name.value.trim(),
      email: email.value.trim(),
      subject: subject.value,
      message: message.value.trim(),
    });
    form.reset();
    toast('Đã gửi tin nhắn. Chúng tôi sẽ phản hồi sớm!');
  } catch (err) {
    toast(err.detail ?? 'Gửi thất bại, vui lòng thử lại.', 'error');
  } finally {
    btn.disabled = false;
  }
});
