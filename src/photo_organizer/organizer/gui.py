"""
Photo & Video Organizer GUI
A graphical interface for organizing photos and videos by date and camera model.
"""
import os
import tkinter as tk
from tkinter import filedialog
from photo_organizer.organizer.core import organize_photos
from photo_organizer.shared.camera_models import get_camera_models
from photo_organizer.shared.config import ALL_EXTENSIONS


def main():
    root = tk.Tk()
    root.eval('tk::PlaceWindow . center')
    root.title("Photo Organizer")
    root.geometry("370x600")

    label = tk.Label(root, text="Organizes photos by date", pady=10)
    label.pack()

    by_camera_model_var = tk.BooleanVar(value=False)
    checkbox = tk.Checkbutton(
        root, text="Organize by camera model", variable=by_camera_model_var)
    checkbox.pack(pady=5)

    add_model_to_folder_var = tk.BooleanVar(value=True)
    add_model_checkbox = tk.Checkbutton(
        root, text="Add camera model to folder name", variable=add_model_to_folder_var)
    add_model_checkbox.pack(pady=5)

    separate_photos_videos_var = tk.BooleanVar(value=False)
    separate_photos_videos_checkbox = tk.Checkbutton(
        root, text="Separate photos & videos", variable=separate_photos_videos_var)
    separate_photos_videos_checkbox.pack(pady=5)

    media_type_var = tk.StringVar(value="photos")
    media_frame = tk.LabelFrame(root, text="Organize:")
    media_frame.pack(pady=5)
    tk.Radiobutton(media_frame, text="Photos only",
                   variable=media_type_var, value="photos").pack(anchor="w")
    tk.Radiobutton(media_frame, text="Videos only",
                   variable=media_type_var, value="videos").pack(anchor="w")
    tk.Radiobutton(media_frame, text="Photos and Videos",
                   variable=media_type_var, value="both").pack(anchor="w")

    camera_model_frame = tk.LabelFrame(root, text="Camera Model:")
    camera_model_frame.pack(pady=5)

    camera_models = get_camera_models()
    camera_models_display = ["Select camera type"] + camera_models
    selected_camera_model = tk.StringVar(value="Select camera type")
    camera_model_dropdown = tk.OptionMenu(
        camera_model_frame, selected_camera_model, *camera_models_display)
    camera_model_dropdown.pack(anchor="center", pady=10)

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
                             for ext in ALL_EXTENSIONS))
            path_label.config(
                text=f"Selected: {folder_path}\nTotal items: {count}")
        print(f"Selected folder: {folder_path}")

    def start_organizing():
        folder_path = selected_folder['path']
        if folder_path:
            print(
                f"[Sanity Check] Selected folder for organizing: {folder_path}")
            by_camera_model = by_camera_model_var.get()
            add_model_to_folder = add_model_to_folder_var.get()
            media_type = media_type_var.get()
            separate_photos_videos = separate_photos_videos_var.get()
            organize_photos(folder_path, by_camera_model=by_camera_model,
                            add_model_to_folder=add_model_to_folder,
                            media_type=media_type,
                            separate_photos_videos=separate_photos_videos)
            path_label.config(text=f"Organized: {folder_path}")
        else:
            path_label.config(text="No folder selected to organize.")

    select_button = tk.Button(
        root, text="Select Folder", command=select_folder_only)
    select_button.pack(pady=5)

    start_button = tk.Button(root, text="Start organizing",
                             command=start_organizing)
    start_button.pack(pady=5)

    root.mainloop()


if __name__ == "__main__":
    main()
