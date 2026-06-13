# CampusFlow — One-Command Startup
# Usage: powershell -ExecutionPolicy Bypass -File start.ps1
# This starts: Backend (FastAPI) + Frontend (Next.js) + Evolution API (Docker)

Write-Host ""
Write-Host "  ╔═══════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║       CampusFlow v2.0         ║" -ForegroundColor Cyan
Write-Host "  ║  Your AI Campus Command Center ║" -ForegroundColor Cyan
Write-Host "  ╚═══════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$root = $PSScriptRoot

# ─── Preflight Checks ────────────────────────────────────────────────────────

# Check Python
$pythonAvailable = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonAvailable) {
    Write-Host "  ✗ Python not found. Install Python 3.11+ from https://python.org" -ForegroundColor Red
    exit 1
}

# Check Node
$nodeAvailable = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeAvailable) {
    Write-Host "  ✗ Node.js not found. Install Node 18+ from https://nodejs.org" -ForegroundColor Red
    exit 1
}

# Check backend venv
if (-not (Test-Path "$root\backend\venv\Scripts\python.exe")) {
    Write-Host "  ⚠ Backend venv not found. Creating..." -ForegroundColor DarkYellow
    Push-Location "$root\backend"
    python -m venv venv
    & venv\Scripts\pip install -r requirements.txt --quiet
    & venv\Scripts\python -m playwright install chromium
    Pop-Location
    Write-Host "  ✓ Backend venv created and dependencies installed" -ForegroundColor Green
}

# Check frontend node_modules
if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "  ⚠ Frontend dependencies not installed. Running npm install..." -ForegroundColor DarkYellow
    Push-Location "$root\frontend"
    npm install
    Pop-Location
    Write-Host "  ✓ Frontend dependencies installed" -ForegroundColor Green
}

# Check backend .env
if (-not (Test-Path "$root\backend\.env")) {
    Write-Host "  ⚠ Backend .env not found. Copying from .env.example..." -ForegroundColor DarkYellow
    Copy-Item "$root\backend\.env.example" "$root\backend\.env"
    Write-Host "  ⚠ EDIT backend\.env with your GROQ_API_KEY and VTOP credentials!" -ForegroundColor Yellow
}

Write-Host ""

# ─── Step 1: Start Evolution API (WhatsApp bridge) ───────────────────────────
Write-Host "[1/3] Starting WhatsApp bridge (Evolution API)..." -ForegroundColor Yellow
$dockerAvailable = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerAvailable) {
    Push-Location $root
    docker compose up -d 2>&1 | Out-Null
    Pop-Location
    Write-Host "  ✓ Evolution API running on http://localhost:8080" -ForegroundColor Green
} else {
    Write-Host "  ⚠ Docker not found — WhatsApp bridge skipped" -ForegroundColor DarkYellow
}

# ─── Step 2: Start Backend ────────────────────────────────────────────────────
Write-Host "[2/3] Starting backend (FastAPI)..." -ForegroundColor Yellow
$backendJob = Start-Process -FilePath "$root\backend\venv\Scripts\python.exe" `
    -ArgumentList "run.py" `
    -WorkingDirectory "$root\backend" `
    -WindowStyle Hidden `
    -PassThru
Start-Sleep 3
Write-Host "  ✓ Backend running on http://localhost:8000" -ForegroundColor Green

# ─── Step 3: Start Frontend ──────────────────────────────────────────────────
Write-Host "[3/3] Starting frontend (Next.js)..." -ForegroundColor Yellow
$frontendJob = Start-Process -FilePath "npm" `
    -ArgumentList "run", "dev" `
    -WorkingDirectory "$root\frontend" `
    -WindowStyle Hidden `
    -PassThru
Start-Sleep 4
Write-Host "  ✓ Frontend running on http://localhost:3000" -ForegroundColor Green

Write-Host ""
Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  CampusFlow is ready!" -ForegroundColor Green
Write-Host "  Open: http://localhost:3000" -ForegroundColor White
Write-Host ""
Write-Host "  Services:" -ForegroundColor Gray
Write-Host "    Frontend:  http://localhost:3000" -ForegroundColor Gray
Write-Host "    Backend:   http://localhost:8000" -ForegroundColor Gray
Write-Host "    WhatsApp:  http://localhost:8080 (if Docker running)" -ForegroundColor Gray
Write-Host ""
Write-Host "  Press Ctrl+C to stop all services" -ForegroundColor DarkGray
Write-Host "═══════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Open browser
Start-Process "http://localhost:3000"

# Wait and handle cleanup
try {
    while ($true) { Start-Sleep 1 }
} finally {
    Write-Host "`nShutting down..." -ForegroundColor Yellow
    if ($backendJob -and -not $backendJob.HasExited) {
        Stop-Process -Id $backendJob.Id -Force -ErrorAction SilentlyContinue
    }
    if ($frontendJob -and -not $frontendJob.HasExited) {
        Stop-Process -Id $frontendJob.Id -Force -ErrorAction SilentlyContinue
    }
    # Also kill any orphaned node/python processes on our ports
    Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    if ($dockerAvailable) {
        Push-Location $root
        docker compose down 2>&1 | Out-Null
        Pop-Location
    }
    Write-Host "All services stopped." -ForegroundColor Green
}
