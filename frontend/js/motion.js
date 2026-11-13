// Presentation only: never delay requests, DOM updates, focus or native dialog actions.
const preference = window.matchMedia('(prefers-reduced-motion: reduce)');
const running = new Set();
const active = new WeakMap();
export const prefersReducedMotion = () => preference.matches;
export const motionDuration = (speed = 'normal') =>
  parseFloat(getComputedStyle(document.documentElement).getPropertyValue(`--motion-${speed}`)) || 220;

function play(element, frames, options = {}) {
  if (!element?.isConnected || preference.matches || !element.animate) return;
  active.get(element)?.cancel();
  const animation = element.animate(frames, {
    duration: motionDuration(), easing: getComputedStyle(element).getPropertyValue('--ease-out').trim() || 'ease-out', ...options,
  });
  running.add(animation);
  active.set(element, animation);
  const done = () => running.delete(animation);
  animation.finished.then(done, done);
  return animation;
}

/** Cap initial staggering at six rows, even for hundreds of mock bookings. */
export function animateList(container, { initial = false } = {}) {
  if (!container || preference.matches) return;
  if (initial) {
    const stagger = parseFloat(getComputedStyle(container).getPropertyValue('--motion-stagger')) || 50;
    [...container.children].slice(0, 6).forEach((element, index) => play(element,
      [{ opacity: .65, transform: 'translateY(8px)' }, { opacity: 1, transform: 'translateY(0)' }],
      { duration: motionDuration('slow'), delay: index * stagger, fill: 'backwards' }));
  } else {
    // A single compositor animation, no per-row work or data delay when refiltering.
    play(container, [{ opacity: .75 }, { opacity: 1 }], { duration: 180 });
  }
}

export function animateStatus(element) {
  return play(element, [{ opacity: .4 }, { opacity: 1 }]);
}

preference.addEventListener('change', () => {
  if (preference.matches) [...running].forEach(animation => animation.cancel());
});

// Once-only scroll reveals. No pre-hidden classes: failure never leaves content blank.
const targets = document.querySelectorAll('[data-reveal]');
if (!preference.matches && targets.length && 'IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      play(entry.target, [{ opacity: .65, transform: 'translateY(8px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: motionDuration('slow') });
      observer.unobserve(entry.target);
    });
  }, { threshold: .12 });
  targets.forEach(element => observer.observe(element));
}

// Observe only small price/status regions, not the large host booking list.
const changed = new MutationObserver(records => {
  const elements = new Set();
  records.forEach(record => {
    const target = record.target.nodeType === Node.ELEMENT_NODE ? record.target : record.target.parentElement;
    const value = target.closest('#summary-total, #grandTotalVal, #bd-total');
    if (value) elements.add(value);
    const application = target.closest('#application-list [data-status="done"]');
    if (application) elements.add(application.querySelector('.badge'));
  });
  elements.forEach(animateStatus);
});
document.querySelectorAll('#summary-total, #grandTotalVal, #bd-total, #application-list')
  .forEach(element => changed.observe(element, { childList: true, subtree: true, ...(element.id === 'application-list' ? { attributes: true, attributeFilter: ['data-status'] } : {}) }));

document.addEventListener('load', event => {
  if (event.target.id === 'lb-img') animateStatus(event.target);
}, true);

let scheduled = false;
function headerShadow() {
  if (scheduled) return;
  scheduled = true;
  requestAnimationFrame(() => {
    document.querySelector('.site-header')?.classList.toggle('is-scrolled', window.scrollY > 8);
    scheduled = false;
  });
}
document.addEventListener('scroll', headerShadow, { passive: true });
headerShadow();
