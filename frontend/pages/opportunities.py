"""Opportunities page."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from frontend.pages.base import PageWidget


class OpportunitiesPage(PageWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Opportunities", parent)
