"""
TIFF to LZW/HEIC Converter - Core Logic
Handles TIFF conversion with metadata preservation.
"""
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

try:
    from PIL import Image
except ImportError:
    raise ImportError("Pillow is required. Install with: pip install Pillow")

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
except ImportError:
    raise ImportError("pillow-heif is required. Install with: pip install pillow-heif")


@dataclass
class ConversionResult:
    """Result of a single conversion operation."""
    source_path: str
    output_path: str
    conversion_type: str
    success: bool
    source_size_bytes: int
    output_size_bytes: int = 0
    compression_ratio: float = 0.0
    verified: bool = False
    error_message: str = ""
    warnings: list = field(default_factory=list)
    duration_seconds: float = 0.0


def get_bit_depth(img: Image.Image) -> int:
    """Determine the bit depth of an image."""
    mode = img.mode

    # Mode to bit depth mapping
    bit_depths = {
        "1": 1,
        "L": 8,
        "P": 8,
        "RGB": 8,
        "RGBA": 8,
        "CMYK": 8,
        "YCbCr": 8,
        "LAB": 8,
        "HSV": 8,
        "I": 32,
        "F": 32,
        "I;16": 16,
        "I;16L": 16,
        "I;16B": 16,
        "I;16N": 16,
        "RGB;16": 16,
        "RGBA;16": 16,
    }

    # Check for 16-bit modes
    if hasattr(img, 'tag_v2'):
        bits_per_sample = img.tag_v2.get(258)  # BitsPerSample tag
        if bits_per_sample:
            if isinstance(bits_per_sample, tuple):
                return max(bits_per_sample)
            return bits_per_sample

    return bit_depths.get(mode, 8)


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
        conversion_type="lzw",
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
        conversion_type="heic",
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
