#!/usr/bin/env python3
"""
TIFF Converter GUI - macOS/Linux Compatible Implementation
Strict adherence to geometry constraints for Tcl/Tk 9.0+ compatibility.
"""
import os
import sys
import logging
import threading
import importlib
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Fallback flags
_TTKBOOTSTRAP_AVAILABLE = False
_IMPORT_ERROR = None

try:
    import ttkbootstrap as ttk
    # CRITICAL: Do NOT use wildcard imports to avoid namespace collisions
    # from ttkbootstrap.constants import *  # NEVER DO THIS
    
    # Locate ScrolledText widget
    ScrolledText = None
    candidates = [
        "ttkbootstrap.scrolled",
        "ttkbootstrap.widgets",
        "tkinter.scrolledtext",
    ]
    for module_path in candidates:
        try:
            mod = importlib.import_module(module_path)
            ScrolledText = getattr(mod, "ScrolledText", None)
            if ScrolledText:
                break
        except Exception:
            continue
    
    if not ScrolledText:
        from tkinter import scrolledtext
        ScrolledText = scrolledtext.ScrolledText
    
    _TTKBOOTSTRAP_AVAILABLE = True
except Exception as e:
    _IMPORT_ERROR = e
    logger.error(f"Failed to load GUI framework: {e}")

from photo_organizer.converter.core import batch_process, process_epson_folder
from photo_organizer.shared.file_utils import format_size


def _check_dependencies():
    """Verify GUI environment before launching."""
    if not _TTKBOOTSTRAP_AVAILABLE:
        root = tk.Tk()
        root.withdraw()
        
        error_details = str(_IMPORT_ERROR).lower() if _IMPORT_ERROR else ""
        if "ttkbootstrap" in error_details:
            message = (
                "❌ Missing Dependency: ttkbootstrap\n\n"
                "Install with:\n"
                "  poetry add ttkbootstrap@latest\n"
                "  poetry install"
            )
        elif "_tkinter" in error_details:
            message = (
                "❌ Tkinter/Tcl-Tk Error\n\n"
                "Python wasn't built with tcl-tk support.\n"
                "On macOS: brew install tcl-tk and rebuild Python."
            )
        else:
            message = f"❌ Dependency Error\n\n{_IMPORT_ERROR}"
        
        messagebox.showerror("Dependency Error", message)
        root.destroy()
        sys.exit(1)


def safe_widget_create(widget_cls, *args, bootstyle=None, **kwargs):
    """
    Safely create a ttkbootstrap widget with bootstyle support.
    
    Falls back to creation without bootstyle if the widget or underlying
    Tcl/Tk doesn't support it. This prevents TclError on some platforms.
    """
    if bootstyle:
        try:
            return widget_cls(*args, bootstyle=bootstyle, **kwargs)
        except (TypeError, tk.TclError):
            # Widget doesn't support bootstyle - retry without it
            return widget_cls(*args, **kwargs)
    else:
        return widget_cls(*args, **kwargs)


