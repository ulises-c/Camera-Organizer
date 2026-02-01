# Ensemble Leader Synthesis

Generated: 2026-01-31T22:20:15-08:00
Leader Model: claude-sonnet-4-5
Duration: 92.86s

---

## Original Request

I have merged 2 projects into one and refactored them. I want to go through the functionality of the "TIFF to HEIC Converter".

Background knowledge: I am using 2 scanners, Epson FastFoto FF-680W & Epson Perfection V39 II, and these output uncompressed TIFF files. The FF-680W also has extra ouputs `<file>_a.TIFF` is an augmented photo and `<file>_b.TIFF` is the backside of the photo (duplex scanning, only scanned if something dark is on the back of the photo, like a note or date). I am still unsure what to do about these since the `_a` files are duplicates, and usually they're nicer but not always. Sometimes they're oversaturated or overexposed. Think of a possible solution for this, maybe ML analysis to see which is more pleasing? I'm not sure.

The main priority of this module in this project is to output `<file>.LZW.TIFF` and `<file>.heic` and then store uncompressed files in a folder in the same directory, to later archive or discard. I want to use LZW compression since I read that it was lossless compression. Let me know of any better solutions.

Example: `2000_May/<files>` should be compressed and converted, and the originals stored in `2000_May/uncompressed`, and the others in `2000_May/HEIC` & `200_May/LZW_compressed`.

Actual data below:

