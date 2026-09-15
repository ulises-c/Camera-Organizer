"""Main application window (PySide6).

Replaces the old subprocess-launching tkinter `launcher.py`. One window, a tool
list on the left, and a panel area on the right. Tool panels are migrated one at
a time; completed panels run engines through `EngineWorker`, while unfinished
tools keep an explicit stub.

Each real panel:
  1. takes a source folder,
  2. builds the options dict,
  3. spawns an EngineWorker(engine, source, options),
  4. wires progress/message/result signals to widgets.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from photo_organizer.engine import TOOLS, ToolSpec
from photo_organizer.gui.panels.batch_renamer import BatchRenamerPanel
from photo_organizer.gui.panels.folder_renamer import FolderRenamerPanel
from photo_organizer.gui.panels.organizer import OrganizerPanel
from photo_organizer.gui.panels.tiff_converter import TiffConverterPanel
from photo_organizer.gui.panels.video_converter import VideoConverterPanel


class StubPanel(QFrame):
    """Placeholder panel for a tool whose GUI is not built yet."""

    def __init__(self, spec: ToolSpec, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)

        title = QLabel(spec.name)
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        desc = QLabel(spec.description)
        desc.setStyleSheet("color: gray;")
        engine = QLabel(f"engine: {spec.engine_path}")
        engine.setStyleSheet("font-family: monospace; color: gray; font-size: 11px;")
        note = QLabel(
            "GUI panel not built yet. The engine is complete and runnable via CLI "
            "or the EngineWorker. This panel will host the source picker, options, "
            "progress bar, log view, and a Cancel button."
        )
        note.setWordWrap(True)

        for w in (title, desc, engine, note):
            layout.addWidget(w)
        layout.addStretch(1)


def make_panel(spec: ToolSpec) -> QWidget:
    """Build a migrated panel when available, otherwise an explicit stub."""
    if spec.key == "organizer":
        return OrganizerPanel()
    if spec.key == "tiff_converter":
        return TiffConverterPanel()
    if spec.key == "video_converter":
        return VideoConverterPanel()
    if spec.key == "folder_renamer":
        return FolderRenamerPanel()
    if spec.key == "batch_renamer":
        return BatchRenamerPanel()
    return StubPanel(spec)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Camera Organizer")
        self.resize(880, 600)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)

        # Left: tool list.
        self.tool_list = QListWidget()
        self.tool_list.setMaximumWidth(230)
        for spec in TOOLS:
            item = QListWidgetItem(spec.name)
            item.setData(Qt.UserRole, spec.key)
            self.tool_list.addItem(item)
        root.addWidget(self.tool_list)

        # Right: stacked panels (one per tool).
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        for spec in TOOLS:
            self.stack.addWidget(make_panel(spec))

        self.tool_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.tool_list.setCurrentRow(0)

    def closeEvent(self, event):
        """Cancel and join any in-flight panel workers before the window dies.

        Destroying a panel-owned QThread mid-encode raises 'QThread: Destroyed
        while thread is still running'. Each panel keeps its worker on `_worker`
        (None when idle); request cooperative cancellation, then wait for the
        thread to unwind so no encode is publishing as we tear down.
        """
        for index in range(self.stack.count()):
            panel = self.stack.widget(index)
            worker = getattr(panel, "_worker", None)
            if worker is not None and worker.isRunning():
                worker.cancel()
                worker.wait()
        super().closeEvent(event)


def run() -> int:
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()
