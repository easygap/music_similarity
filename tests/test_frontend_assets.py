"""프론트엔드 자산이 갖춰야 할 정적 조건들을 잡아두는 회귀 테스트.

브라우저 JS 를 파이썬 쪽에서 실제로 실행하긴 어려우니, 의도한 동작이 코드에
남아 있는지 텍스트 레벨로 확인한다. 라우드 19 에서 추가한 카탈로그 URL
영구화와 즐겨찾기 내보내기/가져오기 같은 기능이 회귀로 사라지지 않도록.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND = REPO_ROOT / "frontend"


def _read(rel: str) -> str:
    return (FRONTEND / rel).read_text(encoding="utf-8")


def test_favorites_js_exports_import_export_helpers():
    """favorites.js 가 exportJson / importJson / replaceAll 을 노출해야 한다."""
    text = _read("js/favorites.js")
    # window.SoundMatchFavorites 에 새 메서드가 다 등록되어야 한다.
    for name in ("exportJson", "importJson", "replaceAll"):
        assert name in text, f"favorites.js 에 {name} 함수가 없습니다."
    # 노출 객체 안에도 들어가 있어야 한다.
    block_start = text.find("window.SoundMatchFavorites = {")
    assert block_start != -1, "SoundMatchFavorites 노출 블록을 찾지 못했습니다."
    block_end = text.find("};", block_start)
    assert block_end != -1
    exported = text[block_start:block_end]
    for name in ("exportJson", "importJson", "replaceAll"):
        assert name in exported, f"SoundMatchFavorites 에 {name} 가 노출되지 않았습니다."


def test_favorites_js_export_payload_has_format_field():
    """exportJson 출력에는 포맷 식별자가 박혀 있어야 import 호환성 체크가 가능하다."""
    text = _read("js/favorites.js")
    assert '"soundmatch.favorites"' in text or "'soundmatch.favorites'" in text
    assert "version" in text


def test_favorites_js_import_handles_array_and_object():
    """importJson 이 raw 배열 / {items: [...]} 두 형태를 모두 받도록 분기되어야 한다."""
    text = _read("js/favorites.js")
    assert "Array.isArray(parsed)" in text
    assert "parsed.items" in text


def test_catalog_html_has_url_persistence_helpers():
    """catalog.html 에 URL 양방향 동기화 헬퍼가 들어 있어야 한다."""
    text = _read("catalog.html")
    for marker in (
        "readStateFromUrl",
        "writeStateToUrl",
        "applyStateToInputs",
        "URLSearchParams",
        "history.replaceState",
        "popstate",
    ):
        assert marker in text, f"catalog.html 에 '{marker}' 가 보이지 않습니다."


def test_catalog_html_writes_url_on_state_changes():
    """필터/페이지/정렬 등을 바꿀 때 writeStateToUrl 이 호출되도록 연결되어야 한다."""
    text = _read("catalog.html")
    # 검색 / 페이지 이동 / 즐겨찾기 토글 / 정렬 변경 핸들러에서 모두 writeStateToUrl 호출.
    assert text.count("writeStateToUrl()") >= 5, "writeStateToUrl 가 충분히 호출되지 않습니다."


def test_catalog_modal_deeplink_to_url():
    """모달이 열리고 닫힐 때 URL 에 song= 파라미터를 양방향으로 동기화해야 한다."""
    text = _read("catalog.html")
    # state 에 song 필드.
    assert 'song: ""' in text or "song:''" in text or "song: \"\"" in text
    # URL 쓰기 / 읽기 양쪽에서 song 다룸.
    assert 'p.set("song", state.song)' in text
    assert 'p.has("song")' in text
    # 모달 열림 시 state.song 갱신.
    assert "state.song = name" in text
    # 닫힘 시 state.song 비움.
    assert 'state.song = ""' in text
    # 초기 로드 시 URL 에 song 있으면 자동 오픈.
    assert "if (state.song)" in text
    assert "openSimilarModal(state.song)" in text


@pytest.mark.parametrize(
    "marker",
    [
        "favorites-export",
        "favorites-import-btn",
        "favorites-import-file",
        'data-i18n="favorites.export"',
        'data-i18n="favorites.import"',
    ],
)
def test_index_html_has_favorites_import_export_buttons(marker: str):
    """메인 페이지 즐겨찾기 섹션에 내보내기/가져오기 UI 가 있어야 한다."""
    text = _read("index.html")
    assert marker in text, f"index.html 에 '{marker}' 가 없습니다."


def test_i18n_has_favorites_import_export_strings():
    """ko/en 모두 새 키들을 가지고 있어야 한다 (parity 테스트와 별개 회귀 안전망)."""
    text = _read("js/i18n.js")
    for key in ("export:", "import:", "importSuccess:", "importFailed:", "exportDone:"):
        assert text.count(key) >= 2, f"i18n.js 에 '{key}' 가 ko/en 양쪽에 보이지 않습니다."


def test_app_js_wires_favorites_export_button():
    """app.js 가 export/import 버튼을 실제로 잡아서 핸들러를 달고 있는지 확인."""
    text = _read("js/app.js")
    assert 'getElementById("favorites-export")' in text
    assert 'getElementById("favorites-import-btn")' in text
    assert 'getElementById("favorites-import-file")' in text
    # Blob 다운로드와 file.text() 기반 import.
    assert "Blob([" in text
    assert "URL.createObjectURL" in text
    assert "importJson" in text


@pytest.mark.parametrize("page", ["catalog.html", "compare.html"])
def test_subpages_load_i18n(page: str):
    """카탈로그 / 비교 페이지도 i18n.js 를 직접 로딩해야 lang 토글이 동작한다."""
    text = _read(page)
    assert '<script src="/i18n.js">' in text, f"{page} 가 i18n.js 를 불러오지 않습니다."


@pytest.mark.parametrize(
    "marker",
    [
        'data-i18n="catalog.title"',
        'data-i18n="catalog.sub"',
        'data-i18n-attr="placeholder:catalog.searchPlaceholder"',
        'data-i18n="catalog.favoritesOnly"',
        'data-i18n="catalog.sortLabel"',
        'data-i18n="catalog.sortDefault"',
        'data-i18n="catalog.prev"',
        'data-i18n="catalog.next"',
        'data-i18n="catalog.bpmDist"',
    ],
)
def test_catalog_html_has_i18n_markers(marker: str):
    """catalog.html 의 정적 텍스트가 모두 i18n 키로 표시되어 있어야 한다."""
    text = _read("catalog.html")
    assert marker in text, f"catalog.html 에 '{marker}' 가 없습니다."


@pytest.mark.parametrize(
    "marker",
    [
        'data-i18n="compare.title"',
        'data-i18n="compare.sub"',
        'data-i18n="compare.left"',
        'data-i18n="compare.right"',
        'data-i18n="compare.emptyTitle"',
        'data-i18n="compare.emptyBody"',
    ],
)
def test_compare_html_has_i18n_markers(marker: str):
    """compare.html 의 정적 텍스트가 모두 i18n 키로 표시되어 있어야 한다."""
    text = _read("compare.html")
    assert marker in text, f"compare.html 에 '{marker}' 가 없습니다."


def test_catalog_js_uses_i18n_runtime():
    """카탈로그의 동적 텍스트(meta, modal, sub) 도 t() / i18n.t() 호출을 거쳐야 한다."""
    text = _read("catalog.html")
    # 안전 폴백 t() 헬퍼가 있고, 핵심 메시지들이 그 헬퍼를 통해 갱신되어야 한다.
    assert "window.i18n && typeof window.i18n.t === \"function\"" in text
    for key in (
        't("catalog.loading")',
        't("catalog.empty")',
        't("catalog.metaRange"',
        't("catalog.cardHint")',
        't("catalog.modalSub"',
        't("catalog.modalLoading")',
        't("catalog.modalFail")',
    ):
        assert key in text, f"catalog.html 에 '{key}' 호출이 없습니다."


def test_compare_js_uses_i18n_runtime():
    """compare.html 도 메트릭 라벨을 t() 로 resolve 해야 한다."""
    text = _read("compare.html")
    assert "window.i18n && typeof window.i18n.t === \"function\"" in text
    for key in (
        "compare.metric.tempo",
        "compare.metric.energy",
        "compare.metric.brightness",
        "compare.metric.noisiness",
        "compare.metric.harmony",
        "compare.metric.chroma",
        't("compare.topMatch")',
        't("compare.topSuffix")',
        't("compare.invalid")',
    ):
        assert key in text, f"compare.html 에 '{key}' 가 없습니다."
