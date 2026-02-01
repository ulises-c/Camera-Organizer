#!/usr/bin/env python3
"""
TIFF Converter GUI - Simplified launcher that imports from tiff-to-heic.

Note: This is a wrapper that launches the full GUI from the tiff-to-heic module.
"""
import sys
from pathlib import Path

# Add tiff-to-heic directory to path
tiff_heic_path = Path(__file__).parent.parent.parent / "tiff-to-heic"
sys.path.insert(0, str(tiff_heic_path))

# Import and run the main GUI
from gui import main

if __name__ == "__main__":
    main()
