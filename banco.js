// banco.js — alertas do SAD lidos do banco do imazongeo_upload (PostgreSQL/PostGIS).
//
// O banco é opcional. Sem DATABASE_URL, com o banco fora do ar, sem a visão do
// SAD ou sem dados do tipo/camada pedido, csvAlertasSad() retorna null e o
// dashboard continua lendo os CSVs do S3.
//
// Visão esperada (padrão vw_{dataset} do imazongeo_upload), uma linha por alerta:
//   tipo        'desmatamento' | 'degradacao'
//   camada      'municipios' | 'assentamentos' | 'terras_indigenas' | 'unidades_conservacao'
//   ano, mes    inteiros
//   sensor      ex.: Sentinel-2
//   uf          sigla da UF
//   municipio   nome do município
//   territorio  nome do assentamento, TI ou UC (vazio na camada municipios)
//   uso         Uso Sustentável | Proteção Integral (só unidades_conservacao)
//   jurisdicao  Federal | Estadual (só unidades_conservacao)
//   area_km2    área do alerta (km²)
const { Pool } = require('pg');

const DATABASE_URL = (process.env.DATABASE_URL || '').trim();
const SAD_VIEW = (process.env.SAD_DB_VIEW || 'imazongeo.vw_sad').trim();
const CACHE_MS = parseInt(process.env.SAD_DB_CACHE_MS || '600000', 10); // 10 min, igual ao /dataset
const RETRY_MS = 60 * 1000; // banco fora do ar ou sem dados: tenta de novo após 1 min
// Teto de polígonos por requisição do mapa. Acima disso o banco devolve nada e o
// navegador cai no GeoJSON do S3, em vez de baixar centenas de MB.
const MAX_POLIGONOS = parseInt(process.env.SAD_DB_MAX_POLIGONOS || '8000', 10);

if (!/^[A-Za-z_]\w*(\.[A-Za-z_]\w*)?$/.test(SAD_VIEW)) {
  throw new Error(`SAD_DB_VIEW inválida: ${SAD_VIEW}`);
}

// Colunas do CSV do dashboard: [coluna da visão, nome usado pelo index.html]
const COLUNAS_BASE = [['tipo', 'ALERTA'], ['mes', 'MES'], ['ano', 'ANO'], ['sensor', 'SENSOR'], ['uf', 'ESTADO']];
const COLUNAS_CAMADA = {
  municipios:           [['municipio', 'MUNICIPIO']],
  assentamentos:        [['municipio', 'MUNICIPIO'], ['territorio', 'ASSENTAMEN']],
  terras_indigenas:     [['municipio', 'MUNICIPIO'], ['territorio', 'TERRA_INDI']],
  unidades_conservacao: [['municipio', 'MUNICIPIO'], ['territorio', 'UNID_CONSE'], ['uso', 'USO'], ['jurisdicao', 'JURISDICAO']]
};
const TIPOS = ['desmatamento', 'degradacao'];

// O dashboard só usa somas de área (nunca conta linhas), então os alertas são
// somados por mês + território: mesmos totais com um CSV bem menor.
function sqlAlertas(camada) {
  const grupo = [...COLUNAS_BASE, ...COLUNAS_CAMADA[camada]];
  return `SELECT ${grupo.map(([col, nome]) => `${col} AS "${nome}"`).join(', ')},
                 round(sum(area_km2)::numeric, 4) AS "AREAKM2"
          FROM ${SAD_VIEW}
          WHERE tipo = $1 AND camada = $2
          GROUP BY ${grupo.map(([col]) => col).join(', ')}
          ORDER BY ano, mes`;
}

// Nome do território no GeoJSON, como o mapa do index.html procura
const NOME_TERRITORIO = {
  assentamentos: 'ASSENTAMEN',
  terras_indigenas: 'TERRA_INDI',
  unidades_conservacao: 'UNID_CONSE'
};

