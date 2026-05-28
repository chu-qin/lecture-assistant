﻿@echo off
chcp 65001 >nul
title 课堂助手
cd /d "%~dp0"

:: Check if .env exists
if not exist ".env" goto :no_env
goto :launch

:no_env
echo/
echo   [提示] 未找到 .env 文件，API Key 尚未配置
echo   请先运行 setup_env.bat 配置 API Key
echo   或手动创建 .env 文件，写入: DEEPSEEK_API_KEY=sk-你的key
echo/
echo   语音转写和课件解析不需要 API Key，继续启动...
echo/
timeout /t 3 >nul

:launch
call ".venv\Scripts\activate.bat"
streamlit run run.py
pause
