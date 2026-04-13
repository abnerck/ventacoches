require('dotenv').config();

const fs = require('fs');
const path = require('path');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');

const SITE_URL = (process.env.SITE_URL || '').replace(/\/$/, '');
const SITE_URL_DISPLAY = SITE_URL ? `${SITE_URL}/` : '';
const BOT_KEY = (process.env.BOT_API_KEY || '').trim();
const DEEPSEEK_KEY = (process.env.DEEPSEEK_API_KEY || '').trim();

/** Chats que ya recibieron bienvenida en esta ejecución del bot */
const welcomedPrivateChats = new Set();

/** Chats privados en pausa (no se llama a la IA; !activar quita) */
const pausedPrivateChats = new Set();

/** Historial por chat para DeepSeek (solo texto usuario/asistente; el contexto va en system). */
const historyByChat = new Map();
const MAX_HISTORY_MESSAGES = 20; // 10 turnos aprox.

/** Antispam avisos de lead al mismo chat (ms) */
const LEAD_NOTIFY_COOLDOWN_MS = 12 * 60 * 1000;
const lastLeadNotifyAt = new Map();

function allowList() {
  const raw = (process.env.ALLOW_FROM || '').trim();
  if (!raw) return null;
  return raw.split(',').map((s) => s.replace(/\D/g, '')).filter(Boolean);
}

function isAllowedPrivate(from) {
  const list = allowList();
  if (!list || !list.length) return true;
  const digits = from.replace(/\D/g, '');
  return list.some((a) => digits.endsWith(a) || digits.includes(a));
}

function getHistory(chatId) {
  return historyByChat.get(chatId) || [];
}

function pushHistory(chatId, userText, assistantText) {
  let h = getHistory(chatId);
  h.push({ role: 'user', content: userText });
  h.push({ role: 'assistant', content: assistantText });
  if (h.length > MAX_HISTORY_MESSAGES) h = h.slice(-MAX_HISTORY_MESSAGES);
  historyByChat.set(chatId, h);
}

/** Números a avisar por WhatsApp (JID 521...@c.us) */
function leadNotifyJids() {
  const raw = (process.env.LEAD_NOTIFY_NUMBERS || process.env.LEAD_NOTIFY || '').trim();
  if (!raw) return [];
  return raw
    .split(/[,;\s]+/)
    .map((s) => s.replace(/\D/g, ''))
    .filter(Boolean)
    .map((d) => `${d}@c.us`);
}

/**
 * Heurística: interés claro en servicio o coche (evita avisar en cada “hola”).
 * Si el cliente solo dice “sí/ok”, exige que el último mensaje del bot invitara a continuar o preguntara algo concreto.
 */
function shouldNotifyLead(userText, assistantReply, history) {
  const t = (userText || '').trim();
  if (t.length < 2) return false;
  const lower = t.toLowerCase();
  const strong =
    /me interesa|quiero (comprar|el|la|ese|esa|saber|cotiz|informes|más info)|cotizaci|precio del|precio de|cuánto sale|cuanto sale|agendar|una cita|apartar|reservar|disponible|sigue disponible|hablar con (un )?asesor|me comunico|me pasas (el )?whatsapp|mándame|mandame|link del|ficha del|ver el coche|lo quiero/i.test(
      lower
    );
  const shortConfirm = /^(sí|si|ok|dale|va|claro|correcto|exacto|listo|perfecto|yep|yes)[\s!.¡?]*$/i.test(
    t.trim()
  );
  let lastAssistant = '';
  for (let i = history.length - 1; i >= 0; i--) {
    if (history[i].role === 'assistant') {
      lastAssistant = history[i].content || '';
      break;
    }
  }
  const lastBot = (lastAssistant || '').toLowerCase();
  const botOfferedFollowUp =
    /\?|te interesa|te late|quieres|quieres que|puedo (enviarte|pasarte|compartirte)|te mando|te comparto|agendar|una cita|siguiente paso|te ayudo con|confirm|te parece si|más detalle|información del|del vehículo|del trámite/i.test(
      lastBot
    );
  if (strong) return true;
  if (shortConfirm && botOfferedFollowUp) return true;
  return false;
}

