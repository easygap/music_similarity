# Windows PowerShell 용 로컬 개발 스크립트.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv")) {
    Write-Host ">> .venv 가상환경 생성"
    python -m venv .venv
}

# venv 활성화
$activate = Join-Path $Root ".venv\Scripts\Activate.ps1"
. $activate

Write-Host ">> 의존성 설치"
pip install --upgrade pip
pip install -r requirements.txt

Write-Host ">> http://localhost:8000 에서 개발 서버 시작"
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
