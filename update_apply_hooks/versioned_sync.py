#!/usr/bin/venv python3

from enum import Enum
from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil

RED = "\033[0;31m"
PURPLE = "\033[0;35m"
L_PURPLE = "\033[1;35m"
NC = "\033[0m"
L_GREEN = "\033[1;32m"
YELLOW = "\033[0;33m"
L_YELLOW = "\033[1;33m"
L_CYAN = "\033[1;36m"
L_BLUE = "\033[1;34m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
GRAY = "\033[38;5;240m"
LIGHT_GRAY = "\033[38;5;242m"
LIGHTER_GRAY = "\033[38;5;246m"

home = os.environ["HOME"] or ""

SYNC_DIR_POSTFIX = "_sync"


@dataclass
class ProgramConfig:
    name: str
    settings_dir_prefix: str
    config_location: Path
    data_location: Path
    config_files_to_sync: set[str | re.Pattern]
    data_files_to_sync: set[str | re.Pattern]


configs: list[ProgramConfig] = [
    ProgramConfig(
        name="Intellij idea",
        config_location=Path(home, ".config/JetBrains"),
        settings_dir_prefix="IntelliJIdea",
        data_location=Path(home, ".local/share/JetBrains/"),
        config_files_to_sync={
            "options/other.xml",
            "options/advancedSettings.xml",
            "options/colors.scheme.xml",
            "options/console-font.xml",
            "options/editor.xml",
            "options/editor-font.xml",
            re.compile("options/linux/.*"),
            re.compile("keymaps/.*"),
            re.compile("colors/.*"),
            re.compile("codestyles/.*"),
        },
        data_files_to_sync={re.compile("classic-ui/.*"), re.compile("Gruvbox_Theme.*")},
    ),
    ProgramConfig(
        name="Rider",
        config_location=Path(home, ".config/JetBrains"),
        settings_dir_prefix="Rider",
        data_location=Path(home, ".local/share/JetBrains/"),
        config_files_to_sync={
            "options/other.xml",
            "options/advancedSettings.xml",
            "options/colors.scheme.xml",
            "options/console-font.xml",
            "options/editor.xml",
            "options/editor-font.xml",
            re.compile("options/linux/.*"),
            re.compile("keymaps/.*"),
            re.compile("colors/.*"),
            re.compile("codestyles/.*"),
        },
        data_files_to_sync={re.compile("classic-ui/.*"), re.compile("Gruvbox_Theme.*")},
    ),
]


@dataclass
class VersionedDirectory:
    is_latest: bool
    version: float
    path_: Path


def get_all_versioned_dirs(base_path: Path, dir_prefix: str):
    print(
        f"{LIGHTER_GRAY}  >> Getting versioned dirs from {CYAN}{base_path}{LIGHTER_GRAY} with prefix: {L_GREEN}{dir_prefix}{NC}"
    )

    dirs: dict[float, VersionedDirectory] = {}
    max_version = 0
    for dir_ in base_path.glob(f"{dir_prefix}*"):
        if str(dir_).endswith(SYNC_DIR_POSTFIX):
            continue
        version = float(dir_.name.replace(dir_prefix, ""))
        print(f"{GRAY}    -> Found dir: {dir_}, {LIGHT_GRAY}version: {L_YELLOW}{version}{NC}")

        versioned_dir = VersionedDirectory(is_latest=False, version=version, path_=dir_)

        dirs[version] = versioned_dir

        if version > max_version:
            max_version = version

    if max_version > 0:
        dirs[max_version].is_latest = True

    return list(dirs.values())


class CopyDirection(Enum):
    TO_SYNC_DIR_FROM_LATEST_PROGRAM_DIR = 0
    TO_LATEST_PROGRAM_DIR_FROM_SYNC_DIR = 1


