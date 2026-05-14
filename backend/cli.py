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


def cmd_serve(args: argparse.Namespace) -> int:
    """uvicorn 으로 backend.main:app 을 띄우는 단축어.

    팀원이 처음 클론했을 때 ``python -m backend.cli serve`` 한 줄이면 동작
    하도록 만들기 위한 편의 명령. 운영 환경에선 직접 uvicorn 을 쓰는 편이
    옵션을 더 세밀하게 줄 수 있다.
    """
    try:
        import uvicorn
    except ImportError:
        print("error: uvicorn 이 설치되어 있지 않습니다. pip install uvicorn", file=sys.stderr)
        return 7
    uvicorn.run(
        "backend.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )
    return 0


def cmd_validate_dataset(args: argparse.Namespace) -> int:
    """카탈로그 CSV 가 엔진에 안전하게 로딩 가능한지 미리 점검한다.

    - 필수 키 컬럼이 있는지
    - NaN/Inf 행이 몇 개인지
    - 분산이 0인 컬럼 (자동 drop 되는 것들) 이 몇 개인지
    - 전체 곡 수
    """

    import numpy as np
    import pandas as pd

    csv_path = Path(args.path)
    if not csv_path.exists():
        print(f"error: 파일을 찾을 수 없습니다: {csv_path}", file=sys.stderr)
        return 2

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:  # noqa: BLE001
        print(f"error: CSV 로딩 실패: {e}", file=sys.stderr)
        return 3

    name_col = "musicname & artist"
    if name_col not in df.columns:
        print(f"error: 필수 키 컬럼 누락: '{name_col}'", file=sys.stderr)
        return 4

    df = df.set_index(name_col)
    feature_cols = [c for c in df.columns if c != "length"]
    if not feature_cols:
        print("error: 특성 컬럼이 하나도 없습니다.", file=sys.stderr)
        return 5

    raw = df[feature_cols].astype(float)
    finite_mask = np.isfinite(raw.values).all(axis=1)
    bad_rows = int((~finite_mask).sum())

    col_std = raw.std(axis=0, ddof=0)
    zero_var_cols = [c for c in feature_cols if col_std.get(c, 0.0) <= 1e-12]

    duplicates = int(df.index.duplicated().sum())
    nan_per_col = raw.isna().sum().to_dict()
    cols_with_nan = [(c, int(n)) for c, n in nan_per_col.items() if n > 0]

    print(f"# 카탈로그 검증 결과: {csv_path}")
    print(f"  총 행: {len(df)}")
    print(f"  특성 컬럼: {len(feature_cols)}개 (length 제외)")
    print(f"  중복된 키: {duplicates}건")
    print(f"  NaN/Inf 가 섞인 행: {bad_rows}건 (엔진이 자동으로 drop)")
    print(f"  분산 0 컬럼: {len(zero_var_cols)}개 (엔진이 자동으로 drop)")
    if cols_with_nan:
        print("  컬럼별 NaN 갯수 (상위 5):")
        for c, n in sorted(cols_with_nan, key=lambda x: -x[1])[:5]:
            print(f"    - {c}: {n}")
    if zero_var_cols:
        print("  분산 0 컬럼 이름 (상위 5):")
        for c in zero_var_cols[:5]:
            print(f"    - {c}")

    # 로딩이 실제로 가능한지까지 확인.
    try:
        engine = MusicSimilarityEngine(csv_path)
        print(f"  ✅ 엔진 로딩 성공. 실제 사용 가능한 곡 수: {engine.catalog_size}")
        print(f"     사용 중인 특성 컬럼: {len(engine.feature_columns)}개")
    except Exception as e:  # noqa: BLE001
        print(f"  ❌ 엔진 로딩 실패: {e}", file=sys.stderr)
        return 6

    # 경고만 있어도 exit 0. 실제 로딩 실패한 경우만 비정상 종료.
    return 0


def cmd_dedupe_dataset(args: argparse.Namespace) -> int:
    """카탈로그 CSV 에서 중복된 키(같은 '곡명 - 아티스트')를 제거해 새 파일로 저장한다.

    첫 번째 항목을 유지하고 나머지를 떨군다. 엔진과 같은 정책.
    """
    import pandas as pd

    src = Path(args.path)
    if not src.exists():
        print(f"error: 파일을 찾을 수 없습니다: {src}", file=sys.stderr)
        return 2

    try:
        df = pd.read_csv(src)
    except Exception as e:  # noqa: BLE001
        print(f"error: CSV 로딩 실패: {e}", file=sys.stderr)
        return 3

    name_col = "musicname & artist"
    if name_col not in df.columns:
        print(f"error: 필수 키 컬럼 누락: '{name_col}'", file=sys.stderr)
        return 4

    before = len(df)
    df_dedup = df.drop_duplicates(subset=[name_col], keep="first")
    dropped = before - len(df_dedup)

    out = Path(args.out)
    if not args.overwrite and out.exists() and out.samefile(src):
        print(
            f"error: 입력과 같은 파일을 덮어쓰려면 --overwrite 가 필요합니다: {out}",
            file=sys.stderr,
        )
        return 5

    out.parent.mkdir(parents=True, exist_ok=True)
    df_dedup.to_csv(out, index=False, encoding="utf-8")
    print("# 중복 제거 결과")
    print(f"  입력: {src} ({before}행)")
    print(f"  출력: {out} ({len(df_dedup)}행)")
    print(f"  제거된 중복: {dropped}행")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    """폴더 안의 음원들을 한꺼번에 분석해 CSV 로 떨군다."""
    import csv

    audio_dir = Path(args.dir)
    if not audio_dir.exists() or not audio_dir.is_dir():
        print(f"error: 디렉토리를 찾을 수 없습니다: {audio_dir}", file=sys.stderr)
        return 2

    exts = {e.lower() for e in args.extensions}
    files = sorted(p for p in audio_dir.iterdir() if p.is_file() and p.suffix.lower() in exts)
    if not files:
        print(f"warning: {audio_dir} 안에 분석할 음원이 없습니다.", file=sys.stderr)
        return 1

    dataset = Path(args.dataset)
    try:
        engine = MusicSimilarityEngine(dataset)
    except Exception as e:  # noqa: BLE001
        print(f"error: 카탈로그 로딩 실패: {e}", file=sys.stderr)
        return 3

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["filename", "rank", "title", "artist", "similarity_percent", "tags"]
    failed = 0
    rows_written = 0

    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for idx, path in enumerate(files, start=1):
            try:
                features = extract_features(path, max_duration=args.max_duration)
                hits, _ = engine.find_similar(features, top_n=args.top_n)
                tags = " / ".join(derive_tags(features))
            except Exception as e:  # noqa: BLE001
                print(f"  [{idx}/{len(files)}] skip {path.name}: {e}", file=sys.stderr)
                failed += 1
                continue
            for hit in hits:
                writer.writerow({
                    "filename": path.name,
                    "rank": hit.rank,
                    "title": hit.name,
                    "artist": hit.artist,
                    "similarity_percent": f"{hit.similarity_percent:.1f}",
                    "tags": tags,
                })
                rows_written += 1
            print(f"  [{idx}/{len(files)}] {path.name}")

    print(f"\n{len(files)}개 파일 중 {failed}개 실패, CSV {rows_written}행 작성: {out_path}")
    return 0 if failed == 0 else 5


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

    batch = sub.add_parser("batch", help="폴더 전체를 한 번에 분석해 CSV 로 떨군다.")
    batch.add_argument("dir", help="음원이 들어있는 디렉토리")
    batch.add_argument("--out", default="batch_results.csv", help="출력 CSV 경로")
    batch.add_argument("--top-n", type=int, default=5, help="파일당 찾을 곡 수 (1~20)")
    batch.add_argument(
        "--max-duration",
        type=float,
        default=30.0,
        help="각 파일을 이 초 수까지만 분석에 사용",
    )
    batch.add_argument(
        "--dataset",
        default="data/dataset.csv",
        help="카탈로그 CSV 경로",
    )
    batch.add_argument(
        "--extensions",
        nargs="+",
        default=[".wav", ".mp3", ".flac", ".ogg", ".m4a"],
        help="포함할 오디오 확장자",
    )
    batch.set_defaults(func=cmd_batch)

    validate = sub.add_parser("validate-dataset", help="카탈로그 CSV 가 엔진에 로딩 가능한지 점검한다.")
    validate.add_argument("path", help="검증할 dataset.csv 경로")
    validate.set_defaults(func=cmd_validate_dataset)

    dedupe = sub.add_parser("dedupe-dataset", help="카탈로그 CSV 의 중복된 키를 제거한다.")
    dedupe.add_argument("path", help="원본 dataset.csv 경로")
    dedupe.add_argument("--out", required=True, help="결과를 저장할 CSV 경로")
    dedupe.add_argument(
        "--overwrite",
        action="store_true",
        help="입력과 같은 파일을 덮어써도 되는지 명시적으로 허용",
    )
    dedupe.set_defaults(func=cmd_dedupe_dataset)

    serve = sub.add_parser("serve", help="uvicorn 으로 백엔드를 띄운다 (개발 편의용 단축어).")
    serve.add_argument("--host", default="127.0.0.1", help="바인딩할 호스트 (기본 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8000, help="리스닝 포트 (기본 8000)")
    serve.add_argument("--reload", action="store_true", help="코드 변경 시 자동 재시작")
    serve.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
    )
    serve.set_defaults(func=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # top_n 은 analyze/batch 에서만 등장. validate-dataset 에는 없으니 hasattr 가드.
    if hasattr(args, "top_n") and not (1 <= args.top_n <= 20):
        print("error: --top-n 은 1~20 범위", file=sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