async function notifyLeadsIfNeeded(client, msg, userText, assistantReply, history) {
  const jids = leadNotifyJids();
  if (!jids.length) return;
  if (!shouldNotifyLead(userText, assistantReply, history)) return;

  const chatId = msg.from;
  const now = Date.now();
  const prev = lastLeadNotifyAt.get(chatId) || 0;
  if (now - prev < LEAD_NOTIFY_COOLDOWN_MS) return;
  lastLeadNotifyAt.set(chatId, now);

  let name = '';
  try {
    const c = await msg.getContact();
    name = (c.pushname || c.name || '').trim();
  } catch (_) {}

  const previewUser = userText.length > 220 ? `${userText.slice(0, 220)}…` : userText;
  const previewBot = assistantReply.length > 280 ? `${assistantReply.slice(0, 280)}…` : assistantReply;
  const body =
    `🔔 *Posible lead*\n` +
    `De: ${name || '(sin nombre)'} \`${chatId.replace(/@c\.us$/, '')}\`\n` +
    `Cliente escribió:\n${previewUser}\n\n` +
    `Última respuesta del bot (extracto):\n${previewBot}`;

  for (const jid of jids) {
    try {
      await client.sendMessage(jid, body);
      console.log('[lead] Aviso enviado a', jid);
    } catch (e) {
      console.error('[lead] No se pudo avisar a', jid, e.message || e);
    }
  }
}

function requireEnv() {
  const missing = [];
  if (!SITE_URL) missing.push('SITE_URL');
  if (!BOT_KEY) missing.push('BOT_API_KEY');
  if (!DEEPSEEK_KEY) missing.push('DEEPSEEK_API_KEY');
  if (missing.length) {
    console.error('Falta en .env:', missing.join(', '));
    console.error('Copia .env.example a .env y rellena.');
    process.exit(1);
  }
}

const api = axios.create({
  baseURL: SITE_URL,
  timeout: 60000,
  headers: { 'X-Bot-Key': BOT_KEY },
  validateStatus: () => true,
});

async function fetchContext() {
  const [g, c] = await Promise.all([
    api.get('/api/bot/gestoria'),
    api.get('/api/bot/coches', { params: { activos: 'true' } }),
  ]);
  if (g.status !== 200) throw new Error(`gestoria HTTP ${g.status}: ${JSON.stringify(g.data)}`);
  if (c.status !== 200) throw new Error(`coches HTTP ${c.status}: ${JSON.stringify(c.data)}`);
  return { gestoria: g.data, coches: c.data };
}

function buildContextText({ gestoria, coches }) {
  const g = gestoria || {};
  const nombre = g.nombre || 'Gestoría';
  const bloques = [];

  bloques.push(`=== ${nombre} ===`);
  if (g.eslogan) bloques.push(g.eslogan);
  if (g.descripcion_corta) bloques.push(g.descripcion_corta);
  if (g.quienes_somos) bloques.push(`QUIÉNES SOMOS:\n${g.quienes_somos}`);

  if (Array.isArray(g.por_que_elegirnos) && g.por_que_elegirnos.length) {
    bloques.push(
      'POR QUÉ ELEGIRNOS:\n' +
        g.por_que_elegirnos.map((x) => `- ${x.titulo}: ${x.texto}`).join('\n')
    );
  }
  if (Array.isArray(g.estadisticas) && g.estadisticas.length) {
    bloques.push(
      'DATOS:\n' + g.estadisticas.map((e) => `- ${e.valor} ${e.etiqueta}`).join('\n')
    );
  }
  if (Array.isArray(g.servicios_generales) && g.servicios_generales.length) {
    bloques.push('SERVICIOS GENERALES:\n' + g.servicios_generales.map((s) => `- ${s}`).join('\n'));
  }
  if (Array.isArray(g.insumos_documentacion) && g.insumos_documentacion.length) {
    bloques.push(
      'INSUMOS Y DOCUMENTACIÓN:\n' + g.insumos_documentacion.map((s) => `- ${s}`).join('\n')
    );
  }
  if (g.tramites_por_estado && typeof g.tramites_por_estado === 'object') {
    const lines = ['TRÁMITES POR ESTADO:'];
    for (const [estado, lista] of Object.entries(g.tramites_por_estado)) {
      if (!Array.isArray(lista)) continue;
      lines.push(`\n${estado}:`);
      lista.forEach((t) => lines.push(`  - ${t}`));
    }
    bloques.push(lines.join('\n'));
  }
  if (Array.isArray(g.proceso_envio) && g.proceso_envio.length) {
    bloques.push(
      'CÓMO FUNCIONA EL ENVÍO:\n' +
        g.proceso_envio
          .map((p) => `${p.paso}. ${p.titulo}: ${p.detalle || ''}`)
          .join('\n')
    );
  }
  if (Array.isArray(g.notas_importantes) && g.notas_importantes.length) {
    bloques.push('IMPORTANTE:\n' + g.notas_importantes.map((n) => `- ${n}`).join('\n'));
  }
  const c = g.contacto || {};
  if (Object.keys(c).length) {
    bloques.push(
      'CONTACTO Y HORARIO:\n' +
        [
          c.ubicacion && `Ubicación: ${c.ubicacion}`,
          c.telefono && `Teléfono: ${c.telefono}`,
          c.whatsapp && `WhatsApp: ${c.whatsapp}`,
          c.email && `Email: ${c.email}`,
          c.horario && `Horario: ${c.horario}`,
          c.nota_atencion && `Nota: ${c.nota_atencion}`,
        ]
          .filter(Boolean)
          .join('\n')
    );
  }
  if (Array.isArray(g.servicios) && g.servicios.length) {
    const extra = g.servicios.map((s) => `- ${s.titulo}: ${s.resumen || ''}`.trim()).join('\n');
    if (extra) bloques.push(`RESUMEN:\n${extra}`);
  }

  const cars = (coches || [])
    .slice(0, 50)
    .map(
      (c) =>
        `ID ${c.id}: ${c.marca} ${c.modelo} (${c.año}) — precio ${c.precio} MXN, km ${c.kilometraje ?? 'n/d'}`
    )
    .join('\n');
  bloques.push(cars ? `COCHES EN VENTA (resumen):\n${cars}` : 'COCHES: sin activos en lista.');

  return bloques.filter(Boolean).join('\n\n');
}

