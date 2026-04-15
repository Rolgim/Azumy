/**
 * SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
 * SPDX-License-Identifier: Apache-2.0
 *
 * map.js — Aladin Lite v3 sky map
 */

import { API } from './websocket.js';

let aladin         = null;
let markerLayer    = null;
let tilingOverlay  = null;
let circleOverlay  = null;
let previewOverlay = null;   // cercle de preview (mousemove)
let firstClick     = null;

export async function initMap(containerId) {
  await loadAladinScript();
  await A.init;

  aladin = A.aladin('#' + containerId, {
    survey:                'CDS/P/DSS2/color',
    fov:                   60,
    target:                '0 0',
    cooFrame:              'ICRSd',
    showReticle:           false,
    showProjectionControl: false,
    showZoomControl:       true,
    showFullscreenControl: true,
    showLayersControl:     true,
    showGotoControl:       true,
    showShareControl:      true,
    showCooLocation:       true,
  });

  markerLayer = A.catalog({ shape: 'circle', color: '#4ec9b0', sourceSize: 12 });
  aladin.addCatalog(markerLayer);

  circleOverlay  = A.graphicOverlay({ color: '#8066be', lineWidth: 2 });
  previewOverlay = A.graphicOverlay({ color: '#8066be', lineWidth: 1, lineDash: [4, 4] });
  aladin.addOverlay(circleOverlay);
  aladin.addOverlay(previewOverlay);

  // Clic
  aladin.on('click', (raOrObj, decArg) => {
    const ra  = (raOrObj !== null && typeof raOrObj === 'object') ? raOrObj.ra  : raOrObj;
    const dec = (raOrObj !== null && typeof raOrObj === 'object') ? raOrObj.dec : decArg;
    if (ra == null || dec == null) return;

    if (!firstClick) {
      // 1st clic → center
      firstClick = { ra, dec };
      placeMarker(ra, dec);
      circleOverlay.removeAll();
      previewOverlay.removeAll();
      document.dispatchEvent(new CustomEvent('sky:select', { detail: { ra, dec } }));
    } else {
      // 2nd clic → radius
      const radius = angularDistance(firstClick.ra, firstClick.dec, ra, dec);
      previewOverlay.removeAll();
      drawCircleOn(circleOverlay, firstClick.ra, firstClick.dec, radius);
      document.dispatchEvent(new CustomEvent('sky:region', {
        detail: { ra: firstClick.ra, dec: firstClick.dec, radius }
      }));
      firstClick = null;
    }
  });

  // Mousemove → circle preview
  const aladinDiv = document.getElementById(containerId);
  aladinDiv.addEventListener('mousemove', e => {
    if (!firstClick || !aladin.pix2world) return;

    const rect = aladinDiv.getBoundingClientRect();
    const x    = e.clientX - rect.left;
    const y    = e.clientY - rect.top;

    // pix2world returns [ra, dec] in degrees
    const skyCoords = aladin.pix2world(x, y);
    if (!skyCoords || skyCoords[0] == null) return;

    const [raMouse, decMouse] = skyCoords;
    const radius = angularDistance(firstClick.ra, firstClick.dec, raMouse, decMouse);

    previewOverlay.removeAll();
    if (radius > 0) {
      drawCircleOn(previewOverlay, firstClick.ra, firstClick.dec, radius);
    }
  });

  // cancel with escape
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && firstClick) {
      firstClick = null;
      previewOverlay.removeAll();
      markerLayer.clear();
    }
  });
}

// Helpers

function placeMarker(ra, dec) {
  markerLayer.clear();
  markerLayer.addSources([A.source(ra, dec)]);
}

export function goTo(ra, dec) {
  if (!aladin) return;
  aladin.gotoRaDec(ra, dec);
  placeMarker(ra, dec);
  firstClick = null;
  circleOverlay?.removeAll();
  previewOverlay?.removeAll();
}

function drawCircleOn(overlay, ra, dec, radiusDeg, steps = 64) {
  const points  = [];
  const decRad  = dec * Math.PI / 180;
  for (let i = 0; i < steps; i++) {
    const angle = (i / steps) * 2 * Math.PI;
    const dRa   = (radiusDeg * Math.cos(angle)) / Math.cos(decRad);
    const dDec  = radiusDeg * Math.sin(angle);
    points.push([ra + dRa, dec + dDec]);
  }
  overlay.removeAll();
  overlay.add(A.polygon(points));
}

function angularDistance(ra1, dec1, ra2, dec2) {
  const toRad = d => d * Math.PI / 180;
  const cos   =
    Math.sin(toRad(dec1)) * Math.sin(toRad(dec2)) +
    Math.cos(toRad(dec1)) * Math.cos(toRad(dec2)) * Math.cos(toRad(ra1 - ra2));
  return Math.acos(Math.min(1, Math.max(-1, cos))) * 180 / Math.PI;
}

// Tiling

export async function loadTiling(filename) {
  if (!aladin || !filename) return;

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
    tilingOverlay.add(A.polygon(tile.coords.map(([ra, dec]) => [ra, dec])));
  }
  console.log(`Loaded ${data.tiles.length} tile polygons`);
}

// Aladin loader

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