"""
Folder Renamer for Camera-Generated Folders
Renames folders from NNNYMMDD pattern to YYYY-MM-DD[_CameraModel]
Supports batch/recursive mode with dry-run preview and safe merge capability.
"""
import os
import re
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from photo_organizer.shared.metadata import get_creation_date, get_camera_model
from photo_organizer.shared.camera_models import resolve_model_name, add_camera_model

FOLDER_PATTERN = re.compile(r"^(\d{3})(\d)(\d{2})(\d{2})$")


def extract_folder_metadata(folder_path: str):
    """
    Extract creation date and camera model from files in folder.
    Samples first, middle, and last files for consistency.
    Returns tuple: (date, model, sample_file_path) or (None, None, None)
    """
    files = []
    for root, _, filenames in os.walk(folder_path):
        for filename in filenames:
            if not filename.startswith('.') and not filename.startswith('_'):
                files.append(os.path.join(root, filename))
    
    if not files:
        return None, None, None
    
    files.sort()
    n = len(files)
    
    indices = [0, n // 2, n - 1] if n > 2 else list(range(n))
    
    for idx in indices:
        try:
            file_path = files[idx]
            date = get_creation_date(file_path)
            model = get_camera_model(file_path)
            
            if date and date != "Unknown":
                return date, model, file_path
        except Exception:
            continue
    
    return None, None, None


def safe_merge_folders(src_path: str, dst_path: str, log_func=None):
    """
    Safely merge contents from src into dst.
    Handles file conflicts by appending suffix.
    Returns (files_moved, files_skipped).
    """
    moved = 0
    skipped = 0
    
    for item in os.listdir(src_path):
        src_item = os.path.join(src_path, item)
        dst_item = os.path.join(dst_path, item)
        
        try:
            if os.path.isdir(src_item):
                if os.path.exists(dst_item):
                    # Recursively merge subdirectories
                    sub_moved, sub_skipped = safe_merge_folders(src_item, dst_item, log_func)
                    moved += sub_moved
                    skipped += sub_skipped
                    # Try to remove now-empty source subdir
                    try:
                        os.rmdir(src_item)
                    except OSError:
                        pass
                else:
                    shutil.move(src_item, dst_item)
                    moved += 1
            else:
                # Handle file
                if os.path.exists(dst_item):
                    # Create unique name for conflict
                    base, ext = os.path.splitext(item)
                    counter = 1
                    while os.path.exists(os.path.join(dst_path, f"{base}_dup{counter}{ext}")):
                        counter += 1
                    dst_item = os.path.join(dst_path, f"{base}_dup{counter}{ext}")
                    shutil.move(src_item, dst_item)
                    moved += 1
                    if log_func:
                        log_func(f"    → Renamed conflict: {item} → {os.path.basename(dst_item)}")
                else:
                    shutil.move(src_item, dst_item)
                    moved += 1
        except Exception as e:
            skipped += 1
            if log_func:
                log_func(f"    ✗ Error moving {item}: {e}")
    
    return moved, skipped


def compute_new_name(folder_path: str, include_model: bool = True) -> tuple:
    """
    Compute new folder name based on metadata.
    Returns (new_path, status) where status indicates:
    'ok', 'merge', 'pattern_mismatch', 'no_metadata', 'already_correct'
    """
    folder_name = os.path.basename(folder_path.rstrip(os.sep))
    
    if not FOLDER_PATTERN.match(folder_name):
        return None, "pattern_mismatch"
    
    date, raw_model, _ = extract_folder_metadata(folder_path)
    
    if not date:
        return None, "no_metadata"
    
    new_name = date
    
    if include_model and raw_model:
        friendly_model = resolve_model_name(raw_model)
        if friendly_model and friendly_model != "UnknownCamera":
            safe_model = friendly_model.replace('/', '-').replace('\\', '-')
            new_name = f"{date}_{safe_model}"
    
    parent_dir = os.path.dirname(folder_path)
    new_path = os.path.join(parent_dir, new_name)
    
    if os.path.normpath(new_path) == os.path.normpath(folder_path):
        return None, "already_correct"
    
    if os.path.exists(new_path):
        return new_path, "merge"
    
    return new_path, "ok"


def gather_candidate_folders(parent_path: str, recursive: bool) -> list:
    """
    Gather all folders that match the camera pattern.
    If recursive, searches entire tree; otherwise, only immediate children.
    """
    candidates = []
    
    if recursive:
        for root, dirs, _ in os.walk(parent_path):
            for dirname in dirs:
                full_path = os.path.join(root, dirname)
                folder_name = os.path.basename(full_path)
                if FOLDER_PATTERN.match(folder_name):
                    candidates.append(full_path)
    else:
        try:
            with os.scandir(parent_path) as entries:
                for entry in entries:
                    if entry.is_dir():
                        folder_name = os.path.basename(entry.path)
                        if FOLDER_PATTERN.match(folder_name):
                            candidates.append(entry.path)
        except Exception as e:
            print(f"Error scanning {parent_path}: {e}")
    
    return sorted(candidates)


class FolderRenamerGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Camera Folder Renamer")
        self.root.geometry("800x650")
        
        self.selected_path = None
        self.recursive_var = tk.BooleanVar(value=True)
        self.dry_run_var = tk.BooleanVar(value=True)
        self.include_model_var = tk.BooleanVar(value=True)
        self.merge_var = tk.BooleanVar(value=False)
        
        self._create_widgets()
    
    def _create_widgets(self):
        main_frame = tk.Frame(self.root, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        tk.Label(
            main_frame,
            text="Camera Folder Batch Renamer",
            font=("Arial", 16, "bold")
        ).pack(pady=(0, 10))
        
        # Path display
        self.path_label = tk.Label(
            main_frame,
            text="No folder selected",
            fg="blue",
            wraplength=700
        )
        self.path_label.pack(pady=10)

        # Options frame
        options_frame = tk.LabelFrame(main_frame, text="Options", padx=10, pady=10)
        options_frame.pack(fill=tk.X, pady=10)
        
        tk.Checkbutton(
            options_frame,
            text="Recursive mode (search all subfolders)",
            variable=self.recursive_var
        ).pack(anchor=tk.W)
        
        tk.Checkbutton(
            options_frame,
            text="Dry run (preview only, no changes)",
            variable=self.dry_run_var
        ).pack(anchor=tk.W)
        
        tk.Checkbutton(
            options_frame,
            text="Include camera model in folder name",
            variable=self.include_model_var
        ).pack(anchor=tk.W)
        
        tk.Checkbutton(
            options_frame,
            text="Merge into existing destination folders (safe merge with conflict resolution)",
            variable=self.merge_var
        ).pack(anchor=tk.W)

        # Buttons
        btn_frame = tk.Frame(main_frame)
        btn_frame.pack(pady=10)
        
        tk.Button(
            btn_frame,
            text="Select Parent Folder",
            command=self.select_folder,
            width=20
        ).pack(side=tk.LEFT, padx=5)
        
        self.run_btn = tk.Button(
            btn_frame,
            text="Start Renaming",
            command=self.rename_folders,
            width=20,
            state=tk.DISABLED,
            bg="#28a745",
            fg="white"
        )
        self.run_btn.pack(side=tk.LEFT, padx=5)

        # Log area
        log_frame = tk.Frame(main_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        scrollbar = tk.Scrollbar(log_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.log_text = tk.Text(
            log_frame,
            height=20,
            state=tk.DISABLED,
            font=("Courier New", 9),
            yscrollcommand=scrollbar.set
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.log_text.yview)

    def log(self, msg):
        """Thread-safe logging to text widget."""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def select_folder(self):
        """Open folder selection dialog."""
        folder = filedialog.askdirectory(title="Select Parent Folder")
        if folder:
            self.selected_path = folder
            self.path_label.config(text=folder)
            self.run_btn.config(state=tk.NORMAL)
            self.log(f"Selected directory: {folder}")

    def rename_folders(self):
        """Main rename operation with preview/confirmation."""
        if not self.selected_path:
            self.log("ERROR: No folder selected")
            return
        
        recursive = self.recursive_var.get()
        dry_run = self.dry_run_var.get()
        include_model = self.include_model_var.get()
        merge_enabled = self.merge_var.get()

        self.log(f"\n{'='*70}")
        self.log(f"Starting scan...")
        self.log(f"Mode: {'Recursive' if recursive else 'Non-recursive'}")
        self.log(f"Merge: {'Enabled' if merge_enabled else 'Disabled'}")
        self.log(f"{'='*70}\n")
        
        # Gather candidates
        candidates = gather_candidate_folders(self.selected_path, recursive)
        
        if not candidates:
            self.log("No folders matching NNNYMMDD pattern found.")
            messagebox.showinfo("No Changes", "No matching folders found.")
            return

        self.log(f"Found {len(candidates)} candidate folders\n")
        
        # Build rename/merge plan
        rename_plan = []
        skip_counts = {
            "pattern_mismatch": 0,
            "no_metadata": 0,
            "already_correct": 0,
            "destination_exists": 0
        }
        
        for old_path in candidates:
            new_path, status = compute_new_name(old_path, include_model)
            
            if status == "ok":
                rename_plan.append((old_path, new_path, "rename"))
            elif status == "merge":
                if merge_enabled:
                    rename_plan.append((old_path, new_path, "merge"))
                else:
                    skip_counts["destination_exists"] += 1
            else:
                skip_counts[status] = skip_counts.get(status, 0) + 1
        
        # Show preview
        self.log(f"Plan Summary:")
        self.log(f"  Renames: {sum(1 for _, _, a in rename_plan if a == 'rename')}")
        self.log(f"  Merges: {sum(1 for _, _, a in rename_plan if a == 'merge')}")
        for reason, count in skip_counts.items():
            if count > 0:
                self.log(f"  Skipped ({reason}): {count}")
        self.log("")
        
        # Preview first 15 operations
        preview_limit = 15
        for i, (old, new, action) in enumerate(rename_plan[:preview_limit]):
            action_str = "RENAME" if action == "rename" else "MERGE"
            self.log(f"  [{action_str}] {os.path.basename(old)} → {os.path.basename(new)}")
        
        if len(rename_plan) > preview_limit:
            self.log(f"  ... and {len(rename_plan) - preview_limit} more\n")
        
        if not rename_plan:
            self.log("Nothing to process.")
            return
        
        # Dry run check
        if dry_run:
            self.log("\n** DRY RUN MODE - No changes made **")
            messagebox.showinfo(
                "Dry Run Complete",
                f"Preview complete!\n\n"
                f"Would process {len(rename_plan)} folders\n"
                f"Uncheck 'Dry run' to apply changes"
            )
            return
        
        # Confirm execution
        confirm_msg = (
            f"About to process {len(rename_plan)} folders:\n\n"
            f"• {sum(1 for _, _, a in rename_plan if a == 'rename')} renames\n"
            f"• {sum(1 for _, _, a in rename_plan if a == 'merge')} merges\n\n"
            f"This cannot be undone. Continue?"
        )
        
        if not messagebox.askyesno("Confirm Operation", confirm_msg):
            self.log("\nOperation cancelled by user")
            return
        
        # Execute
        self.log(f"\n{'='*70}")
        self.log("Executing operations...")
        self.log(f"{'='*70}\n")
        
        success_count = 0
        error_count = 0
        
        for old_path, new_path, action in rename_plan:
            old_name = os.path.basename(old_path)
            new_name = os.path.basename(new_path)
            
            try:
                if action == "rename":
                    os.rename(old_path, new_path)
                    success_count += 1
                    self.log(f"✓ RENAMED: {old_name} → {new_name}")
                    
                elif action == "merge":
                    self.log(f"⚡ MERGING: {old_name} → {new_name}")
                    moved, skipped = safe_merge_folders(old_path, new_path, self.log)
                    
                    # Try to remove empty source folder
                    try:
                        os.rmdir(old_path)
                        self.log(f"✓ MERGED: Moved {moved} items, removed empty source")
                    except OSError:
                        self.log(f"✓ MERGED: Moved {moved} items (source folder not empty)")
                    
                    success_count += 1
                
                # Add camera model to database if detected
                if include_model:
                    _, raw_model, _ = extract_folder_metadata(new_path)
                    if raw_model and raw_model != "UnknownCamera":
                        add_camera_model(raw_model)
                        
            except Exception as e:
                error_count += 1
                self.log(f"✗ ERROR: {old_name}: {str(e)}")
        
        self.log(f"\n{'='*70}")
        self.log(f"Operation Complete!")
        self.log(f"  Success: {success_count}")
        self.log(f"  Errors: {error_count}")
        self.log(f"{'='*70}")
        
        messagebox.showinfo(
            "Complete",
            f"Processing finished!\n\n"
            f"Successful: {success_count}\n"
            f"Errors: {error_count}"
        )
    
    def run(self):
        """Start the GUI main loop."""
        self.root.mainloop()


def main():
    app = FolderRenamerGUI()
    app.run()


if __name__ == "__main__":
    main()
