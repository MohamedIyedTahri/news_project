#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${QWEN_LOCAL_PATH:-}" ]]; then
  echo "QWEN_LOCAL_PATH environment variable must be set to the model directory" >&2
  exit 1
fi

HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8080}
WORKERS=${WORKERS:-1}

exec uvicorn services.qwen_server.app:app --host "${HOST}" --port "${PORT}" --workers "${WORKERS}"
