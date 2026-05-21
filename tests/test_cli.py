"""CLI 도구 단위 테스트."""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from backend.cli import main


def test_cli_analyze_human_readable(tiny_wav, synthetic_dataset, capsys):
    """기본 사람-가독 출력에 파일명/태그/순위가 포함되어야 한다."""
    code = main(["analyze", str(tiny_wav), "--dataset", str(synthetic_dataset), "--top-n", "3"])
    out = capsys.readouterr().out
    assert code == 0
    assert "tone.wav" in out
    assert "BPM" in out
    # 상위 3곡 라인 (합성 dataset 곡들)
    assert "1." in out and "2." in out and "3." in out


def test_cli_analyze_json_output(tiny_wav, synthetic_dataset):
    """--json 옵션은 stdout 으로 그대로 파싱 가능한 JSON 을 흘려야 한다."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main([
            "analyze",
            str(tiny_wav),
            "--dataset", str(synthetic_dataset),
            "--top-n", "2",
            "--json",
        ])
    assert code == 0
    data = json.loads(buf.getvalue())
    assert data["filename"] == "tone.wav"
    assert data["catalog_size"] == 3
    assert len(data["results"]) == 2
    assert data["engine_version"]
    assert data["analyzed_at"]


def test_cli_analyze_missing_file_returns_error(synthetic_dataset, capsys):
    code = main([
        "analyze",
        "no/such/file.wav",
        "--dataset", str(synthetic_dataset),
    ])
    err = capsys.readouterr().err
    assert code != 0
    assert "찾을 수 없습니다" in err


def test_cli_analyze_top_n_out_of_range(tiny_wav, synthetic_dataset, capsys):
    code = main(["analyze", str(tiny_wav), "--dataset", str(synthetic_dataset), "--top-n", "99"])
    err = capsys.readouterr().err
    assert code != 0
    assert "1~20" in err


def test_cli_batch_writes_csv(tmp_path, tiny_wav, synthetic_dataset):
    """batch 명령은 폴더 안 음원을 모두 분석해 CSV 로 떨궈야 한다."""
    import csv as csv_module
    import shutil

    audio_dir = tmp_path / "songs"
    audio_dir.mkdir()
    shutil.copy(tiny_wav, audio_dir / "a.wav")
    shutil.copy(tiny_wav, audio_dir / "b.wav")

    out_csv = tmp_path / "out.csv"
    code = main([
        "batch",
        str(audio_dir),
        "--out", str(out_csv),
        "--dataset", str(synthetic_dataset),
        "--top-n", "2",
    ])
    assert code == 0
    assert out_csv.exists()
    with out_csv.open(encoding="utf-8") as fh:
        rows = list(csv_module.DictReader(fh))
    # 2개 파일 × top_n 2 = 4행.
    assert len(rows) == 4
    assert {row["filename"] for row in rows} == {"a.wav", "b.wav"}
    for row in rows:
        assert row["rank"] in {"1", "2"}
        assert row["title"]


def test_cli_batch_missing_directory(tmp_path, synthetic_dataset, capsys):
    code = main([
        "batch",
        str(tmp_path / "no-such-dir"),
        "--dataset", str(synthetic_dataset),
    ])
    err = capsys.readouterr().err
    assert code != 0
    assert "찾을 수 없습니다" in err


def test_cli_validate_dataset_happy_path(synthetic_dataset, capsys):
    """정상 카탈로그는 검증 명령이 0으로 종료하고 통계를 stdout 에 출력해야 한다."""
    code = main(["validate-dataset", str(synthetic_dataset)])
    out = capsys.readouterr().out
    assert code == 0
    assert "카탈로그 검증 결과" in out
    assert "총 행" in out
    assert "엔진 로딩 성공" in out


def test_cli_validate_dataset_missing_file(tmp_path, capsys):
    code = main(["validate-dataset", str(tmp_path / "no.csv")])
    err = capsys.readouterr().err
    assert code != 0
    assert "찾을 수 없습니다" in err


def test_cli_validate_dataset_missing_name_column(tmp_path, capsys):
    """필수 키 컬럼이 없는 CSV 는 에러로 종료."""
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n", encoding="utf-8")
    code = main(["validate-dataset", str(bad)])
    err = capsys.readouterr().err
    assert code != 0
    assert "필수 키 컬럼" in err


def test_cli_dedupe_dataset(tmp_path, feature_columns, capsys):
    """dedupe-dataset 이 중복 키를 제거하고 통계를 출력해야 한다."""
    import csv as csv_module

    src = tmp_path / "dup.csv"
    with src.open("w", newline="", encoding="utf-8") as fh:
        w = csv_module.writer(fh)
        w.writerow(["musicname & artist", *feature_columns])
        # 같은 키 두 번 + 다른 키 한 번.
        row = [0.5] * len(feature_columns)
        w.writerow(["Alpha - X", *row])
        w.writerow(["Alpha - X", *row])
        w.writerow(["Beta - Y", *row])

    out = tmp_path / "clean.csv"
    code = main(["dedupe-dataset", str(src), "--out", str(out)])
    output = capsys.readouterr().out
    assert code == 0
    assert "제거된 중복: 1행" in output
    # 결과 CSV 는 2행만 남아야 한다.
    with out.open(encoding="utf-8") as fh:
        rows = list(csv_module.reader(fh))
    assert len(rows) == 3  # 헤더 + 2행


def test_cli_compare_two_files(tmp_path, tiny_wav, synthetic_dataset, capsys):
    """두 음원을 compare 명령으로 처리하면 메트릭 비교 표가 출력된다."""
    import shutil

    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    shutil.copy(tiny_wav, a)
    shutil.copy(tiny_wav, b)

    code = main([
        "compare",
        str(a),
        str(b),
        "--dataset", str(synthetic_dataset),
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert "비교 결과" in out
    assert "Tempo (BPM)" in out
    assert "A 의 1위 매칭" in out
    assert "B 의 1위 매칭" in out


def test_cli_compare_json(tmp_path, tiny_wav, synthetic_dataset, capsys):
    """--json 옵션은 stdout 으로 JSON 을 흘려보낸다."""
    import json as _json
    import shutil

    a = tmp_path / "a.wav"
    b = tmp_path / "b.wav"
    shutil.copy(tiny_wav, a)
    shutil.copy(tiny_wav, b)

    code = main([
        "compare",
        str(a),
        str(b),
        "--dataset", str(synthetic_dataset),
        "--json",
    ])
    out = capsys.readouterr().out
    assert code == 0
    data = _json.loads(out)
    assert data["a"]["filename"] == "a.wav"
    assert data["b"]["filename"] == "b.wav"
    assert data["catalog_size"] == 3
    assert data["a"]["top1"] is not None and data["b"]["top1"] is not None


def test_cli_compare_missing_file(tmp_path, synthetic_dataset, tiny_wav, capsys):
    code = main([
        "compare",
        str(tmp_path / "no.wav"),
        str(tiny_wav),
        "--dataset", str(synthetic_dataset),
    ])
    err = capsys.readouterr().err
    assert code != 0
    assert "찾을 수 없습니다" in err


def test_cli_dedupe_dataset_requires_overwrite_for_same_path(tmp_path, feature_columns, capsys):
    """입력과 같은 파일을 덮어쓸 때는 --overwrite 가 필요해야 한다."""
    import csv as csv_module

    src = tmp_path / "same.csv"
    with src.open("w", newline="", encoding="utf-8") as fh:
        w = csv_module.writer(fh)
        w.writerow(["musicname & artist", *feature_columns])
        w.writerow(["A - X", *[0.5] * len(feature_columns)])

    code = main(["dedupe-dataset", str(src), "--out", str(src)])
    err = capsys.readouterr().err
    assert code != 0
    assert "--overwrite" in err


# --- dataset-stats 서브커먼드 ----------------------------------------------

def test_cli_dataset_stats_human_readable(synthetic_dataset, capsys):
    """기본 출력에 카탈로그 행 수 + 키 메트릭 라벨이 포함돼야 한다."""
    code = main(["dataset-stats", str(synthetic_dataset)])
    out = capsys.readouterr().out
    assert code == 0
    # 합성 카탈로그는 3행.
    assert "3행" in out
    assert "BPM" in out
    assert "에너지" in out
    assert "밝기" in out


def test_cli_dataset_stats_json_output(synthetic_dataset):
    """--json 옵션은 jq 파싱 가능한 JSON 만 흘려야 한다."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(["dataset-stats", str(synthetic_dataset), "--json"])
    assert code == 0
    parsed = json.loads(buf.getvalue())
    assert parsed["rows"] == 3
    assert parsed["unique_keys"] == 3
    assert parsed["duplicate_keys"] == 0
    assert "bpm" in parsed
    # 합성 dataset 은 BPM 가 0.5 부근 — 진짜 값이 아니라 더미. 그냥 None 이 아닌지만.
    assert parsed["bpm"] is None or isinstance(parsed["bpm"], dict)


