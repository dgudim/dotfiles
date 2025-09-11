#!/usr/bin/venv python3

import os
from pathlib import Path
import sys


def getenv(name: str) -> str:
    val = os.getenv(name)
    if not val:
        print(f"{RED}{name} is unset!!{NC}")
        sys.exit(1)
    return val


HOME = Path(getenv("HOME"))
REAL_ETC_PATH = Path("/etc")
CHEZMOI_ETC_PATH = Path(getenv("CHEZMOI_SOURCE_DIR"), "dot_config/exact_etc_mirror")
LOCAL_MIRROR_ETC_PATH = Path(HOME, ".config/etc_mirror")

RED = "\033[0;31m"
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


def pre():
    print(f"{L_PURPLE} mirroring {L_CYAN}/etc{L_PURPLE} state{NC}...")

    copied_entries = 0
    skipped_entries = 0

    for filepath in CHEZMOI_ETC_PATH.rglob("*"):
        if not os.path.isfile(filepath):
            continue
        relative_path = str(filepath).removeprefix(f"{CHEZMOI_ETC_PATH}/").removesuffix(".tmpl")

        etc_file = Path(REAL_ETC_PATH, relative_path)
        local_mirror_file = Path(LOCAL_MIRROR_ETC_PATH, relative_path)

        try:
            os.makedirs(os.path.dirname(local_mirror_file), exist_ok=True)
            local_mirror_file.write_bytes(etc_file.read_bytes())
            copied_entries += 1
        except FileNotFoundError:
            skipped_entries += 1

    print(
        f"{L_GREEN}Finished mirroring etc state{NC}, {L_YELLOW}{copied_entries + skipped_entries} files {L_GREEN}processed{NC} ({GREEN}{copied_entries} copied{NC}, {YELLOW}{skipped_entries} skipped{NC})\n"
    )


def post():
    print(f"{L_PURPLE} copying etc mirror to {L_CYAN}/etc{NC}...")

    entries = 0

    for mirror_filepath in LOCAL_MIRROR_ETC_PATH.rglob("*"):
        if not os.path.isfile(mirror_filepath):
            continue

        rel_path = str(mirror_filepath).removeprefix(f"{LOCAL_MIRROR_ETC_PATH}/")
        target_etc_file = Path(REAL_ETC_PATH, rel_path)

        try:
            os.system(f"sudo mkdir -p {os.path.dirname(target_etc_file)}")
            mode = "0644"
            if target_etc_file.suffix == ".sh":
                print(f"Using mode: 755 for {target_etc_file}")
                mode = "0755"
            os.system(f'sudo install --owner=root --group=root --mode={mode} "{mirror_filepath}" "{target_etc_file}"')
            entries = entries + 1
        except Exception as e:
            print(
                f"{GREEN}Installing{NC} {BLUE}{str(mirror_filepath).replace(str(HOME), '~')}{NC} to {CYAN}{target_etc_file}{NC}",
                end="",
            )
            print(f"  {RED}ERR: {e}{NC}")

    print(f"{L_GREEN}Finished copying to etc, {L_YELLOW}{entries} files {L_GREEN}processed{NC}")
