OWNER = (1000, 100)  # owner of the files written into this repo

HOME_FOLDERS_TO_IGNORE = [
    "album/travel-album-v2",
    "dotfiles",
]

# Dotfiles in the home directory (relative to /home/kloud). .env files among
# them are encrypted.
HOME_FILES = [
    ".gitconfig",
    ".bashrc",
    ".config/atuin/config.toml",
    "base_env_definitions",
    "relabel-containers.py"
]

SYSTEM_FILES = [
    # Journal in-ram
    "/etc/systemd/journald.conf.d/volatile.conf",
    "/etc/systemd/journal-upload.conf",
    # Dir for vector
    "/etc/tmpfiles.d/journal-remote.conf",
    # log upload config (from the-rock)
    "/etc/systemd/journal-remote.conf",
    "/etc/systemd/system/systemd-journal-remote.service.d/override.conf",

    # Docker
    "/etc/docker/daemon.json",

    # Base system
    "/etc/fstab",
    "/etc/nanorc",
    "/etc/udev/rules.d/*.rules",
    "/etc/default/grub",
    "/etc/locale.conf",

    # Settings for monitoring
    "/etc/sysctl.d/99-conntrack-acct.conf",
    "/etc/modules-load.d/nf_conntrack.conf",
    "/etc/sysctl.d/91-ulimit.conf",
    "/etc/security/limits.d/90-nproc.conf",

    # Useless wifi
    "/etc/systemd/system/disable-wifi-card.service",

    # Storage, NFS
    "/etc/nfs.conf.d/99-rahead.conf",
    "/etc/cachefilesd.conf",

    # Zram
    "/etc/sysctl.d/99-zram.conf",
    "/etc/systemd/zram-generator.conf",

    # Networking
    "/etc/hosts",
    "/etc/hostname",
    "/etc/ssh/sshd_config",
    "/etc/systemd/resolved.conf",
    "/etc/nsswitch.conf",
    "/etc/avahi/avahi-daemon.conf",
    "/etc/NetworkManager/system-connections/eth0.nmconnection",

    # Hass UPS
    secret("/opt/hass-power-monitor/hass-power-monitor-config.json")
]