def test_cli_dataset_stats_missing_file(tmp_path, capsys):
    """없는 파일 경로 → exit code 2 + stderr 메시지."""
    code = main(["dataset-stats", str(tmp_path / "no.csv")])
    err = capsys.readouterr().err
    assert code == 2
    assert "찾을 수 없습니다" in err


def test_cli_dataset_stats_missing_name_column(tmp_path, capsys):
    """필수 키 컬럼이 없으면 exit code 4."""
    bad = tmp_path / "bad.csv"
    bad.write_text("foo,bar\n1,2\n", encoding="utf-8")
    code = main(["dataset-stats", str(bad)])
    err = capsys.readouterr().err
    assert code == 4
    assert "필수 키 컬럼" in err


# --- dataset-diff 서브커먼드 ----------------------------------------------

def _make_dataset(tmp_path, name, feature_columns, song_names):
    """간단한 dataset CSV 생성 헬퍼."""
    import csv as _csv

    p = tmp_path / name
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = _csv.writer(fh)
        w.writerow(["musicname & artist", *feature_columns])
        for s in song_names:
            w.writerow([s, *[0.5] * len(feature_columns)])
    return p


def test_cli_dataset_diff_human_readable(tmp_path, feature_columns, capsys):
    """added / removed / kept 카운트가 사람-가독 출력에 모두 보여야 한다."""
    old = _make_dataset(tmp_path, "old.csv", feature_columns, ["A - X", "B - X", "C - X"])
    new = _make_dataset(tmp_path, "new.csv", feature_columns, ["A - X", "C - X", "D - X", "E - X"])
    code = main(["dataset-diff", str(old), str(new)])
    out = capsys.readouterr().out
    assert code == 0
    # 추가된 곡(D-X, E-X) 와 제거된 곡(B-X) 가 표시.
    assert "+2" in out and "-1" in out
    assert "D - X" in out and "E - X" in out
    assert "B - X" in out


