set -euo pipefail
source /etc/os-release

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(dirname "$HERE")"

sudo hostnamectl set-hostname the-rock
sudo loginctl enable-linger kloud

sudo timedatectl set-timezone Europe/Vilnius

# ================== Repos
# Docker from Docker's repo
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable" |
    sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

sudo apt update
sudo apt full-upgrade


# ================== Deps

sudo apt install \
chrony dbus-broker docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin \
network-manager systemd-resolved libnss-resolve libnss-mdns libnss-systemd openssh-server openssh-sftp-server \
systemd-journal-remote \
avahi-daemon

sudo apt install \
linux-headers-current-rockchip64 ca-certificates curl python3 \
rsync age zfs-dkms zfsutils-linux zfs-zed \
nfs-kernel-server zstd \
fastfetch \
locales btop htop tmux ripgrep fd-find duf eza fatrace \
cron anacron



# For cu scaling and fan control script
sudo apt install cpufrequtils hdparm sdparm lm-sensors

# Not needed: nothing reads local mail (ZED posts to ntfy)
sudo apt remove exim4-base exim4-config exim4-daemon-light plymouth

# Unused services
sudo apt remove firewalld cups cups-client dnsmasq samba folder2ram unattended-upgrades quota plocate
sudo systemctl mask firewalld apparmor auditd rsyslog.service armbian-ramlog.service

# Handled by scrutiny
sudo apt remove smartmontools hddtemp
sudo systemctl mask smartd.service hddtemp.service

sudo apt-get autoremove --purge

# ================== Services

# Network setup
sudo ln -sfv /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf

sudo systemctl daemon-reload

sudo systemctl enable dbus-broker
sudo systemctl disable systemd-networkd
sudo systemctl enable --now \
NetworkManager systemd-resolved avahi-daemon sshd \
chronyd docker fstrim.timer cron.service anacron.service

sudo bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../hass-watchdog/install.sh"

curl --proto '=https' --tlsv1.2 -LsSf https://setup.atuin.sh | sh

# Saved system configs, home directories, and decrypted env files
sudo python3 "$SERVER_DIR/backup.py" restore
sudo systemctl daemon-reload

# Import pool
# sudo modprobe zfs
# sudo zpool list chonker >/dev/null 2>&1 || sudo zpool import -f chonker

sudo update-initramfs -u
sudo locale-gen

# Logs: journal in RAM (journald.conf.d), uploaded to microchelik; no RAM log sync
sudo systemctl enable  --now armbian-zram-config loadcpufreq.service nfs-server.service zfs-zed.service
sudo systemctl enable  --now systemd-journal-upload.service
sudo systemctl disable --now systemd-journal-remote.socket
sudo systemctl restart docker systemd-journald

# Fan curve from CPU and disk temperatures, spins idle disks down
sudo bash "$SERVER_DIR/fancontrol/install.sh"


