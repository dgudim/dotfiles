#!/usr/bin/python

import dbus
from dbus.mainloop.glib import DBusGMainLoop
import os
import sys


def pause_media():
    os.system("playerctl pause")


def turn_off_keyboard_backlight():
    command = 'qdbus org.kde.kglobalaccel /component/org_kde_powerdevil org.kde.kglobalaccel.Component.invokeShortcut "Decrease Keyboard Brightness"'
    os.system(f"sleep 2 && {command}")
    os.system(f"sleep 3 && {command}")
    # os.system('sleep 3 && brightnessctl --device "tpacpi::kbd_backlight" set 0')


def main():
    if len(sys.argv) != 2:
        print("Wrong number of arguments!")
        sys.exit(1)

    event = sys.argv[1]

    if "HEADPHONE" in event and "unplug" in event:
        pause_media()
        return

    if "LID" in event and "open" in event:
        turn_off_keyboard_backlight()
        return


if __name__ == "__main__":
    main()
