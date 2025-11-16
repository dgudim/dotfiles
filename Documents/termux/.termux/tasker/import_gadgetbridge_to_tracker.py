#!/usr/bin/venv python3

import json
from pathlib import Path
import sqlite3
import os
import time
import datetime

TINY_EVENT_THRESHOLD = 120  # 2 min
SLEEP_BREAK_THRESH = 7200  # 2 hours
GAP_THRESHOLD = 60  # 1 min

source_file = Path(os.environ.get("SOURCE_FILE", "Gadgetbridge.db"))

db = sqlite3.connect(source_file)

cur = db.execute(
    "select TIMESTAMP, OTHER_TIMESTAMP, RAW_KIND from HUAWEI_ACTIVITY_SAMPLE where RAW_KIND in (6, 7) order by TIMESTAMP asc"
)
rows = cur.fetchall()

imported_rows_json = Path("imported_rows.json")
if not imported_rows_json.exists():
    imported_rows_json.write_text("{}", encoding="utf-8")

inserted_rows = json.loads(imported_rows_json.read_text("utf-8"))

last_end = 0
last_start = 0
event_time_extension = 0

rows = [row for row in rows if row[0] < row[1]]  # Filter out invalid rows
filtered_rows = []

for i, row in enumerate(rows):
    if row[0] == last_start:
        last_end = max(last_end, row[1])
        print(f"Updating end time of a duplicate record ({row[1]} -> {last_end})")
        if (
            i == len(rows) - 1 or rows[i + 1][0] != last_start
        ):  # If next entry is not a duplicate of there is no next entry, add the current combined entry
            filtered_rows.append((last_start, last_end, row[2]))
        continue

    if (
        i == len(rows) - 1 or rows[i + 1][0] != row[0]
    ):  # If the next entry is not a duplicate or there is no next entry, add the row, we are safe here. If it is a duplicate, don't add, it will be handled by the upper 'if''
        filtered_rows.append(row)

    last_start = row[0]
    last_end = row[1]

print(f"STAGE 1 completed, merged {len(rows) - len(filtered_rows)} duplicate rows")
rows = filtered_rows
filtered_rows = []

corrected = 0
for i, row in enumerate(rows):
    if i >= len(rows) - 1:
        filtered_rows.append(row)
        break

    next_row = rows[i + 1]

    if row[1] > next_row[0]:  # Overlap between 2 events (end > next start)
        print("Correcting overlap between rows")
        filtered_rows.append((row[0], next_row[0], row[2]))
    else:
        filtered_rows.append(row)

print(f"STAGE 1.1 completed, corrected {corrected} rows")
rows = filtered_rows
filtered_rows = []

merged = 0
breaks = 0

for i, row in enumerate(rows):
    start = row[0]
    end = row[1]
    duration = end - start

    sleep_type = row[2]

    if (
        i < len(rows) - 1
        and duration <= TINY_EVENT_THRESHOLD  # Take small events
        and rows[i + 1][0] - end < SLEEP_BREAK_THRESH  # Don't add to the next sleep session
    ):
        event_time_extension += duration
        merged += 1
        # print("Filtering out short row, appending to next")
        continue

    start -= event_time_extension
    event_time_extension = 0

    if (
        start - last_end > GAP_THRESHOLD and start - last_end < SLEEP_BREAK_THRESH
    ):  # Max break: 30 min
        # print("Adding a break")
        breaks += 1
        filtered_rows.append((last_end, start, -1))

    last_end = end

    if (
        duration <= TINY_EVENT_THRESHOLD
    ):  # The last event in the session, extend the last event
        last_row = filtered_rows[-1]
        filtered_rows[-1] = (last_row[0], end, last_row[2])
        merged += 1
    else:
        # print("Adding normal row")
        filtered_rows.append((start, end, sleep_type))

print(f"STAGE 2 completed, merged {merged} tiny rows")
print(f"STAGE 2.2 completed, added {breaks} breaks")
rows = filtered_rows
filtered_rows = []

for i, row in enumerate(rows):
    start = row[0]
    end = row[1]
    duration = end - start

    sleep_type = row[2]

    if (
        i < len(rows) - 1
        and rows[i + 1][2] == sleep_type
        and rows[i + 1][0] - end < GAP_THRESHOLD
    ):
        event_time_extension += duration
        # print(
        #     f"Filtering out same type row, appending to next ({rows[i + 1][0] - end})"
        # )
        continue

    start -= event_time_extension
    event_time_extension = 0

    filtered_rows.append((start, end, sleep_type))

print(
    f"STAGE 3 completed, merged {len(rows) - len(filtered_rows)} same adjacent rows, final num: {len(filtered_rows)} rows"
)

# starts = [row[0] - 1714100000 for i, row in enumerate(filtered_rows) if i < 60]
# ends = [row[1] - 1714100000 for i, row in enumerate(filtered_rows) if i < 60]
# types = [row[2] for i, row in enumerate(filtered_rows) if i < 60]
#
# import matplotlib.pyplot as plt
# import pandas as pd
#
# df = pd.DataFrame({"begin": starts, "end": ends})
#
# fig, ax = plt.subplots()
#
# for i, (x_1, x_2, typ) in enumerate(zip(starts, ends, types)):
#     ax.add_patch(plt.Rectangle((x_1, 0), x_2 - x_1, 1)).set_color(
#         (i / 60, 0, 1)
#         if typ == 6
#         else ((1, i / 60, 0) if typ == 7 else (0.5, 0.5, i / 60))
#     )
#
# ax.autoscale()
# ax.set_ylim(0, 1)
# plt.show()
#
# exit(0)

total_rows = len(filtered_rows)
inserted = 0
print(f"Processing {total_rows} rows")

for i, row in enumerate(filtered_rows):
    if str(row) in inserted_rows:
        continue

    inserted_rows[str(row)] = ""
    inserted += 1

    start = row[0]
    end = row[1]

    length_minutes = (end - start) / 60
    if length_minutes <= 5:
        length_tag = "Very short"
    elif length_minutes <= 10:
        length_tag = "Short"
    elif length_minutes <= 20:
        length_tag = "Medium"
    elif length_minutes <= 30:
        length_tag = "Long"
    else:
        length_tag = "Very long"

    match row[2]:
        case 6:
            sleeptype = "Light"
        case 7:
            sleeptype = "Deep"
        case _:
            sleeptype = None

    if sleeptype is None:
        print("Inserting break")
        os.system(
            f"am broadcast -a com.razeeman.util.simpletimetracker.ACTION_ADD_RECORD \
--es extra_activity_name 'Sleep break' \
--es extra_record_time_started '{start * 1000}' \
--es extra_record_time_ended '{end * 1000}' \
--es extra_record_tag '{length_tag}' \
com.razeeman.util.simpletimetracker"
        )
        continue

    print(
        f"Importing row: {row} ({sleeptype} sleep) ({datetime.datetime.fromtimestamp(start)} - {datetime.datetime.fromtimestamp(end)}) ({i}/{total_rows}/{int(i/total_rows * 100)}%)"
    )
    os.system(
        f"am broadcast -a com.razeeman.util.simpletimetracker.ACTION_ADD_RECORD \
--es extra_activity_name '{sleeptype} sleep' \
--es extra_record_time_started '{start * 1000}' \
--es extra_record_time_ended '{end * 1000}' \
--es extra_record_tag '{length_tag}' \
com.razeeman.util.simpletimetracker"
    )

    time.sleep(0.05)

print(f"Inserted {inserted} rows")

imported_rows_json.write_text(json.dumps(inserted_rows), encoding="utf-8")

db.close()
