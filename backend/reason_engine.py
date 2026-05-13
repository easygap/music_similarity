"""사용자에게 보여줄 "닮은 이유" 문장을 만들어주는 모듈.

입력:
    - 쿼리 곡의 raw 특성값
    - 매칭된 카탈로그 행의 raw 특성값
    - 두 곡 사이의 특성별 표준화 공간(z-score) 거리 맵

코사인 유사도에 기여도가 높았던 특성 — 즉 두 곡이 표준화 공간에서 가까웠던
특성을 — 음악적인 개념(템포, 음색, 화성 등)으로 묶어 한국어 문장으로 풀어
돌려준다.
"""
from __future__ import annotations

from dataclasses import dataclass

# 특성 컬럼 -> (사용자에게 보여줄 라벨, 단위) 매핑.
# UI 문구를 한 번에 손볼 수 있도록 한 곳에 모아둔다.
FEATURE_LABELS: dict[str, tuple[str, str]] = {
    "bpm": ("템포", "BPM"),
    "rms_mean": ("평균 음량(에너지)", ""),
    "rms_var": ("음량 변화", ""),
    "spectral_centroid_mean": ("음색의 밝기", "Hz"),
    "spectral_centroid_var": ("음색의 밝기 변화", ""),
    "spectral_bandwidth_mean": ("주파수 대역폭", "Hz"),
    "spectral_bandwidth_var": ("주파수 대역폭 변화", ""),
    "spectral_rolloff_mean": ("고주파 분포", "Hz"),
    "spectral_rolloff_var": ("고주파 분포 변화", ""),
    "zero_crossing_rate_mean": ("거친 정도(노이즈성)", ""),
    "zero_crossing_rate_var": ("거친 정도 변화", ""),
    "harmony_mean": ("화성 성분", ""),
    "harmony_var": ("화성 성분 변화", ""),
    "percussive_mean": ("타악기 성분", ""),
    "percussive_var": ("타악기 성분 변화", ""),
    "chroma_frequencies_mean": ("음정 색채(크로마)", ""),
    "chroma_frequencies_var": ("음정 색채 변화", ""),
}

# 58개 특성을 그대로 나열하면 사용자가 못 읽으니 음악적 개념으로 묶어준다.
FEATURE_GROUPS: dict[str, list[str]] = {
    "템포 & 리듬": ["bpm", "rms_mean", "rms_var"],
    "음색 (밝기)": [
        "spectral_centroid_mean",
        "spectral_centroid_var",
        "spectral_rolloff_mean",
        "spectral_rolloff_var",
        "spectral_bandwidth_mean",
        "spectral_bandwidth_var",
    ],
    "거친 질감 & 노이즈": [
        "zero_crossing_rate_mean",
        "zero_crossing_rate_var",
    ],
    "화성 vs 타악기 균형": [
        "harmony_mean",
        "harmony_var",
        "percussive_mean",
        "percussive_var",
    ],
    "음정 분포 (크로마)": [
        "chroma_frequencies_mean",
        "chroma_frequencies_var",
    ],
    "음색 디테일 (MFCC)": [f"mfcc{i}_{stat}" for i in range(1, 21) for stat in ("mean", "var")],
}


@dataclass
class ReasonGroup:
    """음악적 개념 단위(예: 템포&리듬)로 묶은 부분 보고."""

    label: str
    match_score: float  # 0..1, 1에 가까울수록 해당 개념에서 가까움.
    summary: str        # UI 카드에 노출되는 한 줄 요약.
    detail: list[str]   # 그룹 내 가장 비슷했던 특성에 대한 자세한 비교 문구.


@dataclass
class ReasonReport:
    """매칭 한 건에 대한 전체 설명. 위쪽 요약 + 그룹별 디테일."""

    summary: str               # 1~2문장짜리 최상위 요약.
    groups: list[ReasonGroup]  # match_score 내림차순으로 정렬된 그룹들.


def _concept_score(distances: dict[str, float], cols: list[str]) -> float:
    """그룹 컬럼들의 평균 거리(z-score)를 closeness 점수로 변환한다.

    거리 0은 같은 곡, 거리 1은 표준편차 1만큼 떨어진 정도다.
    ``exp(-d)`` 로 매핑해서 거리 0 -> 1.0, 거리가 커지면 0에 수렴하도록 한다.
    """
    import math

    vals = [distances[c] for c in cols if c in distances]
    if not vals:
        return 0.0
    avg = sum(vals) / len(vals)
    return math.exp(-avg)


def _has_final_jongseong(text: str) -> bool:
    """문자열의 마지막 한글 음절에 받침이 있는지 판별한다.

    조사("이/가", "은/는" 등) 선택에 사용. 한글이 아닌 문자(괄호 등)는
    더 거슬러 올라가서 한글 음절을 찾는다. 끝까지 한글이 없으면 받침 없음으로
    가정한다 (문법 안전 측면에서 보수적).
    """
    for ch in reversed(text):
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            # 한글 음절: (코드 - 0xAC00) % 28 != 0 이면 받침 있음.
            return (code - 0xAC00) % 28 != 0
        if ch.isalnum():
            # 한글 사이에 라틴 알파벳/숫자가 끝에 붙는 경우 처리.
            # 숫자는 발음상 받침 유무가 다르다 (예: "0번"=영번, "1번"=일번).
            if ch.isdigit():
                return ch in {"0", "1", "3", "6", "7", "8"}
            return False
    return False


