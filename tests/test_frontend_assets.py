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


def test_catalog_modal_has_focus_trap():
    """카탈로그 모달이 키보드 포커스 트랩과 자동 포커스 이동을 가지고 있어야 한다."""
    text = _read("catalog.html")
    # FOCUSABLE selector + 모달 내부 순환.
    assert "FOCUSABLE_SEL" in text
    assert "focusableInModal" in text
    # Tab / Shift+Tab 분기.
    assert 'e.key !== "Tab"' in text
    assert "e.shiftKey" in text
    # 첫 요소로 자동 포커스.
    assert "nodes[0].focus()" in text


def test_catalog_has_empty_state_reset_button():
    """필터로 결과가 0건일 때 사용자가 막다른 골목을 벗어날 수 있는 reset 버튼."""
    text = _read("catalog.html")
    # resetFilters 함수 본체 + i18n 키 호출이 같이 있어야 한다.
    assert "function resetFilters()" in text
    assert 't("catalog.resetFilters")' in text
    assert 'id="cat-empty-reset"' in text


def test_catalog_bpm_histogram_is_clickable():
    """BPM 히스토그램 막대가 button + 클릭 핸들러로 인터랙티브 해야 한다."""
    text = _read("catalog.html")
    # 막대 element 가 button 으로 그려진다.
    assert 'button type="button" class="cat-hist-bar"' in text
    # 클릭하면 state 의 BPM 범위에 bin 값이 들어간다.
    assert "state.minBpm = minVal" in text
    assert "state.maxBpm = maxVal" in text
    # active 상태 동기화 헬퍼가 존재.
    assert "function _syncHistActiveState()" in text
    # toggle off 동작 (같은 막대 다시 누르면 해제).
    assert "state.minBpm === minVal && state.maxBpm === maxVal" in text


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


def test_service_worker_shell_includes_subpages():
    """SW SHELL 에 /catalog, /compare, /favorites.js 가 모두 들어가야 한다.

    안 들어가면 오프라인 첫 진입 시 그 페이지가 안 뜬다.
    """
    text = _read("sw.js")
    for asset in ("/catalog", "/compare", "/favorites.js"):
        assert f'"{asset}"' in text, f"sw.js SHELL 에 '{asset}' 가 누락되었습니다."


def test_service_worker_version_string():
    """SW VERSION 은 'soundmatch-vN' 형태여야 한다 (캐시 무효화 규약)."""
    import re

    text = _read("sw.js")
    match = re.search(r'VERSION\s*=\s*"soundmatch-v(\d+)"', text)
    assert match, "sw.js 에서 VERSION 상수를 찾을 수 없습니다."
    version_num = int(match.group(1))
    # 셸 자산이 갱신될 때마다 한 칸씩 올라가야 하므로 v1 이상.
    assert version_num >= 2, "SW VERSION 이 자산 추가에 맞춰 bump 되지 않았습니다."


def test_render_mini_metrics_uses_i18n_labels():
    """미니 메트릭 라벨이 한국어 하드코딩이 아니라 i18n 키를 통해 그려져야 한다.

    예전엔 axes 의 label 이 "Tempo", "에너지", "밝기" 로 박혀 있어서 EN 토글
    상태에서도 한국어가 그대로 보였음.
    """
    text = _read("js/app.js")
    # 새 구현: labelKey + t() 호출.
    assert "labelKey: \"summary.tempo\"" in text
    assert "labelKey: \"summary.energy\"" in text
    assert "labelKey: \"summary.brightness\"" in text
    # 옛 하드코딩 라벨은 모두 사라져야 한다 — 무심코 부활하면 회귀.
    assert "label: \"Tempo\"" not in text
    assert "label: \"에너지\"" not in text
    assert "label: \"밝기\"" not in text


