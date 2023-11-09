#!/bin/bash

echo "Executing migrations..."
rm -fv ~/.config/environment.d/xdg.conf
rm -fv ~/.bash_history
if [ -f "/root/.bash_history" ] ; then
    sudo rm -fv /root/.bash_history
fi
rm -fv ~/.config/dragonplayerrc
echo "Done!"
