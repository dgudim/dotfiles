#!/usr/bin/env -S uv run --script

import sys
from pathlib import Path
import os

L_PURPLE = "\033[1;35m"
NC = "\033[0m"
L_CYAN = "\033[1;36m"
L_BLUE = "\033[1;34m"

files_to_add = sys.argv[1:]

if len(files_to_add) == 0:
    print("Nothing to add")

files_to_add_resolved = []

for path in (Path(p) for p in files_to_add):
    if path.is_dir():
        files_to_add_resolved += [subfile for subfile in path.rglob("*") if (subfile.is_file() or subfile.is_symlink())]
    else:
        files_to_add_resolved.append(path)


for file_ in files_to_add_resolved:
    if file_.is_symlink():
        print(f"Adding {L_CYAN}'{file_}'{NC} (symlink)")
        os.system(f'chezmoi add "{file_}"')
    else:
        print(f"Adding {L_PURPLE}'{file_}'{NC}")
        os.system(f'chezmoi_modify_manager -s "{file_}"')

