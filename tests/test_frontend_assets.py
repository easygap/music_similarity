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


def test_footer_shows_build_info_from_version_api():
    """footer 에 v{버전} · {release_date} (· {git_commit}) 형태의 빌드 정보 라인이 있어야 한다."""
    html = _read("index.html")
    assert 'id="footer-build"' in html
    js = _read("js/app.js")
    # /api/version 응답의 version + release_date (+ git_commit) 를 활용.
    assert "data.release_date" in js
    assert "data.git_commit" in js, "git_commit 까지 footer 에 노출해야 합니다."
    # `v` 접두는 그대로 유지.
    assert "`v${" in js or "'v' +" in js or '"v" +' in js
    # 분리자가 · 인지 확인 — 셋 다 (version / date / sha) join 패턴.
    assert ' · ' in js


def test_hero_shows_social_proof_total_analyses():
    """Hero 영역에 누적 분석 횟수 라인이 있어야 한다."""
    html = _read("index.html")
    assert 'id="hero-social-proof"' in html
    js = _read("js/app.js")
    assert "loadSocialProof" in js
    assert 'data.analyses_total' in js or "analyses_total" in js
    assert 't("hero.totalAnalyses"' in js


def test_hero_stat_shows_catalog_freshness():
    """Hero stat 카드에 카탈로그 갱신 일자가 노출되어야 한다."""
    html = _read("index.html")
    assert 'id="stat-catalog-fresh"' in html
    js = _read("js/app.js")
    # /api/health 응답의 catalog_updated_at 을 읽어서 stat-catalog-fresh 채움.
    assert "catalog_updated_at" in js
    assert 't("hero.catalogFresh"' in js
    # lang 토글 시 라벨 재계산.
    assert 'loadLatencyStat()' in js


def test_style_has_print_media_block():
    """style.css 에 결과 페이지를 인쇄/PDF 친화로 만드는 @media print 블록이 있어야 한다."""
    text = _read("css/style.css")
    assert "@media print" in text
    # 핵심 요소들이 숨김 처리되는지 빠르게 확인.
    for marker in (".site-nav,", ".results-actions,", ".audio-player,", "break-inside: avoid"):
        assert marker in text, f"@media print 블록에 '{marker}' 가 없습니다."


def test_catalog_search_highlights_matched_substring():
    """검색어와 매칭된 부분을 <mark> 로 강조하는 헬퍼가 catalog.html 에 존재해야 한다."""
    text = _read("catalog.html")
    assert "function highlightMatch(" in text
    # 대소문자 무시 매칭.
    assert "toLowerCase()" in text
    # mark 클래스
    assert "cat-highlight" in text
    # title / artist 모두 highlight 호출을 거치도록 적용.
    assert "highlightMatch(it.title, needle)" in text
    assert "highlightMatch(it.artist, needle)" in text


def test_catalog_modal_hits_show_match_metrics():
    """카탈로그 모달의 매칭 곡 리스트에도 BPM/에너지 mini-row 가 표시되어야 한다."""
    text = _read("catalog.html")
    # 카탈로그 카드와 같은 buildMetricsLine 헬퍼를 모달에서도 재사용.
    assert "r.match_summary" in text
    assert "buildMetricsLine(r.match_summary" in text
    # 모달 안에서 display: flex / margin-top 강제로 줄바꿈.
    assert ".modal-hits .cat-metrics" in text


def test_catalog_card_has_metrics_mini_row():
    """카탈로그 카드에 BPM/에너지/밝기 mini-row 가 렌더링되어야 한다."""
    text = _read("catalog.html")
    assert "function buildMetricsLine(" in text
    assert 'class="cat-metrics"' in text
    # 카드 render 에서 metrics 객체를 헬퍼로 넘기는지.
    assert "buildMetricsLine(it.metrics)" in text


def test_catalog_search_has_recent_searches_datalist():
    """검색 input 에 최근 검색어 datalist + localStorage 저장 와이어링이 있어야 한다."""
    text = _read("catalog.html")
    assert 'list="cat-recent-searches"' in text
    assert 'id="cat-recent-searches"' in text
    assert "soundmatch.catalog.recent-searches" in text
    assert "function pushRecentSearch(" in text
    assert "function renderRecentSearches()" in text
    # 의미 있는 검색 결과(0건 X) 일 때만 기록.
    assert "state.q && data.total > 0" in text


