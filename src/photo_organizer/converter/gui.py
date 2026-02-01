#!/usr/bin/env python3
"""
TIFF Converter GUI - Simplified launcher that imports from photo_organizer.converter.core.

Note: This is a wrapper that launches the full GUI from the converter module.
"""
import sys
from pathlib import Path

# Import and run the main GUI
# TODO: This needs to be updated to use the new ttkbootstrap GUI when migrated
from photo_organizer.converter.core import create_lzw_copy, create_heic_copy

def main():
    print("TIFF Converter GUI")
    print("Note: Full GUI implementation pending migration from tiff-to-heic")
    print("Current functionality: Core conversion functions available")
    print("  - create_lzw_copy()")
    print("  - create_heic_copy()")

if __name__ == "__main__":
    main()
