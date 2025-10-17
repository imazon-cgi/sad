// server.js
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

        // Carregamento de JS (CDNs + inline por enquanto)
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

        // CSS (inclui Google Fonts)
        "style-src": [
          "'self'",
          "'unsafe-inline'",
          "https://fonts.googleapis.com",
          "https://cdn.jsdelivr.net",
          "https://cdnjs.cloudflare.com",
          "https://cdn.datatables.net",
          "https://unpkg.com"
        ],

        // Fontes
        "font-src": [
          "'self'",
          "https://fonts.gstatic.com",
          "https://cdn.jsdelivr.net",
          "https://cdnjs.cloudflare.com"
        ],

        // IMAGENS — REMOVIDO o placeholder <URL>
        "img-src": [
          "'self'",
          "data:",
          "blob:",
          "https://*.tile.openstreetmap.org",
          "https://*.basemaps.cartocdn.com",
          "https://unpkg.com",
          "https://cdn.jsdelivr.net",
          "https://cdnjs.cloudflare.com",
          "https://cdn.datatables.net",
          "https://imazongeo3-web.s3.sa-east-1.amazonaws.com"
        ],

        // XHR/fetch/EventSource/WebSocket (inclui source maps baixados pelo DevTools)
        "connect-src": [
          "'self'",
          "https://*.tile.openstreetmap.org",
          "https://cdn.datatables.net",
          "https://cdnjs.cloudflare.com",
          "https://cdn.jsdelivr.net",
          "https://unpkg.com"
        ],

        // Workers (html2canvas/leaflet-image, se usados)
        "worker-src": ["'self'", "blob:"],

        "object-src": ["'none'"],
        "frame-ancestors": ["'self'"],
      }
    },
    // Mantém compat com bibliotecas que usam COOP/COEP/COEP
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
  } else if (filePath.endsWith('.json')) {
    res.type('application/json; charset=utf-8');
  }

  if (/\/dataset\//.test(filePath) || filePath.endsWith('.csv') || filePath.endsWith('.geojson') || filePath.endsWith('.json')) {
    res.setHeader('Cache-Control', 'public, max-age=600, stale-while-revalidate=120');
  } else if (/\.(js|css|png|jpg|jpeg|webp|svg|ico|woff2?|ttf)$/.test(filePath)) {
    res.setHeader('Cache-Control', 'public, max-age=604800, immutable');
  } else {
    res.setHeader('Cache-Control', 'no-cache');
  }
}

app.use('/dataset', express.static(DATASET_DIR, { setHeaders: setStaticHeaders }));
app.use('/dataset/sad', express.static(DATASET_DIR, { setHeaders: setStaticHeaders }));

app.use(express.static(ROOT_DIR, {
  setHeaders: setStaticHeaders,
  extensions: ['html']
}));

app.get('/healthz', (_req, res) => res.status(200).send('ok'));

app.use((req, res, next) => {
  if (path.extname(req.path)) return next();
  res.sendFile(path.join(ROOT_DIR, 'index.html'));
});

app.listen(PORT, () => {
  console.log(`✅ Servidor rodando em http://localhost:${PORT}`);
  console.log(`📦 Servindo dataset em /dataset (pasta: ${DATASET_DIR})`);
});
