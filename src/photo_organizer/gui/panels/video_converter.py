"""Video Converter panel (Log→Rec709 + 1080p HEVC share encode)."""
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

from photo_organizer.gui.worker import EngineWorker
from photo_organizer.video_converter.engine import (
    DEFAULT_OPTIONS,
    ffmpeg_available,
    process_video_folder,
)
from photo_organizer.video_converter.luts import catalog

_AUTO_LUT = "Auto (detect per clip)"


class VideoConverterPanel(QWidget):
    """Collect video-converter options and display per-clip engine results."""

    def __init__(self, engine: Callable[..., Any] = process_video_folder, parent=None):
        super().__init__(parent)
        self._engine = engine
        self._worker: EngineWorker | None = None
        self._terminal_state: str | None = None

        layout = QVBoxLayout(self)
        title = QLabel("🎬 Video Converter")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(
            QLabel("S-Log3 → Rec709 (LUT) masters, then 1080p HEVC share encodes.")
        )

        form = QFormLayout()
        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Choose the footage folder…")
        self.browse_button = QPushButton("Browse…")
        source_row = QWidget()
        source_layout = QHBoxLayout(source_row)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.addWidget(self.source_edit, 1)
        source_layout.addWidget(self.browse_button)
        form.addRow("Footage folder", source_row)

        self.lut_combo = QComboBox()
        self.lut_combo.addItem(_AUTO_LUT, None)
        for lut_path in catalog():
            self.lut_combo.addItem(lut_path.stem, str(lut_path))
        form.addRow("LUT", self.lut_combo)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(240, 4320)
        self.height_spin.setSingleStep(120)
        self.height_spin.setValue(DEFAULT_OPTIONS["share_height"])
        form.addRow("Share height (px)", self.height_spin)

        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        self.crf_spin.setValue(DEFAULT_OPTIONS["x265_crf"])
        form.addRow("x265 CRF", self.crf_spin)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(
            ["ultrafast", "superfast", "veryfast", "faster", "fast",
             "medium", "slow", "slower", "veryslow"]
        )
        self.preset_combo.setCurrentText(DEFAULT_OPTIONS["x265_preset"])
        form.addRow("x265 preset", self.preset_combo)
        layout.addLayout(form)

        self.stage1_checkbox = QCheckBox("Stage 1 — colorspace (Log→Rec709 ProRes master)")
        self.stage1_checkbox.setChecked(DEFAULT_OPTIONS["do_stage1"])
        self.stage2_checkbox = QCheckBox("Stage 2 — compress to share HEVC")
        self.stage2_checkbox.setChecked(DEFAULT_OPTIONS["do_stage2"])
        layout.addWidget(self.stage1_checkbox)
        layout.addWidget(self.stage2_checkbox)

        self.dry_run_checkbox = QCheckBox("Preview only")
        self.dry_run_checkbox.setChecked(DEFAULT_OPTIONS["dry_run"])
        self.safety_label = QLabel("Shows the planned encode; no files are written.")
        layout.addWidget(self.dry_run_checkbox)
        layout.addWidget(self.safety_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Choose a footage folder to preview.")
        layout.addWidget(self.status_label)

        layout.addWidget(QLabel("Results"))
        self.result_table = QTableWidget(0, 4)
        self.result_table.setHorizontalHeaderLabels(["Clip", "Stage", "Output", "Result"])
        self.result_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.result_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.result_table.setColumnWidth(1, 130)
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
        self.dry_run_checkbox.toggled.connect(self._update_mode_copy)
        self.run_button.clicked.connect(self._start)
        self.cancel_button.clicked.connect(self._cancel)

    def _browse(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self, "Choose footage folder", self.source_edit.text()
        )
        if selected:
            self.source_edit.setText(selected)

    def build_options(self) -> dict:
        """Return the engine options represented by the current controls."""
        return {
            "dry_run": self.dry_run_checkbox.isChecked(),
            "do_stage1": self.stage1_checkbox.isChecked(),
            "do_stage2": self.stage2_checkbox.isChecked(),
            "share_height": self.height_spin.value(),
            "x265_crf": self.crf_spin.value(),
            "x265_preset": self.preset_combo.currentText(),
            "explicit_lut": self.lut_combo.currentData(),
        }

    def _update_run_enabled(self) -> None:
        source = Path(self.source_edit.text()).expanduser()
        self.run_button.setEnabled(self._worker is None and source.is_dir())

    def _update_mode_copy(self, dry_run: bool) -> None:
        if dry_run:
            self.safety_label.setText("Shows the planned encode; no files are written.")
            self.run_button.setText("Preview")
        else:
            self.safety_label.setText(
                "Live mode — encodes into master/share subfolders "
                "(existing outputs are skipped, never overwritten)."
            )
            self.run_button.setText("Convert videos")

    def _start(self) -> None:
        if not self.run_button.isEnabled():
            return
        dry_run = self.dry_run_checkbox.isChecked()
        if not dry_run:
            if not ffmpeg_available():
                QMessageBox.warning(
                    self,
                    "ffmpeg required",
                    "A live conversion needs ffmpeg and ffprobe on PATH.\n"
                    "Install them (e.g. `brew install ffmpeg`) and try again.",
                )
                return
            answer = QMessageBox.question(
                self,
                "Confirm live conversion",
                "Encode the matching clips now? This runs ffmpeg and writes "
                "master/share files.\n\nExisting outputs are skipped, and "
                "cancellation stops after the current clip.",
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
        self.status_label.setText("Previewing…" if dry_run else "Converting…")
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

    def _on_result(self, results: list) -> None:
        dry_run = self.dry_run_checkbox.isChecked()
        rows = [(r, d) for r in results for d in r.details]
        self.result_table.setRowCount(len(rows))
        for row, (clip, det) in enumerate(rows):
            if not det.success:
                state = f"Failed: {det.error}" if det.error else "Failed"
            elif dry_run:
                state = "Planned"
            else:
                state = "Done"
            self.result_table.setItem(row, 0, QTableWidgetItem(clip.source_stem))
            self.result_table.setItem(row, 1, QTableWidgetItem(det.action))
            self.result_table.setItem(row, 2, QTableWidgetItem(det.output))
            self.result_table.setItem(row, 3, QTableWidgetItem(state))

        if self._terminal_state != "cancelled":
            self._terminal_state = "completed"
            ok = sum(1 for r in results if r.success)
            verb = "planned" if dry_run else "converted"
            self.status_label.setText(
                f"Complete — {ok}/{len(results)} clips {verb}"
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
            self.lut_combo,
            self.height_spin,
            self.crf_spin,
            self.preset_combo,
            self.stage1_checkbox,
            self.stage2_checkbox,
            self.dry_run_checkbox,
        ):
            widget.setEnabled(enabled)
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(not enabled)
