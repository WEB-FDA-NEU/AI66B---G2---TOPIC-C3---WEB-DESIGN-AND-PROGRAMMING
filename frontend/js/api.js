// ============================================================
//  Tầng DUY NHẤT được phép gọi mạng.
//  Không file nào khác được viết fetch().
//
//  CHIA VÙNG THEO NGƯỜI để tránh conflict Git — mỗi người chỉ
//  thêm hàm vào vùng của mình.
// ============================================================
import { USE_MOCK, API_BASE, MOCK_BASE, ACCOUNT_API_MODE, apiModuleEnabled, safeImageURL } from './config.js';
import { getToken, getUser, saveSession, clearSession, updateSessionUser } from './auth.js';

// ---- Phiên bản dữ liệu mock ----
// Dữ liệu mock được copy vào localStorage lần đầu đọc, nên khi ai đó sửa mock/*.json mà máy các bạn
// vẫn giữ bản cũ thì sẽ thấy dữ liệu "không đổi". TĂNG số này mỗi khi sửa mock/*.json:
// lần mở trang kế tiếp, mọi máy tự xóa cache mock cũ (không đụng tới phiên đăng nhập).
const MOCK_DATA_VERSION = '2026-11-13-b';
if (USE_MOCK && !ACCOUNT_API_MODE && localStorage.getItem('mock_version') !== MOCK_DATA_VERSION) {
  ['customerBookings', 'homestays', 'rooms', 'bookings'].forEach(k => localStorage.removeItem(k));
  Object.keys(localStorage).filter(k => k.startsWith('reviews_')).forEach(k => localStorage.removeItem(k));
  localStorage.setItem('mock_version', MOCK_DATA_VERSION);
}

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || 'Đã có lỗi xảy ra.');
    this.status = status;
    this.detail = detail;
  }
}

async function request(url, options = {}) {
  const target = new URL(url, location.href), base = new URL(API_BASE);
  const backend = target.origin === base.origin && target.pathname.startsWith(base.pathname + '/');
  const { timeoutMs = 15000, ...init } = options;
  const headers = new Headers(init.headers || {});
  const token = getToken();
  if (backend && token && token !== 'mock-token') headers.set('Authorization', `Bearer ${token}`);
  else headers.delete('Authorization');
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
    init.body = JSON.stringify(init.body);
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(target.href, { ...init, headers, signal: controller.signal, credentials: 'omit' });
    if (res.status === 401 && backend && !/\/auth\/(login|register)$/.test(target.pathname)) clearSession();
    if (res.status === 204) return null;
    let data = null;
    try { data = await res.json(); } catch (error) { if (controller.signal.aborted) throw error; }
    if (!res.ok) {
      const error = new ApiError(res.status, normalizeDetail(data?.detail));
      error.code = data?.code; error.errors = data?.errors; error.retryAfter = res.headers.get('Retry-After');
      throw error;
    }
    return data;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) throw new ApiError(408, 'Yêu cầu quá thời gian chờ. Chưa xác định kết quả; không gửi lại thao tác đặt phòng bằng key mới.');
    throw new ApiError(0, 'Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.');
  } finally { clearTimeout(timer); }
}

function blockUnintegratedBusiness(module = 'unavailable') {
  if (ACCOUNT_API_MODE && !apiModuleEnabled(module)) throw new ApiError(503, 'Nhóm nghiệp vụ này chưa được kết nối máy chủ. Không ghi dữ liệu mock trong chế độ tài khoản API.');
}

const mediaItem = item => ({ ...item, cover_url: safeImageURL(item.cover_url), images: (item.images || []).map(safeImageURL),
  roomTypes: (item.roomTypes || []).map(r => ({ ...r, image: safeImageURL(r.image), images: (r.images || []).map(safeImageURL) })) });
