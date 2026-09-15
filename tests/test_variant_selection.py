"""Tests for deterministic Epson FastFoto variant grouping."""
from __future__ import annotations

from pathlib import Path

from photo_organizer.converter.variant_selection import group_variants


def test_group_variants_is_case_insensitive_and_deterministic():
    files = [Path("photo_a.TIFF"), Path("PHOTO_b.tif"), Path("Photo.tif")]

    groups = group_variants(files)

    assert list(groups) == ["Photo"]
    assert [path.name for path in groups["Photo"]] == [
        "Photo.tif",
        "photo_a.TIFF",
        "PHOTO_b.tif",
    ]
