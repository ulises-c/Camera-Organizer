"""Safety and fidelity tests for the TIFF/Epson converter engine."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from photo_organizer.converter import engine as converter_engine
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


def test_existing_output_is_never_overwritten_and_source_stays(tmp_path):
    source = tmp_path / "scans"
    source.mkdir()
    scan = source / "photo.tif"
    make_tiff(scan, color=(1, 2, 3))
    existing = source / "lossless_compressed" / "photo.ZIP.TIF"
    existing.parent.mkdir()
    make_tiff(existing, color=(200, 100, 50))
    original_output = existing.read_bytes()

    result = run_converter(
        source,
        dry_run=False,
        create_heic=False,
        create_jpg=False,
        variant_policy="none",
    )

    assert scan.is_file()
    assert existing.read_bytes() == original_output
    assert result.groups[0].success is False
    assert result.groups[0].details[0].status == "skipped_collision"


def test_same_run_output_collision_skips_both_sources(tmp_path):
    source = tmp_path / "scans"
    source.mkdir()
    first = source / "photo.tif"
    second = source / "photo.tiff"
    make_tiff(first, color=(1, 2, 3))
    make_tiff(second, color=(4, 5, 6))

    result = run_converter(
        source,
        dry_run=False,
        create_heic=False,
        create_jpg=False,
        variant_policy="none",
    )

    assert first.is_file()
    assert second.is_file()
    assert not (source / "lossless_compressed" / "photo.ZIP.TIF").exists()
    statuses = [d.status for d in result.groups[0].details]
    assert statuses == ["skipped_collision", "skipped_collision"]


def test_existing_original_archive_target_blocks_all_work(tmp_path):
    source = tmp_path / "scans"
    source.mkdir()
    scan = source / "photo.tif"
    make_tiff(scan, color=(1, 2, 3))
    archived = source / "originals" / "photo.tif"
    archived.parent.mkdir()
    make_tiff(archived, color=(200, 100, 50))
    original_archive = archived.read_bytes()

    result = run_converter(
        source,
        dry_run=False,
        create_heic=False,
        create_jpg=False,
        variant_policy="none",
    )

    assert scan.is_file()
    assert archived.read_bytes() == original_archive
    assert not (source / "lossless_compressed" / "photo.ZIP.TIF").exists()
    assert result.groups[0].details[0].status == "skipped_collision"


def test_output_directory_symlink_escape_is_rejected(tmp_path):
    source = tmp_path / "scans"
    outside = tmp_path / "outside"
    source.mkdir()
    outside.mkdir()
    scan = source / "photo.tif"
    make_tiff(scan)
    (source / "lossless_compressed").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="outside source"):
        run_converter(
            source,
            dry_run=False,
            create_heic=False,
            create_jpg=False,
            variant_policy="none",
        )

    assert scan.is_file()
    assert list(outside.iterdir()) == []


def test_atomic_publish_never_replaces_racing_destination(tmp_path):
    dest = tmp_path / "out.tif"

    def write_fn(temp_path):
        temp_path.write_bytes(b"new")
        dest.write_bytes(b"race winner")

    with pytest.raises(FileExistsError):
        converter_engine._atomic_replace_temp(dest, write_fn)

    assert dest.read_bytes() == b"race winner"
    assert not list(tmp_path.glob(".out.tif.tmp.*"))


def test_live_tiff_only_creates_only_required_directories(tmp_path):
    source = tmp_path / "scans"
    source.mkdir()
    make_tiff(source / "photo.tif")

    result = run_converter(
        source,
        dry_run=False,
        create_heic=False,
        create_jpg=False,
        variant_policy="none",
    )

    assert result.groups[0].success is True
    assert (source / "lossless_compressed" / "photo.ZIP.TIF").is_file()
    assert (source / "originals" / "photo.tif").is_file()
    assert not (source / "lossless_compressed" / "archive").exists()
    assert not (source / "HEIC").exists()
    assert not (source / "JPG").exists()


def test_lossless_tiff_preserves_all_pages_and_pixels(tmp_path):
    source = tmp_path / "scans"
    source.mkdir()
    scan = source / "book.tif"
    make_tiff(scan, color=(20, 40, 60), frames=2)

    result = run_converter(
        source,
        dry_run=False,
        create_heic=False,
        create_jpg=False,
        variant_policy="none",
    )

    output = source / "lossless_compressed" / "book.ZIP.TIF"
    assert result.groups[0].success is True
    with Image.open(output) as image:
        assert image.n_frames == 2
        image.seek(0)
        assert image.getpixel((0, 0)) == (20, 40, 60)
        image.seek(1)
        assert image.getpixel((0, 0)) == (21, 40, 60)


@pytest.mark.parametrize(("compression", "suffix", "tag"), [
    ("deflate", ".ZIP.TIF", 8),
    ("lzw", ".LZW.TIF", 5),
])
def test_lossless_tiff_uses_advertised_codec(tmp_path, compression, suffix, tag):
    source = tmp_path / "scans"
    source.mkdir()
    image = Image.new("RGB", (8, 6), "navy")
    image.save(source / "scan.tif", format="TIFF", dpi=(300, 300))

    run_converter(
        source,
        dry_run=False,
        compression=compression,
        create_heic=False,
        create_jpg=False,
        variant_policy="none",
    )

    output = source / "lossless_compressed" / f"scan{suffix}"
    with Image.open(output) as converted:
        assert converted.tag_v2[259] == tag
        assert converted.info["dpi"] == pytest.approx((300, 300))