def process_versioned_dirs_cleanup_and_copy_sync_files(
    base_path: Path, dir_prefix: str, log_name: str, files_to_sync_patterns: list[str], copy_: CopyDirection
):
    versioned_dirs = get_all_versioned_dirs(base_path, dir_prefix)

    sync_dir = Path(base_path, f"{dir_prefix}_sync")
    print(f"{LIGHTER_GRAY}  Creating {log_name} sync directory: {CYAN}{sync_dir}{NC}")
    sync_dir.mkdir(exist_ok=True)

    if len(versioned_dirs) == 0:
        print(f"{GRAY}  Nothing found")
        return

    latest_program_dir: Path

    for versioned_dir in versioned_dirs:
        if not versioned_dir.is_latest:
            print(f"{RED}  DELETING{LIGHTER_GRAY} old version directory: {L_CYAN}{versioned_dir.path_}{NC}")
            shutil.rmtree(versioned_dir.path_)
        else:
            latest_program_dir = versioned_dir.path_

    sync_files_source = latest_program_dir if copy_ == CopyDirection.TO_SYNC_DIR_FROM_LATEST_PROGRAM_DIR else sync_dir
    sync_files_target = sync_dir if copy_ == CopyDirection.TO_SYNC_DIR_FROM_LATEST_PROGRAM_DIR else latest_program_dir

    print(f"{LIGHTER_GRAY}  Copying synced files")

    source_files = [f for f in sync_files_source.rglob("*") if f.is_file()]

    matched_patterns = set()
    copied_files = 0

    for file_to_sync_pattern in files_to_sync_patterns:
        for source_file in source_files:
            source_file_rel = str(source_file).replace(f"{str(sync_files_source)}/", "")
            if (
                isinstance(file_to_sync_pattern, re.Pattern) and file_to_sync_pattern.match(source_file_rel)
            ) or file_to_sync_pattern == source_file_rel:
                print(f"{LIGHT_GRAY}    {source_file_rel} {YELLOW}matches {LIGHT_GRAY}{file_to_sync_pattern}", end="")
                matched_patterns.add(file_to_sync_pattern)
                copied_files += 1

                target_file = Path(sync_files_target, source_file_rel)
                os.makedirs(os.path.dirname(target_file), exist_ok=True)
                target_file.write_bytes(source_file.read_bytes())

                print(f"{GREEN} copied {GRAY}{str(source_file).removeprefix(f"{home}/")} to {str(target_file).removeprefix(f"{home}/")})")

    print(
        f"{NC}Matched {PURPLE}{len(matched_patterns)}{NC}/{PURPLE}{len(files_to_sync_patterns)} {NC}patterns, copied {L_YELLOW}{copied_files}{NC} files"
    )


def pre():
    for config in configs:
        print(f"{LIGHTER_GRAY}==== Processing: {L_CYAN}{config.name}{NC}")

        process_versioned_dirs_cleanup_and_copy_sync_files(
            config.data_location,
            config.settings_dir_prefix,
            "data",
            config.data_files_to_sync,
            CopyDirection.TO_SYNC_DIR_FROM_LATEST_PROGRAM_DIR,
        )
        process_versioned_dirs_cleanup_and_copy_sync_files(
            config.config_location,
            config.settings_dir_prefix,
            "config",
            config.config_files_to_sync,
            CopyDirection.TO_SYNC_DIR_FROM_LATEST_PROGRAM_DIR,
        )

def post():
    for config in configs:
        print(f"{LIGHTER_GRAY}==== Processing: {L_CYAN}{config.name}{NC}")

        process_versioned_dirs_cleanup_and_copy_sync_files(
            config.data_location,
            config.settings_dir_prefix,
            "data",
            config.data_files_to_sync,
            CopyDirection.TO_LATEST_PROGRAM_DIR_FROM_SYNC_DIR,
        )
        process_versioned_dirs_cleanup_and_copy_sync_files(
            config.config_location,
            config.settings_dir_prefix,
            "config",
            config.config_files_to_sync,
            CopyDirection.TO_LATEST_PROGRAM_DIR_FROM_SYNC_DIR,
        )
