#!/usr/bin/env python3
"""Back up a server's configs into <host>/ next to this script, or restore them.

<host>/backup_config.py  what to back up
<host>/system-configs/   SYSTEM_FILES, at their path under /
<host>/home/             home folders and HOME_FILES
Secrets and .env files are stored age-encrypted as <name>.age.
"""

from __future__ import annotations

import argparse
import os
import runpy
import shutil
import socket
import subprocess
from dataclasses import dataclass, field
from fnmatch import fnmatch
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
    home_files: list[Path] = field(default_factory=list)
    system_files: list[Entry] = field(default_factory=list)


def load_config(config_file: Path) -> Config:
    values = runpy.run_path(
        str(config_file),
        init_globals={"Entry": Entry, "secret": secret, "backup_only": backup_only},
    )
    system_files = []
    for item in values.get("SYSTEM_FILES", []):
        entry = item if isinstance(item, Entry) else Entry(str(item))
        path = Path(entry.path)
        if not path.is_absolute():
            raise SystemExit(f"{config_file}: {entry.path} is not an absolute path")
        if has_magic(str(path.parent)):
            raise SystemExit(f"{config_file}: {entry.path}: only the last component may be a glob")
        system_files.append(entry)
    return Config(
        owner=tuple(values.get("OWNER", (1000, 100))),
        home_folders_to_ignore={p.strip("/") for p in values.get("HOME_FOLDERS_TO_IGNORE", [])},
        home_files=[Path(p) for p in values.get("HOME_FILES", [])],
        system_files=system_files,
    )


def is_env_file(path: Path) -> bool:
    return path.name.endswith(".env")


def with_age(path: Path) -> Path:
    return path.with_name(path.name + ".age")


def without_age(path: Path) -> Path:
    return path.with_name(path.name.removesuffix(".age"))


def is_encrypted_env_file(path: Path) -> bool:
    return path.name.endswith(".age") and is_env_file(without_age(path))


def encrypt(plain: Path, encrypted: Path) -> None:
    data = plain.read_bytes()
    if encrypted.is_file():
        current = subprocess.run(["age", "-d", "-i", AGE_IDENTITY, encrypted], capture_output=True)
        if current.returncode == 0 and current.stdout == data:
            print(f"Unchanged {encrypted}")
            return
    print(f"Encrypting {plain} -> {encrypted}")
    encrypted.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["age", "-R", AGE_RECIPIENT, "-o", encrypted], input=data, check=True)


def decrypt(encrypted: Path, plain: Path) -> None:
    print(f"Decrypting {encrypted} -> {plain}")
    data = subprocess.run(["age", "-d", "-i", AGE_IDENTITY, encrypted], stdout=subprocess.PIPE, check=True).stdout
    plain.parent.mkdir(parents=True, exist_ok=True)
    plain.write_bytes(data)  # an existing file keeps its mode


def encrypt_env_files(folder: Path) -> None:
    for plain in sorted(folder.rglob("*.env")):
        if plain.is_file():
            encrypt(plain, with_age(plain))
            plain.unlink()


def decrypt_env_files(folder: Path) -> None:
    for encrypted in sorted(folder.rglob("*.env.age")):
        if encrypted.is_file():
            decrypt(encrypted, without_age(encrypted))
            encrypted.unlink()


def server_path(path: Path) -> Path:
    return HOST_ROOT / path.relative_to("/")


