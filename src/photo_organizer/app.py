"""Application entry point (PySide6).

`camera-organizer` console script → this. Replaces the old tkinter launcher.
"""
from __future__ import annotations

import logging
import sys


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(message)s")
    from photo_organizer.gui.main_window import run
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
