#!/data/data/com.termux/files/usr/bin/bash

rm -rf ~/dotfiles/Documents/termux/
mkdir -p ~/dotfiles/Documents/termux/

cp -rfv ~/.shortcuts ~/dotfiles/Documents/termux/.shortcuts
cp -rfv ~/.termux ~/dotfiles/Documents/termux/.termux

rm -rf ~/dotfiles/Documents/termux/.termux/tasker/slack_token.sh
rm -rf ~/dotfiles/Documents/termux/.termux/tasker/lastfm_token.sh
rm -rf ~/dotfiles/Documents/termux/.termux/tasker/node_modules/csv-simple-parser

cd ~/dotfiles

eval $(okc-ssh-agent)

git add .
git commit -a -m 'Update termux scripts'
git pull
git push
