#!/usr/bin/env bash
# Prepare an existing PostgreSQL (e.g. RDS `database-1`) for the dev Catalog (#39).
#
# Creates, idempotently:
#   - login role  meeton_dev  (password generated once, kept in the secret; capped
#     connections and statement timeout so dev cannot starve the shared instance)
#   - database    meeton_dev  owned by that role, not connectable by PUBLIC
#   - extension   postgis     in that database (needs the master user once)
#   - secret      meeton-dev-catalog-db  in eu-central-1: {"username","password"},
#     read by the Catalog Lambdas (same shape as an RDS-managed secret)
#
# Run it BEFORE the first `terraform apply` of dev with an external database:
#
#   export EXTERNAL_DB_HOST=<instance>.<id>.eu-north-1.rds.amazonaws.com
#   export PGPASSWORD=<master password>            # or you will be prompted
#   scripts/setup_external_db.sh                   # --drop removes all of the above
#
# Needs: admin AWS credentials (aws CLI), Docker (runs psql from postgres:18-alpine),
# and network access from this machine to the database.
set -euo pipefail

HOST=${EXTERNAL_DB_HOST:?set EXTERNAL_DB_HOST to the database endpoint}
PORT=${EXTERNAL_DB_PORT:-5432}
MASTER_USER=${EXTERNAL_DB_MASTER_USER:-postgres}
ROLE=meeton_dev
DB=meeton_dev
SECRET=meeton-dev-catalog-db
SECRET_REGION=${SECRET_REGION:-eu-central-1}
CONN_LIMIT=${CONN_LIMIT:-20}

if [[ -z "${PGPASSWORD:-}" ]]; then
  read -r -s -p "Master password for ${MASTER_USER}@${HOST}: " PGPASSWORD
  echo
fi
export PGPASSWORD

# psql in a container; the password reaches it via the environment, never argv.
psql_as_master() {
  docker run --rm -i -e PGPASSWORD postgres:18-alpine \
    psql "host=${HOST} port=${PORT} user=${MASTER_USER} dbname=$1 sslmode=${EXTERNAL_DB_SSLMODE:-require} connect_timeout=10" \
    -v ON_ERROR_STOP=1 -q -X
}

if [[ "${1:-}" == "--drop" ]]; then
  read -r -p "Drop database ${DB}, role ${ROLE} and secret ${SECRET}? Type 'drop': " answer
  [[ "$answer" == "drop" ]] || { echo "aborted"; exit 1; }
  psql_as_master postgres <<SQL
DROP DATABASE IF EXISTS ${DB} WITH (FORCE);
DROP ROLE IF EXISTS ${ROLE};
SQL
  aws secretsmanager delete-secret --region "$SECRET_REGION" --secret-id "$SECRET" \
    --force-delete-without-recovery >/dev/null 2>&1 || true
  echo "dropped ${DB}, ${ROLE} and ${SECRET}"
  exit 0
fi

# Reuse the stored password on re-runs so the role and the secret never diverge.
if password=$(aws secretsmanager get-secret-value --region "$SECRET_REGION" --secret-id "$SECRET" \
  --query SecretString --output text 2>/dev/null); then
  password=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["password"])' <<<"$password")
  secret_exists=1
else
  password=$(openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 40)
  secret_exists=0
fi

# 1. role and database (the password is alphanumeric, safe inside a SQL literal)
psql_as_master postgres <<SQL
SELECT format('CREATE ROLE %I LOGIN', '${ROLE}')
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${ROLE}') \gexec
ALTER ROLE ${ROLE} WITH LOGIN PASSWORD '${password}' CONNECTION LIMIT ${CONN_LIMIT};
ALTER ROLE ${ROLE} SET statement_timeout = '15s';
ALTER ROLE ${ROLE} SET idle_in_transaction_session_timeout = '60s';
-- PostgreSQL 16+: the master needs SET on the role to create a database it owns.
GRANT ${ROLE} TO CURRENT_USER;
SELECT format('CREATE DATABASE %I OWNER %I', '${DB}', '${ROLE}')
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '${DB}') \gexec
REVOKE ALL ON DATABASE ${DB} FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE ${DB} TO ${ROLE};
SQL

# 2. PostGIS inside it (CREATE EXTENSION needs rds_superuser; migration 0001's
#    `CREATE EXTENSION IF NOT EXISTS postgis` is then a no-op for meeton_dev).
psql_as_master "$DB" <<SQL
CREATE EXTENSION IF NOT EXISTS postgis;
SELECT 'postgis ' || extversion FROM pg_extension WHERE extname = 'postgis';
SQL

# 3. the secret the Catalog Lambdas read
value=$(R="$ROLE" P="$password" python3 -c 'import json,os; print(json.dumps({"username": os.environ["R"], "password": os.environ["P"]}))')
if [[ "$secret_exists" == 1 ]]; then
  aws secretsmanager put-secret-value --region "$SECRET_REGION" --secret-id "$SECRET" \
    --secret-string file:///dev/stdin <<<"$value" >/dev/null
else
  aws secretsmanager create-secret --region "$SECRET_REGION" --name "$SECRET" \
    --description "Meeton dev Catalog credentials on an external PostgreSQL (#39)" \
    --tags Key=project,Value=meeton Key=env,Value=dev \
    --secret-string file:///dev/stdin <<<"$value" >/dev/null
fi

echo "ready: database ${DB}, role ${ROLE} (max ${CONN_LIMIT} connections), secret ${SECRET} in ${SECRET_REGION}"
