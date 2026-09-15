"""Video converter module: Log→Rec709 colorspace conversion + share compression.

`engine.py` holds all logic (UI-agnostic, uniform engine signature) and shells
out to ffmpeg/ffprobe. `cli.py` is a thin front-end; a PySide6 panel will call
the same `process_video_folder` engine. No tkinter.
"""
from photo_organizer.video_converter.engine import (
    DEFAULT_OPTIONS,
    OpDetail,
    VideoResult,
    process_video_folder,
    save_report,
    verify_color_tags,
)

__all__ = [
    "DEFAULT_OPTIONS",
    "OpDetail",
    "VideoResult",
    "process_video_folder",
    "save_report",
    "verify_color_tags",
]
