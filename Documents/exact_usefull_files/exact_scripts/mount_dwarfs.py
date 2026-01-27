#!/usr/bin/venv python3

import os
from pathlib import Path
import sys
import hashlib

args = sys.argv

if len(args) != 3:
    print("Expected 2 arguments (image location and what to do)")
    sys.exit(1)

image_path = Path(args[1])
action = args[2]

MOUNT_PREFIX = Path("~/.local/share/drwafs-mounts/").expanduser().absolute()


class MountDirHierarchy:
    filestem: str
    base_mount_path: Path
    ro_mount_path: Path
    rw_mount_path: Path
    work_mount_path: Path
    dummy_mount_path: Path
    overlay_mount_path: Path

    def __init__(self, base_mount_path: Path, filestem: str):
        self.filestem = filestem

        self.base_mount_dir = base_mount_path
        self.ro_mount_path = Path(base_mount_path, f"{filestem}-ro")
        self.rw_mount_path = Path(base_mount_path, f"{filestem}-rw")
        self.work_mount_path = Path(base_mount_path, f"{filestem}-work")
        self.dummy_mount_path = Path(base_mount_path, f"{filestem}-dummy")
        self.overlay_mount_path = Path(base_mount_path, f"{filestem}-mount")

        self.ro_mount_path.mkdir(exist_ok=True, parents=True)
        self.rw_mount_path.mkdir(exist_ok=True, parents=True)
        self.work_mount_path.mkdir(exist_ok=True, parents=True)
        self.dummy_mount_path.mkdir(exist_ok=True, parents=True)
        self.overlay_mount_path.mkdir(exist_ok=True, parents=True)


def get_base_mount_dir_from_image_path(path: Path):
    filename = path.stem
    absolute_prefix = path.absolute().parent.as_posix()
    prefix_hash = hashlib.md5(absolute_prefix.encode("utf-8")).hexdigest()[0:10]
    mount_path = Path(MOUNT_PREFIX, f"{filename}-{prefix_hash}")
    return MountDirHierarchy(mount_path, filename)


def mount_base_image_ro(path: Path):
    print(f"Mounting {path} RO")
    mount_info = get_base_mount_dir_from_image_path(path)
    if not mount_info.ro_mount_path.is_mount():
        os.system(f"dwarfs {path.as_posix()} {mount_info.ro_mount_path.as_posix()} -o readonly")
    else:
        print("Image already mounted")

    return mount_info


def mount_image_overlay(path: Path, is_rw: bool):
    mount_info = mount_base_image_ro(path)

    if not mount_info.overlay_mount_path.is_mount():
        mount_args = f"x-gvfs-name={mount_info.filestem}.dwarfs,lowerdir={mount_info.ro_mount_path.as_posix()}"
        if is_rw:
            mount_args += (
                f",upperdir={mount_info.rw_mount_path.as_posix()},workdir={mount_info.work_mount_path.as_posix()}"
            )
        else:
            mount_args += f":{mount_info.dummy_mount_path.as_posix()}"  # Overlayfs refuses to mount with only one dir

        os.system(
            f"pkexec mount -t overlay overlay_{mount_info.overlay_mount_path.stem} -o {mount_args} {mount_info.overlay_mount_path.as_posix()}"
        )
    else:
        print("Overlay already mounted")

    os.system(f"xdg-open {mount_info.overlay_mount_path.as_posix()}")

def unmount_base_image(path: Path):
    pass

def unmount_image_overlay(path: Path):
    pass

if action == "mount-ro":
    mount_image_overlay(image_path, False)

if action == "mount-rw":
    mount_image_overlay(image_path, True)
