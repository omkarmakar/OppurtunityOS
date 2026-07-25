"""Design tokens and global QSS stylesheet for OpportunityOS."""

from __future__ import annotations

# —— Color palette ——
BG_APP = "#0c0c14"
BG_SURFACE = "#12121f"
BG_ELEVATED = "#181828"
BG_CARD = "#1a1a2e"
BG_INPUT = "#222238"
BG_INPUT_HOVER = "#2c2c48"

BORDER_SUBTLE = "#2a2a42"
BORDER_DEFAULT = "#353552"
BORDER_FOCUS = "#7c3aed"

TEXT_PRIMARY = "#e8e8f2"
TEXT_SECONDARY = "#9898b8"
TEXT_MUTED = "#6b6b8a"
TEXT_BRIGHT = "#f4f4fc"

ACCENT = "#7c3aed"
ACCENT_HOVER = "#6d28d9"
ACCENT_LIGHT = "#a78bfa"
ACCENT_MUTED_BG = "#2a1a4e"
ACCENT_SUBTLE = "#1f1535"

SIDEBAR_ACTIVE_BG = "#251a45"
SIDEBAR_HOVER_BG = "#1a1a30"
SIDEBAR_ACTIVE_BORDER = "#8b5cf6"

GREEN = "#10b981"
AMBER = "#f59e0b"
RED = "#ef4444"

RADIUS_SM = "6px"
RADIUS_MD = "10px"
RADIUS_LG = "12px"

FONT_FAMILY = '"Segoe UI Variable", "Segoe UI", "SF Pro Display", system-ui, sans-serif'

PALETTE = [
    "#7c3aed",
    "#2563eb",
    "#10b981",
    "#f59e0b",
    "#ef4444",
    "#ec4899",
    "#06b6d4",
    "#84cc16",
]

# Legacy aliases used across pages
BG_CARD_LEGACY = BG_CARD
CARD_RADIUS = RADIUS_MD


def page_title_stylesheet() -> str:
    return f"""
        QLabel {{
            font-size: 26px;
            font-weight: 600;
            color: {TEXT_BRIGHT};
            background: transparent;
            letter-spacing: -0.3px;
        }}
    """


def page_subtitle_stylesheet() -> str:
    return f"""
        QLabel {{
            font-size: 14px;
            color: {TEXT_SECONDARY};
            background: transparent;
        }}
    """


def muted_label_stylesheet(*, size: int = 13, weight: int = 400) -> str:
    return (
        f"font-size: {size}px; font-weight: {weight}; "
        f"color: {TEXT_SECONDARY}; background: transparent;"
    )


def separator_stylesheet(*, margin_h: int = 0) -> str:
    margin = f" margin: 0 {margin_h}px;" if margin_h else ""
    return f"QFrame {{ color: {BORDER_SUBTLE}; max-height: 1px;{margin} }}"


def scroll_area_stylesheet() -> str:
    return "QScrollArea { border: none; background: transparent; }"


def transparent_widget_stylesheet() -> str:
    return "background: transparent;"


def card_frame_stylesheet(object_name: str, *, border_left: str | None = None) -> str:
    left = f"border-left: 3px solid {border_left};" if border_left else ""
    return f"""
        QFrame#{object_name} {{
            background-color: {BG_CARD};
            border: 1px solid {BORDER_SUBTLE};
            border-radius: {RADIUS_MD};
            {left}
        }}
    """


