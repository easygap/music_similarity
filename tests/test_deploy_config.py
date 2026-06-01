"""배포 설정의 운영 기본값을 지키는 정적 회귀 테스트."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_docker_image_defaults_to_single_worker():
    """프로덕션 이미지 기본값은 in-memory 상태를 분산시키지 않도록 단일 worker 여야 한다."""
    text = _read("Dockerfile")

    assert "WEB_CONCURRENCY=1" in text
    assert "--workers ${WEB_CONCURRENCY:-1}" in text
    assert "--workers ${WEB_CONCURRENCY:-2}" not in text


def test_compose_and_paas_configs_pin_single_worker():
    """compose / Render / Fly 모두 단일 worker 운영 모델을 명시해야 한다."""
    compose = _read("docker-compose.yml")
    render = _read("render.yaml")
    fly = _read("fly.toml")

    assert "WEB_CONCURRENCY=1" in compose
    assert "WEB_CONCURRENCY" in render
    assert 'value: "1"' in render
    assert 'WEB_CONCURRENCY = "1"' in fly


def test_readme_documents_single_worker_default():
    """README 환경 변수 표도 Docker 기본값과 같은 단일 worker 를 안내해야 한다."""
    text = _read("README.md")

    assert "| `WEB_CONCURRENCY` | `1` |" in text
    assert "외부 상태 저장소" in text
