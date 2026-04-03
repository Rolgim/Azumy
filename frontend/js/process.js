/**
 * SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
 * SPDX-License-Identifier: Apache-2.0
 */

import { termClear, termLine, termClassFromMessage } from './terminal.js';
import { progShow, progSet } from './progress.js';
import { openWS } from './websocket.js';

const DEFAULTS = {
  zero:       [24.5, 29.8, 30.1, 30.0],
  scaling:    [2.2,  1.3,  1.2,  1.0],
  fwhm:       [1.6,  3.5,  3.4,  3.5],
  sharpen:    0.5,
  nirl:       0.1,
  ib:         1.0,
  yg:         0.5,
  jr:         0.25,
  white:      22.0,
  stretch:    28.0,
  offset:     29.0,
  hue:        -20.0,
  saturation: 1.2,
};

function getFloat(id)         { return parseFloat(document.getElementById(id).value); }
function getFloatList(id)     { return document.getElementById(id).value.split(',').map(Number); }

export function runProcess() {
  const tile = document.getElementById('processTile').value.trim();
  if (!tile) { termLine('Process', 'c-err', 'Tile spec required'); return; }

  termClear('Process');
  document.getElementById('processResult').style.display = 'none';

  const btn = document.getElementById('btnProcess');
  btn.disabled = true;
  progShow('Process'); progSet('Process', 0);

  const payload = {
    tile,
    zero:       getFloatList('procZero'),
    scaling:    getFloatList('procScaling'),
    fwhm:       getFloatList('procFwhm'),
    sharpen:    getFloat('procSharpen'),
    nirl:       getFloat('procNirl'),
    ib:         getFloat('procIb'),
    yg:         getFloat('procYg'),
    jr:         getFloat('procJr'),
    white:      getFloat('procWhite'),
    stretch:    getFloat('procStretch'),
    offset:     getFloat('procOffset'),
    hue:        getFloat('procHue'),
    saturation: getFloat('procSaturation'),
  };

  openWS('/process/ws', payload, {
    cmd:          m => termLine('Process', 'c-cmd', '$ ' + m.message),
    log:          m => termLine('Process', termClassFromMessage(m.message), m.message),
    progress:     m => progSet('Process', m.percent),
    output_file:  m => showResult(m.name),
    preview: m => showResult(m.name),
    exit:         m => { if (m.code !== 0) termLine('Process', 'c-err', `exit ${m.code}`); },
    done:         m => {
      progSet('Process', 100);
      btn.disabled = false;
      if (m.output_file) showResult(m.output_file);
      if (m.preview_file) showResult(m.preview_file);
    },
    error:       m => { termLine('Process', 'c-err', m.message); btn.disabled = false; },
  });
}

function showResult(filename) {
  const tile  = document.getElementById('processTile').value.split('[')[0].trim();
  const el    = document.getElementById('processResult');
  const img   = document.getElementById('processResultImg');
  const label = document.getElementById('processResultLabel');

  // TIF files can't be displayed directly
  const ext = filename.split('.').pop().toLowerCase();
  if (['jpg','jpeg','png'].includes(ext)) {
    img.src = `http://localhost:8000/workspace/${tile}/${filename}?t=${Date.now()}`;
    img.style.display = 'block';
  } else {
    img.style.display = 'none';
  }
  label.textContent = filename;
  el.style.display = 'block';
}

export function resetProcess() {
  document.getElementById('procZero').value       = DEFAULTS.zero.join(', ');
  document.getElementById('procScaling').value    = DEFAULTS.scaling.join(', ');
  document.getElementById('procFwhm').value       = DEFAULTS.fwhm.join(', ');
  document.getElementById('procSharpen').value    = DEFAULTS.sharpen;
  document.getElementById('procNirl').value       = DEFAULTS.nirl;
  document.getElementById('procIb').value         = DEFAULTS.ib;
  document.getElementById('procYg').value         = DEFAULTS.yg;
  document.getElementById('procJr').value         = DEFAULTS.jr;
  document.getElementById('procWhite').value      = DEFAULTS.white;
  document.getElementById('procStretch').value    = DEFAULTS.stretch;
  document.getElementById('procOffset').value     = DEFAULTS.offset;
  document.getElementById('procHue').value        = DEFAULTS.hue;
  document.getElementById('procSaturation').value = DEFAULTS.saturation;
}

// Set the tile spec (e.g. "tile_12345 [ra, dec]") to process, and update the corresponding input field.
export function setProcessTile(tileSpec) {
  document.getElementById('processTile').value = tileSpec;
}