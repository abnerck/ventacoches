/**
 * Arranque del proceso en el VPS.
 * Conecta aquí tu proveedor de WhatsApp (Twilio, whatsapp-web.js, Cloud API, etc.).
 *
 * npm install dotenv
 * cp .env.example .env   # y edita
 * npm start
 */
import { config } from './config.js';
import { healthCheck } from './ventacoches-api.js';
import { handleUserTextMessage } from './bot-core.js';

async function main() {
  console.log('[agent] Comprobando API…', config.apiBase);
  const h = await healthCheck();
  console.log('[agent] API OK:', h);

  // --- Demo por consola (quitar cuando enchufes WhatsApp) ---
  if (process.argv.includes('--demo')) {
    const q = process.argv.slice(process.argv.indexOf('--demo') + 1).join(' ') || 'hola';
    const reply = await handleUserTextMessage(q);
    console.log('\n--- respuesta ---\n', reply);
    return;
  }

  console.log(
    '[agent] Listo. Añade tu integración WhatsApp en src/whatsapp-adapter.js\n' +
      '  Prueba contexto: node src/index.js --demo coches en venta'
  );
}

main().catch((e) => {
  console.error('[agent] Error:', e.message);
  process.exit(1);
});
