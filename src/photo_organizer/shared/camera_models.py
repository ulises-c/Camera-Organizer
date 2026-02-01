"""
Camera models database with user-writable storage via appdirs.
Ensures camera models can be added and persisted across sessions.
"""
from pathlib import Path
import appdirs

APP_NAME = "photo_organizer"
APP_AUTHOR = "UlisesChavarria"


def get_db_path() -> Path:
    """Get user-writable camera models DB path."""
    data_dir = Path(appdirs.user_data_dir(APP_NAME, APP_AUTHOR))
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "camera_models.txt"
    
    # Initialize from seed on first run
    if not db_path.exists():
        seed = Path(__file__).parent.parent / "data" / "camera_models_seed.txt"
        if seed.exists():
            db_path.write_text(seed.read_text())
        else:
            db_path.write_text("")
    
    return db_path


def get_camera_models() -> list[str]:
    """Returns a sorted list of all camera models."""
    db = get_db_path()
    return sorted({line.strip() for line in db.read_text().splitlines() if line.strip()})


def add_camera_model(model: str):
    """Adds a camera model if not already present."""
    model = model.strip()
    if not model or model == "UnknownCamera":
        return
    models = set(get_camera_models())
    if model not in models:
        models.add(model)
        get_db_path().write_text("\n".join(sorted(models)) + "\n")
