"""Sidebar navigation widget."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget


class SidebarButton(QPushButton):
    """A styled sidebar navigation button."""

    def __init__(self, icon: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setText(f"  {icon}  {text}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setMinimumHeight(44)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("""
            QPushButton {
                text-align: left;
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                color: #8888bb;
                background-color: transparent;
                margin: 2px 8px;
            }
            QPushButton:hover {
                background-color: #1e1e38;
                color: #c0c0e0;
            }
            QPushButton:checked {
                background-color: #2e1065;
                color: #a78bfa;
                font-weight: 600;
            }
        """)


class Sidebar(QWidget):
    """Sidebar with navigation buttons for each page."""

    navigation_changed = Signal(int)

    NAV_ITEMS: list[tuple[str, str]] = [
        ("\u25A3", "Dashboard"),
        ("\u25C9", "Profile"),
        ("\u2609", "Search"),
        ("\u2605", "Opportunities"),
        ("\u2666", "Bookmarks"),
        ("\u25C6", "Notifications"),
        ("\u2699", "Settings"),
        ("\u2630", "Logs"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._buttons: list[SidebarButton] = []
        self._setup_ui()
        self._select(0)

    def _setup_ui(self) -> None:
        self.setFixedWidth(220)
        self.setObjectName("sidebar")
        self.setStyleSheet("""
            QWidget#sidebar {
                background-color: #12121e;
                border-right: 1px solid #2a2a44;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        brand = QLabel("  \u25A0  OOS")
        brand.setStyleSheet("""
            QLabel {
                font-size: 20px;
                font-weight: 700;
                color: #a78bfa;
                padding: 24px 20px 20px 20px;
                background-color: transparent;
            }
        """)
        layout.addWidget(brand)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("QFrame { color: #2a2a44; max-height: 1px; margin: 0 16px; }")
        layout.addWidget(separator)
        layout.addSpacing(12)

        nav_container = QWidget()
        nav_container.setObjectName("navContainer")
        nav_container.setStyleSheet("QWidget#navContainer { background-color: transparent; }")
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(2)

        for idx, (icon, label) in enumerate(self.NAV_ITEMS):
            btn = SidebarButton(icon, label)
            btn.clicked.connect(lambda checked=False, i=idx: self._on_nav_clicked(i))
            self._buttons.append(btn)
            nav_layout.addWidget(btn)

        nav_layout.addStretch(1)
        layout.addWidget(nav_container, 1)

        version = QLabel("v0.3.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #555577;
                padding: 12px;
                background-color: transparent;
            }
        """)
        layout.addWidget(version)

    def _on_nav_clicked(self, index: int) -> None:
        self._select(index)
        self.navigation_changed.emit(index)

    def _select(self, index: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)
