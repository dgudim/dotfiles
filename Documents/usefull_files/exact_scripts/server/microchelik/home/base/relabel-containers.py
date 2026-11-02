#!/usr/bin/env python3
import json
import os
import subprocess
import sys

STACKS_ROOT = "/home/kloud"
DRY_RUN = "--dry-run" in sys.argv


def run(*cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout


def labels(kind, ref):
    return json.loads(run("docker", kind, "inspect", "-f", "{{json .Config.Labels}}", ref)) or {}


for stack in sorted(os.listdir(STACKS_ROOT)):
    stack_dir = os.path.join(STACKS_ROOT, stack)
    if not os.path.isfile(os.path.join(stack_dir, "compose.yaml")):
        continue

    config = json.loads(run("docker", "compose", "config", "--format", "json", cwd=stack_dir))
    running = run("docker", "compose", "ps", "--status", "running", "--format", "{{.Service}} {{.ID}}", cwd=stack_dir)

    changed = []
    for line in running.splitlines():
        service, container = line.split()
        image = labels("image", run("docker", "inspect", "-f", "{{.Image}}", container).strip())
        has = {k: v for k, v in labels("container", container).items()
                if not k.startswith("com.docker.compose.") and k not in image}
        wants = {k: v for k, v in (config["services"][service].get("labels") or {}).items() if k not in image}
        if has != wants:
            changed.append(service)

    if changed:
        print(f"{stack}: {' '.join(changed)}")
        if not DRY_RUN:
            subprocess.run(["docker", "compose", "up", "-d", "--no-deps", *changed], cwd=stack_dir, check=True)
