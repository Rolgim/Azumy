/**
 * SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
 * SPDX-License-Identifier: Apache-2.0
 */

import { initFind, runFind, sendToRetrieve }      from './find.js';
import { runRetrieve, sendToCrop, sendToProcess } from './retrieve.js';
import { loadCropPreview, sendCropToProcess }     from './crop.js';
import { initProcess, runProcess, resetProcess }               from './process.js';

document.getElementById('btnFind').addEventListener('click', runFind);
document.getElementById('btnSendRetrieve').addEventListener('click', sendToRetrieve);

document.getElementById('btnRetrieve').addEventListener('click', runRetrieve);
document.getElementById('btnSendCrop').addEventListener('click', sendToCrop);
document.getElementById('btnSendProcess').addEventListener('click', sendToProcess);

document.getElementById('btnCropPreview').addEventListener('click', () => {
    const tile = document.getElementById('cropTile').value.trim();
    loadCropPreview(tile);
});
document.getElementById('btnCropSend').addEventListener('click', sendCropToProcess);

document.getElementById('btnProcess').addEventListener('click', runProcess);
document.querySelectorAll('.btnResetProcess')
  .forEach(btn => btn.addEventListener('click', resetProcess));

// Init map on page load
initFind();
initProcess();