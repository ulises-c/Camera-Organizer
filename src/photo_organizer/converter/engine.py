"""
TIFF Converter Core - Professional Workflow
Handles parallel processing, smart archiving, and multi-format output.
"""
import logging
import shutil
import time
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Callable, Dict, Optional
from dataclasses import dataclass, field, asdict
import os

try:
    from PIL import Image
    import pillow_heif
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
from photo_organizer.converter.variant_selection import group_variants, choose_best_variant, OperationCancelled

logger = logging.getLogger(__name__)

@dataclass
class OpDetail:
    source: str
    action: str
    output: str
    success: bool
    size_bytes: int = 0
    duration: float = 0.0
    error: str = ""

@dataclass
class ConversionResult:
    source_stem: str
    success: bool
    details: List[OpDetail] = field(default_factory=list)

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
    for k, v in getattr(tags, "items", lambda: [])():
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
    """
    Write to a temp file in dest.parent then atomically move into place.
    IMPORTANT: temp file uses dest.suffix so Pillow can infer format if needed.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp = tempfile.mkstemp(
        prefix=f".{dest.name}.tmp.",
        suffix=(dest.suffix or ""),
        dir=str(dest.parent),
    )
    os.close(fd)
    tmp_path = Path(tmp)

    try:
        if cancel_event is not None and getattr(cancel_event, "is_set", lambda: False)():
            raise OperationCancelled("Process cancelled by user.")
        write_fn(tmp_path)
        os.replace(tmp_path, dest)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

def _check_cancel(cancel_event):
    """Checks if cancellation was requested and raises exception to stop flow."""
    if cancel_event and cancel_event.is_set():
        raise OperationCancelled("Process cancelled by user.")

def process_epson_folder(folder_path: Path, options: dict, progress_callback: Callable, log_callback: Callable) -> List[ConversionResult]:
    def _log(msg):
        if log_callback: log_callback(msg)
        else: logger.info(msg)

    # 1. Extract Options
    dry_run = options.get('dry_run', True)
    create_tiff = True # Forced by requirements
    compression = options.get('compression', 'deflate')  # 'deflate' (ZIP) or 'lzw'
    create_heic = options.get('create_heic', True)
    heic_quality = options.get('heic_quality', 100)
    create_jpg = options.get('create_jpg', False)
    jpg_quality = options.get('jpg_quality', 95)
    
    # FastFoto Workflow
    ff_policy = options.get('variant_policy', 'smart')
    ff_smart_archive = options.get('variant_smart_archiving', True)
    ff_smart_convert = options.get('variant_smart_conversion', True)
    
    cancel_event = options.get('cancel_event')

    # 2. Directory Setup
    dirs = {
        'originals': folder_path / "originals",
        'lossless': folder_path / "lossless_compressed",
        'archive': folder_path / "lossless_compressed" / "archive",
        'heic': folder_path / "HEIC",
        'jpg': folder_path / "JPG"
    }

    if not dry_run:
        for d in dirs.values():
            d.mkdir(parents=True, exist_ok=True)

    # 3. Scanning
    # Get all TIFFs that are in the root folder (exclude subfolders)
    tiff_files = [f for f in folder_path.glob("*.[tT][iI][fF]*") if f.is_file() and f.parent == folder_path]
    
    if not tiff_files:
        _log("No TIFF files found in source directory.")
        return []

    groups = group_variants(tiff_files)
    results = []
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
                    detail = OpDetail(source=variant.name, action=f"TIFF-{compression.upper()}", output=dest_tiff.name, success=False)
                    t0 = time.time()
                    
                    try:
                        if not dry_run:
                            _save_tiff(variant, dest_tiff, compression, cancel_event)
                            detail.size_bytes = dest_tiff.stat().st_size
                        detail.success = True
                        tiff_success = True
                        variants_processed_successfully.append(variant)
                    except Exception as e:
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
                        h_det = OpDetail(source=variant.name, action="HEIC", output=h_dest.name, success=False)
                        t0 = time.time()
                        try:
                            if not dry_run:
                                _save_image(variant, h_dest, "HEIF", heic_quality, cancel_event)
                                h_det.size_bytes = h_dest.stat().st_size
                            h_det.success = True
                        except Exception as e:
                            h_det.error = str(e)
                        h_det.duration = round(time.time() - t0, 3)
                        group_details.append(h_det)
                    
                    # JPG
                    if create_jpg:
                        j_dest = dirs['jpg'] / f"{variant.stem}.jpg"
                        j_det = OpDetail(source=variant.name, action="JPG", output=j_dest.name, success=False)
                        t0 = time.time()
                        try:
                            if not dry_run:
                                _save_image(variant, j_dest, "JPEG", jpg_quality, cancel_event)
                                j_det.size_bytes = j_dest.stat().st_size
                            j_det.success = True
                        except Exception as e:
                            j_det.error = str(e)
                        j_det.duration = round(time.time() - t0, 3)
                        group_details.append(j_det)

            # 6. Move Originals
            if not dry_run:
                for variant in variants_processed_successfully:
                    _check_cancel(cancel_event)
                    try:
                        shutil.move(str(variant), str(dirs['originals'] / variant.name))
                        group_details.append(OpDetail(variant.name, "MOVE_ORIGINAL", "originals/", True))
                    except Exception as e:
                        _log(f"  Failed to move original {variant.name}: {e}")
                        group_details.append(OpDetail(variant.name, "MOVE_ORIGINAL", "originals/", False, error=str(e)))

            results.append(ConversionResult(stem, True, group_details))
            
            # Progress Update
            progress_callback((idx / total_groups) * 100)

    except OperationCancelled:
        _log("🛑 Process Cancelled.")
        return results
    except Exception as e:
        _log(f"❌ Fatal Error: {e}")
        logger.exception("Core loop crash")
        
    return results

def _save_tiff(src: Path, dest: Path, algo: str, cancel_event):
    # Pillow TIFF compression names vary; these are commonly supported:
    # - "tiff_lzw"
    # - "tiff_adobe_deflate" (best default; “ZIP-like”)
    comp = "tiff_adobe_deflate" if algo in ("deflate", "adobe_deflate", "zip") else "tiff_lzw"

    def _write(tmp_path: Path):
        with Image.open(src) as img:
            icc = img.info.get("icc_profile")
            exif = None
            try:
                ex = img.getexif()
                if ex:
                    exif = ex.tobytes()
            except Exception:
                exif = None

            # Robust default: do not attempt full TIFF tag round-trip
            img.save(
                tmp_path,
                format="TIFF",
                compression=comp,
                icc_profile=icc,
                exif=exif,
            )

    _atomic_replace_temp(dest, _write, cancel_event=cancel_event)

def _save_image(src, dest, fmt, qual, cancel_event):
    def _write(tmp_path: Path):
        with Image.open(src) as img:
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.save(tmp_path, format=fmt, quality=qual)

    _atomic_replace_temp(dest, _write, cancel_event=cancel_event)

def save_report(results: List[ConversionResult], output_path: Path):
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
