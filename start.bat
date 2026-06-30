@echo off
chcp 65001 >nul
title 课堂助手 - Lecture Assistant
cd /d "%~dp0"

:: ==========================================
:: Auto-detect and init config
:: ==========================================

:: 1. config.yaml -- auto-create from example if missing
if not exist "config.yaml" (
    if not exist "config.example.yaml" goto :no_template
    echo   [Init] config.yaml not found, creating from config.example.yaml...
    copy config.example.yaml config.yaml >nul 2>&1
    echo   [OK] config.yaml created (default settings, edit if needed)
)
goto :check_env

:no_template
echo   [ERROR] config.example.yaml not found, project files may be corrupted
pause
exit /b 1

:check_env
:: 2. .env -- create placeholder if missing
if exist ".env" goto :check_python

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
echo   [Tip] Voice transcription and courseware parsing work without API Key.
echo   For LLM features, edit .env and add your key.
echo.
timeout /t 2 >nul

:check_python
:: 3. Check Python venv
set PYTHON=.venv\Scripts\python.exe
if exist "%PYTHON%" goto :check_node
echo   [ERROR] Virtual env not found, please run setup_env.bat first
pause
exit /b 1

:check_node
:: 4. Check Node.js for frontend build
where node >nul 2>&1
if %errorlevel% equ 0 goto :build_frontend
echo   [WARNING] Node.js not found, frontend cannot be built
echo   Install Node.js from https://nodejs.org or use Streamlit mode:
echo     %PYTHON% -m streamlit run run.py
pause
exit /b 1

:build_frontend
:: 5. Build frontend
cd frontend
if not exist "node_modules\" (
    echo   [Init] Installing frontend dependencies...
    call npm install
)
echo   [Build] Building frontend...
call npm run build
cd ..

:: 6. Start
echo   [Start] Backend + Frontend...
echo   ========================================
echo     Open http://localhost:8502
echo   ========================================
start http://localhost:8502

%PYTHON% -m uvicorn src.api.server:app --host 0.0.0.0 --port 8502 --log-level warning

pause
