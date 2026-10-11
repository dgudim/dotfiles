#!/bin/sh
set -eu
url="https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-Country.mmdb"
dest="/mnt/sata_500/vector/geoip/GeoLite2-Country.mmdb"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
curl -fL --retry 3 -o "$tmp" "$url"
size="$(wc -c < "$tmp")"
if [ "$size" -lt 1000000 ]; then
  echo "GeoLite2-Country.mmdb too small ($size bytes)" >&2
  exit 1
fi
# Keep only printable text so BusyBox grep can see the database name.
if ! tail -c 400 "$tmp" | tr -c "[:print:]\n" "\n" | grep -q "GeoLite2-Country"; then
  echo "download is not a GeoLite2-Country database" >&2
  exit 1
fi
mv "$tmp" "$dest"
trap - EXIT
chmod 644 "$dest"
compose="/home/kloud/monitoring/compose.yaml"
docker compose -f "$compose" down vector
docker compose -f "$compose" up -d vector
echo "reloaded vector"
echo "updated GeoLite2-Country.mmdb ($size bytes)"
