"""Base page widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class PageWidget(QWidget):
    """Base class for all navigation pages."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(0)

        header = QLabel(self._title)
        header.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: 600;
                color: #f0f0ff;
                padding-bottom: 4px;
            }
        """)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("QFrame { color: #2a2a44; max-height: 1px; }")

        content = QWidget()
        content.setObjectName("pageContent")
        content.setStyleSheet("QWidget#pageContent { background-color: transparent; }")
        content_layout = QVBoxLayout(content)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        label = QLabel(f"Welcome to {self._title}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("""
            QLabel {
                font-size: 16px;
                color: #8888bb;
            }
        """)
        content_layout.addWidget(label)

        layout.addWidget(header)
        layout.addSpacing(8)
        layout.addWidget(separator)
        layout.addSpacing(24)
        layout.addWidget(content, 1)
