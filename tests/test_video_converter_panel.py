"""Tests for the PySide6 video converter panel."""
from __future__ import annotations

import time

from PySide6.QtWidgets import QMessageBox

from photo_organizer.gui.panels.video_converter import VideoConverterPanel
from photo_organizer.video_converter.engine import OpDetail, VideoResult


def wait_until(qapp, predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met in time")


def test_starts_with_safe_defaults(qapp):
    panel = VideoConverterPanel()

    assert panel.dry_run_checkbox.isChecked()
    assert "no files" in panel.safety_label.text().lower()
    assert not panel.run_button.isEnabled()
    assert not panel.cancel_button.isEnabled()
    assert panel.stage1_checkbox.isChecked()
    assert panel.stage2_checkbox.isChecked()


def test_valid_source_enables_and_builds_options(qapp, tmp_path):
    panel = VideoConverterPanel()
    panel.source_edit.setText(str(tmp_path))
    panel.stage2_checkbox.setChecked(False)
    panel.crf_spin.setValue(18)
    panel.height_spin.setValue(2160)

    assert panel.run_button.isEnabled()
    options = panel.build_options()
    assert options["dry_run"] is True
    assert options["do_stage1"] is True
    assert options["do_stage2"] is False
    assert options["x265_crf"] == 18
    assert options["share_height"] == 2160
    # Auto LUT (no explicit pick) leaves explicit_lut None.
    assert options["explicit_lut"] is None


def test_preview_flattens_clip_details_into_rows(qapp, tmp_path):
    def engine(source, options, progress_callback, log_callback):
        return [
            VideoResult(
                source_stem="A", is_log=True, success=True,
                details=[
                    OpDetail("A.MP4", "STAGE1-LUT", "A.mov", True),
                    OpDetail("A.mov", "STAGE2-1080p", "A_1080p.mp4", True),
                ],
            ),
            VideoResult(
                source_stem="B", is_log=False, success=False,
                details=[OpDetail("B.MP4", "STAGE1-NATIVE", "B.mov", False, error="boom")],
            ),
        ]

    panel = VideoConverterPanel(engine=engine)
    panel.source_edit.setText(str(tmp_path))

    panel.run_button.click()
    wait_until(qapp, lambda: panel.result_table.rowCount() == 3)

    assert panel.result_table.item(0, 1).text() == "STAGE1-LUT"
    assert panel.result_table.item(2, 3).text() == "Failed: boom"
    assert "1/2 clips" in panel.status_label.text()


def test_live_run_requires_confirmation(qapp, tmp_path, monkeypatch):
    calls: list[dict] = []

    def engine(source, options, progress_callback, log_callback):
        calls.append(options)
        return []

    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No
    )
    panel = VideoConverterPanel(engine=engine)
    panel.source_edit.setText(str(tmp_path))
    panel.dry_run_checkbox.setChecked(False)

    panel.run_button.click()
    qapp.processEvents()

    assert calls == []
    assert panel.run_button.isEnabled()


def test_engine_exception_is_reported(qapp, tmp_path):
    def engine(source, options, progress_callback, log_callback):
        raise RuntimeError("ffmpeg exploded")

    panel = VideoConverterPanel(engine=engine)
    panel.source_edit.setText(str(tmp_path))

    panel.run_button.click()
    wait_until(qapp, panel.run_button.isEnabled)

    assert "RuntimeError: ffmpeg exploded" in panel.status_label.text()
