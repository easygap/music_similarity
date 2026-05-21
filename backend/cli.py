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


def cmd_compare(args: argparse.Namespace) -> int:
    """두 파일을 분석해 메트릭과 태그를 나란히 비교한다.

    같은 카탈로그로 두 곡을 동시에 분석하고, 메트릭 차이를 가독성 있게 출력.
    각 곡의 1위 매칭도 같이 알려준다 — 두 곡이 카탈로그에서 비슷한 영역에
    있는지 빠르게 감 잡기에 좋다.
    """
    path_a = Path(args.path_a)
    path_b = Path(args.path_b)
    for p in (path_a, path_b):
        if not p.exists():
            print(f"error: 파일을 찾을 수 없습니다: {p}", file=sys.stderr)
            return 2

    dataset = Path(args.dataset)
    try:
        engine = MusicSimilarityEngine(dataset)
    except Exception as e:  # noqa: BLE001
        print(f"error: 카탈로그 로딩 실패: {e}", file=sys.stderr)
        return 3

    try:
        fa = extract_features(path_a, max_duration=args.max_duration)
        fb = extract_features(path_b, max_duration=args.max_duration)
    except Exception as e:  # noqa: BLE001
        print(f"error: 오디오 분석 실패: {e}", file=sys.stderr)
        return 4

    sa = summary_metrics(fa)
    sb = summary_metrics(fb)
    ta = derive_tags(fa)
    tb = derive_tags(fb)
    hits_a, _ = engine.find_similar(fa, top_n=1)
    hits_b, _ = engine.find_similar(fb, top_n=1)
    top_a = hits_a[0] if hits_a else None
    top_b = hits_b[0] if hits_b else None

    metric_labels = [
        ("Tempo (BPM)", "tempo_bpm"),
        ("에너지 (RMS)", "energy_rms"),
        ("밝기 (Hz)", "brightness"),
        ("거친 정도", "noisiness"),
        ("화성/타악기", "harmony_ratio"),
        ("크로마", "chroma"),
    ]

    def _fmt(v):
        if not isinstance(v, int | float):
            return "—"
        if abs(v) >= 100:
            return f"{v:.0f}"
        if abs(v) >= 1:
            return f"{v:.1f}"
        return f"{v:.3f}"

    if args.json:
        import json as _json

        _json.dump(
            {
                "a": {"filename": path_a.name, "summary": sa, "tags": ta,
                       "top1": _hit_to_dict(top_a) if top_a else None},
                "b": {"filename": path_b.name, "summary": sb, "tags": tb,
                       "top1": _hit_to_dict(top_b) if top_b else None},
                "catalog_size": engine.catalog_size,
                "engine_version": ENGINE_VERSION,
            },
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        sys.stdout.write("\n")
        return 0

    print("# 비교 결과")
    print(f"  A: {path_a.name}")
    print(f"  B: {path_b.name}")
    print(f"  카탈로그 {engine.catalog_size}곡 기준")
    print()
    print(f"  {'항목':<14} {'A':>12} {'B':>12} {'Δ':>10}")
    for label, key in metric_labels:
        va = sa.get(key)
        vb = sb.get(key)
        delta = ""
        if isinstance(va, int | float) and isinstance(vb, int | float):
            delta = _fmt(vb - va)
        print(f"  {label:<14} {_fmt(va):>12} {_fmt(vb):>12} {delta:>10}")
    print()
    print(f"  태그 A: {' / '.join(ta) if ta else '-'}")
    print(f"  태그 B: {' / '.join(tb) if tb else '-'}")
    print()
    if top_a:
        print(f"  A 의 1위 매칭: {top_a.name} – {top_a.artist} "
              f"({top_a.similarity_percent:.1f}%)")
    if top_b:
        print(f"  B 의 1위 매칭: {top_b.name} – {top_b.artist} "
              f"({top_b.similarity_percent:.1f}%)")
    return 0


def _hit_to_dict(hit) -> dict:
    return {
        "title": hit.name,
        "artist": hit.artist,
        "similarity_percent": hit.similarity_percent,
    }


def cmd_status(args: argparse.Namespace) -> int:
    """떠 있는 서버의 /api/health 응답을 사람 친화적으로 표시한다.

    배포 후 sanity check / cron monitoring 용 작은 도구. ``--json`` 으로
    그대로 JSON 만 떨궈서 jq / 다른 툴에 파이프하기 쉽게도 만들었다.
    503 (degraded) 응답이면 exit code 3 으로 종료해 cron / CI 에서
    fail 처리 가능.
    """
    import json as _json
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen

    url = args.url.rstrip("/") + "/api/health"
    if args.strict:
        url += "?strict=true"

    req = Request(url, headers={"User-Agent": f"soundmatch-cli/{ENGINE_VERSION}"})
    try:
        with urlopen(req, timeout=args.timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status_code = resp.status
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        status_code = e.code
    except URLError as e:
        print(f"error: 서버 접속 실패 ({args.url}): {e.reason}", file=sys.stderr)
        return 4
    except OSError as e:
        # timeout 등.
        print(f"error: 네트워크 오류 — {e}", file=sys.stderr)
        return 4

    try:
        data = _json.loads(body)
    except _json.JSONDecodeError:
        print(f"error: 서버 응답이 JSON 아님 (status={status_code})", file=sys.stderr)
        print(body[:500], file=sys.stderr)
        return 5

    if args.json:
        # CI / monitoring 친화 — exit code 만으로 통과/실패 판단 가능.
        print(_json.dumps(data, ensure_ascii=False, indent=2))
        return 0 if status_code == 200 else 3

    # 사람 친화 표.
    ok = data.get("status") == "ok"
    head = f"[{data.get('status', '?').upper()}] {args.url}"
    print(head)
    print("─" * len(head))
    rows = [
        ("env", data.get("env", "?")),
        ("version", data.get("version", "?")),
        ("catalog_size", data.get("catalog_size", 0)),
        ("uptime_seconds", data.get("uptime_seconds", 0)),
        ("analyze_p50_seconds", data.get("analyze_latency_p50_seconds", 0)),
        ("catalog_updated_at", data.get("catalog_updated_at") or "—"),
    ]
    label_w = max(len(k) for k, _ in rows)
    for k, v in rows:
        print(f"  {k:<{label_w}} : {v}")
    if not ok:
        # 운영자한테 큰 신호. 색상 없이 표시 (Windows 콘솔 호환).
        print()
        print("  ⚠ status 가 ok 가 아닙니다. /metrics 와 로그를 확인하세요.")
    return 0 if ok else 3


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


def cmd_dataset_stats(args: argparse.Namespace) -> int:
    """카탈로그 CSV 의 BPM / 에너지 / 밝기 / 길이 분포를 콘솔에 요약 출력한다.

    운영자가 카탈로그 갱신 후 sanity check 용. ``--json`` 이면 그대로 jq 에
    파이프하기 쉬운 JSON 만 흘린다. 백엔드 띄울 필요 없이 CSV 만 있으면 된다.
    """
    import json as _json

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

    def _series_summary(series: pd.Series) -> dict[str, float] | None:
        """비어 있지 않은 수치 컬럼의 min/max/avg/p50."""
        s = pd.to_numeric(series, errors="coerce").dropna()
        if s.empty:
            return None
        return {
            "min": float(s.min()),
            "max": float(s.max()),
            "avg": round(float(s.mean()), 2),
            "p50": round(float(np.percentile(s, 50)), 2),
            "count": int(s.size),
        }

    total_rows = int(len(df))
    unique_keys = int(df[name_col].nunique(dropna=True)) if total_rows else 0
    duplicates = total_rows - unique_keys

    # 사용자 화면에 노출되는 핵심 메트릭만 모음. 더 정밀한 컬럼별 통계는
    # validate-dataset 가 다룸 — 여기는 빠르게 한눈에.
    stats = {
        "path": str(csv_path),
        "rows": total_rows,
        "unique_keys": unique_keys,
        "duplicate_keys": duplicates,
        "bpm": _series_summary(df["bpm"]) if "bpm" in df.columns else None,
        "energy_rms": _series_summary(df["rms_mean"]) if "rms_mean" in df.columns else None,
        "brightness_hz": _series_summary(df["spectral_centroid_mean"])
            if "spectral_centroid_mean" in df.columns else None,
        "length_seconds": _series_summary(df["length"]) if "length" in df.columns else None,
    }

    if args.json:
        print(_json.dumps(stats, ensure_ascii=False, indent=2))
        return 0

    # 사람 친화 표.
    head = f"# {csv_path.name} — {total_rows:,}행 (유니크 {unique_keys:,}, 중복 {duplicates:,})"
    print(head)
    print("─" * len(head))

    def _row(label: str, s: dict[str, float] | None, unit: str) -> None:
        if not s:
            print(f"  {label:<10}: (없음)")
            return
        print(
            f"  {label:<10}: min {s['min']:>8.2f}{unit} · max {s['max']:>8.2f}{unit}"
            f" · avg {s['avg']:>8.2f}{unit} · p50 {s['p50']:>8.2f}{unit} · n={s['count']:,}"
        )

    _row("BPM", stats["bpm"], "")
    _row("에너지", stats["energy_rms"], "")
    _row("밝기", stats["brightness_hz"], "Hz")
    _row("길이(s)", stats["length_seconds"], "")
    return 0


def cmd_dataset_diff(args: argparse.Namespace) -> int:
    """두 카탈로그 CSV 를 비교해서 added / removed 곡 목록을 출력한다.

    카탈로그 갱신 후 운영자가 '뭐가 더 들어갔고 뭐가 빠졌는지' 빠르게 확인하는
    용도. 같은 키가 양쪽 다 있으면 변경된 게 아닌 걸로 간주 (특성 값 변경
    감지는 다루지 않음 — 그건 별도 데이터 검증 도구의 몫).
    """
    import json as _json

    import pandas as pd

    old_path = Path(args.old)
    new_path = Path(args.new)
    for p in (old_path, new_path):
        if not p.exists():
            print(f"error: 파일을 찾을 수 없습니다: {p}", file=sys.stderr)
            return 2

    try:
        old_df = pd.read_csv(old_path)
        new_df = pd.read_csv(new_path)
    except Exception as e:  # noqa: BLE001
        print(f"error: CSV 로딩 실패: {e}", file=sys.stderr)
        return 3

    name_col = "musicname & artist"
    for label, df in (("old", old_df), ("new", new_df)):
        if name_col not in df.columns:
            print(f"error: '{label}' 에 필수 키 컬럼 누락: '{name_col}'", file=sys.stderr)
            return 4

    old_keys = set(old_df[name_col].dropna().astype(str))
    new_keys = set(new_df[name_col].dropna().astype(str))
    added = sorted(new_keys - old_keys)
    removed = sorted(old_keys - new_keys)
    kept = len(old_keys & new_keys)

    result = {
        "old_path": str(old_path),
        "new_path": str(new_path),
        "old_total": len(old_keys),
        "new_total": len(new_keys),
        "kept": kept,
        "added": added,
        "removed": removed,
    }

    if args.json:
        print(_json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    head = (
        f"# {old_path.name} → {new_path.name}  "
        f"({len(old_keys):,} → {len(new_keys):,}곡, "
        f"+{len(added)} / -{len(removed)} / 유지 {kept:,})"
    )
    print(head)
    print("─" * len(head))
    # --limit 으로 너무 긴 리스트는 잘라 보여줌. 운영자 console 가독성 위함.
    limit = max(0, int(getattr(args, "limit", 50)))

    def _print_list(label: str, items: list[str]) -> None:
        print(f"  {label} ({len(items):,})")
        if not items:
            return
        shown = items if limit == 0 else items[:limit]
        for n in shown:
            print(f"    + {n}" if label.startswith("추가") else f"    - {n}")
        if limit and len(items) > limit:
            print(f"    ... and {len(items) - limit:,} more (전체는 --limit 0 또는 --json)")

    _print_list("추가된 곡", added)
    _print_list("제거된 곡", removed)
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """현재 빌드의 version / git_commit / release_date 를 출력한다.

    `/api/version` 과 동일한 정보를 서버 없이 즉시 확인하기 위함. CI 가
    배포 후 ``python -m backend.cli version`` 으로 deploy 가 기대한 SHA 와
    일치하는지 검증하는 데 쓰기 좋다. ``--json`` 으로 jq 파이프 친화 출력.
    """
    import json as _json

    # 백엔드 모듈에서 직접 끌어다 쓴다 — 같은 소스 of truth.
    from backend.main import _GIT_COMMIT, _RELEASE_DATE, app

    info = {
        "name": "soundmatch",
        "version": app.version,
        "release_date": _RELEASE_DATE,
        "git_commit": _GIT_COMMIT,
    }

    if args.json:
        print(_json.dumps(info, ensure_ascii=False, indent=2))
        return 0

    # 사람 친화 한 줄. 비어 있는 필드는 자연스럽게 생략.
    parts = [f"v{info['version']}"]
    if info["release_date"]:
        parts.append(info["release_date"])
    if info["git_commit"]:
        parts.append(info["git_commit"])
    print(" · ".join(parts))
    return 0


def cmd_export_catalog(args: argparse.Namespace) -> int:
    """카탈로그 CSV 를 q/BPM/에너지/정렬 필터로 가공해 새 CSV 로 떨군다.

    백엔드의 ``GET /api/catalog/export.csv`` 와 동일한 컬럼/필터를 그대로
    CLI 로 노출. 서버를 띄우지 않고도 CI / cron / Makefile 단계에서 같은
    결과물을 만들 수 있게 한다.

    출력 컬럼: ``title, artist, bpm, energy_rms, brightness, full_name``
    (API export 와 동일 — 운영자가 어디서 가져온 CSV 인지 헷갈리지 않게).

    동일한 CSV injection 방어 (셀이 ``= + - @`` 로 시작하면 ``'`` prefix) 와
    UTF-8 BOM 선두 → Excel 한글 호환 보장.
    """
    import csv as _csv

    import pandas as pd

    src = Path(args.dataset)
    if not src.exists():
        print(f"error: 데이터셋을 찾을 수 없습니다: {src}", file=sys.stderr)
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

    # ---- 필터링 (API 와 동일 의미) ----------------------------------
    needle = (args.q or "").strip().lower()
    if needle:
        df = df[df[name_col].str.lower().str.contains(needle, na=False)]
    if args.min_bpm is not None and "bpm" in df.columns:
        df = df[pd.to_numeric(df["bpm"], errors="coerce").fillna(0) >= args.min_bpm]
    if args.max_bpm is not None and "bpm" in df.columns:
        df = df[pd.to_numeric(df["bpm"], errors="coerce").fillna(0) <= args.max_bpm]
    if args.min_energy is not None and "rms_mean" in df.columns:
        df = df[pd.to_numeric(df["rms_mean"], errors="coerce").fillna(0) >= args.min_energy]
    if args.max_energy is not None and "rms_mean" in df.columns:
        df = df[pd.to_numeric(df["rms_mean"], errors="coerce").fillna(0) <= args.max_energy]

    # ---- 정렬 (default 면 입력 순서 유지) -----------------------------
    def _split(name: str) -> tuple[str, str]:
        title, _, artist = (name or "").partition(" - ")
        return title.strip() or name, artist.strip() or "Unknown"

    if args.sort == "title":
        df = df.sort_values(by=name_col, key=lambda s: s.map(lambda x: _split(x)[0].lower()))
    elif args.sort == "artist":
        df = df.sort_values(by=name_col, key=lambda s: s.map(lambda x: _split(x)[1].lower()))
    elif args.sort == "bpm" and "bpm" in df.columns:
        df = df.assign(_bpm_sort=pd.to_numeric(df["bpm"], errors="coerce").fillna(0)).sort_values("_bpm_sort").drop(columns=["_bpm_sort"])
    elif args.sort == "energy" and "rms_mean" in df.columns:
        df = df.assign(_e_sort=pd.to_numeric(df["rms_mean"], errors="coerce").fillna(0)).sort_values("_e_sort").drop(columns=["_e_sort"])

    # ---- CSV 직렬화 ------------------------------------------------
    def _safe(cell: object) -> str:
        s = "" if cell is None else str(cell)
        if s and s[0] in "=+-@":
            return "'" + s
        return s

    import io as _io

    buf = _io.StringIO()
    writer = _csv.writer(buf, lineterminator="\n")
    writer.writerow(["title", "artist", "bpm", "energy_rms", "brightness", "full_name"])
    rows_written = 0
    for _, row in df.iterrows():
        full = str(row[name_col])
        title, artist = _split(full)
        bpm = float(row.get("bpm", 0.0) or 0.0)
        rms = float(row.get("rms_mean", 0.0) or 0.0)
        sc = float(row.get("spectral_centroid_mean", 0.0) or 0.0)
        writer.writerow([
            _safe(title),
            _safe(artist),
            f"{bpm:.1f}" if bpm > 0 else "",
            f"{rms:.3f}" if rms > 0 else "",
            f"{sc:.0f}" if sc > 0 else "",
            _safe(full),
        ])
        rows_written += 1

    body = "﻿" + buf.getvalue()  # Excel 한글 호환 BOM.

    if args.stdout:
        # 파이프 친화 — BOM 없이 표준 CSV 만 흘림 (다른 도구가 BOM 을 헤더로 오인하는 케이스 회피).
        sys.stdout.write(buf.getvalue())
        print(f"# {rows_written}행 출력", file=sys.stderr)
        return 0

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body, encoding="utf-8")
    print(f"{rows_written}행 작성: {out_path}")
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

    stats = sub.add_parser(
        "dataset-stats",
        help="카탈로그 CSV 의 BPM/에너지/밝기/길이 분포를 콘솔에 요약 출력 (운영 sanity check).",
    )
    stats.add_argument("path", help="dataset.csv 경로")
    stats.add_argument("--json", action="store_true", help="JSON 만 출력 (jq 파이프 친화)")
    stats.set_defaults(func=cmd_dataset_stats)

    ver = sub.add_parser(
        "version",
        help="현재 빌드의 version / git_commit / release_date 를 출력 (서버 없이).",
    )
    ver.add_argument("--json", action="store_true", help="JSON 만 출력 (jq 파이프 친화)")
    ver.set_defaults(func=cmd_version)

    export_cat = sub.add_parser(
        "export-catalog",
        help="카탈로그 CSV 를 q/BPM/에너지/정렬 필터로 가공해 새 CSV 로 내보냄 (API export 의 CLI 미러).",
    )
    export_cat.add_argument(
        "--dataset", default="data/dataset.csv",
        help="원본 카탈로그 CSV 경로 (기본 data/dataset.csv)",
    )
    export_cat.add_argument("-q", "--query", dest="q", default="", help="제목/아티스트 부분 일치 (대소문자 무시)")
    export_cat.add_argument("--min-bpm", type=float, default=None, help="BPM 하한")
    export_cat.add_argument("--max-bpm", type=float, default=None, help="BPM 상한")
    export_cat.add_argument("--min-energy", type=float, default=None, help="RMS 에너지 하한 (0~1)")
    export_cat.add_argument("--max-energy", type=float, default=None, help="RMS 에너지 상한 (0~1)")
    export_cat.add_argument(
        "--sort", default="default",
        choices=["default", "title", "artist", "bpm", "energy"],
        help="정렬 (API 의 sort 와 동일)",
    )
    export_cat.add_argument(
        "-o", "--out", default="catalog-export.csv",
        help="출력 파일 경로 (기본 ./catalog-export.csv). --stdout 와 동시 사용 금지.",
    )
    export_cat.add_argument(
        "--stdout", action="store_true",
        help="결과를 파일 대신 표준 출력으로 (BOM 없음, 파이프 친화).",
    )
    export_cat.set_defaults(func=cmd_export_catalog)

    diff = sub.add_parser(
        "dataset-diff",
        help="두 카탈로그 CSV 간 added / removed 곡 목록을 비교.",
    )
    diff.add_argument("old", help="기존(이전) dataset.csv 경로")
    diff.add_argument("new", help="새(현재) dataset.csv 경로")
    diff.add_argument(
        "--limit", type=int, default=50,
        help="콘솔에 보여줄 각 목록의 최대 개수 (기본 50, 0 이면 무제한)",
    )
    diff.add_argument("--json", action="store_true", help="JSON 만 출력 (jq 파이프 친화)")
    diff.set_defaults(func=cmd_dataset_diff)

    compare = sub.add_parser("compare", help="두 음원 파일을 같은 카탈로그로 분석해 나란히 비교한다.")
    compare.add_argument("path_a", help="A 음원 파일 경로")
    compare.add_argument("path_b", help="B 음원 파일 경로")
    compare.add_argument(
        "--max-duration",
        type=float,
        default=30.0,
        help="각 파일을 이 초 수까지만 분석에 사용",
    )
    compare.add_argument(
        "--dataset",
        default="data/dataset.csv",
        help="카탈로그 CSV 경로",
    )
    compare.add_argument("--json", action="store_true", help="결과를 JSON 으로 출력")
    compare.set_defaults(func=cmd_compare)

    status = sub.add_parser(
        "status",
        help="떠 있는 서버의 /api/health 응답을 사람 친화적으로 표시 (운영 점검).",
    )
    status.add_argument("--url", default="http://127.0.0.1:8000", help="대상 base URL (기본 127.0.0.1:8000)")
    status.add_argument("--strict", action="store_true", help="?strict=true 로 호출 (librosa / 디스크 점검까지)")
    status.add_argument("--json", action="store_true", help="JSON 응답을 그대로 출력")
    status.add_argument("--timeout", type=float, default=5.0, help="네트워크 타임아웃 (초, 기본 5)")
    status.set_defaults(func=cmd_status)

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
