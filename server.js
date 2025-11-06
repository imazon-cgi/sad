const path = require('path');
const fs = require('fs');
const express = require('express');
const compression = require('compression');
const helmet = require('helmet');

const app = express();
const PORT = parseInt(process.env.PORT || '3000', 10);

// Diretórios
const ROOT_DIR = __dirname;
const DATASET_DIR = process.env.DATASET_DIR || path.join(ROOT_DIR, 'dataset');
const SAD_DIR = path.join(DATASET_DIR, 'sad');

if (process.env.TRUST_PROXY) {
  app.set('trust proxy', true);
}

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
    "https://cdn.datatables.net",
    "https://d3js.org"
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
    "https://*.tile.openstreetmap.org",
    "https://*.basemaps.cartocdn.com",
    "https://unpkg.com",
    "https://cdn.jsdelivr.net",
    "https://cdnjs.cloudflare.com",
    "https://cdn.datatables.net",
    "https://imazongeo3-web.s3.sa-east-1.amazonaws.com"
  ],
  "connect-src": [
    "'self'",
    "https://*.tile.openstreetmap.org",
    "https://*.basemaps.cartocdn.com",
    "https://cdn.datatables.net",
    "https://cdnjs.cloudflare.com",
    "https://cdn.jsdelivr.net",
    "https://unpkg.com",
    "https://imazongeo3-web.s3.sa-east-1.amazonaws.com" // liberado p/ fetch futuro se precisar
  ],
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
    res.type('application/geo+json; charset=utf-8');
  } else if (lower.endsWith('.csv')) {
    res.type('text/csv; charset=utf-8');
  } else if (lower.endsWith('.json')) {
    res.type('application/json; charset=utf-8');
  }

  // Cache-Control
  if (lower.includes('/dataset/') || lower.endsWith('.csv') || lower.endsWith('.geojson') || lower.endsWith('.json')) {
    // SWR no browser/proxy + tolerância a erro
    res.setHeader('Cache-Control', 'public, max-age=600, s-maxage=600, stale-while-revalidate=120, stale-if-error=600');
  } else if (/\.(js|css|png|jpg|jpeg|webp|svg|ico|woff2?|ttf)$/.test(lower)) {
    res.setHeader('Cache-Control', 'public, max-age=604800, immutable');
  } else {
    res.setHeader('Cache-Control', 'no-cache');
  }
}

// Logs úteis
console.log('ROOT_DIR:', ROOT_DIR);
console.log('DATASET_DIR:', DATASET_DIR);
console.log('SAD_DIR:', SAD_DIR);

// ======== Servir /dataset ========
app.use('/dataset', express.static(DATASET_DIR, { setHeaders: setStaticHeaders }));
app.use('/dataset/sad', express.static(SAD_DIR, {
  setHeaders: setStaticHeaders,
  index: false,
  maxAge: 0
}));

// ======== Servir /img ========
app.use('/img', express.static(path.join(ROOT_DIR, 'img'), { setHeaders: setStaticHeaders }));

// ======== Raiz (HTML/estáticos do app) ========
app.use(express.static(ROOT_DIR, {
  setHeaders: setStaticHeaders,
  extensions: ['html']
}));

// ======== Healthcheck ========
app.get('/healthz', (_req, res) => res.status(200).send('ok'));

// ======== Debug ========
app.get('/__csp', (req, res) => {
  res.type('text/plain');
  res.send(res.get('content-security-policy') || 'sem CSP');
});

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
  if (path.extname(req.path)) return next();
  res.sendFile(path.join(ROOT_DIR, 'index.html'));
});

// ======== Start ========
app.listen(PORT, () => {
  console.log(`✅ Server em http://localhost:${PORT}`);
  console.log(`🛡️ CSP ${useReportOnly ? '(Report-Only)' : '(Enforcing)'} ativo`);
});
