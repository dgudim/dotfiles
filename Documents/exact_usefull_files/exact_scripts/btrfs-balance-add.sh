#!/bin/sh

FILE="$1"
SIZE="$2"
if [ "$#" -lt 3 ]; then
    LOC="/"
else
    LOC="$3"
fi

btrfs filesystem df "$LOC"  # Print old
truncate -s "$SIZE" "$FILE" # If filesystem doesn't support "truncate", then use dd
modprobe loop               # in case system hasn't yet loaded support for loopback devices
DEV_LOOP="$(losetup -f)"
losetup "$DEV_LOOP" "$FILE"
btrfs device add -f "$DEV_LOOP" "$LOC"
btrfs balance start "$LOC" # feel free to tweak these values
btrfs device delete "$DEV_LOOP" "$LOC"
btrfs filesystem df "$LOC" # Print new
losetup -d "$DEV_LOOP"
rm "$FILE"
