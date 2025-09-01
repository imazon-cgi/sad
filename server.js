// server.js (fallback sem pattern p/ evitar path-to-regexp)
const path = require('path');
const express = require('express');
const compression = require('compression');
const helmet = require('helmet');

const app = express();
const PORT = process.env.PORT || 3000;

const ROOT_DIR = __dirname;
const DATASET_DIR = path.join(ROOT_DIR, 'dataset');
app.use(
  helmet({
    contentSecurityPolicy: {
      useDefaults: true,
      directives: {
        "default-src": ["'self'"],
        "script-src": [
          "'self'",
          "'unsafe-inline'",
          "'unsafe-eval'",             
          "https://code.jquery.com",
          "https://cdn.jsdelivr.net",
          "https://unpkg.com",
          "https://cdnjs.cloudflare.com",
          "https://cdn.datatables.net"
        ],
        "style-src": [
          "'self'",
          "'unsafe-inline'",
          "https://fonts.googleapis.com",
          "https://cdn.jsdelivr.net",
          "https://cdnjs.cloudflare.com",
          "https://cdn.datatables.net",
          "https://unpkg.com"
        ],
        "font-src": [
          "'self'",
          "https://fonts.gstatic.com",
          "https://cdn.jsdelivr.net",
          "https://cdnjs.cloudflare.com"
        ],
        "img-src": [
          "'self'",
          "data:",
          "blob:",
          "https://*.tile.openstreetmap.org"
        ],
        "connect-src": [
          "'self'",
          "https://*.tile.openstreetmap.org"
        ],
        "object-src": ["'none'"],
        "frame-ancestors": ["'self'"]
      }
    },
    crossOriginEmbedderPolicy: false,
    crossOriginOpenerPolicy: { policy: "same-origin-allow-popups" },
    crossOriginResourcePolicy: { policy: "cross-origin" },
    referrerPolicy: { policy: "no-referrer-when-downgrade" }
  })
);

app.use(compression({ threshold: 1024 }));

function setStaticHeaders(res, filePath) {
  if (filePath.endsWith('.geojson')) {
    res.type('application/geo+json; charset=utf-8');
  } else if (filePath.endsWith('.csv')) {
    res.type('text/csv; charset=utf-8');
  }

  if (/\/dataset\//.test(filePath) || filePath.endsWith('.csv') || filePath.endsWith('.geojson')) {
    res.setHeader('Cache-Control', 'public, max-age=600, stale-while-revalidate=120'); // 10 min
  } else if (/\.(js|css|png|jpg|jpeg|webp|svg|ico|woff2?|ttf)$/.test(filePath)) {
    res.setHeader('Cache-Control', 'public, max-age=604800, immutable'); // 7 dias
  } else {
    res.setHeader('Cache-Control', 'no-cache');
  }
}

// /dataset real
app.use('/dataset', express.static(DATASET_DIR, { setHeaders: setStaticHeaders }));

// Alias /dataset/sad -> /dataset (mantém caminhos atuais do HTML)
app.use('/dataset/sad', express.static(DATASET_DIR, { setHeaders: setStaticHeaders }));

// arquivos estáticos a partir da raiz (onde está o index.html)
app.use(express.static(ROOT_DIR, {
  setHeaders: setStaticHeaders,
  extensions: ['html']
}));

// healthcheck
app.get('/healthz', (_req, res) => res.status(200).send('ok'));

// ----- Fallback sem usar path pattern (robusto p/ Express 4/5) -----
app.use((req, res, next) => {
  // se pediu um arquivo com extensão, deixa cair no 404 do static
  if (path.extname(req.path)) return next();
  res.sendFile(path.join(ROOT_DIR, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`✅ Servidor rodando em http://localhost:${PORT}`);
});
