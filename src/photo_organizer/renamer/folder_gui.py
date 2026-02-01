"""
Folder Renamer for Camera-Generated Folders
A GUI to rename camera-generated folders (NNNYMMDD) to the convention YYYY-MM-DD[_CameraModel].
"""
import os
import re
import tkinter as tk
from tkinter import filedialog
from photo_organizer.shared.metadata import get_creation_date, get_camera_model


def extract_date_and_model(folder_path):
    """Extract creation date and camera model from files in folder."""
    files = []
    for root, _, fs in os.walk(folder_path):
        for file in fs:
            files.append(os.path.join(root, file))
    if not files:
        return None, None, None
    files.sort()
    n = len(files)
    indices = [0, n // 2, n - 1] if n > 2 else list(range(n))
    results = []
    for idx in indices:
        # Move up/down if metadata can't be extracted
        i = idx
        while 0 <= i < n:
            file_path = files[i]
            try:
                date = get_creation_date(file_path)
                model = get_camera_model(file_path)
                if date:
                    results.append((date, model, file_path))
                    break
            except Exception:
                pass
            # Try next file (down for first/middle, up for last)
            if idx == n - 1:
                i -= 1
            else:
                i += 1
        else:
            results.append((None, None, None))
    return results


def main():
    root = tk.Tk()
    root.eval('tk::PlaceWindow . center')
    root.title("Folder Renamer (Camera Folders)")
    root.geometry("420x400")

    label = tk.Label(
        root, text="Rename camera folders (NNNYMMDD → YYYY-MM-DD[_CameraModel])", wraplength=400, pady=10)
    label.pack()

    path_label = tk.Label(
        root, text="No parent folder selected", wraplength=400, pady=5)
    path_label.pack()

    selected_folder = {'path': None}

    def select_folder():
        folder_path = filedialog.askdirectory(title='Select Parent Folder')
        if folder_path:
            selected_folder['path'] = folder_path
            path_label.config(text=f"Selected: {folder_path}")
            print(f"Selected folder: {folder_path}")

    def rename_folders():
        parent = selected_folder['path']
        print(f"[DEBUG] Parent folder selected: {parent}")
        if not parent:
            path_label.config(text="No parent folder selected.")
            print("[DEBUG] No parent folder selected.")
            return
        count = 0
        # Only operate on the selected directory itself
        name = os.path.basename(parent)
        folder_path = parent
        print(f"[DEBUG] Checking: {folder_path}")
        if not os.path.isdir(folder_path):
            print(f"[DEBUG] Skipped (not a directory): {folder_path}")
        else:
            # Match NNNYMMDD (e.g., 10050517)
            match = re.match(r"^(\d{3})(\d)(\d{2})(\d{2})$", name)
            print(f"[DEBUG] Regex match for '{name}': {match}")
            if match:
                nnn, y, mm, dd = match.groups()
                results = extract_date_and_model(folder_path)
                print(f"[DEBUG] Extracted results: {results}")
                # Only proceed if all 3 have a date
                if all(r[0] for r in results):
                    # Sanity check: compare YMMDD from folder name to each date
                    for idx, (date, model, file_path) in enumerate(results):
                        year, month, day = date.split('-')
                        y_from_date = year[-1]
                        if (y != y_from_date) or (mm != month) or (dd != day):
                            print(
                                f"[SANITY CHECK WARNING] File {file_path}: Folder YMMDD ({y}{mm}{dd}) does not match image date ({y_from_date}{month}{day})")
                    # Use the first hit for renaming
                    date, model, _ = results[0]
                    new_name = date
                    if model and model != "UnknownCamera":
                        new_name += f"_{model}"
                    new_path = os.path.join(os.path.dirname(parent), new_name)
                    print(
                        f"[DEBUG] Attempting to rename {folder_path} -> {new_path}")
                    if new_path == folder_path:
                        print(
                            f"[DEBUG] New path is same as old path for {folder_path}, skipping.")
                    elif os.path.exists(new_path):
                        print(
                            f"[DEBUG] Destination already exists: {new_path}, skipping.")
                    else:
                        try:
                            os.rename(folder_path, new_path)
                            print(
                                f"[DEBUG] Renamed {folder_path} -> {new_path}")
                            count += 1
                        except Exception as e:
                            print(
                                f"[DEBUG] Failed to rename {folder_path} -> {new_path}: {e}")
                else:
                    print(
                        f"[DEBUG] Not enough files with metadata for {folder_path}")
        path_label.config(text=f"Renamed {count} folders.")
        print(f"[DEBUG] Total folders renamed: {count}")

    select_button = tk.Button(
        root, text="Select Parent Folder", command=select_folder)
    select_button.pack(pady=5)

    rename_button = tk.Button(
        root, text="Rename Camera Folders", command=rename_folders)
    rename_button.pack(pady=5)

    root.mainloop()


if __name__ == "__main__":
    main()
