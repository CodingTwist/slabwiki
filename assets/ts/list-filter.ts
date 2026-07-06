// Client-side filtering for list/directory pages (shops, tunnels, public
// resources). Each `[data-list-filter]` config element declares which search
// input, filterable items, and count/empty targets to wire up, plus an
// optional type <select> and optional group containers to collapse. Items are
// matched by substring against their `data-search` attribute, optionally
// narrowed by an exact `data-type` match. The `list-filter.html` partial emits
// one config element per list; this runs once for the whole page.
interface FilterConfig {
  input: string; // id of the search input
  items: string; // selector matching filterable elements (each with data-search)
  count?: string; // id of the visible-count element
  empty?: string; // id of the "no results" message element
  typeSelect?: string; // id of a <select> filtering via each item's data-type
  groups?: string; // selector for group containers to hide/show and auto-open
}

function initFilter(cfg: FilterConfig): void {
  const input = document.getElementById(cfg.input) as HTMLInputElement | null;
  if (!input) return;
  const typeSel = cfg.typeSelect
    ? (document.getElementById(cfg.typeSelect) as HTMLSelectElement | null)
    : null;
  const items = Array.from(document.querySelectorAll<HTMLElement>(cfg.items));
  const groups = cfg.groups ? Array.from(document.querySelectorAll<HTMLElement>(cfg.groups)) : [];
  const countEl = cfg.count ? document.getElementById(cfg.count) : null;
  const empty = cfg.empty ? document.getElementById(cfg.empty) : null;

  function apply(): void {
    const q = input!.value.trim().toLowerCase();
    const t = typeSel ? typeSel.value : '';
    let shown = 0;
    items.forEach((el) => {
      const hit =
        (!q || (el.getAttribute('data-search') || '').indexOf(q) !== -1) &&
        (!t || el.getAttribute('data-type') === t);
      el.style.display = hit ? '' : 'none';
      if (hit) shown++;
    });
    groups.forEach((g) => {
      const anyVisible = Array.from(g.querySelectorAll<HTMLElement>(cfg.items)).some(
        (el) => el.style.display !== 'none',
      );
      g.style.display = anyVisible ? '' : 'none';
      if (q && anyVisible && g instanceof HTMLDetailsElement) g.open = true;
    });
    if (countEl) countEl.textContent = String(shown);
    if (empty) empty.classList.toggle('hidden', shown > 0);
  }

  const initialQ = new URLSearchParams(location.search).get('q');
  if (initialQ) input.value = initialQ;
  input.addEventListener('input', apply);
  if (typeSel) typeSel.addEventListener('change', apply);
  apply();
}

document.querySelectorAll<HTMLElement>('[data-list-filter]').forEach((el) => {
  const { input, items, count, empty, typeSelect, groups } = el.dataset;
  if (!input || !items) return;
  initFilter({ input, items, count, empty, typeSelect, groups });
});