def test_catalog_search_has_clear_button():
    """카탈로그 검색 input 에 clear (×) 버튼 + Escape 키 핸들러가 있어야 한다."""
    text = _read("catalog.html")
    assert 'id="cat-search-clear"' in text
    assert "function clearSearch()" in text
    assert "function syncSearchClearVisibility()" in text
    # Escape 키 처리.
    assert 'e.key === "Escape"' in text
    # i18n attr.
    assert 'data-i18n-attr="aria-label:catalog.searchClear"' in text


def test_catalog_favorites_toggle_shows_count():
    """카탈로그 즐겨찾기만 보기 토글에 현재 카운트 chip 이 노출되어야 한다."""
    text = _read("catalog.html")
    assert 'id="cat-fav-count"' in text
    assert 'id="cat-favorites-only-label"' in text
    assert "function syncFavoritesCount()" in text
    # 비어 있을 때 토글 비활성 처리.
    assert "favOnly.disabled = true" in text
    assert "is-empty" in text
    # favorites:change 이벤트 구독 (다른 페이지에서 변경 시 즉시 동기화).
    assert 'window.addEventListener("favorites:change", syncFavoritesCount)' in text


def test_catalog_pager_has_first_last_jump_buttons():
    """카탈로그 페이저에 first/last 점프 버튼 + sync 헬퍼가 있어야 한다."""
    text = _read("catalog.html")
    assert 'id="cat-first"' in text
    assert 'id="cat-last"' in text
    assert "function syncPagerControls()" in text
    # last 점프는 ceil(total/size) 로 계산.
    assert "Math.ceil(state.total / state.size)" in text
    # 페이저 4개 버튼 모두 disabled 동기화.
    assert "first.disabled" in text
    assert "last.disabled" in text


def test_catalog_has_page_size_select():
    """카탈로그 페이지에 페이지당 곡 수 select (24/48/96) + URL 영구화 와이어링."""
    text = _read("catalog.html")
    assert 'id="cat-size"' in text
    # 24/48/96 옵션 모두 존재.
    for v in ('value="24"', 'value="48"', 'value="96"'):
        assert v in text
    # change 핸들러 + URL persistence (기본 24 와 다를 때만 URL 노출).
    assert "sizeEl.addEventListener" in text
    assert "state.size !== 24" in text
    # i18n 라벨.
    assert 'data-i18n="catalog.sizeLabel"' in text


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


def test_results_expand_toggle_button_present_and_wired():
    """결과 헤더에 펼침/접기 토글 버튼이 있고, localStorage 에 선호가 저장돼야 한다."""
    html = _read("index.html")
    assert 'id="expand-toggle-btn"' in html
    assert 'data-i18n="results.expandAll"' in html
    js = _read("js/app.js")
    assert "soundmatch.hit-expand-mode" in js
    assert "function readExpandMode()" in js
    assert "function writeExpandMode(" in js
    assert "applyExpandModeToVisibleCards" in js
    # i18n 라벨 동기화.
    assert 't("results.collapseAll")' in js
    assert 't("results.expandAll")' in js


def test_results_csv_export_button_present_and_wired():
    """결과 영역에 CSV 다운로드 버튼이 있고, app.js 가 핸들러를 달고 있어야 한다."""
    html = _read("index.html")
    assert 'id="export-csv-btn"' in html
    assert 'data-i18n="results.exportCsv"' in html
    js = _read("js/app.js")
    assert 'getElementById("export-csv-btn")' in js or '$("#export-csv-btn")' in js
    # 직렬화 헬퍼.
    assert "function buildResultsCsv(" in js
    # RFC 4180 escape 흔적.
    assert "/[\",\\r\\n]/" in js
    # UTF-8 BOM (한글 깨짐 방지).
    assert '"﻿"' in js or "'﻿'" in js


def test_shortcuts_help_modal_and_keybind():
    """'?' 키로 단축키 도움말 모달이 토글되어야 한다."""
    html = _read("index.html")
    assert 'id="shortcuts-modal"' in html
    assert 'data-i18n="shortcuts.title"' in html
    js = _read("js/app.js")
    assert "function openShortcutsModal()" in js
    assert "function closeShortcutsModal()" in js
    # '?' 키 분기 + isTyping 가드.
    assert 'e.key === "?"' in js