export function getAvailability(id, stay) {
  blockUnintegratedBusiness('catalog');
  return request(`${API_BASE}/items/${encodeURIComponent(id)}/availability?${new URLSearchParams(stay)}`);
}
export function getQuote(payload) {
  blockUnintegratedBusiness('catalog');
  return request(`${API_BASE}/bookings/quote`, { method: 'POST', body: payload });
}
export function getPayment(id) {
  blockUnintegratedBusiness('bookings');
  return request(`${API_BASE}/me/bookings/${encodeURIComponent(id)}/payments`).then(rows => rows[0] || null);
}

export async function revokeSession() {
  try { await request(`${API_BASE}/auth/logout`, { method: 'POST' }); }
  catch (error) { if (error.status !== 401) throw error; }
}
export function getHostApplication() {
  if (!ACCOUNT_API_MODE) throw new ApiError(400, 'Chức năng này yêu cầu chế độ tài khoản API.');
  return request(`${API_BASE}/me/host-application`);
}
export function applyHost(application_data = {}) {
  if (!ACCOUNT_API_MODE) throw new ApiError(400, 'Chức năng này yêu cầu chế độ tài khoản API.');
  return request(`${API_BASE}/host/apply`, { method: 'POST', body: { application_data } });
}

/** FastAPI trả 422 dạng MẢNG, các mã khác trả CHUỖI.
 *  Không xử lý chỗ này thì người dùng thấy "[object Object]". */
function normalizeDetail(detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map(e => `${e.loc?.at(-1) ?? ''}: ${e.msg}`).join('\n');
  return null;
}

// ══════════ NGƯỜI 1 — danh sách & chi tiết ══════════
// TODO: đổi getItems/getItem thành tên hợp đề tài
//       (getListings / getConcerts / getHomestays / getRecipes …)

export function getItems(params = {}) {
  blockUnintegratedBusiness('catalog');
  if (USE_MOCK && !ACCOUNT_API_MODE) return request(`${MOCK_BASE}/items.json`).then(d => filterMock(d, params));
  // Một số bộ lọc (room_type, amenity) có thể là MẢNG — mỗi giá trị cần 1 cặp
  // key=value riêng trên querystring, nên không thể đưa thẳng cho URLSearchParams(object).
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v == null || v === '') continue;
    if (Array.isArray(v)) v.forEach(val => val !== '' && qs.append(k, val));
    else qs.set(k, v);
  }
  return request(`${API_BASE}/items?${qs}`).then(data => ({...data, items:data.items.map(mediaItem)}));
}

export async function getItem(id) {
  blockUnintegratedBusiness('catalog');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const data = await request(`${MOCK_BASE}/items.json`);

    const item = data.items.find(
      homestay => String(homestay.id) === String(id)
    );

    if (!item) {
      throw new ApiError(
        404,
        'Không tìm thấy homestay.'
      );
    }

    return item;
  }

  return request(`${API_BASE}/items/${encodeURIComponent(id)}`).then(mediaItem);
}

// ---------- Đánh giá (reviews) của trang chi tiết ----------
// Mock: đọc/ghi vào localStorage, seed lần đầu từ mảng "reviews" có sẵn trong mock/item-<id>.json.
const reviewsKey = id => `reviews_${id}`;

export async function getReviews(itemId, params = {}) {
  blockUnintegratedBusiness('catalog');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const cached = localStorage.getItem(reviewsKey(itemId));
    if (cached) return JSON.parse(cached);
    const item = await getItem(itemId);
    const seed = item.reviews ?? [];
    localStorage.setItem(reviewsKey(itemId), JSON.stringify(seed));
    return seed;
  }
  return request(`${API_BASE}/items/${encodeURIComponent(itemId)}/reviews?${new URLSearchParams({page:1,page_size:20,...params})}`);
}

export async function addReview(itemId, review) {
  blockUnintegratedBusiness('catalog');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const list = await getReviews(itemId);
    const entry = { id: `rv${Date.now()}`, created_at: new Date().toISOString(), ...review };
    list.unshift(entry);
    localStorage.setItem(reviewsKey(itemId), JSON.stringify(list));
    return entry;
  }
  return request(`${API_BASE}/items/${itemId}/reviews`, { method: 'POST', body: review });
}

