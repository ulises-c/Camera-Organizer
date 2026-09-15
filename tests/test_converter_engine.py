"""Safety and fidelity tests for the TIFF/Epson converter engine."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from photo_organizer.converter.engine import process_epson_folder
from photo_organizer.engine import make_cancel_token


def make_tiff(path: Path, *, color=(20, 40, 60), frames=1) -> None:
    images = [Image.new("RGB", (8, 6), (color[0] + i, color[1], color[2]))
              for i in range(frames)]
    images[0].save(path, format="TIFF", save_all=True, append_images=images[1:])


def run_converter(source: Path, **options):
    return process_epson_folder(
        source,
        options,
        lambda _value: None,
        lambda _message: None,
    )


def test_preview_plans_exact_tiff_suffix_without_mutation(tmp_path):
    source = tmp_path / "scans"
    source.mkdir()
    scan = source / "photo.tif"
    backup = source / "ignored.tif.backup"
    make_tiff(scan)
    backup.write_bytes(b"not a tiff")
    before = sorted(p.relative_to(source) for p in source.rglob("*"))

    result = run_converter(
        source,
        dry_run=True,
        create_heic=False,
        create_jpg=False,
        variant_policy="none",
    )

    after = sorted(p.relative_to(source) for p in source.rglob("*"))
    assert before == after
    assert result.cancelled is False
    assert len(result.groups) == 1
    detail = result.groups[0].details[0]
    assert detail.status == "planned"
    assert detail.output == "lossless_compressed/photo.ZIP.TIF"


@pytest.mark.parametrize(
    ("option", "value"),
    [
        ("compression", "brotli"),
        ("variant_policy", "surprise"),
        ("heic_quality", 101),
        ("jpg_quality", -1),
    ],
)
def test_invalid_options_fail_before_mutation(tmp_path, option, value):
    source = tmp_path / "scans"
    source.mkdir()
    make_tiff(source / "photo.tif")

    with pytest.raises(ValueError):
        run_converter(source, **{option: value})

    assert sorted(p.name for p in source.iterdir()) == ["photo.tif"]


def test_precancelled_live_run_creates_nothing(tmp_path):
    source = tmp_path / "scans"
    source.mkdir()
    make_tiff(source / "photo.tif")
    token = make_cancel_token()
    token.set()

    result = run_converter(
        source,
        dry_run=False,
        create_heic=False,
        create_jpg=False,
        variant_policy="none",
        cancel_event=token,
    )

    assert result.cancelled is True
    assert sorted(p.name for p in source.iterdir()) == ["photo.tif"]
