#!/usr/bin/env bash
set -euo pipefail

DEST=/opt/disksleep
SRC_DIR="$(dirname "$(readlink -f "$0")")"

[ "$(id -u)" -eq 0 ] || { echo "Run as root" >&2; exit 1; }
for f in disksleep.py disksleep.service; do
    [ -f "$SRC_DIR/$f" ] || { echo "$f not found next to install.sh" >&2; exit 1; }
done
command -v python3 >/dev/null || { echo "python3 is not installed" >&2; exit 1; }
command -v hdparm >/dev/null || { echo "hdparm is not installed" >&2; exit 1; }

install -d "$DEST"
install -m 755 "$SRC_DIR/disksleep.py" "$DEST/disksleep.py"
install -m 644 "$SRC_DIR/disksleep.service" /etc/systemd/system/disksleep.service
echo "Installed $DEST/disksleep.py and /etc/systemd/system/disksleep.service"

systemctl daemon-reload
systemctl enable --now disksleep.service
systemctl --no-pager status disksleep.service
