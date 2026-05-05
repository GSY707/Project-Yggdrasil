#!/usr/bin/env bash
# safe_shutdown.sh — 向 Yggdrasil worker 发送 SIGTERM 安全关闭信号
# Usage: ./scripts/safe_shutdown.sh [--script-filter yggdrasil_worker] [--wait 30]
set -euo pipefail

SCRIPT_FILTER="${SCRIPT_FILTER:-yggdrasil_worker}"
WAIT_SECONDS="${WAIT_SECONDS:-30}"

PIDS=$(pgrep -f "$SCRIPT_FILTER" 2>/dev/null || true)

if [ -z "$PIDS" ]; then
  echo "No worker process found matching '$SCRIPT_FILTER'."
  exit 0
fi

for PID in $PIDS; do
  echo "Sending SIGTERM to PID $PID..."
  kill -TERM "$PID" || true
done

echo "Waiting up to ${WAIT_SECONDS}s for worker to save checkpoint..."
DEADLINE=$(($(date +%s) + WAIT_SECONDS))
for PID in $PIDS; do
  while kill -0 "$PID" 2>/dev/null && [ "$(date +%s)" -lt "$DEADLINE" ]; do
    sleep 0.5
  done
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "Worker PID $PID exited cleanly."
  else
    echo "WARNING: Worker PID $PID did not exit within ${WAIT_SECONDS}s." >&2
  fi
done
