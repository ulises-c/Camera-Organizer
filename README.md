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
- Metadata extraction from folder contents
- Sanity checking for date consistency

### 🏷️ Batch Renamer

- Fix 'UnknownCamera' references in filenames and folders
- Support for custom camera model names
- Bulk renaming operations

### 🖼️ TIFF Converter

- Convert TIFF to LZW-compressed TIFF
- Convert TIFF to HEIC/HEIF format
- Metadata preservation (EXIF, ICC profiles)
- Lossless and lossy compression options
- Parallel processing for large batches

## System Requirements

### macOS

```bash
# Install Homebrew if needed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install required packages
brew install tcl-tk pyenv poetry

# Build Python with Tkinter support
export LDFLAGS="-L$(brew --prefix tcl-tk)/lib"
export CPPFLAGS="-I$(brew --prefix tcl-tk)/include"
export PKG_CONFIG_PATH="$(brew --prefix tcl-tk)/lib/pkgconfig"
pyenv install 3.12
```

### Linux (Debian/Ubuntu)

```bash
# Install build dependencies
sudo apt-get update && sudo apt-get install -y \
    build-essential libssl-dev zlib1g-dev libbz2-dev \
    libreadline-dev libsqlite3-dev curl git \
    libncursesw5-dev xz-utils tk-dev libxml2-dev \
    libxmlsec1-dev libffi-dev liblzma-dev libheif-dev

# Install pyenv
curl https://pyenv.run | bash

# Install Poetry
curl -sSL https://install.python-poetry.org | python3 -
```

## Quick Start

```bash
# 1. Check your system
make doctor

# 2. Complete setup
make setup

# 3. Run the application
make run
```

## Development Commands

```bash
make help       # Show all commands
make doctor     # Check system dependencies
make setup      # Install everything
make install    # Install Python packages only
make run        # Launch the application
make run-dev    # Run in development mode
make clean      # Clean virtual environment
```

## Troubleshooting

### "tkinter not available" error

- **macOS**: Reinstall Python with tcl-tk support (see System Requirements)
- **Linux**: Install `tk-dev` package before building Python

### "Command not found: poetry"

Install Poetry: https://python-poetry.org/docs/#installation

### Old command still works

You can also run:

```bash
poetry run photo-organizer
poetry run python -m photo_organizer.launcher
```

## Usage

### Launcher (Recommended)

Start the main launcher to access all tools:

```bash
make run
# Or directly:
python src/launcher.py
```

### Individual Tools

Each tool can be run independently:

```bash
# Photo & Video Organizer
python src/organizer/gui.py

# Folder Renamer
python src/renamer/folder_gui.py

# Batch Renamer
python src/renamer/batch_gui.py

# TIFF Converter
python src/converter/gui.py
```

## Project Structure

```
photo-organizer/
├── src/
│   ├── launcher.py              # Main launcher GUI
│   ├── shared/                  # Common utilities
│   │   ├── metadata.py          # EXIF/metadata extraction
│   │   ├── camera_models.py     # Camera model database
│   │   ├── file_utils.py        # File operations
│   │   ├── gui_utils.py         # GUI utilities
│   │   └── config.py            # Application constants
│   ├── organizer/               # Photo/video organizer
│   │   ├── core.py              # Organization logic
│   │   └── gui.py               # Organizer GUI
│   ├── renamer/                 # Renaming tools
│   │   ├── batch_gui.py         # Batch renamer
│   │   └── folder_gui.py        # Folder renamer
│   ├── converter/               # TIFF converter
│   │   ├── core.py              # Conversion logic
│   │   └── gui.py               # Converter GUI
│   └── data/
│       └── camera_models_seed.txt  # Initial camera models
├── tiff-to-heic/                # Original TIFF converter (preserved)
├── pyproject.toml
├── Makefile
└── README.md
```

## Camera Models Database

The application maintains a user-writable camera models database using `appdirs` for proper cross-platform support. The database is stored at:

- **macOS**: `~/Library/Application Support/photo_organizer/camera_models.txt`
- **Linux**: `~/.local/share/photo_organizer/camera_models.txt`

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

- **Primary**: macOS (tested on macOS 12+)
- **Note**: System Python on macOS may have limited tkinter support. For best results, use Python from [python.org](https://www.python.org/downloads/) or Homebrew.

## Development

### Setup Development Environment

```bash
# Install Python with pyenv
make install-python

# Create Poetry environment
make create-env

# Install dependencies
make install

# Activate environment
source .venv/bin/activate
```

### Clean Environment

```bash
make clean
```

## Tested Devices

- Sony a6700
- Sony a6400
- Sony a6300
- Sony RX100 VII
- GoPro Hero 8 Black
- iPhone 14 Pro Max

## License

MIT License

## Authors

- Ulises Chavarria

## Acknowledgments

- TIFF converter inspired by [Universal-Image-Converter](https://github.com/Jesikurr/Universal-Image-Converter)
