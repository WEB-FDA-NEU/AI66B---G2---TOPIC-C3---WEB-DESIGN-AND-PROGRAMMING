import { ACCOUNT_API_MODE, API_SCOPE, safeImageURL } from './config.js';
// ============================================================
//  Tính giá & xử lý ngày/phòng — DÙNG CHUNG cho detail (đã gộp chọn phòng)
//  và booking-page. Một nơi duy nhất tính tiền để 3 trang luôn ra cùng một con số.
// ============================================================

export const SERVICE_FEE_RATE = 0.05;   // phí dịch vụ 5% trên tiền phòng
export const FREE_CANCEL_DAYS = 3;      // hủy trước 3 ngày nhận phòng → hoàn tiền toàn bộ
export const MAX_ADULTS = 10;
export const MAX_CHILDREN = 6;

// ---------- Ngày (dùng giờ địa phương, tránh lệch ngày do toISOString) ----------
const pad = n => String(n).padStart(2, '0');
export const toISO = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const parseISO = s => { const [y, m, d] = String(s).split('-').map(Number); return new Date(y, m - 1, d); };
export const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
export const todayISO = () => toISO(new Date());
export const fmtDate = s => parseISO(s).toLocaleDateString('vi-VN');

export function nightsBetween(checkin, checkout) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(checkin ?? '') || !/^\d{4}-\d{2}-\d{2}$/.test(checkout ?? '')) return 0;
  const n = Math.round((parseISO(checkout) - parseISO(checkin)) / 86400000);
  return n > 0 ? n : 0;
}

/** Ngày mặc định: nhận phòng sau 7 ngày, ở 2 đêm. */
export function defaultStay() {
  const t = new Date();
  return { checkin: toISO(addDays(t, 7)), checkout: toISO(addDays(t, 9)), adults: 2, children: 0 };
}

/** Đọc ngày/khách từ URL; thiếu hoặc sai thì dùng mặc định. */
export function stayFromParams(params) {
  const def = defaultStay();
  let checkin = params.get('checkin') || def.checkin;
  let checkout = params.get('checkout') || '';
  if (checkin < todayISO()) checkin = def.checkin;
  if (!checkout || nightsBetween(checkin, checkout) === 0) checkout = toISO(addDays(parseISO(checkin), 2));
  const clamp = (v, min, max, d) => { const n = parseInt(v, 10); return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : d; };
  return {
    checkin, checkout,
    adults: clamp(params.get('adults'), 1, MAX_ADULTS, def.adults),
    children: clamp(params.get('children'), 0, MAX_CHILDREN, def.children),
  };
}

export const stayToParams = (stay, extra = {}) => new URLSearchParams({
  ...(ACCOUNT_API_MODE ? API_SCOPE === "customer" ? {mode:"api"} : {accounts:"api"} : {}),
  checkin: stay.checkin, checkout: stay.checkout, adults: stay.adults, children: stay.children, ...extra,
});

export const guestText = ({ adults, children }) =>
  `${adults} người lớn${children ? ` · ${children} trẻ em` : ''}`;

// ---------- Loại phòng ----------
// Mock chỉ có 1 giá / homestay → suy ra 2 loại phòng từ giá đó.
// Khi backend có bảng phòng thật, chỉ cần thay hàm này.
export function roomTypesFor(item) {
  if (ACCOUNT_API_MODE) return (item.roomTypes || []).map(r => ({...r, price:r.pricePerNight, image:safeImageURL(r.image || r.images?.[0]), policy:'Hủy theo chính sách đặt phòng'}));
  const base = Number(item.price) || 0;
  const imgs = (item.images?.length ? item.images : [item.cover_url]).filter(Boolean);
  const img = i => imgs[i] ?? imgs[0] ?? 'img/placeholder.svg';   // ảnh phòng lấy từ chính homestay đang xem
  const policy = `Miễn phí hủy trước ${FREE_CANCEL_DAYS} ngày nhận phòng`;
  return [
    { key: 'superior', name: 'Phòng Superior Giường Đôi', image: img(1),
      bed: '1 giường đôi lớn', area: '25 m²', capacity: 2, price: base, policy,
      detail: '🛏 1 giường đôi lớn · 📐 25 m²', note: `✓ ${policy}` },
    { key: 'deluxe', name: 'Deluxe Studio Hướng Núi', image: img(2),
      bed: '1 giường cực lớn + 1 sofa', area: '35 m²', capacity: 3,
      price: Math.round(base * 1.33 / 1000) * 1000, policy, badge: 'Bao gồm ăn sáng',
      detail: '🛏 1 giường cực lớn + 1 sofa · 📐 35 m²' },
  ];
}

// "superior:1,deluxe:2" ⇄ { superior: 1, deluxe: 2 }
export function parseRooms(str) {
  const out = Object.create(null);
  String(str ?? '').split(',').forEach(part => {
    const [k, v] = part.split(':');
    const n = parseInt(v, 10);
    if (k && n > 0) out[k] = Math.min(n, ACCOUNT_API_MODE ? 100 : 4);
  });
  return out;
}
export const stringifyRooms = map =>
  Object.entries(map).filter(([, n]) => n > 0).map(([k, n]) => `${k}:${n}`).join(',');

/** Báo giá đầy đủ. Mọi số tiền trên 3 trang đều đi qua hàm này. */
export function quote({ item, rooms, checkin, checkout }) {
  const nights = nightsBetween(checkin, checkout);
  const types = roomTypesFor(item);
  const lines = types
    .filter(t => (rooms[t.key] ?? 0) > 0)
    .map(t => ({ key: t.key, name: t.name, qty: rooms[t.key], pricePerNight: t.price,
                 capacity: t.capacity, subtotal: t.price * rooms[t.key] * nights }));
  const roomSubtotal = lines.reduce((s, l) => s + l.subtotal, 0);
  const serviceFee = Math.round(roomSubtotal * SERVICE_FEE_RATE);
  return {
    nights, lines,
    roomCount: lines.reduce((s, l) => s + l.qty, 0),
    capacity: lines.reduce((s, l) => s + l.qty * l.capacity, 0),
    roomSubtotal, serviceFee, total: roomSubtotal + serviceFee,
  };
}

/** Số ngày còn lại tới ngày nhận phòng (âm nếu đã qua). */
export const daysUntil = checkin => Math.ceil((parseISO(checkin) - parseISO(todayISO())) / 86400000);

export const ratingLabel = r =>
  r == null ? '' : r >= 4.7 ? 'Xuất sắc' : r >= 4.4 ? 'Rất tốt' : r >= 4 ? 'Tốt' : r >= 3 ? 'Khá' : 'Trung bình';

export const paymentText = payment => `${payment?.simulated ? 'Mô phỏng — không xác nhận ngân hàng. ' : ''}${({pending:'Chưa thanh toán — thanh toán tại chỗ',paid:'Đã ghi nhận thanh toán',refund_pending:'Đang chờ hoàn tiền',refunded:'Đã ghi nhận hoàn tiền',cancelled:'Thanh toán đã hủy',failed:'Thanh toán thất bại'})[payment?.status] || 'Chưa có thông tin thanh toán'}`;
