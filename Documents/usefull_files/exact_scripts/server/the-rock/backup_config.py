OWNER = (1000, 100)  # owner of the files written into this repo

HOME_FOLDERS_TO_IGNORE = [
    "dotfiles",
]

# Dotfiles in the home directory (relative to /home/kloud).
HOME_FILES = [
    ".bashrc",
    ".gitconfig",
    ".config/atuin/config.toml",
]

SYSTEM_FILES = [

    # Journal in-ram
    "/etc/systemd/journald.conf",
    "/etc/systemd/journald.conf.d/volatile.conf",
    "/etc/systemd/journal-remote.conf",
    # Logs: journal in RAM, upload to microchelik
    "/etc/systemd/journal-upload.conf",
    "/etc/systemd/system/systemd-journal-upload.service.d/override.conf",

    # Docker
    "/etc/docker/daemon.json",

    # Base system
    "/etc/fstab",
    "/etc/nanorc",
    "/etc/udev/rules.d/*.rules",
    "/etc/default/cpufrequtils",
    "/etc/locale.gen",
    "/etc/default/locale",
    # Board: device-tree overlays (pwm fan).
    backup_only("/boot/armbianEnv.txt"),

    # Storage
    "/etc/modprobe.d/zfs.conf",
    secret("/etc/zfs/zed.d/zed.rc"), # Has ntfy token
    # NFS server
    "/etc/exports",
    "/etc/nfs.conf",

    # disable armbian-ramlog + zram
    "/etc/default/armbian-ramlog",
    "/etc/default/armbian-zram-config",

    # Networking
    "/etc/hosts",
    "/etc/hostname",
    "/etc/ssh/sshd_config",
    "/etc/systemd/resolved.conf",
    "/etc/nsswitch.conf",
    "/etc/avahi/avahi-daemon.conf",
    "/etc/systemd/network/10-netplan-eth0.network",

    # Hass UPS
    secret("/opt/hass-power-monitor/hass-power-monitor-config.json")
]
