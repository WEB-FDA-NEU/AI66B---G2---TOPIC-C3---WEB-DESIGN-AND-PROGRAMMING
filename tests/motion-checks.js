// Executed by ui-browser.py in an isolated browser profile, never user storage.
(async () => {
  const checks = [];
  const check = (ok, name) => { if (!ok) throw Error('Motion: ' + name); checks.push(name); };
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  const until = async predicate => {
    for (let i = 0; i < 100; i++) { if (await predicate()) return; await wait(30); }
    throw Error('Motion: action did not complete');
  };
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const motion = await import('./js/motion.js');
  check(motion.motionDuration('fast') === 140 && motion.motionDuration() === 220 && motion.motionDuration('slow') === 360, 'shared duration tokens');
  if (location.pathname.endsWith('/host-bookings.html')) {
    const api = await import('./js/api.js');
    const original = localStorage.getItem('bookings');
    const list = document.getElementById('list');
    const tab = status => document.querySelector(`#tabs [data-status="${status}"]`).click();
    for (const status of ['pending', 'confirmed', 'checked_in', 'completed', 'cancelled', 'rejected', '']) {
      tab(status);
      const animations = list.getAnimations();
      check(reduced ? !animations.length : animations.some(a => a.effect.getTiming().duration === 180), 'filter motion ' + (status || 'all'));
      check(document.querySelector('#tabs .is-active').dataset.status === status, 'active filter updates immediately');
    }
    const act = async (before, after) => {
      const booking = (await api.getHostBookings()).find(b => b.status === before);
      check(!!booking, 'fixture exists ' + before);
      const button = document.querySelector(`[data-act="${booking.id}:${after}"]`);
      button.click(); button.click();
      check(button.disabled, 'pending action blocks repeated click');
      await until(() => !button.isConnected);
      check((await api.getHostBookings()).find(b => b.id === booking.id).status === after, 'booking saved ' + after);
      check(document.getElementById('toast').classList.contains('is-visible'), 'status toast visible');
      const badges = [...list.querySelectorAll('.badge')];
      check(reduced ? badges.every(b => !b.getAnimations().length) : badges.some(b => b.getAnimations().length), 'changed badge respects motion preference');
    };
    await act('pending', 'confirmed');
    await act('confirmed', 'checked_in');
    await act('checked_in', 'completed');
    const pending = (await api.getHostBookings()).find(b => b.status === 'pending');
    const opener = document.querySelector(`[data-reject="${pending.id}"]`);
    opener.focus(); opener.click();
    const dialog = document.getElementById('reject-dialog');
    check(dialog.open && dialog.contains(document.activeElement), 'native modal owns focus');
    document.getElementById('rejectConfirm').click();
    check(document.getElementById('rejectErr').textContent.length > 0, 'rejection validation retained');
    document.getElementById('rejectReason').value = 'Motion browser test';
    const confirm = document.getElementById('rejectConfirm');
    confirm.click(); confirm.click();
    check(confirm.disabled, 'rejection blocks repeated click');
    await until(() => !opener.isConnected);
    check(!dialog.open, 'rejection modal closes');
    check((await api.getHostBookings()).find(b => b.id === pending.id).status === 'rejected', 'rejection saved');
    localStorage.setItem('bookings', original);
  }
  if (location.pathname.endsWith('/detail.html')) {
    document.querySelector('.photo-grid__cell').click();
    await wait(400);
    const dialog = document.getElementById('lightbox');
    const height = dialog.getBoundingClientRect().height;
    document.getElementById('lb-next').click();
    await wait(400);
    check(Math.abs(height - dialog.getBoundingClientRect().height) < 1, 'gallery keeps stable height');
    document.getElementById('lb-close').click();
  }
  await wait(700);
  check(document.getAnimations().every(a => a.effect.getTiming().iterations !== Infinity), 'no infinite animation');
  if (reduced) check(document.getAnimations().length === 0, 'reduced motion has no running animation');
  return checks;
})()
