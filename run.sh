#!/usr/bin/env bash
# Run BeamtimeHero on a non-generic port, localhost only; at BL4-1
# (BTH_STATION=bl41 in .env) also on the beamline subnet 192.168.41.0/24.
# App served at http://localhost:${PORT}/ (no base path).
set -euo pipefail

cd "$(dirname "$0")"

# shellcheck disable=SC1091
source venv/bin/activate

# Under systemd there is no login shell: put a per-user `claude` install
# on PATH (CLAUDE_BIN in .env overrides).
export PATH="$PATH:$HOME/.local/bin"

DEFAULT_HOST=127.0.0.1
if grep -qs '^BTH_STATION=bl41' .env; then
    # BL4-1: also the beamline subnet 192.168.41.0/24 (bl41lx1 is 192.168.41.6);
    # never 0.0.0.0, which would also serve the SLAC network.
    DEFAULT_HOST=127.0.0.1,192.168.41.6
    # EPICS Channel Access settings for the read-only caget tool.
    # systemd services don't read /etc/profile.d, so source it here.
    if [ -f /etc/profile.d/epics.sh ]; then
        set +u
        # shellcheck disable=SC1091
        source /etc/profile.d/epics.sh
        set -u
    fi
fi

export PORT="${PORT:-8742}"
export HOST="${HOST:-$DEFAULT_HOST}"    # comma-separated listen addresses

exec python server/serve.py
