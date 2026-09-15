"""Tests for the PySide6 folder-renamer panel."""
from __future__ import annotations

import time

from PySide6.QtWidgets import QFileDialog, QMessageBox

from photo_organizer.gui.panels.folder_renamer import FolderRenamerPanel
from photo_organizer.renamer.engine import RenameOp, RenameResult


def wait_until(qapp, predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for Qt state change")


def test_folder_renamer_starts_with_safe_engine_defaults(qapp):
    panel = FolderRenamerPanel()

    assert panel.dry_run_checkbox.isChecked()
    assert panel.recursive_checkbox.isChecked()
    assert panel.include_model_checkbox.isChecked()
    assert not panel.merge_checkbox.isChecked()
    assert "no files changed" in panel.safety_label.text().lower()
    assert not panel.run_button.isEnabled()
    assert not panel.cancel_button.isEnabled()


def test_valid_folder_enables_preview_and_builds_options(qapp, tmp_path):
    panel = FolderRenamerPanel()
    panel.source_edit.setText(str(tmp_path))
    panel.recursive_checkbox.setChecked(False)
    panel.include_model_checkbox.setChecked(False)
    panel.merge_checkbox.setChecked(True)

    assert panel.run_button.isEnabled()
    assert panel.build_options() == {
        "dry_run": True,
        "recursive": False,
        "include_model": False,
        "merge": True,
    }


def test_browse_button_sets_parent_folder(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(tmp_path))
    panel = FolderRenamerPanel()

    panel.browse_button.click()

    assert panel.source_edit.text() == str(tmp_path)


def test_preview_runs_in_worker_without_renaming_folders(qapp, tmp_path, monkeypatch):
    source = tmp_path / "10000101"
    source.mkdir()
    (source / "photo.jpg").write_bytes(b"photo")
    destination = tmp_path / "2000-01-01"
    monkeypatch.setattr(
        "photo_organizer.renamer.engine.extract_folder_metadata",
        lambda folder_path: ("2000-01-01", None, "photo.jpg"),
    )
    panel = FolderRenamerPanel()
    panel.source_edit.setText(str(tmp_path))

    panel.run_button.click()
    wait_until(qapp, lambda: panel.result_table.rowCount() == 1)

    assert source.is_dir()
    assert not destination.exists()
    assert panel.result_table.item(0, 2).text() == "Planned rename"
    assert panel.progress_bar.value() == 100
    assert panel.run_button.isEnabled()
    assert not panel.cancel_button.isEnabled()


def test_live_run_requires_confirmation_then_renames(qapp, tmp_path, monkeypatch):
    source = tmp_path / "10000101"
    source.mkdir()
    (source / "photo.jpg").write_bytes(b"photo")
    destination = tmp_path / "2000-01-01"
    confirmations = []

    monkeypatch.setattr(
        "photo_organizer.renamer.engine.extract_folder_metadata",
        lambda folder_path: ("2000-01-01", None, "photo.jpg"),
    )

    def confirm(*args):
        confirmations.append(args)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", confirm)
    panel = FolderRenamerPanel()
    panel.source_edit.setText(str(tmp_path))
    panel.dry_run_checkbox.setChecked(False)

    panel.run_button.click()
    wait_until(qapp, lambda: panel.result_table.rowCount() == 1)

    assert len(confirmations) == 1
    assert not source.exists()
    assert destination.is_dir()
    assert panel.result_table.item(0, 2).text() == "Renamed"


def test_declining_merge_confirmation_does_not_start_engine(qapp, tmp_path, monkeypatch):
    calls = []
    prompts = []

    def engine(*args):
        calls.append(args)
        return RenameResult()

    def decline(*args):
        prompts.append(args[2])
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(QMessageBox, "question", decline)
    panel = FolderRenamerPanel(engine=engine)
    panel.source_edit.setText(str(tmp_path))
    panel.merge_checkbox.setChecked(True)
    panel.dry_run_checkbox.setChecked(False)

    panel.run_button.click()
    qapp.processEvents()

    assert calls == []
    assert len(prompts) == 1
    assert "merged" in prompts[0].lower()
    assert panel.run_button.isEnabled()
    assert not panel.cancel_button.isEnabled()


def test_preview_renders_rename_merge_and_skipped_summary(qapp, tmp_path):
    def engine(source, options, progress_callback, log_callback):
        progress_callback(100)
        return RenameResult(
            ops=[
                RenameOp("old-a", "new-a", "rename", True),
                RenameOp("old-b", "new-b", "merge", True),
            ],
            success=2,
            skipped={"no_metadata": 2, "destination_exists": 1},
        )

    panel = FolderRenamerPanel(engine=engine)
    panel.source_edit.setText(str(tmp_path))

    panel.run_button.click()
    wait_until(qapp, lambda: panel.result_table.rowCount() == 2)

    assert panel.result_table.item(0, 2).text() == "Planned rename"
    assert panel.result_table.item(1, 2).text() == "Planned merge"
    assert panel.status_label.text() == "Complete — 2 planned, 0 failed, 3 skipped"


def test_live_result_labels_successful_merge(qapp, tmp_path, monkeypatch):
    def engine(source, options, progress_callback, log_callback):
        return RenameResult(
            ops=[RenameOp("old", "new", "merge", True)],
            success=1,
        )

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args: QMessageBox.StandardButton.Yes,
    )
    panel = FolderRenamerPanel(engine=engine)
    panel.source_edit.setText(str(tmp_path))
    panel.merge_checkbox.setChecked(True)
    panel.dry_run_checkbox.setChecked(False)

    panel.run_button.click()
    wait_until(qapp, lambda: panel.result_table.rowCount() == 1)

    assert panel.result_table.item(0, 2).text() == "Merged"
    assert panel.status_label.text() == "Complete — 1 completed, 0 failed, 0 skipped"


