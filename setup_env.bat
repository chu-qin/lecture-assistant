@echo off
chcp 65001 >nul
title 课堂助手 - 环境初始化
echo ==========================================
echo   课堂助手 - 环境初始化
echo ==========================================
echo/

:: ---- 1. Check Python ----
echo [1/6] 检测 Python 环境...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] 已找到 Python
    set PYCMD=python
    goto :check_done
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] 已找到 Python ^(py launcher^)
    set PYCMD=py
    goto :check_done
)

python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] 已找到 Python ^(python3^)
    set PYCMD=python3
    goto :check_done
)

echo [错误] 未找到 Python
echo 请从 https://www.python.org/downloads/ 安装 Python 3.10+
echo 安装时请勾选 "Add Python to PATH"
pause
exit /b 1

:check_done

:: ---- 2. Create venv ----
echo/
echo [2/6] 创建虚拟环境...
if exist ".venv\Scripts\python.exe" (
    echo [OK] .venv 已存在，跳过
) else (
    %PYCMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo [OK] 虚拟环境创建成功
)

:: ---- 3. Activate and upgrade pip ----
echo/
echo [3/6] 安装依赖包...
call ".venv\Scripts\activate.bat" 2>nul
if %errorlevel% neq 0 (
    echo [警告] 无法激活虚拟环境，继续尝试安装...
)

python -m pip install --upgrade pip --quiet 2>nul
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo/
    echo [错误] 依赖安装失败，请检查网络连接后重试
    pause
    exit /b 1
)
echo [OK] 依赖安装完成

:: ---- 4. ffmpeg ----
echo/
echo [4/6] 配置 ffmpeg...
call :SetupFFmpeg
goto :ffmpeg_done

:SetupFFmpeg
if exist "tools\ffmpeg\bin\ffmpeg.exe" (
    echo [OK] ffmpeg 已存在
    goto :eof
)

echo 正在下载 ffmpeg 绿色版 ^(可能需要几分钟^)...
if not exist "tools\ffmpeg" mkdir "tools\ffmpeg"

set "FFZIP=%TEMP%\ffmpeg_temp.zip"
set "FFDIR=%TEMP%\ffmpeg_extract"

powershell -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' -OutFile '%FFZIP%' -UseBasicParsing" 2>nul

if not exist "%FFZIP%" (
    echo [警告] 无法下载 ffmpeg ^(可选组件，可跳过^)
    goto :eof
)

echo 正在解压 ffmpeg...
powershell -Command "Expand-Archive -Path '%FFZIP%' -DestinationPath '%FFDIR%' -Force" 2>nul

if exist "%FFDIR%" (
    for /d %%d in ("%FFDIR%\*") do (
        if exist "%%d\bin\ffmpeg.exe" xcopy "%%d\*" "tools\ffmpeg\" /E /I /Q /Y >nul 2>&1
    )
    del /q "%FFZIP%" 2>nul
    rmdir /s /q "%FFDIR%" 2>nul
)

if exist "tools\ffmpeg\bin\ffmpeg.exe" (
    echo [OK] ffmpeg 安装完成
) else (
    echo [警告] 自动安装 ffmpeg 失败 ^(可选组件，可跳过^)
)
goto :eof

:ffmpeg_done

:: ---- 5. Config and directories ----
echo/
echo [5/6] 创建配置文件和目录...

if not exist "config.yaml" (
    copy config.example.yaml config.yaml >nul 2>&1
    echo [OK] 已从 config.example.yaml 创建 config.yaml
) else (
    echo [OK] config.yaml 已存在
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
echo [OK] 数据目录创建完成

:: ---- 6. Interactive API key setup ----
echo/
echo [6/6] 配置 API Key...
echo/
echo   请选择你要使用的大模型服务商：
echo     [1] DeepSeek ^(推荐，新用户免费赠送额度^)
echo     [2] OpenAI
echo     [3] 两个都要
echo     [4] 跳过 — 我以后自己配置
echo/
set /p PROVIDER_CHOICE="   请输入选项 (1-4): "

set "DS_KEY="
set "OAI_KEY="

if "%PROVIDER_CHOICE%"=="1" goto :ask_deepseek
if "%PROVIDER_CHOICE%"=="2" goto :ask_openai
if "%PROVIDER_CHOICE%"=="3" goto :ask_both
goto :write_env

:ask_deepseek
echo/
echo   DeepSeek API Key 获取地址: https://platform.deepseek.com/api_keys
set /p DS_KEY="   请粘贴你的 DeepSeek API Key: "
goto :write_env

:ask_openai
echo/
echo   OpenAI API Key 获取地址: https://platform.openai.com/api-keys
set /p OAI_KEY="   请粘贴你的 OpenAI API Key: "
goto :write_env

:ask_both
echo/
echo   DeepSeek API Key 获取地址: https://platform.deepseek.com/api_keys
set /p DS_KEY="   请粘贴你的 DeepSeek API Key: "
echo/
echo   OpenAI API Key 获取地址: https://platform.openai.com/api-keys
set /p OAI_KEY="   请粘贴你的 OpenAI API Key: "
goto :write_env

:write_env
echo/
echo   正在创建 .env 文件...

if not exist ".env" (
    echo # 课堂助手 - API Key 配置 > .env
    echo # 此文件已被 gitignore 排除，不会提交到 GitHub >> .env
    echo. >> .env
)

if "%DS_KEY%"=="" goto :check_oai

:: Write DeepSeek key ^(skip existing line first^)
type ".env" 2>nul | findstr /v /c:"DEEPSEEK_API_KEY=" > .env.tmp
echo DEEPSEEK_API_KEY=%DS_KEY% >> .env.tmp
move .env.tmp .env >nul 2>&1
echo [OK] DeepSeek API Key 已保存

:check_oai
if "%OAI_KEY%"=="" goto :check_skip

:: Write OpenAI key ^(skip existing line first^)
type ".env" 2>nul | findstr /v /c:"OPENAI_API_KEY=" > .env.tmp
echo OPENAI_API_KEY=%OAI_KEY% >> .env.tmp
move .env.tmp .env >nul 2>&1
echo [OK] OpenAI API Key 已保存

:check_skip
if not "%PROVIDER_CHOICE%"=="4" goto :done

echo [跳过] 你可以稍后手动配置 API Key：
echo   在项目根目录新建 .env 文件，写入：
echo   DEEPSEEK_API_KEY=sk-你的key
echo/
echo   或者设置系统环境变量：
echo   set DEEPSEEK_API_KEY=sk-你的key

:done
:: ---- Done ----
echo/
echo ==========================================
echo   Setup done!
echo/
echo   To start:
echo     1. double-click start.bat
echo     2. or run in terminal:
echo        .venv\Scripts\activate
echo        streamlit run run.py
echo/
echo   To uninstall: delete this folder
echo ==========================================
pause
goto :eof