// ══════════ NGƯỜI 2 — tài khoản ══════════
// Chỉ mô phỏng trên thiết bị này. Người dùng có thể sửa localStorage để giả phiên/quyền.
// Chỉ lưu hồ sơ + PBKDF2 verifier có salt; không lưu mật khẩu thô hay verifier vào app_user.
const MOCK_USERS_KEY = 'luxstay_mock_users_v1';
const PASSWORD_ITERATIONS = 600000;
const publicUser = u => Object.fromEntries(
  ['id', 'display_name', 'email', 'phone', 'role', 'avatar', 'createdAt'].map(k => [k, u[k]])
);
const mockSession = user => ({ access_token: 'mock-token', token_type: 'bearer', user: publicUser(user) });
const normalizeEmail = email => String(email ?? '').trim().toLowerCase();

function writeMockUsers(users) {
  try { localStorage.setItem(MOCK_USERS_KEY, JSON.stringify(users)); }
  catch { throw new ApiError(0, 'Không lưu được tài khoản mock. Bộ nhớ trình duyệt có thể đã đầy hoặc bị chặn.'); }
}

async function loadMockUsers() {
  const cached = localStorage.getItem(MOCK_USERS_KEY);
  if (cached !== null) {
    try {
      const users = JSON.parse(cached);
      if (!Array.isArray(users) || users.some(u => !u || !u.email || !u.credential)) throw new Error();
      return users;
    } catch { throw new ApiError(0, 'Dữ liệu tài khoản mock bị hỏng. Hãy sao lưu rồi xóa riêng luxstay_mock_users_v1 để khởi tạo lại.'); }
  }
  const data = await request(`${MOCK_BASE}/users.json`);
  // Tab khác có thể đã khởi tạo trong khi chờ tải JSON.
  if (localStorage.getItem(MOCK_USERS_KEY) !== null) return loadMockUsers();
  const users = data.users.map(u => ({ ...publicUser(u), credential: u.credential }));
  writeMockUsers(users);
  return users;
}

function validateProfile(data) {
  const display_name = String(data.display_name ?? '').trim();
  const email = normalizeEmail(data.email);
  const phone = String(data.phone ?? '').trim();
  if (display_name.length < 2 || display_name.length > 80) throw new ApiError(400, 'Họ tên phải có từ 2 đến 80 ký tự.');
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new ApiError(400, 'Email không hợp lệ.');
  if (phone && !/^(0|\+84)[35789][0-9]{8}$/.test(phone)) throw new ApiError(400, 'Số điện thoại không hợp lệ.');
  return { display_name, email, phone };
}

function validatePassword(password) {
  if (typeof password !== 'string' || password.length < 8 || password.length > 128)
    throw new ApiError(400, 'Mật khẩu phải có từ 8 đến 128 ký tự.');
}

async function derivePassword(password, salt) {
  if (!globalThis.crypto?.subtle) throw new ApiError(0, 'Đổi/kiểm tra mật khẩu mock cần HTTPS hoặc localhost và trình duyệt hỗ trợ Web Crypto.');
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(password), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256',
    salt: Uint8Array.from(salt.match(/../g), x => parseInt(x, 16)), iterations: PASSWORD_ITERATIONS }, key, 256);
  return Array.from(new Uint8Array(bits), x => x.toString(16).padStart(2, '0')).join('');
}

async function makeCredential(password) {
  validatePassword(password);
  if (!globalThis.crypto?.subtle) throw new ApiError(0, 'Tài khoản mock cần HTTPS hoặc localhost và Web Crypto.');
  const salt = Array.from(crypto.getRandomValues(new Uint8Array(16)), x => x.toString(16).padStart(2, '0')).join('');
  return { algorithm: 'PBKDF2-SHA256', iterations: PASSWORD_ITERATIONS, salt, hash: await derivePassword(password, salt) };
}

async function verifyCredential(password, c) {
  if (!c || c.algorithm !== 'PBKDF2-SHA256' || c.iterations !== PASSWORD_ITERATIONS
      || !/^[a-f0-9]{32}$/.test(c.salt) || !/^[a-f0-9]{64}$/.test(c.hash))
    throw new ApiError(0, 'Dữ liệu mật khẩu mock không hợp lệ.');
  return await derivePassword(password, c.salt) === c.hash;
}

