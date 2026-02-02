import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from threading import Thread, Event
from pathlib import Path
from datetime import datetime
import logging
import sys

from photo_organizer.converter.core import process_epson_folder, save_report, HEIF_SAVE_AVAILABLE
from photo_organizer.shared.gui_utils import ToolTip

# Set up module logger that propagates to root (and thus to Launcher's listener)
logger = logging.getLogger("photo_organizer.converter.gui")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)

def safe_widget_create(widget_cls, parent, **kwargs):
    """
    Creates widgets safely for macOS/Linux Tkinter compatibility.
    1. Maps 'width' to 'length' for Scale/Progressbar.
    2. STRIPS 'bootstyle' for container widgets (LabelFrame/Frame) which crash on Mac.
    3. Handles TclErrors gracefully.
    """
    widget_name = getattr(widget_cls, "__name__", str(widget_cls))

    # 1. Map width -> length for bars/scales
    if widget_name in ('Scale', 'Progressbar') and 'width' in kwargs:
        if 'length' not in kwargs: kwargs['length'] = kwargs.pop('width')
        else: kwargs.pop('width')

    # 2. Strict Constraint: No bootstyle for containers
    container_names = ('LabelFrame', 'Frame', 'Labelframe')
    if widget_name in container_names:
        kwargs.pop('bootstyle', None)
        try: return widget_cls(parent, **kwargs)
        except (tk.TclError, TypeError): return widget_cls(parent, **kwargs)

    # 3. Safe creation for styled widgets
    bootstyle = kwargs.pop('bootstyle', None)
    try:
        if bootstyle: return widget_cls(parent, bootstyle=bootstyle, **kwargs)
        return widget_cls(parent, **kwargs)
    except (tk.TclError, TypeError):
        return widget_cls(parent, **kwargs)

