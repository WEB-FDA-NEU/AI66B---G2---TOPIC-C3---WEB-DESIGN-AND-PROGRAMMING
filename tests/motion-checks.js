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
    const list = document.getElementById('list');
    const tab = status => document.querySelector(`#tabs [data-status="${status}"]`).click();
    check((await api.getHostBookings()).length === 0, 'mock host has no seeded bookings');
    const storedCustomerBookings = localStorage.getItem('customerBookings');
    try {
      const stays = await api.getHostHomestays();
      const rooms = await api.getHostRooms();
      const ownedStays = stays.filter(stay => stay.itemId != null).slice(0, 2);
      check(ownedStays.length === 2, 'mock host has owned catalog homestays');
      const ownRooms = ownedStays.map(stay =>
        rooms.find(room => String(room.homestayId) === String(stay.id) && room.itemRoomId != null));
      check(ownRooms.every(Boolean), 'owned mock homestays have catalog rooms');
      const fixtures = ownedStays.map((stay, index) => ({
        id: `motion-own-${index}`,
        userId: 1,
        homestayId: stay.itemId,
        status: 'pending',
        createdAt: '2026-01-01T10:00:00',
        guestName: 'Huy Test',
        guestEmail: 'huy@test.com',
        checkIn: '2026-02-01',
        checkOut: '2026-02-03',
        guests: 2,
        totalPrice: 200000,
        rooms: [{ key: ownRooms[index].itemRoomId, name: ownRooms[index].name, qty: 2 }],
      }));
      fixtures.push({
        ...fixtures[0],
        id: 'motion-foreign',
        homestayId: 'not-owned',
      });
      const previous = storedCustomerBookings ? JSON.parse(storedCustomerBookings) : [];
      localStorage.setItem('customerBookings', JSON.stringify([...previous, ...fixtures]));
      const hostBookings = await api.getHostBookings();
      const mapped = hostBookings.filter(booking => String(booking.id).startsWith('customer-motion-own-'));
      check(mapped.length === 2, 'host sees bookings for owned homestays and excludes other hosts');
      const first = mapped.find(booking => booking.id === 'customer-motion-own-0');
      check(first?.homestayName === ownedStays[0].name
        && first.roomId === ownRooms[0].id
        && first.roomName.includes('2 ×')
        && first.customerPhone,
      'customer booking maps its room, quantity, and customer details');
      await api.updateBookingStatus('customer-motion-own-0', 'confirmed');
      const updated = JSON.parse(localStorage.getItem('customerBookings'))
        .find(booking => booking.id === 'motion-own-0');
      check(updated?.status === 'confirmed', 'host status update is saved to customer booking');
    } finally {
      if (storedCustomerBookings === null) localStorage.removeItem('customerBookings');
      else localStorage.setItem('customerBookings', storedCustomerBookings);
    }
    for (const status of ['pending', 'confirmed', 'checked_in', 'completed', 'cancelled', 'rejected', '']) {
      tab(status);
      const animations = list.getAnimations();
      check(reduced ? !animations.length : animations.some(a => a.effect.getTiming().duration === 180), 'filter motion ' + (status || 'all'));
      check(document.querySelector('#tabs .is-active').dataset.status === status, 'active filter updates immediately');
    }
  }
  if (location.pathname.endsWith('/host-homestays.html')) {
    const api = await import('./js/api.js');
    const hostHomestays = await api.getHostHomestays();
    check(hostHomestays.length === 22 && hostHomestays.every(h => String(h.hostId) === 'host001'),
      'seeded homestays belong to the demo host');
    const storedUser = localStorage.getItem('app_user');
    const storedHomestays = localStorage.getItem('homestays');
    const storedRooms = localStorage.getItem('rooms');
    const storedBookings = localStorage.getItem('bookings');
    const storedCustomerBookings = localStorage.getItem('customerBookings');
    const storedVersion = localStorage.getItem('mock_version');
    const storedHostSeedVersion = localStorage.getItem('host_seed_version');
    try {
      localStorage.setItem('mock_version', '2026-11-14-host-seed-owner');
      localStorage.setItem('host_seed_version', '2026-11-14-no-host-samples');
      localStorage.setItem('homestays', JSON.stringify([
        { id: 'custom-hs', hostId: 'host001', name: 'Homestay tự tạo', status: 'active' },
      ]));
      localStorage.setItem('rooms', JSON.stringify([
        { id: 'custom-room', homestayId: 'custom-hs', name: 'Phòng tự tạo' },
      ]));
      localStorage.setItem('bookings', '[]');
      localStorage.setItem('customerBookings', '[]');
      const migratedApi = await import('./js/api.js?host-seed-migration-check');
      const restoredHomestays = await migratedApi.getHostHomestays();
      const restoredRooms = await migratedApi.getHostRooms();
      check(restoredHomestays.length === 23 && restoredHomestays.some(h => h.id === 'custom-hs'),
        'migration restores host seed homes and preserves custom homes');
      check(restoredRooms.length === 49 && restoredRooms.some(room => room.id === 'custom-room'),
        'migration restores host seed rooms and preserves custom rooms');

      localStorage.setItem('app_user', JSON.stringify({ id: 'new-host-test', role: 'host' }));
      localStorage.setItem('homestays', JSON.stringify([
        { id: 'hs001', hostId: 'host001', name: 'Homestay mẫu cũ', status: 'active' },
      ]));
      localStorage.setItem('rooms', JSON.stringify([
        { id: 'rm001', homestayId: 'hs001', name: 'Phòng mẫu cũ' },
      ]));
      check((await api.getHostHomestays()).length === 0, 'new mock host cannot see another host homestay');
      check((await api.getHostRooms()).length === 0, 'new mock host cannot see another host room');
      const created = await api.saveHostHomestay({ name: 'Homestay mới' });
      check(created.hostId === 'new-host-test', 'new mock homestay belongs to current host');
    } finally {
      if (storedUser === null) localStorage.removeItem('app_user'); else localStorage.setItem('app_user', storedUser);
      if (storedHomestays === null) localStorage.removeItem('homestays'); else localStorage.setItem('homestays', storedHomestays);
      if (storedRooms === null) localStorage.removeItem('rooms'); else localStorage.setItem('rooms', storedRooms);
      if (storedBookings === null) localStorage.removeItem('bookings'); else localStorage.setItem('bookings', storedBookings);
      if (storedCustomerBookings === null) localStorage.removeItem('customerBookings'); else localStorage.setItem('customerBookings', storedCustomerBookings);
      if (storedVersion === null) localStorage.removeItem('mock_version'); else localStorage.setItem('mock_version', storedVersion);
      if (storedHostSeedVersion === null) localStorage.removeItem('host_seed_version'); else localStorage.setItem('host_seed_version', storedHostSeedVersion);
    }
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
  if (location.pathname.endsWith('/admin.html')) {
    const api = await import('./js/api.js');
    const [overview, hosts] = await Promise.all([api.getAdminOverview(), api.getAdminHosts()]);
    check(overview.bookings.length === 0, 'admin overview has no seeded bookings');
    check(hosts.every(host => host.bookingCount === 0 && host.revenue === 0), 'admin hosts have no seeded booking revenue');
    await until(() => document.querySelector('#host-list .row__actions .btn'));
    document.querySelector('#host-list .row__actions .btn').click();
    const dialog = document.getElementById('host-dialog');
    const close = document.getElementById('hd-close-top');
    check(dialog.open, 'host detail dialog opens');
    const rect = close.getBoundingClientRect();
    const hit = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
    check(hit === close || close.contains(hit), 'top close control receives pointer input');
    close.click();
    check(!dialog.open, 'top close control closes host detail dialog');
  }
  await wait(700);
  check(document.getAnimations().every(a => a.effect.getTiming().iterations !== Infinity), 'no infinite animation');
  if (reduced) check(document.getAnimations().length === 0, 'reduced motion has no running animation');
  return checks;
})()
