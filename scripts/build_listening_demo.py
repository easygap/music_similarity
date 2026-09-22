"""직접 합성한 음악 샘플과 실제 측정값을 만든다. 새 런타임 의존성 없음.

python scripts/build_listening_demo.py
WAV를 다시 읽어 librosa로 분석하므로 화면의 파형·스펙트럼은 재생 파일과 같다.
샘플은 외부 음원을 사용하지 않으며 저장소의 MIT 라이선스로 배포한다.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.audio_features import extract_features, summary_metrics  # noqa: E402
from backend.similarity import MusicSimilarityEngine  # noqa: E402

DEST = ROOT / "frontend" / "assets" / "demo"
SR = 22050
DURATION = 60 / 112 * 16 + 0.4


def synthesize(kind: str) -> np.ndarray:
    """Cmaj7–Am7–Fmaj7–G 위의 짧은 멜로디. seed를 고정해 재생성 가능."""
    rng = np.random.default_rng(20260918)
    audio = np.zeros(round(DURATION * SR))
    bpm = 144 if kind == "rhythm" else 112
    beat = 60 / bpm
    chords = [(48, 52, 55, 59), (45, 48, 52, 55), (41, 45, 48, 52), (43, 47, 50, 55)]
    melody = [72, 76, 79, 76, 71, 72, 76, 74, 69, 72, 76, 72, 74, 71, 67, 71]

    def mix(signal: np.ndarray, start: float, gain: float) -> None:
        offset = round(start * SR)
        n = min(len(signal), len(audio) - offset)
        if n > 0:
            audio[offset:offset + n] += signal[:n] * gain

    def note(midi: int, seconds: float, bright: bool = False) -> np.ndarray:
        t = np.arange(round(seconds * SR)) / SR
        freq = 440 * 2 ** ((midi - 69) / 12)
        harmonics = [(1, 1), (2, .36), (3, .12), (4, .05)]
        if bright:
            harmonics += [(5, .18), (7, .10), (9, .06)]
        tone = sum(amp * np.sin(2 * np.pi * freq * multiple * t) * np.exp(-t * (1.8 + multiple * .42)) for multiple, amp in harmonics)
        return tone * np.minimum(t / .009, 1) * np.minimum((seconds - t) / .06, 1)

    for bar, chord in enumerate(chords):
        start = bar * beat * 4
        for j, midi in enumerate(chord):
            mix(note(midi + 12, beat * 3.9, kind == "tone"), start + j * .018, .065)
        for j in range(4):
            mix(note(melody[bar * 4 + j], beat * .95, kind == "tone"), start + beat * j, .16)
            mix(note(chord[0] - 12, beat * .8), start + beat * j, .20)
            t = np.arange(round(.18 * SR)) / SR
            kick = np.sin(2 * np.pi * (48 * t + 8 * (1 - np.exp(-t * 30)))) * np.exp(-t * 24)
            mix(kick, start + beat * j, .20)
        for j in range(8):
            t = np.arange(round(.07 * SR)) / SR
            noise = rng.uniform(-1, 1, len(t))
            hat = (noise - np.roll(noise, 1)) * np.exp(-t * 90)
            mix(hat, start + j * beat / 2, .035 if kind != "rhythm" else .12)
        if kind == "rhythm":
            for j in (1, 3):
                t = np.arange(round(.16 * SR)) / SR
                mix(rng.uniform(-1, 1, len(t)) * np.exp(-t * 32), start + j * beat, .23)
    audio *= np.minimum(np.arange(len(audio)) / (.02 * SR), 1)
    audio *= np.minimum(np.arange(len(audio))[::-1] / (.2 * SR), 1)
    return np.clip(audio * .85, -.95, .95).astype(np.float32)


def build() -> dict:
    DEST.mkdir(parents=True, exist_ok=True)
    engine = MusicSimilarityEngine(ROOT / "data" / "dataset.csv")
    tracks = []
    vectors = []
    for kind in ("original", "tone", "rhythm"):
        path = DEST / f"{kind}.wav"
        sf.write(path, synthesize(kind), SR, subtype="PCM_16")
        y, sr = sf.read(path)
        feature = extract_features(path)
        raw = [feature.values[col] for col in engine.feature_columns]
        vectors.append(engine._scaler.transform([raw])[0])
        spectrum = np.abs(librosa.stft(y, n_fft=2048)).mean(axis=1)
        frequencies = librosa.fft_frequencies(sr=sr, n_fft=2048)
        edges = np.geomspace(40, 10000, 49)
        bands = [float(spectrum[(frequencies >= a) & (frequencies < b)].mean()) if np.any((frequencies >= a) & (frequencies < b)) else 0 for a, b in zip(edges[:-1], edges[1:], strict=True)]
        # dBFS-like relative spectrum: shared reference across all samples, not per-track normalization.
        db = [round(float(20 * np.log10(max(v, 1e-5) / 1024)), 1) for v in bands]
        peaks = [round(float(np.max(np.abs(chunk))), 4) for chunk in np.array_split(y, 144)]
        mel = librosa.feature.melspectrogram(y=y, sr=sr, n_fft=2048, hop_length=256, n_mels=48, fmin=40, fmax=10000)
        # 시간 × mel 주파수. 모든 샘플에 같은 -65..15 dB 범위; 높이는 상대 에너지다.
        mel_db = librosa.power_to_db(mel, ref=1.0, top_db=None)
        surface = [np.rint(np.clip((chunk.mean(axis=1) + 65) / 80, 0, 1) * 255).astype(int).tolist() for chunk in np.array_split(mel_db, 40, axis=1)]
        tracks.append({
            "id": kind,
            "src": f"/static/assets/demo/{kind}.wav",
            "duration": round(len(y) / sr, 3),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "waveform": peaks,
            "surface": surface,
            "spectrum": db,
            "summary": summary_metrics(feature),
        })
    comparisons = []
    for index in (1, 2):
        similarity = float(cosine_similarity([vectors[0]], [vectors[index]])[0, 0])
        # MusicSimilarityEngine.find_similar와 같은 표시 규칙: 음수는 0, 양수는 ×100.
        comparisons.append({"track": tracks[index]["id"], "similarityPercent": round(max(0, min(100, similarity * 100)), 1)})
    data = {"sampleRate": SR, "featureCount": len(engine.feature_columns), "spectrumRange": [40, 10000], "tracks": tracks, "comparisons": comparisons}
    (DEST / "analysis.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    return data


if __name__ == "__main__":
    result = build()
    print(json.dumps({"comparisons": result["comparisons"], "tracks": [{"id": t["id"], "summary": t["summary"], "bytes": t["bytes"]} for t in result["tracks"]]}, ensure_ascii=False, indent=2))
