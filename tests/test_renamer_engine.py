"""Integration tests for renamer engine behavior exposed by the GUI."""
from __future__ import annotations

from pathlib import Path

from photo_organizer.renamer.engine import process_batch_rename, process_folder_rename


def test_batch_rename_handles_matching_files_inside_matching_folders(tmp_path):
    source_dir = tmp_path / "Album_UnknownCamera"
    source_dir.mkdir()
    source_file = source_dir / "image_UnknownCamera.jpg"
    source_file.write_bytes(b"photo")

    result = process_batch_rename(
        tmp_path,
        {"dry_run": False, "model": "Sony a6700"},
        lambda progress: None,
        lambda message: None,
    )

    expected_dir = tmp_path / "Album_Sony a6700"
    assert result.failed == 0
    assert result.success == 2
    assert expected_dir.is_dir()
    assert (expected_dir / "image_Sony a6700.jpg").read_bytes() == b"photo"


def test_folder_rename_handles_nested_matching_folders(tmp_path, monkeypatch):
    parent = tmp_path / "10000101"
    child = parent / "10100102"
    child.mkdir(parents=True)
    (child / "photo.jpg").write_bytes(b"photo")

    dates = {
        "10000101": "2000-01-01",
        "10100102": "2000-01-02",
    }

    def fake_metadata(folder_path):
        return dates.get(Path(folder_path).name), None, "photo.jpg"

    monkeypatch.setattr(
        "photo_organizer.renamer.engine.extract_folder_metadata",
        fake_metadata,
    )

    result = process_folder_rename(
        tmp_path,
        {
            "dry_run": False,
            "recursive": True,
            "include_model": False,
            "merge": False,
        },
        lambda progress: None,
        lambda message: None,
    )

    expected_child = tmp_path / "2000-01-01" / "2000-01-02"
    assert result.failed == 0
    assert result.success == 2
    assert expected_child.is_dir()
    assert (expected_child / "photo.jpg").read_bytes() == b"photo"