// Polígonos dos alertas do período. Os limites estaduais continuam vindo do S3:
// o banco guarda alertas, não contornos de território.
function sqlGeojson(camada, filtro) {
  const props = ["'ANO', ano", "'MES', mes", "'ESTADO', uf", "'MUNICIPIO', municipio",
                 "'AREAKM2', round(area_km2::numeric, 4)"];
  if (NOME_TERRITORIO[camada]) props.push(`'${NOME_TERRITORIO[camada]}', territorio`);
  if (camada === 'unidades_conservacao') props.push("'USO', uso", "'JURISDICAO', jurisdicao");
  return `SELECT json_build_object(
            'type', 'FeatureCollection',
            'features', coalesce(json_agg(json_build_object(
              'type', 'Feature',
              'properties', json_build_object(${props.join(', ')}),
              'geometry', ST_AsGeoJSON(geom, 6)::json)), '[]'::json))::text AS geojson
          FROM ${SAD_VIEW} WHERE ${filtro}`;
}

// $1 camada, $2 início e $3 fim do período (AAAAMM); depois, se houver, o tipo e
// a lista de territórios desenhados no mapa. O corte por ano vem antes do cálculo
// com o mês para o índice (tipo, camada, ano, mes) ser aproveitado.
function filtroGeojson(tipo, camada, de, ate, territorios) {
  const valores = [camada, de, ate];
  let sql = `camada = $1
             AND ano BETWEEN ($2::int / 100) AND ($3::int / 100)
             AND (ano * 100 + mes) BETWEEN $2::int AND $3::int`;
  if (tipo !== 'todos') {
    valores.push(tipo);
    sql += ` AND tipo = $${valores.length}`;
  }
  if (territorios.length) {
    valores.push(territorios);
    sql += ` AND ${camada === 'municipios' ? 'municipio' : 'territorio'} = ANY($${valores.length})`;
  }
  return { sql, valores };
}

