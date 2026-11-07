@echo off
title AI Video Creator
cd /d "%~dp0"

echo ========================================================
echo         Launching AI Video Creator WebApp...
echo ========================================================

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found!
    echo Please run setup.ps1 first to install dependencies.
    echo.
    pause
    exit /b 1
)

:: Launch the application with virtual environment python
".venv\Scripts\python.exe" app.py %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Application exited with code %ERRORLEVEL%.
    pause
)
