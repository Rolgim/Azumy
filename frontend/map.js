/**
 * map.js — Aladin Lite v3 sky map
 * Click on the sky → dispatches "sky:select" with { ra, dec }
 */

let aladin = null;
let markerLayer = null;

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
    showFullscreenControl: false,
    showLayersControl:     true,
    showGotoControl:       true,
    showShareControl:      false,
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

function loadAladinScript() {
  return new Promise((resolve, reject) => {
    if (window.A) { resolve(); return; }
    const script = document.createElement('script');
    script.src     = 'aladin.js';
    script.charset = 'utf-8';
    script.onload  = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
}