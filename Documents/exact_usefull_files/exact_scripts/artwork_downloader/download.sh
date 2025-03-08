#!/bin/bash
set -e
set -o pipefail

touch pending_uniq.txt

# Append stuff left from prev run if present
cat pending_uniq.txt >> pending.txt
cat pending.txt | sort | uniq > pending_uniq.txt
echo '' > pending.txt

gallery-dl --input-file-delete pending_uniq.txt

cd gallery-dl

echo "Removing small images"

fd --type file --extension jpg --max-depth 1 --print0 | xargs -P $(nproc) -r -0 -I{} bash -c 'size=($(identify -format "%w %h" "$1")) || trash-put "$1"; (( ${size[@]:0:1} < 1080 || ${size[@]:1:1} < 1080 )) && echo "Removed $1, Size: ${size[@]:0:1}x${size[@]:1:1}" && trash-put "$1";' -- '{}'

