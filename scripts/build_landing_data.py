"""메인 화면의 '소리 지도'와 '닮은 곡 예시'에 쓰는 정적 데이터를 만든다.

브라우저는 sklearn 을 못 돌리니, 카탈로그 전곡의 특성 벡터를 서버와 같은
StandardScaler 공간에서 PCA 로 3차원까지 투영한 좌표와, 실제 엔진이 뽑은
비교 예시 3쌍을 미리 계산해 ``frontend/js/landing-data.js`` 로 떨궈둔다.

카탈로그(``data/dataset.csv``)가 바뀌면 다시 실행한다::

    python scripts/build_landing_data.py

결과 파일은 전역 ``window.SoundMatchLanding`` 하나만 정의하는 순수 데이터라
CSP(script-src 'self') 아래에서도 그대로 로드된다.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.audio_features import AudioFeatureVector, summary_metrics  # noqa: E402
from backend.main import _spotify_search_url, _youtube_search_url  # noqa: E402
from backend.reason_engine import explain_match, report_to_dict  # noqa: E402
from backend.similarity import MusicSimilarityEngine  # noqa: E402
from backend.tagging import derive_tags  # noqa: E402

DATASET = ROOT / "data" / "dataset.csv"
OUTPUT = ROOT / "frontend" / "js" / "landing-data.js"

# 지도 좌표는 -1000..1000 정수로 저장한다. 소수점 6자리 float 보다 파일이 절반 이하다.
COORD_SCALE = 1000


def _split(full: str) -> tuple[str, str]:
    title, _, artist = full.partition(" - ")
    return title.strip() or full, artist.strip() or "Unknown"


def _project(scaled: np.ndarray) -> tuple[np.ndarray, list[float]]:
    """표준화된 특성 행렬을 PCA 3축으로 투영하고 각 축을 [-1, 1] 로 맞춘다."""
    from sklearn.decomposition import PCA

    pca = PCA(n_components=3, random_state=0)
    coords = pca.fit_transform(scaled)
    # 극단값 몇 곡 때문에 나머지가 가운데로 뭉치지 않도록 2.5σ 에서 자른 뒤 정규화한다.
    out = np.empty_like(coords)
    for axis in range(coords.shape[1]):
        col = coords[:, axis]
        limit = 2.5 * float(col.std()) or 1.0
        clipped = np.clip(col, -limit, limit)
        out[:, axis] = clipped / limit
    explained = [round(float(v), 4) for v in pca.explained_variance_ratio_]
    return out, explained


def _pick_showcase(eng: MusicSimilarityEngine, names: list[str], top_n: int = 3) -> list[dict]:
    """서로 성격이 다른 시드 3곡을 고른다.

    1위 유사도가 높은 순으로 훑으면서 템포 태그가 겹치지 않고, 아티스트도 겹치지 않는
    곡만 남긴다. 결과가 '잘 맞는' 예시로만 채워지되 전부 같은 느낌은 아니게.
    """
    from sklearn.metrics.pairwise import cosine_similarity

    sims = cosine_similarity(eng._catalog_scaled)
    np.fill_diagonal(sims, -1.0)
    # 카탈로그엔 제목만 다른 동일 음원이 몇 곡 섞여 있다(유사도 100%). 그런 쌍은
    # "닮았다"는 예시가 아니라 "같다"는 예시라 보는 사람에게 가짜처럼 느껴진다. 제외.
    DUPLICATE = 0.995
    masked = np.where(sims > DUPLICATE, -1.0, sims)
    best = masked.max(axis=1)
    order = np.argsort(-best)

    tempo_words = ("매우 느림", "느림", "미디엄 템포", "빠른 템포", "매우 빠름")
    used_tempo: set[str] = set()
    used_artists: set[str] = set()
    picks: list[int] = []
    for idx in order:
        if not (0.80 <= best[idx] <= 0.99):
            continue
        full = names[idx]
        _, artist = _split(full)
        raw = eng.catalog_row_raw(full) or {}
        tags = derive_tags(AudioFeatureVector(name=full, values=raw))
        tempo = next((t for t in tags if t in tempo_words), "")
        if not tempo or tempo in used_tempo or artist.lower() in used_artists:
            continue
        top_idx = np.argsort(-sims[idx])[:top_n]
        top_vals = sims[idx][top_idx]
        # 상위 3곡 안에 동일 음원이 끼거나, 3위가 너무 멀면 예시로 쓰기 애매하다.
        if top_vals.max() > DUPLICATE or top_vals.min() < 0.6:
            continue
        # 앞서 고른 시드가 이번 시드의 결과에 또 나오면 예시 세 개가 같은 동네를 맴돈다.
        if any(int(j) in picks for j in top_idx):
            continue
        # 1위가 같은 아티스트의 다른 버전이면 예시로는 심심하다. 상위 3곡 중 최소 두 곡은
        # 다른 아티스트여야 한다.
        others = sum(1 for j in top_idx if _split(names[j])[1].lower() != artist.lower())
        if others < 2:
            continue
        used_tempo.add(tempo)
        used_artists.add(artist.lower())
        picks.append(int(idx))
        if len(picks) == 3:
            break
    return [_showcase_entry(eng, names, i, top_n) for i in picks]


def _showcase_entry(eng: MusicSimilarityEngine, names: list[str], idx: int, top_n: int) -> dict:
    full = names[idx]
    raw = eng.catalog_row_raw(full) or {}
    features = AudioFeatureVector(name=full, values=raw)
    hits, _ = eng.find_similar(features, top_n=top_n + 1)
    filtered = [h for h in hits if f"{h.name} - {h.artist}" != full][:top_n]
    title, artist = _split(full)
    entry = {
        "index": idx,
        "title": title,
        "artist": artist,
        "summary": summary_metrics(features),
        "tags": derive_tags(features),
        "hits": [],
    }
    for rank, hit in enumerate(filtered, start=1):
        hit_full = f"{hit.name} - {hit.artist}"
        cat_raw = eng.catalog_row_raw(hit_full) or {}
        report = explain_match(
            query_raw=features.values,
            catalog_raw=cat_raw,
            distances_scaled=hit.feature_distances,
        )
        safe = dict(cat_raw)
        safe.setdefault("length", 0.0)
        entry["hits"].append({
            "index": names.index(hit_full),
            "rank": rank,
            "title": hit.name,
            "artist": hit.artist,
            "similarity_percent": hit.similarity_percent,
            "match_summary": summary_metrics(AudioFeatureVector(name=hit_full, values=safe)),
            "reason": report_to_dict(report),
            "youtube_search_url": _youtube_search_url(hit.name, hit.artist),
            "spotify_search_url": _spotify_search_url(hit.name, hit.artist),
        })
    return entry


def build() -> dict:
    eng = MusicSimilarityEngine(DATASET)
    names = list(eng._catalog_index)
    coords, explained = _project(eng._catalog_scaled)
    points = [[int(round(v * COORD_SCALE)) for v in row] for row in coords]
    return {
        "generatedAt": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "catalogSize": eng.catalog_size,
        "featureCount": len(eng.feature_columns),
        "explainedVariance": explained,
        "names": names,
        "points": points,
        "showcase": _pick_showcase(eng, names),
    }


def main() -> None:
    data = build()
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    OUTPUT.write_text(
        "// scripts/build_landing_data.py 가 만든 파일. 손으로 고치지 말 것.\n"
        "// 카탈로그 전곡의 PCA 좌표(소리 지도)와 실제 엔진이 뽑은 비교 예시.\n"
        f"window.SoundMatchLanding = {body};\n",
        encoding="utf-8",
    )
    size_kb = OUTPUT.stat().st_size / 1024
    print(f"wrote {OUTPUT.relative_to(ROOT)} ({size_kb:.1f} KB)")
    print(f"explained variance: {data['explainedVariance']}")
    for entry in data["showcase"]:
        top = entry["hits"][0]
        print(
            f"- {entry['title']} - {entry['artist']} [{', '.join(entry['tags'])}]"
            f" -> {top['title']} - {top['artist']} {top['similarity_percent']}%"
        )


if __name__ == "__main__":
    main()
