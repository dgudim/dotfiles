#!/bin/bash

sleep 15

cd /home/kloud/Documents/shared/_Personal/usefull_files/

git fetch

notify-send -u critical "Dot files status" "$(git status)"

paplay /usr/share/sounds/subnautica_theme/general_info.ogg

bash ./scripts/watch_for_changes.sh ./ "Dot files changed" "Commit your changes"
