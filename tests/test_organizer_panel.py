"""Tests for the PySide6 photo/video organizer panel."""
from __future__ import annotations

import time

from PySide6.QtWidgets import QFileDialog, QMessageBox

from photo_organizer.gui.panels.organizer import OrganizerPanel
from photo_organizer.organizer.engine import MoveOp, OrganizeResult


def wait_until(qapp, predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition not met in time")


def test_organizer_starts_with_safe_engine_defaults(qapp):
    panel = OrganizerPanel()

    assert panel.dry_run_checkbox.isChecked()
    assert "no files" in panel.safety_label.text().lower()
    assert not panel.run_button.isEnabled()
    assert not panel.cancel_button.isEnabled()
    assert panel.media_combo.currentText() == "both"


def test_valid_source_enables_preview_and_builds_options(qapp, tmp_path):
    panel = OrganizerPanel()
    panel.source_edit.setText(str(tmp_path))
    panel.recursive_checkbox.setChecked(False)
    panel.by_camera_checkbox.setChecked(False)
    panel.add_model_checkbox.setChecked(True)
    panel.separate_checkbox.setChecked(False)
    panel.media_combo.setCurrentText("photos")

    assert panel.run_button.isEnabled()
    options = panel.build_options()
    assert options == {
        "dry_run": True,
        "destination": str(tmp_path),
        "recursive": False,
        "by_camera_model": False,
        "add_model_to_folder": True,
        "media_type": "photos",
        "separate_photos_videos": False,
    }


def test_source_browse_defaults_destination(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(tmp_path))
    panel = OrganizerPanel()

    panel.browse_button.click()

    assert panel.source_edit.text() == str(tmp_path)
    assert panel.destination_edit.text() == str(tmp_path)
    assert panel.run_button.isEnabled()


def test_preview_runs_real_engine_without_moving_files(qapp, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    photo = source / "photo.JPG"
    photo.write_bytes(b"photo")
    panel = OrganizerPanel()
    panel.source_edit.setText(str(source))

    panel.run_button.click()
    wait_until(qapp, lambda: panel.result_table.rowCount() == 1)
    wait_until(qapp, panel.run_button.isEnabled)

    assert photo.is_file()
    assert panel.result_table.item(0, 2).text() == "Planned"
    assert panel.progress_bar.value() == 100


def test_result_states_render_from_operation_status(qapp, tmp_path):
    def engine(source, options, progress_callback, log_callback):
        return OrganizeResult(
            ops=[
                MoveOp("a.JPG", "out/a.JPG", "planned"),
                MoveOp("b.JPG", "out/b.JPG", "skipped_collision"),
                MoveOp("c.JPG", "out/c.JPG", "skipped_already_organized"),
                MoveOp("d.JPG", "out/d.JPG", "failed", "boom"),
            ],
            planned=1,
            skipped=2,
            failed=1,
        )

    panel = OrganizerPanel(engine=engine)
    panel.source_edit.setText(str(tmp_path))

    panel.run_button.click()
    wait_until(qapp, lambda: panel.result_table.rowCount() == 4)

    assert panel.result_table.item(0, 2).text() == "Planned"
    assert panel.result_table.item(1, 2).text() == "Skipped: collision"
    assert panel.result_table.item(2, 2).text() == "Skipped: already organized"
    assert panel.result_table.item(3, 2).text() == "Failed: boom"
    assert panel.status_label.text() == "Complete — 1 planned, 2 skipped, 1 failed"


def test_live_run_requires_confirmation(qapp, tmp_path, monkeypatch):
    source = tmp_path / "source"
    destination = tmp_path / "organized"
    source.mkdir()
    (source / "photo.JPG").write_bytes(b"photo")

    calls: list[dict] = []

    def engine(source_arg, options, progress_callback, log_callback):
        calls.append(options)
        return OrganizeResult(ops=[MoveOp("photo.JPG", "d/photo.JPG", "moved")], moved=1)

    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No
    )
    panel = OrganizerPanel(engine=engine)
    panel.source_edit.setText(str(source))
    panel.destination_edit.setText(str(destination))
    panel.dry_run_checkbox.setChecked(False)

    panel.run_button.click()
    qapp.processEvents()

    assert calls == []
    assert panel.run_button.isEnabled()


def test_cancelled_result_is_not_overwritten(qapp, tmp_path):
    def engine(source, options, progress_callback, log_callback):
        while not options["cancel_event"].is_set():
            time.sleep(0.01)
        return OrganizeResult(cancelled=True)

    panel = OrganizerPanel(engine=engine)
    panel.source_edit.setText(str(tmp_path))

    panel.run_button.click()
    assert not panel.source_edit.isEnabled()
    assert panel.cancel_button.isEnabled()
    panel.cancel_button.click()
    wait_until(qapp, panel.run_button.isEnabled)

    assert panel.status_label.text() == "Cancelled"


def test_empty_preview_restores_controls(qapp, tmp_path):
    panel = OrganizerPanel()
    panel.source_edit.setText(str(tmp_path))

    panel.run_button.click()
    wait_until(qapp, panel.run_button.isEnabled)

    assert panel.result_table.rowCount() == 0
    assert "0 planned" in panel.status_label.text()


def test_engine_exception_is_reported(qapp, tmp_path):
    def engine(source, options, progress_callback, log_callback):
        raise ValueError("bad metadata")

    panel = OrganizerPanel(engine=engine)
    panel.source_edit.setText(str(tmp_path))

    panel.run_button.click()
    wait_until(qapp, panel.run_button.isEnabled)

    assert "ValueError: bad metadata" in panel.status_label.text()
