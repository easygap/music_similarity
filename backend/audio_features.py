"""Audio feature extraction using librosa.

Extracts the same 58 features used in the capstone dataset so that newly
uploaded audio can be compared directly against the pre-computed catalog.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import librosa
import numpy as np

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
    name: str
    values: dict[str, float] = field(default_factory=dict)

    def to_ordered_list(self) -> list[float]:
        return [self.values[c] for c in FEATURE_COLUMNS]


def extract_features(audio_path: str | Path, *, max_duration: float = 30.0) -> AudioFeatureVector:
    """Extract librosa features from an audio file.

    Trims to max_duration seconds for predictable latency. Returns a feature
    vector keyed by the same column names as the project dataset CSV.
    """
    audio_path = Path(audio_path)
    y, sr = librosa.load(str(audio_path), duration=max_duration)

    if y.size == 0:
        raise ValueError("Audio file is empty or could not be decoded.")

    rms = librosa.feature.rms(y=y)
    try:
        bpm_raw, _ = librosa.beat.beat_track(y=y, sr=sr)
        # librosa >=0.10 returns a numpy array, older versions a scalar.
        bpm_val = float(np.atleast_1d(bpm_raw)[0])
        if not np.isfinite(bpm_val) or bpm_val <= 0:
            bpm_val = 0.0
    except (ValueError, RuntimeError):
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
    """A small human-friendly summary used by the frontend for the radar chart.

    Resilient to missing keys (returns 0.0 for any field the catalog row
    happens to lack) so this can be reused for both fresh queries and
    pre-extracted catalog rows.
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
        "harmony_ratio": round(abs(_get("harmony_mean")) / (perc + 1e-9), 2),
        "chroma": round(_get("chroma_frequencies_mean"), 4),
    }