function loadExtraInstructions() {
  const fromEnv = (process.env.BOT_EXTRA_INSTRUCTIONS || '').replace(/\\n/g, '\n').trim();
  const fileName = (process.env.BOT_INSTRUCTIONS_FILE || 'instructions.txt').trim();
  const filePath = path.isAbsolute(fileName) ? fileName : path.join(__dirname, fileName);
  let fromFile = '';
  try {
    if (fs.existsSync(filePath)) {
      fromFile = fs.readFileSync(filePath, 'utf8').trim();
    }
  } catch (_) {
    /* ignore */
  }
  return [fromEnv, fromFile].filter(Boolean).join('\n\n');
}

async function deepseekAnswer(userMessage, contextBlock, history, { isFirstInChat } = {}) {
  const url = SITE_URL_DISPLAY || '(configura SITE_URL en .env)';
  let system = `Eres el chat de Gestoría Nacional (Cuernavaca/Morelos): trámites vehiculares y coches. Español de México, tono de WhatsApp: natural, directo, amable.

MEMORIA / HILO (muy importante)
- Recibes el historial de ESTE chat en los mensajes anteriores (usuario y asistente). Úsalo siempre: no ignores lo que ya acordaron o preguntaron.
- Si el cliente responde con confirmaciones cortas ("sí", "ok", "dale", "va", "claro"), interpreta según TU último mensaje: el siguiente paso concreto (dato que falta, cita, enlace, qué documento llevar, siguiente pregunta). NO reinicies con "¿en qué te puedo ayudar?" ni un saludo genérico si ya venían hablando de un trámite o un coche.
- Si la confirmación es ambigua, pide UNA aclaración mínima en una sola frase.

ESTILO
- Respuestas CORTAS (pocos párrafos). Evita plantillas largas de bienvenida.
- No empieces con "¡Hola!" ni "Gracias por contactar..." en cada mensaje. Si el cliente ya saludó, ve al grano.
- Máximo 1 emoji por mensaje si encaja; a veces ninguno.
- Resuelve con lo que ya viene en DATOS_ACTUALES (trámites por estado, proceso de envío, servicios, coches, horario, teléfono). No des la sensación de que "solo un asesor humano puede ayudarte": tú resuelves con esa información.
- Si falta un dato concreto (por ejemplo precio de un trámite o plazo legal exacto), dilo en una frase sin sermón y ofrece el teléfono/horario del bloque de contacto solo si hace falta.

PRECIOS
- No inventes precios de trámites ni de envío. Si no están en DATOS_ACTUALES, di que la cotización es según trámite y destino (sin cifras).
- Coches: si en la lista viene precio, puedes mencionarlo; si no, no inventes.

WEB
- URL oficial (copiar tal cual): ${url}
- En mensajes siguientes NO repitas el enlace salvo que pregunten por la página, ver más, catálogo online, etc.
${
  isFirstInChat
    ? `- PRIMER mensaje de este contacto en WhatsApp: una sola respuesta fluida. Al final, en una línea aparte, el enlace al sitio (la URL de arriba). No hagas un segundo saludo tipo "hola" dentro del mismo texto; no repitas agradecimientos largos.`
    : ''
}`;
  const extra = loadExtraInstructions();
  if (extra) {
    system += `\n\n---\nInstrucciones adicionales del negocio (prioridad alta):\n${extra}`;
  }

  const systemWithData = `${system}\n\n---\nDATOS_ACTUALES (inventario y gestoría; úsalos para responder):\n${contextBlock}`;

  const messages = [{ role: 'system', content: systemWithData }, ...history, { role: 'user', content: userMessage }];

  const r = await axios.post(
    'https://api.deepseek.com/chat/completions',
    {
      model: 'deepseek-chat',
      messages,
      max_tokens: 800,
      temperature: 0.42,
    },
    {
      headers: {
        Authorization: `Bearer ${DEEPSEEK_KEY}`,
        'Content-Type': 'application/json',
      },
      timeout: 120000,
    }
  );
  if (r.status !== 200) throw new Error(`DeepSeek ${r.status}: ${JSON.stringify(r.data)}`);
  const text = r.data?.choices?.[0]?.message?.content;
  if (!text) throw new Error('DeepSeek sin texto en la respuesta');
  return text.trim();
}

