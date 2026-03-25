/**
 * map.js — Aladin Lite v3 sky map
 * Click on the sky → dispatches "sky:select" with { ra, dec }
 */

import { API } from './websocket.js';

let aladin      = null;
let markerLayer = null;
let tilingOverlay = null;

export async function initMap(containerId) {
  await loadAladinScript();
  await A.init;

  aladin = A.aladin('#' + containerId, {
    survey:                'CDS/P/DSS2/color',
    fov:                   60,
    target:                '0 0',
    cooFrame:              'ICRSd',
    showReticle:           false,
    showZoomControl:       true,
    showFullscreenControl: true,
    showLayersControl:     true,
    showGotoControl:       true,
    showShareControl:      true,
    showCooLocation:       true,
  });
  
  markerLayer = A.catalog({ shape: 'circle', color: '#4ec9b0', sourceSize: 12 });
  aladin.addCatalog(markerLayer);

  aladin.on('click', (raOrObj, decArg) => {
    const ra  = (raOrObj !== null && typeof raOrObj === 'object') ? raOrObj.ra  : raOrObj;
    const dec = (raOrObj !== null && typeof raOrObj === 'object') ? raOrObj.dec : decArg;
    if (ra == null || dec == null) return;
    placeMarker(ra, dec);
    document.dispatchEvent(new CustomEvent('sky:select', { detail: { ra, dec } }));
  });
}

function placeMarker(ra, dec) {
  markerLayer.clear();
  markerLayer.addSources([A.source(ra, dec)]);
}

export function goTo(ra, dec) {
  if (!aladin) return;
  aladin.gotoRaDec(ra, dec);
  placeMarker(ra, dec);
}

/**
 * Load tiling polygons from the backend and display them as an overlay on the map.
 */
export async function loadTiling(filename) {
  if (!aladin || !filename) return;

  // Remove existing tiling overlay if any
  if (tilingOverlay) {
    aladin.removeOverlay(tilingOverlay);
    tilingOverlay = null;
  }

  let data;
  try {
    const r = await fetch(`${API}/find/tiling?filename=${encodeURIComponent(filename)}`);
    if (!r.ok) { console.warn('Tiling not found:', filename); return; }
    data = await r.json();
  } catch (e) {
    console.warn('Could not load tiling:', e);
    return;
  }

  tilingOverlay = A.graphicOverlay({ color: '#3d85f5', lineWidth: 1 });
  aladin.addOverlay(tilingOverlay);

  for (const tile of data.tiles) {
    // coords GeoJSON : [[ra, dec], ...] - Aladin [[ra, dec], ...]
    const footprint = A.polygon(tile.coords.map(([ra, dec]) => [ra, dec]));
    tilingOverlay.add(footprint);
  }

  console.log(`Loaded ${data.tiles.length} tile polygons`);
}

function loadAladinScript() {
  return new Promise((resolve, reject) => {
    if (window.A) { resolve(); return; }
    const script = document.createElement('script');
    script.src     = '../aladin.js';
    script.charset = 'utf-8';
    script.onload  = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
}