# IntelliDocs AI - Windows Automated Setup Script
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " IntelliDocs AI - Automated Setup         " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Check Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
    exit 1
}
$pyVer = python --version
Write-Host "[OK] Detected: $pyVer" -ForegroundColor Green

# 2. Check Node.js
$nodeCmd = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Host "[ERROR] Node.js is not installed or not in PATH." -ForegroundColor Red
    exit 1
}
$nodeVer = node --version
Write-Host "[OK] Detected Node.js: $nodeVer" -ForegroundColor Green

# 3. Create Virtual Environment
if (-not (Test-Path ".venv")) {
    Write-Host "[1/5] Creating Python virtual environment in .venv..." -ForegroundColor Yellow
    python -m venv .venv
} else {
    Write-Host "[1/5] Virtual environment .venv already exists." -ForegroundColor Green
}

# 4. Install Backend Dependencies
Write-Host "[2/5] Installing Python dependencies..." -ForegroundColor Yellow
& ".\.venv\Scripts\pip.exe" install --upgrade pip
& ".\.venv\Scripts\pip.exe" install -r backend/requirements.txt

# 5. Download Models & Datasets
Write-Host "[3/5] Downloading NLP corpora and models..." -ForegroundColor Yellow
& ".\.venv\Scripts\python.exe" scripts/download_models.py

# 6. Setup .env
if (-not (Test-Path ".env")) {
    Write-Host "[4/5] Creating .env from template..." -ForegroundColor Yellow
    Copy-Item .env.example .env
} else {
    Write-Host "[4/5] .env file exists." -ForegroundColor Green
}

# 7. Install Frontend Dependencies
Write-Host "[5/5] Installing frontend npm packages..." -ForegroundColor Yellow
Push-Location frontend
npm install
Pop-Location

Write-Host "==========================================" -ForegroundColor Green
Write-Host " IntelliDocs AI Setup Complete!           " -ForegroundColor Green
Write-Host " Start backend: .\scripts\run_backend.ps1  " -ForegroundColor Cyan
Write-Host " Start frontend: .\scripts\run_frontend.ps1 " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Green
