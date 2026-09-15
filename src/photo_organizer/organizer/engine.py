"""Photo & Video Organizer — engine.

Extracted from the former tkinter `organizer` module into a UI-agnostic engine
with the uniform signature (source, options, progress_callback, log_callback).
Adds dry-run, cancellation, and progress reporting the original lacked.

Sorts files into date / camera-model folder structures. Video sidecar files
(.XML/.THM/.LRV) follow their parent .MP4's destination.
"""
from __future__ import annotations

import logging
import os
import shutil
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from photo_organizer.engine import OperationCancelled, check_cancel
from photo_organizer.shared.camera_models import add_camera_model, get_camera_models
from photo_organizer.shared.config import (
    ALL_EXTENSIONS,
    PHOTO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    VIDEO_EXTENSIONS_EXTRAS,
)
from photo_organizer.shared.metadata import get_camera_model, get_creation_date

logger = logging.getLogger(__name__)

DEFAULT_OPTIONS = {
    "dry_run": True,
    "destination": None,
    "recursive": True,
    "by_camera_model": True,
    "add_model_to_folder": False,
    "media_type": "both",             # "photos" | "videos" | "both"
    "separate_photos_videos": True,
}


@dataclass
class MoveOp:
    source: str
    dest: str
    status: str
    error: str = ""

    @property
    def success(self) -> bool:
        return self.status in {"planned", "moved"}


@dataclass
class OrganizeResult:
    ops: list[MoveOp] = field(default_factory=list)
    detected_models: list[str] = field(default_factory=list)
    planned: int = 0
    moved: int = 0
    skipped: int = 0
    failed: int = 0
    cancelled: bool = False
    database_error: str = ""