```sh
ulises@Ulisess-Mac-mini Camera % cd /Users/ulises/Documents/Epson\ FastFoto\ FF-680W/2000_May
ulises@Ulisess-Mac-mini 2000_May % ls -l
total 5126656
-rw-------  1 ulises  staff  32422607 Jan 31 17:36 2000_May_0001_a.tif
-rw-------  1 ulises  staff  32422607 Jan 31 17:36 2000_May_0001.tif
-rw-------  1 ulises  staff  32590211 Jan 31 17:36 2000_May_0002_a.tif
-rw-------  1 ulises  staff  32590211 Jan 31 17:36 2000_May_0002.tif
-rw-------  1 ulises  staff  32524863 Jan 31 17:36 2000_May_0003_a.tif
-rw-------  1 ulises  staff  32524863 Jan 31 17:36 2000_May_0003.tif
-rw-------  1 ulises  staff  32716043 Jan 31 17:36 2000_May_0004_a.tif
-rw-------  1 ulises  staff  32716043 Jan 31 17:36 2000_May_0004.tif
-rw-------  1 ulises  staff  32739387 Jan 31 17:36 2000_May_0005_a.tif
-rw-------  1 ulises  staff  32739387 Jan 31 17:36 2000_May_0005.tif
-rw-------  1 ulises  staff  32814323 Jan 31 17:36 2000_May_0006_a.tif
-rw-------  1 ulises  staff  32814323 Jan 31 17:36 2000_May_0006.tif
-rw-------  1 ulises  staff  32870411 Jan 31 17:36 2000_May_0007_a.tif
-rw-------  1 ulises  staff  32870411 Jan 31 17:36 2000_May_0007.tif
-rw-------  1 ulises  staff  33033995 Jan 31 17:36 2000_May_0008_a.tif
-rw-------  1 ulises  staff  33033995 Jan 31 17:36 2000_May_0008.tif
-rw-------  1 ulises  staff  32468871 Jan 31 17:36 2000_May_0009_a.tif
-rw-------  1 ulises  staff  32468871 Jan 31 17:36 2000_May_0009.tif
-rw-------  1 ulises  staff  32594563 Jan 31 17:36 2000_May_0010_a.tif
-rw-------  1 ulises  staff  32594563 Jan 31 17:36 2000_May_0010.tif
-rw-------  1 ulises  staff  32697323 Jan 31 17:36 2000_May_0011_a.tif
-rw-------  1 ulises  staff  32697323 Jan 31 17:36 2000_May_0011.tif
-rw-------  1 ulises  staff  32659883 Jan 31 17:36 2000_May_0012_a.tif
-rw-------  1 ulises  staff  32659883 Jan 31 17:36 2000_May_0012.tif
-rw-------  1 ulises  staff  33071883 Jan 31 17:36 2000_May_0013_a.tif
-rw-------  1 ulises  staff  33071883 Jan 31 17:36 2000_May_0013.tif
-rw-------  1 ulises  staff  32846731 Jan 31 17:36 2000_May_0014_a.tif
-rw-------  1 ulises  staff  32846731 Jan 31 17:36 2000_May_0014.tif
-rw-------  1 ulises  staff  31982427 Jan 31 17:36 2000_May_0015_a.tif
-rw-------  1 ulises  staff  31982427 Jan 31 17:36 2000_May_0015.tif
-rw-------  1 ulises  staff  33001283 Jan 31 17:36 2000_May_0016_a.tif
-rw-------  1 ulises  staff  33001283 Jan 31 17:36 2000_May_0016.tif
-rw-------  1 ulises  staff  32561723 Jan 31 17:36 2000_May_0017_a.tif
-rw-------  1 ulises  staff  32561723 Jan 31 17:36 2000_May_0017.tif
-rw-------  1 ulises  staff  32739487 Jan 31 17:36 2000_May_0018_a.tif
-rw-------  1 ulises  staff  32739487 Jan 31 17:36 2000_May_0018.tif
-rw-------  1 ulises  staff  33104931 Jan 31 17:36 2000_May_0019_a.tif
-rw-------  1 ulises  staff  33104931 Jan 31 17:36 2000_May_0019.tif
-rw-------  1 ulises  staff  33172371 Jan 31 17:36 2000_May_0020_a.tif
-rw-------  1 ulises  staff  33172371 Jan 31 17:36 2000_May_0020.tif
-rw-------  1 ulises  staff  32702371 Jan 31 17:36 2000_May_0021_a.tif
-rw-------  1 ulises  staff  32702371 Jan 31 17:36 2000_May_0021.tif
-rw-------  1 ulises  staff  32546867 Jan 31 17:36 2000_May_0022_a.tif
-rw-------  1 ulises  staff  32546867 Jan 31 17:36 2000_May_0022.tif
-rw-------  1 ulises  staff  33170731 Jan 31 17:36 2000_May_0023_a.tif
-rw-------  1 ulises  staff  33170731 Jan 31 17:36 2000_May_0023.tif
-rw-------  1 ulises  staff  32947027 Jan 31 17:36 2000_May_0024_a.tif
-rw-------  1 ulises  staff  32947027 Jan 31 17:36 2000_May_0024.tif
-rw-------  1 ulises  staff  32370731 Jan 31 17:36 2000_May_0025_a.tif
-rw-------  1 ulises  staff  32370731 Jan 31 17:36 2000_May_0025.tif
-rw-------  1 ulises  staff  33203507 Jan 31 17:36 2000_May_0026_a.tif
-rw-------  1 ulises  staff  33203507 Jan 31 17:36 2000_May_0026.tif
-rw-------  1 ulises  staff  32735747 Jan 31 17:36 2000_May_0027_a.tif
-rw-------  1 ulises  staff  32735747 Jan 31 17:36 2000_May_0027.tif
-rw-------  1 ulises  staff  33112843 Jan 31 17:36 2000_May_0028_a.tif
-rw-------  1 ulises  staff  33112843 Jan 31 17:36 2000_May_0028.tif
-rw-------  1 ulises  staff  33154843 Jan 31 17:36 2000_May_0029_a.tif
-rw-------  1 ulises  staff  33154843 Jan 31 17:36 2000_May_0029.tif
-rw-------  1 ulises  staff  32646363 Jan 31 17:36 2000_May_0030_a.tif
-rw-------  1 ulises  staff  32646363 Jan 31 17:36 2000_May_0030.tif
-rw-------  1 ulises  staff  32940775 Jan 31 17:36 2000_May_0031_a.tif
-rw-------  1 ulises  staff  32940775 Jan 31 17:36 2000_May_0031.tif
-rw-------  1 ulises  staff  32706063 Jan 31 17:36 2000_May_0032_a.tif
-rw-------  1 ulises  staff  32706063 Jan 31 17:36 2000_May_0032.tif
-rw-------  1 ulises  staff  32937563 Jan 31 17:36 2000_May_0033_a.tif
-rw-------  1 ulises  staff  32937563 Jan 31 17:36 2000_May_0033.tif
-rw-------  1 ulises  staff  33164699 Jan 31 17:36 2000_May_0034_a.tif
-rw-------  1 ulises  staff  33164699 Jan 31 17:36 2000_May_0034.tif
-rw-------  1 ulises  staff  32504327 Jan 31 17:36 2000_May_0035_a.tif
-rw-------  1 ulises  staff  32504327 Jan 31 17:36 2000_May_0035.tif
-rw-------  1 ulises  staff  33095375 Jan 31 17:36 2000_May_0036_a.tif
-rw-------  1 ulises  staff  33095375 Jan 31 17:36 2000_May_0036.tif
-rw-------  1 ulises  staff  33109163 Jan 31 17:36 2000_May_0037_a.tif
-rw-------  1 ulises  staff  33109163 Jan 31 17:36 2000_May_0037.tif
-rw-------  1 ulises  staff  33024923 Jan 31 17:36 2000_May_0038_a.tif
-rw-------  1 ulises  staff  33024923 Jan 31 17:36 2000_May_0038.tif
-rw-------  1 ulises  staff  32987483 Jan 31 17:36 2000_May_0039_a.tif
-rw-------  1 ulises  staff  32987483 Jan 31 17:36 2000_May_0039.tif
-rw-------  1 ulises  staff  32664843 Jan 31 17:36 2000_May_0040_a.tif
-rw-------  1 ulises  staff  32664843 Jan 31 17:36 2000_May_0040.tif
```

