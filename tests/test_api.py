"""End-to-end FastAPI route tests using the TestClient + a synthetic dataset."""
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
    r = fastapi_client.get("/")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "Content-Security-Policy" in r.headers


def test_request_id_round_trips(fastapi_client):
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
    r = fastapi_client.post(
        "/api/analyze",
        files={"file": ("evil.mp3", b"<html>nope</html>", "audio/mpeg")},
    )
    assert r.status_code == 400
    assert "오디오 형식" in r.json()["detail"]


def test_analyze_top_n_out_of_range(fastapi_client, tiny_wav):
    with tiny_wav.open("rb") as f:
        r = fastapi_client.post(
            "/api/analyze?top_n=999",
            files={"file": ("tone.wav", f.read(), "audio/wav")},
        )
    assert r.status_code == 422


def test_analyze_happy_path(fastapi_client, tiny_wav):
    """Full pipeline against the synthetic dataset returns ranked results."""
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
    huge = "audio/wav"
    r = fastapi_client.post(
        "/api/analyze",
        files={"file": ("big.wav", b"RIFF" + b"\x00" * 1024, huge)},
        headers={"Content-Length": str(100 * 1024 * 1024)},
    )
    # Either rejected up front (413) or after streaming (also 413 / 400).
    assert r.status_code in (400, 413)


def test_robots_txt(fastapi_client):
    r = fastapi_client.get("/robots.txt")
    assert r.status_code == 200
    assert "User-agent" in r.text


def test_temp_upload_directory_is_empty_after_request(fastapi_client, tiny_wav, tmp_path):
    """Successful analyze should not leave files behind."""
    with tiny_wav.open("rb") as f:
        fastapi_client.post(
            "/api/analyze",
            files={"file": ("tone.wav", f.read(), "audio/wav")},
        )
    upload_dir = Path(__import__("os").environ["MUSIC_UPLOAD_DIR"])
    leftovers = [p for p in upload_dir.iterdir() if p.is_file()]
    assert not leftovers, f"Temp uploads were not cleaned: {leftovers}"