class TIFFConverterGUI:
    def __init__(self):
        _check_dependencies()
        
        self.root = ttk.Window(
            title="TIFF Converter Pro",
            themename="darkly",
            size=(950, 850)
        )
        self.source_dir = None
        self.is_processing = False
        self._create_widgets()
        self._update_dry_run_ui()
        self._log_dry_run_status()

    def _create_widgets(self):
        """Build UI with inner-frame padding strategy and safe packing order."""
        
        # 1. FIXED BOTTOM TOOLBAR (Pack FIRST to guarantee visibility)
        bottom_toolbar = ttk.Frame(self.root)
        bottom_toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Visual separator
        ttk.Separator(bottom_toolbar, orient="horizontal").pack(fill=tk.X)
        
        toolbar_inner = ttk.Frame(bottom_toolbar, padding=15)
        toolbar_inner.pack(fill=tk.X)
        
        safe_widget_create(
            ttk.Button,
            toolbar_inner,
            text="📁 Select Folder",
            command=self.browse_directory,
            bootstyle="secondary"
        ).pack(side=tk.LEFT)
        
        self.start_btn = safe_widget_create(
            ttk.Button,
            toolbar_inner,
            text="🚀 START CONVERSION",
            command=self.start_conversion,
            bootstyle="warning",
            width=35
        )
        self.start_btn.pack(side=tk.RIGHT)
        
        # 2. MAIN SCROLLABLE CONTENT (Pack AFTER toolbar)
        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=tk.YES, padx=20, pady=20)
        
        # Safety Banner
        self.safety_banner = safe_widget_create(
            ttk.Label,
            container,
            text="🔒 DRY RUN MODE ACTIVE",
            anchor=tk.CENTER,
            font=("Helvetica", 11, "bold"),
            bootstyle="inverse-warning"
        )
        self.safety_banner.pack(fill=tk.X, pady=(0, 15))
        
        # === Directory Selection ===
        dir_frame = ttk.LabelFrame(container, text="Source Directory")
        dir_frame.pack(fill=tk.X, pady=5)
        
        dir_inner = ttk.Frame(dir_frame, padding=10)
        dir_inner.pack(fill=tk.X)
        
        self.path_var = tk.StringVar(value="No directory selected")
        ttk.Entry(
            dir_inner,
            textvariable=self.path_var,
            state="readonly"
        ).pack(side=tk.LEFT, fill=tk.X, expand=tk.YES, padx=(0, 10))
        
        safe_widget_create(
            ttk.Button,
            dir_inner,
            text="Browse...",
            command=self.browse_directory,
            bootstyle="secondary-outline"
        ).pack(side=tk.RIGHT)
        
        # === Workflow Configuration ===
        work_frame = ttk.LabelFrame(container, text="Epson FastFoto Workflow")
        work_frame.pack(fill=tk.X, pady=5)
        
        work_inner = ttk.Frame(work_frame, padding=10)
        work_inner.pack(fill=tk.X)
        
        self.epson_mode = tk.BooleanVar(value=True)
        safe_widget_create(
            ttk.Checkbutton,
            work_inner,
            text="Enable Smart Variant Selection (Epson Mode)",
            variable=self.epson_mode,
            bootstyle="success-round-toggle"
        ).pack(anchor=tk.W, pady=2)
        
        self.convert_all_var = tk.BooleanVar(value=False)
        safe_widget_create(
            ttk.Checkbutton,
            work_inner,
            text="Convert ALL variants (Skip quality analysis)",
            variable=self.convert_all_var,
            bootstyle="warning-round-toggle"
        ).pack(anchor=tk.W, padx=25, pady=2)
        
        policy_frame = ttk.Frame(work_inner)
        policy_frame.pack(fill=tk.X, padx=25, pady=5)
        
        ttk.Label(policy_frame, text="Policy:").pack(side=tk.LEFT)
        self.variant_policy = tk.StringVar(value="auto")
        for val, txt in [("auto", "Auto"), ("prefer_base", "Base"), ("prefer_a", "_a")]:
            ttk.Radiobutton(
                policy_frame,
                text=txt,
                variable=self.variant_policy,
                value=val
            ).pack(side=tk.LEFT, padx=10)
        
        # === Conversion Options ===
        opt_frame = ttk.LabelFrame(container, text="Output Options")
        opt_frame.pack(fill=tk.X, pady=5)
        
        opt_inner = ttk.Frame(opt_frame, padding=10)
        opt_inner.pack(fill=tk.X)
        
        # LZW Column
        lzw_frame = ttk.Frame(opt_inner)
        lzw_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES)
        
        self.create_lzw = tk.BooleanVar(value=True)
        safe_widget_create(
            ttk.Checkbutton,
            lzw_frame,
            text="Create Lossless TIFF",
            variable=self.create_lzw,
            bootstyle="success-round-toggle"
        ).pack(anchor=tk.W)
        
        comp_frame = ttk.Frame(lzw_frame)
        comp_frame.pack(anchor=tk.W, padx=25, pady=5)
        
        ttk.Label(comp_frame, text="Compression:").pack(side=tk.LEFT)
        self.compression_type = tk.StringVar(value="lzw")
        ttk.Radiobutton(comp_frame, text="LZW", variable=self.compression_type, value="lzw").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(comp_frame, text="DEFLATE", variable=self.compression_type, value="deflate").pack(side=tk.LEFT)
        
        # HEIC Column
        heic_frame = ttk.Frame(opt_inner)
        heic_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES)
        
        self.create_heic = tk.BooleanVar(value=True)
        safe_widget_create(
            ttk.Checkbutton,
            heic_frame,
            text="Create HEIC",
            variable=self.create_heic,
            bootstyle="success-round-toggle"
        ).pack(anchor=tk.W)
        
        quality_frame = ttk.Frame(heic_frame)
        quality_frame.pack(anchor=tk.W, padx=25, pady=5)
        
        ttk.Label(quality_frame, text="Quality:").pack(side=tk.LEFT, padx=(0, 5))
        self.quality_var = tk.IntVar(value=90)
        safe_widget_create(
            ttk.Scale,
            quality_frame,
            from_=1, to=100,
            variable=self.quality_var,
            bootstyle="info"
        ).pack(side=tk.LEFT, fill=tk.X, expand=tk.YES)
        
        self.quality_label = ttk.Label(quality_frame, text="90", width=3)
        self.quality_label.pack(side=tk.LEFT)
        self.quality_var.trace_add("write", lambda *a: self.quality_label.config(text=str(self.quality_var.get())))
        
        # === Execution Safety ===
        # CRITICAL: Do NOT pass bootstyle to LabelFrame - use safe_widget_create or omit
        dry_frame = ttk.LabelFrame(container, text="⚠️ Execution Safety")
        dry_frame.pack(fill=tk.X, pady=10)
        
        dry_inner = ttk.Frame(dry_frame, padding=10)
        dry_inner.pack(fill=tk.X)
        
        self.dry_run_var = tk.BooleanVar(value=True)
        safe_widget_create(
            ttk.Checkbutton,
            dry_inner,
            text="🔒 DRY RUN MODE (Simulation Only - Recommended)",
            variable=self.dry_run_var,
            bootstyle="danger-round-toggle",
            command=self._on_dry_run_toggle
        ).pack(anchor=tk.W)
        
        # === Progress & Logs ===
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = safe_widget_create(
            ttk.Progressbar,
            container,
            variable=self.progress_var,
            bootstyle="success-striped",
            maximum=100
        )
        self.progress_bar.pack(fill=tk.X, pady=(15, 5))
        
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(container, textvariable=self.status_var, font=("Helvetica", 9)).pack(anchor=tk.W)
        
        # Log Area with robust fallback
        try:
            self.log_area = ScrolledText(container, height=12, autohide=True)
        except TypeError:
            self.log_area = ScrolledText(container, height=12)
        except Exception:
            # Final fallback using plain tk.Text
            log_wrapper = ttk.Frame(container)
            log_wrapper.pack(fill=tk.BOTH, expand=tk.YES)
            self.log_area = tk.Text(log_wrapper, height=12, wrap="word")
            scrollbar = tk.Scrollbar(log_wrapper, command=self.log_area.yview)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.log_area.config(yscrollcommand=scrollbar.set)
            self.log_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES)
        else:
            self.log_area.pack(fill=tk.BOTH, expand=tk.YES)

    def _on_dry_run_toggle(self):
        """Handle dry-run toggle with confirmation."""
        if not self.dry_run_var.get():
            confirm = messagebox.askyesno(
                "⚠️ Disable Dry Run?",
                "Switching to LIVE MODE:\n\n"
                "• Files will be written to disk\n"
                "• Originals will be moved\n"
                "• Changes are permanent\n\n"
                "Continue?"
            )
            if not confirm:
                self.dry_run_var.set(True)
                return
        
        self._update_dry_run_ui()
        self._log_dry_run_status()

    def _update_dry_run_ui(self):
        """Update visual elements based on dry-run state."""
        is_dry = bool(self.dry_run_var.get())
        
        if is_dry:
            try:
                self.safety_banner.config(
                    text="🔒 DRY RUN MODE ACTIVE (Simulation)",
                    bootstyle="inverse-warning"
                )
            except Exception:
                self.safety_banner.config(text="🔒 DRY RUN MODE ACTIVE (Simulation)")
            
            try:
                self.start_btn.config(
                    text="🚀 START CONVERSION (DRY RUN)",
                    bootstyle="warning"
                )
            except Exception:
                self.start_btn.config(text="🚀 START CONVERSION (DRY RUN)")
        else:
            try:
                self.safety_banner.config(
                    text="⚠️ LIVE MODE - FILES WILL BE MODIFIED",
                    bootstyle="inverse-danger"
                )
            except Exception:
                self.safety_banner.config(text="⚠️ LIVE MODE - FILES WILL BE MODIFIED")
            
            try:
                self.start_btn.config(
                    text="🔥 APPLY CHANGES (LIVE)",
                    bootstyle="success"
                )
            except Exception:
                self.start_btn.config(text="🔥 APPLY CHANGES (LIVE)")

    def _log_dry_run_status(self):
        """Log current execution mode to console."""
        is_dry = bool(self.dry_run_var.get())
        separator = "=" * 50
        
        self.log(separator)
        if is_dry:
            self.log("🔒 DRY RUN MODE ENABLED (Default)")
            self.log("   • No files will be modified")
            self.log("   • Operations are simulated")
        else:
            self.log("⚠️ LIVE MODE ENABLED")
            self.log("   • Files WILL be modified")
            self.log("   • Changes are PERMANENT")
        self.log(separator)

    def log(self, message):
        """Append message to log area with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        try:
            self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_area.see(tk.END)
        except Exception:
            # Fallback to stdout if log_area not available
            print(f"[{timestamp}] {message}")

    def browse_directory(self):
        """Browse for source directory."""
        path = filedialog.askdirectory(title="Select TIFF Folder")
        if path:
            self.source_dir = Path(path)
            self.path_var.set(path)
            self.log(f"✓ Selected: {path}")

    def start_conversion(self):
        """Primary entry point for conversion."""
        if not self.source_dir:
            messagebox.showwarning("Input Required", "Please select a source folder.")
            return
        
        if not (self.create_lzw.get() or self.create_heic.get()):
            messagebox.showwarning("Input Required", "Select at least one output format.")
            return
        
        self.is_processing = True
        self.start_btn.config(state=tk.DISABLED)
        try:
            self.log_area.delete("1.0", tk.END)
        except Exception:
            pass
        self._log_dry_run_status()
        
        threading.Thread(target=self._run_conversion, daemon=True).start()

    def _run_conversion(self):
        """Execute conversion in background thread."""
        try:
            options = {
                'create_lzw': self.create_lzw.get(),
                'create_heic': self.create_heic.get(),
                'heic_quality': self.quality_var.get(),
                'verify': True,
                'dry_run': self.dry_run_var.get(),
                'variant_policy': self.variant_policy.get(),
                'compression': self.compression_type.get(),
                'convert_all_variants': self.convert_all_var.get()
            }
            
            if self.epson_mode.get():
                results = process_epson_folder(
                    self.source_dir,
                    options,
                    progress_callback=self.update_progress
                )
            else:
                files = [f for f in self.source_dir.glob("*.tif*") if f.is_file()]
                if not files:
                    self.root.after(0, lambda: messagebox.showinfo("No Files", "No TIFFs found."))
                    return
                options['output_dir'] = self.source_dir
                results = batch_process(files, options, progress_callback=self.update_progress)
            
            success = sum(1 for r in results if r.success)
            self.root.after(0, lambda: self.log(f"\n✅ Finished: {success}/{len(results)} successful"))
            
        except Exception as e:
            logger.exception("Conversion failed")
            self.root.after(0, lambda: self.log(f"\n❌ Error: {e}"))
        finally:
            self.root.after(0, self._finish_conversion)

    def _finish_conversion(self):
        """Reset UI after conversion completes."""
        self.is_processing = False
        self.start_btn.config(state=tk.NORMAL)
        self.progress_var.set(0)
        self.status_var.set("Ready")

    def update_progress(self, current, total):
        """Update progress from background thread."""
        pct = (current / total * 100) if total > 0 else 0
        self.root.after(0, lambda: self.progress_var.set(pct))
        self.root.after(0, lambda: self.status_var.set(f"Processing: {current}/{total}"))


def main():
    """Entry point for GUI application."""
    app = TIFFConverterGUI()
    app.root.mainloop()


if __name__ == "__main__":
    main()