function currentMockUser(users) {
  const me = getToken() === 'mock-token' && getUser();
  const found = me && users.find(u => String(u.id) === String(me.id));
  if (!found) throw new ApiError(401, 'Bạn cần đăng nhập lại bằng tài khoản mock.');
  return found;
}

export async function login(email, password) {
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const users = await loadMockUsers();
    const found = users.find(u => normalizeEmail(u.email) === normalizeEmail(email));
    validatePassword(password);
    if (!found || !(await verifyCredential(password, found.credential)))
      throw new ApiError(401, 'Email hoặc mật khẩu không đúng.');
    return mockSession(found);
  }
  return request(`${API_BASE}/auth/login`, { method: 'POST', body: { email, password } });
}

export async function register(payload) {
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const profile = validateProfile(payload);
    const credential = await makeCredential(payload.password);
    const users = await loadMockUsers();
    const email = profile.email;
    if (users.some(u => u.email === email))
      throw new ApiError(409, 'Email đã được đăng ký.');
    const user = {
      id: Math.max(0, ...users.map(u => Number(u.id) || 0)) + 1,
      ...profile,
      role: payload.role === 'host' ? 'host' : 'user',
      avatar: 'img/placeholder.svg',
      createdAt: new Date().toISOString(),
      credential,
    };
    users.push(user);
    writeMockUsers(users);
    return mockSession(user);
  }
  return request(`${API_BASE}/auth/register`, { method: 'POST', body: payload });
}

export async function getProfile() {
  if (ACCOUNT_API_MODE || !USE_MOCK) {
    const user = await request(`${API_BASE}/me/profile`);
    updateSessionUser(user); return user;
  }
  const user = currentMockUser(await loadMockUsers());
  saveSession(mockSession(user));
  return publicUser(user);
}

export async function updateProfile(payload) {
  if (ACCOUNT_API_MODE || !USE_MOCK) {
    const user = await request(`${API_BASE}/me/profile`, { method: 'PATCH', body: payload });
    updateSessionUser(user); return user;
  }
  const profile = validateProfile(payload);
  const users = await loadMockUsers();
  const user = currentMockUser(users);
  if (users.some(u => u.id !== user.id && normalizeEmail(u.email) === profile.email))
    throw new ApiError(409, 'Email đã được đăng ký.');
  if (payload.avatar !== undefined && !/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/=]+$/.test(payload.avatar))
    throw new ApiError(400, 'Ảnh đại diện không hợp lệ.');
  if (payload.avatar?.length > 500000) throw new ApiError(400, 'Ảnh đại diện quá lớn để lưu mock.');
  Object.assign(user, profile, payload.avatar === undefined ? {} : { avatar: payload.avatar });
  writeMockUsers(users);
  saveSession(mockSession(user));
  return publicUser(user);
}

export async function changePassword(currentPassword, newPassword) {
  if (ACCOUNT_API_MODE || !USE_MOCK) {
    await request(`${API_BASE}/me/password`, { method: 'POST', body: { current_password: currentPassword, new_password: newPassword } });
    clearSession(); return;
  }
  validatePassword(newPassword);
  const user = currentMockUser(await loadMockUsers());
  if (!(await verifyCredential(currentPassword, user.credential))) throw new ApiError(400, 'Mật khẩu hiện tại không đúng.');
  if (currentPassword === newPassword) throw new ApiError(400, 'Mật khẩu mới phải khác mật khẩu hiện tại.');
  const credential = await makeCredential(newPassword);
  // Đọc lại sau crypto để giữ các thay đổi hồ sơ phát sinh trong lúc chờ.
  const users = await loadMockUsers();
  const latest = currentMockUser(users);
  if (latest.id !== user.id || latest.credential.hash !== user.credential.hash)
    throw new ApiError(409, 'Tài khoản đã thay đổi ở tab khác. Vui lòng thử lại.');
  latest.credential = credential;
  writeMockUsers(users);
}

