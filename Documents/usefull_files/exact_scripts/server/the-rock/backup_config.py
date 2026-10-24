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
    backup_only("/etc/fstab"),

    "/etc/nanorc",

    # Board: device-tree overlays (pwm fan).
    backup_only("/boot/armbianEnv.txt"),
    "/etc/default/cpufrequtils",
    "/etc/udev/rules.d/*.rules",

    "/etc/modprobe.d/zfs.conf",
    secret("/etc/zfs/zed.d/zed.rc"), # Has ntfy token

    # NFS server
    "/etc/exports",
    "/etc/nfs.conf",

    # Docker
    "/etc/docker/daemon.json",

    # Logs: journal in RAM, upload to microchelik; disable armbian-ramlog
    "/etc/systemd/journald.conf",
    "/etc/systemd/journald.conf.d/volatile.conf",
    "/etc/systemd/journal-upload.conf",
    "/etc/systemd/system/systemd-journal-upload.service.d/override.conf",
    "/etc/default/armbian-ramlog",
    "/etc/default/armbian-zram-config",

    # System
    "/etc/ssh/sshd_config",
    "/etc/locale.gen",
    "/etc/default/locale",
    "/etc/systemd/resolved.conf",
]
