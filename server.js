// server.js (Linux-ready)
// Executar com: NODE_ENV=production node server.js
// Opcional:
//   - CSP_REPORT_ONLY=1 (só reporta violações, não bloqueia)
//   - TRUST_PROXY=1      (se estiver atrás de Nginx/Apache)
//   - PORT=3000
//   - DATASET_DIR=/caminho/absoluto/para/dataset (se quiser sobrescrever)

const path = require('path');
const fs = require('fs');
const express = require('express');
const compression = require('compression');
const helmet = require('helmet');

const app = express();
const PORT = parseInt(process.env.PORT || '3000', 10);

// Diretórios (Linux é case-sensitive)
const ROOT_DIR = __dirname;
const DATASET_DIR = process.env.DATASET_DIR || path.join(ROOT_DIR, 'dataset');

// Se estiver atrás de proxy (Nginx/Apache), habilite para ter IP correto
if (process.env.TRUST_PROXY) {
  app.set('trust proxy', true);
}

// ======== Content Security Policy (CSP) ========
// Inclui CDNs usados e tiles OSM/CARTO. Libera data:/blob: para imagens.
// Em Linux, verifique se não há proxy injetando outro CSP.
const cspDirectives = {
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

  // IMPORTANTE: sem placeholders (<URL>) aqui
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

  // Inclui fetch de source-maps do DevTools (unpkg/jsdelivr/cdnjs)
  "connect-src": [
    "'self'",
    "https://*.tile.openstreetmap.org",
    "https://cdn.datatables.net",
    "https://cdnjs.cloudflare.com",
    "https://cdn.jsdelivr.net",
    "https://unpkg.com"
  ],

  // Workers (html2canvas/leaflet-image, se utilizados)
  "worker-src": ["'self'", "blob:"],

  "object-src": ["'none'"],
  "frame-ancestors": ["'self'"]
};

const useReportOnly = !!process.env.CSP_REPORT_ONLY;

app.use(
  helmet({
    contentSecurityPolicy: {
      useDefaults: true,
      directives: cspDirectives,
      reportOnly: useReportOnly
    },
    crossOriginEmbedderPolicy: false,
    crossOriginOpenerPolicy: { policy: "same-origin-allow-popups" },
    crossOriginResourcePolicy: { policy: "cross-origin" },
    referrerPolicy: { policy: "no-referrer-when-downgrade" }
  })
);

// ======== Compressão ========
app.use(compression({ threshold: 1024 }));

// ======== Headers estáticos (MIME + Cache) ========
function setStaticHeaders(res, filePath) {
  const lower = filePath.toLowerCase();

  if (lower.endsWith('.geojson')) {
    // GeoJSON com MIME correto
    res.type('application/geo+json; charset=utf-8');
  } else if (lower.endsWith('.csv')) {
    res.type('text/csv; charset=utf-8');
  } else if (lower.endsWith('.json')) {
    res.type('application/json; charset=utf-8');
  }

  // Cache-Control
  if (lower.includes('/dataset/') || lower.endsWith('.csv') || lower.endsWith('.geojson') || lower.endsWith('.json')) {
    // Dados: 10 min + SWR
    res.setHeader('Cache-Control', 'public, max-age=600, stale-while-revalidate=120');
  } else if (/\.(js|css|png|jpg|jpeg|webp|svg|ico|woff2?|ttf)$/.test(lower)) {
    // Assets: 7 dias, immutable
    res.setHeader('Cache-Control', 'public, max-age=604800, immutable');
  } else {
    // HTML e outros: sem cache
    res.setHeader('Cache-Control', 'no-cache');
  }
}

// ======== Servir /dataset (Linux: nomes exatos!) ========
app.use('/dataset', express.static(DATASET_DIR, { setHeaders: setStaticHeaders }));
// Alias (se necessário para compatibilidade)
app.use('/dataset/sad', express.static(DATASET_DIR, { setHeaders: setStaticHeaders }));

// ======== Raiz (HTML/estáticos) ========
app.use(express.static(ROOT_DIR, {
  setHeaders: setStaticHeaders,
  extensions: ['html'] // permite /rota → /rota.html
}));

// ======== Healthcheck ========
app.get('/healthz', (_req, res) => res.status(200).send('ok'));

// ======== Rotas de debug (úteis na VM Linux) ========
// 1) Mostrar o CSP que este processo realmente enviou
app.get('/__csp', (req, res) => {
  res.type('text/plain');
  res.send(res.get('content-security-policy') || 'sem CSP');
});

const SAD_DIR = path.join(DATASET_DIR, 'sad');
app.use('/dataset/sad', express.static(SAD_DIR, {
  index: false,
  maxAge: '0',          // evita cache
  etag: false,
  lastModified: false,
  cacheControl: false
}));
// 2) Listar conteúdo do dataset (para checar nomes/case)
app.get('/__ls', (req, res) => {
  const sub = req.query.dir || '';
  const dir = path.join(DATASET_DIR, sub);
  fs.readdir(dir, (err, files) => {
    if (err) return res.status(500).json({ err: err.message, dir });
    res.json({ dir, files });
  });
});

// ======== SPA fallback ========
app.use((req, res, next) => {
  if (path.extname(req.path)) return next(); // pede arquivo com extensão → deixa 404 padrão
  res.sendFile(path.join(ROOT_DIR, 'index.html'));
});

// ======== Start ========
app.listen(PORT, () => {
  console.log(`✅ Server (Linux) em http://localhost:${PORT}`);
  console.log(`📦 DATASET_DIR: ${DATASET_DIR}`);
  console.log(`🛡️ CSP ${useReportOnly ? '(Report-Only)' : '(Enforcing)'} ativo`);
});
