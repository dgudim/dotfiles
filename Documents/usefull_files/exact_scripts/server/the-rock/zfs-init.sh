#!/usr/bin/env bash
# Creates the "chonker" pool on empty disks. ERASES /dev/sdb, /dev/sdd and /dev/sda.

sudo zpool create -f -o ashift=12 chonker mirror /dev/sdb /dev/sdd
sudo zpool add -f chonker cache /dev/sda
sudo zfs set mountpoint=/mnt/chonker chonker

sudo zfs set atime=off chonker
sudo zfs set compression=lz4 chonker
sudo zfs set xattr=sa chonker # Store extended attributes in inodes for better performance
sudo zfs set acltype=posixacl chonker
sudo zfs set sync=disabled chonker # Treat sync writes as async, I don't care, I have a UPS

sudo zfs create chonker/media
sudo zfs create chonker/music
sudo zfs create chonker/photos

sudo zfs set compression=off chonker/media
sudo zfs set compression=off chonker/music
sudo zfs set compression=off chonker/photos

sudo zfs set recordsize=1M chonker/media
sudo zfs set recordsize=1M chonker/music
sudo zfs set recordsize=1M chonker/photos

sudo chown kloud:users /mnt/chonker/media /mnt/chonker/music /mnt/chonker/photos
