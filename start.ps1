# MIF Glue Job Agent — Startup Script (Windows)
# Run this from the poc/ directory

# Ensure Node.js is on PATH (in case it was installed after the current session started)
$env:PATH = "C:\Program Files\nodejs;$env:APPDATA\npm;" + $env:PATH

# 1. Start Backend
Write-Host "Starting FastAPI backend..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\backend'; py -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

# 2. Start Frontend
Write-Host "Starting Next.js frontend..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$PSScriptRoot\frontend'; npm run dev"

Write-Host ""
Write-Host "✅ Both services starting!" -ForegroundColor Green
Write-Host "   Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "   Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "   API docs: http://localhost:8000/docs" -ForegroundColor White
