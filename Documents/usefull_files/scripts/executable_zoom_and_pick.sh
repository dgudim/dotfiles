#!/bin/bash

qdbus org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_in"
qdbus org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_in"
qdbus org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_in"
qdbus org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_in"
qdbus org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_in"

qdbus org.kde.klipper /klipper setClipboardContents "#$(printf '%x\n' $(qdbus --literal org.kde.KWin /ColorPicker pick | grep -o '\d*' ) | cut -c 3-)"

qdbus org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_out"
qdbus org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_out"
qdbus org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_out"
qdbus org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_out"
qdbus org.kde.kglobalaccel /component/kwin invokeShortcut "view_zoom_out"
