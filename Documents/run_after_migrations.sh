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

# Replaced with Vesktop
rm -rfv ~/.config/BetterDiscord\ Installer
rm -rfv ~/.config/BetterDiscord
rm -rfv ~/.config/discord

# Make sure kde notification service is started instead of dunst
mkdir -p ~/.local/share/dbus-1/services/
ln -sf /usr/share/dbus-1/services/org.kde.plasma.Notifications.service ~/.local/share/dbus-1/services/org.kde.plasma.Notifications.service

# Moved to XDG
rm -rfv ~/.ssr

# No need to override since arched switched to dbus-broker by default
rm -fv /home/kloud/.config/systemd/user/dbus.service

echo -e "${L_GREEN}Done!$NC\n"
