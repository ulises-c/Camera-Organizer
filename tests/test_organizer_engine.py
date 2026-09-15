"""Safety and behavior tests for the photo/video organizer engine."""
from __future__ import annotations

from pathlib import Path

from photo_organizer.organizer import engine as organizer_engine
from photo_organizer.organizer.engine import process_organize


def run_organizer(source: Path, **options):
    return process_organize(
        source,
        options,
        lambda _value: None,
        lambda _message: None,
    )


def fixed_metadata(monkeypatch, *, date="2024-05-17", model="Sony_a6700"):
    monkeypatch.setattr(organizer_engine, "get_creation_date", lambda _path: date)
    monkeypatch.setattr(organizer_engine, "get_camera_model", lambda _path: model)


def test_preview_reports_planned_without_moving_file(tmp_path, monkeypatch):
    source = tmp_path / "source"
    destination = tmp_path / "organized"
    source.mkdir()
    photo = source / "photo.JPG"
    photo.write_bytes(b"photo")
    fixed_metadata(monkeypatch)

    result = run_organizer(source, destination=destination, dry_run=True)

    assert photo.is_file()
    assert not destination.exists()
    assert result.planned == 1
    assert result.moved == 0
    assert result.ops[0].status == "planned"


def test_already_organized_file_is_skipped(tmp_path, monkeypatch):
    source = tmp_path / "source"
    photo = source / "Sony_a6700" / "photos" / "2024-05-17" / "photo.JPG"
    photo.parent.mkdir(parents=True)
    photo.write_bytes(b"photo")
    fixed_metadata(monkeypatch)

    result = run_organizer(source, dry_run=True)

    assert result.skipped == 1
    assert result.planned == 0
    assert result.ops[0].status == "skipped_already_organized"


def test_existing_destination_collision_is_skipped(tmp_path, monkeypatch):
    source = tmp_path / "source"
    destination = tmp_path / "organized"
    source.mkdir()
    photo = source / "photo.JPG"
    photo.write_bytes(b"new")
    existing = destination / "Sony_a6700" / "photos" / "2024-05-17" / "photo.JPG"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing")
    fixed_metadata(monkeypatch)

    result = run_organizer(source, destination=destination, dry_run=True)

    assert result.skipped == 1
    assert result.planned == 0
    assert result.ops[0].status == "skipped_collision"
    assert existing.read_bytes() == b"existing"


def test_planned_destination_collision_is_skipped(tmp_path, monkeypatch):
    source = tmp_path / "source"
    destination = tmp_path / "organized"
    for subfolder, content in (("a", b"first"), ("b", b"second")):
        folder = source / subfolder
        folder.mkdir(parents=True)
        (folder / "photo.JPG").write_bytes(content)
    fixed_metadata(monkeypatch)

    result = run_organizer(source, destination=destination, dry_run=True)

    assert result.planned == 1
    assert result.skipped == 1
    assert [op.status for op in result.ops] == ["planned", "skipped_collision"]


def test_metadata_cannot_escape_destination_root(tmp_path, monkeypatch):
    source = tmp_path / "source"
    destination = tmp_path / "organized"
    source.mkdir()
    (source / "photo.JPG").write_bytes(b"photo")
    fixed_metadata(monkeypatch, date="../../escape", model="..")

    result = run_organizer(source, destination=destination, dry_run=True)

    dest_path = Path(result.ops[0].dest).resolve()
    assert destination.resolve() in dest_path.parents
    assert ".." not in Path(result.ops[0].dest).parts


def test_live_move_relocates_file_and_skips_no_overwrite(tmp_path, monkeypatch):
    source = tmp_path / "source"
    destination = tmp_path / "organized"
    source.mkdir()
    photo = source / "photo.JPG"
    photo.write_bytes(b"photo")
    fixed_metadata(monkeypatch)

    result = run_organizer(source, destination=destination, dry_run=False)

    assert result.moved == 1
    assert not photo.exists()
    moved_to = destination / "Sony_a6700" / "photos" / "2024-05-17" / "photo.JPG"
    assert moved_to.read_bytes() == b"photo"
    assert result.ops[0].status == "moved"


def test_preview_never_touches_camera_database(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "photo.JPG").write_bytes(b"photo")
    fixed_metadata(monkeypatch, model="ILCE-9999")

    def explode(*args, **kwargs):
        raise AssertionError("database accessed during preview")

    monkeypatch.setattr(organizer_engine, "get_camera_models", explode)
    monkeypatch.setattr(organizer_engine, "add_camera_model", explode)

    result = run_organizer(source, dry_run=True)

    assert result.planned == 1


def test_models_persist_only_for_successful_moves(tmp_path, monkeypatch):
    source = tmp_path / "source"
    destination = tmp_path / "organized"
    source.mkdir()
    (source / "photo.JPG").write_bytes(b"photo")
    fixed_metadata(monkeypatch, model="ILCE-9999")
    monkeypatch.setattr(organizer_engine, "get_camera_models", list)
    added: list[str] = []
    monkeypatch.setattr(organizer_engine, "add_camera_model", added.append)

    run_organizer(source, destination=destination, dry_run=False)

    assert added == ["ILCE-9999"]


def test_database_failure_is_nonfatal_after_moves(tmp_path, monkeypatch):
    source = tmp_path / "source"
    destination = tmp_path / "organized"
    source.mkdir()
    photo = source / "photo.JPG"
    photo.write_bytes(b"photo")
    fixed_metadata(monkeypatch, model="ILCE-9999")
    monkeypatch.setattr(organizer_engine, "get_camera_models", list)

    def boom(_model):
        raise OSError("disk full")

    monkeypatch.setattr(organizer_engine, "add_camera_model", boom)

    result = run_organizer(source, destination=destination, dry_run=False)

    assert result.moved == 1
    assert not photo.exists()
    assert "disk full" in result.database_error


def test_cancellation_reports_partial_and_cancelled_state(tmp_path, monkeypatch):
    source = tmp_path / "source"
    destination = tmp_path / "organized"
    source.mkdir()
    (source / "a.JPG").write_bytes(b"a")
    (source / "b.JPG").write_bytes(b"b")
    fixed_metadata(monkeypatch)
    from photo_organizer.engine import make_cancel_token
    token = make_cancel_token()
    token.set()

    result = process_organize(
        source,
        {"dry_run": False, "destination": destination, "cancel_event": token},
        lambda _value: None,
        lambda _message: None,
    )

    assert result.cancelled is True
    assert result.moved == 0


def test_recursive_false_ignores_nested_files(tmp_path, monkeypatch):
    source = tmp_path / "source"
    destination = tmp_path / "organized"
    source.mkdir()
    (source / "top.JPG").write_bytes(b"top")
    nested = source / "nested"
    nested.mkdir()
    (nested / "deep.JPG").write_bytes(b"deep")
    fixed_metadata(monkeypatch)

    result = run_organizer(source, destination=destination, recursive=False, dry_run=True)

    assert result.planned == 1
    assert Path(result.ops[0].source).name == "top.JPG"
