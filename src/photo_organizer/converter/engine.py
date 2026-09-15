"""
TIFF Converter Core - Professional Workflow
Handles parallel processing, smart archiving, and multi-format output.
"""
import json
import logging
import os
import shutil
import tempfile
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import pillow_heif
    from PIL import Image
    pillow_heif.register_heif_opener()
    HEIF_SAVE_AVAILABLE = True
except ImportError:
    HEIF_SAVE_AVAILABLE = False
    from PIL import Image

from PIL.TiffImagePlugin import IFDRational

try:
    from PIL.TiffImagePlugin import ImageFileDirectory_v2
except Exception:
    ImageFileDirectory_v2 = None

# Ensure these imports exist in your project structure
from photo_organizer.converter.variant_selection import (
    OperationCancelled,
    choose_best_variant,
    group_variants,
)

logger = logging.getLogger(__name__)

DEFAULT_OPTIONS = {
    "dry_run": True,
    "compression": "deflate",
    "create_heic": HEIF_SAVE_AVAILABLE,
    "heic_quality": 100,
    "create_jpg": False,
    "jpg_quality": 95,
    "variant_policy": "smart",
    "variant_smart_archiving": True,
    "variant_smart_conversion": True,
}


@dataclass
class OpDetail:
    source: str
    action: str
    output: str
    status: str
    size_bytes: int = 0
    duration: float = 0.0
    error: str = ""

    @property
    def success(self) -> bool:
        return self.status in {"planned", "written", "moved"}


@dataclass
class ConversionResult:
    source_stem: str
    success: bool
    details: list[OpDetail] = field(default_factory=list)


@dataclass
class ConversionRunResult:
    groups: list[ConversionResult] = field(default_factory=list)
    cancelled: bool = False

# Exclude tags that are layout/pointers/binary blobs and frequently break scanner TIFF re-save.
EXCLUDED_TIFF_TAGS = {
    # Core image structure / offsets that MUST be regenerated
    254, 255, 256, 257, 258, 259, 262,
    273, 277, 278, 279, 284, 322, 323, 324, 325, 330, 338,

    # EXIF/GPS offsets and maker notes blobs
    34665, 34853, 37500,

    # XMP (often malformed in scanner output)
    700,

    # PageNumber frequently malformed
    297,
}

def _sanitize_tiff_tags(tags) -> dict:
    if not tags:
        return {}
    safe = {}
    # tags may be an IFD-like object; iterate items defensively
    for k, v in getattr(tags, "items", list)():
        try:
            tid = int(k)
        except Exception:
            continue
        if tid in EXCLUDED_TIFF_TAGS:
            continue

        # Reject big binary payloads
        if isinstance(v, (bytes, bytearray, memoryview)):
            # keep tiny binary (rare) but drop large packets
            if len(v) > 128:
                continue
            safe[tid] = bytes(v)
            continue

        # Normalize rationals
        if isinstance(v, IFDRational):
            safe[tid] = float(v)
            continue

        # Keep primitive types and small tuples/lists of primitives
        if isinstance(v, (int, float, str)):
            if isinstance(v, str) and len(v) > 1024:
                continue
            safe[tid] = v
            continue

        if isinstance(v, (tuple, list)):
            if len(v) > 16:
                continue
            out = []
            ok = True
            for e in v:
                if isinstance(e, IFDRational):
                    out.append(float(e))
                elif isinstance(e, (int, float, str)):
                    out.append(e)
                else:
                    ok = False
                    break
            if ok:
                safe[tid] = tuple(out)
            continue

        # Drop everything else
    return safe

