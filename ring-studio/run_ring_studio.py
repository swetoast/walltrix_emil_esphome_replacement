"""Entry point for the packed Windows app. `python -m ring_studio` does the same from source."""

import flet as ft

from ring_studio.ui import main

if __name__ == "__main__":
    ft.run(main)
