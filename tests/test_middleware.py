"""RequestLogMiddleware / lifespan degraded path 회귀 테스트.

통합 경로(test_api) 가 대부분 커버하지만, X-Request-ID 분기와
다운된 엔진 상태에서의 health 응답은 명시적 회귀 안전망이 없다.
여기서 마이크로 단위로 검증한다.
"""
from __future__ import annotations

import importlib
import os
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def fresh_module(tmp_path, monkeypatch):
    """깨끗한 backend.main 인스턴스. 다른 테스트의 module 캐시 / metrics 가 끼지 않도록."""
    os.environ.setdefault("MUSIC_SKIP_WARMUP", "1")
    # 합성 dataset 을 새로 깔아 둔다 — 정상 케이스 검증용.
    import csv

    from backend.audio_features import FEATURE_COLUMNS

    ds = tmp_path / "dataset.csv"
    with ds.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["musicname & artist", *FEATURE_COLUMNS])
        for i, name in enumerate(["A - x", "B - x", "C - x"]):
            row = [0.5 + 0.1 * i + 0.01 * j for j in range(len(FEATURE_COLUMNS))]
            w.writerow([name, *row])
    monkeypatch.setenv("MUSIC_DATASET_PATH", str(ds))

    import backend.main as mod

    importlib.reload(mod)
    return mod


# ---- RequestLogMiddleware --------------------------------------------------

def test_request_id_generated_when_missing(fresh_module):
    """X-Request-ID 헤더가 없으면 미들웨어가 새 UUID 를 발급해 응답에 넣어야 한다."""
    with TestClient(fresh_module.app) as c:
        r = c.get("/api/health")
    rid = r.headers.get("X-Request-ID")
    assert rid, "X-Request-ID 헤더가 응답에 없습니다."
    # UUID hex 라 32자 16진수. 길이로만 sanity check.
    assert len(rid) == 32
    int(rid, 16)  # 16진수 파싱 실패하면 ValueError.


def test_request_id_preserved_from_client(fresh_module):
    """클라이언트가 보낸 X-Request-ID 가 그대로 응답으로 돌아와야 한다 (분산 추적)."""
    sent = uuid.uuid4().hex
    with TestClient(fresh_module.app) as c:
        r = c.get("/api/health", headers={"X-Request-ID": sent})
    assert r.headers.get("X-Request-ID") == sent


def test_request_counter_skipped_for_metrics_and_sw(fresh_module):
    """/metrics 와 /sw.js 호출은 requests_total 카운터에 잡혀서는 안 된다.

    이쪽 경로까지 카운터에 잡히면 운영 그래프가 노이즈로 가득 차서 실제
    business request 추이를 못 본다.
    """
    with TestClient(fresh_module.app) as c:
        # 비즈니스 경로 한 번 (baseline 잡기 전).
        c.get("/api/health")
        before = c.get("/metrics").text
        # /metrics 자체 호출 한 번 더 — 카운터가 안 늘어나야 한다.
        c.get("/metrics")
        c.get("/sw.js")
        after = c.get("/metrics").text

    def total(text: str) -> int:
        for line in text.splitlines():
            if line.startswith("soundmatch_requests_total "):
                return int(float(line.split()[-1]))
        return -1

    # 두 시점 사이 /metrics 와 /sw.js 만 호출됐으니 delta 가 0 이어야 한다.
    delta = total(after) - total(before)
    assert delta == 0, f"/metrics 또는 /sw.js 호출이 requests_total 에 잡혔습니다 (delta={delta})."


def test_security_headers_attached_to_every_response(fresh_module):
    """모든 응답에 핵심 시큐어 헤더가 붙어야 한다 (HTML / JSON / 정적 파일 무관)."""
    with TestClient(fresh_module.app) as c:
        for path in ("/", "/api/health", "/style.css", "/manifest.webmanifest"):
            r = c.get(path)
            assert r.status_code in (200, 304), (path, r.status_code)
            assert r.headers.get("X-Content-Type-Options") == "nosniff", path
            assert r.headers.get("X-Frame-Options") == "DENY", path


# ---- lifespan degraded path -------------------------------------------------

def test_health_returns_degraded_503_when_engine_fails(monkeypatch, tmp_path):
    """카탈로그 CSV 가 깨져 있어 get_engine() 이 실패하면 /api/health 가 503 + status=degraded."""
    os.environ.setdefault("MUSIC_SKIP_WARMUP", "1")
    # 비어 있는 CSV. similarity engine 로딩 시점에 ValueError 가 떨어진다.
    bad = tmp_path / "bad.csv"
    bad.write_text("musicname & artist\n", encoding="utf-8")
    monkeypatch.setenv("MUSIC_DATASET_PATH", str(bad))
    import backend.main as mod

    importlib.reload(mod)
    with TestClient(mod.app) as c:
        r = c.get("/api/health")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["catalog_size"] == 0
    # 운영자 디버깅을 위해 어디서 실패했는지 식별자가 명시되어야 한다.
    assert body["reason"] == "engine_load_failed"
    # reason_detail 은 exception 클래스명 — 빈 문자열이 아니라 실제 type 이 와야 한다.
    assert body["reason_detail"], "reason_detail 이 비어 있으면 안 됩니다."


def test_health_strict_returns_503_when_upload_dir_unwritable(fresh_module, tmp_path, monkeypatch):
    """strict 모드에서 업로드 디렉토리에 쓰기 실패하면 503.

    실제로 readonly 디렉토리를 만들기는 OS 의존적이라 어렵다. 대신 UPLOAD_DIR 를
    존재하지 않는 깊은 경로로 가리켜서 write_bytes 가 FileNotFoundError → 우리
    코드의 OSError 분기로 떨어지게 한다.
    """
    monkeypatch.setattr(
        fresh_module,
        "UPLOAD_DIR",
        tmp_path / "no-such-parent" / "no-such-dir",
        raising=True,
    )
    with TestClient(fresh_module.app) as c:
        r = c.get("/api/health?strict=true")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    # 업로드 디렉토리 분기에 떨어졌으면 reason 이 upload_dir_not_writable.
    assert body["reason"] == "upload_dir_not_writable"
    # OSError 계열 (Windows: FileNotFoundError, POSIX: 동일) 의 클래스명이 들어와야 한다.
    assert body["reason_detail"] in {"FileNotFoundError", "PermissionError", "OSError"}


def test_ready_returns_503_when_upload_dir_unwritable(fresh_module, tmp_path, monkeypatch):
    """/api/ready 는 query string 없이도 strict health 와 같은 실패를 드러낸다."""
    monkeypatch.setattr(
        fresh_module,
        "UPLOAD_DIR",
        tmp_path / "no-such-parent" / "no-such-dir",
        raising=True,
    )
    with TestClient(fresh_module.app) as c:
        r = c.get("/api/ready")
    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["reason"] == "upload_dir_not_writable"


def test_health_ok_does_not_leak_reason_fields(fresh_module):
    """정상(ok) 응답에서는 reason / reason_detail 이 null 이어야 한다.

    degraded 전용 필드가 ok 응답에 빈 문자열 또는 임의 값으로 새어 나가면
    운영 대시보드 알람이 잘못 울릴 수 있다.
    """
    with TestClient(fresh_module.app) as c:
        r = c.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    # ok 응답에는 reason 키 자체가 없거나 None 이어야 한다.
    assert body.get("reason") is None
    assert body.get("reason_detail") is None
