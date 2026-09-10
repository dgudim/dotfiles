from pathlib import Path
import shutil

USER_DIR = Path("/home/kloud")
BACKUP_DIR = Path(USER_DIR, "dotfiles/Documents/usefull_files/exact_scripts/server/the-rock/system-configs")

BACKUP_DIR.mkdir(exist_ok=True)

configs_to_copy = [
    Path("/etc/systemd/resolved.conf"),
    Path("/etc/ssh/sshd_config"),
    Path("/etc/fstab"),
    Path("/etc/nsswitch.conf"),
    Path("/etc/avahi/avahi-daemon.conf"),
    Path("/etc/default/grub")
]

for config in configs_to_copy:
    print(f"Copying {config}")
    config_full_path = Path(BACKUP_DIR, config.as_posix().partition('/')[2])
    config_full_path.parent.mkdir(exist_ok=True, parents=True)
    shutil.copy(config, config_full_path)
