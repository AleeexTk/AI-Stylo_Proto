@echo off
echo Starting AI-Stylo API Gateway v1.0...
cd /d "%~dp0"
set PYTHONPATH=%PYTHONPATH%;%cd%
python apps/api_gateway/main.py
pause
