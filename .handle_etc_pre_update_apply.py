#!/usr/bin/python
import shutil
import os
import sys
import glob
import importlib.util
from pathlib import Path

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


def getenv(name: str) -> str:
    val = os.getenv(name)
    if not val:
        print(f"{RED}{name} is unset!!{NC}")
        sys.exit(1)
    return val


print(
    f"{L_PURPLE}Running {L_BLUE}etc pre update/apply hook{NC},{L_PURPLE} mirroring {L_CYAN}/etc{L_PURPLE} state{NC}..."
)

home = getenv("HOME")
real_etc_path = "/etc"
chezmoi_etc_path = os.path.join(getenv("CHEZMOI_SOURCE_DIR"), "dot_config/etc_mirror")
local_mirror_etc_path = os.path.join(home, ".config/etc_mirror")


def copyto(src: str, dst: str):
    dst = os.path.dirname(dst)
    try:
        os.makedirs(dst, exist_ok=True)
        os.system(f'cp -pf "{src}" "{dst}"')
        # print(f"  {L_GREEN}OK{NC}")
    except Exception as e:
        print(
            f"{GREEN}Copying{NC} {BLUE}{src}{NC} to {CYAN}{dst.replace(home, '~')}{NC}",
            end="",
        )
        print(f"  {RED}ERR: {e}{NC}")


entries = 0

shutil.rmtree(local_mirror_etc_path)
for filepath in glob.iglob(chezmoi_etc_path + "**/**", recursive=True, dir_fd=False):
    if not os.path.isfile(filepath):
        continue
    relative_path = filepath.replace(f"{chezmoi_etc_path}/", "").replace(".tmpl", "")
    etc_file = os.path.join(real_etc_path, relative_path)
    local_mirror_file = os.path.join(local_mirror_etc_path, relative_path)
    copyto(etc_file, local_mirror_file)
    entries = entries + 1

print(
    f"{L_GREEN}Finished mirroring etc state{NC}, {L_YELLOW}{entries} files {L_GREEN}processed{NC}\n"
)

print(f"{L_PURPLE}Running {L_BLUE}etc pre update/apply hooks{NC}")

chezmoi_home = getenv("CHEZMOI_SOURCE_DIR")
hooks_path = os.path.join(chezmoi_home, "update_apply_hooks")
for hook_filepath in glob.iglob(hooks_path + "**/**", recursive=False, dir_fd=False):
    if not os.path.isfile(hook_filepath):
        continue

    hook_filepath_path = Path(hook_filepath)

    module = importlib.import_module(
        f"update_apply_hooks.{hook_filepath_path.stem}",
        package=str(hook_filepath_path.absolute()),
    )

    module.pre()
