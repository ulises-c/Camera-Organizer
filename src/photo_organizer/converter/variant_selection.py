"""
Variant selection logic for Epson FastFoto scans.
Handles _a (augmented) and _b (backside) file variants.
"""
import logging
import math
from pathlib import Path

import numpy as np
from PIL import Image

from photo_organizer.engine import OperationCancelled
from photo_organizer.engine import check_cancel as _shared_check_cancel

logger = logging.getLogger(__name__)

def check_cancel(cancel_event):
    _shared_check_cancel(cancel_event)

def compute_quality_metrics(image_path: Path, cancel_event=None) -> dict[str, float]:
    """
    Compute quality metrics. Checks for cancellation before heavy steps.
    """
    try:
        check_cancel(cancel_event)
        
        with Image.open(image_path) as img:
            check_cancel(cancel_event)
            
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            # Resize for faster processing, but check cancel first
            check_cancel(cancel_event)
            img.thumbnail((1024, 1024))
            
            check_cancel(cancel_event)
            arr = np.array(img, dtype=np.float32)

            # Analysis logic...
            if arr.ndim == 3:
                gray = np.dot(arr[..., :3], [0.2989, 0.5870, 0.1140])
            else:
                gray = arr

            check_cancel(cancel_event)
            
            # Sharpness (Laplacian variance)
            gx = np.diff(gray, axis=1)
            gy = np.diff(gray, axis=0)
            sharpness = float(np.var(gx) + np.var(gy))
            
            check_cancel(cancel_event)

            brightness_mean = float(gray.mean())
            contrast_std = float(gray.std())
            
            exposure_score = 1.0 - abs(brightness_mean - 128.0) / 128.0
            exposure_score = max(0.0, min(1.0, exposure_score))
            
            check_cancel(cancel_event)

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
    except OperationCancelled:
        raise
    except Exception as e:
        logger.warning(f"Failed to compute metrics for {image_path}: {e}")
        return {'sharpness': 0.0, 'score': 0.0}

def compute_quality_score(metrics: dict[str, float]) -> float:
    # Weighted score
    score = (
        metrics.get('sharpness', 0) * 1.0 +
        metrics.get('contrast_std', 0) * 2.0 +
        metrics.get('colorfulness', 0) * 1.5 +
        (metrics.get('exposure_score', 0) * 100.0)
    )
    return score

def group_variants(files: list[Path]) -> dict[str, list[Path]]:
    """Group FastFoto variants case-insensitively in stable base/_a/_b order."""
    def rank(path: Path) -> tuple[int, str, str]:
        stem = path.stem.casefold()
        variant_rank = 1 if stem.endswith('_a') else 2 if stem.endswith('_b') else 0
        return variant_rank, path.name.casefold(), path.name

    grouped: dict[str, list[Path]] = {}
    labels: dict[str, str] = {}
    for path in sorted(files, key=rank):
        stem = path.stem
        base = stem[:-2] if stem.casefold().endswith(('_a', '_b')) else stem
        key = base.casefold()
        grouped.setdefault(key, []).append(path)
        labels.setdefault(key, base)

    return {
        labels[key]: grouped[key]
        for key in sorted(grouped, key=lambda item: (labels[item].casefold(), labels[item]))
    }

def choose_best_variant(
    variants: list[Path], 
    policy: str = 'auto', 
    cancel_event = None
) -> tuple[Path, dict]:
    """
    Selects the best variant. Raises OperationCancelled if interrupted.
    """
    check_cancel(cancel_event)
    
    if not variants:
        raise ValueError("No variants provided")
    
    # Filter out backside
    fronts = [p for p in variants if not p.stem.lower().endswith('_b')]
    if not fronts:
         return variants[0], {'reason': 'no_fronts'}
         
    if len(fronts) == 1:
        return fronts[0], {'reason': 'single'}

    # Policy checks
    base_file = next((p for p in fronts if not p.stem.lower().endswith('_a')), None)
    a_file = next((p for p in fronts if p.stem.lower().endswith('_a')), None)

    if policy == 'prefer_base' and base_file:
        return base_file, {'reason': 'policy_base'}
    if policy == 'prefer_a' and a_file:
        return a_file, {'reason': 'policy_augment'}

    # Auto analysis
    results = []
    for path in fronts:
        check_cancel(cancel_event) # Check inside loop
        metrics = compute_quality_metrics(path, cancel_event)
        score = compute_quality_score(metrics)
        results.append({'path': path, 'score': score})
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[0]['path'], {'reason': 'quality_score', 'score': results[0]['score']}
