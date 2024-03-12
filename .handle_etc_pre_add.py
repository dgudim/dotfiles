#!/usr/bin/python
import shutil
import os
import sys

RED = "\033[0;31m"
L_PURPLE = "\033[1;35m"
NC = "\033[0m"
L_GREEN = "\033[1;32m"
YELLOW = "\033[0;33m"
L_CYAN = "\033[1;36m"
L_BLUE = "\033[1;34m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"


def getenv(name: str) -> str:
    val = os.getenv(name)
    if not val:
        print(f"{name} is unset!!")
        sys.exit(1)
    return val


command_dir = getenv("CHEZMOI_COMMAND_DIR")
files_to_add = [os.path.join(command_dir, file_to_add) for file_to_add in getenv("CHEZMOI_ARGS").split(" ")[2:]]

for file_to_add in files_to_add:
    if file_to_add.find("/etc") != -1:
        print(f"Detected file(s) in {L_CYAN}/etc{NC}, adding to chezmoi indirectly")
        break

for source_path in files_to_add:

    if source_path.find("/etc") == -1:
        sys.exit(0)

    if not os.path.exists(source_path):
        print(f"{RED}File does not exist!!{NC}")
        sys.exit(1)

    st = oct(os.stat(source_path).st_mode & 0o777)[2:]

    if st != "644":
        print(f"{RED}Wrong permissions (got {st}, expected 644)!!{NC}")
        sys.exit(0)

    home = getenv("HOME")
    chezmoi_etc_path = os.path.join(
        getenv("CHEZMOI_SOURCE_DIR"), "dot_config/etc_mirror")


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


    copyto(source_path, os.path.join(
        chezmoi_etc_path, source_path.replace("/etc/", "")))
