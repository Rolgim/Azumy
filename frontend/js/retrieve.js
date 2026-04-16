/**
 * SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
 * SPDX-License-Identifier: Apache-2.0
 */

import { termClear, termLine, termClassFromMessage } from './terminal.js';
import { progShow, progSet } from './progress.js';
import { openWS } from './websocket.js';

export let retrievedTiles = [];
export let selectedTiles  = [];


/**
 * Build the targets list and radius from the Find fields.
 * Priority: Objects > RA/Dec > tile indices
 */
function buildTargets() {
  const objects = document.getElementById('findObjects')?.value.trim().split(/\s+/).filter(Boolean) ?? [];
  const ra      = parseFloat(document.getElementById('findRa')?.value);
  const dec     = parseFloat(document.getElementById('findDec')?.value);
  const radius  = document.getElementById('findRadius')?.value.trim() || null;
  const tiles   = document.getElementById('retrieveTiles')?.value.trim().split(/\s+/).filter(Boolean) ?? [];

  let targets;
  if (objects.length) {
    targets = objects;                          // "M82", "NGC6505" …
  } else if (!isNaN(ra) && !isNaN(dec)) {
    targets = [`${ra},${dec}`];                 // format azulero : "270.93,67.05"
  } else {
    targets = tiles;                            // fallback : champ tile indices
  }

  return { targets, radius };
}


export function runRetrieve() {
  termClear('Global');
  document.getElementById('sendCrop').style.display = 'none';
  retrievedTiles = []; selectedTiles = [];
  document.getElementById('tilesRetrieved').innerHTML = '';

  const { targets, radius } = buildTargets();
  if (!targets.length) {
    termLine('Global', 'c-err', 'No targets provided — fill Objects, RA/Dec, or Tile indices');
    return;
  }

  const btn = document.getElementById('btnRetrieve');
  btn.disabled = true;
  progShow('Retrieve'); progSet('Retrieve', 0);

  const payload = {
    targets,
    radius,
    provider: document.getElementById('retrieveProvider').value,
    dsr:      document.getElementById('retrieveDsr').value,
  };

  let heartbeatInterval = null;
  let heartbeatStart    = null;
  let heartbeatEl       = null;

  function startHeartbeat() {
    heartbeatStart = Date.now();
    heartbeatEl = document.createElement('span');
    heartbeatEl.className = 'c-dim';
    document.getElementById('termGlobal').appendChild(heartbeatEl);
    heartbeatInterval = setInterval(() => {
      const elapsed = ((Date.now() - heartbeatStart) / 1000).toFixed(0);
      heartbeatEl.textContent = `  downloading... ${elapsed}s elapsed\n`;
      document.getElementById('termGlobal').scrollTop = 9999;
    }, 1000);
  }

  function stopHeartbeat() {
    if (!heartbeatInterval) return;
    clearInterval(heartbeatInterval);
    heartbeatEl?.remove();
    heartbeatInterval = null;
  }

  openWS('/retrieve/ws', payload, {
    cmd:  m => termLine('Global', 'c-cmd', '$ ' + m.message),
    log:  m => {
      termLine('Global', termClassFromMessage(m.message), m.message);
      if (m.message.startsWith('Download and extract')) startHeartbeat();
    },
    file: m => {
      stopHeartbeat();
      termLine('Global', 'c-ok', `✓ [${m.filter}] ${m.name}`);
      startHeartbeat();
    },
    progress: m => progSet('Retrieve', m.percent),
    tile: m => {
      if (!retrievedTiles.includes(m.index)) {
        retrievedTiles.push(m.index);
        addTileChip({ index: m.index });
        document.getElementById('sendCrop').style.display = 'block';
      }
    },
    exit: m => {
      stopHeartbeat();
      if (m.code !== 0) termLine('Global', 'c-err', `exit ${m.code}`);
    },
    done: m => {
      stopHeartbeat();
      progSet('Retrieve', 100);
      btn.disabled = false;
    },
    error: m => {
      stopHeartbeat();
      termLine('Global', 'c-err', m.message);
      btn.disabled = false;
    },
  });
}


function addTileChip(tile) {
  const chip = document.createElement('div');
  chip.className     = 'tile';
  chip.dataset.index = tile.index;
  chip.textContent   = tile.index;
  chip.onclick = () => {
    const wasSelected = chip.classList.contains('sel');
    document.querySelectorAll('#tilesRetrieved .tile').forEach(c => c.classList.remove('sel'));
    selectedTiles = [];
    if (!wasSelected) {
      chip.classList.add('sel');
      selectedTiles.push(tile.index);
    }
  };
  document.getElementById('tilesRetrieved').appendChild(chip);
}


export function sendToCrop() {
  const tile = selectedTiles.length ? selectedTiles[0] : retrievedTiles[0];
  if (!tile) return;
  const details = document.getElementById('detailsCrop');
  if (details) details.open = true;
  document.getElementById('cropTile').value = tile;
  document.getElementById('cropTile').scrollIntoView({ behavior: 'smooth' });
}