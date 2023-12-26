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

print(f"{L_PURPLE}Running checks{NC}...")

warn = 0


def findall(s: str, sub: str):
    return [m.start() for m in re.finditer(sub, s)]


def read_file(path: str) -> str:
    try:
        f = open(path, "r", encoding="utf-8")
        contents = f.read()
        f.close()
        return contents
    except Exception:
        return ""


def check_mount_opts(fstab: str, fs: str, opts: str):
    to_add = 0
    entries = len(findall(fstab, f" {fs} "))
    for opt in opts.split(","):
        if entries > len(findall(fstab, f"({opt})")):
            print(f"{YELLOW}Consider adding {opt} to {fs}{NC}")
            to_add += 1
    return to_add


fstab = read_file("/etc/fstab")
if fstab.find("/tmp") != -1:
    warn += 1
    print(f"{YELLOW}Consider removing /tmp from fstab{NC}")

if fstab.find(" 3") != -1:
    warn += 1
    print(f"{YELLOW}Consider changing fsck field to 2 from 3 fstab{NC}")

warn += check_mount_opts(fstab, "ext4", "defaults,commit=60,noatime")
warn += check_mount_opts(fstab, "vfat", "defaults,noatime,umask=0077")
warn += check_mount_opts(
    fstab, "btrfs", "compress=zstd:[0-9]+,exec,noatime,X-fstrim\.notrim"
)

warn += check_mount_opts(
    fstab, "ntfs", "windows_names,rw,uid=1000,gid=1000,async,nofail,prealloc,users,exec"
)

warn += check_mount_opts(fstab, "nfs", "defaults,nofail")

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
        print(f"{L_RED}Couldn't find luks root in fstab!{NC}")

print(f"{L_GREEN}Finished running checks, {L_CYAN}{warn}{L_GREEN} warning(s){NC}\n")