requireEnv();

const client = new Client({
  authStrategy: new LocalAuth({ dataPath: '.wwebjs_auth' }),
  puppeteer: {
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  },
});

client.on('qr', (qr) => {
  console.log('Escanea este QR con WhatsApp (Dispositivos vinculados):');
  qrcode.generate(qr, { small: true });
});

client.on('authenticated', () => console.log('Autenticado, iniciando sesión…'));
client.on('auth_failure', (m) => console.error('Fallo de auth:', m));
client.on('disconnected', (r) => console.warn('Desconectado:', r));

client.on('ready', async () => {
  console.log('Listo. SITE_URL=', SITE_URL);
  try {
    const ctx = await fetchContext();
    console.log('API OK: coches en catálogo ≈', (ctx.coches || []).length);
  } catch (e) {
    console.error('No pude leer la API del sitio (revisa SITE_URL y BOT_API_KEY):', e.message);
  }
});

client.on('message', async (msg) => {
  try {
    if (msg.fromMe) return;
    const chat = await msg.getChat();
    if (chat.isGroup) return;
    if (!isAllowedPrivate(msg.from)) return;
    const text = (msg.body || '').trim();
    if (!text) return;

    const cmd = text.toLowerCase();

    if (cmd === '!pausar') {
      pausedPrivateChats.add(msg.from);
      await msg.reply(
        '⏸️ Este chat quedó en pausa: no responderé con la IA hasta que escribas !activar\n' +
          '(Los comandos !pausar, !activar y !estado siguen funcionando.)'
      );
      return;
    }
    if (cmd === '!activar') {
      const was = pausedPrivateChats.delete(msg.from);
      await msg.reply(
        was
          ? '▶️ Chat activado de nuevo. ¿En qué te ayudo?'
          : 'Este chat ya estaba activo.'
      );
      return;
    }
    if (cmd === '!estado') {
      const n = pausedPrivateChats.size;
      const here = pausedPrivateChats.has(msg.from) ? 'Sí' : 'No';
      await msg.reply(
        `📋 Estado del bot: en línea.\n` +
          `Chats en pausa (total): ${n}\n` +
          `Este chat pausado: ${here}\n\n` +
          `Comandos: !pausar · !activar · !estado`
      );
      return;
    }

    if (pausedPrivateChats.has(msg.from)) return;

    const ctx = await fetchContext();
    const block = buildContextText(ctx);
    const hist = getHistory(msg.from);
    const isFirstInChat = !welcomedPrivateChats.has(msg.from);
    const reply = await deepseekAnswer(text, block, hist, { isFirstInChat });
    if (isFirstInChat) welcomedPrivateChats.add(msg.from);
    await msg.reply(reply);
    pushHistory(msg.from, text, reply);
    await notifyLeadsIfNeeded(client, msg, text, reply, hist);
  } catch (e) {
    console.error(e);
    try {
      await msg.reply('Ahora no puedo responder. Intenta en unos minutos o visita nuestra web.');
    } catch (_) {}
  }
});

client.initialize();
