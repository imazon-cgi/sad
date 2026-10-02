#!/usr/bin/env bash
# preparar_banco_sad.sh — deixa um PostgreSQL pronto para o dashboard do SAD.
#
# Na ordem:
#   1. baixa uma pasta compartilhada do Google Drive (gdown);
#   2. cria o esquema imazongeo (controle + sad_alerta + a visão vw_sad);
#   3. grava no banco os alertas baixados.
#
# O esquema e a carga são os do imazongeo_upload: este script chama
# 'imazongeo-banco' e não reimplementa nada — as correções de geometria e de
# texto, o registro em 'carga' e a substituição de meses continuam valendo.
#
# O dashboard lê a visão imazongeo.vw_sad (ver banco.js); enquanto o banco não
# existir, ele segue lendo os CSVs do S3, então rodar isto é opcional.
#
# Uso:
#   scripts/preparar_banco_sad.sh --pasta https://drive.google.com/drive/folders/ID
#
# Requisitos: python3 (para instalar o gdown), o comando imazongeo-banco e um
# PostgreSQL 15+ com PostGIS 3 apontado por DATABASE_URL.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PASTA=""
DESTINO="$RAIZ/dados-sad"
MODO="real"
SOMENTE_SCHEMA=0
PULAR_DOWNLOAD=0
VERBOSE=0
CLI="${IMAZONGEO_BANCO:-}"

ajuda() {
  # cabeçalho deste arquivo, até a primeira linha que não é comentário
  sed -n '2,/^[^#]/p' "${BASH_SOURCE[0]}" | sed -n 's/^#[[:space:]]\{0,1\}//p'
  cat <<'FIM'

Opções:
  --pasta URL           pasta compartilhada do Google Drive (link "qualquer
                        pessoa com o link"); obrigatória, salvo --pular-download
  --destino DIR         onde baixar e procurar os arquivos (padrão: ./dados-sad)
  --database-url URL    banco de destino (padrão: $DATABASE_URL, ou o .env daqui)
  --modo MODO           real | simulation | dry_run (padrão: real)
                        dry_run só valida; simulation grava e desfaz no final
  --somente-schema      cria as tabelas e não carrega os arquivos
  --pular-download      usa o que já está em --destino, sem acessar o Drive
  --imazongeo-banco BIN caminho do comando imazongeo-banco
  -v, --verbose         log detalhado da carga
  -h, --ajuda           esta ajuda
FIM
}

erro() { printf 'erro: %s\n' "$*" >&2; exit 1; }
passo() { printf '\n==> %s\n' "$*"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pasta)            PASTA="${2:-}"; shift 2 ;;
    --destino)          DESTINO="${2:-}"; shift 2 ;;
    --database-url)     DATABASE_URL="${2:-}"; shift 2 ;;
    --modo)             MODO="${2:-}"; shift 2 ;;
    --somente-schema)   SOMENTE_SCHEMA=1; shift ;;
    --pular-download)   PULAR_DOWNLOAD=1; shift ;;
    --imazongeo-banco)  CLI="${2:-}"; shift 2 ;;
    -v|--verbose)       VERBOSE=1; shift ;;
    -h|--ajuda|--help)  ajuda; exit 0 ;;
    *) erro "opção desconhecida: $1 (use --ajuda)" ;;
  esac
done

case "$MODO" in
  real|simulation|dry_run) ;;
  *) erro "--modo inválido: $MODO (real, simulation ou dry_run)" ;;
esac
[[ $PULAR_DOWNLOAD -eq 1 || -n $PASTA ]] || erro "informe --pasta com o link do Drive (ou --pular-download)"

# ---------------------------------------------------------------------------
# Banco de destino
# ---------------------------------------------------------------------------
if [[ -z "${DATABASE_URL:-}" && -f "$RAIZ/.env" ]]; then
  # mesma variável que o dashboard usa em .env
  DATABASE_URL="$(sed -n 's/^[[:space:]]*DATABASE_URL=//p' "$RAIZ/.env" | tail -1 | tr -d '\042\047')"
fi
[[ -n "${DATABASE_URL:-}" ]] || erro "defina DATABASE_URL (ou use --database-url):
  postgresql://usuario:senha@host:5432/imazongeo"
export DATABASE_URL

# ---------------------------------------------------------------------------
# Comandos necessários
# ---------------------------------------------------------------------------
localizar_cli() {
  if [[ -n "$CLI" ]]; then
    command -v "$CLI" >/dev/null 2>&1 || [[ -x "$CLI" ]] || erro "imazongeo-banco não encontrado em: $CLI"
    return 0
  fi
  if command -v imazongeo-banco >/dev/null 2>&1; then CLI=imazongeo-banco; return 0; fi
  local candidato
  for candidato in \
    "$RAIZ/../imazongeo_upload/.venv/bin/imazongeo-banco" \
    "$HOME/imazon/imazongeo_upload/.venv/bin/imazongeo-banco" \
    "/opt/imazongeo-upload/.venv/bin/imazongeo-banco"; do
    [[ -x "$candidato" ]] && { CLI="$(cd "$(dirname "$candidato")" && pwd)/$(basename "$candidato")"; return 0; }
  done
  return 1
}

