// server.js (fallback sem pattern p/ evitar path-to-regexp)
const path = require('path');
const express = require('express');
const compression = require('compression');
const helmet = require('helmet');

const app = express();
const PORT = process.env.PORT || 3000;

const ROOT_DIR = __dirname;
const DATASET_DIR = path.join(ROOT_DIR, 'dataset');

// ==============================
// Content Security Policy (CSP)
// ==============================
// - Libera CDNs usados no projeto (jsdelivr, unpkg, cdnjs, datatables, Google Fonts)
// - Libera tiles OSM e CARTO (basemaps.cartocdn.com)
// - Habilita data:/blob: para imagens (canvas/exportações)
// - Adiciona worker-src para html2canvas/leaflet-image (quando aplicável)
// - Mantém 'unsafe-inline' porque o HTML tem script e estilos inline
app.use(
  helmet({
    contentSecurityPolicy: {
      useDefaults: true,
      directives: {
        "default-src": ["'self'"],

        "script-src": [
          "'self'",
          "'unsafe-inline'",
          "'unsafe-eval'",              // necessário p/ alguns bundles e DevTools em modo dev
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

        // IMAGENS: permite data:/blob: e os tiles de mapa (OSM + CARTO)
        "img-src": [
          "'self'",
          "data:",
          "blob:",
          "https://*.tile.openstreetmap.org",
          "https://*.basemaps.cartocdn.com"
        ],

        // FETCH/XHR/tiles/sourcemaps: permita OSM/CARTO e (opcional) CDNs p/ baixar *.map no DevTools
        "connect-src": [
          "'self'",
          "https://*.tile.openstreetmap.org",
          "https://*.basemaps.cartocdn.com",
          "https://cdn.jsdelivr.net",
          "https://unpkg.com"
        ],

        // para html2canvas/leaflet-image e workers que possam ser usados
        "worker-src": ["'self'", "blob:"],

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

// Compressão
app.use(compression({ threshold: 1024 }));

// ----------------------------------------
// Headers de tipo e cache para estáticos
// ----------------------------------------
function setStaticHeaders(res, filePath) {
  // Tipos corretos
  if (filePath.endsWith('.geojson')) {
    res.type('application/geo+json; charset=utf-8');
  } else if (filePath.endsWith('.csv')) {
    res.type('text/csv; charset=utf-8');
  }

  // Cache-control adequado
  if (/\/dataset\//.test(filePath) || filePath.endsWith('.csv') || filePath.endsWith('.geojson')) {
    // Dados: curtos (10 min) + stale-while-revalidate
    res.setHeader('Cache-Control', 'public, max-age=600, stale-while-revalidate=120');
  } else if (/\.(js|css|png|jpg|jpeg|webp|svg|ico|woff2?|ttf)$/.test(filePath)) {
    // Assets: 7 dias, immutable
    res.setHeader('Cache-Control', 'public, max-age=604800, immutable');
  } else {
    // HTML, etc.: no-cache para sempre pegar a versão mais recente
    res.setHeader('Cache-Control', 'no-cache');
  }
}

// -------------------------------
// Rotas estáticas /dataset reais
// -------------------------------
app.use('/dataset', express.static(DATASET_DIR, { setHeaders: setStaticHeaders }));

// Alias /dataset/sad -> /dataset (mantém caminhos atuais do HTML)
app.use('/dataset/sad', express.static(DATASET_DIR, { setHeaders: setStaticHeaders }));

// -------------------------------------------
// Arquivos estáticos a partir da raiz (HTML)
// -------------------------------------------
app.use(express.static(ROOT_DIR, {
  setHeaders: setStaticHeaders,
  extensions: ['html'] // permite /rota resolver para /rota.html
}));

// Healthcheck simples
app.get('/healthz', (_req, res) => res.status(200).send('ok'));

// ----------------------------------------------------
// Fallback para SPA: serve index.html p/ rotas limpas
// (sem depender de path-to-regexp/patterns)
// ----------------------------------------------------
app.use((req, res, next) => {
  // Se pediu um arquivo com extensão, deixa cair no 404 do static
  if (path.extname(req.path)) return next();
  res.sendFile(path.join(ROOT_DIR, 'index.html'));
});

// Start
app.listen(PORT, () => {
  console.log(`✅ Servidor rodando em http://localhost:${PORT}`);
  console.log(`📦 Servindo dataset em /dataset (pasta: ${DATASET_DIR})`);
});
