#!/bin/bash

#Declare a string array
bloat=(         "com.samsung.android.bixby.service"
                "com.samsung.android.bixby.agent"
                "com.samsung.android.bixby.wakeup"
                "com.samsung.android.aremojieditor"
                "com.samsung.android.aremoji"
                "com.samsung.android.livestickers"
                "com.samsung.android.stickercenter"
                "com.sec.android.mimage.avatarstickers"
                "com.samsung.android.arzone"
                "com.samsung.android.ardrawing"
                "com.microsoft.skydrive"
                "com.microsoft.appmanager"
                "com.samsung.android.app.spage"
                "com.samsung.android.mateagent"
                "com.samsung.android.mdx"
                "com.samsung.android.accessibility.talkback"
                "ru.yandex.searchplugin"
				"com.facebook.system"
                "com.facebook.appmanager"
                "com.facebook.services"
                "com.facebook.katana"
                "com.aura.oobe.samsung.gl"
                "com.snap.camerakit.plugin.v1"
                "com.samsung.android.mcfds"
                "com.samsung.android.ipsgeofence"
				"com.samsung.android.service.health"
				"com.samsung.android.inputshare"
				"com.samsung.android.rubin.app"
				"com.samsung.android.knox.analytics.uploader")

semibloat=(
                "com.samsung.android.game.gametools"
				"com.samsung.android.game.gamehome"
				"com.samsung.android.game.gos"
				"com.samsung.android.app.tips"
				"com.samsung.android.app.reminder"
				"com.samsung.android.app.routines"
)


for app in "${bloat[@]}"; do
    echo installing $app to clear data
    adb shell pm install-existing --user 0 $app
    echo clearing $app
    adb shell pm clear $app
    echo removing $app
    adb shell pm uninstall --user 0 $app
    echo
done
echo ""
