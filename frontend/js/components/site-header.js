// ============================================================
// <site-header>
// Header dùng chung cho toàn bộ website Homestay Booking.
//
// Mỗi trang chỉ cần:
//
// <site-header active="home"></site-header>
//
// Giá trị active:
// home      -> Stays
// search    -> Homestays
// bookings  -> My bookings
// profile   -> Profile
// host      -> Property Management
//
// Chỉ sửa Header ở file này.
// Không tạo Header riêng trong từng HTML.
// ============================================================

import { initHeader } from '../auth.js';


// ============================================================
// HEADER TEMPLATE
// ============================================================

const TEMPLATE = /* html */ `

<header class="site-header">

  <div class="container">

    <!-- ======================================================
         HÀNG TRÊN
         Logo + VND + List your property + Register + Sign in
         ====================================================== -->

    <div class="site-header__top">

      <!-- LOGO -->
      <a
        class="logo"
        href="index.html">
        Homestay Booking
      </a>


      <!-- ====================================================
           CÁC NÚT BÊN PHẢI
           ==================================================== -->

      <div class="site-header__actions">

        <!-- Currency -->
        <span class="hide-sm">
          VND
        </span>


        <!-- Language -->
        <span class="hide-sm">
          🌐
        </span>


        <!-- List your property -->
        <a
          class="site-header__link hide-sm"
          href="host-dashboard.html">
          List your property
        </a>


        <!-- ==================================================
             KHÁCH CHƯA ĐĂNG NHẬP
             ================================================== -->

        <span data-auth="guest">

          <a
            class="btn btn--light"
            href="register.html">
            Register
          </a>

          <a
            class="btn btn--light"
            href="login.html">
            Sign in
          </a>

        </span>


        <!-- ==================================================
             USER ĐÃ ĐĂNG NHẬP
             ================================================== -->

        <span data-auth="user" hidden>

          <span
            class="hide-sm"
            data-user-name>
          </span>

          <a
            class="btn btn--light"
            href="#"
            data-action="logout">
            Sign out
          </a>

        </span>


        <!-- ==================================================
             MOBILE MENU
             ================================================== -->

        <button
          class="nav-toggle"
          type="button"
          aria-label="Mở menu"
          aria-expanded="false"
          aria-controls="mainNav">

          ☰

        </button>

      </div>

    </div>


    <!-- ======================================================
         THANH MENU CHÍNH
         ====================================================== -->

    <nav
      class="main-nav"
      id="mainNav"
      aria-label="Main navigation">

      <ul class="nav-links">


        <!-- ==================================================
             1. STAYS
             ================================================== -->

        <li>

          <a
            href="index.html"
            data-nav="home">

            🛏 Stays

          </a>

        </li>


        <!-- ==================================================
             2. HOMESTAYS
             File có thật trong project:
             host-homestays.html
             ================================================== -->

        <li>

          <a
            href="host-homestays.html"
            data-nav="search">

            🏠 Homestays

          </a>

        </li>


        <!-- ==================================================
             3. MY BOOKINGS
             ================================================== -->

        <li>

          <a
            href="booking-list.html"
            data-nav="bookings">

            📋 My bookings

          </a>

        </li>


        <!-- ==================================================
             4. PROFILE
             ================================================== -->

        <li>

          <a
            href="profile.html"
            data-nav="profile">

            👤 Profile

          </a>

        </li>


        <!-- ==================================================
             5. PROPERTY MANAGEMENT
             ================================================== -->

        <li>

          <a
            href="host-dashboard.html"
            data-nav="host">

            🏠 Property Management

          </a>

        </li>


      </ul>

    </nav>

  </div>

</header>

`;


// ============================================================
// SITE HEADER COMPONENT
// ============================================================

class SiteHeader extends HTMLElement {

  connectedCallback() {

    // --------------------------------------------------------
    // Hiển thị Header
    // --------------------------------------------------------

    this.innerHTML = TEMPLATE;


    // --------------------------------------------------------
    // Xử lý trạng thái đăng nhập
    //
    // Chưa đăng nhập:
    // Register | Sign in
    //
    // Đã đăng nhập:
    // Username | Sign out
    // --------------------------------------------------------

    initHeader();


    // --------------------------------------------------------
    // ACTIVE MENU
    //
    // Ví dụ:
    //
    // <site-header active="home"></site-header>
    //
    // sẽ làm Stays được highlight.
    // --------------------------------------------------------

    const active = this.getAttribute('active');

    if (active) {

      const activeNav = this.querySelector(
        `[data-nav="${active}"]`
      );

      if (activeNav) {

        activeNav.classList.add('is-active');

      }

    }


    // --------------------------------------------------------
    // MOBILE MENU
    // --------------------------------------------------------

    const toggle = this.querySelector('.nav-toggle');

    const nav = this.querySelector('#mainNav');


    if (toggle && nav) {

      toggle.addEventListener('click', () => {

        const open = nav.classList.toggle('is-open');

        toggle.setAttribute(
          'aria-expanded',
          String(open)
        );

      });

    }

  }

}


// ============================================================
// ĐĂNG KÝ CUSTOM ELEMENT
// ============================================================

customElements.define(
  'site-header',
  SiteHeader
);