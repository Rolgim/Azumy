import { API } from '../config.js';

function isTiff(url) {
    return url.endsWith('.tif') || url.endsWith('.tiff');
  }

export function openLightbox(entry) {
  const lb      = document.getElementById('lightbox');
  const img     = document.getElementById('lightboxImg');
  const spinner = document.getElementById('lightboxSpinner');
  const info    = document.getElementById('lightboxInfo');

  lb.classList.add('open');

  img.style.display = 'none';
  spinner.style.display = 'block';
  spinner.textContent = 'Loading…';
  info.textContent = 
  '';

  const fullImg = new Image();

  fullImg.onload = () => {
    img.src = fullImg.src;
    img.style.display = 'block';
    spinner.style.display = 'none';

    info.textContent = `${entry.workdir} · ${entry.size_mb} MB · ${entry.engine}`;
  };

  fullImg.onerror = () => {
    spinner.textContent = 'Failed to load image';
  };

  const finalUrl = isTiff(entry.full_url)
    ? entry.preview_url
    : entry.full_url;

  fullImg.src = `${API}${finalUrl}?t=${Date.now()}`;
}

export function initLightbox() {
  const lb       = document.getElementById('lightbox');
  const img      = document.getElementById('lightboxImg');
  const closeBtn = document.getElementById('lightboxClose');

  closeBtn.addEventListener('click', closeLightbox);

  lb.addEventListener('click', (e) => {
    if (e.target === lb) closeLightbox();
  });

  img.addEventListener('click', (e) => e.stopPropagation());

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeLightbox();
  });
}

export function closeLightbox() {
  const lb  = document.getElementById('lightbox');
  const img = document.getElementById('lightboxImg');

  lb.classList.remove('open');
  img.src = '';
}