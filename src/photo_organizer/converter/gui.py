#!/usr/bin/env python3
"""
TIFF Converter GUI - Migrated from tiff-to-heic project
Modern implementation using ttkbootstrap
"""
import os
import sys
import logging
import threading
import importlib
from pathlib import Path
from tkinter import filedialog, messagebox

logger = logging.getLogger(__name__)

_TTKBOOTSTRAP_AVAILABLE = False
_IMPORT_ERROR = None

try:
    import ttkbootstrap as ttk
    from ttkbootstrap.constants import *

    ScrolledText = None
    candidates = [
        "ttkbootstrap.widgets.scrolled",
        "ttkbootstrap.scrolled",
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
        raise ImportError("Could not locate ScrolledText in ttkbootstrap or tkinter")

    _TTKBOOTSTRAP_AVAILABLE = True

except Exception as e:
    _IMPORT_ERROR = e
    logger.error(f"Failed to import ttkbootstrap: {e}", exc_info=True)

from photo_organizer.converter.core import batch_process, save_report, process_epson_folder
from photo_organizer.shared.file_utils import format_size


def _check_dependencies():
    """Check required dependencies and show helpful error if missing."""
    if not _TTKBOOTSTRAP_AVAILABLE:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()

        error_details = str(_IMPORT_ERROR).lower()

        if "ttkbootstrap" in error_details or "scrolledtext" in error_details:
            message = (
                "❌ Missing Dependency: ttkbootstrap\n\n"
                "Install/upgrade with:\n"
                "  poetry add ttkbootstrap@latest\n"
                "  poetry install\n\n"
                f"Error: {_IMPORT_ERROR}"
            )
        elif "_tkinter" in error_details:
            message = (
                "❌ Tkinter/Tcl-Tk Error\n\n"
                "The GUI framework cannot load. On macOS, this usually means:\n\n"
                "1. Python wasn't built with tcl-tk support\n"
                "2. Homebrew's tcl-tk isn't linked properly\n\n"
                "Fix:\n"
                "  brew install tcl-tk\n"
                "  export LDFLAGS=\"-L$(brew --prefix tcl-tk)/lib\"\n"
                "  export CPPFLAGS=\"-I$(brew --prefix tcl-tk)/include\"\n"
                "  pyenv install 3.12 --force\n"
                "  cd <project> && poetry install\n\n"
                f"Technical details: {_IMPORT_ERROR}"
            )
        else:
            message = (
                f"❌ Dependency Error\n\n"
                f"Failed to load GUI dependencies.\n\n"
                f"Error: {_IMPORT_ERROR}"
            )

        messagebox.showerror("Dependency Error", message)
        root.destroy()
        raise ImportError(message) from _IMPORT_ERROR


class TIFFConverterGUI:
    def __init__(self):
        _check_dependencies()
        
        self.root = ttk.Window(
            title="TIFF Converter",
            themename="darkly",
            size=(950, 950)
        )
        self.source_dir = None
        self.is_processing = False
        self._create_widgets()
        
        # Log initial dry-run state
        self._log_dry_run_status()

    def _create_widgets(self):
        # Main container (Frame supports padding, per GUI_CONSTRAINTS.md)
        container = ttk.Frame(self.root, padding=20)
        container.pack(fill=BOTH, expand=YES)

        # Header
        ttk.Label(
            container,
            text="🖼️ TIFF to HEIC/LZW Converter",
            font=("Helvetica", 20, "bold")
        ).pack(pady=(0, 20))

        # === Directory Selection ===
        dir_frame = ttk.LabelFrame(container, text="Source Directory")
        dir_frame.pack(fill=X, pady=10)
        
        dir_inner = ttk.Frame(dir_frame, padding=10)
        dir_inner.pack(fill=X)
        
        self.path_var = ttk.StringVar(value="No directory selected")
        ttk.Entry(
            dir_inner,
            textvariable=self.path_var,
            state="readonly"
        ).pack(side=LEFT, fill=X, expand=YES, padx=(0, 10))
        
        ttk.Button(
            dir_inner,
            text="Browse...",
            command=self.browse_directory
        ).pack(side=RIGHT)

        # === Workflow Configuration ===
        work_frame = ttk.LabelFrame(container, text="Epson FastFoto Workflow")
        work_frame.pack(fill=X, pady=10)
        
        work_inner = ttk.Frame(work_frame, padding=10)
        work_inner.pack(fill=X)
        
        self.epson_mode = ttk.BooleanVar(value=True)
        ttk.Checkbutton(
            work_inner,
            text="Enable Epson FastFoto Mode",
            variable=self.epson_mode,
            bootstyle="info-toolbutton"
        ).pack(anchor=W)
        
        # Convert All option
        self.convert_all_var = ttk.BooleanVar(value=False)
        ttk.Checkbutton(
            work_inner,
            text="Convert ALL variants (skip selection, process base, _a, and _b)",
            variable=self.convert_all_var,
            bootstyle="warning-round-toggle"
        ).pack(anchor=W, padx=20, pady=5)
        
        # Variant selection policy
        policy_frame = ttk.Frame(work_inner)
        policy_frame.pack(fill=X, padx=20, pady=5)
        
        ttk.Label(policy_frame, text="Variant Selection:").pack(side=LEFT)
        self.variant_policy = ttk.StringVar(value="auto")
        ttk.Radiobutton(
            policy_frame, text="Auto (Quality)", 
            variable=self.variant_policy, value="auto"
        ).pack(side=LEFT, padx=5)
        ttk.Radiobutton(
            policy_frame, text="Prefer Base", 
            variable=self.variant_policy, value="prefer_base"
        ).pack(side=LEFT, padx=5)
        ttk.Radiobutton(
            policy_frame, text="Prefer _a", 
            variable=self.variant_policy, value="prefer_a"
        ).pack(side=LEFT, padx=5)
        
        # Informational note
        ttk.Label(
            work_inner,
            text="ℹ️ Backside (_b) files are ALWAYS converted automatically\n"
                 "   Selection only applies to base vs _a variants",
            font=("Helvetica", 9, "italic"),
            bootstyle="info"
        ).pack(anchor=W, padx=20, pady=(2, 5))

        # === EXECUTION SAFETY (Prominent Section) ===
        safety_frame = ttk.LabelFrame(container, text="⚠️ Execution Safety")
        safety_frame.pack(fill=X, pady=15)
        
        safety_inner = ttk.Frame(safety_frame, padding=10)
        safety_inner.pack(fill=X)
        
        self.dry_run_var = ttk.BooleanVar(value=True)
        self.dry_run_chk = ttk.Checkbutton(
            safety_inner,
            text="🔒 DRY RUN MODE (Preview only, no files written or moved)",
            variable=self.dry_run_var,
            bootstyle="danger-round-toggle",
            command=self._on_dry_run_toggle
        )
        self.dry_run_chk.pack(fill=X)
        
        # Status badge
        badge_frame = ttk.Frame(safety_inner)
        badge_frame.pack(fill=X, pady=(8, 0))
        
        self.dry_status_label = ttk.Label(
            badge_frame,
            text="DRY RUN: ENABLED",
            font=("Helvetica", 11, "bold"),
            bootstyle="warning"
        )
        self.dry_status_label.pack(side=LEFT)

        # === Conversion Options ===
        opt_frame = ttk.LabelFrame(container, text="Conversion Options")
        opt_frame.pack(fill=X, pady=10)
        
        opt_inner = ttk.Frame(opt_frame, padding=10)
        opt_inner.pack(fill=X)

        self.create_lzw = ttk.BooleanVar(value=True)
        ttk.Checkbutton(
            opt_inner,
            text="Create LZW Compressed TIFF",
            variable=self.create_lzw,
            bootstyle="round-toggle"
        ).pack(anchor=W, pady=2)

        # Compression type
        comp_frame = ttk.Frame(opt_inner)
        comp_frame.pack(fill=X, padx=20, pady=2)
        
        ttk.Label(comp_frame, text="Compression:").pack(side=LEFT)
        self.compression_type = ttk.StringVar(value="lzw")
        ttk.Radiobutton(
            comp_frame, text="LZW",
            variable=self.compression_type, value="lzw"
        ).pack(side=LEFT, padx=5)
        ttk.Radiobutton(
            comp_frame, text="DEFLATE (smaller)",
            variable=self.compression_type, value="deflate"
        ).pack(side=LEFT)

        self.create_heic = ttk.BooleanVar(value=True)
        ttk.Checkbutton(
            opt_inner,
            text="Create HEIC (High Efficiency)",
            variable=self.create_heic,
            bootstyle="round-toggle"
        ).pack(anchor=W, pady=2)

        # HEIC quality
        quality_frame = ttk.Frame(opt_inner)
        quality_frame.pack(fill=X, padx=20, pady=5)
        
        ttk.Label(quality_frame, text="HEIC Quality:").pack(side=LEFT, padx=(0, 10))
        self.quality_var = ttk.IntVar(value=90)
        ttk.Scale(
            quality_frame,
            from_=1, to=100,
            variable=self.quality_var,
            bootstyle="info"
        ).pack(side=LEFT, fill=X, expand=YES, padx=(0, 10))
        
        self.quality_label = ttk.Label(quality_frame, text="90")
        self.quality_label.pack(side=LEFT)
        self.quality_var.trace_add("write", lambda *a: self.quality_label.config(
            text=str(self.quality_var.get())
        ))

        # === Progress ===
        self.progress_var = ttk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            container,
            variable=self.progress_var,
            bootstyle="success-striped",
            maximum=100
        )
        self.progress_bar.pack(fill=X, pady=(15, 5))
        
        self.status_var = ttk.StringVar(value="Ready")
        ttk.Label(container, textvariable=self.status_var).pack()

        # === Log Area ===
        ttk.Label(container, text="Processing Log:").pack(anchor=W, pady=(10, 5))
        self.log_area = ScrolledText(container, height=12, autohide=True)
        self.log_area.pack(fill=BOTH, expand=YES)

        # === Action Button ===
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill=X, pady=(15, 0))
        
        self.start_btn = ttk.Button(
            btn_frame,
            text="🚀 START CONVERSION (DRY RUN)",
            bootstyle="warning",
            command=self.start_conversion,
            state=DISABLED
        )
        self.start_btn.pack(side=RIGHT)

    def _on_dry_run_toggle(self):
        """Handle dry-run toggle with confirmation and UI updates."""
        enabled = bool(self.dry_run_var.get())
        
        # Confirmation when disabling dry-run
        if not enabled:
            confirm = messagebox.askyesno(
                "Disable Dry Run",
                "⚠️ You are about to DISABLE Dry Run.\n\n"
                "This will allow the tool to:\n"
                "• Write new LZW and HEIC files\n"
                "• Move original files to uncompressed/\n\n"
                "Are you sure you want to proceed?"
            )
            if not confirm:
                self.dry_run_var.set(True)
                return
        
        # Update UI
        self._update_dry_run_ui()
        self._log_dry_run_status()

    def _update_dry_run_ui(self):
        """Update all dry-run visual indicators."""
        enabled = bool(self.dry_run_var.get())
        
        if enabled:
            self.dry_status_label.config(
                text="DRY RUN: ENABLED",
                bootstyle="warning"
            )
            self.start_btn.config(
                text="🚀 START CONVERSION (DRY RUN)",
                bootstyle="warning"
            )
        else:
            self.dry_status_label.config(
                text="DRY RUN: DISABLED ⚠️",
                bootstyle="danger"
            )
            self.start_btn.config(
                text="🚀 START CONVERSION (APPLY CHANGES)",
                bootstyle="success"
            )

    def _log_dry_run_status(self):
        """Log current dry-run status to console."""
        enabled = bool(self.dry_run_var.get())
        if enabled:
            self.log("=" * 60)
            self.log("🔒 DRY RUN MODE: ENABLED")
            self.log("   • No files will be written")
            self.log("   • No files will be moved")
            self.log("   • All operations are simulated")
            self.log("=" * 60 + "\n")
        else:
            self.log("=" * 60)
            self.log("⚠️  DRY RUN MODE: DISABLED")
            self.log("   • Files WILL be written to LZW_compressed/ and HEIC/")
            self.log("   • Originals WILL be moved to uncompressed/")
            self.log("   • Changes are PERMANENT")
            self.log("=" * 60 + "\n")

    def browse_directory(self):
        """Browse for source directory."""
        path = filedialog.askdirectory(title="Select Folder with TIFF Files")
        if path:
            self.source_dir = Path(path)
            self.path_var.set(path)
            self.log(f"✓ Selected directory: {path}\n")
            self.start_btn.config(state=NORMAL)

    def log(self, message):
        """Append message to log area."""
        self.log_area.insert(END, f"{message}\n")
        self.log_area.see(END)

    def start_conversion(self):
        """Start the conversion process."""
        if not self.source_dir:
            messagebox.showerror("Error", "Please select a directory first")
            return
        
        if not self.create_lzw.get() and not self.create_heic.get():
            messagebox.showwarning("Warning", "Please select at least one output format")
            return

        self.is_processing = True
        self.start_btn.config(state=DISABLED)
        self.log_area.delete("1.0", END)
        
        # Log execution mode
        self._log_dry_run_status()
        self.log(f"🚀 Starting conversion...\n")
        
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
                self.root.after(0, lambda: self.log("📸 Epson FastFoto Workflow\n"))
                results = process_epson_folder(
                    self.source_dir,
                    options,
                    progress_callback=self.update_progress
                )
                report_name = "epson_conversion_report.json"
            else:
                # Standard batch processing
                tiff_files = []
                for ext in ["*.tif", "*.tiff", "*.TIF", "*.TIFF"]:
                    tiff_files.extend(list(self.source_dir.glob(ext)))
                
                if not tiff_files:
                    self.root.after(0, lambda: messagebox.showinfo(
                        "No Files", "No TIFF files found in selected directory"
                    ))
                    self._finish_conversion()
                    return

                options["output_dir"] = self.source_dir
                options["workers"] = os.cpu_count() or 4
                results = batch_process(tiff_files, options, progress_callback=self.update_progress)
                report_name = "conversion_report.json"
            
            # Save report
            report_path = self.source_dir / report_name
            save_report(results, report_path)
            
            # Summary
            success_count = sum(1 for r in results if r.success)
            total_count = len(results)
            
            dry_msg = " (DRY RUN - no changes made)" if options['dry_run'] else ""
            
            self.root.after(0, lambda: self.log(
                f"\n{'=' * 60}\n"
                f"✅ Conversion complete{dry_msg}\n"
                f"   Processed: {success_count}/{total_count}\n"
                f"   Report: {report_name}\n"
                f"{'=' * 60}"
            ))
            
            self.root.after(0, lambda: messagebox.showinfo(
                "Complete",
                f"Processed {success_count}/{total_count} files successfully.\n\n"
                f"Report saved: {report_name}"
            ))
            
        except Exception as e:
            self.root.after(0, lambda: self.log(f"\n❌ Error: {str(e)}"))
            self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
        finally:
            self.root.after(0, self._finish_conversion)

    def _finish_conversion(self):
        """Cleanup after conversion."""
        self.is_processing = False
        self.start_btn.config(state=NORMAL)
        self.status_var.set("Ready")

    def update_progress(self, current, total):
        """Update progress bar."""
        percentage = (current / total) * 100 if total > 0 else 0
        self.root.after(0, lambda: self.progress_var.set(percentage))
        self.root.after(0, lambda: self.status_var.set(f"Processing: {current}/{total}"))


def main():
    app = TIFFConverterGUI()
    app.root.mainloop()


if __name__ == "__main__":
    main()
