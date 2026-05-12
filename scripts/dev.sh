#!/usr/bin/env bash
# Local dev runner. Creates a virtual env on first run, then launches uvicorn
# with autoreload so the frontend / backend reload on save.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  echo ">> Creating virtual environment in .venv"
  python -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate

echo ">> Installing dependencies"
pip install --upgrade pip
pip install -r requirements.txt

echo ">> Starting dev server on http://localhost:8000"
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
