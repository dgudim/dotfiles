#!/usr/bin/python
import os
import sys
import glob

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
    f"{L_PURPLE}Running {L_BLUE}etc post update/apply hook{NC},{L_PURPLE} copying etc mirror to {L_CYAN}/etc{NC}..."
)

home = getenv("HOME")
real_etc_path = "/etc"
local_mirror_etc_path = os.path.join(home, ".config/etc_mirror")

entries = 0

for mirror_filepath in glob.iglob(
    local_mirror_etc_path + "**/**", recursive=True, dir_fd=False
):
    if not os.path.isfile(mirror_filepath):
        continue
    rel_path = mirror_filepath.replace(f"{local_mirror_etc_path}/", "")
    target_etc_file = os.path.join("/etc", rel_path)

    try:
        os.system(f"sudo mkdir -p {os.path.dirname(target_etc_file)}")
        os.system(
            f'sudo install --owner=root --group=root --mode=0644 "{mirror_filepath}" "{target_etc_file}"'
        )
        entries = entries + 1
    except Exception as e:
        print(
            f"{GREEN}Installing{NC} {BLUE}{mirror_filepath.replace(home, '~')}{NC} to {CYAN}{target_etc_file}{NC}",
            end="",
        )
        print(f"  {RED}ERR: {e}{NC}")

print(
    f"{L_GREEN}Finished copying to etc, {L_YELLOW}{entries} files {L_GREEN}processed{NC}"
)


print(
    f"{L_PURPLE}Running {L_BLUE}etc post update/apply hook{NC},{L_PURPLE} loading {L_CYAN}dconf{L_PURPLE} state{NC}..."
)
os.system("cd ~/.config/dconf/ && dconf load / < user.txt")
print(f"{L_GREEN}Loaded dconf state{NC}\n")
