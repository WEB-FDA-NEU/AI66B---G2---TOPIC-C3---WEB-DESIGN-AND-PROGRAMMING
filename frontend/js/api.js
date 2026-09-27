// ============================================================
//  Tầng DUY NHẤT được phép gọi mạng.
//  Không file nào khác được viết fetch().
//
//  CHIA VÙNG THEO NGƯỜI để tránh conflict Git — mỗi người chỉ
//  thêm hàm vào vùng của mình.
// ============================================================
import { USE_MOCK, API_BASE, MOCK_BASE } from './config.js';
import { getToken, getUser } from './auth.js';

export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || 'Đã có lỗi xảy ra.');
    this.status = status;
    this.detail = detail;
  }
}

async function request(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(options.body);
  }

  let res;
  try {
    res = await fetch(url, { ...options, headers });
  } catch {
    throw new ApiError(0, 'Không kết nối được máy chủ. Kiểm tra mạng rồi thử lại.');
  }

  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch { /* body rỗng */ }
  if (!res.ok) throw new ApiError(res.status, normalizeDetail(data?.detail));
  return data;
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
  if (USE_MOCK) return request(`${MOCK_BASE}/items.json`).then(d => filterMock(d, params));
  // Một số bộ lọc (room_type, amenity) có thể là MẢNG — mỗi giá trị cần 1 cặp
  // key=value riêng trên querystring, nên không thể đưa thẳng cho URLSearchParams(object).
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v == null || v === '') continue;
    if (Array.isArray(v)) v.forEach(val => val !== '' && qs.append(k, val));
    else qs.set(k, v);
  }
  return request(`${API_BASE}/items?${qs}`);
}

export function getItem(id) {
  if (USE_MOCK) return request(`${MOCK_BASE}/item-${id}.json`);
  return request(`${API_BASE}/items/${id}`);
}

// ---------- Đánh giá (reviews) của trang chi tiết ----------
// Mock: đọc/ghi vào localStorage, seed lần đầu từ mảng "reviews" có sẵn trong mock/item-<id>.json.
const reviewsKey = id => `reviews_${id}`;

export async function getReviews(itemId) {
  if (USE_MOCK) {
    const cached = localStorage.getItem(reviewsKey(itemId));
    if (cached) return JSON.parse(cached);
    const item = await getItem(itemId);
    const seed = item.reviews ?? [];
    localStorage.setItem(reviewsKey(itemId), JSON.stringify(seed));
    return seed;
  }
  return request(`${API_BASE}/items/${itemId}/reviews`);
}

export async function addReview(itemId, review) {
  if (USE_MOCK) {
    const list = await getReviews(itemId);
    const entry = { id: `rv${Date.now()}`, created_at: new Date().toISOString(), ...review };
    list.unshift(entry);
    localStorage.setItem(reviewsKey(itemId), JSON.stringify(list));
    return entry;
  }
  return request(`${API_BASE}/items/${itemId}/reviews`, { method: 'POST', body: review });
}

// ══════════ NGƯỜI 2 — tài khoản ══════════
/** Cache danh sách user đọc từ mock/users.json — dùng chung cho login() và register(). */
let MOCK_USERS = null;
async function loadMockUsers() {
  if (!MOCK_USERS) {
    const data = await request(`${MOCK_BASE}/users.json`);
    MOCK_USERS = data.users ?? [];
  }
  return MOCK_USERS;
}

export async function login(email, password) {
  if (USE_MOCK) {
    const users = await loadMockUsers();
    const found = users.find(u => u.email === email.trim().toLowerCase());
    if (!found || found.password !== password)
      throw new ApiError(401, 'Email hoặc mật khẩu không đúng.');
    const { password: _pw, ...user } = found;   // không bao giờ trả password về client
    return { access_token: 'mock-token', token_type: 'bearer', user };
  }
  return request(`${API_BASE}/auth/login`, { method: 'POST', body: { email, password } });
}

