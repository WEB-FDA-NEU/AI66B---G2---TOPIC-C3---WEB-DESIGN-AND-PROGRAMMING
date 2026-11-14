(async () => {
  const checks = [];
  const check = (ok, label) => { if (!ok) throw Error('Home: ' + label); checks.push(label); };
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  if (location.pathname.endsWith('/search.html')) {
    if (new URLSearchParams(location.search).get('checkin') !== '2099-01-10') return checks;
    const assertStay = () => {
      const params = new URLSearchParams(location.search);
      check(params.get('checkin') === '2099-01-10' && params.get('checkout') === '2099-01-12' && params.get('guests') === '3', 'search keeps stay URL parameters');
      const link = new URL(document.querySelector('#results .card__link').href);
      check(link.searchParams.get('checkin') === '2099-01-10' && link.searchParams.get('checkout') === '2099-01-12' && link.searchParams.get('adults') === '3', 'detail links preserve dates and translate guests to adults');
    };
    assertStay();
    const sort = document.getElementById('sort');
    sort.value = 'price_asc'; sort.dispatchEvent(new Event('change'));
    for (let i = 0; i < 100 && !document.querySelector('#results .card'); i++) await wait(30);
    assertStay();
    check(!document.getElementById('stay-context').hidden, 'search displays stay context');
    return checks;
  }
  if (location.pathname.endsWith('/detail.html')) {
    if (new URLSearchParams(location.search).get('checkin') !== '2099-01-10') return checks;
    check(document.getElementById('stay-checkin').value === '2099-01-10' && document.getElementById('stay-checkout').value === '2099-01-12' && document.getElementById('stay-adults').value === '3', 'detail initializes stay from incoming URL');
    return checks;
  }
  if (!location.pathname.endsWith('/index.html')) return checks;
  const { getItems } = await import('./js/api.js');
  const { initHero, initRail } = await import('./js/components/home-carousels.js');
  const items = (await getItems({ sort: 'newest', page_size: 1000 })).items;
  const hero = document.getElementById('hero-carousel');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const current = () => Number(hero.dataset.index);
  check(hero.querySelectorAll('.hero-slide').length === 6, 'six data-driven hero slides');
  check(hero.querySelector('.is-active .hero-cta').href === hero.querySelector('.is-active .hero-image-link').href, 'image and CTA share correct detail link');
  const cards = [...document.querySelectorAll('.stay-rail .card__link')];
  check(new Set(cards.map(card => card.href)).size === cards.length && cards.length === items.length, 'homestay groups are disjoint and complete');
  check([...document.querySelectorAll('#top-rated .card__link')].every(card => items.find(item => String(item.id) === new URL(card.href).searchParams.get('id')).rating >= 4.5), 'top rated uses real scores');
  for (const destination of document.querySelectorAll('#destinations a')) {
    const q = new URL(destination.href).searchParams.get('q');
    const results = await getItems({ q });
    check(results.total > 0 && destination.querySelector('small').textContent.startsWith(String(results.total)), 'destination count and working search link');
  }
  let before = current();
  document.getElementById('hero-next').click();
  check(current() === (before + 1) % 6, 'next arrow');
  document.getElementById('hero-prev').click();
  check(current() === before, 'previous arrow');
  document.querySelectorAll('.hero-dot')[3].click();
  check(current() === 3 && document.querySelectorAll('.hero-slide:not(.is-active)[inert]').length === 5, 'dots and inactive slide accessibility');
  hero.dispatchEvent(new PointerEvent('pointerdown', { pointerType: 'touch', clientX: 240, clientY: 250, bubbles: true }));
  hero.dispatchEvent(new PointerEvent('pointerup', { pointerType: 'touch', clientX: 140, clientY: 255, bubbles: true }));
  check(current() === 4, 'horizontal touch gesture advances');
  hero.click(); // Consume the click suppressed after a swipe.
  hero.dispatchEvent(new PointerEvent('pointerdown', { pointerType: 'touch', clientX: 200, clientY: 250, bubbles: true }));
  hero.dispatchEvent(new PointerEvent('pointerup', { pointerType: 'touch', clientX: 205, clientY: 340, bubbles: true }));
  check(current() === 4, 'vertical scrolling does not change slides');
  const rail = document.getElementById('results');
  const previous = document.querySelector('[data-rail-prev="results"]');
  const next = document.querySelector('[data-rail-next="results"]');
  check(previous.disabled, 'rail previous disabled at start');
  if (rail.scrollWidth > rail.clientWidth + 2) {
    next.click(); await wait(700);
    check(rail.scrollLeft > 0 && !previous.disabled, 'rail next scrolls');
    rail.scrollTo({ left: rail.scrollWidth, behavior: 'instant' }); await wait(100);
    check(next.disabled, 'rail next disabled at end');
  } else check(next.disabled, 'short rail disables next');
  rail.scrollTo({ left: 0, behavior: 'instant' });
  // Verify rendering with one/zero items, then repeated initialization ownership.
  initHero(hero, [items[0]]);
  check(hero.querySelector('.hero-controls').hidden && document.getElementById('hero-pause').hidden, 'single slide hides controls');
  initHero(hero, []);
  check(hero.querySelectorAll('.hero-slide').length === 0 && hero.querySelector('.hero-controls').hidden, 'zero slides has no active timer/controls');
  initHero(hero, items.slice(0, 6));
  initHero(hero, items.slice(0, 6));
  document.getElementById('hero-next').click();
  check(current() === 1, 'reinitializing does not duplicate click handlers');
  initRail(rail); initRail(rail);
  // Every form test prevents navigation after capturing whether validation canceled it.
  const form = document.getElementById('searchForm');
  document.getElementById('checkin').value = '2099-01-10';
  document.getElementById('checkout').value = '2099-01-09';
  let valid = form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  check(!valid && !document.getElementById('searchError').hidden, 'invalid dates blocked');
  document.getElementById('checkout').value = '2099-01-12';
  document.getElementById('guests').value = '0';
  check(!form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })), 'zero guests blocked');
  document.getElementById('guests').value = '3';
  check(form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })), 'valid search accepted');
  document.getElementById('destination').value = items[0].location;
  const query = new URLSearchParams(new FormData(form));
  check(query.get('guests') === '3' && query.get('checkin') === '2099-01-10' && query.get('q') === items[0].location, 'GET form contains destination dates guests');
  initHero(hero, items.slice(0, 6));
  if (reduced) {
    check(!document.getElementById('hero-pause').disabled && hero.dataset.autoplayState === 'paused-reduced-motion', 'reduced motion pauses autoplay but offers explicit play');
    await wait(2200); check(current() === 0, 'reduced motion never auto advances');
    const control = document.getElementById('hero-pause');
    control.focus(); control.click();
    await wait(2200); check(current() === 1 && document.activeElement === control, 'explicit play works with reduced motion and retained button focus');
    check(getComputedStyle(hero.querySelector('.hero-slide')).transitionDuration === '0s', 'reduced motion still disables fade after opt-in');
    control.dispatchEvent(new PointerEvent('pointerdown', { pointerType: 'touch', bubbles: true }));
    control.click();
    before = current(); await wait(2200); check(current() === before && hero.dataset.autoplayState === 'paused-user', 'touch pause remains stopped');
  } else {
    await wait(2200); check(current() === 1, 'autoplay advances once after 2 seconds');
    hero.dispatchEvent(new PointerEvent('pointerenter', { pointerType: 'mouse' }));
    before = current(); await wait(2200); check(current() === before, 'hover pauses autoplay');
    hero.dispatchEvent(new PointerEvent('pointerleave', { pointerType: 'mouse' }));
    hero.querySelector('.is-active .hero-cta').focus();
    check(hero.contains(document.activeElement), 'CTA receives focus: ' + document.activeElement.tagName);
    before = current(); await wait(2200); check(current() === before, 'keyboard focus pauses autoplay');
    document.activeElement.blur();
    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    document.dispatchEvent(new Event('visibilitychange'));
    before = current(); await wait(2200); check(current() === before, 'visibility event pauses autoplay');
    delete document.hidden; document.dispatchEvent(new Event('visibilitychange'));
    document.getElementById('hero-next').click();
    before = current(); await wait(2200); check(current() === before, 'manual interaction stops autoplay');
    document.getElementById('hero-pause').focus();
    document.getElementById('hero-pause').click();
    await wait(2200); check(current() !== before && document.activeElement.id === 'hero-pause', 'explicit play resumes autoplay without moving focus');
  }
  // Give image failures time to resolve to the existing local placeholder.
  document.querySelectorAll('.home-page img').forEach(image => image.loading = 'eager');
  await Promise.race([Promise.all([...document.querySelectorAll('.home-page img')].map(img => img.decode().catch(() => {}))), wait(15000)]);
  check([...document.querySelectorAll('.home-page img')].filter(img => img.complete).every(img => img.naturalWidth > 0), 'loaded images have a valid image or fallback');
  checks.push('image fallbacks: ' + document.querySelectorAll('[data-fallback]').length);
  checks.push('images pending: ' + [...document.querySelectorAll('.home-page img')].filter(img => !img.complete).length);
  document.getElementById('hero-pause').click();
  scrollTo(0, 0);
  return checks;
})()
