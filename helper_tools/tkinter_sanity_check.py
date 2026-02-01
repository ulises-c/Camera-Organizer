# Quick sanity check for tkinter installation
try:
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    print("tkinter is installed and working.")
    root.destroy()
except ImportError as e:
    print("tkinter is NOT installed:", e)
except Exception as e:
    print("An error occurred while testing tkinter:", e)
