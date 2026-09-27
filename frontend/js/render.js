// ============================================================
//  Biến JSON thành DOM, dựa trên <template> viết sẵn trong HTML.
//
//  QUY TẮC VÀNG: markup nằm trong HTML, không nằm trong chuỗi JS.
//    Sai:  el.innerHTML = `<div class="card">${item.title}</div>`
//    Đúng: clone <template> rồi gán bằng .textContent
//
//  Vì sao: (1) không thủng XSS, (2) HTML viết ở Mốc 2 sống nguyên sang Mốc 4,
//  (3) sửa giao diện thì sửa HTML/CSS, không phải đi sửa chuỗi trong JS.
//
//  QUY TẮC ĐẶT FILE: một hàm render chỉ chuyển vào đây khi ≥ 2 màn hình dùng chung.
//  Chỉ 1 màn dùng thì để trong js/pages/<màn-đó>.js
// ============================================================

export const formatVND = n =>
  new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 }).format(n);

export function timeAgo(iso) {
  const mins = Math.floor((Date.now() - new Date(iso)) / 60000);
  // Dữ liệu seed hoặc lệch múi giờ có thể cho ra mốc ở TƯƠNG LAI → mins âm.
  // Không chặn thì giao diện hiện "-16864 phút trước".
  if (mins < 1)    return 'Vừa xong';
  if (mins < 60)   return `${mins} phút trước`;
  if (mins < 1440) return `${Math.floor(mins / 60)} giờ trước`;
  return `${Math.floor(mins / 1440)} ngày trước`;
}

// TODO: đổi nhãn trạng thái theo state machine ở Section 3 của Mốc 1
const STATUS_LABEL = { active: 'Đang hoạt động', sold: 'Đã bán', hidden: 'Đang ẩn' };

export function renderCard(item) {
  const node = document.getElementById('tpl-card').content.cloneNode(true);

  const link = node.querySelector('.card__link');
  link.href = `detail.html?id=${item.id}`;

  const img = node.querySelector('.card__img');
  img.src = item.cover_url;
  img.alt = item.title;

  node.querySelector('.card__title').textContent = item.title;

  node.querySelector('.card__meta').textContent =
    item.location ?? item.meta ?? '';

  const priceEl = node.querySelector('.card__price');
  priceEl.textContent = `${formatVND(item.price)} / đêm`;

  if (item.rating != null) {
    const ratingWrap = document.createElement('div');
    ratingWrap.className = 'card__rating';

    const rating = document.createElement('span');
    rating.className = 'rating';
    rating.textContent = `⭐ ${item.rating.toFixed(1)}`;

    const text = document.createElement('span');
    text.textContent = ' · Đánh giá tốt';

    ratingWrap.append(rating, text);

    priceEl.before(ratingWrap);
  }

  const badge = node.querySelector('.card__badge');

  if (item.price_old && item.price_old > item.price) {
    const discount = Math.round(
      (1 - item.price / item.price_old) * 100
    );

    badge.textContent = `-${discount}%`;
    badge.dataset.status = 'sale';
  } else {
    badge.remove();
  }

  return node;
}

/** Đổ mảng vào container. replaceChildren xoá sạch cái cũ trong một bước. */
export function renderList(container, items, renderOne) {
  container.replaceChildren(...items.map(renderOne));
}
