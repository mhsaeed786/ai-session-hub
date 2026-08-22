@echo off
setlocal
cd /d "%~dp0"

echo === AI Session Hub Setup ===
echo.

REM 1. Create virtual environment
if not exist "venv" (
    echo [1/3] Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create venv. Make sure Python is on PATH.
        pause
        exit /b 1
    )
) else (
    echo [1/3] Virtual environment already exists.
)

REM 2. Install dependencies
echo [2/3] Installing dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

REM 3. Optional daily sync task
echo [3/3] Registering daily sync with Windows Task Scheduler...
set TASK_NAME=AI_Session_Hub_Daily_Sync
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1
schtasks /Create /TN "%TASK_NAME%" /TR "cmd /c cd /d \"%~dp0\" && venv\Scripts\python.exe run.py --sync" /SC DAILY /ST 02:00 /F
if errorlevel 1 (
    echo WARNING: Could not register Task Scheduler job. Run as Administrator if desired.
) else (
    echo Task Scheduler job created: daily sync at 2:00 AM.
)

echo.
echo === Setup Complete ===
echo.
echo To sync now:     venv\Scripts\python.exe run.py --sync
echo To start server:  venv\Scripts\python.exe run.py --serve
echo Then open:        http://127.0.0.1:5100
echo.
pause
