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
    """Sidebar with collapsible navigation for reduced cognitive load."""

    navigation_changed = Signal(int)

    # Restructured nav with category grouping
    # Format: (icon, label, page_index, category)
    NAV_ITEMS: list[tuple[str, str, int, str]] = [
        ("\u25A3", "Home", 0, "main"),          # Dashboard (index 0)
        ("\u2609", "Discover", 2, "main"),      # Search (index 2)
        ("\u2605", "Saved", 4, "main"),         # Bookmarks (index 4)
        ("\u25C9", "Profile", 1, "advanced"),   # Profile (index 1)
        ("\u2699", "Settings", 6, "advanced"),  # Settings (index 6)
        ("\u2630", "Logs", 7, "advanced"),      # Logs (index 7)
    ]

    # Page index mapping for backward compatibility
    PAGE_INDICES = {
        "Dashboard": 0,
        "Profile": 1,
        "Search": 2,
        "Opportunities": 3,
        "Bookmarks": 4,
        "Notifications": 5,
        "Settings": 6,
        "Logs": 7,
    }

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

        # Build main navigation items
        for icon, label, page_idx, category in self.NAV_ITEMS:
            if category == "main":
                btn = SidebarButton(icon, label)
                btn.clicked.connect(lambda checked=False, i=page_idx: self._on_nav_clicked(i))
                self._buttons.append(btn)
                nav_layout.addWidget(btn)
        
        # Add spacer before advanced section
        nav_layout.addSpacing(12)
        
        # Add advanced section header
        advanced_header = QLabel("Advanced")
        advanced_header.setStyleSheet(f"""
            QLabel {{
                font-size: 10px;
                font-weight: 600;
                color: {TEXT_MUTED};
                padding: 8px 16px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                background-color: transparent;
            }}
        """)
        nav_layout.addWidget(advanced_header)
        
        # Add advanced navigation items
        for icon, label, page_idx, category in self.NAV_ITEMS:
            if category == "advanced":
                btn = SidebarButton(icon, label)
                btn.clicked.connect(lambda checked=False, i=page_idx: self._on_nav_clicked(i))
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

    def _on_nav_clicked(self, page_index: int) -> None:
        """Handle navigation button click with proper page index."""
        self._select_by_page_index(page_index)
        self.navigation_changed.emit(page_index)
    
    def _select_by_page_index(self, page_index: int) -> None:
        """Select button by page index, handling the new navigation structure."""
        # Find which button corresponds to this page index
        for btn_idx, btn in enumerate(self._buttons):
            # Map button to page based on NAV_ITEMS
            nav_item = None
            for item in self.NAV_ITEMS:
                if item[2] == page_index:  # item[2] is the page_index
                    nav_item = item
                    break
            
            is_this_button = False
            for nav_item in self.NAV_ITEMS:
                if nav_item[2] == page_index and nav_item[1] == btn.text().strip().split()[-1]:
                    is_this_button = True
                    break
            
            btn.setChecked(is_this_button)

    def _select(self, index: int) -> None:
        for i, btn in enumerate(self._buttons):
            btn.setChecked(i == index)
