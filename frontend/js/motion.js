
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// ---------- Tiêu đề hero: tách từng từ để chữ "cuộn" lên lần lượt ----------
// Nếu không chạy được (lỗi JS) thì thẻ h1 giữ nguyên văn bản thường, không mất chữ.
function initHeroWords(hero) {
  const h1 = hero.querySelector('h1');
  if (!h1 || h1.dataset.wordReady) return;
  const text = h1.textContent.trim();
  if (!text) return;
  h1.dataset.wordReady = 'true';
  h1.setAttribute('aria-label', text);
  h1.textContent = '';
  text.split(' ').forEach((word, i) => {
    if (i) h1.appendChild(document.createTextNode(' '));
    const mask = document.createElement('span');
    mask.className = 'word-mask';
    mask.setAttribute('aria-hidden', 'true');
    const inner = document.createElement('span');
    inner.className = 'word';
    inner.textContent = word;
    inner.style.setProperty('--wd', (i * 70) + 'ms');
    mask.appendChild(inner);
    h1.appendChild(mask);
  });
  h1.classList.add('word-reveal');
}

// ---------- Hero: chữ + ô tìm kiếm xuất hiện tuần tự, chạy 1 lần lúc tải trang ----------
function initHero() {
  const hero = document.querySelector('.hero__inner');
  if (!hero || reduceMotion) return;
  initHeroWords(hero);
  hero.classList.add('hero-init');
  // 2 lần requestAnimationFrame để trình duyệt kịp "sơn" trạng thái ẩn
  // trước khi bật is-ready, tránh bị giật/nhảy khung hình đầu tiên.
  requestAnimationFrame(() => requestAnimationFrame(() => hero.classList.add('is-ready')));
}

// ---------- Section cuộn tới đâu, hiện tới đó ----------
function initReveal() {
  const targets = document.querySelectorAll('[data-reveal]');
  if (!targets.length || reduceMotion || !('IntersectionObserver' in window)) return;

  targets.forEach(el => el.classList.add('reveal-init'));

  const io = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      entry.target.classList.add('is-visible');
      io.unobserve(entry.target);
    });
  }, { threshold: .15, rootMargin: '0px 0px -40px 0px' });

  targets.forEach(el => io.observe(el));
}

// ---------- Header: đổ bóng khi trang cuộn xuống ----------
function initHeaderShadow() {
  let header = null;
  const check = () => {
    header ??= document.querySelector('.site-header');
    if (!header) return;
    header.classList.toggle('is-scrolled', window.scrollY > 8);
  };
  document.addEventListener('scroll', check, { passive: true });
  check();
}

initHero();
initReveal();
initHeaderShadow();