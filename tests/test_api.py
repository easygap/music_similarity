"""FastAPI 라우트 e2e 테스트. TestClient + 합성 데이터셋 조합."""
from __future__ import annotations

from pathlib import Path


def test_health(fastapi_client):
    r = fastapi_client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["catalog_size"] == 3
    # 부팅 시간 이후로 흐른 시간이 보고되어야 한다.
    assert "uptime_seconds" in body
    assert body["uptime_seconds"] >= 0
    # latency P50 도 헬스에 함께 노출 (샘플 없으면 0).
    assert "analyze_latency_p50_seconds" in body


def test_catalog(fastapi_client):
    r = fastapi_client.get("/api/catalog")
    assert r.status_code == 200
    body = r.json()
    assert body["catalog_size"] == 3
    assert isinstance(body["features"], list)


def test_security_headers_on_index(fastapi_client):
    """프론트엔드(HTML) 응답에 시큐어 헤더가 붙어야 한다."""
    r = fastapi_client.get("/")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in r.headers


def test_request_id_round_trips(fastapi_client):
    """클라이언트가 보낸 X-Request-ID 가 응답에서도 동일하게 돌아와야 한다."""
    r = fastapi_client.get("/api/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers.get("X-Request-ID") == "abc-123"


def test_analyze_rejects_bad_extension(fastapi_client):
    r = fastapi_client.post(
        "/api/analyze",
        files={"file": ("evil.exe", b"MZ\x00\x00", "application/octet-stream")},
    )
    assert r.status_code == 400
    assert "지원하지 않는" in r.json()["detail"]


def test_analyze_rejects_empty_file(fastapi_client):
    r = fastapi_client.post(
        "/api/analyze",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )
    assert r.status_code == 400


def test_analyze_rejects_disguised_html(fastapi_client):
    """확장자만 mp3 인 HTML 파일은 매직 바이트 검증에서 잡혀야 한다."""
    r = fastapi_client.post(
        "/api/analyze",
        files={"file": ("evil.mp3", b"<html>nope</html>", "audio/mpeg")},
    )
    assert r.status_code == 400
    assert "오디오 형식" in r.json()["detail"]


def test_analyze_top_n_out_of_range(fastapi_client, tiny_wav):
    """top_n 이 범위를 벗어나면 FastAPI Query validator 가 422 를 돌려야 한다."""
    with tiny_wav.open("rb") as f:
        r = fastapi_client.post(
            "/api/analyze?top_n=999",
            files={"file": ("tone.wav", f.read(), "audio/wav")},
        )
    assert r.status_code == 422


def test_analyze_happy_path(fastapi_client, tiny_wav):
    """합성 데이터셋 대상 정상 분석 흐름."""
    with tiny_wav.open("rb") as f:
        r = fastapi_client.post(
            "/api/analyze?top_n=3",
            files={"file": ("tone.wav", f.read(), "audio/wav")},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["filename"] == "tone.wav"
    assert body["catalog_size"] == 3
    assert len(body["results"]) == 3
    top = body["results"][0]
    assert "title" in top
    assert "artist" in top
    assert "similarity_percent" in top
    assert "reason" in top
    assert "summary" in top["reason"]
    assert "groups" in top["reason"]
    assert "youtube_search_url" in top
    assert "spotify_search_url" in top


def test_analyze_oversized_payload_via_content_length(fastapi_client):
    """Content-Length 만 거대해도 사전 차단되어야 한다."""
    r = fastapi_client.post(
        "/api/analyze",
        files={"file": ("big.wav", b"RIFF" + b"\x00" * 1024, "audio/wav")},
        headers={"Content-Length": str(100 * 1024 * 1024)},
    )
    # 사전 차단(413) 이거나 스트리밍 도중 차단(413/400) 모두 허용.
    assert r.status_code in (400, 413)


def test_robots_txt(fastapi_client):
    r = fastapi_client.get("/robots.txt")
    assert r.status_code == 200
    assert "User-agent" in r.text
    assert "Sitemap" in r.text


def test_sitemap_xml(fastapi_client):
    r = fastapi_client.get("/sitemap.xml")
    assert r.status_code == 200
    assert "<urlset" in r.text


def test_pwa_manifest(fastapi_client):
    """PWA manifest 가 정상 JSON 으로 서빙되어야 한다."""
    r = fastapi_client.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert "application/manifest+json" in r.headers.get("content-type", "")
    data = r.json()
    assert data["name"]
    assert data["start_url"] == "/"
    assert isinstance(data["icons"], list)


def test_service_worker(fastapi_client):
    """SW 는 캐싱되면 안 되고 Service-Worker-Allowed 헤더가 붙어야 한다."""
    r = fastapi_client.get("/sw.js")
    assert r.status_code == 200
    assert "no-store" in r.headers.get("cache-control", "")
    assert r.headers.get("service-worker-allowed") == "/"


def test_offline_page(fastapi_client):
    r = fastapi_client.get("/offline.html")
    assert r.status_code == 200
    assert "오프라인" in r.text


def test_analyze_includes_metadata(fastapi_client, tiny_wav):
    """분석 결과에 분석 시각/엔진 버전/cached 플래그가 포함되어야 한다."""
    with tiny_wav.open("rb") as f:
        r = fastapi_client.post(
            "/api/analyze",
            files={"file": ("tone.wav", f.read(), "audio/wav")},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["analyzed_at"]  # ISO-8601 문자열
    assert "T" in body["analyzed_at"]
    assert body["engine_version"]
    assert body["cached"] is False  # 최초 분석은 캐시 미스


def test_analyze_second_call_hits_cache(fastapi_client, tiny_wav):
    """같은 파일을 두 번 올리면 두 번째는 캐시 히트가 되어야 한다."""
    with tiny_wav.open("rb") as f:
        payload = f.read()
    r1 = fastapi_client.post(
        "/api/analyze",
        files={"file": ("tone.wav", payload, "audio/wav")},
    )
    assert r1.status_code == 200
    assert r1.json()["cached"] is False

    r2 = fastapi_client.post(
        "/api/analyze",
        files={"file": ("tone.wav", payload, "audio/wav")},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["cached"] is True
    # 캐시 히트는 새로운 요청 ID 를 받아야 하고, 그래도 결과 자체는 동일해야 한다.
    assert body2["request_id"] != r1.json()["request_id"]
    assert body2["results"] == r1.json()["results"]


def test_metrics_includes_cache_counters(fastapi_client, tiny_wav):
    """/metrics 응답에 cache hit/miss 카운터가 노출되어야 한다."""
    # 분석 한 번 돌려서 카운터를 채운다.
    with tiny_wav.open("rb") as f:
        fastapi_client.post(
            "/api/analyze",
            files={"file": ("tone.wav", f.read(), "audio/wav")},
        )
    r = fastapi_client.get("/metrics")
    body = r.text
    assert "soundmatch_cache_hits_total" in body
    assert "soundmatch_cache_misses_total" in body
    assert "soundmatch_cache_entries" in body


def test_health_strict_mode(fastapi_client):
    """strict=1 모드에서도 정상 응답이면 200 + status=ok 를 돌려준다."""
    r = fastapi_client.get("/api/health?strict=1")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_catalog_search_default(fastapi_client):
    r = fastapi_client.get("/api/catalog/search")
    assert r.status_code == 200
    body = r.json()
    # 합성 카탈로그는 3곡이라서 기본 페이지에 다 들어와야 한다.
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["size"] == 24
    assert body["has_more"] is False
    assert len(body["items"]) == 3


def test_catalog_search_query_filters(fastapi_client):
    """q 파라미터가 부분 일치(대소문자 무시) 로 동작해야 한다."""
    r = fastapi_client.get("/api/catalog/search?q=alpha")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["title"].lower() == "alpha"


def test_catalog_search_pagination(fastapi_client):
    """size=1 이면 페이지마다 한 곡씩 잘려서 has_more 가 올바르게 나와야 한다."""
    r = fastapi_client.get("/api/catalog/search?size=1&page=1")
    body = r.json()
    assert body["total"] == 3
    assert len(body["items"]) == 1
    assert body["has_more"] is True

    r2 = fastapi_client.get("/api/catalog/search?size=1&page=3")
    body2 = r2.json()
    assert len(body2["items"]) == 1
    assert body2["has_more"] is False


def test_catalog_search_validates_size_bound(fastapi_client):
    r = fastapi_client.get("/api/catalog/search?size=9999")
    assert r.status_code == 422


def test_version_endpoint(fastapi_client):
    """/api/version 이 메타 정보를 정상 반환해야 한다."""
    r = fastapi_client.get("/api/version")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "soundmatch"
    assert body["version"]
    assert "features" in body and isinstance(body["features"], dict)
    assert body["features"]["spectrogram"] is True
    assert body["features"]["by_catalog"] is True
    assert isinstance(body["max_upload_bytes"], int)
    assert isinstance(body["rate_limit_per_min"], int)


def test_by_catalog_cache_marks_second_call(fastapi_client):
    """같은 (name, top_n) 으로 두 번 호출하면 두 번째는 cached: true 가 돼야 한다."""
    name = "Alpha - Tester"
    r1 = fastapi_client.get(f"/api/analyze/by-catalog?name={name}&top_n=2")
    r2 = fastapi_client.get(f"/api/analyze/by-catalog?name={name}&top_n=2")
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json().get("cached") is False
    assert r2.json().get("cached") is True
    # 결과 자체는 동일해야 한다.
    assert r1.json()["results"] == r2.json()["results"]


def test_analyze_by_catalog_returns_results(fastapi_client):
    """카탈로그 곡 이름으로 by-catalog 호출하면 자기 자신은 제외하고 응답해야 한다."""
    r = fastapi_client.get("/api/analyze/by-catalog?name=Alpha%20-%20Tester&top_n=2")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "catalog"
    assert body["title"] == "Alpha"
    assert body["artist"] == "Tester"
    # top_n=2 만 받았으니 결과도 최대 2개. 자기 자신은 빠져야 함.
    assert 1 <= len(body["results"]) <= 2
    for r_ in body["results"]:
        assert not (r_["title"] == "Alpha" and r_["artist"] == "Tester")


def test_analyze_by_catalog_unknown_name(fastapi_client):
    r = fastapi_client.get("/api/analyze/by-catalog?name=No%20Such%20Song")
    assert r.status_code == 404


def test_catalog_random(fastapi_client):
    """랜덤 추천 엔드포인트가 정상 응답하고 limit 범위 안에서 곡을 돌려준다."""
    r = fastapi_client.get("/api/catalog/random?n=2")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3  # 합성 카탈로그 사이즈
    assert len(body["items"]) == 2
    for it in body["items"]:
        assert "title" in it and "artist" in it


def test_catalog_random_validates_bounds(fastapi_client):
    r = fastapi_client.get("/api/catalog/random?n=999")
    assert r.status_code == 422


def test_catalog_page_renders(fastapi_client):
    r = fastapi_client.get("/catalog")
    assert r.status_code == 200
    assert "카탈로그 둘러보기" in r.text


def test_metrics_includes_inflight_gauge(fastapi_client):
    r = fastapi_client.get("/metrics")
    assert "soundmatch_inflight_analyses" in r.text


def test_favorites_js_served(fastapi_client):
    """favorites.js 정적 라우트가 정상 응답해야 한다."""
    r = fastapi_client.get("/favorites.js")
    assert r.status_code == 200
    body = r.text
    assert "SoundMatchFavorites" in body
    assert "soundmatch.favorites" in body


def test_metrics_includes_uptime_and_latency(fastapi_client, tiny_wav):
    """/metrics 에 uptime 과 latency P50/P95 게이지가 노출되어야 한다."""
    # 분석을 한 번 돌려서 latency 샘플이 생기게.
    with tiny_wav.open("rb") as f:
        fastapi_client.post(
            "/api/analyze",
            files={"file": ("tone.wav", f.read(), "audio/wav")},
        )
    r = fastapi_client.get("/metrics")
    body = r.text
    assert "soundmatch_uptime_seconds" in body
    assert "soundmatch_analyze_latency_p50_seconds" in body
    assert "soundmatch_analyze_latency_p95_seconds" in body


def test_health_head_method(fastapi_client):
    """모니터링 도구가 자주 사용하는 HEAD /api/health 가 200 으로 응답해야 한다."""
    r = fastapi_client.head("/api/health")
    assert r.status_code == 200
    # HEAD 응답은 본문 없어야 정상.
    assert r.content == b""


def test_sitemap_lists_static_pages(fastapi_client):
    """sitemap.xml 에 정적 페이지들이 모두 포함되어야 한다."""
    r = fastapi_client.get("/sitemap.xml")
    assert r.status_code == 200
    body = r.text
    for path in ("/", "/catalog", "/compare", "/privacy", "/terms"):
        assert f"<loc>{path}</loc>" in body


def test_analyze_returns_tags(fastapi_client, tiny_wav):
    """분석 결과에 휴리스틱 태그 배열이 포함되어야 한다."""
    with tiny_wav.open("rb") as f:
        r = fastapi_client.post(
            "/api/analyze",
            files={"file": ("tone.wav", f.read(), "audio/wav")},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "tags" in body
    assert isinstance(body["tags"], list)
    # 사인파라도 RMS / spectral / zcr 은 다 0이 아니라서 최소 1개는 매핑돼야 한다.
    assert len(body["tags"]) >= 1


def test_rate_limit_headers_exposed(fastapi_client, tiny_wav):
    """정상 분석 응답에 X-RateLimit-* 헤더가 붙어야 한다."""
    with tiny_wav.open("rb") as f:
        r = fastapi_client.post(
            "/api/analyze",
            files={"file": ("tone.wav", f.read(), "audio/wav")},
        )
    assert r.status_code == 200
    assert r.headers.get("X-RateLimit-Limit")
    assert r.headers.get("X-RateLimit-Remaining") is not None
    assert r.headers.get("X-RateLimit-Reset")


def test_metrics_endpoint(fastapi_client):
    """/metrics 가 Prometheus exposition 형식으로 응답해야 한다."""
    r = fastapi_client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    assert "soundmatch_requests_total" in body
    assert "# HELP" in body
    assert "# TYPE" in body
    assert "soundmatch_catalog_size" in body


def test_compare_page(fastapi_client):
    r = fastapi_client.get("/compare")
    assert r.status_code == 200
    assert "두 곡 나란히 비교" in r.text


def test_analyze_returns_spectrogram_svg(fastapi_client, tiny_wav):
    """정상 분석 결과에 멜 스펙트로그램 SVG 가 함께 내려와야 한다."""
    with tiny_wav.open("rb") as f:
        r = fastapi_client.post(
            "/api/analyze?top_n=3",
            files={"file": ("tone.wav", f.read(), "audio/wav")},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "spectrogram_svg" in body
    svg = body["spectrogram_svg"]
    # 빈 문자열은 시각화 실패 시의 폴백이라 허용. 정상 분석에선 SVG 가 들어와야 한다.
    assert svg.startswith("<svg ")
    assert "</svg>" in svg


def test_privacy_page(fastapi_client):
    r = fastapi_client.get("/privacy")
    assert r.status_code == 200
    assert "개인정보 처리 방침" in r.text


def test_terms_page(fastapi_client):
    r = fastapi_client.get("/terms")
    assert r.status_code == 200
    assert "이용 약관" in r.text


def test_catalog_sample(fastapi_client):
    """카탈로그 미리보기 엔드포인트가 정상 동작하는지 확인."""
    r = fastapi_client.get("/api/catalog/sample?limit=2")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1
    assert len(body["items"]) <= 2
    if body["items"]:
        item = body["items"][0]
        assert "title" in item and "artist" in item


def test_catalog_sample_validates_limit(fastapi_client):
    r = fastapi_client.get("/api/catalog/sample?limit=9999")
    assert r.status_code == 422


def test_openapi_docs_available(fastapi_client):
    """/docs 와 /openapi.json 가 서빙되는지 가벼운 확인."""
    spec = fastapi_client.get("/openapi.json")
    assert spec.status_code == 200
    data = spec.json()
    # 우리가 등록한 엔드포인트가 스펙에 들어 있어야 한다.
    paths = data.get("paths", {})
    assert "/api/health" in paths
    assert "/api/catalog" in paths
    assert "/api/analyze" in paths


def test_temp_upload_directory_is_empty_after_request(fastapi_client, tiny_wav):
    """정상 분석 후 임시 파일이 디스크에 남아있지 않아야 한다."""
    with tiny_wav.open("rb") as f:
        fastapi_client.post(
            "/api/analyze",
            files={"file": ("tone.wav", f.read(), "audio/wav")},
        )
    upload_dir = Path(__import__("os").environ["MUSIC_UPLOAD_DIR"])
    leftovers = [p for p in upload_dir.iterdir() if p.is_file()]
    assert not leftovers, f"임시 업로드 파일이 정리되지 않았습니다: {leftovers}"
