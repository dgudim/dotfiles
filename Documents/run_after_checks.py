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
    warn = 0

    for line in fstabb.split("\n"):
        if len(line) == 0 or line[0] == "#":
            continue
        if line.find(" ntfs ") != -1:
            # Replace with the new ntfs driver
            print(f"{YELLOW}Consider replacing ntfs with ntfs3 {NC} ({line})")
            warn += 1

        dump_pass = re.search(r" (\d) *? (\d)", line)
        if len(dump_pass.groups()) == 2:
            fsck_pass = int(dump_pass.group(2).strip())
            if fsck_pass > 2:
                warn += 1
                print(f"{YELLOW}Consider changing fsck field to 2 from {fsck_pass} {NC} ({line})")

            if fsck_pass == 1 and line.find(" / ") == -1:
                print(f"{YELLOW}Consider changing fsck field to 2 from {fsck_pass} {NC} (Only root should have pass value of 1) ({line})")

            if fsck_pass != 1 and line.find(" / ") != -1:
                print(f"{YELLOW}Consider changing fsck field to 1 from {fsck_pass} {NC} (Root should have pass value of 1) ({line})")

            if fsck_pass == 0:
                if line.find(" btrfs ") == -1:
                    print(f"{YELLOW}Consider changing fsck field to 2 from {fsck_pass} {NC} ({line})")
                else:
                    print(f"{YELLOW}Consider changing fsck field to 0 from {fsck_pass} (Btrfs does not need it) {NC} ({line})")


        for fs, opts in fsopts.items():
            if line.find(f" {fs} ") == -1:
                # Skip options for other filesystems
                continue
            # Yay, we found our target filesystem
            for opt in opts:
                if sum(1 for _ in re.finditer(f"({opt})", line)) != 1:
                    print(f"{YELLOW}Consider adding {opt} to {fs}{NC} ({line})")
                    warn += 1
            # A line can only contain 1 filesystem, exit, process next line
            break

    return warn


print(f"{LIGHTER_GRAY}Checking fstab{NC}")
fstab = read_file("/etc/fstab")

print(f"{LIGHT_GRAY}Checking tmp dir{NC}")
if fstab.find("/tmp") != -1:
    warn += 1
    print(f"{YELLOW}Consider removing /tmp from fstab{NC}")

print(f"{LIGHT_GRAY}Checking mount options{NC}")
ntfs_mount_opts = [
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
]
warn += check_mount_opts(
    fstab,
    {
        "ext4": ["defaults", "commit=60", "noatime"],
        "vfat": ["defaults", "noatime", "umask=0077"],
        "btrfs": ["compress=zstd:[0-9]+", "exec", "noatime", "X-fstrim\.notrim"],
        "ntfs": ntfs_mount_opts,
        "ntfs3": ntfs_mount_opts,
        "ntfs-3g": ntfs_mount_opts,
        "nfs": ["defaults", "nofail"],
    },
)

print(f"{LIGHTER_GRAY}Checking kernel cmdline{NC}")
cmdline = read_file("/etc/kernel/cmdline")
grub = read_file("/etc/default/grub")

bootfile = cmdline if len(cmdline) > 0 else grub

if len(bootfile) > 0 and bootfile.find("mitigations=off") == -1:
    warn += 1
    print(f"{YELLOW}Turn off mitigations in kernel cmdline{NC}")

if len(bootfile) > 0 and bootfile.find("rd.luks.options") != -1:
    warn += 1
    print(f"{YELLOW}Remove rd.luks.options from kernel cmdline{NC}")

# https://wiki.archlinux.org/title/Dm-crypt/Specialties#Discard/TRIM_support_for_solid_state_drives_(SSD)
if cmdline.find("rd.luks") != -1:
    print(f"{LIGHTER_GRAY}Checking /etc/crypttab{NC}")

    os.system("sudo cat /etc/crypttab > /tmp/luks_crypttab")
    crypttab = read_file("/tmp/luks_crypttab")
    os.system("rm /tmp/luks_crypttab")

    luks_root = re.search(
        r"\/dev\/mapper\/luks-(.*?) *?\/ *?(ext4|btrfs)", fstab)
    if luks_root is not None:
        luks_root_uuid = luks_root.group(1)
        disk_dev_id = "/dev/" + os.path.basename(os.readlink(f"/dev/disk/by-uuid/{luks_root_uuid}"))

        os.system(f"sudo cryptsetup luksDump {disk_dev_id} | grep Flags | cut -d':' -f2 > /tmp/luks_root_flags")
        luks_root_flags = read_file("/tmp/luks_root_flags")
        os.system("rm /tmp/luks_root_flags")

        if luks_root_flags.find("allow-discards") == -1 or luks_root_flags.find("no-read-workqueue") == -1 or luks_root_flags.find("no-write-workqueue") == -1:
            print(
                f"{YELLOW}sudo cryptsetup --perf-no_read_workqueue --perf-no_write_workqueue --allow-discards --persistent refresh {disk_dev_id} luks-{luks_root_uuid}{NC}"
            )
            warn += 1

        luks_crypttab_opts = re.search(
            rf"UUID={luks_root_uuid} .*?\/crypto_keyfile\.bin .*?(.*)", crypttab
        )

        if (
            luks_crypttab_opts is not None
            and luks_crypttab_opts.group(1).find("discard") != -1
        ):
            print(
                f"{YELLOW}Consider removing discard from luks {L_BLUE}{luks_root_uuid}{YELLOW} in crypttab{NC}"
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
