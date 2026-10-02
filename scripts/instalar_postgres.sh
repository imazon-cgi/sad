#!/usr/bin/env bash
# instalar_postgres.sh — instala o PostgreSQL com PostGIS e cria o banco imazongeo.
#
# É o passo anterior ao preparar_banco_sad.sh: deixa o servidor de pé, com o
# usuário, o banco e a extensão PostGIS, e imprime o DATABASE_URL (com
# --escrever-env, grava direto no .env do dashboard).
#
# Se já houver um PostgreSQL 15+ no ar, ele é reaproveitado e nada é instalado.
# Um usuário que já existe não tem a senha trocada, a não ser com --senha.
# Para usar um servidor pronto (inclusive remoto), passe --admin-url.
#
# Uso:
#   scripts/instalar_postgres.sh                      # usa/instala local e cria o banco
#   scripts/instalar_postgres.sh --escrever-env       # e grava o DATABASE_URL no .env
#   scripts/instalar_postgres.sh --simular            # só mostra o que faria
#
# Requisitos: Ubuntu/Debian com sudo (para instalar), ou um PostgreSQL 15+ já
# rodando. Depois disto, rode scripts/preparar_banco_sad.sh para carregar os dados.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

VERSAO=""
BANCO="imazongeo"
USUARIO="${USER:-imazongeo}"
SENHA=""
SENHA_DADA=0
ADMIN_URL=""
PORTA=""
HOST="localhost"
ESCREVER_ENV=0
SIMULAR=0

ajuda() {
  # cabeçalho deste arquivo, até a primeira linha que não é comentário
  sed -n '2,/^[^#]/p' "${BASH_SOURCE[0]}" | sed -n 's/^#[[:space:]]\{0,1\}//p'
  cat <<'FIM'

Opções:
  --versao N           versão a instalar quando não há PostgreSQL 15+ (padrão: 17)
  --banco NOME         banco a criar (padrão: imazongeo)
  --usuario NOME       dono do banco (padrão: seu usuário do sistema)
  --senha SENHA        senha do usuário (padrão: gerada; usuário existente não muda)
  --porta N            porta do cluster a usar (padrão: a do cluster encontrado)
  --host HOST          host para montar o DATABASE_URL (padrão: localhost)
  --admin-url URL      conecta como superusuário por esta URL, em vez de sudo -u postgres
  --escrever-env       grava o DATABASE_URL no .env do projeto
  --simular            mostra os comandos sem executar nada
  -h, --ajuda          esta ajuda
FIM
}

erro() { printf 'erro: %s\n' "$*" >&2; exit 1; }
gerar_senha() {
  if command -v openssl >/dev/null 2>&1; then openssl rand -hex 16
  elif command -v python3 >/dev/null 2>&1; then python3 -c 'import secrets; print(secrets.token_hex(16))'
  else od -An -tx1 -N16 /dev/urandom | tr -d ' \n'; fi
}
passo() { printf '\n==> %s\n' "$*"; }
executar() {
  if [[ $SIMULAR -eq 1 ]]; then printf '    [simulação] %s\n' "$*"; else "$@"; fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --versao)        VERSAO="${2:-}"; shift 2 ;;
    --banco)         BANCO="${2:-}"; shift 2 ;;
    --usuario)       USUARIO="${2:-}"; shift 2 ;;
    --senha)         SENHA="${2:-}"; SENHA_DADA=1; shift 2 ;;
    --porta)         PORTA="${2:-}"; shift 2 ;;
    --host)          HOST="${2:-}"; shift 2 ;;
    --admin-url)     ADMIN_URL="${2:-}"; shift 2 ;;
    --escrever-env)  ESCREVER_ENV=1; shift ;;
    --simular)       SIMULAR=1; shift ;;
    -h|--ajuda|--help) ajuda; exit 0 ;;
    *) erro "opção desconhecida: $1 (use --ajuda)" ;;
  esac
done

