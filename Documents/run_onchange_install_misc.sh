
{{ if (or (eq .chezmoi.hostname "sauron") (eq .chezmoi.hostname "portable-heater")) }}
adwaita-steam-gtk --install
adwaita-steam-gtk --update
{{ end }}

wineasio-register
# setup_dxvk install
# https://askubuntu.com/questions/299286/how-to-recover-focus-after-losing-it-while-using-wine
wine reg add 'HKEY_CURRENT_USER\Software\Wine\X11 Driver' /t REG_SZ /v UseTakeFocus /d N /f

# waydroid prop set persist.waydroid.multi_windows true
#
# default (/etc/machine-id)-*-arch*-*.conf
# timeout 5
# console-mode max
#
# Crontab:
# disable usb wakeup: @reboot sleep 10 && echo "XHC" > /proc/acpi/wakeup

# Polkit-1  /usr/lib/pam.d/polkit-1

## Rootless docker
sudo usermod --add-subuids 100000-165535 --add-subgids 100000-165535 $USER
