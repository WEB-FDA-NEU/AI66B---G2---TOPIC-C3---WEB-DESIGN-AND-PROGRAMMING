// ============================================================
//  <site-header> — header dùng chung cho MỌI trang.
//  Mỗi trang chỉ cần:   <site-header active="home"></site-header>
//  Giá trị active: home | search | bookings | profile | host
//  → mục tương ứng trên thanh nav được tô sáng.
//
//  Sửa nav/logo ở ĐÂY một lần, mọi trang đổi theo. Đừng tự làm nav riêng trong trang của mình.
// ============================================================
import { initHeader } from '../auth.js';

const TEMPLATE = /* html */ `
<header class="site-header">
  <div class="container">

    <div class="site-header__top">
      <a class="logo" href="index.html">Homestay Booking</a>

      <div class="site-header__actions">
        <span class="hide-sm">VND</span>
        <a class="site-header__link hide-sm" href="host-dashboard.html">Đăng homestay của bạn</a>

        <span data-auth="guest" hidden>
          <a class="btn btn--light" href="register.html">Đăng ký</a>
          <a class="btn btn--light" href="login.html">Đăng nhập</a>
        </span>
        <span data-auth="user" hidden>
          <span class="hide-sm" data-user-name></span>
          <a class="btn btn--light" href="#" data-action="logout">Thoát</a>
        </span>

        <button class="nav-toggle" type="button" aria-label="Mở menu" aria-expanded="false" aria-controls="mainNav">☰</button>
      </div>
    </div>

    <nav class="main-nav" id="mainNav" aria-label="Điều hướng chính">
      <ul class="nav-links">
        <li><a href="index.html"        data-nav="home">🛏 Trang chủ</a></li>
        <li><a href="search.html"       data-nav="search">🏠 Tìm homestay</a></li>
        <li><a href="booking-list.html" data-nav="bookings">📋 Đặt phòng của tôi</a></li>
        <li><a href="profile.html"      data-nav="profile">👤 Tài khoản</a></li>
        <li><a href="host-dashboard.html" data-nav="host">🔑 Chủ nhà</a></li>
      </ul>
    </nav>

  </div>
</header>`;

class SiteHeader extends HTMLElement {
  connectedCallback() {
    // innerHTML an toàn ở đây vì TEMPLATE là hằng số do ta viết.
    // Quy tắc: KHÔNG đưa dữ liệu người dùng nhập qua innerHTML.
    this.innerHTML = TEMPLATE;
    initHeader();   // bật/tắt phần Đăng nhập ↔ Tài khoản

    const active = this.getAttribute('active');
    if (active) this.querySelector(`[data-nav="${active}"]`)?.classList.add('is-active');

    // Menu mobile (< 768px)
    const toggle = this.querySelector('.nav-toggle');
    const nav = this.querySelector('#mainNav');
    toggle.addEventListener('click', () => {
      const open = nav.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', String(open));
    });
  }
}

customElements.define('site-header', SiteHeader);
