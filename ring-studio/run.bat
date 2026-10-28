@echo off
rem Runs Ring Studio from source on Windows. The first run installs everything into .venv here.
cd /d "%~dp0"
if not exist .venv (
  python -m venv .venv || exit /b 1
  .venv\Scripts\python -m pip install -r requirements.txt || exit /b 1
)
.venv\Scripts\python -m ring_studio
