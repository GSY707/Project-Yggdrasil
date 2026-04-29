#!/usr/bin/env bash
# check_migrations.sh — Verify the Alembic migration head matches ORM models.
#
# Starts a disposable PostgreSQL container, applies all migrations, then runs
# `alembic check` to detect any model changes missing a corresponding migration.
#
# Usage: bash scripts/check_migrations.sh
# Env:   YGGDRASIL_MIGRATE_CHECK_PORT  (default: 15432) — host port for the temp container

set -euo pipefail

CONTAINER="yggdrasil-migrate-check-$$"
PG_PORT="${YGGDRASIL_MIGRATE_CHECK_PORT:-15432}"

cleanup() {
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> Starting temporary PostgreSQL container (pgvector/pgvector:pg17) ..."
docker run -d \
    --name "$CONTAINER" \
    -e POSTGRES_DB=yggdrasil \
    -e POSTGRES_USER=postgres \
    -e POSTGRES_PASSWORD=postgres \
    -p "${PG_PORT}:5432" \
    pgvector/pgvector:pg17

echo "==> Waiting for PostgreSQL to be ready ..."
for i in $(seq 1 30); do
    if docker exec "$CONTAINER" pg_isready -U postgres >/dev/null 2>&1; then
        echo "    Ready after ${i}s."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: PostgreSQL did not become ready within 30 s." >&2
        exit 1
    fi
    sleep 1
done

export YGGDRASIL_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:${PG_PORT}/yggdrasil"

echo "==> Applying all migrations (alembic upgrade head) ..."
uv run alembic upgrade head

echo "==> Checking for ORM drift (alembic check) ..."
uv run alembic check

echo ""
echo "Migration check passed — ORM is in sync with the latest migration head."
