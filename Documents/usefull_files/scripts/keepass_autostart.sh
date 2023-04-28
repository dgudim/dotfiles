#!/bin/bash
sleep 30
secret-tool lookup user kloud | keepassxc --pw-stdin /home/kloud/Documents/shared/_Personal/keepass.kdbx