export async function register(payload) {
  if (USE_MOCK) {
    const users = await loadMockUsers();
    const email = payload.email.trim().toLowerCase();
    if (users.some(u => u.email === email))
      throw new ApiError(409, 'Email đã được đăng ký.');
    const user = {
      id: users.length + 1,
      display_name: payload.display_name,
      email,
      phone: payload.phone ?? '',
      role: 'user',
      avatar: 'img/placeholder.svg',
      createdAt: new Date().toISOString(),
    };
    users.push(user);
    return { access_token: 'mock-token', token_type: 'bearer', user };
  }
  return request(`${API_BASE}/auth/register`, { method: 'POST', body: payload });
}

// ══════════ NGƯỜI 3 — TODO: thêm vùng của em ở đây ══════════

export async function getBookings() {
  if (USE_MOCK) {
    const list = await readTable('customerBookings', 'bookings.json');
    const me = getUser();
    return me ? list.filter(b => b.userId === me.id) : list;
  }
  return request(`${API_BASE}/me/bookings`);
}

export async function cancelBooking(id) {
  if (USE_MOCK) {
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
export async function getHostHomestays() {
  if (USE_MOCK) {
    const list = await readTable('homestays', 'host-homestays.json');
    return list.filter(h => h.hostId === HOST_ID && h.status !== 'deleted');
  }
  return request(`${API_BASE}/host/homestays`);
}

export async function getHostHomestay(id) {
  if (USE_MOCK) {
    const list = await readTable('homestays', 'host-homestays.json');
    const found = list.find(h => h.id === id);
    if (!found) throw new ApiError(404, 'Không tìm thấy homestay.');
    return found;
  }
  return request(`${API_BASE}/host/homestays/${id}`);
}

/** Tạo mới (không có id) hoặc cập nhật (có id). */
export async function saveHostHomestay(data) {
  if (USE_MOCK) {
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
  if (USE_MOCK) {
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
export async function getHostRooms(homestayId) {
  if (USE_MOCK) {
    const list = await readTable('rooms', 'host-rooms.json');
    return homestayId ? list.filter(r => r.homestayId === homestayId) : list;
  }
  const qs = homestayId ? `?homestay_id=${homestayId}` : '';
  return request(`${API_BASE}/host/rooms${qs}`);
}

export async function getHostRoom(id) {
  if (USE_MOCK) {
    const list = await readTable('rooms', 'host-rooms.json');
    const found = list.find(r => r.id === id);
    if (!found) throw new ApiError(404, 'Không tìm thấy phòng.');
    return found;
  }
  return request(`${API_BASE}/host/rooms/${id}`);
}

export async function saveHostRoom(data) {
  if (USE_MOCK) {
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
  return data.id
    ? request(`${API_BASE}/host/rooms/${data.id}`, { method: 'PUT', body: data })
    : request(`${API_BASE}/host/rooms`, { method: 'POST', body: data });
}

export async function deleteHostRoom(id) {
  if (USE_MOCK) {
    const list = await readTable('rooms', 'host-rooms.json');
    const next = list.filter(r => r.id !== id);
    writeTable('rooms', next);
    return null;
  }
  return request(`${API_BASE}/host/rooms/${id}`, { method: 'DELETE' });
}

// ---------- Đặt phòng (duyệt / từ chối) ----------
export async function getHostBookings() {
  if (USE_MOCK) return readTable('bookings', 'host-bookings.json');
  return request(`${API_BASE}/host/bookings`);
}

/** reason bắt buộc khi status = 'rejected' — xem docs/api-contract.md */
export async function updateBookingStatus(id, status, reason = '') {
  if (!BOOKING_STATUSES.includes(status)) throw new ApiError(400, 'Trạng thái không hợp lệ.');
  if (status === 'rejected' && !reason.trim()) throw new ApiError(400, 'Vui lòng nhập lý do từ chối.');
  if (USE_MOCK) {
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