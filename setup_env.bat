@echo off
title Lecture Assistant Setup
echo ==========================================
echo   Lecture Assistant - Setup
echo ==========================================
echo.

:: ---- 1. Check Python ----
echo [1/5] Checking Python...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Python found
    set PYCMD=python
    goto :check_done
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Python found (py launcher)
    set PYCMD=py
    goto :check_done
)

python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Python found (python3)
    set PYCMD=python3
    goto :check_done
)

echo [ERROR] Python not found.
echo Please install Python 3.10+ from https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation.
pause
exit /b 1

:check_done

:: ---- 2. Create venv ----
echo.
echo [2/5] Creating virtual environment...
if exist ".venv\Scripts\python.exe" (
    echo [OK] .venv already exists, skipping
) else (
    %PYCMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
)

:: ---- 3. Activate and upgrade pip ----
echo.
echo [3/5] Installing dependencies...
call ".venv\Scripts\activate.bat" 2>nul
if %errorlevel% neq 0 (
    echo [WARN] Could not activate venv, continuing anyway...
)

python -m pip install --upgrade pip --quiet 2>nul
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Failed to install dependencies.
    echo Check your internet connection and try again.
    pause
    exit /b 1
)
echo [OK] Dependencies installed

:: ---- 4. ffmpeg ----
echo.
echo [4/5] Setting up ffmpeg...
call :SetupFFmpeg
goto :ffmpeg_done

:SetupFFmpeg
if exist "tools\ffmpeg\bin\ffmpeg.exe" (
    echo [OK] ffmpeg already exists
    goto :eof
)

echo Downloading ffmpeg portable (this may take a minute)...
if not exist "tools\ffmpeg" mkdir "tools\ffmpeg"

set "FFZIP=%TEMP%\ffmpeg_temp.zip"
set "FFDIR=%TEMP%\ffmpeg_extract"

powershell -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' -OutFile '%FFZIP%' -UseBasicParsing" 2>nul

if not exist "%FFZIP%" (
    echo [WARN] Could not download ffmpeg ^(optional, can skip^).
    goto :eof
)

echo Extracting ffmpeg...
powershell -Command "Expand-Archive -Path '%FFZIP%' -DestinationPath '%FFDIR%' -Force" 2>nul

if exist "%FFDIR%" (
    for /d %%d in ("%FFDIR%\*") do (
        if exist "%%d\bin\ffmpeg.exe" xcopy "%%d\*" "tools\ffmpeg\" /E /I /Q /Y >nul 2>&1
    )
    del /q "%FFZIP%" 2>nul
    rmdir /s /q "%FFDIR%" 2>nul
)

if exist "tools\ffmpeg\bin\ffmpeg.exe" (
    echo [OK] ffmpeg installed
) else (
    echo [WARN] Could not auto-install ffmpeg ^(optional, can skip^).
)
goto :eof

:ffmpeg_done

:: ---- 5. Config and directories ----
echo.
echo [5/5] Creating config and directories...

if not exist "config.yaml" (
    copy config.example.yaml config.yaml >nul 2>&1
    echo [OK] Created config.yaml
    echo.
    echo ****************************************************
    echo IMPORTANT: Edit config.yaml and set your DeepSeek API key!
    echo Or run: set DEEPSEEK_API_KEY=sk-your-key
    echo ****************************************************
) else (
    echo [OK] config.yaml already exists
)

mkdir "data\model_cache\modelscope" 2>nul
mkdir "data\model_cache\huggingface" 2>nul
mkdir "data\audio" 2>nul
mkdir "data\courseware" 2>nul
mkdir "data\transcripts" 2>nul
mkdir "data\parsed_docs" 2>nul
mkdir "data\merged" 2>nul
mkdir "data\review_materials" 2>nul
mkdir "data\chroma_db" 2>nul
echo [OK] Directories created

:: ---- Done ----
echo.
echo ==========================================
echo   Setup complete!
echo.
echo   To start:
echo     1. .venv\Scripts\activate
echo     2. streamlit run run.py
echo.
echo   To uninstall: delete this folder
echo ==========================================
pause
