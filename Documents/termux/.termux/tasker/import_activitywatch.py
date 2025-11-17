#!/usr/bin/env -S uv run --script

#
# dependencies = [
#   "aw_client",
#   "python-dateutil"
# ]
# ///

from dataclasses import dataclass, field
import datetime
import os
import time
from dateutil import tz
from pathlib import Path
import sys
from aw_client import ActivityWatchClient
from aw_core import Event

TARGET_BUCKET = "aw-watcher-android-test"
CHUNK_MERGE_THRESHOLD = datetime.timedelta(minutes=11)
CHUNK_MERGE_THRESHOLD_SEC = CHUNK_MERGE_THRESHOLD.total_seconds()

CHUNK_LENGTH_THRESHOLD_SEC = 60 * 3


@dataclass
class Chunk:
    start: datetime.datetime
    end: datetime.datetime


@dataclass
class AppEntry:
    activity_name: str
    matching_names: list[str]
    events: list[Event] = field(default_factory=list)
    chunks: list[Chunk] = field(default_factory=list)

    def consume_if_matches(self, event: Event):
        event_app_name = str(event.data["app"]).lower()
        for search_str in self.matching_names:
            if search_str.lower() in event_app_name:
                self.events.append(event)
                break

    def load_chunks(self):
        print(f" = Chunking {self.activity_name}...")

        current_chunk: Chunk | None = None
        for event in reversed(self.events):  # Events are stored from newest to oldest
            event_start = event.timestamp
            event_end = event.timestamp + event.duration
            if current_chunk is None:
                current_chunk = Chunk(start=event_start, end=event_end)
            elif current_chunk.end + CHUNK_MERGE_THRESHOLD >= event_start:
                current_chunk.end = event_end
            else:
                self.chunks.append(current_chunk)
                current_chunk = Chunk(start=event_start, end=event_end)

        if current_chunk is not None:
            self.chunks.append(current_chunk)

    def load_into_timetracker(self):
        print(f"Creating {len(self.chunks)} events in the time tracker for {self.activity_name}...")

        TOTAL_CHUNKS = len(self.chunks)

        for i, chunk in enumerate(self.chunks):
            start = chunk.start
            end = chunk.end

            if (end - start).total_seconds() < CHUNK_LENGTH_THRESHOLD_SEC:
                print(f"Chunk {i} of {self.activity_name} is too short, skipping")
                continue

            length_seconds = (end - start).total_seconds()
            if length_seconds <= 5 * 60:
                LENGTH_TAG = "Very short"
            elif length_seconds <= 10 * 60:
                LENGTH_TAG = "Short"
            elif length_seconds <= 20 * 60:
                LENGTH_TAG = "Medium"
            elif length_seconds <= 30 * 60:
                LENGTH_TAG = "Long"
            else:
                LENGTH_TAG = "Very long"

            print(f"Inserting chunk {start} - {end} for {self.activity_name}")
            print(f"Importing chunk: {start} - {end} ({i}/{TOTAL_CHUNKS}/{int(i / TOTAL_CHUNKS * 100)}%)")
            os.system(
                f"am broadcast -a com.razeeman.util.simpletimetracker.ACTION_ADD_RECORD \
        --es extra_activity_name '{self.activity_name}' \
        --es extra_record_time_started '{int(start.timestamp() * 1000)}' \
        --es extra_record_time_ended '{int(end.timestamp() * 1000)}' \
        --es extra_record_tag '{LENGTH_TAG}' \
        com.razeeman.util.simpletimetracker"
            )

            time.sleep(0.05)


app_map: list[AppEntry] = [
    AppEntry(activity_name="YouTube", matching_names=["UwUTube", "YouTube"]),
    AppEntry(activity_name="Browsing", matching_names=["Chrome", "Cromite", "Firefox", "chromium"]),
    AppEntry(activity_name="News", matching_names=["Feeder", "YouTube"]),
    AppEntry(activity_name="IM", matching_names=["Nagram", "Discord", "Aliucord", "UwUCord"]),
]


TZ = tz.tzutc()


last_import_timestamp_file = Path("./last_import_aw_timstamp.txt")
last_import_dt_utc = datetime.datetime.fromtimestamp(0, tz=TZ)

if last_import_timestamp_file.exists():
    last_import_dt_utc = datetime.datetime.fromtimestamp(
        int(last_import_timestamp_file.read_text(encoding="utf8").strip()), tz=TZ
    )

current_dt = datetime.datetime.now(tz=TZ)
today = current_dt.date()
max_import_up_to: datetime.datetime = datetime.datetime(today.year, today.month, today.day, tzinfo=TZ)

if last_import_dt_utc >= max_import_up_to:
    print("Already imported")
    sys.exit(0)

client = ActivityWatchClient("importer", testing=True, port=5600)  # Safe mode

# Get buckets
buckets = client.get_buckets()

print("Available buckets:", list(buckets.keys()))

selected_bucket = None

for bucket_key in buckets:
    if bucket_key == TARGET_BUCKET:
        selected_bucket = buckets[bucket_key]
        break

print()

if selected_bucket is None:
    print(f"Could not find target bucket: {TARGET_BUCKET}")
    sys.exit(1)
else:
    print(f"Getting events from {TARGET_BUCKET} ({last_import_dt_utc} - {max_import_up_to})")

# Get raw events from a bucket
events = client.get_events(TARGET_BUCKET, start=last_import_dt_utc, end=max_import_up_to)

print(f"\nGot {len(events)} events")
print("Categorizing...")

for _event in events:
    for app_class in app_map:
        app_class.consume_if_matches(_event)

print("Post-processing...")

for app_class in app_map:
    print(f"\n - {app_class.activity_name}: {len(app_class.events)} events")
    app_class.load_chunks()
    print(f" + {app_class.activity_name}: {len(app_class.chunks)} chunks")

print("\nSending to time tracker...")

for app_class in app_map:
    app_class.load_into_timetracker()

print("Saving checkpoint")
last_import_timestamp_file.write_text(str(max_import_up_to.timestamp()), encoding="utf8")
print("DONE!")
