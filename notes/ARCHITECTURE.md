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
    main_window.py       Window shell + per-tool panels (stubs for now).
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
  `engine.check_cancel(...)` and raise `OperationCancelled`.
- `options["dry_run"]` defaults to **True** everywhere — nothing mutates disk
  until explicitly turned off.
- Engines never import Qt or tkinter. They print nothing; they call callbacks.

The GUI discovers tools through `engine.TOOLS` (a list of `ToolSpec`) and loads
each engine lazily via `ToolSpec.load_engine()` — so adding a tool is one entry
in the registry, no wiring.

## GUI status: deferred

`main_window.py` shows a working window with a tool list and **stub panels**. The
engines are complete and runnable now via CLI / `EngineWorker`. Building a real
panel = source picker + options widgets + progress bar + log view + Cancel, all
driven by an `EngineWorker` (already implemented and tested).

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
