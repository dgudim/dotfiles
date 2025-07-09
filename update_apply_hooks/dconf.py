#!/usr/bin/venv python3

import os

L_PURPLE = "\033[1;35m"
NC = "\033[0m"
L_CYAN = "\033[1;36m"
L_BLUE = "\033[1;34m"


def pre():
    print(f"{L_PURPLE} dumping {L_CYAN}dconf{L_PURPLE} state{NC}...")

    os.system("cd ~/.config/dconf/ && dconf dump / > user.txt")


def post():
    print(f"{L_PURPLE} loading {L_CYAN}dconf{L_PURPLE} state{NC}...")

    os.system("cd ~/.config/dconf/ && dconf load / < user.txt")
