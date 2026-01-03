#!/data/data/com.termux/files/usr/bin/bash
PENDING_ARTSTATION_IMAGES_FILE_LOCATION="~/storage/downloads/artworks/pending.txt"
PIXIV_IMAGES_SOURCE_DIR="~/storage/shared/Pictures/PixivFunc/"
BASE_PERSONAL_DIR="/storage/3538-3530/Documents/personal"

mkdir -pv ~/.temp_artwork_downloader
cp -fv ~/dotfiles/Documents/exact_usefull_files/exact_scripts/artwork_downloader/download_and_sort.py ~/.temp_artwork_downloader/download_and_sort.py

cd ~/.temp_artwork_downloader
uv run download_and_sort.py

