#!/usr/bin/python

import dbus
from dbus.mainloop.glib import DBusGMainLoop
import os
import sys


def pause_media():
    os.system("playerctl pause")


def turn_off_keyboard_backlight():
    os.system('brightnessctl --device "tpacpi::kbd_backlight" set 0')


def main():
    if len(sys.argv) != 2:
        print("Wrong number of arguments!")
        sys.exit(1)

    event = sys.argv[1]

    if "HEADPHONE unplug" in event:
        pause_media()
        return

    if "LID open" in event:
        turn_off_keyboard_backlight()
        return


if __name__ == "__main__":
    main()
