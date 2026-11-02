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
    echo "Installing python3 and python3-requests..."
    zypper --non-interactive install --no-recommends python3 python3-requests || apt install python3 python3-requests
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

main() {
    need_root
    install_deps
    install_files
    install_unit

    echo
    echo "Installed ${SERVICE_NAME}."
    echo "  files:   ${INSTALL_DIR}"
    echo "  config:  ${INSTALL_DIR}/hass-power-monitor-config.json"
    echo "  unit:    /etc/systemd/system/${SERVICE_NAME}.service"
    echo
    systemctl --no-pager --full status "${SERVICE_NAME}.service" || true
}

main "$@"
