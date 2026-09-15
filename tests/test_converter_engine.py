"""Safety and fidelity tests for the TIFF/Epson converter engine."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from photo_organizer.converter import engine as converter_engine
from photo_organizer.converter.engine import process_epson_folder, save_report
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


def test_requested_heic_without_encoder_is_explicit_failure(tmp_path, monkeypatch):
    source = tmp_path / "scans"
    source.mkdir()
    make_tiff(source / "scan.tif")
    monkeypatch.setattr(converter_engine, "HEIF_SAVE_AVAILABLE", False)

    result = run_converter(
        source,
        dry_run=True,
        create_heic=True,
        create_jpg=False,
        variant_policy="none",
    )

    assert result.groups[0].success is False
    heic = next(d for d in result.groups[0].details if d.action == "HEIC")
    assert heic.status == "failed"
    assert "unavailable" in heic.error.lower()


def test_original_stays_when_any_requested_derivative_fails(tmp_path, monkeypatch):
    source = tmp_path / "scans"
    source.mkdir()
    scan = source / "scan.tif"
    make_tiff(scan)

    def fail_jpeg(*args, **kwargs):
        raise OSError("jpeg failed")

    monkeypatch.setattr(converter_engine, "_save_image", fail_jpeg)

    result = run_converter(
        source,
        dry_run=False,
        create_heic=False,
        create_jpg=True,
        variant_policy="none",
    )

    assert scan.is_file()
    assert (source / "lossless_compressed" / "scan.ZIP.TIF").is_file()
    assert result.groups[0].success is False
    assert not any(d.action == "MOVE_ORIGINAL" for d in result.groups[0].details)


def test_jpeg_flattens_alpha_on_white_and_preserves_metadata(tmp_path):
    source = tmp_path / "scans"
    source.mkdir()
    image = Image.new("RGBA", (16, 16), (255, 0, 0, 0))
    exif = Image.Exif()
    exif[270] = "scanner description"
    image.save(source / "scan.tif", format="TIFF", dpi=(300, 300), exif=exif)

    result = run_converter(
        source,
        dry_run=False,
        create_heic=False,
        create_jpg=True,
        jpg_quality=95,
        variant_policy="none",
    )

    assert result.groups[0].success is True
    with Image.open(source / "JPG" / "scan.jpg") as converted:
        red, green, blue = converted.getpixel((0, 0))
        assert min(red, green, blue) > 240
        assert converted.info["dpi"] == pytest.approx((300, 300), abs=1)
        assert converted.getexif()[270] == "scanner description"


def test_cancelled_current_group_keeps_partial_operations(tmp_path, monkeypatch):
    source = tmp_path / "scans"
    source.mkdir()
    scan = source / "scan.tif"
    make_tiff(scan)
    token = make_cancel_token()

    def cancel_jpeg(src, dest, fmt, qual, cancel_event):
        cancel_event.set()
        raise converter_engine.OperationCancelled("cancelled")

    monkeypatch.setattr(converter_engine, "_save_image", cancel_jpeg)

    result = run_converter(
        source,
        dry_run=False,
        create_heic=False,
        create_jpg=True,
        variant_policy="none",
        cancel_event=token,
    )

    assert result.cancelled is True
    assert len(result.groups) == 1
    assert [d.status for d in result.groups[0].details] == ["written", "cancelled"]
    assert scan.is_file()


def test_cancel_during_encode_prevents_publication(tmp_path):
    dest = tmp_path / "output.tif"
    token = make_cancel_token()

    def write_then_cancel(temp_path):
        temp_path.write_bytes(b"encoded")
        token.set()

    with pytest.raises(converter_engine.OperationCancelled):
        converter_engine._atomic_replace_temp(dest, write_then_cancel, token)

    assert not dest.exists()
    assert not list(tmp_path.glob(".output.tif.tmp.*"))


def test_original_move_is_atomic_and_never_clobbers(tmp_path):
    source = tmp_path / "scan.tif"
    destination = tmp_path / "originals" / "scan.tif"
    source.write_bytes(b"new")
    destination.parent.mkdir()
    destination.write_bytes(b"existing")

    with pytest.raises(FileExistsError):
        converter_engine._move_no_clobber(source, destination)

    assert source.read_bytes() == b"new"
    assert destination.read_bytes() == b"existing"


def test_report_totals_are_derived_from_structured_statuses(tmp_path):
    source = tmp_path / "scans"
    source.mkdir()
    make_tiff(source / "scan.tif")
    result = run_converter(
        source,
        dry_run=True,
        create_heic=False,
        create_jpg=False,
        variant_policy="none",
    )
    report = tmp_path / "report.json"

    save_report(result, report)

    data = json.loads(report.read_text())
    assert data["summary"] == {
        "total_groups": 1,
        "successful_groups": 1,
        "total_operations": 1,
        "planned": 1,
        "written": 0,
        "moved": 0,
        "skipped": 0,
        "failed": 0,
        "cancelled": False,
    }


def test_base_variant_policy_archives_augmented_lossless_and_limits_jpeg(tmp_path):
    source = tmp_path / "scans"
    source.mkdir()
    for name in ("photo.tif", "photo_a.tif", "photo_b.tif"):
        make_tiff(source / name)

    result = run_converter(
        source,
        dry_run=True,
        create_heic=False,
        create_jpg=True,
        variant_policy="base",
        variant_smart_archiving=True,
        variant_smart_conversion=True,
    )

    details = result.groups[0].details
    planned = {(d.source, d.action, d.output) for d in details}
    assert ("photo.tif", "JPG", "JPG/photo.jpg") in planned
    assert ("photo_b.tif", "JPG", "JPG/photo_b.jpg") in planned
    assert not any(d.source == "photo_a.tif" and d.action == "JPG" for d in details)
    assert (
        "photo_a.tif",
        "TIFF-DEFLATE",
        "lossless_compressed/archive/photo_a.ZIP.TIF",
    ) in planned
