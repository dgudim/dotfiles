OWNER = (1000, 100)  # owner of the files written into this repo

HOME_FOLDERS_TO_IGNORE = [
    "album",
    "dotfiles",
]

# Dotfiles in the home directory (relative to /home/kloud). .env files among
# them are encrypted.
HOME_FILES = [
    ".gitconfig",
    ".bashrc",
    ".config/atuin/config.toml",
    "run_nextcloud.sh",
]

SYSTEM_FILES = [

    # Journal in-ram + dir for vector
    "/etc/systemd/journald.conf.d/volatile.conf",
    "/etc/systemd/journal-upload.conf",
    "/etc/systemd/journal-remote.conf",
    "/etc/tmpfiles.d/journal-remote.conf",
    "/etc/systemd/system/systemd-journal-remote.service.d/override.conf",

    "/etc/docker/daemon.json",

    "/etc/fstab",

    "/etc/default/grub",
    "/etc/nanorc",
    "/etc/sysctl.d/99-conntrack-acct.conf",
    "/etc/modules-load.d/nf_conntrack.conf",
    "/etc/sysctl.d/91-ulimit.conf",

    "/etc/security/limits.d/90-nproc.conf",
    "/etc/systemd/system/disable-wifi-card.service",

    # Zram
    "/etc/sysctl.d/99-zram.conf",
    "/etc/systemd/zram-generator.conf",

    # NFS
    "/etc/nfs.conf.d/99-rahead.conf",
    "/etc/cachefilesd.conf"

    # System
    "/etc/hosts",
    "/etc/systemd/resolved.conf",
    "/etc/nsswitch.conf",
    "/etc/avahi/avahi-daemon.conf",
    "/etc/locale.conf",
    "/etc/ssh/sshd_config",
]
