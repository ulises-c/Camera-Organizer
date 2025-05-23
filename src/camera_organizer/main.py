# Photo Organizer by Date
# Supported formats: .HIF, .ARW, .JPG
# Uses Tkinter for folder selection

import os
import shutil
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
import exifread
import tkinter.ttk as ttk
import subprocess
import sys
from camera_models_db import get_camera_models, add_camera_model
from helper_tools.tk_tooltip import ToolTip

# Supported file extensions
# Tested with Sony a6700, GoPro Hero 8 Black, iPhone 14 Pro Max, Sony RX100 VII
# Video file extensions and their extras
video_extensions = ['.MP4', '.MOV']
# extra files generated by cameras
video_extensions_extras = ['.XML', '.THM', '.LRV']
video_extensions += video_extensions_extras
# Photos file extensions
photo_extensions = ['.HIF', '.ARW', '.JPG']
# Combine all extensions into a single list
extensions = video_extensions + photo_extensions

# Known camera models
# Example list of known camera models
camera_models = get_camera_models()


def get_creation_date(file_path):
    """Returns the file's creation date in YYYY-MM-DD format."""
    timestamp = os.path.getmtime(file_path)
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')


def get_camera_model(file_path):
    """Extracts the camera model from image EXIF metadata or accompanying XML for videos. Returns 'UnknownCamera' if not found."""
    import re
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(
                f, stop_tag="Image Model", details=False)
            model = tags.get("Image Model")
            if model:
                # Clean up model string for folder naming
                return str(model).replace('/', '_').replace(' ', '_')
    except Exception:
        pass
    # If not found and is a video file, try to find and parse XML
    ext = os.path.splitext(file_path)[1].upper()
    video_exts = [ext.upper() for ext in video_extensions]
    if ext in video_exts:
        base, _ = os.path.splitext(file_path)
        xml_path = base + 'M01.XML'  # Sony convention: C0063.MP4 -> C0063M01.XML
        if not os.path.exists(xml_path):
            # Try just .XML (GoPro, etc.)
            # BUG: Some cameras do not have the XML file so this will fail
            xml_path = base + '.XML'
        if os.path.exists(xml_path):
            try:
                with open(xml_path, 'r', encoding='utf-8') as xf:
                    xml_content = xf.read()
                    # Look for <Device ... modelName="..." .../>
                    match = re.search(
                        r'<Device [^>]*modelName="([^"]+)"', xml_content)
                    if match:
                        return match.group(1).replace('/', '_').replace(' ', '_')
            except Exception:
                pass
    return "UnknownCamera"


