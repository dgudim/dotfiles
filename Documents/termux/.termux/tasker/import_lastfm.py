#!/usr/bin/venv python3
from dataclasses import dataclass
import datetime
from pathlib import Path

import requests
from dateutil import tz

import sys
import os
import time


@dataclass
class ScrobbleRecord:
    dt: int


api_key = os.environ["LASTFM_API_KEY"]
username = "Kl0ud_"
chunk_merge_threshold = 60 * 6  # 6 minutes

last_import_timestamp_file = Path("./last_import_lastfm_timstamp.txt")
last_import_timestamp_dt_utc = 0

if last_import_timestamp_file.exists():
    last_import_timestamp_dt_utc = int(last_import_timestamp_file.read_text(encoding="utf8").strip())

current_dt = datetime.datetime.now(tz=datetime.timezone.utc)
today = current_dt.date()
max_import_up_to = int(datetime.datetime(today.year, today.month, today.day, tzinfo=tz.tzutc()).timestamp())

if last_import_timestamp_dt_utc >= max_import_up_to:
    print("Already imported")
    sys.exit(0)


def get_page(page: int, limit: int) -> tuple[list[ScrobbleRecord], int] | None:
    for iter_ in range(5):
        try:
            response = requests.post(
                f"https://ws.audioscrobbler.com/2.0/?api_key={api_key}&method=User.getrecenttracks&extended=0&user={username}&page={page}&format=json&limit={limit}&from={last_import_timestamp_dt_utc}&to={max_import_up_to}",
                timeout=30,
            )
            response.raise_for_status()
            json_data = response.json()
            json_data = json_data["recenttracks"]
            total_pages_d = json_data["@attr"]["totalPages"]
            tracks = [ScrobbleRecord(dt=int(track["date"]["uts"])) for track in json_data["track"] if "date" in track]
            return tracks, int(total_pages_d)
        except Exception as e:
            print(f"Error getting page {page} from lastfm", e)
            time.sleep((iter_ + 1) * 2)

    return None


total_pages_tp = get_page(1, 500)
if total_pages_tp is None:
    print("Failed getting total page number")
    sys.exit(1)

all_scrobbles: list[ScrobbleRecord] = []
chunks: list[tuple[int, int]] = []

for i in range(total_pages_tp[1]):
    p = i + 1

    print(f"Getting page: {p}/{total_pages_tp[1]}")

    current_page = get_page(p, 500)
    if current_page is None:
        print("Import failed")
        sys.exit(1)

    all_scrobbles += current_page[0]
    print(f"{len(all_scrobbles)} scrobbles")

print("Chunking...")

current_chunk_start = 0
current_chunk_end = 0
for scrobble in reversed(all_scrobbles):  # API returns the list from newest to oldest
    if current_chunk_start == 0:
        current_chunk_start = scrobble.dt
        current_chunk_end = scrobble.dt
    elif scrobble.dt - current_chunk_end <= chunk_merge_threshold:
        current_chunk_end = scrobble.dt
    else:
        chunks.append((current_chunk_start, current_chunk_end + chunk_merge_threshold))
        current_chunk_start = 0
        current_chunk_end = 0

if current_chunk_end != 0:
    chunks.append((current_chunk_start, current_chunk_end + chunk_merge_threshold))

print("Done!")
print("Importing into time tracker")

print(f"Processing {len(chunks)} chunks")

for chunk in chunks:
    start = chunk[0]
    end = chunk[1]

    length_minutes = (end - start) / 60
    if length_minutes <= 5 * chunk_merge_threshold:
        LENGTH_TAG = "Very short"
    elif length_minutes <= 10 * chunk_merge_threshold:
        LENGTH_TAG = "Short"
    elif length_minutes <= 20 * chunk_merge_threshold:
        LENGTH_TAG = "Medium"
    elif length_minutes <= 30 * chunk_merge_threshold:
        LENGTH_TAG = "Long"
    else:
        LENGTH_TAG = "Very long"

    print("Inserting chunk {start} - {end}")
    os.system(
        f"am broadcast -a com.razeeman.util.simpletimetracker.ACTION_ADD_RECORD \
--es extra_activity_name 'Music' \
--es extra_record_time_started '{start * 1000}' \
--es extra_record_time_ended '{end * 1000}' \
--es extra_record_tag '{LENGTH_TAG}' \
com.razeeman.util.simpletimetracker"
    )

    time.sleep(0.05)

print("Saving checkpoint")
last_import_timestamp_file.write_text(str(max_import_up_to), encoding='utf8')
print("DONE!")