---

## Synthesized Solution

# Synthesized Solution: TIFF to HEIC Converter with Epson FastFoto Workflow

After analyzing all responses, I'll provide a comprehensive, production-ready solution that combines the best elements from each approach.

## Executive Summary

All responses correctly identified the core requirements and proposed similar architectural patterns. I'll synthesize the most robust approach covering:

1. **Compression Strategy**: Stick with LZW for now, but make compression configurable
2. **Variant Handling**: Use lightweight heuristics (not ML initially) to choose between `_a` and base files
3. **Folder Organization**: Automated subfolder creation and archival
4. **Safety**: Preserve originals, verify conversions, support dry-run

## Key Design Decisions

### 1. Compression Choice

**Recommendation**: LZW is fine, but add DEFLATE as an option.

```python
# Both are lossless; DEFLATE often 10-15% better for photos
COMPRESSION_OPTIONS = {
    'lzw': 'tiff_lzw',
    'deflate': 'tiff_adobe_deflate'
}
```

### 2. Variant Selection Strategy

**Approach**: Lightweight heuristic (no heavy ML dependencies initially).

The consensus across all responses was to use:

- **Sharpness** (edge variance/Laplacian)
- **Exposure** (distance from mid-gray)
- **Colorfulness** (saturation metrics)
- **Optional SSIM** if scikit-image available

## Complete Implementation

### File: `src/photo_organizer/converter/variant_selection.py` (NEW)

