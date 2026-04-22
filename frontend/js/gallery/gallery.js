import { fetchGallery } from './api.js';
import { renderGallery } from './render.js';
import { initLightbox } from './lightbox.js';

async function init() {
  initLightbox(); 
  const entries = await fetchGallery();
  renderGallery(entries);
}

init();