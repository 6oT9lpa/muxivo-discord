#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/muxivo-discord}"
SQLITE_DB="${SQLITE_DB:-$APP_DIR/data/nexsusguard.db}"
POSTGRES_URL="${POSTGRES_URL:?POSTGRES_URL is required}"
PYTHON_BIN="${PYTHON_BIN:-$APP_DIR/.venv/bin/python}"

cd "$APP_DIR"

echo "[postgres-stage] creating schema and migrating SQLite data..."
PYTHONPATH="$APP_DIR" "$PYTHON_BIN" scripts/migrate_sqlite_to_postgres.py \
  --sqlite "$SQLITE_DB" \
  --postgres "$POSTGRES_URL" \
  --truncate

echo "[postgres-stage] validating PostgreSQL connection..."
PYTHONPATH="$APP_DIR" DATABASE_URL="$POSTGRES_URL" "$PYTHON_BIN" - <<'PY'
import asyncio
from infrastructure.database import DatabaseManager
from infrastructure.config import get_config

async def main():
    manager = DatabaseManager(get_config().database_url)
    await manager.initialize()
    tables = await manager.fetch_all(
        "SELECT tablename AS name FROM pg_catalog.pg_tables WHERE schemaname = 'public'"
    )
    print(f"postgres_tables={len(tables)}")
    await manager.close()

asyncio.run(main())
PY

echo "[postgres-stage] done"