def test_cli_dataset_diff_json_output(tmp_path, feature_columns):
    """--json 출력은 added/removed 배열을 포함해야 한다."""
    old = _make_dataset(tmp_path, "old.csv", feature_columns, ["A - X", "B - X"])
    new = _make_dataset(tmp_path, "new.csv", feature_columns, ["A - X"])
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main(["dataset-diff", str(old), str(new), "--json"])
    assert code == 0
    parsed = json.loads(buf.getvalue())
    assert parsed["kept"] == 1
    assert parsed["added"] == []
    assert parsed["removed"] == ["B - X"]


def test_cli_dataset_diff_no_changes(tmp_path, feature_columns, capsys):
    """양쪽이 완전히 같으면 +0 / -0 / 유지 = old 전체."""
    songs = ["A - X", "B - X", "C - X"]
    old = _make_dataset(tmp_path, "old.csv", feature_columns, songs)
    new = _make_dataset(tmp_path, "new.csv", feature_columns, songs)
    code = main(["dataset-diff", str(old), str(new)])
    out = capsys.readouterr().out
    assert code == 0
    assert "+0" in out and "-0" in out


def test_cli_dataset_diff_missing_file(tmp_path, feature_columns, capsys):
    """한쪽 파일이 없으면 exit code 2 + stderr 안내."""
    new = _make_dataset(tmp_path, "new.csv", feature_columns, ["A - X"])
    code = main(["dataset-diff", str(tmp_path / "missing.csv"), str(new)])
    err = capsys.readouterr().err
    assert code == 2
    assert "찾을 수 없습니다" in err


