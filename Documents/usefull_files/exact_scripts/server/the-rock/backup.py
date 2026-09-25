from pathlib import Path
import shutil
import subprocess

USER_DIR = Path("/home/kloud")
BACKUP_DIR = Path(USER_DIR, "dotfiles/Documents/usefull_files/exact_scripts/server/the-rock")
AGE_RECIPIENT = USER_DIR / ".ssh" / "id_ed25519.pub"

home_folders_to_ignore = [
    "album",
    "dotfiles",
]

BACKUP_DIR.mkdir(exist_ok=True)

configs_to_copy = [
    Path("/etc/systemd/resolved.conf"),
    Path("/etc/ssh/sshd_config"),
    Path("/etc/fstab"),
    Path("/etc/nsswitch.conf"),
    Path("/etc/avahi/avahi-daemon.conf"),
    Path("/etc/default/grub"),
]


def is_env_file(path: Path) -> bool:
    return path.name == ".env" or path.name.endswith(".env")


def encrypt_copied_env_files(destination: Path) -> None:
    for env_file in destination.rglob("*"):
        if not env_file.is_file() or not is_env_file(env_file):
            continue
        encrypted = env_file.with_name(env_file.name + ".age")
        print(f"Encrypting {env_file} -> {encrypted}")
        subprocess.run(
            ["age", "-R", str(AGE_RECIPIENT), "-o", str(encrypted), str(env_file)],
            check=True,
        )
        env_file.unlink()

HOME_BACKUP_DIR = BACKUP_DIR / "home"

def copy_home_directories() -> None:
    HOME_BACKUP_DIR.mkdir(exist_ok=True)
    ignored = set(home_folders_to_ignore)
    mirrored = set()
    for entry in USER_DIR.iterdir():
        if not entry.is_dir() or entry.name.startswith(".") or entry.name in ignored:
            continue
        destination = HOME_BACKUP_DIR / entry.name
        mirrored.add(entry.name)
        destination.mkdir(exist_ok=True)
        print(f"Mirroring {entry} -> {destination}")
        subprocess.run(
            ["rsync", "-a", "--delete", f"{entry}/", f"{destination}/"],
            check=True,
        )
        encrypt_copied_env_files(destination)

    for existing in HOME_BACKUP_DIR.iterdir():
        if existing.name in mirrored:
            continue
        print(f"Removing {existing}")
        if existing.is_dir() and not existing.is_symlink():
            shutil.rmtree(existing)
        else:
            existing.unlink()


for config in configs_to_copy:
    print(f"Copying {config}")
    config_full_path = Path(BACKUP_DIR, "system-configs", config.as_posix().partition("/")[2])
    config_full_path.parent.mkdir(exist_ok=True, parents=True)
    shutil.copy(config, config_full_path)

system_configs = BACKUP_DIR / "system-configs"
for path in [system_configs, *system_configs.rglob("*")]:
    shutil.chown(path, user="kloud", group="users")

copy_home_directories()
