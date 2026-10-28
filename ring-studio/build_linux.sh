#!/bin/sh
# Builds the "Ring Studio" app in the dist folder. Run it from this folder on Linux.
# Everything is installed into .venv here, so it works where pip may not touch the system Python
# (Arch, Debian 12 and newer, Ubuntu 23.04 and newer).
set -e
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install --upgrade -r requirements.txt "flet[cli]==1.0.5" pyinstaller
.venv/bin/flet pack run_ring_studio.py --name "Ring Studio" --icon assets/icon.png \
  --hidden-import serial.tools.list_ports keyring.backends.SecretService keyring.backends.kwallet -y
echo
echo "Done: dist/Ring Studio"
