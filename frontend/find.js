import { termClear, termLine, termClassFromMessage } from './terminal.js';
import { progShow, progSet } from './progress.js';
import { openWS } from './websocket.js';

export let foundTiles    = [];
export let selectedTiles = [];

export function runFind() {
  termClear('Find');
  document.getElementById('tilesResult').innerHTML = '';
  document.getElementById('sendRetrieve').style.display = 'none';
  foundTiles = []; selectedTiles = [];

  const btn = document.getElementById('btnFind');
  btn.disabled = true;
  progShow('Find'); progSet('Find', 0);

  const ra  = document.getElementById('findRa').value.trim();
  const dec = document.getElementById('findDec').value.trim();

  const payload = {
    workspace:   '.',
    objects:     document.getElementById('findObjects').value.trim().split(/\s+/).filter(Boolean),
    coordinates: (ra && dec) ? [{ ra: parseFloat(ra), dec: parseFloat(dec) }] : [],
    tiling:      document.getElementById('findTiling').value.trim(),
  };

  let progress = 0;

  openWS('/find/ws', payload, {
    cmd:  m => termLine('Find', 'c-cmd', '$ ' + m.message),
    log:  m => {
      termLine('Find', termClassFromMessage(m.message), m.message);
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
  chip.className   = 'tile';
  chip.dataset.index = tile.index;
  chip.textContent = tile.index + (tile.mode ? ` (${tile.mode})` : '');
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