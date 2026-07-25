"""Base page widget."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from frontend.theme import (
    page_subtitle_stylesheet,
    page_title_stylesheet,
    separator_stylesheet,
)


class PageWidget(QWidget):
    """Base class for all navigation pages."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._title = title
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 36, 36, 36)
        layout.setSpacing(0)

        header = QLabel(self._title)
        header.setStyleSheet(page_title_stylesheet())

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(separator_stylesheet())

        content = QWidget()
        content.setObjectName("pageContent")
        content.setStyleSheet("QWidget#pageContent { background-color: transparent; }")
        content_layout = QVBoxLayout(content)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.setSpacing(12)

        label = QLabel(f"Welcome to {self._title}")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(page_subtitle_stylesheet())

        content_layout.addWidget(label)

        layout.addWidget(header)
        layout.addSpacing(10)
        layout.addWidget(separator)
        layout.addSpacing(28)
        layout.addWidget(content, 1)
