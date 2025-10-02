#!/usr/bin/env bash
set -euo pipefail

# Defaults
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
APP_MODULE="${APP_MODULE:-backend.app:app}"

# Prefer Nixpacks venv path if it exists; otherwise fall back to PATH
if [ -x "/app/venv/bin/uvicorn" ]; then
  exec /app/venv/bin/uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT"
else
  exec uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT"
fi

