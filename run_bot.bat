@echo off
title MediaLink Telegram Bot
cd /d "%~dp0"

echo ====================================================
echo Starting MediaLink Telegram Bot...
echo ====================================================

python bot.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred while running the bot.
    echo Please make sure your TELEGRAM_BOT_TOKEN is set in .env.
    echo.
    pause
)
