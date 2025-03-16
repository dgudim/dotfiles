#!/bin/bash

target_dir="/tmp/yay/udev-notify-my"
mkdir -pv "$target_dir"
cp -vf pkgbuilds/udev-notify-PKGBUILD "$target_dir/PKGBUILD"
cd "$target_dir"
makepkg -si
