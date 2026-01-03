#!/data/data/com.termux/files/usr/bin/bash
export PENDING_ARTSTATION_IMAGES_FILE_LOCATION="$HOME/storage/downloads/artworks/pending.txt"
export PIXIV_IMAGES_SOURCE_DIR="$HOME/storage/shared/Pictures/PixivFunc/"
export BASE_PERSONAL_DIR="/storage/3538-3530/Documents/personal"

mkdir -pv ~/.temp_artwork_downloader
cp -fv ~/dotfiles/Documents/exact_usefull_files/exact_scripts/artwork_downloader/download_and_sort.py ~/.temp_artwork_downloader/download_and_sort.py

cd ~/.temp_artwork_downloader
uv run download_and_sort.py

