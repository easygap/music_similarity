"""사용자 가독 reason 엔진 테스트."""
from __future__ import annotations

from backend.reason_engine import (
    FEATURE_GROUPS,
    _has_final_jongseong,
    _i_ga,
    explain_match,
    report_to_dict,
)


def _make_features():
    """엔진이 비교할 거리감이 있는 현실적인 raw 특성 두 벌을 만든다."""
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
    # 받침이 없는 한글 음절.
    assert _has_final_jongseong("템포") is False  # 포 → 받침 없음
    assert _has_final_jongseong("음악") is True   # 악 → 받침 있음
    # 괄호 같은 비한글 문자가 끝에 붙어도 직전 한글 음절을 봐야 한다.
    assert _has_final_jongseong("거친 정도(노이즈성)") is True
    # 영문/숫자만 들어 있으면 받침 없음으로 보수적으로 처리.
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
    assert "**" in report.summary, "최상위 요약에 강조(**) 표시가 있어야 한다"
    assert 1 <= len(report.groups) <= 3
    # 그룹은 match_score 내림차순으로 정렬되어야 한다.
    scores = [g.match_score for g in report.groups]
    assert scores == sorted(scores, reverse=True)
    # 각 그룹은 비어있지 않은 summary 와 디테일 리스트를 가져야 한다.
    for g in report.groups:
        assert g.label in FEATURE_GROUPS
        assert g.summary
        assert isinstance(g.detail, list)


def test_explain_match_handles_negative_values():
    """mfcc, harmony 처럼 음수가 자연스러운 특성에서도 비율이 이상하게 나오지 않아야."""
    q, c = _make_features()
    q["mfcc1_mean"] = -24.5
    c["mfcc1_mean"] = -23.1
    distances = {k: 0.05 for k in q}
    distances["mfcc1_mean"] = 0.04

    report = explain_match(q, c, distances)
    text = " ".join(d for g in report.groups for d in g.detail)
    # 출력 한국어 안에 nan/inf 같은 단어가 새어 나오면 안 됨.
    assert "nan" not in text.lower()
    assert "inf" not in text.lower()


def test_report_to_dict_is_json_safe():
    q, c = _make_features()
    distances = {k: 0.05 for k in q}
    report = explain_match(q, c, distances)
    payload = report_to_dict(report)
    import json

    # 라운드트립으로 직렬화가 깔끔하게 되는지 확인.
    json.loads(json.dumps(payload, ensure_ascii=False))


def test_explain_match_identical_features():
    """쿼리 = 매칭이면 최상위 그룹의 match_score 가 1.0 에 가까워야 한다."""
    q, c = _make_features()
    c = dict(q)  # 완전 동일한 복사본
    distances = {k: 0.0 for k in q}
    report = explain_match(q, c, distances)
    assert report.groups[0].match_score > 0.95
