/**
 * SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
 * SPDX-License-Identifier: Apache-2.0
 */

import { termClear, termLine, termClassFromMessage } from './terminal.js';
import { progShow, progSet } from './progress.js';
import { openWS } from './config.js';

export let retrievedWorkdirs = [];
export let selectedWorkdir   = null;


function buildTargets() {
  const sourceType = document.getElementById('sourceType')?.value ?? 'tiles';
  const radius     = document.getElementById('findRadius')?.value.trim() || null;

  let targets;

  switch (sourceType) {
    case 'Object': {
      const objects = document.getElementById('findObjects')?.value.trim().split(/\s+/).filter(Boolean) ?? [];
      if (!objects.length) return { targets: [], radius, error: 'No objects specified' };
      targets = objects;
      break;
    }
    case 'RA/Dec': {
      const ra  = parseFloat(document.getElementById('findRa')?.value);
      const dec = parseFloat(document.getElementById('findDec')?.value);
      if (isNaN(ra) || isNaN(dec)) return { targets: [], radius, error: 'Invalid RA/Dec' };
      targets = [`${ra},${dec}`];
      break;
    }
    case 'tiles':
    default: {
      targets = document.getElementById('retrieveTiles')?.value.trim().split(/\s+/).filter(Boolean) ?? [];
      if (!targets.length) return { targets: [], radius: null, error: 'No tile indices provided' };
      break;
    }
  }

  // Radius only relevant for Object and RA/Dec
  const effectiveRadius = sourceType === 'tiles' ? null : radius;
  return { targets, radius: effectiveRadius };
}


export function runRetrieve() {
  // cleaning
  termClear('Global');
  const detailsFind = document.getElementById('detailsFind');
  if (detailsFind) detailsFind.open = false;
  const detailsProcess = document.getElementById('detailsProcess');
  if (detailsProcess) detailsProcess.open = false;
  const detailsCrop = document.getElementById('detailsCrop');
  if (detailsCrop) detailsCrop.open = false;
  const processResult = document.getElementById('processResult');
  processResult.style.display = 'none';
  const cropContainer= document.getElementById('cropContainer');
  cropContainer.classList.add('hidden');

  retrievedWorkdirs = [];
  selectedWorkdir   = null;
  document.getElementById('tilesRetrieved').innerHTML = '';
  document.getElementById('retrieveActions').classList.add('hidden');

  const { targets, radius, error } = buildTargets();
  if (!targets.length) {
    termLine('Global', 'c-err', error ?? 'No targets provided');
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
  const detailsCrop = document.getElementById('detailsCrop');
  if (detailsCrop) detailsCrop.open = true;
  document.getElementById('cropTile').value = workdir;
  document.getElementById('cropTile').scrollIntoView({ behavior: 'smooth' });
  const detailsRetrieve = document.getElementById('detailsRetrieve');
  if (detailsRetrieve) detailsRetrieve.open = false;
}


export function sendToProcess() {
  const workdir = getSelected();
  if (!workdir) return;
  const detailsProcess = document.getElementById('detailsProcess');
  if (detailsProcess) detailsProcess.open = true;
  document.getElementById('processTile').value = workdir;
  document.getElementById('processTile').scrollIntoView({ behavior: 'smooth' });
  const detailsRetrieve = document.getElementById('detailsRetrieve');
  if (detailsRetrieve) detailsRetrieve.open = false;
}