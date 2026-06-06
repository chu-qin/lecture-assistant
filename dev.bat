@echo off
chcp 65001 >nul
title 课堂助手 [开发模式]
cd /d "%~dp0"

set PYTHON=.venv\Scripts\python.exe

cd frontend

echo   [开发模式]
echo   前端 http://localhost:5173 (热更新)
echo   后端 http://localhost:8502 (API)
echo/

start http://localhost:5173

start "API Server" cmd /c "cd /d %~dp0 && %PYTHON% -m uvicorn src.api.server:app --host 0.0.0.0 --port 8502 --log-level info"

npm run dev

pause