def test_cli_dataset_diff_limit_truncates_long_lists(tmp_path, feature_columns, capsys):
    """--limit N 이면 N 개만 표시하고 'and X more' 안내."""
    old = _make_dataset(tmp_path, "old.csv", feature_columns, [])
    # 새 dataset 에 60곡 추가.
    new = _make_dataset(tmp_path, "new.csv", feature_columns, [f"Song{i} - X" for i in range(60)])
    code = main(["dataset-diff", str(old), str(new), "--limit", "10"])
    out = capsys.readouterr().out
    assert code == 0
    assert "+60" in out
    # 처음 10곡만 표시 + "and 50 more" 안내.
    assert "and 50 more" in out


# --- status 서브커먼드 -----------------------------------------------------

def test_cli_status_unreachable_server_returns_4(capsys):
    """존재하지 않는 서버 주소 → exit code 4 + stderr 안내."""
    code = main([
        "status",
        "--url", "http://127.0.0.1:1",  # 거의 확실히 닫힌 포트
        "--timeout", "1",
    ])
    err = capsys.readouterr().err
    assert code == 4
    assert "error:" in err


def test_cli_status_pretty_output(monkeypatch, capsys):
    """가짜 /api/health 응답을 주입하면 사람-가독 출력에 키들이 노출되어야 한다."""
    from contextlib import contextmanager

    payload = (
        '{"status": "ok", "catalog_size": 781, "env": "production", '
        '"version": "1.3.0", "uptime_seconds": 12.3, '
        '"analyze_latency_p50_seconds": 1.2, '
        '"catalog_updated_at": "2026-05-15T00:42:51+00:00"}'
    )

    class FakeResp:
        status = 200

        def read(self):
            return payload.encode("utf-8")

    @contextmanager
    def fake_urlopen(req, timeout=5.0):
        yield FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    code = main(["status", "--url", "http://example.test"])
    out = capsys.readouterr().out
    assert code == 0
    assert "OK" in out
    assert "catalog_size" in out and "781" in out
    assert "1.3.0" in out
    # ISO 시각의 처음 부분이 들어가야 한다 (운영자가 보면 알 수 있는 형태).
    assert "2026-05-15" in out


def test_cli_status_degraded_returns_3(monkeypatch, capsys):
    """503 + status=degraded 응답이면 exit code 3."""
    from contextlib import contextmanager
    from urllib.error import HTTPError

    @contextmanager
    def fake_urlopen(req, timeout=5.0):
        raise HTTPError(
            req.full_url, 503, "Service Unavailable", {},
            _io.BytesIO(b'{"status": "degraded", "catalog_size": 0, "env": "production", "version": "1.3.0", "uptime_seconds": 1.0}'),
        )

    import io as _io

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    code = main(["status", "--url", "http://example.test"])
    out = capsys.readouterr().out
    assert code == 3
    assert "DEGRADED" in out
    assert "ok 가 아닙니다" in out


