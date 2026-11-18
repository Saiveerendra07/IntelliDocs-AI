# Start FastAPI Backend Server
Write-Host "Starting IntelliDocs AI Backend on http://localhost:8000..." -ForegroundColor Cyan

if (Test-Path ".venv\Scripts\uvicorn.exe") {
    $env:PYTHONPATH = "D:\nlpProject"
    & ".\.venv\Scripts\uvicorn.exe" backend.app.main:app --host 0.0.0.0 --port 8000 --reload
} else {
    Write-Host "[ERROR] Virtual environment not found. Run .\scripts\setup.ps1 first." -ForegroundColor Red
}
