"""Batch-renamer panel."""
from __future__ import annotations

from collections.abc import Callable, Iterable
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
from photo_organizer.renamer.engine import RenameResult, process_batch_rename
from photo_organizer.shared.camera_models import get_camera_models


class BatchRenamerPanel(QWidget):
    """Collect safe batch-renamer inputs before an engine run."""

    def __init__(self, models: Iterable[str] | None = None,
                 engine: Callable[..., Any] = process_batch_rename, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._worker: EngineWorker | None = None
        self._terminal_state: str | None = None

        layout = QVBoxLayout(self)
        title = QLabel("🏷️ Batch Renamer")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Replace 'UnknownCamera' in file and folder names."))

        form = QFormLayout()
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Choose a folder…")
        self.browse_button = QPushButton("Browse…")
        source_row = QWidget()
        source_layout = QHBoxLayout(source_row)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addWidget(self.source_edit, 1)
        source_layout.addWidget(self.browse_button)
        form.addRow("Source folder", source_row)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(list(models) if models is not None else get_camera_models())
        self.model_combo.setCurrentIndex(-1)
        self.model_combo.setEditText("")
        model_editor = self.model_combo.lineEdit()
        if model_editor is not None:
            model_editor.setPlaceholderText("Select or enter a camera model…")
        form.addRow("Camera model", self.model_combo)
        layout.addLayout(form)

        self.dry_run_checkbox = QCheckBox("Preview only")
        self.dry_run_checkbox.setChecked(True)
        self.safety_label = QLabel("Shows proposed changes; no files changed.")
        layout.addWidget(self.dry_run_checkbox)
        layout.addWidget(self.safety_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Choose a folder and camera model to preview renames.")
        layout.addWidget(self.status_label)

        layout.addWidget(QLabel("Results"))
        self.result_table = QTableWidget(0, 3)
        self.result_table.setHorizontalHeaderLabels(["Current path", "New path", "Result"])
        self.result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.result_table.setColumnWidth(2, 140)
        layout.addWidget(self.result_table, 1)

        layout.addWidget(QLabel("Activity log"))
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(1_000)
        self.log_view.setPlaceholderText("Run details will appear here.")
        layout.addWidget(self.log_view, 1)

        buttons = QHBoxLayout()
        self.run_button = QPushButton("Preview renames")
        self.run_button.setEnabled(False)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setEnabled(False)
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.run_button)
        layout.addLayout(buttons)

        self.source_edit.textChanged.connect(self._update_run_enabled)
        self.browse_button.clicked.connect(self._browse)
        self.model_combo.currentTextChanged.connect(self._update_run_enabled)
        self.dry_run_checkbox.toggled.connect(self._update_mode_copy)
        self.run_button.clicked.connect(self._start)
        self.cancel_button.clicked.connect(self._cancel)

    def _browse(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Choose folder to rename", self.source_edit.text()
        )
        if selected:
            self.source_edit.setText(selected)

    def build_options(self) -> dict:
        """Return the engine options represented by the current controls."""
        return {
            "dry_run": self.dry_run_checkbox.isChecked(),
            "model": self.model_combo.currentText().strip(),
        }

    def _update_run_enabled(self) -> None:
        source = Path(self.source_edit.text()).expanduser()
        has_model = bool(self.model_combo.currentText().strip())
        self.run_button.setEnabled(
            self._worker is None and source.is_dir() and has_model
        )

    def _update_mode_copy(self, dry_run: bool) -> None:
        if dry_run:
            self.safety_label.setText("Shows proposed changes; no files changed.")
            self.run_button.setText("Preview renames")
        else:
            self.safety_label.setText("Live mode — matching files and folders will be renamed.")
            self.run_button.setText("Rename files")

    def _start(self) -> None:
        if not self.run_button.isEnabled():
            return
        if not self.dry_run_checkbox.isChecked():
            answer = QMessageBox.question(
                self,
                "Confirm live rename",
                "Rename every matching file and folder now? This changes names on disk.",
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
            "Previewing…" if self.dry_run_checkbox.isChecked() else "Renaming…"
        )
        self._set_inputs_enabled(False)

        worker = EngineWorker(self._engine, source, self.build_options(), self)
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

    def _on_result(self, result: RenameResult) -> None:
        dry_run = self.dry_run_checkbox.isChecked()
        self.result_table.setRowCount(len(result.ops))
        for row, op in enumerate(result.ops):
            state = "Planned" if dry_run and op.success else "Renamed" if op.success else "Failed"
            if op.error:
                state = f"Failed: {op.error}"
            self.result_table.setItem(row, 0, QTableWidgetItem(op.old))
            self.result_table.setItem(row, 1, QTableWidgetItem(op.new))
            self.result_table.setItem(row, 2, QTableWidgetItem(state))
        if self._terminal_state != "cancelled":
            self._terminal_state = "completed"
            verb = "planned" if dry_run else "renamed"
            self.status_label.setText(
                f"Complete — {result.success} {verb}, {result.failed} failed"
            )

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
        self.model_combo.setEnabled(enabled)
        self.dry_run_checkbox.setEnabled(enabled)
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(not enabled)