def organize_photos(folder_path, by_camera_model=True, add_model_to_folder=False, media_type="both", separate_photos_videos=True):
    print("\n")
    print(
        f"Organize with camera model as parent folder (T/F): {by_camera_model}")
    print(f"Add camera model to folder name (T/F): {add_model_to_folder}")
    print(f"Media type to organize: {media_type}")
    print(f"Separate photos and videos: {separate_photos_videos}")
    print("\n")

    # Use global extension lists
    photo_exts = [ext.upper() for ext in photo_extensions]
    video_exts = [ext.upper() for ext in video_extensions]
    all_exts = [ext.upper() for ext in extensions]

    # Filter extensions based on media_type
    if media_type == "photos":
        valid_exts = photo_exts
    elif media_type == "videos":
        # NOTE: Other file types are created when video is recorded and should be grouped with the video files.
        # NOTE: There is usually a shared base string with the video file
        # NOTE: e.g. GH010038.THM and GH010038.MP4 and GL010038.LRV - for GoPro Hero 8 Black
        # NOTE: e.g. C0063.MP4 and C0063M01.XML - for Sony cameras
        valid_exts = video_exts
    else:
        valid_exts = all_exts

    # Helper: get MP4 base for video extras
    def get_mp4_base(filename):
        # Handles Sony: C0063M01.XML -> C0063.MP4, GoPro: GH010038.LRV -> GH010038.MP4
        name, ext = os.path.splitext(filename)
        if ext.upper() in video_extensions_extras:
            # Remove known suffixes (Sony: M01, GoPro: LRV/THM)
            if name.endswith('M01'):
                name = name[:-3]
            elif name.endswith('LRV') or name.endswith('THM'):
                name = name[:-3]
        return name

    known_files = {}
    mp4_dest_map = {}
    detected_models = set()
    # First pass: build known_files for all modes
    for root, _, files in os.walk(folder_path):
        for file in files:
            ext = os.path.splitext(file)[1].upper()
            if ext in valid_exts:
                file_path = os.path.join(root, file)
                date_folder = get_creation_date(file_path)
                camera_model = get_camera_model(file_path)
                basename, _ = os.path.splitext(file)
                if camera_model != "UnknownCamera":
                    detected_models.add(camera_model)
                # Set media_type_folder only if separating photos/videos
                if separate_photos_videos:
                    if ext in photo_exts:
                        media_type_folder = "photos"
                    elif ext in video_exts:
                        media_type_folder = "videos"
                    else:
                        media_type_folder = "other"
                    if add_model_to_folder and camera_model != "UnknownCamera":
                        media_type_folder = f"{media_type_folder}_{camera_model}"
                else:
                    media_type_folder = None
                if camera_model != "UnknownCamera":
                    if by_camera_model and add_model_to_folder:
                        dest_folder = os.path.join(
                            folder_path, camera_model, media_type_folder, f"{date_folder}_{camera_model}") if separate_photos_videos else os.path.join(folder_path, camera_model, f"{date_folder}_{camera_model}")
                    elif by_camera_model:
                        dest_folder = os.path.join(
                            folder_path, camera_model, media_type_folder, date_folder) if separate_photos_videos else os.path.join(folder_path, camera_model, date_folder)
                    elif add_model_to_folder:
                        dest_folder = os.path.join(
                            folder_path, media_type_folder, f"{date_folder}_{camera_model}") if separate_photos_videos else os.path.join(folder_path, f"{date_folder}_{camera_model}")
                    else:
                        dest_folder = os.path.join(
                            folder_path, media_type_folder, date_folder) if separate_photos_videos else os.path.join(folder_path, date_folder)
                    known_files[(basename, date_folder)] = dest_folder
                    # For MP4, also map its base for extras
                    if ext == '.MP4':
                        mp4_base = basename
                        mp4_dest_map[(mp4_base, date_folder)] = dest_folder

    # Second pass: move files
    for root, _, files in os.walk(folder_path):
        print(f"Checking folder: {root} | Files: {len(files)}")
        counter = 0
        for file in files:
            ext = os.path.splitext(file)[1].upper()
            if ext in valid_exts:
                counter += 1
                file_path = os.path.join(root, file)
                date_folder = get_creation_date(file_path)
                camera_model = get_camera_model(file_path)
                if camera_model != "UnknownCamera":
                    detected_models.add(camera_model)
                basename, _ = os.path.splitext(file)
                if separate_photos_videos:
                    if ext in photo_exts:
                        media_type_folder = "photos"
                    elif ext in video_exts:
                        media_type_folder = "videos"
                    else:
                        media_type_folder = "other"
                    if add_model_to_folder and camera_model != "UnknownCamera":
                        media_type_folder = f"{media_type_folder}_{camera_model}"
                else:
                    media_type_folder = None
                dest_folder = None
                # Unified logic for .HIF with UnknownCamera
                if camera_model == "UnknownCamera" and ext == ".HIF":
                    dest_folder = known_files.get((basename, date_folder))
                    if dest_folder is None:
                        dest_folder = os.path.join(
                            folder_path, camera_model, media_type_folder, f"{date_folder}_{camera_model}")
                # For video extras, use MP4's destination if possible
                elif ext in ['.XML', '.THM', '.LRV']:
                    mp4_base = get_mp4_base(basename)
                    dest_folder = mp4_dest_map.get((mp4_base, date_folder))
                    if not dest_folder:
                        # fallback to normal logic
                        if by_camera_model and add_model_to_folder:
                            dest_folder = os.path.join(
                                folder_path, camera_model, media_type_folder, f"{date_folder}_{camera_model}") if separate_photos_videos else os.path.join(folder_path, camera_model, f"{date_folder}_{camera_model}")
                        elif by_camera_model:
                            dest_folder = os.path.join(
                                folder_path, camera_model, media_type_folder, date_folder) if separate_photos_videos else os.path.join(folder_path, camera_model, date_folder)
                        elif add_model_to_folder:
                            dest_folder = os.path.join(
                                folder_path, media_type_folder, f"{date_folder}_{camera_model}") if separate_photos_videos else os.path.join(folder_path, f"{date_folder}_{camera_model}")
                        else:
                            dest_folder = os.path.join(
                                folder_path, media_type_folder, date_folder) if separate_photos_videos else os.path.join(folder_path, date_folder)
                else:
                    if by_camera_model and add_model_to_folder:
                        dest_folder = os.path.join(
                            folder_path, camera_model, media_type_folder, f"{date_folder}_{camera_model}") if separate_photos_videos else os.path.join(folder_path, camera_model, f"{date_folder}_{camera_model}")
                    elif by_camera_model:
                        dest_folder = os.path.join(
                            folder_path, camera_model, media_type_folder, date_folder) if separate_photos_videos else os.path.join(folder_path, camera_model, date_folder)
                    elif add_model_to_folder:
                        dest_folder = os.path.join(
                            folder_path, media_type_folder, f"{date_folder}_{camera_model}") if separate_photos_videos else os.path.join(folder_path, f"{date_folder}_{camera_model}")
                    else:
                        dest_folder = os.path.join(
                            folder_path, media_type_folder, date_folder) if separate_photos_videos else os.path.join(folder_path, date_folder)
                os.makedirs(dest_folder, exist_ok=True)
                shutil.move(file_path, os.path.join(dest_folder, file))
        print(f"Total files moved: {counter}")
        print(f"Finished checking folder: {root}")
    # After organizing, update camera model database
    db_models = set(get_camera_models())
    new_models = detected_models - db_models
    for model in new_models:
        add_camera_model(model)