def test_cancelled_state_is_not_overwritten_by_partial_result(qapp, tmp_path):
    def cancellable_engine(source, options, progress_callback, log_callback):
        while not options["cancel_event"].is_set():
            time.sleep(0.01)
        return RenameResult()

    panel = FolderRenamerPanel(engine=cancellable_engine)
    panel.source_edit.setText(str(tmp_path))

    panel.run_button.click()
    assert not panel.source_edit.isEnabled()
    assert not panel.browse_button.isEnabled()
    assert not panel.recursive_checkbox.isEnabled()
    assert not panel.include_model_checkbox.isEnabled()
    assert not panel.merge_checkbox.isEnabled()
    assert not panel.dry_run_checkbox.isEnabled()
    assert panel.cancel_button.isEnabled()

    panel.cancel_button.click()
    wait_until(qapp, panel.run_button.isEnabled)

    assert panel.status_label.text() == "Cancelled"
    assert not panel.cancel_button.isEnabled()


def test_engine_error_is_shown_and_restores_controls(qapp, tmp_path):
    def broken_engine(source, options, progress_callback, log_callback):
        raise RuntimeError("boom")

    panel = FolderRenamerPanel(engine=broken_engine)
    panel.source_edit.setText(str(tmp_path))

    panel.run_button.click()
    wait_until(qapp, lambda: panel.status_label.text().startswith("Failed"))
    wait_until(qapp, panel.run_button.isEnabled)

    assert "RuntimeError: boom" in panel.status_label.text()
    assert "RuntimeError: boom" in panel.log_view.toPlainText()
    assert not panel.cancel_button.isEnabled()


def test_empty_preview_reports_zero_operations(qapp, tmp_path):
    panel = FolderRenamerPanel()
    panel.source_edit.setText(str(tmp_path))

    panel.run_button.click()
    wait_until(qapp, lambda: panel.status_label.text().startswith("Complete"))

    assert panel.status_label.text() == "Complete — 0 planned, 0 failed, 0 skipped"
    assert panel.result_table.rowCount() == 0
    assert panel.run_button.isEnabled()
