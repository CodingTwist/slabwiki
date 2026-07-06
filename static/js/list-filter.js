"use strict";
function initFilter(cfg) {
    const input = document.getElementById(cfg.input);
    if (!input)
        return;
    const typeSel = cfg.typeSelect
        ? document.getElementById(cfg.typeSelect)
        : null;
    const items = Array.from(document.querySelectorAll(cfg.items));
    const groups = cfg.groups ? Array.from(document.querySelectorAll(cfg.groups)) : [];
    const countEl = cfg.count ? document.getElementById(cfg.count) : null;
    const empty = cfg.empty ? document.getElementById(cfg.empty) : null;
    function apply() {
        const q = input.value.trim().toLowerCase();
        const t = typeSel ? typeSel.value : '';
        let shown = 0;
        items.forEach((el) => {
            const hit = (!q || (el.getAttribute('data-search') || '').indexOf(q) !== -1) &&
                (!t || el.getAttribute('data-type') === t);
            el.style.display = hit ? '' : 'none';
            if (hit)
                shown++;
        });
        groups.forEach((g) => {
            const anyVisible = Array.from(g.querySelectorAll(cfg.items)).some((el) => el.style.display !== 'none');
            g.style.display = anyVisible ? '' : 'none';
            if (q && anyVisible && g instanceof HTMLDetailsElement)
                g.open = true;
        });
        if (countEl)
            countEl.textContent = String(shown);
        if (empty)
            empty.classList.toggle('hidden', shown > 0);
    }
    const initialQ = new URLSearchParams(location.search).get('q');
    if (initialQ)
        input.value = initialQ;
    input.addEventListener('input', apply);
    if (typeSel)
        typeSel.addEventListener('change', apply);
    apply();
}
document.querySelectorAll('[data-list-filter]').forEach((el) => {
    const { input, items, count, empty, typeSelect, groups } = el.dataset;
    if (!input || !items)
        return;
    initFilter({ input, items, count, empty, typeSelect, groups });
});