```python
"""
Variant selection logic for Epson FastFoto scans.
Handles _a (augmented) and _b (backside) file variants.
"""
import math
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from PIL import Image, ImageFilter, ImageStat
import numpy as np

logger = logging.getLogger(__name__)

try:
    from skimage.metrics import structural_similarity as ssim
    SSIM_AVAILABLE = True
except ImportError:
    SSIM_AVAILABLE = False


def canonical_stem(path: Path) -> str:
    """
    Return canonical stem removing _a/_b suffixes.
    Example: '2000_May_0001_a' -> '2000_May_0001'
    """
    stem = path.stem
    if stem.endswith('_a') or stem.endswith('_b'):
        return stem[:-2]
    return stem


def group_variants(files: List[Path]) -> Dict[str, List[Path]]:
    """
    Group files by canonical stem.
    Returns: {'2000_May_0001': [path1, path1_a, path1_b], ...}
    """
    groups = {}
    for path in files:
        base_stem = canonical_stem(path)
        groups.setdefault(base_stem, []).append(path)
    return groups


def compute_quality_metrics(image_path: Path) -> Dict[str, float]:
    """
    Compute lightweight quality metrics for an image.

    Metrics:
    - sharpness: Edge variance (higher = sharper)
    - brightness_mean: Average brightness (0-255)
    - contrast_std: Standard deviation (higher = more contrast)
    - colorfulness: Color saturation metric
    - exposure_score: Distance from ideal mid-gray (higher = better)
    """
    try:
        with Image.open(image_path) as img:
            # Convert to RGB for consistent analysis
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            # Resize for faster processing (maintain aspect ratio)
            img.thumbnail((1024, 1024))

            # Convert to numpy array
            arr = np.array(img, dtype=np.float32)

            # Grayscale for sharpness/exposure
            if arr.ndim == 3:
                gray = np.dot(arr[..., :3], [0.2989, 0.5870, 0.1140])
            else:
                gray = arr

            # Sharpness (Laplacian variance)
            gx = np.diff(gray, axis=1)
            gy = np.diff(gray, axis=0)
            sharpness = float(np.var(gx) + np.var(gy))

            # Brightness and contrast
            brightness_mean = float(gray.mean())
            contrast_std = float(gray.std())

            # Exposure score (prefer mid-range, penalize clipping)
            exposure_score = 1.0 - abs(brightness_mean - 128.0) / 128.0
            exposure_score = max(0.0, min(1.0, exposure_score))

            # Colorfulness (only for RGB)
            colorfulness = 0.0
            if arr.ndim == 3 and arr.shape[2] >= 3:
                r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
                rg_std = float(np.std(r - g))
                yb_std = float(np.std(0.5 * (r + g) - b))
                colorfulness = math.sqrt(rg_std**2 + yb_std**2)

            return {
                'sharpness': sharpness,
                'brightness_mean': brightness_mean,
                'contrast_std': contrast_std,
                'colorfulness': colorfulness,
                'exposure_score': exposure_score
            }
    except Exception as e:
        logger.warning(f"Failed to compute metrics for {image_path}: {e}")
        return {
            'sharpness': 0.0,
            'brightness_mean': 0.0,
            'contrast_std': 0.0,
            'colorfulness': 0.0,
            'exposure_score': 0.0
        }


def compute_quality_score(metrics: Dict[str, float]) -> float:
    """
    Combine metrics into a single quality score.

    Weights (tunable):
    - Sharpness: 0.40 (most important for scans)
    - Exposure: 0.25 (avoid over/underexposure)
    - Colorfulness: 0.20 (prefer saturated but not oversaturated)
    - Contrast: 0.15 (good dynamic range)
    """
    # Normalize sharpness (log scale to handle wide range)
    sharp_norm = math.log1p(metrics['sharpness']) / 10.0

    # Normalize colorfulness
    color_norm = min(1.0, metrics['colorfulness'] / 50.0)

    # Normalize contrast
    contrast_norm = min(1.0, metrics['contrast_std'] / 60.0)

    score = (
        0.40 * sharp_norm +
        0.25 * metrics['exposure_score'] +
        0.20 * color_norm +
        0.15 * contrast_norm
    )

    return float(score)


def compute_ssim(path1: Path, path2: Path) -> Optional[float]:
    """Compute structural similarity if scikit-image available."""
    if not SSIM_AVAILABLE:
        return None

    try:
        with Image.open(path1) as img1, Image.open(path2) as img2:
            # Convert to grayscale and resize to common dimensions
            arr1 = np.array(img1.convert('L').resize((512, 512)))
            arr2 = np.array(img2.convert('L').resize((512, 512)))

            similarity = ssim(arr1, arr2, data_range=255)
            return float(similarity)
    except Exception as e:
        logger.warning(f"SSIM computation failed: {e}")
        return None


def choose_best_variant(
    variants: List[Path],
    policy: str = 'auto',
    ssim_threshold: float = 0.98
) -> Tuple[Path, Dict]:
    """
    Choose the best variant from a group.

    Args:
        variants: List of file paths (base, _a, _b variants)
        policy: 'auto' | 'prefer_base' | 'prefer_a'
        ssim_threshold: If SSIM > threshold, consider duplicates

    Returns:
        (chosen_path, selection_info)
    """
    if not variants:
        raise ValueError("No variants provided")

    # Separate backside files
    backside = [p for p in variants if p.stem.endswith('_b')]
    front_candidates = [p for p in variants if not p.stem.endswith('_b')]

    if not front_candidates:
        # Only backside files (unusual)
        logger.warning(f"Only backside files found for {variants[0].stem}")
        return variants[0], {'reason': 'only_backside_available'}

    # Single candidate - easy choice
    if len(front_candidates) == 1:
        return front_candidates[0], {
            'reason': 'single_candidate',
            'backside_count': len(backside)
        }

    # Apply policy
    base_file = next((p for p in front_candidates if not p.stem.endswith('_a')), None)
    a_file = next((p for p in front_candidates if p.stem.endswith('_a')), None)

    if policy == 'prefer_base' and base_file:
        return base_file, {'reason': 'policy_prefer_base'}

    if policy == 'prefer_a' and a_file:
        return a_file, {'reason': 'policy_prefer_a'}

    # Auto mode: compute metrics
    results = []
    for path in front_candidates:
        metrics = compute_quality_metrics(path)
        score = compute_quality_score(metrics)
        results.append({
            'path': path,
            'metrics': metrics,
            'score': score
        })

    # Sort by score
    results.sort(key=lambda x: x['score'], reverse=True)

    # Check if files are essentially duplicates via SSIM
    ssim_value = None
    if base_file and a_file and len(front_candidates) == 2:
        ssim_value = compute_ssim(base_file, a_file)
        if ssim_value and ssim_value >= ssim_threshold:
            # Files are duplicates - prefer base for consistency
            chosen = base_file
            return chosen, {
                'reason': 'ssim_duplicate',
                'ssim': ssim_value,
                'scores': {r['path'].name: r['score'] for r in results}
            }

    # Choose highest scoring
    chosen = results[0]['path']
    score_diff = results[0]['score'] - results[1]['score'] if len(results) > 1 else 0

    info = {
        'reason': 'quality_metrics',
        'scores': {r['path'].name: r['score'] for r in results},
        'score_difference': score_diff,
        'ambiguous': score_diff < 0.05,  # Flag close calls for review
        'ssim': ssim_value,
        'backside_count': len(backside)
    }

    if info['ambiguous']:
        logger.info(f"Ambiguous choice for {canonical_stem(chosen)}: score diff = {score_diff:.3f}")

    return chosen, info
```

