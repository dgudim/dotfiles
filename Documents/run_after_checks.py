#!/usr/bin/python

import re
import os

RED = "\033[0;31m"
L_RED = "\033[1;31m"
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

print(f"{L_PURPLE}Running checks{NC}...")

warn = 0


def read_file(path: str) -> str:
    try:
        f = open(path, "r", encoding="utf-8")
        contents = f.read()
        f.close()
        return contents
    except Exception:
        return ""


def check_mount_opts(fstabb: str, fsopts: dict[str, list[str]]):
    to_add = 0

    for line in fstabb.split("\n"):
        if len(line) == 0 or line[0] == "#":
            continue
        if line.find(" ntfs ") != -1:
            # Replace with the new ntfs driver
            print(f"{YELLOW}Consider replacing ntfs with ntfs3 {NC} ({line})")
            continue
        for fs, opts in fsopts.items():
            if line.find(f" {fs} ") == -1:
                # Skip options for other filesystems
                continue
            # Yay, we found our target filesystem
            for opt in opts:
                if sum(1 for _ in re.finditer(f"({opt})", line)) != 1:
                    print(f"{YELLOW}Consider adding {opt} to {fs}{NC} ({line})")
                    to_add += 1
            # A line can only contain 1 filesystem, exit, process next line
            break

    return to_add


print(f"{LIGHTER_GRAY}Checking fstab{NC}")
fstab = read_file("/etc/fstab")

print(f"{LIGHT_GRAY}Checking tmp dir{NC}")
if fstab.find("/tmp") != -1:
    warn += 1
    print(f"{YELLOW}Consider removing /tmp from fstab{NC}")

print(f"{LIGHT_GRAY}Checking fsck field{NC}")
if fstab.find(" 3") != -1:
    warn += 1
    print(f"{YELLOW}Consider changing fsck field to 2 from 3 fstab{NC}")

print(f"{LIGHT_GRAY}Checking mount options{NC}")
warn += check_mount_opts(
    fstab,
    {
        "ext4": ["defaults", "commit=60", "noatime"],
        "vfat": ["defaults", "noatime", "umask=0077"],
        "btrfs": ["compress=zstd:[0-9]+", "exec", "noatime", "X-fstrim\.notrim"],
        "ntfs3": [
            "windows_names",
            "rw",
            "uid=1000",
            "gid=1000",
            "async",
            "nofail",
            "prealloc",
            "users",
            "exec",
            "noatime",
        ],
        "nfs": ["defaults", "nofail"],
    },
)

print(f"{LIGHTER_GRAY}Checking kernel cmdline{NC}")
cmdline = read_file("/etc/kernel/cmdline")
if len(cmdline) > 0 and cmdline.find("mitigations=off") == -1:
    warn += 1
    print(f"{YELLOW}Turn off mitigations in cmdline{NC}")
elif len(cmdline) == 0:
    grub = read_file("/etc/default/grub")
    if len(grub) > 0 and grub.find("mitigations=off") == -1:
        warn += 1
        print(f"{YELLOW}Turn off mitigations in grub{NC}")

if cmdline.find("rd.luks") != -1:
    print(f"{LIGHTER_GRAY}Checking /etc/crypttab{NC}")

    os.system("sudo cat /etc/crypttab > /tmp/luks_crypttab")
    crypttab = read_file("/tmp/luks_crypttab")
    os.system("rm /tmp/luks_crypttab")

    luks_root = re.search(
        r"\/dev\/mapper\/luks-(.*?) *?\/ *?(ext4|btrfs)", fstab)
    if luks_root is not None:
        luks_root_uuid = luks_root.group(1)

        luks_crypttab_opts = re.search(
            rf"UUID={luks_root_uuid} .*?\/crypto_keyfile\.bin .*?(.*)", crypttab
        )

        if (
            luks_crypttab_opts is not None
            and luks_crypttab_opts.group(1).find("discard") == -1
        ):
            print(
                f"{YELLOW}Consider adding discard to luks {L_BLUE}{luks_root_uuid}{YELLOW} in crypttab{NC}"
            )
            warn += 1
    else:
        print(f"{RED}Couldn't find luks root in fstab!{NC}")

print(f"{LIGHTER_GRAY}Checking firefox profile{NC}")
firefox_profile_root = "/home/kloud/.mozilla/firefox"
firefox_profiles = [
    os.path.join(firefox_profile_root, d)
    for d in os.listdir(firefox_profile_root)
    if os.path.isdir(os.path.join(firefox_profile_root, d))
    and f"{d}".find("default-release") != -1
    and f"{d}".find("backup") == -1
]

firefox_settings = [
    "widget.use-xdg-desktop-portal.file-picker",
    "media.ffmpeg.vaapi.enabled",
    "media.av1.enabled",
    "gfx.x11-egl.force-enabled",
    "widget.dmabuf.force-enabled",
    "gfx.webrender.all",
    "gfx.webrender.compositor",
    "gfx.webrender.compositor.force-enabled",
    "dom.webgpu.enabled",
    "gfx.webrender.precache-shaders",
    "gfx.webrender.force-partial-present",
    "svg.context-properties.content.enabled",
    "accessibility.typeaheadfind.enablesound",
    "accessibility.typeaheadfind.soundURL"
]

if len(firefox_profiles) == 0:
    print(f"{RED}Couldn't find firefox profile{NC}")
else:

    def check_setting(s: str, setting: str) -> int:
        if s.find(setting) == -1:
            print(f"{YELLOW}Consider adding {setting} to firefox{NC}")
            return 1
        return 0

    print(f"{GRAY}Selected firefox profile: {firefox_profiles[0]}{NC}")

    about_config = read_file(os.path.join(firefox_profiles[0], "prefs.js"))
    for setting in firefox_settings:
        warn += check_setting(about_config, setting)

print(f"{L_GREEN}Finished running checks, {L_CYAN}{warn}{L_GREEN} warning(s){NC}\n")
