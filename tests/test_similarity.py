"""sklearn 기반 유사도 엔진 테스트."""
from __future__ import annotations

import csv
import math

import pytest

from backend.audio_features import FEATURE_COLUMNS, AudioFeatureVector
from backend.similarity import MusicSimilarityEngine


def _vec(values_by_index: dict[int, float]) -> AudioFeatureVector:
    """FEATURE_COLUMNS 인덱스를 키로 받아 특성 벡터를 만든다."""
    base = {c: 0.5 for c in FEATURE_COLUMNS}
    for i, v in values_by_index.items():
        base[FEATURE_COLUMNS[i]] = v
    return AudioFeatureVector(name="query", values=base)


def test_loads_synthetic_dataset(synthetic_dataset):
    engine = MusicSimilarityEngine(synthetic_dataset)
    assert engine.catalog_size == 3
    # length 는 원본 캡스톤 파이프라인에 맞춰 특성에서 제외돼야 한다.
    assert "length" not in engine.feature_columns


def test_find_similar_returns_ranked_hits(synthetic_dataset):
    engine = MusicSimilarityEngine(synthetic_dataset)
    # 첫 번째 합성곡(Alpha) 과 유사한 쿼리.
    query = _vec({})
    hits, _ = engine.find_similar(query, top_n=3)
    assert len(hits) == 3
    # 결과는 유사도 내림차순으로 정렬되어 있어야 한다.
    sims = [h.similarity for h in hits]
    assert sims == sorted(sims, reverse=True)
    # 표시용 퍼센트가 정상 범위에 있는지.
    for h in hits:
        assert 0.0 <= h.similarity_percent <= 100.0


def test_find_similar_top_n_bounds(synthetic_dataset):
    engine = MusicSimilarityEngine(synthetic_dataset)
    hits, _ = engine.find_similar(_vec({}), top_n=1)
    assert len(hits) == 1


def test_rejects_nonfinite_query(synthetic_dataset):
    engine = MusicSimilarityEngine(synthetic_dataset)
    # FEATURE_COLUMNS[0] 은 ``length`` 로 엔진이 라벨로만 쓰니까 제외된다.
    # 실제로 사용되는 컬럼인 bpm(index 3) 에 NaN 을 넣어야 검증이 발동.
    bad = _vec({3: float("nan")})
    with pytest.raises(ValueError):
        engine.find_similar(bad)


def test_rejects_missing_feature(synthetic_dataset):
    engine = MusicSimilarityEngine(synthetic_dataset)
    vec = AudioFeatureVector(name="q", values={"bpm": 120.0})  # 거의 모든 컬럼 누락
    with pytest.raises(ValueError):
        engine.find_similar(vec)


def test_drops_zero_variance_columns(tmp_path, feature_columns):
    """모든 행에서 같은 값을 가진 컬럼은 자동으로 제거되어야 한다."""
    csv_path = tmp_path / "ds.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["musicname & artist", *feature_columns])
        for i, name in enumerate(["A - x", "B - x", "C - x"]):
            row = {c: 0.5 + 0.1 * i + 0.001 * j for j, c in enumerate(feature_columns)}
            # bpm 만 모든 행에서 동일하게.
            row["bpm"] = 120.0
            writer.writerow([name, *[row[c] for c in feature_columns]])
    engine = MusicSimilarityEngine(csv_path)
    assert "bpm" not in engine.feature_columns
    # 그 상태에서도 정상적으로 유사도 계산이 돌아가야 한다.
    base = {c: 0.5 for c in feature_columns}
    base["bpm"] = 120.0
    hits, _ = engine.find_similar(AudioFeatureVector(name="q", values=base), top_n=2)
    assert hits
    assert all(math.isfinite(h.similarity) for h in hits)


def test_rejects_empty_dataset(tmp_path, feature_columns):
    csv_path = tmp_path / "empty.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["musicname & artist", *feature_columns])
    with pytest.raises(ValueError):
        MusicSimilarityEngine(csv_path)


def test_real_catalog_loads(real_dataset_path):
    """실제 카탈로그 CSV 가 깨끗하게 로드되는지 확인."""
    if not real_dataset_path.exists():
        pytest.skip("실제 데이터셋이 CI 환경에 없음")
    engine = MusicSimilarityEngine(real_dataset_path)
    assert engine.catalog_size > 0
    # 자기 자신을 쿼리로 넣으면 1위가 자기 자신이어야 한다 (self-similarity sanity check).
    import pandas as pd

    df = pd.read_csv(real_dataset_path, index_col="musicname & artist")
    first_name = df.index[0]
    raw_row = df.loc[first_name].to_dict()
    vec = AudioFeatureVector(name=first_name, values=raw_row)
    hits, _ = engine.find_similar(vec, top_n=3)
    assert hits[0].similarity > 0.95
