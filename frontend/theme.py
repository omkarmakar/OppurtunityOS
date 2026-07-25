"""Dark theme QSS stylesheet for OpportunityOS."""

DARK_THEME = """
    QMainWindow {
        background-color: #0f0f1a;
    }

    QWidget {
        background-color: #0f0f1a;
        color: #e4e4f0;
        font-family: "Segoe UI", "SF Pro Display", "Helvetica Neue", Arial, sans-serif;
    }

    QStatusBar {
        background-color: #12121e;
        color: #8888bb;
        border-top: 1px solid #2a2a44;
        font-size: 12px;
        padding: 2px 12px;
    }

    QScrollBar:vertical {
        background-color: #1a1a2e;
        width: 8px;
        border: none;
    }

    QScrollBar::handle:vertical {
        background-color: #3a3a5e;
        border-radius: 4px;
        min-height: 30px;
    }

    QScrollBar::handle:vertical:hover {
        background-color: #5a5a7e;
    }

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
"""


def get_stylesheet() -> str:
    return DARK_THEME
