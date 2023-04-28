#!/bin/bash
while true; do

P_SECONDS=0

inotifywait -m --exclude "\.git" -e modify,create,delete,move -r $1 | {
    while read dir action file; do
        if (( $(date +%s) <= $P_SECONDS + 2 )); then
            continue
        fi
        P_SECONDS=$(date +%s)
        notify-send -u critical "$2" "$3 ($file/$action)"
    done
}

done
