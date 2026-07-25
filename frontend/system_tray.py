"""System tray icon with show/hide/quit context menu."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget


def create_app_icon() -> QIcon:
    """Generate the app icon programmatically (accent circle with 'O')."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(124, 58, 237))
    painter.setPen(QColor(124, 58, 237))
    painter.drawEllipse(4, 4, 56, 56)
    painter.setPen(QColor(255, 255, 255))
    font = QFont("Segoe UI", 28, QFont.Weight.Bold)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "O")
    painter.end()
    return QIcon(pixmap)


class SystemTrayManager:
    """Owns the system tray icon and provides show/hide/quit menu."""

    def __init__(self, parent: QWidget | None = None) -> None:
        self._parent = parent
        self._tray_icon: QSystemTrayIcon | None = None
        self._show_action: QAction | None = None
        self._setup_tray()

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self._tray_icon = QSystemTrayIcon()
        self._tray_icon.setIcon(create_app_icon())
        self._tray_icon.setToolTip("OpportunityOS")

        menu = QMenu()
        self._show_action = QAction("Hide")
        self._show_action.triggered.connect(self._toggle_visibility)
        menu.addAction(self._show_action)
        menu.addSeparator()
        quit_action = QAction("Quit")
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(quit_action)

        self._tray_icon.setContextMenu(menu)
        self._tray_icon.activated.connect(self._on_activated)
        self._tray_icon.show()

    @property
    def tray_icon(self) -> QSystemTrayIcon | None:
        return self._tray_icon

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_visibility()

    def _toggle_visibility(self) -> None:
        if self._parent is None:
            return
        if self._parent.isVisible():
            self._parent.hide()
            self._update_menu_text()
        else:
            self._parent.show()
            self._parent.raise_()
            self._parent.activateWindow()
            self._update_menu_text()

    def set_parent(self, parent: QWidget) -> None:
        self._parent = parent

    def _update_menu_text(self) -> None:
        if self._show_action and self._parent:
            self._show_action.setText("Hide" if self._parent.isVisible() else "Show")

    def _on_quit(self) -> None:
        if self._parent and hasattr(self._parent, "quit_application"):
            self._parent.quit_application()
        else:
            app = QApplication.instance()
            if app:
                app.quit()

    def show_message(self, title: str, message: str, timeout: int = 5000) -> None:
        if self._tray_icon and self._tray_icon.isVisible():
            self._tray_icon.showMessage(title, message, timeout=timeout)
