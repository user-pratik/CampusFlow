@echo off
title CampusFlow Setup
echo.
echo   ╔═══════════════════════════════╗
echo   ║    CampusFlow First-Time      ║
echo   ║         Setup                 ║
echo   ╚═══════════════════════════════╝
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [ERROR] Python not found. Install Python 3.11+ from https://python.org
    echo   Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

:: Check Node
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [ERROR] Node.js not found. Install Node 18+ from https://nodejs.org
    pause
    exit /b 1
)

echo [1/5] Setting up backend virtual environment...
cd /d "%~dp0backend"
if not exist "venv" (
    python -m venv venv
    echo   Created venv
) else (
    echo   venv already exists
)

echo [2/5] Installing backend dependencies...
call venv\Scripts\activate
pip install -r requirements.txt --quiet
echo   Done

echo [3/5] Installing Playwright browser...
python -m playwright install chromium
echo   Done

echo [4/5] Setting up frontend...
cd /d "%~dp0frontend"
call npm install
echo   Done

echo [5/5] Creating config files...
cd /d "%~dp0backend"
if not exist ".env" (
    copy .env.example .env >nul
    echo   Created backend\.env — EDIT THIS FILE with your credentials!
) else (
    echo   backend\.env already exists
)

cd /d "%~dp0frontend"
if not exist ".env.local" (
    copy .env.example .env.local >nul
    echo   Created frontend\.env.local
) else (
    echo   frontend\.env.local already exists
)

echo.
echo   ═══════════════════════════════════════════
echo   Setup complete!
echo.
echo   NEXT STEPS:
echo   1. Edit backend\.env with your credentials:
echo      - GROQ_API_KEY (get from https://console.groq.com/keys)
echo      - VTOP_USERNAME (your registration number)
echo      - VTOP_PASSWORD (your VTOP password)
echo.
echo   2. Run start.bat to launch CampusFlow
echo   ═══════════════════════════════════════════
echo.
pause
