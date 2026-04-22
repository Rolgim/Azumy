/**
 * SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
 * SPDX-License-Identifier: Apache-2.0
 */

import { termClear, termLine, termClassFromMessage } from './terminal.js';
import { progShow, progSet } from './progress.js';
import { openWS, API } from './websocket.js';
import { initMap, goTo, loadTiling, drawCircle } from './map.js';

export let foundTiles    = [];
export let selectedTiles = [];

let selectedRa  = null;
let selectedDec = null;
let selectedRadius = null;

export async function initFind() {
  await initMap('aladinMap');
  initUI();
}

function initUI() {
  // Map → fill fields without radius
  document.addEventListener('sky:select', ({ detail: { ra, dec } }) => {
    selectedRa  = ra;
    selectedDec = dec;
    document.getElementById('findRa').value  = ra.toFixed(6);
    document.getElementById('findDec').value = dec.toFixed(6);
  });

    // Map → fill fields with radius
  document.addEventListener('sky:region', ({ detail: { ra, dec, radius } }) => {
    selectedRa  = ra;
    selectedDec = dec;
    selectedRadius = radius;
    document.getElementById('findRa').value  = ra.toFixed(6);
    document.getElementById('findDec').value = dec.toFixed(6);
    document.getElementById('findRadius').value = radius.toFixed(6);
  });

  // Manual fields → map
  document.getElementById('findRa')?.addEventListener('change', syncFieldsToMap);
  document.getElementById('findDec')?.addEventListener('change', syncFieldsToMap);
  document.getElementById('findRadius')?.addEventListener('change', syncFieldsToMap);

  // Tiling input → update map overlay
  document.getElementById('findTiling')?.addEventListener('change', e => loadTiling(e.target.value.trim()));
  document.getElementById('findTiling')?.addEventListener('blur',   e => loadTiling(e.target.value.trim()));

  // Upload button → open file picker
  document.getElementById('btnUploadTiling')?.addEventListener('click', (e) => {
    e.preventDefault();
    const input = document.getElementById('tilingFileInput');
    if (input) { input.value = null; input.click(); }
  });

  // File selected → upload to backend
  document.getElementById('tilingFileInput')?.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const btn = document.getElementById('btnUploadTiling');
    if (btn) { btn.disabled = true; btn.textContent = 'Uploading…'; }

    const form = new FormData();
    form.append('file', file);

    try {
      const resp = await fetch(`${API}/find/geojson`, { method: 'POST', body: form });

      if (resp.ok) {
        const data = await resp.json();
        if (btn) { btn.disabled = false; btn.textContent = data.filename; btn.dataset.tiling = data.filename; }
        loadTiling(data.filename);
      } else {
        if (btn) { btn.disabled = false; btn.textContent = 'Load'; }
        console.warn('Upload failed');
      }
    } catch (err) {
      if (btn) { btn.disabled = false; btn.textContent = 'Load'; }
      console.warn('Upload error:', err);
    }
  });
}

function syncFieldsToMap() {
  const ra  = parseFloat(document.getElementById('findRa').value);
  const dec = parseFloat(document.getElementById('findDec').value);
  if (isNaN(ra) || isNaN(dec)) return;
  selectedRa = ra; selectedDec = dec;
  goTo(ra, dec);
  const radius = parseFloat(document.getElementById('findRadius').value);
  selectedRadius = isNaN(radius) ? null : radius;
  drawCircle(ra, dec, selectedRadius);
}

export function runFind() {
  termClear('Global');
  document.getElementById('findActions').classList.add('hidden');
  document.getElementById('tilesResult').innerHTML = '';
  foundTiles = []; selectedTiles = [];

  const btn = document.getElementById('btnFind');
  btn.disabled = true;
  progShow('Find'); progSet('Find', 0);

  const objects = document.getElementById('findObjects').value.trim().split(/\s+/).filter(Boolean);
  const ra  = parseFloat(document.getElementById('findRa').value);
  const dec = parseFloat(document.getElementById('findDec').value);

  const payload = {
    objects,
    coordinates: (!isNaN(ra) && !isNaN(dec)) ? [{ ra, dec }] : [],
    tiling: document.getElementById('btnUploadTiling')?.dataset.tiling || '',
  };

  let progress = 0;

  openWS('/find/ws', payload, {
    cmd:  m => termLine('Global', 'c-cmd', '$ ' + m.message),
    log:  m => {
      termLine('Global', termClassFromMessage(m.message), m.message);
      const coordMatch = m.message.match(/Coordinates:\s*([\d.]+)\s*deg[^,]*,\s*([\d.]+)/);
      if (coordMatch) goTo(parseFloat(coordMatch[1]), parseFloat(coordMatch[2]));
      progress = Math.min(progress + 10, 90);
      progSet('Find', progress);
    },
    tile: m => {
      foundTiles.push(m.data);
      addTileChip(m.data);
      document.getElementById('findActions').classList.remove('hidden');
    },
    exit:  m => { if (m.code !== 0) termLine('Global', 'c-err', `exit ${m.code}`); },
    done:  () => { progSet('Find', 100); btn.disabled = false; },
    error: m => { termLine('Global', 'c-err', m.message); btn.disabled = false; },
  });
}

function addTileChip(tile) {
  const chip = document.createElement('div');
  chip.className     = 'tile';
  chip.dataset.index = tile.index;
  chip.textContent   = tile.index + (tile.mode ? ` (${tile.mode})` : '');
  chip.onclick = () => {
    chip.classList.toggle('sel');
    if (chip.classList.contains('sel')) selectedTiles.push(tile.index);
    else selectedTiles = selectedTiles.filter(x => x !== tile.index);
  };
  document.getElementById('tilesResult').appendChild(chip);
}

export function sendToRetrieve() {
  const current = document.getElementById('retrieveTiles').value.trim();
  const toAdd   = selectedTiles.length ? selectedTiles : foundTiles.map(t => t.index);
  const all     = [...new Set([...current.split(/\s+/).filter(Boolean), ...toAdd])];
  document.getElementById('retrieveTiles').value = all.join(' ');
  const details = document.getElementById('detailsRetrieve');
  if (details) {
    details.open = true;
  }
  document.getElementById('termGlobal').innerHTML = '';
  document.getElementById('btnRetrieve').scrollIntoView({ behavior: 'smooth' });
}