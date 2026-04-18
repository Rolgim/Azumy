/**
 * SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
 * SPDX-License-Identifier: Apache-2.0
 */

import { termClear, termLine, termClassFromMessage } from './terminal.js';
import { progShow, progSet } from './progress.js';
import { openWS } from './websocket.js';

export let retrievedWorkdirs = [];   // ex: ["102159776", "102159776/NGC6505"]
export let selectedWorkdir   = null;


function buildTargets() {
  const objects = document.getElementById('findObjects')?.value.trim().split(/\s+/).filter(Boolean) ?? [];
  const ra      = parseFloat(document.getElementById('findRa')?.value);
  const dec     = parseFloat(document.getElementById('findDec')?.value);
  const radius  = document.getElementById('findRadius')?.value.trim() || null;
  const tiles   = document.getElementById('retrieveTiles')?.value.trim().split(/\s+/).filter(Boolean) ?? [];

  let targets;
  if (objects.length)                  targets = objects;
  else if (!isNaN(ra) && !isNaN(dec))  targets = [`${ra},${dec}`];
  else                                 targets = tiles;

  return { targets, radius };
}


export function runRetrieve() {
  termClear('Global');
  retrievedWorkdirs = [];
  selectedWorkdir   = null;
  document.getElementById('tilesRetrieved').innerHTML = '';
  document.getElementById('retrieveActions').classList.add('hidden');

  const { targets, radius } = buildTargets();
  if (!targets.length) {
    termLine('Global', 'c-err', 'No targets — fill Objects, RA/Dec, or Tile indices');
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
  let heartbeatEl       = null;

  function startHeartbeat() {
    heartbeatEl = document.createElement('span');
    heartbeatEl.className = 'c-dim';
    document.getElementById('termGlobal').appendChild(heartbeatEl);
    const start = Date.now();
    heartbeatInterval = setInterval(() => {
      heartbeatEl.textContent = `  downloading... ${((Date.now()-start)/1000).toFixed(0)}s elapsed\n`;
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
    workdir:  m => addWorkdirChip(m.value),
    exit: m => {
      stopHeartbeat();
      if (m.code !== 0) termLine('Global', 'c-err', `exit ${m.code}`);
    },
    done: m => {
      stopHeartbeat();
      progSet('Retrieve', 100);
      btn.disabled = false;
      // Fallback si aucun workdir reçu : utiliser les tiles du message done
      if (retrievedWorkdirs.length === 0) {
        (m.tiles ?? []).forEach(t => addWorkdirChip(t));
      }
    },
    error: m => {
      stopHeartbeat();
      termLine('Global', 'c-err', m.message);
      btn.disabled = false;
    },
  });
}


function addWorkdirChip(workdir) {
  if (retrievedWorkdirs.includes(workdir)) return;
  retrievedWorkdirs.push(workdir);

  const chip = document.createElement('div');
  chip.className     = 'tile';
  chip.dataset.value = workdir;
  chip.textContent   = workdir;
  chip.onclick = () => {
    document.querySelectorAll('#tilesRetrieved .tile').forEach(c => c.classList.remove('sel'));
    chip.classList.add('sel');
    selectedWorkdir = workdir;
  };
  // Sélectionner automatiquement le premier chip
  if (retrievedWorkdirs.length === 1) {
    chip.classList.add('sel');
    selectedWorkdir = workdir;
  }

  document.getElementById('tilesRetrieved').appendChild(chip);
  document.getElementById('retrieveActions').classList.remove('hidden');
}


function getSelected() {
  return selectedWorkdir ?? retrievedWorkdirs[0] ?? null;
}


export function sendToCrop() {
  const workdir = getSelected();
  if (!workdir) return;
  const details = document.getElementById('detailsCrop');
  if (details) details.open = true;
  document.getElementById('cropTile').value = workdir;
  document.getElementById('cropTile').scrollIntoView({ behavior: 'smooth' });
}


export function sendToProcess() {
  const workdir = getSelected();
  if (!workdir) return;
  const details = document.getElementById('detailsProcess');
  if (details) details.open = true;
  document.getElementById('processTile').value = workdir;
  document.getElementById('processTile').scrollIntoView({ behavior: 'smooth' });
}