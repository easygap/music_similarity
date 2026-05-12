"""Sklearn-based music similarity engine.

Loads the project dataset of pre-extracted audio features and provides a
`find_similar` function that returns a ranked list of catalog tracks for a
new query feature vector.

The pipeline mirrors the original capstone notebook:

    1. Drop the non-feature `length` column (used only as a label key here).
    2. Scale the remaining columns with sklearn's `StandardScaler`.
    3. Compute cosine similarity between the query and every catalog track.
    4. Sort descending and return the top-N hits.

The scaler is fit once on the catalog at startup and reused for any new
query, so a single song uploaded by a user gets exactly the same treatment
as the original training data.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from .audio_features import AudioFeatureVector, FEATURE_COLUMNS


# The dataset key column carries the song title and the artist together.
NAME_COLUMN = "musicname & artist"

# `length` exists in the CSV but the original capstone code drops it before
# similarity is computed. We keep that behaviour.
LABEL_COLUMN = "length"


@dataclass
class SimilarityHit:
    rank: int
    name: str
    artist: str
    similarity: float           # raw cosine similarity in [-1, 1]
    similarity_percent: float   # mapped to [0, 100] for display
    feature_distances: Dict[str, float]


class MusicSimilarityEngine:
    """Loads the dataset once and answers similarity queries.

    Construct with the path to `dataset.csv`. The engine pre-fits a scaler
    so every query is scaled in the same feature space as the catalog.
    """

    def __init__(self, dataset_path: str | Path):
        self.dataset_path = Path(dataset_path)
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset not found: {self.dataset_path}")

        df = pd.read_csv(self.dataset_path)
        if NAME_COLUMN not in df.columns:
            raise ValueError(
                f"Dataset is missing the '{NAME_COLUMN}' column."
            )

        df = df.set_index(NAME_COLUMN)
        # The catalog of feature columns we will use for similarity.
        self._feature_columns: List[str] = [
            c for c in df.columns if c != LABEL_COLUMN
        ]

        # Save the raw (unscaled) matrix for the reason engine — explanations
        # are friendlier when computed on real-world units rather than z-scores.
        self._catalog_raw = df[self._feature_columns].astype(float)
        self._catalog_index: List[str] = list(df.index)

        scaler = StandardScaler()
        self._catalog_scaled = scaler.fit_transform(self._catalog_raw.values)
        self._scaler = scaler

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def catalog_size(self) -> int:
        return len(self._catalog_index)

    @property
    def feature_columns(self) -> List[str]:
        return list(self._feature_columns)

    def query_vector(self, features: AudioFeatureVector) -> np.ndarray:
        """Convert a user-uploaded feature vector to the scaled space."""
        row = np.array(
            [features.values[c] for c in self._feature_columns],
            dtype=float,
        ).reshape(1, -1)
        return self._scaler.transform(row)

    def find_similar(
        self,
        features: AudioFeatureVector,
        *,
        top_n: int = 5,
    ) -> Tuple[List[SimilarityHit], np.ndarray]:
        """Return the top-N most similar catalog tracks.

        Returns the ranked hits and the scaled query vector (handy if the
        caller wants to feed it into the reason engine).
        """
        query_scaled = self.query_vector(features)

        sims = cosine_similarity(query_scaled, self._catalog_scaled).ravel()
        ranked = np.argsort(-sims)
        hits: List[SimilarityHit] = []

        # Pre-compute per-feature absolute differences against the catalog in
        # the SCALED space. These are what the reason engine actually uses.
        diffs_scaled = np.abs(self._catalog_scaled - query_scaled)

        for r_idx, catalog_idx in enumerate(ranked[:top_n], start=1):
            full_name = self._catalog_index[catalog_idx]
            title, _, artist = full_name.partition(" - ")
            sim = float(sims[catalog_idx])
            # Map cosine [-1, 1] -> percent [0, 100], but clamp the lower
            # bound: in practice all catalog tracks are positive and we
            # don't want misleading 50% floors for clearly different songs.
            percent = max(0.0, min(100.0, sim * 100.0))

            feature_distance_map: Dict[str, float] = {
                col: float(diffs_scaled[catalog_idx, j])
                for j, col in enumerate(self._feature_columns)
            }

            hits.append(
                SimilarityHit(
                    rank=r_idx,
                    name=title.strip() or full_name,
                    artist=artist.strip() or "Unknown",
                    similarity=sim,
                    similarity_percent=round(percent, 1),
                    feature_distances=feature_distance_map,
                )
            )

        return hits, query_scaled.ravel()

    def catalog_row_raw(self, name: str) -> Dict[str, float] | None:
        """Look up the raw (unscaled) features for a catalog entry by name."""
        if name not in self._catalog_index:
            return None
        return self._catalog_raw.loc[name].to_dict()
