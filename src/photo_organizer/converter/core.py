"""
TIFF Converter Core - Parallel processing and conversion logic.
Migrated from tiff-to-heic project with full functionality preserved.
"""
import time
import json
import logging
import shutil
from pathlib import Path
from typing import List, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime

try:
    from PIL import Image
except ImportError:
    raise ImportError("Pillow is required. Install with: pip install Pillow")

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    raise ImportError("pillow-heif is required. Install with: pip install pillow-heif")

from photo_organizer.shared.image_utils import get_bit_depth, format_size

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Test HEIF save capability at module load
HEIF_SAVE_AVAILABLE = False
try:
    test_img = Image.new('RGB', (2, 2), color=(255, 0, 0))
    import tempfile
    tf = Path(tempfile.gettempdir()) / "photo_organizer_heif_test.heic"
    test_img.save(tf, format="HEIF", quality=90)
    if tf.exists():
        HEIF_SAVE_AVAILABLE = True
        tf.unlink(missing_ok=True)
except Exception:
    HEIF_SAVE_AVAILABLE = False


@dataclass
class ConversionResult:
    """Result of a single file conversion operation."""
    source_path: str
    output_path: str
    conversion_type: str  # "LZW" or "HEIC"
    success: bool
    source_size_bytes: int
    output_size_bytes: int = 0
    compression_ratio: float = 0.0
    verified: bool = False
    error_message: str = ""
    warnings: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0


def _init_worker():
    """Initialize worker process - critical for macOS 'spawn' method."""
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except Exception:
        pass


def create_heic_copy(
    source_path: Path,
    output_path: Path,
    quality: int = -1,
    verify: bool = True,
    dry_run: bool = False
) -> ConversionResult:
    """Create an HEIC copy of a TIFF file with robust error handling."""
    start_time = time.time()

    result = ConversionResult(
        source_path=str(source_path),
        output_path=str(output_path),
        conversion_type="HEIC",
        success=False,
        source_size_bytes=source_path.stat().st_size
    )

    if dry_run:
        result.success = True
        result.output_size_bytes = 0
        result.warnings.append("DRY RUN - no files written")
        result.duration_seconds = time.time() - start_time
        logger.info(f"DRY RUN: simulated HEIC for {source_path.name}")
        return result

    if not HEIF_SAVE_AVAILABLE:
        result.error_message = "HEIF/HEIC saving not available (libheif/pillow-heif missing or broken)"
        result.success = False
        logger.error(f"HEIC conversion failed for {source_path.name}: {result.error_message}")
        result.duration_seconds = time.time() - start_time
        return result

    try:
        with Image.open(source_path) as img:
            # Check bit depth and preserve metadata BEFORE conversion
            bit_depth = get_bit_depth(img)
            exif = img.info.get("exif")
            icc_profile = img.info.get("icc_profile")

            if bit_depth > 8:
                result.warnings.append(
                    f"High bit depth ({bit_depth}-bit) converted to 8-bit for HEIC. "
                    "Potential quality/precision loss may occur."
                )

            # Aggressive mode normalization for HEIC compatibility
            if img.mode in ("RGBA", "LA"):
                img = img.convert("RGB")
            elif img.mode == "P":
                img = img.convert("RGB")
            
            # Handle 16-bit/Float images - convert to 8-bit
            if img.mode in ("I", "I;16", "I;16L", "I;16B", "I;16N", "F"):
                import numpy as np
                arr = np.array(img)
                if arr.dtype in (np.float32, np.float64):
                    arr = np.clip(arr * 255, 0, 255).astype(np.uint8)
                else:
                    arr = (arr >> 8).astype(np.uint8) if arr.max() > 255 else arr.astype(np.uint8)
                img = Image.fromarray(arr)
            
            # Final safety check
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Save with multiple fallback attempts
            save_kwargs = {}
            if quality == -1:
                save_kwargs["quality"] = -1
            else:
                save_kwargs["quality"] = quality

            if exif:
                save_kwargs["exif"] = exif
            if icc_profile:
                save_kwargs["icc_profile"] = icc_profile

            saved = False
            save_errors = []

            # Try multiple format specifications
            for fmt in ("HEIF", None):
                try:
                    if fmt:
                        img.save(output_path, format=fmt, **save_kwargs)
                    else:
                        img.save(output_path, **save_kwargs)
                    saved = True
                    break
                except Exception as e:
                    save_errors.append((fmt or "auto", str(e)))
                    # Fallback: if lossless (-1) failed, try high quality
                    if quality == -1 and not saved:
                        try:
                            fallback_kwargs = save_kwargs.copy()
                            fallback_kwargs["quality"] = 95
                            if fmt:
                                img.save(output_path, format=fmt, **fallback_kwargs)
                            else:
                                img.save(output_path, **fallback_kwargs)
                            result.warnings.append("Lossless HEIF failed, using quality=95")
                            saved = True
                            break
                        except Exception:
                            continue

            if not saved:
                err_msg = " | ".join(f"{fmt}:{err}" for fmt, err in save_errors)
                raise RuntimeError(f"All HEIC save attempts failed: {err_msg}")

            # Verify file was actually created
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise RuntimeError("HEIC file created but is empty or missing")

        result.output_size_bytes = output_path.stat().st_size
        result.compression_ratio = result.source_size_bytes / \
            result.output_size_bytes if result.output_size_bytes > 0 else 0
        result.success = True

        # Verify if requested
        if verify:
            try:
                with Image.open(output_path) as verify_img:
                    verify_img.verify()
                result.verified = True
            except Exception as e:
                result.warnings.append(f"Verification warning: {str(e)}")
                result.verified = False

    except Exception as e:
        result.error_message = str(e)
        result.success = False
        logger.exception(f"HEIC conversion failed for {source_path.name}: {e}")

    result.duration_seconds = time.time() - start_time
    return result


