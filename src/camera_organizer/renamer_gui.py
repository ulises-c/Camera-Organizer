"""
Batch Renamer for Unknown Cameras
--------------------------------
A graphical interface for batch renaming files and folders containing 'UnknownCamera' in their name.

Features:
- Dropdown menu to select a known camera model
- Renames all files/folders with 'UnknownCamera' to the selected model
- Uses shared camera model list from main.py

Usage:
Run this script to launch the batch renamer GUI.
"""

import os
import tkinter as tk
from tkinter import filedialog
from main import extensions
from camera_models_db import get_camera_models
import subprocess
import sys


def main():
    root = tk.Tk()
    root.eval('tk::PlaceWindow . center')
    root.title("Batch Rename Unknown Cameras")
    root.geometry("370x450")

    camera_model_frame = tk.LabelFrame(
        root, text="Batch Rename Unknown Cameras")
    camera_model_frame.pack(pady=10, fill='x')
    tk.Label(camera_model_frame, text="Select camera model:").pack(anchor="w")
    camera_models = get_camera_models()
    camera_models_display = ["Select camera type"] + camera_models
    selected_camera_model = tk.StringVar(value="Select camera type")
    camera_model_dropdown = tk.OptionMenu(
        camera_model_frame, selected_camera_model, *camera_models_display)
    camera_model_dropdown.pack(anchor="center", pady=5)

    # Radio buttons for choosing rename mode
    rename_mode_var = tk.StringVar(value="dropdown")
    radio_frame = tk.Frame(camera_model_frame)
    radio_frame.pack(anchor="w", pady=2)
    tk.Radiobutton(radio_frame, text="Use dropdown",
                   variable=rename_mode_var, value="dropdown").pack(side="left")
    tk.Radiobutton(radio_frame, text="Use custom name",
                   variable=rename_mode_var, value="custom").pack(side="left")

    tk.Label(camera_model_frame, text="Or enter custom name:").pack(anchor="w")
    custom_name_entry = tk.Entry(camera_model_frame)
    custom_name_entry.pack(anchor="center", pady=5)

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
        print(f"Selected folder: {folder_path}")

    def batch_rename_unknown_cameras():
        folder_path = selected_folder['path']
        if not folder_path:
            path_label.config(text="No folder selected for renaming.")
            return
        print(
            f"[Sanity Check] Selected folder for batch renaming: {folder_path}")
        rename_mode = rename_mode_var.get()
        if rename_mode == "custom":
            model = custom_name_entry.get().strip()
        else:
            model = selected_camera_model.get()
        if not model or model == "Select camera type":
            path_label.config(text="Please select or enter a camera model.")
            return
        renamed_count = 0
        for root, dirs, files in os.walk(folder_path):
            for name in files + dirs:
                if "UnknownCamera" in name:
                    old_path = os.path.join(root, name)
                    new_name = name.replace("UnknownCamera", model)
                    new_path = os.path.join(root, new_name)
                    if os.path.isdir(old_path):
                        if os.path.exists(new_path):
                            # Move contents from old_path to new_path
                            for item in os.listdir(old_path):
                                src_item = os.path.join(old_path, item)
                                dst_item = os.path.join(new_path, item)
                                if os.path.exists(dst_item):
                                    continue  # Skip if already exists
                                os.rename(src_item, dst_item)
                            try:
                                os.rmdir(old_path)
                            except OSError:
                                pass  # Directory not empty or error
                        else:
                            os.rename(old_path, new_path)
                        renamed_count += 1
                    else:
                        os.rename(old_path, new_path)
                        renamed_count += 1
        path_label.config(
            text=f"Renamed {renamed_count} items to {model}.")

    select_button = tk.Button(
        root, text="Select Folder", command=select_folder_only)
    select_button.pack(pady=5)

    batch_rename_button = tk.Button(
        root, text="Batch Rename Unknown Cameras", command=batch_rename_unknown_cameras)
    batch_rename_button.pack(pady=5)

    root.mainloop()


if __name__ == "__main__":
    main()
