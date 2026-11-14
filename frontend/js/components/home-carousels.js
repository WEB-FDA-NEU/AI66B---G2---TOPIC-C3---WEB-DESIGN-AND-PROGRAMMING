import { formatVND } from '../render.js';
import { accountHref } from '../config.js';
import { prefersReducedMotion } from '../motion.js';

const controllers = new WeakMap();
const imageURL = value => {
  try { const url = new URL(value, location.href); return ['http:', 'https:'].includes(url.protocol) ? url.href : null; }
  catch { return null; }
};
export const hasCover = item => !!item.cover_url && !!imageURL(item.cover_url);
export function imageFallback(image) {
  image.addEventListener('error', () => {
    if (image.dataset.fallback) return;
    image.dataset.fallback = 'true';
    image.src = 'img/placeholder.svg';
  });
}

/** A single owned timeout; reinitialization always disposes the previous controller. */
export function initHero(root, items) {
  controllers.get(root)?.();
  const abort = new AbortController();
  const on = (target, type, listener) => target.addEventListener(type, listener, { signal: abort.signal });
  const preference = matchMedia('(prefers-reduced-motion: reduce)');
  const slides = root.querySelector('#hero-slides');
  const dots = root.querySelector('#hero-dots');
  const pause = root.querySelector('#hero-pause');
  const controls = root.querySelector('.hero-controls');
  let index = 0, timer = null, userPaused = false, hovered = false, disposed = false;
  let reducedMotionOptIn = false, explicitResume = false;
  slides.replaceChildren(); dots.replaceChildren();
  const nodes = items.map((item, i) => {
    const node = document.getElementById('tpl-hero-slide').content.cloneNode(true);
    const article = node.querySelector('article');
    article.setAttribute('aria-label', `${i + 1} / ${items.length}`);
    article.dataset.id = item.id;
    const href = accountHref(`detail.html?id=${encodeURIComponent(item.id)}`);
    node.querySelectorAll('a').forEach(a => a.href = href);
    node.querySelector('.hero-cta').setAttribute('aria-label', `Khám phá ${item.title}`);
    const image = node.querySelector('img');
    imageFallback(image);
    image.src = imageURL(item.cover_url);
    image.loading = 'eager'; // Preload the small, capped set for flicker-free fades.
    image.fetchPriority = i === 0 ? 'high' : 'low';
    node.querySelector('h2').textContent = item.title;
    node.querySelector('.hero-location').textContent = item.location;
    const price = node.querySelector('.hero-price');
    price.textContent = formatVND(item.price);
    const perNight = document.createElement('small');
    perNight.textContent = ' / đêm'; price.append(perNight);
    slides.append(node);
    const dot = document.createElement('button');
    dot.type = 'button'; dot.className = 'hero-dot';
    dot.setAttribute('aria-label', `Xem ${item.title}, ${i + 1} / ${items.length}`);
    on(dot, 'click', () => move(i, true));
    dots.append(dot);
    return article;
  });
  function stop() { clearTimeout(timer); timer = null; }
  const motionPaused = () => preference.matches && !reducedMotionOptIn;
  const focusPaused = () => root.contains(document.activeElement) && !(explicitResume && document.activeElement === pause);
  const hoverPaused = () => hovered && !(explicitResume && pause.matches(':hover'));
  const canPlay = () => nodes.length > 1 && !userPaused && !motionPaused() && !hoverPaused() && !focusPaused() && !document.hidden;
  function schedule() {
    stop();
    if (disposed) return;
    const paused = userPaused || motionPaused();
    pause.disabled = false;
    pause.textContent = paused ? 'Bật tự chuyển' : 'Tạm dừng';
    pause.setAttribute('aria-label', paused ? 'Bật tự chuyển homestay' : 'Tạm dừng tự chuyển');
    pause.setAttribute('aria-pressed', String(paused));
    root.dataset.autoplayState = nodes.length < 2 ? 'single' : document.hidden ? 'hidden' : userPaused ? 'paused-user' : motionPaused() ? 'paused-reduced-motion' : focusPaused() ? 'paused-focus' : hoverPaused() ? 'paused-hover' : 'running';
    pause.title = motionPaused() ? 'Đang tắt theo cài đặt giảm chuyển động. Bạn có thể chủ động bật tự chuyển; hiệu ứng chuyển động vẫn tắt.'
      : root.dataset.autoplayState === 'paused-focus' ? 'Tự chuyển đang tạm dừng khi bạn thao tác bằng bàn phím trong banner.'
      : root.dataset.autoplayState === 'paused-hover' ? 'Di chuyển chuột ra ngoài banner để tiếp tục tự chuyển.'
      : paused ? 'Bật tự chuyển sau mỗi 2 giây.' : 'Tạm dừng tự chuyển homestay.';
    if (canPlay()) timer = setTimeout(() => {
      timer = null;
      // Recheck at execution too: focus/visibility events can be throttled in background tabs.
      if (canPlay()) move(index + 1);
      else schedule();
    }, 2000);
  }
  function move(next, manual = false) {
    if (!nodes.length) return;
    index = (next + nodes.length) % nodes.length;
    if (manual) { userPaused = true; explicitResume = false; }
    nodes.forEach((node, i) => {
      const active = i === index;
      node.classList.toggle('is-active', active);
      node.inert = !active;
      node.setAttribute('aria-hidden', String(!active));
      dots.children[i].setAttribute('aria-current', String(active));
    });
    root.dataset.index = index;
    if (manual) root.querySelector('#hero-status').textContent = `${index + 1} / ${nodes.length}: ${items[index].title}`;
    schedule();
  }
  controls.hidden = nodes.length < 2;
  pause.hidden = nodes.length < 2;
  on(root.querySelector('#hero-prev'), 'click', () => move(index - 1, true));
  on(root.querySelector('#hero-next'), 'click', () => move(index + 1, true));
  on(pause, 'click', () => {
    if (userPaused || motionPaused()) {
      userPaused = false;
      reducedMotionOptIn = preference.matches;
      explicitResume = true;
    } else { userPaused = true; explicitResume = false; }
    schedule();
  });
  on(root, 'pointerenter', event => { if (event.pointerType !== 'touch') { hovered = true; schedule(); } });
  on(root, 'pointerleave', () => { hovered = false; schedule(); });
  on(root, 'focusin', schedule);
  on(root, 'focusout', () => queueMicrotask(schedule));
  on(document, 'visibilitychange', schedule);
  on(preference, 'change', () => { reducedMotionOptIn = false; explicitResume = false; schedule(); });
  let start = null;
  on(root, 'pointerdown', event => {
    if (event.pointerType !== 'touch') return;
    if (event.target.closest('#hero-pause')) return;
    start = { x: event.clientX, y: event.clientY };
    userPaused = true; explicitResume = false; schedule();
  });
  let suppressClickUntil = 0;
  on(root, 'pointerup', event => {
    if (!start) return;
    const dx = event.clientX - start.x, dy = event.clientY - start.y;
    start = null;
    if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy)) { suppressClickUntil = performance.now() + 350; move(index + (dx < 0 ? 1 : -1), true); }
  });
  on(root, 'pointercancel', () => { start = null; });
  root.addEventListener('click', event => {
    if (performance.now() < suppressClickUntil) event.preventDefault();
    suppressClickUntil = 0;
  }, { capture: true, signal: abort.signal });
  const dispose = () => { disposed = true; stop(); abort.abort(); controllers.delete(root); };
  controllers.set(root, dispose);
  on(window, 'pagehide', stop);
  on(window, 'pageshow', schedule);
  if (nodes.length) move(0);
  return dispose;
}

