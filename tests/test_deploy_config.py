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


def test_docker_image_accepts_git_commit_build_arg():
    """이미지 안에 .git 이 없어도 빌드 SHA 를 주입할 수 있어야 한다."""
    text = _read("Dockerfile")

    assert 'ARG GIT_COMMIT=""' in text
    assert "ENV MUSIC_GIT_COMMIT=${GIT_COMMIT}" in text


def test_docker_healthcheck_uses_python_runtime_only():
    """프로덕션 이미지는 healthcheck 때문에 curl 패키지를 추가 설치하지 않는다."""
    text = _read("Dockerfile")

    assert "curl" not in text
    assert "HEALTHCHECK --interval=30s --timeout=5s" in text
    assert '"python", "-c"' in text
    assert "urllib.request.urlopen" in text
    assert "os.environ.get('PORT', '8000')" in text


def test_deploy_healthchecks_use_readiness_probe():
    """배포 healthcheck 는 path-only readiness probe 로 strict 검사를 실행해야 한다."""
    dockerfile = _read("Dockerfile")
    compose = _read("docker-compose.yml")
    render = _read("render.yaml")
    fly = _read("fly.toml")

    assert "/api/ready" in dockerfile
    assert "/api/ready" in compose
    assert "healthCheckPath: /api/ready" in render
    assert 'path = "/api/ready"' in fly
    assert "timeout=3" in dockerfile
    assert "timeout=3" in compose


def test_ci_docker_build_injects_github_sha():
    """CI Docker 빌드는 /api/version 에 노출할 커밋 SHA 를 같이 넘겨야 한다."""
    text = _read(".github/workflows/ci.yml")

    assert "docker/build-push-action@v7" in text
    assert "build-args: |" in text
    assert "GIT_COMMIT=${{ github.sha }}" in text


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
