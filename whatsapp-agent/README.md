# Agente WhatsApp (VPS) — Gestoría Nacional + inventario

Carpeta **independiente** del sitio Flask: se despliega en un **VPS** y habla con la base de datos **solo a través de HTTPS** hacia tu sitio en **PythonAnywhere**.

## Por qué no hay conexión directa a la BD

- En PythonAnywhere la base es **SQLite** (`instance/cars.db`): es un archivo local.
- No está expuesta por red; un VPS **no puede** montar ni abrir ese archivo.
- Solución: el sitio Flask expone **`/api/bot/*`** con la cabecera **`X-Bot-Key`** (igual que la variable `BOT_API_KEY` en el servidor).

## En PythonAnywhere (Flask)

1. En el `.env` del proyecto (o variables del panel), define una clave larga aleatoria:

   `BOT_API_KEY=tu_clave_secreta_larga`

2. **Reload** de la web app.

3. Comprueba (sustituye dominio y clave):

   ```bash
   curl -s -H "X-Bot-Key: tu_clave_secreta_larga" https://TU-DOMINIO/api/bot/health
   ```

4. Edita los textos de gestoría en el repo: `data/gestoria_servicios.json` (el bot los obtiene con `GET /api/bot/gestoria`).

## En el VPS (este agente)

```bash
cd whatsapp-agent
cp .env.example .env
# Edita VENTACOCHES_API_BASE, BOT_API_KEY, PUBLIC_SITE_URL
npm install dotenv
npm start
```

Prueba sin WhatsApp:

```bash
node src/index.js --demo qué coches tienen
node src/index.js --demo gestoría
node src/index.js --demo 5
```

## Rutas API del bot (Flask)

| Método | Ruta | Uso |
|--------|------|-----|
| GET | `/api/bot/health` | Comprobar clave y red |
| GET | `/api/bot/gestoria` | JSON de servicios / FAQ |
| GET | `/api/bot/coches?activos=true` | Listado para el agente |
| GET | `/api/bot/coche/<id>` | Detalle + lista de rutas de fotos |

Todas requieren cabecera: `X-Bot-Key: <BOT_API_KEY>`.

## Siguiente paso

Indica cómo quieres el comportamiento del bot (tono, reglas, si usa OpenAI, Twilio, etc.) y enlazamos `src/whatsapp-adapter.js` y `src/bot-core.js` a tu flujo real.
