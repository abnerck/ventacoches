import { config } from './config.js';

/**
 * Cliente HTTP hacia Flask en PythonAnywhere.
 * No hay conexión directa a SQLite desde el VPS: todo pasa por HTTPS + X-Bot-Key.
 */
async function botFetch(path, options = {}) {
  const url = `${config.apiBase}${path.startsWith('/') ? path : `/${path}`}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Bot-Key': config.botApiKey,
      ...(options.headers || {}),
    },
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    const err = new Error(data?.error || `HTTP ${res.status}`);
    err.status = res.status;
    err.body = data;
    throw err;
  }
  return data;
}

export async function healthCheck() {
  return botFetch('/api/bot/health');
}

export async function getGestoriaInfo() {
  return botFetch('/api/bot/gestoria');
}

export async function listCoches({ soloActivos = true } = {}) {
  const q = soloActivos ? '?activos=true' : '?activos=false';
  return botFetch(`/api/bot/coches${q}`);
}

export async function getCoche(id) {
  return botFetch(`/api/bot/coche/${id}`);
}

/** Convierte ruta /static/... en URL absoluta para enviar por WhatsApp */
export function absoluteStaticUrl(maybePath) {
  if (!maybePath) return null;
  if (maybePath.startsWith('http')) return maybePath;
  return `${config.publicSiteUrl}${maybePath.startsWith('/') ? '' : '/'}${maybePath}`;
}
