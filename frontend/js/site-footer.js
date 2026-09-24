// ============================================================
//  <site-footer> — footer dùng chung. Mỗi trang: <site-footer></site-footer>
// ============================================================
const YEAR = new Date().getFullYear();

const TEMPLATE = /* html */ `
<footer class="site-footer">
  <div class="container site-footer__grid">

    <div class="site-footer__brand">
      <p class="logo">Homestay Booking</p>
      <p class="site-footer__tagline">Tìm homestay phù hợp và đặt phòng trực tuyến dễ dàng.</p>
    </div>

    <nav class="site-footer__col" aria-labelledby="ft-guest">
      <h3 class="site-footer__title" id="ft-guest">Khách hàng</h3>
      <ul>
        <li><a href="search.html">Tìm homestay</a></li>
        <li><a href="booking-list.html">Đặt phòng của tôi</a></li>
        <li><a href="profile.html">Tài khoản</a></li>
      </ul>
    </nav>

    <nav class="site-footer__col" aria-labelledby="ft-host">
      <h3 class="site-footer__title" id="ft-host">Chủ nhà</h3>
      <ul>
        <li><a href="host-dashboard.html">Bảng điều khiển</a></li>
        <li><a href="host-homestays.html">Quản lý homestay</a></li>
        <li><a href="host-rooms.html">Quản lý phòng</a></li>
      </ul>
    </nav>

    <nav class="site-footer__col" aria-labelledby="ft-about">
      <h3 class="site-footer__title" id="ft-about">Về chúng tôi</h3>
      <ul>
        <li><a href="#">Giới thiệu</a></li>
        <li><a href="#">Điều khoản</a></li>
        <li><a href="#">Liên hệ</a></li>
      </ul>
    </nav>

  </div>

  <div class="container site-footer__bottom">
    <p>© ${YEAR} Homestay Booking — Đồ án Web Design &amp; Programming, lớp AI66B, National Economics University.</p>
  </div>
</footer>`;

class SiteFooter extends HTMLElement {
  connectedCallback() { this.innerHTML = TEMPLATE; }   // hằng số do ta viết → an toàn
}

customElements.define('site-footer', SiteFooter);
