@echo off
title Lecture Assistant
cd /d "%~dp0"
call ".venv\Scripts\activate.bat"
start "" http://localhost:8501
streamlit run run.py
pause
