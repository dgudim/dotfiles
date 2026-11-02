#!/usr/bin/env bash
set -euo pipefail

DEST=/opt/docker-ordered-start-stop
SRC_DIR="$(dirname "$(readlink -f "$0")")"

[ "$(id -u)" -eq 0 ] || { echo "Run as root" >&2; exit 1; }
for f in docker-ordered-start-stop docker-ordered-start-stop.service; do
    [ -f "$SRC_DIR/$f" ] || { echo "$f not found next to install.sh" >&2; exit 1; }
done
command -v docker >/dev/null || { echo "docker is not installed" >&2; exit 1; }

install -d "$DEST"
install -m 755 "$SRC_DIR/docker-ordered-start-stop" "$DEST/docker-ordered-start-stop"
install -m 644 "$SRC_DIR/docker-ordered-start-stop.service" /etc/systemd/system/docker-ordered-start-stop.service
echo "Installed $DEST/docker-ordered-start-stop and /etc/systemd/system/docker-ordered-start-stop.service"

systemctl daemon-reload
systemctl enable --now docker-ordered-start-stop.service
systemctl --no-pager status docker-ordered-start-stop.service
