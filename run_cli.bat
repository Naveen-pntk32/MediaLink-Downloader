@echo off
title MediaLink Downloader CLI
cd /d "%~dp0"

python app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred. Press any key to exit...
    pause >nul
)
