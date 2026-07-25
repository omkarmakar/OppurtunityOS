"""Sidebar navigation widget."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from frontend.theme import (
    ACCENT_LIGHT,
    BG_SURFACE,
    BORDER_SUBTLE,
    FONT_FAMILY,
    SIDEBAR_ACTIVE_BG,
    SIDEBAR_ACTIVE_BORDER,
    SIDEBAR_HOVER_BG,
    TEXT_MUTED,
    TEXT_SECONDARY,
)


class SidebarButton(QPushButton):
    """A styled sidebar navigation button."""

    def __init__(self, icon: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setText(f"  {icon}  {text}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCheckable(True)
        self.setMinimumHeight(42)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding: 10px 16px 10px 14px;
                border: none;
                border-radius: 8px;
                font-family: {FONT_FAMILY};
                font-size: 13px;
                font-weight: 500;
                color: {TEXT_SECONDARY};
                background-color: transparent;
                margin: 1px 10px;
            }}
            QPushButton:hover {{
                background-color: {SIDEBAR_HOVER_BG};
                color: #c8c8e0;
            }}
            QPushButton:checked {{
                background-color: {SIDEBAR_ACTIVE_BG};
                color: {ACCENT_LIGHT};
                font-weight: 600;
                border-left: 3px solid {SIDEBAR_ACTIVE_BORDER};
                padding-left: 11px;
            }}
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
        self.setFixedWidth(232)
        self.setObjectName("sidebar")
        self.setStyleSheet(f"""
            QWidget#sidebar {{
                background-color: {BG_SURFACE};
                border-right: 1px solid {BORDER_SUBTLE};
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        brand_wrap = QWidget()
        brand_wrap.setObjectName("brandWrap")
        brand_wrap.setStyleSheet("QWidget#brandWrap { background: transparent; }")
        brand_layout = QVBoxLayout(brand_wrap)
        brand_layout.setContentsMargins(20, 28, 20, 20)
        brand_layout.setSpacing(2)

        brand = QLabel("OpportunityOS")
        brand.setStyleSheet(f"""
            QLabel {{
                font-size: 17px;
                font-weight: 700;
                color: {ACCENT_LIGHT};
                background-color: transparent;
                letter-spacing: -0.2px;
            }}
        """)
        brand_layout.addWidget(brand)

        tagline = QLabel("Discover & track")
        tagline.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                font-weight: 500;
                color: {TEXT_MUTED};
                background-color: transparent;
                padding-left: 1px;
            }}
        """)
        brand_layout.addWidget(tagline)
        layout.addWidget(brand_wrap)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"QFrame {{ color: {BORDER_SUBTLE}; max-height: 1px; margin: 0 16px; }}")
        layout.addWidget(separator)
        layout.addSpacing(10)

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
        version.setStyleSheet(f"""
            QLabel {{
                font-size: 11px;
                color: {TEXT_MUTED};
                padding: 14px;
                background-color: transparent;
            }}
        """)
        layout.addWidget(version)

    def _on_nav_clicked(self, index: int) -> None:
        self._select(index)
        self.navigation_changed.emit(index)

    def _select(self, index: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)
