@echo off
title Controle Financeiro
echo Iniciando sistema de controle financeiro...
echo Acesse: http://localhost:8501
echo.
"%~dp0venv\Scripts\python.exe" -m streamlit run "%~dp0app.py" --server.port 8501 --browser.serverAddress localhost
pause
