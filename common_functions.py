#!/usr/bin/venv python3

from enum import Enum
import importlib
import os
from pathlib import Path
import sys


def getenv(name: str) -> str:
    val = os.getenv(name)
    if not val:
        print(f"{RED}{name} is unset!!{NC}")
        sys.exit(1)
    return val


RED = "\033[0;31m"
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


class HookType(Enum):
    PRE = 0
    POST = 1


ignore_patterns = ["__pycache__", "common_functions.py"]


def run_hooks(hook_type: HookType):
    hook_type_str = hook_type.name.lower()

    print(f"{L_PURPLE}Running {L_BLUE}{hook_type_str} update/apply hooks{NC}")

    hooks_path = Path(getenv("CHEZMOI_SOURCE_DIR"), "update_apply_hooks")
    for hook_filepath in hooks_path.rglob("*"):
        if not hook_filepath.is_file() or any(
            (ignore_pattern in str(hook_filepath)) for ignore_pattern in ignore_patterns
        ):
            continue

        print(f"{L_PURPLE}Running {L_BLUE}{hook_type_str} update/apply hook{NC}: {L_CYAN}{hook_filepath.stem}{NC}...")

        module = importlib.import_module(
            f"update_apply_hooks.{hook_filepath.stem}",
            package=str(hook_filepath.absolute()),
        )

        match hook_type:
            case HookType.PRE:
                module.pre()
            case HookType.POST:
                module.post()
