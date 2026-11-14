// ============================================================
//  Lưu token và cập nhật header cho đúng trạng thái đăng nhập.
//  Mock giữ localStorage cũ; token API nằm trong sessionStorage của tab.
//  Cả hai vẫn đọc được bởi JavaScript/XSS; không phải HttpOnly hoặc bảo mật tuyệt đối.
//  User cache chỉ phục vụ UX, GET profile/backend mới quyết định identity/role.
// ============================================================
import { ACCOUNT_API_MODE, API_SCOPE, accountHref, supportedApiRoute } from './config.js';
const TOKEN_KEY = ACCOUNT_API_MODE ? 'luxstay_api_access_token' : 'app_token';
const USER_KEY = ACCOUNT_API_MODE ? 'luxstay_api_user' : 'app_user';
const storage = ACCOUNT_API_MODE ? sessionStorage : localStorage;

export const getToken = () => storage.getItem(TOKEN_KEY);
export const getUser = () => {
  try {
    const user = JSON.parse(storage.getItem(USER_KEY) || 'null');
    return user && typeof user === 'object' && user.id != null ? user : null;
  } catch { return null; }
};
export const isLoggedIn = () => !!getToken() && !!getUser();

export function saveSession({ access_token, user }) {
  const fields = ACCOUNT_API_MODE ? ['id','display_name','role'] : ['id','display_name','email','phone','role','avatar','createdAt'];
  const safe = Object.fromEntries(fields.map(k => [k,user[k]]));
  storage.setItem(TOKEN_KEY, access_token);
  storage.setItem(USER_KEY, JSON.stringify(safe));
  document.querySelectorAll('[data-user-name]').forEach(el => { el.textContent = user.display_name ?? ''; });
}

export function clearSession() { storage.removeItem(TOKEN_KEY); storage.removeItem(USER_KEY); }
export function updateSessionUser(user) { saveSession({ access_token: getToken(), user }); }
let logoutPending;
export function logout() {
  if (logoutPending) return logoutPending;
  logoutPending = (async () => {
    if (ACCOUNT_API_MODE && getToken()) {
      const { revokeSession } = await import('./api.js');
      await revokeSession();
    }
    clearSession();
    location.href = accountHref(ACCOUNT_API_MODE ? 'login.html' : 'index.html');
  })().finally(() => { logoutPending = undefined; });
  return logoutPending;
}

/** Lưu trang hiện tại rồi chuyển sang Login — dùng cho "login branch" ở Mốc 1. */
export function requireLogin() {
  if (!/\/(login|register)\.html$/.test(location.pathname)) sessionStorage.setItem(ACCOUNT_API_MODE ? 'api_return_to' : 'app_return_to', location.pathname + location.search);
  location.href = accountHref('login.html');
}

/** Sau khi đăng nhập xong thì quay lại đúng chỗ người dùng đang đứng. */
export function returnAfterLogin() {
  const key = ACCOUNT_API_MODE ? 'api_return_to' : 'app_return_to';
  const raw = sessionStorage.getItem(key); sessionStorage.removeItem(key);
  const fallback = ACCOUNT_API_MODE ? 'profile.html' : 'index.html';
  let next = fallback;
  try {
    const url = new URL(raw || fallback, location.href);
    if (url.origin === location.origin && ['http:', 'https:'].includes(url.protocol) && !/\/(login|register)\.html$/.test(url.pathname) &&
      (!ACCOUNT_API_MODE || supportedApiRoute(url.pathname))) next = url.pathname + url.search;
  } catch { /* Reject external/malformed return targets. */ }
  location.href = accountHref(next);
}

if (ACCOUNT_API_MODE) {
  const wire = () => {
    const hint = document.createElement('p'); hint.className = 'field__hint'; hint.dataset.accountApiNotice = '';
    hint.textContent = API_SCOPE === 'accounts' ? 'Tài khoản đang dùng máy chủ thử nghiệm. Đặt phòng và quản trị chưa được bật ở chế độ này.' : 'Dữ liệu đang lấy từ máy chủ thử nghiệm.';
    document.querySelector('main')?.prepend(hint);
    document.querySelectorAll('a[href]').forEach(link => {
      if (link.getAttribute('href').startsWith('#')) return;
      const url = new URL(link.href, location.href);
      if (url.origin === location.origin && url.pathname.endsWith('.html')) link.href = accountHref(url.href);
    });
    document.querySelectorAll('.field__hint').forEach(el => {
      if (el.textContent.includes('Tài khoản mô phỏng chỉ lưu')) el.textContent = 'Thông tin tài khoản được lưu trên máy chủ. Yêu cầu làm host phải chờ quản trị viên xét duyệt.';
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', wire, { once: true }); else queueMicrotask(wire);
}
if (ACCOUNT_API_MODE) document.addEventListener('click', event => {
  const link = event.target.closest?.('a[href]');
  if (!link || link.getAttribute('href').startsWith('#')) return;
  const url = new URL(link.href, location.href);
  if (url.origin === location.origin && url.pathname.endsWith('.html')) link.href = accountHref(url.href);
}, true);

/** Đổi phần bên phải của header theo trạng thái đăng nhập. */
export function initHeader() {
  if (ACCOUNT_API_MODE) document.querySelectorAll('site-header a[href]').forEach(link => {
    const url = new URL(link.href, location.href);
    if (url.origin === location.origin && url.pathname.endsWith('.html')) link.href = accountHref(url.href);
  });
  const guest = document.querySelector('[data-auth="guest"]');
  const user  = document.querySelector('[data-auth="user"]');
  if (!guest || !user) return;              // trang này không có header → bỏ qua

  const logged = isLoggedIn();
  guest.hidden = logged;
  user.hidden  = !logged;

  const nameEl = document.querySelector('[data-user-name]');
  if (nameEl && logged) nameEl.textContent = getUser()?.display_name ?? '';

  document.querySelector('[data-action="logout"]')?.addEventListener('click', e => {
    e.preventDefault();
    logout().catch(async error => {
      const { toast } = await import('./ui.js');
      toast(error.detail ?? 'Không thu hồi được phiên. Vui lòng thử lại.', 'error');
    });
  });
}
