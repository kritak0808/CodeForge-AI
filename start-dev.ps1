# CodeForge AI — Development Launcher
# Run: powershell -ExecutionPolicy Bypass -File start-dev.ps1

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║          CodeForge AI — Dev Launcher             ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$ROOT = $PSScriptRoot

# ── Backend ──────────────────────────────────────────────────────────────────
Write-Host "[1/2] Starting FastAPI backend on http://localhost:8000 ..." -ForegroundColor Yellow

$backendPath = Join-Path $ROOT "apps\api"
Start-Process -NoNewWindow -FilePath "cmd.exe" -ArgumentList "/c cd `"$backendPath`" && python run.py" -PassThru | Out-Null

Start-Sleep -Seconds 3

# ── Frontend ─────────────────────────────────────────────────────────────────
Write-Host "[2/2] Starting Next.js frontend on http://localhost:3000 ..." -ForegroundColor Yellow

$frontendPath = Join-Path $ROOT "apps\web"
Start-Process -NoNewWindow -FilePath "cmd.exe" -ArgumentList "/c cd `"$frontendPath`" && npm run dev" -PassThru | Out-Null

Write-Host ""
Write-Host "✓ Both servers are starting!" -ForegroundColor Green
Write-Host ""
Write-Host "  Frontend  →  http://localhost:3000" -ForegroundColor Cyan
Write-Host "  Backend   →  http://localhost:8000" -ForegroundColor Cyan
Write-Host "  API Docs  →  http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Login: admin / admin123" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop..." -ForegroundColor Gray
