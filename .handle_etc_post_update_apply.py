#!/usr/bin/python
import os
import sys
import glob

RED = "\033[0;31m"
L_PURPLE = "\033[1;35m"
NC = "\033[0m"
L_GREEN = "\033[1;32m"
YELLOW = "\033[0;33m"
L_CYAN = "\033[1;36m"
L_BLUE = "\033[1;34m"


def getenv(name: str) -> str:
    val = os.getenv(name)
    if not val:
        print(f"{RED}{name} is unset!!{NC}")
        sys.exit(1)
    return val


print(
    f"{L_PURPLE}Running {L_BLUE}etc post update/apply hook{NC},{L_PURPLE} copying etc mirror to {L_CYAN}/etc{NC}..."
)

home = getenv("HOME")
real_etc_path = "/etc"
local_mirror_etc_path = os.path.join(home, ".config/etc_mirror")

for mirror_filepath in glob.iglob(
    local_mirror_etc_path + "**/**", recursive=True, dir_fd=False
):
    if not os.path.isfile(mirror_filepath):
        continue
    rel_path = mirror_filepath.replace(f"{local_mirror_etc_path}/", "")
    target_etc_file = os.path.join("/etc", rel_path)

    os.system(f"sudo mkdir -pv {os.path.dirname(target_etc_file)}")
    os.system(
        f'sudo install -v --owner=root --group=root --mode=0644 "{mirror_filepath}" "{target_etc_file}" '
        f'| sed /removed/s//`printf "{YELLOW}removed{NC}"`/'
        f'| sed /\\-\\>/s//`printf "{L_GREEN}\\-\\>{NC}"`/'
        ""
    )

print(f"{L_GREEN}Finished copying to etc{NC}")
