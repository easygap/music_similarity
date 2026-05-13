"""Rebuild data/dataset.csv from a folder of .wav files.

Walks `audio_dir`, extracts the 58 librosa features for each track, and
writes a CSV in the same column layout the original capstone notebook
used so the similarity engine can load it.

Usage
-----
    python scripts/rebuild_dataset.py --audio-dir ./songs --out data/dataset.csv

Filenames should follow the convention "Song Title - Artist Name.wav"
because the engine splits on " - " to display the artist separately.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# Allow `python scripts/rebuild_dataset.py` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.audio_features import FEATURE_COLUMNS, extract_features  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild the dataset CSV from audio files.")
    parser.add_argument("--audio-dir", required=True, help="Folder containing audio files")
    parser.add_argument("--out", default="data/dataset.csv", help="Output CSV path")
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".wav", ".mp3", ".flac", ".ogg", ".m4a"],
        help="Audio extensions to include",
    )
    parser.add_argument(
        "--max-duration",
        type=float,
        default=30.0,
        help="Trim each file to this many seconds before extracting features",
    )
    args = parser.parse_args()

    audio_dir = Path(args.audio_dir)
    if not audio_dir.exists():
        print(f"error: audio-dir does not exist: {audio_dir}", file=sys.stderr)
        return 1

    exts = {e.lower() for e in args.extensions}
    files: list[Path] = sorted(
        p for p in audio_dir.iterdir() if p.is_file() and p.suffix.lower() in exts
    )
    if not files:
        print(f"warning: no audio files found in {audio_dir}", file=sys.stderr)
        return 1

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    header = ["musicname & artist", *FEATURE_COLUMNS]
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)

        for idx, path in enumerate(files, 1):
            try:
                feats = extract_features(path, max_duration=args.max_duration)
            except Exception as e:  # noqa: BLE001
                print(f"  [{idx}/{len(files)}] skip {path.name}: {e}", file=sys.stderr)
                continue
            row = [path.stem] + [feats.values[c] for c in FEATURE_COLUMNS]
            writer.writerow(row)
            print(f"  [{idx}/{len(files)}] {path.name}")

    print(f"\nWrote {out} with {len(files)} candidate tracks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
