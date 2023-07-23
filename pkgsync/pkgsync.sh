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
EXCLUSION_LIST=./pkg_exclude.list

# packages in shared install list to not install on this system
BLACKLIST_LIST=./pkg_blacklist.list

# packages to remove from all systems, you must sync it between systems
REMOVE_LIST=./pkg_remove.list

# packages to install on all systems, you must sync it between systems
INSTALL_LIST=./pkg_install.list

# scripts must be executable and have non-zero exit status for pkgsync to continue

# script that is ran before pkgsync calculations start, can be used to sync various lists
#PRESTART_SCRIPT=/etc/pkgsync/pkg_prestart.sh

# script that is ran when INSTALL_LIST is changed, can be used to sync it
#FINISH_SCRIPT=/etc/pkgsync/pkg_finish.sh

# directory to store temporary working files in
#TMP_DIR=/tmp

[ -x "$PRESTART_SCRIPT" ] && "$PRESTART_SCRIPT"

# we really don't care if these exist or not or are empty, we just want empty files if so
grep -v '^#' "$EXCLUSION_LIST" 2>/dev/null | sort -u > "$TMP_DIR/pkg_exclude.list"   || true
grep -v '^#' "$BLACKLIST_LIST" 2>/dev/null | sort -u > "$TMP_DIR/pkg_blacklist.list" || true
grep -v '^#' "$REMOVE_LIST"    2>/dev/null | sort -u > "$TMP_DIR/pkg_remove.list"    || true
grep -v '^#' "$INSTALL_LIST"   2>/dev/null | sort -u > "$TMP_DIR/pkg_install.list"   || true

# get our explicitly installed packages, minus hardware-specific exclusions
pacman -Qqe | sort | comm -23 - "$TMP_DIR/pkg_exclude.list" > "$TMP_DIR/mypkgs_with_exclusions.txt"

# exclude packages to remove
comm -23 "$TMP_DIR/mypkgs_with_exclusions.txt" "$TMP_DIR/pkg_remove.list" > "$TMP_DIR/mypkgs_with_exclusions_without_remove.txt"

# list of packages to remove
comm -12 "$TMP_DIR/mypkgs_with_exclusions.txt" "$TMP_DIR/pkg_remove.list" > "$TMP_DIR/pkg_toremove.list"

# combine our packages with shared installed list, excluding remove
sort -u "$TMP_DIR/mypkgs_with_exclusions_without_remove.txt" "$TMP_DIR/pkg_install.list" | comm -23 - "$TMP_DIR/pkg_remove.list" > "$TMP_DIR/pkg_installed.list"

# list of packages to install, with our blacklist excluded
comm -13 "$TMP_DIR/mypkgs_with_exclusions_without_remove.txt" "$TMP_DIR/pkg_installed.list" | comm -23 - "$TMP_DIR/pkg_blacklist.list" > "$TMP_DIR/pkg_toinstall.list"

# packages already on this computer not in the shared install list we need to put in there
comm -23 "$TMP_DIR/pkg_installed.list" "$TMP_DIR/pkg_install.list" > "$TMP_DIR/pkg_ourinstall.list"

# offer to install missing packages
if [ -s "$TMP_DIR/pkg_toinstall.list" ]
then
    yn=l
    while [[ ! "$yn" =~ ^[YyNnAa]$ ]]
    do
        read -p "Install new packages? (yes/no/list/abort)..." -n 1 yn
        echo
        [[ "$yn" =~ ^[Ll]$ ]] && cat "$TMP_DIR/pkg_toinstall.list"
    done
    [[ "$yn" =~ ^[Yy]$ ]] && sudo pacman -S --needed --confirm - < "$TMP_DIR/pkg_toinstall.list"
    [[ "$yn" =~ ^[Aa]$ ]] && exit 1
fi

# offer to remove packages
if [ -s "$TMP_DIR/pkg_toremove.list" ]
then
    yn=l
    while [[ ! "$yn" =~ ^[YyNnAa]$ ]]
    do
        read -p "Remove packages? (yes/no/list/abort)..." -n 1 yn
        echo
        [[ "$yn" =~ ^[Ll]$ ]] && cat "$TMP_DIR/pkg_toremove.list"
    done
    [[ "$yn" =~ ^[Yy]$ ]] && sudo pacman -Runs --confirm - < "$TMP_DIR/pkg_toremove.list"
    [[ "$yn" =~ ^[Aa]$ ]] && exit 1
fi

# offer to update install list, if it changed
if [ -s "$TMP_DIR/pkg_ourinstall.list" ]
then
    yn=l
    while [[ ! "$yn" =~ ^[YyNnAa]$ ]]
    do
        read -p "Append packages unique to this computer to install list and run finish script? (yes/no/list/abort)..." -n 1 yn
        echo
        [[ "$yn" =~ ^[Ll]$ ]] && cat "$TMP_DIR/pkg_ourinstall.list"
    done
    [[ "$yn" =~ ^[Yy]$ ]] && cat "$TMP_DIR/pkg_ourinstall.list" >> "$INSTALL_LIST"
    [[ "$yn" =~ ^[Aa]$ ]] && exit 1
    [ -x "$FINISH_SCRIPT" ] && "$FINISH_SCRIPT"
fi

rm -f "$TMP_DIR/pkg_exclude.list" "$TMP_DIR/pkg_blacklist.list" "$TMP_DIR/pkg_remove.list" "$TMP_DIR/mypkgs_with_exclusions.txt" "$TMP_DIR/mypkgs_with_exclusions_without_remove.txt" "$TMP_DIR/pkg_toremove.list" "$TMP_DIR/pkg_installed.list" "$TMP_DIR/pkg_toinstall.list" "$TMP_DIR/pkg_ourinstall.list"
