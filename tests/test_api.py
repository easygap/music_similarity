"""FastAPI 라우트 e2e 테스트. TestClient + 합성 데이터셋 조합."""
from __future__ import annotations

from pathlib import Path


def test_health(fastapi_client):
    r = fastapi_client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["catalog_size"] == 3


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
