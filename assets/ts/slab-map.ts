/// <reference types="leaflet" />

// Renders one Leaflet map per `.slab-map` element on the page. Tile servers
// are Pl3xMap instances, one per Survival season, each exposing three worlds
// (overworld / nether / end) that share a base name with `_nether` /
// `_the_end` suffixes. CRS.Simple maps a Minecraft world coordinate (x, z)
// 1:1 onto Leaflet's (lng, lat).
interface SlabMapMarker {
  t: string; // title
  u: string; // link (page URL)
  x: number;
  z: number;
}

type Dimension = 'overworld' | 'nether' | 'the_end';

const DIMENSION_SUFFIX: Record<Dimension, string> = {
  overworld: '',
  nether: '_nether',
  the_end: '_the_end',
};

const DIMENSION_LABEL: Record<Dimension, string> = {
  overworld: 'Overworld',
  nether: 'Nether',
  the_end: 'The End',
};

const SCALE_FACTOR = 0.0625; // matches Pl3xMap's default world-to-pixel ratio

function worldToLatLng(x: number, z: number): L.LatLngTuple {
  return [z, x];
}

function initMap(el: HTMLElement): void {
  const tilesBase = el.dataset.tilesBase;
  const world = el.dataset.world;
  if (!tilesBase || !world) return;

  const mini = el.dataset.mini === 'true';
  const autofit = el.dataset.autofit === 'true';
  const zoom = Number(el.dataset.zoom || 4);
  const detailZoom = Number(el.dataset.detailZoom || 7);
  const [cx, cz] = (el.dataset.center || '0,0').split(',').map(Number);
  const markers: SlabMapMarker[] = el.dataset.markers ? JSON.parse(el.dataset.markers) : [];

  const params = new URLSearchParams(window.location.search);
  const qx = params.has('x') ? Number(params.get('x')) : null;
  const qz = params.has('z') ? Number(params.get('z')) : null;

  const focusAttr = el.dataset.focus;
  const [fx, fz] = focusAttr ? focusAttr.split(',').map(Number) : [NaN, NaN];
  const hasFocus = mini && !Number.isNaN(fx) && !Number.isNaN(fz);

  const crs = L.Util.extend({}, L.CRS.Simple, {
    transformation: new L.Transformation(SCALE_FACTOR, 0, SCALE_FACTOR, 0),
  }) as L.CRS;

  const initialCenter = hasFocus ? worldToLatLng(fx, fz) : worldToLatLng(qx ?? cx, qz ?? cz);
  const initialZoom = mini ? detailZoom : qx !== null ? Math.max(zoom, detailZoom) : zoom;

  const map = L.map(el, {
    crs,
    preferCanvas: true,
    zoomSnap: autofit ? 0 : 1,
    zoomControl: !mini,
    dragging: !mini,
    scrollWheelZoom: !mini,
    doubleClickZoom: !mini,
    boxZoom: !mini,
    keyboard: !mini,
    touchZoom: !mini,
  }).setView(initialCenter, initialZoom, { animate: false });

  const tileUrl = (dim: Dimension) =>
    `${tilesBase}/${encodeURIComponent(world + DIMENSION_SUFFIX[dim])}/{z}/vanilla/{x}_{y}.png`;

  let currentLayer: L.TileLayer | null = null;
  function setDimension(dim: Dimension): void {
    if (currentLayer) map.removeLayer(currentLayer);
    currentLayer = L.tileLayer(tileUrl(dim), {
      tileSize: 512,
      noWrap: true,
      minNativeZoom: 0,
      maxNativeZoom: 4,
      maxZoom: 8,
      zoomOffset: -4,
      zoomReverse: true,
      tms: true,
      attribution: '<a href="https://modrinth.com/plugin/pl3xmap/">Pl3xMap</a>',
    }).addTo(map);
  }
  setDimension('overworld');

  L.control.scale({ imperial: false }).addTo(map);

  if (!mini) {
    const DimensionControl = L.Control.extend({
      onAdd(): HTMLElement {
        const wrap = L.DomUtil.create('div', 'leaflet-bar slab-dimension-control');
        L.DomEvent.disableClickPropagation(wrap);
        (Object.keys(DIMENSION_SUFFIX) as Dimension[]).forEach((dim) => {
          const btn = L.DomUtil.create('a', '', wrap);
          btn.href = '#';
          btn.textContent = DIMENSION_LABEL[dim];
          if (dim === 'overworld') btn.classList.add('active');
          L.DomEvent.on(btn, 'click', (e: Event) => {
            L.DomEvent.preventDefault(e);
            wrap.querySelectorAll('a').forEach((a) => a.classList.remove('active'));
            btn.classList.add('active');
            setDimension(dim);
          });
        });
        return wrap;
      },
    });
    new DimensionControl({ position: 'topright' }).addTo(map);
  }

  markers.forEach((m) => {
    const marker = L.marker(worldToLatLng(m.x, m.z)).addTo(map);
    if (!mini) {
      const label = m.u ? `<a href="${m.u}">${m.t}</a>` : m.t;
      marker.bindPopup(`${label}<br><span class="text-faint">${m.x}, ${m.z}</span>`);
    }
  });

  // getBoundsZoom degenerates to maxZoom if the container is still
  // display:none (e.g. a collapsed toggle) when this runs, since it measures
  // a 0x0 viewport - only autofit once the container has real dimensions.
  function applyAutofit(): void {
    if (!autofit || qx !== null || !markers.length) return;
    map.stop();
    map.invalidateSize({ animate: false });
    const bounds = L.latLngBounds(markers.map((m) => worldToLatLng(m.x, m.z)));
    map.fitBounds(bounds, { padding: [4, 4], animate: false });
  }

  if (el.offsetParent !== null) applyAutofit();

  if (!mini && qx !== null && qz !== null) {
    L.marker(worldToLatLng(qx, qz), { title: 'Location' })
      .addTo(map)
      .bindPopup(`${qx}, ${qz}`)
      .openPopup();
  }

  if (!mini) {
    map.on('click', (e: L.LeafletMouseEvent) => {
      const x = Math.round(e.latlng.lng);
      const z = Math.round(e.latlng.lat);
      navigator.clipboard && navigator.clipboard.writeText(`${x} ${z}`);
    });
  }

  // Maps rendered inside a collapsed <details>/toggle section start out
  // display:none, so Leaflet measures a 0x0 viewport and only loads one
  // tile (and getBoundsZoom degenerates for autofit). Re-measure once the
  // container becomes visible.
  if (el.offsetParent === null) {
    const observer = new MutationObserver(() => {
      if (el.offsetParent !== null) {
        applyAutofit();
        map.invalidateSize({ animate: false });
        observer.disconnect();
      }
    });
    let node: HTMLElement | null = el;
    while (node) {
      observer.observe(node, { attributes: true, attributeFilter: ['class', 'style'] });
      node = node.parentElement;
    }
  }
}

document.querySelectorAll<HTMLElement>('.slab-map').forEach(initMap);
