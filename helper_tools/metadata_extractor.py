import json
import subprocess
from pathlib import Path
from PIL import Image, ExifTags, TiffImagePlugin
from PIL.TiffImagePlugin import IFDRational

# ==========================================================
# UTILITIES
# ==========================================================


def safe_call(fn, default=None):
    try:
        return fn()
    except Exception as e:
        return {"_error": str(e)}


def decode_tiff_tag(tag_id):
    # NOTE: I have been told TAGS_V2 was removed/refactored, may need to adjust this implementation for reliability
    return TiffImagePlugin.TAGS_V2.get(tag_id, f"Unknown({tag_id})")


def decode_exif_tag(tag_id):
    return ExifTags.TAGS.get(tag_id, f"Unknown({tag_id})")


def json_safe(value):
    """
    Recursively convert Pillow / TIFF-specific types
    into JSON-serializable primitives.
    """
    if isinstance(value, IFDRational):
        return float(value)

    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"

    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]

    return value


# ==========================================================
# PILLOW METADATA EXTRACTION
# ==========================================================

def extract_metadata_pillow(img: Image.Image):
    meta = {}

    # -------------------------------
    # Core image info
    # -------------------------------
    meta["core"] = {
        "format": img.format,
        "mode": img.mode,
        "size": img.size,
        "info_keys": sorted(img.info.keys()),
    }

    # -------------------------------
    # Resolution
    # -------------------------------
    def get_resolution():
        dpi = img.info.get("dpi")
        if dpi:
            return {"x": dpi[0], "y": dpi[1], "unit": "dpi"}

        if hasattr(img, "tag_v2"):
            x = img.tag_v2.get(282)  # XResolution
            y = img.tag_v2.get(283)  # YResolution
            if x and y:
                return {"x": float(x), "y": float(y), "unit": "dpi (TIFF)"}
        return None

    meta["resolution"] = safe_call(get_resolution)

    # -------------------------------
    # ICC profile
    # -------------------------------
    icc = img.info.get("icc_profile")
    meta["icc_profile"] = {
        "present": icc is not None,
        "bytes": len(icc) if icc else 0,
    }

    # -------------------------------
    # EXIF (camera-style)
    # -------------------------------
    def get_exif():
        exif = img.getexif()
        if not exif:
            return None
        return {
            decode_exif_tag(tag_id): value
            for tag_id, value in exif.items()
        }

    meta["exif"] = safe_call(get_exif)

    # -------------------------------
    # TIFF tags (scanner-style)
    # -------------------------------
    def get_tiff_tags():
        if not hasattr(img, "tag_v2"):
            return None

        tags = {}
        for tag_id, value in img.tag_v2.items():
            name = decode_tiff_tag(tag_id)
            tags[name] = value
        return tags

    meta["tiff"] = safe_call(get_tiff_tags)

    return meta


# ==========================================================
# EXIFTOOL METADATA EXTRACTION
# ==========================================================

def extract_metadata_exiftool(image_path: Path):
    try:
        result = subprocess.run(
            ["exiftool", "-json", "-G", "-n", str(image_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        return data[0] if data else {}
    except FileNotFoundError:
        return {"_error": "exiftool not found on PATH"}
    except subprocess.CalledProcessError as e:
        return {
            "_error": "exiftool failed",
            "stderr": e.stderr,
        }


# ==========================================================
# MAIN (HARDCODED IMAGE LIST)
# ==========================================================

def main():
    image_paths = [
        Path("examples/1996_0001.tif"),
        Path("examples/img20260131_15340430.tif"),
        # Path("examples/another_image.jpg"),
    ]

    for image_path in image_paths:
        print(f"\n🔍 Analyzing: {image_path}")

        if not image_path.exists():
            print(f"⚠️  Skipping missing file: {image_path}")
            continue

        output_dir = image_path.parent
        stem = image_path.stem

        # ---------------------------
        # Pillow extraction
        # ---------------------------
        try:
            with Image.open(image_path) as img:
                pillow_meta = extract_metadata_pillow(img)
        except Exception as e:
            pillow_meta = {"_error": f"Pillow failed: {e}"}

        pillow_out = output_dir / f"{stem}.pillow.metadata.json"
        pillow_out.write_text(
            json.dumps(json_safe(pillow_meta), indent=2, sort_keys=False),
            encoding="utf-8",
        )

        # ---------------------------
        # ExifTool extraction
        # ---------------------------
        exiftool_meta = extract_metadata_exiftool(image_path)
        exiftool_out = output_dir / f"{stem}.exiftool.metadata.json"
        exiftool_out.write_text(
            json.dumps(exiftool_meta, indent=2, sort_keys=False),
            encoding="utf-8",
        )

        print(f"  ✔ Pillow:   {pillow_out.name}")
        print(f"  ✔ ExifTool: {exiftool_out.name}")

    print("\n✅ Batch metadata analysis complete.")


if __name__ == "__main__":
    main()
