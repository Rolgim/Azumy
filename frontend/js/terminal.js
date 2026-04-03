/**
 * SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
 * SPDX-License-Identifier: Apache-2.0
 */

export function termClear(id) {
    document.getElementById('term' + id).innerHTML = '';
  }
   
  export function termLine(id, cls, text) {
    const t = document.getElementById('term' + id);
    const s = document.createElement('span');
    s.className = cls;
    s.textContent = text + '\n';
    t.appendChild(s);
    t.scrollTop = t.scrollHeight;
  }
   
  export function termClassFromMessage(message) {
    if (message.startsWith('WARNING')) return 'c-warn';
    if (message.startsWith('ERROR'))   return 'c-err';
    return '';
  }
   