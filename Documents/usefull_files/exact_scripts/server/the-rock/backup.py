import os
from pathlib import Path
import shutil
import subprocess

USER_DIR = Path("/home/kloud")
BACKUP_DIR = Path(USER_DIR, "dotfiles/Documents/usefull_files/exact_scripts/server/the-rock")
# On the server this is /etc. The scheduled job mounts host /etc at /host-etc.
ETC_DIR = Path(os.environ.get("BACKUP_ETC", "/etc"))
AGE_RECIPIENT = USER_DIR / ".ssh" / "id_ed25519.pub"
AGE_IDENTITY = USER_DIR / ".ssh" / "id_ed25519"

home_folders_to_ignore = [
    "album",
    "dotfiles",
]

BACKUP_DIR.mkdir(exist_ok=True)

# Source path, and where it lands under system-configs/.
system_configs_to_copy = [
    (ETC_DIR / "systemd/resolved.conf", Path("etc/systemd/resolved.conf")),
    (ETC_DIR / "ssh/sshd_config", Path("etc/ssh/sshd_config")),
    (ETC_DIR / "fstab", Path("etc/fstab")),
    (ETC_DIR / "nsswitch.conf", Path("etc/nsswitch.conf")),
    (ETC_DIR / "avahi/avahi-daemon.conf", Path("etc/avahi/avahi-daemon.conf")),
    (ETC_DIR / "default/grub", Path("etc/default/grub")),
    (ETC_DIR / "nanorc", Path("etc/nanorc")),
    (ETC_DIR / "hosts", Path("etc/hosts")),
    (USER_DIR / ".gitconfig", Path("home/kloud/.gitconfig")),
]


def is_env_file(path: Path) -> bool:
    return path.name == ".env" or path.name.endswith(".env")


def plaintext_matches_existing(env_file: Path, encrypted: Path) -> bool:
    if not encrypted.is_file():
        return False
    result = subprocess.run(
        ["age", "-d", "-i", str(AGE_IDENTITY), str(encrypted)],
        capture_output=True,
    )
    return result.returncode == 0 and result.stdout == env_file.read_bytes()


def remove_stale_age_files(source: Path, destination: Path) -> None:
    if not destination.exists():
        return
    for encrypted in destination.rglob("*.age"):
        if not encrypted.is_file() or not is_env_file(Path(encrypted.name.removesuffix(".age"))):
            continue
        relative = encrypted.relative_to(destination).with_name(encrypted.name.removesuffix(".age"))
        if (source / relative).is_file():
            continue
        print(f"Removing {encrypted}")
        encrypted.unlink()


def encrypt_copied_env_files(destination: Path) -> None:
    for env_file in destination.rglob("*"):
        if not env_file.is_file() or not is_env_file(env_file):
            continue
        encrypted = env_file.with_name(env_file.name + ".age")
        if plaintext_matches_existing(env_file, encrypted):
            print(f"Unchanged {encrypted}")
            env_file.unlink()
            continue
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
        remove_stale_age_files(entry, destination)
        subprocess.run(
            [
                "rsync",
                "-a",
                "--delete",
                "--filter",
                "protect *.age",
                f"{entry}/",
                f"{destination}/",
            ],
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


for source, dest_relative in system_configs_to_copy:
    if not source.is_file():
        print(f"Skipping {source}")
        continue
    destination = BACKUP_DIR / "system-configs" / dest_relative
    print(f"Copying {source}")
    destination.parent.mkdir(exist_ok=True, parents=True)
    shutil.copy(source, destination)

system_configs = BACKUP_DIR / "system-configs"
for path in [system_configs, *system_configs.rglob("*")]:
    shutil.chown(path, user=1000, group=100)

copy_home_directories()
