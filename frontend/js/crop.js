/**
 * SPDX-FileCopyrightText: Copyright (C) 2026, CNES (Rollin Gimenez)
 * SPDX-License-Identifier: Apache-2.0
 * 
 * crop.js — Interactive crop via canvas rectangle selection
 */

import { API } from './websocket.js';

let tileWidth  = 0;
let tileHeight = 0;
let currentTile = '';

// Rectangle drawing state
let drawing = false;
let startX = 0, startY = 0, endX = 0, endY = 0;

export async function loadCropPreview(tile) {
  if (!tile) return;
  currentTile = tile;

  const container = document.getElementById('cropContainer');
  container.classList.add('hidden');
  const canvas    = document.getElementById('cropCanvas');
  const status    = document.getElementById('cropStatus');

  status.textContent = 'Loading VIS channel…';
  container.classList.remove('hidden');
  clearSelection();

  // Charger l'image via fetch pour récupérer les headers X-Tile-Width/Height
  let resp;
  try {
    resp = await fetch(`${API}/crop/preview/${encodeURIComponent(tile)}`);
    if (!resp.ok) { status.textContent = `Error: ${resp.statusText}`; return; }
  } catch (e) {
    status.textContent = `Cannot reach server: ${e}`;
    return;
  }

  tileWidth  = parseInt(resp.headers.get('X-Tile-Width')  || '16000');
  tileHeight = parseInt(resp.headers.get('X-Tile-Height') || '16000');

  const blob = await resp.blob();
  const url  = URL.createObjectURL(blob);
  const img  = new Image();

  img.onload = () => {
    canvas.width  = img.width;
    canvas.height = img.height;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(img, 0, 0);
    URL.revokeObjectURL(url);
    status.textContent = `${tileWidth} × ${tileHeight} px — draw a rectangle to select a region`;
    initDraw(canvas, ctx, img);
  };
  img.src = url;
}

function initDraw(canvas, ctx, img) {
  // Function to convert mouse event coordinates to canvas coordinates, accounting for CSS scaling
  const getCanvasCoords = (e) => {
    const rect = canvas.getBoundingClientRect();
    
    // 1. compute scale factors between canvas size and displayed size
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    
    // 2. apply inverse of CSS transform to mouse coordinates
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY
    };
  };

  canvas.onmousedown = e => {
    const coords = getCanvasCoords(e);
    startX = coords.x;
    startY = coords.y;
    drawing = true;
  };

  canvas.onmousemove = e => {
    if (!drawing) return;
    const coords = getCanvasCoords(e);
    endX = coords.x;
    endY = coords.y;

    // Redraw
    ctx.drawImage(img, 0, 0);
    ctx.strokeStyle = '#4ec9b0';
    ctx.lineWidth = 2 * (canvas.width / 1000); 
    ctx.strokeRect(startX, startY, endX - startX, endY - startY);
    ctx.fillStyle = 'rgba(78,201,176,0.15)';
    ctx.fillRect(startX, startY, endX - startX, endY - startY);
  };

  canvas.onmouseup = async () => {
    if (!drawing) return;
    drawing = false;
    await computeSlicing(canvas);
  };

  canvas.onmouseleave = () => { drawing = false; };
}

async function computeSlicing(canvas) {
  // convert coords canvas → coords image
  const scaleX = tileWidth  / canvas.width;
  const scaleY = tileHeight / canvas.height;

  // normalize to top-left origin and ensure x0 < x1, y0 < y1
  const x0 = Math.min(startX, endX) * scaleX;
  const x1 = Math.max(startX, endX) * scaleX;
  const y0 = (canvas.height - Math.max(startY, endY)) * scaleY;
  const y1 = (canvas.height - Math.min(startY, endY)) * scaleY;

  const resp = await fetch(`${API}/crop/slicing`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tile: currentTile, x0, x1, y0, y1, w: tileWidth, h: tileHeight }),
  });
  const data = await resp.json();

  document.getElementById('cropSlicing').textContent = data.slicing;
  document.getElementById('cropResult').style.display = 'block';
  document.getElementById('cropStatus').textContent =
    `Selection: [${data.y0}:${data.y1}, ${data.x0}:${data.x1}]`;
}

function clearSelection() {
  document.getElementById('cropResult').style.display = 'none';
  document.getElementById('cropSlicing').textContent = '';
}

export function sendCropToProcess() {
  const slicing = document.getElementById('cropSlicing').textContent;
  if (!slicing) return;
  const details = document.getElementById('detailsProcess');
  if (details) {
    details.open = true;
  }
  document.getElementById('processTile').value = slicing;
  document.getElementById('btnProcess').scrollIntoView({ behavior: 'smooth' });
  const detailsCrop = document.getElementById('detailsCrop');
  if (detailsCrop) detailsCrop.open = false;
}