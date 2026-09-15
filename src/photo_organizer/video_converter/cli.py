"""Command-line front-end for the video converter.

Usable today without the GUI. The future tkinter gui.py will call the same
core.process_video_folder(); this module is just an argparse adapter that wires
stdout logging + a tqdm-free percentage print into the callbacks.

Examples:
  python -m photo_organizer.video_converter.cli "/path/to/footage" --dry-run
  python -m photo_organizer.video_converter.cli "/path/to/footage" --run
  python -m photo_organizer.video_converter.cli "/path/to/footage" --run --stage1-only
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from photo_organizer.video_converter.engine import (
    DEFAULT_OPTIONS,
    process_video_folder,
    save_report,
)

logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(message)s")
log = logging.getLogger("photo_organizer.video_converter.cli")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Smart Log→Rec709 + 1080p share compression.")
    p.add_argument("folder", type=Path, help="Folder of camera clips (.MP4/.MOV)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Plan only (default)")
    mode.add_argument("--run", action="store_true", help="Actually encode")
    p.add_argument("--stage1-only", action="store_true", help="Colorspace only")
    p.add_argument("--stage2-only", action="store_true", help="Compress only")
    p.add_argument("--crf", type=int, default=DEFAULT_OPTIONS["x265_crf"])
    p.add_argument("--height", type=int, default=DEFAULT_OPTIONS["share_height"])
    p.add_argument("--lut", type=Path, default=None, help="Force a specific .cube LUT")
    p.add_argument("--report", type=Path, default=None, help="Write JSON report here")
    args = p.parse_args(argv)

    opts = dict(DEFAULT_OPTIONS)
    opts["dry_run"] = not args.run
    opts["x265_crf"] = args.crf
    opts["share_height"] = args.height
    if args.lut:
        opts["explicit_lut"] = args.lut
    if args.stage1_only:
        opts["do_stage2"] = False
    if args.stage2_only:
        opts["do_stage1"] = False

    def on_progress(pct: float):
        sys.stderr.write(f"\r  progress: {pct:5.1f}%")
        sys.stderr.flush()
        if pct >= 100:
            sys.stderr.write("\n")

    def on_log(msg: str):
        log.info(msg)

    results = process_video_folder(args.folder, opts, on_progress, on_log)
    if args.report:
        save_report(results, args.report)
        log.info(f"Report → {args.report}")
    return 0 if all(r.success for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
