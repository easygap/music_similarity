"""Shared pytest fixtures."""
from __future__ import annotations

import csv
import math
import sys
import wave
from pathlib import Path

import pytest

# Make `backend` importable when running pytest from repo root.
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
    """Pull the canonical feature order from the production module."""
    from backend.audio_features import FEATURE_COLUMNS
    return list(FEATURE_COLUMNS)


@pytest.fixture()
def synthetic_dataset(tmp_path: Path, feature_columns) -> Path:
    """Build a minimal in-memory dataset CSV with a few synthetic rows.

    Each row gets distinct feature values so cosine similarity has something
    non-degenerate to chew on.
    """
    csv_path = tmp_path / "dataset.csv"
    rows = []
    base = {c: 0.5 for c in feature_columns}
    for i, name in enumerate(["Alpha - Tester", "Beta - Tester", "Gamma - Tester"]):
        row = dict(base)
        for j, c in enumerate(feature_columns):
            row[c] = 0.5 + 0.1 * i + 0.01 * j
        # length is used as label only.
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
    """A 2-second mono 22050Hz sine wave."""
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
    """A file with the right extension but garbage content."""
    p = tmp_path / "fake.wav"
    p.write_bytes(b"this is not audio at all")
    return p


@pytest.fixture()
def html_disguised_as_mp3(tmp_path: Path) -> Path:
    p = tmp_path / "evil.mp3"
    p.write_bytes(b"<html><script>alert(1)</script></html>")
    return p


@pytest.fixture()
def fastapi_client(monkeypatch, synthetic_dataset, tmp_path):
    """A TestClient pointed at a synthetic dataset and isolated upload dir."""
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    monkeypatch.setenv("MUSIC_DATASET_PATH", str(synthetic_dataset))
    monkeypatch.setenv("MUSIC_UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("MUSIC_RATE_LIMIT_PER_MIN", "100")  # don't trip in tests
    monkeypatch.setenv("MUSIC_ENV", "test")

    # Fresh import so the module-level constants pick up the env vars.
    for mod in list(sys.modules):
        if mod.startswith("backend"):
            del sys.modules[mod]

    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app) as client:
        yield client
