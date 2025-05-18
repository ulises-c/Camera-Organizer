"""
camera_model_db.py
------------------
Simple utility for managing a camera models database (camera_models.txt).
- add_camera_model(model): Adds a model if not present.
- get_camera_models(): Returns a sorted list of all models.
"""
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'camera_models.txt')


def get_camera_models():
    if not os.path.exists(DB_PATH):
        open(DB_PATH, 'w').close()
    with open(DB_PATH, 'r') as f:
        return sorted(set(line.strip() for line in f if line.strip()))


def add_camera_model(model):
    model = model.strip()
    if not model or model == "UnknownCamera":
        return
    models = set(get_camera_models())
    if model not in models:
        models.add(model)
        with open(DB_PATH, 'w') as f:
            for m in sorted(models):
                f.write(m + '\n')
