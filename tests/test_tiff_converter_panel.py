"""Tests for the PySide6 TIFF Converter panel."""
from __future__ import annotations

import time

from PySide6.QtWidgets import QFileDialog, QMessageBox

from photo_organizer.converter.engine import (
    ConversionResult,
    ConversionRunResult,
    OpDetail,
)
from photo_organizer.gui.panels.tiff_converter import TiffConverterPanel


def wait_until(qapp, predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met in time")


def test_starts_with_preview_and_engine_defaults(qapp):
    panel = TiffConverterPanel()

    assert panel.lossless_checkbox.isChecked()
    assert not panel.lossless_checkbox.isEnabled()
    assert panel.dry_run_checkbox.isChecked()
    assert "no files" in panel.safety_label.text().lower()
    assert panel.compression_combo.currentData() == "deflate"
    assert not panel.jpg_checkbox.isChecked()
    assert not panel.run_button.isEnabled()
    assert not panel.cancel_button.isEnabled()


def test_valid_source_and_controls_build_options(qapp, tmp_path):
    panel = TiffConverterPanel()
    panel.source_edit.setText(str(tmp_path))
    panel.compression_combo.setCurrentIndex(1)
    panel.heic_checkbox.setChecked(False)
    panel.jpg_checkbox.setChecked(True)
    panel.jpg_quality_spin.setValue(90)
    panel.fastfoto_checkbox.setChecked(False)

    assert panel.run_button.isEnabled()
    assert panel.build_options() == {
        "dry_run": True,
        "compression": "lzw",
        "create_heic": False,
        "heic_quality": panel.heic_quality_spin.value(),
        "create_jpg": True,
        "jpg_quality": 90,
        "variant_policy": "none",
        "variant_smart_archiving": panel.archive_checkbox.isChecked(),
        "variant_smart_conversion": panel.smart_conversion_checkbox.isChecked(),
    }
    assert not panel.variant_policy_combo.isEnabled()
    assert panel.jpg_quality_spin.isEnabled()


def test_browse_sets_source(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(tmp_path))
    panel = TiffConverterPanel()

    panel.browse_button.click()

    assert panel.source_edit.text() == str(tmp_path)
    assert panel.run_button.isEnabled()


def test_preview_real_engine_does_not_mutate_source(qapp, tmp_path):
    from PIL import Image

    Image.new("RGB", (8, 6), "navy").save(tmp_path / "scan.tif", format="TIFF")
    before = sorted(path.name for path in tmp_path.iterdir())
    panel = TiffConverterPanel()
    panel.source_edit.setText(str(tmp_path))
    panel.heic_checkbox.setChecked(False)
    panel.fastfoto_checkbox.setChecked(False)

    panel.run_button.click()
    wait_until(qapp, lambda: panel.result_table.rowCount() == 1)
    wait_until(qapp, panel.run_button.isEnabled)

    assert sorted(path.name for path in tmp_path.iterdir()) == before
    assert panel.result_table.item(0, 3).text() == "Planned"
    assert panel.progress_bar.value() == 100


def test_structured_statuses_are_rendered(qapp, tmp_path):
    def engine(source, options, progress_callback, log_callback):
        return ConversionRunResult(groups=[ConversionResult(
            "scan", False,
            [
                OpDetail("scan.tif", "TIFF-DEFLATE", "lossless/scan.tif", "written", 1_048_576),
                OpDetail("scan.tif", "JPG", "JPG/scan.jpg", "skipped_collision", error="exists"),
                OpDetail("scan.tif", "MOVE_ORIGINAL", "originals/scan.tif", "failed", error="denied"),
            ],
        )])

    panel = TiffConverterPanel(engine=engine)
    panel.source_edit.setText(str(tmp_path))

    panel.run_button.click()
    wait_until(qapp, lambda: panel.result_table.rowCount() == 3)

    assert panel.result_table.item(0, 3).text() == "Written"
    assert panel.result_table.item(0, 4).text() == "1.0 MB"
    assert panel.result_table.item(1, 3).text() == "Skipped: collision: exists"
    assert panel.result_table.item(2, 3).text() == "Failed: denied"
    assert "1 skipped, 1 failed" in panel.status_label.text()


def test_live_run_requires_confirmation(qapp, tmp_path, monkeypatch):
    calls: list[dict] = []

    def engine(source, options, progress_callback, log_callback):
        calls.append(options)
        return ConversionRunResult()

    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No
    )
    panel = TiffConverterPanel(engine=engine)
    panel.source_edit.setText(str(tmp_path))
    panel.dry_run_checkbox.setChecked(False)

    panel.run_button.click()
    qapp.processEvents()

    assert calls == []
    assert panel.run_button.isEnabled()


def test_cancelled_result_is_not_overwritten(qapp, tmp_path):
    def engine(source, options, progress_callback, log_callback):
        while not options["cancel_event"].is_set():
            time.sleep(0.01)
        return ConversionRunResult(cancelled=True)

    panel = TiffConverterPanel(engine=engine)
    panel.source_edit.setText(str(tmp_path))

    panel.run_button.click()
    assert not panel.source_edit.isEnabled()
    assert panel.cancel_button.isEnabled()
    panel.cancel_button.click()
    wait_until(qapp, panel.run_button.isEnabled)

    assert panel.status_label.text() == "Cancelled"


def test_empty_preview_restores_controls(qapp, tmp_path):
    panel = TiffConverterPanel()
    panel.source_edit.setText(str(tmp_path))
    panel.heic_checkbox.setChecked(False)

    panel.run_button.click()
    wait_until(qapp, panel.run_button.isEnabled)

    assert panel.result_table.rowCount() == 0
    assert "0/0 groups" in panel.status_label.text()


def test_engine_exception_is_reported(qapp, tmp_path):
    def engine(source, options, progress_callback, log_callback):
        raise ValueError("bad TIFF")

    panel = TiffConverterPanel(engine=engine)
    panel.source_edit.setText(str(tmp_path))

    panel.run_button.click()
    wait_until(qapp, panel.run_button.isEnabled)

    assert "ValueError: bad TIFF" in panel.status_label.text()
