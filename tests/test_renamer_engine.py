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
    assert all(Path(op.new).exists() for op in result.ops)


def test_folder_merge_reports_partial_failure(tmp_path, monkeypatch):
    source = tmp_path / "10000101"
    source.mkdir()
    (source / "blocked.jpg").write_bytes(b"photo")
    destination = tmp_path / "2000-01-01"
    destination.mkdir()

    monkeypatch.setattr(
        "photo_organizer.renamer.engine.extract_folder_metadata",
        lambda folder_path: ("2000-01-01", None, "blocked.jpg"),
    )
    monkeypatch.setattr(
        "photo_organizer.renamer.engine.shutil.move",
        lambda source_path, destination_path: (_ for _ in ()).throw(
            PermissionError("blocked")
        ),
    )

    result = process_folder_rename(
        tmp_path,
        {
            "dry_run": False,
            "recursive": True,
            "include_model": False,
            "merge": True,
        },
        lambda progress: None,
        lambda message: None,
    )

    assert result.success == 0
    assert result.failed == 1
    assert not result.ops[0].success
    assert "incomplete" in result.ops[0].error.lower()
    assert source.is_dir()


def test_folder_rename_merges_same_destination_created_by_plan(tmp_path, monkeypatch):
    first = tmp_path / "10000101"
    second = tmp_path / "10100101"
    first.mkdir()
    second.mkdir()
    (first / "first.jpg").write_bytes(b"first")
    (second / "second.jpg").write_bytes(b"second")

    monkeypatch.setattr(
        "photo_organizer.renamer.engine.extract_folder_metadata",
        lambda folder_path: ("2000-01-01", None, "photo.jpg"),
    )

    result = process_folder_rename(
        tmp_path,
        {
            "dry_run": False,
            "recursive": True,
            "include_model": False,
            "merge": True,
        },
        lambda progress: None,
        lambda message: None,
    )

    destination = tmp_path / "2000-01-01"
    assert result.success == 2
    assert result.failed == 0
    assert [op.action for op in result.ops] == ["rename", "merge"]
    assert (destination / "first.jpg").read_bytes() == b"first"
    assert (destination / "second.jpg").read_bytes() == b"second"


def test_folder_rename_skips_merge_destination_that_is_not_directory(tmp_path, monkeypatch):
    source = tmp_path / "10000101"
    source.mkdir()
    (source / "photo.jpg").write_bytes(b"photo")
    destination = tmp_path / "2000-01-01"
    destination.write_bytes(b"not a directory")

    monkeypatch.setattr(
        "photo_organizer.renamer.engine.extract_folder_metadata",
        lambda folder_path: ("2000-01-01", None, "photo.jpg"),
    )

    result = process_folder_rename(
        tmp_path,
        {
            "dry_run": False,
            "recursive": True,
            "include_model": False,
            "merge": True,
        },
        lambda progress: None,
        lambda message: None,
    )

    assert result.ops == []
    assert result.skipped["destination_not_directory"] == 1
    assert source.is_dir()
    assert destination.read_bytes() == b"not a directory"
