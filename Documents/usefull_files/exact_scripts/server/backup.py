#!/usr/bin/env python3
"""Back up a server's configs into <host>/ next to this script, or restore them.

<host>/backup_config.py  what to back up
<host>/system-configs/   SYSTEM_FILES, at their path under /
<host>/home/             home folders and HOME_FILES
Secrets (secret() in SYSTEM_FILES or HOME_FILES) and .env files are stored
age-encrypted as <name>.age.

Each backup builds system-configs/ and home/ from scratch and then swaps them in.
age output is randomised, so a secret that didn't change keeps its old .age file.
"""

from __future__ import annotations

import argparse
import os
import runpy
import shutil
import socket
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass, field
from glob import has_magic
from pathlib import Path

HOME = Path(os.environ.get("HOME", ""))
HOST_ROOT = Path(os.environ.get("HOST_ROOT", "/"))
AGE_RECIPIENT = HOME / ".ssh/id_ed25519.pub"
AGE_IDENTITY = HOME / ".ssh/id_ed25519"


@dataclass(frozen=True)
class Entry:
    path: str
    secret: bool = False
    restore: bool = True  # False: kept for reference, applied by hand


def secret(path: str) -> Entry:
    return Entry(path, secret=True)


def backup_only(path: str, secret: bool = False) -> Entry:
    return Entry(path, secret=secret, restore=False)


@dataclass
class Config:
    owner: tuple[int, int] = (1000, 100)
    home_folders_to_ignore: set[str] = field(default_factory=set)
    home_files: list[Entry] = field(default_factory=list)
    system_files: list[Entry] = field(default_factory=list)


def load_config(config_file: Path) -> Config:
    values = runpy.run_path(
        str(config_file),
        init_globals={"Entry": Entry, "secret": secret, "backup_only": backup_only},
    )

    def entries(name: str) -> list[Entry]:
        return [item if isinstance(item, Entry) else Entry(str(item)) for item in values.get(name, [])]

    def fail(entry: Entry, problem: str):
        raise SystemExit(f"{config_file}: {entry.path}: {problem}")

    system_files = entries("SYSTEM_FILES")
    for entry in system_files:
        if not Path(entry.path).is_absolute():
            fail(entry, "SYSTEM_FILES paths must be absolute")
        if has_magic(str(Path(entry.path).parent)):
            fail(entry, "only the last component may be a glob")

    home_files = entries("HOME_FILES")
    for entry in home_files:
        if Path(entry.path).is_absolute():
            fail(entry, "HOME_FILES paths are relative to the home folder")
        if not entry.restore:
            fail(entry, "backup_only() isn't supported in HOME_FILES")

    return Config(
        owner=tuple(values.get("OWNER", (1000, 100))),
        home_folders_to_ignore={p.strip("/") for p in values.get("HOME_FOLDERS_TO_IGNORE", [])},
        home_files=home_files,
        system_files=system_files,
    )


# Files and encryption


def is_env_file(path: Path) -> bool:
    return path.name.endswith(".env")


def with_age(path: Path) -> Path:
    return path.with_name(path.name + ".age")


def without_age(path: Path) -> Path:
    return path.with_name(path.name.removesuffix(".age"))


def encrypt(plain: Path, encrypted: Path, previous: Path | None = None) -> None:
    """Encrypt plain to encrypted. age output differs on every run, so an unchanged
    file keeps its previous ciphertext (previous, default: encrypted itself)."""
    data = plain.read_bytes()
    previous = previous or encrypted
    encrypted.parent.mkdir(parents=True, exist_ok=True)
    if previous.is_file():
        current = subprocess.run(["age", "-d", "-i", AGE_IDENTITY, previous], capture_output=True)
        if current.returncode == 0 and current.stdout == data:
            print(f"Unchanged {encrypted}")
            if previous != encrypted:
                shutil.copy2(previous, encrypted)
            return
    print(f"Encrypting {plain} -> {encrypted}")
    subprocess.run(["age", "-R", AGE_RECIPIENT, "-o", encrypted], input=data, check=True)


def decrypt(encrypted: Path, plain: Path) -> None:
    print(f"Decrypting {encrypted} -> {plain}")
    data = subprocess.run(["age", "-d", "-i", AGE_IDENTITY, encrypted], stdout=subprocess.PIPE, check=True).stdout
    plain.parent.mkdir(parents=True, exist_ok=True)
    plain.write_bytes(data)  # an existing file keeps its mode


