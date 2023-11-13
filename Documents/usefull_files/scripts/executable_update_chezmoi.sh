#!/bin/bash

#sleep 15
chezmoi git fetch
paplay /usr/share/sounds/subnautica_theme/general_info.ogg &
res=$(notify-send -u critical --action=yes="Update now" "Dot files status" "$(chezmoi git status)")
if [ "$res" = "yes" ]; then
    konsole -e '$SHELL -c "chezmoi update; $SHELL"' &
fi
