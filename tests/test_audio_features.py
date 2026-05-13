"""Tests for the librosa feature extraction layer."""
from __future__ import annotations

import math

import numpy as np
import pytest

from backend.audio_features import (
    FEATURE_COLUMNS,
    AudioFeatureVector,
    extract_features,
    summary_metrics,
)


def test_feature_columns_layout():
    """The canonical column list matches the original capstone CSV."""
    # 18 base + 20 mfccs * 2 (mean+var) = 58 columns total.
    assert len(FEATURE_COLUMNS) == 58
    # Order: length first, then RMS/BPM/...
    assert FEATURE_COLUMNS[0] == "length"
    assert FEATURE_COLUMNS[3] == "bpm"
    # Last 40 are MFCCs.
    assert FEATURE_COLUMNS[-40:] == [
        f"mfcc{i}_{stat}" for i in range(1, 21) for stat in ("mean", "var")
    ]


def test_extract_features_synthetic_wav(tiny_wav):
    """All declared columns are present and finite for a clean sine wave."""
    vec = extract_features(tiny_wav)
    assert isinstance(vec, AudioFeatureVector)
    assert set(vec.values) == set(FEATURE_COLUMNS)
    arr = np.array([vec.values[c] for c in FEATURE_COLUMNS], dtype=float)
    assert np.isfinite(arr).all(), "Feature extraction produced non-finite values"


def test_extract_features_short_clip(tmp_path):
    """librosa should still return a usable vector for a 0.5s clip."""
    import wave

    sr = 22050
    path = tmp_path / "short.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        frames = bytearray()
        for n in range(int(sr * 0.5)):
            v = int(20000 * math.sin(2 * math.pi * 220 * n / sr))
            frames.extend(v.to_bytes(2, "little", signed=True))
        w.writeframes(bytes(frames))

    vec = extract_features(path, max_duration=10)
    assert "bpm" in vec.values
    assert math.isfinite(vec.values["rms_mean"])


def test_extract_features_rejects_empty_audio(tmp_path):
    """A 0-byte 'audio' file should raise rather than silently return zeros."""
    import wave

    path = tmp_path / "empty.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"")
    with pytest.raises((ValueError, RuntimeError)):
        extract_features(path)


def test_summary_metrics_shape(tiny_wav):
    vec = extract_features(tiny_wav)
    s = summary_metrics(vec)
    for k in (
        "tempo_bpm",
        "energy_rms",
        "brightness",
        "noisiness",
        "harmony_ratio",
        "chroma",
    ):
        assert k in s
        assert math.isfinite(float(s[k]))
