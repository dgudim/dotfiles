#!/bin/bash

set -e
set -u

konsole -e "bash -c 'python /home/kloud/Documents/usefull_files/scripts/dwarfs_helper.py \"$1\" $2 || read -p \"Press enter to close\"'"