def test_run_analysis_uses_abort_controller():
    """runAnalysis 가 AbortController 를 만들어 fetch signal 로 전달하고,
    이전 진행 중이던 요청은 abort 하도록 되어 있어야 한다.
    """
    text = _read("js/app.js")
    assert "new AbortController()" in text
    assert "signal: controller.signal" in text
    # 이전 controller abort
    assert "_analysisAbortController.abort()" in text
    # stale 응답 가드
    assert "_analysisAbortController !== controller" in text
    # AbortError 는 에러 화면 안 띄우고 그냥 무시
    assert 'err.name === "AbortError"' in text


def test_reset_button_aborts_in_flight_analysis():
    """리셋 버튼이 진행 중인 분석을 같이 cancel 해야 stale 응답이 빈 화면에
    안 떠 오른다.
    """
    text = _read("js/app.js")
    # reset 핸들러 안에서 abort 호출.
    reset_section = text.split("resetBtn.addEventListener", 1)[1].split("});", 1)[0]
    assert "_analysisAbortController.abort()" in reset_section


def test_error_boundary_messages_pass_through_i18n():
    """error-boundary.js 의 토스트 메시지가 한국어 하드코딩이 아니라 i18n
    키를 통과해야 한다. 영어 사용자한테도 일관된 경험.
    """
    text = _read("js/error-boundary.js")
    # 키 호출이 들어가 있어야 한다.
    assert 'tr("error.globalToast")' in text
    assert 'tr("error.unhandledToast")' in text
    # 옛 한국어 하드코딩이 토스트 호출 부분에 남아 있으면 회귀.
    # (폴백 dict 안에는 한국어가 있어도 됨 — 그건 i18n.js 로드 실패 대비.)
    assert 'show("문제가 발생했어요' not in text
    assert 'show("요청 처리 중' not in text


def test_error_boundary_loaded_after_i18n():
    """index.html 에서 error-boundary.js 는 i18n.js 보다 뒤에 로드되어야
    `tr()` 호출 시점에 window.i18n 이 이미 정의되어 있음.
    """
    text = _read("index.html")
    i18n_pos = text.find('src="/i18n.js"')
    eb_pos = text.find('src="/error-boundary.js"')
    assert i18n_pos != -1 and eb_pos != -1
    assert i18n_pos < eb_pos


def test_history_strips_spectrogram_svg_before_saving():
    """addToHistory 가 localStorage 에 저장하기 전 ~320KB 짜리 spectrogram_svg
    를 빈 문자열로 trim 해야 한다. 그렇지 않으면 5건만으로 5MB 쿼터를 거의
    독식해서 즐겨찾기도 같이 망가짐.
    """
    text = _read("js/app.js")
    # trimmed copy 를 만들고 spectrogram_svg 만 비우는 패턴이 있어야 한다.
    assert 'spectrogram_svg: ""' in text
    assert "Object.assign({}, data, { spectrogram_svg" in text


def test_write_history_handles_quota_failure_with_toast():
    """writeHistory 가 try/catch 에서 silently 무시하지 말고 사용자에게 알려야
    한다. (history.storageFull i18n 키 호출이 있는지로 검증.)
    """
    text = _read("js/app.js")
    assert 't("history.storageFull")' in text


def test_favorites_emits_storage_full_event_on_quota_failure():
    """favorites.js write 실패 시 'favorites:storage-full' 이벤트를 쏴서
    app.js 가 사용자에게 토스트로 알릴 수 있어야 한다.
    """
    text_fav = _read("js/favorites.js")
    assert 'CustomEvent("favorites:storage-full")' in text_fav
    text_app = _read("js/app.js")
    assert 'favorites:storage-full' in text_app
    # 토스트 호출도 묶여 있어야 한다.
    assert 't("favorites.storageFull")' in text_app


def test_seed_from_hit_failure_restores_previous_results():
    """seedFromHit 가 실패해도 이전 결과 화면이 그대로 남아야 한다."""
    text = _read("js/app.js")
    # catch 블록이 _seedPrev 가 있을 때 renderResults 로 복원하고 토스트만 띄움.
    assert "renderResults(_seedPrev" in text
    assert 't("results.seedFailedToast")' in text


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
