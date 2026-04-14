#!/bin/bash

qdbus6 org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_in"
qdbus6 org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_in"
qdbus6 org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_in"
qdbus6 org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_in"
qdbus6 org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_in"

qdbus6 org.kde.klipper /klipper setClipboardContents "#$(printf '%x\n' $(qdbus6 --literal org.kde.KWin /ColorPicker pick | grep -o '\d*' ) | cut -c 3-)"

qdbus6 org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_out"
qdbus6 org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_out"
qdbus6 org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_out"
qdbus6 org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_out"
qdbus6 org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_out"
