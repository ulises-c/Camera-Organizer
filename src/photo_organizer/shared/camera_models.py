"""
Camera models database with JSON storage and backwards compatibility.
Maps EXIF model names to friendly display names with alias support.
"""
import json
from pathlib import Path
import appdirs


# NOTE: APP_AUTHOR and APP_NAME are used by appdirs to create the user data directory.
# BUG: This only works for my machine, does not support a generic setup.
# TODO: Think of a different solution.
APP_NAME = "photo_organizer"
APP_AUTHOR = "UlisesChavarria"

DEFAULT_MODELS = [
    {
        "exif_name": "ILCE-6700",
        "display_name": "Sony a6700",
        "folder_name": "Sony a6700",
        "aliases": ["A6700", "ILCE-6700"]
    },
    {
        "exif_name": "ILCE-6400",
        "display_name": "Sony a6400",
        "folder_name": "Sony a6400",
        "aliases": ["A6400"]
    },
    {
        "exif_name": "ILCE-6300",
        "display_name": "Sony a6300",
        "folder_name": "Sony a6300",
        "aliases": ["A6300"]
    },
    {
        "exif_name": "DSC-RX100M7",
        "display_name": "Sony RX100 VII",
        "folder_name": "Sony RX100 VII",
        "aliases": ["RX100M7", "RX100 VII"]
    },
    {
        "exif_name": "HERO8 Black",
        "display_name": "GoPro Hero 8 Black",
        "folder_name": "GoPro Hero 8 Black",
        "aliases": ["HERO8"]
    }
]


def get_db_dir() -> Path:
    """Get user data directory for the application."""
    data_dir = Path(appdirs.user_data_dir(APP_NAME, APP_AUTHOR))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_db_path() -> Path:
    """Get path to JSON database file."""
    return get_db_dir() / "camera_models.json"


def get_legacy_txt_path() -> Path:
    """Get path to legacy text database file."""
    return get_db_dir() / "camera_models.txt"


def _migrate_from_txt_if_needed():
    """Migrate from legacy text/seed format to JSON if needed."""
    json_path = get_db_path()

    if json_path.exists():
        return

    txt_path = get_legacy_txt_path()
    seed_dir = Path(__file__).parent.parent / "data"
    seed_json = seed_dir / "camera_models_seed.json"
    # TODO: Remove txt seed support in future versions
    seed_txt = seed_dir / "camera_models_seed.txt"

    models = []

    # Priority order: user txt > package JSON > package txt > defaults
    if txt_path.exists():
        for line in txt_path.read_text(encoding='utf-8').splitlines():
            name = line.strip()
            if name:
                models.append({
                    "exif_name": name,
                    "display_name": name,
                    "folder_name": name,
                    "aliases": [name]
                })
    elif seed_json.exists():
        try:
            models = json.loads(seed_json.read_text(encoding='utf-8'))
            if not isinstance(models, list):
                models = []
        except Exception:
            models = []
    elif seed_txt.exists():
        for line in seed_txt.read_text(encoding='utf-8').splitlines():
            name = line.strip()
            if name:
                models.append({
                    "exif_name": name,
                    "display_name": name,
                    "folder_name": name,
                    "aliases": [name]
                })

    if not models:
        models = DEFAULT_MODELS

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(models, indent=2, ensure_ascii=False),
        encoding='utf-8'
    )


def load_models() -> list[dict]:
    """Load camera models from JSON database."""
    _migrate_from_txt_if_needed()
    db_path = get_db_path()

    try:
        return json.loads(db_path.read_text(encoding='utf-8'))
    except Exception as e:
        print(f"Error loading camera models: {e}")
        return DEFAULT_MODELS


def save_models(models: list[dict]):
    """Save camera models to JSON database."""
    db_path = get_db_path()
    db_path.write_text(json.dumps(
        models, indent=2, ensure_ascii=False), encoding='utf-8')


def get_camera_models() -> list[str]:
    """Get sorted list of display names for UI dropdowns."""
    models = load_models()
    return sorted({m.get("display_name", "") for m in models if m.get("display_name")})


def resolve_model_name(raw_model: str) -> str:
    """
    Resolve EXIF model name to folder-friendly name.
    Checks exif_name, then aliases for a match.
    """
    if not raw_model or raw_model == "UnknownCamera":
        return "UnknownCamera"

    models = load_models()
    clean_raw = raw_model.strip().replace('_', ' ')

    for model in models:
        if model.get("exif_name", "").strip() == raw_model:
            return model.get("folder_name", raw_model)

    clean_lower = clean_raw.lower()
    for model in models:
        aliases = model.get("aliases", [])
        for alias in aliases:
            if alias.strip().lower() == clean_lower:
                return model.get("folder_name", raw_model)

    return raw_model


def add_camera_model(exif_name: str, display_name: str = None, folder_name: str = None):
    """Add a new camera model to the database."""
    if not exif_name or exif_name == "UnknownCamera":
        return

    models = load_models()

    for model in models:
        if model.get("exif_name") == exif_name:
            return

    models.append({
        "exif_name": exif_name,
        "display_name": display_name or exif_name,
        "folder_name": folder_name or display_name or exif_name,
        "aliases": [exif_name]
    })

    save_models(models)
