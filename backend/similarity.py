"""sklearn 기반 음악 유사도 엔진.

사전 추출된 카탈로그 CSV를 한 번 로딩해두고, 새로 들어온 쿼리에 대해
``find_similar`` 로 순위가 매겨진 상위 N곡을 돌려준다.

파이프라인은 원작 캡스톤 노트북과 동일하다:

    1. ``length`` 컬럼은 라벨용으로만 쓰고 특성에선 제외한다.
    2. 남은 컬럼을 sklearn ``StandardScaler`` 로 표준화한다.
    3. 쿼리와 카탈로그 전곡에 대해 코사인 유사도를 구한다.
    4. 내림차순으로 정렬해서 top-N을 잘라 반환한다.

스케일러는 카탈로그 로딩 시점에 한 번만 fit한다. 사용자가 새로 업로드한
곡도 학습 시점과 똑같은 변환을 거치도록 동일한 scaler 인스턴스를 재사용.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import StandardScaler

from .audio_features import AudioFeatureVector

# 카탈로그 CSV의 인덱스 컬럼명. "곡명 - 아티스트" 형식의 키가 들어있다.
NAME_COLUMN = "musicname & artist"

# ``length`` 는 CSV에 존재하지만 원작 코드에서 유사도 계산 전에 drop한다.
# 그 동작을 그대로 유지한다.
LABEL_COLUMN = "length"


@dataclass
class SimilarityHit:
    """단일 매칭 결과. 프론트엔드에 그대로 직렬화될 필드 집합."""

    rank: int
    name: str
    artist: str
    similarity: float          # 코사인 유사도 raw 값. [-1, 1] 범위.
    similarity_percent: float  # UI 표시용으로 [0, 100] 으로 매핑한 값.
    feature_distances: dict[str, float]


class MusicSimilarityEngine:
    """카탈로그를 한 번 로딩하고 유사도 쿼리에 응답하는 엔진.

    ``dataset.csv`` 경로를 받아 생성한다. 생성자에서 scaler를 미리 fit하므로
    이후 들어오는 모든 쿼리는 카탈로그와 똑같은 특성 공간에서 정규화된다.
    """

    def __init__(self, dataset_path: str | Path):
        self.dataset_path = Path(dataset_path)
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"데이터셋을 찾을 수 없습니다: {self.dataset_path}")

        df = pd.read_csv(self.dataset_path)
        if NAME_COLUMN not in df.columns:
            raise ValueError(
                f"데이터셋에 필수 컬럼 '{NAME_COLUMN}' 이 없습니다."
            )

        df = df.set_index(NAME_COLUMN)
        # 실제 유사도 계산에 쓸 특성 컬럼만 골라낸다.
        feature_columns: list[str] = [c for c in df.columns if c != LABEL_COLUMN]

        # 이유(reason) 엔진은 z-score보다 실제 단위가 있는 값으로 비교할 때
        # 사용자가 이해하기 쉽다. 그래서 raw 매트릭스도 같이 들고 있는다.
        raw = df[feature_columns].astype(float)

        # NaN/inf가 섞인 행은 통째로 제거한다. StandardScaler를 오염시켜
        # 카탈로그 전체 유사도가 조용히 망가지는 걸 막기 위함.
        finite_mask = np.isfinite(raw.values).all(axis=1)
        if not finite_mask.all():
            raw = raw.loc[finite_mask]
        if raw.empty:
            raise ValueError("데이터셋에 유효한(finite) 값으로 구성된 행이 하나도 없습니다.")

        # 분산이 0인 컬럼도 제거. StandardScaler에서 0으로 나누기가 발생해
        # NaN이 생기고, cosine similarity가 전 카탈로그에서 깨진다.
        col_std = raw.std(axis=0, ddof=0)
        keep_cols = [c for c in feature_columns if col_std.get(c, 0.0) > 1e-12]
        if not keep_cols:
            raise ValueError("데이터셋에 사용 가능한(non-constant) 특성 컬럼이 없습니다.")

        self._feature_columns: list[str] = keep_cols
        self._dropped_columns: list[str] = [c for c in feature_columns if c not in keep_cols]
        self._catalog_raw = raw[self._feature_columns]
        self._catalog_index: list[str] = list(raw.index)

        scaler = StandardScaler()
        scaled = scaler.fit_transform(self._catalog_raw.values)
        if not np.isfinite(scaled).all():
            # 위에서 거른 뒤에도 NaN이 떨어졌다면 카탈로그가 의심스러운 상태.
            # 조용히 통과시키지 않고 startup에서 막는다.
            raise ValueError(
                "StandardScaler 결과에 non-finite 값이 포함되어 있습니다. "
                "중복 행/상수 컬럼이 없는지 확인하세요."
            )
        self._catalog_scaled = scaled
        self._scaler = scaler

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def catalog_size(self) -> int:
        return len(self._catalog_index)

    @property
    def feature_columns(self) -> list[str]:
        return list(self._feature_columns)

    def query_vector(self, features: AudioFeatureVector) -> np.ndarray:
        """업로드된 특성 벡터를 카탈로그와 같은 표준화 공간으로 변환한다.

        필수 컬럼이 빠져 있거나 non-finite 값이 들어오면 ValueError를 던진다.
        """
        try:
            raw_values = [float(features.values[c]) for c in self._feature_columns]
        except KeyError as e:
            raise ValueError(f"쿼리에 필수 특성이 빠져 있습니다: {e}") from e
        row = np.array(raw_values, dtype=float).reshape(1, -1)
        if not np.isfinite(row).all():
            raise ValueError("쿼리 특성 벡터에 non-finite 값이 포함되어 있습니다.")
        scaled = self._scaler.transform(row)
        if not np.isfinite(scaled).all():
            raise ValueError("쿼리 변환 결과가 non-finite 입니다.")
        return scaled

    def find_similar(
        self,
        features: AudioFeatureVector,
        *,
        top_n: int = 5,
    ) -> tuple[list[SimilarityHit], np.ndarray]:
        """상위 N개 유사 곡을 반환한다.

        반환값은 ``(hits, scaled_query)`` 튜플이다. scaled_query는 호출 측에서
        reason 엔진에 그대로 넘기고 싶을 때 쓰라고 같이 돌려준다.
        """
        query_scaled = self.query_vector(features)

        sims = cosine_similarity(query_scaled, self._catalog_scaled).ravel()
        ranked = np.argsort(-sims)
        hits: list[SimilarityHit] = []

        # 카탈로그와 쿼리 사이의 특성별 절대 거리를 표준화 공간에서 미리 구해둔다.
        # reason 엔진이 실제로 쓰는 값.
        diffs_scaled = np.abs(self._catalog_scaled - query_scaled)

        for r_idx, catalog_idx in enumerate(ranked[:top_n], start=1):
            full_name = self._catalog_index[catalog_idx]
            title, _, artist = full_name.partition(" - ")
            sim = float(sims[catalog_idx])
            # cosine [-1, 1] -> percent [0, 100]. 음수는 0으로 클램프해서
            # "0% 매칭" 으로 표시한다. 사실상 카탈로그 곡은 거의 양수.
            percent = max(0.0, min(100.0, sim * 100.0))

            feature_distance_map: dict[str, float] = {
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

    def catalog_row_raw(self, name: str) -> dict[str, float] | None:
        """카탈로그 항목의 원본(미정규화) 특성값을 조회한다."""
        if name not in self._catalog_index:
            return None
        return self._catalog_raw.loc[name].to_dict()