def get_stylesheet() -> str:
    return f"""
    QMainWindow {{
        background-color: {BG_APP};
    }}

    QWidget {{
        background-color: {BG_APP};
        color: {TEXT_PRIMARY};
        font-family: {FONT_FAMILY};
        font-size: 13px;
    }}

    QStatusBar {{
        background-color: {BG_SURFACE};
        color: {TEXT_MUTED};
        border-top: 1px solid {BORDER_SUBTLE};
        font-size: 12px;
        padding: 4px 16px;
    }}

    QLabel {{
        background: transparent;
    }}

    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_SM};
        padding: 8px 12px;
        font-size: 13px;
        selection-background-color: {ACCENT};
        selection-color: white;
    }}

    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border: 1px solid {BORDER_FOCUS};
    }}

    QLineEdit:disabled, QTextEdit:disabled {{
        color: {TEXT_MUTED};
        background-color: {BG_ELEVATED};
    }}

    QComboBox {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_SM};
        padding: 6px 12px;
        font-size: 13px;
        min-height: 20px;
    }}

    QComboBox:hover {{
        background-color: {BG_INPUT_HOVER};
        border-color: {BORDER_DEFAULT};
    }}

    QComboBox:focus {{
        border: 1px solid {BORDER_FOCUS};
    }}

    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {BG_ELEVATED};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_SM};
        padding: 4px;
        selection-background-color: {ACCENT};
        selection-color: white;
        outline: none;
    }}

    QSpinBox {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_SM};
        padding: 6px 12px;
        font-size: 13px;
    }}

    QSpinBox:hover {{
        background-color: {BG_INPUT_HOVER};
    }}

    QSpinBox:focus {{
        border: 1px solid {BORDER_FOCUS};
    }}

    QSpinBox::up-button, QSpinBox::down-button {{
        border: none;
        width: 18px;
        background: transparent;
    }}

    QPushButton {{
        background-color: {BG_INPUT};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_SM};
        padding: 8px 16px;
        font-size: 13px;
        font-weight: 600;
    }}

    QPushButton:hover {{
        background-color: {BG_INPUT_HOVER};
        border-color: {BORDER_DEFAULT};
    }}

    QPushButton:pressed {{
        background-color: {BG_ELEVATED};
    }}

    QPushButton:disabled {{
        color: {TEXT_MUTED};
        background-color: {BG_ELEVATED};
        border-color: {BORDER_SUBTLE};
    }}

    QPushButton#primaryButton {{
        background-color: {ACCENT};
        color: white;
        border: none;
    }}

    QPushButton#primaryButton:hover {{
        background-color: {ACCENT_HOVER};
    }}

    QPushButton#primaryButton:disabled {{
        background-color: {BG_INPUT_HOVER};
        color: {TEXT_MUTED};
    }}

    QCheckBox {{
        font-size: 13px;
        color: {TEXT_PRIMARY};
        spacing: 8px;
    }}

    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border: 2px solid {BORDER_DEFAULT};
        border-radius: 4px;
        background-color: {BG_INPUT};
    }}

    QCheckBox::indicator:hover {{
        border-color: {ACCENT_LIGHT};
    }}

    QCheckBox::indicator:checked {{
        background-color: {ACCENT};
        border-color: {ACCENT};
    }}

    QProgressBar {{
        background-color: {BG_INPUT};
        border: none;
        border-radius: 4px;
        min-height: 6px;
        max-height: 6px;
    }}

    QProgressBar::chunk {{
        background-color: {ACCENT};
        border-radius: 4px;
    }}

    QTableWidget {{
        background-color: transparent;
        border: none;
        font-size: 12px;
        color: {TEXT_PRIMARY};
        gridline-color: transparent;
    }}

    QTableWidget::item {{
        padding: 8px 6px;
        border-bottom: 1px solid {BORDER_SUBTLE};
    }}

    QHeaderView::section {{
        background-color: transparent;
        color: {TEXT_SECONDARY};
        font-weight: 600;
        font-size: 11px;
        text-transform: uppercase;
        padding: 8px 6px;
        border: none;
        border-bottom: 1px solid {BORDER_DEFAULT};
    }}

    QGroupBox {{
        font-size: 14px;
        font-weight: 600;
        color: {TEXT_BRIGHT};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_MD};
        margin-top: 12px;
        padding-top: 16px;
        background-color: {BG_CARD};
    }}

    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 8px;
    }}

    QListWidget {{
        background-color: {BG_ELEVATED};
        border: 1px solid {BORDER_SUBTLE};
        border-radius: {RADIUS_SM};
        color: {TEXT_PRIMARY};
        padding: 4px;
    }}

    QListWidget::item {{
        padding: 6px 8px;
        border-radius: 4px;
    }}

    QListWidget::item:selected {{
        background-color: {ACCENT_SUBTLE};
        color: {ACCENT_LIGHT};
    }}

    QScrollBar:vertical {{
        background-color: transparent;
        width: 10px;
        border: none;
        margin: 4px 2px;
    }}

    QScrollBar::handle:vertical {{
        background-color: {BORDER_DEFAULT};
        border-radius: 5px;
        min-height: 32px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {TEXT_MUTED};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    QScrollBar:horizontal {{
        background-color: transparent;
        height: 10px;
        border: none;
        margin: 2px 4px;
    }}

    QScrollBar::handle:horizontal {{
        background-color: {BORDER_DEFAULT};
        border-radius: 5px;
        min-width: 32px;
    }}

    QScrollBar::handle:horizontal:hover {{
        background-color: {TEXT_MUTED};
    }}

    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    QToolTip {{
        background-color: {BG_ELEVATED};
        color: {TEXT_PRIMARY};
        border: 1px solid {BORDER_DEFAULT};
        border-radius: {RADIUS_SM};
        padding: 6px 10px;
        font-size: 12px;
    }}
    """
