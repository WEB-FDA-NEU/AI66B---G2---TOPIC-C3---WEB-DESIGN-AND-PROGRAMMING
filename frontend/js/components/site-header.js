// ============================================================
// <site-header>
// Header dùng chung cho toàn bộ website. Mỗi trang chỉ cần:
//
//   <site-header active="home"></site-header>
//
// Giá trị active (mục menu được tô sáng):
//   home      → Trang chủ
//   search    → Homestay
//   bookings  → Đặt phòng của tôi
//   profile   → Hồ sơ
//   host      → Quản lý homestay   (chỉ role host thấy)
//   admin     → Quản trị           (chỉ role admin thấy)
//
// Chỉ sửa header ở file này. Không tạo header riêng trong từng HTML.
// Style của header nằm ở css/layout.css (mục HEADER) — không viết style inline ở đây.
// ============================================================

import { initHeader, getUser } from '../auth.js';
import '../motion.js';

// Tên thương hiệu: đổi ở ĐÂY là cả header đổi theo.
// (Nhớ đổi cả <title> trong các file HTML nếu đổi tên.)
const BRAND = 'Homestay Booking';

// Biểu tượng ☰ dạng SVG: hiển thị giống nhau trên mọi thiết bị, không phụ thuộc font.
const ICON_MENU = /* html */ `
<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor"
     stroke-width="2" stroke-linecap="round" aria-hidden="true">
  <path d="M4 7h16M4 12h16M4 17h16"/>
</svg>`;

// ============================================================
// TEMPLATE
// ============================================================

const TEMPLATE = /* html */ `
<header class="site-header">
  <div class="container">

    <!-- Hàng 1: logo + tài khoản + nút menu (mobile). CSS xếp logo · menu · tài khoản thành MỘT hàng trên desktop. -->
    <div class="site-header__top">

      <a class="logo" href="index.html" aria-label="${BRAND} – Trang chủ">
        <span class="logo__mark" aria-hidden="true">${BRAND[0]}</span>
        <span class="logo__text">${BRAND}</span>
      </a>

      <div class="site-header__actions">

        <!-- Khách chưa đăng nhập. "Đăng ký" ẩn trên điện thoại (trang đăng nhập đã có link đăng ký). -->
        <span data-auth="guest">
          <a class="btn btn--light hide-sm" href="register.html">Đăng ký</a>
          <a class="btn btn--light" href="login.html">Đăng nhập</a>
        </span>

        <!-- Đã đăng nhập -->
        <span data-auth="user" hidden>
          <span class="hide-sm" data-user-name></span>
          <a class="btn btn--light" href="#" data-action="logout">Đăng xuất</a>
        </span>

        <button class="nav-toggle" type="button" aria-label="Mở menu"
                aria-expanded="false" aria-controls="mainNav">
          ${ICON_MENU}
        </button>
      </div>
    </div>

    <!-- Menu chính -->
    <nav class="main-nav" id="mainNav" aria-label="Menu chính">
      <ul class="nav-links">

        <li><a href="index.html"  data-nav="home">Trang chủ</a></li>
        <li><a href="search.html" data-nav="search">Homestay</a></li>

        <!-- Chỉ dành cho khách hàng: ẩn khi role là host hoặc admin -->
        <li data-customer-nav><a href="booking-list.html" data-nav="bookings">Đặt phòng của tôi</a></li>

        <li><a href="profile.html" data-nav="profile">Hồ sơ</a></li>

        <!-- Chỉ role host -->
        <li data-host-nav><a href="host-dashboard.html" data-nav="host">Quản lý homestay</a></li>

        <!-- Chỉ role admin -->
        <li data-admin-nav><a href="admin.html" data-nav="admin">Quản trị</a></li>

      </ul>
    </nav>

  </div>
</header>
`;

// ============================================================
// COMPONENT
// ============================================================

class SiteHeader extends HTMLElement {

  connectedCallback() {
    this.innerHTML = TEMPLATE;

    // Chưa đăng nhập: Đăng ký | Đăng nhập.  Đã đăng nhập: tên người dùng | Đăng xuất.
    initHeader();

    // Tô sáng mục menu đang xem
    const active = this.getAttribute('active');
    if (active) {
      const activeNav = this.querySelector(`[data-nav="${active}"]`);
      if (activeNav) {
        activeNav.classList.add('is-active');
        activeNav.setAttribute('aria-current', 'page');
      }
    }

    // Ẩn/hiện mục menu theo role.
    //   Quản lý homestay: chỉ host · Quản trị: chỉ admin · Đặt phòng của tôi: ẩn với host và admin
    const role = getUser()?.role;

    const hostNav = this.querySelector('[data-host-nav]');
    if (hostNav && role !== 'host') hostNav.hidden = true;

    const adminNav = this.querySelector('[data-admin-nav]');
    if (adminNav && role !== 'admin') adminNav.hidden = true;

    const customerNav = this.querySelector('[data-customer-nav]');
    if (customerNav && (role === 'host' || role === 'admin')) customerNav.hidden = true;

    // Menu trên điện thoại / máy tính bảng
    const toggle = this.querySelector('.nav-toggle');
    const nav = this.querySelector('#mainNav');
    if (toggle && nav) {
      const setOpen = (open) => {
        nav.classList.toggle('is-open', open);
        toggle.setAttribute('aria-expanded', String(open));
        toggle.setAttribute('aria-label', open ? 'Đóng menu' : 'Mở menu');
      };
      toggle.addEventListener('click', () => setOpen(!nav.classList.contains('is-open')));
      // Esc để đóng menu (hỗ trợ bàn phím)
      this.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && nav.classList.contains('is-open')) { setOpen(false); toggle.focus(); }
      });
    }
  }
}

customElements.define('site-header', SiteHeader);
