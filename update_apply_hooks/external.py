#!/usr/bin/venv python3

import urllib.request
import shutil
from pathlib import Path

L_PURPLE = "\033[1;35m"
NC = "\033[0m"
CYAN = "\033[0;36m"
BLUE = "\033[0;34m"
YELLOW='\033[0;33m'

external_scripts = [
    ("https://gitlab.com/cscs/maxperfwiz/raw/main/maxperfwiz", "~/Documents/usefull_files/maxperfwiz"),
    ("https://gist.githubusercontent.com/mtekman/9769fa3eb28dd0dbdd1e8ce802157e95/raw", "~/Documents/usefull_files/least_used.sh"),
    ("https://raw.githubusercontent.com/jake-stewart/color256/refs/heads/main/color256.py", "~/Documents/usefull_files/color256.py")
]

def pre():
    print(f"{L_PURPLE} Downloading external scripts{NC}...")

    for url, path in external_scripts:
        pathlib_path = Path(path)
        full_target_path = pathlib_path.expanduser().as_posix()

        print(f"{BLUE}Downloading {url}{NC}")
        try:
            temp_path, response = urllib.request.urlretrieve(url)

            pathlib_path.unlink(missing_ok=True)

            shutil.move(temp_path, full_target_path)
            print(f"{CYAN} - Downloaded{NC} into {full_target_path}")
        except Exception as e:
            print(f"{YELLOW}Failed downloading: {url}{NC}: {e}")


def post():
    pass

