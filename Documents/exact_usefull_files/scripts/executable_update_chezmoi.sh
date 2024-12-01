#!/bin/bash

set -e
set -u

sleep 15
chezmoi git fetch
paplay /usr/share/sounds/subnautica_theme/general_info.ogg &
res=$(notify-send -u critical --action=yes="Update now" "Dot files status" "$(chezmoi git status)")
if [ "$res" = "yes" ]; then
    konsole -e 'bash --rcfile ~/.bash_aliases -ic "chzu; bash"' &
fi

check_conflicts() {
    if [ -f ~/.config/syncthing/config.xml ]; then
        FOLDERS="$(cat ~/.config/syncthing/config.xml | grep -Po '"/home.*?"|"/mnt.*?"')"
    else
        FOLDERS="$(cat ~/.local/state/syncthing/config.xml | grep -Po '"/home.*?"|"/mnt.*?"')"

    fi

    while IFS= read -r folder; do
        find "$(echo "$folder" | tr -d '"')" -name "*sync-conflict*"
    done <<<"$FOLDERS"
}

CONFLICTS=$(check_conflicts)

if [ ! -z "$CONFLICTS" ]; then
    notify-send -u critical "Syncthing conflicts found" "$CONFLICTS"
fi
