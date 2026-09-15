"""Integration tests for renamer engine behavior exposed by the GUI."""
from __future__ import annotations

from photo_organizer.renamer.engine import process_batch_rename


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
