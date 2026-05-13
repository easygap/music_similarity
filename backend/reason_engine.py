"""Human-readable similarity-reason generator.

Given a query song's scaled feature vector, the catalog row it matched
against (raw + scaled), and the per-feature scaled distance map, this
module returns short Korean sentences that explain *why* the two songs
came out similar.

The idea: features that contributed most to the cosine similarity — i.e.
features where the two songs are closest in the scaled space — get
translated into musical concepts the user can actually picture.
"""
from __future__ import annotations

from dataclasses import dataclass

# Feature -> (human label, unit, friendly explanation template)
# The template receives `q` (query value) and `c` (catalog value).
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

# Group features into musical concepts so we summarise rather than dump 58 lines.
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
    label: str
    match_score: float          # 0..1, 1 = very close on this concept
    summary: str                # short sentence the UI shows
    detail: list[str]           # per-feature bullet points


@dataclass
class ReasonReport:
    summary: str                # 1–2 sentence top-level explanation
    groups: list[ReasonGroup]   # ranked best-matching musical concepts


def _concept_score(distances: dict[str, float], cols: list[str]) -> float:
    """Average scaled distance over the concept's columns -> closeness score.

    Distances are in z-score units; a distance of 0 means the two songs are
    indistinguishable on that feature, ~1 means one standard deviation apart.
    We map distance d -> closeness exp(-d) so 0 stays at 1.0 and large
    distances asymptote to 0.
    """
    import math

    vals = [distances[c] for c in cols if c in distances]
    if not vals:
        return 0.0
    avg = sum(vals) / len(vals)
    return math.exp(-avg)


def _has_final_jongseong(text: str) -> bool:
    """Return True if the last Korean syllable of ``text`` has a final consonant.

    Used to pick the right particle ('이' vs '가', '은' vs '는', etc.). For
    non-Korean trailing characters (e.g. ')'), we fall back to assuming no
    final consonant, which produces grammatically safer output.
    """
    for ch in reversed(text):
        code = ord(ch)
        if 0xAC00 <= code <= 0xD7A3:
            return (code - 0xAC00) % 28 != 0
        if ch.isalnum():
            # Latin letters/digits inside a Korean sentence: treat the digit
            # case carefully — '0','1','3','6','7','8' are read with 받침.
            if ch.isdigit():
                return ch in {"0", "1", "3", "6", "7", "8"}
            return False
    return False


def _i_ga(text: str) -> str:
    """Return '이' or '가' for the subject particle, depending on the trailing letter."""
    return "이" if _has_final_jongseong(text) else "가"


def _phrase_compare(query: float, catalog: float, label: str, unit: str) -> str:
    """Return a short Korean sentence comparing two raw feature values."""
    if abs(query - catalog) < 1e-9:
        return f"{label}{_i_ga(label)} 거의 동일합니다 ({query:.2f}{unit})."
    # Use absolute values for ratio so negative-valued features (e.g. mfcc
    # means, harmony_mean) don't produce misleading "ratio" interpretations.
    abs_q, abs_c = abs(query), abs(catalog)
    higher, lower = (abs_q, abs_c) if abs_q > abs_c else (abs_c, abs_q)
    if lower < 1e-9:
        # Both effectively zero on the magnitude axis — fall through to "비슷한 값".
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
    """Build a human-readable explanation for a single match.

    `distances_scaled` is the per-feature absolute distance in the
    StandardScaler space — small values mean the two songs are close on
    that feature.
    """
    group_scores: list[ReasonGroup] = []
    for group_label, cols in FEATURE_GROUPS.items():
        score = _concept_score(distances_scaled, cols)

        # Pick the most-similar features inside this group for the detail list.
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
            # MFCCs are abstract; mention the closeness numerically.
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
