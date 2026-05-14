"""스펙트로그램 SVG 렌더링 모듈의 회귀 테스트.

대부분은 librosa 통합 경로(test_api.py) 가 덮지만, 그쪽은 실패 시 빈
문자열로 swallow 되어서 내부 헬퍼 함수(_downsample_2d, _color_for,
_render_svg) 가 깨져도 알기 어렵다. 여기서 헬퍼 단위로 직접 검증한다.
"""
from __future__ import annotations

import numpy as np

from backend.spectrogram import (
    _color_for,
    _downsample_2d,
    _render_svg,
    build_mel_spectrogram_svg,
)

# --- _downsample_2d -----------------------------------------------------

def test_downsample_preserves_overall_shape():
    """입력보다 작은 (h, w) 로 풀링했을 때 shape 가 정확히 (h, w)."""
    arr = np.arange(96 * 200, dtype=float).reshape(96, 200)
    out = _downsample_2d(arr, 48, 96)
    assert out.shape == (48, 96)


def test_downsample_pads_smaller_input():
    """입력이 목표 그리드보다 작으면 0 패딩 + 원본 값을 좌상단에 보존."""
    arr = np.array([[1.0, 2.0], [3.0, 4.0]])  # 2x2
    out = _downsample_2d(arr, 4, 4)  # 더 큰 그리드 요청
    assert out.shape == (4, 4)
    # 좌상단 2x2 는 원본.
    assert out[0, 0] == 1.0
    assert out[1, 1] == 4.0
    # 나머지는 arr.min() = 1.0 로 채워진다.
    assert out[3, 3] == 1.0


def test_downsample_handles_empty_input():
    """완전히 빈 입력도 죽지 않고 0 채운 그리드를 돌려준다."""
    arr = np.zeros((0, 0))
    out = _downsample_2d(arr, 2, 2)
    assert out.shape == (2, 2)
    assert (out == 0.0).all()


def test_downsample_avg_pooling_values():
    """평균 풀링이 실제로 평균을 낸다 — 4x4 → 2x2 sanity check."""
    arr = np.array(
        [
            [1.0, 2.0, 3.0, 4.0],
            [5.0, 6.0, 7.0, 8.0],
            [9.0, 10.0, 11.0, 12.0],
            [13.0, 14.0, 15.0, 16.0],
        ]
    )
    out = _downsample_2d(arr, 2, 2)
    # 좌상단 4셀의 평균.
    assert out[0, 0] == np.array([1.0, 2.0, 5.0, 6.0]).mean()
    assert out[1, 1] == np.array([11.0, 12.0, 15.0, 16.0]).mean()


# --- _color_for ---------------------------------------------------------

def test_color_for_clamps_below_zero():
    """음수 값도 가장 어두운 색으로 안정적으로 매핑."""
    c = _color_for(-1.0)
    assert c.startswith("#")
    assert len(c) == 7


def test_color_for_clamps_above_one():
    """1 이상도 가장 밝은 시안으로 매핑."""
    c = _color_for(5.0)
    assert c.startswith("#")
    assert len(c) == 7


def test_color_for_endpoints():
    """양 끝점은 기대 색상(어두운 보라 / 시안) 근처."""
    dark = _color_for(0.0)
    bright = _color_for(1.0)
    # 두 색이 같으면 안 된다.
    assert dark != bright
    # 어두운 끝: 첫 채널(R) 값이 작다.
    assert int(dark[1:3], 16) < int(bright[1:3], 16)


def test_color_for_returns_hex_format():
    """리턴 형식이 모두 #rrggbb 형태여야 한다 (CSS 컬러 파싱 안전성)."""
    import re

    pattern = re.compile(r"^#[0-9a-f]{6}$")
    for v in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert pattern.match(_color_for(v)), f"{v} -> {_color_for(v)}"


# --- _render_svg --------------------------------------------------------

def test_render_svg_produces_valid_svg_root():
    """렌더 결과가 <svg ... viewBox=...> 로 시작해야 한다."""
    grid = np.zeros((4, 4))
    svg = _render_svg(grid)
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg"')
    assert "viewBox" in svg
    assert svg.endswith("</svg>")


def test_render_svg_has_one_rect_per_cell_plus_background():
    """각 셀당 한 개 rect + 배경 rect 한 개 — 4×4 그리드면 17개."""
    grid = np.zeros((4, 4))
    svg = _render_svg(grid)
    assert svg.count("<rect ") == 4 * 4 + 1


def test_render_svg_includes_aria_label():
    """접근성: aria-label 이 들어 있어야 스크린리더 사용자가 이미지 의미를 안다."""
    svg = _render_svg(np.zeros((2, 2)))
    assert 'aria-label="업로드한 곡의 멜 스펙트로그램"' in svg
    assert 'role="img"' in svg


# --- build_mel_spectrogram_svg (통합) --------------------------------------

def test_build_mel_spectrogram_returns_string(tiny_wav):
    """짧은 사인파 WAV 도 SVG 문자열을 안전하게 돌려줘야 한다."""
    svg = build_mel_spectrogram_svg(tiny_wav)
    assert isinstance(svg, str)
    assert "<svg" in svg
    # 사인파라도 어떤 셀은 색을 받는다.
    assert "<rect" in svg


def test_build_mel_spectrogram_max_duration_clips(tiny_wav):
    """max_duration 을 짧게 잡아도 죽지 않아야 한다."""
    svg = build_mel_spectrogram_svg(tiny_wav, max_duration=0.1)
    assert isinstance(svg, str)
