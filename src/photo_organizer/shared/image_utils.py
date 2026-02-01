"""Image-specific utilities for bit depth and analysis."""
from PIL import Image


def get_bit_depth(img: Image.Image) -> int:
    """
    Determine bit depth of a PIL Image.
    
    Checks mode first, then TIFF tags for high-bit-depth images.
    """
    mode = img.mode
    
    # Standard mode mappings
    bit_depths = {
        "1": 1, "L": 8, "P": 8, "RGB": 8, "RGBA": 8,
        "CMYK": 8, "YCbCr": 8, "LAB": 8, "HSV": 8,
        "I": 32, "F": 32,
        "I;16": 16, "I;16L": 16, "I;16B": 16, "I;16N": 16,
        "RGB;16": 16, "RGBA;16": 16,
    }
    
    # Check TIFF tag 258 (BitsPerSample) for override
    if hasattr(img, 'tag_v2'):
        bits = img.tag_v2.get(258)  # BitsPerSample tag
        if bits:
            if isinstance(bits, tuple):
                return max(bits)  # For multi-channel, use max
            return bits
    
    return bit_depths.get(mode, 8)


def format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"
