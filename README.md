# Photo Organizer Suite

A comprehensive toolkit for organizing photos, videos, and scans. Includes multiple tools for different organizational tasks, all accessible through a unified launcher.

## Features

### 📸 Photo & Video Organizer

- Sort files into date and camera-model folders derived from metadata
- Support for photos (.HIF, .ARW, .JPG) and videos (.MP4, .MOV) plus sidecars
- Optional separate source and destination folders, and optional recursion
- Flexible layout options (by camera, append model to date folders, separate media types)
- Never overwrites: existing and already-organized destinations are skipped
- Camera-model database updates only after successful live moves

### 📁 Folder Renamer

- Rename camera-generated folders (NNNYMMDD format)
- Convert to readable YYYY-MM-DD[_CameraModel] format
- Sample folder media to derive date and camera model metadata
- Preview recursive renames and optionally merge without overwriting conflicts

### 🏷️ Batch Renamer

- Fix 'UnknownCamera' references in filenames and folders
- Support for custom camera model names
- Bulk renaming operations

### 🖼️ TIFF Converter

- Create verified lossless TIFFs (Deflate/`.ZIP.TIF` or LZW/`.LZW.TIF`), preserving all pages
- Optional lossy HEIC and JPEG copies (when a HEIF encoder is available)
- Epson FastFoto FF-680W workflow with deterministic `_a`/`_b` variant selection
- Quality-based front selection (smart), or explicit prefer-base / prefer-augmented
- Metadata preservation (EXIF, ICC, DPI) with alpha flattened onto white for lossy outputs
- Never overwrites: existing outputs and archived originals are skipped
- Outputs organized into `lossless_compressed/`, `lossless_compressed/archive/`, `HEIC/`, `JPG/`, and `originals/`

## System Requirements

- Python 3.11–3.13
- [`uv`](https://docs.astral.sh/uv/)
- `ffmpeg` + `ffprobe` for video conversion (`brew install ffmpeg` on macOS)
- A desktop supported by Qt/PySide6

## Quick Start

```bash
make doctor
make sync
make run
```

`make run` launches the unified PySide6 application. All five tools — Photo &
Video Organizer, Folder Renamer, Batch Renamer, Video Converter, and TIFF
Converter — are fully migrated to native panels. The migration from the old
tkinter launcher is complete.

## Development Commands

```bash
make help        # List commands
make sync        # Install dependencies with uv
make run         # Launch the PySide6 app
make lint        # Run Ruff
make test        # Run pytest
make clean       # Remove Python caches
```

## Usage

### PySide6 application

```bash
make run
# or
uv run camera-organizer
```

Both renamer panels and the Organizer default to **Preview only**, so their
first run does not change files. Clear that option and confirm the warning
dialog to perform live changes. The Organizer moves files (never overwriting:
existing or already-organized destinations are skipped) and can target a
separate destination folder. Folder merges must be enabled explicitly;
conflicts receive a `_dupN` suffix rather than overwriting existing files.

### TIFF converter

The **TIFF Converter** panel scans root-level `.tif`/`.tiff` files and always
writes a verified lossless TIFF (Deflate or LZW), with optional lossy HEIC/JPEG
copies. It defaults to **Preview only**, which validates the plan — inputs,
multipage handling, destination collisions, and encoder availability — without
touching disk. A live run writes derivatives, re-opens each TIFF to confirm it,
then moves the originals; existing outputs and archived originals are skipped
rather than overwritten. FastFoto `_a`/`_b` variant selection is optional.

### Video converter

The **Video Converter** panel drives the same engine from the GUI (footage
folder, LUT auto-detect or explicit pick, stage toggles, share height, x265 CRF
and preset), defaulting to **Preview only**. A live run needs `ffmpeg`/`ffprobe`
on PATH and encodes into `01_rec709_master/` and `02_share_1080p/` subfolders;
existing outputs are skipped rather than overwritten. The CLI remains available:

```bash
# Plan only (default)
uv run python -m photo_organizer.video_converter.cli "/path/to/footage" --dry-run

# Perform Log→Rec709 and 1080p HEVC conversion
uv run python -m photo_organizer.video_converter.cli "/path/to/footage" --run
```

## Project Structure

```
src/photo_organizer/
├── app.py                       # PySide6 application entry point
├── engine/__init__.py           # Shared engine contract and tool registry
├── gui/
│   ├── main_window.py           # Unified window and panel routing
│   ├── worker.py                # Reusable background QThread
│   └── panels/
│       ├── organizer.py         # Metadata-based date/camera-model sorting
│       ├── batch_renamer.py     # UnknownCamera file/folder renaming
│       ├── folder_renamer.py    # Metadata-based camera-folder renaming
│       ├── tiff_converter.py    # Lossless TIFF + lossy HEIC/JPEG (FastFoto)
│       └── video_converter.py   # Log→Rec709 + 1080p HEVC share encode
├── organizer/engine.py          # Photo/video organization logic
├── renamer/engine.py            # Batch and folder rename logic
├── converter/engine.py          # TIFF/Epson conversion logic
├── video_converter/             # Video engine, probe, LUT, reports, and CLI
├── shared/                      # Metadata, models, config, image/file utilities
└── data/                        # Packaged camera-model seeds
```

## Camera Models Database

The application maintains a user-writable camera models database using `appdirs` for proper cross-platform support. The database is stored at:

- **macOS**: `~/Library/Application Support/photo_organizer/camera_models.json`
- **Linux**: `~/.local/share/photo_organizer/camera_models.json`

New camera models are added to the database only after a successful live
organize move (never during preview).

## Supported File Types

### Photos

- `.HIF` - High Efficiency Image Format
- `.ARW` - Sony RAW
- `.JPG` - JPEG images

### Videos

- `.MP4` - MPEG-4 video
- `.MOV` - QuickTime video
- `.XML` - Video metadata (Sony, GoPro)
- `.THM` - Video thumbnails
- `.LRV` - Low-resolution video

### TIFF

- `.TIF` / `.TIFF` - Tagged Image File Format
- Multi-page TIFF support (detection)
- High bit-depth images (8-bit, 16-bit, 32-bit)

## Platform Support

- macOS is the primary target.
- Linux and Windows are supported by the Python/PySide6 stack but are not yet
  covered by project CI.

## Development

Keep all file-processing logic in UI-agnostic engines. PySide6 panels should
only validate inputs, construct option dictionaries, run an `EngineWorker`, and
render its signals/results.

Before submitting a change:

```bash
make lint
make test
```

## Tested Devices

### Cameras

- Sony a6700
- Sony a6400
- Sony a6300
- Sony RX100 VII
- GoPro Hero 8 Black
- iPhone 14 Pro Max

### Scanners

- Epson FastFoto FF-680W (with \_a augmented and \_b backside support)
- Epson Perfection V39 II

## License

MIT License

## Authors

- Ulises Chavarria

## Acknowledgments

- TIFF converter inspired by [Universal-Image-Converter](https://github.com/Jesikurr/Universal-Image-Converter)
