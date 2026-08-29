#!/usr/bin/env bash
set -euo pipefail

INSTALL_DIR=/opt/hass-power-monitor
SERVICE_NAME=hass-power-monitor
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

need_root() {
    if [[ ${EUID} -ne 0 ]]; then
        echo "This script must be run as root (sudo $0)." >&2
        exit 1
    fi
}

install_deps() {
    echo "Installing python3 and python3-requests with zypper..."
    zypper --non-interactive install --no-recommends python3 python3-requests
}

install_files() {
    echo "Installing files to ${INSTALL_DIR}..."
    mkdir -p "${INSTALL_DIR}"
    rm -rf "${INSTALL_DIR}/venv"
    install -m 755 "${SCRIPT_DIR}/hass-power-monitor.py" "${INSTALL_DIR}/hass-power-monitor.py"

    local dest_config="${INSTALL_DIR}/hass-power-monitor-config.json"
    if [[ -f "${dest_config}" ]]; then
        echo "Keeping existing config at ${dest_config}"
    else
        install -m 600 "${SCRIPT_DIR}/hass-power-monitor-config.json" "${dest_config}"
    fi
}

install_unit() {
    echo "Installing systemd unit..."
    install -m 644 "${SCRIPT_DIR}/hass-power-monitor.service" "/etc/systemd/system/${SERVICE_NAME}.service"

    systemctl daemon-reload
    systemctl enable --now "${SERVICE_NAME}.service"
}

warn_if_unconfigured() {
    local dest_config="${INSTALL_DIR}/hass-power-monitor-config.json"
    python3 - "${dest_config}" <<'PY'
import json, sys
path = sys.argv[1]
with open(path) as f:
    cfg = json.load(f)
missing = [k for k in ("api_key", "sensor_id") if not str(cfg.get(k, "")).strip()]
if missing:
    print(f"Warning: {path} still has empty fields: {', '.join(missing)}")
    print("Edit the config, then run: systemctl restart hass-power-monitor")
    sys.exit(0)
PY
}

main() {
    need_root
    install_deps
    install_files
    install_unit
    warn_if_unconfigured

    echo
    echo "Installed ${SERVICE_NAME}."
    echo "  files:   ${INSTALL_DIR}"
    echo "  config:  ${INSTALL_DIR}/hass-power-monitor-config.json"
    echo "  unit:    /etc/systemd/system/${SERVICE_NAME}.service"
    echo
    systemctl --no-pager --full status "${SERVICE_NAME}.service" || true
}

main "$@"
