#!/usr/bin/env python3
"""Main launcher for Photo Organizer Suite."""
import os
import sys
import subprocess
import logging
from pathlib import Path
import threading
import tkinter as tk
from tkinter import messagebox

# Configure logging for backend console visibility
logger = logging.getLogger("photo_organizer.launcher")
logging.basicConfig(level=logging.INFO, stream=sys.stderr,
                    format='%(message)s')

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
        self.processes = {}  # map module -> {proc, btn}
        self.create_widgets()

    def center_window(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f'{w}x{h}+{x}+{y}')

    def create_widgets(self):
        header = tk.Frame(self.root, pady=20)
        header.pack(fill=tk.X)
        tk.Label(header, text="📦 Photo Organizer Suite", font=(
            "Helvetica", 24, "bold")).pack(pady=(0, 5))
        tk.Label(header, text="Comprehensive tools for organizing photos and scans", font=(
            "Helvetica", 10), fg="gray").pack()

        container = tk.Frame(self.root, padx=20, pady=20)
        container.pack(fill=tk.BOTH, expand=True)

        for tool in TOOLS:
            self.create_tool_button(container, tool)

        self.status_var = tk.StringVar(value="Ready")
        tk.Label(self.root, textvariable=self.status_var, fg="gray", bd=1,
                 relief=tk.SUNKEN, anchor=tk.W, padx=10, pady=5).pack(side=tk.BOTTOM, fill=tk.X)

    def create_tool_button(self, parent, tool):
        f = tk.Frame(parent, pady=10)
        f.pack(fill=tk.X)

        lf = tk.Frame(f)
        lf.pack(fill=tk.X, side=tk.LEFT, expand=True)
        tk.Label(lf, text=tool["name"], font=(
            "Helvetica", 12, "bold"), anchor=tk.W).pack(anchor=tk.W)
        tk.Label(lf, text=tool["desc"], font=(
            "Helvetica", 9), fg="gray", anchor=tk.W).pack(anchor=tk.W)

        btn = tk.Button(f, text="Launch", width=12)
        btn.config(command=lambda m=tool["module"],
                   b=btn: self.launch_tool(m, b))
        btn.pack(side=tk.RIGHT)

    def launch_tool(self, module_name, btn):
        # 1. Check existing (Global guard)
        # Block launching if ANY tool is running
        for m, info in list(self.processes.items()):
            p = info.get("proc")
            if p and p.poll() is None:
                messagebox.showwarning(
                    "Running",
                    f"Another tool is already running ({m}). Only one tool can run at a time."
                )
                return
        
        # Cleanup finished processes
        if module_name in self.processes:
            del self.processes[module_name]

        try:
            # 2. Prepare Environment
            env = os.environ.copy()
            root_dir = str(Path(__file__).parent.parent)
            env["PYTHONPATH"] = f"{root_dir}{os.pathsep}{env.get('PYTHONPATH', '')}"
            env["PYTHONUNBUFFERED"] = "1"

            # 3. Launch with stdout capture (unbuffered)
            proc = subprocess.Popen(
                [sys.executable, "-u", "-m", module_name],
                env=env, cwd=os.getcwd(),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                bufsize=1, universal_newlines=True
            )

            # 4. Update UI
            btn.config(state=tk.DISABLED)
            self.processes[module_name] = {'proc': proc, 'btn': btn}
            self.status_var.set(f"Launched: {module_name.split('.')[-1]}")
            logger.info(f"🚀 Launched {module_name} (PID {proc.pid})")

            # 5. Monitor threads
            threading.Thread(target=self._stream_output, args=(
                proc, module_name), daemon=True).start()
            threading.Thread(target=self._watch_exit, args=(
                module_name, btn, proc), daemon=True).start()

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _stream_output(self, proc, name):
        """Streams child process output to the main console."""
        with proc.stdout:
            for line in iter(proc.stdout.readline, ''):
                sys.stderr.write(f"[{name}] {line}")
                sys.stderr.flush()

    def _watch_exit(self, name, btn, proc):
        """Enables the button when process exits."""
        rc = proc.wait()
        logger.info(f"🏁 {name} exited with code {rc}")

        def _reset():
            if name in self.processes:
                del self.processes[name]
            try:
                btn.config(state=tk.NORMAL)
            except:
                pass
            self.status_var.set(f"Exited: {name.split('.')[-1]}")

        self.root.after(0, _reset)


def main():
    app = LauncherApp()
    app.root.mainloop()


if __name__ == "__main__":
    LauncherApp().root.mainloop()
