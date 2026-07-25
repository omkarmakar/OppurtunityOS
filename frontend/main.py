"""PySide6 GUI application entry point with system tray integration."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from frontend.system_tray import SystemTrayManager, create_app_icon
from frontend.utils.startup import register as register_startup
from frontend.windows.main_window import MainWindow


def main() -> None:
    """Initialize and run the GUI application."""
    app = QApplication(sys.argv)
    app.setApplicationName("OpportunityOS")
    app.setApplicationVersion("0.1.0")
    app.setWindowIcon(create_app_icon())
    app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    tray = SystemTrayManager(window)
    window._tray_manager = tray

    # Register for Windows startup (idempotent, safe on non-Windows)
    register_startup()

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
