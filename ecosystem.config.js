// ecosystem.config.js
const path = require('path');
const fs   = require('fs');

function resolveAppDir(appName) {
  const candidates = [
    process.env.APP_DIR,                                            // caminho explícito
    process.env.DASH_ROOT && path.join(process.env.DASH_ROOT, appName), // base + app
    path.join(__dirname, appName),                                  // pasta irmã
    __dirname,                                                      // mesma pasta do ecosystem
    process.cwd()                                                   // diretório de execução
  ]
    .filter(Boolean)
    .map(p => path.resolve(p));

  for (const dir of candidates) {
    if (fs.existsSync(path.join(dir, 'server.js'))) {
      return dir;
    }
  }
  // fallback: primeiro candidato válido ou __dirname
  return candidates[0] || __dirname;
}

const APP_NAME  = process.env.APP_NAME || 'sad';
const APP_DIR   = resolveAppDir(APP_NAME);
const PORT_PROD = Number(process.env.PORT || process.env.PORT_PROD || 8052); // padrão 8052
const PORT_DEV  = Number(process.env.PORT_DEV || 8053);
const LOG_DIR   = path.resolve(process.env.LOG_DIR || path.join(APP_DIR, 'logs'));

module.exports = {
  apps: [
    // Produção (sem watch)
    {
      name: APP_NAME,                  // "sad"
      script: 'server.js',
      cwd: APP_DIR,
      instances: 1,
      exec_mode: 'fork',
      watch: false,
      env: {
        PORT: PORT_PROD,
        NODE_ENV: 'production'
      },
      error_file: path.join(LOG_DIR, 'pm2-error.log'),
      out_file:   path.join(LOG_DIR, 'pm2-out.log'),
      time: true
    },

    // Desenvolvimento (com watch) — opcional
    {
      name: `${APP_NAME}-dev`,
      script: 'server.js',
      cwd: APP_DIR,
      instances: 1,
      exec_mode: 'fork',
      watch: [
        'server.js',
        'index.html',
        'img'
      ],
      ignore_watch: [
        'node_modules',
        'logs',
        '.git',
        '.pm2',
        'dataset' // remova se quiser reiniciar ao mudar dados
      ],
      watch_options: {
        usePolling: true,
        interval: 1000
      },
      env: {
        PORT: PORT_DEV,
        NODE_ENV: 'development'
      },
      error_file: path.join(LOG_DIR, 'pm2-error-dev.log'),
      out_file:   path.join(LOG_DIR, 'pm2-out-dev.log'),
      time: true
    }
  ]
};
