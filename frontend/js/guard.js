// ============================================================
//  Chặn truy cập theo role. Dùng cho trang quản trị và các trang của host.
//
//  Cách dùng (mỗi trang cần chặn làm đúng 2 việc):
//    1) HTML:  <body data-require-role="admin">     (hoặc "host")
//    2) JS của trang: thêm  import '../guard.js';  SAU các dòng import site-header/site-footer
//       (trong admin.html thì  import './js/guard.js';)
//
//  Chưa đăng nhập      → chuyển sang login.html, đăng nhập xong quay lại đúng trang này.
//  Sai role            → thay nội dung trang bằng thông báo "không có quyền".
//  Bị chặn thì mã còn lại của trang KHÔNG chạy (top-level await không bao giờ xong).
//
//  LƯU Ý: đây chỉ là lớp giao diện, người dùng vẫn có thể sửa localStorage. Quyền thật phải kiểm tra
//  ở backend (xem deps.py: get_admin; cần thêm get_host tương tự khi làm router của host).
// ============================================================
import { getUser, isLoggedIn, requireLogin } from './auth.js';

const required = document.body.dataset.requireRole;
const LABEL = { admin: 'quản trị viên', host: 'host' };

function showDenied(user) {
  const box = document.createElement('div');
  box.className = 'empty';
  const title = Object.assign(document.createElement('p'), {
    className: 'empty__title', textContent: `Trang này chỉ dành cho ${LABEL[required] ?? required}.` });
  const hint = Object.assign(document.createElement('p'), {
    className: 'empty__hint', textContent: `Bạn đang đăng nhập với tài khoản ${user.display_name ?? ''}.` });
  const actions = Object.assign(document.createElement('div'), { className: 'empty__actions' });
  actions.append(Object.assign(document.createElement('a'), {
    className: 'btn btn--primary', href: 'index.html', textContent: 'Về trang chủ' }));
  if (required === 'host' && user.role === 'user') {
    actions.append(Object.assign(document.createElement('a'), {
      className: 'btn btn--outline', href: 'host-register.html', textContent: 'Đăng ký làm host' }));
  }
  box.append(title, hint, actions);
  document.querySelector('main')?.replaceChildren(box);
}

if (required) {
  const user = getUser();
  if (!isLoggedIn()) {
    requireLogin();
    await new Promise(() => {});
  } else if (user.role !== required) {
    showDenied(user);
    document.body.dataset.guardOk = '';
    await new Promise(() => {});
  }
  document.body.dataset.guardOk = '';   // được phép: hiện nội dung
}