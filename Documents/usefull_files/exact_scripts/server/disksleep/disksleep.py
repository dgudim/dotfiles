#!/usr/bin/env python3

import signal
import subprocess
import sys
import time
from pathlib import Path

IDLE_MIN = 30        # spin a drive down after this long without reads/writes
INTERVAL_SEC = 60

SYS_BLOCK = Path("/sys/block")
DISKSTATS = Path("/proc/diskstats")


def spinning_drives():
    drives = []
    for dev in SYS_BLOCK.glob("sd*"):
        try:
            if (dev / "queue" / "rotational").read_text().strip() == "1":
                drives.append(dev.name)
        except OSError:
            pass  # drive went away
    return drives


def io_counters():
    # /proc/diskstats fields: [2] name, [5] sectors read, [9] sectors written
    return {f[2]: (f[5], f[9]) for f in map(str.split, DISKSTATS.read_text().splitlines())}


def spin_down(dev):
    r = subprocess.run(["hdparm", "-y", f"/dev/{dev}"], capture_output=True, text=True)
    if r.returncode == 0:
        print(f"{dev}: idle for {IDLE_MIN} min, spinning down", flush=True)
    else:
        print(f"{dev}: spin-down failed: {r.stderr.strip()}", flush=True)


signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
disks = {}  # sdX -> (sectors r/w, time of last change, asleep)

while True:
    stats = io_counters()
    now = time.monotonic()
    for dev in spinning_drives():
        io = stats.get(dev)
        last_io, last_change, asleep = disks.get(dev, (io, now, False))
        if io != last_io:
            last_change, asleep = now, False  # real I/O: drive is awake again
        elif not asleep and now - last_change >= IDLE_MIN * 60:
            spin_down(dev)
            asleep = True
        disks[dev] = (io, last_change, asleep)
    time.sleep(INTERVAL_SEC)
