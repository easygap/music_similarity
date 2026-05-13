"""업로드된 음원의 멜 스펙트로그램을 SVG 로 그려주는 모듈.

PNG 를 만들려면 matplotlib 의존성이 필요해서 무거워진다. 우리는 librosa 가
이미 들어있고 numpy 만으로 충분한 SVG 격자를 만들 수 있으므로 그 쪽을 택했다.

응답 JSON 에 그대로 들어갈 수 있도록 ``build_mel_spectrogram_svg`` 가 SVG
문자열을 반환한다. 프론트엔드는 받은 문자열을 ``innerHTML`` 로 그리면 끝.
"""
from __future__ import annotations

from pathlib import Path

import librosa
import numpy as np

# 시각화 그리드 크기. 너무 크면 응답 페이로드가 커져서 모바일이 힘들다.
_TIME_BINS = 96
_FREQ_BINS = 48
_PIXEL_W = 720
_PIXEL_H = 220


def build_mel_spectrogram_svg(audio_path: str | Path, *, max_duration: float = 30.0) -> str:
    """오디오 파일로부터 멜 스펙트로그램 SVG 문자열을 만든다.

    실패하더라도 빈 문자열을 돌려주도록 호출 측에서 처리. 시각화는 부가 기능이라
    실패가 분석 자체를 막아서는 안 된다.
    """
    audio_path = Path(audio_path)
    y, sr = librosa.load(str(audio_path), duration=max_duration)
    if y.size == 0:
        return ""

    # mel-spectrogram → dB. shape: (n_mels, time_frames)
    mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=_FREQ_BINS * 2)
    mel_db = librosa.power_to_db(mel, ref=np.max)

    # 가로축(시간) bin 수를 _TIME_BINS 로, 세로축(주파수)을 _FREQ_BINS 로 다운샘플.
    grid = _downsample_2d(mel_db, _FREQ_BINS, _TIME_BINS)

    # dB 값을 [0, 1] 로 정규화. -80dB 가 가장 어둡고, 0dB 가 가장 밝다.
    grid = np.clip(grid, -80.0, 0.0)
    norm = (grid + 80.0) / 80.0
    return _render_svg(norm)


def _downsample_2d(arr: np.ndarray, h: int, w: int) -> np.ndarray:
    """2D 배열을 평균 풀링으로 (h, w) 그리드로 축소한다."""
    src_h, src_w = arr.shape
    # 안전장치: 입력이 더 작으면 그냥 원본을 0 패딩.
    if src_h < h or src_w < w:
        out = np.full((h, w), arr.min() if arr.size else 0.0, dtype=arr.dtype)
        rh = min(h, src_h)
        rw = min(w, src_w)
        out[:rh, :rw] = arr[:rh, :rw]
        return out

    # numpy 인덱스 그룹으로 평균 풀링. 빠르고 외부 의존성 없음.
    row_idx = np.linspace(0, src_h, h + 1, dtype=int)
    col_idx = np.linspace(0, src_w, w + 1, dtype=int)
    out = np.empty((h, w), dtype=arr.dtype)
    for i in range(h):
        r0, r1 = row_idx[i], max(row_idx[i + 1], row_idx[i] + 1)
        for j in range(w):
            c0, c1 = col_idx[j], max(col_idx[j + 1], col_idx[j] + 1)
            out[i, j] = arr[r0:r1, c0:c1].mean()
    return out


def _color_for(value: float) -> str:
    """0..1 정규화된 에너지를 보라색→시안 그라데이션 색상으로 매핑."""
    v = max(0.0, min(1.0, float(value)))
    # 두 색 사이 선형 보간.
    # 어두운 보라(#1a1430) → 보라(#7c5cff) → 시안(#22d3ee).
    if v < 0.5:
        t = v * 2
        r = int(0x1a + (0x7c - 0x1a) * t)
        g = int(0x14 + (0x5c - 0x14) * t)
        b = int(0x30 + (0xff - 0x30) * t)
    else:
        t = (v - 0.5) * 2
        r = int(0x7c + (0x22 - 0x7c) * t)
        g = int(0x5c + (0xd3 - 0x5c) * t)
        b = int(0xff + (0xee - 0xff) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _render_svg(grid: np.ndarray) -> str:
    """정규화된 (h, w) 그리드를 SVG 사각형 셀들로 직렬화."""
    h, w = grid.shape
    # 셀의 픽셀 크기. viewBox 기준으로 작성하므로 단순 비율.
    cell_w = _PIXEL_W / w
    cell_h = _PIXEL_H / h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_PIXEL_W} {_PIXEL_H}" '
        f'role="img" aria-label="업로드한 곡의 멜 스펙트로그램">',
        # 배경
        f'<rect width="{_PIXEL_W}" height="{_PIXEL_H}" fill="#0b0b18"/>',
    ]

    # 윗줄(높은 주파수)을 위로, 아랫줄(낮은 주파수)을 아래로 그리고 싶으므로 뒤집어 그린다.
    for i in range(h):
        y_index = h - 1 - i
        for j in range(w):
            color = _color_for(grid[y_index, j])
            x = j * cell_w
            y = i * cell_h
            parts.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" '
                f'width="{cell_w + 0.6:.2f}" height="{cell_h + 0.6:.2f}" '
                f'fill="{color}"/>'
            )
    parts.append("</svg>")
    return "".join(parts)
