#!/usr/bin/env python3
"""Back up a server's configs into this repo, or restore them onto a fresh install.

Usage: backup.py [backup|restore] [--host NAME]

Every server has a folder next to this script (microchelik/, the-rock/) with a
backup_config.py that lists what to save. Files land in <host>/system-configs/
(by their path on the server) and <host>/home/ (the home directory). .env files
and entries marked secret() are stored encrypted with age.

The host is the server's hostname, read from /etc/hostname (from
$BACKUP_ETC/hostname when the job runs in a container), or --host to override.

Environment overrides:
  BACKUP_ROOT       folder holding the host folders (default: next to this script)
  BACKUP_ETC        where the server's /etc is (default /etc; /host-etc in a container)
  BACKUP_HOST_ROOT  where the rest of the server's filesystem is (default /)
Both are used for restoring too.
"""

from __future__ import annotations

import argparse
import os
import runpy
import shutil
import socket
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from fnmatch import fnmatch
from glob import has_magic
from pathlib import Path

USER_DIR = Path(os.environ.get("BACKUP_USER_DIR", "/home/kloud"))
DEFAULT_ROOT = USER_DIR / "dotfiles/Documents/usefull_files/exact_scripts/server"
ETC_DIR = Path(os.environ.get("BACKUP_ETC", "/etc"))
HOST_ROOT = Path(os.environ.get("BACKUP_HOST_ROOT", "/"))
AGE_RECIPIENT = USER_DIR / ".ssh" / "id_ed25519.pub"
AGE_IDENTITY = USER_DIR / ".ssh" / "id_ed25519"
IS_ROOT = os.geteuid() == 0


@dataclass(frozen=True)
class Entry:
    """A file on the server. A glob is allowed in the last path component only."""

    path: str
    secret: bool = False  # stored as <name>.age
    restore: bool = True  # False: kept for reference, applied by hand (setup.sh)


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
    entries = []
    for item in values.get("SYSTEM_FILES", []):
        entry = item if isinstance(item, Entry) else Entry(str(item))
        path = Path(entry.path)
        if not path.is_absolute():
            raise SystemExit(f"{config_file}: {entry.path} is not an absolute path")
        if has_magic(str(path.parent)):
            raise SystemExit(f"{config_file}: {entry.path}: only the last component may be a glob")
        entries.append(entry)
    return Config(
        owner=tuple(values.get("OWNER", (1000, 100))),
        home_folders_to_ignore=set(values.get("HOME_FOLDERS_TO_IGNORE", [])),
        home_files=[Path(p) for p in values.get("HOME_FILES", [])],
        system_files=entries,
    )


def is_env_file(path: Path) -> bool:
    return path.name == ".env" or path.name.endswith(".env")


def without_age(path: Path) -> Path:
    return path.with_name(path.name.removesuffix(".age"))


def encrypt(plain: Path, encrypted: Path, data: bytes | None = None) -> None:
    """Encrypt plain (or data read from it) to encrypted. An unchanged file is left
    alone, since age output differs every time and git would see a change."""
    if data is None:
        data = plain.read_bytes()
    if encrypted.is_file():
        result = subprocess.run(["age", "-d", "-i", str(AGE_IDENTITY), str(encrypted)], capture_output=True)
        if result.returncode == 0 and result.stdout == data:
            print(f"Unchanged {encrypted}")
            return
    print(f"Encrypting {plain} -> {encrypted}")
    subprocess.run(["age", "-R", str(AGE_RECIPIENT), "-o", str(encrypted)], input=data, check=True)


def decrypt(encrypted: Path, plain: Path) -> None:
    print(f"Decrypting {encrypted} -> {plain}")
    subprocess.run(["age", "-d", "-i", str(AGE_IDENTITY), "-o", str(plain), str(encrypted)], check=True)


# Server files are read directly when possible and through sudo otherwise
# (root-only files, folders we can't enter). Running as root skips sudo.

def as_root(args: list[str]) -> list[str]:
    return args if IS_ROOT else ["sudo", *args]


