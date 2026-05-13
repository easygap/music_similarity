"""오디오 특성으로부터 사용자 친화적인 태그 몇 개를 뽑아내는 모듈.

장르를 정확히 분류하는 모델이 아니다 — 우리가 가진 58개 특성을 보고 합리적으로
"이 곡은 이런 느낌일 것 같다" 정도의 휴리스틱 라벨을 붙이는 게 목표다.
태그는 결과 카드 + 비교 화면에서 가독성 좋게 노출된다.

태그 후보(중복 가능, 보통 곡당 2~4개 노출):
    템포: 매우 빠름 / 빠름 / 미디엄 / 느림 / 매우 느림
    에너지: 에너지 폭발 / 다이내믹 / 잔잔
    음색: 밝은 톤 / 미드 톤 / 어두운 톤
    질감: 거친 / 부드러운
    화성/타악기: 멜로디 위주 / 비트 위주 / 균형
"""
from __future__ import annotations

from .audio_features import AudioFeatureVector


def _tempo_tag(bpm: float) -> str | None:
    if bpm <= 0:
        return None
    if bpm < 65:
        return "매우 느림"
    if bpm < 90:
        return "느림"
    if bpm < 120:
        return "미디엄 템포"
    if bpm < 145:
        return "빠른 템포"
    return "매우 빠름"


def _energy_tag(rms: float) -> str | None:
    if rms <= 0:
        return None
    if rms < 0.08:
        return "잔잔"
    if rms < 0.2:
        return "다이내믹"
    return "에너지 폭발"


def _brightness_tag(centroid: float) -> str | None:
    if centroid <= 0:
        return None
    if centroid < 1500:
        return "어두운 톤"
    if centroid < 3500:
        return "미드 톤"
    return "밝은 톤"


def _roughness_tag(zcr: float) -> str | None:
    if zcr <= 0:
        return None
    if zcr < 0.06:
        return "부드러운 질감"
    if zcr < 0.15:
        return None  # 평범한 범위는 굳이 노출 안 함.
    return "거친 질감"


def _balance_tag(harmony: float, percussive: float) -> str | None:
    # 절댓값 기준으로 비교. mfcc/harmony 등이 음수일 수 있어서.
    h = abs(harmony)
    p = abs(percussive)
    if h < 1e-9 and p < 1e-9:
        return None
    if p == 0 or h / max(p, 1e-9) > 3.0:
        return "멜로디 위주"
    if h / max(p, 1e-9) < 0.33:
        return "비트 위주"
    return None  # 균형 잡힌 곡은 태그 없이 둔다 (시각적 노이즈 줄이기).


def derive_tags(features: AudioFeatureVector) -> list[str]:
    """특성 벡터에서 사람 가독 태그 리스트를 반환. 빈 리스트도 정상."""
    v = features.values

    def _val(key: str) -> float:
        try:
            return float(v.get(key, 0.0))
        except (TypeError, ValueError):
            return 0.0

    candidates = [
        _tempo_tag(_val("bpm")),
        _energy_tag(_val("rms_mean")),
        _brightness_tag(_val("spectral_centroid_mean")),
        _roughness_tag(_val("zero_crossing_rate_mean")),
        _balance_tag(_val("harmony_mean"), _val("percussive_mean")),
    ]
    # None 제거하고 중복도 정리 (이론상 중복은 없지만 안전).
    seen: set[str] = set()
    out: list[str] = []
    for c in candidates:
        if c and c not in seen:
            out.append(c)
            seen.add(c)
    return out