class TIFFConverterGUI:
    def __init__(self):
        self.root = ttk.Window(title="TIFF Converter Pro", themename="darkly", size=(950, 900))
        self.source_dir = None
        self.is_processing = False
        self.cancel_event = Event()
        
        self._init_vars()
        self._create_layout()
        self._update_dry_run_state()
        self._toggle_ff()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_vars(self):
        self.path_var = tk.StringVar(value="Select source folder...")
        self.dry_run = tk.BooleanVar(value=True)
        self.compression = tk.StringVar(value="deflate")
        self.create_heic = tk.BooleanVar(value=HEIF_SAVE_AVAILABLE)
        self.heic_qual = tk.IntVar(value=100)
        self.create_jpg = tk.BooleanVar(value=False)
        self.jpg_qual = tk.IntVar(value=95)
        
        # FastFoto Workflow
        self.ff_enabled = tk.BooleanVar(value=True)
        self.ff_policy = tk.StringVar(value="smart")
        self.ff_smart_archive = tk.BooleanVar(value=True)
        self.ff_smart_convert = tk.BooleanVar(value=True)
        
        self.progress_val = tk.DoubleVar(value=0)
        self.status_var = tk.StringVar(value="Ready")

    def _create_layout(self):
        # 1. TOOLBAR (Pack BOTTOM first for correct geometry)
        toolbar = ttk.Frame(self.root, padding=10)
        toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.start_btn = safe_widget_create(ttk.Button, toolbar, text="RUN SIMULATION", command=self.start, bootstyle="warning", width=20)
        self.start_btn.pack(side=tk.RIGHT, padx=5)
        
        self.cancel_btn = safe_widget_create(ttk.Button, toolbar, text="Cancel", command=self.cancel, bootstyle="danger-outline")
        self.cancel_btn.pack(side=tk.RIGHT, padx=5)
        self.cancel_btn.config(state=tk.DISABLED)

        # 2. MAIN CONTENT
        main = ttk.Frame(self.root, padding=20)
        main.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.banner = safe_widget_create(ttk.Label, main, text="DRY RUN MODE", bootstyle="inverse-warning", anchor="center")
        self.banner.pack(fill=tk.X, pady=(0, 15))

        # Source Section
        lf_src = safe_widget_create(ttk.LabelFrame, main, text=" 1. Source Folder ")
        lf_src.pack(fill=tk.X, pady=5)
        inner_src = ttk.Frame(lf_src, padding=10)
        inner_src.pack(fill=tk.X)
        ttk.Entry(inner_src, textvariable=self.path_var, state="readonly").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(inner_src, text="Browse", command=self.browse).pack(side=tk.RIGHT)

        # Options Section
        lf_opt = safe_widget_create(ttk.LabelFrame, main, text=" 2. Output Options ")
        lf_opt.pack(fill=tk.X, pady=5)
        inner_opt = ttk.Frame(lf_opt, padding=10)
        inner_opt.pack(fill=tk.X)

        # TIFF Row
        row_tif = ttk.Frame(inner_opt)
        row_tif.pack(fill=tk.X, pady=5)
        # Fix: Moved width to constructor (via safe_widget_create or explicit arg) or use padding
        ttk.Label(row_tif, text="Lossless TIFF:", font=("Helvetica", 9, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        r1 = ttk.Radiobutton(row_tif, text="Deflate (.ZIP.TIF)", variable=self.compression, value="deflate")
        r1.pack(side=tk.LEFT, padx=10)
        r2 = ttk.Radiobutton(row_tif, text="LZW (.LZW.TIF)", variable=self.compression, value="lzw")
        r2.pack(side=tk.LEFT)
        ToolTip(r1, "Standard Adobe Deflate. High compression, widely supported.")

        # HEIC Row
        row_heic = ttk.Frame(inner_opt)
        row_heic.pack(fill=tk.X, pady=5)
        cb_h = safe_widget_create(ttk.Checkbutton, row_heic, text="Convert to HEIC", variable=self.create_heic, bootstyle="success-round-toggle", width=18)
        cb_h.pack(side=tk.LEFT, padx=(0, 10))
        if not HEIF_SAVE_AVAILABLE: cb_h.config(state=tk.DISABLED, text="HEIC (N/A)")
        
        ttk.Label(row_heic, text="Quality:").pack(side=tk.LEFT, padx=5)
        safe_widget_create(ttk.Scale, row_heic, from_=50, to=100, variable=self.heic_qual, width=200).pack(side=tk.LEFT)
        ttk.Label(row_heic, textvariable=self.heic_qual).pack(side=tk.LEFT, padx=5)

        # JPG Row
        row_jpg = ttk.Frame(inner_opt)
        row_jpg.pack(fill=tk.X, pady=5)
        safe_widget_create(ttk.Checkbutton, row_jpg, text="Convert to JPG", variable=self.create_jpg, bootstyle="success-round-toggle", width=18).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(row_jpg, text="Quality:").pack(side=tk.LEFT, padx=5)
        safe_widget_create(ttk.Scale, row_jpg, from_=50, to=100, variable=self.jpg_qual, width=200).pack(side=tk.LEFT)
        ttk.Label(row_jpg, textvariable=self.jpg_qual).pack(side=tk.LEFT, padx=5)

        # FastFoto Workflow
        lf_ff = safe_widget_create(ttk.LabelFrame, main, text=" 3. FastFoto Smart Workflow ")
        lf_ff.pack(fill=tk.X, pady=5)
        inner_ff = ttk.Frame(lf_ff, padding=10)
        inner_ff.pack(fill=tk.X)
        
        safe_widget_create(ttk.Checkbutton, inner_ff, text="Enable Smart Workflow", variable=self.ff_enabled, command=self._toggle_ff, bootstyle="info-round-toggle").pack(anchor="w")
        
        self.ff_sub = ttk.Frame(inner_ff, padding=(20, 5, 0, 0))
        self.ff_sub.pack(fill=tk.X)
        
        ttk.Label(self.ff_sub, text="Selection Policy:").pack(anchor="w")
        row_pol = ttk.Frame(self.ff_sub)
        row_pol.pack(fill=tk.X, pady=(2, 5))
        for p in ['smart', 'base', 'augment', 'none']:
            ttk.Radiobutton(row_pol, text=p.capitalize(), variable=self.ff_policy, value=p).pack(side=tk.LEFT, padx=(0, 10))
            
        safe_widget_create(ttk.Checkbutton, self.ff_sub, text="Smart Archive (Move rejects to archive/)", variable=self.ff_smart_archive, bootstyle="warning-round-toggle").pack(anchor="w", pady=2)
        safe_widget_create(ttk.Checkbutton, self.ff_sub, text="Smart Conversion (Convert 'Selects' only)", variable=self.ff_smart_convert, bootstyle="warning-round-toggle").pack(anchor="w", pady=2)

        # Execution
        row_exec = ttk.Frame(main, padding=(0, 10))
        row_exec.pack(fill=tk.X)
        safe_widget_create(ttk.Checkbutton, row_exec, text="Dry Run Mode (No changes)", variable=self.dry_run, command=self._toggle_dry_run, bootstyle="danger-round-toggle").pack(side=tk.LEFT)

        # Progress
        self.pbar = safe_widget_create(ttk.Progressbar, main, variable=self.progress_val, bootstyle="success-striped")
        self.pbar.pack(fill=tk.X, pady=5)
        ttk.Label(main, textvariable=self.status_var).pack(anchor="w")

        # Logs
        from tkinter.scrolledtext import ScrolledText
        self.log_area = ScrolledText(main, height=10, state='disabled', font=("Courier", 11))
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def _toggle_ff(self):
        state = 'normal' if self.ff_enabled.get() else 'disabled'
        for child in self.ff_sub.winfo_children():
            try: child.configure(state=state)
            except: pass

    def _toggle_dry_run(self):
        if not self.dry_run.get():
            if not messagebox.askyesno("Confirm", "Disable Dry Run? This will modify files on disk."):
                self.dry_run.set(True)
        self._update_dry_run_state()

    def _update_dry_run_state(self):
        if self.dry_run.get():
            self.banner.config(text="🛡️ DRY RUN MODE ENABLED", bootstyle="inverse-warning")
            self.start_btn.config(text="RUN SIMULATION", bootstyle="warning")
        else:
            self.banner.config(text="⚠️ LIVE MODE ACTIVE", bootstyle="inverse-danger")
            self.start_btn.config(text="EXECUTE LIVE", bootstyle="success")

    def log(self, msg):
        self.root.after(0, lambda: self._log_safe(msg))
        logger.info(msg) # Propagate to console

    def _log_safe(self, msg):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def browse(self):
        p = filedialog.askdirectory()
        if p:
            self.source_dir = Path(p)
            self.path_var.set(p)
            self.log(f"Selected: {p}")

    def start(self):
        if not self.source_dir:
            messagebox.showwarning("Error", "Select a folder.")
            return
        self.is_processing = True
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.cancel_event.clear()
        self.progress_val.set(0)
        self.status_var.set("Working...")
        Thread(target=self._worker, daemon=True).start()

    def cancel(self):
        self.cancel_event.set()
        self.status_var.set("Stopping...")
        self.log("Cancellation requested...")

    def _worker(self):
        opts = {
            'dry_run': self.dry_run.get(),
            'compression': self.compression.get(),
            'create_heic': self.create_heic.get(),
            'heic_quality': self.heic_qual.get(),
            'create_jpg': self.create_jpg.get(),
            'jpg_quality': self.jpg_qual.get(),
            'variant_policy': self.ff_policy.get() if self.ff_enabled.get() else 'none',
            'variant_smart_archiving': self.ff_smart_archive.get(),
            'variant_smart_conversion': self.ff_smart_convert.get(),
            'cancel_event': self.cancel_event
        }
        try:
            results = process_epson_folder(self.source_dir, opts, self._update_progress, self.log)
            
            rep = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            save_report(results, self.source_dir / rep)
            self.log(f"Report saved: {rep}")
            
            if self.cancel_event.is_set():
                 self.log("🛑 Process Stopped.")
            else:
                 self.root.after(0, lambda: messagebox.showinfo("Success", f"Processed {len(results)} groups."))
        except Exception as e:
            self.log(f"Error: {e}")
        finally:
            self.root.after(0, self._reset)

    def _update_progress(self, val):
        self.root.after(0, lambda: self.progress_val.set(val))
        # Critical for macOS responsiveness during threads
        self.root.after(0, self.root.update_idletasks)

    def _reset(self):
        self.is_processing = False
        self.start_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self.status_var.set("Ready")

    def _on_close(self):
        if self.is_processing:
            if not messagebox.askyesno("Exit", "Stop process and exit?"): return
            self.cancel()
        self.root.destroy()

if __name__ == "__main__":
    TIFFConverterGUI().root.mainloop()
