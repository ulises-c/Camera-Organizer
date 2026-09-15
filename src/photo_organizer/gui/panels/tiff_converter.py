"""TIFF / Epson FastFoto Converter panel."""
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
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from photo_organizer.converter.engine import (
    DEFAULT_OPTIONS,
    HEIF_SAVE_AVAILABLE,
    ConversionRunResult,
    process_epson_folder,
)
from photo_organizer.gui.worker import EngineWorker

_STATUS_LABELS = {
    "planned": "Planned",
    "written": "Written",
    "moved": "Moved original",
    "skipped_collision": "Skipped: collision",
    "cancelled": "Cancelled",
}


class TiffConverterPanel(QWidget):
    """Configure the lossless TIFF + optional lossy FastFoto workflow."""

    def __init__(self, engine: Callable[..., Any] = process_epson_folder, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._worker: EngineWorker | None = None
        self._terminal_state: str | None = None

        layout = QVBoxLayout(self)
        title = QLabel("🖼️ TIFF Converter")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(
            QLabel("Create verified lossless TIFFs and optional lossy HEIC/JPEG copies.")
        )

        source_form = QFormLayout()
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Choose a folder containing root-level TIFFs…")
        self.browse_button = QPushButton("Browse…")
        source_row = QWidget()
        source_layout = QHBoxLayout(source_row)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addWidget(self.source_edit, 1)
        source_layout.addWidget(self.browse_button)
        source_form.addRow("Source folder", source_row)
        layout.addLayout(source_form)

        option_columns = QHBoxLayout()
        format_widget = QWidget()
        format_form = QFormLayout(format_widget)

        self.lossless_checkbox = QCheckBox("Create lossless TIFF (required)")
        self.lossless_checkbox.setChecked(True)
        self.lossless_checkbox.setEnabled(False)
        format_form.addRow(self.lossless_checkbox)

        self.compression_combo = QComboBox()
        self.compression_combo.addItem("Deflate (.ZIP.TIF)", "deflate")
        self.compression_combo.addItem("LZW (.LZW.TIF)", "lzw")
        self.compression_combo.setCurrentIndex(
            self.compression_combo.findData(DEFAULT_OPTIONS["compression"])
        )
        format_form.addRow("Compression", self.compression_combo)

        self.heic_checkbox = QCheckBox("Create HEIC (lossy)")
        self.heic_checkbox.setChecked(DEFAULT_OPTIONS["create_heic"])
        self.heic_checkbox.setEnabled(HEIF_SAVE_AVAILABLE)
        format_form.addRow(self.heic_checkbox)
        self.heic_quality_spin = QSpinBox()
        self.heic_quality_spin.setRange(0, 100)
        self.heic_quality_spin.setValue(DEFAULT_OPTIONS["heic_quality"])
        format_form.addRow("HEIC quality", self.heic_quality_spin)

        self.jpg_checkbox = QCheckBox("Create JPEG (lossy)")
        self.jpg_checkbox.setChecked(DEFAULT_OPTIONS["create_jpg"])
        format_form.addRow(self.jpg_checkbox)
        self.jpg_quality_spin = QSpinBox()
        self.jpg_quality_spin.setRange(0, 100)
        self.jpg_quality_spin.setValue(DEFAULT_OPTIONS["jpg_quality"])
        format_form.addRow("JPEG quality", self.jpg_quality_spin)
        option_columns.addWidget(format_widget, 1)

        fastfoto_widget = QWidget()
        fastfoto_form = QFormLayout(fastfoto_widget)
        self.fastfoto_checkbox = QCheckBox("Enable FastFoto variant selection")
        self.fastfoto_checkbox.setChecked(DEFAULT_OPTIONS["variant_policy"] != "none")
        fastfoto_form.addRow(self.fastfoto_checkbox)

        self.variant_policy_combo = QComboBox()
        self.variant_policy_combo.addItem("Smart quality score", "smart")
        self.variant_policy_combo.addItem("Prefer base scan", "base")
        self.variant_policy_combo.addItem("Prefer augmented (_a)", "augment")
        self.variant_policy_combo.setCurrentIndex(
            self.variant_policy_combo.findData(DEFAULT_OPTIONS["variant_policy"])
        )
        fastfoto_form.addRow("Front selection", self.variant_policy_combo)

        self.archive_checkbox = QCheckBox(
            "Put non-selected lossless copies in lossless_compressed/archive/"
        )
        self.archive_checkbox.setChecked(DEFAULT_OPTIONS["variant_smart_archiving"])
        fastfoto_form.addRow(self.archive_checkbox)

        self.smart_conversion_checkbox = QCheckBox(
            "Create HEIC/JPEG only for selected fronts (and all backs)"
        )
        self.smart_conversion_checkbox.setChecked(
            DEFAULT_OPTIONS["variant_smart_conversion"]
        )
        fastfoto_form.addRow(self.smart_conversion_checkbox)
        option_columns.addWidget(fastfoto_widget, 1)
        layout.addLayout(option_columns)

        if not HEIF_SAVE_AVAILABLE:
            heif_note = QLabel("HEIC unavailable: install the pillow-heif extra.")
            heif_note.setStyleSheet("color: gray;")
            layout.addWidget(heif_note)

        self.dry_run_checkbox = QCheckBox("Preview only")
        self.dry_run_checkbox.setChecked(DEFAULT_OPTIONS["dry_run"])
        self.safety_label = QLabel(
            "Shows and validates planned outputs; no files are written or moved."
        )
        self.safety_label.setWordWrap(True)
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
        self.result_table = QTableWidget(0, 5)
        self.result_table.setHorizontalHeaderLabels(
            ["Source", "Action", "Output", "Status", "Size"]
        )
        self.result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.result_table.setColumnWidth(1, 120)
        self.result_table.setColumnWidth(3, 160)
        layout.addWidget(self.result_table, 2)

        layout.addWidget(QLabel("Activity log"))
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2_000)
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

        self.source_edit.textChanged.connect(self._update_run_enabled)
        self.browse_button.clicked.connect(self._browse)
        self.heic_checkbox.toggled.connect(self._update_conditional_controls)
        self.jpg_checkbox.toggled.connect(self._update_conditional_controls)
        self.fastfoto_checkbox.toggled.connect(self._update_conditional_controls)
        self.dry_run_checkbox.toggled.connect(self._update_mode_copy)
        self.run_button.clicked.connect(self._start)
        self.cancel_button.clicked.connect(self._cancel)
        self._update_conditional_controls()

    def _browse(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Choose TIFF source folder", self.source_edit.text()
        )
        if selected:
            self.source_edit.setText(selected)

    def _update_conditional_controls(self) -> None:
        fastfoto = self.fastfoto_checkbox.isChecked()
        lossy = self.heic_checkbox.isChecked() or self.jpg_checkbox.isChecked()
        self.heic_quality_spin.setEnabled(self.heic_checkbox.isChecked())
        self.jpg_quality_spin.setEnabled(self.jpg_checkbox.isChecked())
        self.variant_policy_combo.setEnabled(fastfoto)
        self.archive_checkbox.setEnabled(fastfoto)
        self.smart_conversion_checkbox.setEnabled(fastfoto and lossy)

    def build_options(self) -> dict:
        """Return exactly the engine options represented by this panel."""
        return {
            "dry_run": self.dry_run_checkbox.isChecked(),
            "compression": self.compression_combo.currentData(),
            "create_heic": self.heic_checkbox.isChecked(),
            "heic_quality": self.heic_quality_spin.value(),
            "create_jpg": self.jpg_checkbox.isChecked(),
            "jpg_quality": self.jpg_quality_spin.value(),
            "variant_policy": (
                self.variant_policy_combo.currentData()
                if self.fastfoto_checkbox.isChecked()
                else "none"
            ),
            "variant_smart_archiving": self.archive_checkbox.isChecked(),
            "variant_smart_conversion": self.smart_conversion_checkbox.isChecked(),
        }

    def _update_run_enabled(self) -> None:
        source = Path(self.source_edit.text()).expanduser()
        self.run_button.setEnabled(self._worker is None and source.is_dir())

    def _update_mode_copy(self, dry_run: bool) -> None:
        if dry_run:
            self.safety_label.setText(
                "Shows and validates planned outputs; no files are written or moved."
            )
            self.run_button.setText("Preview")
        else:
            self.safety_label.setText(
                "Live mode — writes requested derivatives, verifies lossless TIFFs, "
                "then moves originals. Conflicts are skipped; completed work is not "
                "rolled back on cancellation."
            )
            self.run_button.setText("Convert TIFFs")

    def _start(self) -> None:
        if not self.run_button.isEnabled():
            return
        options = self.build_options()
        if not options["dry_run"]:
            formats = ["lossless TIFF"]
            if options["create_heic"]:
                formats.append("lossy HEIC")
            if options["create_jpg"]:
                formats.append("lossy JPEG")
            answer = QMessageBox.question(
                self,
                "Confirm live TIFF conversion",
                "Convert root-level .tif/.tiff files now?\n\n"
                f"Outputs: {', '.join(formats)}\n"
                "Successful originals move to originals/. Existing outputs are "
                "never overwritten, and completed work is not rolled back if cancelled.",
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
            "Previewing…" if options["dry_run"] else "Converting…"
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

    def _on_result(self, result: ConversionRunResult) -> None:
        details = [detail for group in result.groups for detail in group.details]
        self.result_table.setRowCount(len(details))
        for row, detail in enumerate(details):
            if detail.status == "failed":
                status = f"Failed: {detail.error}" if detail.error else "Failed"
            elif detail.status.startswith("skipped_"):
                status = _STATUS_LABELS.get(detail.status, "Skipped")
                if detail.error:
                    status += f": {detail.error}"
            else:
                status = _STATUS_LABELS.get(detail.status, detail.status)
            size = f"{detail.size_bytes / 1_048_576:.1f} MB" if detail.size_bytes else ""
            self.result_table.setItem(row, 0, QTableWidgetItem(detail.source))
            self.result_table.setItem(row, 1, QTableWidgetItem(detail.action))
            self.result_table.setItem(row, 2, QTableWidgetItem(detail.output))
            self.result_table.setItem(row, 3, QTableWidgetItem(status))
            self.result_table.setItem(row, 4, QTableWidgetItem(size))

        if result.cancelled:
            self._on_cancelled()
        if self._terminal_state != "cancelled":
            self._terminal_state = "completed"
            successful = sum(1 for group in result.groups if group.success)
            planned = sum(1 for detail in details if detail.status == "planned")
            written = sum(1 for detail in details if detail.status == "written")
            moved = sum(1 for detail in details if detail.status == "moved")
            skipped = sum(1 for detail in details if detail.status.startswith("skipped_"))
            failed = sum(1 for detail in details if detail.status == "failed")
            self.status_label.setText(
                f"Complete — {successful}/{len(result.groups)} groups; "
                f"{planned} planned, {written} written, {moved} moved, "
                f"{skipped} skipped, {failed} failed"
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
        for widget in (
            self.source_edit,
            self.browse_button,
            self.compression_combo,
            self.heic_checkbox,
            self.jpg_checkbox,
            self.fastfoto_checkbox,
            self.dry_run_checkbox,
        ):
            widget.setEnabled(enabled)
        if enabled:
            self.heic_checkbox.setEnabled(HEIF_SAVE_AVAILABLE)
            self._update_conditional_controls()
        else:
            self.heic_quality_spin.setEnabled(False)
            self.jpg_quality_spin.setEnabled(False)
            self.variant_policy_combo.setEnabled(False)
            self.archive_checkbox.setEnabled(False)
            self.smart_conversion_checkbox.setEnabled(False)
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(not enabled)