def create_lzw_copy(
    source_path: Path,
    output_path: Path,
    verify: bool = True,
    dry_run: bool = False,
    compression: str = 'lzw'
) -> ConversionResult:
    """Create a compressed copy of a TIFF file with configurable compression."""
    start_time = time.time()

    result = ConversionResult(
        source_path=str(source_path),
        output_path=str(output_path),
        conversion_type=f"TIFF-{compression.upper()}",
        success=False,
        source_size_bytes=source_path.stat().st_size
    )

    if dry_run:
        result.success = True
        result.output_size_bytes = 0
        result.warnings.append("DRY RUN - no files written")
        result.duration_seconds = time.time() - start_time
        logger.info(f"DRY RUN: simulated {compression.upper()} for {source_path.name}")
        return result

    try:
        compression_map = {
            'lzw': 'tiff_lzw',
            'deflate': 'tiff_adobe_deflate'
        }
        
        with Image.open(source_path) as img:
            bit_depth = get_bit_depth(img)
            
            # Preserve EXIF and other metadata
            exif = img.info.get("exif")
            icc_profile = img.info.get("icc_profile")

            # Save with specified compression
            save_kwargs = {
                "compression": compression_map.get(compression, 'tiff_lzw'),
            }
            if exif:
                save_kwargs["exif"] = exif
            if icc_profile:
                save_kwargs["icc_profile"] = icc_profile

            img.save(output_path, **save_kwargs)

        result.output_size_bytes = output_path.stat().st_size
        result.compression_ratio = result.source_size_bytes / \
            result.output_size_bytes if result.output_size_bytes > 0 else 0
        result.success = True

        # Verify if requested
        if verify:
            try:
                with Image.open(output_path) as verify_img:
                    verify_img.verify()
                    # Re-open for deeper check
                with Image.open(output_path) as verify_img:
                    _ = verify_img.load()
                result.verified = True
            except Exception as e:
                raise ValueError(f"Verification failed: {e}")

        # Calculate compression ratio
        ratio = (1 - result.output_size_bytes / result.source_size_bytes) * 100
        result.warnings.append(f"Compression: {ratio:.1f}% reduction")

    except Exception as e:
        result.error_message = str(e)
        result.success = False
        logger.error(f"LZW conversion failed for {source_path.name}: {e}")

    result.duration_seconds = time.time() - start_time
    return result




