/**
 * Lógica de negocio del agente (sin acoplarse a WhatsApp).
 * Aquí conectaremos tu LLM / reglas cuando nos des las instrucciones.
 */
import {
  getGestoriaInfo,
  listCoches,
  getCoche,
  absoluteStaticUrl,
} from './ventacoches-api.js';

/** Resumen de catálogo para contexto del modelo o respuestas fijas */
export async function buildCatalogSummary(maxItems = 12) {
  const coches = await listCoches({ soloActivos: true });
  const slice = coches.slice(0, maxItems);
  const lines = slice.map(
    (c) =>
      `#${c.id} ${c.marca} ${c.modelo} (${c.año}) — $${c.precio} MXN — km ${c.kilometraje ?? '—'} — ${c.tipo_combustible || ''}`
  );
  return lines.join('\n');
}

export async function buildGestoriaContext() {
  const data = await getGestoriaInfo();
  return JSON.stringify(data, null, 2);
}

export async function describeCoche(id) {
  const c = await getCoche(id);
  const foto = absoluteStaticUrl(c.foto_principal);
  const partes = [
    `${c.marca} ${c.modelo} (${c.año})`,
    `Precio: $${c.precio} MXN`,
    c.kilometraje != null ? `Kilometraje: ${c.kilometraje} km` : null,
    c.tipo_combustible ? `Combustible: ${c.tipo_combustible}` : null,
    c.descripcion ? `Descripción: ${c.descripcion}` : null,
    foto ? `Foto: ${foto}` : null,
  ].filter(Boolean);
  return partes.join('\n');
}

/**
 * Punto de entrada provisional: clasificación muy simple por palabras clave.
 * Sustituir por tu flujo con IA cuando lo indiques.
 */
export async function handleUserTextMessage(text) {
  const t = (text || '').toLowerCase().trim();

  if (/coche|auto|vehículo|vehiculo|catálogo|catalogo|precio|bmw|nissan|toyota|honda/i.test(t)) {
    const summary = await buildCatalogSummary(15);
    return `Estos son algunos vehículos en inventario:\n\n${summary}\n\n¿Te interesa el número de alguno?`;
  }

  if (/gestor|trámite|tramite|placa|verificación|verificacion|tenencia/i.test(t)) {
    const ctx = await buildGestoriaContext();
    return `Información de gestoría (resumen interno para el asistente):\n${ctx.slice(0, 3500)}`;
  }

  if (/^#?\s*(\d+)$/.test(t) || /coche\s*#?\s*(\d+)/i.test(t)) {
    const m = t.match(/(\d+)/);
    if (m) {
      try {
        return await describeCoche(Number.parseInt(m[1], 10));
      } catch (e) {
        return 'No encontré ese vehículo. Prueba con otro número de inventario.';
      }
    }
  }

  return (
    'Puedo orientarte sobre trámites de **Gestoría Nacional** o sobre **vehículos en venta**. ' +
    'Pregunta por "gestoría" o por "coches", o escribe el número de un vehículo (ej. 5).'
  );
}
