#!/bin/bash

for i in $(seq $(notify-send -p " " -t 1) -1 0);
  do qdbus org.kde.plasmashell /org/freedesktop/Notifications org.freedesktop.Notifications.CloseNotification $i;
done
