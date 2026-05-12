"""Audio feature extraction using librosa.

Extracts the same 58 features used in the capstone dataset so that newly
uploaded audio can be compared directly against the pre-computed catalog.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import librosa
import numpy as np


FEATURE_COLUMNS: List[str] = [
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
    values: Dict[str, float] = field(default_factory=dict)

    def to_ordered_list(self) -> List[float]:
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
        bpm, _ = librosa.beat.beat_track(y=y, sr=sr)
    except Exception:
        bpm = 0.0
    zero_crossings = librosa.zero_crossings(y, pad=False).astype(np.float32)
    harm, perc = librosa.effects.hpss(y)
    spec = librosa.feature.spectral_centroid(y=y, sr=sr)
    band = librosa.feature.spectral_bandwidth(y=y, sr=sr)
    roll = librosa.feature.spectral_rolloff(y=y, sr=sr)
    chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20)

    values: Dict[str, float] = {
        "length": float(len(y)),
        "rms_mean": float(np.mean(rms)),
        "rms_var": float(np.var(rms)),
        "bpm": float(bpm if np.isscalar(bpm) else np.atleast_1d(bpm)[0]),
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


def summary_metrics(features: AudioFeatureVector) -> Dict[str, float]:
    """A small human-friendly summary used by the frontend for the radar chart."""
    v = features.values
    return {
        "tempo_bpm": round(v["bpm"], 1),
        "energy_rms": round(v["rms_mean"], 4),
        "brightness": round(v["spectral_centroid_mean"], 1),
        "noisiness": round(v["zero_crossing_rate_mean"], 4),
        "harmony_ratio": round(
            abs(v["harmony_mean"]) / (abs(v["percussive_mean"]) + 1e-9), 2
        ),
        "chroma": round(v["chroma_frequencies_mean"], 4),
    }