def copy(source: Path, destination: Path) -> None:
    print(f"Copying {source} -> {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


@contextmanager
def rebuild(folder: Path):
    """Build a new copy of folder in folder.new; it replaces folder only if building succeeds."""
    new = folder.with_name(folder.name + ".new")
    shutil.rmtree(new, ignore_errors=True)  # left over from a killed run
    new.mkdir(parents=True)
    try:
        yield new
    except BaseException:
        shutil.rmtree(new, ignore_errors=True)  # can hold .env files not yet encrypted
        raise
    shutil.rmtree(folder, ignore_errors=True)
    new.rename(folder)


def chown_tree(root: Path, uid: int, gid: int) -> None:
    if not root.exists():
        return
    for path in [root, *root.rglob("*")]:
        os.chown(path, uid, gid, follow_symlinks=False)


def rsync(*args: str | Path) -> None:
    subprocess.run(["rsync", "-a", *map(str, args)], check=True)


class Backup:
    def __init__(self, host_dir: Path, config: Config):
        self.config = config
        self.system_dir = host_dir / "system-configs"
        self.home_dir = host_dir / "home"

    def backup(self) -> None:
        self.backup_system_files()
        self.backup_home()
        chown_tree(self.system_dir, *self.config.owner)
        chown_tree(self.home_dir, *self.config.owner)

    def restore(self) -> None:
        self.restore_system_files()
        self.restore_home()

    # System files: /etc/fstab is saved as system-configs/etc/fstab

    def saved_files(self, entry: Entry) -> list[Path]:
        """Files already in the backup for this entry."""
        path = Path(entry.path)
        pattern = path.name + ".age" if entry.secret else path.name
        folder = self.system_dir / path.parent.relative_to("/")
        return [f for f in sorted(folder.glob(pattern)) if f.is_file()]

    def backup_system_files(self) -> None:
        with rebuild(self.system_dir) as new_dir:
            for entry in self.config.system_files:
                path = Path(entry.path)
                server_folder = HOST_ROOT / path.parent.relative_to("/")
                sources = [f for f in sorted(server_folder.glob(path.name)) if f.is_file()]
                if not sources:
                    print(f"Skipping {entry.path}")
                for source in sources:
                    relative = source.relative_to(HOST_ROOT)
                    if entry.secret:
                        encrypt(source, with_age(new_dir / relative), with_age(self.system_dir / relative))
                    else:
                        copy(source, new_dir / relative)

    def restore_system_files(self) -> None:
        for entry in self.config.system_files:
            if not entry.restore:
                print(f"Not restoring {entry.path} (backup only)")
                continue
            saved_files = self.saved_files(entry)
            if not saved_files:
                print(f"Skipping {entry.path}")
            for saved in saved_files:
                destination = HOST_ROOT / saved.relative_to(self.system_dir)
                if entry.secret:
                    decrypt(saved, without_age(destination))
                else:
                    copy(saved, destination)

    # Home: top-level folders are mirrored, dotfiles come from HOME_FILES

    def home_folders(self) -> list[Path]:
        ignored = self.config.home_folders_to_ignore | {"__pycache__"}
        return [
            folder
            for folder in sorted(HOME.iterdir())
            if folder.is_dir() and not folder.name.startswith(".") and folder.name not in ignored
        ]

    def backup_home(self) -> None:
        folders = {folder.name: folder for folder in self.home_folders()}

        for entry in self.config.home_files:
            first = Path(entry.path).parts[0]
            if entry.secret and first in folders:
                raise SystemExit(
                    f"{entry.path}: {first}/ is mirrored as a whole, so this secret would also be "
                    f"saved unencrypted. Add {first} to HOME_FOLDERS_TO_IGNORE or keep it out of HOME_FILES."
                )

        with rebuild(self.home_dir) as new_dir:
            for name, folder in folders.items():
                self.mirror_home_folder(folder, new_dir / name)

            for entry in self.config.home_files:
                relative = Path(entry.path)
                source = HOME / relative
                if not source.is_file():
                    print(f"Skipping {source}")
                elif entry.secret or is_env_file(relative):
                    encrypt(source, with_age(new_dir / relative), with_age(self.home_dir / relative))
                else:
                    copy(source, new_dir / relative)

    def mirror_home_folder(self, source: Path, saved: Path) -> None:
        """Copy source to saved, keeping .env files only as .env.age."""
        print(f"Mirroring {source} -> {saved}")
        excludes = []
        for ignored in sorted(self.config.home_folders_to_ignore):
            if ignored.startswith(f"{source.name}/"):
                excludes.append(f"--exclude=/{ignored.removeprefix(f'{source.name}/')}")
        rsync(*excludes, f"{source}/", f"{saved}/")

        previous = self.home_dir / source.name
        for plain in sorted(saved.rglob("*.env")):
            if plain.is_file():
                encrypt(plain, with_age(plain), with_age(previous / plain.relative_to(saved)))
                plain.unlink()

    def restore_home(self) -> None:
        if not self.home_dir.is_dir():
            print(f"Skipping {self.home_dir}")
            return
        print(f"Restoring {self.home_dir} -> {HOME}")
        top_level = [p for p in sorted(self.home_dir.iterdir()) if not p.is_symlink()]
        symlinks = [f"--exclude=/{p.name}" for p in self.home_dir.iterdir() if p.is_symlink()]
        rsync("--no-owner", "--no-group", "--exclude=*.age", *symlinks, f"{self.home_dir}/", f"{HOME}/")
        for encrypted in sorted(self.home_dir.rglob("*.age")):
            decrypt(encrypted, HOME / without_age(encrypted.relative_to(self.home_dir)))

        owner = HOME.stat()
        for saved in top_level:
            chown_tree(HOME / without_age(saved).name, owner.st_uid, owner.st_gid)


def detect_host() -> str:
    hostname_file = HOST_ROOT / "etc/hostname"
    name = hostname_file.read_text().strip() if hostname_file.is_file() else ""
    return (name or socket.gethostname()).split(".")[0]


def find_host_dir(host: str) -> Path:
    repo = Path(__file__).resolve().parent
    if (repo / host / "backup_config.py").is_file():
        return repo / host
    raise SystemExit(f"No backup config for host {host!r} (looked in {repo}). Use --host.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up or restore a server's configs.")
    parser.add_argument("action", nargs="?", default="backup", choices=["backup", "restore"])
    parser.add_argument("--host", help="host folder to use (default: this machine's hostname)")
    args = parser.parse_args()

    host = args.host or detect_host()
    host_dir = find_host_dir(host)
    print(f"Host {host}: {host_dir}")
    backup = Backup(host_dir, load_config(host_dir / "backup_config.py"))
    if args.action == "backup":
        backup.backup()
    else:
        backup.restore()


if __name__ == "__main__":
    main()
