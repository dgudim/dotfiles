#!/usr/bin/venv python3

from enum import Enum
from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import sys


def getenv(name: str) -> str:
    val = os.getenv(name)
    if not val:
        print(f"{RED}{name} is unset!!{NC}")
        sys.exit(1)
    return val


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

HOME = Path(getenv("HOME"))

SYNC_DIR_POSTFIX = "_sync"


@dataclass
class ProgramConfig:
    name: str
    settings_dir_prefix: str
    config_location: Path | None
    data_location: Path | None
    config_files_to_sync: set[str | re.Pattern]
    data_files_to_sync: set[str | re.Pattern]


configs: list[ProgramConfig] = [
    ProgramConfig(
        name="Intellij idea",
        config_location=Path(HOME, ".config/JetBrains"),
        settings_dir_prefix="IntelliJIdea",
        data_location=Path(HOME, ".local/share/JetBrains/"),
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
        config_location=Path(HOME, ".config/JetBrains"),
        settings_dir_prefix="Rider",
        data_location=Path(HOME, ".local/share/JetBrains/"),
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
        name="Blender",
        config_location=Path(HOME, ".config/blender"),
        settings_dir_prefix="",
        data_location=None,
        config_files_to_sync={
            "config/userpref.blend",
            re.compile("extensions/blender_org/.*"),
            re.compile("scripts/.*"),
        },
        data_files_to_sync=set(),
    ),
]

ignore_patterns = ["__pycache__"]


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
    max_version: float = 0
    for dir_ in base_path.glob(f"{dir_prefix}*"):
        if str(dir_).endswith(SYNC_DIR_POSTFIX):
            continue
        version = float(dir_.name.replace(dir_prefix, ""))
        print(f"{GRAY}    -> Found dir: {dir_}, {LIGHT_GRAY}version: {L_YELLOW}{version}{NC}")

        dirs[version] = VersionedDirectory(is_latest=False, version=version, path_=dir_)

        max_version = max(max_version, version)

    if max_version > 0:
        dirs[max_version].is_latest = True

    return list(dirs.values())


class CopyDirection(Enum):
    TO_SYNC_DIR_FROM_LATEST_PROGRAM_DIR = 0
    TO_LATEST_PROGRAM_DIR_FROM_SYNC_DIR = 1


def process_versioned_dirs_cleanup_and_copy_sync_files(
    base_path: Path, dir_prefix: str, log_name: str, files_to_sync_patterns: set[str | re.Pattern], copy_: CopyDirection
):
    versioned_dirs = get_all_versioned_dirs(base_path, dir_prefix)

    sync_dir = Path(base_path, f"{dir_prefix}_sync")
    print(f"{LIGHTER_GRAY}  Creating {log_name} sync directory: {CYAN}{sync_dir}{NC}")
    sync_dir.mkdir(exist_ok=True)

    if len(versioned_dirs) == 0:
        print(f"{GRAY}  Nothing found")
        return

    latest_program_dir: Path | None = None

    for versioned_dir in versioned_dirs:
        if not versioned_dir.is_latest:
            print(f"{RED}  DELETING{LIGHTER_GRAY} old version directory: {L_CYAN}{versioned_dir.path_}{NC}")
            shutil.rmtree(versioned_dir.path_)
        else:
            latest_program_dir = versioned_dir.path_

    assert (
        latest_program_dir is not None
    )  # Can't be None, we checked for versioned_dirs size higher and there MUST be 1 dir marked as latest

    sync_files_source = latest_program_dir if copy_ == CopyDirection.TO_SYNC_DIR_FROM_LATEST_PROGRAM_DIR else sync_dir
    sync_files_target = sync_dir if copy_ == CopyDirection.TO_SYNC_DIR_FROM_LATEST_PROGRAM_DIR else latest_program_dir

    print(f"{LIGHTER_GRAY}  Copying synced files")

    source_files = [
        f
        for f in sync_files_source.rglob("*")
        if f.is_file() and not any((ignore_pattern in str(f)) for ignore_pattern in ignore_patterns)
    ]

    matched_patterns = set()
    copied_files = 0

    for file_to_sync_pattern in files_to_sync_patterns:
        for source_file in source_files:
            source_file_rel = str(source_file).removeprefix(f"{str(sync_files_source)}/")
            if (
                isinstance(file_to_sync_pattern, re.Pattern) and file_to_sync_pattern.match(source_file_rel)
            ) or file_to_sync_pattern == source_file_rel:
                print(f"{LIGHT_GRAY}    {source_file_rel} {YELLOW}matches {LIGHT_GRAY}{file_to_sync_pattern}", end="")
                matched_patterns.add(file_to_sync_pattern)
                copied_files += 1

                target_file = Path(sync_files_target, source_file_rel)
                os.makedirs(os.path.dirname(target_file), exist_ok=True)
                target_file.write_bytes(source_file.read_bytes())

                print(
                    f"{GREEN} copied {GRAY}{str(source_file).replace(str(HOME), '~')} to {str(target_file).replace(str(HOME), '~')})"
                )

    print(
        f"{NC}Matched {PURPLE}{len(matched_patterns)}{NC}/{PURPLE}{len(files_to_sync_patterns)} {NC}patterns, copied {L_YELLOW}{copied_files}{NC} files"
    )

    unmatched_patterns = files_to_sync_patterns - matched_patterns

    if len(unmatched_patterns) > 0:
        print(f"{YELLOW}Unmatched patterns: {L_YELLOW}{unmatched_patterns}{NC}")


def pre():
    print(f"{L_PURPLE} Copying versioned {L_CYAN}program settings {L_PURPLE}to sync dir...{NC}")

    for config in configs:
        print(f"{LIGHTER_GRAY}==== Processing: {L_CYAN}{config.name}{NC}")

        if config.data_location is not None:
            process_versioned_dirs_cleanup_and_copy_sync_files(
                config.data_location,
                config.settings_dir_prefix,
                "data",
                config.data_files_to_sync,
                CopyDirection.TO_SYNC_DIR_FROM_LATEST_PROGRAM_DIR,
            )

        if config.config_location is not None:
            process_versioned_dirs_cleanup_and_copy_sync_files(
                config.config_location,
                config.settings_dir_prefix,
                "config",
                config.config_files_to_sync,
                CopyDirection.TO_SYNC_DIR_FROM_LATEST_PROGRAM_DIR,
            )


def post():
    print(f"{L_PURPLE} Applying versioned {L_CYAN}program settings {L_PURPLE}from sync dir...{NC}")

    for config in configs:
        print(f"{LIGHTER_GRAY}==== Processing: {L_CYAN}{config.name}{NC}")

        if config.data_location is not None:
            process_versioned_dirs_cleanup_and_copy_sync_files(
                config.data_location,
                config.settings_dir_prefix,
                "data",
                config.data_files_to_sync,
                CopyDirection.TO_LATEST_PROGRAM_DIR_FROM_SYNC_DIR,
            )

        if config.config_location is not None:
            process_versioned_dirs_cleanup_and_copy_sync_files(
                config.config_location,
                config.settings_dir_prefix,
                "config",
                config.config_files_to_sync,
                CopyDirection.TO_LATEST_PROGRAM_DIR_FROM_SYNC_DIR,
            )