### File: `src/photo_organizer/converter/core.py` (UPDATED)

Add this function to handle the Epson workflow:

```python
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
    from .variant_selection import group_variants, choose_best_variant

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
                res_lzw.warnings.append("AMBIGUOUS: Manual review recommended")
            results.append(res_lzw)

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
            results.append(res_heic)

        # Move originals to archive (only if conversions succeeded and not dry_run)
        if not options.get('dry_run', False) and all(r.success for r in results[-2:] if r):
            for variant in variants:
                try:
                    if variant.stem.endswith('_b'):
                        dest = backside_dir / variant.name
                    else:
                        dest = uncompressed_dir / variant.name

                    # Handle duplicates
                    if dest.exists():
                        counter = 1
                        base, ext = dest.stem, dest.suffix
                        while True:
                            new_dest = dest.parent / f"{base}_dup{counter}{ext}"
                            if not new_dest.exists():
                                dest = new_dest
                                break
                            counter += 1

                    variant.rename(dest)
                    logger.debug(f"Moved {variant.name} -> {dest.relative_to(folder_path)}")
                except Exception as e:
                    logger.error(f"Failed to move {variant.name}: {e}")

        if progress_callback:
            progress_callback(idx, total)

    return results


def create_lzw_copy(
    source_path: Path,
    output_path: Path,
    verify: bool = True,
    dry_run: bool = False,
    compression: str = 'lzw'
) -> ConversionResult:
    """Enhanced with configurable compression."""
    start_time = time.time()
    res = ConversionResult(
        str(source_path),
        str(output_path),
        f"TIFF-{compression.upper()}",
        False,
        source_path.stat().st_size
    )

    if dry_run:
        res.success = True
        res.warnings.append("DRY RUN - no files written")
        return res

    try:
        compression_map = {
            'lzw': 'tiff_lzw',
            'deflate': 'tiff_adobe_deflate'
        }

        with Image.open(source_path) as img:
            save_kwargs = {
                'compression': compression_map.get(compression, 'tiff_lzw'),
                'exif': img.info.get('exif'),
                'icc_profile': img.info.get('icc_profile')
            }
            save_kwargs = {k: v for k, v in save_kwargs.items() if v is not None}

            img.save(output_path, **save_kwargs)

        res.output_size_bytes = output_path.stat().st_size

        # Verification
        if verify:
            try:
                with Image.open(output_path) as verify_img:
                    verify_img.verify()
                    # Re-open for deeper check
                with Image.open(output_path) as verify_img:
                    _ = verify_img.load()
            except Exception as e:
                raise ValueError(f"Verification failed: {e}")

        res.success = True

        # Calculate compression ratio
        ratio = (1 - res.output_size_bytes / res.source_size_bytes) * 100
        res.warnings.append(f"Compression: {ratio:.1f}% reduction")

    except Exception as e:
        res.error_message = str(e)
        logger.error(f"LZW conversion failed for {source_path.name}: {e}")

    res.duration_seconds = time.time() - start_time
    return res
```

### File: `src/photo_organizer/converter/gui.py` (UPDATED)

Add Epson workflow toggle:

