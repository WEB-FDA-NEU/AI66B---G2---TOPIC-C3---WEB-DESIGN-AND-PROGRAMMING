// ============================================================
//  Giữ mock mặc định để bảo toàn các luồng chưa tích hợp.
//  Phase 8 chuyển từng nhóm qua cờ route ?accounts=api.
//  Chưa được đổi USE_MOCK=false cho toàn ứng dụng trước gate tích hợp.
// ============================================================

export const USE_MOCK = true;

// Same-origin Uvicorn/staging by default; standard Live Server ports target the same loopback host.
// A deployment may supply a non-secret global LUXSTAY_CONFIG.apiBase before module loading.
const loopback = ['localhost', '127.0.0.1'].includes(location.hostname);
const configuredBase = globalThis.LUXSTAY_CONFIG?.apiBase;
export const API_BASE = new URL(configuredBase || (loopback && ['5500', '5501'].includes(location.port)
  ? `http://${location.hostname}:8000/api` : '/api'), location.origin).href.replace(/\/$/, '');
if (!['http:', 'https:'].includes(new URL(API_BASE).protocol) || new URL(API_BASE).username || new URL(API_BASE).password) throw Error('Invalid API origin');
export const API_SCOPE = new URLSearchParams(location.search).get('mode') === 'api' ? 'customer'
  : new URLSearchParams(location.search).get('accounts') === 'api' ? 'accounts' : 'mock';
export const ACCOUNT_API_MODE = API_SCOPE !== 'mock';
export const apiModuleEnabled = module => module === 'accounts' || (API_SCOPE === 'customer' && ['catalog','bookings','host-bookings','host-properties','host-rooms','host-dashboard','admin'].includes(module));
const accountRoutes = new Set(['login.html', 'register.html', 'profile.html', 'host-register.html']);
const customerRoutes = new Set([...accountRoutes, 'index.html','search.html','shop.html','detail.html','booking-page.html','booking-list.html','booking-detail.html','booking-confirmed.html','host-bookings.html','host-homestays.html','host-homestay-form.html','host-rooms.html','host-dashboard.html','admin.html','404.html']);
export const supportedApiRoute = path => (API_SCOPE === 'customer' ? customerRoutes : accountRoutes).has(path.split('/').pop() || 'index.html');
export const accountHref = path => {
  const url = new URL(path, location.href);
  if (url.origin !== location.origin || !['http:', 'https:'].includes(url.protocol)) return 'profile.html?accounts=api';
  if (API_SCOPE === 'customer') { url.searchParams.set('mode', 'api'); url.searchParams.delete('accounts'); }
  else if (ACCOUNT_API_MODE) url.searchParams.set('accounts', 'api');
  return url.pathname + url.search + url.hash;
};
export function safeImageURL(value) {
  if (typeof value !== 'string' || /[\u0000-\u001f\u007f]/.test(value)) return 'img/placeholder.svg';
  if (/^data:image\/(png|jpeg|webp);base64,[A-Za-z0-9+/=]+$/.test(value) && value.length <= 500000) return value;
  try {
    const base = value.startsWith('/uploads/') ? new URL(API_BASE).origin : location.href;
    const url = new URL(value, base);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return 'img/placeholder.svg';
    return url.href;
  } catch { return 'img/placeholder.svg'; }
}
// Unsupported API routes fail closed instead of falling back to local business records.
if (ACCOUNT_API_MODE && !supportedApiRoute(location.pathname)) {
  if (document.readyState === 'loading') await new Promise(resolve => document.addEventListener('DOMContentLoaded', resolve, { once: true }));
  const box = document.createElement('section'); box.className = 'empty';
  const message = document.createElement('p'); message.textContent = 'Chức năng này chưa được kết nối máy chủ trong đợt tích hợp tài khoản.';
  const back = document.createElement('a'); back.href = 'profile.html?accounts=api'; back.className = 'btn btn--primary'; back.textContent = 'Về hồ sơ';
  box.append(message, back); document.querySelector('main')?.replaceChildren(box);
  await new Promise(() => {});
}

export const MOCK_BASE = 'mock';

// Vì sao đường dẫn TƯƠNG ĐỐI ('mock', 'api') chứ không phải tuyệt đối ('/mock'):
// đường dẫn bắt đầu bằng "/" tính từ GỐC máy chủ. Nếu ai đó chạy server ở thư mục
// cha rồi mở http://localhost:5500/frontend/shop.html thì "/css/..." trỏ sai chỗ
// và trang mất sạch CSS. Đường dẫn tương đối tính từ chính trang đang mở nên
// chạy đúng ở mọi cách đặt thư mục gốc.

export const PAGE_SIZE = 20;
