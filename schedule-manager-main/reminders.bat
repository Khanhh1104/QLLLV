@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please run: py -3.12 setup_project.py
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m app.reminders --loop
pause
