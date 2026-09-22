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


def test_operations_guide_documents_single_worker_default():
    """README에서 연결한 운영 안내도 Docker와 같은 단일 worker를 기본값으로 둔다."""
    assert "(CONTRIBUTING.md)" in _read("README.md")
    text = _read("CONTRIBUTING.md")

    assert "| `WEB_CONCURRENCY` | `1` |" in text
    assert "외부 상태 저장소" in text


def test_requirements_keep_validated_release_versions():
    """검증을 마친 출시 의존성 묶음이 병합 과정에서 되돌아가지 않아야 한다."""
    runtime = _read("requirements.txt")
    dev = _read("requirements-dev.txt")

    for requirement in (
        "fastapi==0.139.0",
        "starlette==1.3.1",
        "uvicorn[standard]==0.51.0",
        "python-multipart==0.0.32",
        "numpy==2.4.6",
        "scikit-learn==1.9.0",
        "soundfile==0.14.0",
        "setuptools==83.0.0",
    ):
        assert requirement in runtime

    for requirement in (
        "pytest==9.1.1",
        "pytest-asyncio==1.4.0",
        "pytest-cov==7.1.0",
        "httpx2==2.7.0",
        "ruff==0.15.21",
    ):
        assert requirement in dev

    assert "\nhttpx==" not in dev
