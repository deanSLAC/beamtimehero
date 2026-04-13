#!/usr/bin/env bash
# Run BeamtimeHero on localhost only, non-generic port.
# App served at http://localhost:${PORT}/ (no base path).
set -euo pipefail

cd "$(dirname "$0")"

# shellcheck disable=SC1091
source venv/bin/activate

export PORT="${PORT:-8742}"
export HOST="${HOST:-127.0.0.1}"

exec uvicorn app:app --app-dir server --host "$HOST" --port "$PORT"
