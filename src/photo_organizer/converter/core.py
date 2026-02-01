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
    dry_run: bool = False
) -> ConversionResult:
    """Create an LZW-compressed copy of a TIFF file."""
    start_time = time.time()

    result = ConversionResult(
        source_path=str(source_path),
        output_path=str(output_path),
        conversion_type="LZW",
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
            bit_depth = get_bit_depth(img)
            
            # Preserve EXIF and other metadata
            exif = img.info.get("exif")
            icc_profile = img.info.get("icc_profile")

            # Save with LZW compression
            save_kwargs = {
                "compression": "tiff_lzw",
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
                result.verified = True
            except Exception as e:
                result.warnings.append(f"Verification warning: {str(e)}")
                result.verified = False

    except Exception as e:
        result.error_message = str(e)
        result.success = False

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
    
    # LZW conversion
    if options.get("create_lzw", True):
        lzw_output = output_dir / f"{file_path.stem}_lzw.tif"
        results.append(create_lzw_copy(file_path, lzw_output))
    
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