def copy(source: Path, destination: Path) -> None:
    print(f"Copying {source} -> {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def remove(path: Path) -> None:
    print(f"Removing {path}")
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def chown_tree(root: Path, uid: int, gid: int) -> None:
    if not root.exists():
        return
    for path in [root, *root.rglob("*")]:
        os.chown(path, uid, gid, follow_symlinks=False)


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

    # System files, handled as server paths like /etc/fstab

    def saved_path(self, entry: Entry, path: Path) -> Path:
        saved = self.system_dir / path.relative_to("/")
        return with_age(saved) if entry.secret else saved

    def paths_on_server(self, entry: Entry) -> list[Path]:
        path = Path(entry.path)
        if not has_magic(path.name):
            return [path]
        found = server_path(path.parent).glob(path.name)
        return [path.parent / f.name for f in sorted(found) if f.is_file()]

    def paths_in_backup(self, entry: Entry) -> list[Path]:
        path = Path(entry.path)
        folder = self.system_dir / path.parent.relative_to("/")
        pattern = path.name + ".age" if entry.secret else path.name
        names = [f.name for f in sorted(folder.glob(pattern)) if f.is_file()]
        return [path.parent / (name.removesuffix(".age") if entry.secret else name) for name in names]

    def is_in_config(self, saved: Path) -> bool:
        is_secret = saved.name.endswith(".age")
        path = Path("/") / saved.relative_to(self.system_dir)
        if is_secret:
            path = without_age(path)
        for entry in self.config.system_files:
            pattern = Path(entry.path)
            if entry.secret == is_secret and path.parent == pattern.parent and fnmatch(path.name, pattern.name):
                return True
        return False

    def backup_system_files(self) -> None:
        for entry in self.config.system_files:
            paths = self.paths_on_server(entry)
            if not paths:
                print(f"Skipping {entry.path}")
            for path in paths:
                source = server_path(path)
                if not source.is_file():
                    print(f"Skipping {source}")
                elif entry.secret:
                    encrypt(source, self.saved_path(entry, path))
                else:
                    copy(source, self.saved_path(entry, path))
            self.prune_glob(entry, paths)
        self.prune_system_files()

    def prune_glob(self, entry: Entry, on_server: list[Path]) -> None:
        """Drop saved files a glob no longer matches, unless its whole folder is missing."""
        path = Path(entry.path)
        if not has_magic(path.name) or not server_path(path.parent).is_dir():
            return
        for backed_up in self.paths_in_backup(entry):
            if backed_up not in on_server:
                remove(self.saved_path(entry, backed_up))

    def prune_system_files(self) -> None:
        """Drop saved files that were removed from the config, then empty folders."""
        for saved in sorted(self.system_dir.rglob("*"), reverse=True):
            if saved.is_dir():
                if not any(saved.iterdir()):
                    saved.rmdir()
            elif not self.is_in_config(saved):
                remove(saved)

    def restore_system_files(self) -> None:
        for entry in self.config.system_files:
            if not entry.restore:
                print(f"Not restoring {entry.path} (backup only)")
                continue
            paths = self.paths_in_backup(entry)
            if not paths:
                print(f"Skipping {entry.path}")
            for path in paths:
                if entry.secret:
                    decrypt(self.saved_path(entry, path), server_path(path))
                else:
                    copy(self.saved_path(entry, path), server_path(path))

    # Home: top-level folders are mirrored, dotfiles come from HOME_FILES

    def home_folders(self) -> list[Path]:
        ignored = self.config.home_folders_to_ignore | {"__pycache__"}
        return [
            folder
            for folder in sorted(HOME.iterdir())
            if folder.is_dir() and not folder.name.startswith(".") and folder.name not in ignored
        ]

    def backup_home(self) -> None:
        self.home_dir.mkdir(parents=True, exist_ok=True)
        backed_up = set()

        for folder in self.home_folders():
            self.mirror_home_folder(folder, self.home_dir / folder.name)
            backed_up.add(folder.name)

        for relative in self.config.home_files:
            source = HOME / relative
            saved = self.home_dir / relative
            if not source.is_file():
                print(f"Skipping {source}")
                continue
            if is_env_file(source):
                encrypt(source, with_age(saved))
            else:
                copy(source, saved)
            backed_up.add(relative.parts[0])

        for saved in self.home_dir.iterdir():
            if without_age(saved).name not in backed_up:
                remove(saved)

    def mirror_home_folder(self, source: Path, saved: Path) -> None:
        print(f"Mirroring {source} -> {saved}")
        saved.mkdir(exist_ok=True)
        # rsync leaves .age files alone, so drop the ones whose .env is gone here
        for encrypted in saved.rglob("*.env.age"):
            if encrypted.is_file() and not (source / without_age(encrypted).relative_to(saved)).is_file():
                remove(encrypted)
        prefix = f"{source.name}/"
        excludes = []
        for ignored in sorted(self.config.home_folders_to_ignore):
            if ignored.startswith(prefix):
                subpath = ignored.removeprefix(prefix)
                # risk: lets --delete-excluded remove .age files under it too
                excludes += [f"--exclude=/{subpath}", f"--filter=risk /{subpath}/**"]
        uid, gid = self.config.owner
        subprocess.run(
            [
                "rsync", "-a", "--delete", "--delete-excluded", f"--chown={uid}:{gid}",
                *excludes, "--filter", "protect *.age",
                f"{source}/", f"{saved}/",
            ],
            check=True,
        )
        encrypt_env_files(saved)

    def restore_home(self) -> None:
        if not self.home_dir.is_dir():
            print(f"Skipping {self.home_dir}")
            return
        home_owner = HOME.stat()
        for saved in sorted(self.home_dir.iterdir()):
            destination = HOME / saved.name
            if saved.is_symlink():
                continue
            if saved.is_dir():
                print(f"Restoring {saved} -> {destination}")
                destination.mkdir(exist_ok=True)
                subprocess.run(["rsync", "-a", "--no-owner", "--no-group", f"{saved}/", f"{destination}/"], check=True)
                decrypt_env_files(destination)
            elif is_encrypted_env_file(saved):
                destination = without_age(destination)
                decrypt(saved, destination)
            elif saved.is_file():
                copy(saved, destination)
            else:
                continue
            chown_tree(destination, home_owner.st_uid, home_owner.st_gid)


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