function celulaCsv(v) {
  if (v === null || v === undefined) return '';
  const s = String(v);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

function paraCsv(nomes, linhas) {
  const saida = [nomes.join(',')];
  for (const linha of linhas) saida.push(linha.map(celulaCsv).join(','));
  return saida.join('\n') + '\n';
}

let pool = null;
function obterPool() {
  if (!pool) {
    pool = new Pool({
      connectionString: DATABASE_URL,
      max: 4,
      connectionTimeoutMillis: 3000,
      idleTimeoutMillis: 30000,
      statement_timeout: 120000
    });
    // Erro numa conexão ociosa (ex.: banco reiniciado) não pode derrubar o servidor
    pool.on('error', err => console.warn('Banco: conexão ociosa perdida:', err.message));
  }
  return pool;
}

// Loga só quando a fonte de um tipo/camada muda, para não repetir a cada consulta
const ultimaMensagem = new Map();
function registrar(chave, mensagem) {
  if (ultimaMensagem.get(chave) === mensagem) return;
  ultimaMensagem.set(chave, mensagem);
  console.log(`SAD ${chave}: ${mensagem}`);
}

let indisponivelAte = 0;
function aoFalhar(chave, err) {
  indisponivelAte = Date.now() + RETRY_MS;
  const motivo = err.code === '42P01' ? `${SAD_VIEW} não existe` : (err.message || err.code);
  registrar(chave, `banco indisponível (${motivo}); lendo do S3`);
  return null;
}

async function consultarCsv(tipo, camada) {
  const chave = `${tipo}/${camada}`;
  try {
    const { rows, fields } = await obterPool().query({
      text: sqlAlertas(camada),
      values: [tipo, camada],
      rowMode: 'array'
    });
    if (!rows.length) {
      registrar(chave, `sem dados em ${SAD_VIEW}; lendo do S3`);
      return null;
    }
    registrar(chave, `lendo do banco (${SAD_VIEW})`);
    return paraCsv(fields.map(f => f.name), rows);
  } catch (err) {
    return aoFalhar(chave, err);
  }
}

async function consultarGeojson(tipo, camada, de, ate, territorios) {
  const chave = `${tipo}/${camada}.geojson`;
  const { sql, valores } = filtroGeojson(tipo, camada, de, ate, territorios);
  try {
    const { rows } = await obterPool().query(`SELECT count(*) FROM ${SAD_VIEW} WHERE ${sql}`, valores);
    const total = Number(rows[0].count);
    if (!total) {
      registrar(chave, `sem polígonos no período em ${SAD_VIEW}; lendo do S3`);
      return null;
    }
    if (total > MAX_POLIGONOS) {
      registrar(chave, `período com ${total} polígonos (teto ${MAX_POLIGONOS}); lendo do S3`);
      return null;
    }
    const r = await obterPool().query(sqlGeojson(camada, sql), valores);
    registrar(chave, `lendo do banco (${SAD_VIEW})`);
    return r.rows[0].geojson;
  } catch (err) {
    return aoFalhar(chave, err);
  }
}

async function consultarPeriodo() {
  try {
    const { rows } = await obterPool().query(
      `SELECT min(ano) AS ano_min, max(ano) AS ano_max,
              (SELECT max(mes) FROM ${SAD_VIEW} WHERE ano = (SELECT max(ano) FROM ${SAD_VIEW})) AS mes_max
       FROM ${SAD_VIEW}`
    );
    const p = rows[0];
    if (!p || !p.ano_max) return null;
    registrar('periodo', `${p.ano_min} a ${p.ano_max}-${String(p.mes_max).padStart(2, '0')}`);
    return JSON.stringify({ ano_min: p.ano_min, ano_max: p.ano_max, mes_max: p.mes_max });
  } catch (err) {
    return aoFalhar('periodo', err);
  }
}

// chave -> { expira, valor: Promise<string|null> }; a Promise evita consultas
// repetidas quando vários navegadores pedem o mesmo arquivo ao mesmo tempo.
const cache = new Map();

function comCache(chave, consultar) {
  const item = cache.get(chave);
  if (item && item.expira > Date.now()) return item.valor;
  if (Date.now() < indisponivelAte) return Promise.resolve(null);

  const novo = { expira: Date.now() + CACHE_MS, valor: consultar() };
  novo.valor.then(v => { if (v === null) novo.expira = Date.now() + RETRY_MS; });
  if (cache.size > 60) cache.delete(cache.keys().next().value); // o mapa varia com o período
  cache.set(chave, novo);
  return novo.valor;
}

// CSV dos alertas no layout do dashboard, ou null se o banco não puder ser usado
function csvAlertasSad(tipo, camada) {
  if (!DATABASE_URL || !TIPOS.includes(tipo) || !COLUNAS_CAMADA[camada]) return Promise.resolve(null);
  return comCache(`${tipo}/${camada}`, () => consultarCsv(tipo, camada));
}

// GeoJSON dos alertas do período (AAAAMM), opcionalmente só dos territórios
// desenhados no mapa. null quando o banco não pode ser usado: o navegador
// então busca o GeoJSON do S3.
function geojsonAlertasSad(tipo, camada, de, ate, territorios = []) {
  const periodoOk = Number.isInteger(de) && Number.isInteger(ate) && de >= 200001 && ate <= 210012 && de <= ate;
  if (!DATABASE_URL || !periodoOk) return Promise.resolve(null);
  if (!COLUNAS_CAMADA[camada] || !(tipo === 'todos' || TIPOS.includes(tipo))) return Promise.resolve(null);
  const chave = `${tipo}/${camada}.geojson/${de}-${ate}/${territorios.join('|')}`;
  return comCache(chave, () => consultarGeojson(tipo, camada, de, ate, territorios));
}

// {ano_min, ano_max, mes_max} do banco, ou null (a página então usa o padrão dela)
function periodoSad() {
  if (!DATABASE_URL) return Promise.resolve(null);
  return comCache('periodo', consultarPeriodo);
}

module.exports = { csvAlertasSad, geojsonAlertasSad, periodoSad, bancoConfigurado: !!DATABASE_URL, SAD_VIEW };
