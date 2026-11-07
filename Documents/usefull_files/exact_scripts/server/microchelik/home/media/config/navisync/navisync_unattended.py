#!/usr/bin/env python3
import builtins
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request

APP = "/app"
STATE = "/state"

SAFE_ANSWERS = [
    # Only reached with AUTO_CONFIRM off, or before loving Navidrome stars on
    # Last.fm (SYNC_LOVED_TO_LASTFM).
    (r"Proceed with", lambda: "y" if os.getenv("AUTO_CONFIRM") == "True" else "n"),
    # A loved track exists on several albums: star all of them
    (r"Select which version\(s\) to star", lambda: "A"),
    # PLAYCOUNT_CONFLICT_RESOLUTION=ask: keep Navidrome's higher count
    (r"Keep Navidrome \(N\) or use Last\.fm \(L\)", lambda: "N"),
]


class ErrorWatch:
    def __init__(self, stream):
        self.stream = stream

    def write(self, text):
        written = self.stream.write(text)
        if "❌" in text:
            self.stream.write("\n   Stopping here so nothing is written after an error.\n")
            self.stream.flush()
            raise SystemExit(1)
        return written

    def __getattr__(self, name):
        return getattr(self.stream, name)


def unattended_input(prompt=""):
    for pattern, answer in SAFE_ANSWERS:
        if re.search(pattern, prompt):
            reply = answer()
            print(f"{prompt}{reply}   (answered automatically)")
            return reply
    raise SystemExit(
        "\n❌ NaviSync asked a question that has no unattended answer:\n"
        f"   {prompt.strip()}\n"
        "   Answer it in an interactive run."
    )


def send_recent_plays_to_spindle(navidrome_db, spindle_url, secret, days=60):
    """Send the last `days` of Navidrome's play history to Spindle's ingest API.

    That's how plays from other players (via Last.fm and NaviSync) reach
    Spindle. Each play keeps Navidrome's track and start time, so Spindle skips
    the ones its plugin already reported. Resending the window every run is
    harmless and catches up after missed runs.
    """
    since = int(time.time()) - days * 86400
    db = sqlite3.connect(f"file:{navidrome_db}?mode=ro", uri=True)
    try:
        plays = db.execute("""SELECT s.submission_time, u.user_name, s.media_file_id
            FROM scrobbles s JOIN user u ON u.id = s.user_id
            WHERE s.submission_time >= ? ORDER BY s.submission_time""", (since,)).fetchall()
    finally:
        db.close()
    added = 0
    for played_at, user, track_id in plays:
        body = json.dumps({"played_at": played_at, "user": user, "nd_track_id": track_id}).encode()
        req = urllib.request.Request(f"{spindle_url}/ingest", data=body, method="POST",
                                     headers={"Content-Type": "application/json", "X-Spindle-Secret": secret})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                added += json.load(resp).get("inserted", False)
        except (urllib.error.URLError, OSError) as e:
            print(f"❌ Couldn't send plays to Spindle at {spindle_url}: {e}")
    print(f"📊 Spindle: sent {len(plays)} plays from the last {days} days, {added} were new")


def main():
    for sub in ("cache", "json"):
        os.makedirs(os.path.join(STATE, sub), exist_ok=True)

    version = os.path.join(APP, "VERSION")
    if os.path.exists(version):
        print(open(version).read().strip())

    sys.stdout = ErrorWatch(sys.stdout)

    if not sys.stdin.isatty():
        builtins.input = unattended_input

    os.chdir(APP)
    sys.path.insert(0, APP)
    import main as navisync  # NaviSync's main.py

    navisync.main()

    spindle_url = os.getenv("SPINDLE_URL")
    if spindle_url:
        send_recent_plays_to_spindle(os.getenv("NAVIDROME_DB_PATH"), spindle_url,
                                     os.getenv("SPINDLE_INGEST_SECRET", ""))


if __name__ == "__main__":
    main()