def sudo_test(flag: str, path: Path) -> bool:
    return subprocess.run(as_root(["test", flag, str(path)])).returncode == 0


def host_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except PermissionError:
        return sudo_test("-f", path)


def host_is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except PermissionError:
        return sudo_test("-d", path)


def host_glob(folder: Path, pattern: str) -> list[Path]:
    if not host_is_dir(folder):
        return []
    if os.access(folder, os.R_OK | os.X_OK):
        return sorted(m for m in folder.glob(pattern) if host_is_file(m))
    found = subprocess.run(
        as_root(["find", str(folder), "-mindepth", "1", "-maxdepth", "1", "-type", "f", "-name", pattern, "-print0"]),
        capture_output=True,
        check=True,
    ).stdout
    return sorted(Path(os.fsdecode(name)) for name in found.split(b"\0") if name)


def host_read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except PermissionError:
        return subprocess.run(as_root(["cat", str(path)]), capture_output=True, check=True).stdout


def host_mode(path: Path) -> int:
    try:
        return path.stat().st_mode & 0o7777
    except PermissionError:
        return int(subprocess.run(as_root(["stat", "-c", "%a", str(path)]), capture_output=True, check=True).stdout, 8)


def copy_from_host(source: Path, destination: Path) -> None:
    """Like shutil.copy2, falling back to sudo for files we can't read."""
    try:
        shutil.copy2(source, destination)
    except PermissionError:
        destination.write_bytes(host_read(source))
        destination.chmod(host_mode(source))


def host_path(path: Path) -> Path:
    """Where an absolute server path can be read from (handles the container mounts)."""
    relative = path.relative_to("/")
    if relative.parts and relative.parts[0] == "etc":
        return ETC_DIR.joinpath(*relative.parts[1:])
    return HOST_ROOT / relative


def install_file(source: Path, destination: Path, preserve_mode: bool = True) -> None:
    """Copy a file into place; outside the home directory with sudo and owned by root."""
    print(f"Restoring {source} -> {destination}")
    if destination.is_relative_to(USER_DIR):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        return
    subprocess.run(["sudo", "mkdir", "-p", str(destination.parent)], check=True)
    preserve = ["--preserve=mode,timestamps"] if preserve_mode else []
    subprocess.run(["sudo", "cp", *preserve, str(source), str(destination)], check=True)


