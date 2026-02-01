"""
Photo & Video Organizer - Core Logic
Organizes files by date and camera model with various options.
"""
import os
import shutil
from pathlib import Path
from photo_organizer.shared.metadata import get_creation_date, get_camera_model
from photo_organizer.shared.camera_models import get_camera_models, add_camera_model
from photo_organizer.shared.config import (
    VIDEO_EXTENSIONS, VIDEO_EXTENSIONS_EXTRAS, PHOTO_EXTENSIONS, ALL_EXTENSIONS
)


def organize_photos(
    folder_path: str,
    by_camera_model: bool = True,
    add_model_to_folder: bool = False,
    media_type: str = "both",
    separate_photos_videos: bool = True
):
    """
    Organize photos and videos by date and camera model.
    
    Args:
        folder_path: Root directory to organize
        by_camera_model: Create camera model parent folders
        add_model_to_folder: Add camera model suffix to date folders
        media_type: "photos", "videos", or "both"
        separate_photos_videos: Create separate photos/videos subdirectories
    """
    print("\n")
    print(f"Organize with camera model as parent folder (T/F): {by_camera_model}")
    print(f"Add camera model to folder name (T/F): {add_model_to_folder}")
    print(f"Media type to organize: {media_type}")
    print(f"Separate photos and videos: {separate_photos_videos}")
    print("\n")

    # Use extension lists from config
    photo_exts = [ext.upper() for ext in PHOTO_EXTENSIONS]
    video_exts = [ext.upper() for ext in VIDEO_EXTENSIONS]
    all_exts = [ext.upper() for ext in ALL_EXTENSIONS]

    # Filter extensions based on media_type
    if media_type == "photos":
        valid_exts = photo_exts
    elif media_type == "videos":
        valid_exts = video_exts
    else:
        valid_exts = all_exts

    # Helper: get MP4 base for video extras
    def get_mp4_base(filename):
        # Handles Sony: C0063M01.XML -> C0063.MP4, GoPro: GH010038.LRV -> GH010038.MP4
        name, ext = os.path.splitext(filename)
        if ext.upper() in VIDEO_EXTENSIONS_EXTRAS:
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
