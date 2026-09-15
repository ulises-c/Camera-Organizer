# Video Converter (Log → Rec709 + Share Compression)

Smart, metadata-driven conversion of camera footage to Rec709, then efficient
1080p HEVC encodes for sharing (Instagram etc.). Built to match the repo's
module conventions (UI-agnostic engine + callbacks, with CLI and PySide6
front-ends sharing the same entry point).

## Why "smart"

Each clip is classified from its **Sony sidecar XML** (`…M01.XML`,
`CaptureGammaEquation` / `CaptureColorPrimaries`) plus `ffprobe`:

- **S-Log3 clips** → a Log→Rec709 3D LUT (`.cube`) is applied.
- **Native Rec709 clips** → transcoded **without** a LUT, so they are never
  double-corrected.

A missing/unreadable XML is treated as **not** Log (fail-safe: we never apply a
Log LUT to footage we can't confirm is Log).

## Two stages

1. **Colorspace** (`STAGE1`): per-clip LUT-or-not → 4K **ProRes** masters tagged
   `bt709`.
2. **Compress** (`STAGE2`): downscale to **1080p HEVC (x265)** CRF with a bitrate
   cap, `hvc1` tag, `+faststart` → shareable MP4s.

### Color-tag correctness
`lut3d` strips container color side-data, so color metadata is stamped directly
into the encoder (prores flags in stage 1; `x265-params colorprim/transfer/
colormatrix=bt709` in stage 2). `verify_color_tags()` confirms every output.

## Requirements
- `ffmpeg` + `ffprobe` on PATH (`brew install ffmpeg`).
- LUT library (defaults to `~/Documents/Final Cut Pro/LUTs`). For A6700 S-Log3 the
  code auto-resolves Sony `LC-709TypeA`, then `LC-709`, then Cam2Rec equivalents.

## CLI usage
```bash
# plan only (default)
python -m photo_organizer.video_converter.cli "/path/to/footage" --dry-run

# real encode, both stages
python -m photo_organizer.video_converter.cli "/path/to/footage" --run

# one stage only / tuning
python -m photo_organizer.video_converter.cli "/path/to/footage" --run --stage1-only
python -m photo_organizer.video_converter.cli "/path/to/footage" --run --crf 22 --height 1080
python -m photo_organizer.video_converter.cli "/path/to/footage" --run --lut "/abs/path/to.cube"
```

Outputs land in `01_rec709_master/` and `02_share_1080p/` inside the source folder.
Existing outputs are skipped, so runs are resumable.

## GUI status

The unified PySide6 shell discovers this engine through `engine.TOOLS`, and the
**Video Converter** panel (`gui/panels/video_converter.py`) is fully wired: it
calls `engine.process_video_folder(folder, options, progress_cb, log_cb)` through
the shared `EngineWorker`. Controls include the footage folder, LUT auto-detect or
explicit override (`luts.catalog()`), per-stage toggles, share height, x265 CRF
and preset, preview mode (default), progress, logs, and cooperative cancellation.
Preview builds the plan without requiring `ffmpeg`; live runs are gated behind an
`ffmpeg_available()` check and a confirmation dialog.