class Backup:
    def __init__(self, host_dir: Path, config: Config):
        self.host_dir = host_dir
        self.config = config
        self.system_dir = host_dir / "system-configs"
        self.home_dir = host_dir / "home"

    # ---- system files -------------------------------------------------------

    def files_on_host(self, entry: Entry) -> list[tuple[Path, Path]]:
        """(source, path relative to /) for every file the entry matches on the server."""
        path = Path(entry.path)
        if not has_magic(path.name):
            return [(host_path(path), path.relative_to("/"))]
        relative_dir = path.parent.relative_to("/")
        return [(m, relative_dir / m.name) for m in host_glob(host_path(path.parent), path.name)]

    def files_in_backup(self, entry: Entry) -> list[tuple[Path, Path]]:
        """(saved file, path relative to /) for every saved file the entry matches."""
        path = Path(entry.path)
        saved_dir = self.system_dir / path.parent.relative_to("/")
        if not saved_dir.is_dir():
            return []
        pattern = path.name + (".age" if entry.secret else "")
        relative_dir = path.parent.relative_to("/")
        return [
            (saved, relative_dir / without_age(saved).name if entry.secret else relative_dir / saved.name)
            for saved in sorted(saved_dir.glob(pattern))
            if saved.is_file()
        ]

    def entry_for(self, saved: Path) -> Entry | None:
        relative = saved.relative_to(self.system_dir)
        is_age = saved.name.endswith(".age")
        server_path = Path("/") / (without_age(relative) if is_age else relative)
        for entry in self.config.system_files:
            path = Path(entry.path)
            if entry.secret == is_age and server_path.parent == path.parent and fnmatch(server_path.name, path.name):
                return entry
        return None

    def backup_system(self) -> None:
        for entry in self.config.system_files:
            matches = self.files_on_host(entry)
            if not matches:
                print(f"Skipping {entry.path}")
            for source, relative in matches:
                if not host_is_file(source):
                    print(f"Skipping {source}")
                    continue
                destination = self.system_dir / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                if entry.secret:
                    encrypt(source, destination.with_name(destination.name + ".age"), host_read(source))
                else:
                    print(f"Copying {source}")
                    copy_from_host(source, destination)
            self.prune_glob(entry, {relative for _, relative in matches})
        self.prune_system()

    def prune_glob(self, entry: Entry, present: set[Path]) -> None:
        """For a glob whose folder exists on the server, drop saved files it no longer matches."""
        path = Path(entry.path)
        if not has_magic(path.name) or not host_is_dir(host_path(path.parent)):
            return
        for saved, relative in self.files_in_backup(entry):
            if relative not in present:
                print(f"Removing {saved}")
                saved.unlink()

    def prune_system(self) -> None:
        """Drop saved files whose entry was removed from the config (or changed secret/plain)."""
        if not self.system_dir.is_dir():
            return
        for saved in sorted(self.system_dir.rglob("*"), reverse=True):
            if saved.is_dir():
                if not any(saved.iterdir()):
                    saved.rmdir()
                continue
            if self.entry_for(saved) is None:
                print(f"Removing {saved}")
                saved.unlink()

    def restore_system(self) -> None:
        for entry in self.config.system_files:
            if not entry.restore:
                print(f"Not restoring {entry.path} (backup only)")
                continue
            matches = self.files_in_backup(entry)
            if not matches:
                print(f"Skipping {entry.path}")
            for saved, relative in matches:
                destination = host_path(Path("/") / relative)
                if not entry.secret:
                    install_file(saved, destination)
                    continue
                with tempfile.TemporaryDirectory() as tmp:
                    plain = Path(tmp) / destination.name
                    decrypt(saved, plain)
                    plain.chmod(0o644)
                    # An existing file keeps its mode, a new one gets 644
                    install_file(plain, destination, preserve_mode=False)

    # ---- home directory -----------------------------------------------------

    def remove_stale_age_files(self, source: Path, destination: Path) -> None:
        if not destination.exists():
            return
        for encrypted in destination.rglob("*.age"):
            if not encrypted.is_file() or not is_env_file(without_age(encrypted)):
                continue
            if (source / without_age(encrypted).relative_to(destination)).is_file():
                continue
            print(f"Removing {encrypted}")
            encrypted.unlink()

    def encrypt_copied_env_files(self, destination: Path) -> None:
        for env_file in destination.rglob("*"):
            if not env_file.is_file() or not is_env_file(env_file):
                continue
            encrypt(env_file, env_file.with_name(env_file.name + ".age"))
            env_file.unlink()

    def backup_home(self) -> None:
        self.home_dir.mkdir(exist_ok=True)
        mirrored = set()
        uid, gid = self.config.owner
        for entry in USER_DIR.iterdir():
            if (
                not entry.is_dir()
                or entry.name.startswith(".")
                or entry.name == "__pycache__"
                or entry.name in self.config.home_folders_to_ignore
            ):
                continue
            destination = self.home_dir / entry.name
            mirrored.add(entry.name)
            destination.mkdir(exist_ok=True)
            print(f"Mirroring {entry} -> {destination}")
            self.remove_stale_age_files(entry, destination)
            rsync = ["rsync", "-a", "--delete", "--filter", "protect *.age", f"{entry}/", f"{destination}/"]
            if IS_ROOT:
                subprocess.run([*rsync[:2], f"--chown={uid}:{gid}", *rsync[2:]], check=True)
            elif subprocess.run(rsync, stderr=subprocess.DEVNULL).returncode == 23:
                # Some files are root-only (container data): copy again with sudo, owned by us
                print(f"Some files in {entry} need root, copying with sudo")
                chown = f"--chown={os.getuid()}:{os.getgid()}"
                subprocess.run(["sudo", *rsync[:2], chown, *rsync[2:]], check=True)
            self.encrypt_copied_env_files(destination)

        for relative in self.config.home_files:
            source = USER_DIR / relative
            if not host_is_file(source):
                print(f"Skipping {source}")
                continue
            destination = self.home_dir / relative
            mirrored.add(relative.parts[0])
            print(f"Copying {source} -> {destination}")
            destination.parent.mkdir(parents=True, exist_ok=True)
            copy_from_host(source, destination)
            if is_env_file(destination):
                self.encrypt_copied_env_files(destination.parent)

        for existing in self.home_dir.iterdir():
            if existing.name in mirrored:
                continue
            print(f"Removing {existing}")
            if existing.is_dir() and not existing.is_symlink():
                shutil.rmtree(existing)
            else:
                existing.unlink()

    def decrypt_env_files(self, root: Path) -> None:
        for encrypted in root.rglob("*.age"):
            plain = without_age(encrypted)
            if encrypted.is_file() and is_env_file(plain):
                decrypt(encrypted, plain)
                encrypted.unlink()

    def restore_home(self) -> None:
        if not self.home_dir.is_dir():
            print(f"Skipping {self.home_dir}")
            return
        for entry in self.home_dir.iterdir():
            if entry.is_symlink():
                continue
            destination = USER_DIR / entry.name
            if entry.is_file():
                if entry.name.endswith(".age") and is_env_file(without_age(entry)):
                    destination = without_age(destination)
                    decrypt(entry, destination)
                else:
                    install_file(entry, destination)
                self.give_to_home_owner(destination)
                continue
            if not entry.is_dir():
                continue
            destination.mkdir(exist_ok=True)
            print(f"Restoring {entry} -> {destination}")
            subprocess.run(["rsync", "-a", "--no-owner", "--no-group", f"{entry}/", f"{destination}/"], check=True)
            self.decrypt_env_files(destination)
            self.give_to_home_owner(destination)

    def give_to_home_owner(self, root: Path) -> None:
        """When restoring with sudo, hand restored home files to the home folder's owner."""
        if not IS_ROOT or not root.exists():
            return
        owner = USER_DIR.stat()
        for path in [root, *root.rglob("*")]:
            os.chown(path, owner.st_uid, owner.st_gid, follow_symlinks=False)

    # ---- entry points -------------------------------------------------------

    def give_to_user(self, root: Path) -> None:
        if not IS_ROOT or not root.exists():
            return
        uid, gid = self.config.owner
        for path in [root, *root.rglob("*")]:
            os.chown(path, uid, gid, follow_symlinks=False)

    def backup(self) -> None:
        self.backup_system()
        self.give_to_user(self.system_dir)
        self.backup_home()
        self.give_to_user(self.home_dir)

    def restore(self) -> None:
        self.restore_system()
        self.restore_home()


