import { termClear, termLine, termClassFromMessage } from './terminal.js';
import { progShow, progSet } from './progress.js';
import { openWS } from './websocket.js';
 
export function runRetrieve() {
  termClear('Retrieve');
 
  const tiles = document.getElementById('retrieveTiles').value.trim().split(/\s+/).filter(Boolean);
  if (!tiles.length) {
    termLine('Retrieve', 'c-err', 'No tile indices provided');
    return;
  }
 
  const btn = document.getElementById('btnRetrieve');
  btn.disabled = true;
  progShow('Retrieve'); progSet('Retrieve', 0);
 
  const payload = {
    workspace:    '.',
    tile_indices: tiles,
    provider:     document.getElementById('retrieveProvider').value,
    dsr:          document.getElementById('retrieveDsr').value,
  };
 
  openWS('/retrieve/ws', payload, {
    cmd:      m => termLine('Retrieve', 'c-cmd', '$ ' + m.message),
    log:      m => termLine('Retrieve', termClassFromMessage(m.message), m.message),
    file:     m => termLine('Retrieve', 'c-ok', `✓ [${m.filter}] ${m.name}`),
    progress: m => progSet('Retrieve', m.percent),
    exit:     m => { if (m.code !== 0) termLine('Retrieve', 'c-err', `exit ${m.code}`); },
    done:     () => { progSet('Retrieve', 100); btn.disabled = false; },
    error:    m => { termLine('Retrieve', 'c-err', m.message); btn.disabled = false; },
  });
}
 