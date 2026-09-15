"""Shared engine primitives.

Every feature (organizer, renamer, TIFF converter, video converter) exposes a
UI-agnostic *engine* function with a uniform signature so a single Qt worker can
drive any of them:

    def run(source: Path, options: dict,
            progress_callback: Callable[[float], None],
            log_callback: Callable[[str], None]) -> list: ...

- `options` is a plain dict; a cancellation token lives under options["cancel_event"].
- `progress_callback` receives a 0–100 float.
- `log_callback` receives human-readable lines.

This module holds the pieces engines share: the cancellation exception, a cancel
check, a `Reporter` convenience wrapper, and a `TOOLS` registry the GUI reads to
discover tools without importing every engine eagerly.
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from typing import Protocol


class OperationCancelled(Exception):
    """Raised to unwind cleanly when the user cancels an operation."""


CancelToken = threading.Event  # any object with .is_set()/.set() works


def make_cancel_token() -> CancelToken:
    return threading.Event()


def check_cancel(cancel_event: CancelToken | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise OperationCancelled("Process cancelled by user.")


class EngineCallable(Protocol):
    def __call__(self, source, options: dict,
                 progress_callback: Callable[[float], None],
                 log_callback: Callable[[str], None]) -> list: ...


@dataclass
class Reporter:
    """Bundles the callbacks + cancel token an engine needs.

    Engines may take the raw callbacks (uniform signature) or accept a Reporter;
    `Reporter.from_options` builds one from the standard args so engine code can
    call `rep.log(...)`, `rep.progress(...)`, `rep.check_cancel()` uniformly.
    """
    progress_callback: Callable[[float], None] = lambda pct: None
    log_callback: Callable[[str], None] = lambda msg: None
    cancel_event: CancelToken | None = None

    @classmethod
    def from_options(cls, options: dict,
                     progress_callback: Callable[[float], None],
                     log_callback: Callable[[str], None]) -> Reporter:
        return cls(progress_callback or (lambda p: None),
                   log_callback or (lambda m: None),
                   (options or {}).get("cancel_event"))

    def log(self, msg: str) -> None:
        self.log_callback(msg)

    def progress(self, pct: float) -> None:
        self.progress_callback(pct)

    def check_cancel(self) -> None:
        check_cancel(self.cancel_event)


@dataclass(frozen=True)
class ToolSpec:
    """Describes one tool for the GUI registry, without importing its engine."""
    key: str
    name: str
    description: str
    engine_path: str          # "module:function", imported lazily
    source_kind: str = "folder"   # "folder" | "file"

    def load_engine(self) -> EngineCallable:
        mod_name, func_name = self.engine_path.split(":")
        return getattr(import_module(mod_name), func_name)


# Central registry the GUI iterates over. Engines are imported lazily via
# ToolSpec.load_engine() so importing this module stays cheap.
TOOLS: list[ToolSpec] = [
    ToolSpec(
        key="organizer",
        name="📸 Photo & Video Organizer",
        description="Sort files into date / camera-model folders",
        engine_path="photo_organizer.organizer.engine:process_organize",
    ),
    ToolSpec(
        key="folder_renamer",
        name="📁 Folder Renamer",
        description="Rename NNNYMMDD camera folders to YYYY-MM-DD",
        engine_path="photo_organizer.renamer.engine:process_folder_rename",
    ),
    ToolSpec(
        key="batch_renamer",
        name="🏷️ Batch Renamer",
        description="Replace 'UnknownCamera' in file/folder names",
        engine_path="photo_organizer.renamer.engine:process_batch_rename",
    ),
    ToolSpec(
        key="tiff_converter",
        name="🖼️ TIFF Converter",
        description="Epson scans → lossless TIFF / HEIC / JPG",
        engine_path="photo_organizer.converter.engine:process_epson_folder",
    ),
    ToolSpec(
        key="video_converter",
        name="🎬 Video Converter",
        description="Log→Rec709 + 1080p HEVC share encode",
        engine_path="photo_organizer.video_converter.engine:process_video_folder",
    ),
]


def get_tool(key: str) -> ToolSpec:
    for t in TOOLS:
        if t.key == key:
            return t
    raise KeyError(f"Unknown tool: {key}")
