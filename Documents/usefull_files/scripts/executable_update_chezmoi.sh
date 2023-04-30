#!/bin/bash

sleep 15
chezmoi git fetch
notify-send -u critical "Dot files status" "$(chezmoi git status)"
paplay /usr/share/sounds/subnautica_theme/general_info.ogg
