import 'dotenv/config';

function requireEnv(name) {
  const v = process.env[name];
  if (!v || !String(v).trim()) {
    throw new Error(`Falta variable de entorno: ${name}`);
  }
  return String(v).trim().replace(/\/$/, '');
}

export const config = {
  apiBase: requireEnv('VENTACOCHES_API_BASE'),
  botApiKey: requireEnv('BOT_API_KEY'),
  publicSiteUrl: (process.env.PUBLIC_SITE_URL || process.env.VENTACOCHES_API_BASE).replace(/\/$/, ''),
};
