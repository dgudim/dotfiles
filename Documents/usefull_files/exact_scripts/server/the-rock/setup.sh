#Add repos
source /etc/os-release

sudo zypper addrepo https://download.opensuse.org/repositories/devel:tools/$VERSION/devel:tools.repo
sudo zypper addrepo -cfp 90 'https://ftp.gwdg.de/pub/linux/misc/packman/suse/openSUSE_Leap_$releasever/' packman

sudo zypper refresh
sudo zypper dist-upgrade --from packman --allow-vendor-change
sudo zypper install --allow-vendor-change --from packman ffmpeg gstreamer-plugins-{good,bad,ugly,libav} libavcodec

zypper modifyrepo --refresh devel_tools
zypper modifyrepo --refresh packman

# Deps
sudo zypper install \
chrony dbus-broker docker docker-compose \
NetworkManager systemd-resolved nss-mdns openssh-sftp-server \
cron

# Network setup
sudo ln -sfv /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf

sudo systemctl enable dbus-broker
sudo systemctl enable --now \
NetworkManager systemd-resolved avahi-daemon sshd \
bluetooth chronyd docker cron

# Audio deps
sudo zypper install \
pipewire wireplumber pipewire-pulseaudio pulseaudio-utils dfu-util pipewire-alsa \
alsa-firmware alsa-plugins bluez bluez-firmware bluez-auto-enable-devices

# Different utils
sudo zypper install \
fwupd fastfetch btop htop eza \
jq yq usbip tcpdump \
intel-media-driver intel-gpu-tools \
waypipe ripgrep fd duf \
atuin rsync \
bindfs

# Bindfs is for nextcloud

# Handled by scrutiny
sudo zypper remove smartmontools
