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
from threading import Event

logger = logging.getLogger(__name__)

# Fallback flags
_TTKBOOTSTRAP_AVAILABLE = False
_IMPORT_ERROR = None

try:
    import ttkbootstrap as ttk
    
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
    """Safely create a ttkbootstrap widget with bootstyle support."""
    if bootstyle:
        try:
            return widget_cls(*args, bootstyle=bootstyle, **kwargs)
        except (TypeError, tk.TclError):
            return widget_cls(*args, **kwargs)
    return widget_cls(*args, **kwargs)


class GUILogHandler(logging.Handler):
    """
    Thread-safe logging handler that forwards log records to GUI.
    Uses weak coupling via callable to avoid circular references.
    """
    def __init__(self, forward_fn):
        super().__init__()
        self.forward_fn = forward_fn

    def emit(self, record):
        try:
            msg = self.format(record)
            # forward_fn must use root.after() for thread safety
            self.forward_fn(msg)
        except Exception:
            # Fail silently to avoid cascading logging errors
            pass


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
        
        # Thread control
        self.worker_thread = None
        self.cancel_event = Event()
        
        self._create_widgets()
        
        # Attach logger -> GUI forwarder
        def _forward_log_to_gui(message):
            # Ensure execution on main thread for Tkinter safety
            self.root.after(0, lambda: self.log(message))
        
        self._log_handler = GUILogHandler(_forward_log_to_gui)
        self._log_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s: %(message)s", 
            "%H:%M:%S"
        )
        self._log_handler.setFormatter(formatter)
        logging.getLogger('photo_organizer').addHandler(self._log_handler)
        
        # Cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self._update_dry_run_ui()
        self._log_dry_run_status()

    def _create_widgets(self):
        """Build UI with inner-frame padding strategy and safe packing order."""
        
        # 1. FIXED BOTTOM TOOLBAR (Pack FIRST to guarantee visibility)
        bottom_toolbar = ttk.Frame(self.root)
        bottom_toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        ttk.Separator(bottom_toolbar, orient="horizontal").pack(fill=tk.X)
        
        toolbar_inner = ttk.Frame(bottom_toolbar, padding=15)
        toolbar_inner.pack(fill=tk.X)
        
        self.start_btn = safe_widget_create(
            ttk.Button,
            toolbar_inner,
            text="🚀 START CONVERSION",
            command=self.start_conversion,
            bootstyle="warning",
            width=40
        )
        self.start_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Cancel button
        self.cancel_btn = safe_widget_create(
            ttk.Button,
            toolbar_inner,
            text="✖ Cancel",
            command=self.cancel_conversion,
            bootstyle="danger-outline",
            width=12
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=(5, 0))
        self.cancel_btn.config(state=tk.DISABLED)
        
        # 2. MAIN SCROLLABLE CONTENT (Pack AFTER toolbar)
        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=tk.YES, padx=20, pady=20)
        
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
        
        try:
            self.log_area = ScrolledText(container, height=12, autohide=True)
        except (TypeError, tk.TclError):
            try:
                self.log_area = ScrolledText(container, height=12)
            except Exception:
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
            self.safety_banner.config(text="🔒 DRY RUN MODE ACTIVE (Simulation)", bootstyle="inverse-warning")
            self.start_btn.config(text="🚀 START CONVERSION (DRY RUN)", bootstyle="warning")
        else:
            self.safety_banner.config(text="⚠️ LIVE MODE - FILES WILL BE MODIFIED", bootstyle="inverse-danger")
            self.start_btn.config(text="🔥 APPLY CHANGES (LIVE)", bootstyle="success")

    def _log_dry_run_status(self):
        """Log current execution mode."""
        is_dry = bool(self.dry_run_var.get())
        self.log("=" * 50)
        self.log(f"MODE: {'🔒 DRY RUN (Simulation)' if is_dry else '⚠️ LIVE (Permanent Changes)'}")
        self.log("=" * 50)

    def log(self, message: str):
        """
        Thread-safe logging to UI text widget.
        Always schedules updates on the Tcl/Tk main loop.
        """
        def _append_log():
            timestamp = datetime.now().strftime("%H:%M:%S")
            try:
                self.log_area.insert(tk.END, f"[{timestamp}] {message}\n")
                self.log_area.see(tk.END)
            except Exception as e:
                # Fallback if widget destroyed during exit
                print(f"Log Error: {e}")
        
        # Always use after(0) instead of direct call
        if hasattr(self, 'root') and self.root.winfo_exists():
            self.root.after(0, _append_log)
        else:
            print(f"[Fallback] {message}")

    def browse_directory(self):
        """Browse for source directory."""
        path = filedialog.askdirectory(title="Select TIFF Folder")
        if path:
            self.source_dir = Path(path)
            self.path_var.set(path)
            self.log(f"✓ Selected: {path}")

    def start_conversion(self):
        """Primary entry point for conversion."""
        if self.is_processing:
            return
        
        if not self.source_dir:
            messagebox.showwarning("Input Required", "Please select a source folder.")
            return
        
        if not (self.create_lzw.get() or self.create_heic.get()):
            messagebox.showwarning("Input Required", "Select at least one output format.")
            return
        
        self.is_processing = True
        self.start_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        self.cancel_event.clear()
        
        try:
            self.log_area.delete("1.0", tk.END)
        except Exception:
            pass
        
        self._log_dry_run_status()
        
        # Start worker and track it
        self.worker_thread = threading.Thread(
            target=self._run_conversion, 
            daemon=True
        )
        self.worker_thread.start()
        
        # Start watchdog to ensure UI recovery
        self._start_watchdog()

    def _start_watchdog(self):
        """Poll worker thread to ensure UI recovery."""
        def _check_thread():
            try:
                if self.worker_thread and self.worker_thread.is_alive():
                    # Still running, check again in 1 second
                    self.root.after(1000, _check_thread)
                    return
            except Exception:
                pass
            
            # Thread finished or died - ensure cleanup
            self.root.after(0, self._finish_conversion)
        
        self.root.after(1000, _check_thread)

    def cancel_conversion(self):
        """Request cancellation of ongoing conversion."""
        if not hasattr(self, "cancel_event"):
            return
        
        self.cancel_event.set()
        self.log("✋ Cancel requested. Stopping processing...")
        self.cancel_btn.config(state=tk.DISABLED)

    def _run_conversion(self):
        """Execute conversion in background thread with robust error handling."""
        results = []
        try:
            options = {
                'create_lzw': self.create_lzw.get(),
                'create_heic': self.create_heic.get(),
                'heic_quality': self.quality_var.get(),
                'verify': True,
                'dry_run': self.dry_run_var.get(),
                'variant_policy': self.variant_policy.get(),
                'compression': self.compression_type.get(),
                'convert_all_variants': self.convert_all_var.get(),
                'cancel_event': self.cancel_event,
                'workers': 4
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
            
            if self.cancel_event.is_set():
                self.log("⚠️ Conversion cancelled by user")
            else:
                success_count = sum(1 for r in results if r.success)
                total_count = len(results)
                self.root.after(0, lambda: self.log(f"\n✅ Conversion Complete: {success_count}/{total_count} processed successfully"))
            
        except Exception as e:
            logger.exception("Conversion failed")
            self.root.after(0, lambda: self.log(f"\n❌ Error: {e}"))
        finally:
            # CRITICAL: Use after(0) instead of after_idle for macOS Tcl/Tk 9.0+
            self.root.after(0, self._finish_conversion)

    def _finish_conversion(self):
        """Reset UI state after conversion. Must run on main thread."""
        self.is_processing = False
        self.start_btn.config(state=tk.NORMAL)
        self.cancel_btn.config(state=tk.DISABLED)
        self.progress_var.set(0)
        self.status_var.set("Ready")
        self.worker_thread = None
        self.cancel_event = Event()  # Fresh event for next run
        self.log("🏁 System Ready.")

    def _on_close(self):
        """Cleanup on window close."""
        try:
            logging.getLogger('photo_organizer').removeHandler(self._log_handler)
        except Exception:
            pass
        try:
            if self.cancel_event:
                self.cancel_event.set()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def update_progress(self, current, total):
        """Thread-safe progress updates."""
        pct = (current / total * 100) if total > 0 else 0
        
        def _update():
            self.progress_var.set(pct)
            self.status_var.set(f"Processing: {current}/{total}")
        
        self.root.after(0, _update)


def main():
    app = TIFFConverterGUI()
    app.root.mainloop()


if __name__ == "__main__":
    main()