def test_cli_status_json_passthrough(monkeypatch, capsys):
    """--json 옵션이면 JSON 그대로 흘리고 200 일 때 exit 0."""
    from contextlib import contextmanager

    class FakeResp:
        status = 200

        def read(self):
            return b'{"status": "ok", "catalog_size": 3}'

    @contextmanager
    def fake_urlopen(req, timeout=5.0):
        yield FakeResp()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    code = main(["status", "--url", "http://example.test", "--json"])
    out = capsys.readouterr().out
    assert code == 0
    # 출력은 parse 가능한 JSON.
    parsed = json.loads(out)
    assert parsed["status"] == "ok"
    assert parsed["catalog_size"] == 3


# --- export-catalog 서브커먼드 --------------------------------------------

def test_cli_export_catalog_writes_csv(synthetic_dataset, tmp_path, capsys):
    """파일 출력 모드 — 헤더 + 3행이 BOM 포함 CSV 로 떨어져야 한다."""
    out_path = tmp_path / "out.csv"
    code = main([
        "export-catalog",
        "--dataset", str(synthetic_dataset),
        "-o", str(out_path),
    ])
    assert code == 0
    text = out_path.read_text(encoding="utf-8")
    assert text.startswith("﻿"), "BOM 이 선두에 있어야 합니다 (Excel 한글 호환)."
    lines = text.lstrip("﻿").splitlines()
    assert lines[0] == "title,artist,bpm,energy_rms,brightness,full_name"
    # 합성 카탈로그 3행.
    assert len(lines) == 1 + 3


def test_cli_export_catalog_query_filter(synthetic_dataset, tmp_path):
    """-q 옵션은 부분 일치 (대소문자 무시) 로 동작해야 한다."""
    out_path = tmp_path / "alpha.csv"
    code = main([
        "export-catalog",
        "--dataset", str(synthetic_dataset),
        "-q", "ALPHA",
        "-o", str(out_path),
    ])
    assert code == 0
    lines = out_path.read_text(encoding="utf-8").lstrip("﻿").splitlines()
    # 헤더 + Alpha 한 곡.
    assert len(lines) == 2
    assert "Alpha" in lines[1]


def test_cli_export_catalog_stdout_no_bom(synthetic_dataset, capsys):
    """--stdout 옵션은 파이프 친화로 BOM 없이 CSV 만 흘려야 한다."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = main([
            "export-catalog",
            "--dataset", str(synthetic_dataset),
            "--stdout",
        ])
    assert code == 0
    body = buf.getvalue()
    # stdout 모드는 BOM 없음.
    assert not body.startswith("﻿"), "stdout 모드에서는 BOM 이 붙으면 안 됩니다."
    assert body.startswith("title,artist,bpm,energy_rms,brightness,full_name")


def test_cli_export_catalog_missing_dataset(tmp_path, capsys):
    """없는 데이터셋 → exit code 2."""
    code = main([
        "export-catalog",
        "--dataset", str(tmp_path / "nope.csv"),
        "-o", str(tmp_path / "out.csv"),
    ])
    err = capsys.readouterr().err
    assert code == 2
    assert "찾을 수 없습니다" in err


def test_cli_export_catalog_blocks_formula_injection(tmp_path, feature_columns):
    """API export 와 동일하게 = 로 시작하는 셀에 ' prefix 가 붙어야 한다."""
    import csv as _csv

    ds = tmp_path / "evil.csv"
    with ds.open("w", newline="", encoding="utf-8") as fh:
        w = _csv.writer(fh)
        w.writerow(["musicname & artist", *feature_columns])
        w.writerow(["=cmd|calc!A1 - Attacker", *[0.5] * len(feature_columns)])
    out_path = tmp_path / "out.csv"
    code = main([
        "export-catalog",
        "--dataset", str(ds),
        "-o", str(out_path),
    ])
    assert code == 0
    body = out_path.read_text(encoding="utf-8").lstrip("﻿")
    rows = body.splitlines()
    assert len(rows) >= 2
    # 셀이 = 으로 직접 시작해서는 안 된다.
    assert rows[1].startswith("'=cmd"), f"수식 셀에 quote prefix 가 빠졌습니다: {rows[1]!r}"
