"""Photo & Video Organizer panel."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from photo_organizer.gui.worker import EngineWorker
from photo_organizer.organizer.engine import (
    DEFAULT_OPTIONS,
    OrganizeResult,
    process_organize,
)

_STATUS_LABELS = {
    "planned": "Planned",
    "moved": "Moved",
    "skipped_already_organized": "Skipped: already organized",
    "skipped_collision": "Skipped: collision",
}


class OrganizerPanel(QWidget):
    """Collect organizer options and display engine results."""

    def __init__(self, engine: Callable[..., Any] = process_organize, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._worker: EngineWorker | None = None
        self._terminal_state: str | None = None

        layout = QVBoxLayout(self)
        title = QLabel("📸 Photo & Video Organizer")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(
            QLabel("Sort media into date and camera-model folders by metadata.")
        )

        form = QFormLayout()
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Choose the folder to organize…")
        self.browse_button = QPushButton("Browse…")
        source_row = QWidget()
        source_layout = QHBoxLayout(source_row)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addWidget(self.source_edit, 1)
        source_layout.addWidget(self.browse_button)
        form.addRow("Source folder", source_row)

        self.destination_edit = QLineEdit()
        self.destination_edit.setPlaceholderText("Defaults to the source folder…")
        self.destination_browse_button = QPushButton("Browse…")
        destination_row = QWidget()
        destination_layout = QHBoxLayout(destination_row)
        destination_layout.setContentsMargins(0, 0, 0, 0)
        destination_layout.addWidget(self.destination_edit, 1)
        destination_layout.addWidget(self.destination_browse_button)
        form.addRow("Destination folder", destination_row)

        self.media_combo = QComboBox()
        self.media_combo.addItems(["both", "photos", "videos"])
        self.media_combo.setCurrentText(DEFAULT_OPTIONS["media_type"])
        form.addRow("Media type", self.media_combo)
        layout.addLayout(form)

        self.recursive_checkbox = QCheckBox("Search subfolders recursively")
        self.recursive_checkbox.setChecked(DEFAULT_OPTIONS["recursive"])
        self.by_camera_checkbox = QCheckBox("Group by camera model")
        self.by_camera_checkbox.setChecked(DEFAULT_OPTIONS["by_camera_model"])
        self.add_model_checkbox = QCheckBox("Append camera model to date folders")
        self.add_model_checkbox.setChecked(DEFAULT_OPTIONS["add_model_to_folder"])
        self.separate_checkbox = QCheckBox("Separate photos and videos")
        self.separate_checkbox.setChecked(DEFAULT_OPTIONS["separate_photos_videos"])
        for box in (
            self.recursive_checkbox,
            self.by_camera_checkbox,
            self.add_model_checkbox,
            self.separate_checkbox,
        ):
            layout.addWidget(box)

        self.dry_run_checkbox = QCheckBox("Preview only")
        self.dry_run_checkbox.setChecked(DEFAULT_OPTIONS["dry_run"])
        self.safety_label = QLabel("Shows planned moves; no files are moved.")
        layout.addWidget(self.dry_run_checkbox)
        layout.addWidget(self.safety_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Choose a source folder to preview.")
        layout.addWidget(self.status_label)

        layout.addWidget(QLabel("Results"))
        self.result_table = QTableWidget(0, 3)
        self.result_table.setHorizontalHeaderLabels(["Source", "Destination", "Result"])
        self.result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.result_table.setColumnWidth(2, 180)
        layout.addWidget(self.result_table, 2)

        layout.addWidget(QLabel("Activity log"))
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(1_000)
        self.log_view.setPlaceholderText("Run details will appear here.")
        layout.addWidget(self.log_view, 1)

        buttons = QHBoxLayout()
        self.run_button = QPushButton("Preview")
        self.run_button.setEnabled(False)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.run_button)
        layout.addLayout(buttons)

        self.source_edit.textChanged.connect(self._on_source_changed)
        self.browse_button.clicked.connect(self._browse_source)
        self.destination_browse_button.clicked.connect(self._browse_destination)
        self.dry_run_checkbox.toggled.connect(self._update_mode_copy)
        self.run_button.clicked.connect(self._start)
        self.cancel_button.clicked.connect(self._cancel)

    def _browse_source(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Choose source folder", self.source_edit.text()
        )
        if selected:
            self.source_edit.setText(selected)

    def _browse_destination(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Choose destination folder", self.destination_edit.text()
        )
        if selected:
            self.destination_edit.setText(selected)

    def _on_source_changed(self, text: str) -> None:
        # Default the destination to the source (in-place organize) until the
        # user picks a different one.
        if not self.destination_edit.text().strip():
            self.destination_edit.setText(text)
        self._update_run_enabled()

    def build_options(self) -> dict:
        """Return the engine options represented by the current controls."""
        destination = self.destination_edit.text().strip() or self.source_edit.text()
        return {
            "dry_run": self.dry_run_checkbox.isChecked(),
            "destination": destination,
            "recursive": self.recursive_checkbox.isChecked(),
            "by_camera_model": self.by_camera_checkbox.isChecked(),
            "add_model_to_folder": self.add_model_checkbox.isChecked(),
            "media_type": self.media_combo.currentText(),
            "separate_photos_videos": self.separate_checkbox.isChecked(),
        }

    def _update_run_enabled(self) -> None:
        source = Path(self.source_edit.text()).expanduser()
        self.run_button.setEnabled(self._worker is None and source.is_dir())

    def _update_mode_copy(self, dry_run: bool) -> None:
        if dry_run:
            self.safety_label.setText("Shows planned moves; no files are moved.")
            self.run_button.setText("Preview")
        else:
            self.safety_label.setText(
                "Live mode — files are moved (never overwritten); "
                "cancellation does not roll back completed moves."
            )
            self.run_button.setText("Organize files")

    def _start(self) -> None:
        if not self.run_button.isEnabled():
            return
        options = self.build_options()
        if not self.dry_run_checkbox.isChecked():
            answer = QMessageBox.question(
                self,
                "Confirm live organize",
                "Move the matching files now?\n\n"
                f"Source: {self.source_edit.text()}\n"
                f"Destination: {options['destination']}\n"
                f"Recursive: {options['recursive']}\n"
                f"Media: {options['media_type']}\n\n"
                "Conflicts are skipped, and completed moves are not rolled back "
                "if you cancel.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        source = Path(self.source_edit.text()).expanduser()
        self._terminal_state = None
        self.result_table.setRowCount(0)
        self.log_view.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText(
            "Previewing…" if self.dry_run_checkbox.isChecked() else "Organizing…"
        )
        self._set_inputs_enabled(False)

        worker = EngineWorker(self._engine, source, options, self)
        self._worker = worker
        worker.progress.connect(self.progress_bar.setValue)
        worker.message.connect(self.log_view.appendPlainText)
        worker.result_ready.connect(self._on_result)
        worker.failed.connect(self._on_failed)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(self._on_thread_finished)
        worker.start()

    def _cancel(self) -> None:
        if self._worker is None:
            return
        self.status_label.setText("Cancelling…")
        self.cancel_button.setEnabled(False)
        self._worker.cancel()

    def _on_result(self, result: OrganizeResult) -> None:
        self.result_table.setRowCount(len(result.ops))
        for row, op in enumerate(result.ops):
            if op.status == "failed":
                state = f"Failed: {op.error}" if op.error else "Failed"
            else:
                state = _STATUS_LABELS.get(op.status, op.status)
            self.result_table.setItem(row, 0, QTableWidgetItem(op.source))
            self.result_table.setItem(row, 1, QTableWidgetItem(op.dest))
            self.result_table.setItem(row, 2, QTableWidgetItem(state))

        if result.cancelled:
            self._on_cancelled()
        if self._terminal_state != "cancelled":
            self._terminal_state = "completed"
            done = result.planned if self.dry_run_checkbox.isChecked() else result.moved
            verb = "planned" if self.dry_run_checkbox.isChecked() else "moved"
            status = (
                f"Complete — {done} {verb}, {result.skipped} skipped, "
                f"{result.failed} failed"
            )
            if result.database_error:
                status += f" (camera database not updated: {result.database_error})"
            self.status_label.setText(status)

    def _on_failed(self, error: str) -> None:
        self._terminal_state = "failed"
        self.status_label.setText(f"Failed — {error}")
        self.log_view.appendPlainText(error)

    def _on_cancelled(self) -> None:
        self._terminal_state = "cancelled"
        self.status_label.setText("Cancelled")

    def _on_thread_finished(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()
        self._set_inputs_enabled(True)
        self._update_run_enabled()

    def _set_inputs_enabled(self, enabled: bool) -> None:
        self.source_edit.setEnabled(enabled)
        self.browse_button.setEnabled(enabled)
        self.destination_edit.setEnabled(enabled)
        self.destination_browse_button.setEnabled(enabled)
        self.media_combo.setEnabled(enabled)
        self.recursive_checkbox.setEnabled(enabled)
        self.by_camera_checkbox.setEnabled(enabled)
        self.add_model_checkbox.setEnabled(enabled)
        self.separate_checkbox.setEnabled(enabled)
        self.dry_run_checkbox.setEnabled(enabled)
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(not enabled)
