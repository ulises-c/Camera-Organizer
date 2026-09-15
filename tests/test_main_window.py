"""Tests for the PySide6 application shell."""
from __future__ import annotations

from photo_organizer.engine import TOOLS
from photo_organizer.gui.main_window import MainWindow
from photo_organizer.gui.panels.batch_renamer import BatchRenamerPanel
from photo_organizer.gui.panels.folder_renamer import FolderRenamerPanel
from photo_organizer.gui.panels.organizer import OrganizerPanel


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
