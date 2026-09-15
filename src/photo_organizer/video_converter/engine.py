"""Video converter core — Log→Rec709 + share compression.

Two stages, mirroring the shell prototype but as callable functions:

  Stage 1 (colorspace): smart per-clip. S-Log3 clips get the Log→Rec709 LUT;
    native-Rec709 clips are transcoded WITHOUT a LUT (never double-corrected).
    Output: 4K ProRes masters tagged bt709.

  Stage 2 (compress): downscale masters to 1080p HEVC (H.265) for sharing/IG.

Follows the repo conventions from converter/core.py: a
`process_video_folder(folder_path, options, progress_callback, log_callback)`
entry point, dataclass results, dry_run default, cancel_event/OperationCancelled,
and save_report().

Color-tag note: the lut3d filter drops color side-data, so ffmpeg won't stamp
color_trc/primaries on the LUT path. We therefore pass color metadata directly
to the encoder (prores_ks flags in stage 1; x265-params in stage 2) AND expose
verify_color_tags() so the GUI can confirm every output is correctly flagged.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from photo_organizer.engine import OperationCancelled, check_cancel
from photo_organizer.video_converter.luts import LutChoice, resolve_lut
from photo_organizer.video_converter.probe import Clip, ffprobe_bin, probe_dir

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Result types (parallel to converter/core.py's OpDetail / ConversionResult)
# --------------------------------------------------------------------------- #
@dataclass
class OpDetail:
    source: str
    action: str            # "STAGE1-LUT", "STAGE1-NATIVE", "STAGE2-1080p"
    output: str
    success: bool
    size_bytes: int = 0
    duration: float = 0.0
    error: str = ""


@dataclass
class VideoResult:
    source_stem: str
    is_log: bool
    success: bool
    details: list[OpDetail] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Defaults (the GUI will expose these as controls)
# --------------------------------------------------------------------------- #
DEFAULT_OPTIONS = {
    "dry_run": True,
    "do_stage1": True,          # colorspace conversion
    "do_stage2": True,          # share compression
    "prores_profile": 1,        # 0=Proxy 1=LT 2=Std 3=HQ
    "share_height": 1080,
    "x265_crf": 20,
    "x265_preset": "medium",
    "x265_maxrate": "16M",
    "x265_bufsize": "24M",
    "aac_bitrate": "256k",
    "lut_root": None,           # None -> luts.DEFAULT_LUT_ROOT
    "explicit_lut": None,       # force a specific .cube for all log clips
    "master_dirname": "01_rec709_master",
    "share_dirname": "02_share_1080p",
}


def ffmpeg_bin() -> str:
    exe = shutil.which("ffmpeg")
    if not exe:
        raise RuntimeError("ffmpeg not found on PATH. Install ffmpeg (brew install ffmpeg).")
    return exe


def _run_ffmpeg(cmd: list[str], cancel_event) -> None:
    """Run ffmpeg, polling so a cancel request terminates the child promptly."""
    check_cancel(cancel_event)
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, text=True)
    try:
        while True:
            try:
                _, err = proc.communicate(timeout=0.5)
                break
            except subprocess.TimeoutExpired:
                if cancel_event and cancel_event.is_set():
                    proc.kill()
                    proc.wait()
                    raise OperationCancelled("Process cancelled by user.")
        if proc.returncode != 0:
            tail = (err or "").strip().splitlines()[-3:]
            raise RuntimeError("ffmpeg failed: " + " | ".join(tail))
    finally:
        if proc.poll() is None:
            proc.kill()


# --------------------------------------------------------------------------- #
# Command builders (pure — unit-testable, reused by GUI preview)
# --------------------------------------------------------------------------- #
def build_stage1_cmd(clip: Clip, dest: Path, lut: LutChoice | None,
                     prores_profile: int) -> list[str]:
    if lut is not None:
        # format hops guarantee full-range 10-bit in/out around the 3D LUT.
        vf = (f"format=yuv444p10le,lut3d=file='{lut.path}',format=yuv422p10le")
    else:
        vf = "format=yuv422p10le"
    return [
        ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(clip.path),
        "-vf", vf,
        "-c:v", "prores_ks", "-profile:v", str(prores_profile), "-vendor", "apl0",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-c:a", "copy",
        str(dest),
    ]


def build_stage2_cmd(src: Path, dest: Path, opts: dict) -> list[str]:
    h = int(opts["share_height"])
    return [
        ffmpeg_bin(), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src),
        "-vf", f"scale=-2:{h}:flags=lanczos",
        "-c:v", "libx265", "-preset", opts["x265_preset"], "-crf", str(opts["x265_crf"]),
        "-maxrate", opts["x265_maxrate"], "-bufsize", opts["x265_bufsize"],
        "-pix_fmt", "yuv420p10le",
        # Belt-and-suspenders: stamp color into the HEVC bitstream itself, since
        # the lut3d path can strip container-level color side-data.
        "-x265-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-tag:v", "hvc1",
        "-c:a", "aac", "-b:a", opts["aac_bitrate"],
        "-movflags", "+faststart",
        str(dest),
    ]


def verify_color_tags(path: Path) -> dict:
    """Return the color_* tags actually written, so callers can assert bt709."""
    out = subprocess.run(
        [ffprobe_bin(), "-v", "quiet", "-select_streams", "v:0",
         "-show_entries", "stream=color_space,color_transfer,color_primaries",
         "-of", "json", str(path)],
        capture_output=True, text=True,
    )
    try:
        s = json.loads(out.stdout)["streams"][0]
        return {k: s.get(k, "unknown") for k in
                ("color_space", "color_transfer", "color_primaries")}
    except Exception:
        return {}


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def process_video_folder(folder_path: Path, options: dict,
                         progress_callback: Callable[[float], None],
                         log_callback: Callable[[str], None]) -> list[VideoResult]:
    def _log(msg: str):
        if log_callback:
            log_callback(msg)
        else:
            logger.info(msg)

    opts = {**DEFAULT_OPTIONS, **(options or {})}
    dry_run = opts["dry_run"]
    cancel_event = opts.get("cancel_event")
    folder_path = Path(folder_path)

    master_dir = folder_path / opts["master_dirname"]
    share_dir = folder_path / opts["share_dirname"]

    _log(f"Scanning {folder_path} …")
    clips = probe_dir(folder_path)
    if not clips:
        _log("No .MP4/.MOV clips found in source directory.")
        return []

    n_log = sum(1 for c in clips if c.is_log)
    _log(f"Found {len(clips)} clips: {n_log} S-Log3, {len(clips) - n_log} native Rec709. "
         f"(dry_run={dry_run})")

    if not dry_run:
        if opts["do_stage1"]:
            master_dir.mkdir(parents=True, exist_ok=True)
        if opts["do_stage2"]:
            share_dir.mkdir(parents=True, exist_ok=True)

    results: list[VideoResult] = []
    total = len(clips)

    try:
        for idx, clip in enumerate(clips, 1):
            check_cancel(cancel_event)
            stem = clip.path.stem
            res = VideoResult(source_stem=stem, is_log=clip.is_log, success=True)
            _log(f"[{idx}/{total}] {stem}  "
                 f"({'LOG→709 LUT' if clip.is_log else 'native 709, no LUT'})")

            master_path = master_dir / f"{stem}.mov"

            # ---- Stage 1: colorspace ----
            if opts["do_stage1"]:
                lut = None
                if clip.is_log:
                    lut = resolve_lut(clip.gamma, clip.gamut,
                                      lut_root=opts["lut_root"],
                                      explicit=opts["explicit_lut"])
                    if lut is None:
                        res.success = False
                        res.details.append(OpDetail(clip.path.name, "STAGE1-LUT",
                                                    master_path.name, False,
                                                    error="No matching LUT found"))
                        _log(f"  ✗ no LUT for {clip.gamma}/{clip.gamut}; skipping clip")
                        results.append(res)
                        progress_callback(idx / total * 100)
                        continue
                    _log(f"  LUT: {lut.label}")

                action = "STAGE1-LUT" if lut else "STAGE1-NATIVE"
                det = OpDetail(clip.path.name, action, master_path.name, False)
                t0 = time.time()
                try:
                    if master_path.exists():
                        _log("  skip stage1 (master exists)")
                        det.success = True
                    else:
                        cmd = build_stage1_cmd(clip, master_path, lut, opts["prores_profile"])
                        if not dry_run:
                            _run_ffmpeg(cmd, cancel_event)
                            det.size_bytes = master_path.stat().st_size
                        det.success = True
                except OperationCancelled:
                    raise
                except Exception as e:
                    det.error = str(e)
                    res.success = False
                    _log(f"  ✗ stage1: {e}")
                det.duration = round(time.time() - t0, 3)
                res.details.append(det)

            # ---- Stage 2: compress ----
            if opts["do_stage2"] and res.success:
                src = master_path if master_path.exists() or not dry_run else clip.path
                # If stage1 was skipped entirely, compress straight from source.
                if not opts["do_stage1"]:
                    src = clip.path
                share_path = share_dir / f"{stem}_{opts['share_height']}p.mp4"
                det = OpDetail(src.name, f"STAGE2-{opts['share_height']}p",
                              share_path.name, False)
                t0 = time.time()
                try:
                    if share_path.exists():
                        _log("  skip stage2 (share exists)")
                        det.success = True
                    else:
                        cmd = build_stage2_cmd(src, share_path, opts)
                        if not dry_run:
                            _run_ffmpeg(cmd, cancel_event)
                            det.size_bytes = share_path.stat().st_size
                            tags = verify_color_tags(share_path)
                            if tags.get("color_transfer") != "bt709":
                                _log(f"  ⚠ color tag check: {tags}")
                        det.success = True
                except OperationCancelled:
                    raise
                except Exception as e:
                    det.error = str(e)
                    res.success = False
                    _log(f"  ✗ stage2: {e}")
                det.duration = round(time.time() - t0, 3)
                res.details.append(det)

            results.append(res)
            progress_callback(idx / total * 100)

    except OperationCancelled:
        _log("🛑 Process Cancelled.")
        return results
    except Exception as e:
        _log(f"❌ Fatal Error: {e}")
        logger.exception("Video core loop crash")

    ok = sum(1 for r in results if r.success)
    _log(f"Complete. {ok}/{len(results)} clips succeeded.")
    return results


def save_report(results: list[VideoResult], output_path: Path) -> None:
    data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_clips": len(results),
            "successful_clips": sum(1 for r in results if r.success),
            "log_clips": sum(1 for r in results if r.is_log),
            "total_operations": sum(len(r.details) for r in results),
        },
        "clips": [
            {
                "stem": r.source_stem,
                "is_log": r.is_log,
                "success": r.success,
                "ops": [asdict(d) for d in r.details],
            }
            for r in results
        ],
    }
    try:
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save report: {e}")
