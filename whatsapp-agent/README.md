# Agente WhatsApp (solo VPS / tu PC)

Esta carpeta **no va en el Git del sitio web**. Cópiala al servidor con `scp`/`rsync` o mantén un **repositorio Git aparte** solo para el bot.

## Stack

- **whatsapp-web.js** + Puppeteer (sesión en `.wwebjs_auth/`)
- **DeepSeek** vía API compatible OpenAI (`https://api.deepseek.com`)
- Datos de **gestoría + coches** desde tu sitio: `GET /api/bot/*` + cabecera `X-Bot-Key`

## Requisitos en PythonAnywhere

`BOT_API_KEY` en el `.env` de Flask (misma clave que en `.env` del agente).

## VPS (Ubuntu ejemplo)

```bash
sudo apt update
sudo apt install -y chromium-browser fonts-liberation libappindicator3-1 || true
```

Si Puppeteer no encuentra Chrome:

```bash
which chromium-browser || which chromium
# Pon en .env:
# PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser
```

## Instalación

```bash
cd whatsapp-agent
npm install
cp .env.example .env
nano .env
npm start
```

Primera vez: escanea el **QR** en consola. La sesión queda en `.wwebjs_auth/`.

## Probar sin abrir WhatsApp

```bash
node src/index.js --demo coches
node src/index.js --demo-llm "¿Qué coches tienen y qué trámites hacen?"
```

## Producción

Usa `pm2`, `systemd` o `screen` para mantener el proceso vivo. Reinicia si cambias `.env`.

## Personalización

- Tono y reglas: `src/prompts.js`
- Lógica de contexto: `src/bot-core.js`
