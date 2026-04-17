import pkg from 'whatsapp-web.js';
import qrcode from 'qrcode-terminal';
import { config } from './config.js';
import { buildFullContextForLLM } from './bot-core.js';
import { replyWithDeepSeek } from './llm-deepseek.js';

const { Client, LocalAuth } = pkg;
const RECONNECT_BASE_DELAY_MS = 5_000;
const RECONNECT_MAX_DELAY_MS = 60_000;

/** @type {Map<string, {role: string, content: string}[]>} */
const historyByChat = new Map();

function getHistory(chatId) {
  return historyByChat.get(chatId) || [];
}

function pushTurn(chatId, userText, assistantText) {
  let h = getHistory(chatId);
  h.push({ role: 'user', content: userText });
  h.push({ role: 'assistant', content: assistantText });
  if (h.length > 24) h = h.slice(-24);
  historyByChat.set(chatId, h);
}

export function createWhatsAppClient() {
  const puppeteerConfig = {
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  };
  if (config.puppeteerExecutablePath) {
    puppeteerConfig.executablePath = config.puppeteerExecutablePath;
  }

  const client = new Client({
    authStrategy: new LocalAuth({
      clientId: 'gestoria-nacional',
      dataPath: '.wwebjs_auth',
    }),
    puppeteer: puppeteerConfig,
  });
  let reconnectAttempts = 0;
  let reconnectTimer = null;
  let reconnectInProgress = false;

  function getReconnectDelay() {
    const exp = Math.min(reconnectAttempts, 6);
    const delay = RECONNECT_BASE_DELAY_MS * 2 ** exp;
    return Math.min(delay, RECONNECT_MAX_DELAY_MS);
  }

  async function scheduleReconnect(reason) {
    if (reconnectTimer || reconnectInProgress) return;
    const delay = getReconnectDelay();
    reconnectAttempts += 1;
    console.warn(
      `[wa] Reintentando reconexion en ${Math.round(delay / 1000)}s. Motivo:`,
      reason
    );
    reconnectTimer = setTimeout(async () => {
      reconnectTimer = null;
      reconnectInProgress = true;
      try {
        await client.initialize();
      } catch (err) {
        console.error('[wa] Fallo al reconectar:', err?.message || err);
        reconnectInProgress = false;
        await scheduleReconnect('initialize error');
        return;
      }
      reconnectInProgress = false;
    }, delay);
  }

  client.on('qr', (qr) => {
    console.log('[wa] Escanea el QR con WhatsApp → Dispositivos vinculados');
    qrcode.generate(qr, { small: true });
  });

  client.on('ready', () => {
    reconnectAttempts = 0;
    console.log('[wa] Cliente listo');
  });

  client.on('auth_failure', (m) => {
    console.error('[wa] Fallo de autenticación:', m);
    scheduleReconnect('auth_failure').catch((err) => {
      console.error('[wa] Error programando reconexion:', err?.message || err);
    });
  });

  client.on('disconnected', (r) => {
    console.warn('[wa] Desconectado:', r);
    scheduleReconnect(r || 'disconnected').catch((err) => {
      console.error('[wa] Error programando reconexion:', err?.message || err);
    });
  });

  client.on('message', async (msg) => {
    try {
      if (msg.fromMe) return;
      if (msg.from === 'status@broadcast') return;

      const chat = await msg.getChat();
      if (chat.isGroup && !config.allowGroups) return;

      const text = (msg.body || '').trim();
      if (!text) return;

      await chat.sendStateTyping();

      const contextBlock = await buildFullContextForLLM();
      const chatId = msg.from;
      const history = getHistory(chatId);

      const answer = await replyWithDeepSeek({
        userMessage: text,
        contextBlock,
        history,
      });

      pushTurn(chatId, text, answer);
      await msg.reply(answer);
    } catch (e) {
      console.error('[wa] Error al responder:', e);
      try {
        await msg.reply(
          'Hubo un error al procesar tu mensaje. Intenta de nuevo en un momento.'
        );
      } catch (_) {
        /* ignore */
      }
    }
  });

  return client;
}
