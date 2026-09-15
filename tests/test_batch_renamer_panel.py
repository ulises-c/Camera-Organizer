"""Tests for the first real PySide6 tool panel."""
from __future__ import annotations

import time

from PySide6.QtWidgets import QFileDialog, QMessageBox

from photo_organizer.gui.panels.batch_renamer import BatchRenamerPanel
from photo_organizer.renamer.engine import RenameResult


def wait_until(qapp, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for Qt state change")


def test_batch_renamer_starts_in_safe_invalid_state(qapp):
    panel = BatchRenamerPanel(models=["Sony a6700"])

    assert panel.dry_run_checkbox.isChecked()
    assert "no files changed" in panel.safety_label.text().lower()
    assert not panel.run_button.isEnabled()
    assert not panel.cancel_button.isEnabled()


def test_valid_folder_and_model_enable_preview_and_build_options(qapp, tmp_path):
    panel = BatchRenamerPanel(models=["Sony a6700"])

    panel.source_edit.setText(str(tmp_path))
    panel.model_combo.setCurrentText("Sony a6700")

    assert panel.run_button.isEnabled()
    assert panel.build_options() == {"dry_run": True, "model": "Sony a6700"}


def test_browse_button_sets_selected_folder(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(tmp_path))
    panel = BatchRenamerPanel(models=[])

    panel.browse_button.click()

    assert panel.source_edit.text() == str(tmp_path)


def test_preview_runs_in_worker_without_mutating_files(qapp, tmp_path):
    original = tmp_path / "trip_UnknownCamera.jpg"
    original.write_bytes(b"photo")
    renamed = tmp_path / "trip_Sony a6700.jpg"
    panel = BatchRenamerPanel(models=["Sony a6700"])
    panel.source_edit.setText(str(tmp_path))
    panel.model_combo.setCurrentText("Sony a6700")

    panel.run_button.click()
    wait_until(qapp, lambda: panel.result_table.rowCount() == 1)

    assert original.exists()
    assert not renamed.exists()
    assert panel.result_table.item(0, 2).text() == "Planned"
    assert panel.progress_bar.value() == 100
    assert panel.run_button.isEnabled()
    assert not panel.cancel_button.isEnabled()


def test_live_run_requires_confirmation_then_renames(qapp, tmp_path, monkeypatch):
    original = tmp_path / "trip_UnknownCamera.jpg"
    original.write_bytes(b"photo")
    renamed = tmp_path / "trip_Sony a6700.jpg"
    confirmations = []

    def confirm(*args):
        confirmations.append(args)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", confirm)
    panel = BatchRenamerPanel(models=["Sony a6700"])
    panel.source_edit.setText(str(tmp_path))
    panel.model_combo.setCurrentText("Sony a6700")
    panel.dry_run_checkbox.setChecked(False)

    panel.run_button.click()
    wait_until(qapp, lambda: panel.result_table.rowCount() == 1)

    assert len(confirmations) == 1
    assert not original.exists()
    assert renamed.exists()
    assert panel.result_table.item(0, 2).text() == "Renamed"


def test_declining_live_confirmation_does_not_start_engine(qapp, tmp_path, monkeypatch):
    calls = []

    def engine(*args):
        calls.append(args)
        return RenameResult()

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.No,
    )
    panel = BatchRenamerPanel(models=["Sony a6700"], engine=engine)
    panel.source_edit.setText(str(tmp_path))
    panel.model_combo.setCurrentText("Sony a6700")
    panel.dry_run_checkbox.setChecked(False)

    panel.run_button.click()
    qapp.processEvents()

    assert calls == []
    assert panel.run_button.isEnabled()
    assert not panel.cancel_button.isEnabled()


def test_cancelled_state_is_not_overwritten_by_partial_result(qapp, tmp_path):
    def cancellable_engine(source, options, progress_callback, log_callback):
        while not options["cancel_event"].is_set():
            time.sleep(0.01)
        return RenameResult()

    panel = BatchRenamerPanel(models=["Sony a6700"], engine=cancellable_engine)
    panel.source_edit.setText(str(tmp_path))
    panel.model_combo.setCurrentText("Sony a6700")

    panel.run_button.click()
    panel.cancel_button.click()
    wait_until(qapp, panel.run_button.isEnabled)

    assert panel.status_label.text() == "Cancelled"
    assert not panel.cancel_button.isEnabled()


def test_empty_preview_reports_zero_planned_and_restores_controls(qapp, tmp_path):
    panel = BatchRenamerPanel(models=["Sony a6700"])
    panel.source_edit.setText(str(tmp_path))
    panel.model_combo.setCurrentText("Sony a6700")

    panel.run_button.click()
    wait_until(qapp, lambda: panel.status_label.text().startswith("Complete"))

    assert "0 planned" in panel.status_label.text()
    assert panel.result_table.rowCount() == 0
    assert panel.run_button.isEnabled()


def test_engine_error_is_shown_and_restores_controls(qapp, tmp_path):
    def broken_engine(source, options, progress_callback, log_callback):
        raise RuntimeError("boom")

    panel = BatchRenamerPanel(models=["Sony a6700"], engine=broken_engine)
    panel.source_edit.setText(str(tmp_path))
    panel.model_combo.setCurrentText("Sony a6700")

    panel.run_button.click()
    wait_until(qapp, lambda: panel.status_label.text().startswith("Failed"))
    wait_until(qapp, panel.run_button.isEnabled)

    assert "RuntimeError: boom" in panel.status_label.text()
    assert "RuntimeError: boom" in panel.log_view.toPlainText()
    assert not panel.cancel_button.isEnabled()
