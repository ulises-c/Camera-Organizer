"""
TIFF Converter Core - Parallel processing and conversion logic.
Migrated from tiff-to-heic project with full functionality preserved.
"""
import time
import json
import logging
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


def create_heic_copy(
    source_path: Path,
    output_path: Path,
    quality: int = -1,  # -1 means lossless
    verify: bool = True,
    dry_run: bool = False
) -> ConversionResult:
    """Create an HEIC copy of a TIFF file."""
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
        result.duration_seconds = time.time() - start_time
        return result

    try:
        with Image.open(source_path) as img:
            # Check bit depth and add warning if high
            bit_depth = get_bit_depth(img)
            if bit_depth > 8:
                result.warnings.append(
                    f"High bit depth ({bit_depth}-bit) converted to HEIC. "
                    "Potential quality/precision loss may occur."
                )

            # Convert to RGB if necessary (HEIC doesn't support all modes)
            if img.mode in ("RGBA", "LA"):
                # Keep alpha if present
                pass
            elif img.mode not in ("RGB", "L"):
                img = img.convert("RGB")

            # Handle 16-bit images - convert to 8-bit for HEIC
            if img.mode in ("I", "I;16", "I;16L", "I;16B", "I;16N", "F"):
                import numpy as np
                arr = np.array(img)
                if arr.dtype == np.float32 or arr.dtype == np.float64:
                    # Normalize float images
                    arr = ((arr - arr.min()) / (arr.max() - arr.min())
                           * 255).astype(np.uint8)
                elif arr.dtype == np.uint16 or arr.dtype == np.int32:
                    # Scale 16-bit to 8-bit
                    arr = (arr / 256).astype(np.uint8)
                else:
                    arr = arr.astype(np.uint8)
                img = Image.fromarray(arr)

            # Get EXIF data
            exif = img.info.get("exif")

            # Save as HEIC
            save_kwargs = {}
            if quality == -1:
                save_kwargs["quality"] = -1  # Lossless
            else:
                save_kwargs["quality"] = quality

            if exif:
                save_kwargs["exif"] = exif

            img.save(output_path, format="HEIF", **save_kwargs)

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

    result.duration_seconds = time.time() - start_time
    return result


def process_single_file(file_path: Path, options: dict) -> List[ConversionResult]:
    """Process a single file with configured options."""
    results = []
    
    output_dir = options.get("output_dir", file_path.parent)
    compression = options.get("compression", "lzw")
    
    # LZW conversion
    if options.get("create_lzw", True):
        lzw_output = output_dir / f"{file_path.stem}_lzw.tif"
        results.append(create_lzw_copy(file_path, lzw_output, compression=compression))
    
    # HEIC conversion
    if options.get("create_heic", False):
        heic_output = output_dir / f"{file_path.stem}.heic"
        quality = options.get("heic_quality", 90)
        results.append(create_heic_copy(file_path, heic_output, quality))
    
    return results


def batch_process(
    files: List[Path],
    options: dict,
    progress_callback=None
) -> List[ConversionResult]:
    """
    Parallel batch processing with worker pool.
    
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
    
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(process_single_file, f, options): f 
            for f in files
        }
        
        for future in as_completed(futures):
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
    Process an Epson FastFoto folder with automatic variant selection.
    
    Workflow:
    1. Group files by stem (handling _a/_b variants)
    2. Choose best front-side image per group
    3. Convert to LZW and HEIC
    4. Move originals to uncompressed/ (backside files to backside/ subfolder)
    
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
    """
    from photo_organizer.converter.variant_selection import group_variants, choose_best_variant
    
    # Create output directories
    lzw_dir = folder_path / "LZW_compressed"
    heic_dir = folder_path / "HEIC"
    uncompressed_dir = folder_path / "uncompressed"
    backside_dir = uncompressed_dir / "backside"
    
    if not options.get('dry_run', False):
        for d in [lzw_dir, heic_dir, uncompressed_dir, backside_dir]:
            d.mkdir(parents=True, exist_ok=True)
    
    # Find all TIFF files
    tiff_files = []
    for ext in ['*.tif', '*.tiff', '*.TIF', '*.TIFF']:
        tiff_files.extend(folder_path.glob(ext))
    
    # Filter out files already in subdirectories
    tiff_files = [f for f in tiff_files if f.parent == folder_path]
    
    if not tiff_files:
        logger.warning(f"No TIFF files found in {folder_path}")
        return []
    
    # Group by stem
    groups = group_variants(tiff_files)
    
    logger.info(f"Found {len(groups)} unique images with {len(tiff_files)} total files")
    
    results = []
    total = len(groups)
    
    for idx, (stem, variants) in enumerate(groups.items(), 1):
        # Choose best variant
        policy = options.get('variant_policy', 'auto')
        chosen, selection_info = choose_best_variant(variants, policy=policy)
        
        # Log selection
        logger.info(f"[{idx}/{total}] {stem}: chose {chosen.name} ({selection_info['reason']})")
        
        # Define output paths
        lzw_output = lzw_dir / f"{stem}.LZW.tif"
        heic_output = heic_dir / f"{stem}.heic"
        
        # Track current group's results separately
        group_results = []
        
        # Convert to LZW
        if options.get('create_lzw', True):
            compression = options.get('compression', 'lzw')
            res_lzw = create_lzw_copy(
                chosen,
                lzw_output,
                verify=options.get('verify', True),
                dry_run=options.get('dry_run', False),
                compression=compression
            )
            res_lzw.warnings.append(f"Selection: {selection_info['reason']}")
            if selection_info.get('ambiguous'):
                res_lzw.warnings.append("⚠️  AMBIGUOUS: Manual review recommended")
            group_results.append(res_lzw)
        
        # Convert to HEIC
        if options.get('create_heic', True):
            quality = options.get('heic_quality', 90)
            res_heic = create_heic_copy(
                chosen,
                heic_output,
                quality=quality,
                verify=options.get('verify', True),
                dry_run=options.get('dry_run', False)
            )
            res_heic.warnings.append(f"Selection: {selection_info['reason']}")
            if selection_info.get('ambiguous'):
                res_heic.warnings.append("⚠️  AMBIGUOUS: Manual review recommended")
            group_results.append(res_heic)
        
        # Add to master results
        results.extend(group_results)
        
        # Move originals only if THIS group's conversions succeeded
        if (not options.get('dry_run', False) and 
            group_results and 
            all(r.success for r in group_results)):
            
            for variant in variants:
                try:
                    # Determine destination
                    if variant.stem.endswith('_b'):
                        dest = backside_dir / variant.name
                    else:
                        dest = uncompressed_dir / variant.name
                    
                    # Handle duplicates
                    if dest.exists():
                        counter = 1
                        base = dest.stem
                        ext = dest.suffix
                        while True:
                            new_dest = dest.parent / f"{base}_dup{counter}{ext}"
                            if not new_dest.exists():
                                dest = new_dest
                                break
                            counter += 1
                    
                    # Move file
                    variant.rename(dest)
                    logger.debug(f"Moved {variant.name} → {dest.relative_to(folder_path)}")
                    
                except Exception as e:
                    logger.error(f"Failed to move {variant.name}: {e}")
        
        if progress_callback:
            progress_callback(idx, total)
    
    return results


def save_report(results: List[ConversionResult], output_path: Path):
    """Save processing report as JSON."""
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "total_files": len(results),
        "successful": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
        "results": [asdict(r) for r in results]
    }
    
    with open(output_path, 'w') as f:
        json.dump(report_data, f, indent=2)
    
    logger.info(f"Report saved to {output_path}")
