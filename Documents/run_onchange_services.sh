#!/bin/bash

set -e

echo "Setting up services..."

sudo systemctl enable drkonqi-coredump-processor@.service
systemctl --user enable --now drkonqi-coredump-launcher.socket drkonqi-coredump-cleanup.timer

# Enable kernel modules cleanup
sudo systemctl enable linux-modules-cleanup.service

# Enable dbus-broker
systemctl enable --user dbus-broker.service
sudo systemctl enable dbus-broker.service

# Enable docker socket
systemctl enable --now --user docker.socket

echo "Service setup done!"
