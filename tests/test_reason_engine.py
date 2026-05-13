"""Tests for the human-readable reason engine."""
from __future__ import annotations

from backend.reason_engine import (
    FEATURE_GROUPS,
    _has_final_jongseong,
    _i_ga,
    explain_match,
    report_to_dict,
)


def _make_features():
    """Realistic-ish feature dicts so the engine has something to compare."""
    q = {
        "bpm": 128.0,
        "rms_mean": 0.31,
        "rms_var": 0.005,
        "spectral_centroid_mean": 3120.5,
        "spectral_centroid_var": 350000.0,
        "spectral_bandwidth_mean": 2700.0,
        "spectral_bandwidth_var": 100000.0,
        "spectral_rolloff_mean": 6000.0,
        "spectral_rolloff_var": 1400000.0,
        "zero_crossing_rate_mean": 0.12,
        "zero_crossing_rate_var": 0.10,
        "harmony_mean": 1e-5,
        "harmony_var": 0.04,
        "percussive_mean": 1e-5,
        "percussive_var": 0.01,
        "chroma_frequencies_mean": 0.34,
        "chroma_frequencies_var": 0.08,
    }
    for i in range(1, 21):
        q[f"mfcc{i}_mean"] = 0.0
        q[f"mfcc{i}_var"] = 100.0
    c = dict(q)
    c["bpm"] = 130.0
    c["spectral_centroid_mean"] = 3150.0
    return q, c


def test_jongseong_detection():
    # Korean syllable with final consonant.
    assert _has_final_jongseong("템포") is False  # 포 has no jongseong
    assert _has_final_jongseong("음악") is True  # 악 has jongseong
    # Trailing parens fall through to next Korean char.
    assert _has_final_jongseong("거친 정도(노이즈성)") is True
    # Non-Korean trailing alphabetics are treated as no-jongseong.
    assert _has_final_jongseong("BPM") is False


def test_i_ga_picks_correct_particle():
    assert _i_ga("템포") == "가"
    assert _i_ga("음악") == "이"


def test_explain_match_returns_summary_and_groups():
    q, c = _make_features()
    distances = {k: 0.05 for k in q}
    distances["bpm"] = 0.02
    distances["spectral_centroid_mean"] = 0.03

    report = explain_match(q, c, distances)
    assert report.summary
    assert "**" in report.summary, "Summary should bold the top-matching concept"
    assert 1 <= len(report.groups) <= 3
    # All groups must be sorted by descending match_score.
    scores = [g.match_score for g in report.groups]
    assert scores == sorted(scores, reverse=True)
    # Each group has a non-empty summary; most have detail bullets.
    for g in report.groups:
        assert g.label in FEATURE_GROUPS
        assert g.summary
        assert isinstance(g.detail, list)


def test_explain_match_handles_negative_values():
    """Negative-valued features (mfcc, harmony) shouldn't make ratio go weird."""
    q, c = _make_features()
    q["mfcc1_mean"] = -24.5
    c["mfcc1_mean"] = -23.1
    distances = {k: 0.05 for k in q}
    distances["mfcc1_mean"] = 0.04

    report = explain_match(q, c, distances)
    text = " ".join(d for g in report.groups for d in g.detail)
    # No negative ratios or NaN substrings should leak into Korean output.
    assert "nan" not in text.lower()
    assert "inf" not in text.lower()


def test_report_to_dict_is_json_safe():
    q, c = _make_features()
    distances = {k: 0.05 for k in q}
    report = explain_match(q, c, distances)
    payload = report_to_dict(report)
    import json

    # Should serialise round-trip without surprises.
    json.loads(json.dumps(payload, ensure_ascii=False))


def test_explain_match_identical_features():
    """Identical query/catalog vectors should produce 'very close' summaries."""
    q, c = _make_features()
    c = dict(q)  # exact copy
    distances = {k: 0.0 for k in q}
    report = explain_match(q, c, distances)
    # The top group's score is near 1.0.
    assert report.groups[0].match_score > 0.95
