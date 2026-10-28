#!/bin/sh
# Builds the "Ring Studio" app in the dist folder. Run it from this folder on Linux.
set -e
python3 -m pip install --upgrade -r requirements.txt "flet[cli]==1.0.5" pyinstaller
flet pack run_ring_studio.py --name "Ring Studio" --icon assets/icon.png --hidden-import serial.tools.list_ports keyring.backends.SecretService keyring.backends.kwallet -y
echo
echo "Done: dist/Ring Studio"
