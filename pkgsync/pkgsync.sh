#!/bin/bash

set -e



# | ------------------------------------------------------------------------------- |
# |                                                                                 |
# | This is a modified script taken from https://github.com/moparisthebest/pkgsync  |
# |                                                                                 |
# | ------------------------------------------------------------------------------- |




# this is the configuration for pkgsync

# list files can have comments starting with #, and do not need to be sorted

# packages on this system to exclude from shared install list
HARDWARE_LIST=./pkg_hardware_$(hostname).list
# echo $HARDWARE_LIST

# packages in shared install list to not install on this system
BLACKLIST_LIST=./pkg_blacklist_$(hostname).list
# echo $BLACKLIST_LIST

# packages to remove from all systems, you must sync it between systems
REMOVE_LIST=./pkg_remove.list

# packages to install on all systems, you must sync it between systems
INSTALL_LIST=./pkg_install.list

# directory to store temporary working files in
TMP_DIR=/tmp

[ -x "$PRESTART_SCRIPT" ] && "$PRESTART_SCRIPT"

# we really don't care if these exist or not or are empty, we just want empty files if so
grep -v '^#' "$HARDWARE_LIST"  2>/dev/null | sort -u > "$TMP_DIR/local_install.list"  || true
grep -v '^#' "$INSTALL_LIST"   2>/dev/null | sort -u > "$TMP_DIR/global_install.list" || true
grep -v '^#' "$BLACKLIST_LIST" 2>/dev/null | sort -u > "$TMP_DIR/local_black.list"    || true
grep -v '^#' "$REMOVE_LIST"    2>/dev/null | sort -u > "$TMP_DIR/global_black.list"   || true

pacman -Qqe | sort > "$TMP_DIR/explicitly_installed.list"

cat "$TMP_DIR/local_install.list" "$TMP_DIR/global_install.list" | sort -u > "$TMP_DIR/combined_install.list"
cat "$TMP_DIR/local_black.list" "$TMP_DIR/global_black.list"     | sort -u > "$TMP_DIR/combined_black.list"

# 23 = remove lines unique to FILE2 and lines that appear in both files
# To add = locally installed (explicit) - global install list - local install list (hardware)
comm -23 "$TMP_DIR/explicitly_installed.list" "$TMP_DIR/combined_install.list" > "$TMP_DIR/pkg_to_add.list"

# To remove = (blacklist (global) + blacklist (local)) (<<<-intersection with->>>) locally installed (explicit)
comm -12 "$TMP_DIR/explicitly_installed.list" "$TMP_DIR/combined_black.list" > "$TMP_DIR/pkg_to_remove.list"

# To install = global install list + local install list (hardware) - locally installed - blacklist (global) - blacklist (local)
comm -23 "$TMP_DIR/combined_install.list" "$TMP_DIR/combined_black.list" | comm -23 - "$TMP_DIR/explicitly_installed.list" > "$TMP_DIR/pkg_to_install.list"

# offer to install missing packages
if [ -s "$TMP_DIR/pkg_to_install.list" ]
then
    yn=l
    while [[ ! "$yn" =~ ^[YyNnAa]$ ]]
    do
        read -p "Install new packages? (yes/no/list/abort)..." -n 1 yn
        echo
        [[ "$yn" =~ ^[Ll]$ ]] && cat "$TMP_DIR/pkg_to_install.list"
    done
    if [[ "$yn" =~ ^[Yy]$ ]]
    then
        yay -S --needed --confirm $(cat $TMP_DIR/pkg_to_install.list)
        # Mark as explicitly installed
        sudo pacman -D --asexplicit --confirm - < "$TMP_DIR/pkg_to_install.list"
    fi
    [[ "$yn" =~ ^[Aa]$ ]] && exit 1
fi

# offer to remove packages
if [ -s "$TMP_DIR/pkg_to_remove.list" ]
then
    yn=l
    while [[ ! "$yn" =~ ^[YyNnAa]$ ]]
    do
        read -p "Remove packages? (yes/no/list/abort)..." -n 1 yn
        echo
        [[ "$yn" =~ ^[Ll]$ ]] && cat "$TMP_DIR/pkg_to_remove.list"
    done
    [[ "$yn" =~ ^[Yy]$ ]] && sudo pacman -D --asdeps - < "$TMP_DIR/pkg_to_remove.list"
    [[ "$yn" =~ ^[Yy]$ ]] && sudo pacman -Runs --confirm - < "$TMP_DIR/pkg_to_remove.list"
    [[ "$yn" =~ ^[Aa]$ ]] && exit 0
fi

# offer to update install list, if it changed
if [ -s "$TMP_DIR/pkg_to_add.list" ]
then
    yn=l
    while [[ ! "$yn" =~ ^[YyNnAa]$ ]]
    do
        read -p "Append packages unique to this computer to install list (yes/no/list/abort)..." -n 1 yn
        echo
        [[ "$yn" =~ ^[Ll]$ ]] && cat "$TMP_DIR/pkg_to_add.list"
    done
    [[ "$yn" =~ ^[Yy]$ ]] && cat "$TMP_DIR/pkg_to_add.list" >> "$INSTALL_LIST"
    [[ "$yn" =~ ^[Aa]$ ]] && exit 0
fi

