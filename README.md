# Photo Organizer Suite

A comprehensive toolkit for organizing photos, videos, and scans. Includes multiple tools for different organizational tasks, all accessible through a unified launcher.

## Features

### 📸 Photo & Video Organizer

- Sort files by date and camera model
- Support for photos (.HIF, .ARW, .JPG) and videos (.MP4, .MOV)
- Flexible organization options (by camera, by date, separate media types)
- Automatic camera model detection and database management

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

- Convert TIFF to LZW/DEFLATE compressed TIFF
- Convert TIFF to HEIC/HEIF format
- Epson FastFoto FF-680W workflow with automatic variant selection
- Intelligent quality-based selection between augmented (\_a) and base files
- Metadata preservation (EXIF, ICC profiles)
- Lossless and lossy compression options
- Parallel processing for large batches
- Automatic organization into LZW_compressed/, HEIC/, and uncompressed/ folders

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

`make run` launches the unified PySide6 application. The Folder Renamer and
Batch Renamer are fully migrated; Organizer, TIFF Converter, and Video Converter
currently show migration stubs while their UI-agnostic engines remain available.

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

Both renamer panels default to **Preview only**, so their first run does not
change files. Clear that option and confirm the warning dialog to perform live
renames. Folder merges must also be enabled explicitly; conflicts receive a
`_dupN` suffix rather than overwriting existing files.

### Video converter CLI

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
│       ├── batch_renamer.py     # UnknownCamera file/folder renaming
│       └── folder_renamer.py    # Metadata-based camera-folder renaming
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

New camera models are automatically added when detected during organization.

## Supported File Types

### Photos

- `.HIF` - High Efficiency Image Format
- `.ARW` - Sony RAW
- `.JPG` / `.JPEG` - JPEG images

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
