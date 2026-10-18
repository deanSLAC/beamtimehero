#!/usr/bin/env bash
# Install BeamtimeHero as a system service that starts at boot. Run as root.
#   systemd/install.sh            install, enable for boot and start it
#   systemd/install.sh remove     stop, disable, remove
set -euo pipefail
UNIT=beamtimehero.service
SRC="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)/$UNIT"
[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
if [ "${1:-}" = remove ]; then
    systemctl disable --now "$UNIT" || true
    rm -f "/etc/systemd/system/$UNIT"
    systemctl daemon-reload
    echo "removed $UNIT"
    exit 0
fi
ln -sf "$SRC" "/etc/systemd/system/$UNIT"
systemctl daemon-reload
systemctl enable --now "$UNIT"
echo "installed, enabled and started $UNIT: http://127.0.0.1:8742"
