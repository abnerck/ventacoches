/**
 * Coloca aquí la integración real con WhatsApp.
 *
 * Opciones habituales en VPS:
 * - Twilio API for WhatsApp (HTTP, sin navegador)
 * - Meta WhatsApp Cloud API
 * - whatsapp-web.js (Puppeteer + sesión; más frágil en servidor)
 *
 * Ejemplo de flujo:
 *   1) Recibes mensaje entrante del proveedor
 *   2) const reply = await handleUserTextMessage(texto)
 *   3) Envías reply al usuario con el SDK del proveedor
 */
import { handleUserTextMessage } from './bot-core.js';

export async function onIncomingTextMessage({ body }) {
  return handleUserTextMessage(body);
}
