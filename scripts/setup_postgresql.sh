#!/usr/bin/env bash

# Automated PostgreSQL + TimescaleDB setup for Raspberry Pi / Debian-based systems
# - Installs PGDG packages and TimescaleDB
# - Creates an application database/user
# - Enables the TimescaleDB extension
# - Writes .env with PG_DATABASE_URL and related settings
# Idempotent: safe to re-run; will skip work if already applied.

set -euo pipefail

# ---- Configurable parameters (env overrides allowed) ----
DB_NAME=${DB_NAME:-"dt-ulb"}
DB_USER=${DB_USER:-"dt-base-user"}
DB_PASS=${DB_PASS:-"dt-base-password"}
DB_HOST=${DB_HOST:-"localhost"}
DB_PORT=${DB_PORT:-"5432"}

# Timescale/PostgreSQL package lines (adjust if your distro ships different versions)
TS_REPO_LINE=${TS_REPO_LINE:-"deb https://packagecloud.io/timescale/timescaledb/debian/ $(lsb_release -c -s) main"}

echo "[1/7] Installing prerequisites and adding repositories"
sudo apt-get update -y
sudo apt install gnupg postgresql-common apt-transport-https lsb-release wget

# Add PGDG repo if not present
if [[ ! -f /etc/apt/sources.list.d/pgdg.list ]]; then
  echo "Adding PGDG repository..."
  sudo /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y
fi

# Add TimescaleDB repo + key if not present
if [[ ! -f /etc/apt/sources.list.d/timescaledb.list ]]; then
  echo "$TS_REPO_LINE" | sudo tee /etc/apt/sources.list.d/timescaledb.list
  wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/timescaledb.gpg
fi

echo "[2/7] Installing PostgreSQL and TimescaleDB packages"
sudo apt-get update -y
# Install meta package; it will select the correct PG version (e.g., 16/18)
sudo apt-get install -y timescaledb-2-postgresql-18 postgresql-client-18 timescaledb-toolkit-postgresql-18

echo "[3/7] Running timescaledb-tune (auto-yes)"
if command -v timescaledb-tune >/dev/null 2>&1; then
  sudo timescaledb-tune --yes >/dev/null || true
fi

echo "[4/7] Restarting PostgreSQL service"
sudo systemctl restart postgresql

echo "[5/7] Creating database and user (if missing)"

# Helper to query a single value as the postgres superuser
pg_super() { sudo -u postgres psql -v ON_ERROR_STOP=1 -Atqc "$1"; }

# Create user if missing
USER_EXISTS=$(pg_super "SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}'") || USER_EXISTS=""
if [[ "${USER_EXISTS}" != "1" ]]; then
  echo "Creating USER ${DB_USER}"
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE USER \"${DB_USER}\" WITH PASSWORD '${DB_PASS}';"
else
  echo "USER ${DB_USER} already exists — skipping"
fi

# Create database if missing
DB_EXISTS=$(pg_super "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'") || DB_EXISTS=""
if [[ "${DB_EXISTS}" != "1" ]]; then
  echo "Creating database ${DB_NAME}"
  sudo -u postgres psql -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"${DB_NAME}\" OWNER \"${DB_USER}\";"
else
  echo "Database ${DB_NAME} already exists — skipping"
fi

echo "[6/7] Enabling TimescaleDB extension on ${DB_NAME} and granting privileges"
sudo -u postgres psql -v ON_ERROR_STOP=1 -d "${DB_NAME}" -c "CREATE EXTENSION IF NOT EXISTS timescaledb; CREATE EXTENSION IF NOT EXISTS timescaledb_toolkit;"
sudo -u postgres psql -v ON_ERROR_STOP=1 -d "${DB_NAME}" -c "GRANT ALL ON SCHEMA public TO \"${DB_USER}\";"

echo "[7/7] Writing .env configuration"
ENV_FILE=".env"
PG_URL="postgresql+psycopg://${DB_USER}:${DB_PASS}@${DB_HOST}:${DB_PORT}/${DB_NAME}"

touch "${ENV_FILE}"
if grep -q '^PG_DATABASE_URL=' "${ENV_FILE}"; then
  sed -i "s#^PG_DATABASE_URL=.*#PG_DATABASE_URL=${PG_URL}#" "${ENV_FILE}"
else
  echo "PG_DATABASE_URL=${PG_URL}" >>"${ENV_FILE}"
fi

grep -q '^SQL_POOL_SIZE=' "${ENV_FILE}" || echo "SQL_POOL_SIZE=5" >>"${ENV_FILE}"

echo "\nSetup complete. Connection: ${PG_URL}"
echo "Next: run migrations:"
echo "  poetry run python scripts/run_sql_migration.py"

# Backup examples:
#  pg_dump -U "${DB_USER}" -h "${DB_HOST}" -p "${DB_PORT}" -d "${DB_NAME}" > "${DB_NAME}_backup_$(date +%Y%m%d).sql"
# Restore examples:
#  psql -U "${DB_USER}" -h "${DB_HOST}" -p "${DB_PORT}" -d "${DB_NAME}" < backup.sql

# - **Migration to Managed Cloud**: To migrate to AWS RDS, Azure Database for PostgreSQL, or other managed services:
#   1. Provision managed PostgreSQL instance with TimescaleDB support
#   2. Update `PG_DATABASE_URL` environment variable
#   3. Run migrations against new instance
#   4. No application code changes required
