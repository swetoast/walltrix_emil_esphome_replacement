@echo off
rem Builds "Ring Studio.exe" in the dist folder. Run it from this folder on Windows.
if not exist .venv python -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python -m pip install --upgrade -r requirements.txt "flet[cli]==1.0.5" pyinstaller pillow
if errorlevel 1 exit /b 1
.venv\Scripts\flet pack run_ring_studio.py --name "Ring Studio" --icon assets\icon.ico --add-data "ring_studio\examples;ring_studio\examples" --hidden-import serial.tools.list_ports flet_code_editor keyring.backends.Windows --product-name "Ring Studio" --file-description "Ring Studio" -y
if errorlevel 1 exit /b 1
echo.
echo Done: dist\Ring Studio.exe
