"""``data/dataset.csv`` 를 .wav 폴더에서 다시 빌드한다.

``audio_dir`` 아래 음원을 순회하며 58개 특성을 뽑아, 원작 캡스톤 노트북과
동일한 컬럼 레이아웃으로 CSV 를 출력한다. 그래야 유사도 엔진이 그대로 로드.

사용법
-----
    python scripts/rebuild_dataset.py --audio-dir ./songs --out data/dataset.csv

파일명 규칙: "곡 제목 - 아티스트.wav" — UI 에서 아티스트를 분리해 표시할 때 사용.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

# 저장소 루트에서 `python scripts/rebuild_dataset.py` 로 직접 실행 가능하도록 path 보정.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.audio_features import FEATURE_COLUMNS, extract_features  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="음원 폴더에서 카탈로그 CSV 를 다시 만든다.")
    parser.add_argument("--audio-dir", required=True, help="음원 파일이 들어 있는 디렉토리")
    parser.add_argument("--out", default="data/dataset.csv", help="출력 CSV 경로")
    parser.add_argument(
        "--extensions",
        nargs="+",
        default=[".wav", ".mp3", ".flac", ".ogg", ".m4a"],
        help="포함할 오디오 확장자 목록",
    )
    parser.add_argument(
        "--max-duration",
        type=float,
        default=30.0,
        help="각 파일을 이 초 수만큼만 분석에 사용",
    )
    args = parser.parse_args()

    audio_dir = Path(args.audio_dir)
    if not audio_dir.exists():
        print(f"error: --audio-dir 경로가 존재하지 않음: {audio_dir}", file=sys.stderr)
        return 1

    exts = {e.lower() for e in args.extensions}
    files: list[Path] = sorted(
        p for p in audio_dir.iterdir() if p.is_file() and p.suffix.lower() in exts
    )
    if not files:
        print(f"warning: {audio_dir} 안에서 처리할 음원을 찾지 못했음", file=sys.stderr)
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

    print(f"\n총 {len(files)} 후보 트랙을 {out} 에 기록 완료.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
