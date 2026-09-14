@echo off
title Media Downloader & Converter
cd /d "%~dp0"

echo ====================================================
echo Starting Media Downloader...
echo ====================================================

python app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred. Press any key to exit...
    pause >nul
)
