/**
 * SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
 * SPDX-License-Identifier: Apache-2.0
 */

export function progShow(id) {
    document.getElementById('prog' + id).style.display = 'block';
  }
  
  export function progSet(id, pct) {
    document.getElementById('prog' + id + 'Bar').style.width = pct + '%';
  }