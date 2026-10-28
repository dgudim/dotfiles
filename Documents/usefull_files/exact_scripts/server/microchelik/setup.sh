set -euo pipefail
source /etc/os-release

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_DIR="$(dirname "$HERE")"

sudo hostnamectl set-hostname microchelik
sudo loginctl enable-linger kloud

sudo timedatectl set-timezone Europe/Vilnius

# ================== Repos
sudo zypper addrepo https://download.opensuse.org/repositories/devel:tools/$VERSION/devel:tools.repo
sudo zypper addrepo -cfp 90 'https://ftp.gwdg.de/pub/linux/misc/packman/suse/openSUSE_Leap_$releasever/' packman
# sudo zypper addrepo -f https://download.opensuse.org/repositories/Kernel:/stable:/Backport/$VERSION/ kernel-backport

sudo zypper modifyrepo --refresh devel_tools
sudo zypper modifyrepo --refresh packman

sudo zypper refresh
sudo zypper dist-upgrade --from packman --allow-vendor-change
sudo zypper install --allow-vendor-change --from packman ffmpeg gstreamer-plugins-{good,bad,ugly,libav} libavcodec

# ================== Deps

sudo zypper install \
chrony dbus-broker docker docker-compose \
NetworkManager systemd-resolved nss-mdns nss-systemd nss-resolve openssh-server openssh-sftp-server \
systemd-journal-remote \
avahi

# Different utils (Bindfs is for nextcloud)
sudo zypper install \
fwupd fastfetch btop htop eza \
jq yq usbip tcpdump \
intel-media-driver intel-gpu-tools \
waypipe ripgrep fd duf rsync fatrace \
bindfs age \
python313-uv python313-pip tmux ouch strace \
libva-utils libvulkan_intel \
libhidapi-hidraw0 pkgconf hunspell cronie cronie-anacron

# Audio deps
sudo zypper install \
pipewire wireplumber pipewire-pulseaudio pulseaudio-utils dfu-util pipewire-alsa \
alsa-firmware alsa-plugins bluez bluez-firmware bluez-auto-enable-devices

# Zram
sudo zypper install zram-generator

# Unused services
sudo zypper remove snapper firewalld cups cups-client dnsmasq samba quota plocate
sudo systemctl mask firewalld apparmor auditd rsyslog.service

# Handled by scrutiny
sudo zypper remove smartmontools hdparm sdparm hddtemp
sudo systemctl mask smartd.service hddtemp.service
sudo systemctl mask btrfs-balance.timer btrfsmaintenance-refresh.path btrfs-scrub.timer

zypper packages --unneeded | awk -F'|' 'NR==0 || NR==1 || NR==2 || NR==3 || NR==4 {next} {print $3}' > list
while read p; do sudo zypper info $p && sudo zypper se --requires $p && sudo zypper rm $p; done  < list
rm -rf list

# ================== Services

# Network setup
sudo ln -sfv /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf

sudo systemctl daemon-reload

sudo systemctl enable dbus-broker
sudo systemctl enable --now \
NetworkManager systemd-resolved avahi-daemon sshd \
bluetooth chronyd docker cron.service fstrim.timer

sudo bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../hass-watchdog/install.sh"

curl --proto '=https' --tlsv1.2 -LsSf https://setup.atuin.sh | sh

# Saved system configs, home directories, and decrypted env files
sudo python3 "$SERVER_DIR/backup.py" restore
sudo systemctl daemon-reload

sudo systemctl enable --now disable-wifi-card.service

# Journal in RAM, uploaded to VictoriaLogs through vector
sudo systemctl disable --now systemd-journal-upload.service # Vector reads logs itself
sudo systemctl enable  --now systemd-journal-remote.socket  # Upload from other machines
sudo systemctl restart docker systemd-journald

# Nfs caching
sudo zypper install cachefilesd
sudo systemctl enable cachefilesd
