# Photo Organizer by Date
# Supported formats: .HIF, .ARW, .JPG
# Uses Tkinter for folder selection

import os
import shutil
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
import exifread

# Supported file extensions
extensions_sony = ['.HIF', '.ARW', '.JPG', '.MP4', '.XML']
extensions_gopro = ['.JPG', '.MP4', '.THM', '.LRV']
extensions_iphone = ['.HEIC', '.MOV']
# Combine all extensions into a single list
extensions = extensions_sony + extensions_gopro + extensions_iphone

def get_creation_date(file_path):
    """Returns the file's creation date in YYYY-MM-DD format."""
    timestamp = os.path.getmtime(file_path)
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')


def get_camera_model(file_path):
    """Extracts the camera model from image EXIF metadata. Returns 'UnknownCamera' if not found."""
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(
                f, stop_tag="Image Model", details=False)
            model = tags.get("Image Model")
            if model:
                # Clean up model string for folder naming
                return str(model).replace('/', '_').replace(' ', '_')
    except Exception as e:
        pass
    return "UnknownCamera"


def organize_photos(folder_path, by_camera_model=True, add_model_to_folder=False):
    # Map (basename, date) -> destination_folder for known camera models
    print(
        f"\n\nOrganize with camera model as parent folder (T/F): {by_camera_model}")
    print(f"Add camera model to folder name (T/F): {add_model_to_folder}\n\n")

    known_files = {}
    # First pass: build known_files for all modes
    for root, _, files in os.walk(folder_path):
        for file in files:
            if any(file.upper().endswith(ext) for ext in extensions):
                file_path = os.path.join(root, file)
                date_folder = get_creation_date(file_path)
                camera_model = get_camera_model(file_path)
                basename, ext = os.path.splitext(file)
                if camera_model != "UnknownCamera":
                    # Determine destination folder for known_files mapping
                    if by_camera_model and add_model_to_folder:
                        dest_folder = os.path.join(
                            folder_path, camera_model, f"{date_folder}_{camera_model}")
                    elif add_model_to_folder:
                        dest_folder = os.path.join(
                            folder_path, f"{date_folder}_{camera_model}")
                    elif by_camera_model:
                        dest_folder = os.path.join(
                            folder_path, camera_model, date_folder)
                    else:
                        dest_folder = os.path.join(folder_path, date_folder)
                    known_files[(basename, date_folder)] = dest_folder

    # Second pass: move files
    for root, _, files in os.walk(folder_path):
        print(f"Checking folder: {root} | Files: {len(files)}")
        counter = 0
        for file in files:
            if any(file.upper().endswith(ext) for ext in extensions):
                counter += 1
                file_path = os.path.join(root, file)
                date_folder = get_creation_date(file_path)
                camera_model = get_camera_model(file_path)
                basename, ext = os.path.splitext(file)
                dest_folder = None
                # Unified logic for .HIF with UnknownCamera
                if camera_model == "UnknownCamera" and ext.upper() == ".HIF":
                    dest_folder = known_files.get((basename, date_folder))
                    if dest_folder is None:
                        # fallback to default logic
                        if by_camera_model and add_model_to_folder:
                            dest_folder = os.path.join(
                                folder_path, camera_model, f"{date_folder}_{camera_model}")
                        elif add_model_to_folder:
                            dest_folder = os.path.join(
                                folder_path, f"{date_folder}_{camera_model}")
                        elif by_camera_model:
                            dest_folder = os.path.join(
                                folder_path, camera_model, date_folder)
                        else:
                            dest_folder = os.path.join(
                                folder_path, date_folder)
                else:
                    if by_camera_model and add_model_to_folder and camera_model:
                        dest_folder = os.path.join(
                            folder_path, camera_model, f"{date_folder}_{camera_model}")
                    elif add_model_to_folder and camera_model:
                        dest_folder = os.path.join(
                            folder_path, f"{date_folder}_{camera_model}")
                        print(
                            f"[Sanity Check] Folder will be named: {date_folder}_{camera_model}")
                    elif by_camera_model:
                        dest_folder = os.path.join(
                            folder_path, camera_model, date_folder)
                    else:
                        dest_folder = os.path.join(folder_path, date_folder)
                os.makedirs(dest_folder, exist_ok=True)
                shutil.move(file_path, os.path.join(dest_folder, file))
                print(f"Moved {file} to {dest_folder}")
        print(f"Total files moved: {counter}")
        print(f"Finished checking folder: {root}")

# GUI for folder selection


def select_folder(by_camera_model_var=None):
    folder_path = filedialog.askdirectory(title='Select Folder to Organize')
    if folder_path:
        by_camera_model = by_camera_model_var.get() if by_camera_model_var else True
        organize_photos(folder_path, by_camera_model=by_camera_model)
        print("Organization complete.")


if __name__ == "__main__":
    # Photo Organizer by Date
    # Supported formats: .HIF, .ARW, .JPG
    # Uses Tkinter for folder selection

    root = tk.Tk()
    root.eval('tk::PlaceWindow . center')
    root.title("Photo Organizer")
    root.geometry("300x250")

    label = tk.Label(root, text="Organizes photos by date", pady=10)
    label.pack()

    # Checkbox for camera model organization
    by_camera_model_var = tk.BooleanVar(value=False)
    checkbox = tk.Checkbutton(
        root, text="Organize by camera model", variable=by_camera_model_var)
    checkbox.pack(pady=5)

    # Checkbox for adding camera model to folder name
    # Format: (YYYY-MM-DD_CameraModel)
    add_model_to_folder_var = tk.BooleanVar(value=True)
    add_model_checkbox = tk.Checkbutton(
        root, text="Add camera model to folder name", variable=add_model_to_folder_var)
    add_model_checkbox.pack(pady=5)

    path_label = tk.Label(root, text="No folder selected",
                          wraplength=280, pady=5)
    path_label.pack()

    selected_folder = {'path': None}

    def select_folder_only():
        folder_path = filedialog.askdirectory(title='Select Folder')
        if folder_path:
            selected_folder['path'] = folder_path
            count = 0
            for root_dir, _, files in os.walk(folder_path):
                count += sum(1 for file in files if any(file.upper().endswith(ext)
                             for ext in extensions))
            path_label.config(
                text=f"Selected: {folder_path}\nTotal items: {count}")

    def start_organizing():
        folder_path = selected_folder['path']
        if folder_path:
            by_camera_model = by_camera_model_var.get()
            add_model_to_folder = add_model_to_folder_var.get()
            organize_photos(folder_path, by_camera_model=by_camera_model,
                            add_model_to_folder=add_model_to_folder)
            path_label.config(text=f"Organized: {folder_path}")
        else:
            path_label.config(text="No folder selected to organize.")

    select_button = tk.Button(
        root, text="Select Folder", command=select_folder_only)
    select_button.pack(pady=5)

    start_button = tk.Button(root, text="Start organizing",
                             command=start_organizing)
    start_button.pack(pady=20)

    root.mainloop()
