@echo off
chcp 65001 >nul
title 课堂助手
cd /d "%~dp0"

:: ==========================================
:: Auto-detect and init config
:: ==========================================

:: 1. config.yaml -- auto-create from example if missing
if exist "config.yaml" goto :check_env
if not exist "config.example.yaml" goto :no_template

echo   [Init] config.yaml not found, creating from config.example.yaml...
copy config.example.yaml config.yaml >nul 2>&1
echo   [OK] config.yaml created (default settings, you can edit it later)
echo.
goto :check_env

:no_template
echo   [ERROR] config.example.yaml not found, project files may be corrupted
pause
exit /b 1

:check_env
:: 2. .env -- create placeholder if missing
if exist ".env" goto :check_key

echo   [Init] .env not found, creating placeholder...
(
    echo # Lecture Assistant - API Key Config
    echo # This file is gitignored, will not be committed
    echo.
    echo # Configure at least one API Key before using LLM features:
    echo # DEEPSEEK_API_KEY=sk-your-key
    echo # OPENAI_API_KEY=sk-your-key
) > .env
echo   [OK] .env created (API Key not configured, LLM features unavailable)
echo.
echo   [Tip] Voice transcription and courseware parsing work without API Key.
echo   For AI review generation / Q&A, edit .env and add:
echo     DEEPSEEK_API_KEY=sk-your-key
echo   Get your key at: https://platform.deepseek.com/api_keys
echo.
timeout /t 3 >nul
goto :launch

:check_key
:: Quick check for DEEPSEEK_API_KEY in .env
findstr /b "DEEPSEEK_API_KEY=" .env >nul 2>&1
if not errorlevel 1 goto :launch

echo.
echo   [Tip] .env exists but DEEPSEEK_API_KEY is not set.
echo   LLM features (AI review generation / Q&A) will be unavailable.
echo   To enable, edit .env and add: DEEPSEEK_API_KEY=sk-your-key
echo.
timeout /t 3 >nul

:launch
:: 3. Start
echo   Starting Lecture Assistant...
call ".venv\Scripts\activate.bat" 2>nul
streamlit run run.py
pause
