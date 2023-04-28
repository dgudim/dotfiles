#!/bin/bash

sleep 15

notify-send -u critical "Dot files status" "$(chezmoi update)"
paplay /usr/share/sounds/subnautica_theme/general_info.ogg
