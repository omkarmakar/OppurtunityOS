"""PySide6 GUI application entry point with system tray integration.

Ensures the backend is running before constructing the main window, and
cleans up the backend process on quit.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from frontend.backend_manager import BackendManager
from frontend.system_tray import SystemTrayManager, create_app_icon
from frontend.utils.startup import register as register_startup
from frontend.windows.main_window import MainWindow

_BACKEND_MANAGER: BackendManager | None = None


def _get_backend_manager() -> BackendManager:
    global _BACKEND_MANAGER
    if _BACKEND_MANAGER is None:
        _BACKEND_MANAGER = BackendManager()
    return _BACKEND_MANAGER


def _show_splash(parent: QApplication) -> QDialog:
    """Display a simple blocking splash dialog while the backend starts."""
    dialog = QDialog()
    dialog.setWindowTitle("Starting OpportunityOS...")
    dialog.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
    dialog.setFixedSize(380, 140)
    dialog.setStyleSheet("""
        QDialog {
            background-color: #1a1a2e;
            border: 1px solid #7c3aed;
            border-radius: 8px;
        }
    """)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(12)

    title = QLabel("Starting OpportunityOS...")
    title.setStyleSheet("color: #e0e0e0; font-size: 18px; font-weight: bold;")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)

    message = QLabel("Waiting for the backend server to become ready")
    message.setStyleSheet("color: #a0a0a0; font-size: 12px;")
    message.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(message)

    progress = QProgressBar()
    progress.setRange(0, 0)
    progress.setFixedHeight(6)
    progress.setStyleSheet("""
        QProgressBar {
            background-color: #2a2a3e;
            border: none;
            border-radius: 3px;
        }
        QProgressBar::chunk {
            background-color: #7c3aed;
            border-radius: 3px;
        }
    """)
    layout.addWidget(progress)

    # Centre the dialog on screen
    screen = parent.primaryScreen()
    if screen:
        geo = screen.availableGeometry()
        x = (geo.width() - dialog.width()) // 2
        y = (geo.height() - dialog.height()) // 2
        dialog.move(x, y)

    dialog.show()
    parent.processEvents()
    return dialog


def _show_startup_error(log_path: str) -> None:
    """Show an error dialog when the backend fails to start."""
    dialog = QDialog()
    dialog.setWindowTitle("Backend Startup Failed")
    dialog.setFixedSize(480, 240)
    dialog.setStyleSheet("""
        QDialog {
            background-color: #1a1a2e;
            border: 1px solid #dc2626;
            border-radius: 8px;
        }
    """)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(12)

    title = QLabel("Could not start the backend server")
    title.setStyleSheet("color: #fca5a5; font-size: 16px; font-weight: bold;")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)

    msg = QLabel(
        "The backend process did not start within the time limit. "
        "The application will continue but API calls will fail.\n\n"
        "Check the log file for details:\n"
        f"{log_path}"
    )
    msg.setWordWrap(True)
    msg.setStyleSheet("color: #c0c0c0; font-size: 12px;")
    layout.addWidget(msg)

    btn_layout = QHBoxLayout()
    btn_layout.addStretch()
    ok_btn = QPushButton("Continue")
    ok_btn.setStyleSheet("""
        QPushButton {
            background-color: #7c3aed; color: white;
            padding: 8px 24px; border: none; border-radius: 4px;
        }
        QPushButton:hover { background-color: #6d28d9; }
    """)
    ok_btn.clicked.connect(dialog.accept)
    btn_layout.addWidget(ok_btn)
    layout.addLayout(btn_layout)

    dialog.exec()


def main() -> None:
    """Initialize the backend, then launch the GUI."""
    app = QApplication(sys.argv)
    app.setApplicationName("OpportunityOS")
    app.setApplicationVersion("0.1.0")
    app.setWindowIcon(create_app_icon())
    app.setQuitOnLastWindowClosed(False)

    # Show splash and ensure backend is running
    splash = _show_splash(app)
    manager = _get_backend_manager()
    backend_ok = manager.ensure_backend_running()
    splash.close()

    if not backend_ok:
        from pathlib import Path
        from core.config import get_config
        cfg = get_config()
        log_path = str(Path(cfg.paths.log_dir) / "backend.log")
        _show_startup_error(log_path)

    # Build the main window (this was the original startup code)
    window = MainWindow()
    tray = SystemTrayManager(window)
    window._tray_manager = tray

    # Register for Windows startup (idempotent, safe on non-Windows)
    register_startup()

    window.show()

    exit_code = app.exec()

    # Shutdown: stop the backend if we started it
    manager.stop_backend()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