localizar_cli || erro "imazongeo-banco não encontrado. Instale o imazongeo_upload
  (pip install -e '.[banco]' no repositório) ou use --imazongeo-banco BIN."

# gdown fica num venv próprio, para não mexer no python do sistema
localizar_gdown() {
  if command -v gdown >/dev/null 2>&1; then GDOWN=gdown; return 0; fi
  local venv="${XDG_CACHE_HOME:-$HOME/.cache}/sad-gdown"
  if [[ ! -x "$venv/bin/gdown" ]]; then
    passo "Instalando o gdown em $venv"
    python3 -m venv "$venv"
    "$venv/bin/pip" install --quiet --upgrade pip gdown
  fi
  GDOWN="$venv/bin/gdown"
}

# ---------------------------------------------------------------------------
# 1. Download da pasta do Drive
# ---------------------------------------------------------------------------
if [[ $PULAR_DOWNLOAD -eq 1 ]]; then
  passo "Download pulado; usando os arquivos de $DESTINO"
  [[ -d "$DESTINO" ]] || erro "$DESTINO não existe"
else
  localizar_gdown
  mkdir -p "$DESTINO"
  passo "Baixando a pasta do Drive em $DESTINO"
  # --continue retoma o que já veio pela metade; os arquivos do SAD são grandes
  "$GDOWN" --folder "$PASTA" -O "$DESTINO" --continue --retries 3
fi

# ---------------------------------------------------------------------------
# 2. Esquema
# ---------------------------------------------------------------------------
passo "Criando/atualizando o esquema imazongeo (tabelas do SAD e a visão vw_sad)"
if [[ $MODO == dry_run ]]; then
  echo "    (--modo dry_run: nada é gravado, nem o esquema)"
else
  "$CLI" criar-schema --dataset sad
fi

if [[ $SOMENTE_SCHEMA -eq 1 ]]; then
  passo "Pronto (--somente-schema). Para carregar depois:"
  echo "    $CLI importar-sad \"$DESTINO\"/*.geojson --modo real"
  exit 0
fi

# ---------------------------------------------------------------------------
# 3. Carga dos alertas
# ---------------------------------------------------------------------------
# Aceita o que o importador entende: ZIPs (inspecionados por dentro) e os
# GeoJSON/Shapefile soltos no padrão alertas_sad_{tipo}_{MM}_{AAAA}..._{camada}.
mapfile -t ENCONTRADOS < <(
  find "$DESTINO" -type f \( -iname '*.zip' -o -iname '*.geojson' -o -iname '*.shp' \) | sort
)
[[ ${#ENCONTRADOS[@]} -gt 0 ]] || erro "nenhum .zip, .geojson ou .shp em $DESTINO"

ARQUIVOS=()
IGNORADOS=()
for arquivo in "${ENCONTRADOS[@]}"; do
  nome="$(basename "$arquivo")"
  if [[ "${nome,,}" == *.zip || "${nome,,}" == alertas_sad_* ]]; then
    ARQUIVOS+=("$arquivo")
  else
    IGNORADOS+=("$nome")
  fi
done

if [[ ${#IGNORADOS[@]} -gt 0 ]]; then
  printf '    fora do padrão do SAD, ignorado(s): %s\n' "${IGNORADOS[*]}"
fi
[[ ${#ARQUIVOS[@]} -gt 0 ]] || erro "nenhum arquivo no padrão alertas_sad_*; confira a pasta baixada"

passo "Gravando ${#ARQUIVOS[@]} arquivo(s) no banco (--modo $MODO)"
printf '    %s\n' "${ARQUIVOS[@]##*/}"
if [[ $VERBOSE -eq 1 ]]; then
  "$CLI" -v importar-sad "${ARQUIVOS[@]}" --modo "$MODO"
else
  "$CLI" importar-sad "${ARQUIVOS[@]}" --modo "$MODO"
fi

# ---------------------------------------------------------------------------
# Resumo do que ficou no banco
# ---------------------------------------------------------------------------
if [[ $MODO == real ]] && command -v psql >/dev/null 2>&1; then
  passo "No banco agora"
  psql -X -d "$DATABASE_URL" -c "
    SELECT tipo, camada, count(*) AS alertas,
           min(ano*100+mes) AS primeiro, max(ano*100+mes) AS ultimo,
           round(sum(area_km2)::numeric, 1) AS km2
    FROM imazongeo.vw_sad GROUP BY 1, 2 ORDER BY 1, 2;" || true
fi

passo "Pronto. O dashboard passa a ler do banco assim que DATABASE_URL estiver no .env dele."
