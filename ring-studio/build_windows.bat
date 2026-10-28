@echo off
rem Builds "Ring Studio.exe" in the dist folder. Run it from this folder on Windows.
python -m pip install --upgrade -r requirements.txt "flet[cli]==1.0.5" pyinstaller pillow
if errorlevel 1 exit /b 1
flet pack run_ring_studio.py --name "Ring Studio" --icon assets\icon.ico --hidden-import serial.tools.list_ports --product-name "Ring Studio" --file-description "Ring Studio" -y
if errorlevel 1 exit /b 1
echo.
echo Done: dist\Ring Studio.exe
