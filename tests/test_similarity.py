"""Tests for the sklearn-based similarity engine."""
from __future__ import annotations

import csv
import math

import pytest

from backend.audio_features import FEATURE_COLUMNS, AudioFeatureVector
from backend.similarity import MusicSimilarityEngine


def _vec(values_by_index: dict[int, float]) -> AudioFeatureVector:
    base = {c: 0.5 for c in FEATURE_COLUMNS}
    for i, v in values_by_index.items():
        base[FEATURE_COLUMNS[i]] = v
    return AudioFeatureVector(name="query", values=base)


def test_loads_synthetic_dataset(synthetic_dataset):
    engine = MusicSimilarityEngine(synthetic_dataset)
    assert engine.catalog_size == 3
    # `length` is excluded from features per the original capstone pipeline.
    assert "length" not in engine.feature_columns


def test_find_similar_returns_ranked_hits(synthetic_dataset):
    engine = MusicSimilarityEngine(synthetic_dataset)
    # Query that's essentially "Alpha" (i=0 in synthetic_dataset).
    query = _vec({})
    hits, q = engine.find_similar(query, top_n=3)
    assert len(hits) == 3
    # Hits must be ordered descending by similarity.
    sims = [h.similarity for h in hits]
    assert sims == sorted(sims, reverse=True)
    # Percent display is bounded.
    for h in hits:
        assert 0.0 <= h.similarity_percent <= 100.0


def test_find_similar_top_n_bounds(synthetic_dataset):
    engine = MusicSimilarityEngine(synthetic_dataset)
    hits, _ = engine.find_similar(_vec({}), top_n=1)
    assert len(hits) == 1


def test_rejects_nonfinite_query(synthetic_dataset):
    engine = MusicSimilarityEngine(synthetic_dataset)
    # FEATURE_COLUMNS[0] is `length`, which the engine drops as a label.
    # Use bpm (index 3) which IS in the engine's feature set.
    bad = _vec({3: float("nan")})
    with pytest.raises(ValueError):
        engine.find_similar(bad)


def test_rejects_missing_feature(synthetic_dataset):
    engine = MusicSimilarityEngine(synthetic_dataset)
    vec = AudioFeatureVector(name="q", values={"bpm": 120.0})  # missing most columns
    with pytest.raises(ValueError):
        engine.find_similar(vec)


def test_drops_zero_variance_columns(tmp_path, feature_columns):
    """A column with identical values across all rows should be excluded."""
    csv_path = tmp_path / "ds.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["musicname & artist", *feature_columns])
        for i, name in enumerate(["A - x", "B - x", "C - x"]):
            row = {c: 0.5 + 0.1 * i + 0.001 * j for j, c in enumerate(feature_columns)}
            # Make `bpm` constant across all rows.
            row["bpm"] = 120.0
            writer.writerow([name, *[row[c] for c in feature_columns]])
    engine = MusicSimilarityEngine(csv_path)
    assert "bpm" not in engine.feature_columns
    # And similarity still works.
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
    """The shipped dataset must load cleanly."""
    if not real_dataset_path.exists():
        pytest.skip("Real dataset not present in CI environment")
    engine = MusicSimilarityEngine(real_dataset_path)
    assert engine.catalog_size > 0
    # Self-similarity sanity: a query made from the FIRST catalog row should
    # rank that same row as the top match.
    import pandas as pd

    df = pd.read_csv(real_dataset_path, index_col="musicname & artist")
    first_name = df.index[0]
    raw_row = df.loc[first_name].to_dict()
    vec = AudioFeatureVector(name=first_name, values=raw_row)
    hits, _ = engine.find_similar(vec, top_n=3)
    assert hits[0].similarity > 0.95
