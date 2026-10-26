set -euo pipefail
source /etc/os-release

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(dirname "$HERE")"

sudo hostnamectl set-hostname the-rock
sudo loginctl enable-linger kloud

# Docker from Docker's repo
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable" |
    sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

sudo apt update
sudo apt full-upgrade

# ZFS, NFS, Docker, log upload, fan control deps, utils
sudo apt install \
    linux-headers-current-rockchip64 ca-certificates curl python3 chrony dbus-broker \
    rsync age zfs-dkms zfsutils-linux zfs-zed \
    nfs-kernel-server \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin \
    systemd-journal-remote \
    cron anacron cpufrequtils hdparm lm-sensors \
    locales btop htop tmux ripgrep fd-find duf eza fatrace \
    avahi-daemon network-manager systemd-resolved libnss-mdns openssh-sftp-server

# Not needed: nothing reads local mail (ZED posts to ntfy)
sudo apt remove exim4-base exim4-config exim4-daemon-light hddtemp plymouth
sudo apt-get autoremove --purge
sudo systemctl mask smartd.service hddtemp.service

# Handled by scrutiny
sudo zypper remove smartmontools

# Network setup
sudo ln -sfv /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf

sudo systemctl enable dbus-broker
sudo systemctl disable systemd-networkd
sudo systemctl enable --now \
NetworkManager systemd-resolved avahi-daemon sshd \
chronyd docker fstrim.timer

sudo bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../hass-watchdog/install.sh"

curl --proto '=https' --tlsv1.2 -LsSf https://setup.atuin.sh | sh

# Saved system configs, home directories, and decrypted env files
sudo python3 "$SERVER_DIR/backup.py" restore

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

sudo systemctl enable --now cron.service anacron.service loadcpufreq.service \
    nfs-server.service zfs-zed.service docker.service
sudo exportfs -ra
sudo systemctl restart zfs-zed.service docker.service

# Fan curve from CPU and disk temperatures, spins idle disks down
sudo bash "$SERVER_DIR/fancontrol/install.sh"




















# TODO

# Deps and network
sudo apt install \
hdparm hddtemp sdparm \
libnss-resolve libnss-systemd avahi-daemon \
docker docker-compose \
chrony dbus-broker \
openssh-server openssh-sftp-server \
cron zstd \
zfsutils-linux zfs-zed zfs-dkms linux-headers-current-rockchip64


sudo ln -sfv /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf

sudo systemctl enable dbus-broker
sudo systemctl enable --now \
systemd-networkd systemd-resolved avahi-daemon sshd \
chronyd docker \
cron


sudo apt remove unattended-upgrades quota mlocate plocate smartmontools



# sudo zpool create chonker mirror /dev/sdb /dev/sdd -f
# sudo zpool add chonker cache /dev/sda -f
# sudo zfs set mountpoint=/mnt/chonker chonker

# sudo zfs set atime=off chonker
# sudo zfs set compression=lz4 chonker
# sudo zfs set xattr=sa chonker # Store extended attributes in inodes for better performance
# sudo zfs set sync=disabled chonker # Treat sync writes as async, I don't care, I have a UPS

# sudo zfs create chonker/media
# sudo zfs create chonker/music

# sudo zfs set compression=off chonker/media
# sudo zfs set compression=off chonker/music



# ???????? sudo systemctl disable armbian-ramlog armbian-zram-config


