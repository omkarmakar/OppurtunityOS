"""Main application window with sidebar and page navigation."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QStatusBar, QWidget

from core.config import get_config
from frontend.pages.bookmarks import BookmarksPage
from frontend.pages.dashboard import DashboardPage
from frontend.pages.logs import LogsPage
from frontend.pages.notifications import NotificationsPage
from frontend.pages.opportunities import OpportunitiesPage
from frontend.pages.profile import ProfilePage
from frontend.pages.search import SearchPage
from frontend.pages.settings import SettingsPage
from frontend.theme import BG_APP, get_stylesheet
from frontend.widgets.sidebar import Sidebar
from services.background import create_and_start_scheduler


class MainWindow(QMainWindow):
    """Primary application window with sidebar navigation."""

    PAGE_LABELS: list[str] = [
        "Dashboard",
        "Profile",
        "Search",
        "Opportunities",
        "Bookmarks",
        "Notifications",
        "Settings",
        "Logs",
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pages: list[QWidget] = []
        self._scheduler = None
        self._force_close = False
        self._tray_manager = None
        self._setup_ui()
        self._start_background_tasks()

    def _setup_ui(self) -> None:
        self.setWindowTitle("OpportunityOS")
        self.setMinimumSize(QSize(1024, 768))
        self.resize(1280, 800)

        self.setStyleSheet(get_stylesheet())

        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = Sidebar()
        sidebar.navigation_changed.connect(self._navigate)
        layout.addWidget(sidebar)

        self._stack = QStackedWidget()
        self._stack.setObjectName("pageStack")
        self._stack.setStyleSheet(f"""
            QStackedWidget#pageStack {{
                background-color: {BG_APP};
            }}
        """)
        layout.addWidget(self._stack, 1)

        self._pages = [
            DashboardPage(),
            ProfilePage(),
            SearchPage(),
            OpportunitiesPage(),
            BookmarksPage(),
            NotificationsPage(),
            SettingsPage(),
            LogsPage(),
        ]

        for page in self._pages:
            self._stack.addWidget(page)

        status = QStatusBar(self)
        status.showMessage("Ready")
        self.setStatusBar(status)

    def _start_background_tasks(self) -> None:
        try:
            cfg = get_config()
            self._scheduler = create_and_start_scheduler(cfg)
        except Exception as exc:
            self.statusBar().showMessage(f"Scheduler: {exc}")

    def closeEvent(self, event) -> None:
        if self._scheduler:
            self._scheduler.stop()
        if self._force_close:
            super().closeEvent(event)
        else:
            event.ignore()
            self.hide()
            if self._tray_manager:
                self._tray_manager._update_menu_text()

    def quit_application(self) -> None:
        """Force-close the window and exit the process."""
        self._force_close = True
        self.close()

    def _navigate(self, index: int) -> None:
        if 0 <= index < self._stack.count():
            self._stack.setCurrentIndex(index)
            label = self.PAGE_LABELS[index] if index < len(self.PAGE_LABELS) else ""
            self.statusBar().showMessage(f"Navigated to {label}")
