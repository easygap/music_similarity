#!/usr/bin/env bash
# 로컬 개발 실행 스크립트.
# 최초 실행 시 .venv 를 만들고 의존성을 깐 다음, autoreload 로 uvicorn 을 띄운다.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  echo ">> .venv 가상환경 생성"
  python -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate

echo ">> 의존성 설치"
pip install --upgrade pip
pip install -r requirements.txt

echo ">> http://localhost:8000 에서 개발 서버 시작"
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
