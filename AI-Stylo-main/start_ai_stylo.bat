@echo off
setlocal

cd /d "%~dp0"
python scripts\bootstrap_and_run.py --mode rpg

endlocal
