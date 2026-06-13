#!/usr/bin/env python3
"""Sort downloaded audio files into artist folders in the music collection.

Reads each file's artist (from its tags, falling back to the "Artist - Song"
filename), fuzzy-matches it to an existing `!Artist` folder in the collection,
and moves the file there. Files whose artist has no folder are left in place
and reported. Runs as a dry-run unless --apply is given.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional
from mutagen import File as MutagenFile

SCRIPT_DIR = Path(__file__).resolve().parent
SOURCE_DIR = SCRIPT_DIR / "music"
COLLECTION_DIR = Path("/home/kloud/Documents/shared/_Music")

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".opus", ".oga", ".ogg", ".flac", ".wav", ".webm"}

ARTIST_FOLDER_PREFIX = "!"

FUZZY_THRESHOLD = 0.85


def normalize(name: str) -> str:
    """Normalise an artist name or folder name for comparison."""
    name = name.strip().lstrip(ARTIST_FOLDER_PREFIX).strip().lower()
    return " ".join(name.split())


def build_artist_folders(collection: Path) -> list[tuple[str, Path]]:
    """Return (normalised_name, path) for every `!`-prefixed folder."""
    folders: list[tuple[str, Path]] = []
    for path in collection.rglob("*"):
        if path.is_dir() and path.name.startswith(ARTIST_FOLDER_PREFIX):
            folders.append((normalize(path.name), path))
    return folders


def get_artist(file_path: Path) -> Optional[str]:
    """Read the artist from tags, falling back to the "Artist - Song" name."""
    try:
        audio = MutagenFile(file_path, easy=True)
        if audio and audio.get("artist"):
            artist = audio["artist"][0].strip()
            if artist:
                return artist
    except Exception:
        pass
    if " - " in file_path.stem:
        artist = file_path.stem.split(" - ", 1)[0].strip()
        return artist or None
    return None


def match_folder(
    artist: str, folders: list[tuple[str, Path]], threshold: float
) -> Optional[Path]:
    """Find the best artist folder for an artist name, or None."""
    norm_artist = normalize(artist)
    if not norm_artist:
        return None
    best_score = 0.0
    best_path: Optional[Path] = None
    best_depth = 10**9
    for norm_name, path in folders:
        score = SequenceMatcher(None, norm_artist, norm_name).ratio()
        depth = len(path.relative_to(COLLECTION_DIR).parts)
        # Prefer the highest score; on ties prefer the shallowest folder.
        if score > best_score or (score == best_score and depth < best_depth):
            best_score, best_path, best_depth = score, path, depth
    if best_path is not None and best_score >= threshold:
        return best_path
    return None


def unique_destination(dest: Path) -> Path:
    """Avoid clobbering: append " (n)" before the suffix if dest exists."""
    if not dest.exists():
        return dest
    stem, suffix = dest.stem, dest.suffix
    n = 2
    while True:
        candidate = dest.with_name(f"{stem} ({n}){suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sort downloaded audio files into artist folders in the "
        "music collection."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually move files. Without this, only previews the moves.",
    )
    parser.add_argument(
        "--source",
        default=str(SOURCE_DIR),
        help=f"Folder of files to sort (default: {SOURCE_DIR})",
    )
    parser.add_argument(
        "--music-dir",
        default=str(COLLECTION_DIR),
        help=f"Music collection to sort into (default: {COLLECTION_DIR})",
    )
    args = parser.parse_args(argv)

    source = Path(args.source).expanduser()
    collection = Path(args.music_dir).expanduser()
    if not source.is_dir():
        print(f"Source folder not found: {source}", file=sys.stderr)
        return 1
    if not collection.is_dir():
        print(f"Collection folder not found: {collection}", file=sys.stderr)
        return 1

    files = sorted(
        p
        for p in source.rglob("*")
        if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
    )
    if not files:
        print(f"No audio files found in {source}.")
        return 0

    print(f"Indexing artist folders in {collection} ...")
    folders = build_artist_folders(collection)
    print(f"Found {len(folders)} artist folders.")
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"\n[{mode}] Sorting {len(files)} file(s):\n")

    moved = 0
    unsorted: list[Path] = []
    for f in files:
        artist = get_artist(f)
        folder = match_folder(artist, folders, FUZZY_THRESHOLD) if artist else None
        if folder is None:
            unsorted.append(f)
            reason = f"no folder for artist '{artist}'" if artist else "no artist found"
            print(f"  [skip] {f.name}  ({reason})")
            continue
        dest = unique_destination(folder / f.name)
        rel = folder.relative_to(collection)
        print(f"  [move] {f.name}  ->  {rel}/")
        if args.apply:
            shutil.move(str(f), str(dest))
            moved += 1

    print(
        f"\nDone. {moved if args.apply else 0} moved, "
        f"{len(unsorted)} left unsorted, {len(files)} total."
    )
    if not args.apply:
        print("This was a dry-run. Re-run with --apply to perform the moves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
