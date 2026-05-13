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
