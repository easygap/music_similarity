"""음원 한 파일을 명령줄에서 곧장 분석하는 도구.

사용 예
-------
    # 사람-가독 출력
    python -m backend.cli analyze ./mysong.wav --top-n 5

    # 결과를 그대로 JSON 으로 받기 (스크립트/파이프라인용)
    python -m backend.cli analyze ./mysong.wav --json > result.json

서버를 띄우지 않고도 카탈로그 비교를 돌릴 수 있어 배치 작업 / 일회성 디버깅에
편하다. 내부적으로는 같은 ``MusicSimilarityEngine`` 과 같은 ``extract_features``
를 사용하므로 결과는 ``/api/analyze`` 와 동일.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from .audio_features import AudioFeatureVector, extract_features, summary_metrics
from .reason_engine import explain_match, report_to_dict
from .similarity import MusicSimilarityEngine
from .tagging import derive_tags

ENGINE_VERSION = "1.3.0"


def _build_response(
    engine: MusicSimilarityEngine,
    features: AudioFeatureVector,
    top_n: int,
    filename: str,
) -> dict:
    """API 응답과 동일한 형태의 dict 를 만든다."""
    hits, _ = engine.find_similar(features, top_n=top_n)
    results: list[dict] = []
    for hit in hits:
        full_name = f"{hit.name} - {hit.artist}"
        catalog_raw = engine.catalog_row_raw(full_name) or {}
        report = explain_match(
            query_raw=features.values,
            catalog_raw=catalog_raw,
            distances_scaled=hit.feature_distances,
        )
        if catalog_raw:
            safe_catalog = dict(catalog_raw)
            safe_catalog.setdefault("length", 0.0)
            match_summary = summary_metrics(
                AudioFeatureVector(name=full_name, values=safe_catalog)
            )
        else:
            match_summary = None
        results.append(
            {
                "rank": hit.rank,
                "title": hit.name,
                "artist": hit.artist,
                "similarity": hit.similarity,
                "similarity_percent": hit.similarity_percent,
                "match_summary": match_summary,
                "reason": report_to_dict(report),
            }
        )
    return {
        "filename": filename,
        "summary": summary_metrics(features),
        "tags": derive_tags(features),
        "results": results,
        "catalog_size": engine.catalog_size,
        "analyzed_at": datetime.now(UTC).isoformat(),
        "engine_version": ENGINE_VERSION,
    }


def _render_text(data: dict) -> str:
    lines: list[str] = []
    lines.append(f"# {data['filename']}")
    lines.append(f"카탈로그 {data['catalog_size']}곡 비교 · {data['analyzed_at']}")
    if data["tags"]:
        lines.append("태그: " + " / ".join(data["tags"]))
    s = data["summary"]
    lines.append(
        f"요약: tempo={s['tempo_bpm']} BPM · energy={s['energy_rms']} · "
        f"brightness={s['brightness']} Hz · chroma={s['chroma']}"
    )
    lines.append("")
    for r in data["results"]:
        lines.append(
            f"  {r['rank']:>2}. {r['title']} – {r['artist']}  "
            f"({r['similarity_percent']:.1f}%)"
        )
        top_group = (r["reason"]["groups"] or [None])[0]
        if top_group:
            lines.append(f"      ↳ {top_group['label']} · {top_group['summary']}")
    return "\n".join(lines) + "\n"


def cmd_analyze(args: argparse.Namespace) -> int:
    audio_path = Path(args.path)
    if not audio_path.exists():
        print(f"error: 파일을 찾을 수 없습니다: {audio_path}", file=sys.stderr)
        return 2

    dataset = Path(args.dataset)
    try:
        engine = MusicSimilarityEngine(dataset)
    except Exception as e:  # noqa: BLE001
        print(f"error: 카탈로그 로딩 실패: {e}", file=sys.stderr)
        return 3

    try:
        features = extract_features(audio_path, max_duration=args.max_duration)
    except Exception as e:  # noqa: BLE001
        print(f"error: 오디오 분석 실패: {e}", file=sys.stderr)
        return 4

    data = _build_response(
        engine=engine,
        features=features,
        top_n=args.top_n,
        filename=audio_path.name,
    )

    if args.json:
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_render_text(data))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m backend.cli",
        description="음악 유사도 분석을 명령줄에서 실행한다.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    analyze = sub.add_parser("analyze", help="음원 파일 하나를 분석한다.")
    analyze.add_argument("path", help="분석할 음원 파일 경로")
    analyze.add_argument("--top-n", type=int, default=5, help="찾을 곡 수 (1~20)")
    analyze.add_argument(
        "--max-duration",
        type=float,
        default=30.0,
        help="이 초 수까지만 분석에 사용 (기본 30초)",
    )
    analyze.add_argument(
        "--dataset",
        default="data/dataset.csv",
        help="카탈로그 CSV 경로 (기본: data/dataset.csv)",
    )
    analyze.add_argument(
        "--json",
        action="store_true",
        help="결과를 JSON 으로 stdout 에 출력",
    )
    analyze.set_defaults(func=cmd_analyze)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not (1 <= args.top_n <= 20):
        print("error: --top-n 은 1~20 범위", file=sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
