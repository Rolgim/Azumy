import { openLightbox } from './lightbox.js';
import { API } from '../config.js';

export function renderGallery(entries) {
  const grid = document.getElementById('galleryGrid');
  const empty = document.getElementById('emptyState');

  if (!entries.length) {
    empty.style.display = 'block';
    return;
  }

  for (const entry of entries) {
    const card = document.createElement('div');
    card.className = 'gallery-card';

    card.innerHTML = `
        <img src="${API}${entry.preview_url}?t=${Date.now()}"
            alt="${entry.workdir}"
            loading="lazy">
        <div class="card-info">
            <div class="card-workdir">${entry.workdir}</div>
            <div class="card-meta">
            ${entry.filename} · ${entry.engine}
            </div>
        </div>
        `;

    card.addEventListener('click', () => openLightbox(entry));
    grid.appendChild(card);
  }
}