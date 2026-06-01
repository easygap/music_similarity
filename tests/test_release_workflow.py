"""릴리즈 자동화가 잘못된 태그를 막는지 확인하는 정적 회귀 테스트."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_release_workflow_checks_version_consistency_before_release():
    """태그 / 패키지 버전 / CHANGELOG 섹션이 안 맞으면 릴리즈가 중단돼야 한다."""
    text = _read(".github/workflows/release.yml")

    assert "릴리즈 태그 정합성 확인" in text
    assert 'pathlib.Path("backend/__init__.py")' in text
    assert "__version__" in text
    assert "CHANGELOG.md 에 ## [{version}] 섹션이 없습니다." in text
    assert "태그 버전({version})과 backend.__version__" in text

    guard_step = text.index("- name: 릴리즈 태그 정합성 확인")
    notes_step = text.index("- name: CHANGELOG 섹션 추출")
    release_step = text.index("- name: GitHub Release 생성")
    assert guard_step < notes_step < release_step
    assert '"## [Unreleased]"' not in text


def test_readme_documents_release_order_and_guard():
    """README 에 사람이 따라갈 릴리즈 순서와 자동 가드가 설명돼 있어야 한다."""
    text = _read("README.md")

    assert "## 릴리즈" in text
    assert "backend/__init__.py" in text
    assert "git tag vx.y.z && git push origin vx.y.z" in text
    assert "릴리즈 생성을 중단" in text
