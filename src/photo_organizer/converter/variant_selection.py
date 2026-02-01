"""
Variant selection logic for Epson FastFoto scans.
Handles _a (augmented) and _b (backside) file variants.
"""
import math
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)

try:
    from skimage.metrics import structural_similarity as ssim
    SSIM_AVAILABLE = True
except ImportError:
    SSIM_AVAILABLE = False


def canonical_stem(path: Path) -> str:
    """
    Return canonical stem removing _a/_b suffixes (case-insensitive).
    Example: '2000_May_0001_a' -> '2000_May_0001'
    """
    stem = path.stem
    if stem.lower().endswith('_a') or stem.lower().endswith('_b'):
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
    Choose the best FRONT variant only.
    
    NOTE: Backside (_b) files must be filtered out before calling this.
    This function only compares base vs _a variants.
    
    Args:
        variants: List of file paths (should NOT include _b files)
        policy: 'auto' | 'prefer_base' | 'prefer_a'
        ssim_threshold: If SSIM > threshold, consider duplicates
    
    Returns:
        (chosen_path, selection_info)
    """
    if not variants:
        raise ValueError("No variants provided for selection")
    
    # Safety check: filter out backsides (case-insensitive)
    front_candidates = [p for p in variants if not p.stem.lower().endswith('_b')]
    
    if not front_candidates:
        raise ValueError("No front-side candidates provided - only backsides found")
    
    if len(front_candidates) == 1:
        return front_candidates[0], {'reason': 'single_candidate'}
    
    # Identify base and _a files (case-insensitive)
    base_file = next((p for p in front_candidates if not p.stem.lower().endswith('_a')), None)
    a_file = next((p for p in front_candidates if p.stem.lower().endswith('_a')), None)
    
    # Policy-based selection
    if policy == 'prefer_base' and base_file:
        return base_file, {'reason': 'policy_prefer_base'}
    if policy == 'prefer_a' and a_file:
        return a_file, {'reason': 'policy_prefer_a'}
    
    # Auto mode: quality metrics analysis
    results = []
    for path in front_candidates:
        metrics = compute_quality_metrics(path)
        score = compute_quality_score(metrics)
        results.append({'path': path, 'score': score, 'metrics': metrics})
    
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # SSIM duplicate detection (avoid storing near-identical files)
    if SSIM_AVAILABLE and base_file and a_file:
        similarity = compute_ssim(base_file, a_file)
        if similarity and similarity >= ssim_threshold:
            return base_file, {
                'reason': 'ssim_duplicate',
                'ssim': similarity,
                'note': 'Base and _a are virtually identical'
            }
    
    # Return highest quality
    score_diff = results[0]['score'] - results[1]['score'] if len(results) > 1 else 0
    return results[0]['path'], {
        'reason': 'quality_metrics',
        'ambiguous': score_diff < 0.05,
        'score_diff': score_diff
    }
