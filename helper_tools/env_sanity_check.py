#!/usr/bin/env python3
"""
Comprehensive Environment Diagnostic Suite for Photo Organizer
Production-grade verification with safe imports and detailed reporting.
"""
import sys
import os
import platform
import importlib
import importlib.util
from pathlib import Path

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

def safe_find_spec(name):
    """Safely check for module spec without raising exceptions."""
    try:
        base_pkg = name.split('.')[0]
        spec = importlib.util.find_spec(base_pkg)
        if spec is None:
            return None
        if '.' in name:
            return importlib.util.find_spec(name)
        return spec
    except (ModuleNotFoundError, ValueError, AttributeError):
        return None
    except Exception:
        return None

def get_version(module_name):
    """Attempt to retrieve version from module."""
    try:
        mod = importlib.import_module(module_name.split('.')[0])
        for attr in ['__version__', 'VERSION', 'version']:
            if hasattr(mod, attr):
                ver = getattr(mod, attr)
                return str(ver) if ver else "unknown"
        
        try:
            from importlib.metadata import version
            return version(module_name.split('.')[0])
        except Exception:
            pass
            
        return "unknown"
    except Exception:
        return "unknown"

def check_module(name, attribute=None):
    """
    Safely check if a module exists and optionally verify an attribute.
    Returns (success: bool, message: str)
    """
    spec = safe_find_spec(name)
    if spec is None:
        return False, "Not installed"
    
    try:
        module = importlib.import_module(name)
        if attribute and not hasattr(module, attribute):
            return False, f"Missing attribute '{attribute}'"
        
        version = get_version(name)
        return True, f"v{version}"
    except Exception as e:
        return False, f"Import error: {str(e)[:50]}"

def check_tkinter():
    """Deep check of tkinter and Tcl/Tk runtime."""
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        tk_ver = root.tk.call('info', 'patchlevel')
        root.destroy()
        return True, f"Tcl/Tk v{tk_ver}"
    except Exception as e:
        return False, str(e)[:80]

def check_scrolledtext():
    """Check all possible locations for ScrolledText widget."""
    locations = [
        ("ttkbootstrap.scrolled", "ScrolledText"),
        ("ttkbootstrap.widgets", "ScrolledText"),
        ("tkinter.scrolledtext", "ScrolledText"),
    ]
    
    for module_path, widget_name in locations:
        ok, _ = check_module(module_path, widget_name)
        if ok:
            return True, f"Found in {module_path}"
    
    return False, "Not found in any expected location"

def main():
    print_header("System Information")
    print(f"Platform      : {platform.platform()}")
    print(f"Python        : {sys.version.split()[0]}")
    print(f"Executable    : {sys.executable}")
    print(f"Virtual Env   : {os.getenv('VIRTUAL_ENV', 'None')}")
    
    venv_dir = Path.cwd() / ".venv"
    print(f".venv exists  : {venv_dir.exists()}")
    
    if venv_dir.exists():
        in_venv = str(venv_dir.resolve()) in sys.executable
        status = "✅ Yes" if in_venv else "❌ No (using cached/system env)"
        print(f"Using .venv   : {status}")
        if not in_venv:
            print(f"\n⚠️  Not using local .venv! Run: make reset\n")

    print_header("GUI Framework (tkinter)")
    ok, msg = check_tkinter()
    status = "✅ PASS" if ok else "❌ FAIL"
    print(f"{status} | {msg}")
    
    if not ok and platform.system() == "Darwin":
        print("\n💡 macOS Fix:")
        print("   brew install tcl-tk")
        print("   export LDFLAGS=\"-L$(brew --prefix tcl-tk)/lib\"")
        print("   export CPPFLAGS=\"-I$(brew --prefix tcl-tk)/include\"")
        print("   pyenv install 3.12 --force")

    print_header("Critical Dependencies")
    critical = [
        ("PIL", "Pillow"),
        ("pillow_heif", "pillow-heif"),
        ("ttkbootstrap", "ttkbootstrap"),
        ("numpy", "numpy"),
        ("exifread", "ExifRead"),
        ("appdirs", "appdirs"),
    ]
    
    failures = []
    for module_name, display_name in critical:
        ok, msg = check_module(module_name)
        status = "✅" if ok else "❌"
        print(f"{status} {display_name:<20} : {msg}")
        if not ok:
            failures.append(display_name)

    print_header("ScrolledText Widget Check")
    ok, msg = check_scrolledtext()
    status = "✅ PASS" if ok else "❌ FAIL"
    print(f"{status} | {msg}")
    
    if not ok:
        print("\n💡 Fix: Update ttkbootstrap or check GUI import fallback:")
        print("   poetry add ttkbootstrap@latest")
        print("   poetry install")

    print_header("Optional Dependencies")
    optional = [
        ("skimage.metrics", "scikit-image (for SSIM quality metrics)"),
    ]
    
    for module_name, display_name in optional:
        ok, msg = check_module(module_name)
        status = "✅" if ok else "⚠️ "
        result = msg if ok else "Not installed (optional)"
        print(f"{status} {display_name:<45} : {result}")

    print_header("Summary")
    if failures:
        print(f"❌ FAILED: Missing {len(failures)} required package(s):")
        for pkg in failures:
            print(f"   - {pkg}")
        print("\nRun: make reset")
        sys.exit(1)
    else:
        print("✅ ALL CHECKS PASSED - Environment is healthy!")
        sys.exit(0)

if __name__ == "__main__":
    main()
