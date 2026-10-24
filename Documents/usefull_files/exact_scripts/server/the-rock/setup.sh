set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(dirname "$HERE")"

sudo hostnamectl set-hostname the-rock
sudo loginctl enable-linger kloud

# Tools the restore needs
sudo apt update
sudo apt full-upgrade
sudo apt install ca-certificates curl python3 rsync age

# Saved system configs (before the packages that own them), home folders, env files
python3 "$SERVER_DIR/backup.py" restore

# Docker from Docker's repo
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable" |
    sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
sudo apt update

# ZFS, NFS, Docker, log upload, fan control deps, utils
sudo apt install \
    linux-headers-current-rockchip64 zfs-dkms zfsutils-linux zfs-zed \
    nfs-kernel-server \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin \
    systemd-journal-remote \
    cron anacron cpufrequtils hdparm lm-sensors smartmontools \
    locales btop htop tmux ripgrep fd-find duf eza fatrace \
    avahi-daemon

# Not needed: nothing reads local mail (ZED posts to ntfy)
sudo apt remove exim4-base exim4-config exim4-daemon-light hddtemp plymouth
sudo apt-get autoremove --purge
sudo systemctl mask smartd.service hddtemp.service

# Import pool
sudo modprobe zfs
sudo zpool list chonker >/dev/null 2>&1 || sudo zpool import -f chonker
sudo update-initramfs -u
sudo locale-gen
sudo systemctl daemon-reload

# Logs: journal in RAM (journald.conf.d), uploaded to microchelik; no RAM log sync
sudo systemctl disable --now armbian-ramlog.service rsyslog.service
sudo systemctl mask armbian-ramlog.service rsyslog.service
sudo systemctl restart systemd-journald
sudo systemctl enable --now systemd-journal-upload.service

sudo systemctl enable --now cron.service anacron.service fstrim.timer loadcpufreq.service \
    nfs-server.service zfs-zed.service docker.service
sudo exportfs -ra
sudo systemctl restart zfs-zed.service docker.service

# Fan curve from CPU and disk temperatures, spins idle disks down
sudo bash "$SERVER_DIR/fancontrol/install.sh"

curl --proto '=https' --tlsv1.2 -LsSf https://setup.atuin.sh | sh