// ══════════ NGƯỜI 3 — TODO: thêm vùng của em ở đây ══════════

export async function getBookings(params = {}) {
  blockUnintegratedBusiness('bookings');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const list = await readTable('customerBookings', 'bookings.json');
    const me = getUser();
    return me ? list.filter(b => String(b.userId) === String(me.id)) : list;
  }
  return request(`${API_BASE}/me/bookings?${new URLSearchParams(params)}`);
}

export async function getBooking(id) {
  blockUnintegratedBusiness('bookings');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const b = (await getBookings()).find(x => String(x.id) === String(id));
    if (!b) throw new ApiError(404, 'Không tìm thấy đặt phòng này.');
    return b;
  }
  return request(`${API_BASE}/me/bookings/${id}`);
}

export async function createBooking(payload, key) {
  blockUnintegratedBusiness('bookings');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const me = getUser();
    if (!me) throw new ApiError(401, 'Bạn cần đăng nhập để đặt phòng.');
    const list = await readTable('customerBookings', 'bookings.json');
    const id = list.reduce((m, b) => Math.max(m, Number(b.id) || 0), 0) + 1;
    const booking = {
      id, userId: me.id, status: 'pending', createdAt: new Date().toISOString(),
      code: 'BK' + String(id).padStart(6, '0'),   // cùng định dạng mã với booking-detail
      ...payload,
    };
    list.push(booking);
    writeTable('customerBookings', list);
    return booking;
  }
  if (!key) throw new ApiError(400, 'Stable Idempotency-Key required');
  return request(`${API_BASE}/me/bookings`, { method: 'POST', body: payload, headers:{'Idempotency-Key':key} });
}

export async function cancelBooking(id) {
  blockUnintegratedBusiness('bookings');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const list = await readTable('customerBookings', 'bookings.json');
    const idx = list.findIndex(b => String(b.id) === String(id));
    if (idx === -1) throw new ApiError(404, 'Không tìm thấy booking.');
    list[idx].status = 'cancelled';
    writeTable('customerBookings', list);
    return list[idx];
  }
  return request(`${API_BASE}/me/bookings/${id}/cancel`, { method: 'POST' });
}

// ══════════ NGƯỜI 4 — quản lý của host: homestay, phòng, đặt phòng ══════════
// TODO: khi có đăng nhập thật cho role host, lấy HOST_ID từ getUser().id
const HOST_ID = 'host001';
const BOOKING_STATUSES = ['pending', 'confirmed', 'checked_in', 'completed', 'cancelled', 'rejected'];

/** Đọc "bảng" mock có thể sửa được: lần đầu load từ file JSON trong mock/,
 *  các lần sau đọc/ghi vào localStorage (giả lập backend cho tới khi nối API thật). */
async function readTable(key, file) {
  const cached = localStorage.getItem(key);
  if (cached) return JSON.parse(cached);
  const seed = await request(`${MOCK_BASE}/${file}`);
  const list = seed[key] ?? seed;
  localStorage.setItem(key, JSON.stringify(list));
  return list;
}
function writeTable(key, list) { localStorage.setItem(key, JSON.stringify(list)); }
const newId = prefix => `${prefix}${Date.now()}${Math.floor(Math.random() * 100)}`;

// ---------- Homestay ----------
export async function getHostHomestays(params = {}) {
  blockUnintegratedBusiness('host-properties');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const list = await readTable('homestays', 'host-homestays.json');
    return list.filter(h => h.hostId === HOST_ID && h.status !== 'deleted');
  }
  return request(`${API_BASE}/host/homestays?${new URLSearchParams(params)}`);
}

export async function getHostHomestay(id) {
  blockUnintegratedBusiness('host-properties');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const list = await readTable('homestays', 'host-homestays.json');
    const found = list.find(h => h.id === id);
    if (!found) throw new ApiError(404, 'Không tìm thấy homestay.');
    return found;
  }
  return request(`${API_BASE}/host/homestays/${id}`);
}

