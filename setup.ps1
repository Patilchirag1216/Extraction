# Create the Python 3.12 virtual environment and install dependencies.
# Usage (from the project folder):
#     powershell -ExecutionPolicy Bypass -File .\setup.ps1

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "Checking for Python 3.12..." -ForegroundColor Cyan
$py312 = $null
try { & py -3.12 --version *> $null; if ($?) { $py312 = "py -3.12" } } catch {}

if (-not $py312) {
    $candidate = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    if (Test-Path $candidate) { $py312 = $candidate }
}

if (-not $py312) {
    Write-Host "Python 3.12 was not found. Install it with:" -ForegroundColor Yellow
    Write-Host "    winget install --id Python.Python.3.12 -e"
    exit 1
}

Write-Host "Creating virtual environment (.venv)..." -ForegroundColor Cyan
& $py312 -m venv .venv

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
Write-Host "Upgrading pip..." -ForegroundColor Cyan
& $venvPy -m pip install --upgrade pip setuptools wheel

Write-Host "Installing requirements (this downloads several hundred MB)..." -ForegroundColor Cyan
& $venvPy -m pip install -r requirements.txt

Write-Host ""
Write-Host "Setup complete. Start the app with:" -ForegroundColor Green
Write-Host "    run_app.bat"
Write-Host "or"
Write-Host "    .\.venv\Scripts\python -m streamlit run app.py"
