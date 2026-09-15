"""Renamer — engine.

UI-agnostic rename logic extracted from the former tkinter `batch_gui`/`folder_gui`.
Two engine functions share the uniform signature (source, options, progress_cb, log_cb):

- process_batch_rename:  replace "UnknownCamera" in file/folder names with a model.
- process_folder_rename: rename NNNYMMDD camera folders → YYYY-MM-DD[_Model],
                         with optional safe merge into existing destinations.

Pure helpers (compute_new_name, gather_candidate_folders, safe_merge_folders)
are kept importable for tests and a future GUI preview.
"""
from __future__ import annotations

import logging
import os
import re
import shutil
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from photo_organizer.engine import OperationCancelled, check_cancel
from photo_organizer.shared.camera_models import add_camera_model, resolve_model_name
from photo_organizer.shared.metadata import get_camera_model, get_creation_date

logger = logging.getLogger(__name__)

FOLDER_PATTERN = re.compile(r"^(\d{3})(\d)(\d{2})(\d{2})$")


@dataclass
class RenameOp:
    old: str
    new: str
    action: str          # "rename" | "merge"
    success: bool
    error: str = ""


@dataclass
class RenameResult:
    ops: list[RenameOp] = field(default_factory=list)
    success: int = 0
    failed: int = 0
    skipped: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Batch renamer (UnknownCamera → model)
# --------------------------------------------------------------------------- #
BATCH_DEFAULT_OPTIONS = {
    "dry_run": True,
    "model": "",            # required: display name or custom string
}


def process_batch_rename(source, options: dict,
                         progress_callback: Callable[[float], None],
                         log_callback: Callable[[str], None]) -> RenameResult:
    def _log(msg: str):
        (log_callback or logger.info)(msg)

    opts = {**BATCH_DEFAULT_OPTIONS, **(options or {})}
    dry_run = opts["dry_run"]
    cancel_event = opts.get("cancel_event")
    model = (opts.get("model") or "").strip()
    folder_path = str(source)

    result = RenameResult()
    if not model or model == "Select camera type":
        _log("✗ No camera model provided; nothing to do.")
        return result

    # Collect matches first (files + dirs) for progress + safe ordering.
    matches: list[tuple[str, str, bool]] = []  # (root, name, is_dir)
    for root, dirs, files in os.walk(folder_path):
        for name in files + dirs:
            if "UnknownCamera" in name:
                matches.append((root, name, os.path.isdir(os.path.join(root, name))))

    total = len(matches)
    if total == 0:
        _log("No names containing 'UnknownCamera' found.")
        return result

    _log(f"Found {total} items to rename → {model} (dry_run={dry_run})")
    try:
        for idx, (root, name, is_dir) in enumerate(matches, 1):
            check_cancel(cancel_event)
            old_path = os.path.join(root, name)
            new_path = os.path.join(root, name.replace("UnknownCamera", model))
            op = RenameOp(old=old_path, new=new_path, action="rename", success=False)
            try:
                if not dry_run:
                    if is_dir and os.path.exists(new_path):
                        # Merge contents into existing destination dir.
                        for item in os.listdir(old_path):
                            dst_item = os.path.join(new_path, item)
                            if not os.path.exists(dst_item):
                                os.rename(os.path.join(old_path, item), dst_item)
                        try:
                            os.rmdir(old_path)
                        except OSError:
                            pass
                    else:
                        os.rename(old_path, new_path)
                op.success = True
                result.success += 1
            except OperationCancelled:
                raise
            except Exception as e:
                op.error = str(e)
                result.failed += 1
                _log(f"  ✗ {name}: {e}")
            result.ops.append(op)
            progress_callback(idx / total * 100)
    except OperationCancelled:
        _log("🛑 Process cancelled.")
        return result

    _log(f"Complete. Renamed {result.success}, failed {result.failed}.")
    return result


# --------------------------------------------------------------------------- #
# Folder renamer (NNNYMMDD → YYYY-MM-DD[_Model])
# --------------------------------------------------------------------------- #
FOLDER_DEFAULT_OPTIONS = {
    "dry_run": True,
    "recursive": True,
    "include_model": True,
    "merge": False,
}