[[ "$BANCO" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || erro "nome de banco inválido: $BANCO"
[[ "$USUARIO" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || erro "nome de usuário inválido: $USUARIO"

# ---------------------------------------------------------------------------
# Onde mandar os comandos de superusuário
# ---------------------------------------------------------------------------
# Sem --admin-url: procura um cluster 15+ no ar (o PostGIS do imazongeo precisa
# de 15+); se não houver, instala. Com --admin-url, nada é instalado.
cluster_no_ar() {
  command -v pg_lsclusters >/dev/null 2>&1 || return 1
  pg_lsclusters --no-header 2>/dev/null |
    awk '$1 >= 15 && $4 == "online" { print $1, $3 }' | sort -rn | awk 'NR == 1'
}

if [[ -n "$ADMIN_URL" ]]; then
  passo "Usando o servidor de --admin-url (nada será instalado)"
else
  encontrado="$(cluster_no_ar || true)"
  if [[ -n "$encontrado" ]]; then
    ver_cluster="${encontrado% *}"
    [[ -n "$PORTA" ]] || PORTA="${encontrado#* }"
    passo "PostgreSQL $ver_cluster já está no ar (porta $PORTA); nada a instalar"
  else
    VERSAO="${VERSAO:-17}"
    passo "Instalando PostgreSQL $VERSAO com PostGIS (precisa de sudo)"
    command -v apt-get >/dev/null 2>&1 || erro "instalação automática só em Ubuntu/Debian.
  Instale PostgreSQL 15+ e PostGIS 3 e rode de novo, ou use --admin-url."

    # Repositório oficial, se a distribuição não tiver a versão pedida
    # grep -c (e não -q): com pipefail, o -q fecha o pipe e o apt-cache morre com SIGPIPE
    if [[ "$(apt-cache policy "postgresql-$VERSAO" 2>/dev/null | grep -c 'Candidate: [0-9]')" == 0 ]]; then
      passo "Adicionando o repositório oficial do PostgreSQL (PGDG)"
      executar sudo apt-get install -y curl ca-certificates
      executar sudo install -d /usr/share/postgresql-common/pgdg
      executar sudo curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
        https://www.postgresql.org/media/keys/ACCC4CF8.asc
      if [[ $SIMULAR -eq 1 ]]; then
        printf '    [simulação] %s\n' "adiciona /etc/apt/sources.list.d/pgdg.list"
      else
        echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
https://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo "$VERSION_CODENAME")-pgdg main" |
          sudo tee /etc/apt/sources.list.d/pgdg.list >/dev/null
      fi
      executar sudo apt-get update
    fi

    executar sudo apt-get install -y "postgresql-$VERSAO" "postgresql-$VERSAO-postgis-3"
    # systemd normal; em WSL/contêiner, pg_ctlcluster resolve
    if command -v systemctl >/dev/null 2>&1 && systemctl list-units >/dev/null 2>&1; then
      executar sudo systemctl enable --now postgresql
    else
      executar sudo pg_ctlcluster "$VERSAO" main start || true
    fi
    [[ -n "$PORTA" ]] || PORTA="$(pg_lsclusters --no-header 2>/dev/null |
      awk -v v="$VERSAO" '$1 == v && NR == 1 { print $3 }')"
    [[ -n "$PORTA" || $SIMULAR -eq 1 ]] || erro "cluster $VERSAO não subiu; veja: pg_lsclusters"
  fi
fi

PORTA="${PORTA:-5432}"

# psql como superusuário: por --admin-url ou pelo usuário postgres do sistema
psql_admin() {
  if [[ -n "$ADMIN_URL" ]]; then
    psql -X -v ON_ERROR_STOP=1 "$ADMIN_URL" "$@"
  else
    sudo -u postgres psql -X -v ON_ERROR_STOP=1 -p "$PORTA" "$@"
  fi
}
# mesma URL de --admin-url, trocando só o nome do banco (preserva ?sslmode=...)
url_no_banco() {
  local base="${ADMIN_URL%%\?*}" params=""
  [[ "$ADMIN_URL" == *\?* ]] && params="?${ADMIN_URL#*\?}"
  printf '%s/%s%s' "${base%/*}" "$BANCO" "$params"
}
psql_admin_banco() {
  if [[ -n "$ADMIN_URL" ]]; then
    psql -X -v ON_ERROR_STOP=1 "$(url_no_banco)" "$@"
  else
    sudo -u postgres psql -X -v ON_ERROR_STOP=1 -p "$PORTA" -d "$BANCO" "$@"
  fi
}

if [[ $SIMULAR -eq 1 ]]; then
  passo "Criaria o usuário $USUARIO, o banco $BANCO, a extensão PostGIS e jit = off"
  echo "    (--simular: nada foi executado)"
  exit 0
fi

# ---------------------------------------------------------------------------
# Usuário, banco e PostGIS
# ---------------------------------------------------------------------------
USUARIO_EXISTIA="$(psql_admin -tAc "SELECT 1 FROM pg_roles WHERE rolname = '$USUARIO'" || true)"
if [[ -z "$USUARIO_EXISTIA" && -z "$SENHA" ]]; then
  SENHA="$(gerar_senha)"
fi

passo "Criando o usuário $USUARIO e o banco $BANCO"
# format(%I/%L) monta os nomes e a senha sem risco de injeção
psql_admin -v usuario="$USUARIO" -v senha="$SENHA" -v banco="$BANCO" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'usuario', :'senha')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'usuario') \gexec
SELECT format('CREATE DATABASE %I OWNER %I', :'banco', :'usuario')
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'banco') \gexec
SQL