/** Tạo mới (không có id) hoặc cập nhật (có id). */
export async function saveHostHomestay(data) {
  blockUnintegratedBusiness('host-properties');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const list = await readTable('homestays', 'host-homestays.json');
    if (data.id) {
      const i = list.findIndex(h => h.id === data.id);
      if (i === -1) throw new ApiError(404, 'Không tìm thấy homestay.');
      list[i] = { ...list[i], ...data };
    } else {
      data.id = newId('hs');
      data.hostId = HOST_ID;
      data.status = 'active';
      data.createdAt = new Date().toISOString();
      list.push(data);
    }
    writeTable('homestays', list);
    return data;
  }
  return data.id
    ? request(`${API_BASE}/host/homestays/${data.id}`, { method: 'PUT', body: data })
    : request(`${API_BASE}/host/homestays`, { method: 'POST', body: data });
}

/** Xóa mềm: chỉ đổi status, không xóa khỏi mảng (giữ lịch sử booking liên kết). */
export async function deleteHostHomestay(id) {
  blockUnintegratedBusiness('host-properties');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const list = await readTable('homestays', 'host-homestays.json');
    const i = list.findIndex(h => h.id === id);
    if (i === -1) throw new ApiError(404, 'Không tìm thấy homestay.');
    list[i].status = 'deleted';
    writeTable('homestays', list);
    return null;
  }
  return request(`${API_BASE}/host/homestays/${id}`, { method: 'DELETE' });
}

// ---------- Phòng ----------
export async function getHostRooms(homestayId, params = {}) {
  blockUnintegratedBusiness('host-rooms');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const list = await readTable('rooms', 'host-rooms.json');
    return homestayId ? list.filter(r => r.homestayId === homestayId) : list;
  }
  return request(`${API_BASE}/host/rooms?${new URLSearchParams({ ...params, ...(homestayId ? { homestay_id: homestayId } : {}) })}`);
}

export async function getHostRoom(id) {
  blockUnintegratedBusiness('host-rooms');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const list = await readTable('rooms', 'host-rooms.json');
    const found = list.find(r => r.id === id);
    if (!found) throw new ApiError(404, 'Không tìm thấy phòng.');
    return found;
  }
  return request(`${API_BASE}/host/rooms/${id}`);
}

export async function saveHostRoom(data) {
  blockUnintegratedBusiness('host-rooms');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const list = await readTable('rooms', 'host-rooms.json');
    if (data.id) {
      const i = list.findIndex(r => r.id === data.id);
      if (i === -1) throw new ApiError(404, 'Không tìm thấy phòng.');
      list[i] = { ...list[i], ...data };
    } else {
      data.id = newId('rm');
      data.blockedDates = data.blockedDates ?? [];
      list.push(data);
    }
    writeTable('rooms', list);
    return data;
  }
  const { blockedDates: _legacyDates, ...payload } = data;
  return data.id
    ? request(`${API_BASE}/host/rooms/${data.id}`, { method: 'PUT', body: payload })
    : request(`${API_BASE}/host/rooms`, { method: 'POST', body: payload });
}

export async function deleteHostRoom(id) {
  blockUnintegratedBusiness('host-rooms');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const list = await readTable('rooms', 'host-rooms.json');
    const next = list.filter(r => r.id !== id);
    writeTable('rooms', next);
    return null;
  }
  return request(`${API_BASE}/host/rooms/${id}`, { method: 'DELETE' });
}

// ---------- Đặt phòng (duyệt / từ chối) ----------
export async function getHostBookings(params = {}) {
  blockUnintegratedBusiness('host-bookings');
  if (USE_MOCK && !ACCOUNT_API_MODE) return readTable('bookings', 'host-bookings.json');
  return request(`${API_BASE}/host/bookings?${new URLSearchParams(params)}`);
}

