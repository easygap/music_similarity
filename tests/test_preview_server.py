"""디자인 프리뷰 서버(preview_server.py) 회귀 테스트.

preview_server 는 librosa/sklearn 없이 frontend 를 띄워보는 개발 도구다.
새 API 엔드포인트가 백엔드에 추가될 때 여기도 같이 갱신되지 않으면
디자이너가 카탈로그 페이지 / 샘플 버튼 등을 프리뷰할 수 없게 된다.
그 'drift' 를 잡기 위한 안전망.
"""
from __future__ import annotations

import json
import socket
import threading
import urllib.request
from contextlib import closing
from http.server import HTTPServer

import pytest

import preview_server


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def preview_url():
    """preview_server 를 백그라운드 스레드로 띄우고 base URL 을 돌려준다."""
    port = _free_port()
    httpd = HTTPServer(("127.0.0.1", port), preview_server.PreviewHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def _get(url: str):
    with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: S310 - 로컬 테스트 서버
        return resp.status, resp.read().decode("utf-8")


def test_preview_dummy_catalog_is_well_formed():
    """PREVIEW_CATALOG 의 각 항목이 프론트가 기대하는 형태여야 한다."""
    assert len(preview_server.PREVIEW_CATALOG) >= 20
    for item in preview_server.PREVIEW_CATALOG:
        assert "title" in item and "artist" in item
        m = item["metrics"]
        assert {"bpm", "energy_rms", "brightness"} <= set(m)


def test_preview_serves_version(preview_url):
    """/api/version 더미가 git_commit / dependencies 까지 포함해야 한다."""
    status, body = _get(preview_url + "/api/version")
    assert status == 200
    data = json.loads(body)
    assert data["version"]
    assert "git_commit" in data
    assert "dependencies" in data


def test_preview_serves_version_changelog(preview_url):
    """/api/version/changelog 더미 — '새 기능' 모달용."""
    status, body = _get(preview_url + "/api/version/changelog")
    assert status == 200
    data = json.loads(body)
    assert data["releases"], "releases 가 비어 있으면 모달이 빈 상태로 뜬다."
    assert "version" in data["releases"][0]


def test_preview_catalog_search_paginates_and_filters(preview_url):
    """/api/catalog/search 더미가 q 필터 + 페이지네이션을 흉내내야 한다."""
    status, body = _get(preview_url + "/api/catalog/search?page=1&size=10")
    assert status == 200
    data = json.loads(body)
    assert data["size"] == 10
    assert len(data["items"]) == 10
    assert data["has_more"] is True
    # q 필터 — 'Track 03' 은 한 곡만.
    _, body2 = _get(preview_url + "/api/catalog/search?q=Track%2003")
    assert json.loads(body2)["total"] == 1


def test_preview_catalog_random_and_by_catalog(preview_url):
    """샘플 버튼 경로 — random 으로 곡을 뽑고 by-catalog 로 분석 결과를 받는다."""
    status, body = _get(preview_url + "/api/catalog/random?n=3")
    assert status == 200
    assert len(json.loads(body)["items"]) == 3
    status2, body2 = _get(preview_url + "/api/analyze/by-catalog?name=Preview+Track+05+-+Tobu")
    assert status2 == 200
    data = json.loads(body2)
    assert data["results"], "by-catalog 응답에 results 가 있어야 결과 화면이 그려진다."


def test_preview_export_csv(preview_url):
    """/api/catalog/export.csv 더미가 CSV 헤더로 시작해야 한다."""
    status, body = _get(preview_url + "/api/catalog/export.csv")
    assert status == 200
    # BOM 을 떼고 헤더 검증.
    assert body.lstrip("﻿").startswith("title,artist,bpm,energy_rms,brightness,full_name")


@pytest.mark.parametrize("js", [
    "/app.js", "/i18n.js", "/theme-init.js", "/favorites.js",
    "/visualizers.js", "/error-boundary.js", "/sw-register.js",
])
def test_preview_serves_root_js_files(preview_url, js):
    """HTML 이 루트 경로(<script src="/app.js">)로 부르는 JS 가 200 이어야 한다.

    FastAPI 앱은 frontend/js/ 를 루트에서 서빙한다. 프리뷰 서버도 같은 alias 를
    따라가지 않으면 페이지가 통째로 동작 안 한다 (실제로 한 번 깨졌던 회귀).
    """
    status, _ = _get(preview_url + js)
    assert status == 200, f"{js} 가 200 이 아닙니다."


def test_preview_serves_root_style_css(preview_url):
    """/style.css 도 frontend/css/ 에서 서빙되어야 한다."""
    status, _ = _get(preview_url + "/style.css")
    assert status == 200


@pytest.mark.parametrize("page", ["/catalog", "/compare", "/privacy", "/terms"])
def test_preview_serves_pretty_page_routes(preview_url, page):
    """확장자 없는 페이지 라우트(/catalog 등) 도 HTML 을 돌려줘야 한다.

    FastAPI 앱이 @app.get("/catalog") 식으로 노출하는 경로 — 프리뷰 서버도
    같은 매핑을 해줘야 nav 링크 / deep link 가 동작한다.
    """
    status, body = _get(preview_url + page)
    assert status == 200, f"{page} 가 200 이 아닙니다."
    assert "<!DOCTYPE html>" in body or "<!doctype html>" in body.lower()


def test_preview_serves_catalog_sample(preview_url):
    """/api/catalog/sample — 메인 페이지 하단 카탈로그 미리보기용."""
    status, body = _get(preview_url + "/api/catalog/sample?limit=6")
    assert status == 200
    data = json.loads(body)
    assert len(data["items"]) == 6
