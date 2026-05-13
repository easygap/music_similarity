"""휴리스틱 태깅 모듈 단위 테스트."""
from __future__ import annotations

from backend.audio_features import FEATURE_COLUMNS, AudioFeatureVector
from backend.tagging import derive_tags


def _vec(**overrides) -> AudioFeatureVector:
    values = {c: 0.0 for c in FEATURE_COLUMNS}
    values.update(overrides)
    return AudioFeatureVector(name="t", values=values)


def test_derive_tags_returns_list():
    """기본 케이스: 0인 벡터에 대해서도 크래시 없이 빈 리스트 반환."""
    assert isinstance(derive_tags(_vec()), list)


def test_fast_tempo_tag():
    tags = derive_tags(_vec(bpm=170.0, rms_mean=0.3, spectral_centroid_mean=4000.0))
    assert "매우 빠름" in tags


def test_slow_tempo_tag():
    tags = derive_tags(_vec(bpm=55.0, rms_mean=0.05, spectral_centroid_mean=900.0))
    assert "매우 느림" in tags
    assert "잔잔" in tags
    assert "어두운 톤" in tags


def test_energy_explosion_tag():
    tags = derive_tags(_vec(bpm=120.0, rms_mean=0.4, spectral_centroid_mean=3000.0))
    assert "에너지 폭발" in tags


def test_bright_tone_tag():
    tags = derive_tags(_vec(bpm=120.0, rms_mean=0.15, spectral_centroid_mean=5000.0))
    assert "밝은 톤" in tags


def test_rough_texture_tag():
    tags = derive_tags(
        _vec(bpm=140.0, rms_mean=0.2, spectral_centroid_mean=3000.0, zero_crossing_rate_mean=0.2)
    )
    assert "거친 질감" in tags


def test_melody_dominant_tag():
    tags = derive_tags(
        _vec(
            bpm=100.0,
            rms_mean=0.15,
            spectral_centroid_mean=2000.0,
            harmony_mean=0.3,
            percussive_mean=0.05,
        )
    )
    assert "멜로디 위주" in tags


def test_beat_dominant_tag():
    tags = derive_tags(
        _vec(
            bpm=100.0,
            rms_mean=0.15,
            spectral_centroid_mean=2000.0,
            harmony_mean=0.05,
            percussive_mean=0.3,
        )
    )
    assert "비트 위주" in tags


def test_tags_have_no_duplicates():
    """동일 태그가 중복 노출되면 안 된다."""
    tags = derive_tags(_vec(bpm=170.0, rms_mean=0.4, spectral_centroid_mean=5000.0))
    assert len(tags) == len(set(tags))
