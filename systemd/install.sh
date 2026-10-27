#!/usr/bin/env bash
# Install BeamtimeHero as a system service that starts at boot. Run as root.
#   systemd/install.sh            install, enable for boot and start it,
#                                 and let group fourone restart it (polkit)
#   systemd/install.sh remove     stop, disable, remove
set -euo pipefail
UNIT=beamtimehero.service
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
SRC="$DIR/$UNIT"
# polkit rule: group fourone may start/stop/restart the unit without sudo
RULE=50-beamtimehero.rules
[ "$(id -u)" = 0 ] || { echo "run as root" >&2; exit 1; }
if [ "${1:-}" = remove ]; then
    systemctl disable --now "$UNIT" || true
    rm -f "/etc/systemd/system/$UNIT" "/etc/polkit-1/rules.d/$RULE"
    systemctl daemon-reload
    echo "removed $UNIT"
    exit 0
fi
ln -sf "$SRC" "/etc/systemd/system/$UNIT"
# copied, not symlinked: polkit must not follow a rule into a writable repo
install -m 644 -o root -g root "$DIR/$RULE" "/etc/polkit-1/rules.d/$RULE"
systemctl daemon-reload
systemctl enable --now "$UNIT"
echo "installed, enabled and started $UNIT: http://127.0.0.1:8742 and http://192.168.41.6:8742"
