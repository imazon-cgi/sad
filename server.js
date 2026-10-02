const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '.env'), quiet: true });
const fs = require('fs');
const express = require('express');
const compression = require('compression');
const helmet = require('helmet');
const { csvAlertasSad, geojsonAlertasSad, periodoSad, bancoConfigurado, SAD_VIEW } = require('./banco');

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
console.log('Banco do SAD:', bancoConfigurado ? SAD_VIEW : 'DATABASE_URL não definida (só S3)');

// ======== Alertas do SAD no banco ========
// 503 quando o banco não está configurado/ativo ou ainda não tem a tabela do
// SAD: o navegador então lê o CSV (ou o GeoJSON) do S3.
function semBanco(res) {
  res.setHeader('Cache-Control', 'no-store');
  res.status(503).type('text/plain').send('Alertas do SAD indisponíveis no banco');
}

function comCacheDe10Min(res, tipoMime) {
  res.type(tipoMime);
  res.setHeader('Cache-Control', 'public, max-age=600, stale-while-revalidate=120');
}

// Período coberto pelo banco: a página monta os filtros de mês/ano com ele
app.get('/api/sad/periodo', async (_req, res) => {
  const periodo = await periodoSad();
  if (periodo === null) return semBanco(res);
  comCacheDe10Min(res, 'application/json; charset=utf-8');
  res.send(periodo);
});

app.get('/api/sad/:tipo/:camada.csv', async (req, res) => {
  const csv = await csvAlertasSad(req.params.tipo, req.params.camada);
  if (csv === null) return semBanco(res);
  comCacheDe10Min(res, 'text/csv; charset=utf-8');
  res.send(csv);
});

// Polígonos do mapa no período pedido (de/ate no formato AAAAMM) e, quando
// informados, só dos territórios do ranking (separados por '|')
app.get('/api/sad/:tipo/:camada.geojson', async (req, res) => {
  const territorios = String(req.query.territorios || '')
    .split('|').map(t => t.trim()).filter(Boolean).slice(0, 50);
  const geojson = await geojsonAlertasSad(
    req.params.tipo,
    req.params.camada,
    parseInt(req.query.de, 10),
    parseInt(req.query.ate, 10),
    territorios
  );
  if (geojson === null) return semBanco(res);
  comCacheDe10Min(res, 'application/geo+json; charset=utf-8');
  res.send(geojson);
});

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
// Arquivos do servidor ficam fora: o .env tem a senha do banco, e os logs e a
// configuração não interessam ao navegador.
const ARQUIVOS_PRIVADOS = /^\/(server\.js|banco\.js|package(-lock)?\.json|ecosystem\.config\.js|logs(\/|$))/;
app.use((req, res, next) => {
  if (ARQUIVOS_PRIVADOS.test(req.path)) return res.status(404).type('text/plain').send('Não encontrado');
  next();
});

app.use(express.static(ROOT_DIR, {
  setHeaders: setStaticHeaders,
  extensions: ['html'],
  dotfiles: 'ignore' // .env e outros arquivos ocultos
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
