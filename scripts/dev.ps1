# Local dev runner for Windows PowerShell.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv")) {
    Write-Host ">> Creating virtual environment in .venv"
    python -m venv .venv
}

# Activate the venv.
$activate = Join-Path $Root ".venv\Scripts\Activate.ps1"
. $activate

Write-Host ">> Installing dependencies"
pip install --upgrade pip
pip install -r requirements.txt

Write-Host ">> Starting dev server on http://localhost:8000"
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
