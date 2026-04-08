# Agente WhatsApp (fuera de este repositorio)

La carpeta **`whatsapp-agent/`** está en **`.gitignore`**: el repositorio `ventacoches` solo versiona el **sitio web** (Flask + plantillas + `data/gestoria_servicios.json` + API `/api/bot/*`).

## Qué sí sube con Git

- `app.py` (rutas `/api/bot/...` y `BOT_API_KEY`)
- `data/gestoria_servicios.json`

## Dónde está el bot

En tu máquina de desarrollo: `whatsapp-agent/` dentro del mismo proyecto (por comodidad), pero **no se hace push**.

## Cómo llevarlo al VPS

Desde tu PC (Windows PowerShell ejemplo; ajusta usuario e IP):

```powershell
scp -r C:\Users\abner\OneDrive\Escritorio\ventacoches\whatsapp-agent usuario@TU_VPS:/home/usuario/
```

O con **rsync** desde WSL/Linux.

En el VPS:

```bash
cd ~/whatsapp-agent
cp .env.example .env
nano .env
npm install
npm start
```

## Opcional: Git solo del agente

```bash
cd whatsapp-agent
git init
git add .
git commit -m "agente"
```

Y un remoto privado (GitHub/GitLab) solo para el bot.