/** reason bắt buộc khi status = 'rejected' — xem docs/api-contract.md */
export async function updateBookingStatus(id, status, reason = '') {
  blockUnintegratedBusiness('host-bookings');
  if (!BOOKING_STATUSES.includes(status)) throw new ApiError(400, 'Trạng thái không hợp lệ.');
  if (status === 'rejected' && !reason.trim()) throw new ApiError(400, 'Vui lòng nhập lý do từ chối.');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const list = await readTable('bookings', 'host-bookings.json');
    const i = list.findIndex(b => b.id === id);
    if (i === -1) throw new ApiError(404, 'Không tìm thấy đặt phòng.');
    list[i].status = status;
    list[i].rejectReason = status === 'rejected' ? reason.trim() : '';
    writeTable('bookings', list);
    return list[i];
  }
  return request(`${API_BASE}/host/bookings/${id}/status`, { method: 'PATCH', body: { status, reason } });
}
// ---------- Admin dashboard ----------
// Trả về dữ liệu THÔ để trang tự tính (đếm, nhóm theo kỳ/tỉnh): { users, bookings, homestays }
//  - users:     [{ id, createdAt, role }]
//  - bookings:  [{ id, itemId, createdAt, status, totalPrice }]
//  - homestays: [{ id, title, location }]
// Mock: mock/admin-overview.json + mock/items.json. Backend thật: GET /admin/overview (cùng dạng).
export async function getAdminOverview(params = {}) {
  blockUnintegratedBusiness('admin');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    const [ov, items] = await Promise.all([
      request(`${MOCK_BASE}/admin-overview.json`),
      request(`${MOCK_BASE}/items.json`),
    ]);
    return {
      users: ov.users,
      bookings: ov.bookings,
      homestays: items.items.map(i => ({ id: i.id, title: i.title, location: i.location })),
    };
  }
  return request(`${API_BASE}/admin/overview?${new URLSearchParams(params)}`);
}

// ---------- Admin: danh sách host ----------
// Trả về: [{ id, display_name, email, phone, avatar, createdAt, homestays: [{id,title,location,rating,price}],
//            bookingCount, revenue }]   (revenue = tổng tiền các đơn đã hoàn thành)
// Mock: mock/admin-hosts.json + admin-overview.json + items.json, cộng thêm host đăng ký mới trên máy này
// (role "host" trong localStorage). Backend thật: GET /admin/hosts (cùng dạng).
export async function getAdminHosts(params = {}) {
  blockUnintegratedBusiness('admin');
  if (USE_MOCK && !ACCOUNT_API_MODE) {
    // Use the actual mock ownership tables; there is no admin-hosts.json fixture.
    const [users, homestays, rooms, bookings] = await Promise.all([
      loadMockUsers(), readTable('homestays', 'host-homestays.json'),
      readTable('rooms', 'host-rooms.json'), readTable('bookings', 'host-bookings.json')
    ]);
    return users.filter(user => user.role === 'host').map(user => {
      const owned = homestays.filter(h => String(h.hostId) === String(user.id) && h.status !== 'deleted');
      const roomIds = new Set(rooms.filter(r => owned.some(h => String(h.id) === String(r.homestayId))).map(r => String(r.id)));
      const mine = bookings.filter(b => roomIds.has(String(b.roomId)));
      return {
        id: user.id, display_name: user.display_name, email: user.email, phone: user.phone,
        avatar: user.avatar, createdAt: user.createdAt,
        homestays: owned.map(h => ({ id: h.id, title: h.name, location: h.address, rating: h.rating ?? null, price: h.price ?? null })),
        bookingCount: mine.length,
        revenue: mine.filter(b => b.status === 'completed').reduce((sum, b) => sum + Number(b.totalPrice || 0), 0)
      };
    });
  }
  return request(`${API_BASE}/admin/hosts?${new URLSearchParams(params)}`);
}

// ══════════ NGƯỜI 5 — TODO: thêm vùng của em ở đây ══════════


