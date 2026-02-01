#!/usr/bin/venv python3

import os
from pathlib import Path
import shutil
from subprocess import Popen
import subprocess
import sys
import hashlib
from typing import NoReturn
from collections.abc import Callable

args = sys.argv

if len(args) != 3:
    print("Expected 2 arguments (image location and what to do)")
    sys.exit(1)

input_path = Path(args[1]).absolute()
action = args[2]

MOUNT_PREFIX = Path("~/.local/share/drwafs-mounts/").expanduser().absolute()

SUDO_APP = "sudo"

RED = "\033[0;31m"
L_RED = "\033[1;31m"
PURPLE = "\033[0;35m"
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
GRAY = "\033[38;5;240m"
LIGHT_GRAY = "\033[38;5;242m"
LIGHTER_GRAY = "\033[38;5;246m"


class MountDirHierarchy:
    filestem: str
    base_mount_dir: Path
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


def err_exit(message: str) -> NoReturn:
    print(f"{L_RED}{message}{NC}")
    _ = input(f"{LIGHT_GRAY}Press any key to continue{NC}")
    sys.exit(1)


def checked_exec(command: str):
    print(f"{L_CYAN}| {GRAY}exec _> {LIGHTER_GRAY}{command}{NC}")
    exit_code = os.system(command)
    if exit_code != 0:
        err_exit(f"Error executing command: '{RED}{command}{NC}'")


def display_gui_question(message: str):
    process = Popen(["kdialog", "--warningyesno", message, "--icon", "dialog-warning"], stdout=subprocess.PIPE)
    exit_code = process.wait()
    return not bool(exit_code)


def get_base_mount_dir_from_image_path(image_path: Path):
    filename = image_path.stem
    absolute_prefix = image_path.parent.as_posix()
    prefix_hash = hashlib.md5(absolute_prefix.encode("utf-8")).hexdigest()[0:10]
    mount_path = Path(MOUNT_PREFIX, f"{filename}-{prefix_hash}")
    return MountDirHierarchy(mount_path, filename)


def mount_base_image_ro(image_path: Path):
    print(f"{CYAN}Mounting {L_CYAN}{image_path} {L_YELLOW}RO{NC}")
    mount_info = get_base_mount_dir_from_image_path(image_path)
    if not mount_info.ro_mount_path.is_mount():
        checked_exec(f"dwarfs '{image_path.as_posix()}' '{mount_info.ro_mount_path.as_posix()}' -o allow_root")
    else:
        print(f"{YELLOW}Image already mounted{NC}")

    return mount_info


def mount_image_overlay(image_path: Path, is_rw: bool):
    mount_info = mount_base_image_ro(image_path)

    if not mount_info.overlay_mount_path.is_mount():
        mount_args = f"x-gvfs-name={mount_info.filestem}.dwarfs,lowerdir={mount_info.ro_mount_path.as_posix()}"
        if is_rw:
            mount_args += (
                f",upperdir={mount_info.rw_mount_path.as_posix()},workdir={mount_info.work_mount_path.as_posix()}"
            )
        else:
            mount_args += f":{mount_info.dummy_mount_path.as_posix()}"  # Overlayfs refuses to mount with only one dir

        checked_exec(
            f"{SUDO_APP} mount -t overlay 'overlay_{mount_info.overlay_mount_path.stem.lower().strip().replace(' ', '_')}' -o {mount_args} '{mount_info.overlay_mount_path.as_posix()}'"
        )
    else:
        print(f"{YELLOW}Overlay already mounted{NC}")

    checked_exec(f"xdg-open '{mount_info.overlay_mount_path.as_posix()}'")


