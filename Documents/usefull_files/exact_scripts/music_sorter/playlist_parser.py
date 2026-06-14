#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from yt_dlp import YoutubeDL
from mutagen.oggopus import OggOpus

# A timestamp like 1:23 or 01:02:03
TIMESTAMP_RE = re.compile(r"(?:\d{1,2}:)?\d{1,2}:\d{2}")
# Leading track numbering like "1.", "01)", "1 -" at the start of a line.
LEADING_INDEX_RE = re.compile(r"^\s*\d{1,3}\s*[.):\-]\s*")
# Wrapping brackets [0:00], (0:00).
BRACKETED_TS_RE = re.compile(r"[\[(]\s*(?:\d{1,2}:)?\d{1,2}:\d{2}\s*[\])]")

EXCLUDED_RESULT_PHRASES = ("chill mix", "432 hz", "432hz")

# A YouTube search result is only accepted when its title is at least this
# similar to the track title; below this it is treated as "not found" rather
# than accepting a junk result.
MIN_SEARCH_SCORE = 0.5

DEFAULT_MUSIC_DIR = "/home/kloud/Documents/shared/_Music"

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = Path("playlists")
DOWNLOAD_DIR = SCRIPT_DIR / "music"

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".opus", ".oga", ".ogg", ".flac", ".wav", ".webm"}

# How similar a normalised title and filename must be to count as a match.
DEFAULT_MATCH_THRESHOLD = 0.86

