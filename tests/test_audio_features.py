"""librosa 특성 추출 레이어 테스트."""
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
    """표준 컬럼 순서가 원본 캡스톤 CSV와 동일해야 한다."""
    # 18개 기본 + 20개 MFCC * 2(mean+var) = 58.
    assert len(FEATURE_COLUMNS) == 58
    # 순서: length, rms_mean, rms_var, bpm, ...
    assert FEATURE_COLUMNS[0] == "length"
    assert FEATURE_COLUMNS[3] == "bpm"
    # 마지막 40개가 MFCC.
    assert FEATURE_COLUMNS[-40:] == [
        f"mfcc{i}_{stat}" for i in range(1, 21) for stat in ("mean", "var")
    ]


def test_extract_features_synthetic_wav(tiny_wav):
    """클린한 사인파 wav 에 대해 58개 특성이 전부 finite 값으로 나와야 한다."""
    vec = extract_features(tiny_wav)
    assert isinstance(vec, AudioFeatureVector)
    assert set(vec.values) == set(FEATURE_COLUMNS)
    arr = np.array([vec.values[c] for c in FEATURE_COLUMNS], dtype=float)
    assert np.isfinite(arr).all(), "특성 추출 결과에 non-finite 값이 섞여 있음"


def test_extract_features_short_clip(tmp_path):
    """0.5초 짜리 짧은 클립도 librosa 가 처리할 수 있어야 한다."""
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
    """0바이트 오디오는 조용히 0을 돌려주지 않고 예외를 던져야 한다."""
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
    """summary_metrics 의 6개 필드가 모두 finite 값으로 나와야 한다."""
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
