# Agente WhatsApp (Node en VPS) + API en la web (PythonAnywhere)

La carpeta **`whatsapp-agent/`** está en **`.gitignore`**: el repo versiona el **sitio Flask** y la **API `/api/bot/*`**; el proceso Node se despliega aparte en el VPS.

## API `/api/bot/*` (en `app.py`)

Todas requieren cabecera **`X-Bot-Key`**: el mismo valor que **`BOT_API_KEY`** en el `.env` del servidor (PythonAnywhere).

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/bot/health` | Comprueba clave y servicio; `absolute_media` indica si `PUBLIC_SITE_URL` está configurada. |
| GET | `/api/bot/gestoria` | JSON de `data/gestoria_servicios.json`. |
| GET | `/api/bot/coches` | Lista de coches; query `activos=false` para incluir inactivos. |
| GET | `/api/bot/coche/<id>` | Detalle + lista `fotos` (URLs). |

**`PUBLIC_SITE_URL`** (opcional, sin `/` final): si está definida en el servidor (ej. `https://tuusuario.pythonanywhere.com`), las rutas de fotos salen como URL absoluta para que el bot pueda enviar enlaces válidos en WhatsApp.

### Variables en PythonAnywhere (Web → Variables de entorno o `.env`)

- `BOT_API_KEY` — obligatoria para que la API responda al bot.
- `PUBLIC_SITE_URL` — recomendada para fotos absolutas.

Tras cambiar variables: **Reload** de la web app.

### Probar desde tu PC (sustituye URL y clave)

```bash
curl -sS -H "X-Bot-Key: TU_CLAVE" "https://TUUSUARIO.pythonanywhere.com/api/bot/health"
```

## Qué sube con Git

- `app.py` (incluye `/api/bot/*`)
- `data/gestoria_servicios.json`
- `.env.example` (plantilla; **no** subas `.env`)

## Dónde está el bot

En tu PC: `whatsapp-agent/` junto al proyecto (por comodidad), **sin** `git push` al repo principal.

## Llevar el agente al VPS

```powershell
scp -r C:\Users\abner\OneDrive\Escritorio\ventacoches\whatsapp-agent usuario@TU_VPS:/home/usuario/
```

En el VPS:

```bash
cd ~/whatsapp-agent
cp .env.example .env
nano .env
npm install
npm start
```

En el `.env` del bot: URL base del sitio en PA, la misma `BOT_API_KEY`, y claves DeepSeek / sesión WhatsApp según tu `whatsapp-agent`.

## Opcional: repo Git solo del agente

```bash
cd whatsapp-agent
git init
git add .
git commit -m "agente"
```

Remoto privado (GitHub/GitLab) solo para el bot.
