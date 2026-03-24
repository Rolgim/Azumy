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
    tile_indices: tiles,
    provider:     document.getElementById('retrieveProvider').value,
    dsr:          document.getElementById('retrieveDsr').value,
  };

  let heartbeatInterval = null;
  let heartbeatStart    = null;
  let heartbeatEl       = null;

  function startHeartbeat() {
    heartbeatStart = Date.now();
    heartbeatEl = document.createElement('span');
    heartbeatEl.className = 'c-dim';
    document.getElementById('termRetrieve').appendChild(heartbeatEl);

    heartbeatInterval = setInterval(() => {
      const elapsed = ((Date.now() - heartbeatStart) / 1000).toFixed(0);
      heartbeatEl.textContent = `  downloading... ${elapsed}s elapsed\n`;
      document.getElementById('termRetrieve').scrollTop = 9999;
    }, 1000);
  }

  function stopHeartbeat() {
    if (!heartbeatInterval) return;
    clearInterval(heartbeatInterval);
    heartbeatEl?.remove();
    heartbeatInterval = null;
  }

  openWS('/retrieve/ws', payload, {
    cmd:  m => termLine('Retrieve', 'c-cmd', '$ ' + m.message),
    log:  m => {
      // "Download and extract datafiles to:" start the heartbeat, then stop it when the first file is received (or on error/exit)
      if (m.message.startsWith('Download and extract')) {
        termLine('Retrieve', termClassFromMessage(m.message), m.message);
        startHeartbeat();
      } else {
        termLine('Retrieve', termClassFromMessage(m.message), m.message);
      }
    },
    file: m => {
      stopHeartbeat();
      termLine('Retrieve', 'c-ok', `✓ [${m.filter}] ${m.name}`);
      startHeartbeat(); // restart heartbeat for next file (if any)
    },
    progress: m => progSet('Retrieve', m.percent),
    exit:  m => {
      stopHeartbeat();
      if (m.code !== 0) termLine('Retrieve', 'c-err', `exit ${m.code}`);
    },
    done:  () => {
      stopHeartbeat();
      progSet('Retrieve', 100);
      btn.disabled = false;
    },
    error: m => {
      stopHeartbeat();
      termLine('Retrieve', 'c-err', m.message);
      btn.disabled = false;
    },
  });
}