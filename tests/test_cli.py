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
