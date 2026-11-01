@echo off
setlocal
cd /d "%~dp0"
set "DEBUG=0"
if exist "%~dp0.runtime\python-3.15.2\python.exe" (
  "%~dp0.runtime\python-3.15.2\python.exe" -I "%~dp0start-velora.py"
) else (
  python -I "%~dp0start-velora.py"
)
if errorlevel 1 pause
endlocal
