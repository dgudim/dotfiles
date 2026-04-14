#!/usr/bin/python

import glob
from datetime import datetime, timedelta
import csv
import os
import itertools
import calendar
import math

username = os.environ.get("FULL_NAME")

weekday_map = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}


class ActivityEntry:
    start_datetime: datetime
    end_datetime: datetime
    duration_seconds: float

    def __init__(self, start_datetime: str, end_datetime: str, duration: str):
        self.start_datetime = datetime.strptime(start_datetime, "%Y-%m-%d %H:%M:%S")
        self.end_datetime = datetime.strptime(end_datetime, "%Y-%m-%d %H:%M:%S")
        x = datetime.strptime(duration, "%H:%M:%S")
        self.duration_seconds = timedelta(
            hours=x.hour, minutes=x.minute, seconds=x.second
        ).total_seconds()

    def get_timerange(self) -> str:
        return (
            self.start_datetime.strftime("%H:%M")
            + " - "
            + self.end_datetime.strftime("%H:%M")
        )


def generate_report(year_month: list[str], entries: list[ActivityEntry]):
    month = year_month[1]
    year = year_month[0]

    # Returns weekday (0-6 ~ Mon-Sun) and number of days (28-31) for year, month
    month_range = calendar.monthrange(int(year), int(month))

    first_weekday_number = month_range[0]
    total_days = month_range[1]

    month_range_str = f"{year}-{month} (01.{month} - {total_days}.{month})"
    report = f"Work hours report from {username}\n{month_range_str} \n======================================= \n\n"

    grouped_by_day = dict(
        (key, list(group))
        for key, group in itertools.groupby(
            entries, lambda entry: int(entry.start_datetime.strftime("%d")) - 1
        )
    )

    total_hours = math.ceil(
        (math.fsum(entry.duration_seconds for entry in entries) / 60.0 / 60.0)
    )
    week_seconds = 0.0

    for day in range(0, total_days):
        current_weekday_number = (first_weekday_number + day) % 7

        timerange_str = "none"
        if day in grouped_by_day:
            entries_on_day = grouped_by_day.get(day, [])

            timerange_str = "  ".join(
                str(entry.get_timerange()) for entry in entries_on_day
            )

            week_seconds += math.fsum(
                entry.duration_seconds for entry in entries_on_day
            )

        report += (
            f"\n{day + 1:02d}.{month} {weekday_map[current_weekday_number]}: {timerange_str}"
        )

        if current_weekday_number == 6 or day == total_days - 1:
            report += f"\n\nWEEK (SUB)TOTAL: {round(week_seconds / 60.0 / 60.0)}\n\n"
            week_seconds = 0

    report_filename = f"{username} {month_range_str}.txt"
    with open(report_filename, "w", encoding="UTF-8") as f:
        f.write(report + f"\n=========================\nTOTAL: {total_hours}\n")
        print(f"Wrote report: {report_filename}")


with open(glob.glob("*.csv")[0], newline="", encoding="UTF-8") as csvfile:
    activities = list(csv.reader(csvfile, delimiter=",", quotechar='"'))
    activities.pop(
        0
    )  # Remove header (['activity name', 'time started', 'time ended', 'comment', 'categories', 'record tags', 'duration', 'duration minutes'])

    entries_grouped = dict(
        (key, list(group))
        for key, group in itertools.groupby(
            (
                ActivityEntry(activity[1], activity[2], activity[6])
                for activity in activities
                if activity[0].lower().strip() == "work"
            ),
            lambda entry: entry.start_datetime.strftime("%Y-%m"),
        )
    )

    _ = [
        generate_report(year_month.split("-"), entries)
        for year_month, entries in entries_grouped.items()
    ]