# GUI for folder selection


def select_folder(by_camera_model_var=None):
    folder_path = filedialog.askdirectory(title='Select Folder to Organize')
    if folder_path:
        by_camera_model = by_camera_model_var.get() if by_camera_model_var else True
        organize_photos(folder_path, by_camera_model=by_camera_model)
        print("Organization complete.")


def launch_folder_renamer_gui():
    import os
    import sys
    import subprocess
    script_path = os.path.join(os.path.dirname(
        __file__), 'folder_renamer_gui.py')
    subprocess.Popen([sys.executable, script_path])


if __name__ == "__main__":
    import tkinter as tk
    import subprocess
    import sys
    import os

    def launch_gui(script_name):
        script_path = os.path.join(os.path.dirname(__file__), script_name)
        subprocess.Popen([sys.executable, script_path])

    def main():
        root = tk.Tk()
        root.eval('tk::PlaceWindow . center')
        root.title("Camera Organizer Launcher")
        root.geometry("350x450")
        # Center the window on the screen
        root.update_idletasks()
        label = tk.Label(root, text="Choose a tool to launch:", pady=10)
        label.pack()
        # Add a label with a description
        desc_label = tk.Label(root, text="Organizer: Organize photos/videos by date and camera model.\nBatch Renamer: Rename files/folders with 'UnknownCamera'.",
                              wraplength=320, justify="left", fg="gray")
        desc_label.pack(pady=(0, 10))
        
        # Button - Open Organizer GUI
        org_btn = tk.Button(root, text="Photo & Video Organizer", width=30,
                            command=lambda: launch_gui("organizer_gui.py"))
        org_btn.pack(pady=10)
        ToolTip(org_btn, "Organize photos and videos by date and camera model.")
        
        # Button - Open Batch Renamer GUI (renames UnknownCamera)
        ren_btn = tk.Button(root, text="Batch Renamer for 'UnknownCamera'",
                            width=30, command=lambda: launch_gui("renamer_gui.py"))
        ren_btn.pack(pady=10)
        ToolTip(
            ren_btn, "Batch rename files/folders with 'UnknownCamera' in their name.")
        
        # Button - Open Folder Renamer GUI
        folder_renamer_btn = tk.Button(
            root, text="Camera Folder Renamer", width=30, command= lambda: launch_gui("folder_renamer_gui.py"))
        folder_renamer_btn.pack(pady=10)
        ToolTip(folder_renamer_btn, "Rename camera folders (NNNYMMDD → YYYY-MM-DD[_CameraModel])")

        root.mainloop()

    main()