def extract_folder_metadata(folder_path: str):
    """Return (date, model, sample_file) sampling first/middle/last files."""
    files = []
    for root, _, filenames in os.walk(folder_path):
        for fn in filenames:
            if not fn.startswith((".", "_")):
                files.append(os.path.join(root, fn))
    if not files:
        return None, None, None
    files.sort()
    n = len(files)
    for idx in ([0, n // 2, n - 1] if n > 2 else range(n)):
        try:
            fp = files[idx]
            date = get_creation_date(fp)
            model = get_camera_model(fp)
            if date and date != "Unknown":
                return date, model, fp
        except Exception:
            continue
    return None, None, None


def compute_new_name(folder_path: str, include_model: bool = True):
    """Return (new_path, status): ok | merge | pattern_mismatch | no_metadata | already_correct."""
    folder_name = os.path.basename(folder_path.rstrip(os.sep))
    if not FOLDER_PATTERN.match(folder_name):
        return None, "pattern_mismatch"
    date, raw_model, _ = extract_folder_metadata(folder_path)
    if not date:
        return None, "no_metadata"
    new_name = date
    if include_model and raw_model:
        friendly = resolve_model_name(raw_model)
        if friendly and friendly != "UnknownCamera":
            new_name = f"{date}_{friendly.replace('/', '-').replace(chr(92), '-')}"
    new_path = os.path.join(os.path.dirname(folder_path), new_name)
    if os.path.normpath(new_path) == os.path.normpath(folder_path):
        return None, "already_correct"
    if os.path.exists(new_path):
        return new_path, "merge"
    return new_path, "ok"


def gather_candidate_folders(parent_path: str, recursive: bool) -> list:
    candidates = []
    if recursive:
        for root, dirs, _ in os.walk(parent_path):
            for d in dirs:
                if FOLDER_PATTERN.match(d):
                    candidates.append(os.path.join(root, d))
    else:
        try:
            with os.scandir(parent_path) as entries:
                for e in entries:
                    if e.is_dir() and FOLDER_PATTERN.match(os.path.basename(e.path)):
                        candidates.append(e.path)
        except Exception as ex:
            logger.error(f"Error scanning {parent_path}: {ex}")
    return sorted(candidates)


def safe_merge_folders(src_path: str, dst_path: str, log_func=None):
    """Merge src into dst, resolving file conflicts with a _dupN suffix."""
    moved = skipped = 0
    for item in os.listdir(src_path):
        src_item = os.path.join(src_path, item)
        dst_item = os.path.join(dst_path, item)
        try:
            if os.path.isdir(src_item):
                if os.path.exists(dst_item):
                    m, s = safe_merge_folders(src_item, dst_item, log_func)
                    moved += m
                    skipped += s
                    try:
                        os.rmdir(src_item)
                    except OSError:
                        pass
                else:
                    shutil.move(src_item, dst_item)
                    moved += 1
            else:
                if os.path.exists(dst_item):
                    base, ext = os.path.splitext(item)
                    c = 1
                    while os.path.exists(os.path.join(dst_path, f"{base}_dup{c}{ext}")):
                        c += 1
                    dst_item = os.path.join(dst_path, f"{base}_dup{c}{ext}")
                shutil.move(src_item, dst_item)
                moved += 1
        except Exception as e:
            skipped += 1
            if log_func:
                log_func(f"    ✗ Error moving {item}: {e}")
    return moved, skipped


def process_folder_rename(source, options: dict,
                          progress_callback: Callable[[float], None],
                          log_callback: Callable[[str], None]) -> RenameResult:
    def _log(msg: str):
        (log_callback or logger.info)(msg)

    opts = {**FOLDER_DEFAULT_OPTIONS, **(options or {})}
    dry_run = opts["dry_run"]
    cancel_event = opts.get("cancel_event")
    recursive = opts["recursive"]
    include_model = opts["include_model"]
    merge = opts["merge"]
    parent = str(source)

    result = RenameResult(skipped={"pattern_mismatch": 0, "no_metadata": 0,
                                   "already_correct": 0, "destination_exists": 0})

    candidates = gather_candidate_folders(parent, recursive)
    if not candidates:
        _log("No folders matching NNNYMMDD pattern found.")
        return result
    _log(f"Found {len(candidates)} candidate folders (dry_run={dry_run})")

    plan: list[tuple[str, str, str]] = []
    for old in candidates:
        new_path, status = compute_new_name(old, include_model)
        if status == "ok" and new_path:
            plan.append((old, new_path, "rename"))
        elif status == "merge" and new_path:
            if merge:
                plan.append((old, new_path, "merge"))
            else:
                result.skipped["destination_exists"] += 1
        else:
            result.skipped[status] = result.skipped.get(status, 0) + 1

    for status, count in result.skipped.items():
        if count:
            _log(f"  skip ({status}): {count}")

    total = len(plan)
    if total == 0:
        _log("Nothing to process.")
        return result

    try:
        for idx, (old, new, action) in enumerate(plan, 1):
            check_cancel(cancel_event)
            oldn, newn = os.path.basename(old), os.path.basename(new)
            op = RenameOp(old=old, new=new, action=action, success=False)
            try:
                if action == "rename":
                    if not dry_run:
                        os.rename(old, new)
                    _log(f"  RENAME {oldn} → {newn}")
                else:
                    _log(f"  MERGE  {oldn} → {newn}")
                    if not dry_run:
                        _moved, _ = safe_merge_folders(old, new, _log)
                        try:
                            os.rmdir(old)
                        except OSError:
                            pass
                if not dry_run and include_model:
                    _, raw_model, _ = extract_folder_metadata(new)
                    if raw_model and raw_model != "UnknownCamera":
                        add_camera_model(raw_model)
                op.success = True
                result.success += 1
            except OperationCancelled:
                raise
            except Exception as e:
                op.error = str(e)
                result.failed += 1
                _log(f"  ✗ {oldn}: {e}")
            result.ops.append(op)
            progress_callback(idx / total * 100)
    except OperationCancelled:
        _log("🛑 Process cancelled.")
        return result

    _log(f"Complete. {result.success} ok, {result.failed} failed.")
    return result


def save_report(result: RenameResult, output_path: Path) -> None:
    data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {"success": result.success, "failed": result.failed,
                    "skipped": result.skipped},
        "ops": [asdict(o) for o in result.ops],
    }
    try:
        Path(output_path).write_text(__import__("json").dumps(data, indent=2))
    except Exception as e:
        logger.error(f"Failed to save report: {e}")
