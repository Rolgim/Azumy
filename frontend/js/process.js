/**
 * SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
 * SPDX-License-Identifier: Apache-2.0
 */

import { termClear, termLine, termClassFromMessage } from './terminal.js';
import { progShow, progSet } from './progress.js';
import { openWS, API } from './websocket.js';

// Defaults //////////////////////////////////////////

const AZUL_DEFAULTS = {
  zero:       [24.5, 29.8, 30.1, 30.0],
  scaling:    [2.2,  1.3,  1.2,  1.0],
  fwhm:       [1.6,  3.5,  3.4,  3.5],
  sharpen:    0.5,  nirl: 0.1,  ib: 1.0,
  yg:         0.5,  jr:   0.25,
  white:      22.0, stretch: 28.0, offset: 29.0,
  hue:        -20.0, saturation: 1.2,
};

const EUMMY_DEFAULTS = {
  blackwhite: [-1.3, 7000],
  pivot:      0.15,
  contrast:   '',
  scales:     [0.002039, 0.5950, 1.0000, 1.0985],
  fr:         0.3,
  saturate:   [2.0],
  um:         [1.6, 0.75, 0.09],
  um_enabled: true,
  blend_iy:   false,
  fi:         1.6,
};

// Helpers //////////////////////////////////////////

const $   = id => document.getElementById(id);
const flt = id => parseFloat($(id).value);
const lst = id => $(id).value.split(',').map(Number);
const chk = id => $(id).checked;

let currentEngine = 'azul';

// Engine switch //////////////////////////////////////////

export function initProcess() {
  $('engineAzul').addEventListener('change',  () => setEngine('azul'));
  $('engineEummy').addEventListener('change', () => setEngine('eummy'));
}

function setEngine(engine) {
  currentEngine = engine;
  $('azulParams').style.display  = engine === 'azul'  ? 'block' : 'none';
  $('eummyParams').style.display = engine === 'eummy' ? 'block' : 'none';
}

// Build payload //////////////////////////////////////////

function buildPayload(tile) {
  if (currentEngine === 'azul') {
    return {
      engine: 'azul', tile,
      zero:       lst('procZero'),
      scaling:    lst('procScaling'),
      fwhm:       lst('procFwhm'),
      sharpen:    flt('procSharpen'),
      nirl:       flt('procNirl'),
      ib:         flt('procIb'),
      yg:         flt('procYg'),
      jr:         flt('procJr'),
      white:      flt('procWhite'),
      stretch:    flt('procStretch'),
      offset:     flt('procOffset'),
      hue:        flt('procHue'),
      saturation: flt('procSaturation'),
    };
  } else {
    const contrast = $('eummyContrast').value.trim();
    return {
      engine:     'eummy',
      tile:       tile.split('[')[0],
      blackwhite: lst('eummyBlackwhite'),
      pivot:      flt('eummyPivot'),
      contrast:   contrast ? parseFloat(contrast) : null,
      scales:     lst('eummyScales'),
      fr:         flt('eummyFr'),
      saturate:   lst('eummySaturate'),
      um:         lst('eummyUm'),
      um_enabled: chk('eummyUmEnabled'),
      blend_iy:   chk('eummyBlendIY'),
      fi:         flt('eummyFi'),
    };
  }
}

// Run //////////////////////////////////////////

export function runProcess() {
  const tile = $('processTile').value.trim();
  if (!tile) { termLine('Process', 'c-err', 'Tile spec required'); return; }

  termClear('Process');
  $('processResult').style.display = 'none';

  const btn = $('btnProcess');
  btn.disabled = true;
  progShow('Process'); progSet('Process', 0);

  openWS('/process/ws', buildPayload(tile), {
    cmd:         m => termLine('Process', 'c-cmd', '$ ' + m.message),
    log:         m => termLine('Process', termClassFromMessage(m.message), m.message),
    progress:    m => progSet('Process', m.percent),
    output_file: m => showResult(m.name, tile.split('[')[0]),
    preview:     m => showResult(m.name, tile.split('[')[0]),
    exit:        m => { if (m.code !== 0) termLine('Process', 'c-err', `exit ${m.code}`); },
    done:        m => {
      progSet('Process', 100);
      btn.disabled = false;
      const tileNum = tile.split('[')[0];
      if (m.preview_file) showResult(m.preview_file, tileNum);
      else if (m.output_file) showResult(m.output_file, tileNum);
    },
    error: m => { termLine('Process', 'c-err', m.message); btn.disabled = false; },
  });
}

function showResult(filename, tileNum) {
  if (!filename) return;
  const ext = filename.split('.').pop().toLowerCase();
  if (['jpg', 'jpeg', 'png'].includes(ext)) {
    $('processResultImg').src = `${API}/workspace/${tileNum}/${filename}?t=${Date.now()}`;
    $('processResultImg').style.display = 'block';
  } else {
    $('processResultImg').style.display = 'none';
  }
  $('processResultLabel').textContent = filename;
  $('processResult').style.display = 'block';
}

// Reset //////////////////////////////////////////

export function resetProcess() {
  if (getCurrentEngine() === 'azul') {
    $('procZero').value       = AZUL_DEFAULTS.zero.join(', ');
    $('procScaling').value    = AZUL_DEFAULTS.scaling.join(', ');
    $('procFwhm').value       = AZUL_DEFAULTS.fwhm.join(', ');
    $('procSharpen').value    = AZUL_DEFAULTS.sharpen;
    $('procNirl').value       = AZUL_DEFAULTS.nirl;
    $('procIb').value         = AZUL_DEFAULTS.ib;
    $('procYg').value         = AZUL_DEFAULTS.yg;
    $('procJr').value         = AZUL_DEFAULTS.jr;
    $('procWhite').value      = AZUL_DEFAULTS.white;
    $('procStretch').value    = AZUL_DEFAULTS.stretch;
    $('procOffset').value     = AZUL_DEFAULTS.offset;
    $('procHue').value        = AZUL_DEFAULTS.hue;
    $('procSaturation').value = AZUL_DEFAULTS.saturation;
  } else {
    $('eummyBlackwhite').value  = EUMMY_DEFAULTS.blackwhite.join(', ');
    $('eummyPivot').value       = EUMMY_DEFAULTS.pivot;
    $('eummyContrast').value    = '';
    $('eummyScales').value      = EUMMY_DEFAULTS.scales.join(', ');
    $('eummyFr').value          = EUMMY_DEFAULTS.fr;
    $('eummySaturate').value    = EUMMY_DEFAULTS.saturate.join(', ');
    $('eummyUm').value          = EUMMY_DEFAULTS.um.join(', ');
    $('eummyUmEnabled').checked = EUMMY_DEFAULTS.um_enabled;
    $('eummyBlendIY').checked   = EUMMY_DEFAULTS.blend_iy;
    $('eummyFi').value          = EUMMY_DEFAULTS.fi;
  }
}

function getCurrentEngine() {
  return $('engineAzul').checked ? 'azul' : 'eummy';
}

export function setProcessTile(tileSpec) {
  $('processTile').value = tileSpec;
}