"""librosa로 오디오 특성을 추출하는 모듈.

업로드된 음원에서 캡스톤 데이터셋과 똑같이 58개 특성을 뽑아서,
사전 계산된 카탈로그와 그대로 비교할 수 있도록 한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import librosa
import numpy as np

# 카탈로그 CSV의 컬럼 순서와 1:1로 맞춘다. 순서를 바꾸면 기존 dataset.csv와 호환이 깨지니 주의.
FEATURE_COLUMNS: list[str] = [
    "length",
    "rms_mean",
    "rms_var",
    "bpm",
    "zero_crossing_rate_mean",
    "zero_crossing_rate_var",
    "harmony_mean",
    "harmony_var",
    "percussive_mean",
    "percussive_var",
    "spectral_centroid_mean",
    "spectral_centroid_var",
    "spectral_bandwidth_mean",
    "spectral_bandwidth_var",
    "spectral_rolloff_mean",
    "spectral_rolloff_var",
    "chroma_frequencies_mean",
    "chroma_frequencies_var",
]
for _i in range(1, 21):
    FEATURE_COLUMNS.append(f"mfcc{_i}_mean")
    FEATURE_COLUMNS.append(f"mfcc{_i}_var")


@dataclass
class AudioFeatureVector:
    """추출된 특성 벡터. name은 파일 stem, values는 컬럼명→값 매핑."""

    name: str
    values: dict[str, float] = field(default_factory=dict)

    def to_ordered_list(self) -> list[float]:
        """FEATURE_COLUMNS 순서로 평탄화한 리스트를 반환한다."""
        return [self.values[c] for c in FEATURE_COLUMNS]


def extract_features(audio_path: str | Path, *, max_duration: float = 30.0) -> AudioFeatureVector:
    """오디오 파일에서 librosa 특성을 뽑아낸다.

    레이턴시를 예측 가능하게 유지하기 위해 ``max_duration`` 초까지만 자른다.
    반환값의 키는 카탈로그 CSV 컬럼명과 동일하므로 즉시 비교에 사용할 수 있다.
    """
    audio_path = Path(audio_path)
    y, sr = librosa.load(str(audio_path), duration=max_duration)

    if y.size == 0:
        raise ValueError("오디오 파일이 비어있거나 디코딩에 실패했습니다.")

    rms = librosa.feature.rms(y=y)
    try:
        bpm_raw, _ = librosa.beat.beat_track(y=y, sr=sr)
        # librosa 0.10부터는 numpy array를 반환하고, 이전 버전은 스칼라를 준다.
        bpm_val = float(np.atleast_1d(bpm_raw)[0])
        if not np.isfinite(bpm_val) or bpm_val <= 0:
            bpm_val = 0.0
    except (ValueError, RuntimeError):
        # 박자 추정에 실패하면 BPM은 0으로 두고 다른 특성으로 비교한다.
        bpm_val = 0.0
    bpm = bpm_val
    zero_crossings = librosa.zero_crossings(y, pad=False).astype(np.float32)
    harm, perc = librosa.effects.hpss(y)
    spec = librosa.feature.spectral_centroid(y=y, sr=sr)
    band = librosa.feature.spectral_bandwidth(y=y, sr=sr)
    roll = librosa.feature.spectral_rolloff(y=y, sr=sr)
    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)

    values: dict[str, float] = {
        "length": float(len(y)),
        "rms_mean": float(np.mean(rms)),
        "rms_var": float(np.var(rms)),
        "bpm": bpm,
        "zero_crossing_rate_mean": float(np.mean(zero_crossings)),
        "zero_crossing_rate_var": float(np.var(zero_crossings)),
        "harmony_mean": float(np.mean(harm)),
        "harmony_var": float(np.var(harm)),
        "percussive_mean": float(np.mean(perc)),
        "percussive_var": float(np.var(perc)),
        "spectral_centroid_mean": float(np.mean(spec)),
        "spectral_centroid_var": float(np.var(spec)),
        "spectral_bandwidth_mean": float(np.mean(band)),
        "spectral_bandwidth_var": float(np.var(band)),
        "spectral_rolloff_mean": float(np.mean(roll)),
        "spectral_rolloff_var": float(np.var(roll)),
        "chroma_frequencies_mean": float(np.mean(chroma)),
        "chroma_frequencies_var": float(np.var(chroma)),
    }

    for i, m in enumerate(mfccs, start=1):
        values[f"mfcc{i}_mean"] = float(np.mean(m))
        values[f"mfcc{i}_var"] = float(np.var(m))

    return AudioFeatureVector(name=audio_path.stem, values=values)


def summary_metrics(features: AudioFeatureVector) -> dict[str, float]:
    """프론트엔드 레이더 차트용으로 보기 좋게 정리한 요약 지표.

    카탈로그 행에 키가 빠져 있어도 죽지 않도록 모든 필드를 0.0으로 폴백한다.
    덕분에 쿼리 결과와 사전 추출된 카탈로그 행 둘 다에서 재사용 가능하다.
    """
    v = features.values

    def _get(key: str) -> float:
        try:
            val = float(v.get(key, 0.0))
        except (TypeError, ValueError):
            return 0.0
        return val if np.isfinite(val) else 0.0

    perc = abs(_get("percussive_mean"))
    return {
        "tempo_bpm": round(_get("bpm"), 1),
        "energy_rms": round(_get("rms_mean"), 4),
        "brightness": round(_get("spectral_centroid_mean"), 1),
        "noisiness": round(_get("zero_crossing_rate_mean"), 4),
        # 0으로 나누지 않도록 1e-9 더해준다. 그래도 큰 비율은 frontend에서 클램프.
        "harmony_ratio": round(abs(_get("harmony_mean")) / (perc + 1e-9), 2),
        "chroma": round(_get("chroma_frequencies_mean"), 4),
    }
