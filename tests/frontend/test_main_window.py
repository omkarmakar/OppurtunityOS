"""Main window tests."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStackedWidget
from pytestqt.qtbot import QtBot

from frontend.windows.main_window import MainWindow
from frontend.widgets.sidebar import Sidebar


class TestMainWindow:
    """Test suite for the MainWindow class."""

    def test_window_title(self, qtbot: QtBot) -> None:
        window = MainWindow()
        qtbot.add_widget(window)
        assert window.windowTitle() == "OpportunityOS"

    def test_minimum_size(self, qtbot: QtBot) -> None:
        window = MainWindow()
        qtbot.add_widget(window)
        assert window.minimumWidth() == 1024
        assert window.minimumHeight() == 768

    def test_sidebar_exists(self, qtbot: QtBot) -> None:
        window = MainWindow()
        qtbot.add_widget(window)
        sidebar = window.findChild(Sidebar)
        assert sidebar is not None
        assert sidebar.width() == 220

    def test_eight_pages_in_stack(self, qtbot: QtBot) -> None:
        window = MainWindow()
        qtbot.add_widget(window)
        stack = window.findChild(QStackedWidget)
        assert stack is not None
        assert stack.count() == 8

    def test_navigation_changes_page(self, qtbot: QtBot) -> None:
        window = MainWindow()
        qtbot.add_widget(window)
        stack = window.findChild(QStackedWidget)
        sidebar = window.findChild(Sidebar)
        assert stack.currentIndex() == 0
        sidebar.navigation_changed.emit(3)
        assert stack.currentIndex() == 3

    def test_close_hides_instead_of_closing(self, qtbot: QtBot) -> None:
        window = MainWindow()
        qtbot.add_widget(window)
        window.show()
        assert window.isVisible()
        window.close()
        assert not window.isVisible()

    def test_quit_application_closes(self, qtbot: QtBot) -> None:
        window = MainWindow()
        qtbot.add_widget(window)
        window.show()
        assert window.isVisible()
        window.quit_application()
        assert not window.isVisible()