```python
def _create_widgets(self):
    # ... existing code ...

    # Workflow Mode
    workflow_frame = ttk.LabelFrame(container, text="Workflow Mode", padding=10)
    workflow_frame.pack(fill=X, pady=10)

    self.epson_mode = ttk.BooleanVar(value=True)
    ttk.Checkbutton(
        workflow_frame,
        text="Epson FastFoto Workflow",
        variable=self.epson_mode,
        bootstyle="info-toolbutton"
    ).pack(anchor=W)

    ttk.Label(
        workflow_frame,
        text="• Groups _a/_b variants\n"
             "• Creates LZW_compressed/ and HEIC/ folders\n"
             "• Moves originals to uncompressed/",
        font=("Helvetica", 9),
        foreground="gray"
    ).pack(anchor=W, padx=20, pady=5)

    # Variant selection policy
    policy_frame = ttk.Frame(workflow_frame)
    policy_frame.pack(fill=X, padx=20, pady=5)

    ttk.Label(policy_frame, text="Variant Selection:").pack(side=LEFT)
    self.variant_policy = ttk.StringVar(value="auto")
    ttk.Radiobutton(
        policy_frame, text="Auto (Quality)",
        variable=self.variant_policy, value="auto"
    ).pack(side=LEFT, padx=5)
    ttk.Radiobutton(
        policy_frame, text="Prefer Base",
        variable=self.variant_policy, value="prefer_base"
    ).pack(side=LEFT, padx=5)
    ttk.Radiobutton(
        policy_frame, text="Prefer _a",
        variable=self.variant_policy, value="prefer_a"
    ).pack(side=LEFT, padx=5)

    # Compression type
    comp_frame = ttk.Frame(options_frame)
    comp_frame.pack(fill=X, pady=5)

    ttk.Label(comp_frame, text="TIFF Compression:").pack(side=LEFT)
    self.compression_type = ttk.StringVar(value="lzw")
    ttk.Radiobutton(
        comp_frame, text="LZW",
        variable=self.compression_type, value="lzw"
    ).pack(side=LEFT, padx=5)
    ttk.Radiobutton(
        comp_frame, text="DEFLATE (smaller)",
        variable=self.compression_type, value="deflate"
    ).pack(side=LEFT, padx=5)


def _run_conversion(self):
    # ... existing validation ...

    try:
        options = {
            'create_lzw': self.create_lzw.get(),
            'create_heic': self.create_heic.get(),
            'heic_quality': self.quality_var.get(),
            'verify': True,
            'dry_run': False,
            'variant_policy': self.variant_policy.get(),
            'compression': self.compression_type.get()
        }

        if self.epson_mode.get():
            # Use Epson workflow
            results = process_epson_folder(
                self.source_dir,
                options,
                progress_callback=self.update_progress
            )
        else:
            # Standard batch process
            tiff_files = list(self.source_dir.glob("*.tif*"))
            results = batch_process(
                tiff_files,
                options,
                progress_callback=self.update_progress
            )

        # ... existing result handling ...
```

## Usage Example

```python
from pathlib import Path
from photo_organizer.converter.core import process_epson_folder

# Process your May 2000 folder
results = process_epson_folder(
    Path("/Users/ulises/Documents/Epson FastFoto FF-680W/2000_May"),
    options={
        'variant_policy': 'auto',  # Use quality metrics
        'compression': 'deflate',   # Better compression
        'create_lzw': True,
        'create_heic': True,
        'heic_quality': 90,
        'verify': True,
        'dry_run': False  # Set True for testing
    }
)
```

## Result Structure

After processing `2000_May/`:

```
2000_May/
├── HEIC/
│   ├── 2000_May_0001.heic
│   ├── 2000_May_0002.heic
│   └── ...
├── LZW_compressed/
│   ├── 2000_May_0001.LZW.tif
│   ├── 2000_May_0002.LZW.tif
│   └── ...
└── uncompressed/
    ├── backside/
    │   └── 2000_May_0001_b.tif (if any)
    ├── 2000_May_0001.tif
    ├── 2000_May_0001_a.tif
    └── ...
```

## Key Features

✅ **Safe**: Preserves all originals in `uncompressed/`  
✅ **Smart**: Chooses best variant using quality metrics  
✅ **Flexible**: Configurable policies and compression  
✅ **Transparent**: Logs all decisions and flags ambiguous cases  
✅ **Verifiable**: Built-in verification after conversion  
✅ **Tested**: Dry-run mode for safe testing

## Next Steps

1. **Test with dry-run** on a small batch first
2. **Review ambiguous cases** flagged in logs
3. **Consider ML** if you accumulate labeled preferences (500+ examples)
4. **Add checksums** to the JSON report for archival integrity
5. **Implement tar+compression** for long-term storage of `uncompressed/`

This solution combines the robustness of all proposals while remaining practical and immediately usable.
