"""
Unified metadata extraction for photos and videos.
Handles EXIF data, camera models, and creation dates.
"""
import os
import re
from datetime import datetime
from pathlib import Path
import exifread
from PIL import Image


def get_creation_date(file_path: str) -> str:
    """Extract creation date as YYYY-MM-DD."""
    # Try EXIF first
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, stop_tag="EXIF DateTimeOriginal", details=False)
            dt_str = tags.get("EXIF DateTimeOriginal")
            if dt_str:
                return str(dt_str)[:10].replace(':', '-')
    except Exception:
        pass
    
    # Try Pillow
    try:
        with Image.open(file_path) as img:
            exif = img.getexif()
            if exif and 36867 in exif:  # DateTimeOriginal
                return exif[36867][:10].replace(':', '-')
    except Exception:
        pass
    
    # Fallback to mtime
    return datetime.fromtimestamp(os.path.getmtime(file_path)).strftime('%Y-%m-%d')


def get_camera_model(file_path: str) -> str:
    """Extract camera model with video XML fallback."""
    ext = Path(file_path).suffix.upper()
    
    # Try ExifRead (best for RAW/JPG)
    try:
        with open(file_path, 'rb') as f:
            tags = exifread.process_file(f, stop_tag="Image Model", details=False)
            model = tags.get("Image Model")
            if model:
                return str(model).replace('/', '_').replace(' ', '_')
    except Exception:
        pass
    
    # Try Pillow (for TIFF/general)
    try:
        with Image.open(file_path) as img:
            exif = img.getexif()
            if exif and 272 in exif:  # Model tag
                return str(exif[272]).replace('/', '_').replace(' ', '_')
    except Exception:
        pass
    
    # Video XML fallback (Sony/GoPro)
    if ext in {'.MP4', '.MOV'}:
        base = os.path.splitext(file_path)[0]
        for suffix in ['M01.XML', '.XML']:
            xml_path = base + suffix
            if os.path.exists(xml_path):
                try:
                    with open(xml_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        match = re.search(r'modelName="([^"]+)"', content)
                        if match:
                            return match.group(1).replace('/', '_').replace(' ', '_')
                except Exception:
                    pass
    
    return "UnknownCamera"