if [[ -n "$USUARIO_EXISTIA" ]]; then
  if [[ $SENHA_DADA -eq 1 ]]; then
    # \gexec só funciona por stdin; psql -c não aceita meta-comando junto do SQL
    psql_admin -v usuario="$USUARIO" -v senha="$SENHA" <<'SQL'
SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'usuario', :'senha') \gexec
SQL
    echo "    usuário $USUARIO já existia: senha trocada pela de --senha"
  else
    echo "    usuário $USUARIO já existia: senha mantida (use --senha para trocar)"
  fi
fi

passo "Habilitando o PostGIS em $BANCO"
psql_admin_banco -v usuario="$USUARIO" -v banco="$BANCO" <<'SQL'
CREATE EXTENSION IF NOT EXISTS postgis;
-- O JIT do PostgreSQL 16+ derruba consultas pesadas com PostGIS
SELECT format('ALTER DATABASE %I SET jit = off', :'banco') \gexec
SELECT format('GRANT ALL ON DATABASE %I TO %I', :'banco', :'usuario') \gexec
SELECT format('GRANT CREATE ON SCHEMA public TO %I', :'usuario') \gexec
SQL
echo "    PostGIS $(psql_admin_banco -tAc 'SELECT postgis_version()')"

# ---------------------------------------------------------------------------
# DATABASE_URL
# ---------------------------------------------------------------------------
if [[ -n "$SENHA" ]]; then
  URL="postgresql://$USUARIO:$SENHA@$HOST:$PORTA/$BANCO"
else
  URL="postgresql://$USUARIO:SENHA_ATUAL@$HOST:$PORTA/$BANCO"
fi

passo "Banco pronto"
echo "    DATABASE_URL=$URL"

if [[ $ESCREVER_ENV -eq 1 ]]; then
  if [[ -z "$SENHA" ]]; then
    echo "    .env não alterado: a senha do usuário existente não é conhecida aqui."
  else
    arquivo="$RAIZ/.env"
    if [[ -f "$arquivo" ]]; then
      cp "$arquivo" "$arquivo.bak"; chmod 600 "$arquivo.bak"  # guarda a senha antiga
      echo "    cópia do anterior em .env.bak"
    fi
    { [[ -f "$arquivo" ]] && grep -v '^[[:space:]]*DATABASE_URL=' "$arquivo" || true
      echo "DATABASE_URL=$URL"
    } > "$arquivo.novo"
    mv "$arquivo.novo" "$arquivo"
    chmod 600 "$arquivo"
    echo "    DATABASE_URL gravado em $arquivo"
  fi
fi

cat <<FIM

Próximo passo — criar o esquema do SAD e carregar os dados:
    scripts/preparar_banco_sad.sh --pasta https://drive.google.com/drive/folders/ID
FIM
