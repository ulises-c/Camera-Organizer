# Architecture (uv + PySide6)

The app is split into **UI-agnostic engines** and a **thin PySide6 layer**. This
is the rule that keeps a GUI optional and the logic testable.

## Layers

```
src/photo_organizer/
  engine/__init__.py     Shared contract: OperationCancelled, check_cancel,
                         Reporter, ToolSpec + TOOLS registry.
  app.py                 Console-script entry → launches the PySide6 window.
  gui/
    worker.py            EngineWorker(QThread): runs ANY engine off-thread,
                         marshals progress/log callbacks → Qt signals, cancel().
    main_window.py       Window shell + completed and stub tool panels.
  organizer/engine.py        process_organize(...)
  renamer/engine.py          process_batch_rename(...), process_folder_rename(...)
  converter/engine.py        process_epson_folder(...)   (TIFF/Epson)
  video_converter/           engine.py, probe.py, luts.py, cli.py
  shared/                    metadata, camera_models, config, file/image utils
```

## The engine contract (every engine obeys this)

```python
def run(source, options: dict,
        progress_callback: Callable[[float], None],   # 0–100
        log_callback: Callable[[str], None]) -> ResultObject: ...
```

- Cancellation token lives at `options["cancel_event"]`; engines poll it with
  `engine.check_cancel(...)` (raising `OperationCancelled`) or a direct
  `is_set()` check for soft unwinding. A result object may carry a `cancelled`
  flag: the worker reports cancellation from that flag when present, and only
  falls back to the requested token when the result is silent — so an engine
  that ignores the token and finishes is never reported as cancelled.
- `options["dry_run"]` defaults to **True** everywhere — nothing mutates disk
  until explicitly turned off.
- Engines never import Qt or tkinter. They print nothing; they call callbacks.
- Result objects expose structured per-item status (e.g. the Organizer's
  `planned` / `moved` / `skipped_already_organized` / `skipped_collision` /
  `failed`) and truthful totals so preview and live runs are unambiguous.
- Destinations derived from untrusted metadata are reduced to single safe path
  segments; moves never overwrite and never escape the destination root.


The GUI discovers tools through `engine.TOOLS` (a list of `ToolSpec`) and loads
each engine lazily via `ToolSpec.load_engine()`. Registering a tool is one entry
in `TOOLS`; wiring a *real* panel is an explicit routing branch in
`make_panel()` (the default is the shared `StubPanel`).

## GUI status: migration complete

`main_window.py` provides the unified application shell. All five tools —
**Photo & Video Organizer**, **Folder Renamer**, **Batch Renamer**, **Video
Converter**, and **TIFF Converter** — are complete native panels with
preview-safe defaults, live-run confirmation, progress, logs, structured
results, and cooperative cancellation. Organizer adds a separate destination
folder, optional recursion, non-overwriting collision skips, truthful partial
cancellation, and camera-model persistence limited to successful live moves.
Folder Renamer adds recursive discovery, optional camera-model suffixes, and
explicit non-overwriting merges. Video Converter adds LUT auto-detect/override,
per-stage toggles, x265 tuning, and an ffmpeg-on-PATH guard for live runs. TIFF
Converter adds a two-column option matrix (compression, HEIC/JPEG with capability
gating, FastFoto variant policy), verified lossless output, and no-overwrite
collision skips. `MainWindow.closeEvent` cancels and joins any in-flight panel
worker so a mid-encode close never destroys a running `QThread`.

Adding another tool means one `ToolSpec` in `engine.TOOLS` plus a routing branch
in `make_panel()`; processing decisions stay in the engine.

## Rules replacing the old tkinter constraints

- Long work runs in an `EngineWorker` (QThread), never on the UI thread.
- Touch widgets only from signal handlers on the main thread; the worker only
  emits signals.
- Cancel is cooperative — set the token, let the engine unwind; never kill threads.
- Keep design decisions (naming, output layout) in the engine, not the panel.

## Tooling

- **uv** manages the env: `uv sync --extra ssim` builds `.venv`; `uv run …` runs.
- Python 3.11–3.13 (PySide6 6.11).
- `ffmpeg`/`ffprobe` required for `video_converter` (`brew install ffmpeg`).
