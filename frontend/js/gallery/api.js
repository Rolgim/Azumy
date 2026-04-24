import { API } from '../config.js';

export async function fetchGallery() {
  const resp = await fetch(`${API}/workspace/gallery`);
  if (!resp.ok) return [];

  const data = await resp.json();
  return data.entries ?? [];
}