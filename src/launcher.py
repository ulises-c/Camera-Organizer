#!/usr/bin/env python3
"""Main launcher for Photo Organizer Suite."""
import sys
import subprocess
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    print("tkinter is required but not installed.")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parent

TOOLS = [
    {
        "name": "📸 Photo & Video Organizer",
        "desc": "Sort files by date and camera model",
        "script": PROJECT_ROOT / "organizer" / "gui.py",
    },
    {
        "name": "📁 Folder Renamer",
        "desc": "Rename NNNYMMDD camera folders to YYYY-MM-DD",
        "script": PROJECT_ROOT / "renamer" / "folder_gui.py",
    },
    {
        "name": "🏷️ Batch Renamer",
        "desc": "Fix 'UnknownCamera' in filenames",
        "script": PROJECT_ROOT / "renamer" / "batch_gui.py",
    },
    {
        "name": "🖼️ TIFF Converter",
        "desc": "Convert TIFF to HEIC or LZW compression",
        "script": PROJECT_ROOT / "converter" / "gui.py",
    }
]


class LauncherApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Photo Organizer Suite")
        self.root.geometry("550x500")
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

        # Tool name and description
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

        # Launch button
        btn = tk.Button(
            frame,
            text="Launch",
            width=12,
            command=lambda s=tool['script']: self.launch_tool(s)
        )
        btn.pack(side=tk.RIGHT)

        if not tool['script'].exists():
            btn.config(state='disabled')

    def launch_tool(self, script_path: Path):
        try:
            subprocess.Popen([sys.executable, str(script_path)])
            self.status_var.set(f"Launched: {script_path.name}")
        except Exception as e:
            self.status_var.set(f"Error: {e}")

    def run(self):
        self.root.mainloop()


def main():
    app = LauncherApp()
    app.run()


if __name__ == "__main__":
    main()
