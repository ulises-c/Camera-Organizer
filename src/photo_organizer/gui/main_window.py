"""Main application window (PySide6).

Replaces the old subprocess-launching tkinter `launcher.py`. One window, a tool
list on the left, and a panel area on the right. Because the GUI is intentionally
deferred, each tool currently shows a *stub* panel that documents its engine and
options; the engines themselves are complete and callable (CLI / tests).

When a panel is built for real, it will:
  1. take a source folder,
  2. build the options dict,
  3. spawn an EngineWorker(spec.load_engine(), source, options),
  4. wire progress/message/finished to widgets.
The plumbing (worker, registry, engines) is already in place.
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
        self.tool_list.setMaximumWidth(260)
        for spec in TOOLS:
            item = QListWidgetItem(spec.name)
            item.setData(Qt.UserRole, spec.key)
            self.tool_list.addItem(item)
        root.addWidget(self.tool_list)

        # Right: stacked panels (one per tool).
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        for spec in TOOLS:
            self.stack.addWidget(StubPanel(spec))

        self.tool_list.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.tool_list.setCurrentRow(0)


def run() -> int:
    import sys
    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec()
