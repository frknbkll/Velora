@echo off
setlocal
cd /d "%~dp0"
python -I "%~dp0update-runtime.py"
if errorlevel 1 pause
endlocal
