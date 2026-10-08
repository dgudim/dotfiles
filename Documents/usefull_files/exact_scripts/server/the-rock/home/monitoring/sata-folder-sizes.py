#!/usr/bin/env python3
"""Measure top-level folders on /mnt/sata_500 and push the sizes to VictoriaMetrics."""

import fcntl
import os
import subprocess
import sys
import time
import urllib.request

MOUNT = "/mnt/sata_500"
IMPORT_URL = "http://127.0.0.1:8428/api/v1/import/prometheus"
LOCK_PATH = "/tmp/sata-folder-sizes.lock"


def esc(value):
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "")


def parse_du(stdout, stderr):
    denied_folders = set()
    prefix = MOUNT + "/"
    for line in stderr.splitlines():
        if "Permission denied" not in line or "'" not in line:
            continue
        path = line.split("'", 2)[1]
        if not path.startswith(prefix):
            continue
        denied_folders.add(path[len(prefix) :].split("/", 1)[0])

    samples = []
    for line in stdout.splitlines():
        if "\t" in line:
            size, path = line.split("\t", 1)
        else:
            size, path = line.split(None, 1)
        if not path.startswith(prefix):
            continue
        folder = path[len(prefix) :]
        if "/" in folder:
            continue
        label = f'mount="{esc(MOUNT)}",folder="{esc(folder)}"'
        if folder in denied_folders or not os.access(path, os.R_OK | os.X_OK):
            samples.append(f"disk_directory_unreadable{{{label}}} 1")
            continue
        samples.append(f"disk_directory_bytes{{{label}}} {int(size)}")
    samples.append(f"disk_directory_scan_timestamp_seconds {int(time.time())}")
    return samples


def measure():
    proc = subprocess.run(
        ["du", "-x", "-d", "1", "-B1", MOUNT],
        capture_output=True,
        text=True,
    )
    return parse_du(proc.stdout, proc.stderr)


def push(samples):
    body = ("\n".join(samples) + "\n").encode()
    req = urllib.request.Request(IMPORT_URL, data=body, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def main():
    lock = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    if len(sys.argv) == 3:
        with open(sys.argv[1], encoding="utf-8", errors="replace") as handle:
            stdout = handle.read()
        with open(sys.argv[2], encoding="utf-8", errors="replace") as handle:
            stderr = handle.read()
        samples = parse_du(stdout, stderr)
    else:
        samples = measure()
    push(samples)


if __name__ == "__main__":
    main()
