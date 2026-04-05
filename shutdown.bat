@echo off
title Ultra Agent System — Shutdown
echo ============================================================
echo   Ultra Agent System — Shutdown
echo ============================================================
echo.

:: Kill the Release Server and Cron Manager by window title
taskkill /fi "WINDOWTITLE eq Ultra Agent*" /f >nul 2>&1

:: Also kill by script name in case titles don't match
for /f "tokens=2" %%i in ('wmic process where "commandline like '%%release-server.py%%'" get processid /value 2^>nul ^| findstr ProcessId') do (
    taskkill /pid %%i /f >nul 2>&1
)
for /f "tokens=2" %%i in ('wmic process where "commandline like '%%cron-manager.py%%'" get processid /value 2^>nul ^| findstr ProcessId') do (
    taskkill /pid %%i /f >nul 2>&1
)

echo   All Ultra Agent processes stopped.
echo ============================================================
echo.
pause