def test_shortcuts_modal_has_focus_trap():
    """shortcuts 도움말 모달도 카탈로그 모달과 같은 focus trap + 이전 포커스 복원."""
    js = _read("js/app.js")
    assert "SHORTCUTS_FOCUSABLE_SEL" in js
    assert "function shortcutsFocusable()" in js
    # 모달 열림 시 이전 포커스 저장.
    assert "_shortcutsPrevFocus = document.activeElement" in js
    # 닫힘 시 복원.
    assert "_shortcutsPrevFocus.focus()" in js
    # Tab key 트랩 분기 — 모달 keydown 리스너.
    assert "shortcutsModal.addEventListener(\"keydown\"" in js


def test_favorites_section_has_sort_select_with_localstorage_pref():
    """즐겨찾기 섹션에 정렬 select + localStorage 선호 저장이 와이어링돼야 한다."""
    html = _read("index.html")
    assert 'id="favorites-sort"' in html
    assert 'data-i18n="favorites.sortRecent"' in html
    assert 'data-i18n="favorites.sortTitle"' in html
    assert 'data-i18n="favorites.sortArtist"' in html
    js = _read("js/app.js")
    assert "soundmatch.fav-sort" in js
    assert "function readFavSort()" in js
    assert "function sortFavorites(" in js
    # localeCompare 로 ko/en 양쪽 자연 정렬.
    assert "localeCompare(" in js


def test_hit_card_has_catalog_deeplink_button():
    """각 hit 카드에 '카탈로그에서 보기' 버튼 + /catalog?song= 와이어링."""
    html = _read("index.html")
    assert 'link-btn-catalog' in html
    assert 'data-link="catalog"' in html
    assert 'data-i18n="results.openInCatalog"' in html
    js = _read("js/app.js")
    assert "[data-link=\"catalog\"]" in js
    # /catalog?song= 형식의 deep-link.
    assert "/catalog?song=" in js
    assert "encodeURIComponent(songKey)" in js


def test_result_meta_uses_local_timezone_formatter():
    """결과 메타의 analyzed_at 이 ISO 를 사용자 로컬 타임존으로 포맷해야 한다."""
    text = _read("js/app.js")
    assert "function formatLocalTimestamp(" in text
    # Date 생성 + toLocaleString.
    assert "new Date(String(iso))" in text
    assert "d.toLocaleString(" in text
    # Locale 분기 (ko-KR / en-US).
    assert '"en-US"' in text and '"ko-KR"' in text
    # renderResultMeta 가 헬퍼를 호출.
    assert "formatLocalTimestamp(data.analyzed_at)" in text


def test_results_meta_footer_shows_analysis_info():
    """결과 영역 끝에 분석 메타 footer (시각/카탈로그/엔진/캐시) 가 그려져야 한다."""
    html = _read("index.html")
    assert 'id="result-meta"' in html
    js = _read("js/app.js")
    assert "function renderResultMeta(" in js
    # 핵심 키들이 함께 그려지는지.
    for needle in ("analyzed_at", "catalog_size", "engine_version", "cached"):
        assert needle in js
    # i18n 키 호출.
    for key in ("metaAnalyzedAt", "metaCatalogSize", "metaCached"):
        assert f't("results.{key}"' in js or f't("results.{key}",' in js


def test_results_jk_keyboard_navigation():
    """결과 페이지에서 j/k (↓/↑) 로 hit 카드 이동 + Enter 토글 핸들러 존재 확인."""
    text = _read("js/app.js")
    assert "function selectHitByIdx(" in text
    # j / ArrowDown / k / ArrowUp 분기.
    assert 'e.key === "j"' in text
    assert 'e.key === "k"' in text
    assert "ArrowDown" in text
    assert "ArrowUp" in text
    # 선택된 카드의 dataset.
    assert 'el.dataset.selected = "true"' in text
    # CSS 측 selected 표시.
    css = _read("css/style.css")
    assert '.hit[data-selected="true"]' in css


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