def unmount_image(image_path: Path, keep_changes: Callable[..., bool]):
    print(f"{CYAN}Unmounting {L_CYAN}{image_path}{NC}")
    mount_info = get_base_mount_dir_from_image_path(image_path)

    compressed_image: Path | None = None

    if next(mount_info.rw_mount_path.iterdir(), None) is not None:
        if keep_changes():
            compressed_image = compress(mount_info.overlay_mount_path, False)
            if compressed_image is None:
                err_exit("Couldn't recompress, target image already exists")

    if mount_info.overlay_mount_path.is_mount():
        checked_exec(f"{SUDO_APP} umount '{mount_info.overlay_mount_path.as_posix()}'")
        print(f"{BLUE}Cleaning RW remains{NC}")
        shutil.rmtree(mount_info.rw_mount_path)
        checked_exec(f"{SUDO_APP} rm -rf '{mount_info.work_mount_path.as_posix()}'")
    else:
        print(f"{YELLOW}Overlay already unmounted{NC}")

    if mount_info.ro_mount_path.is_mount():
        checked_exec(f"umount '{mount_info.ro_mount_path.as_posix()}'")
    else:
        print(f"{YELLOW}Image already unmounted{NC}")

    if compressed_image is not None:
        print(f"{BLUE}Deleting old image{NC}")
        image_path.unlink()
        print(f"{BLUE}Moving {L_BLUE}new image {BLUE}to {L_BLUE}old location{NC}")
        compressed_image.rename(image_path)

    return mount_info


def compress(source_dir_path: Path, delete_directory: bool):
    print(f"{CYAN}Compressing {L_CYAN}{source_dir_path}{NC}")

    input_folder_name = source_dir_path.stem
    output_image_path = Path(source_dir_path.parent, f"{input_folder_name}.dwarfs")
    if output_image_path.exists() and not display_gui_question("Output image already exists, overwrite?"):
        return

    # maximum compression (l9), 4MiB (2^22) blocks, 5 blocks lookback (20 Need to be decompressed at worst)
    checked_exec(
        f"mkdwarfs -l9 --force --block-size-bits=22 --max-lookback-blocks=5 --categorize -i '{source_dir_path.as_posix()}' -o '{output_image_path}'"
    )

    if delete_directory:
        print(f"{BLUE}Deleting {L_BLUE}source directory{NC}")
        shutil.rmtree(source_dir_path)

    return output_image_path


def extract_image(image_path: Path, target_path: Path | None, delete_image: bool):
    print(f"{CYAN}Compressing {L_CYAN}{image_path}{NC}")

    if target_path is None:
        target_path = Path(image_path.parent, image_path.stem)

    if target_path.exists():
        if not display_gui_question("Output path already exists, extract on top?"):
            return

    target_path.mkdir(exist_ok=True, parents=True)

    mount_info = mount_base_image_ro(image_path)
    print(f"{BLUE}Copying files{NC}")
    shutil.copytree(mount_info.ro_mount_path, target_path, dirs_exist_ok=True, symlinks=True)

    if (
        not mount_info.overlay_mount_path.is_mount() or delete_image
    ):  # Only unmount if the base image is mounted (we did it) or we are going to delete the image
        unmount_image(image_path, lambda: False)
    else:
        print(f"{YELLOW}Not unmounting the image since overlay is mounted{NC}")

    if delete_image:
        print(f"{BLUE}Deleting {L_BLUE}source image{NC}")
        image_path.unlink()


def extract_into(image_path: Path, delete_image: bool):
    process = Popen(["kdialog", "--getexistingdirectory"], stdout=subprocess.PIPE, text=True)
    exit_code = process.wait()

    extraction_directory = Path(str(process.stdout.read()).strip()) if exit_code == 0 and process.stdout else None

    extract_image(image_path, extraction_directory, delete_image)


match action:
    case "mount-ro":
        mount_image_overlay(input_path, False)
    case "mount-rw":
        mount_image_overlay(input_path, True)
    case "unmount-discard-changes":
        unmount_image(input_path, lambda: False)
    case "unmount-keep-changes":
        unmount_image(input_path, lambda: True)
    case "unmount-interactive":
        unmount_image(input_path, lambda: display_gui_question("Image was modified, keep changes?"))
    case "make-image":
        compress(input_path, False)
    case "make-image-delete-source":
        compress(input_path, True)
    case "extract-cwd":
        extract_image(input_path, None, False)
    case "extract-cwd-delete":
        extract_image(input_path, None, True)
    case "extract-select":
        extract_into(input_path, False)
    case "extract-select-delete":
        extract_into(input_path, True)