def process_single_file(file_path: Path, options: dict) -> List[ConversionResult]:
    """Process a single file with configured options."""
    results = []
    output_dir = options.get("output_dir", file_path.parent)
    compression = options.get("compression", "lzw")
    dry_run = options.get("dry_run", False)
    verify = options.get("verify", True)
    
    if options.get("create_lzw", True):
        lzw_output = output_dir / f"{file_path.stem}.LZW.tif"
        results.append(create_lzw_copy(file_path, lzw_output, verify=verify, dry_run=dry_run, compression=compression))
    
    if options.get("create_heic", False):
        heic_output = output_dir / f"{file_path.stem}.heic"
        quality = options.get("heic_quality", 90)
        results.append(create_heic_copy(file_path, heic_output, quality=quality, verify=verify, dry_run=dry_run))
    
    return results


def batch_process(
    files: List[Path],
    options: dict,
    progress_callback=None
) -> List[ConversionResult]:
    """
    Parallel batch processing with worker pool.
    
    For dry runs or single-worker scenarios, processes sequentially to avoid
    macOS spawn-related GUI hangs.
    
    Args:
        files: List of TIFF files to process
        options: Processing options dict
        progress_callback: Optional callback(completed_count, total_count)
    
    Returns:
        List of ConversionResult objects
    """
    results = []
    workers = options.get("workers", 4)
    total = len(files)
    completed = 0
    cancel_event = options.get('cancel_event', None)

    # Sequential processing for dry-run to avoid ProcessPoolExecutor issues on macOS
    if options.get("dry_run", False) or workers == 1:
        for f in files:
            # Check for cancellation
            if cancel_event and cancel_event.is_set():
                logger.info("Processing cancelled by user")
                break
            
            try:
                file_results = process_single_file(f, options)
                results.extend(file_results)
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)
            except Exception as e:
                logger.error(f"Processing error for {f}: {e}")
        return results

    # Parallel processing for production runs
    with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker) as executor:
        futures = {executor.submit(process_single_file, f, options): f for f in files}
        
        for future in as_completed(futures):
            # Check for cancellation
            if cancel_event and cancel_event.is_set():
                logger.info("Processing cancelled by user")
                break
            
            try:
                file_results = future.result()
                results.extend(file_results)
                completed += 1
                
                if progress_callback:
                    progress_callback(completed, total)
                    
            except Exception as e:
                logger.error(f"Processing error: {e}")
    
    return results