def detect_host(explicit: str | None) -> str:
    if explicit:
        return explicit
    hostname_file = ETC_DIR / "hostname"
    if hostname_file.is_file():
        name = hostname_file.read_text().strip().split(".")[0]
        if name:
            return name
    return socket.gethostname().split(".")[0]


def find_host_dir(host: str) -> Path:
    candidates = [Path(os.environ["BACKUP_ROOT"])] if os.environ.get("BACKUP_ROOT") else []
    candidates += [Path(__file__).resolve().parent, DEFAULT_ROOT]
    for root in candidates:
        if (root / host / "backup_config.py").is_file():
            return root / host
    searched = ", ".join(str(c / host / "backup_config.py") for c in candidates)
    raise SystemExit(f"No backup config for host {host!r} (looked for {searched}). Use --host.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Back up or restore a server's configs.")
    parser.add_argument("action", nargs="?", default="backup", choices=["backup", "restore"])
    parser.add_argument("--host", help="host folder to use (default: this machine's hostname)")
    args = parser.parse_args()

    host = detect_host(args.host)
    host_dir = find_host_dir(host)
    print(f"Host {host}: {host_dir}")
    backup = Backup(host_dir, load_config(host_dir / "backup_config.py"))
    backup.backup() if args.action == "backup" else backup.restore()


if __name__ == "__main__":
    main()
