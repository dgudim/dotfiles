#!/usr/bin/venv python3

import os

L_PURPLE = "\033[1;35m"
NC = "\033[0m"
L_CYAN = "\033[1;36m"
L_BLUE = "\033[1;34m"


def pre():
    print(f"{L_PURPLE} dumping {L_CYAN}activitywatch{L_PURPLE} settings{NC}...")
    os.system(
        "cd ~/.local/share/activitywatch/aw-server-rust/ && sqlite3 sqlite.db '.dump key_value' > settings.sql && sed -i 's/TRANSACTION;/TRANSACTION;DROP TABLE key_value;/g' settings.sql"
    )


def post():
    print(f"{L_PURPLE} loading {L_CYAN}activitywatch{L_PURPLE} settings{NC}...")
    os.system("killall aw-qt && killall aw-server-rust && sleep 5")
    os.system(
        "cd ~/.local/share/activitywatch/aw-server-rust/ && sqlite3 sqlite.db < settings.sql"
    )
    os.system("aw-qt > /dev/null & disown")
