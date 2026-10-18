#!/usr/bin/env bash
# Run BeamtimeHero on localhost only, non-generic port.
# App served at http://localhost:${PORT}/ (no base path).
set -euo pipefail

cd "$(dirname "$0")"

# shellcheck disable=SC1091
source venv/bin/activate

# Under systemd there is no login shell: put a per-user `claude` install
# on PATH (CLAUDE_BIN in .env overrides).
export PATH="$PATH:$HOME/.local/bin"

# BL4-1: EPICS Channel Access settings for the read-only caget tool.
# systemd services don't read /etc/profile.d, so source it here.
if [ -f /etc/profile.d/epics.sh ] && grep -qs '^BTH_STATION=bl41' .env; then
    set +u
    # shellcheck disable=SC1091
    source /etc/profile.d/epics.sh
    set -u
fi

export PORT="${PORT:-8742}"
export HOST="${HOST:-127.0.0.1}"

exec uvicorn app:app --app-dir server --host "$HOST" --port "$PORT"
