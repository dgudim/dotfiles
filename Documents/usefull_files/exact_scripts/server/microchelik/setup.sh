#Add repos
source /etc/os-release

sudo zypper addrepo https://download.opensuse.org/repositories/devel:tools/$VERSION/devel:tools.repo
sudo zypper addrepo -cfp 90 'https://ftp.gwdg.de/pub/linux/misc/packman/suse/openSUSE_Leap_$releasever/' packman
sudo zypper addrepo -f https://download.opensuse.org/repositories/Kernel:/stable:/Backport/$VERSION/ kernel-backport

sudo zypper refresh
sudo zypper dist-upgrade --from packman --allow-vendor-change
sudo zypper install --allow-vendor-change --from packman ffmpeg gstreamer-plugins-{good,bad,ugly,libav} libavcodec

zypper modifyrepo --refresh devel_tools
zypper modifyrepo --refresh packman

# Deps
sudo zypper install \
chrony dbus-broker docker docker-compose \
NetworkManager systemd-resolved nss-mdns openssh-sftp-server \
systemd-journal-remote

# Network setup
sudo ln -sfv /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf

sudo systemctl enable dbus-broker
sudo systemctl enable --now \
NetworkManager systemd-resolved avahi-daemon sshd \
bluetooth chronyd docker fstrim.timer

sudo hostnamectl set-hostname microchelik
sudo loginctl enable-linger kloud

# Unneeded + replaced with scrutiny
sudo systemctl disable --now firewalld apparmor smartd
sudo systemctl mask firewalld apparmor smartd
sudo systemctl disable --now btrfs-balance.timer btrfsmaintenance-refresh.path btrfs-scrub.timer

# Audio deps
sudo zypper install \
pipewire wireplumber pipewire-pulseaudio pulseaudio-utils dfu-util pipewire-alsa \
alsa-firmware alsa-plugins bluez bluez-firmware bluez-auto-enable-devices

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

sudo systemctl enable --now cron

# Handled by scrutiny
sudo zypper remove smartmontools

# Headless: desktop, browser, office, and unused services
sudo zypper remove \
MozillaFirefox MozillaThunderbird libreoffice\* \
xfce4-session xfce4-taskmanager xfce4-panel xfce4-power-manager xfce4-settings \
xfce4-notifyd xfce4-screensaver xfce4-panel-branding-openSUSE xfce4-terminal \
xfce4-whiskermenu-plugin xfce4-dict xfce4-appfinder \
xfce4-panel-restore-defaults xfce4-session-branding-openSUSE xfce4-settings-branding-openSUSE \
xfce4-notifyd-branding-openSUSE xfce4-power-manager-branding-openSUSE \
xfce4-screenshooter xfce4-screenshooter-lang \
xorg-x11-server xorg-x11-essentials xorg-x11-server-extra x11-tools xorg-x11-fonts \
cockpit cockpit-packages cockpit-bridge \
snapper firewalld cups dnsmasq file-roller

sudo systemctl disable --now auditd
sudo systemctl mask auditd

[ -L /etc/resolv.conf ] || sudo ln -fvs /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf

sudo bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../hass-watchdog/install.sh"

curl --proto '=https' --tlsv1.2 -LsSf https://setup.atuin.sh | sh

# Saved system configs, home directories, and decrypted env files
python3 "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/backup.py" restore

sudo systemctl daemon-reload
sudo systemctl enable --now disable-wifi-card.service

# Journal in RAM, uploaded to VictoriaLogs through vector
sudo systemctl restart systemd-journald
sudo systemctl disable --now rsyslog.service
sudo systemctl disable --now systemd-journal-upload.service # Vector reads logs itself
sudo systemctl enable  --now systemd-journal-remote.socket  # Upload from other machines
sudo systemctl restart docker

# Setup nfs caching
sudo zypper install cachefilesd
sudo systemctl daemon-reload
sudo systemctl enable cachefilesd

# Zram
sudo zypper install zram-generator
# sudo systemctl daemon-reload
# sudo systemctl start systemd-zram-setup@zram0.service
