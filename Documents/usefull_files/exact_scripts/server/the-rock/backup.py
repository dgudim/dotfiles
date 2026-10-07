import os
from pathlib import Path
import shutil
import subprocess
import sys

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
    (USER_DIR / ".bashrc", Path("home/kloud/.bashrc")),
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
                "--chown=1000:100",
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


def give_to_user(root: Path) -> None:
    if not root.exists():
        return
    for path in [root, *root.rglob("*")]:
        os.chown(path, 1000, 100, follow_symlinks=False)


def backup() -> None:
    for source, dest_relative in system_configs_to_copy:
        if not source.is_file():
            print(f"Skipping {source}")
            continue
        destination = BACKUP_DIR / "system-configs" / dest_relative
        print(f"Copying {source}")
        destination.parent.mkdir(exist_ok=True, parents=True)
        shutil.copy(source, destination)

    give_to_user(BACKUP_DIR / "system-configs")
    copy_home_directories()
    give_to_user(HOME_BACKUP_DIR)


def restore_file(saved: Path, destination: Path) -> None:
    print(f"Restoring {saved} -> {destination}")
    if destination.is_relative_to("/etc"):
        subprocess.run(["sudo", "mkdir", "-p", str(destination.parent)], check=True)
        subprocess.run(["sudo", "cp", "-a", str(saved), str(destination)], check=True)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(saved, destination)


def decrypt_env_files(root: Path) -> None:
    for encrypted in root.rglob("*.age"):
        if not encrypted.is_file():
            continue
        plain = encrypted.with_name(encrypted.name.removesuffix(".age"))
        if not is_env_file(plain):
            continue
        print(f"Decrypting {encrypted} -> {plain}")
        subprocess.run(
            ["age", "-d", "-i", str(AGE_IDENTITY), "-o", str(plain), str(encrypted)],
            check=True,
        )
        encrypted.unlink()


def restore_home_directories() -> None:
    if not HOME_BACKUP_DIR.is_dir():
        print(f"Skipping {HOME_BACKUP_DIR}")
        return
    for entry in HOME_BACKUP_DIR.iterdir():
        if not entry.is_dir() or entry.is_symlink():
            continue
        destination = USER_DIR / entry.name
        destination.mkdir(exist_ok=True)
        print(f"Restoring {entry} -> {destination}")
        subprocess.run(
            ["rsync", "-a", "--no-owner", "--no-group", f"{entry}/", f"{destination}/"],
            check=True,
        )
        decrypt_env_files(destination)


def restore() -> None:
    for _source, dest_relative in system_configs_to_copy:
        saved = BACKUP_DIR / "system-configs" / dest_relative
        if not saved.is_file():
            print(f"Skipping {saved}")
            continue
        restore_file(saved, _source)
    restore_home_directories()


def main() -> None:
    action = "backup"
    if len(sys.argv) > 1:
        action = sys.argv[1].removeprefix("--")
    if action == "backup":
        backup()
    elif action == "restore":
        restore()
    else:
        raise SystemExit(f"Unknown action {sys.argv[1]!r}. Use backup or restore.")


if __name__ == "__main__":
    main()
