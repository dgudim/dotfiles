#!/bin/bash

set -e
set -o pipefail

L_GREEN='\033[1;32m'
L_PURPLE='\033[1;35m'
NC='\033[0m'

echo -e "${L_PURPLE}Executing migrations$NC..."
rm -rfv ~/.gnupg
rm -fv ~/.config/environment.d/xdg.conf
rm -fv ~/.bash_history
sudo rm -fv /root/.bash_history
rm -fv ~/.config/dragonplayerrc
rm -rfv ~/.config/nheko

# Replaced with Vesktop
rm -rfv ~/.config/BetterDiscord\ Installer
rm -rfv ~/.config/BetterDiscord
rm -rfv ~/.config/discord

# Make sure kde notification service is started instead of dunst (obsolete, delete)
rm -rfv ~/.local/share/dbus-1/services/org.kde.plasma.Notifications.service

# Moved to XDG
rm -rfv ~/.ssr

# No need to override since arch switched to dbus-broker by default
rm -fv ~/.config/systemd/user/dbus.service

# Merged with main file
sudo rm -fv /etc/debuginfod/alhp.urls

# Cleanup after viber
rm -rfv ~/.ViberPC

# Delete plasma 5 stuff
rm -fv ~/.config/khotkeysrc
rm -fv ~/.config/kwalletd5.notifyrc
rm -rfv ~/.local/share/kservices5
rm -fv ~/.local/share/applications/gpick.desktop
rm -rfv ~/.local/share/icons/Simp1e-Gruvbox-Dark
rm -rf ~/.local/share/applications/ksysguard.desktop

# Fix activitywatch
sudo rm -f /opt/activitywatch/libwayland-client.so.0

# Delete sensitive data
secret-tool clear user kloud || true

# Replaced with pipxu
rm -rfv ~/.local/share/pipx

# Symlink to stub systemd-resolved stub resolver
[ -L /etc/resolv.conf ] || sudo ln -fvs /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf

# Renamed
rm -fv ~/.config/autostart/syncthingtray-qt6.desktop

echo -e "${L_GREEN}Done!$NC\n"
