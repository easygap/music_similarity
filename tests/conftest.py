"""테스트 전반에서 쓰는 공통 픽스처."""
from __future__ import annotations

import csv
import math
import sys
import wave
from pathlib import Path

import pytest

# 저장소 루트에서 pytest 를 실행해도 ``backend`` 패키지가 임포트되게 한다.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def real_dataset_path(repo_root: Path) -> Path:
    return repo_root / "data" / "dataset.csv"


@pytest.fixture(scope="session")
def feature_columns():
    """프로덕션 모듈에서 정의된 표준 컬럼 순서를 그대로 노출."""
    from backend.audio_features import FEATURE_COLUMNS
    return list(FEATURE_COLUMNS)


@pytest.fixture()
def synthetic_dataset(tmp_path: Path, feature_columns) -> Path:
    """합성 카탈로그 CSV를 만들어 준다.

    각 행이 조금씩 다른 값을 가지도록 해서 코사인 유사도가 자명한 결과
    (1.0 또는 0.0) 만 내지 않게 한다.
    """
    csv_path = tmp_path / "dataset.csv"
    rows = []
    base = {c: 0.5 for c in feature_columns}
    for i, name in enumerate(["Alpha - Tester", "Beta - Tester", "Gamma - Tester"]):
        row = dict(base)
        for j, c in enumerate(feature_columns):
            row[c] = 0.5 + 0.1 * i + 0.01 * j
        # length 는 라벨 용도라서 분석에는 안 들어가지만 CSV에는 채워둔다.
        row["length"] = 1000 + i
        rows.append(("musicname & artist", name, row))

    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["musicname & artist", *feature_columns])
        for _key, name, row in rows:
            writer.writerow([name, *[row[c] for c in feature_columns]])
    return csv_path


@pytest.fixture()
def tiny_wav(tmp_path: Path) -> Path:
    """테스트용 2초 짜리 모노 22050Hz 사인파 WAV."""
    path = tmp_path / "tone.wav"
    sr = 22050
    duration = 2.0
    freq = 440.0
    nframes = int(sr * duration)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)  # 16-bit
        w.setframerate(sr)
        frames = bytearray()
        for n in range(nframes):
            val = int(32767 * 0.3 * math.sin(2 * math.pi * freq * n / sr))
            frames.extend(val.to_bytes(2, "little", signed=True))
        w.writeframes(bytes(frames))
    return path


@pytest.fixture()
def bogus_audio(tmp_path: Path) -> Path:
    """확장자만 .wav 인 쓰레기 파일. 매직 바이트 검증 실패 경로 테스트용."""
    p = tmp_path / "fake.wav"
    p.write_bytes(b"this is not audio at all")
    return p


@pytest.fixture()
def html_disguised_as_mp3(tmp_path: Path) -> Path:
    """HTML 을 mp3 로 위장한 파일. 매직 바이트 검사가 막아내야 한다."""
    p = tmp_path / "evil.mp3"
    p.write_bytes(b"<html><script>alert(1)</script></html>")
    return p


@pytest.fixture()
def fastapi_client(monkeypatch, synthetic_dataset, tmp_path):
    """합성 데이터셋 + 격리된 업로드 디렉토리를 가리키는 TestClient."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    monkeypatch.setenv("MUSIC_DATASET_PATH", str(synthetic_dataset))
    monkeypatch.setenv("MUSIC_UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("MUSIC_RATE_LIMIT_PER_MIN", "100")  # 테스트에서 rate limit 안 걸리게.
    monkeypatch.setenv("MUSIC_ENV", "test")
    monkeypatch.setenv("MUSIC_SKIP_WARMUP", "1")  # 워밍업으로 테스트 시간 늘리지 않기.

    # 모듈 레벨 상수들이 새 환경변수를 읽도록 backend 모듈을 다시 임포트.
    for mod in list(sys.modules):
        if mod.startswith("backend"):
            del sys.modules[mod]

    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as client:
        yield client
