#!/usr/bin/venv python3
import datetime
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from dateutil import tz


@dataclass
class ScrobbleRecord:
    dt: int
    song_name: str
    artist: str

    def get_comment_entry(self):
        return f"{datetime.datetime.fromtimestamp(self.dt, tz=tz.tzutc()).strftime('%H:%M')}: {self.artist} - {self.song_name}"

    def dt_projected_end(self):
        return min(self.dt + avg_song_duration_seconds, max_import_up_to)


api_key = os.environ["LASTFM_API_KEY"]
username = "Kl0ud_"
chunk_merge_threshold_seconds = 60 * 8    # 8 minutes DON'T CHANGE THIS OR REIMPORT EVERYTHING. Used as a 'duration tag length multiplier' as well
avg_song_duration_seconds = int(60 * 3.5) # 3.5 minutes

last_import_timestamp_file = Path("./last_import_lastfm_timstamp.txt")
last_import_timestamp_dt_utc = 0

if last_import_timestamp_file.exists():
    last_import_timestamp_dt_utc = int(last_import_timestamp_file.read_text(encoding="utf8").strip())

current_dt = datetime.datetime.now(tz=tz.tzutc())
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
            tracks = [
                ScrobbleRecord(dt=int(track["date"]["uts"]), artist=track["artist"]["#text"], song_name=track["name"])
                for track in json_data["track"]
                if "date" in track
            ]
            return tracks, int(total_pages_d)
        except Exception as e:
            print(f"Error getting page {page} from lastfm", e)
            time.sleep((iter_ + 1) * 2)

    return None


total_pages_tp = get_page(1, 500)
if total_pages_tp is None:
    print("Failed getting total page number")
    sys.exit(1)


@dataclass
class Chunk:
    start: int
    end: int
    comment: str

    def get_escaped_comment(self):
        return self.comment.replace("'", "").replace('"', "")


all_scrobbles: list[ScrobbleRecord] = []
chunks: list[Chunk] = []

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

current_chunk: Chunk | None = None
for scrobble in reversed(all_scrobbles):  # API returns the list from newest to oldest
    if current_chunk is None:
        current_chunk = Chunk(start=scrobble.dt, end=scrobble.dt_projected_end(), comment=scrobble.get_comment_entry())
    elif current_chunk.end + chunk_merge_threshold_seconds >= scrobble.dt:
        current_chunk.end = scrobble.dt_projected_end()
        current_chunk.comment += f"\n{scrobble.get_comment_entry()}"
    else:
        chunks.append(current_chunk)
        current_chunk = Chunk(start=scrobble.dt, end=scrobble.dt_projected_end(), comment=scrobble.get_comment_entry())

if current_chunk is not None:
    chunks.append(current_chunk)

print("Done!")
print("Importing into time tracker")

TOTAL_CHUNKS = len(chunks)
print(f"Processing {TOTAL_CHUNKS} chunks")

for i, chunk in enumerate(chunks):
    start = chunk.start
    end = chunk.end

    length_seconds = end - start
    if length_seconds <= 5 * chunk_merge_threshold_seconds:
        LENGTH_TAG = "Very short"
    elif length_seconds <= 10 * chunk_merge_threshold_seconds:
        LENGTH_TAG = "Short"
    elif length_seconds <= 20 * chunk_merge_threshold_seconds:
        LENGTH_TAG = "Medium"
    elif length_seconds <= 30 * chunk_merge_threshold_seconds:
        LENGTH_TAG = "Long"
    else:
        LENGTH_TAG = "Very long"

    print(f"Inserting chunk {start} - {end}")
    print(
        f"Importing chunk: {start} - {end} ({datetime.datetime.fromtimestamp(start)} - {datetime.datetime.fromtimestamp(end)}) ({i}/{TOTAL_CHUNKS}/{int(i / TOTAL_CHUNKS * 100)}%)"
    )
    os.system(
        f"am broadcast -a com.razeeman.util.simpletimetracker.ACTION_ADD_RECORD \
--es extra_activity_name 'Music' \
--es extra_record_time_started '{start * 1000}' \
--es extra_record_time_ended '{end * 1000}' \
--es extra_record_tag '{LENGTH_TAG}' \
--es extra_record_comment '{chunk.get_escaped_comment()}' \
com.razeeman.util.simpletimetracker"
    )

    time.sleep(0.05)

print("Saving checkpoint")
last_import_timestamp_file.write_text(str(max_import_up_to), encoding="utf8")
print("DONE!")
