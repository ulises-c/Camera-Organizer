#!/usr/bin/env python3
"""Main launcher for Photo Organizer Suite."""
import sys
import subprocess
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    print("Error: tkinter is required but not installed.")
    print("On macOS with pyenv, run: make install-python-macos")
    sys.exit(1)

TOOLS = [
    {
        "name": "📸 Photo & Video Organizer",
        "desc": "Sort files by date and camera model",
        "module": "photo_organizer.organizer.gui",
    },
    {
        "name": "📁 Folder Renamer",
        "desc": "Rename NNNYMMDD camera folders to YYYY-MM-DD",
        "module": "photo_organizer.renamer.folder_gui",
    },
    {
        "name": "🏷️ Batch Renamer",
        "desc": "Fix 'UnknownCamera' in filenames",
        "module": "photo_organizer.renamer.batch_gui",
    },
    {
        "name": "🖼️ TIFF Converter",
        "desc": "Convert TIFF to HEIC or LZW compression",
        "module": "photo_organizer.converter.gui",
    }
]


class LauncherApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Photo Organizer Suite")
        self.root.geometry("600x520")
        self.center_window()
        self.create_widgets()

    def center_window(self):
        """Center the window on screen."""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def create_widgets(self):
        # Header
        header = tk.Frame(self.root, pady=20)
        header.pack(fill=tk.X)

        tk.Label(
            header,
            text="📦 Photo Organizer Suite",
            font=("Helvetica", 24, "bold")
        ).pack(pady=(0, 5))

        tk.Label(
            header,
            text="Comprehensive tools for organizing photos and scans",
            font=("Helvetica", 10),
            fg="gray"
        ).pack()

        # Tools container
        container = tk.Frame(self.root, padx=20, pady=20)
        container.pack(fill=tk.BOTH, expand=True)

        for tool in TOOLS:
            self.create_tool_button(container, tool)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status = tk.Label(
            self.root,
            textvariable=self.status_var,
            fg="gray",
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.W,
            padx=10,
            pady=5
        )
        status.pack(side=tk.BOTTOM, fill=tk.X)

    def create_tool_button(self, parent, tool):
        frame = tk.Frame(parent, pady=10)
        frame.pack(fill=tk.X)

        # Left side: labels
        label_frame = tk.Frame(frame)
        label_frame.pack(fill=tk.X, side=tk.LEFT, expand=True)
        
        tk.Label(
            label_frame,
            text=tool["name"],
            font=("Helvetica", 12, "bold"),
            anchor=tk.W
        ).pack(anchor=tk.W)
        
        tk.Label(
            label_frame,
            text=tool["desc"],
            font=("Helvetica", 9),
            fg="gray",
            anchor=tk.W
        ).pack(anchor=tk.W, pady=(2, 0))

        # Right side: button
        btn = tk.Button(
            frame,
            text="Launch",
            width=12,
            command=lambda m=tool["module"]: self.launch_tool(m)
        )
        btn.pack(side=tk.RIGHT)

    def launch_tool(self, module_name: str):
        """Launch tool as separate process using module path."""
        try:
            subprocess.Popen([sys.executable, "-m", module_name])
            tool_name = module_name.split('.')[-1]
            self.status_var.set(f"Launched: {tool_name}")
        except Exception as e:
            self.status_var.set(f"Error launching {module_name}: {e}")

    def run(self):
        self.root.mainloop()


def main():
    app = LauncherApp()
    app.run()


if __name__ == "__main__":
    main()
