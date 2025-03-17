#!/bin/bash

if ! yay -Q | grep udev-no | cut -d ' ' -f2 | grep -q 0.3.2; then
    target_dir="/tmp/yay/udev-notify-my"
    mkdir -pv "$target_dir"
    cp -vf pkgbuilds/udev-notify-PKGBUILD "$target_dir/PKGBUILD"
    cd "$target_dir"
    makepkg -si
fi
