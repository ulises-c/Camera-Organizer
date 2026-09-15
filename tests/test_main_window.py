"""Tests for the PySide6 application shell."""
from __future__ import annotations

from photo_organizer.engine import TOOLS
from photo_organizer.gui.main_window import MainWindow
from photo_organizer.gui.panels.batch_renamer import BatchRenamerPanel
from photo_organizer.gui.panels.folder_renamer import FolderRenamerPanel
from photo_organizer.gui.panels.organizer import OrganizerPanel
from photo_organizer.gui.panels.tiff_converter import TiffConverterPanel
from photo_organizer.gui.panels.video_converter import VideoConverterPanel


def test_main_window_uses_real_batch_renamer_panel(qapp):
    window = MainWindow()
    index = next(i for i, spec in enumerate(TOOLS) if spec.key == "batch_renamer")

    assert isinstance(window.stack.widget(index), BatchRenamerPanel)


def test_main_window_uses_real_folder_renamer_panel(qapp):
    window = MainWindow()
    index = next(i for i, spec in enumerate(TOOLS) if spec.key == "folder_renamer")

    assert isinstance(window.stack.widget(index), FolderRenamerPanel)


def test_main_window_uses_real_organizer_panel(qapp):
    window = MainWindow()
    index = next(i for i, spec in enumerate(TOOLS) if spec.key == "organizer")

    assert isinstance(window.stack.widget(index), OrganizerPanel)


def test_main_window_uses_real_video_converter_panel(qapp):
    window = MainWindow()
    index = next(i for i, spec in enumerate(TOOLS) if spec.key == "video_converter")

    assert isinstance(window.stack.widget(index), VideoConverterPanel)


def test_main_window_uses_real_tiff_converter_panel(qapp):
    window = MainWindow()
    index = next(i for i, spec in enumerate(TOOLS) if spec.key == "tiff_converter")

    assert isinstance(window.stack.widget(index), TiffConverterPanel)


def test_close_event_cancels_active_workers(qapp):
    import time

    from photo_organizer.converter.engine import ConversionRunResult

    def slow_engine(source, options, progress_callback, log_callback):
        while not options["cancel_event"].is_set():
            time.sleep(0.01)
        return ConversionRunResult(cancelled=True)

    window = MainWindow()
    index = next(i for i, spec in enumerate(TOOLS) if spec.key == "tiff_converter")
    panel = window.stack.widget(index)
    panel._engine = slow_engine
    panel.source_edit.setText(".")
    panel.run_button.click()
    deadline = time.time() + 2.0
    while panel._worker is None and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    assert panel._worker is not None and panel._worker.isRunning()

    window.close()

    assert panel._worker is None or not panel._worker.isRunning()
