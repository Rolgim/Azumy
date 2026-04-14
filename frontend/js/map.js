/**
 * SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
 * SPDX-License-Identifier: Apache-2.0
 * 
 * map.js — Aladin Lite v3 sky map
 * Click on the sky → dispatches "sky:select" with { ra, dec }
 */

import { API } from './websocket.js';

let aladin      = null;
let markerLayer = null;
let tilingOverlay = null;
let circleOverlay = null;
let firstClick = null;

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

  // overlay cercle
  circleOverlay = A.graphicOverlay({ color: '#8066be', lineWidth: 2 });
  aladin.addOverlay(circleOverlay);

  aladin.on('click', (raOrObj, decArg) => {
    const ra  = (raOrObj !== null && typeof raOrObj === 'object') ? raOrObj.ra  : raOrObj;
    const dec = (raOrObj !== null && typeof raOrObj === 'object') ? raOrObj.dec : decArg;
    if (ra == null || dec == null) return;

    // 1st clic  -> position
    if (!firstClick) {
      firstClick = { ra, dec };

      placeMarker(ra, dec);
      circleOverlay.removeAll();

      document.dispatchEvent(new CustomEvent('sky:select', {
        detail: { ra, dec }
      }));

      return;
    }

    // 2nd clic → radius
    const radius = angularDistance(
      firstClick.ra,
      firstClick.dec,
      ra,
      dec
    );

    drawCircle(firstClick.ra, firstClick.dec, radius);
    console.log(radius);

    document.dispatchEvent(new CustomEvent('sky:region', {
      detail: {
        ra: firstClick.ra,
        dec: firstClick.dec,
        radius
      }
    }));

    // reset
    firstClick = null;
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

  // reset selection
  firstClick = null;
  if (circleOverlay) circleOverlay.removeAll();
}

/**
 * Draw circle (polygon approximation)
 */
function drawCircle(ra, dec, radiusDeg) {
  const points = [];
  const steps = 64;

  const decRad = dec * Math.PI / 180;

  for (let i = 0; i < steps; i++) {
    const angle = (i / steps) * 2 * Math.PI;

    const dRa  = (radiusDeg * Math.cos(angle)) / Math.cos(decRad);
    const dDec = radiusDeg * Math.sin(angle);

    points.push([ra + dRa, dec + dDec]);
  }

  circleOverlay.removeAll();
  circleOverlay.add(A.polygon(points));
}

/**
 * Angular distance (deg)
 */
function angularDistance(ra1, dec1, ra2, dec2) {
  const toRad = d => d * Math.PI / 180;

  const r1 = toRad(ra1);
  const d1 = toRad(dec1);
  const r2 = toRad(ra2);
  const d2 = toRad(dec2);

  const cos =
    Math.sin(d1) * Math.sin(d2) +
    Math.cos(d1) * Math.cos(d2) * Math.cos(r1 - r2);

  return Math.acos(Math.min(1, cos)) * 180 / Math.PI;
}

/**
 * Load tiling polygons from the backend
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