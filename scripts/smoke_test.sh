#!/usr/bin/env bash
# smoke_test.sh — Start the infra stack, run migrations, start core-api, and
# verify the /health endpoint returns a successful response.
#
# Usage: bash scripts/smoke_test.sh
# Env:   YGGDRASIL_SMOKE_API_PORT  (default: 18000) — host port for core-api

set -euo pipefail

COMPOSE_FILE="infra/docker-compose.yml"
CORE_API_PORT="${YGGDRASIL_SMOKE_API_PORT:-18000}"
STATE_ROOT=".ci/smoke-state-root"
CORE_API_PID=""

cleanup() {
    echo "==> Tearing down ..."
    [ -n "$CORE_API_PID" ] && kill "$CORE_API_PID" 2>/dev/null || true
    docker compose -f "$COMPOSE_FILE" down --remove-orphans -v >/dev/null 2>&1 || true
    rm -rf "$STATE_ROOT"
}
trap cleanup EXIT

mkdir -p "$STATE_ROOT"

echo "==> Starting infra stack (postgres, redis, nats, minio) ..."
docker compose -f "$COMPOSE_FILE" up -d postgres redis nats minio

echo "==> Waiting for PostgreSQL to be ready ..."
for i in $(seq 1 60); do
    if docker exec yggdrasil-postgres pg_isready -U postgres >/dev/null 2>&1; then
        echo "    Ready after ${i}s."
        break
    fi
    if [ "$i" -eq 60 ]; then
        echo "ERROR: PostgreSQL did not become ready within 60 s." >&2
        exit 1
    fi
    sleep 1
done

echo "==> Waiting for Redis to be ready ..."
for i in $(seq 1 30); do
    if docker exec yggdrasil-redis redis-cli ping >/dev/null 2>&1; then
        echo "    Ready after ${i}s."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: Redis did not become ready within 30 s." >&2
        exit 1
    fi
    sleep 1
done

export YGGDRASIL_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5432/yggdrasil"
export YGGDRASIL_REDIS_URL="redis://localhost:6379/0"
export YGGDRASIL_AUTO_CREATE_SCHEMA="1"
export YGGDRASIL_STATE_ROOT="$STATE_ROOT"
export YGGDRASIL_CORE_API_BASE_URL="http://127.0.0.1:${CORE_API_PORT}"

echo "==> Applying migrations (alembic upgrade head) ..."
uv run alembic upgrade head

echo "==> Starting core-api on port ${CORE_API_PORT} ..."
uv run python -m uvicorn yggdrasil_core_api.app:app \
    --host 127.0.0.1 --port "$CORE_API_PORT" &
CORE_API_PID=$!

echo "==> Waiting for core-api /health to respond ..."
for i in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${CORE_API_PORT}/health" >/dev/null 2>&1; then
        echo "    Healthy after ${i}s."
        break
    fi
    if ! kill -0 "$CORE_API_PID" 2>/dev/null; then
        echo "ERROR: core-api process exited unexpectedly." >&2
        exit 1
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: core-api /health did not respond within 30 s." >&2
        exit 1
    fi
    sleep 1
done

echo "==> Calling /health ..."
RESPONSE=$(curl -sf "http://127.0.0.1:${CORE_API_PORT}/health")
echo "    Response: $RESPONSE"

echo ""
echo "Smoke test passed — core-api /health returned OK."
