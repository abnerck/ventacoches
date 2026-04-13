# Agente WhatsApp (VPS)

Código en **`whatsapp-agent/`** (Node.js): **whatsapp-web.js** (QR) + **DeepSeek** + API **`/api/bot/*`** del sitio en PythonAnywhere.

## En el servidor (VPS) — comandos

```bash
cd ~
# Si el repo ya está en el VPS:
cd ruta/al/ventacoches/whatsapp-agent
# O clona el repo y entra a whatsapp-agent

cp .env.example .env
nano .env   # SITE_URL, BOT_API_KEY (igual que Flask), DEEPSEEK_API_KEY

# Node 18+ recomendado
npm install
npm start
```

La primera vez aparece un **QR en la terminal**: WhatsApp → Ajustes → Dispositivos vinculados → Vincular.

## Producción (que no se caiga al cerrar SSH)

```bash
sudo apt install -y screen   # o usa pm2: npm i -g pm2
screen -S wa
cd ~/ventacoches/whatsapp-agent && npm start
# Ctrl+A, D para desenganchar
```

## Si Puppeteer / Chrome falla (Ubuntu)

```bash
sudo apt update
sudo apt install -y ca-certificates fonts-liberation libnss3 libatk1.0-0 libgbm1 libxss1 libasound2
```

## Variables `.env` del bot

| Variable | Ejemplo |
|----------|---------|
| `SITE_URL` | `https://gestorianacional.com.mx` |
| `BOT_API_KEY` | Misma que en Flask / `.env` de PA |
| `DEEPSEEK_API_KEY` | De [platform.deepseek.com](https://platform.deepseek.com) |
| `ALLOW_FROM` | Opcional: `521234567890,5219988776655` (solo esos números) |
| `LEAD_NOTIFY_NUMBERS` | Opcional: números **México** `521…` separados por coma. Si el bot detecta interés claro (ej. “me interesa”, “quiero cotizar”, “sí” tras una oferta), envía un aviso por WhatsApp a esos números (máx. uno cada ~12 min por chat). |

## Actualizar solo el agente (Git + VPS)

El agente vive en la carpeta **`whatsapp-agent/`** del mismo repo que Flask. No hace falta un repo aparte salvo que quieras uno.

1. **Aquí (PC):** cambias `whatsapp-agent/`, haces `git add`, `commit` y `push` al repo (toda la app o solo archivos del agente).
2. **En el VPS:** entras al **directorio raíz del repo** (donde está `whatsapp-agent/`), `git pull`, y **solo reinicias el bot** (no hace falta tocar PythonAnywhere si no cambiaste Flask):

```bash
cd ~/ventacoches   # o la ruta donde clonaste el repo
git pull
cd whatsapp-agent
# si cambió package.json:
# npm install
screen -r wabot   # o como llames a la sesión
# Ctrl+C y luego:
npm start
# Ctrl+A, D
```

Si el VPS solo tiene **copiada** la carpeta `whatsapp-agent` sin git, entonces o clonas el repo completo una vez, o sincronizas con `rsync`/`scp` desde tu máquina; lo recomendable es **mismo repo** y `git pull` en la raíz.

## Comandos en WhatsApp (chat privado)

| Comando | Efecto |
|---------|--------|
| `!pausar` | Ese chat deja de recibir respuestas de la IA hasta `!activar`. |
| `!activar` | Quita la pausa en ese chat. |
| `!estado` | Cuántos chats están en pausa en total y si el tuyo está pausado. |

La pausa es por chat y vive en memoria: si reinicias el bot, se olvida.

## API en Flask

Ver rutas `/api/bot/*` en `app.py`. El WSGI en PA debe cargar `BOT_API_KEY` (y `load_dotenv` del `.env` del proyecto).
