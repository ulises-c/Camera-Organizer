import tkinter as tk
from tkinter import filedialog, messagebox
import ttkbootstrap as ttk
from threading import Thread, Event
from pathlib import Path
from datetime import datetime
import logging
import sys
import os
import errno
import atexit
import appdirs

from photo_organizer.converter.core import process_epson_folder, save_report, HEIF_SAVE_AVAILABLE, OperationCancelled
from photo_organizer.shared.gui_utils import ToolTip

# Set up module logger that propagates to root (and thus to Launcher's listener)
logger = logging.getLogger("photo_organizer.converter.gui")
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)

def _lock_path_for(tool_name: str) -> Path:
    d = Path(appdirs.user_data_dir("photo_organizer", "PhotoOrganizerProject"))
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{tool_name}.lock"

def _acquire_lock(lock_path: Path) -> None:
    if lock_path.exists():
        try:
            pid = int(lock_path.read_text(encoding="utf-8").strip())
            os.kill(pid, 0)  # alive?
            raise RuntimeError("already_running")
        except ProcessLookupError:
            lock_path.unlink(missing_ok=True)
        except Exception:
            # unreadable or permission weirdness -> treat as “running” conservatively
            raise RuntimeError("already_running")

    # atomic create
    try:
        fd = os.open(str(lock_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        with os.fdopen(fd, "w") as f:
            f.write(str(os.getpid()))
    except OSError as e:
        if e.errno in (errno.EEXIST, errno.EACCES):
            raise RuntimeError("already_running")
        raise

def _release_lock(lock_path: Path | None) -> None:
    try:
        if not lock_path or not lock_path.exists():
            return

        content = lock_path.read_text(encoding="utf-8").strip()
        try:
            pid = int(content)
        except Exception:
            # corrupted/unreadable -> stale
            lock_path.unlink(missing_ok=True)
            return

        if pid == os.getpid():
            lock_path.unlink(missing_ok=True)
            return

        # remove stale locks (PID not alive)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            lock_path.unlink(missing_ok=True)
        except Exception:
            # if we can't determine, be conservative
            pass
    except Exception:
        pass

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

        # Single instance lock
        self._lock_path = _lock_path_for("tiff_converter")
        try:
            _acquire_lock(self._lock_path)
        except RuntimeError as e:
            if str(e) == "already_running":
                messagebox.showwarning(
                    "Already running",
                    "TIFF Converter is already running (only one instance is allowed)."
                )
                self.root.destroy()
                raise SystemExit(1)
            raise
        atexit.register(_release_lock, self._lock_path)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_vars(self):
        self.path_var = tk.StringVar(value="Select source folder...")
        self.dry_run = tk.BooleanVar(value=True)
        self.create_tiff = tk.BooleanVar(value=True)
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
        
        cb_tif = safe_widget_create(ttk.Checkbutton, row_tif, text="Create Lossless TIFF (Required)", variable=self.create_tiff, bootstyle="success-round-toggle", width=25)
        cb_tif.pack(side=tk.LEFT, padx=(0, 10))
        cb_tif.configure(state="disabled")
        
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
        # Always marshal to Tk thread
        self.root.after(0, lambda: self._append_log(msg))
        logger.info(msg) # Propagate to console

    def _append_log(self, msg: str):
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
            messagebox.showwarning("Error", "Select a folder first.")
            return
        if self.is_processing:
            return

        self.is_processing = True
        self.cancel_event.clear()
        self.progress_val.set(0)

        self.start_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)

        self.log(f"Starting process (dry_run={self.dry_run.get()})...")
        Thread(target=self._worker, daemon=True).start()

    def cancel(self):
        # immediate UX feedback; avoid "cancel after complete"
        if not getattr(self, "is_processing", False):
            return
        self.cancel_event.set()
        try:
            self.cancel_btn.config(state=tk.DISABLED)
        except Exception:
            pass
        try:
            self.status_var.set("Cancelling...")
        except Exception:
            pass
        self.log("Cancellation requested...")

    def _finalize_run(self, *, success: bool, cancelled: bool, report_name: str | None = None, err: str | None = None):
        """
        Runs on Tk main thread only. Resets UI and optionally shows a dialog.
        """
        # Reset state FIRST (prevents “stuck” + close prompt confusion)
        self.is_processing = False

        # best-effort: release instance lock so launcher can re-open immediately if user closes
        # (Though lock is primarily cleared on exit, checking it here doesn't hurt)
        try:
            if not getattr(self, "root", None) or not self.root.winfo_exists():
                return
        except Exception:
            pass

        try:
            self.start_btn.config(state=tk.NORMAL)
            self.cancel_btn.config(state=tk.DISABLED)
            self.status_var.set("Ready")
            self.progress_val.set(0)
        except Exception:
            pass

        # Optional dialogs: schedule slightly later to avoid Tk/macOS modal weirdness
        if err:
            self.root.after(50, lambda: messagebox.showerror("Error", err))
        elif cancelled:
            # Usually no dialog needed; if you do, keep it non-blocking-ish
            self.root.after(50, lambda: messagebox.showinfo("Cancelled", "Operation cancelled."))
        elif success:
            msg = "Task finished."
            if report_name:
                msg += f"\nReport: {report_name}"
            self.root.after(50, lambda: messagebox.showinfo("Complete", msg))

    def _worker(self):
        src = self.source_dir
        report_name = None
        cancelled = False
        err = None
        try:
            opts = {
                "dry_run": self.dry_run.get(),
                "create_tiff": self.create_tiff.get(),
                "compression": self.compression.get(),
                "create_heic": self.create_heic.get(),
                "heic_quality": int(self.heic_qual.get()),
                "create_jpg": self.create_jpg.get(),
                "jpg_quality": int(self.jpg_qual.get()),
                "variant_policy": self.ff_policy.get() if self.ff_enabled.get() else 'none',
                "variant_smart_archiving": self.ff_smart_archive.get(),
                "variant_smart_conversion": self.ff_smart_convert.get(),
                "cancel_event": self.cancel_event,
            }

            self.log("Process initialized; beginning conversion.")
            results = process_epson_folder(src, opts, self._update_progress, self.log)

            report_name = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            save_report(results, src / report_name)
            self.log(f"Report saved: {report_name}")
            self.log("Complete.")

        except OperationCancelled:
            cancelled = True
            self.log("Process cancelled.")
        except Exception as e:
            err = str(e)
            self.log(f"❌ Error: {err}")
            logger.exception("Worker thread exception")
        finally:
            self.root.after(
                0,
                lambda: self._finalize_run(
                    success=(err is None and not cancelled),
                    cancelled=cancelled,
                    report_name=report_name,
                    err=err,
                ),
            )
        # IMPORTANT: no direct widget ops here (worker thread)

    def _update_progress(self, val):
        self.root.after(0, lambda: self.progress_val.set(val))
        self.root.after(0, lambda: self.status_var.set(f"Processing: {int(val)}%"))

    def _on_close(self):
        if getattr(self, "is_processing", False):
            if not messagebox.askyesno("Exit", "A process is running. Cancel and exit?"):
                return
            self.cancel()
        _release_lock(getattr(self, "_lock_path", None))
        self.root.destroy()

if __name__ == "__main__":
    TIFFConverterGUI().root.mainloop()