def _atomic_replace_temp(dest: Path, write_fn: Callable[[Path], None], cancel_event=None):
    """Write beside ``dest`` and publish atomically without overwriting."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise FileExistsError(f"Destination already exists: {dest}")

    fd, tmp = tempfile.mkstemp(
        prefix=f".{dest.name}.tmp.",
        suffix=(dest.suffix or ""),
        dir=str(dest.parent),
    )
    os.close(fd)
    tmp_path = Path(tmp)

    try:
        _check_cancel(cancel_event)
        write_fn(tmp_path)
        _check_cancel(cancel_event)
        # The temp file is on the same filesystem. A hard-link publication is
        # atomic and fails with EEXIST if another process won the race; unlike
        # os.replace(), it can never clobber an existing output.
        os.link(tmp_path, dest)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

def _check_cancel(cancel_event):
    """Checks if cancellation was requested and raises exception to stop flow."""
    if cancel_event and cancel_event.is_set():
        raise OperationCancelled("Process cancelled by user.")


def _validated_options(options: dict | None) -> dict:
    provided = dict(options or {})
    unknown = set(provided) - (set(DEFAULT_OPTIONS) | {"cancel_event"})
    if unknown:
        raise ValueError(f"Unknown converter options: {', '.join(sorted(unknown))}")
    opts = {**DEFAULT_OPTIONS, **provided}
    if opts["compression"] not in {"deflate", "lzw"}:
        raise ValueError("compression must be 'deflate' or 'lzw'")
    if opts["variant_policy"] not in {"smart", "base", "augment", "none"}:
        raise ValueError("variant_policy must be smart, base, augment, or none")
    for key in ("heic_quality", "jpg_quality"):
        value = opts[key]
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
            raise ValueError(f"{key} must be an integer from 0 to 100")
    for key in ("dry_run", "create_heic", "create_jpg",
                "variant_smart_archiving", "variant_smart_conversion"):
        if not isinstance(opts[key], bool):
            raise TypeError(f"{key} must be boolean")
    return opts


def process_epson_folder(folder_path: Path, options: dict,
                         progress_callback: Callable,
                         log_callback: Callable) -> ConversionRunResult:
    def _log(msg):
        if log_callback: log_callback(msg)
        else: logger.info(msg)

    opts = _validated_options(options)
    folder_path = Path(folder_path)
    if not folder_path.is_dir():
        raise ValueError(f"Source folder does not exist: {folder_path}")
    if folder_path.is_symlink():
        raise ValueError("Source folder cannot be a symlink")
    run_result = ConversionRunResult()

    # 1. Extract Options
    dry_run = opts['dry_run']
    create_tiff = True  # Lossless TIFF is the mandatory workflow output.
    compression = opts['compression']
    create_heic = opts['create_heic']
    heic_quality = opts['heic_quality']
    create_jpg = opts['create_jpg']
    jpg_quality = opts['jpg_quality']

    # FastFoto Workflow
    ff_policy = opts['variant_policy']
    ff_smart_archive = opts['variant_smart_archiving']
    ff_smart_convert = opts['variant_smart_conversion']

    cancel_event = opts.get('cancel_event')
    if cancel_event and cancel_event.is_set():
        run_result.cancelled = True
        return run_result

    # 2. Directory Setup
    dirs = {
        'originals': folder_path / "originals",
        'lossless': folder_path / "lossless_compressed",
        'archive': folder_path / "lossless_compressed" / "archive",
        'heic': folder_path / "HEIC",
        'jpg': folder_path / "JPG"
    }
    source_root = folder_path.resolve()
    for output_dir in dirs.values():
        resolved = output_dir.resolve(strict=False)
        if source_root != resolved and source_root not in resolved.parents:
            raise ValueError(f"Output directory resolves outside source: {output_dir}")

    # 3. Scanning — exact root-level .tif/.tiff files only.
    tiff_files = sorted(
        f for f in folder_path.iterdir()
        if f.is_file() and not f.is_symlink() and f.suffix.lower() in {'.tif', '.tiff'}
    )

    if not tiff_files:
        _log("No TIFF files found in source directory.")
        return run_result

    groups = group_variants(tiff_files)
    results = run_result.groups
    total_groups = len(groups)

    try:
        for idx, (stem, variants) in enumerate(groups.items(), 1):
            _check_cancel(cancel_event)
            _log(f"Processing group [{idx}/{total_groups}]: {stem}")

            # 4. Smart Analysis
            # Separate backsides (Epson FastFoto denotes backs with _b)
            backs = [v for v in variants if v.stem.lower().endswith('_b')]
            fronts = [v for v in variants if not v.stem.lower().endswith('_b')]
            
            selected_fronts = []
            rejected_fronts = []

            if not fronts:
                pass
            elif ff_policy == 'none' or len(fronts) == 1:
                selected_fronts = fronts
            else:
                # Map UI policy to analysis internal policy
                p_map = {'smart': 'auto', 'base': 'prefer_base', 'augment': 'prefer_a'}
                try:
                    # Pass cancel_event down to allow interrupting heavy NumPy calcs
                    winner, reason = choose_best_variant(fronts, policy=p_map.get(ff_policy, 'auto'), cancel_event=cancel_event)
                    selected_fronts = [winner]
                    rejected_fronts = [f for f in fronts if f != winner]
                    _log(f"  → Selected: {winner.name} ({reason.get('reason', 'policy')})")
                except OperationCancelled:
                    raise
                except Exception as e:
                    _log(f"  ⚠ Analysis error: {e}. Defaulting to Base.")
                    selected_fronts = [fronts[0]]
                    rejected_fronts = fronts[1:]

            group_details = []
            variants_processed_successfully = []

            all_process_candidates = fronts + backs
            output_stem_counts = Counter(v.stem.casefold() for v in all_process_candidates)
            duplicate_output_stems = {
                candidate_stem for candidate_stem, count in output_stem_counts.items()
                if count > 1
            }

            # 5. Process Files
            for variant in all_process_candidates:
                _check_cancel(cancel_event)
                
                # A. Mandatory Lossless TIFF
                is_rejected = (variant in rejected_fronts)
                
                # Determine destination: Archive if rejected & smart archive ON, else standard lossless folder
                target_dir = dirs['archive'] if (is_rejected and ff_smart_archive) else dirs['lossless']
                
                # Suffix logic
                suffix = ".ZIP.TIF" if compression == 'deflate' else ".LZW.TIF"
                dest_tiff = target_dir / f"{variant.stem}{suffix}"
                
                tiff_success = False
                if create_tiff:
                    detail = OpDetail(
                        source=variant.name,
                        action=f"TIFF-{compression.upper()}",
                        output=str(dest_tiff.relative_to(folder_path)),
                        status="planned" if dry_run else "pending",
                    )
                    t0 = time.time()

                    if variant.stem.casefold() in duplicate_output_stems:
                        detail.status = "skipped_collision"
                        detail.error = "Multiple inputs map to the same output"
                        group_details.append(detail)
                        continue
                    original_dest = dirs['originals'] / variant.name
                    if original_dest.exists():
                        detail.status = "skipped_collision"
                        detail.error = "Original archive target already exists"
                        group_details.append(detail)
                        continue

                    try:
                        if dest_tiff.exists():
                            detail.status = "skipped_collision"
                            _log(f"  Skip existing output: {detail.output}")
                        elif dry_run:
                            tiff_success = True
                            variants_processed_successfully.append(variant)
                        else:
                            _save_tiff(variant, dest_tiff, compression, cancel_event)
                            detail.size_bytes = dest_tiff.stat().st_size
                            detail.status = "written"
                            tiff_success = True
                            variants_processed_successfully.append(variant)
                    except OperationCancelled:
                        detail.status = "cancelled"
                        raise
                    except Exception as e:
                        detail.status = "failed"
                        detail.error = str(e)
                        _log(f"  Error (TIFF): {e}")
                    
                    detail.duration = round(time.time() - t0, 3)
                    group_details.append(detail)
                else:
                    tiff_success = True
                    variants_processed_successfully.append(variant)

                # B. Conversions (HEIC/JPG)
                # Logic: Convert if it's a "Select", a "Backside", or if Smart Conversion is DISABLED
                should_convert = (variant in selected_fronts) or (variant in backs) or (not ff_smart_convert)

                if should_convert and tiff_success:
                    # HEIC
                    if create_heic and HEIF_SAVE_AVAILABLE:
                        h_dest = dirs['heic'] / f"{variant.stem}.heic"
                        h_det = OpDetail(
                            source=variant.name,
                            action="HEIC",
                            output=str(h_dest.relative_to(folder_path)),
                            status="planned" if dry_run else "pending",
                        )
                        t0 = time.time()
                        try:
                            if not dry_run:
                                _save_image(variant, h_dest, "HEIF", heic_quality, cancel_event)
                                h_det.size_bytes = h_dest.stat().st_size
                                h_det.status = "written"
                        except OperationCancelled:
                            h_det.status = "cancelled"
                            raise
                        except Exception as e:
                            h_det.status = "failed"
                            h_det.error = str(e)
                        h_det.duration = round(time.time() - t0, 3)
                        group_details.append(h_det)
                    
                    # JPG
                    if create_jpg:
                        j_dest = dirs['jpg'] / f"{variant.stem}.jpg"
                        j_det = OpDetail(
                            source=variant.name,
                            action="JPG",
                            output=str(j_dest.relative_to(folder_path)),
                            status="planned" if dry_run else "pending",
                        )
                        t0 = time.time()
                        try:
                            if not dry_run:
                                _save_image(variant, j_dest, "JPEG", jpg_quality, cancel_event)
                                j_det.size_bytes = j_dest.stat().st_size
                                j_det.status = "written"
                        except OperationCancelled:
                            j_det.status = "cancelled"
                            raise
                        except Exception as e:
                            j_det.status = "failed"
                            j_det.error = str(e)
                        j_det.duration = round(time.time() - t0, 3)
                        group_details.append(j_det)

            # 6. Move Originals
            if not dry_run:
                for variant in variants_processed_successfully:
                    _check_cancel(cancel_event)
                    try:
                        original_dest = dirs['originals'] / variant.name
                        original_dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(variant), str(original_dest))
                        group_details.append(OpDetail(
                            variant.name, "MOVE_ORIGINAL",
                            str(original_dest.relative_to(folder_path)), "moved"
                        ))
                    except Exception as e:
                        _log(f"  Failed to move original {variant.name}: {e}")
                        group_details.append(OpDetail(
                            variant.name, "MOVE_ORIGINAL", "originals/", "failed",
                            error=str(e)
                        ))

            group_success = bool(group_details) and all(d.success for d in group_details)
            results.append(ConversionResult(stem, group_success, group_details))
            
            # Progress Update
            progress_callback((idx / total_groups) * 100)

    except OperationCancelled:
        _log("🛑 Process Cancelled.")
        run_result.cancelled = True
        return run_result

    return run_result

def _save_tiff(src: Path, dest: Path, algo: str, cancel_event):
    comp = "tiff_adobe_deflate" if algo == "deflate" else "tiff_lzw"

    def _write(tmp_path: Path):
        with Image.open(src) as img:
            frames = []
            expected = []
            frame_count = getattr(img, "n_frames", 1)
            for index in range(frame_count):
                _check_cancel(cancel_event)
                img.seek(index)
                frame = img.copy()
                frames.append(frame)
                expected.append((frame.size, frame.mode, frame.getpixel((0, 0))))

            info = dict(img.info)
            save_kwargs = {
                "format": "TIFF",
                "compression": comp,
                "save_all": len(frames) > 1,
                "append_images": frames[1:],
            }
            for key in ("icc_profile", "dpi", "exif"):
                if info.get(key) is not None:
                    save_kwargs[key] = info[key]
            frames[0].save(tmp_path, **save_kwargs)

        # Reopen and validate every page before the temp file is publishable.
        with Image.open(tmp_path) as check:
            if getattr(check, "n_frames", 1) != len(expected):
                raise RuntimeError("TIFF verification failed: page count changed")
            for index, (size, mode, sample_pixel) in enumerate(expected):
                check.seek(index)
                if check.size != size or check.mode != mode:
                    raise RuntimeError("TIFF verification failed: dimensions or mode changed")
                if check.getpixel((0, 0)) != sample_pixel:
                    raise RuntimeError("TIFF verification failed: pixel data changed")

    _atomic_replace_temp(dest, _write, cancel_event=cancel_event)

def _save_image(src, dest, fmt, qual, cancel_event):
    def _write(tmp_path: Path):
        with Image.open(src) as img:
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(tmp_path, format=fmt, quality=qual)

    _atomic_replace_temp(dest, _write, cancel_event=cancel_event)

def save_report(results: list[ConversionResult], output_path: Path):
    data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_groups": len(results),
            "successful_groups": sum(1 for r in results if r.success),
            "total_operations": sum(len(r.details) for r in results)
        },
        "groups": [
            {
                "group": r.source_stem,
                "success": r.success,
                "ops": [vars(d) for d in r.details]
            } for r in results
        ]
    }
    try:
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save report: {e}")