FILENAME_NOISE_RE = re.compile(
    r"""
    \([^)]*\)            # ( ... )
    | \[[^\]]*\]         # [ ... ]
    | _\d{2,4}k          # bitrate suffix like _128k
    | \b(?:official|music|video|lyric|lyrics|audio|hd|hq|4k|8k|remaster
          |remastered|visualizer|mv|feat|ft|featuring)\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass
class Track:
    """A parsed track plus its matched YouTube video and local file (if any)."""

    index: int
    title: str
    source: str  # "chapters" or "description"
    start_time: float | None = None
    matched_title: str | None = None
    matched_url: str | None = None
    matched_id: str | None = None
    matched_duration: float | None = None
    match_score: float | None = None
    local_path: str | None = None
    local_score: float | None = None


# --------------------------------------------------------------------------- #
# Metadata fetching
# --------------------------------------------------------------------------- #
def fetch_info(url: str) -> dict:
    """Fetch full video metadata without downloading the media."""
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "extract_flat": False,
    }
    with YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


# --------------------------------------------------------------------------- #
# Title cleaning
# --------------------------------------------------------------------------- #
def clean_title(raw: str) -> str:
    """Normalise a chapter/description line into a searchable track title."""
    title = raw.strip()
    title = BRACKETED_TS_RE.sub("", title)
    title = TIMESTAMP_RE.sub("", title)
    title = LEADING_INDEX_RE.sub("", title)
    # Collapse leftover separators and whitespace.
    title = title.strip(" \t-–—|·•:.")
    title = re.sub(r"\s{2,}", " ", title)
    return title.strip()


def is_non_music_title(title: str) -> bool:
    """Filter out non-track chapter labels (intros, outros, etc.)."""
    if len(title) < 2:
        return True
    lowered = title.lower()
    noise = {"intro", "outro", "start", "end", "tracklist", "track list"}
    return lowered in noise


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def parse_chapters(info: dict) -> list[Track]:
    chapters = info.get("chapters") or []
    tracks: list[Track] = []
    for ch in chapters:
        title = clean_title(ch.get("title", ""))
        if not title or is_non_music_title(title):
            continue
        tracks.append(
            Track(
                index=len(tracks) + 1,
                title=title,
                source="chapters",
                start_time=ch.get("start_time"),
            )
        )
    return tracks


def parse_description(info: dict) -> list[Track]:
    """Recover a tracklist from timestamped lines in the description."""
    description = info.get("description") or ""
    tracks: list[Track] = []
    for line in description.splitlines():
        if not TIMESTAMP_RE.search(line):
            continue
        # Capture the first timestamp's position so we can keep it as start_time.
        m = TIMESTAMP_RE.search(line)
        start = parse_timestamp(m.group(0)) if m else None
        title = clean_title(line)
        if not title or is_non_music_title(title):
            continue
        tracks.append(
            Track(
                index=len(tracks) + 1,
                title=title,
                source="description",
                start_time=start,
            )
        )
    return tracks


def parse_timestamp(ts: str) -> int | None:
    parts = [int(p) for p in ts.split(":")]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return None


def extract_tracks(info: dict, mode: str) -> tuple[list[Track], str]:
    """Return (tracks, source_used) according to the selected mode."""
    chapter_tracks = parse_chapters(info) if mode != "description" else []
    if chapter_tracks:
        return chapter_tracks, "chapters"
    if mode == "chapters":
        return [], "chapters"
    desc_tracks = parse_description(info)
    return desc_tracks, "description"


# --------------------------------------------------------------------------- #
# Searching
# --------------------------------------------------------------------------- #
def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def is_excluded_result(title: str | None) -> bool:
    """Skip search results whose title contains an excluded phrase."""
    if not title:
        return False
    lowered = title.lower()
    return any(phrase in lowered for phrase in EXCLUDED_RESULT_PHRASES)


def search_track(
    ydl: YoutubeDL, query: str, limit: int = 5
) -> tuple[dict | None, float]:
    """Return the best non-excluded search result and its similarity score.

    Among the top ``limit`` results, excluded titles are skipped and the
    remaining candidate most similar to ``query`` is chosen.
    """
    try:
        result = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    except Exception:
        return None, 0.0

    best: dict | None = None
    best_score = 0.0
    for entry in (result or {}).get("entries") or []:
        title = entry.get("title")
        if is_excluded_result(title):
            continue
        score = similarity(query, title or "")
        if score > best_score:
            best, best_score = entry, score
    return best, best_score


def resolve_tracks(tracks: list[Track]) -> None:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "default_search": "ytsearch",
    }
    with YoutubeDL(opts) as ydl:
        for track in tracks:
            entry, score = search_track(ydl, track.title)
            if not entry or score < MIN_SEARCH_SCORE:
                best_title = entry.get("title") if entry else None
                detail = (
                    f"best was '{best_title}' at score {round(score, 3)}"
                    if entry
                    else "no usable results"
                )
                print(f"  [{track.index:>2}] {track.title}  ->  [no good match] ({detail})")
                continue
            vid = entry.get("id")
            track.matched_id = vid
            track.matched_title = entry.get("title")
            track.matched_url = entry.get("url") or (
                f"https://www.youtube.com/watch?v={vid}" if vid else None
            )
            track.matched_duration = entry.get("duration")
            track.match_score = round(score, 3)
            print(
                f"  [{track.index:>2}] {track.title}  ->  "
                f"{track.matched_title} (score {track.match_score})"
            )


# --------------------------------------------------------------------------- #
# Local music collection
# --------------------------------------------------------------------------- #
def normalize_for_match(text: str) -> str:
    """Aggressively normalise a title/filename for fuzzy comparison."""
    text = text.lower()
    text = FILENAME_NOISE_RE.sub(" ", text)
    # Normalise separators and drop remaining punctuation.
    text = re.sub(r"[_\-–—|•·:/\\]", " ", text)
    text = re.sub(r"[^\w&\s]", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def build_local_index(music_dir: Path) -> list[tuple[str, Path]]:
    """Scan the collection and return (normalised_name, path) for each audio file."""
    index: list[tuple[str, Path]] = []
    for path in music_dir.rglob("*"):
        if path.suffix.lower() in AUDIO_EXTENSIONS and path.is_file():
            index.append((normalize_for_match(path.stem), path))
    return index


def name_match_score(norm_title: str, norm_name: str) -> float:
    """Similarity of a track title to a filename, tolerant of extra descriptors.

    Uses string similarity, but when every word of the (shorter) track title is
    present in the filename it counts as a strong match. This handles files
    that carry extra trailing text (e.g. "(Hunger Games)") while avoiding the
    false positives a plain ratio causes for songs that merely share an artist.
    """
    ratio = SequenceMatcher(None, norm_title, norm_name).ratio()
    title_tokens = set(norm_title.split())
    name_tokens = set(norm_name.split())
    if title_tokens and len(title_tokens) >= 2 and title_tokens <= name_tokens:
        return max(ratio, 0.95)
    return ratio


def match_local(
    tracks: list[Track],
    index: list[tuple[str, Path]],
    threshold: float = DEFAULT_MATCH_THRESHOLD,
) -> None:
    """Match each track to the best file in the collection, in place."""
    for track in tracks:
        norm_title = normalize_for_match(track.title)
        best_score = 0.0
        best_path: Path | None = None
        for norm_name, path in index:
            score = name_match_score(norm_title, norm_name)
            if score > best_score:
                best_score, best_path = score, path
        if best_path is not None and best_score >= threshold:
            track.local_path = str(best_path)
            track.local_score = round(best_score, 3)


def sanitize_filename(name: str) -> str:
    """Make a track title safe to use as a filename."""
    name = re.sub(r'[\\/:*?"<>|]+', "", name).strip()
    return name[:150] or "track"


def split_artist_title(text: str) -> tuple[str | None, str]:
    """Split a "Artist - Song" title into (artist, song)."""
    if " - " in text:
        artist, song = text.split(" - ", 1)
        return artist.strip() or None, song.strip()
    return None, text.strip()


def tag_audio(path: Path, track_title: str) -> None:
    """Write title and artist tags onto a downloaded opus file."""
    artist, song = split_artist_title(track_title)
    audio = OggOpus(str(path))
    audio["title"] = [song]
    if artist:
        audio["artist"] = [artist]
    audio.save()


def download_tracks(tracks: list[Track], download_dir: Path) -> None:
    download_dir.mkdir(parents=True, exist_ok=True)
    for track in tracks:
        if not track.matched_url:
            print(f"  skip (no source found): {track.title}")
            continue
        safe = sanitize_filename(track.title)
        out_path = download_dir / f"{safe}.opus"
        opts = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "format": "bestaudio[acodec=opus]/bestaudio/best",
            "outtmpl": str(download_dir / f"{safe}.%(ext)s"),
            # Fetch the thumbnail so EmbedThumbnail can write the cover art.
            "writethumbnail": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "opus",
                    "preferredquality": "0",
                },
                {"key": "EmbedThumbnail"},
            ],
        }
        try:
            with YoutubeDL(opts) as ydl:
                ydl.download([track.matched_url])
            tag_audio(out_path, track.title)
            track.local_path = str(out_path)
            track.local_score = 1.0
            print(f"  downloaded: {safe}.opus")
        except Exception as exc:  # noqa: BLE001 - report and continue.
            print(f"  FAILED: {track.title} ({exc})")


def confirm(prompt_text: str, assume_yes: bool = False) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        print(f"{prompt_text} [y/N]: N (non-interactive)")
        return False
    try:
        return input(f"{prompt_text} [y/N]: ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def track_target(track: Track, collection_dir: Path) -> str | None:
    """Playable entry: the local file relative to the collection, else the URL."""
    if track.local_path:
        relpath = os.path.relpath(track.local_path, collection_dir)
        return relpath.removeprefix("!~}music{~!/")
    return track.matched_url


def write_outputs(
    tracks: list[Track],
    info: dict,
    out_dir: Path,
    basename: str,
    collection_dir: Path,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    if any(track_target(t, collection_dir) for t in tracks):
        m3u_path = out_dir / f"{basename}.m3u8"
        m3u = ["#EXTM3U"]
        for t in tracks:
            target = track_target(t, collection_dir)
            if not target:
                continue
            dur = int(t.matched_duration) if t.matched_duration else -1
            m3u.append(f"#EXTINF:{dur},{t.title}")
            m3u.append(target)
        m3u_path.write_text("\n".join(m3u) + "\n")
        written.append(m3u_path)

    return written


def safe_name(info: dict) -> str:
    title = info.get("title") or info.get("id") or "playlist"
    slug = re.sub(r"[^\w\- ]+", "", title).strip().replace(" ", "_")
    return slug[:80] or "playlist"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a playlist from a YouTube compilation video's "
        "chapters and description."
    )
    parser.add_argument("url", help="YouTube compilation video URL")
    parser.add_argument(
        "--mode",
        choices=["auto", "chapters", "description"],
        default="auto",
        help="Where to read the tracklist from. 'auto' prefers chapters and "
        "falls back to the description (default: auto)",
    )
    parser.add_argument(
        "--music-dir",
        default=DEFAULT_MUSIC_DIR,
        help=f"Local music collection to match against (default: {DEFAULT_MUSIC_DIR})",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Assume 'yes' and download missing songs without prompting.",
    )
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Never download; just report which songs are missing.",
    )
    args = parser.parse_args(argv)

    print(f"Fetching metadata for: {args.url}")
    try:
        info = fetch_info(args.url)
    except Exception as exc:  # noqa: BLE001 - surface yt-dlp errors to the user.
        print(f"Failed to fetch video info: {exc}", file=sys.stderr)
        return 1

    tracks, used = extract_tracks(info, args.mode)
    if not tracks:
        print(
            "No tracks found. The video may lack chapters and have an "
            "unparseable description. Try --mode description, or inspect the "
            "video manually.",
            file=sys.stderr,
        )
        return 2
    print(f"Found {len(tracks)} tracks from {used}.")

    # Match against the local collection.
    music_dir = Path(args.music_dir).expanduser()
    if not music_dir.is_dir():
        print(f"Music directory not found: {music_dir}", file=sys.stderr)
        return 1
    print(f"Scanning local collection at {music_dir} ...")
    index = build_local_index(music_dir)
    print(f"Indexed {len(index)} audio files.")
    match_local(tracks, index, DEFAULT_MATCH_THRESHOLD)

    found = [t for t in tracks if t.local_path]
    missing = [t for t in tracks if not t.local_path]
    print(f"\nAlready in collection: {len(found)}/{len(tracks)}")
    for t in found:
        print(f"  [+] {t.title}  (score {t.local_score})")
    for t in missing:
        print(f"  [-] {t.title}")

    # Handle missing songs.
    if missing:
        if args.no_download:
            print(f"\n{len(missing)} song(s) missing; --no-download set, skipping.")
        else:
            do_download = confirm(
                f"\n{len(missing)} song(s) are not in the collection. "
                f"Download them into {DOWNLOAD_DIR}?",
                assume_yes=args.yes,
            )
            if do_download:
                print("Searching YouTube for missing songs...")
                resolve_tracks(missing)
                print(f"Downloading into {DOWNLOAD_DIR} ...")
                download_tracks(missing, DOWNLOAD_DIR)
    else:
        print("\nAll songs are already in the collection. Building playlist.")

    written = write_outputs(tracks, info, OUTPUT_DIR, safe_name(info), music_dir)

    still_missing = [t for t in tracks if not t.local_path]
    print(f"\nPlaylist: {len(tracks) - len(still_missing)}/{len(tracks)} songs available.")
    print("Wrote:")
    for path in written:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