def process_epson_folder(
    folder_path: Path,
    options: dict,
    progress_callback=None
) -> List[ConversionResult]:
    """
    Process an Epson FastFoto folder with explicit backside handling.
    
    Behavior:
    - Backside (_b) files are ALWAYS converted (no quality comparison)
    - Selection only occurs between base and _a front variants
    - Option to convert all variants (skip selection entirely)
    - Originals moved only after successful conversion
    - Dry run mode: No directories created, no files written/moved
    - Cancel event: Stop processing if requested
    
    Args:
        folder_path: Source directory
        options: Configuration dict with keys:
            - variant_policy: 'auto' | 'prefer_base' | 'prefer_a'
            - compression: 'lzw' | 'deflate'
            - create_lzw: bool
            - create_heic: bool
            - heic_quality: int (-1 for lossless)
            - verify: bool
            - dry_run: bool
            - convert_all_variants: bool (skip selection, convert all)
            - cancel_event: threading.Event for cancellation
    """
    from photo_organizer.converter.variant_selection import group_variants, choose_best_variant
    
    dry_run = options.get('dry_run', False)
    convert_all = options.get('convert_all_variants', False)
    policy = options.get('variant_policy', 'auto')
    create_lzw = options.get('create_lzw', True)
    create_heic = options.get('create_heic', False)
    compression = options.get('compression', 'lzw')
    heic_quality = options.get('heic_quality', 90)
    verify = options.get('verify', True)
    cancel_event = options.get('cancel_event', None)
    
    # Create output directories
    lzw_dir = folder_path / "LZW_compressed"
    heic_dir = folder_path / "HEIC"
    uncompressed_dir = folder_path / "uncompressed"
    backside_dir = uncompressed_dir / "backside"
    
    if not dry_run:
        for d in [lzw_dir, heic_dir, uncompressed_dir, backside_dir]:
            d.mkdir(parents=True, exist_ok=True)
    
    # Find TIFF files (case-insensitive)
    tiff_files = []
    for ext in ['*.tif', '*.tiff', '*.TIF', '*.TIFF']:
        tiff_files.extend(folder_path.glob(ext))
    tiff_files = [f for f in tiff_files if f.parent == folder_path]
    
    if not tiff_files:
        logger.warning(f"No TIFF files found in {folder_path}")
        return []
    
    groups = group_variants(tiff_files)
    results = []
    total = len(groups)
    
    for idx, (stem, variants) in enumerate(groups.items(), 1):
        # Check for cancellation
        if cancel_event and cancel_event.is_set():
            logger.info("Processing cancelled by user")
            break
        
        # Partition variants (case-insensitive suffix detection)
        backside_files = [p for p in variants if p.stem.lower().endswith('_b')]
        front_candidates = [p for p in variants if not p.stem.lower().endswith('_b')]
        
        logger.info(f"[{idx}/{total}] Group {stem}: Processing variants")
        
        # Build conversion queue
        to_convert = []  # List of (Path, reason_string)
        
        # Handle front candidates
        if convert_all:
            for f in front_candidates:
                to_convert.append((f, "convert_all"))
        elif front_candidates:
            chosen, info = choose_best_variant(front_candidates, policy=policy)
            to_convert.append((chosen, info.get('reason', 'selected')))
        
        # ALWAYS add all backside files (mandatory conversion)
        for b in backside_files:
            to_convert.append((b, "backside_auto"))
        
        # Track per-file conversion success for safe archiving
        success_tracker = {}
        
        # Execute conversions
        for source_path, reason in to_convert:
            file_results = []
            
            # LZW conversion
            if create_lzw:
                out = lzw_dir / f"{source_path.stem}.LZW.tif"
                res = create_lzw_copy(
                    source_path, out,
                    verify=verify,
                    dry_run=dry_run,
                    compression=compression
                )
                res.warnings.append(f"Reason: {reason}")
                file_results.append(res)
                results.append(res)
            
            # HEIC conversion
            if create_heic:
                out = heic_dir / f"{source_path.stem}.heic"
                res = create_heic_copy(
                    source_path, out,
                    quality=heic_quality,
                    verify=verify,
                    dry_run=dry_run
                )
                res.warnings.append(f"Reason: {reason}")
                file_results.append(res)
                results.append(res)
            
            # Determine success for archiving:
            # If LZW was requested, require LZW success
            # Otherwise, require HEIC success
            primary_success = False
            if create_lzw:
                primary_success = any(r.success and r.conversion_type.startswith("TIFF") for r in file_results)
            elif create_heic:
                primary_success = any(r.success and r.conversion_type == "HEIC" for r in file_results)
            
            success_tracker[source_path] = primary_success
        
        # Archive originals (only if conversions succeeded and not dry-run)
        if not dry_run:
            for variant in variants:
                # FIXED LOGIC: Only move files that were successfully converted
                if not success_tracker.get(variant, False):
                    logger.error(f"Skipping archive for {variant.name} - conversion not successful or not attempted")
                    continue
                
                # Determine destination (case-insensitive backside detection)
                dest_dir = backside_dir if variant.stem.lower().endswith('_b') else uncompressed_dir
                dest_path = dest_dir / variant.name
                
                # Handle collisions
                if dest_path.exists():
                    counter = 1
                    base = dest_path.stem
                    ext = dest_path.suffix
                    while True:
                        new_dest = dest_dir / f"{base}_dup{counter}{ext}"
                        if not new_dest.exists():
                            dest_path = new_dest
                            break
                        counter += 1
                
                # Cross-filesystem safe move
                try:
                    shutil.move(str(variant), str(dest_path))
                    logger.info(f"Archived: {variant.name} → {dest_path.relative_to(folder_path)}")
                except Exception as e:
                    logger.error(f"Failed to archive {variant.name}: {e}")
        
        if progress_callback:
            progress_callback(idx, total)
    
    if dry_run:
        logger.info("✓ Dry run completed - no files modified")
    
    return results


def save_report(results: List[ConversionResult], output_path: Path):
    """Save processing report as JSON."""
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "total_operations": len(results),
        "successful": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
        "results": [asdict(r) for r in results]
    }
    
    with open(output_path, 'w') as f:
        json.dump(report_data, f, indent=2)
