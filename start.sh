#!/usr/bin/env bash
set -euo pipefail

# Defaults
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
APP_MODULE="${APP_MODULE:-backend.app:app}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"
USE_GUNICORN="${USE_GUNICORN:-0}"
UVICORN_WORKERS="${UVICORN_WORKERS:-1}"

# Resolve binaries (prefer Nixpacks venv if present)
if [ -x "/app/venv/bin/uvicorn" ]; then
  UVICORN_BIN="/app/venv/bin/uvicorn"
else
  UVICORN_BIN="uvicorn"
fi

if [ -x "/app/venv/bin/gunicorn" ]; then
  GUNICORN_BIN="/app/venv/bin/gunicorn"
else
  GUNICORN_BIN="gunicorn"
fi

# Sanitize WEB_CONCURRENCY (fallback to 1 if not an integer)
if ! [[ "$WEB_CONCURRENCY" =~ ^[0-9]+$ ]]; then
  WEB_CONCURRENCY=1
fi

# Decide runner:
# - If USE_GUNICORN=1 or WEB_CONCURRENCY>=2, use Gunicorn for multi-process
# - Otherwise, use Uvicorn directly (simpler, single-process by default)
if [ "$USE_GUNICORN" = "1" ] || [ "$WEB_CONCURRENCY" -ge 2 ]; then
  echo "INFO: Starting with Gunicorn (workers=$WEB_CONCURRENCY)"
  exec "$GUNICORN_BIN" \
    -k uvicorn.workers.UvicornWorker \
    -w "$WEB_CONCURRENCY" \
    -b "$HOST:$PORT" \
    --log-level "${LOG_LEVEL:-info}" \
    "$APP_MODULE"
else
  echo "INFO: Starting with Uvicorn (workers=$UVICORN_WORKERS)"
  exec "$UVICORN_BIN" "$APP_MODULE" --host "$HOST" --port "$PORT" --workers "$UVICORN_WORKERS"
fi
