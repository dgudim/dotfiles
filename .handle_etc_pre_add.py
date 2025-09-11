#!/usr/bin/python
import shutil
import os

from common_functions import BLUE, CYAN, GREEN, L_CYAN, L_GREEN, NC, RED, getenv

home = getenv("HOME")
chezmoi_etc_path = os.path.join(getenv("CHEZMOI_SOURCE_DIR"), "dot_config/exact_etc_mirror")

command_dir = getenv("CHEZMOI_COMMAND_DIR")
files_to_add = [os.path.join(command_dir, file_to_add) for file_to_add in getenv("CHEZMOI_ARGS").split(" ")[2:]]


def copyto(src: str, dst: str):
    print(
        f"{GREEN}Copying{NC} {BLUE}{src}{NC} to {CYAN}{dst.replace(home, '~')}{NC}",
        end="",
    )
    dst = os.path.dirname(dst)
    try:
        os.makedirs(dst, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  {L_GREEN}OK{NC}")
    except Exception as e:
        print(f"  {RED}ERR: {e}{NC}")


for file_to_add in files_to_add:
    if file_to_add.startswith("/etc"):
        print(f"Detected file(s) in {L_CYAN}/etc{NC}, adding to chezmoi indirectly")
        break

for source_path in files_to_add:
    if not source_path.startswith("/etc"):
        continue

    if not os.path.exists(source_path):
        print(f"{RED}File '{source_path}' does not exist!!{NC}")
        continue

    st = oct(os.stat(source_path).st_mode & 0o777)[2:]

    if st != "644":
        print(f"{RED}Wrong permissions (got {st}, expected 644)!!{NC}")
        continue

    copyto(source_path, os.path.join(chezmoi_etc_path, source_path.replace("/etc/", "")))
