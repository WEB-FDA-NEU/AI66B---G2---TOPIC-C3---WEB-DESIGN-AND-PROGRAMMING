import { getItems } from '../api.js';
import { renderCard, renderList } from '../render.js';
import { todayISO, addDays, parseISO, toISO } from '../pricing.js';
import { showSkeleton, showEmpty, showError } from '../ui.js';
import { initHero, initRail, hasCover, imageFallback } from '../components/home-carousels.js';
import '../components/site-header.js';
import '../components/site-footer.js';

const $ = id => document.getElementById(id);
const form = $('searchForm');
$('checkin').min = $('checkout').min = todayISO();
$('checkin').addEventListener('change', () => {
  $('checkout').min = $('checkin').value ? toISO(addDays(parseISO($('checkin').value), 1)) : todayISO();
});
form.addEventListener('submit', event => {
  const ci = $('checkin').value, co = $('checkout').value;
  const guests = Number($('guests').value);
  const message = ((ci || co) && !(ci && co)) ? 'Vui lòng chọn cả ngày nhận và trả phòng.'
    : ci && (ci < todayISO() || co <= ci) ? 'Ngày trả phòng phải sau ngày nhận phòng; ngày nhận không được ở quá khứ.'
    : !Number.isInteger(guests) || guests < 1 || guests > 10 ? 'Vui lòng chọn từ 1 đến 10 khách.' : '';
  $('searchError').textContent = message; $('searchError').hidden = !message;
  if (message) event.preventDefault();
});

let dispose = [];
function renderGroup(id, items) {
  const rail = $(id);
  rail.closest('[data-home-section]').hidden = !items.length;
  if (!items.length) return;
  renderList(rail, items, renderCard);
  dispose.push(initRail(rail));
}
function renderDestinations(items) {
  const groups = new Map();
  items.forEach(item => {
    const parts = item.location.split(',').map(part => part.trim()).filter(Boolean);
    const name = parts.length > 2 ? parts.at(-2) : parts.at(-1);
    if (!groups.has(name)) groups.set(name, { name, item, count: 0 });
    groups.get(name).count++;
  });
  $('destinations-list').replaceChildren(...[...groups.keys()].map(name => {
    const option = document.createElement('option'); option.value = name; return option;
  }));
  const nodes = [...groups.values()].sort((a, b) => b.count - a.count).slice(0, 6).map(({ name, item, count }) => {
    const node = $('tpl-destination').content.cloneNode(true);
    node.querySelector('a').href = `search.html?${new URLSearchParams({ q: name })}`;
    const image = node.querySelector('img'); imageFallback(image); image.src = item.cover_url;
    node.querySelector('strong').textContent = name;
    node.querySelector('small').textContent = `${count} homestay`;
    return node;
  });
  $('destinations').replaceChildren(...nodes);
  $('destinations').closest('section').hidden = !nodes.length;
}

async function load() {
  dispose.forEach(stop => stop()); dispose = [];
  showSkeleton($('results'), 4);
  try {
    // Request all current listings through the existing API, not a parallel JSON source.
    const { items } = await getItems({ sort: 'newest', page_size: 1000 });
    const usable = items.filter(item => item.status === 'active' && item.title && item.location && Number.isFinite(item.price) && item.price >= 0 && hasCover(item));
    if (!usable.length) {
      $('hero-slides').replaceChildren();
      showEmpty($('hero-slides'), { title: 'Chưa có homestay', hint: 'Hãy quay lại sau.', actionText: 'Tìm homestay', actionHref: 'search.html' });
      showEmpty($('results'), { title: 'Chưa có homestay', hint: 'Hãy quay lại sau.', actionText: 'Tìm homestay', actionHref: 'search.html' });
      renderDestinations([]);
      return;
    }
    const rated = item => Number.isFinite(item.rating) && item.rating >= 4.5 && item.rating <= 5;
    const hero = [...usable].sort((a, b) => (b.rating ?? 0) - (a.rating ?? 0)).slice(0, 6);
    dispose.push(initHero($('hero-carousel'), hero));
    renderDestinations(usable);
    const featured = usable.slice(0, 4);
    const used = new Set(featured.map(item => item.id));
    const top = usable.filter(item => !used.has(item.id) && rated(item)).sort((a, b) => b.rating - a.rating).slice(0, 4);
    top.forEach(item => used.add(item.id));
    renderGroup('results', featured);
    renderGroup('top-rated', top);
    renderGroup('explore', usable.filter(item => !used.has(item.id)).slice(0, 8));
  } catch (error) {
    $('hero-slides').replaceChildren();
    showError($('hero-slides'), error, load);
    showError($('results'), error, load);
  }
}
load();
