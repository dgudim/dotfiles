#!/bin/bash

set -e

RAW_URL=$1
PROCESSED_URL=$(echo "$RAW_URL" | sed -e "s/\?.*//" -e "s/large/4k/" )

FILENAME=$(wget "$PROCESSED_URL" 2>&1 | grep 'Saving to' | grep -Eo '‘.*?’' | sed -e 's/’//' -e 's/‘//')

if [ ! -f "$FILENAME" ]; then
    echo "$FILENAME not found!"
    exit 1
fi

TARGET_FILE="./out/${FILENAME//png/jpeg}"

SKIP_MAGICK=$2

mkdir -p out
if [ -z ${SKIP_MAGICK+x} ]; then
  magick "$FILENAME" -fuzz 3% -trim -quality 100 "$TARGET_FILE" && rm "$FILENAME"
else
  mv "$FILENAME" "$TARGET_FILE"
fi

echo "Done"