// ---------- chỉ dùng ở chế độ mock; backend thật lọc bằng SQL ----------
function filterMock(data, { q = '', sort = 'newest', category = '',
                          min_price = '', max_price = '',
                          room_type = [], amenity = [], rating = '',
                          page = 1, page_size = 0 }) {
  let items = data.items;
  if (q) {
    const needle = q.toLowerCase();
    // Khớp theo tên HOẶC địa điểm — "Sa Pa" phải ra được các homestay ở Sa Pa.
    items = items.filter(i => i.title.toLowerCase().includes(needle)
      || (i.location ?? '').toLowerCase().includes(needle));
  }
  if (category)  items = items.filter(i => i.category === category);
  if (min_price) items = items.filter(i => i.price >= Number(min_price));
  if (max_price) items = items.filter(i => i.price <= Number(max_price));
  if (room_type.length) items = items.filter(i => room_type.includes(i.room_type));
  // Tiện ích: phải có ĐỦ tất cả tiện ích đã chọn, không phải chỉ cần 1 trong số đó.
  if (amenity.length)   items = items.filter(i => amenity.every(a => (i.amenities ?? []).includes(a)));
  if (rating)    items = items.filter(i => (i.rating ?? 0) >= Number(rating));

  if (sort === 'price_asc')  items = [...items].sort((a, b) => a.price - b.price);
  if (sort === 'price_desc') items = [...items].sort((a, b) => b.price - a.price);
  if (sort === 'newest')     items = [...items].sort((a, b) => b.created_at.localeCompare(a.created_at));

  const total = items.length;
  const size  = Number(page_size) || data.page_size || 20;
  const start = (Number(page) - 1) * size;
  return { items: items.slice(start, start + size), total, page: Number(page), page_size: size };
}

export async function uploadImage(file) {
  if (!ACCOUNT_API_MODE) throw new ApiError(503, 'Upload requires API mode.');
  if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 5 * 1024 * 1024) throw new ApiError(422, 'JPEG, PNG, WebP; maximum 5 MB.');
  const body = new FormData(); body.append('file', file);
  return request(`${API_BASE}/uploads`, { method: 'POST', body });
}

export async function getRoomBlocks(roomId) {
  blockUnintegratedBusiness('host-rooms');
  return request(`${API_BASE}/host/rooms/${encodeURIComponent(roomId)}/blocks`);
}
export async function saveRoomBlock(roomId, block) {
  blockUnintegratedBusiness('host-rooms');
  const { id, ...body } = block;
  return request(`${API_BASE}/host/rooms/${encodeURIComponent(roomId)}/blocks${id ? '/' + encodeURIComponent(id) : ''}`, { method: id ? 'PUT' : 'POST', body });
}
export async function deleteRoomBlock(roomId, blockId) {
  blockUnintegratedBusiness('host-rooms');
  return request(`${API_BASE}/host/rooms/${encodeURIComponent(roomId)}/blocks/${encodeURIComponent(blockId)}`, { method: 'DELETE' });
}

export async function getHostDashboard(params = {}) {
  blockUnintegratedBusiness('host-dashboard');
  return request(`${API_BASE}/host/dashboard?${new URLSearchParams(params)}`);
}

export async function getAdminApplications(params = {}) {
  blockUnintegratedBusiness('admin'); return request(`${API_BASE}/admin/host-applications?${new URLSearchParams(params)}`);
}
export async function decideHostApplication(id, action, reason = '') {
  blockUnintegratedBusiness('admin');
  if (!['approve','reject'].includes(action)) throw new ApiError(422, 'Invalid decision');
  return request(`${API_BASE}/admin/host-applications/${encodeURIComponent(id)}/${action}`, { method: 'POST', ...(action === 'reject' ? { body: { reason } } : {}) });
}
export async function getAdminUsers(params = {}) {
  blockUnintegratedBusiness('admin'); return request(`${API_BASE}/admin/users?${new URLSearchParams(params)}`);
}
export async function updateAdminUser(id, body) {
  blockUnintegratedBusiness('admin'); return request(`${API_BASE}/admin/users/${encodeURIComponent(id)}`, { method: 'PATCH', body });
}
export async function getAdminHomestays(params = {}) {
  blockUnintegratedBusiness('admin'); return request(`${API_BASE}/admin/homestays?${new URLSearchParams(params)}`);
}
export async function moderateHomestay(id, body) {
  blockUnintegratedBusiness('admin'); return request(`${API_BASE}/admin/homestays/${encodeURIComponent(id)}/status`, { method: 'PATCH', body });
}
