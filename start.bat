@echo off
chcp 65001 >nul
title 课堂助手 - Lecture Assistant
cd /d "%~dp0"

:: Check .env
if not exist ".env" (
    echo/
    echo   [提示] 未找到 .env 文件，API Key 尚未配置
    echo   请先运行 setup_env.bat 配置 API Key
    echo   或手动创建 .env 文件，写入: DEEPSEEK_API_KEY=sk-你的key
    echo/
    echo   语音转写和课件解析不需要 API Key，继续启动...
    echo/
    timeout /t 3 >nul
)

call ".venv\Scripts\activate.bat"

:: Build frontend (always rebuild to pick up latest changes)
echo   [构建] 正在构建前端...
cd frontend
call npm run build
cd ..

echo   [启动] 后端服务 + 前端页面...
echo/
echo   ========================================
echo    打开浏览器访问 http://localhost:8502
echo   ========================================
echo/
start http://localhost:8502

python -m uvicorn src.api.server:app --host 0.0.0.0 --port 8502 --log-level warning

pause
