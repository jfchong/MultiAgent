@echo off
cd /d "%~dp0"
if "%~1"=="" (
    python scripts\ultra.py --interactive
) else (
    python scripts\ultra.py %*
)
