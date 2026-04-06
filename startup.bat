@echo off
title Ultra Agent System — Startup
echo ============================================================
echo   Ultra Agent System — Startup
echo ============================================================
echo.

cd /d "%~dp0"

:: Check Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3 and add to PATH.
    pause
    exit /b 1
)

:: Step 1: Initialize database
echo [1/4] Initializing database...
python scripts\db-init.py
if %errorlevel% neq 0 (
    echo [ERROR] Database initialization failed.
    pause
    exit /b 1
)
echo.

:: Step 2: Run health check
echo [2/4] Running health check...
python scripts\health-check.py
echo.

:: Step 3: Start Dashboard server (background)
echo [3/4] Starting Dashboard server on http://localhost:53800 ...
start "Ultra Agent — Dashboard Server" /min python scripts\dashboard-server.py --port 53800
timeout /t 2 /nobreak >nul
echo       Dashboard server started (minimized).
echo.

:: Step 4: Start Cron Manager (background)
echo [4/4] Starting Cron Manager...
start "Ultra Agent — Cron Manager" /min python scripts\cron-manager.py
timeout /t 1 /nobreak >nul
echo       Cron Manager started (minimized).
echo.

echo ============================================================
echo   Ultra Agent System is RUNNING
echo.
echo   Dashboard:    http://localhost:53800
echo   Database:     %cd%\ultra.db
echo   Logs:         %cd%\logs\
echo.
echo   To stop: close the "Dashboard Server" and "Cron Manager"
echo            windows, or run shutdown.bat
echo ============================================================
echo.
pause
