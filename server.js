const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '.env'), quiet: true });
const fs = require('fs');
const os = require('os');
const express = require('express');
const compression = require('compression');
const helmet = require('helmet');
const { Pool } = require('pg');
const { execFile } = require('child_process');
const { promisify } = require('util');
const execFileAsync = promisify(execFile);
const { csvAlertasSad, geojsonAlertasSad, periodoSad, bancoConfigurado, SAD_VIEW } = require('./banco');

const app = express();
const PORT = parseInt(process.env.PORT || '3000', 10);

// Diretórios
const ROOT_DIR = __dirname;
const DATASET_DIR = process.env.DATASET_DIR || path.join(ROOT_DIR, 'dataset');
const SAD_DIR = path.join(DATASET_DIR, 'sad');
const downloadPool = bancoConfigurado ? new Pool({ connectionString: process.env.DATABASE_URL, max: 2 }) : null;

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

// Download completo de todas as camadas de um mês. A fonte é a visão PostGIS,
// garantindo que CSV, GeoJSON e Shapefile contenham exatamente o mesmo recorte.
app.get('/api/sad/download/:ano/:mes.:formato', async (req, res) => {
  if (!downloadPool) return semBanco(res);
  const ano = Number(req.params.ano), mes = Number(req.params.mes);
  const formato = String(req.params.formato).toLowerCase();
  if (!Number.isInteger(ano) || !Number.isInteger(mes) || mes < 1 || mes > 12 || !['csv','geojson','zip'].includes(formato)) return res.status(400).send('Parâmetros inválidos');
  const { rows } = await downloadPool.query(`SELECT tipo, camada, ano, mes, sensor, uf, municipio, territorio, uso, jurisdicao, area_km2, ST_AsGeoJSON(geom)::json AS geometry FROM imazongeo.vw_sad WHERE ano=$1 AND mes=$2 ORDER BY tipo, camada`, [ano, mes]);
  if (!rows.length) return res.status(404).send('Sem dados para o período');
  const props = r => ({ tipo:r.tipo, camada:r.camada, ano:r.ano, mes:r.mes, sensor:r.sensor, uf:r.uf, municipio:r.municipio, territorio:r.territorio, uso:r.uso, jurisdicao:r.jurisdicao, area_km2:Number(r.area_km2) });
  const fc = { type:'FeatureCollection', features: rows.map(r => ({ type:'Feature', properties:props(r), geometry:r.geometry })) };
  const stamp = `${ano}_${String(mes).padStart(2,'0')}`;
  if (formato === 'geojson') { res.type('application/geo+json'); return res.attachment(`sad_${stamp}.geojson`).send(JSON.stringify(fc)); }
  if (formato === 'csv') {
    const head = ['tipo','camada','ano','mes','sensor','uf','municipio','territorio','uso','jurisdicao','area_km2','geometry'];
    const esc = v => { const s = typeof v === 'object' ? JSON.stringify(v) : (v ?? ''); return /[",\n]/.test(String(s)) ? `"${String(s).replace(/"/g,'""')}"` : s; };
    const body = rows.map(r => [r.tipo,r.camada,r.ano,r.mes,r.sensor,r.uf,r.municipio,r.territorio,r.uso,r.jurisdicao,r.area_km2,JSON.stringify(r.geometry)].map(esc).join(',')).join('\n');
    res.type('text/csv'); return res.attachment(`sad_${stamp}.csv`).send(head.join(',')+'\n'+body+'\n');
  }
  const tmp = await fs.promises.mkdtemp(path.join(os.tmpdir(), `sad-${stamp}-`));
  try { const geo = path.join(tmp, `sad_${stamp}.geojson`); await fs.promises.writeFile(geo, JSON.stringify(fc)); const shp = path.join(tmp, 'shapefile'); await fs.promises.mkdir(shp); await execFileAsync('ogr2ogr', ['-f','ESRI Shapefile',shp,geo]); await execFileAsync('zip', ['-j', '-q', path.join(tmp, `sad_${stamp}.zip`), ...await fs.promises.readdir(shp).then(a=>a.map(x=>path.join(shp,x)))]); res.download(path.join(tmp, `sad_${stamp}.zip`), `sad_${stamp}.zip`, () => fs.promises.rm(tmp,{recursive:true,force:true})); } catch (e) { await fs.promises.rm(tmp,{recursive:true,force:true}); res.status(500).send(`Falha ao gerar Shapefile: ${e.message}`); }
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
