#!/bin/bash
sleep 30
kdialog --password "KeePass DB pass" | keepassxc --pw-stdin /home/kloud/Documents/shared/_Personal/keepass.kdbx
