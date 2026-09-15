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
  `engine.check_cancel(...)` and raise `OperationCancelled`.
- `options["dry_run"]` defaults to **True** everywhere — nothing mutates disk
  until explicitly turned off.
- Engines never import Qt or tkinter. They print nothing; they call callbacks.

The GUI discovers tools through `engine.TOOLS` (a list of `ToolSpec`) and loads
each engine lazily via `ToolSpec.load_engine()` — so adding a tool is one entry
in the registry, no wiring.

## GUI status: migration in progress

`main_window.py` provides the unified application shell. The **Folder Renamer**
and **Batch Renamer** are complete panels with preview-safe defaults, live-run
confirmation, progress, logs, structured results, and cooperative cancellation.
Folder Renamer additionally exposes recursive discovery, optional camera-model
suffixes, and explicit non-overwriting merges. Organizer, TIFF Converter, and
Video Converter still show stubs while their engines remain usable.

Adding the next real panel means wiring its source/options controls to an
`EngineWorker`; processing decisions stay in the engine.

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
