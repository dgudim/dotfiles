#!/usr/bin/env python3
"""Measure top-level folders on /mnt/sata_500 and push the sizes to VictoriaMetrics."""

import fcntl
import os
import subprocess
import time
from pathlib import Path

import requests

MOUNT = Path("/mnt/sata_500")
IMPORT_URL = "http://127.0.0.1:8428/api/v1/import/prometheus"
LOCK_PATH = Path("/tmp/sata-folder-sizes.lock")


def esc(value):
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "")


def denied_folders(stderr, mount):
    folders = set()
    for line in stderr.splitlines():
        if "Permission denied" not in line or "'" not in line:
            continue
        try:
            relative = Path(line.split("'", 2)[1]).relative_to(mount)
        except ValueError:
            continue
        if relative.parts:
            folders.add(relative.parts[0])
    return folders


def collect(mount, stdout, stderr):
    denied = denied_folders(stderr, mount)
    samples = []
    for line in stdout.splitlines():
        size, raw = line.split("\t", 1) if "\t" in line else line.split(None, 1)
        path = Path(raw)
        try:
            relative = path.relative_to(mount)
        except ValueError:
            continue
        if len(relative.parts) != 1:
            continue
        folder = relative.parts[0]
        label = f'mount="{esc(str(mount))}",folder="{esc(folder)}"'
        if folder in denied or not os.access(path, os.R_OK | os.X_OK):
            samples.append(f"disk_directory_unreadable{{{label}}} 1")
            continue
        samples.append(f"disk_directory_bytes{{{label}}} {int(size)}")
    samples.append(f"disk_directory_scan_timestamp_seconds {int(time.time())}")
    return samples


def measure(mount=MOUNT):
    proc = subprocess.run(
        ["du", "-x", "-d", "1", "-B1", os.fspath(mount)],
        capture_output=True,
        text=True,
    )
    return collect(mount, proc.stdout, proc.stderr)


def push(samples):
    response = requests.post(IMPORT_URL, data=("\n".join(samples) + "\n").encode(), timeout=30)
    response.raise_for_status()


def main():
    lock = LOCK_PATH.open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    push(measure())


if __name__ == "__main__":
    main()