def _i_ga(text: str) -> str:
    """문자열 끝 발음에 맞춰 주격 조사 '이' 또는 '가' 를 반환."""
    return "이" if _has_final_jongseong(text) else "가"


def _phrase_compare(query: float, catalog: float, label: str, unit: str) -> str:
    """두 raw 특성값을 비교해 한 줄짜리 한국어 문장을 반환한다."""
    if abs(query - catalog) < 1e-9:
        return f"{label}{_i_ga(label)} 거의 동일합니다 ({query:.2f}{unit})."
    # mfcc 평균이나 harmony_mean 처럼 음수가 자연스러운 특성이 있으므로
    # 비율은 절댓값으로 계산한다. 안 그러면 부호 차이 때문에 문장이 이상해진다.
    abs_q, abs_c = abs(query), abs(catalog)
    higher, lower = (abs_q, abs_c) if abs_q > abs_c else (abs_c, abs_q)
    if lower < 1e-9:
        # 두 값 다 0에 가까우면 "비슷한 값" 으로 안전하게 묶는다.
        ratio = 1.0
    else:
        ratio = higher / lower
    if ratio < 1.2:
        closeness = "비슷한"
    elif ratio < 2.0:
        closeness = "유사한 범위의"
    else:
        closeness = "어느 정도 떨어진"
    return (
        f"{label}: 업로드한 곡 {query:.2f}{unit} · 매칭된 곡 {catalog:.2f}{unit} "
        f"({closeness} 값)"
    )


def explain_match(
    query_raw: dict[str, float],
    catalog_raw: dict[str, float],
    distances_scaled: dict[str, float],
    *,
    top_groups: int = 3,
    top_detail_per_group: int = 2,
) -> ReasonReport:
    """매칭 한 건에 대한 사람-가독 설명을 만든다.

    ``distances_scaled`` 는 StandardScaler 공간에서의 특성별 절대 거리.
    값이 작을수록 두 곡이 해당 특성에서 가깝다는 의미다.
    """
    group_scores: list[ReasonGroup] = []
    for group_label, cols in FEATURE_GROUPS.items():
        score = _concept_score(distances_scaled, cols)

        # 그룹 안에서도 가장 가까웠던 특성 몇 개만 디테일 줄에 노출한다.
        eligible = [(c, distances_scaled.get(c, float("inf"))) for c in cols]
        eligible.sort(key=lambda x: x[1])

        detail_lines: list[str] = []
        for col, _d in eligible[:top_detail_per_group]:
            if col in query_raw and col in catalog_raw and col in FEATURE_LABELS:
                label, unit = FEATURE_LABELS[col]
                detail_lines.append(
                    _phrase_compare(
                        query_raw[col], catalog_raw[col], label, unit
                    )
                )

        if not detail_lines and group_label == "음색 디테일 (MFCC)":
            # MFCC는 추상적이라 raw 값을 보여줘봐야 안 와닿는다.
            # 평균 거리만 숫자로 보여줘서 "가까웠다/멀었다" 만 전달.
            mfcc_dists = [distances_scaled.get(c, 0.0) for c in cols]
            avg = sum(mfcc_dists) / max(1, len(mfcc_dists))
            detail_lines.append(
                f"MFCC 20차원 평균 거리 {avg:.3f} (낮을수록 음색 디테일이 유사)"
            )

        summary_sentence = _group_summary(group_label, score)
        group_scores.append(
            ReasonGroup(
                label=group_label,
                match_score=round(score, 3),
                summary=summary_sentence,
                detail=detail_lines,
            )
        )

    group_scores.sort(key=lambda g: g.match_score, reverse=True)
    top = group_scores[:top_groups]

    if top:
        best = top[0]
        top_summary = (
            f"두 곡은 **{best.label}** 측면이 특히 닮았고, "
            f"전반적인 청각적 인상이 비슷합니다."
        )
    else:
        top_summary = "두 곡이 비슷한 청각적 인상을 가지고 있습니다."

    return ReasonReport(summary=top_summary, groups=top)


def _group_summary(label: str, score: float) -> str:
    """closeness 점수를 사람 말로 변환한다."""
    if score > 0.9:
        adv = "거의 같은"
    elif score > 0.75:
        adv = "매우 닮은"
    elif score > 0.55:
        adv = "닮은"
    elif score > 0.35:
        adv = "어느 정도 비슷한"
    else:
        adv = "다소 차이가 있는"

    return f"{label} 측면에서 {adv} 특성을 보입니다."


def report_to_dict(report: ReasonReport) -> dict:
    """ReasonReport 를 JSON 직렬화 가능한 dict 로 평탄화한다."""
    return {
        "summary": report.summary,
        "groups": [
            {
                "label": g.label,
                "match_score": g.match_score,
                "summary": g.summary,
                "detail": g.detail,
            }
            for g in report.groups
        ],
    }