def _mp4_base(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    if ext.upper() in VIDEO_EXTENSIONS_EXTRAS and name.endswith(("M01", "LRV", "THM")):
        name = name[:-3]
    return name


def _safe_component(value: str, fallback: str) -> str:
    """Reduce a metadata string to a single safe path segment.

    Metadata (camera model, derived date) is untrusted: a value like ``..`` or
    ``../../escape`` must never traverse outside the destination root. Strip any
    path separators and reject empty / dot-only results.
    """
    leaf = os.path.basename(str(value).replace("\\", "/").rstrip("/"))
    if not leaf or leaf in {".", ".."}:
        return fallback
    return leaf


def _dest_folder(root: str, camera_model: str, media_folder, date_folder: str,
                 by_camera: bool, add_model: bool, separate: bool) -> str:
    """Compute a destination folder path from the option matrix."""
    if by_camera and add_model:
        tail = f"{date_folder}_{camera_model}"
        return (os.path.join(root, camera_model, media_folder, tail) if separate
                else os.path.join(root, camera_model, tail))
    if by_camera:
        return (os.path.join(root, camera_model, media_folder, date_folder) if separate
                else os.path.join(root, camera_model, date_folder))
    if add_model:
        tail = f"{date_folder}_{camera_model}"
        return (os.path.join(root, media_folder, tail) if separate
                else os.path.join(root, tail))
    return (os.path.join(root, media_folder, date_folder) if separate
            else os.path.join(root, date_folder))


def process_organize(source, options: dict,
                     progress_callback: Callable[[float], None],
                     log_callback: Callable[[str], None]) -> OrganizeResult:
    def _log(msg: str):
        (log_callback or logger.info)(msg)

    opts = {**DEFAULT_OPTIONS, **(options or {})}
    dry_run = opts["dry_run"]
    cancel_event = opts.get("cancel_event")
    by_camera = opts["by_camera_model"]
    recursive = opts["recursive"]

    add_model = opts["add_model_to_folder"]
    media_type = opts["media_type"]
    separate = opts["separate_photos_videos"]
    folder_path = str(source)
    destination_root = str(opts["destination"] or source)

    photo_exts = [e.upper() for e in PHOTO_EXTENSIONS]
    video_exts = [e.upper() for e in VIDEO_EXTENSIONS]
    all_exts = [e.upper() for e in ALL_EXTENSIONS]
    valid_exts = (photo_exts if media_type == "photos"
                  else video_exts if media_type == "videos"
                  else all_exts)

    _log(f"Scanning {folder_path} (dry_run={dry_run}) …")

    # Collect all target files first so we can report progress and build the
    # MP4→destination map for sidecar files.
    to_process: list[tuple[str, str, str, str]] = []  # (path, ext, basename, date)
    mp4_dest_map: dict[tuple[str, str], str] = {}
    detected_models: set[str] = set()

    cancelled_during_scan = False
    for root, _, files in os.walk(folder_path):
        if cancel_event is not None and cancel_event.is_set():
            cancelled_during_scan = True
            break
        for file in files:
            ext = os.path.splitext(file)[1].upper()
            if ext not in valid_exts:
                continue
            fp = os.path.join(root, file)
            date_folder = _safe_component(get_creation_date(fp), "UnknownDate")
            camera_model = _safe_component(get_camera_model(fp), "UnknownCamera")
            basename = os.path.splitext(file)[0]
            if camera_model != "UnknownCamera":
                detected_models.add(camera_model)
            to_process.append((fp, ext, basename, date_folder))
            if ext == ".MP4" and camera_model != "UnknownCamera":
                media_folder = "videos" if separate else None
                if separate and add_model:
                    media_folder = f"videos_{camera_model}"
                mp4_dest_map[(basename, date_folder)] = _dest_folder(
                    destination_root, camera_model, media_folder, date_folder,
                    by_camera, add_model, separate)
        if not recursive:
            break

    result = OrganizeResult()
    if cancelled_during_scan:
        result.cancelled = True
        result.detected_models = sorted(detected_models)
        _log("🛑 Process cancelled during scan.")
        return result

    total = len(to_process)
    if total == 0:
        if cancel_event is not None and cancel_event.is_set():
            result.cancelled = True
            return result
        _log("No matching files found.")
        return result

    try:
        reserved_destinations: set[Path] = set()
        moved_models: set[str] = set()
        for idx, (fp, ext, basename, date_folder) in enumerate(to_process, 1):
            check_cancel(cancel_event)
            camera_model = _safe_component(get_camera_model(fp), "UnknownCamera")

            if separate:
                media_folder = ("photos" if ext in photo_exts
                                else "videos" if ext in video_exts else "other")
                if add_model and camera_model != "UnknownCamera":
                    media_folder = f"{media_folder}_{camera_model}"
            else:
                media_folder = None

            # Sidecar files ride along with their MP4 when we know it.
            if ext in (".XML", ".THM", ".LRV"):
                dest = mp4_dest_map.get((_mp4_base(basename), date_folder))
                if not dest:
                    dest = _dest_folder(destination_root, camera_model, media_folder,
                                        date_folder, by_camera, add_model, separate)
            else:
                dest = _dest_folder(destination_root, camera_model, media_folder,
                                    date_folder, by_camera, add_model, separate)

            op = MoveOp(
                source=fp,
                dest=os.path.join(dest, os.path.basename(fp)),
                status="planned" if dry_run else "pending",
            )
            source_path = Path(op.source).resolve()
            destination_path = Path(op.dest).resolve()
            if source_path == destination_path:
                op.status = "skipped_already_organized"
                result.skipped += 1
                result.ops.append(op)
                progress_callback(idx / total * 100)
                continue
            if destination_path in reserved_destinations or destination_path.exists():
                op.status = "skipped_collision"
                result.skipped += 1
                result.ops.append(op)
                progress_callback(idx / total * 100)
                continue
            reserved_destinations.add(destination_path)
            try:
                if dry_run:
                    result.planned += 1
                else:
                    os.makedirs(dest, exist_ok=True)
                    shutil.move(fp, op.dest)
                    op.status = "moved"
                    result.moved += 1
                    if camera_model != "UnknownCamera":
                        moved_models.add(camera_model)
            except OperationCancelled:
                raise
            except Exception as e:
                op.status = "failed"
                op.error = str(e)
                result.failed += 1
                _log(f"  ✗ {os.path.basename(fp)}: {e}")
            result.ops.append(op)
            progress_callback(idx / total * 100)

    except OperationCancelled:
        _log("🛑 Process cancelled.")
        result.cancelled = True
        result.detected_models = sorted(detected_models)
        return result

    # Persist only camera models tied to files we actually moved. Never touch
    # the database in preview, and treat a persistence failure as non-fatal:
    # the media has already moved successfully.
    if not dry_run and moved_models:
        try:
            db_models = set(get_camera_models())
            for model in sorted(moved_models - db_models):
                add_camera_model(model)
        except Exception as e:
            result.database_error = str(e)
            _log(f"⚠️  Camera database not updated: {e}")

    result.detected_models = sorted(detected_models)
    _log(f"Complete. Moved {result.moved}, planned {result.planned}, "
         f"skipped {result.skipped}, failed {result.failed}.")
    return result


def save_report(result: OrganizeResult, output_path: Path) -> None:
    data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {"planned": result.planned, "moved": result.moved,
                    "skipped": result.skipped, "failed": result.failed,
                    "cancelled": result.cancelled,
                    "detected_models": result.detected_models},
        "ops": [asdict(o) for o in result.ops],
    }
    try:
        Path(output_path).write_text(__import__("json").dumps(data, indent=2))
    except Exception as e:
        logger.error(f"Failed to save report: {e}")
