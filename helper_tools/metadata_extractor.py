from PIL import Image, ExifTags, TiffImagePlugin
from pathlib import Path
import pprint

# ==========================================================
# CONFIG
# ==========================================================

IMAGE_PATH = Path("examples/1996_0001.tif")  # <-- EDIT THIS

# ==========================================================
# UTILITIES
# ==========================================================

def safe_call(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def decode_tiff_tag(tag_id):
    return TiffImagePlugin.TAGS_V2.get(tag_id, f"Unknown({tag_id})")


def decode_exif_tag(tag_id):
    return ExifTags.TAGS.get(tag_id, f"Unknown({tag_id})")


# ==========================================================
# METADATA EXTRACTION
# ==========================================================

def extract_metadata(img: Image.Image):
    meta = {}

    # ------------------------------------------------------
    # Core image info (always safe)
    # ------------------------------------------------------

    meta["core"] = {
        "format": img.format,
        "mode": img.mode,
        "size": img.size,
        "info_keys": sorted(img.info.keys()),
    }

    # ------------------------------------------------------
    # Resolution (normalized)
    # ------------------------------------------------------

    def get_resolution():
        dpi = img.info.get("dpi")
        if dpi:
            return {"x": dpi[0], "y": dpi[1], "unit": "dpi"}

        xres = img.tag_v2.get(282) if hasattr(img, "tag_v2") else None
        yres = img.tag_v2.get(283) if hasattr(img, "tag_v2") else None

        if xres and yres:
            return {
                "x": float(xres),
                "y": float(yres),
                "unit": "dpi (TIFF)",
            }

        return None

    meta["resolution"] = safe_call(get_resolution)

    # ------------------------------------------------------
    # ICC profile
    # ------------------------------------------------------

    icc = img.info.get("icc_profile")
    meta["icc_profile"] = {
        "present": icc is not None,
        "bytes": len(icc) if icc else 0,
    }

    # ------------------------------------------------------
    # EXIF metadata (camera-style)
    # ------------------------------------------------------

    def get_exif():
        exif = img.getexif()
        if not exif:
            return None

        decoded = {}
        for tag_id, value in exif.items():
            decoded[decode_exif_tag(tag_id)] = value
        return decoded

    meta["exif"] = safe_call(get_exif)

    # ------------------------------------------------------
    # TIFF tags (scanner-style)
    # ------------------------------------------------------

    def get_tiff_tags():
        if not hasattr(img, "tag_v2"):
            return None

        tags = {}
        for tag_id, value in img.tag_v2.items():
            name = decode_tiff_tag(tag_id)

            # Make values printable
            if isinstance(value, (list, tuple)):
                value = list(value)
            elif isinstance(value, bytes):
                value = f"<{len(value)} bytes>"

            tags[name] = value

        return tags

    meta["tiff"] = safe_call(get_tiff_tags)

    # ------------------------------------------------------
    # Scanner-identifying fields (best effort)
    # ------------------------------------------------------

    def get_scanner_info():
        tiff = meta.get("tiff") or {}
        return {
            "Make": tiff.get("Make"),
            "Model": tiff.get("Model"),
            "Software": tiff.get("Software"),
            "DateTime": tiff.get("DateTime"),
        }

    meta["scanner"] = safe_call(get_scanner_info)

    return meta


# ==========================================================
# MAIN
# ==========================================================

def main():
    if not IMAGE_PATH.exists():
        raise FileNotFoundError(f"Image not found: {IMAGE_PATH}")

    with Image.open(IMAGE_PATH) as img:
        metadata = extract_metadata(img)

    print("\n=== Extracted Metadata ===\n")
    pprint.pprint(metadata, sort_dicts=False)


if __name__ == "__main__":
    main()
