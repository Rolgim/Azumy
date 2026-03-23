import { termClear, termLine, termClassFromMessage } from './terminal.js';
import { progShow, progSet } from './progress.js';
import { openWS } from './websocket.js';
import { initMap, goTo } from './map.js';

export let foundTiles    = [];
export let selectedTiles = [];

let selectedRa  = null;
let selectedDec = null;

export async function initFind() {
  await initMap('aladinMap');

  // Map → fill fields
  document.addEventListener('sky:select', ({ detail: { ra, dec } }) => {
    selectedRa  = ra;
    selectedDec = dec;
    document.getElementById('findRa').value  = ra.toFixed(6);
    document.getElementById('findDec').value = dec.toFixed(6);
  });

  // Manual fields → map
  document.getElementById('findRa').addEventListener('change', syncFieldsToMap);
  document.getElementById('findDec').addEventListener('change', syncFieldsToMap);
}

function syncFieldsToMap() {
  const ra  = parseFloat(document.getElementById('findRa').value);
  const dec = parseFloat(document.getElementById('findDec').value);
  if (isNaN(ra) || isNaN(dec)) return;
  selectedRa = ra; selectedDec = dec;
  goTo(ra, dec);
}

export function runFind() {
  termClear('Find');
  document.getElementById('tilesResult').innerHTML = '';
  document.getElementById('sendRetrieve').style.display = 'none';
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
    tiling:      document.getElementById('findTiling').value.trim(),
  };

  // If the server sends "Coordinates: X deg, Y deg", center the map on these coordinates 
  // (e.g. if the input was an object name that got resolved)
  let progress = 0;

  openWS('/find/ws', payload, {
    cmd:  m => termLine('Find', 'c-cmd', '$ ' + m.message),
    log:  m => {
      termLine('Find', termClassFromMessage(m.message), m.message);
      // "- Coordinates: 148.97 deg, 69.68 deg" → center map on these coordinates
      const coordMatch = m.message.match(/Coordinates:\s*([\d.]+)\s*deg[^,]*,\s*([\d.]+)/);
      if (coordMatch) goTo(parseFloat(coordMatch[1]), parseFloat(coordMatch[2]));
      progress = Math.min(progress + 10, 90);
      progSet('Find', progress);
    },
    tile: m => {
      foundTiles.push(m.data);
      addTileChip(m.data);
      document.getElementById('sendRetrieve').style.display = 'block';
    },
    exit:  m => { if (m.code !== 0) termLine('Find', 'c-err', `exit ${m.code}`); },
    done:  () => { progSet('Find', 100); btn.disabled = false; },
    error: m => { termLine('Find', 'c-err', m.message); btn.disabled = false; },
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
  document.getElementById('termRetrieve').innerHTML = '';
  document.getElementById('termRetrieve').scrollIntoView({ behavior: 'smooth' });
}