export function initRail(rail) {
  controllers.get(rail)?.();
  const abort = new AbortController();
  const previous = document.querySelector(`[data-rail-prev="${rail.id}"]`);
  const next = document.querySelector(`[data-rail-next="${rail.id}"]`);
  function update() {
    previous.disabled = rail.scrollLeft <= 2;
    next.disabled = rail.scrollLeft + rail.clientWidth >= rail.scrollWidth - 2;
  }
  function move(direction) {
    const step = (rail.firstElementChild?.getBoundingClientRect().width || rail.clientWidth) + parseFloat(getComputedStyle(rail).columnGap || 0);
    rail.scrollBy({ left: direction * step, behavior: prefersReducedMotion() ? 'instant' : 'smooth' });
  }
  previous.addEventListener('click', () => move(-1), { signal: abort.signal });
  next.addEventListener('click', () => move(1), { signal: abort.signal });
  rail.addEventListener('scroll', update, { passive: true, signal: abort.signal });
  rail.addEventListener('keydown', event => {
    if (event.target !== rail || !['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault(); move(event.key === 'ArrowLeft' ? -1 : 1);
  }, { signal: abort.signal });
  const observer = new ResizeObserver(update);
  observer.observe(rail);
  const dispose = () => { abort.abort(); observer.disconnect(); controllers.delete(rail); };
  controllers.set(rail, dispose);
  update();
  return dispose;
}
