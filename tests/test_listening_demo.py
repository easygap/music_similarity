"""배포하는 샘플, 화면 수치, 기존 분석 엔진이 같은 음원을 설명하는지 검증한다."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from sklearn.metrics.pairwise import cosine_similarity

from backend.audio_features import extract_features, summary_metrics
from backend.similarity import MusicSimilarityEngine

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "frontend" / "assets" / "demo"


def test_samples_and_displayed_scores_match_engine():
    data = json.loads((DEMO / "analysis.json").read_text(encoding="utf-8"))
    engine = MusicSimilarityEngine(ROOT / "data" / "dataset.csv")
    assert data["featureCount"] == len(engine.feature_columns) == 57
    vectors = []
    for track in data["tracks"]:
        path = DEMO / (track["id"] + ".wav")
        assert hashlib.sha256(path.read_bytes()).hexdigest() == track["sha256"]
        y, rate = sf.read(path)
        assert rate == data["sampleRate"]
        assert len(y) / rate == pytest.approx(track["duration"], abs=.001)
        assert path.stat().st_size == track["bytes"]
        peaks = [np.max(np.abs(chunk)) for chunk in np.array_split(y, 144)]
        assert peaks == pytest.approx(track["waveform"], abs=.0001)
        surface = np.array(track["surface"])
        assert surface.shape == (40, 48)
        assert np.all((surface >= 0) & (surface <= 255))
        features = extract_features(path)
        assert summary_metrics(features) == pytest.approx(track["summary"], rel=.002, abs=.0001)
        vectors.append(engine._scaler.transform([[features.values[key] for key in engine.feature_columns]])[0])
    for index, comparison in enumerate(data["comparisons"], start=1):
        score = max(0, cosine_similarity([vectors[0]], [vectors[index]])[0, 0] * 100)
        assert score == pytest.approx(comparison["similarityPercent"], abs=.1)
    assert data["comparisons"][0]["similarityPercent"] > data["comparisons"][1]["similarityPercent"]


def test_text_compression_preserves_audio_ranges(fastapi_client):
    client = fastapi_client
    compressed = client.get("/style.css", headers={"Accept-Encoding": "gzip"})
    plain = client.get("/style.css", headers={"Accept-Encoding": "identity"})
    assert compressed.headers["content-encoding"] == "gzip"
    assert "accept-encoding" in compressed.headers["vary"].lower()
    assert compressed.content == plain.content
    with client.stream("GET", "/style.css", headers={"Accept-Encoding": "gzip"}) as response:
        encoded = b"".join(response.iter_raw())
    assert len(encoded) < len(plain.content) / 2

    expected = (DEMO / "original.wav").read_bytes()
    part = client.get("/static/assets/demo/original.wav", headers={"Range": "bytes=100-999", "Accept-Encoding": "gzip"})
    assert part.status_code == 206
    assert part.content == expected[100:1000]
    assert "content-encoding" not in part.headers
    assert part.headers["content-range"] == f"bytes 100-999/{len(expected)}"
