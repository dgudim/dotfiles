#!/usr/bin/env bash
set -euo pipefail

DEST=/opt/fancontrol
SRC_DIR="$(dirname "$(readlink -f "$0")")"

[ "$(id -u)" -eq 0 ] || { echo "Run as root" >&2; exit 1; }
for f in fancontrol.py fancontrol.service; do
    [ -f "$SRC_DIR/$f" ] || { echo "$f not found next to install.sh" >&2; exit 1; }
done
command -v python3 >/dev/null || { echo "python3 is not installed" >&2; exit 1; }

install -d "$DEST"
install -m 755 "$SRC_DIR/fancontrol.py" "$DEST/fancontrol.py"
install -m 644 "$SRC_DIR/fancontrol.service" /etc/systemd/system/fancontrol.service
echo "Installed $DEST/fancontrol.py and /etc/systemd/system/fancontrol.service"

systemctl daemon-reload
systemctl enable fancontrol.service
systemctl restart fancontrol.service
systemctl --no-pager status fancontrol.service
