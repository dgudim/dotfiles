#!/usr/bin/venv python3

import sys
import os

args = sys.argv

if len(args) != 3:
    sys.exit(1)

path = args[1]
action = args[2]

mountdir_name = ".".join(os.path.basename(path).split(".")[0:-1])
mountpath = f"/home/kloud/.local/share/drwafs-mounts/{mountdir_name}"

os.system("mountpoint '{mountpath}'")

is_mounted

if action == "mount":
    print(f"Mounting into {mountdir_name}")

elif action == "unmount":
    print(f"Unmounting {mountdir_name}")
