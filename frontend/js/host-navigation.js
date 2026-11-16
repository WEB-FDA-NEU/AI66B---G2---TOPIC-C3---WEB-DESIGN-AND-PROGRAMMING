import { accountHref } from './config.js';

const DASHBOARD_SCROLL_KEY = 'hostDashboardScrollY';
const HOST_DESTINATIONS = new Set([
  'host-homestay-form.html',
  'host-homestays.html',
  'host-rooms.html',
  'host-bookings.html',
]);

function isPlainLeftClick(event) {
  return event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;
}

export function initHostDashboardNavigation() {
  const normalizeLink = link => {
    const destination = new URL(link.href, location.href);
    if (destination.origin !== location.origin || !HOST_DESTINATIONS.has(destination.pathname.split('/').pop())) return;
    link.href = accountHref(`${destination.pathname}${destination.search}${destination.hash}`);
  };
  document.querySelectorAll('a[href]').forEach(normalizeLink);
  document.addEventListener('click', event => {
    if (event.defaultPrevented || !isPlainLeftClick(event)) return;
    const link = event.target instanceof Element ? event.target.closest('a[href]') : null;
    if (!link) return;
    const destination = new URL(link.href, location.href);
    if (destination.origin !== location.origin || !HOST_DESTINATIONS.has(destination.pathname.split('/').pop())) return;
    const state = history.state && typeof history.state === 'object' ? history.state : {};
    history.replaceState({ ...state, [DASHBOARD_SCROLL_KEY]: window.scrollY }, '');
  });

  const restoreScroll = () => {
    const state = history.state;
    if (!state || !Number.isFinite(state[DASHBOARD_SCROLL_KEY])) return;

    const scrollY = state[DASHBOARD_SCROLL_KEY];
    const nextState = { ...state };
    delete nextState[DASHBOARD_SCROLL_KEY];
    history.replaceState(nextState, '');
    requestAnimationFrame(() => requestAnimationFrame(() => window.scrollTo(0, scrollY)));
  };

  window.addEventListener('host-dashboard-ready', restoreScroll, { once: true });
  window.addEventListener('pageshow', event => {
    if (event.persisted) restoreScroll();
  });
}

export function initHostDashboardReturn() {
  const link = document.querySelector('[data-host-dashboard-return]');
  if (!link) return;

  let previousPage;
  try {
    previousPage = new URL(document.referrer);
  } catch {
    return;
  }

  const dashboardPath = new URL(accountHref('host-dashboard.html'), location.href).pathname;
  if (previousPage.origin !== location.origin || previousPage.pathname !== dashboardPath) return;

  link.href = accountHref(`${previousPage.pathname}${previousPage.search}${previousPage.hash}`);
  link.hidden = false;
  link.addEventListener('click', event => {
    if (event.defaultPrevented || !isPlainLeftClick(event) || history.length < 2) return;
    event.preventDefault();
    history.back();
  });
}
