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
  if (USE_MOCK) return request(`${MOCK_BASE}/items.json`).then(async d => filterMock({ ...d, items: applyRatings([...(await readHostItems()), ...d.items]) }, params));
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

export async function getItem(id) {
  if (USE_MOCK) {
    const data = await request(`${MOCK_BASE}/items.json`);

    const item = applyRatings([...(await readHostItems()), ...data.items]).find(
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

  return request(`${API_BASE}/items/${id}`);
}

// Điểm trung bình mới (sau khi khách gửi đánh giá) — chỉ mock; backend thật tự tính bằng SQL.
const RATINGS_KEY = 'itemRatings';
function readRatings() { try { return JSON.parse(localStorage.getItem(RATINGS_KEY) || '{}'); } catch { return {}; } }
function applyRatings(items) {
  const map = readRatings();
  return items.map(i => map[i.id] != null ? { ...i, rating: map[i.id] } : i);
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
    const me = getUser();
    if (me) entry.userId = me.id;
    // Gắn nhãn "Đã lưu trú" nếu người này có booking hoàn thành ở homestay này
    try {
      const bookings = await readTable('customerBookings', 'bookings.json');
      entry.verified = !!me && bookings.some(b => b.userId === me.id && String(b.homestayId) === String(itemId) && b.status === 'completed');
    } catch { entry.verified = false; }
    list.unshift(entry);
    localStorage.setItem(reviewsKey(itemId), JSON.stringify(list));
    const avg = list.reduce((sum, r) => sum + Number(r.rating), 0) / list.length;
    const map = readRatings(); map[itemId] = Math.round(avg * 10) / 10;
    localStorage.setItem(RATINGS_KEY, JSON.stringify(map));
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
  // Áp các thay đổi hồ sơ/mật khẩu đã lưu ở localStorage (mock) lên dữ liệu gốc,
  // để đăng nhập lại vẫn thấy thông tin mới.
  const patches = readUserPatches();
  MOCK_USERS.forEach(u => Object.assign(u, patches[u.id] ?? {}));
  return MOCK_USERS;
}

const USER_PATCH_KEY = 'mockUserPatches';
function readUserPatches() {
  try { return JSON.parse(localStorage.getItem(USER_PATCH_KEY) || '{}'); } catch { return {}; }
}
function savePatch(id, fields) {
  const patches = readUserPatches();
  patches[id] = { ...(patches[id] ?? {}), ...fields };
  localStorage.setItem(USER_PATCH_KEY, JSON.stringify(patches));
}
const withoutPassword = ({ password: _pw, ...user }) => user;

/** Cập nhật hồ sơ: { display_name, email, phone, avatar } — chỉ gửi trường cần đổi. */
export async function updateProfile(fields) {
  if (USE_MOCK) {
    const me = getUser();
    if (!me) throw new ApiError(401, 'Bạn cần đăng nhập.');
    const users = await loadMockUsers();
    const current = users.find(u => String(u.id) === String(me.id)) ?? me;
    const next = { ...fields };
    if (next.email) {
      next.email = next.email.trim().toLowerCase();
      if (users.some(u => u.email === next.email && String(u.id) !== String(me.id)))
        throw new ApiError(409, 'Email đã được sử dụng bởi tài khoản khác.');
    }
    savePatch(me.id, next);
    return withoutPassword({ ...current, ...next });
  }
  return request(`${API_BASE}/me`, { method: 'PUT', body: fields });
}

/** Đổi mật khẩu: kiểm tra mật khẩu hiện tại rồi mới đổi. */
export async function changePassword(currentPassword, newPassword) {
  if (USE_MOCK) {
    const me = getUser();
    if (!me) throw new ApiError(401, 'Bạn cần đăng nhập.');
    const users = await loadMockUsers();
    const current = users.find(u => String(u.id) === String(me.id));
    if (!current || current.password !== currentPassword)
      throw new ApiError(400, 'Mật khẩu hiện tại không đúng.');
    savePatch(me.id, { password: newPassword });
    return null;
  }
  return request(`${API_BASE}/me/password`, { method: 'POST', body: { current_password: currentPassword, new_password: newPassword } });
}

// ---------- Tin nhắn liên hệ ----------
// Mock: lưu ở localStorage (cùng trình duyệt thì admin mới thấy tin vừa gửi).
// Backend thật: POST /contact (công khai) và GET/PATCH/DELETE /admin/contact-messages (chỉ admin).
const MESSAGES_KEY = 'contactMessages';
const readMessages = () => { try { return JSON.parse(localStorage.getItem(MESSAGES_KEY) || '[]'); } catch { return []; } };

export async function sendContactMessage({ name, email, subject, message }) {
  if (USE_MOCK) {
    const list = readMessages();
    list.push({ id: newId('msg'), name, email, subject, message, createdAt: new Date().toISOString(), read: false });
    writeTable(MESSAGES_KEY, list);
    return null;
  }
  return request(`${API_BASE}/contact`, { method: 'POST', body: { name, email, subject, message } });
}

export async function getContactMessages() {
  if (USE_MOCK) return readMessages().sort((x, y) => y.createdAt.localeCompare(x.createdAt));
  return request(`${API_BASE}/admin/contact-messages`);
}

export async function setContactMessageRead(id, read = true) {
  if (USE_MOCK) {
    const list = readMessages();
    const m = list.find(x => x.id === id);
    if (m) m.read = read;
    writeTable(MESSAGES_KEY, list);
    return null;
  }
  return request(`${API_BASE}/admin/contact-messages/${id}`, { method: 'PATCH', body: { read } });
}

export async function deleteContactMessage(id) {
  if (USE_MOCK) {
    writeTable(MESSAGES_KEY, readMessages().filter(x => x.id !== id));
    return null;
  }
  return request(`${API_BASE}/admin/contact-messages/${id}`, { method: 'DELETE' });
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
      role: payload.role ?? 'user',
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
    const mine = me ? list.filter(b => String(b.userId) === String(me.id)) : list;
    // Mới nhất lên đầu
    return [...mine].sort((a, b) => (b.createdAt ?? '').localeCompare(a.createdAt ?? '') || Number(b.id) - Number(a.id));
  }
  return request(`${API_BASE}/me/bookings`);
}

export async function getBooking(id) {
  if (USE_MOCK) {
    const list = await readTable('customerBookings', 'bookings.json');
    const me = getUser();
    const found = list.find(b => String(b.id) === String(id) && (!me || String(b.userId) === String(me.id)));
    if (!found) throw new ApiError(404, 'Không tìm thấy đặt phòng.');
    return found;
  }
  return request(`${API_BASE}/me/bookings/${id}`);
}

/** Tạo booking sau khi thanh toán giả lập thành công. */
export async function createBooking(payload) {
  if (USE_MOCK) {
    const me = getUser();
    if (!me) throw new ApiError(401, 'Bạn cần đăng nhập để đặt phòng.');
    const list = await readTable('customerBookings', 'bookings.json');
    const id = list.reduce((m, b) => Math.max(m, Number(b.id) || 0), 0) + 1;
    const booking = {
      id, userId: me.id, status: 'confirmed', createdAt: new Date().toISOString(),
      code: 'LX' + String(Date.now()).slice(-8), ...payload,
    };
    list.push(booking);
    writeTable('customerBookings', list);
    return booking;
  }
  return request(`${API_BASE}/me/bookings`, { method: 'POST', body: payload });
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

// ---------- Đồng bộ homestay của host → trang tìm kiếm / chi tiết (chỉ mock) ----------
// Host thêm/sửa homestay (kèm ảnh) ở màn Quản lý → homestay đó hiện luôn ở Tìm kiếm và Chi tiết.
// Backend thật: khi nối API, bảng homestay chỉ có MỘT nguồn nên không cần đoạn này.
const HOST_ITEMS_KEY = 'hostPublicItems';
function readHostItemsRaw() {
  try { return JSON.parse(localStorage.getItem(HOST_ITEMS_KEY) || '[]'); } catch { return []; }
}
/** Ảnh chỉ lưu MỘT lần (ở bảng homestays) để không ăn đôi bộ nhớ localStorage;
 *  ở đây ghép ảnh lại vào bản công khai khi đọc. */
async function readHostItems() {
  const raw = readHostItemsRaw();
  if (!raw.length) return raw;
  const table = await readTable('homestays', 'host-homestays.json');
  return raw.map(i => {
    const h = table.find(x => x.id === i.hostRef);
    const imgs = h?.images?.length ? h.images : ['img/placeholder.svg'];
    return { ...i, images: imgs, cover_url: imgs[0] };
  });
}
async function syncPublicItem(h) {
  try {
    const rooms = await readTable('rooms', 'host-rooms.json');
    const prices = rooms.filter(r => r.homestayId === h.id).map(r => r.pricePerNight).filter(Boolean);
    const price = Number(h.price) || (prices.length ? Math.min(...prices) : 0);
    const items = readHostItemsRaw().filter(i => i.hostRef !== h.id);
    if (h.status !== 'deleted') {
      const imgs = h.images?.length ? h.images : ['img/placeholder.svg'];
      items.push({
        id: `host-${h.id}`, hostRef: h.id,
        title: h.name, location: h.address, meta: h.address,
        room_type: 'Toàn bộ homestay', amenities: h.amenities ?? [],
        rating: null, price,   // ảnh ghép lại lúc đọc (readHostItems)
        status: 'active', created_at: h.createdAt ?? new Date().toISOString(),
        description: h.description,
      });
    }
    localStorage.setItem(HOST_ITEMS_KEY, JSON.stringify(items));
  } catch (e) {
    console.warn('Không đồng bộ được homestay sang trang công khai (có thể đầy bộ nhớ trình duyệt).', e);
  }
}

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
    try { writeTable('homestays', list); }
    catch {
      // localStorage (~5MB) đầy vì ảnh quá nặng → báo lỗi dễ hiểu thay vì "Không lưu được"
      throw new ApiError(507, 'Bộ nhớ trình duyệt đã đầy do ảnh quá nặng. Hãy giảm số lượng ảnh hoặc xóa bớt homestay thử nghiệm.');
    }
    await syncPublicItem(data.id ? list.find(h => h.id === data.id) : data);
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
    await syncPublicItem(list[i]);
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